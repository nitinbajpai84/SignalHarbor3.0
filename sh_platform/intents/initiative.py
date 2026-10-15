"""IC v2 (22): the Initiative's six start questions and the check the open route runs. The wall and card routes below are
stubs for 23 and 24 (501 until their card lands).

The screen (ui/src/intents/start/InitiativeStart.tsx) saves answers through PUT /api/intents/{id}, prepares the wall through
the existing m1 Prepare route and opens through POST /api/intents/{id}/open; that route calls check_open() for an Initiative.
"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body, Request

from modules.m1_intent.api import deps as m1deps
from modules.m1_intent.api import session as m1session
from modules.m1_intent.domain.preparation import PrepError, default_preparation
from sh_platform.intents import _viewer, not_yet
from sh_platform.intents import events as E
from sh_platform.intents import lifecycle as L
from sh_platform.intents import records as R
from sh_platform.intents import store as S
from sh_platform.jsonfile import lock_for, write_json_atomic
from sh_platform.profile import areas as areas_store
from sh_platform.profile import store as profile_store

router = APIRouter()

# The canonical table of file 22 (ruling 2): order, key, North's wording, required to open.
# ponytail: held here until modules/m1_intent/contracts/initiative_start.yaml exists (not in this card's paths).
QUESTIONS: list[dict] = [
    {"key": "goal", "lead": "What are you trying to achieve?", "required": True},
    {"key": "people", "lead": "Whom do you need to involve, and who is affected?", "required": True},
    {"key": "build", "lead": "Do you think this needs a build (new data, pipelines, reports)?", "required": True},
    {"key": "definitions", "lead": "Do we already have a business glossary and technical definitions for this, or will we discover them along the way?", "required": True},
    {"key": "areas", "lead": "Which areas does this touch?", "required": True},
    {"key": "deadline", "lead": "When must this be decided by?", "required": True},
]
DEFAULT_DAYS = 10  # brief section 2, file 02: an Initiative's time box in working days
SPLIT = {"think_unfiltered": 3, "define_strategically": 6, "build_ready": 1}  # file 02 stage days
GOAL_MAX, WHY_MIN, WHY_MAX = 140, 20, 600  # file 22 Open questions 12


def add_working_days(start: date, n: int) -> date:
    """`n` working days (Monday to Friday) after `start` (ruling 22: no holidays until the profile has a calendar)."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


def working_days(start: date, end: date) -> int:
    """Working days after `start` up to and including `end`."""
    return sum((start + timedelta(days=i)).weekday() < 5 for i in range(1, (end - start).days + 1))


def _value(answers: dict, key: str):
    cell = answers.get(key)
    return cell.get("value") if isinstance(cell, dict) else None


def check_open(intent: dict) -> str | None:
    """The first missing item an Initiative needs before it opens, in plain words; None when it may open (file 22 Rules)."""
    miss = check_answers(intent)
    if miss:
        return miss
    ref = (intent.get("stages") or [{}])[0].get("ref") or {}
    if ref.get("kind") != "wall_session" or not ref.get("id"):
        return "The wall is not prepared yet. Try again."
    return None


def check_answers(intent: dict) -> str | None:
    a = intent.get("start_answers") or {}
    goal = _value(a, "goal") or {}
    line, why = str(goal.get("line") or "").strip(), str(goal.get("why") or "").strip()
    if not line or len(line) > GOAL_MAX:
        return "Say the goal in one line."
    if not WHY_MIN <= len(why) <= WHY_MAX:
        return "A few words on why will help the people you invite."
    people = _value(a, "people") or {}
    if not (people.get("participants") or people.get("sponsor") or people.get("just_me")):
        return "Name the people to involve, or choose Just me for now."
    if _value(a, "build") not in ("yes", "no", "not_sure"):
        return "Say whether this needs a build."
    if _value(a, "definitions") not in ("yes", "some", "no"):
        return "Say whether the definitions exist."
    if not _value(a, "areas"):
        return "Pick at least one area."
    try:
        date.fromisoformat(str(_value(a, "deadline")))
    except ValueError:
        return "Pick the date this must be decided by."
    if not str(intent.get("title") or "").strip():
        return "Give the intent a title."
    return None


# ---- routes: save one answer; open with the wall hand-over ------------------------------------------------------------------

KEYS_Q = tuple(q["key"] for q in QUESTIONS)
TITLE_MAX, CELL_MAX, SUMMARY_MAX = 120, 6000, 2000


def _draft_of(rec: dict, by: str) -> None:
    L._organiser(rec, by)  # a draft is its creator's alone (ruling 14)
    if rec["type"] != "initiative":
        raise ValueError("This is not an Initiative.")
    if rec["state"] != "draft":
        raise L.Refused(409, "This intent is already open.")


def _cell(raw, name: str, now: str) -> dict:
    """An answer cell {value, mark, by, from, at, ...}: the server stamps by and at; North never writes `stated`."""
    if not isinstance(raw, dict) or "value" not in raw or len(json.dumps(raw)) > CELL_MAX or raw.get("mark") not in ("stated", "guessed"):
        raise ValueError("That answer could not be read.")
    return {**raw, "by": name if raw["mark"] == "stated" else "North", "from": str(raw.get("from") or "")[:200], "at": now}


# ---- carrying a hypothesis into a new intent (57: "Pick it up" and "Think it through first"; 35; 37) -----------------------------

def _num(x: dict | None) -> str | None:
    if not isinstance(x, dict) or not isinstance(x.get("value"), (int, float)):
        return None
    return f"{x['value']:,.4g}{' ' + x['unit'] if x.get('unit') else ''}" if abs(x["value"]) < 1e4 else f"{x['value']:,.0f}{' ' + x['unit'] if x.get('unit') else ''}"


def hypothesis_lines(v: dict) -> dict:
    """Plain-words pieces of a hypothesis version: the measure line, the target line (or "") and up to three supporting lines."""
    m, t = v.get("measure") or {}, v.get("target") or {}
    name, by = m.get("name") or m.get("id") or "", t.get("by") or v.get("review_date")
    measure = name and ", ".join(p for p in (f"Measure: {name}", _num(v.get("baseline")) and f"now {_num(v.get('baseline'))}",
                                             _num(t) and f"target {_num(t)}", by and f"by {by}") if p)
    target = f"{name or 'The measure'} reaches {_num(t)}{f' by {by}' if by else ''}." if _num(t) else ""
    belief = str(v.get("belief") or "").strip()
    ev = sorted((e for e in v.get("evidence") or [] if e.get("stance") == "supports" and e.get("text") and e["text"].strip() != belief),
                key=lambda e: {"data": 0, "voice": 1}.get(e.get("record_kind"), 2))[:3]
    return {"name": name, "measure": measure, "target": target, "evidence": " ".join(e["text"].rstrip(".") + "." for e in ev)}


def carry_answers(kind: str, opp: dict, v: dict, today: date, now: str) -> dict:
    """The start answers an opportunity's hypothesis can fill, each guessed by North with the opportunity as source (57 steps 6, 7)."""
    src = f"The opportunity: {opp.get('title') or ''}"[:200]
    h, belief, areas = hypothesis_lines(v), str(v.get("belief") or opp.get("title") or "").strip(), [a for a in opp.get("areas") or [] if isinstance(a, str)]
    if v.get("theme") and ": " in belief:  # a theme's belief leads with the voice count; the idea is what they ask for
        belief = belief.split(": ", 1)[1]
    if kind == "brainstorm":
        out = {"statement": belief[:200], "context": " ".join(x for x in (h["evidence"], h["measure"]) if x)[:1000], "good_outcome": h["target"][:300], "areas": areas}
        return {k: x for k, x in out.items() if x}

    def cell(value, **more) -> dict:
        return {"value": value, "mark": "guessed", "by": "North", "from": src, "at": now, **more}
    why = " ".join(x for x in (h["evidence"], h["measure"] and h["measure"] + ".") if x) or str((opp.get("pattern") or {}).get("text") or "")
    out = {"goal": cell({"line": belief[:GOAL_MAX], "why": why[:WHY_MAX]})}
    if h["name"]:  # the measure and target are the definition the Initiative starts from
        out["definitions"] = cell("some", terms=[h["name"]], rejected=[], found=[], counts=None, note=h["measure"])
    if areas:
        out["areas"] = cell(areas)
    try:
        review = date.fromisoformat(str(v.get("review_date")))
    except ValueError:
        review = None
    if review and review > today:  # decide-by from the review date, held inside the Initiative's ten working days
        d = min(review, add_working_days(today, DEFAULT_DAYS))
        out["deadline"] = cell(d.isoformat(), working_days=working_days(today, d))
    return out


def carry(plane, viewer, intent_id: str, opp_id, version: int, now: str) -> dict:
    """Opening a start from an opportunity: fill the answers it can, write hypothesis_ref on the draft, mark the opportunity `became` and
    the hypothesis carried into it. Only the person who picked the opportunity up, on their own draft of the type they picked it up as."""
    from sh_platform.intents import hypotheses as H
    from sh_platform.intents import opportunities as O
    rec = S.read_intent(plane, intent_id)
    if rec is None or (rec["people"].get("organiser") or {}).get("account_id") != viewer.account_id:
        raise LookupError(intent_id)
    if rec["state"] != "draft":
        raise L.Refused(409, "This intent is already open.")
    opp = O.get(plane, str(opp_id))
    if opp is None:
        raise ValueError("That opportunity could not be found.")
    hyp = H.get(plane, (opp.get("hypothesis_ref") or {}).get("id", ""))
    if (rec.get("hypothesis_ref") or {}).get("id") == (hyp or {}).get("id") and opp.get("became") == intent_id:
        return rec  # already carried: opening the start again changes nothing
    if (opp["state"] != "picked_up" or opp.get("picked_up_by") != viewer.account_id or opp.get("picked_up_as") != rec["type"]
            or opp.get("became") not in (None, intent_id) or rec.get("hypothesis_ref")):
        raise L.Refused(409, "Pick the opportunity up on the radar first.")
    if hyp is None:
        raise L.Refused(409, "This opportunity has no hypothesis to carry yet.")
    answers, ref = carry_answers(rec["type"], opp, H.latest(hyp), date.fromisoformat(now[:10]), now), H.ref(hyp)

    def change(r: dict) -> None:
        a = r.get("start_answers") or {}
        if r["type"] == "initiative":
            r["start_answers"] = {**answers, **a}  # an answer the person already gave stands
            goal = (r["start_answers"].get("goal") or {}).get("value") or {}
            r["title"], r["purpose"] = r.get("title") or str(goal.get("line") or "")[:TITLE_MAX], r.get("purpose") or str(goal.get("line") or "")
        else:
            new = {k: x for k, x in answers.items() if not a.get(k)}
            r["start_answers"] = {**a, **new, "carried": {"from": f"The opportunity: {opp.get('title') or ''}"[:200], "values": new}}
            r["title"] = r.get("title") or str(r["start_answers"].get("statement") or "")[:80].rstrip(" .,;:")
            r["areas"] = r.get("areas") or list(r["start_answers"].get("areas") or [])[:20]
        r["hypothesis_ref"], r["draft_updated_at"] = ref, now
    rec = S.update_intent(plane, intent_id, version, change)
    with lock_for(O._dir(plane) / f"{opp['id']}.json"):
        o = O.get(plane, opp["id"])
        if o and not o.get("became"):
            o["became"] = intent_id
            O._hist(o, viewer.account_id, "became", rec["type"])
            O._save(plane, o)
    mark_carried(plane, ref, intent_id)
    return rec


def mark_carried(plane, ref: dict, intent_id: str) -> None:
    """The hypothesis records the intent it was carried into (57 states: checked to carried)."""
    from sh_platform.intents import hypotheses as H
    path = plane.path("intents", "hypotheses", f"{ref['id']}.json")
    with lock_for(path):
        h = H.get(plane, ref["id"])
        if h is None or any(c.get("intent") == intent_id for c in h["carried_into"]):
            return
        h["carried_into"].append({"intent": intent_id, "version": ref["version"]})
        h["state"] = "carried"
        write_json_atomic(path, h)


def inherited_ref(plane, rec: dict) -> dict | None:
    """An Initiative made by a Brainstorm's What next (37) takes the Brainstorm's hypothesis (57 step 9)."""
    src_id = (rec.get("links") or {}).get("from")
    if rec.get("hypothesis_ref") or not isinstance(src_id, str) or not src_id:
        return None
    try:
        src = S.read_intent(plane, src_id) or {}
    except S.Unreadable:
        return None
    ref = src.get("hypothesis_ref") or (((src.get("outcome") or {}).get("chosen") or {}).get("hypothesis_ref"))
    return {"id": ref["id"], "version": ref.get("version")} if isinstance(ref, dict) and ref.get("id") else None


@router.put("/api/intents/{intent_id}/start")
def put_intents_by_intent_id_start(request: Request, intent_id: str, body: dict = Body(default={})):
    """Save one start answer to the draft (file 22 States: draft, question N). Body {version, key, cell}.
    Or carry an opportunity's hypothesis into an Initiative or Brainstorm draft (57). Body {version, carry: <opportunity id>}."""
    if isinstance(body, dict) and "carry" in body:
        return R._run(request, lambda plane, viewer, now: S.cut(carry(plane, viewer, intent_id, body["carry"], R._version(body), now), "content", viewer))
    name = _viewer(request).name or ""

    def change(rec, by, b, now, plane, req):
        _draft_of(rec, by)
        if b.get("key") not in KEYS_Q:
            raise ValueError("That is not one of the start questions.")
        cell = _cell(b.get("cell"), name, now)
        old = (rec.get("start_answers") or {}).get("goal") or {}
        rec["start_answers"] = {**(rec.get("start_answers") or {}), b["key"]: cell}
        if b["key"] == "goal":
            line = str((cell["value"] or {}).get("line") or "").strip()[:GOAL_MAX]
            if not rec["title"] or rec["title"] == str((old.get("value") or {}).get("line") or "")[:TITLE_MAX]:
                rec["title"] = line[:TITLE_MAX]  # North drafts the title from the goal until the person edits it
            rec["purpose"] = line
        rec["draft_updated_at"] = now
    return R._act(request, intent_id, body, change)


def _area_name(plane, area_id: str) -> str:
    try:
        return next((a["name"] for a in areas_store.listing(profile_store.load(plane)) if a["id"] == area_id and a["name"]), area_id)
    except Exception:  # an unreadable profile: the id is a fair topic, editable in "Change the wall setup"
        return area_id


def _prepare_wall(request: Request, plane, rec: dict, viewer_id: str) -> str:
    """The wall draft through the existing Prepare (m1 create_draft, in process): purpose from the goal line, outcome from the why,
    seats from the people named, topic from the first area, window from stage 1's share. Returns the session id."""
    a = rec["start_answers"]
    goal, people = _value(a, "goal"), _value(a, "people")
    days = working_days(date.today(), date.fromisoformat(_value(a, "deadline")))
    raw = {"purpose": goal["line"][:500], "outcome": goal["why"][:500],
           "seats": max(1, min(10, 1 + len(people.get("participants") or []) + (1 if people.get("sponsor") else 0))),
           "topic": _area_name(plane, _value(a, "areas")[0])[:60], "wall_window_days": max(1, min(SPLIT["think_unfiltered"], days))}
    settings, templates = m1deps.contracts(request)
    store = m1deps.store(request)
    s = store.create(viewer_id, m1session._prepare(request, raw, default_preparation(settings, templates)))
    store.count(s["id"], 1, 0)
    return s["id"]


@router.post("/api/intents/{intent_id}/start/open")
def post_intents_by_intent_id_start_open(request: Request, intent_id: str, body: dict = Body(default={})):
    """"That is right, open this intent": check, prepare the wall draft (reused on retry, found by stages[0].ref), then write the
    record open with the flat outcome (ruling 16) and stages[0].ref in one write. Body {version, title, summary: {text, mark}}."""
    def go(plane, viewer, now):
        b = R._body(body)
        version, by = R._version(b), viewer.account_id
        title = R._text(b.get("title"), TITLE_MAX, "title")
        summary = b.get("summary") or {}
        text = R._text(summary.get("text"), SUMMARY_MAX, "summary")
        if not text:
            raise ValueError("Write the summary before you open this intent.")
        rec = S.read_intent(plane, intent_id)
        if rec is None or (rec["people"].get("organiser") or {}).get("account_id") != by:
            raise LookupError(intent_id)
        _draft_of(rec, by)
        miss = check_answers({**rec, "title": title})
        if miss:
            raise ValueError(miss)
        today, ends = date.fromisoformat(now[:10]), date.fromisoformat(str(_value(rec["start_answers"], "deadline")))
        if ends <= today:
            raise ValueError("Pick a date after today.")
        if working_days(today, ends) > DEFAULT_DAYS:  # the screen's cap, held on the server too
            raise ValueError(f"Pick a date no later than {add_working_days(today, DEFAULT_DAYS):%d %b %Y}. You can ask for more time later.")
        ref =(rec["stages"] or [{}])[0].get("ref")
        if not ref:
            try:
                sid = _prepare_wall(request, plane, rec, by)
            except PrepError as e:
                raise ValueError(e.message) from None
            ref = {"kind": "wall_session", "id": sid}
            rec = S.update_intent(plane, intent_id, version, lambda r: r.update(stages=[{"key": "think_unfiltered", "state": "waiting",
                                                                                          "opened_at": None, "closed_at": None, "ref": ref}]))
            version = rec["version"]
        accounts, tz, sm = R._accounts(request), L.company_zone(plane), {"text": text, "mark": summary.get("mark")}
        inherit = inherited_ref(plane, rec)

        def opening(r: dict) -> None:
            open_record(r, ref, title, sm, by, viewer.name, now, accounts, tz)
            if inherit:
                r["hypothesis_ref"] = inherit
        rec = S.update_intent(plane, intent_id, version, opening)
        if inherit:
            mark_carried(plane, inherit, intent_id)
        E.try_append(plane, intent_id, "opened", {"account": by, "name": viewer.name, "role": "organiser"},
                     {"store": "intent", "id": intent_id}, {"type": "initiative"}, "act")  # spec 16: the open is a milestone line
        return S.cut(rec, "content", viewer)
    return R._run(request, go)


def open_record(r: dict, ref: dict, title: str, summary: dict, by: str, name: str, now: str, accounts: dict, tz) -> None:
    """The open write: record fields from the answers, the lifecycle move to open (time box and stages), stages[0].ref, and the
    flat outcome (ruling 16: goal, why, build_needed, definitions_exist at the top of `outcome`). Marks stay in start_answers."""
    a = r["start_answers"]
    goal, people, deadline = _value(a, "goal"), _value(a, "people"), _value(a, "deadline")
    r["title"], r["purpose"] = title, goal["line"].strip()
    r["areas"] = R._areas(_value(a, "areas"))
    r["people"] = R._people({"sponsor": people.get("sponsor"), "participants": people.get("participants") or [],
                             "affected": people.get("affected") or []}, r["people"], accounts)
    r["affected_may_read"] = people.get("affected_may_read") is True
    ends = datetime.combine(date.fromisoformat(deadline), datetime.fromisoformat(now).timetz()).isoformat()
    L.move(r, "open", by, now, tz=tz, ends=ends)
    r["stages"][0]["ref"] = ref
    r["refs"]["wall_session_ids"] = list(dict.fromkeys([*r["refs"]["wall_session_ids"], ref["id"]]))
    defs = a["definitions"]
    r["outcome"].update(goal=goal["line"].strip(), why=goal["why"].strip(), build_needed=_value(a, "build"),
                        definitions_exist=defs["value"], definitions_found={"terms": defs.get("found") or [], "counts": defs.get("counts")},
                        decide_by={"date": deadline, "working_days": working_days(date.fromisoformat(now[:10]), date.fromisoformat(deadline))},
                        people_note={"just_me": people.get("just_me") is True, "not_listed": people.get("not_listed") or []},
                        start_summary={"text": summary["text"], "mark": "stated" if summary.get("mark") == "stated" else "guessed",
                                       "confirmed_by": name, "confirmed_at": now})
    r["opened_by"] = by
    answer = {"yes": True, "no": False}.get(_value(a, "build"))  # build-ready line 7, the charter and closure read the record's own answer
    if answer is not None and r.get("build_needed") is None:
        r.update(build_needed=answer, build_needed_by={"account_id": by, "name": name}, build_needed_at=now)


@router.post("/api/intents/{intent_id}/contributions")
def post_intents_by_intent_id_contributions(request: Request):
    return not_yet("24")


@router.get("/api/intents/{intent_id}/wall")
def get_intents_by_intent_id_wall(request: Request):
    return not_yet("23")


@router.get("/api/intents/{intent_id}/cards")
def get_intents_by_intent_id_cards(request: Request):
    return not_yet("24")


@router.post("/api/intents/{intent_id}/cards")
def post_intents_by_intent_id_cards(request: Request):
    return not_yet("24")


@router.get("/api/intents/{intent_id}/cards/{card_id}")
def get_intents_by_intent_id_cards_by_card_id(request: Request):
    return not_yet("24")


@router.patch("/api/intents/{intent_id}/cards/{card_id}")
def patch_intents_by_intent_id_cards_by_card_id(request: Request):
    return not_yet("24")


@router.post("/api/intents/{intent_id}/cards/{card_id}/withdraw")
def post_intents_by_intent_id_cards_by_card_id_withdraw(request: Request):
    return not_yet("24")


@router.post("/api/intents/{intent_id}/cards/{card_id}/move")
def post_intents_by_intent_id_cards_by_card_id_move(request: Request):
    return not_yet("24")
