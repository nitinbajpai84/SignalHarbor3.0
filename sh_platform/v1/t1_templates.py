"""T1 Templates: every output document follows a template the company has adopted (V1-BUILD Round 10).

Under the company plane: `templates/<id>.json` (the working copy), `templates/versions/<id>__v<n>.json` (a snapshot at each adoption;
a document started on version n keeps reading it), `templates/settings.json` {standard: {kind: id}}, `templates/log.json` (the change
log, also for skills and governance), `templates/examples/<eid>.json`, `templates/governance.json`, `templates/requests.json`.
Company skills live in `skills/<agent>/<file>.md` (the loader prefers them). An intent pins its template in
`intents/<iid>/template.json` {id, version, at}. Nothing here calls a model.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import skill_loader as SL
from sh_platform.v1 import t1_seeds as TS

Refused = N.Refused
KINDS = {"intent_of_work": "Intent of work", "process_map": "Process map", "definitions": "Business definitions",
         "benchmarks": "Benchmark sheet", "system_design": "System design", "data_model": "Data model",
         "build_pack": "Build pack", "run_book": "Run book", "consumption_brief": "Consumption brief"}
TYPES = ("text", "long_text", "list", "table", "number", "date", "person", "choice")
FREE = {"label": "Comments and anything else", "required": False}
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_KEY = re.compile(r"[a-z][a-z0-9_]{0,40}")
_FILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}\.md")
MAX_TEXT = 20000
MAX_FIELDS = 60
FREE_KEY = "comments"
SAMPLE_COMPANY = "ardmore-1"
SEED_VERSION = 2  # 2: sections (T1b) and two templates per kind
RESERVED = {"settings", "log", "governance", "requests"}  # files beside the templates


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


def need_admin(viewer) -> None:
    if not _is_admin(viewer):
        raise Refused(403, "Only your company admin can change templates, agent skills and rules.")


def _p(plane, *parts):
    return plane.path("templates", *parts)


def _read(path, kind=dict):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        raise Refused(500, "That could not be read. Please try again.") from None


def _clean_id(value) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise Refused(404, "We could not find that template.")
    return value


# ---- the change log ---------------------------------------------------------------------------------------------------------------

def log(plane, by: str, what: str, ref: str = "", note: str = "") -> None:
    path = _p(plane, "log.json")
    with lock_for(path):
        rows = _read(path, list) or []
        rows.append({"at": _now(), "by": by, "what": what, "ref": ref, "note": note})
        write_json_atomic(path, rows[-500:])


def change_log(plane, viewer) -> list[dict]:
    need_admin(viewer)
    return list(reversed(_read(_p(plane, "log.json"), list) or []))


# ---- seeds ------------------------------------------------------------------------------------------------------------------------

def _f(key, label, help_="", required=True, type_="long_text", **more) -> dict:
    return {"key": key, "label": label, "help": help_, "required": required, "type": type_, **more}


EXAMPLES = {  # two filled intents of work for the sample company, by field key
    "ex-monthly-wealth-report": ("Monthly wealth and performance report", {
        "goal": "A monthly wealth and performance report for the family council, so the council stops waiting for spreadsheets.",
        "readers": "The family council; they decide whether to rebalance and how much to draw.",
        "frequency": "By the eighth working day each month.",
        "process": "1. Custodian sends positions (operations). 2. Analyst copies them into the pack workbook. 3. Analyst checks totals "
                   "by hand. 4. Partner reviews and sends.",
        "result": "A pack with net worth, allocation, performance against benchmark and fees, one page per portfolio.",
        "kpis": ["Net worth: market value of all positions plus cash", "Time-weighted return, month and year to date",
                 "Fees paid, month and year to date"],
        "inputs": ["Custodian positions file (operations, by email)", "Cash ledger export (finance)"],
        "rules": "Family members see their own portfolios; partners see all; history kept ten years; the partner approves changes.",
        "success": "The pack goes out by the eighth working day with no manual copying and the totals agree with the custodian.",
        "unclear": ["Which benchmark applies to the growth portfolio (the partner can settle)"],
        "benchmarks": ["For September the pack reported net worth of 41.2 million; it should read the same within 0.1 percent."],
        FREE_KEY: "The council would also like a one-line commentary per portfolio."}),
    "ex-quarterly-fee-review": ("Quarterly fee review", {
        "goal": "A quarterly review of every fee we pay managers and custodians, so we can challenge the ones that drift.",
        "readers": "The investment committee; they decide which mandates to renegotiate.",
        "frequency": "Within ten working days of each quarter end.",
        "process": "1. Finance lists invoices. 2. Analyst matches each to its fee schedule. 3. Differences go to the committee chair.",
        "result": "A table of fees by manager against the agreed schedule, with differences marked.",
        "kpis": ["Fees paid against schedule, by manager", "Total cost as a share of assets"],
        "inputs": ["Invoices (finance, PDF by email)", "Fee schedules (legal, documents)"],
        "rules": "Committee members only; keep seven years; the chair approves any change.",
        "success": "Every invoice is matched to a schedule and each difference has an owner.",
        "unclear": ["Whether performance fees count in total cost (the committee chair can settle)"],
        "benchmarks": ["For the second quarter we reported 0.82 percent of assets; it should read the same within 0.02."],
        FREE_KEY: ""}),
}


def _hint(key: str) -> dict:
    """What North learns, the fixed question, parse need and default for a seed key, read from i6_chat's GOALS (read only)."""
    try:
        from sh_platform.v1.i6_chat import GOALS
        learn, ask, parse, default = GOALS[key]
        return {k: v for k, v in {"learn": learn, "ask": ask, "parse": parse, "default": default}.items() if v}
    except Exception:  # the seed still works without i6_chat's wording
        return {}


def _record(seed: dict, sample: bool = False) -> dict:
    secs = seed["sections"]
    rec = {"id": seed["id"], "kind": seed["kind"], "name": seed["name"], "description": seed["description"], "version": 1, "state": "adopted",
           "sections": secs, "fields": TS.fields_from(secs), "free_text": dict(FREE), "examples": [], "adopted_by": "Seeded",
           "adopted_at": _now(), "unadopted_changes": False}
    if seed.get("companions"):
        rec["companions"] = dict(seed["companions"])
    return rec


def _access():
    with __import__("contextlib").suppress(Exception):
        from sh_platform.v1 import g1_access as G1
        f = G1.template_field()
        return {**f, "label": f["label"], "help": f.get("help", "")}
    return None


def _write(plane, rec: dict) -> None:
    write_json_atomic(_p(plane, "versions", f"{rec['id']}__v1.json"), rec)
    write_json_atomic(_p(plane, f"{rec['id']}.json"), rec)


def _seed(plane) -> None:
    """Every seed template, written only where missing (so it also tops up a company seeded before T1b); the settings file goes last."""
    std = (_read(_p(plane, "settings.json")) or {}).get("standard") or {}
    for seed in TS.seeds(_hint, _access()):
        rec = _record(seed)
        if plane.company_id == SAMPLE_COMPANY and seed["id"] == "standard-intent-of-work":
            for eid, (title, values) in EXAMPLES.items():
                write_json_atomic(_p(plane, "examples", f"{eid}.json"), {"id": eid, "name": title, "template_id": rec["id"], "values": values})
                rec["examples"].append(eid)
        if not _p(plane, f"{rec['id']}.json").exists():
            _write(plane, rec)
        elif (old := TS.OLD_NAMES.get(rec["id"])) and (w := _read(_p(plane, f"{rec['id']}.json"))) and w.get("name") == old and w.get("adopted_by") == "Seeded":
            for path in [_p(plane, f"{rec['id']}.json"), *sorted(_p(plane, "versions").glob(f"{rec['id']}__v*.json"))]:  # the T1b names
                got = _read(path)
                if got:
                    write_json_atomic(path, {**got, "name": rec["name"], "description": rec["description"], **({"companions": rec["companions"]} if rec.get("companions") else {})})
        std.setdefault(rec["kind"], TS.STANDARD_IDS.get(rec["kind"]) or rec["id"])
    write_json_atomic(_p(plane, "settings.json"), {"standard": std, "seed": SEED_VERSION})


def ensure(plane) -> None:
    mark = _p(plane, "settings.json")
    if (read_json_strict(mark, dict) or {}).get("seed") == SEED_VERSION:
        return
    with lock_for(mark):
        if (read_json_strict(mark, dict) or {}).get("seed") != SEED_VERSION:
            _seed(plane)


# ---- reading ----------------------------------------------------------------------------------------------------------------------

def with_sections(rec: dict | None) -> dict | None:
    """A record written before T1b has no sections: they are made from its fields (the fields stay as they are)."""
    if rec and not rec.get("sections") and rec.get("fields"):
        rec = {**rec, "sections": TS.sections_from_fields(rec["fields"], rec.get("kind"))}
    return rec


def _working(plane, tid: str) -> dict:
    ensure(plane)
    rec = with_sections(_read(_p(plane, f"{_clean_id(tid)}.json")))
    if rec is None:
        raise Refused(404, "We could not find that template.")
    return rec


def _snapshot(plane, tid: str, version: int) -> dict | None:
    return with_sections(_read(_p(plane, "versions", f"{_clean_id(tid)}__v{int(version)}.json")))


def _standard(plane) -> dict:
    return (_read(_p(plane, "settings.json")) or {}).get("standard") or {}


def _all(plane) -> list[dict]:
    ensure(plane)
    files = [p for p in sorted(_p(plane).glob("*.json")) if p.stem not in RESERVED]
    return [with_sections(r) for r in (_read(p) for p in files) if isinstance(r, dict) and r.get("id") and r.get("kind")]


def template_for(plane, kind: str, template_id: str | None = None, version: int | None = None) -> dict | None:
    """The template a document follows. An id (and optional pinned version) gives that one as adopted: the snapshot, so edits not yet
    adopted never reach a person. No id gives the company's standard for the kind, else any adopted one, else None."""
    ensure(plane)
    if template_id:
        w = _working(plane, template_id)
        if w.get("kind") != kind:
            return None
        v = version or w.get("version") or 0
        return _snapshot(plane, w["id"], v) if v else None
    std = _standard(plane).get(kind)
    for tid in ([std] if std else []) + [r["id"] for r in _all(plane) if r["kind"] == kind and r.get("state") == "adopted"]:
        got = template_for(plane, kind, tid)
        if got and _working(plane, tid).get("state") == "adopted":
            return got
    return None


def _example_list(plane, r: dict) -> list[dict]:
    out = []
    for eid in r.get("examples") or []:
        try:
            out.append({"id": eid, "name": example(plane, eid)["name"]})
        except Refused:
            pass
    return out


def _summary(plane, r: dict, std: dict, shown: dict | None = None) -> dict:
    s = shown or r  # the fields people read are the adopted version's
    fields = s.get("fields") or []
    return {"id": r["id"], "kind": r["kind"], "kind_name": KINDS.get(r["kind"], r["kind"]), "name": s.get("name"),
            "description": s.get("description", ""), "version": r.get("version", 0), "state": r.get("state"),
            "standard": std.get(r["kind"]) == r["id"], "required": [f["label"] for f in fields if f.get("required")],
            "good_to_have": [f["label"] for f in fields if not f.get("required")], "examples": _example_list(plane, s),
            "unadopted_changes": bool(r.get("unadopted_changes")), "adopted_by": r.get("adopted_by"), "adopted_at": r.get("adopted_at"),
            "outline": [{k: x.get(k) for k in ("key", "heading", "required", "type", "columns", "view")} for x in s.get("sections") or []],
            "companions": companions_of(plane, s)}


def listing(plane, viewer, kind: str | None = None, every: bool = False) -> list[dict]:
    """What a person may choose: adopted templates as adopted. The admin's `every` adds drafts and retired ones (working copies)."""
    if every:
        need_admin(viewer)
    ensure(plane)
    std, out = _standard(plane), []
    for r in _all(plane):
        if kind and r["kind"] != kind:
            continue
        if every:
            out.append(_summary(plane, r, std))
        elif r.get("state") == "adopted" and r.get("version"):
            out.append(_summary(plane, r, std, _snapshot(plane, r["id"], r["version"])))
    return sorted(out, key=lambda x: not x["standard"])  # the company's standard first


def get(plane, viewer, tid: str) -> dict:
    """One template: the admin reads the working copy, anyone else the adopted version."""
    w = _working(plane, tid)
    if _is_admin(viewer):
        return {**w, "summary": _summary(plane, w, _standard(plane))}
    if w.get("state") != "adopted":
        raise Refused(404, "We could not find that template.")
    return _snapshot(plane, tid, w["version"]) or w


def example(plane, eid: str) -> dict:
    ensure(plane)
    got = _read(_p(plane, "examples", f"{_clean_id(eid)}.json"))
    if got is None:
        raise Refused(404, "We could not find that example.")
    return got


# ---- the admin's changes ----------------------------------------------------------------------------------------------------------

def _fields(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_FIELDS:
        raise Refused(422, "A template needs at least one field.")
    out, seen = [], set()
    for f in raw:
        if not isinstance(f, dict):
            raise Refused(422, "Each field needs a key and a label.")
        key, label = str(f.get("key") or "").strip(), " ".join(str(f.get("label") or "").split())
        if not _KEY.fullmatch(key) or key == FREE_KEY or not label or key in seen:
            raise Refused(422, f"The field \"{label or key}\" needs a label and its own short key (letters, digits and underscores).")
        seen.add(key)
        typ = f.get("type") if f.get("type") in TYPES else "text"
        row = {"key": key, "label": label[:200], "help": str(f.get("help") or "")[:600], "required": f.get("required") is True, "type": typ}
        if typ == "choice":
            row["choices"] = [str(c)[:80] for c in f.get("choices") or [] if str(c).strip()][:30]
        if typ == "table":
            row["columns"] = [str(c)[:60] for c in f.get("columns") or [] if str(c).strip()][:12]
        for extra in ("ask", "default", "learn", "parse"):  # North's wording, kept when the admin does not touch it
            if f.get(extra):
                row[extra] = str(f[extra])[:600]
        out.append(row)
    return out


def _sections(raw, prior) -> list[dict]:
    """Sections from the admin: each is checked as a field (key, heading, type) and keeps its instruction, example and view."""
    if not isinstance(raw, list):
        raise Refused(422, "A template needs at least one section.")
    fields = _fields([{**x, "label": x.get("heading") or x.get("label"), "help": x.get("instruction") or x.get("help")} for x in raw if isinstance(x, dict)])
    by = {x.get("key"): x for x in raw if isinstance(x, dict)}
    out = TS.sections_from_fields(fields, None, prior)
    for sct in out:
        given = by.get(sct["key"]) or {}
        sct["example"] = str(given.get("example", sct.get("example", "")))[:400]
        if given.get("view") in ("swimlane", "steps", "table", "cards"):
            sct["view"] = given["view"]
    return out


def create(plane, viewer, body: dict) -> dict:
    need_admin(viewer)
    ensure(plane)
    src = _working(plane, body["from_id"]) if body.get("from_id") else None
    kind = src["kind"] if src else body.get("kind")
    if kind not in KINDS:
        raise Refused(422, "Choose which document the template is for.")
    name = " ".join(str(body.get("name") or "").split())[:120]
    if not name:
        raise Refused(422, "Give the template a name.")
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or kind
    tid, n = base, 2
    while _p(plane, f"{tid}.json").exists() or tid in RESERVED:
        tid, n = f"{base}-{n}", n + 1
    rec = {"id": tid, "kind": kind, "name": name, "description": str(body.get("description") or (src or {}).get("description") or "")[:400],
           "version": 0, "state": "draft", "fields": (src or {}).get("fields") or [_f("summary", "Summary", "", True)],
           "sections": (src or {}).get("sections") or TS.sections_from_fields([_f("summary", "Summary", "", True)]),
           **({"companions": src["companions"]} if src and src.get("companions") else {}),
           "free_text": dict(FREE), "examples": list((src or {}).get("examples") or []), "adopted_by": None, "adopted_at": None,
           "unadopted_changes": True}
    write_json_atomic(_p(plane, f"{tid}.json"), rec)
    log(plane, viewer.name, "created template", tid, f"from {src['id']}" if src else "")
    return rec


def edit(plane, viewer, tid: str, body: dict) -> dict:
    need_admin(viewer)
    path = _p(plane, f"{_clean_id(tid)}.json")
    with lock_for(path):
        rec = _working(plane, tid)
        if rec["state"] == "retired":
            raise Refused(409, "This template is retired. Create a new one from it.")
        if "name" in body:
            rec["name"] = " ".join(str(body["name"]).split())[:120] or rec["name"]
        if "description" in body:
            rec["description"] = str(body["description"])[:400]
        if "sections" in body:  # the sections are the template; the fields follow from them
            rec["sections"] = _sections(body["sections"], rec.get("sections"))
            rec["fields"] = TS.fields_from(rec["sections"])
        elif "fields" in body:
            rec["fields"] = _fields(body["fields"])
            rec["sections"] = TS.sections_from_fields(rec["fields"], rec.get("kind"), rec.get("sections"))
        rec["unadopted_changes"] = True
        write_json_atomic(path, rec)
    log(plane, viewer.name, "edited template", tid)
    return rec


def adopt(plane, viewer, tid: str, standard: bool = False) -> dict:
    """Adopting versions it: a snapshot is kept; documents already started keep the version they began on."""
    need_admin(viewer)
    path = _p(plane, f"{_clean_id(tid)}.json")
    with lock_for(path):
        rec = _working(plane, tid)
        rec.update(version=int(rec.get("version") or 0) + 1, state="adopted", adopted_by=viewer.name, adopted_at=_now(),
                   unadopted_changes=False)
        write_json_atomic(_p(plane, "versions", f"{rec['id']}__v{rec['version']}.json"), rec)
        write_json_atomic(path, rec)
        std = _standard(plane)
        if standard or rec["kind"] not in std:
            write_json_atomic(_p(plane, "settings.json"), {**_read(_p(plane, "settings.json")), "standard": {**std, rec["kind"]: rec["id"]}})
    log(plane, viewer.name, "adopted template", tid, f"version {rec['version']}")
    return rec


def retire(plane, viewer, tid: str) -> dict:
    need_admin(viewer)
    path = _p(plane, f"{_clean_id(tid)}.json")
    with lock_for(path):
        rec = _working(plane, tid)
        rec["state"] = "retired"
        write_json_atomic(path, rec)
        std = _standard(plane)
        if std.get(rec["kind"]) == rec["id"]:
            others = [r["id"] for r in _all(plane) if r["kind"] == rec["kind"] and r["id"] != rec["id"] and r.get("state") == "adopted"]
            std = {k: v for k, v in std.items() if k != rec["kind"]}
            if others:
                std[rec["kind"]] = others[0]
            write_json_atomic(_p(plane, "settings.json"), {**_read(_p(plane, "settings.json")), "standard": std})
    log(plane, viewer.name, "retired template", tid)
    return rec


# ---- what the agents read ---------------------------------------------------------------------------------------------------------

def goals_from(template: dict | None) -> dict:
    """North's goals in i6_chat.GOALS' shape: key -> (what to learn, the fallback's question, I2's parse need or None, default).
    Must-fill fields first (they decide "done"), then good-to-have ones, then the free text, offered last."""
    if not template:
        return {}
    fields = template.get("fields") or []
    out = {}
    for f in [x for x in fields if x.get("required")] + [x for x in fields if not x.get("required")]:
        label = f.get("label") or f["key"]
        out[f["key"]] = (f.get("learn") or f.get("help") or label.lower(), f.get("ask") or f"{label}?", f.get("parse") or None,
                         f.get("default") or None)
    free = template.get("free_text") or FREE
    out[FREE_KEY] = (free.get("label", FREE["label"]).lower(), "Is there anything else you would like to add?", None, "nothing more")
    return out


def required_keys(template: dict | None) -> list[str]:
    return [f["key"] for f in (template or {}).get("fields") or [] if f.get("required")]


_SOW = {  # a required field also counts as filled when the statement of work already holds it, by kind of document
    "intent_of_work": {
        "goal": lambda s: (s.get("goal") or {}).get("line"), "readers": lambda s: (s.get("goal") or {}).get("readers"),
        "frequency": lambda s: (s.get("goal") or {}).get("needed_by"), "process": lambda s: (s.get("process") or {}).get("steps"),
        "kpis": lambda s: s.get("kpis"), "inputs": lambda s: s.get("sources"), "rules": lambda s: s.get("governance"),
        "benchmarks": lambda s: _benchmarks(s)},
    "process_map": {"steps": lambda s: (s.get("process") or {}).get("steps"), "handovers": lambda s: (s.get("process") or {}).get("handovers")},
    "definitions": {"kpis": lambda s: s.get("kpis")},
}
_ALIAS = {("process_map", "steps"): ("process",), ("definitions", "kpis"): ("kpis",)}  # the intent of work's own answer to the same slot
COMPANIONS = ("process_map", "definitions")


def _benchmarks(sow: dict) -> list | None:
    """NU-03: the benchmark slot is the KPIs' benchmarks: filled when every figure the person asked for has one, either rows on the
    benchmark sheet with a reported figure (G3 pointer) or the person's "none" (None). A suggested KPI not yet confirmed does not count."""
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict) and not (k.get("pack_suggested") and k.get("status") == "unclear")]
    ok = lambda b: b is None or (isinstance(b, dict) and b.get("reported") is not None)  # noqa: E731
    return [k.get("benchmark") for k in kpis] if kpis and all("benchmark" in k and ok(k["benchmark"]) for k in kpis) else None


def _has(v) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    return v is not None and v != [] and v != {}


def missing_required(template: dict | None, record: dict | None) -> list[str]:
    """Labels of the must-fill fields still empty. A field is filled when a value is held: `record[key]`, `record["values"][key]`,
    `record["template_fields"][key]` (written by North or edited on the document), or the statement of work slot of a built-in field.
    A goal North ticked, or settled as unclear, is not a value."""
    rec = record or {}
    values = {**(rec.get("values") or {}), **(rec.get("template_fields") or {})}
    kind = (template or {}).get("kind") or "intent_of_work"
    out = []
    for f in (template or {}).get("fields") or []:
        k = f["key"]
        keys = (k, *_ALIAS.get((kind, k), ()))
        slot = _SOW.get(kind, {}).get(k)
        if f.get("required") and not (_has(rec.get(k)) or any(_has(values.get(x)) for x in keys) or (slot and _has(slot(rec)))):
            out.append(f.get("label") or k)
    return out


# ---- an intent and its template ---------------------------------------------------------------------------------------------------

def companions_of(plane, template: dict | None, named_only: bool = False) -> dict:
    """The process map and definitions templates an intent template names: {kind: {id, name}}; the company's standard where it names none
    (unless `named_only`)."""
    out = {}
    for kind in COMPANIONS:
        tid = ((template or {}).get("companions") or {}).get(kind)
        t = template_for(plane, kind, tid) if tid else None
        t = t or (None if named_only else template_for(plane, kind))
        if t:
            out[kind] = {"id": t["id"], "name": t["name"]}
    return out


def choose(plane, iid: str, template_id: str | None = None) -> dict:
    """Pin the template (id and its current adopted version) on the intent, with the companions it names (process map, definitions); no
    id pins the company's standard. A pin never changes afterwards, except that a companion may be switched (`switch`)."""
    path = N._path(plane, iid, "template.json")
    with lock_for(path):
        had = _read(path)
        if had:
            return had
        t = template_for(plane, "intent_of_work", template_id)
        if t is None or _working(plane, t["id"]).get("state") != "adopted":
            raise Refused(404, "We could not find that template.")
        pin = {"id": t["id"], "version": t["version"], "at": _now()}
        pin["companions"] = {k: {"id": c["id"], "version": template_for(plane, k, c["id"])["version"]} for k, c in companions_of(plane, t, True).items()}
        write_json_atomic(path, pin)
    return pin


def switch(plane, iid: str, kind: str, template_id: str) -> dict:
    """Change the process map or definitions template of an intent. The content is the statement of work's, not the template's, so it stays."""
    if kind not in COMPANIONS:
        raise Refused(422, "Only the process map and the definitions template can be switched.")
    if record_for_intent(plane, iid).get("state") == "signed":
        raise Refused(409, "The intent of work is signed. Its templates can no longer change.")
    t = template_for(plane, kind, template_id)
    if t is None or _working(plane, template_id).get("state") != "adopted":
        raise Refused(404, "We could not find that template.")
    choose(plane, iid)  # an intent that began before templates is pinned to the standard first
    path = N._path(plane, iid, "template.json")
    with lock_for(path):
        pin = _read(path) or {}
        pin["companions"] = {**(pin.get("companions") or {}), kind: {"id": t["id"], "version": t["version"]}}
        write_json_atomic(path, pin)
    return pin


def for_intent(plane, iid: str, kind: str = "intent_of_work") -> dict | None:
    """The template this intent follows at the version it started on; the company's standard when none was chosen. `kind` asks for
    a companion (process map, definitions): the pinned one, else the one the intent template names, else the company's standard."""
    pin = _read(N._path(plane, iid, "template.json"))
    if kind == "intent_of_work":
        return template_for(plane, kind, pin["id"], pin["version"]) if pin else template_for(plane, kind)
    mine = ((pin or {}).get("companions") or {}).get(kind)
    if mine and (got := template_for(plane, kind, mine["id"], mine["version"])):
        return got
    named = companions_of(plane, for_intent(plane, iid)).get(kind)
    return template_for(plane, kind, named["id"]) if named else template_for(plane, kind)


def record_for_intent(plane, iid: str) -> dict:
    sow = _read(N._path(plane, iid, "sow.json")) or {}
    return sow


def sign_block(plane, iid: str) -> str | None:
    """Why the intent of work cannot be signed yet (a must-fill section of its templates is empty), or None. Intents with no pinned
    template began before templates and are not checked. Sections of the process map and definitions are named with their document."""
    if _read(N._path(plane, iid, "template.json")) is None:
        return None
    sow = record_for_intent(plane, iid)
    gaps = []
    pinned = (_read(N._path(plane, iid, "template.json")) or {}).get("companions") or {}
    for kind in ("intent_of_work", *(k for k in COMPANIONS if k in pinned)):  # a companion counts when the template named it or the person switched it
        t = for_intent(plane, iid, kind)
        gaps += [(f"{KINDS[kind]}: {g}" if kind != "intent_of_work" else g) for g in (missing_required(t, sow) if t else [])]
    return ("The intent of work cannot be signed yet. Still to fill in: " + "; ".join(gaps) + ".") if gaps else None


def check_sign(plane, iid: str, error) -> None:
    """For the sign hooks (same shape as p1_project.check_sign): raise `error(sentence)` when `sign_block` has one."""
    block = sign_block(plane, iid)
    if block:
        raise error(block)


# ---- governance rules -------------------------------------------------------------------------------------------------------------

def governance(plane) -> dict:
    return _read(_p(plane, "governance.json")) or {"version": 0, "rules": [], "by": None, "at": None}


def governance_rules(plane) -> list[str]:
    """The sentences Span bakes into every design, each with its owner."""
    return [f"{r['rule']} (owner: {r.get('owner') or 'the company admin'})" for r in governance(plane)["rules"]]


def save_governance(plane, viewer, rules) -> dict:
    need_admin(viewer)
    if not isinstance(rules, list) or len(rules) > 100:
        raise Refused(422, "Send the rules as a list.")
    clean = []
    for r in rules:
        r = r if isinstance(r, dict) else {}
        text = " ".join(str(r.get("rule") or "").split())[:400]
        if text:
            clean.append({"rule": text, "owner": " ".join(str(r.get("owner") or "").split())[:80]})
    path = _p(plane, "governance.json")
    with lock_for(path):
        rec = {"version": governance(plane)["version"] + 1, "rules": clean, "by": viewer.name, "at": _now()}
        write_json_atomic(_p(plane, "governance_versions", f"v{rec['version']}.json"), rec)
        write_json_atomic(path, rec)
    log(plane, viewer.name, "changed governance rules", "governance", f"version {rec['version']}, {len(clean)} rules")
    return rec


# ---- agent skills per company -----------------------------------------------------------------------------------------------------

def _agent(name: str) -> str:
    if name not in SL.agents():
        raise Refused(404, "We could not find that agent.")
    return name


def _skill_file(name: str) -> str:
    if not _FILE.fullmatch(str(name)):
        raise Refused(422, "A skill file has a short lower-case name ending in .md.")
    return name


def skills(plane, viewer) -> list[dict]:
    need_admin(viewer)
    return [{"agent": a, "label": SL.skill_label(a, plane), "files": [
        {"name": n, "source": "company" if SL.is_company(p, plane) else "repo", "text": p.read_text(encoding="utf-8")}
        for n, p in SL.skill_files(a, plane).items()]} for a in SL.agents()]


def _keep(plane, agent: str, name: str, text: str) -> None:
    keep = plane.path("skills", agent, "_versions")
    keep.mkdir(parents=True, exist_ok=True)
    n = len(list(keep.glob(f"{name[:-3]}__v*.md"))) + 1
    (keep / f"{name[:-3]}__v{n}.md").write_text(text, encoding="utf-8")


def save_skill(plane, viewer, agent: str, name: str, text) -> dict:
    need_admin(viewer)
    agent, name = _agent(agent), _skill_file(name)
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise Refused(422, "Write the skill as plain text (not empty, not too long).")
    cur = SL.skill_files(agent, plane).get(name)
    dest = plane.path("skills", agent, name)
    with lock_for(dest):
        if cur is not None:  # what is replaced is kept, numbered
            _keep(plane, agent, name, cur.read_text(encoding="utf-8"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text.strip() + "\n", encoding="utf-8")
    log(plane, viewer.name, "changed agent skill", f"{agent}/{name}")
    return {"agent": agent, "name": name, "source": "company"}


def reset_skill(plane, viewer, agent: str, name: str) -> dict:
    """Back to the repo's default: the company's copy is removed (a numbered copy stays in the versions folder)."""
    need_admin(viewer)
    agent, name = _agent(agent), _skill_file(name)
    dest = plane.path("skills", agent, name)
    if dest.is_file():
        _keep(plane, agent, name, dest.read_text(encoding="utf-8"))
        dest.unlink()
    log(plane, viewer.name, "returned agent skill to the default", f"{agent}/{name}")
    return {"agent": agent, "name": name, "source": "repo"}


# ---- requests (until the ticket centre T2 exists; T2 migrates this file) ----------------------------------------------------------

def raise_request(plane, viewer, body: dict) -> dict:
    kind = body.get("kind") if body.get("kind") in ("template", "skill") else "template"
    text = " ".join(str(body.get("text") or "").split())[:1000]
    if not text:
        raise Refused(422, "Say in a line what you need.")
    path = _p(plane, "requests.json")
    with lock_for(path):
        rows = _read(path, list) or []
        row = {"id": f"REQ-{len(rows) + 1:04d}", "kind": kind, "about": str(body.get("about") or "")[:120], "text": text,
               "by": viewer.name, "by_id": getattr(viewer, "account_id", None), "at": _now(), "state": "open", "note": ""}
        rows.append(row)
        write_json_atomic(path, rows)
    try:  # T2: the request is also a ticket to the company admin; this row stays as the admin console's list
        from sh_platform.v1 import t2_tickets
        if to := (t2_tickets.admins(plane) or [None])[0]:
            t2_tickets.raise_guarded(plane, by=viewer.name, to=to, title=f"{'Skill' if kind == 'skill' else 'Template'} request: {text}"[:120], body=text, stage="intent",
                                     links=[{"kind": "file", "ref": f"templates/requests.json#{row['id']}"}])
    except ImportError:
        pass
    return row


def requests(plane, viewer) -> list[dict]:
    need_admin(viewer)
    return list(reversed(_read(_p(plane, "requests.json"), list) or []))


def answer_request(plane, viewer, rid: str, state: str, note: str = "") -> dict:
    need_admin(viewer)
    if state not in ("done", "declined", "open"):
        raise Refused(422, "Choose done, declined or open.")
    path = _p(plane, "requests.json")
    with lock_for(path):
        rows = _read(path, list) or []
        row = next((r for r in rows if r["id"] == rid), None)
        if row is None:
            raise Refused(404, "We could not find that request.")
        row.update(state=state, note=str(note)[:400], answered_by=viewer.name, answered_at=_now())
        write_json_atomic(path, rows)
    log(plane, viewer.name, f"marked request {state}", rid)
    return row
