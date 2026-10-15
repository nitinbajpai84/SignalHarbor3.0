"""Span's and Flow's suggestions (plan BUILD-AGENTS-SPAN-FLOW 3.3): an agent proposes, a named person accepts, declines or asks.

The kinds are a closed list (KINDS), each with a schema the arguments are checked against. During an agent run the propose tool only collects
(`AgentResult.proposals`); after the run the caller hands the items to `file()`, which re-validates them, drops any whose numbers do not trace
to this run's tool facts, removes duplicates of open ones, caps the run at three and writes `build/proposals/P-<n>.json`. Only the accept route
applies anything, under the person's name: a model_change opens a change note (chain.open_note), an architecture_decision adds a stated
decision line to the change note, an incident_note acknowledges the alert. A signed record is never touched.

Reuse: the earlier emitters/proposals.py (doc L1-30, STATUSES L57, `_req` L115-133, `validate` L385-414), reshaped to JSON files in the plane.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.agents import guard
from sh_platform.agents.groups import group_ok
from sh_platform.build import alerts, chain
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()

STATES = ("proposed", "accepted", "declined", "asked", "superseded")
OPEN = ("proposed", "asked")
PID = re.compile(r"P-\d{4,6}")
MAX_TEXT = 2000
PER_RUN = 3
DAILY_CAP = 20  # ponytail: one fixed cap per company per day (Q5); a company setting when a customer asks
EFFORT = ("small", "medium", "large")
COMMON = {"title": (str, True), "what": (str, True), "why": (str, True), "technique": (str, False), "evidence": (dict, False),
          "impact": (dict, False), "alternatives": (list, False), "effort": (str, False), "cites": (list, False)}
KINDS: dict[str, dict] = {
    "model_change": {"from": {"Span", "Flow"}, "schema": {**COMMON, "technique": (str, True), "subject": (str, True), "measure": (str, False)}},  # a model change always names its technique (SF09b)
    "architecture_decision": {"from": {"Span"}, "schema": {**COMMON, "change_id": (str, True), "placement": (str, True), "options": (list, True),
                                                           "chosen": (str, True), "follows": (str, False)}},
    "incident_note": {"from": {"Flow"}, "schema": {**COMMON, "alert_id": (str, True), "next_step": (str, False)}},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _rd(path, empty=None) -> Any:
    try:
        d = read_json_strict(path)
    except (OSError, ValueError):
        log.warning("a proposal input could not be read")
        return empty
    return empty if d is None else d


# ---- checks ---------------------------------------------------------------------------------------------------------------------------

def _req(params: dict, schema: dict[str, tuple[type, bool]]) -> dict:
    """Copied from the earlier emitters/proposals.py: required keys present, types right, unknown keys refused."""
    clean: dict[str, Any] = {}
    for name, (typ, required) in schema.items():
        v = params.get(name)
        if v is None or v == "" or v == []:
            if required:
                raise ValueError(f"'{name}' is required")
            continue
        if not isinstance(v, typ):
            raise ValueError(f"'{name}' must be {typ.__name__}")
        clean[name] = v
    extra = set(params) - set(schema)
    if extra:
        raise ValueError(f"unexpected parameter(s): {', '.join(sorted(extra))}")
    return clean


def validate(kind: str, args: dict) -> dict:
    """The arguments of one proposal, cleaned; ValueError in plain words when they break the kind's schema."""
    if kind not in KINDS:
        raise ValueError(f"unknown proposal kind {kind!r}")
    if not isinstance(args, dict):
        raise ValueError("the arguments must be an object")
    c = _req(args, KINDS[kind]["schema"])
    for k, v in c.items():
        if isinstance(v, str):
            if len(v) > MAX_TEXT:
                raise ValueError(f"'{k}' is longer than {MAX_TEXT} characters")
            c[k] = v.strip()
    if c.get("effort") not in (None, *EFFORT):
        raise ValueError("effort must be small, medium or large")
    ev = c.get("evidence") or {}
    if set(ev) - {"counts", "fields", "queries"}:
        raise ValueError("evidence holds counts, fields and queries only")
    for x in ev.get("counts") or []:
        if not (isinstance(x, dict) and set(x) == {"label", "value", "group_size"} and group_ok(x.get("group_size"))):
            raise ValueError("each evidence count is {label, value, group_size} over a group of five or more")
    for k in ("fields", "queries"):
        if not all(isinstance(s, str) and len(s) <= 200 for s in ev.get(k) or []):
            raise ValueError(f"evidence {k} are short names")
    im = c.get("impact") or {}
    if set(im) - {"contracts", "marts", "dashboards"} or not all(isinstance(s, str) for v in im.values() for s in (v or [])):
        raise ValueError("impact names contracts, marts and dashboards only")
    if not all(isinstance(a, dict) and set(a) <= {"option", "why_not"} and a.get("option") for a in c.get("alternatives") or []):
        raise ValueError("each alternative is {option, why_not}")
    if not all(isinstance(x, dict) and set(x) <= {"source", "passage_id"} for x in c.get("cites") or []):
        raise ValueError("each citation is {source, passage_id}")
    if kind == "architecture_decision":
        if len(c["options"]) < 2 or not all(isinstance(o, str) for o in c["options"]) or c["chosen"] not in c["options"]:
            raise ValueError("a decision has at least two options and the choice is one of them")
        if not chain.CID.fullmatch(c["change_id"]):
            raise ValueError("change_id is not a change note id")
    if kind == "model_change" and c.get("measure") and not re.fullmatch(r"[A-Za-z0-9_]{1,20}", c["measure"]):
        raise ValueError("measure is a measure code")
    return c


# ponytail: slowly changing type words are names, not figures; a pack-driven list if techniques with other numbers appear
_TYPE_WORDS = re.compile(r"(?i)\b(?:scd|type)[\s_-]?[0-6]\b|\btypes\s+[0-6](?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)[0-6])*\b")
_NAMEISH = re.compile(r"(?=\S*[A-Za-z])(?=\S*\d)[\w.:/-]+")


def figures_trace(text: str, facts: list[dict], names=(), allowed: str = "") -> bool:
    """Every figure in `text` traces to `facts` (the guard's rule). Cut out first: slowly changing type words, and each listed name that holds
    a letter and a digit (K12, org_03_statements, gold.k12.nav), as a whole word. Unlike listing names in the guard's question (SF09's
    workaround), a bare figure that equals the digits inside a name is still checked (SF14). `allowed`: the company's own definition text
    (a check's bounds), whose figures may be repeated."""
    t = _TYPE_WORDS.sub(" ", str(text or ""))
    words = {w.strip(".:/-") for n in names if n for w in re.findall(r"[\w.:/-]+", str(n))}
    words = {w for w in words if _NAMEISH.fullmatch(w)}
    for w in sorted(words, key=len, reverse=True):
        t = re.sub(r"(?<![\w.-])" + re.escape(w) + r"(?![\w-])", " ", t, flags=re.I)
    return guard.check_numbers(t, facts, allowed).ok


def _texts(c: dict) -> list[str]:
    """Every word a person reads in a proposal: the prose, the technique, the next step, the decision words and the alternatives (SF14)."""
    out = [str(c.get(k) or "") for k in ("title", "what", "why", "technique", "subject", "placement", "chosen", "follows", "next_step")]
    return out + [str(o) for o in c.get("options") or []] + [str(a.get(k) or "") for a in c.get("alternatives") or [] for k in ("option", "why_not")]


def _traces(c: dict, facts: list[dict], names=(), allowed: str = "") -> bool:
    """Every evidence count and every figure in the words traces to this run's tool facts. Names that may hold digits: the item's own
    identifiers (measure, subject, decision words, evidence fields, impact names, ids) and `names` from the caller."""
    src = guard._sources(facts)
    ev, im = c.get("evidence") or {}, c.get("impact") or {}
    if any(guard._value(x["value"]) not in src for x in ev.get("counts") or []):
        return False
    ids = [c.get(k) for k in ("measure", "subject", "placement", "chosen", "change_id", "alert_id")] + list(c.get("options") or [])         + list(ev.get("fields") or []) + list(ev.get("queries") or []) + [n for v in im.values() for n in v or []] + list(names)
    return all(figures_trace(t, facts, ids, allowed) for t in _texts(c))


def _target(kind: str, c: dict) -> str:
    if kind == "model_change":
        return f"model:{view.norm(c['subject'])}"
    if kind == "architecture_decision":
        return f"decision:{c['change_id']}:{view.norm(c['placement'])}"
    return f"alert:{c['alert_id']}"


# ---- store ----------------------------------------------------------------------------------------------------------------------------

def _folder(plane):
    return plane.path("build", "proposals")


def _path(plane, pid: str):
    if not PID.fullmatch(str(pid)):
        raise ValueError("not a proposal id")
    return plane.path("build", "proposals", f"{pid}.json")


def all_proposals(plane) -> list[dict]:
    f = _folder(plane)
    out = [_rd(p) for p in sorted(f.glob("P-*.json"))] if f.is_dir() else []
    return [p for p in out if isinstance(p, dict) and PID.fullmatch(str(p.get("id")))]


def read(plane, pid: str) -> dict | None:
    try:
        p = _path(plane, pid)
    except ValueError:
        return None
    d = _rd(p) if p.is_file() else None
    return d if isinstance(d, dict) else None


def _blueprint(plane) -> dict:
    d = _rd(plane.path("build", "blueprint.json"), {})
    return d if isinstance(d, dict) else {}


def _alert(plane, aid: str) -> dict | None:
    return next((a for a in alerts._read(plane) if a.get("id") == aid), None)


def _addressee(plane, kind: str, c: dict) -> tuple[str | None, str, dict]:
    """(name, role word, what the proposal saw). model_change: the measure's data owner, else the blueprint signer, else the charter's
    architect. architecture_decision: the architect on the change note. incident_note: the alert's tell person."""
    if kind == "model_change":
        bp = _blueprint(plane)
        seen = {"blueprint_version": bp.get("version")}
        if c.get("measure"):
            from sh_platform.consume import cards
            try:
                if o := cards.data_owner(plane, c["measure"].upper()):
                    return o, "data owner", seen
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                log.warning("the data owner could not be read")
        signer = next((s.get("name") for s in reversed(bp.get("signed_by") or []) if isinstance(s, dict) and s.get("name")), None)
        if signer:
            return signer, "blueprint signer", seen
        return chain.people_of(plane, {})["architect"]["name"], "architect", seen
    if kind == "architecture_decision":
        note = _rd(plane.path("build", "changes", f"{c['change_id']}.json"), {}) or {}
        if not note.get("id"):
            return None, "architect", {}
        ppl = chain.people_of(plane, chain._intent(plane, note.get("intent_id")))
        return ppl["architect"]["name"], "architect", {"change_state": note.get("state")}
    a = _alert(plane, c["alert_id"]) or {}
    return a.get("tell"), "alert contact", {"alert_state": a.get("state"), "source": a.get("source")}


def file(plane, agent: str, items: list[dict], run_meta: dict) -> list[dict]:
    """File the proposals one agent run collected. run_meta: {run_id, facts (AgentResult.tool_facts), outside_seen, intent_id, and optionally
    definitions (the company's check texts whose figures may be repeated), change_id or alert_id (the one target a run that read outside
    material may name)}.
    Returns the records written; invalid, untraced, duplicate, unaddressed and over-cap items are dropped (logged, never raised)."""
    facts = run_meta.get("facts") or []
    out: list[dict] = []
    with lock_for(_folder(plane) / "_seq"):
        have = all_proposals(plane)
        open_targets = {(p["kind"], p.get("target")) for p in have if p.get("state") in OPEN}
        today = _now()[:10]
        room = DAILY_CAP - sum(1 for p in have if str(p.get("created_at", ""))[:10] == today)
        n = max([int(p["id"][2:]) for p in have] + [0])
        for it in items or []:
            if len(out) >= min(PER_RUN, room):
                break
            kind = (it or {}).get("kind") if isinstance(it, dict) else None
            try:
                if agent not in KINDS.get(kind, {}).get("from", ()):
                    raise ValueError(f"{agent} may not propose {kind!r}")
                c = validate(kind, it.get("args") or {})
            except ValueError as e:
                log.info("a proposal was refused: %s", e)
                continue
            names = [(_alert(plane, c["alert_id"]) or {}).get("source")] if kind == "incident_note" else []
            if not _traces(c, facts, names, str(run_meta.get("definitions") or "")):
                log.info("a proposal was dropped: a number does not trace to this run's facts")
                continue
            target = _target(kind, c)
            if (kind, target) in open_targets:
                continue
            outside = bool(it.get("outside_seen") or run_meta.get("outside_seen"))
            key = "alert_id" if kind == "incident_note" else "change_id"
            if outside and kind != "model_change" and c.get(key) != run_meta.get(key):
                log.info("a proposal was dropped: a run that read outside material may not pick its target")
                continue
            # outside material never picks the addressee: the measure (which names a data owner) is not used to address it (3.3 point 4)
            to, to_role, seen = _addressee(plane, kind, {k: v for k, v in c.items() if not (outside and k == "measure")})
            if not to:
                log.info("a proposal was dropped: nobody to address it to")
                continue
            n += 1
            extra = {k: c[k] for k in KINDS[kind]["schema"] if k not in COMMON and k in c}
            rec = {"id": f"P-{n:04d}", "kind": kind, "by_agent": agent, "fix_by": "Span" if kind == "model_change" else None, "to": to, "to_role": to_role,
                   "intent_id": run_meta.get("intent_id"), "change_id": c.get("change_id"), "target": target, "title": c["title"], "what": c["what"],
                   "technique": c.get("technique"), "why": c["why"],
                   "evidence": {"counts": [], "fields": [], "queries": [], **(c.get("evidence") or {})},
                   "impact": {"contracts": [], "marts": [], "dashboards": [], **(c.get("impact") or {})},
                   "alternatives": c.get("alternatives") or [], "effort": c.get("effort"), "cites": c.get("cites") or [], **extra,
                   "seen": seen, "outside_seen": outside, "state": "proposed", "thread": [], "decided": None,
                   "run_id": run_meta.get("run_id"), "created_at": _now()}
            _folder(plane).mkdir(parents=True, exist_ok=True)
            write_json_atomic(_path(plane, rec["id"]), rec)
            open_targets.add((kind, target))
            out.append(rec)
    for rec in out:
        if rec.get("intent_id"):
            from sh_platform.intents import events
            events.try_append(plane, rec["intent_id"], f"{agent.lower()}_drafted", agent.lower(), {"store": "build.proposals", "id": rec["id"]},
                              {"what": "suggestion", "ref": rec["id"]}, "draft")
    return out


# ---- who sees and who decides ---------------------------------------------------------------------------------------------------------

def _hidden(plane, viewer: view.Viewer, p: dict) -> bool:
    """A proposal on a restricted measure follows the measure's access list (blueprint._hidden)."""
    if not p.get("measure"):
        return False
    from sh_platform.build import blueprint
    bp = _blueprint(plane)
    return bool(bp.get("access")) and str(p["measure"]).lower() in blueprint._hidden(bp, viewer)


def is_addressee(viewer: view.Viewer, p: dict) -> bool:
    return chain._is(viewer, p.get("to"))


def visible(plane, viewer: view.Viewer, p: dict) -> bool:
    if _hidden(plane, viewer, p):
        return False
    return bool(chain.BUILD_USERS & set(viewer.roles)) or is_addressee(viewer, p)


def shown(viewer: view.Viewer, p: dict) -> dict:
    return {**p, "can_decide": p.get("state") in OPEN and is_addressee(viewer, p),
            "outside_note": "Span read outside material for this." if p.get("outside_seen") else None}


# ---- applying an accepted proposal ----------------------------------------------------------------------------------------------------

NOT_READY = "Not available yet: the change-note step is not ready"


def _quote(p: dict) -> list[dict]:
    src, who = f"build/proposals/{p['id']}.json", p.get("by_agent") or "Span"
    ln = lambda t: {"text": str(t)[:MAX_TEXT], "mark": "guessed", "from": src, "by": "Span", "at": _now()}  # noqa: E731
    out = [ln(f"From {who}'s suggestion {p['id']}: {p.get('title')}"), ln(f"What: {p.get('what')}"), ln(f"Why: {p.get('why')}")]
    return out + [ln(f"Evidence: {c['label']}: {c['value']}") for c in (p.get("evidence") or {}).get("counts") or []]


def open_from_proposal(plane, proposal: dict, by: str) -> dict:
    """An accepted model_change opens a change note through chain.open_note (marked from P-n). The "Why" section quotes the proposal;
    the people come from the Initiative, else the newest signed charter. {"error": ...} when the chain step is not ready."""
    open_note = getattr(chain, "open_note", None)
    if open_note is None:
        return {"error": "not_ready", "message": NOT_READY}
    codes = [str(proposal["measure"]).upper()] if proposal.get("measure") else sorted(
        {m.split(".")[1].upper() for m in (proposal.get("impact") or {}).get("marts") or [] if m.startswith("gold.") and m.count(".") >= 1})
    sections = {k: [] for k in chain.SECTIONS}
    sections["why"] = _quote(proposal)
    src = f"build/proposals/{proposal['id']}.json"
    sections["tests"] = [{"text": f"{c}: our figure matches the reported figure for every reported period", "mark": "guessed", "from": src, "by": "Span",
                          "at": _now(), "measure": c, "check": "catalogue", "href": "/centre/build/prove"} for c in codes]
    if any((n.get("source") or {}).get("id") == proposal["id"] for n in chain.all_notes(plane)):
        return {}
    iid = proposal.get("intent_id")
    people = {r: v["name"] for r, v in chain.people_of(plane, chain._intent(plane, iid)).items()}
    source = {"kind": "proposal", "id": proposal["id"], "accepted_by": by}
    if iid and any(n.get("intent_id") == iid for n in chain.all_notes(plane)):
        source["intent_id"] = iid  # linked only once the Initiative has its own note, or chain.ensure would never open that one
    return open_note(plane, proposal.get("title") or "A model change", sections, people, source, "Span")


def _apply(plane, viewer: view.Viewer, p: dict) -> tuple[dict | None, JSONResponse | None]:
    """Re-check the target is still where the proposal saw it, then apply. Returns ({result}, None) or (None, error)."""
    if p["kind"] == "model_change":
        if _blueprint(plane).get("version") != (p.get("seen") or {}).get("blueprint_version"):
            return None, _err(409, "stale", "The model changed since this was suggested. Ask Span to review it again.")
        note = open_from_proposal(plane, p, viewer.name)
        if note.get("error"):
            return None, _err(409, "not_ready", note["message"])
        if not note.get("id"):
            return None, _err(409, "already_open", "A change note is already open for this suggestion.")
        return {"change_id": note["id"]}, None
    if p["kind"] == "architecture_decision":
        path = plane.path("build", "changes", f"{p['change_id']}.json")
        with lock_for(path):
            note = _rd(path, {}) or {}
            if note.get("state") != "with_architect":
                return None, _err(409, "stale", "The change note has moved on from the design step.")
            others = [o for o in p["options"] if o != p["chosen"]]
            text = f"{p['placement']}: {p['chosen']}, because {p['why']}. Other option: {', '.join(others)}." + (f" Then: {p['follows']}." if p.get("follows") else "")
            note["sections"]["decisions"].append({"text": text[:MAX_TEXT], "mark": "stated", "from": f"build/proposals/{p['id']}.json", "by": viewer.name,
                                                  "at": _now(), "placement": p["placement"], "options": p["options"], "chosen": p["chosen"], "why": p["why"],
                                                  "follows": p.get("follows")})
            write_json_atomic(path, note)
        return {"change_id": p["change_id"]}, None
    a = _alert(plane, p["alert_id"])
    if not a or a.get("state") != "open":
        return None, _err(409, "stale", "The alert is no longer open.")
    alerts.act(plane, p["alert_id"], "ack", viewer.name, p["what"])
    return {"alert_id": p["alert_id"]}, None


def _remember(plane, p: dict, accepted: bool, reason: str | None) -> None:
    """3.5: a decided model_change becomes a company decision in Span's memory (modelling.remember_decision), when that card has landed."""
    if p["kind"] != "model_change":
        return
    tech, subj = p.get("technique") or "the change", p.get("subject")
    text = f"Chose {tech} for {subj} because {p.get('why')}" if accepted else f"Declined {tech} for {subj}: {reason}"
    try:
        from sh_platform.build.agents import modelling
        modelling.remember_decision(plane, text[:MAX_TEXT])
    except (ImportError, AttributeError, TypeError, OSError, ValueError):
        log.info("the decision was not remembered: decision memory is not available")


# ---- Pulse ----------------------------------------------------------------------------------------------------------------------------

def pulse_lines(plane, viewer: view.Viewer) -> dict[str, list[dict]]:
    """{decide: [...]}: one line per open proposal addressed to this person (decision lines are never cut by the daily cap, R10)."""
    from sh_platform.pulse.lines import line
    out = []
    for p in all_proposals(plane):
        if p.get("state") not in OPEN or not is_addressee(viewer, p) or _hidden(plane, viewer, p):
            continue
        rec = f"build/proposals/{p['id']}.json"
        if p["kind"] == "incident_note":
            src = str((p.get("seen") or {}).get("source") or "pipeline").replace("_", " ")
            out.append(line(f"proposal:{p['id']}", "request", f"Span wrote a note on the {src} alert. Check it.", p["id"], "/centre/build/ops",
                            "Open the alert", rec, p.get("created_at")))
            continue
        subj = p.get("subject") or p.get("placement") or p.get("title")
        title = (f"Span suggests a model change for {subj}. Decide." if p["by_agent"] == "Flow" else f"Span suggests a change to {subj}. Decide.")
        out.append(line(f"proposal:{p['id']}", "decision", title, p["id"], "/centre/build/blueprint#suggestions", "Open the suggestion", rec, p.get("created_at")))
    return {"decide": out}


# ---- routes ---------------------------------------------------------------------------------------------------------------------------

def _ctx(request: Request, pid: str | None = None):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return None, _err(403, "forbidden", "This company space cannot be opened.")
    if pid is None:
        return (plane, viewer, None), None
    p = read(plane, pid)
    if p is None or not visible(plane, viewer, p):
        return None, _err(404, "not_found", "There is no such suggestion.")
    return (plane, viewer, p), None


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


def _text(b: dict, key: str) -> str | None:
    v = b.get(key)
    return v.strip()[:MAX_TEXT] if isinstance(v, str) and v.strip() else None


@router.get("/api/company/build/proposals")
def get_proposals(request: Request):
    c, e = _ctx(request)
    if e:
        return e
    plane, viewer, _ = c
    rows = [shown(viewer, p) for p in reversed(all_proposals(plane)) if visible(plane, viewer, p)]
    return {"proposals": rows, "empty": None if rows else "Span has no suggestions right now."}


@router.get("/api/company/build/proposals/{pid}")
def get_proposal(request: Request, pid: str):
    c, e = _ctx(request, pid)
    return e or shown(c[1], c[2])


def _decide(request: Request, pid: str):
    c, e = _ctx(request, pid)
    if e:
        return None, e
    plane, viewer, p = c
    if not is_addressee(viewer, p):
        return None, _err(403, "forbidden", f"Only {p.get('to') or 'the named person'} may decide this suggestion.")
    if p.get("state") not in OPEN:
        return None, _err(409, "decided", "This suggestion has already been decided.")
    return c, None


def _event(plane, viewer: view.Viewer, p: dict, decision: str) -> None:
    if p.get("intent_id"):
        from sh_platform.intents import events
        events.try_append(plane, p["intent_id"], "proposal_decided", {"account": viewer.account_id or viewer.name, "name": viewer.name, "role": ""},
                          {"store": "build.proposals", "id": p["id"]}, {"pid": p["id"], "decision": decision}, "act")


@router.post("/api/company/build/proposals/{pid}/accept")
async def post_accept(request: Request, pid: str):
    c, e = _decide(request, pid)
    if e:
        return e
    plane, viewer, p = c
    with lock_for(_path(plane, pid)):
        p = read(plane, pid) or p
        if p.get("state") not in OPEN:
            return _err(409, "decided", "This suggestion has already been decided.")
        p = {**p, "decided": {"by": viewer.name, "at": _now(), "reason": None}}
        result, err = _apply(plane, viewer, p)
        if err:
            return err
        p = {**p, "state": "accepted", "result": result}
        write_json_atomic(_path(plane, pid), p)
    _event(plane, viewer, p, "accepted")
    _remember(plane, p, True, None)
    return shown(viewer, p)


@router.post("/api/company/build/proposals/{pid}/decline")
async def post_decline(request: Request, pid: str):
    b = await _body(request)
    c, e = _decide(request, pid)
    if e:
        return e
    plane, viewer, p = c
    if not (why := _text(b, "reason")):
        return _err(422, "invalid", "Say why you decline it.")
    with lock_for(_path(plane, pid)):
        p = read(plane, pid) or p
        if p.get("state") not in OPEN:
            return _err(409, "decided", "This suggestion has already been decided.")
        p = {**p, "state": "declined", "decided": {"by": viewer.name, "at": _now(), "reason": why}}
        write_json_atomic(_path(plane, pid), p)
    _event(plane, viewer, p, "declined")
    _remember(plane, p, False, why)
    return shown(viewer, p)


@router.post("/api/company/build/proposals/{pid}/ask")
async def post_ask(request: Request, pid: str):
    b = await _body(request)
    c, e = _decide(request, pid)
    if e:
        return e
    plane, viewer, p = c
    if not (q := _text(b, "text")):
        return _err(422, "invalid", "Write your question.")
    with lock_for(_path(plane, pid)):
        p = read(plane, pid) or p
        p = {**p, "state": "asked", "thread": [*(p.get("thread") or []), {"by": viewer.name, "text": q, "at": _now()}]}
        write_json_atomic(_path(plane, pid), p)
    _event(plane, viewer, p, "asked")
    return shown(viewer, p)
