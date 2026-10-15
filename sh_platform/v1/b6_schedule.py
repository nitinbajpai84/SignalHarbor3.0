"""B4: the scheduler and the Airflow export. A stdlib thread checks every minute and runs live the plans whose schedule is due;
`on_arrival(plane, source_code)` is called by intake after a file load. Never two runs of one project at once (b6_run refuses the second)."""
from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timedelta

from sh_platform.v1 import b6_run as R
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_STOP = threading.Event()


def _at(s: dict) -> tuple[int, int]:
    h, m = (str((s or {}).get("at") or "06:00").split(":") + ["0"])[:2]
    return int(h), int(m)


def _weekday(s: dict) -> int:
    d = s.get("day")
    return d % 7 if isinstance(d, int) else _DAYS.index(str(d)[:3].lower()) if str(d)[:3].lower() in _DAYS else 0


def _dom(s: dict) -> int:
    m = re.match(r"\s*(\d+)", str(s.get("day") or ""))  # V6: the design pack words it "8th working day of each month"; the number leads
    return min(max(int(m.group(1)) if m else 1, 1), 28)


def last_slot(sched: dict, now: datetime) -> datetime | None:
    """The newest moment at or before `now` when this schedule says "run"; None for on_arrival or an unknown frequency."""
    freq = (sched or {}).get("freq")
    h, m = _at(sched)
    today = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if freq == "daily":
        return today if today <= now else today - timedelta(days=1)
    if freq == "weekly":
        s = today - timedelta(days=(now.weekday() - _weekday(sched)) % 7)
        return s if s <= now else s - timedelta(days=7)
    if freq == "monthly":
        s = today.replace(day=_dom(sched))
        return s if s <= now else (s.replace(day=1) - timedelta(days=1)).replace(day=_dom(sched), hour=h, minute=m)
    return None


def is_due(plan: dict, last_live: datetime | None, now: datetime) -> bool:
    """Due when the newest slot has passed and no live run has started since it."""
    if plan.get("state") not in R.LIVE_OK:
        return False
    slot = last_slot(plan.get("schedule") or {}, now)
    return slot is not None and (last_live is None or last_live < slot)


def _last_live(plane, pid: str) -> datetime | None:
    for r in R.runs(plane, pid, 50):
        if r.get("mode") == "live":
            return datetime.fromisoformat(r["started"]).astimezone().replace(tzinfo=None)
    return None


def _projects(plane) -> list[str]:
    b = plane.path("build")
    return sorted(p.name for p in b.iterdir() if p.is_dir() and any(p.glob("plan-v*.json"))) if b.exists() else []


def tick(plane, now: datetime | None = None) -> list[dict]:
    """Run every due plan of this company once, live. Returns the run records. `now` is local server time."""
    now = now or datetime.now()
    out = []
    for pid in _projects(plane):
        try:
            plan = R.latest_plan(plane, pid, live=True)
            if plan and is_due(plan, _last_live(plane, pid), now):
                out.append(R.run(plane, pid, "live", plan, by="scheduler", trigger="schedule"))
        except R.Refused as e:
            log.info("scheduled run of %s skipped: %s", pid, e.message)
        except Exception:
            log.exception("scheduled run of %s failed", pid)
    return out


def on_arrival(plane, source_code: str) -> list[dict]:
    """Intake calls this after a file from `source_code` has loaded: runs the on_arrival plans that use that source."""
    out = []
    for pid in _projects(plane):
        try:
            plan = R.latest_plan(plane, pid, live=True)
            if (plan and plan.get("state") in R.LIVE_OK and (plan.get("schedule") or {}).get("freq") == "on_arrival"
                    and any(s.get("code") == source_code for s in plan.get("sources") or [])):
                out.append(R.run(plane, pid, "live", plan, by="file arrival", trigger="file_arrived"))
        except R.Refused as e:
            log.info("on-arrival run of %s skipped: %s", pid, e.message)
        except Exception:
            log.exception("on-arrival run of %s failed", pid)
    return out


def start(planes, interval: float = 60.0) -> threading.Thread:
    """Start the scheduler thread. `planes` is a callable returning the company planes to check. Stop with stop().
    Called once at server start, so it also puts the warehouse in server mode (one shared connection per company file)."""
    wh.serve()
    _STOP.clear()

    def loop() -> None:
        while not _STOP.wait(interval):
            try:
                for plane in planes():
                    # W3: through the job queue. Simple mode runs it here, as before; production hands it to a worker (one tick per company per minute)
                    from sh_platform.jobs import handlers as H, queue
                    queue().submit("b6.tick", H.payload_of(plane), key=H.minute_key("b6.tick", plane))
            except Exception:
                log.exception("scheduler pass failed")

    t = threading.Thread(target=loop, name="b6-scheduler", daemon=True)
    t.start()
    return t


def stop() -> None:
    _STOP.set()
    wh.release()


# ---- Airflow ------------------------------------------------------------------------------------------------------------------

def _cron(s: dict) -> str | None:
    h, m = _at(s)
    f = (s or {}).get("freq")
    return (f"{m} {h} * * *" if f == "daily" else f"{m} {h} * * {(_weekday(s) + 1) % 7}" if f == "weekly"
            else f"{m} {h} {_dom(s)} * *" if f == "monthly" else None)


def slug_of(plane, pid: str) -> str:
    title = pid
    try:
        from sh_platform.v1 import p1_project
        title = p1_project.read(plane, pid).get("title") or pid
    except Exception:
        pass
    return re.sub(r"[^a-z0-9]+", "_", f"{title}_{pid}".lower()).strip("_")[:60]


def _replace_sql(sql: str) -> str:
    """The plan's CREATE TABLE AS made re-runnable (create or replace); INSERT statements stay as they are."""
    return re.sub(r"(?is)^\s*create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?", "create or replace table ", sql.strip().rstrip(";"), count=1)


def airflow_dag(plane, pid: str, plan: dict | None = None) -> str:
    """Python text of an Airflow DAG: one task per table, same dependencies, same schedule. For the client deployment; never run here."""
    plan = plan or R.latest_plan(plane, pid, live=True)
    if not plan:
        raise R.Refused("This project has no build plan yet.", 404)
    sched = plan.get("schedule") or {}
    names = [t["name"] for t in plan.get("tables", [])]
    on_arrival = "; on_arrival plans are triggered by the file load, not by time" if sched.get("freq") == "on_arrival" else ""
    lines = [f'"""Generated by Signal Harbor for project {pid}, plan version {plan["version"]}. Do not edit; regenerate from the plan."""',
             "import os", "from datetime import datetime", "", "import duckdb", "from airflow import DAG", "from airflow.operators.python import PythonOperator", "",
             "WAREHOUSE = os.environ['SH_WAREHOUSE']  # path to the company warehouse at the client", "", "",
             "def build(sql):", "    if not sql:", "        return  # bronze: filled by file loads",
             "    con = duckdb.connect(WAREHOUSE)", "    try:", "        con.execute(sql)", "    finally:", "        con.close()", "",
             f"CRON = {_cron(sched)!r}  # {sched.get('freq', 'manual')}{on_arrival}", "",
             f"with DAG({slug_of(plane, pid)!r}, start_date=datetime(2026, 1, 1), schedule=CRON, catchup=False) as dag:"]
    for t in plan.get("tables", []):
        sql = _replace_sql(t["sql"]) if (t.get("sql") or "").strip().lower().startswith("create") else (t.get("sql") or "")
        lines.append(f"    {t['name']} = PythonOperator(task_id={t['name']!r}, python_callable=build, op_args=[{sql!r}])")
    for t in plan.get("tables", []):
        for d in t.get("depends_on") or []:
            if d in names:
                lines.append(f"    {d} >> {t['name']}")
    return "\n".join(lines) + "\n"


def export_airflow(plane, pid: str) -> str:
    """Write the DAG to data/<company>/airflow/<project_slug>.py; returns the file path."""
    text = airflow_dag(plane, pid)
    f = plane.path("airflow", slug_of(plane, pid) + ".py")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return str(f)
