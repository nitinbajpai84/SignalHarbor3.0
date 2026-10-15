"""B4: run a build plan on the company warehouse. Tables run in dependency order; each step builds `<table>__next` and swaps it in
one transaction, so a failed step leaves the previous table untouched and stops the run. Sandbox runs use a copy of the warehouse
(`warehouse/sandbox.duckdb`); live runs need an approved plan. Run log: `build/<project_id>/runs.jsonl`.
Plan files are written by card B2 (`build/<project_id>/plan-v<n>.json`); this module only reads them, and moves `state` to built/live."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from contextlib import suppress
from datetime import datetime, timezone

import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from sh_platform.jsonfile import lock_for, read_json_strict
from sh_platform.v1 import run_log, wh
from sh_platform.v1.b6_plan import _BAD as _BAD_NODES

log = logging.getLogger(__name__)
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,100}$")
_RUNNING: set[str] = set()
_GUARD = threading.Lock()
_SANDBOX = threading.Lock()  # ponytail: one sandbox file per company, so sandbox runs take turns; per-project files if that queues
LIVE_OK = {"approved", "built", "live"}


class Refused(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.message, self.status = message, status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dir(plane, pid: str):
    if not isinstance(pid, str) or not _ID.match(pid):
        raise Refused("There is no such project.", 404)
    return plane.path("build", pid)


# ---- plans and log ------------------------------------------------------------------------------------------------------------

def plan_file(plane, pid: str, version: int):
    return _dir(plane, pid) / f"plan-v{int(version)}.json"


def latest_plan(plane, pid: str, live: bool = False) -> dict | None:
    """The newest plan version of the project, or None. With live=True the newest approved/built/live version: a later version
    that is only proposed (a chat change waiting for the head of data) must not stop a live run or the schedule."""
    found = sorted(((int(m.group(1)), p) for p in _dir(plane, pid).glob("plan-v*.json") if (m := re.fullmatch(r"plan-v(\d+)\.json", p.name))),
                   reverse=True)
    plans = (read_json_strict(p, dict) for _, p in found)
    if not live:
        return next(plans, None)
    first = None
    for pl in plans:
        first = first or pl
        if pl.get("state") in LIVE_OK:
            return pl
    return first  # none approved: the caller refuses with its own words


def runs(plane, pid: str, limit: int = 20) -> list[dict]:
    """Newest first."""
    f = _dir(plane, pid) / "runs.jsonl"
    if not f.exists():
        return []
    out = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out[::-1][:limit]


def _log(plane, pid: str, rec: dict) -> None:
    f = _dir(plane, pid) / "runs.jsonl"
    with lock_for(f):
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(rec) + "\n")


def _move(plane, pid: str, plan: dict, mode: str, by: str | None) -> None:
    """After a good run: plan state through B2 (logged, NEXT-checked), then the project stage through P1."""
    from sh_platform.v1 import b6_plan as B, p1_project as P1
    steps = (["built"] if plan["state"] == "approved" else []) + (["live"] if mode == "live" else [])
    for st in steps:
        if plan["state"] != st:
            plan["state"] = B.set_state(plane, pid, st, by or "runner", plan["version"])["state"]
    with suppress(P1.Refused):  # a plan can exist without a project record (tests, imports)
        P1.set_stage(plane, pid, "live" if mode == "live" else "built")
    if mode == "live":  # H10: Lumen proposes a starter dashboard in the studio (once; a failure never fails the run)
        try:
            from sh_platform.v1 import b7_studio
            b7_studio.start_starter(plane, pid)
        except Exception:  # noqa: BLE001
            log.exception("could not propose the starter dashboard for %s", pid)


# ---- order and SQL ------------------------------------------------------------------------------------------------------------

def order(plan: dict) -> list[dict]:
    """Plan tables with every table after the ones it depends on (plan order breaks ties). A cycle is refused."""
    by = {t["name"]: t for t in plan.get("tables", [])}
    done: list[dict] = []
    seen: set[str] = set()

    def visit(n: str, path: tuple = ()) -> None:
        if n in seen or n not in by:  # a table outside the plan (silver, bronze loaded elsewhere) is assumed present
            return
        if n in path:
            raise Refused(f"The plan has a loop: {' -> '.join(path + (n,))}. Ask Span to fix the order of the tables.")
        for d in by[n].get("depends_on") or []:
            visit(d, path + (n,))
        seen.add(n)
        done.append(by[n])

    for t in plan.get("tables", []):
        visit(t["name"])
    return done


def _unsafe(sql: str) -> bool:
    """True unless the SQL is ONE create or insert with nothing in it that drops, deletes, updates, copies or runs a command (CALL, LOAD, PRAGMA).
    Parsed, not matched as text: the same words inside a string ('call') or a name (capital_call) are data (UC6 H1); same check as the plan's."""
    try:
        sts = sqlglot.parse(sql, dialect="duckdb")
    except SqlglotError:
        return True
    return len(sts) != 1 or not isinstance(sts[0], (exp.Create, exp.Insert)) or sts[0].find(*_BAD_NODES) is not None


def build_statements(t: dict, exists: bool, run_id: str | None = None) -> list[str]:
    """Statements that build `<name>__next` from the plan's SQL (CREATE TABLE AS, or INSERT onto a copy of the current table)."""
    name, sql = t["name"], (t.get("sql") or "").strip().rstrip(";").strip()
    if not _NAME.match(name):
        raise ValueError(f"The table name '{name}' is not allowed.")
    if _unsafe(sql):
        raise ValueError("The SQL may only create or add rows; it contains something else.")
    nxt = f"{name}__next"
    ctas = re.match(rf'(?is)^create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?"?{name}"?\s+as\b(.*)$', sql)
    if ctas:
        if run_id and str(t.get("layer") or "").lower() == "gold":  # RUN1: a gold table says which run built it
            return [f"create or replace table {nxt} as select '{run_id}' as run_id, * from ({ctas.group(1).strip()}) rn_src"]
        return [f"create or replace table {nxt} as{ctas.group(1)}"]
    ins = re.match(rf'(?is)^insert\s+into\s+"?{name}"?\b(.*)$', sql)
    if ins:
        if exists:
            base = f"create or replace table {nxt} as select * from {name}"
        else:
            cols = ", ".join(f"{c['name']} {c.get('type') or 'varchar'}" for c in t.get("columns") or [])
            if not cols:
                raise ValueError("The table does not exist yet and the plan lists no columns for it.")
            base = f"create or replace table {nxt} ({cols})"
        return [base, f"insert into {nxt}{ins.group(1)}"]
    raise ValueError(f"The SQL must create or fill the table it is listed under ({name}).")


def _step(con, t: dict, run_id: str | None = None) -> int:
    name, nxt = t["name"], f"{t['name']}__next"
    exists = bool(con.execute("select 1 from information_schema.tables where table_name = ? and table_schema = current_schema()", [name]).fetchone())
    stmts = build_statements(t, exists, run_id)
    con.execute("begin")
    try:
        for s in stmts:
            con.execute(s)
        con.execute(f"drop table if exists {name}")
        con.execute(f"alter table {nxt} rename to {name}")
        n = con.execute(f"select count(*) from {name}").fetchone()[0]
        con.execute("commit")
        return n
    except Exception:
        with suppress(Exception):
            con.execute("rollback")
        raise


# ---- run ----------------------------------------------------------------------------------------------------------------------

def _fresh_sandbox(plane, dst) -> None:
    """Fill `dst` with a copy of the warehouse through DuckDB itself. The server holds evidence.duckdb open (wh.serve) and Windows
    refuses a plain file copy of an open DuckDB file (PermissionError, which once read as "company space could not be opened")."""
    for p in (dst, dst.with_name(dst.name + ".wal")):
        p.unlink(missing_ok=True)
    with wh.connect(plane) as con:
        src = con.execute("select current_database()").fetchone()[0]
        con.execute("detach database if exists rn_sandbox")
        con.execute("attach '{}' as rn_sandbox".format(str(dst).replace("'", "''")))
        try:
            con.execute(f'copy from database "{src}" to rn_sandbox')
        finally:
            con.execute("detach database rn_sandbox")


def _sandbox_con(plane) -> duckdb.DuckDBPyConnection:
    dst = plane.path("warehouse", "sandbox.duckdb")
    try:
        _fresh_sandbox(plane, dst)
    except (OSError, duckdb.IOException) as e:  # a sharing violation (antivirus, a leftover handle): try once more
        log.warning("sandbox copy failed, trying again: %r", e)
        time.sleep(1)
        _fresh_sandbox(plane, dst)
    return duckdb.connect(str(dst))


def run(plane, pid: str, mode: str = "sandbox", plan: dict | None = None, by: str | None = None, trigger: str = "manual", job_id: str | None = None) -> dict:
    """Run the project's newest plan (or the one given). Returns the run record, also appended to runs.jsonl.
    A live run needs an approved plan; two runs of one project never overlap."""
    if mode not in ("sandbox", "live"):
        raise Refused("Choose sandbox or live.", 400)
    plan = plan or latest_plan(plane, pid, live=mode == "live")
    if not plan:
        raise Refused("This project has no build plan yet.", 404)
    if mode == "live" and plan.get("state") not in LIVE_OK:
        raise Refused("The plan is not approved yet. Run it in the sandbox, or ask the head of data to approve it.")
    key = f"{plane.root}|{pid}"
    with _GUARD:
        if key in _RUNNING:
            raise Refused("This project is already running. Please wait for it to finish.")
        _RUNNING.add(key)
    try:
        tables = order(plan)
        rid = run_log.start_run(plane, "pipeline", "test" if mode == "sandbox" else "production", trigger, by, plan_id=pid, pack_version=plan["version"], job_id=job_id)
        rec = {"run_id": rid, "plan_version": plan["version"], "mode": mode, "by": by, "started": _now(), "finished": None,
               "status": "running", "steps": []}
        if mode == "sandbox" and not _SANDBOX.acquire(timeout=120):
            raise OSError("another sandbox run holds the sandbox file")
        try:
            con = _sandbox_con(plane) if mode == "sandbox" else wh.connect(plane)
        except BaseException:
            run_log.finish(plane, rid, "failed")
            if mode == "sandbox":
                _SANDBOX.release()
            raise
        failed = False
        try:
            for t in tables:
                if failed:
                    rec["steps"].append({"table": t["name"], "rows": None, "ms": 0, "status": "not run", "error": None})
                    continue
                if not (t.get("sql") or "").strip():  # bronze: filled by file loads, not by the pipeline
                    rec["steps"].append({"table": t["name"], "rows": None, "ms": 0, "status": "filled by file loads", "error": None})
                    continue
                if t.get("layer") == "silver" and t.get("depends_on") and all(str(d).startswith("bronze_") for d in t["depends_on"]):
                    # UC5: the approved sheet mapping already wrote these rows when the file was loaded (e0c_load); inserting them again from
                    # bronze would duplicate them, and bronze is a catalogue record, not a table the load fills
                    rec["steps"].append({"table": t["name"], "rows": None, "ms": 0, "status": "filled by file loads", "error": None})
                    continue
                t0 = time.perf_counter()
                try:
                    n = _step(con, t, rec['run_id'])
                    rec["steps"].append({"table": t["name"], "rows": n, "ms": round((time.perf_counter() - t0) * 1000), "status": "ok", "error": None})
                except Exception as e:  # a bad statement or missing table: the run stops, earlier results stay
                    msg = str(e).splitlines()[0][:300] if str(e) else e.__class__.__name__
                    log.warning("pipeline step %s failed: %s", t["name"], msg)
                    rec["steps"].append({"table": t["name"], "rows": None, "ms": round((time.perf_counter() - t0) * 1000), "status": "failed",
                                         "error": f"{t['name']} could not be built: {msg}"})
                    failed = True
        finally:
            con.close()
            if mode == "sandbox":
                _SANDBOX.release()
        rec["status"] = "failed" if failed else "ok"
        rec["finished"] = _now()
        for st in rec["steps"]:
            run_log.step(plane, rec["run_id"], st["table"], next((str(t.get("layer")) for t in tables if t["name"] == st["table"] and t.get("layer")), None), st["table"],
                         None, st["rows"], 0, 1 if st["status"] == "ok" else 0, 1 if st["status"] == "failed" else 0, st["error"])
        run_log.finish(plane, rec["run_id"], rec["status"])
        if mode == "live":  # the layer-prefixed names (gold.x) follow the tables this run built
            try:
                from sh_platform.v1 import e0a_catalogue
                e0a_catalogue.refresh_aliases(plane)
            except Exception:  # noqa: BLE001 - the run itself succeeded; the aliases are a convenience
                log.warning("could not refresh the layer views after run %s", rec["run_id"], exc_info=True)
        _log(plane, pid, rec)
        if not failed and plan.get("state") in LIVE_OK:
            _move(plane, pid, plan, mode, by)
        if mode == "live":
            try:
                notify(plane, pid, plan, rec)
            except Exception:
                log.exception("could not write the Action cards for run %s", rec["run_id"])
        return rec
    finally:
        with _GUARD:
            _RUNNING.discard(key)


# ---- cards in Action ----------------------------------------------------------------------------------------------------------

def _user_ids(con, org: str, who: list[str]) -> set[str]:
    out = set()
    for w in who:
        for col in ("id", "external_identity_id", "display_name", "email"):
            r = con.execute(f"select cast(id as varchar) from users where cast(organization_id as varchar) = ? and is_active and cast({col} as varchar) = ?",
                          [org, w]).fetchone()
            if r:
                out.add(r[0])
                break
    return out


def notify(plane, pid: str, plan: dict, rec: dict) -> int:
    """A failed live run: a card for the plan owner. A good one: C3's "refreshed" card for each dashboard of the project
    (cx_share does the audience, the access check and the once-per-run rule). Returns cards written."""
    if rec["status"] == "ok":
        from sh_platform.v1 import cx_share
        rebuilt = {s["table"] for s in rec["steps"] if s["status"] == "ok"}
        made, d = 0, plane.path("consume", pid, "dashboards")
        for f in sorted(d.glob("*.json")) if d.exists() else []:
            dash = read_json_strict(f, dict) or {}
            changed = sum(any(t in (tile.get("sql") or "") for t in rebuilt) for tile in dash.get("tiles") or [])
            made += len(cx_share.notify(plane, pid, f.stem, "refreshed", token=rec["run_id"], tiles_changed=changed)["made"])
        return made
    from sh_platform.v1.e1_write import org_id
    from sh_platform.v1.e5_pulse import _card
    org = org_id(plane)
    title = pid
    with suppress(Exception):
        from sh_platform.v1 import p1_project
        title = p1_project.read(plane, pid).get("title") or pid
    bad = next((s for s in rec["steps"] if s["status"] == "failed"), {})
    head, urgency = f"Pipeline failed · {title}", "needs_me"
    text = f"{bad.get('error', 'A step failed.')} The tables from the last good run are unchanged."
    made = 0
    with wh.connect(plane) as con:
        for uid in _user_ids(con, org, [plan.get("proposed_by")] if plan.get("proposed_by") else []):
            c = _card("*", f"run:{rec['run_id']}", "pipeline", head, text, status_word="Failed", urgency=urgency, action_type="review",
                      action="Open the project", as_of=rec["finished"][:10], link=f"/centre/build/p/{pid}")
            now = wh.now()
            con.execute("insert into pulse_items (id, organization_id, recipient_user_id, exception_id, headline, summary, generated_at, as_of_at, "
                        "urgency, action_type, delivery_status) values (?,?,?,?,?,?,?,?,?,?,'pending')",
                        [wh.new_id(), org, uid, None, head[:250], json.dumps(c), now, now, urgency, c["action_type"]])
            made += 1
    return made
