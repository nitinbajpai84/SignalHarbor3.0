"""BC-5: the built-in runner. Contracts (SHAPES 3) in, bronze, silver, gold and a run log (SHAPES 4) out. Counts only, never rows."""
import base64
import binascii
import calendar
import fnmatch
import json
import logging
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from sh_platform.build import contracts, schedule, transforms
from sh_platform.graph.build_nodes import record_commit
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CrossCompanyError, valid_module_id
from sh_platform.context_docs.reader import Refusal, ext_of
from sh_platform.profile import store
from sh_platform.profile.view import sees_source
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.tabular import MAX_FILE_BYTES, read_table
from sh_platform.warehouse import _q, counts_only, load_bronze, open_company, refresh_readonly_copy

log = logging.getLogger(__name__)
router = APIRouter()
NOT_YET = contracts.NOT_YET
FORBIDDEN = "Your company space could not be opened. Please ask your administrator."


def _company(request: Request):
    try:
        return _plane(request), _viewer(request)
    except (PermissionError, CrossCompanyError):
        raise HTTPException(403, FORBIDDEN) from None


def _hidden_sources(plane, viewer) -> set[str]:
    """Source ids whose profile system the viewer may not see (module 2's source rule)."""
    return {contracts.slug(((i.get("name") or {}).get("value")) or k) for k, i in (store.raw(plane).get("systems") or {}).items()
            if isinstance(i, dict) and not sees_source(i, viewer)}


def _mask_runs(plane, viewer, runs: list[dict]) -> list[dict]:
    """A set-aside line for a check on a measure the viewer may not see loses its rule and field; the count stays (SF17b)."""
    from sh_platform.build import blueprint as B
    bp = contracts._read(plane, "build", "blueprint.json")
    hidden = B._hidden(bp, viewer) if all(k in bp for k in ("lineage", "access")) else set()
    if not hidden:
        return runs
    gone = {x["measure"].lower() for x in bp["lineage"] if str(x.get("mart", "")).split(".")[1:2] and x["mart"].split(".")[1] in hidden} | hidden
    mask = lambda t: str(t).partition(":")[0].strip().lower() in gone or str(t).startswith(tuple(f"gold.{h}:" for h in hidden))  # noqa: E731
    cant = "a check you cannot see"
    return [{**r, "quarantined": [{"rule": "", "field": "", "count": q.get("count"), "masked": True} if mask(q.get("rule", "")) else q for q in r.get("quarantined") or []],
             "rules": [{**x, "rule": cant} if mask(x.get("rule", "")) else x for x in r.get("rules") or []],
             "not_run": [cant if mask(x) else x for x in r.get("not_run") or []],
             "notes": [cant if mask(x) else x for x in r.get("notes") or []]} for r in runs]


def _runs_path(plane) -> Path:
    return plane.path("warehouse", "runs.json")


def read_runs(plane) -> list[dict]:
    try:
        return (read_json_strict(_runs_path(plane), dict) or {}).get("runs", [])
    except (OSError, ValueError):
        log.warning("run log could not be read")
        return []


def _deadline(spec: str, d: date) -> datetime | None:
    """'D+2 09:00' is that time on day d plus 2; 'WD8' is the end of the 8th working day (Mon to Fri) of the month after d's month."""
    m = re.fullmatch(r"D\+(\d+)\s+(\d{1,2}):(\d{2})", (spec or "").strip())
    if m:
        return datetime.combine(d + timedelta(days=int(m[1])), time(int(m[2]), int(m[3])))
    m = re.fullmatch(r"WD(\d+)", (spec or "").strip())
    if not m or int(m[1]) < 1:
        return None
    y, mo = (d.year + (d.month == 12), d.month % 12 + 1)
    days = [date(y, mo, i) for i in range(1, calendar.monthrange(y, mo)[1] + 1) if date(y, mo, i).weekday() < 5]
    return datetime.combine(days[int(m[1]) - 1], time(23, 59)) if int(m[1]) <= len(days) else None


class Blocked(Exception):
    """A run that must wait; the message says for what, in plain words."""


def _landed(plane, pattern: str) -> Path | None:
    swap = {".csv": ".xlsx", ".xlsx": ".csv"}.get(Path(pattern).suffix.lower())  # a file may land as either kind
    files = [p for pat in (pattern, str(Path(pattern).with_suffix(swap)) if swap else pattern) for p in plane.area("landing").glob(pat) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def _marts(bp: dict, source: str) -> tuple[dict[str, list[tuple[str, str, str]]], set[str], list[str]]:
    """{table: [(column, field, op)]}, the restricted tables, and what cannot be built."""
    tables: dict[str, list] = {}
    notes: list[str] = []
    for ln in bp.get("lineage", []):
        if contracts.slug(ln.get("source")) != source:
            continue
        parts = str(ln.get("mart", "")).split(".")
        op = transforms.op_of(ln.get("transform", ""))
        if len(parts) != 3 or parts[0] != "gold" or not op or not ln.get("fields"):
            notes.append(f"{ln.get('measure')}: {NOT_YET}")
            continue
        tables.setdefault(parts[1], []).append((parts[2], ln["fields"][0], op))
    restricted = {a["mart"].split(".")[1] for a in bp.get("access", []) if a.get("may_see") is not None and str(a.get("mart", "")).count(".") >= 1}
    return tables, restricted, notes


def _rules(con, bp: dict, c: dict, typed, run_id: str) -> tuple[list[dict], list[str], bool, list[dict]]:
    """Rule results, rules that could not run, whether a block rule failed, and what went to quarantine (SF12: the offending rows of a
    failed block rule are copied to quarantine.<source>, emptied at the start of each run so it holds this run's rows only)."""
    out, not_run, block, held = [], [], False, []
    con.execute("create schema if not exists quarantine")
    con.execute(f"drop table if exists quarantine.{c['source']}")
    for rid in c["rules"]:
        measure, _, text = rid.partition(":")
        fields = [f for ln in bp.get("lineage", []) if ln.get("measure") == measure for f in ln.get("fields", [])]
        keys = [k for f in bp.get("model", {}).get("facts", []) if measure in f.get("measures", []) for k in f.get("keys", [])]
        r = transforms.check_rule(con, c["source"], text, fields, keys, typed)
        if r is None:
            not_run.append(rid)
            continue
        out.append({"rule": rid, "passed": r[0], "count": r[1]})
        sev = next((x.get("severity") for x in bp.get("rules", []) if x.get("measure") == measure and x.get("rule") == text), "block")
        if not r[0] and sev == "block":
            block = True
            held += transforms.quarantine(con, c["source"], rid, text, fields, keys, typed, run_id)
    return out, not_run, block, held


def run_pipeline(plane, c: dict) -> dict:
    src, started, run_id = c["source"], datetime.now(timezone.utc), uuid.uuid4().hex
    runs = read_runs(plane)
    waiting = [d for d in c["depends_on"] if not schedule.ok_today(runs, d, started.date())]
    if waiting:
        raise Blocked(f"{src} waits for {', '.join(waiting)}, which has no successful run today. Run that first.")
    bp = contracts._read(plane, "build", "blueprint.json")
    f = _landed(plane, c["pattern"])
    if f is None:
        raise FileNotFoundError("No file has landed for this source yet.")
    arrived = datetime.fromtimestamp(f.stat().st_mtime)
    load_bronze(plane, src, f.name)
    tables, restricted, notes = _marts(bp, src)
    con = open_company(plane)
    try:
        typed = transforms.build_silver(con, src)
        have = {col for col, _ in typed}
        schema_ok = all(s["field"] in have for s in c["schema"])
        rules, not_run, block, held = _rules(con, bp, c, typed, run_id)
        if restricted:
            con.execute("attach '" + str(plane.path("warehouse", "restricted.duckdb")).replace("'", "''") + "' as r")
            con.execute("create schema if not exists r.gold")
        built = [t for t, ms in tables.items() if transforms.build_mart(con, src, t, ms, typed, "r" if t in restricted else "")]
        rules += [{"rule": f"gold.{t}: left as it was, no period could be worked out ({NOT_YET})", "passed": False, "count": 0} for t in tables if t not in built]
        dc = next((col for col, t in typed if t == "date"), None)
        d = con.execute(f"select max({_q(dc)}) from silver.{src}").fetchone()[0] if dc else None
    finally:
        con.close()
    rows = counts_only(plane, f"silver.{src}")["rows"]
    refresh_readonly_copy(plane)
    ready = datetime.now(timezone.utc)
    due, sla = _deadline(c["expected"], d or arrived.date()), _deadline(c["sla"], d or arrived.date())
    on_time = bool(due and arrived <= due)
    failed = block or not schema_ok or not rows
    run = {"id": run_id, "source": src, "started": started.isoformat(), "ended": datetime.now(timezone.utc).isoformat(),
           "on_time": on_time, "rows": rows, "schema_ok": schema_ok, "rules": rules, "not_run": not_run, "notes": notes, "quarantined": held,
           "marts_ready": None if failed else ready.isoformat(), "sla_met": None if failed or not sla else ready.replace(tzinfo=None) <= sla,
           "owner": c["owner"], "status": "failed" if failed else "ok" if on_time else "late"}
    with lock_for(_runs_path(plane)):
        write_json_atomic(_runs_path(plane), {"runs": read_runs(plane) + [run]})
    try:  # M4: the pipeline node on the map keeps one commit per run
        record_commit(plane, src, f"run {run['id']}: {run['status']}, {rows} rows", "Builder")
    except (OSError, ValueError):
        log.warning("commit for %s could not be written", src)
    log.info("run %s of %s: %s", run["id"], src, run["status"])
    return run


@router.get("/api/company/build/pipelines")
def get_api_company_build_pipelines(request: Request):
    plane, viewer = _company(request)
    no = _hidden_sources(plane, viewer)
    runs, bp = read_runs(plane), contracts._read(plane, "build", "blueprint.json")
    hidden = {f"gold.{a['mart'].split('.')[1]}" for a in bp.get("access", []) if a.get("may_see") is not None and "." in str(a.get("mart"))
              and viewer.name not in a["may_see"]}
    return {"pipelines": [{**c, "marts": [m for m in c["marts"] if m not in hidden],
                           "last_run": next(iter(_mask_runs(plane, viewer, [r for r in reversed(runs) if r["source"] == c["source"]][:1])), None)} for c in contracts.ensure(plane) if c["source"] not in no]}


@router.post("/api/company/build/pipelines/{source}/run")
def post_api_company_build_pipelines_source_run(request: Request, source: str):
    plane, _ = _company(request)
    c = next((c for c in contracts.ensure(plane) if c["source"] == source and valid_module_id(source)), None)
    if c is None:
        raise HTTPException(404, "There is no pipeline for this source.")
    try:
        return run_pipeline(plane, c)
    except (FileNotFoundError, Blocked) as e:
        raise HTTPException(409, str(e)) from None
    except (ValueError, OSError) as e:  # a file that cannot be loaded; the message holds no row
        raise HTTPException(422, str(e)) from None


@router.get("/api/company/build/runs")
def get_api_company_build_runs(request: Request):
    plane, viewer = _company(request)
    no = _hidden_sources(plane, viewer)
    live = {c["source"] for c in contracts.ensure(plane)} - no  # a run of a source with no contract any more is history for nobody
    return {"runs": _mask_runs(plane, viewer, [r for r in read_runs(plane) if r["source"] in live])}


def _late_entry(plane, c: dict, now: datetime) -> None:
    """Ops sees a source that is past its time with nothing landed: a run entry with no rows."""
    run = {"id": uuid.uuid4().hex, "source": c["source"], "started": now.isoformat(), "ended": now.isoformat(), "on_time": False, "rows": 0,
           "schema_ok": False, "rules": [], "not_run": [], "notes": [schedule.LATE_NOTE], "marts_ready": None, "sla_met": None,
           "owner": c["owner"], "status": "late"}
    with lock_for(_runs_path(plane)):
        write_json_atomic(_runs_path(plane), {"runs": read_runs(plane) + [run]})


@router.get("/api/company/build/schedule")
def get_api_company_build_schedule(request: Request):
    plane, _ = _company(request)
    now, runs = datetime.now(timezone.utc), read_runs(plane)
    return {"date": now.date().isoformat(), "plan": [{"source": c["source"], "expected": c["expected"],
            "state": schedule.state_of(c, runs, now, _landed(plane, c["pattern"]) is not None)} for c in contracts.ensure(plane)]}


@router.post("/api/company/build/pipelines/run-due")
def post_api_company_build_pipelines_run_due(request: Request):
    """Every source past its time with no run today, dependencies first. Returns what ran and what was skipped, and why."""
    plane, _ = _company(request)
    now, ran, skipped = datetime.now(timezone.utc), [], []
    cs = contracts.ensure(plane)
    for c in schedule.order(cs):
        runs = read_runs(plane)
        today = schedule.today_runs(runs, c["source"], now.date())
        real = [r for r in today if not schedule.is_placeholder(r)]
        st = schedule.state_of(c, runs, now, _landed(plane, c["pattern"]) is not None)
        if real:
            skipped.append({"source": c["source"], "reason": f"Already ran today ({real[-1]['status']})."})
        elif st == "waiting":
            skipped.append({"source": c["source"], "reason": "Not due yet."})
        elif st == "late":
            if not today:
                _late_entry(plane, c, now)
            skipped.append({"source": c["source"], "reason": "Late: " + schedule.LATE_NOTE})
        else:
            try:
                ran.append(run_pipeline(plane, c))
            except (FileNotFoundError, Blocked, ValueError, OSError) as e:
                skipped.append({"source": c["source"], "reason": str(e)})
    if not any(x["reason"] == "Not due yet." for x in skipped):  # 57 C5: the last run of the day is done, the radar scans once
        try:
            from sh_platform.intents import radar
            radar.scan_daily(plane, radar._pack(request))
        except Exception as e:  # noqa: BLE001 - a radar failure never fails the runs
            log.warning("radar daily scan skipped (%s)", type(e).__name__)
    return {"ran": ran, "skipped": skipped}


@router.post("/api/company/build/pipelines/{source}/upload")
async def post_api_company_build_pipelines_source_upload(request: Request, source: str):
    """A CSV or XLSX dropped for one source lands in the landing zone as the contract's pattern with today's date. The file travels as base64
    in a JSON body ({filename, data}), the same as the other upload routes; size and type are read_table's checks."""
    plane, _ = _company(request)
    c = next((c for c in contracts.ensure(plane) if c["source"] == source and valid_module_id(source)), None)
    if c is None:
        raise HTTPException(404, "There is no pipeline for this source.")
    limit = MAX_FILE_BYTES * 4 // 3 + 64 * 1024
    raw, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"That file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB. Please send a smaller one.")
        raw.append(chunk)
    try:
        body = json.loads(b"".join(raw))
        name, data = body["filename"], base64.b64decode(str(body.get("data", "")), validate=True)
        assert isinstance(name, str)
    except (ValueError, KeyError, TypeError, AssertionError, binascii.Error):
        raise HTTPException(400, "Please choose a file to send.") from None
    kind = ext_of(name)
    if kind not in ("csv", "xlsx"):
        raise HTTPException(422, "Please send an Excel (.xlsx) or CSV file.")
    try:
        header, rows = await run_in_threadpool(read_table, name, data)
    except Refusal as e:
        raise HTTPException(422, str(e)) from None
    stem = Path(c["pattern"]).with_suffix("." + kind).name
    orig = re.sub(r"[^\w.\- ()]+", "_", Path(name.replace("\\", "/")).name).strip(". ") or "file"
    # keep the sender's file name when the pipeline pattern already accepts it, else wrap it in the pattern; never overwrite a different file
    fname = orig if fnmatch.fnmatch(orig, stem) else stem.replace("*", "_" + Path(orig).stem, 1)
    try:
        dest = plane.path(c["lands_at"], fname)
        dest.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while dest.exists() and dest.read_bytes() != data:
            n += 1
            fname = f"{Path(fname).stem.rsplit('~', 1)[0]}~{n}{Path(fname).suffix}"
            dest = plane.path(c["lands_at"], fname)
        dest.write_bytes(data)
    except (OSError, CrossCompanyError, ValueError):
        raise HTTPException(422, "That file could not be saved.") from None
    log.info("upload for %s landed as %s (%s rows)", source, fname, len(rows))
    return {"source": source, "file": fname, "rows": len(rows)}
