"""Spec 43: the Decision intent. Start questions, option cards, notes, North's drafts, and the decider's three choices.

Writes go through store.update_intent (lock, version check, index row); refusals reuse records._run. North drafts here from the records
the acting person may see (earlier closed decisions in the same areas, the named measures or processes, the linked intent) through the
kernel agent runtime and the egress gateway (R14, north._call); word rules are only the fallback, marked `fallback: true` so the screen
says so. North never chooses, never fills the Why, never writes a number it cannot trace.
Ruling 25: the decider's act records the decision and confirms; the intent moves to `closing` and the organiser closes it (spec 09).
"""
import json
import logging
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request

from sh_platform.graph.read import graph_for
from sh_platform.graph.versions import append_version
from sh_platform.intents import events as E
from sh_platform.intents import lifecycle as L
from sh_platform.intents import north as N
from sh_platform.intents import store as S
from sh_platform.intents.records import _accounts, _areas, _person, _run

log = logging.getLogger(__name__)
router = APIRouter()

# Open question 8 and 3 of spec 43, proposed limits taken as they stand until reviewed.
ADVISERS_MAX, QUESTION_MAX, NAME_MAX, NOTE_MAX, REASON_MAX, TEXT_MAX = 5, 140, 60, 300, 400, 400
LATER_DAYS, LONG_DAYS, OPTIONS_MAX, REC_MIN_OPTIONS = 5, 10, 4, 2
OWNER_ONLY = "Only the card's owner or the decider can decide this"
NOT_DECIDER = "Only the decider can do this."
NOT_OPEN = "This decision is no longer open."
UNKNOWN_COST = "Not known. Needs: a quote or an estimate."
LONG_NOTE = "That is longer than a decision should take. Consider an Initiative."
SYSTEM = ("You are North. You help one named person decide; you never decide, pick, rank or score. Use only the question, the records "
          "and the notes in the context. Never write a number that is not in them. Plain English, British spelling, no names of people.")
ASK_OPTIONS = ("Draft two to four distinct option cards for this decision. Reply with ONLY one JSON object "
               '{"options": [{"name": "at most 60 characters", "means": "one sentence", "for": ["short line"], "against": ["short line"], '
               '"refs": ["ref of each record it rests on"]}]}')
ASK_LEAN = ("Say which one option the records and notes lean to, with one clause of reason. You do not decide. Reply with ONLY one JSON "
            'object {"option_id": "id from the context", "because": "one clause", "refs": ["ref of each record it rests on"]}')


# ---- who is who --------------------------------------------------------------------------------------------------------------

def _roles(rec: dict, viewer) -> set[str]:
    p = rec.get("people") or {}
    out = {r for r in ("organiser", "decider") if S._named(p.get(r), viewer)}
    if any(S._named(a, viewer) for a in p.get("advisers") or []):
        out.add("adviser")
    return out


def _load(plane, viewer, intent_id: str) -> tuple[dict, set[str]]:
    rec = S.read_intent(plane, intent_id)
    tier = S.tier_of(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if tier is None or rec["type"] != "decision":
        raise LookupError(intent_id)
    return rec, _roles(rec, viewer)


def _need(ok: bool, message: str, status: int = 403) -> None:
    if not ok:
        raise L.Refused(status, message)


def _text(v, limit: int, what: str, required: bool = True) -> str:
    s = " ".join(v.split()) if isinstance(v, str) else ""
    if (required and not s) or len(s) > limit:
        raise L.Refused(400, f"Say {what} in at most {limit} characters." if required else f"Keep {what} to {limit} characters.")
    return s


def _lines(v) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or len(v) > 10:
        raise L.Refused(400, "For and against are short lists.")
    return [_text(x, TEXT_MAX, "each line") for x in v if isinstance(x, str) and x.strip()]


def _who(viewer, role: str) -> dict:
    return {"account": viewer.account_id, "name": viewer.name, "role": role}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def _day(iso: str | None) -> str:
    try:
        d = datetime.fromisoformat(str(iso))
        return f"{d.day} {d:%b}"
    except ValueError:
        return ""


# ---- North: drafts from records only -----------------------------------------------------------------------------------------

def drop_untraced(text: str, allowed: str) -> tuple[str, list[str]]:
    """Remove every number in `text` that does not appear in `allowed` (the records' own words). Returns the text and what was dropped."""
    known = set(re.findall(r"\d+(?:[.,]\d+)?", allowed))
    dropped: list[str] = []

    def keep(m: re.Match) -> str:
        if m.group(0) in known:
            return m.group(0)
        dropped.append(m.group(0))
        return ""
    return " ".join(re.sub(r"\d+(?:[.,]\d+)?", keep, text).split()), dropped


def with_numbers(task: str, records: str) -> str:
    """The task plus the numbers the records hold. The runtime's number guard lets through a figure the question names, so a draft may
    repeat a record's own number (a time, a count); drop_untraced still drops any number the records do not hold."""
    nums = list(dict.fromkeys(re.findall(r"\d+(?:\.\d+)?", records)))[:400]
    return task + (" Numbers in the records, which you may repeat: " + ", ".join(nums) + "." if nums else "")


def _ask(request, plane, task: str, context: dict) -> dict | None:
    """One North turn through the kernel runtime and the egress gateway, read as a JSON object; None when the model cannot answer."""
    gate = getattr(request.app.state, "entitlements", None) if request is not None else None
    if gate is None:
        return None
    try:
        text = N._call(plane, N._model(request, plane), gate, SYSTEM, {"facts": [], **context}, with_numbers(task, json.dumps(context))) or ""
        a, b = text.find("{"), text.rfind("}")
        got = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except Exception:  # noqa: BLE001 - a provider failure falls back to word rules, never breaks the person's own act
        log.warning("North could not draft for a decision", exc_info=True)
        return None
    return got if isinstance(got, dict) else None


def _clip(v, limit: int) -> str:
    return " ".join(v.split())[:limit] if isinstance(v, str) else ""


def _records(plane, rec: dict, viewer) -> list[dict]:
    """The records North may read for this decision, as the acting person sees them: source chips {kind, ref, label, at}."""
    out, areas = [], {a.lower() for a in rec.get("areas") or []}
    mine = S.areas_of(plane, viewer)
    for r in S.read_index(plane):
        if r["type"] == "decision" and r["state"] == "closed" and r["id"] != rec["id"] and areas & {a.lower() for a in r["areas"]} \
                and S.tier_of(r, viewer, mine):
            out.append({"kind": "decision", "ref": r["id"], "label": f"Decision: {r['title']}", "at": r.get("closed_at") or ""})
    src = (rec.get("links") or {}).get("from")
    if src:
        s = S.read_intent(plane, src)
        if s and S.tier_of(s, viewer, mine):
            out.append({"kind": "intent", "ref": src, "label": f"{s['type'].capitalize()}: {s['title']}", "at": s.get("created_at", "")})
    seen = {n["id"]: n for n in graph_for(plane, viewer)["nodes"] if not n.get("restricted")}
    for a in rec["outcome"].get("affects") or []:
        n = seen.get(a.get("node_id"))
        if n:
            out.append({"kind": "node", "ref": n["id"], "label": f"{n['type']}: {n['label']}", "at": ""})
    return out


def _split(question: str) -> list[str]:
    """Option names read from the question: "whether to X" gives X and not X; "A or B" gives A and B.
    ponytail: word rules over the question; a model draft through the gateway when the runner (spec 08) offers one."""
    q = question.strip().rstrip("?.").strip()
    m = re.search(r"\bwhether (?:to |we should |we )?(.+)$", q, re.I)
    if m:
        x = m.group(1)
        return [f"Yes, {x}"[:NAME_MAX], "No, keep things as they are"]
    if re.search(r"\bor\b", q, re.I):
        head, _, tail = q.rpartition(" or ")
        first = re.split(r"\b(?:which|between|use|choose|pick)\b|:", head, flags=re.I)[-1].strip(" :,")
        parts = [p.strip(" ,") for p in re.split(r",", first) if p.strip(" ,")] + [tail.strip()]
        return [p[:NAME_MAX] for p in parts if p][:OPTIONS_MAX]
    return ["Go ahead as asked", "Do not go ahead"]


def _north_card(name: str, means: str, for_: list[str], sources: list[dict], now: str) -> dict:
    return {"id": _new_id("opt"), "name": name, "means": means, "for": for_, "against": [], "needs": UNKNOWN_COST, "origin": "north",
            "by": "North", "at": now, "confirmed_by": None, "edited_by": None, "sources": sources, "notes": [], "accepted": []}


def _model_options(plane, rec: dict, recs: list[dict], now: str, request) -> list[dict] | None:
    out = rec["outcome"]
    got = _ask(request, plane, ASK_OPTIONS, {"question": out.get("question"), "purpose": rec.get("purpose") or "",
                                             "records": {r["ref"]: r["label"] for r in recs},
                                             "kept_options": [o["name"] for o in out.get("options") or []]})
    allowed = " ".join([out.get("question") or "", rec.get("purpose") or ""] + [r["label"] for r in recs])
    cards = []
    for x in (got or {}).get("options") or []:
        name = drop_untraced(_clip(x.get("name"), NAME_MAX), allowed)[0] if isinstance(x, dict) else ""
        if not name:
            continue
        lines = lambda k: [drop_untraced(_clip(t, TEXT_MAX), allowed)[0] for t in (x.get(k) or [])[:3] if _clip(t, TEXT_MAX)]  # noqa: E731
        refs = {str(r) for r in x.get("refs") or []}
        card = _north_card(name, drop_untraced(_clip(x.get("means"), TEXT_MAX), allowed)[0], lines("for"), [r for r in recs if r["ref"] in refs], now)
        cards.append({**card, "against": lines("against"), "fallback": False})
    return cards[:OPTIONS_MAX] if len(cards) >= 2 else None


def draft_options(plane, rec: dict, viewer, now: str, request=None) -> list[dict]:
    """North's option cards from the model (R14); word rules only when the model cannot answer, each such card marked `fallback`.
    Each card rests on the records named in `sources`; a card with none is marked as such and shown last."""
    recs = _records(plane, rec, viewer)
    drafted = _model_options(plane, rec, recs, now, request)
    if drafted:
        return drafted
    context = [r for r in recs if r["kind"] != "decision"]
    cards = []
    for name in _split(rec["outcome"].get("question") or rec.get("title") or ""):
        cards.append(_north_card(name, f"The decision is made as \"{name}\".", [], context, now))
    for r in [r for r in recs if r["kind"] == "decision"][: max(0, OPTIONS_MAX - len(cards))]:
        prior = S.read_intent(plane, r["ref"]) or {}
        chosen = next((o for o in (prior.get("outcome") or {}).get("options") or [] if o.get("id") == prior["outcome"].get("chosen")), None)
        if chosen:
            cards.append(_north_card(f"As before: {chosen['name']}"[:NAME_MAX], f"Do what was decided in \"{prior['title']}\".",
                                     [f"Chosen before, on {_day(r['at'])}."], [r], now))
    return [{**c, "fallback": True} for c in cards[:OPTIONS_MAX]]


def _fingerprint(rec: dict) -> str:
    return json.dumps([[o["id"], o["name"], o.get("means"), o.get("for"), o.get("against"), o.get("needs"), [s["ref"] for s in o.get("sources") or []],
                        [(n["text"], n["state"]) for n in o.get("notes") or []]] for o in rec["outcome"].get("options") or []])


def _model_lean(plane, rec: dict, now: str, request) -> dict | None:
    out, opts = rec["outcome"], rec["outcome"].get("options") or []
    got = _ask(request, plane, ASK_LEAN, {"question": out.get("question"), "options": {
        o["id"]: {"name": o["name"], "means": o.get("means"), "for": o.get("for"), "against": o.get("against"), "needs": o.get("needs"),
                  "records": {s["ref"]: s["label"] for s in o.get("sources") or []},
                  "notes": [f"{n['kind']} ({n['state']}): {n['text']}" for n in o.get("notes") or []]} for o in opts}})
    best = next((o for o in opts if got and o["id"] == got.get("option_id")), None)
    because = _clip((got or {}).get("because"), REASON_MAX).rstrip(".")
    if not best or not because:
        return None
    every = {s["ref"]: s for o in opts for s in o.get("sources") or []}
    sources = [every[r] for r in dict.fromkeys(str(r) for r in got.get("refs") or []) if r in every] or best.get("sources") or []
    if not sources:
        return None
    allowed = " ".join([out.get("question") or ""] + [s["label"] for s in every.values()]
                       + [" ".join([o["name"], o.get("means") or "", *(o.get("for") or []), *(o.get("against") or []), o.get("needs") or ""]
                                   + [n["text"] for n in o.get("notes") or []]) for o in opts])
    line, dropped = drop_untraced(f"North leans to {best['name']}, because {because}.", allowed)
    return {"option_id": best["id"], "line": line, "sources": sources, "dropped": bool(dropped)}


def recommend(rec: dict, now: str, plane=None, request=None) -> dict | None:
    """One option, one clause of reason, the source chips. Fewer than two options or no record: None, and `missing` says why."""
    opts = rec["outcome"].get("options") or []
    if len(opts) < REC_MIN_OPTIONS or not any(o.get("sources") for o in opts):
        return None
    old, key = rec["outcome"].get("recommendation") or {}, _fingerprint(rec)
    if old.get("key") == key and old.get("fallback") is False and any(o["id"] == old.get("option_id") for o in opts):
        return old  # nothing it rests on changed: keep the model's line, no second call
    lean = _model_lean(plane, rec, now, request) if plane is not None else None
    support = lambda o: (len(o.get("sources") or []), sum(1 for n in o.get("notes") or [] if n.get("state") == "accepted"))  # noqa: E731
    best = max(opts, key=support)
    if sum(1 for o in opts if support(o) == support(best)) > 1:
        reason = "it was chosen before" if best["origin"] == "north" and best["name"].startswith("As before") else "it rests on the records named"
    else:
        reason = "it has the most records behind it"
    allowed = " ".join(s["label"] for s in best.get("sources") or []) + " " + (rec["outcome"].get("question") or "")
    line, dropped = drop_untraced(f"North leans to {best['name']}, because {reason}.", allowed)
    if lean:
        best, line, dropped = next(o for o in opts if o["id"] == lean["option_id"]), lean["line"], lean["dropped"]
    missing = [f"North could not work out the cost of {o['name']}. Missing: a quote or an estimate." for o in opts if o.get("needs") == UNKNOWN_COST]
    if dropped:
        missing.append("North dropped a number it could not trace to a record.")
    return {"option_id": best["id"], "line": line, "sources": lean["sources"] if lean else best.get("sources") or [], "missing": missing,
            "drafted_at": now, "drafted_by": "North", "fallback": not lean, "key": key}


def _north(plane, rec: dict, viewer, now: str, redraft: bool, request=None) -> None:
    out = rec["outcome"]
    if redraft:  # a draft never overwrites a human edit: only North's untouched cards are replaced
        out["options"] = [o for o in out["options"] if not (o["origin"] == "north" and not o.get("edited_by") and not o.get("confirmed_by"))]
        out["options"] += draft_options(plane, rec, viewer, now, request)[: OPTIONS_MAX]
    notes = sum(len(o.get("notes") or []) for o in out["options"])
    refs = {src["ref"] for o in out["options"] if o["origin"] == "north" for src in o.get("sources") or []}
    out["north"] = {"drafted_at": now, "records": len(refs), "notes": notes,
                    "drafted": sum(1 for o in out["options"] if o["origin"] == "north")}
    # ponytail: the model call runs inside the record lock; the fingerprint means only a change calls it again
    out["recommendation"] = recommend(rec, now, plane, request)


def _purpose(plane, rec: dict, decider: dict) -> str:
    """North's one-line purpose (journey 54 step 1) from the record only; closure (spec 09) needs a purpose to close."""
    src = S.read_intent(plane, (rec.get("links") or {}).get("from") or "") if (rec.get("links") or {}).get("from") else None
    lead = f"Follows on from the {src['type']} \"{src['title']}\". " if src and src.get("title") else ""
    return f"{lead}{decider['name']} decides, with the advisers' notes."


# ---- start questions (Screen A) ----------------------------------------------------------------------------------------------

def _open(rec, viewer, b, now, plane, request) -> list[str]:
    roles = _roles(rec, viewer)
    _need("organiser" in roles, "Only the organiser can do that.")
    _need(rec["state"] == "draft", "This decision is already open.", 409)
    a = b.get("answers") if isinstance(b.get("answers"), dict) else {}
    question = _text(a.get("question"), QUESTION_MAX, "what must be decided")
    accounts = _accounts(request)
    decider = _person(a.get("decider"), accounts) if a.get("decider") else None
    _need(bool(decider and decider.get("account_id")), "Name who decides", 400)
    advisers = [_person(x, accounts) for x in a.get("advisers") or [] if x]
    _need(len(advisers) <= ADVISERS_MAX, "That is more advisers than this decision allows.", 400)
    areas = _areas(a.get("areas") or [])
    _need(bool(areas), "Choose at least one area", 400)
    tz = L.company_zone(plane)
    notes = []
    ends = a.get("ends")
    if ends:
        try:
            end = datetime.fromisoformat(str(ends))
        except ValueError:
            raise L.Refused(400, "That end date is not a date.") from None
        end = end if end.tzinfo else end.replace(hour=17, tzinfo=tz)
        _need(end.astimezone(tz).weekday() < 5, "Pick a working day.", 400)
        _need(end > datetime.now(timezone.utc), "Pick a day after today.", 400)
        if end > L.add_working_days(datetime.now(timezone.utc), LONG_DAYS, tz):
            notes.append(LONG_NOTE)
    purpose = _text(a.get("purpose") or "", 500, "the purpose", required=False) or _purpose(plane, rec, decider)
    rec.update(title=question, purpose=purpose, areas=areas,
               affected_may_read=bool(a.get("affected_may_read")))
    p = rec["people"]
    p.update(decider=decider, advisers=advisers, sponsor=p.get("sponsor") or decider)
    rec["outcome"] = {"kind": "decision", "question": question, "options": [], "recommendation": None, "chosen": None, "why": "",
                      "why_drafted": False, "decided_by": None, "decided_at": None, "no_decision_reason": None, "deferral": None,
                      "writes": [], "considered_snapshot": [], "affects": [], "north": None}
    L.move(rec, "open", viewer.account_id, now, tz=tz)
    if ends:
        rec["time_box"]["ends"] = end.astimezone(timezone.utc).isoformat()  # spec 43: a longer date is a note, not a block
    rec["outcome"]["options"] = draft_options(plane, rec, viewer, now, request)
    _north(plane, rec, viewer, now, redraft=False, request=request)
    return notes


# ---- the decider's choices ---------------------------------------------------------------------------------------------------

def _close_by_decider(rec: dict, viewer, now: str, summary: str) -> None:
    """Ruling 25: the decider's act is the confirmation; the intent waits in `closing` for the organiser with North's closure draft."""
    p = rec["people"]
    rec["closure"] = {**L.blank_closure("north"), "summary": summary, "why_it_happened": rec["outcome"]["question"],
                      "what_came_out": summary, "confirmed": [{"role": "decider", "by": viewer.account_id, "at": now}]}
    for s in rec["stages"]:
        if s["state"] != "closed":
            s.update(state="closed", closed_at=now, opened_at=s.get("opened_at") or now)
    rec["outcome"].update(decided_by=(p.get("decider") or {}).get("name"), decided_at=now,
                          considered_snapshot=[{k: v for k, v in o.items()} for o in rec["outcome"]["options"]])
    L._hist(rec, viewer.account_id, "open", "closing", now, "decider recorded")
    rec["state"] = "closing"


def _write_nodes(plane, rec: dict, viewer, option_name: str, why: str) -> None:
    seen = {n["id"] for n in graph_for(plane, viewer)["nodes"] if not n.get("restricted")}
    writes = []
    for a in rec["outcome"].get("affects") or []:
        if a["node_id"] in seen:
            row = append_version(plane, a["node_id"], f"Decision: {option_name}. {why[:120]}", viewer.name, f"intent:{rec['id']}")
            writes.append({"node_id": a["node_id"], "version": row["v"], "ref": f"intent:{rec['id']}"})
        else:
            writes.append({"node_id": a["node_id"], "version": None, "ref": None, "skipped": "Not written: you cannot see it"})
    src = (rec.get("links") or {}).get("from")
    if src:
        try:
            other = S.read_intent(plane, src)
            if other and rec["id"] not in other["links"]["to"]:
                S.update_intent(plane, src, other["version"], lambda r: r["links"]["to"].append(rec["id"]))
            writes.append({"node_id": None, "intent_id": src, "version": None, "ref": f"intent:{src}"})
        except (S.VersionConflict, S.Unreadable, LookupError):
            writes.append({"node_id": None, "intent_id": src, "version": None, "ref": None, "skipped": "Not written: the source intent changed"})
    rec["outcome"]["writes"] = writes


def _decide(rec, viewer, b, now, plane, request):
    kind, roles, out = b.get("kind"), _roles(rec, viewer), rec["outcome"]
    if kind == "open":
        return {"notes": _open(rec, viewer, b, now, plane, request), "event": ("opened", {"type": "decision"})}
    if kind == "cancel":
        _need(bool(roles & {"organiser", "decider"}) or "company_admin" in (getattr(viewer, "roles", None) or []),
              "Only the organiser, the decider or the company admin can cancel this decision.")
        _need(rec["state"] in ("open", "draft"), NOT_OPEN, 409)
        reason = _text(b.get("reason"), REASON_MAX, "why it is cancelled")
        frm = rec["state"]
        rec["closure"] = {**(rec.get("closure") or L.blank_closure()), "cancel_reason": reason, "closed_by": viewer.account_id,
                          "closed_at": now, "signed": False}
        rec["state"] = "cancelled"
        L._hist(rec, viewer.account_id, frm, "cancelled", now, reason)
        return {"event": ("cancelled", {"cancel_reason": "given"})}
    _need(rec["state"] == "open", NOT_OPEN, 409)
    if kind == "affects":
        _need(bool(roles & {"organiser", "decider"}), "Only the organiser or the decider can name a measure or process.")
        nodes = b.get("nodes") if isinstance(b.get("nodes"), list) else []
        seen = {n["id"]: n for n in graph_for(plane, viewer)["nodes"] if not n.get("restricted")}
        keep = [a for a in out.get("affects") or [] if a["node_id"] in nodes and a["node_id"] not in seen]  # nodes I cannot see stay
        add = [{"node_id": i, "type": seen[i]["type"]} for i in dict.fromkeys(nodes) if i in seen and seen[i]["type"] in ("Measure", "Process")]
        out["affects"] = keep + add
        _north(plane, rec, viewer, now, redraft=False, request=request)
        return {}
    if kind == "decider":
        _need("organiser" in roles, "Only the organiser can change the decider.")
        new = _person(b.get("decider"), _accounts(request))
        _need(bool(new and new.get("account_id")), "Name who decides", 400)
        old = (rec["people"].get("decider") or {}).get("name")
        rec["people"]["decider"] = new
        L._hist(rec, viewer.account_id, "open", "open", now, f"decider changed from {old} to {new['name']}")
        return {"event": ("person_invited", {"role": "decider"})}
    _need("decider" in roles, NOT_DECIDER)
    if kind == "choose":
        opt = next((o for o in out["options"] if o["id"] == b.get("option_id")), None)
        _need(opt is not None, "That option is not on this decision.", 404)
        why = _text(b.get("why"), REASON_MAX, "why")
        out.update(chosen=opt["id"], why=why, why_drafted=bool(b.get("why_drafted")) and why == why_draft(opt), no_decision_reason=None)
        _write_nodes(plane, rec, viewer, opt["name"], why)
        _close_by_decider(rec, viewer, now, f"Decided: {opt['name']}. By {viewer.name}.")
        return {"event": ("signed", {"what": "decision"})}
    if kind == "none":
        reason = _text(b.get("reason"), REASON_MAX, "why there is no decision")
        out.update(chosen=None, why="", no_decision_reason=reason)
        _close_by_decider(rec, viewer, now, f"No decision. Reason: {reason}")
        return {"event": ("signed", {"what": "no_decision"})}
    if kind == "later":
        if out.get("deferral"):
            raise L.Refused(409, f"Already extended once on {_day(out['deferral']['at'])}. Pick or say no decision.")
        reason = _text(b.get("reason"), REASON_MAX, "why it must wait")
        tz = L.company_zone(plane)
        try:
            to = datetime.fromisoformat(str(b.get("to")))
        except ValueError:
            raise L.Refused(400, "That date is not a date.") from None
        to = to if to.tzinfo else to.replace(hour=17, tzinfo=tz)
        was = datetime.fromisoformat(rec["time_box"]["ends"])
        _need(to.astimezone(tz).weekday() < 5, "Pick a working day.", 400)
        _need(was < to <= L.add_working_days(was, LATER_DAYS, tz), "Pick a working day after the current date and within a week.", 400)
        new_end = to.astimezone(timezone.utc).isoformat()
        rec["time_box"]["extended_by"].append({"by": viewer.account_id, "at": now, "reason": reason, "kind": "decide_later", "was": rec["time_box"]["ends"]})
        out["deferral"] = {"from": rec["time_box"]["ends"], "to": new_end, "reason": reason, "by": viewer.name, "at": now}
        rec["time_box"]["ends"] = new_end
        L._hist(rec, viewer.account_id, "open", "open", now, "decide later")
        return {"event": ("extended", {"old_end": out["deferral"]["from"][:25], "new_end": new_end[:25]})}
    raise L.Refused(400, "Choose one: pick an option, decide later, or no decision.")


def why_draft(opt: dict) -> str:
    """North's draft for the Why field: a suggestion the decider must confirm, never filled in on its own."""
    return f"{opt['name']} weighed best against the other options and the advisers' notes."


# ---- options and notes -------------------------------------------------------------------------------------------------------

def _card_owner(rec: dict, opt: dict, viewer) -> bool:
    if opt.get("by_account"):
        return opt["by_account"] == viewer.account_id
    return S._named(rec["people"].get("organiser"), viewer)  # North's cards and anonymous cards belong to the organiser


def _options(rec, viewer, b, now, plane, request):
    roles, out, action = _roles(rec, viewer), rec["outcome"], b.get("action") or "add"
    _need(rec["state"] == "open", NOT_OPEN, 409)
    if action == "redraft":
        _need("organiser" in roles, "Only the organiser can ask North to redraft.")
        _north(plane, rec, viewer, now, redraft=True, request=request)
        return {"event": ("north_drafted", {"draft_of": "proposal"}), "draft": True}
    _need(bool(roles & {"organiser", "decider", "adviser"}), "Only the organiser, the decider and the advisers can add options.")
    if action == "add":
        anon = bool(b.get("anonymous"))
        _need(len(out["options"]) < 20, "This decision has enough options.", 400)
        opt = {"id": _new_id("opt"), "name": _text(b.get("name"), NAME_MAX, "the option's name"),
               "means": _text(b.get("means") or "", TEXT_MAX, "what it means", required=False), "for": _lines(b.get("for")),
               "against": _lines(b.get("against")), "needs": _text(b.get("needs") or "", TEXT_MAX, "the cost or need", required=False),
               "origin": "anonymous" if anon else "adviser" if roles == {"adviser"} else "person", "by": "Anonymous" if anon else viewer.name,
               "at": now, "confirmed_by": None, "edited_by": None, "sources": [], "notes": [], "accepted": []}
        if not anon:
            opt["by_account"] = viewer.account_id
        out["options"].append(opt)
        _north(plane, rec, viewer, now, redraft=False, request=request)
        return {"event": ("card_added", {"lane": "option"}), "anonymous": anon, "ref": {"store": "decision_option", "id": opt["id"]}}
    opt = next((o for o in out["options"] if o["id"] == b.get("option_id")), None)
    _need(opt is not None, "That option is not on this decision.", 404)
    if action == "confirm":
        _need(opt["origin"] == "north" and (_card_owner(rec, opt, viewer) or "adviser" in roles), "Only the organiser or an adviser can confirm this.")
        opt["confirmed_by"] = viewer.name
    elif action == "edit":
        _need(_card_owner(rec, opt, viewer) or "organiser" in roles, "Only the person who added this card or the organiser can edit it.")
        for k, lim in (("name", NAME_MAX), ("means", TEXT_MAX), ("needs", TEXT_MAX)):
            if k in b:
                opt[k] = _text(b[k], lim, k, required=k == "name")
        for k in ("for", "against"):
            if k in b:
                opt[k] = _lines(b[k])
        opt["edited_by"] = viewer.name
    else:
        raise L.Refused(400, "That is not something you can do to an option.")
    _north(plane, rec, viewer, now, redraft=False, request=request)
    return {}


def _note(rec, viewer, b, now, plane, request, option_id: str):
    roles = _roles(rec, viewer)
    _need(rec["state"] == "open", NOT_OPEN, 409)
    _need(bool(roles & {"organiser", "decider", "adviser"}), "Only the organiser, the decider and the advisers can add notes.")
    opt = next((o for o in rec["outcome"]["options"] if o["id"] == option_id), None)
    _need(opt is not None, "That option is not on this decision.", 404)
    kind = b.get("kind") if b.get("kind") in ("comment", "suggestion") else "comment"
    anon = bool(b.get("anonymous"))
    note = {"id": _new_id("note"), "kind": kind, "text": _text(b.get("text"), NOTE_MAX, "your note"), "by": "Anonymous" if anon else viewer.name,
            "at": now, "state": "open", "decided_by": None, "decided_at": None, "answer": None}
    if not anon:
        note["by_account"] = viewer.account_id
    opt["notes"].append(note)
    _north(plane, rec, viewer, now, redraft=False, request=request)
    return {"event": ("card_added", {"lane": "note"}), "anonymous": anon, "ref": {"store": "decision_note", "id": f"{option_id}:{note['id']}"}}


def _note_decide(rec, viewer, b, now, plane, request, note_id: str):
    _need(rec["state"] == "open", NOT_OPEN, 409)
    hit = next(((o, n) for o in rec["outcome"]["options"] for n in o["notes"] if n["id"] == note_id), None)
    _need(hit is not None, "That note is not on this decision.", 404)
    opt, note = hit
    _need(_card_owner(rec, opt, viewer) or "decider" in _roles(rec, viewer), OWNER_ONLY)
    state = b.get("state")
    _need(state in ("accepted", "declined", "answered"), "Accept, decline or answer.", 400)
    _need(note["state"] == "open", "This note has already been decided.", 409)
    _need(state == "answered" or note["kind"] == "suggestion", "Only a suggestion can be accepted or declined.", 400)
    answer = _text(b.get("answer") or "", NOTE_MAX, "your answer", required=state == "answered") or None
    note.update(state=state, decided_by=viewer.name, decided_at=now, answer=answer)
    if state == "accepted":
        opt["accepted"].append({"text": note["text"], "by": viewer.name, "at": now})
        opt["edited_by"] = opt.get("edited_by") or viewer.name
    _north(plane, rec, viewer, now, redraft=False, request=request)
    return {}


# ---- routes ------------------------------------------------------------------------------------------------------------------

def _shape(rec: dict) -> dict:
    """An older record (an earlier seed) may hold options as {id, text, drafted_by, added_by} and lack outcome lists: fill the spec 43
    shape in place, so a note or an option on it never fails and the card has a name and an author."""
    out = rec.setdefault("outcome", {})
    for k, v in (("options", []), ("recommendation", None), ("chosen", None), ("why", ""), ("why_drafted", False), ("decided_by", None),
                 ("decided_at", None), ("no_decision_reason", None), ("deferral", None), ("writes", []), ("considered_snapshot", []),
                 ("affects", []), ("north", None)):
        out.setdefault(k, v)
    for o in out["options"]:
        origin = o.get("origin") or ("north" if o.get("drafted_by") == "north" else "adviser" if o.get("added_by") == "adviser" else "person")
        o.update(origin=origin, name=o.get("name") or o.get("text") or "", by=o.get("by") or ("North" if origin == "north" else "an adviser"))
        for k, v in (("means", ""), ("needs", ""), ("at", ""), ("confirmed_by", None), ("edited_by", None)):
            o.setdefault(k, v)
        for k in ("for", "against", "sources", "notes", "accepted"):
            o[k] = o.get(k) or []
    return rec


def _act(request: Request, intent_id: str, body, change, *extra):
    """Read, check the person's part, write once through the store, then append the event line (after the write: the event file
    keeps its own counter on the record)."""
    def go(plane, viewer, now):
        b = body if isinstance(body, dict) else {}
        rec, _ = _load(plane, viewer, intent_id)
        info: dict = {}
        rec = S.update_intent(plane, intent_id, rec["version"], lambda r: info.update(change(_shape(r), viewer, b, now, plane, request, *extra) or {}))
        if info.get("event"):
            kind, detail = info["event"]
            if info.get("draft"):
                E.try_append(plane, intent_id, kind, "north", None, detail, "draft")
            else:
                E.try_append(plane, intent_id, kind, None if info.get("anonymous") else _who(viewer, "/".join(sorted(_roles(rec, viewer)))),
                             info.get("ref") or {"store": "intent", "id": intent_id}, detail, "act", anonymous=bool(info.get("anonymous")))
        rec = S.read_intent(plane, intent_id) or rec
        cut = S.cut(rec, S.tier_of(rec, viewer, S.areas_of(plane, viewer)) or "exists", viewer)
        return {**cut, "notes_for_you": info.get("notes") or []}
    return _run(request, go)


@router.post("/api/intents/{intent_id}/decide")
def post_intents_by_intent_id_decide(request: Request, intent_id: str, body: dict = Body(default={})):
    """kind: open (the five start questions), choose, later, none (the decider), cancel, affects, decider (change the decider).
    kind start writes nothing: it names the company's sponsors and admins so Q3 can default to "The sponsor" and mark the roles."""
    if isinstance(body, dict) and body.get("kind") == "start":
        def marks(plane, viewer, now):
            _load(plane, viewer, intent_id)
            accts = [a for a in request.app.state.account_store.in_company(request.state.company_id) if not a.get("disabled")]
            return {"marks": {a["account_id"]: [r for r in ("sponsor", "company_admin") if r in (a.get("roles") or [])] for a in accts},
                    "sponsor": next((L.person(a["account_id"], a["display_name"]) for a in accts if "sponsor" in (a.get("roles") or [])), None)}
        return _run(request, marks)
    return _act(request, intent_id, body, _decide)


@router.post("/api/intents/{intent_id}/options")
def post_intents_by_intent_id_options(request: Request, intent_id: str, body: dict = Body(default={})):
    """action: add (default), edit, confirm, redraft."""
    return _act(request, intent_id, body, _options)


@router.post("/api/intents/{intent_id}/options/{option_id}/notes")
def post_intents_by_intent_id_options_by_option_id_notes(request: Request, intent_id: str, option_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, _note, option_id)


@router.post("/api/intents/{intent_id}/notes/{note_id}/decide")
def post_intents_by_intent_id_notes_by_note_id_decide(request: Request, intent_id: str, note_id: str, body: dict = Body(default={})):
    return _act(request, intent_id, body, _note_decide, note_id)
