"""V6-builder: Span the builder. On an approved design pack it connects each source as the pack says, confirms it against the intent's system
record, runs the pipeline on a copy by itself, asks for a benchmark, shows the variance line by line, and then goes live or hands the variance back
to the architect (an agents/handoff item). The architect issues the next pack version; the builder reruns by itself.

The pack is the newest APPROVED plan of the project (b6_plan). A source in it may carry (all optional, nothing is invented when absent):
  arrives {how: upload|sftp|mailbox|sharepoint|database, connector: <c5 id>, file: <name or pattern>, columns: [..], host: <host>}
  fields  [{name, page}]   for a PDF source: the fields marked on the sample
and the plan may carry
  key_figures [{label, table, column, agg: sum|max|min|count, by?: column, match?: [alias], unit?: money|pct}]   what the report is checked on
  benchmark   {portfolio, code, month, names?: {<series key>: <plain name>}, tolerance?: <money tolerance>}
The intent's system record is `build/<pid>/systems.json`: {source code: {name, file, columns, host, how, frequency, owner}}.
The builder's own record is `build/<pid>/builder.json`: {rounds, benchmark, thread, needs, settled}. Figures are Decimal strings, never floats.
Connection checks go through c5_connect (default deny, egress log); no model is called anywhere in this module."""
from __future__ import annotations

import base64
import binascii
import fnmatch
import logging
import re
import threading
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import duckdb

from sh_platform.agents import handoff as H
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import b9_verify as V
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import e1_access, e1_reports, e2_intake, e5_pulse, wh
from sh_platform.v1 import p1_project as P1
from sh_platform.v1.c5_connect import ops as C5
from sh_platform.v1.c5_connect import spec as C5S
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import ARCHITECT, DATA_ENGINEER, seat_of

log = logging.getLogger(__name__)
BUILDER = "Span the builder"
ARCH = "Span the architect"
HOW = {"upload": "an uploaded file", "sftp": "SFTP", "mailbox": "the mailbox", "sharepoint": "SharePoint", "database": "a database"}
CONNECTOR_KINDS = {"sftp": "sftp", "mailbox": "imap", "sharepoint": "graph"}
PCT_TOL = Decimal("0.005")  # two decimals shown; a report rounds the same way
MAX_UPLOAD = 8_000_000
_LOCK = threading.RLock()  # ponytail: one process; a file lock if several web workers start the same round
_SKIP = {"the", "of", "and", "this", "run", "report", "total"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dec(v) -> Decimal:
    return Decimal(str(v))


# ---- records ------------------------------------------------------------------------------------------------------------------------

def _path(plane, pid: str):
    return R._dir(plane, pid) / "builder.json"


def load(plane, pid: str) -> dict:
    try:
        got = read_json_strict(_path(plane, pid), dict)
    except (OSError, ValueError):
        raise Refused(500, "The builder's record could not be read. Please ask your administrator.") from None
    return got or {"rounds": [], "benchmark": None, "thread": [], "needs": [], "settled": [], "not_needed": []}


def _save(plane, pid: str, fn) -> dict:
    path = _path(plane, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(path):
        rec = load(plane, pid)
        fn(rec)
        write_json_atomic(path, rec)
    return rec


def _say(rec: dict, who: str, text: str, evidence: list | None = None) -> None:
    rec["thread"].append({"who": who, "at": _now(), "text": text, "evidence": evidence or []})


def systems_of(plane, pid: str) -> dict:
    try:
        return read_json_strict(R._dir(plane, pid) / "systems.json", dict) or {}
    except (OSError, ValueError):
        return {}


def pack_of(plane, pid: str) -> dict | None:
    """The newest approved plan: the builder always runs the latest approved version, never a draft."""
    for n in reversed(B.versions(plane, pid)):
        p = B.get(plane, pid, n)
        if p and p.get("state") in R.LIVE_OK:
            return p
    return None


# ---- 1. connect each source as the pack says ----------------------------------------------------------------------------------------

def _same(field: str, a, b) -> bool:
    if field == "columns":
        return sorted(str(c).strip().lower() for c in a or []) == sorted(str(c).strip().lower() for c in b or [])
    a, b = str(a or "").strip().lower(), str(b or "").strip().lower()
    return a == b or fnmatch.fnmatch(b, a) or fnmatch.fnmatch(a, b)


def _mismatches(code: str, arr: dict, system: dict, observed: dict, settled: list) -> list[dict]:
    """One entry per field where the records disagree: the pack against the intent's system record, or the pack against what was seen on the connection."""
    out = []
    for f in ("file", "columns", "host"):
        pk, it, ob = arr.get(f), system.get(f), observed.get(f)
        bad = (pk and it and not _same(f, pk, it)) or (pk and ob and not _same(f, pk, ob)) or (not pk and it and ob and not _same(f, it, ob))
        if bad and f"{code}|{f}|{ob}" not in settled:
            out.append({"field": f, "pack": pk, "intent": it, "seen": ob})
    return out


def _connect(plane, src: dict, system: dict, settled: list, F=None) -> dict:
    code, arr = src["code"], src.get("arrives") or {}
    how = arr.get("how") or "upload"
    c = {"code": code, "name": src.get("name") or system.get("name") or code, "kind": src.get("kind"), "how": how, "how_words": HOW.get(how, how), "status": "connected",
         "detail": "", "owner": src.get("owner") or system.get("owner"), "seen": {}, "mismatches": [], "from_intent": bool(system)}
    seen = c["seen"]
    if how in CONNECTOR_KINDS:  # a c5 connector: test (read only), then what would arrive
        try:
            spec = C5S.get(plane, arr.get("connector"))
        except L.Refused:
            return {**c, "status": "failed", "detail": "The connection named in the pack is not set up yet."}
        if spec.get("kind") != CONNECTOR_KINDS[how]:
            return {**c, "status": "failed", "detail": f"The connection named in the pack is not a {HOW[how]} connection."}
        t = C5.test(plane, spec, F)
        if not t["ok"]:
            return {**c, "status": "failed", "detail": t["message"]}
        names = [i["name"] for i in C5.dry_run(plane, spec, F).get("would_arrive", [])]
        seen.update(host=spec.get("host"), file=names[0] if names else None)
        c["detail"] = f"Reused the connection already set up. {len(names)} file{'s' if len(names) != 1 else ''} waiting."
    elif how == "database":
        return {**c, "status": "failed", "detail": "Database connections are not set up in this product yet. Ask the data team for a file export."}
    elif src.get("kind") == "unstructured":  # PDF statements: some landed, and the fields marked on the sample
        docs, marked = e2_intake.listing(plane), src.get("fields") or []
        if not docs or not marked:
            return {**c, "status": "needs_sample", "detail": "No statement has been loaded yet." if not docs else "No fields are marked on a sample statement yet."}
        c["detail"] = f"Reading {len(marked)} marked field{'s' if len(marked) != 1 else ''} from each statement ({len(docs)} on file for the company)."
    else:  # an uploaded file: the sample must have landed
        files = L.listing(plane)["by_source"].get(src.get("landing_source") or code, [])
        if not files:
            return {**c, "status": "needs_sample", "detail": "No sample file has arrived for this source yet."}
        seen.update(file=files[0]["name"])
        c["detail"] = f"{len(files)} file{'s' if len(files) != 1 else ''} landed, latest {files[0]['name']}."
    c["mismatches"] = _mismatches(code, arr, system, seen, settled)
    if c["mismatches"]:
        c["status"] = "mismatch"
    return c


def _connect_marked(plane, src: dict, system: dict, settled: list, F, marks: list) -> dict:
    """_connect, except that a source a person marked "not needed" which still has no sample is shown as that, never as a block (H3)."""
    c = _connect(plane, src, system, settled, F)
    m = next((x for x in marks if x["code"] == src["code"]), None)
    if m and c["status"] == "needs_sample":
        return {**c, "status": "not_needed", "detail": f"Marked not needed by {m['by']}" + (f": {m['reason']}" if m.get("reason") else "") + ". It has no sample file."}
    return c


def _needs(plane, pid: str, conns: list[dict], pack: dict, old: list) -> list[dict]:
    """Only a failed connection or a missing sample reaches a person, as an Action item to the person who can fix it."""
    ppl = P1.read(plane, pid)["people"]
    out = []
    for c in conns:
        if c["status"] not in ("failed", "needs_sample"):
            continue
        kind = "connection_failed" if c["status"] == "failed" else "missing_sample"
        to = [n for n in ([ppl.get("head_of_data")] if kind == "connection_failed" else [c.get("owner") or ppl.get("raiser")]) if n]
        if kind == "connection_failed" and not to:
            to = [r["name"] for r in H.recipients(plane, pid)]
        nid = f"{pid}:{c['code']}:{kind}"
        prev = next((n for n in old if n["id"] == nid), None)
        out.append({"id": nid, "kind": kind, "source": c["code"], "name": c["name"], "to": to, "text": c["detail"], "at": prev["at"] if prev else _now(),
                    "pack_version": pack["version"]})
    return out


# ---- 2. run on a copy ---------------------------------------------------------------------------------------------------------------

def _checks(plane, pid: str) -> dict | None:
    try:
        figs = [f for f in V.figures(plane, pid) if f["check"] != "Not compared"]
    except (Refused, OSError, duckdb.Error):
        return None
    ok = sum(f["check"] == "Match" for f in figs)
    return {"passed": ok, "total": len(figs)}


def _label(pack: dict, table: str) -> str:
    """A table as people say it: its purpose when the pack gives one, else the name without its layer and project prefix."""
    t = next((t for t in pack.get("tables", []) if t["name"] == table), {})
    return str(t.get("purpose") or re.sub(r"^(bronze|gold)_(prj_[0-9a-f]{8}_)?", "", table).replace("_", " ")).strip().capitalize()


def _run(plane, pid: str, pack: dict) -> dict:
    """Through the job queue when there is one (production), inline in simple mode (b6 job handler); this version of the pack, never a newer draft."""
    from sh_platform.jobs.handlers import run_pipeline
    try:
        rec = run_pipeline(plane, pid, "sandbox", BUILDER, version=pack["version"])
    except R.Refused as e:
        return {"status": "failed", "error": e.message, "pack_version": pack["version"]}
    layers = {t["name"]: t["layer"] for t in pack.get("tables", [])}
    steps = rec.get("steps", [])
    shown = [{"label": _label(pack, s["table"]), "layer": layers.get(s["table"]), "rows": s["rows"], "status": s["status"]} for s in steps]
    return {"status": rec["status"], "run_id": rec["run_id"], "pack_version": pack["version"], "started": rec["started"], "finished": rec["finished"],
            "error": next((s["error"] for s in steps if s.get("error")), None),
            "tables": {k: sum(1 for v in layers.values() if v == k) for k in ("bronze", "silver", "gold")},
            "steps": shown, "gold_rows": sum(s["rows"] or 0 for s in steps if layers.get(s["table"]) == "gold"), "checks": _checks(plane, pid) if rec["status"] == "ok" else None}


def start(plane, viewer, pid: str, F=None, force: bool = False) -> dict:
    """Connect and run the newest approved pack, once per pack version (a second call finds the round already made). Nothing here waits for a click:
    the screen calls it when it opens, and the architect's new version starts a new round. `force` connects again (after an address is allowed)."""
    if viewer is not None and DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can start the builder.")
    with _LOCK:
        pack = pack_of(plane, pid)
        if not pack:
            raise Refused(409, "The design pack is not approved yet. The builder starts when it is.")
        rec = load(plane, pid)
        cur = rec["rounds"][-1] if rec["rounds"] else None
        if cur and cur["pack_version"] == pack["version"] and not (force and cur["state"] in ("blocked", "failed")):
            if viewer is not None and cur["state"] == "ran" and rec.get("benchmark") and not cur.get("variance"):
                # the round ran at approval with no viewer: check it against the benchmark now, as the person who may see the figures
                v = variance(plane, viewer, pid, pack, rec["benchmark"])

                def put(r):
                    r["rounds"][-1].update(variance=v, state="checked")
                    _say(r, BUILDER, f"{v['summary']['unexplained']} unexplained variance remain." if v["summary"]["unexplained"] else "The variance is cleared.")
                _save(plane, pid, put)
                return load(plane, pid)["rounds"][-1]
            return cur
        system = systems_of(plane, pid)
        conns = [_connect_marked(plane, s, system.get(s["code"]) or {}, rec["settled"], F, rec.get("not_needed") or []) for s in pack.get("sources", [])]
        rnd = {"pack_version": pack["version"], "started_at": _now(), "connections": conns, "run": None, "variance": None, "state": "connecting", "outcome": None}
        stuck = [c for c in conns if c["status"] not in ("connected", "not_needed")]
        if stuck:
            rnd["state"] = "blocked"
        else:
            rnd["run"] = _run(plane, pid, pack)
            rnd["state"] = "ran" if rnd["run"]["status"] == "ok" else "failed"
        bm = rec.get("benchmark")
        if rnd["state"] == "ran" and bm and viewer is not None:  # at approval (no viewer) the next start by a person checks it
            rnd["variance"] = variance(plane, viewer, pid, pack, bm)
            rnd["state"] = "checked"

        def go(r):
            if cur and cur["pack_version"] == pack["version"]:
                r["rounds"][-1] = rnd  # a forced reconnect replaces the blocked round of this version
            else:
                r["rounds"].append(rnd)
            r["needs"] = _needs(plane, pid, conns, pack, r["needs"])
            if len(r["rounds"]) == 1 and not r["thread"]:
                _say(r, BUILDER, f"I took design pack version {pack['version']} as it was approved. I connect each source as it says and run on a copy. I only come back to you when something fails.")
            if rnd["state"] == "blocked":
                _say(r, BUILDER, "I could not finish connecting: " + "; ".join(f"{c['name']}: {c['detail'] or 'the source details differ'}" for c in stuck))
            if len(r["rounds"]) > 1 and rnd["state"] in ("ran", "checked", "failed"):
                v = rnd["variance"]
                _say(r, BUILDER, f"Pack version {pack['version']} is approved, so I ran again. " + (
                    "The run failed." if rnd["state"] == "failed" else
                    f"{v['summary']['unexplained']} unexplained variance remain." if v and v["summary"]["unexplained"] else "The variance is cleared." if v else "I check it against the benchmark when the page opens." if bm else "Send me the benchmark and I will check it."))
        _save(plane, pid, go)
        return rnd


def recheck(plane, viewer, pid: str, F=None) -> dict:
    return start(plane, viewer, pid, F, force=True)


def set_not_needed(plane, viewer, pid: str, body: dict) -> dict:
    """H3: a person takes a source with no sample out of the build ("not needed"), or puts it back (`needed: true`). Never silent: it is named in the
    thread with who and why. Only a source that has no sample can be marked."""
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can mark a source as not needed.")
    code, back, reason = body.get("source"), body.get("needed") is True, str(body.get("reason") or "").strip()[:300]
    pack = pack_of(plane, pid)
    src = next((s for s in (pack or {}).get("sources", []) if s["code"] == code), None)
    if not src:
        raise Refused(404, "That source is not in the approved pack.")
    rec = load(plane, pid)
    marked = any(m["code"] == code for m in rec.get("not_needed") or [])
    conn = next((c for c in (rec["rounds"][-1]["connections"] if rec["rounds"] else []) if c["code"] == code), None)
    if not back and (not conn or conn["status"] != "needs_sample"):
        raise Refused(409, "Only a source that is waiting for a sample can be marked as not needed.")
    if back != marked:
        raise Refused(409, "That source is already " + ("needed." if back else "marked as not needed."))
    name = src.get("name") or code

    def put(r):
        r["not_needed"] = [m for m in r.get("not_needed") or [] if m["code"] != code]
        if not back:
            r["not_needed"].append({"code": code, "name": name, "by": viewer.name, "at": _now(), "reason": reason})
        _say(r, BUILDER, f"{viewer.name} {'put back' if back else 'marked'} {name} {'as needed' if back else 'as not needed'}" + (f": {reason}" if reason and not back else "") + ".")
    _save(plane, pid, put)
    B.log(plane, pid, viewer.name, "put a source back" if back else "marked a source not needed", pack["version"], code)
    return recheck(plane, viewer, pid)


def on_approved(plane, pid: str, F=None) -> dict | None:
    """The head of data approved a pack version: start the builder without a click. Called by whoever approves (integration), never raises."""
    try:
        return start(plane, None, pid, F)
    except Exception:  # noqa: BLE001 - the approval stands; the screen starts the round when it opens
        log.warning("the builder could not start after approval", exc_info=True)
        return None


def resolve(plane, viewer, pid: str, body: dict) -> dict:
    """Settle a mismatch once: the chosen value is written to the intent's system map AND the pack together. The mismatch is not raised again."""
    if DATA_ENGINEER not in seat_of(viewer) and ARCHITECT not in seat_of(viewer):
        raise Refused(403, "Only the data team can settle a mismatch.")
    code, field, value = (body.get(k) for k in ("source", "field", "value"))
    if field not in ("file", "columns", "host") or not code or value in (None, "", []):
        raise Refused(400, "Say which source and field, and the value to keep.")
    if field == "columns" and not isinstance(value, list):
        value = [x.strip() for x in str(value).split(",") if x.strip()]
    pack = pack_of(plane, pid)
    if not pack or code not in {s["code"] for s in pack["sources"]}:
        raise Refused(404, "That source is not in the approved pack.")
    rec = load(plane, pid)
    conn = next((c for c in (rec["rounds"][-1]["connections"] if rec["rounds"] else []) if c["code"] == code), None)
    seen = (conn or {}).get("seen", {}).get(field)
    sysf = R._dir(plane, pid) / "systems.json"
    with lock_for(sysf):
        systems = systems_of(plane, pid)
        systems.setdefault(code, {})[field] = value
        write_json_atomic(sysf, systems)
    with lock_for(B.folder(plane, pid)):  # a connection detail, not a design change: the pack version stays, the correction is logged
        plan = B.get(plane, pid, pack["version"])
        src = next(s for s in plan["sources"] if s["code"] == code)
        src.setdefault("arrives", {})[field] = value
        plan.setdefault("corrections", []).append({"source": code, "field": field, "value": value, "by": viewer.name, "at": _now()})
        B._save(plane, plan)
    B.log(plane, pid, viewer.name, "corrected a connection detail", pack["version"], f"{code} {field}")
    _save(plane, pid, lambda r: (r["settled"].append(f"{code}|{field}|{seen}"),
                                 _say(r, BUILDER, f"{viewer.name} settled {field} for {conn['name'] if conn else code}: the system map and the pack now agree.")))
    return recheck(plane, viewer, pid)


# ---- 3. the benchmark ---------------------------------------------------------------------------------------------------------------

_LINE = re.compile(r"^(?P<label>.*?[A-Za-z].*?)[\s:|,;]+(?P<num>[+-]?\d[\d,]*(?:\.\d+)?)\s*(?P<pct>%)?\s*$")


def parse_report(text: str) -> list[dict]:
    """Figures found in a report's text: a label then a number or a percentage at the end of a line."""
    out = []
    for ln in text.splitlines()[:5000]:
        m = _LINE.match(re.sub(r"[*_`]", "", ln).strip())
        if not m:
            continue
        try:
            v = _dec(m["num"].replace(",", ""))
        except InvalidOperation:
            continue
        out.append({"label": m["label"].strip(" :|,;-"), "value": str(v), "unit": "pct" if m["pct"] else "money"})
        if len(out) >= 500:
            break
    return out


def signed_reports(plane) -> list[dict]:
    return [{"id": v["id"], "name": f"{r['name']}, {v['period_end']}", "issued_at": v["issued_at"]} for r in e1_reports.listing(plane)
            for v in r["versions"] if v["status"] == "issued"]


def _signed_lines(plane, viewer, vid: str) -> tuple[str, list[dict]]:
    name = next((s["name"] for s in signed_reports(plane) if s["id"] == vid), None)
    if not name:
        raise Refused(404, "That signed report was not found.")
    admin = "company_admin" in set(viewer.roles)
    lines = []
    for ln in e1_reports.as_issued(plane, vid):
        pf = ln.get("portfolio_id")
        if (pf and e1_access.level(plane, viewer, portfolio_id=str(pf)) == "none") or (not pf and not admin):
            continue  # a figure the data engineer may not see is not copied into the check
        lines.append({"label": "Total holdings" if ln["is_total"] else ln["label"], "value": str(_dec(ln["value"])), "unit": "money", "note": ln["status"]})
    return name, lines


def set_benchmark(plane, viewer, pid: str, body: dict) -> dict:
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can give the builder a benchmark.")
    if body.get("report_version_id"):
        name, lines = _signed_lines(plane, viewer, str(body["report_version_id"]))
        bm = {"kind": "signed", "name": name, "report_version_id": str(body["report_version_id"])}
    else:
        name = str(body.get("name") or "").strip()[:200]
        try:
            data = base64.b64decode(body["b64"], validate=True) if body.get("b64") else str(body.get("text") or "").encode("utf-8")
        except (binascii.Error, ValueError):
            raise Refused(400, "That file could not be read. Please upload it again.") from None
        if not name or not data or len(data) > MAX_UPLOAD:
            raise Refused(400, "Give the report a name and a file under 8 MB.")
        from sh_platform.context_docs import reader
        try:
            text = "\n".join(t for _, t in reader.read_segments(name, data))
            kept = L.receive(plane, data, name, viewer.name, "benchmark")  # the original is kept as received
        except (reader.Refusal, L.Refused) as e:
            raise Refused(422, getattr(e, "message", None) or str(e)) from None
        lines = parse_report(text)
        bm = {"kind": "upload", "name": name, "file_id": kept["file_id"]}
    if not lines:
        raise Refused(422, "I could not find any figures in that report. Upload it with the figures as text, or pick a signed report.")
    bm.update(by=viewer.name, at=_now(), lines=lines)
    pack = pack_of(plane, pid)

    def go(r):
        r["benchmark"] = bm
        _say(r, BUILDER, f"Thank you. I read {len(lines)} figure{'s' if len(lines) != 1 else ''} in {name} and compared every one I can find in the run.")
    _save(plane, pid, go)
    rec = load(plane, pid)
    cur = rec["rounds"][-1] if rec["rounds"] else None
    if cur and cur["run"] and cur["run"]["status"] == "ok" and pack:
        v = variance(plane, viewer, pid, pack, bm)

        def put(r):
            r["rounds"][-1].update(variance=v, state="checked")
        _save(plane, pid, put)
    return view(plane, viewer, pid)


# ---- 4. variance, line by line ------------------------------------------------------------------------------------------------------

def _cols(con, table: str) -> dict[str, str]:
    return V._cols(con, table)


def _key_figures(plane, pack: dict) -> list[dict]:
    """The run's figures the report is checked on, read from the copy: what the pack names, else the totals of the gold tables."""
    out, con = [], V._copy(plane)
    try:
        for kf in pack.get("key_figures") or []:
            t, c, agg = kf.get("table", ""), kf.get("column", ""), kf.get("agg", "sum")
            cols = _cols(con, t) if V._NAME.match(t or "") else {}
            by = kf.get("by") if kf.get("by") in cols else None
            if c not in cols or agg not in ("sum", "max", "min", "count") or not V._NAME.match(c):
                continue
            sel = f'"{by}", ' if by else ""
            when = kf.get("when") if kf.get("when") in cols and V._NAME.match(kf["when"]) else None  # V6B: a figure of one month, not of every month in the table
            month = str((pack.get("benchmark") or {}).get("month") or "")
            cond, args = "", []
            if when and re.fullmatch(r"\d{4}-\d{2}", month):
                cond, args = f" where strftime(\"{when}\", '%Y-%m') = ?", [month]
            elif when:
                cond = f' where "{when}" = (select max("{when}") from "{t}")'
            sql = f'select {sel}{agg}("{c}") from "{t}"' + cond + (f' group by "{by}" order by "{by}"' if by else "")  # noqa: S608 - names checked against the copy's columns
            for row in con.execute(sql, args).fetchall():
                v = row[-1]
                if v is None:
                    continue
                out.append({"label": f"{kf.get('label', c)}" + (f": {row[0]}" if by else ""), "run": str(_dec(v)), "unit": kf.get("unit", "money"), "match": kf.get("match") or [],
                            "name": str(row[0]) if by else None})
        if not pack.get("key_figures"):
            for f in V._gold_figures(con, pack):
                if f["run"] is not None and "rows" not in f["figure"]:
                    out.append({"label": f["figure"], "run": f["run"], "unit": "money", "match": [], "name": None})
    finally:
        con.close()
    return out


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", s.lower())) - _SKIP


def _find(label: str, pool: list[dict], unit: str) -> dict | None:
    want = _tokens(label)
    best, score = None, 0
    for f in pool:
        if f["unit"] != unit:
            continue
        names = [f["label"], *f.get("match", [])]
        for n in names:
            have = _tokens(n)
            if have and want and (have <= want or want <= have):
                s = len(have & want) + (10 if have == want else 0)
                if s > score:
                    best, score = f, s
    return best


def _revisions(plane) -> list[dict]:
    """Statements amended after they were first recorded: the new value, the one it replaced, who it is about, when. Each carries its evidence."""
    try:
        with wh.connect(plane, read_only=True) as con:
            rows = con.execute("select v.id, coalesce(i.canonical_name, ''), v.value_amount - o.value_amount, coalesce(v.received_at, v.recorded_at) "
                               "from valuation_observations v join valuation_observations o on o.id = v.supersedes_valuation_id "
                               "left join instruments i on i.id = v.instrument_id").fetchall()
    except (OSError, duckdb.Error):
        return []
    return [{"name": n, "delta": _dec(d), "when": at, "trail": {"kind": "valuation", "id": str(i)}} for i, n, d, at in rows]


def _explain(delta: Decimal, label: str, revs: list[dict]) -> list[dict]:
    """Evidence that explains `delta` (run minus report): the revisions that add up to it. None when nothing does, so it stays unexplained."""
    def ev(r):
        w = r["when"]
        d = f"{w.day} {w:%b}" if hasattr(w, "day") else str(w)[:10]
        return {"text": f"{r['name'] or 'A statement'} amended {d}", "trail": r["trail"]}
    own = [r for r in revs if r["name"] and r["name"].lower() in label.lower()]
    for pool in (own, revs):
        if pool and sum(r["delta"] for r in pool) == delta:
            return [ev(r) for r in pool]
        one = [r for r in pool if r["delta"] == delta]
        if one:
            return [ev(one[0])]
    return []


def _benchmark_run(plane, viewer, pid: str, pack: dict) -> tuple[list[dict], list[dict]]:
    """The run's portfolio and benchmark returns and each leg's weight, from b9_verify.comparison (the signed definition, the run's own weights table)."""
    bm = pack.get("benchmark") or {}
    if not all(bm.get(k) for k in ("portfolio", "code", "month")):
        return [], []
    try:
        c = V.comparison(plane, viewer, pid, {k: bm[k] for k in ("portfolio", "code", "month")})
    except (Refused, OSError, duckdb.Error, KeyError, IndexError, ZeroDivisionError):
        return [], []
    names = bm.get("names") or {}
    figs = [{"label": lab, "run": str(_dec(v)), "unit": "pct", "match": alias} for lab, v, alias in (
        ("Portfolio return", c["portfolio_pct"], [str(bm["portfolio"]).replace("-", " ")]), ("Benchmark return", c["benchmark_run_pct"], [str(bm["code"]).replace("-", " ")]),
        ("Difference", c["difference_run_pts"], [])) if v is not None]  # the report calls the benchmark by the family's name for it ('Office blend')
    legs = [{"label": names.get(r["component"]) or r["label"], "run": str(_dec(r["used_weight_pct"])), "unit": "pct", "match": [r["component"]]} for r in c["rows"]]
    return figs, legs


def variance(plane, viewer, pid: str, pack: dict, bm: dict) -> dict:
    """Every report line that has a figure in the run, compared: matches, explained (a revision with its evidence), or unexplained."""
    figs, (more, legs), revs = _key_figures(plane, pack), _benchmark_run(plane, viewer, pid, pack), None
    pool, tol = figs + more, _dec((pack.get("benchmark") or {}).get("tolerance") or 0)
    revs = _revisions(plane)
    lines, leg_lines, unmatched, by_fig = [], [], [], {}
    for r in bm["lines"]:
        unit = r["unit"]
        leg = _find(r["label"], legs, unit)
        f = leg or _find(r["label"], pool, unit)
        if not f:
            unmatched.append(r)
            continue
        delta = _dec(f["run"]) - _dec(r["value"])
        row = {"figure": r["label"] if not leg else leg["label"], "run": f["run"], "report": r["value"], "unit": unit, "diff": str(delta), "status": "matches", "evidence": []}
        if abs(delta) > (PCT_TOL if unit == "pct" else tol):
            ev = _explain(delta, row["figure"], revs) if unit == "money" else []
            row.update(status="explained" if ev else "unexplained", evidence=ev)
        (leg_lines if leg else lines).append(row)
        if not leg:
            by_fig[f["label"]] = row
    p, b, d = (by_fig.get(k) for k in ("Portfolio return", "Benchmark return", "Difference"))
    if p and b and d and p["status"] == "matches" and b["status"] == "unexplained" and d["status"] == "unexplained" \
            and abs(_dec(d["diff"]) + _dec(b["diff"])) <= 2 * PCT_TOL:  # H8: the difference follows the benchmark; the benchmark line carries the variance
        d.update(status="explained", evidence=[{"text": "Follows the benchmark return; the portfolio return matches."}])
    if unmatched and not (lines or leg_lines):  # V6 walk: a report none of whose figures the run holds was "cleared"; nothing compared is an unexplained variance
        lines = [{"figure": r["label"], "run": None, "report": r["value"], "unit": r["unit"], "diff": None, "status": "unexplained",
                  "evidence": [{"text": "This run has no figure for this line."}]} for r in unmatched]
        unmatched = []
    allv = lines + leg_lines
    summary = {s: sum(x["status"] == s for x in allv) for s in ("matches", "explained", "unexplained")}
    return {"benchmark": bm["name"], "lines": lines, "legs": leg_lines, "unmatched": unmatched, "summary": summary, "at": _now(),
            "headline": f"{summary['unexplained']} unexplained variance{'s' if summary['unexplained'] != 1 else ''}" if summary["unexplained"] else "Matches, with explained differences" if summary["explained"] else "Matches"}


# ---- 5. go live, or send back to the architect --------------------------------------------------------------------------------------

def run_trouble(cur: dict | None) -> str | None:
    """The failing step of the round's run, in plain words: which table, what it is for, and the warehouse's reason. None when it did not fail."""
    run = (cur or {}).get("run") or {}
    if run.get("status") != "failed":
        return None
    err = str(run.get("error") or "")
    table, _, why = err.partition(" could not be built: ")
    why = re.sub(r"^\w+ Error:\s*", "", why or err).strip().rstrip("!")
    m = re.search(r"Function with name (\w+) does not exist", why)
    why = f"it calls {m[1]}, which the warehouse does not have" if m else why or "the warehouse gave no reason"
    step = next((s for s in run.get("steps") or [] if s.get("status") == "failed"), {})
    what = f" ({str(step['label']).rstrip('.')})" if step.get("label") else ""
    return (f"The run on the copy stopped at the step that builds {table or 'a table'}{what}: {why}. "
            "Send the design back to the architect to correct that step.")


def _current(plane, pid: str) -> dict:
    rec = load(plane, pid)
    cur = rec["rounds"][-1] if rec["rounds"] else None
    if not cur or cur["state"] not in ("checked", "ran") or not cur["run"] or cur["run"]["status"] != "ok":
        raise Refused(409, run_trouble(cur) or "The run on the copy has not finished cleanly yet.")
    return cur


def go_live(plane, viewer, pid: str, body: dict | None = None) -> dict:
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can go live.")
    body = body or {}
    cur, pack = _current(plane, pid), pack_of(plane, pid)
    if not pack or pack["version"] != cur["pack_version"]:
        raise Refused(409, "A newer pack version is approved. Wait for the builder to run it.")
    v = cur["variance"]
    if v is None and not body.get("no_benchmark"):
        raise Refused(409, "Give the builder a benchmark to check against first, or say there is none.")
    if v and v["summary"]["unexplained"] and not body.get("accept_variance"):
        raise Refused(409, "There is an unexplained variance. Send it back to the architect, or confirm that you go live anyway.")
    from sh_platform.jobs.handlers import run_pipeline
    try:
        run_pipeline(plane, pid, "live", viewer.name, version=pack["version"])
    except R.Refused as e:
        raise Refused(e.status, e.message) from None
    sc = pack.get("schedule") or {}
    when = f"{sc.get('freq', 'daily')} at {sc.get('at', '06:00')}" + (f", by the {sc['day']}" if sc.get("freq") == "monthly" and sc.get("day") else "")  # the pack's refresh rule, its day too

    def go(r):
        r["rounds"][-1].update(state="live", outcome={"kind": "live", "by": viewer.name, "at": _now(), "anyway": bool(v and v["summary"]["unexplained"])})
        _say(r, BUILDER, f"{viewer.name} took pack version {pack['version']} live on the pack schedule ({when}). Lumen proposes a starter dashboard next.")
    _save(plane, pid, go)
    return view(plane, viewer, pid)


def send_back(plane, viewer, pid: str, note: str = "") -> dict:
    """Hand the variance to the architect role with the evidence: an agents/handoff item, filed pending and shown in the data team's Action."""
    if DATA_ENGINEER not in seat_of(viewer):
        raise Refused(403, "Only the data engineer can send a run back.")
    cur = _current(plane, pid)
    v = cur["variance"]
    bad = [x for x in (v["lines"] + v["legs"]) if x["status"] == "unexplained"] if v else []
    if not bad:
        raise Refused(409, "There is no unexplained variance to send back.")
    fmt = lambda x, k: f"{Decimal(x[k]):,.2f}" + ("%" if x["unit"] == "pct" else "")  # noqa: E731
    facts = [f"{x['figure']}: this run {fmt(x, 'run') if x['run'] is not None else 'has no figure'}, the report {fmt(x, 'report')}." for x in bad[:4]]
    facts.append(f"Benchmark: {v['benchmark']}.")
    facts.append(f"Everything else matches or is explained ({v['summary']['matches'] + v['summary']['explained']} lines).")
    item = {"from": "builder", "what": "variance", "links": [f"/centre/build/p/{pid}/pipelines"], "facts": facts[:6],
            "question": (" ".join(str(note or "").split())[:300] or f"The run differs from the benchmark on {len(bad)} line{'s' if len(bad) > 1 else ''}. Please update the pack.")}
    ev = H.file(plane, viewer, pid, item)
    if not ev:
        raise Refused(409, "This variance is already with the architect.")
    text = f"{len(bad)} line{'s' if len(bad) > 1 else ''} in pack version {cur['pack_version']} differ from {v['benchmark']}: " + " ".join(facts[:len(bad[:4])])

    def go(r):
        r["rounds"][-1].update(state="sent_back", outcome={"kind": "sent_back", "by": viewer.name, "at": _now(), "handoff": ev["id"]})
        _say(r, BUILDER, text, [e for x in bad for e in x["evidence"]] or [{"text": f"Benchmark: {v['benchmark']}"}])
    _save(plane, pid, go)
    return view(plane, viewer, pid)


def issue_version(plane, viewer, pid: str, body: dict) -> dict:
    """The architect issues the next pack version from the variance: the changed tables' SQL, the change shown before and after. The head of data approves
    it (b6_plan, never the person who proposed); the builder then runs it by itself."""
    if ARCHITECT not in seat_of(viewer):
        raise Refused(403, "Only the architect can issue a new pack version.")
    pack = pack_of(plane, pid)
    if not pack:
        raise Refused(409, "There is no approved pack to change.")
    changes = body.get("changes")
    if not isinstance(changes, list) or not changes:
        raise Refused(400, "Say which table to change and the new SQL.")
    plan, shown = {**pack, "tables": [dict(t) for t in pack["tables"]]}, []
    for ch in changes:
        t = next((t for t in plan["tables"] if t["name"] == ch.get("table")), None)
        if not t or not str(ch.get("sql") or "").strip():
            raise Refused(400, "Each change names a table of the pack and gives its new SQL.")
        shown.append({"table": t["name"], "before": t.get("sql", ""), "after": ch["sql"], "why": str(ch.get("why") or "")[:300]})
        t["sql"] = ch["sql"]
    plan.pop("corrections", None)
    plan["change_from"] = {"version": pack["version"], "changes": shown, "handoff": body.get("handoff_id")}
    new = B.new_version(plane, pid, plan, viewer)
    if body.get("handoff_id"):
        try:
            H.decide(plane, viewer, str(body["handoff_id"]), True, pid)
        except H.Refused:
            pass  # already answered by someone else: the new version stands
    note = " ".join(str(body.get("note") or "").split())[:400] or "I changed " + ", ".join(c["table"] for c in shown) + "."
    _save(plane, pid, lambda r: _say(r, ARCH, f"Pack version {new['version']} issued from version {pack['version']}. {note} The head of data approves it, then the builder runs it.",
                                     [{"text": f"{c['table']}: {c['why'] or 'changed'}"} for c in shown]))
    return {"version": new["version"], "state": new["state"], "changes": shown}


# ---- what the screen reads ----------------------------------------------------------------------------------------------------------

def view(plane, viewer, pid: str) -> dict:
    rec, pack = load(plane, pid), pack_of(plane, pid)
    seats = seat_of(viewer)
    cur = rec["rounds"][-1] if rec["rounds"] else None
    latest = (B.get(plane, pid) or {}) if B.versions(plane, pid) else {}
    de = DATA_ENGINEER in seats
    ran = bool(cur and cur["run"] and cur["run"]["status"] == "ok" and cur["state"] in ("checked", "ran"))
    current = bool(pack and cur and cur["pack_version"] == pack["version"])
    lay = {k: sum(1 for t in (pack or {}).get("tables", []) if t["layer"] == k) for k in ("bronze", "silver", "gold")}
    # can.start: a round that ran at approval is also started (checked against the benchmark) when a person opens the page
    return {"project_id": pid,
            "pack": None if not pack else {"version": pack["version"], "state": pack["state"], "approved_by": pack.get("approved_by"), "approved_at": pack.get("approved_at"),
                                           "sources": len(pack.get("sources", [])), "tables": lay, "schedule": pack.get("schedule"), "change_from": pack.get("change_from"),
                                           "sql": [{"table": t["name"], "label": _label(pack, t["name"]), "sql": t.get("sql", "")} for t in pack.get("tables", []) if t.get("sql")]},
            "waiting": None if pack else "The design pack is not approved yet. The builder starts when it is.",
            "newer": {"version": latest["version"], "state": latest["state"]} if latest and pack and latest.get("version", 0) > pack["version"] else None,
            "round": cur, "rounds": [{"pack_version": r["pack_version"], "state": r["state"], "headline": (r["variance"] or {}).get("headline")} for r in rec["rounds"]],
            "benchmark": rec["benchmark"] and {k: v for k, v in rec["benchmark"].items() if k != "lines"} | {"figures": len(rec["benchmark"]["lines"])},
            "signed_reports": signed_reports(plane) if de and not rec["benchmark"] else [], "thread": rec["thread"], "needs": [n for n in rec["needs"]], "not_needed": rec.get("not_needed") or [],
            "can": {"start": de and bool(pack) and (not current or bool(cur["state"] == "ran" and rec["benchmark"] and not cur.get("variance"))), "recheck": de and bool(cur and cur["state"] == "blocked"), "benchmark": de and ran,
                    "go_live": de and ran and current and bool(cur.get("variance")), "send_back": de and ran and current and bool(cur.get("variance")) and cur["variance"]["summary"]["unexplained"] > 0,
                    "settle": de or ARCHITECT in seats, "not_needed": de and bool(cur and any(c["status"] in ("needs_sample", "not_needed") for c in cur["connections"])), "issue": ARCHITECT in seats and bool(pack)}}


# ---- Action items for the right person ----------------------------------------------------------------------------------------------

def pulse_cards(plane, con, today) -> list[dict]:
    """A needs-me card for the person who can fix an open connection failure or provide a missing sample (e5_pulse source; no model)."""
    from sh_platform.v1.n2_comments import people
    root = plane.path("build")
    if not root.is_dir():
        return []
    ppl = {p["name"].lower(): p for p in people(plane)}
    out = []
    for d in sorted(root.iterdir()):
        try:
            rec = load(plane, d.name) if re.fullmatch(r"prj-[0-9a-f]{8}", d.name) else None
        except Refused:
            rec = None
        for n in (rec or {}).get("needs", []):
            who = n["kind"] == "connection_failed"
            day = n["at"][:10]
            for name in n["to"]:
                p = ppl.get(str(name).lower())
                if not p:
                    continue
                c = e5_pulse.card("*", f"builder:{n['id']}", "builder", ("Connection failed: " if who else "Sample needed: ") + n["name"], n["text"],
                                  status_word="Waiting for you", urgency="needs_me", action_type="open_build", action="Open the pipeline", as_of=day, received=day,
                                  owner=BUILDER, link=f"/centre/build/p/{d.name}/pipelines", rank=2)
                c["recipient"] = p["id"]
                out.append(c)
    return out


e5_pulse.register_source(pulse_cards)
