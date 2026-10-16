"""V6 b10: the Architecture step. Span the architect reads before asking, asks only what is missing, takes samples, drafts the design pack,
the team corrects it line by line, and the head of data approves and locks it. The approved pack drives the b6 plan.

Records, all under `build/<pid>/` (the b6 folder, so the plan and the pack live together):
- `pack-v<n>.json`  one design pack version: {project_id, version, state: draft|proposed|approved|superseded, systems, target: {silver, gold},
  catalogue, mapping, rules, sources, notes, edits, created_by(_id), created_at, approved_by, approved_at, base_version, built_by, plan_version}
- `pack-answers.json`  the answers to the minimal question set ({qid: value}) and the systems the builder confirmed
- `pack-samples.json`  {system_id: sample} (a profiled Excel/CSV, or a PDF with the fields a person marked)
Intent system map: `intents/<iid>/system_map.json` holds corrections to a system's record ({system_id: {field: value, ...}}); the signed
intent is never rewritten. `systems_of(plane, iid)` is the one reading of the map (the intent's sources overlaid with corrections).
Every change is appended to the plan log (`B.log`). Money is never computed here; figures come from records."""
from __future__ import annotations

import json
import logging
import re
import types
from datetime import date, datetime, timedelta, timezone

import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import b2_scan as B2
from sh_platform.v1 import b6_plan as B
from sh_platform.v1 import b6_span as S
from sh_platform.v1 import b10_design as D
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import seats as SE
from sh_platform.v1 import wh
from sh_platform.v1.c5_connect import spec as C5
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
STATES = ("draft", "proposed", "approved", "superseded")
CHANNELS = ("upload", "mailbox", "sftp", "sharepoint", "database")
CHANNEL_WORDS = {"upload": "Upload each file", "mailbox": "A mailbox", "sftp": "An SFTP folder", "sharepoint": "A SharePoint folder", "database": "A database"}
KIND_CHANNEL = {"imap": "mailbox", "sftp": "sftp", "graph": "sharepoint"}
FORMATS = ("excel", "csv", "pdf", "email", "database", "other")
HEAD = getattr(SE, "HEAD_OF_DATA", SE.ARCHITECT)  # the head of data seat; until the seat exists, the architect seat is the head of data
SYSTEM_FIELDS = ("holds", "owner", "format", "channel", "frequency")
_PERIOD = {"month": "monthly", "monthly": "monthly", "day": "daily", "daily": "daily", "week": "weekly", "weekly": "weekly"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _need(viewer, seat: str) -> None:
    if seat not in SE.seat_of(viewer):
        raise Refused(403, "Only the head of data can do this." if seat == HEAD else SE.REFUSAL.get(seat, "You cannot do this."))


def _slug(text, n: int = 40) -> str:
    return S.slug(text, n)


def _human(name: str) -> str:
    return re.sub(r"_+", " ", str(name)).strip().capitalize()


# ---- the intent system map ---------------------------------------------------------------------------------------------------------

def _map_path(plane, iid: str):
    return plane.path("intents", iid, "system_map.json")


def _overlay(plane, iid: str) -> dict:
    try:
        return read_json_strict(_map_path(plane, iid), dict) or {}
    except (OSError, ValueError):
        return {}


def _code(s: dict) -> str:
    return _slug(s.get("code") or s.get("name") or "source", 24)


def systems_of(plane, iid: str, sow: dict | None = None) -> list[dict]:
    """One record per system named in the intent: what it holds, owner, format, how it arrives (channel), how often (frequency); the intent's
    own words with any later correction laid over them. `corrected` lists the fields a correction changed, `intent` the intent's value."""
    from sh_platform.v1 import i2_north as N
    sow = sow or N.read_sow(plane, iid)
    over = _overlay(plane, iid)
    out = []
    for s in sow.get("sources") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        sid = str(s.get("id") or _code(s))
        was = {"holds": s.get("holds") or "", "owner": s.get("owner") or "",
               "format": s.get("format") or ("pdf" if s.get("structure") == "unstructured" or s.get("kind") == "document" else _ext_format(s)),
               "channel": s.get("channel") if s.get("channel") in CHANNELS else "", "frequency": s.get("arrives") or ""}
        fix = {k: v for k, v in (over.get(sid) or {}).items() if k in SYSTEM_FIELDS and v}
        out.append({"id": sid, "code": _code(s), "name": s["name"], "kind": s.get("kind") or "system", "structure": s.get("structure") or "structured",
                    **{**was, **fix}, "intent": was, "corrected": sorted(k for k, v in fix.items() if v != was.get(k)),
                    "samples": list(s.get("samples") or [])})
    return out


def _ext_format(s: dict) -> str:
    """excel or csv from the name of a sample the person attached; '' when none was."""
    names = [str(x).lower() for x in [s.get("sample_path"), *(s.get("samples") or [])] if x]
    return next(("excel" if n.endswith((".xlsx", ".xlsm", ".xls")) else "csv" for n in names if n.endswith((".xlsx", ".xlsm", ".xls", ".csv"))), "")


def correct_system(plane, viewer, iid: str, sid: str, changes: dict, sow: dict | None = None) -> dict:
    """A value the builder found different from the intent's: kept in the intent's system map beside the intent's own, by whom and when."""
    known = {s["id"]: s for s in systems_of(plane, iid, sow)}
    if sid not in known:
        raise Refused(404, "That system is not in the intent.")
    want = {k: str(v).strip()[:200] for k, v in (changes or {}).items() if k in SYSTEM_FIELDS and isinstance(v, str)}
    if "channel" in want and want["channel"] not in CHANNELS:
        raise Refused(400, "It arrives by upload, mailbox, SFTP, SharePoint or a database.")
    if not want:
        raise Refused(400, "Say what is different.")
    with lock_for(_map_path(plane, iid)):
        d = _overlay(plane, iid)
        row = d.setdefault(sid, {})
        row.update(want)
        row["history"] = (row.get("history") or []) + [{"at": now(), "by": viewer.name, "set": want, "intent_said": {k: known[sid]["intent"].get(k) for k in want}}]
        write_json_atomic(_map_path(plane, iid), d)
    return {s["id"]: s for s in systems_of(plane, iid, sow)}[sid]


# ---- storage -----------------------------------------------------------------------------------------------------------------------

def _file(plane, pid: str, name: str):
    return B.folder(plane, pid) / name


def _read(plane, pid: str, name: str) -> dict:
    try:
        return read_json_strict(_file(plane, pid, name), dict) or {}
    except (OSError, ValueError):
        return {}


def _write(plane, pid: str, name: str, data: dict) -> None:
    with lock_for(_file(plane, pid, name)):
        write_json_atomic(_file(plane, pid, name), data)


def versions(plane, pid: str) -> list[int]:
    return sorted(int(m.group(1)) for p in B.folder(plane, pid).glob("pack-v*.json") if (m := re.fullmatch(r"pack-v(\d+)\.json", p.name)))


def get(plane, pid: str, version: int | None = None) -> dict | None:
    vs = versions(plane, pid)
    n = version or (vs[-1] if vs else None)
    if n is None or n not in vs:
        return None
    try:
        return read_json_strict(_file(plane, pid, f"pack-v{n}.json"), dict)
    except (OSError, ValueError):
        raise Refused(409, "The design pack cannot be read. Please try again.") from None


def latest_approved(plane, pid: str) -> dict | None:
    for n in reversed(versions(plane, pid)):
        p = get(plane, pid, n)
        if p and p["state"] == "approved":
            return p
    return None


def _save(plane, pack: dict) -> dict:
    _write(plane, pack["project_id"], f"pack-v{pack['version']}.json", pack)
    return pack


def _log(plane, pid: str, viewer, what: str, version: int | None, note: str = "") -> None:
    B.log(plane, pid, viewer.name, what, version, note)


# ---- reading before asking ---------------------------------------------------------------------------------------------------------

def _project(plane, pid: str) -> tuple[dict, dict]:
    prj = P1.read(plane, pid)
    return prj, S.signed_sow(plane, prj)


def _find_files(plane, system: dict, scan: list[dict], listing: dict) -> dict:
    """What the scan found for one system: its landed files, columns, rows, documents."""
    src = {"id": system["id"], "name": system["name"], "sample_path": (system.get("samples") or [""])[0]}
    mine = B2._files_of(src, scan)
    landed = listing.get("by_source", {}).get(system["code"], []) + listing.get("by_source", {}).get(system["id"], [])
    docs = [f for f in landed if str(f.get("name", "")).lower().endswith(".pdf")]
    out = {"files": len({f["name"] for f in mine}) or len([f for f in landed if f not in docs]), "documents": len(docs)}
    if mine:
        out.update(columns=max(len(f["columns"]) for f in mine), rows=sum(f["rows"] for f in mine), names=sorted({f["name"] for f in mine})[:5])
    return out


def _status(system: dict, spec: dict | None, found: dict, sample: dict | None) -> str:
    if spec:
        return "connected"
    if found.get("files") or found.get("documents"):
        return "landed"
    return "sample" if sample else "never_seen"


def summary(plane, viewer, pid: str) -> dict:
    """2a. What Span already knows, from the signed intent, the process map, the catalogue, the connectors and the landed files; it scans
    connected systems and landed files itself. Nothing here is asked of anyone."""
    prj, sow = _project(plane, pid)
    iid = prj["intent_id"]
    samples = _read(plane, pid, "pack-samples.json")
    answers = _read(plane, pid, "pack-answers.json")
    specs = {s["source_code"]: s for s in C5.all_specs(plane).values()}
    listing = L.listing(plane)
    scan = B2.landing_files(plane)
    systems = []
    for s in systems_of(plane, iid, sow):
        spec = specs.get(s["code"])
        found = _find_files(plane, s, scan, listing)
        status = _status(s, spec, found, samples.get(s["id"]))
        channel = s["channel"] or (KIND_CHANNEL.get(spec["kind"], "") if spec else "")
        systems.append({**s, "channel": channel, "connector": spec["id"] if spec else None, "status": status, "found": found,
                        "sample": samples.get(s["id"]), "from_intent": bool(s["intent"]["channel"] or s["intent"]["frequency"]),
                        "confirmed": s["id"] in (answers.get("confirmed") or [])})
    goal = sow.get("goal") or {}
    kpis = [{"code": k.get("code"), "name": k.get("name"), "definition": k.get("definition") or "", "formula": k.get("formula") or "",
             "period": k.get("period") or "", "signed": bool(k.get("definition") or k.get("formula")), "owner": k.get("owner") or ""}
            for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("name")]
    steps = [st for st in (sow.get("process") or {}).get("steps") or [] if isinstance(st, dict)]
    model = {t["name"] for t in E.current(plane)["tables"]}
    asks = questions(plane, viewer, pid)
    return {"project_id": pid, "title": prj.get("title"), "people": prj.get("people") or {}, "intent_id": iid, "readers": goal.get("readers") or [], "needed_by": goal.get("needed_by") or "",
            "kpis": kpis, "steps": len(steps), "systems": systems, "catalogue_tables": len(model),
            "asked": [q["id"] for q in asks["open"]], "not_asked": asks["known"],
            "line": f"I read the signed intent and the process map ({len(steps)} steps). I scanned what already arrives. "
                    + (f"I only need to ask you {len(asks['open'])} thing{'s' if len(asks['open']) != 1 else ''}." if asks["open"] else "I have everything I need.")}


# ---- the minimal question set ------------------------------------------------------------------------------------------------------

_KIND_RE = [("control_total", re.compile(r"total|footer|control")), ("agree", re.compile(r"agree|match|within|reconcil|toleran|compare")),
            ("completeness", re.compile(r"by the|deadline|business day|before|no later|in by|on time"))]


def _check_proposals(sow: dict) -> list[dict]:
    out = []
    for st in (sow.get("process") or {}).get("steps") or []:
        txt = str((st or {}).get("control") or "").strip()
        if not txt:
            continue
        kind = next((k for k, rx in _KIND_RE if rx.search(txt.lower())), "other")
        tol = re.search(r"within\s+([\w.,%]+(?:\s+[A-Za-z]{3,4})?(?:\s+per\s+\w+)?)", txt, re.I)
        out.append({"id": f"chk-{_slug(txt, 24)}", "kind": kind, "text": txt[:200], "tolerance": ("exact" if kind == "control_total" else tol.group(1) if tol else "to confirm"),
                    "source": "process_map", "step": st.get("name")})
    if not out:
        out = [{"id": "chk-control-total", "kind": "control_total", "text": "The loaded total equals the source file's footer total", "tolerance": "exact",
                "source": "default", "step": None}]
    return out


def _freshness(sow: dict) -> dict:
    nb = str((sow.get("goal") or {}).get("needed_by") or "")
    low = nb.lower()
    at = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", nb)
    freq = "monthly" if "month" in low or "business day" in low else "weekly" if "week" in low else "daily"
    day = re.search(r"(\d+(?:st|nd|rd|th)\s+business\s+day)", low)
    return {"freq": freq, "at": at.group(0) if at else "06:00", "day": day.group(1) if day else (nb if freq == "monthly" and nb else None),
            "label": f"{at.group(0) if at else '06:00'} {freq}" + (f", by the {day.group(1)}" if day else "")}


def _grain(sow: dict) -> tuple[dict, bool]:
    """(proposal, known): the level of the figures from the KPIs' 'by' words and period. Known when the intent names both."""
    dims = list(dict.fromkeys(str(b).lower() for k in sow.get("kpis") or [] if isinstance(k, dict) for b in k.get("benchmark_by") or []
                              if str(b).lower() not in _PERIOD))
    words = " ".join(f"{k.get('period') or ''} {' '.join(map(str, k.get('benchmark_by') or []))}" for k in sow.get("kpis") or [] if isinstance(k, dict)).lower()
    period = next((v for w, v in _PERIOD.items() if re.search(rf"\b{w}\b", words + " " + str((sow.get('goal') or {}).get('needed_by') or "").lower())), "")
    label = f"{period or 'monthly'} by {' and '.join(dims) if dims else 'entity'}"
    return {"label": label, "period": period or "monthly", "dims": dims or ["entity"]}, bool(period and dims)


def _history_candidates(plane, sow: dict) -> list[str]:
    """Text columns of the company model whose words the intent itself uses (never a fixed list): what might need its history kept."""
    said = set(re.findall(r"[a-z]{3,}", json.dumps({k: sow.get(k) for k in ("goal", "process", "kpis", "sources", "catalogue")}).lower()))
    out = []
    for t in E.current(plane)["tables"]:
        for c in t["columns"]:
            w = set(c["name"].split("_"))
            if str(c["type"]).lower() in ("text", "varchar") and not w & {"id", "code", "key", "name", "note", "currency"} and w <= said and c["name"] not in out:
                out.append(c["name"])
    return out[:6]


def questions(plane, viewer, pid: str) -> dict:
    """2b. {open: [...], known: [...]}: a question only where the intent and the scans cannot answer, each with a default to accept."""
    prj, sow = _project(plane, pid)
    answers = _read(plane, pid, "pack-answers.json").get("answers") or {}
    specs = {s["source_code"] for s in C5.all_specs(plane).values()}
    landed = L.listing(plane).get("by_source", {})
    samples = _read(plane, pid, "pack-samples.json")
    qs, known = [], []

    def add(qid, topic, title, why, proposal, options=None, evidence=""):
        a = answers.get(qid)
        qs.append({"id": qid, "topic": topic, "title": title, "why": why, "proposal": proposal, "options": options or [], "answer": a,
                   "state": "answered" if a is not None else "open", "evidence": evidence})

    need = [s for s in systems_of(plane, prj["intent_id"], sow) if not (s["channel"] or s["code"] in specs or landed.get(s["code"]))]
    for s in systems_of(plane, prj["intent_id"], sow):
        if s not in need:
            known.append(f"{s['name']}: {'connected' if s['code'] in specs else 'landed' if landed.get(s['code']) else 'arrives by ' + CHANNEL_WORDS.get(s['channel'], s['channel']).lower()}")
    for s in need:
        d = "mailbox" if s["format"] == "pdf" else "sftp" if "day" in s["frequency"].lower() or "daily" in s["frequency"].lower() else "upload"
        add(f"source:{s['id']}", "Source", f"How does {s['name']} arrive?", "Named in the intent, not connected and no channel recorded.",
            d, list(CHANNELS), f"{s['name']} holds {s['holds'] or 'data'}; it arrives {s['frequency'] or 'at an unknown rhythm'}.")
    g, g_known = _grain(sow)
    if g_known:
        known.append(f"Grain: {g['label']} (from the intent)")
    else:
        add("grain", "Grain", "What level are the figures at?", "The intent does not say it plainly.", g, [], "From the KPIs' 'by' words and period.")
    cands = _history_candidates(plane, sow)
    add("history", "History", "Which details keep their history?", "Type 2 means a change of manager or class does not rewrite past months.",
        [], cands, "Default: none beyond values by date.")
    add("checks", "Checks", "Which checks must hold before figures are used?", "Proposed from the process map: the checks done by hand today.",
        _check_proposals(sow), [], "Tolerances come from the process map where it states one.")
    unsigned = [{"code": k.get("code"), "name": k.get("name")} for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("name")
                and not (k.get("definition") or k.get("formula"))]
    signed = [k.get("name") for k in sow.get("kpis") or [] if isinstance(k, dict) and (k.get("definition") or k.get("formula"))]
    if signed:
        known.append("Definitions signed in the intent: " + ", ".join(map(str, signed)))
    if unsigned:
        add("definitions", "Definitions", "How is each of these worked out?", "No signed definition yet.",
            {k["code"]: "" for k in unsigned}, [], ", ".join(k["name"] for k in unsigned))
    add("freshness", "Freshness", "When must the data be ready?", "From the intent's 'when needed'.", _freshness(sow), [], str((sow.get("goal") or {}).get("needed_by") or ""))
    narrow = [r for r in sow.get("governance") or [] if isinstance(r, dict) and r.get("kind") == "access" and r.get("applies_to")]
    if narrow:
        add("access", "Access", "Does any table need narrower access?", "The intent limits access for part of the data.",
            {"narrower": []}, [], "; ".join(str(r.get("rule"))[:80] for r in narrow))
    else:
        known.append("Access: inherited from the intent")
    for s in systems_of(plane, prj["intent_id"], sow):
        if s["format"] == "pdf" and not (samples.get(s["id"]) or {}).get("fields"):
            add(f"sample:{s['id']}", "Sample", f"Mark the fields to read on a {s['name']} statement", "A PDF's fields must be shown once.", "mark", [], "")
        elif s["format"] in ("excel", "csv") and not (s["code"] in specs or landed.get(s["code"]) or samples.get(s["id"])):
            add(f"sample:{s['id']}", "Sample", f"Show a sample of {s['name']}", "Never seen before.", "upload", [], "")
    return {"open": [q for q in qs if q["state"] == "open"], "all": qs, "known": known}


def answer(plane, viewer, pid: str, qid: str, value) -> dict:
    _need(viewer, SE.DATA_ENGINEER)
    got = {q["id"]: q for q in questions(plane, viewer, pid)["all"]}
    if qid not in got:
        raise Refused(404, "There is no such question.")
    q = got[qid]
    if qid.startswith("source:") and value not in CHANNELS:
        raise Refused(400, "It arrives by upload, mailbox, SFTP, SharePoint or a database.")
    if not qid.startswith(("source:", "sample:")) and type(value) is not type(q["proposal"]):
        raise Refused(400, "That answer does not fit the question.")
    if qid == "checks" and not all(isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("text"), str) for c in value):
        raise Refused(400, "Each check needs its words.")
    if qid.startswith("source:"):  # never ask twice: the answer goes to the intent's system map as well
        prj = P1.read(plane, pid)
        correct_system(plane, viewer, prj["intent_id"], qid.split(":", 1)[1], {"channel": value})
    with lock_for(_file(plane, pid, "pack-answers.json")):
        d = _read(plane, pid, "pack-answers.json")
        d.setdefault("answers", {})[qid] = value
        write_json_atomic(_file(plane, pid, "pack-answers.json"), d)
    _log(plane, pid, viewer, "answered a design question", None, q["title"][:120])
    return questions(plane, viewer, pid)


def accept_all(plane, viewer, pid: str) -> dict:
    """'Accept all and continue': every open question takes Span's proposal (samples excepted: they need a file)."""
    for q in questions(plane, viewer, pid)["open"]:
        if q["topic"] != "Sample":
            answer(plane, viewer, pid, q["id"], q["proposal"])
    return questions(plane, viewer, pid)


def confirm_systems(plane, viewer, pid: str, ids: list[str]) -> dict:
    """The builder or architect confirms systems 'from the intent'; nothing is retyped."""
    _need(viewer, SE.DATA_ENGINEER)
    prj, sow = _project(plane, pid)
    have = {s["id"] for s in systems_of(plane, prj["intent_id"], sow)}
    ids = [i for i in ids if i in have]
    with lock_for(_file(plane, pid, "pack-answers.json")):
        d = _read(plane, pid, "pack-answers.json")
        d["confirmed"] = list(dict.fromkeys((d.get("confirmed") or []) + ids))
        write_json_atomic(_file(plane, pid, "pack-answers.json"), d)
    _log(plane, pid, viewer, "confirmed systems from the intent", None, f"{len(ids)} systems")
    return summary(plane, viewer, pid)


# ---- samples -----------------------------------------------------------------------------------------------------------------------

def _system(plane, pid: str, sid: str) -> dict:
    prj, sow = _project(plane, pid)
    s = next((x for x in systems_of(plane, prj["intent_id"], sow) if x["id"] == sid), None)
    if s is None:
        raise Refused(404, "That system is not in the intent.")
    return s


def _put_sample(plane, pid: str, sid: str, sample: dict) -> dict:
    with lock_for(_file(plane, pid, "pack-samples.json")):
        d = _read(plane, pid, "pack-samples.json")
        d[sid] = sample
        write_json_atomic(_file(plane, pid, "pack-samples.json"), d)
    return sample


def sample_table(plane, viewer, pid: str, sid: str, name: str, data: bytes) -> dict:
    """An Excel or CSV sample, profiled by the existing scan (e0c landing + e0b profile); where each column goes is proposed by the rules."""
    _need(viewer, SE.DATA_ENGINEER)
    s = _system(plane, pid, sid)
    try:
        rec = L.receive(plane, data, name, viewer.name, s["code"])
    except L.Refused as e:
        raise Refused(400, e.args[0] if e.args else "That file could not be kept.") from None
    if rec["state"] == "quarantined":
        raise Refused(400, "Show an Excel or CSV file here. A PDF statement is marked on the sample page.")
    try:
        rec = L.profile(plane, rec["file_id"])
    except L.Refused as e:
        raise Refused(422, e.args[0] if e.args else "We could not read this file.") from None
    prof = rec.get("profile") or {}
    goes = {}
    try:
        from sh_platform.v1 import e0b_tools
        goes = (e0b_tools.propose_mapping(plane, prof, viewer, model=None) or {}).get("columns") or {}
    except Exception:  # noqa: BLE001 - the mapping proposal is a help; the profile stands without it
        log.warning("no mapping proposal for the sample of %s", sid)
    cols = [{"name": c.get("name"), "type": c.get("kind"), "goes_to": goes.get(c.get("name")) if isinstance(goes.get(c.get("name")), str) else ""}
            for c in prof.get("column_info") or []]
    return _put_sample(plane, pid, sid, {"kind": "table", "name": rec["name"], "file_id": rec["file_id"], "rows": prof.get("row_count"), "columns": cols,
                                         "at": now(), "by": viewer.name})


def sample_pdf(plane, viewer, pid: str, sid: str, name: str, data: bytes) -> dict:
    """A PDF statement kept for the e2 reader; its text lines come back so the person can mark the fields."""
    _need(viewer, SE.DATA_ENGINEER)
    from sh_platform.v1 import x5_extract as X
    s = _system(plane, pid, sid)
    if not data or not name.lower().endswith(".pdf"):
        raise Refused(400, "Show a PDF statement here.")
    clean = L._clean_name(name)
    dest = plane.path("documents", clean)
    if dest.exists() and dest.read_bytes() != data:  # never overwrite another document of the same name
        import hashlib
        clean = f"{dest.stem}-{hashlib.sha256(data).hexdigest()[:8]}{dest.suffix}"
        dest = plane.path("documents", clean)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    lines = X._lines(plane, f"documents/{clean}")
    old = _read(plane, pid, "pack-samples.json").get(sid) or {}
    return _put_sample(plane, pid, sid, {"kind": "pdf", "name": clean, "path": f"documents/{clean}", "lines": len(lines), "system": s["name"],
                                         "fields": old.get("fields") or [], "at": now(), "by": viewer.name})


def sample_lines(plane, viewer, pid: str, sid: str) -> list[dict]:
    from sh_platform.v1 import x5_extract as X
    s = (_read(plane, pid, "pack-samples.json").get(sid) or {})
    if s.get("kind") != "pdf":
        raise Refused(404, "There is no PDF sample for this system.")
    return [{"n": i, "text": t[:200]} for i, t in enumerate(X._lines(plane, s["path"]))][:200]


def mark_field(plane, viewer, pid: str, sid: str, line: int, name: str, fmt: str = "text") -> dict:
    """Mark one field on the PDF sample: the line it sits on, its name and format. Stored with the sample and for the e2 reader (x5 type)."""
    _need(viewer, SE.DATA_ENGINEER)
    from sh_platform.v1 import x5_extract as X
    sample = _read(plane, pid, "pack-samples.json").get(sid) or {}
    if sample.get("kind") != "pdf":
        raise Refused(404, "Add the PDF sample first.")
    lines = X._lines(plane, sample["path"])
    name = str(name or "").strip()[:60]
    if not name or not isinstance(line, int) or not 0 <= line < len(lines):
        raise Refused(400, "Say which line the field is on and what to call it.")
    fmt = fmt if fmt in X.FORMATS else "text"
    value = X.parse(fmt, lines[line])
    label = X.derive_label(lines[line], fmt, value)
    field = {"name": name, "format": fmt, "where_usually": label, "example": value, "line": line}
    fields = [f for f in sample.get("fields") or [] if f["name"].lower() != name.lower()] + [field]
    sample = _put_sample(plane, pid, sid, {**sample, "fields": fields})
    prj = P1.read(plane, pid)
    s = _system(plane, pid, sid)
    t = X.upsert(plane, prj["intent_id"], {"name": f"{s['name']} statement", "files": [sample["path"]],
                                       "fields": [{"name": f["name"], "meaning": f"Marked on the {s['name']} sample", "format": f["format"],
                                                   "where_usually": f["where_usually"], "required": True} for f in fields]}, state="confirmed", tid=sample.get("type_id"))
    _put_sample(plane, pid, sid, {**sample, "type_id": t["id"]})
    _log(plane, pid, viewer, "marked a field to read", None, f"{s['name']}: {name}")
    return sample


# ---- generating the pack -----------------------------------------------------------------------------------------------------------

def _answer(answers: dict, qid: str, default):
    return answers.get(qid, default)


def _sql_parts(sql: str) -> tuple[str | None, list[tuple[str, str]]]:
    """(base query with a placeholder select list, [(column, expression)]) of a `create table ... as select`; None when it is not a plain select."""
    try:
        st = sqlglot.parse_one(sql, read="duckdb")
        sel = st.expression
        if not isinstance(sel, exp.Select):
            return None, []
        cols = [(e.alias_or_name, (e.this if isinstance(e, exp.Alias) else e).sql(dialect="duckdb")) for e in sel.expressions]
        base = sel.copy()
        base.set("expressions", [exp.Star()])
        return base.sql(dialect="duckdb"), cols
    except SqlglotError:
        return None, []


def _build_sql(name: str, t: dict) -> str:
    if not t.get("base_sql"):
        return t["sql"]
    base = sqlglot.parse_one(t["base_sql"], read="duckdb")
    try:
        base.set("expressions", [exp.alias_(sqlglot.parse_one(c["expr"], read="duckdb"), c["name"]) for c in t["columns"]])
    except SqlglotError as e:
        raise Refused(400, f"The formula for a column of {name} cannot be read: {str(e).splitlines()[0][:120]}") from None
    return f"create table {name} as {base.sql(dialect='duckdb')}"


def _owner_for(sow: dict, alias_hint: str, raiser: str) -> str:
    tok = set(re.findall(r"[a-z]{3,}", alias_hint.lower()))
    for k in sow.get("kpis") or []:
        if isinstance(k, dict) and tok & set(re.findall(r"[a-z]{3,}", str(k.get("name")).lower())) and k.get("owner"):
            return str(k["owner"])
    return raiser or ""


_NUMT = ("double", "decimal", "bigint", "numeric", "float", "int")
_DEFAULT = {"difference": "Portfolio return less benchmark return, for the same portfolio and month.",
            "value": "The last value recorded for the fund up to the month end; an amended statement replaces the one it amends.",
            "status": "Official, revised (an amended statement), estimated (a manager estimate) or unverified (not yet approved).",
            "month": "The first day of the month the figure belongs to.", "currency": "The currency the value is recorded in.",
            "component": "A leg of the signed benchmark; the private-markets sleeve is the equity index plus its spread.",
            "component_weight": "The weight the leg carries in that month, from the signed benchmark version."}


def _def_for(sow: dict, col: str, expr: str, defs: dict[str, str] | None = None) -> str:
    """One definition per column: the pack's definition of the figure the column is (portfolio return, benchmark return, net worth), else the signed KPI
    whose name shares the most words with the column name (one clear winner only), else a plain default or the column's name in words."""
    defs = defs or {}
    if col.replace("_", " ") in defs:
        return defs[col.replace("_", " ")]
    if col in _DEFAULT:
        return _DEFAULT[col]
    tok = set(col.split("_")) - {"month", "date", "by", "usd", "sgd", "id", "code", "name"}
    scored = sorted(((len(tok & set(re.findall(r"[a-z]{3,}", str(k.get("name")).lower()))), k) for k in sow.get("kpis") or [] if isinstance(k, dict)), key=lambda x: -x[0])
    if scored and scored[0][0] and (len(scored) == 1 or scored[1][0] < scored[0][0]):
        k = scored[0][1]
        return str(k.get("definition") or k.get("name"))
    return _human(col)


def _gold(plane, sow: dict, plan: dict, answers: dict, raiser: str, hist: list[str], defs: dict[str, str] | None = None) -> list[dict]:
    g, _ = _grain(sow)
    out = []
    for t in plan["tables"]:
        if t["layer"] != "gold":
            continue
        base, parts = _sql_parts(t["sql"])
        exprs = {**{k.lower(): v for k, v in parts}, **dict(parts)}  # a declared name may differ from the SQL's alias only in case
        if base and any(c["name"] not in exprs and c["name"].lower() not in exprs for c in t["columns"]):
            base = None  # a declared column the SQL does not name: build from the SQL as written, never from a guessed formula
        exprs.update({c["name"]: exprs[c["name"].lower()] for c in t["columns"] if c["name"] not in exprs and c["name"].lower() in exprs})
        try:
            q = sqlglot.parse_one(t["sql"], read="duckdb").expression
            gb = [int(x.name) - 1 for x in (q.args.get("group").expressions if q.args.get("group") else []) if isinstance(x, exp.Literal) and x.name.isdigit()]
        except (SqlglotError, AttributeError):
            gb = []
        keys = t.get("keys") or [t["columns"][i]["name"] for i in gb if i < len(t["columns"])] or [c["name"] for c in t["columns"] if not str(c["type"]).lower().startswith(_NUMT)][:3]
        cols = [{"name": c["name"], "type": str(c["type"]).upper(), "expr": exprs.get(c["name"], c.get("from") or c["name"]),
                 "definition": (t.get("col_defs") or {}).get(c["name"]) or _def_for(sow, c["name"], exprs.get(c["name"], ""), defs), "sensitivity": "internal", "history": c["name"] in hist} for c in t["columns"]]
        out.append({"name": t["name"], "purpose": t.get("purpose") or "", "grain": t.get("grain") or _grain_of(t, keys, g), "keys": keys, "kpis": list(t.get("kpis") or []),
                    "history": [c["name"] for c in cols if c["history"]], "owner": _owner_for(sow, t["name"] + " " + t.get("purpose", ""), raiser),
                    "columns": cols, "base_sql": base, "sql": t["sql"], "depends_on": list(t["depends_on"])})
    return out


def _grain_of(t: dict, keys: list[str], g: dict) -> str:
    """The grain in words: the key columns when there are some that are not the intent's own dimensions ('Portfolio, benchmark, month'), else the intent's."""
    if not keys:
        return "one row"
    if any(k not in g["dims"] and k not in ("month", "day", "week", "quarter", "year", "date") for k in keys):
        return ", ".join(_human(k.removesuffix("_code")) for k in keys)
    return g["label"]


def _silver(plane, plan: dict, hist: list[str], notes: list[str], gold: list[dict] | None = None, viewer=None, pid: str = "") -> list[dict]:
    out = _silver_used(plane, plan, hist, notes, gold)
    use = D.usage(plane, viewer, pid, [o["name"] for o in out]) if viewer is not None else {}
    titles = D.project_titles(plane, {u["project_id"] for v in use.values() for u in v if u.get("project_id")})
    for o in out:  # FIXC: silver reused, and which other projects already read it
        o["status"] = "reused" if o["status"] == "used" else o["status"]
        o["other_projects"] = sorted({titles.get(u["project_id"], "") for u in use.get(o["name"], [])} - {""})
        o["feeds_other"] = sorted({u["table"] for u in use.get(o["name"], [])})
    future = D.usage(plane, viewer, pid, [s["name"] for s in plan.get("new_silver") or [] if s.get("extends")]) if viewer is not None else {}
    for s in plan.get("new_silver") or []:  # FIXC: silver proposed (needs the head of data), with what was looked for, what was considered and who is affected
        aff = future.get(s["name"], [])
        out.append({"name": s["name"], "status": "proposed", "history": [], "columns": [c["name"] for c in s["columns"]], "column_types": {c["name"]: c["type"] for c in s["columns"]},
                    "note": ("Adds columns to the existing table " if s.get("extends") else "A new table: ") + ", ".join(c["name"] for c in s["columns"]) + f"; model change {plan.get('model_changes')} waits for the head of data",
                    "looked_for": s.get("looked_for", ""), "considered": s.get("considered", []), "model_change": plan.get("model_changes"), "extends": bool(s.get("extends")),
                    "affects": sorted({f"{titles.get(u['project_id'], '')}: {u['table']}" for u in aff}) if aff else [], "other_projects": []})
    return out


def _silver_used(plane, plan: dict, hist: list[str], notes: list[str], gold: list[dict] | None = None) -> list[dict]:
    cat = {t["name"]: {c["name"] for c in t["columns"]} for t in E.current(plane)["tables"]}
    out, placed = [], set()
    for t in plan["tables"]:
        if t["layer"] != "silver":
            continue
        mine = [h for h in hist if h in cat.get(t["name"], ())]
        placed |= set(mine)
        out.append({"name": t["name"], "status": "extended" if mine else "used", "history": mine, "columns": [c["name"] for c in t["columns"]],
                    "note": ("Extended: " + ", ".join(mine) + " keep their history (type 2)") if mine else "Used as it is"})
    have = {o["name"] for o in out}
    for g in gold or []:  # V6B: the company-model tables the gold tables read are the silver tables used (or extended, when a detail keeps its history)
        words = set(re.findall(r"[a-z_0-9]+", g["sql"].lower()))
        for d in g["depends_on"]:
            if d in cat and d not in have:
                have.add(d)
                mine = [h for h in hist if h in cat[d] and h in words]
                placed |= set(mine)
                out.append({"name": d, "status": "extended" if mine else "used", "history": mine, "columns": sorted(cat[d] & words),
                            "note": ("Extended: " + ", ".join(_human(h).lower() for h in mine) + " keep their history (type 2)") if mine else "Used as it is"})
    for h in hist:
        if h not in placed:
            notes.append(f"{_human(h)} keeps its history but is in no silver table of the plan yet; a model change adds it.")
    return out


def _bronze_of(plan: dict) -> dict[str, dict]:
    return {t["name"]: t for t in plan["tables"] if t["layer"] == "bronze"}


def _mapping(plane, plan: dict, gold: list[dict], systems: list[dict], samples: dict, notes: list[str]) -> list[dict]:
    bronze = _bronze_of(plan)
    silver_cols = {t["name"]: {c["name"]: c for c in t["columns"]} for t in plan["tables"] if t["layer"] == "silver"}
    name_of = {s["code"]: s["name"] for s in systems}
    silver_alias: dict[str, dict] = {}
    for t in plan["tables"]:
        if t["layer"] == "silver" and t.get("sql"):
            try:
                silver_alias[t["name"]] = {x.alias_or_name: x.name for x in sqlglot.parse_one(t["sql"], read="duckdb").find_all(exp.Table)}
            except SqlglotError:
                pass
    rows, seen_codes = [], set()
    model = {t["name"] for t in E.current(plane)["tables"]}

    def origin(stable: str, col: str) -> tuple[str, str, str, str]:
        c = (silver_cols.get(stable) or {}).get(col)
        frm = (c or {}).get("from") or ""
        first = frm.split(",")[0].strip()
        if "." in first:
            alias_, bc = first.split(".", 1)
            bt = (silver_alias.get(stable) or {}).get(alias_, alias_)  # `b.value` in the silver insert: b is the bronze table read as b
        else:
            bt = ""
        if bt.startswith("bronze_"):
            b = bronze.get(bt) or {}
            hdr = next((x.get("from") for x in b.get("columns") or [] if x["name"] == bc), bc)
            return name_of.get(b.get("source"), b.get("source") or ""), str(hdr), f"{bt}.{bc}", b.get("source") or ""
        return "", "", "", ""

    def add(**r):
        r["id"] = "m-" + _slug("|".join([r["gold"], r["system"], r["source_field"], r["kind"]]), 60)
        r.setdefault("words", "")
        r.setdefault("needs_person", "")
        r.setdefault("resolved", False)
        rows.append(r)

    for g in gold:
        try:
            q = sqlglot.parse_one(g["sql"], read="duckdb").expression
            alias = {tb.alias_or_name: tb.name for tb in q.find_all(exp.Table)}
        except SqlglotError:
            q, alias = None, {}
        for c in g["columns"]:
            refs = []
            try:
                refs = list(dict.fromkeys((alias.get(x.table, x.table or next(iter(alias.values()), "")), x.name) for x in sqlglot.parse_one(c["expr"], read="duckdb").find_all(exp.Column)))
            except SqlglotError:
                pass
            if not refs:
                add(kind="derived", system="", source_field="", bronze="", silver="", gold=f"{g['name']}.{c['name']}",
                    words=_words(c["expr"]), note="")
                continue
            refs = [(st, sc) for st, sc in refs if st in silver_cols or st in model]
            if not refs and c["expr"].strip():
                add(kind="derived", system="", source_field="", bronze="", silver="", gold=f"{g['name']}.{c['name']}", words=_words(c["expr"]), note="")
                continue
            for st, sc in refs:
                sysn, hdr, bcol, code = origin(st, sc)
                seen_codes.add(code)
                add(kind="source" if bcol else "silver", system=sysn or "Company model", source_field=hdr, bronze=bcol, silver=f"{st}.{sc}",
                    gold=f"{g['name']}.{c['name']}", words=_words(c["expr"]))
    for s in systems:  # a system nothing flows from: the sheet says what a person must settle
        if s["code"] in seen_codes:
            continue
        smp = samples.get(s["id"]) or {}
        if smp.get("kind") == "pdf" and smp.get("fields"):
            for f in smp["fields"]:
                add(kind="read", system=s["name"], source_field=f"{f['name']} (marked)", bronze=f"bronze_{s['code']}_documents.text", silver="", gold="",
                    words=f"Read the value after '{f['where_usually']}' on every statement")
        elif smp.get("kind") == "table":
            add(kind="check", system=s["name"], source_field=f"{len(smp.get('columns') or [])} columns", bronze="", silver="", gold="",
                words="Sample kept; map it before it feeds a table", needs_person="Map this sample to the model before the builder can use it.")
        else:
            add(kind="check", system=s["name"], source_field="", bronze="", silver="", gold="", words="",
                needs_person=("Mark the fields to read on one statement." if s["format"] == "pdf" else "No approved mapping yet: show a sample and map it."))
    for n in notes:
        m = re.search(r"could not place the KPI '([^']+)'", n)
        if m:
            add(kind="derived", system="", source_field="", bronze="", silver="", gold=f"?.{_slug(m.group(1))}", words="", needs_person=f"Define {m.group(1)}: no table could be chosen for it.")
        m = re.search(r"Define the KPI '([^']+)': (.*)", n)
        if m:  # FIXC: a figure with no definition (or a condition the rules cannot write) is listed for a person, never silent
            add(kind="derived", system="", source_field="", bronze="", silver="", gold=f"?.{_slug(m.group(1))}", words="", needs_person=f"Define {m.group(1)}: {m.group(2)[:200]}")
    return rows


def _words(expr: str) -> str:
    e = expr.strip()
    m = re.fullmatch(r"(sum|avg|count|min|max)\((.*)\)", e, re.I)
    if m:
        return {"sum": "Sum of", "avg": "Average of", "count": "Count of", "min": "Lowest", "max": "Highest"}[m.group(1).lower()] + " " + m.group(2).split(".")[-1]
    m = re.fullmatch(r"date_trunc\('(\w+)',\s*(.*)\)", e, re.I)
    if m:
        return f"{m.group(1).capitalize()} of {m.group(2).split('.')[-1]}"
    return "As it is" if re.fullmatch(r"[\w.]+", e) else e[:120]


def _catalogue(plane, silver: list[dict], gold: list[dict], plan: dict, mapping: list[dict]) -> list[dict]:
    cat = {t["name"]: t for t in E.current(plane)["tables"]}
    src_of = {m["gold"]: m for m in mapping if m["gold"]}
    out = []
    for t in plan["tables"]:
        if t["layer"] == "bronze":
            out += [{"table": t["name"], "layer": "bronze", "column": c["name"], "meaning": f"{c.get('from') or c['name']} as landed", "source": t.get("source") or "",
                     "sensitivity": "internal"} for c in t["columns"]]
    for s in silver:
        if s["status"] == "proposed":
            out += [{"table": s["name"], "layer": "silver", "column": n, "meaning": "Proposed: " + s["note"], "source": "model change", "sensitivity": "internal"} for n in s["columns"]]
            continue
        c = cat.get(s["name"], {})
        out += [{"table": s["name"], "layer": "silver", "column": x["name"], "meaning": str(x.get("note") or _human(x["name"])), "source": "company model",
                 "sensitivity": "internal"} for x in c.get("columns", []) if x["name"] in s["columns"]]
    for g in gold:
        for c in g["columns"]:
            m = src_of.get(f"{g['name']}.{c['name']}")
            out.append({"table": g["name"], "layer": "gold", "column": c["name"], "meaning": c["definition"],
                        "source": (m or {}).get("silver") or "derived", "sensitivity": c["sensitivity"]})
    return out


def _rules(sow: dict, answers: dict, notes: list[str], block: dict | None = None) -> dict:
    checks = _answer(answers, "checks", _check_proposals(sow))
    fresh = _answer(answers, "freshness", _freshness(sow))
    return {"checks": checks, "history": _answer(answers, "history", []),
            "refresh": {k: fresh.get(k) for k in ("freq", "at", "day", "label")},
            "late_data": "A value that arrives late is marked estimated and the month is rerun when it arrives.",
            "benchmark": (f"checked against {block['code']} version {block['version']} for {block['portfolio']} in {block['month']}" if block and block.get("portfolio") and block.get("code")
                                                                else "asked later by the builder"), "access": _answer(answers, "access", {"narrower": []})}


def _pack_sources(systems: list[dict], samples: dict) -> list[dict]:
    return [{"id": s["id"], "code": s["code"], "name": s["name"], "format": s["format"], "channel": s["channel"], "frequency": s["frequency"],
             "owner": s["owner"], "connector": s.get("connector"), "sample": (samples.get(s["id"]) or {}).get("name"),
             "marked_fields": [f["name"] for f in (samples.get(s["id"]) or {}).get("fields") or []]} for s in systems]


def _text_of(sow: dict) -> str:
    return json.dumps({k: sow.get(k) for k in ("goal", "process", "kpis", "governance", "sources")}, default=str).lower()


def _benchmark_info(plane, sow: dict) -> dict | None:
    """The signed benchmark the intent means, read from the company's approved definitions: its code if the intent names it, else the one whose name shares
    two words with the intent, else the only one there is. {code, name, version, method, legs: [{key, spread, note}]}; None when there is none."""
    try:
        with wh.connect(plane, read_only=True) as con:
            rows = con.execute("select id, benchmark_code, benchmark_name, version_number, calculation_method from benchmark_definitions d where approval_status = 'approved' "
                               "and version_number = (select max(version_number) from benchmark_definitions x where x.benchmark_code = d.benchmark_code and x.approval_status = 'approved') "
                               "order by benchmark_code").fetchall()
            legs = {str(r[0]): con.execute("select market_series_key, coalesce(spread_bps, 0), coalesce(treatment_note, '') from benchmark_components where benchmark_definition_id = ? "
                                           "order by component_weight desc", [r[0]]).fetchall() for r in rows}
    except (OSError, duckdb.Error):
        return None
    text, words = _text_of(sow), set(re.findall(r"[a-z]{3,}", _text_of(sow)))
    pick = next((r for r in rows if r[1].lower() in text), None) or next(
        (r for r in rows if len(set(re.findall(r"[a-z]{3,}", f"{r[2]} {r[1]}".lower())) - {"benchmark"} & words) >= 2), None) or (rows[0] if len(rows) == 1 else None)
    if not pick:
        return None
    return {"code": pick[1], "name": pick[2], "version": pick[3], "method": pick[4] or "",
            "legs": [{"key": k, "spread": float(sp), "note": note} for k, sp, note in legs[str(pick[0])]]}


def _leg_name(leg: dict) -> str:
    """A leg as people say it: the sleeve's name when the treatment note gives one ('private-markets sleeve: equity index + 300 bps'), else the index in words."""
    from sh_platform.v1 import b9_verify as V
    note = str(leg.get("note") or "")
    if leg.get("spread") and ":" in note:
        return note.split(":")[0].strip().capitalize()
    return V.plain_name(leg["key"] + (" plus spread" if leg.get("spread") else ""))


def _definitions(sow: dict, plan: dict, info: dict | None) -> list[dict]:
    """One definition for each figure the pack computes (portfolio return, benchmark return, net worth) and for each other KPI of the intent. A signed
    definition is used as it is; the benchmark's comes from its signed version; anything else is Span's proposal and says so."""
    cols = {c["name"] for t in plan["tables"] if t["layer"] == "gold" for c in t.get("columns") or []}
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("name")]

    def signed(rx: str, skip: str = "") -> tuple[dict | None, str]:
        for k in kpis:
            name = str(k.get("name"))
            if re.search(rx, name, re.I) and not (skip and re.search(skip, name, re.I)) and (k.get("definition") or k.get("formula")):
                return k, str(k.get("definition") or k.get("formula"))
        return None, ""

    out, used = [], set()

    def add(name: str, rx: str, skip: str, rule: str, src: tuple[str, str] | None = None) -> None:
        k, d = signed(rx, skip)
        used.update(str(x.get("name")) for x in kpis if re.search(rx, str(x.get("name")), re.I) and not (skip and re.search(skip, str(x.get("name")), re.I)))
        out.append({"name": name, "definition": (src or ("", ""))[0] or d or rule,
                    "source": (src or ("", ""))[1] or ("Signed in the intent" if d else "Proposed by Span"), "signed": bool(src or d), "columns": []})

    if "portfolio_return" in cols:
        add("Portfolio return", r"return", r"benchmark", "The change in the portfolio's recorded value over the month, over its value at the month before; "
            "flows are not removed yet.")
    if "benchmark_return" in cols:
        add("Benchmark return", r"benchmark", "", "The weighted sum of the benchmark's legs.",
            ((f"{info['method']} The legs of {info['code']}, version {info['version']}: " + ", ".join(_leg_name(x).lower() for x in info["legs"]) + ".").strip(),
             f"Signed: benchmark version {info['version']}") if info else None)
    if "net_worth" in cols:
        add("Net worth", r"net worth", "", "Holdings by entity at the month end, from the valuations the company model records.")
    for k in kpis:
        if k["name"] not in used:
            d = str(k.get("definition") or k.get("formula") or "")
            out.append({"name": str(k["name"]), "definition": d or "Not defined yet.", "source": "Signed in the intent" if d else "Needs a definition", "signed": bool(d), "columns": []})
    return out


def _tie_definitions(defs: list[dict], gold: list[dict]) -> None:
    """Each definition lists the gold columns that carry it."""
    for d in defs:
        key = d["name"].lower().replace(" ", "_")
        d["columns"] = [f"{g['name']}.{c['name']}" for g in gold for c in g["columns"] if c["name"] == key]


def _benchmark_block(plane, viewer, sow: dict, gold: list[dict], info: dict | None, notes: list[str]) -> dict | None:
    """What the builder checks the run against: the portfolio, the signed benchmark and the month, and the figures to compare (portfolio return, benchmark
    return, difference). Worked out from the intent and the company's records: the portfolio the intent names (else the first the engineer may see), the
    signed benchmark, and the last month with recorded values. None when the pack draws no benchmark table."""
    table = next((g for g in gold if {"portfolio_return", "benchmark_return"} <= {c["name"] for c in g["columns"]}), None)
    if table is None:
        return None
    from sh_platform.v1 import k7_routes
    text = _text_of(sow)
    block = {"portfolio": "", "portfolio_name": "", "code": (info or {}).get("code", ""), "version": (info or {}).get("version"), "benchmark_name": (info or {}).get("name", ""),
             "month": "", "table": table["name"], "weights_table": next((g["name"] for g in gold if g["name"].endswith("_benchmark_weights")), None),
             "names": {x["key"] + (" plus spread" if x["spread"] else ""): _leg_name(x) for x in (info or {}).get("legs", [])},
             "figures": [{"key": "portfolio_return", "label": "Portfolio return", "unit": "pct"}, {"key": "benchmark_return", "label": "Benchmark return", "unit": "pct"},
                         {"key": "difference", "label": "Difference", "unit": "points"}]}
    try:
        with wh.connect(plane, read_only=True) as con:
            pfs = con.execute("select portfolio_code, portfolio_name, cast(id as varchar) from portfolios order by portfolio_code").fetchall()
            names = [set(re.findall(r"[a-z]{3,}", f"{n}".lower())) for _, n, _ in pfs]
            common = {w for ws in names for w in ws if sum(w in o for o in names) > 1}
            said = set(re.findall(r"[a-z]{3,}", text))
            def score(x):  # the code itself, then 'liquid portfolio' (a distinctive word of the name before the word portfolio), then any distinctive word of the name
                return -(x[0][0].lower() in text) * 20 - 5 * sum(f"{w} portfolio" in text for w in x[1] - common) - len((x[1] - common) & said)
            order = sorted(zip(pfs, names), key=lambda x: (score(x), x[0][0]))
            for (code, name, pid_), _ in order:
                try:
                    k7_routes._portfolio(plane, viewer, code)
                except Refused:
                    continue
                first = wh.today(plane).replace(day=1)
                got = con.execute("select max(date_trunc('month', valuation_date)) from valuation_observations where portfolio_id = ? and valuation_date < ?", [pid_, first]).fetchone()[0]
                block.update(portfolio=code, portfolio_name=name, month=str(got)[:7] if got else (first - timedelta(1)).strftime("%Y-%m"))
                break
    except (OSError, duckdb.Error):
        pass
    if not block["code"]:
        notes.append("No signed benchmark could be matched to the intent; name it so the builder can check the result against it.")
    if not block["portfolio"]:
        notes.append("No portfolio could be chosen for the benchmark check; name it so the builder can check the result against it.")
    return block


def _key_figures(gold: list[dict], block: dict | None) -> list[dict]:
    """The money figures of the report the builder checks the run on: for each gold table with a month and a money column, its total at the month and the
    figure split by its first name key (Total holdings; each fund)."""
    out = []
    for g in gold:
        when = next((c["name"] for c in g["columns"] if c["type"] == "DATE"), None)
        money = next((c["name"] for c in g["columns"] if c["type"].startswith("DECIMAL(18")), None)
        if not (when and money) or g["name"].endswith(("_benchmark_monthly", "_benchmark_weights")):
            continue
        label = "Total holdings" if "holdings" in g["name"] else "Net worth" if "net_worth" in g["name"] else _human(money)
        by = next((k for k in g["keys"] if k not in (when, "portfolio_code") and any(c["name"] == k and c["type"].startswith("VARCHAR") for c in g["columns"])), None)
        base = {"table": g["name"], "column": money, "agg": "sum", "unit": "money", "when": when}
        out.append({**base, "label": label})
        if by:
            out.append({**base, "label": _human(by), "by": by})
    return out


def generate(plane, viewer, pid: str, model=None) -> dict:
    """2c. Span drafts the design pack from the intent, the answers and the samples (rules first, the model only where the plan rules could
    not place a figure). A draft is rewritten in place keeping the corrections people made; after a proposal or approval it is a new version."""
    _need(viewer, SE.DATA_ENGINEER)
    prj, sow = _project(plane, pid)
    answers = _read(plane, pid, "pack-answers.json").get("answers") or {}
    samples = _read(plane, pid, "pack-samples.json")
    plan = S.draft_plan(plane, viewer, pid, None)  # the model is asked once, by the designer, for every figure the rules left
    plan = D.design(plane, viewer, pid, sow, plan, _grain(sow)[0], model)
    if not plan.get("new_silver") and (cv := D.change_view(plane, pid)) and cv["state"] == "proposed":  # a model change Span's chat filed for this project joins the pack
        plan.update(new_silver=cv["tables"], model_changes=cv["version"])
    plan = B.validate(plane, plan)  # FIXC: the use case's own gold tables; validate fills their columns
    hist = [h for h in _answer(answers, "history", []) if isinstance(h, str)]
    notes = list(plan.get("notes") or [])
    raiser = str((prj.get("people") or {}).get("raiser") or prj.get("started_by") or "")
    info = _benchmark_info(plane, sow)
    defs = _definitions(sow, plan, info)
    hist = list(dict.fromkeys(hist + [h for t in plan["tables"] if t["layer"] == "gold" for h in t.get("history") or []]))
    gold = _gold(plane, sow, plan, answers, raiser, hist, {d["name"].lower(): d["definition"] for d in defs})
    silver = _silver(plane, plan, hist, notes, gold, viewer, pid)
    block = _benchmark_block(plane, viewer, sow, gold, info, notes)
    pr = next((d for d in defs if d["name"] == "Portfolio return" and d["signed"] and "flow" in d["definition"].lower()), None)
    if pr and block:  # the gold table changes in value over the month; a month with trades or calls needs the flows taken out first
        notes.append("The signed portfolio return takes out net flows. The table works from recorded values and does not remove them yet, so it is exact only for months with no flows.")
    _tie_definitions(defs, gold)
    sums = summary(plane, viewer, pid)["systems"]
    mapping = _mapping(plane, plan, gold, sums, samples, notes)
    with lock_for(B.folder(plane, pid)):
        vs = versions(plane, pid)
        prev = get(plane, pid)
        if prev and prev["state"] == "draft":
            n, base = prev["version"], prev.get("base_version")
        else:
            n, base = (vs[-1] if vs else 0) + 1, (prev or {}).get("version")
        pack = {"project_id": pid, "version": n, "state": "draft", "base_version": base, "systems": sums_for_pack(sums), "target": {"silver": silver, "gold": gold},
                "mapping": mapping, "rules": _rules(sow, answers, notes, block), "sources": _pack_sources(sums, samples), "notes": notes,
                "benchmark": block, "key_figures": _key_figures(gold, block), "definitions": defs,
                "created_by": viewer.name, "created_by_id": str(viewer.account_id or viewer.name), "created_at": now(), "approved_by": None, "approved_at": None,
                "built_by": plan.get("built_by", "rules"), "plan_version": None, "model_change": plan.get("model_changes") if plan.get("new_silver") else None, "edits": (prev or {}).get("edits", []) if prev and prev["state"] == "draft" else []}
        pack["catalogue"] = _catalogue(plane, silver, gold, plan, mapping)
        if prev and prev["state"] == "draft":
            _carry(prev, pack)
        _save(plane, pack)
    _log(plane, pid, viewer, "drafted the design pack", pack["version"], f"{len(gold)} gold tables, {len(mapping)} mapping rows")
    return pack


def sums_for_pack(sums: list[dict]) -> list[dict]:
    return [{k: s[k] for k in ("id", "code", "name", "holds", "owner", "format", "channel", "frequency", "status", "connector", "confirmed", "corrected", "intent")}
            for s in sums]


def _carry(old: dict, new: dict) -> None:
    """A regenerated draft keeps what people corrected: gold columns' definitions and owners, resolved mapping rows."""
    og = {g["name"]: g for g in old["target"]["gold"]}
    for g in new["target"]["gold"]:
        o = og.get(g["name"])
        if not o:
            continue
        g["owner"] = o.get("owner") or g["owner"]
        oc = {c["name"]: c for c in o["columns"]}
        for c in g["columns"]:
            if c["name"] in oc and any(e["section"] == "gold_column" and e["key"] == f"{g['name']}.{c['name']}" for e in old.get("edits", [])):
                c.update({k: oc[c["name"]][k] for k in ("definition", "sensitivity", "expr", "type")})
    od = {d["name"]: d for d in old.get("definitions") or []}
    for d in new.get("definitions") or []:
        o = od.get(d["name"])
        if o and any(e["section"] == "definition" and e["key"] == d["name"] for e in old.get("edits", [])):
            d.update({k: o[k] for k in ("definition", "source", "signed")})
    for e in old.get("edits", []):
        if e["section"] == "benchmark" and new.get("benchmark"):
            new["benchmark"][e["field"]] = e["after"]
    om = {m["id"]: m for m in old["mapping"]}
    for m in new["mapping"]:
        o = om.get(m["id"])
        if o and (o.get("resolved") or o.get("edited")):
            m.update({k: o[k] for k in ("words", "resolved", "needs_person", "edited") if k in o})


# ---- correcting a line (versioned edits) -------------------------------------------------------------------------------------------

ALLOWED = {"gold_table": ("purpose", "grain", "keys", "owner", "history", "sql", "depends_on", "definitions"),
           "gold_add": ("purpose", "sql", "depends_on", "grain", "keys", "owner", "definitions"), "gold_remove": ("remove",), "gold_column": ("definition", "type", "sensitivity", "expr"),
           "silver": ("note",), "mapping": ("words", "formula", "resolve"), "rule_check": ("text", "tolerance"),
           "refresh": ("freq", "at", "day"), "rule": ("late_data", "benchmark"), "system": SYSTEM_FIELDS, "catalogue": ("meaning", "sensitivity"),
           "definition": ("definition",), "benchmark": ("portfolio", "code", "month")}


def _editable(plane, pid: str, viewer, version: int | None) -> dict:
    """The version a correction lands on: the draft in place; a proposed one goes back to draft; an approved one stays locked and forks a new draft."""
    pack = get(plane, pid, version)
    if pack is None:
        raise Refused(404, "There is no design pack yet. Ask Span to draft it.")
    last = (versions(plane, pid) or [0])[-1]
    if version and version != last:
        raise Refused(409, "Only the latest version can be corrected. Open the latest version.")
    if pack["state"] in ("approved", "superseded"):
        pack = {**json.loads(json.dumps(pack)), "version": last + 1, "state": "draft", "base_version": pack["version"], "approved_by": None, "approved_at": None,
                "created_by": viewer.name, "created_by_id": str(viewer.account_id or viewer.name), "created_at": now(), "edits": [], "plan_version": None}
    elif pack["state"] == "proposed":
        pack["state"] = "draft"
    return pack


def edit(plane, viewer, pid: str, section: str, key: str, changes: dict, note: str = "", version: int | None = None) -> dict:
    """Correct one line of the pack. Allowed fields per section are listed in ALLOWED; every change is recorded with who, when, before and after."""
    _need(viewer, SE.DATA_ENGINEER)
    if section not in ALLOWED:
        raise Refused(400, "That part of the pack cannot be corrected.")
    bad = [f for f in changes if f not in ALLOWED[section]]
    if bad or not changes:
        raise Refused(400, "That cannot be changed on this line: " + ", ".join(bad or ["nothing was given"]) + ".")
    with lock_for(B.folder(plane, pid)):
        pack = _editable(plane, pid, viewer, version)
        log_ = []

        def setf(obj: dict, f: str, v):
            before = obj.get(f)
            if before != v:
                obj[f] = v
                log_.append({"at": now(), "by": viewer.name, "by_id": _id(viewer), "section": section, "key": key, "field": f, "before": before, "after": v, "note": note[:300]})

        gold = {g["name"]: g for g in pack["target"]["gold"]}
        if section == "gold_add":  # FIXC: the head of data or the engineer adds a gold table: a name, what it is for and its select
            if key in gold:
                raise Refused(409, "The pack already has a table with that name; correct it instead.")
            g = {"name": key, "purpose": str(changes.get("purpose") or "").strip()[:300], "grain": str(changes.get("grain") or "").strip()[:200], "keys": [], "history": [],
                 "owner": str(changes.get("owner") or "").strip()[:100] or _id(viewer), "columns": [], "base_sql": None, "sql": str(changes.get("sql") or "").strip(),
                 "depends_on": _tables_of(changes.get("depends_on")), "kpis": []}
            _refresh_gold(plane, viewer, pid, pack, g, changes, adding=True)
            pack["target"]["gold"].append(g)
            log_.append({"at": now(), "by": viewer.name, "by_id": _id(viewer), "section": section, "key": key, "field": "added", "before": None, "after": g["grain"] or g["purpose"], "note": note[:300]})
        elif section == "gold_remove":
            if key not in gold:
                raise Refused(404, "There is no such table in the pack.")
            pack["target"]["gold"] = [x for x in pack["target"]["gold"] if x["name"] != key]
            pack["mapping"] = [m for m in pack["mapping"] if not m["gold"].startswith(key + ".")]
            pack["catalogue"] = [c for c in pack["catalogue"] if c["table"] != key]
            log_.append({"at": now(), "by": viewer.name, "by_id": _id(viewer), "section": section, "key": key, "field": "removed", "before": gold[key]["grain"], "after": None, "note": note[:300]})
        elif section in ("gold_table", "gold_column"):
            tname, _, cname = key.partition(".")
            g = gold.get(tname)
            if g is None:
                raise Refused(404, "There is no such table in the pack.")
            tgt = g if section == "gold_table" else next((c for c in g["columns"] if c["name"] == cname), None)
            if tgt is None:
                raise Refused(404, "There is no such column in the pack.")
            if section == "gold_table" and ({"sql", "depends_on"} & set(changes)):  # a table written as a select: columns, types and sources follow from it
                g.update(sql=str(changes.get("sql", g["sql"]) or "").strip(), depends_on=_tables_of(changes.get("depends_on", g["depends_on"])), base_sql=None)
                _refresh_gold(plane, viewer, pid, pack, g, changes)
                log_.append({"at": now(), "by": viewer.name, "by_id": _id(viewer), "section": section, "key": key, "field": "sql", "before": None, "after": g["sql"][:300], "note": note[:300]})
            for f, v in changes.items():
                if f in ("sql", "depends_on", "definitions"):
                    continue
                if f == "keys" or f == "history":
                    names = {c["name"] for c in g["columns"]}
                    if not isinstance(v, list) or not set(v) <= names:
                        raise Refused(400, f"{f} must be columns of {tname}.")
                    if f == "history":
                        for c in g["columns"]:
                            c["history"] = c["name"] in v
                if f == "expr":
                    _check_expr(v)
                setf(tgt, f, v if not isinstance(v, str) else v.strip())
            if section == "gold_column" and "expr" in changes:
                g["sql"] = _build_sql(g["name"], g)
        elif section == "silver":
            t = next((x for x in pack["target"]["silver"] if x["name"] == key), None)
            if t is None:
                raise Refused(404, "There is no such silver table in the pack.")
            [setf(t, f, str(v)[:300]) for f, v in changes.items()]
        elif section == "mapping":
            m = next((x for x in pack["mapping"] if x["id"] == key), None)
            if m is None:
                raise Refused(404, "There is no such mapping row.")
            for f, v in changes.items():
                if f == "words":
                    setf(m, "words", str(v)[:300])
                    m["edited"] = True
                elif f == "formula":
                    gt, _, gc = m["gold"].partition(".")
                    col = next((c for g in pack["target"]["gold"] if g["name"] == gt for c in g["columns"] if c["name"] == gc), None)
                    if col is None:
                        raise Refused(400, "Only a row that ends in a gold column has a formula.")
                    _check_expr(v)
                    log_.append({"at": now(), "by": viewer.name, "by_id": _id(viewer), "section": section, "key": key, "field": "formula", "before": col["expr"], "after": v.strip(), "note": note[:300]})
                    col["expr"] = v.strip()
                    gt_ = next(g for g in pack["target"]["gold"] if g["name"] == gt)
                    gt_["sql"] = _build_sql(gt, gt_)
                elif f == "resolve":
                    setf(m, "resolved", bool(v))
                    m["edited"] = True
                    if v and not (note or m.get("words")):
                        raise Refused(400, "Say in a few words how it was settled.")
                    if v and note:
                        m["words"] = note[:300]
        elif section == "rule_check":
            c = next((x for x in pack["rules"]["checks"] if x["id"] == key), None)
            if c is None:
                raise Refused(404, "There is no such check.")
            [setf(c, f, str(v)[:200]) for f, v in changes.items()]
        elif section == "refresh":
            r = pack["rules"]["refresh"]
            for f, v in changes.items():
                if f == "freq" and v not in B.FREQ:
                    raise Refused(400, "The schedule must be daily, weekly, monthly or on arrival.")
                setf(r, f, v)
        elif section == "rule":
            [setf(pack["rules"], f, str(v)[:300]) for f, v in changes.items()]
        elif section == "system":
            s = next((x for x in pack["systems"] if x["id"] == key), None)
            if s is None:
                raise Refused(404, "There is no such system in the pack.")
            prj = P1.read(plane, pid)
            correct_system(plane, viewer, prj["intent_id"], key, changes)  # the intent's system map and the pack change together
            [setf(s, f, str(v)[:200]) for f, v in changes.items()]
            for src in pack["sources"]:
                if src["id"] == key:
                    src.update({k: str(v)[:200] for k, v in changes.items() if k in src})
        elif section == "definition":
            d = next((x for x in pack.get("definitions") or [] if x["name"] == key), None)
            if d is None:
                raise Refused(404, "There is no such definition in the pack.")
            for f, v in changes.items():
                setf(d, f, str(v).strip()[:600])
            d["source"], d["signed"] = f"Corrected by {viewer.name}", False
            for ref in d.get("columns") or []:  # the columns that carry the figure say the same
                tn, _, cn = ref.partition(".")
                for g in pack["target"]["gold"]:
                    for col in g["columns"] if g["name"] == tn else []:
                        if col["name"] == cn:
                            col["definition"] = d["definition"]
        elif section == "benchmark":
            b = pack.get("benchmark")
            if b is None:
                raise Refused(404, "This pack has no benchmark check.")
            for f, v in changes.items():
                v = str(v).strip()
                if (f == "month" and not re.fullmatch(r"\d{4}-\d{2}", v)) or not v:
                    raise Refused(400, "Give the month like 2026-09, and the portfolio and benchmark by their codes.")
                setf(b, f, v)
        elif section == "catalogue":
            tname, _, cname = key.partition(".")
            c = next((x for x in pack["catalogue"] if x["table"] == tname and x["column"] == cname), None)
            if c is None:
                raise Refused(404, "There is no such catalogue line.")
            [setf(c, f, str(v)[:300]) for f, v in changes.items()]
            for g in pack["target"]["gold"]:
                if g["name"] == tname:
                    for col in g["columns"]:
                        if col["name"] == cname:
                            col["definition" if "meaning" in changes else "sensitivity"] = c["meaning" if "meaning" in changes else "sensitivity"]
        if not log_:
            return pack
        pack["edits"] = pack.get("edits", []) + log_
        pack["plan_version"] = None
        _save(plane, pack)
    _log(plane, pid, viewer, "corrected the design pack", pack["version"], f"{section} {key}")
    return pack


def _tables_of(v) -> list[str]:
    items = re.split(r"[\s,;]+", v.strip()) if isinstance(v, str) else v
    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        raise Refused(400, "depends_on is the list of tables the select reads.")
    return [x for x in items if x]


def _refresh_gold(plane, viewer, pid: str, pack: dict, g: dict, changes: dict, adding: bool = False) -> None:
    """FIXC: a gold table written (or rewritten) as a select: run it through the plan check with the pack's other tables, take its columns and types from the
    check, keep the definitions people already gave, list the new columns that still need one, and show the silver tables it reads as reused."""
    if not g["sql"]:
        raise Refused(400, "Give the select for the table: create table <name> as select ...")
    others = [x for x in pack["target"]["gold"] if x["name"] != g["name"]]
    want = [{"name": x["name"], "layer": "gold", "purpose": x["purpose"], "columns": [], "sql": _build_sql(x["name"], x), "depends_on": list(x["depends_on"])} for x in others + [g]]
    plan = S.draft_plan(plane, viewer, pid, None, pack_gold=want, model_changes=pack.get("model_change"))
    got = next((t for t in plan["tables"] if t["name"] == g["name"]), None)
    if got is not None:
        got = next(t for t in B.validate(plane, plan)["tables"] if t["name"] == g["name"])  # the check fills the columns and their types
    if got is None:
        why = [n for n in plan.get("notes") or [] if g["name"] in n]
        raise Refused(400, "The plan check refused " + g["name"] + ". " + " ".join(why)[:300])
    old = {c["name"]: c for c in g["columns"]}
    given = {str(k): str(v).strip()[:600] for k, v in (changes.get("definitions") or {}).items()} if isinstance(changes.get("definitions"), dict) else {}
    g["columns"] = [{"name": c["name"], "type": str(c["type"]).upper(), "expr": c["name"], "history": False,
                     "definition": given.get(c["name"]) or old.get(c["name"], {}).get("definition") or "Needs a definition",
                     "sensitivity": old.get(c["name"], {}).get("sensitivity", "internal")} for c in got["columns"]]
    g["depends_on"] = list(got["depends_on"])
    names = [c["name"] for c in g["columns"]]
    g["keys"] = [k for k in (changes.get("keys") if isinstance(changes.get("keys"), list) else g["keys"]) if k in names] or [c["name"] for c in g["columns"] if not c["type"].startswith(("DECIMAL", "DOUBLE", "BIGINT", "INTEGER"))][:3]
    g["grain"] = g["grain"] or ", ".join(_human(k) for k in g["keys"])
    pack["mapping"] = [m for m in pack["mapping"] if not (m["gold"].startswith(g["name"] + ".") and m["kind"] == "derived")]
    for c in g["columns"]:
        undefined = c["definition"] == "Needs a definition"
        pack["mapping"].append({"id": "m-" + _slug(f"{g['name']}|{c['name']}|derived", 60), "kind": "derived", "system": "", "source_field": "", "bronze": "", "silver": "",
                                "gold": f"{g['name']}.{c['name']}", "words": "Written in the table's select", "note": "", "resolved": False if undefined else True,
                                "needs_person": f"Define {c['name']} of {g['name']}." if undefined else ""})
    have = {s["name"] for s in pack["target"]["silver"]}
    cat = {t["name"]: t for t in E.current(plane)["tables"]}
    for d in g["depends_on"]:
        if d in cat and d not in have:
            have.add(d)
            pack["target"]["silver"].append({"name": d, "status": "reused", "history": [], "columns": [c["name"] for c in cat[d]["columns"]], "note": "Used as it is", "other_projects": [], "feeds_other": []})
    for c in g["columns"]:
        pack["catalogue"] = [x for x in pack["catalogue"] if not (x["table"] == g["name"] and x["column"] == c["name"])] + [
            {"table": g["name"], "layer": "gold", "column": c["name"], "meaning": c["definition"], "source": "derived", "sensitivity": c["sensitivity"]}]


def _check_expr(v) -> None:
    if not isinstance(v, str) or not v.strip():
        raise Refused(400, "Give the formula as a short expression.")
    try:
        e = sqlglot.parse_one(v, read="duckdb")
    except SqlglotError as x:
        raise Refused(400, f"That formula cannot be read: {str(x).splitlines()[0][:120]}") from None
    if e.find(exp.Subquery, exp.Select, exp.Drop, exp.Delete, exp.Update, exp.Command) is not None or ";" in v:
        raise Refused(400, "A formula is an expression over the table's columns, not a query.")


# ---- approval ------------------------------------------------------------------------------------------------------------------------

def _id(viewer) -> str:
    return str(getattr(viewer, "account_id", None) or viewer.name)


def makers(pack: dict) -> set[str]:
    """Everyone who drafted, corrected or sent this version: none of them may approve it (maker never checker)."""
    return {pack.get("created_by_id"), pack.get("submitted_by_id"), *(e.get("by_id") for e in pack.get("edits") or [])} - {None}


def open_rows(pack: dict) -> list[dict]:
    return [m for m in pack["mapping"] if m.get("needs_person") and not m.get("resolved")]


def submit(plane, viewer, pid: str, version: int | None = None) -> dict:
    """The engineer sends the pack to the head of data; rows that still need a person stop it."""
    _need(viewer, SE.DATA_ENGINEER)
    with lock_for(B.folder(plane, pid)):
        pack = get(plane, pid, version)
        if pack is None or pack["state"] != "draft":
            raise Refused(409, "Only a draft pack can be sent for approval.")
        if (rows := open_rows(pack)):
            raise Refused(409, f"{len(rows)} mapping row{'s' if len(rows) != 1 else ''} still need a person: settle them first.")
        pack.update(state="proposed", submitted_by_id=_id(viewer))
        _save(plane, pack)
    _log(plane, pid, viewer, "sent the design pack for approval", pack["version"])
    return pack


def approve(plane, viewer, pid: str, version: int | None = None, note: str = "") -> dict:
    """2d. The head of data approves and locks the pack. Never the person who made this version; an earlier approved version is superseded."""
    _need(viewer, HEAD)
    with lock_for(B.folder(plane, pid)):
        pack = get(plane, pid, version)
        if pack is None or pack["state"] != "proposed":
            raise Refused(409, "Only a pack sent for approval can be approved.")
        if _id(viewer) in makers(pack):
            raise Refused(403, "You made or changed this version, so someone else needs to approve it.")
        if open_rows(pack):
            raise Refused(409, "Some mapping rows still need a person.")
        for n in versions(plane, pid):
            o = get(plane, pid, n)
            if o and o["state"] == "approved" and n != pack["version"]:
                o["state"] = "superseded"
                _save(plane, o)
        pack.update(state="approved", approved_by=viewer.name, approved_by_id=str(viewer.account_id or viewer.name), approved_at=now(), approval_note=note[:300])
        _save(plane, pack)
    _log(plane, pid, viewer, "approved the design pack", pack["version"], note)
    return _approve_plan_with(plane, viewer, pid, pack, note)


def _approve_plan_with(plane, viewer, pid: str, pack: dict, note: str) -> dict:
    """FIXC: one approval by the head of data covers the pack, the model change it carries and the build plan drawn from it, so the builder can start.
    The plan is drawn as the pack's maker proposed it (the approver never proposes). When the plan cannot be drawn or approved the pack stays approved
    and says why; the head of data can retry from the screen (approve_plan)."""
    maker = types.SimpleNamespace(name=pack.get("created_by"), account_id=pack.get("submitted_by_id") or pack.get("created_by_id"))
    try:
        plan = _plan_from(plane, maker, pid, pack, None)
        B.approve(plane, viewer, pid, plan["version"], note=f"Approved with design pack version {pack['version']}. {note}".strip())
        pack.update(plan_error=None, plan_state="approved")
    except Refused as e:
        pack.update(plan_error=e.message, plan_state="not_approved")
    with lock_for(B.folder(plane, pid)):
        cur = get(plane, pid, pack["version"])
        cur.update(plan_error=pack["plan_error"], plan_state=pack["plan_state"])
        _save(plane, cur)
    return cur


def approve_plan(plane, viewer, pid: str) -> dict:
    """The head of data approves the build plan drawn from the approved pack when the one-step approval could not (a retry; the button on the pack screen)."""
    _need(viewer, HEAD)
    pack = latest_approved(plane, pid)
    if pack is None:
        raise Refused(409, "Approve the design pack first.")
    plan = B.get(plane, pid, pack.get("plan_version")) if pack.get("plan_version") else None
    if plan is None or plan["state"] != "proposed":
        maker = types.SimpleNamespace(name=pack.get("created_by"), account_id=pack.get("submitted_by_id") or pack.get("created_by_id"))
        plan = _plan_from(plane, maker, pid, pack, None)
    B.approve(plane, viewer, pid, plan["version"], note=f"Approved with design pack version {pack['version']}.")
    with lock_for(B.folder(plane, pid)):
        cur = get(plane, pid, pack["version"])
        cur.update(plan_error=None, plan_state="approved")
        _save(plane, cur)
    return cur


def reject(plane, viewer, pid: str, reason: str, version: int | None = None) -> dict:
    _need(viewer, HEAD)
    reason = str(reason or "").strip()
    if not reason:
        raise Refused(400, "Please say briefly why this pack is not right.")
    with lock_for(B.folder(plane, pid)):
        pack = get(plane, pid, version)
        if pack is None or pack["state"] != "proposed":
            raise Refused(409, "Only a pack sent for approval can be sent back.")
        pack.update(state="draft", send_back=reason[:500])
        _save(plane, pack)
    _log(plane, pid, viewer, "sent the design pack back", pack["version"], reason)
    return pack


# ---- versions: history and diff ------------------------------------------------------------------------------------------------------

def _flat(pack: dict) -> dict[str, str]:
    f: dict[str, str] = {}
    for g in pack["target"]["gold"]:
        for k in ("purpose", "grain", "owner"):
            f[f"gold {g['name']} {k}"] = str(g.get(k))
        f[f"gold {g['name']} keys"] = ", ".join(g["keys"])
        f[f"gold {g['name']} history"] = ", ".join(g["history"])
        for c in g["columns"]:
            f[f"gold {g['name']}.{c['name']}"] = f"{c['type']} | {c['expr']} | {c['definition']}"
    for s in pack["target"]["silver"]:
        f[f"silver {s['name']}"] = s["note"]
    for m in pack["mapping"]:
        f[f"mapping {m['id']}"] = f"{m['words']} | {m.get('needs_person') if not m.get('resolved') else 'settled'}"
    for c in pack["rules"]["checks"]:
        f[f"check {c['id']}"] = f"{c['text']} | {c['tolerance']}"
    for k, v in pack["rules"]["refresh"].items():
        f[f"refresh {k}"] = str(v)
    for d in pack.get("definitions") or []:
        f[f"definition {d['name']}"] = f"{d['definition']} | {d['source']}"
    for k, v in (pack.get("benchmark") or {}).items():
        if k in ("portfolio", "code", "version", "month"):
            f[f"benchmark {k}"] = str(v)
    for s in pack["systems"]:
        f[f"system {s['name']}"] = f"{s['channel']} | {s['frequency']} | {s['format']} | {s['owner']}"
    return f


def diff(plane, pid: str, a: int, b: int) -> dict:
    pa, pb = get(plane, pid, a), get(plane, pid, b)
    if pa is None or pb is None:
        raise Refused(404, "That version does not exist.")
    fa, fb = _flat(pa), _flat(pb)
    rows = [{"line": k, "change": "added", "before": None, "after": fb[k]} for k in fb if k not in fa]
    rows += [{"line": k, "change": "removed", "before": fa[k], "after": None} for k in fa if k not in fb]
    rows += [{"line": k, "change": "changed", "before": fa[k], "after": fb[k]} for k in fb if k in fa and fa[k] != fb[k]]
    return {"from": a, "to": b, "changes": rows}


def history(plane, pid: str) -> list[dict]:
    out = []
    for n in versions(plane, pid):
        p = get(plane, pid, n)
        out.append({"version": n, "state": p["state"], "by": p["created_by"], "at": p["created_at"], "approved_by": p.get("approved_by"), "approved_at": p.get("approved_at"),
                    "edits": len(p.get("edits") or []), "base_version": p.get("base_version"), "plan_version": p.get("plan_version")})
    return out


# ---- driving the b6 plan ---------------------------------------------------------------------------------------------------------------

def apply_to_plan(plane, viewer, pid: str, model=None) -> dict:
    """The approved pack drives the build plan: its gold tables (with their corrected formulas) replace the rules' gold tables, the rest of the
    plan is drawn as before, and the result is saved as the next plan version for the head of data. A table the plan check refuses stops it."""
    _need(viewer, SE.DATA_ENGINEER)
    pack = latest_approved(plane, pid)
    if pack is None:
        raise Refused(409, "Approve the design pack first. The plan is drawn from the approved version.")
    return _plan_from(plane, viewer, pid, pack, model)


def _plan_from(plane, viewer, pid: str, pack: dict, model=None) -> dict:
    want = [{"name": g["name"], "layer": "gold", "purpose": g["purpose"], "columns": [], "sql": _build_sql(g["name"], g), "depends_on": list(g["depends_on"])}
            for g in pack["target"]["gold"]]
    plan = S.draft_plan(plane, viewer, pid, model, pack_gold=want, model_changes=pack.get("model_change"))
    got = {t["name"] for t in plan["tables"]}
    if (lost := [w["name"] for w in want if w["name"] not in got]):
        why = [n for n in plan.get("notes") or [] if any(x in n for x in lost)]
        raise Refused(409, "The plan check refused " + ", ".join(lost) + ". " + " ".join(why)[:400])
    sc = pack["rules"]["refresh"]
    plan["schedule"] = {"freq": sc.get("freq") or "daily", "at": sc.get("at") or "06:00", "day": sc.get("day")}
    plan["pack_version"] = pack["version"]
    plan["own_batches"] = True  # the Pipelines page checks the files this plan's sources loaded, not the whole company's
    if (bm := pack.get("benchmark")) and bm.get("portfolio") and bm.get("code") and bm.get("month"):  # V6B: the builder compares the run with the report on this
        plan["benchmark"] = {k: bm[k] for k in ("portfolio", "code", "month", "names") if bm.get(k)}
    plan["key_figures"] = [dict(k) for k in pack.get("key_figures") or []]
    by_code = {x["code"][:24]: x for x in pack["sources"]}  # b6_span cuts a source code at 24 characters
    for src in plan.get("sources") or []:  # V6 integration: the builder (b11) connects each source as the pack says, so the plan carries how it arrives and the marked fields
        ps = by_code.get(str(src.get("code"))[:24])
        if ps:
            src["arrives"] = {k: v for k, v in {"how": ps.get("channel") or "upload", "connector": ps.get("connector")}.items() if v}
            src["fields"] = [{"name": n} for n in ps.get("marked_fields") or []]
    plan["notes"] = list(plan.get("notes") or []) + [f"Drawn from design pack version {pack['version']}, approved by {pack['approved_by']}."]
    plan = B.new_version(plane, pid, plan, viewer)
    with lock_for(B.folder(plane, pid)):
        cur = get(plane, pid, pack["version"])
        cur["plan_version"] = plan["version"]
        _save(plane, cur)
    _log(plane, pid, viewer, "drew the build plan from the design pack", plan["version"], f"pack version {pack['version']}")
    return plan


def view(plane, viewer, pid: str, version: int | None = None) -> dict:
    """The pack for the screen, with who may do what."""
    pack = get(plane, pid, version)
    seats = SE.seat_of(viewer)
    mine = pack is not None and _id(viewer) in makers(pack)
    st = (pack or {}).get("state")
    can = {"answer": SE.DATA_ENGINEER in seats, "generate": SE.DATA_ENGINEER in seats, "edit": SE.DATA_ENGINEER in seats and pack is not None,
           "submit": SE.DATA_ENGINEER in seats and st == "draft", "approve": HEAD in seats and st == "proposed" and not mine,
           "reject": HEAD in seats and st == "proposed", "plan": SE.DATA_ENGINEER in seats and st == "approved"}
    can["approve_plan"] = HEAD in seats and st == "approved" and (pack or {}).get("plan_state") == "not_approved"
    base = {"project_id": pid, "versions": history(plane, pid), "can": can, "model_change": D.change_view(plane, pid) if pack and pack.get("model_change") else None}
    if pack is None:
        return {**base, "pack": None}
    plan = B.get(plane, pid)
    return {**base, "pack": {**pack, "open_rows": len(open_rows(pack)), "locked": st == "approved",
                             "counts": {"sources": len(pack["sources"]), "gold": len(pack["target"]["gold"]), "silver": len(pack["target"]["silver"]),
                                        "mapping": len(pack["mapping"]), "checks": len(pack["rules"]["checks"])}},
            "plan_version": (plan or {}).get("version"), "log": [x for x in B.read_log(plane, pid) if "design" in x["what"] or "pack" in x["what"]][-20:]}
