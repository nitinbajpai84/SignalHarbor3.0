"""IC v2 (08): North as the workflow runner.

North reads the type contract (02) and the intent record, keeps its own thread in `intents/<id>/north.json` (turns, drafts, the
turn, nudges), asks the missing start question, drafts openings, closure and proposals, nudges and watches the clock. It never
signs, closes, cancels, extends, deletes or shares: no function here writes `intent.json`. Every text North makes for a record is
a draft until a named person confirms it. Model calls go through the kernel agent runtime (number guard, run log, egress client).

Other modules call `north_turn(plane, intent_id, viewer, text)` and `panel(...)`; the Pulse builder calls `nudges_for(plane, viewer)`.
"""
import json
import logging
import re
import secrets
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.m1_intent.agent.north import AGENT_NAME, EARLIER_PERSON, EARLIER_REPLIES, MODULE_ID
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.intents import _plane, _viewer, access, store
from sh_platform.intents import clock as time_box
from sh_platform.intents.types import load_catalogue
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.memory.summarise import background as memory_background
from sh_platform.memory.summarise import remember_for_account
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import links
from sh_platform.profile import store as profile_store

log = logging.getLogger(__name__)
router = APIRouter()
RULES_FILE = Path(__file__).with_name("north_rules.yaml")
LATEST = "LATEST MESSAGE FROM THE PERSON (answer this one; the earlier turns in the context are only background):"
SLOTS = ("organiser", "sponsor", "decider", "owner", "reporter", "participants", "advisers")
CAN_ANSWER = frozenset({"organiser", "sponsor", "decider", "owner", "reporter", "participant", "adviser"})
LEFT_TOKEN = re.compile(r"\b(?:PERSON|EMAIL|PHONE|ORG|COMPANY|ACCOUNT)_\d{2,}\b")
ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# a person asking North to act for them: only an instruction at the start of the message, never a sentence that mentions closing
ACT = re.compile(r"^\s*(?:please\s+|can you\s+|could you\s+)?(sign|approve|close|cancel|delete|reopen|extend|rate)\b", re.I)
ACT_KIND = {"sign": "sign", "approve": "sign", "close": "close", "cancel": "close", "delete": "close", "reopen": "close",
            "extend": "extend", "rate": "rate"}


class NorthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _iso(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


# ---- records

def _intent(plane, intent_id: str) -> dict:
    if not ID.match(str(intent_id)):
        raise NorthError(404, "We could not find that intent.")
    try:
        doc = read_json_strict(plane.path("intents", intent_id, "intent.json"), dict)
    except (OSError, ValueError, CrossCompanyError):
        doc = None
    if not doc:
        raise NorthError(404, "We could not find that intent.")
    return doc


def _file(plane, intent_id: str) -> Path:
    return plane.path("intents", intent_id, "north.json")


def _blank() -> dict:
    return {"turns": [], "drafts": [], "asked": [], "turn": None, "nudges": [], "last_check": None, "clock_fired": [],
            "memory_done": False}


def _read(plane, intent_id: str) -> dict:
    doc = read_json_strict(_file(plane, intent_id), dict) or {}
    return {**_blank(), **doc}


def _update(plane, intent_id: str, fn):
    """Read, change, write one thread under the file's lock. `fn(state)` may raise NorthError; nothing is written then."""
    path = _file(plane, intent_id)
    with lock_for(path):
        st = _read(plane, intent_id)
        out = fn(st)
        write_json_atomic(path, st)
        return out


# ---- who is who

def _ids(plane, viewer) -> set[str]:
    from sh_platform.memory.api import person_id
    mine = {viewer.account_id} if viewer.account_id else set()
    try:
        pid = person_id(plane, viewer.account_id)
    except (OSError, ValueError, KeyError):
        pid = None
    return mine | ({pid} if pid else set())


def memory_opening(plane, viewer, type_: str | None = None) -> dict | None:
    """North's first line from what it remembers about this person ("Last time you ..."), or None when it remembers nothing (spec 46)."""
    from sh_platform.intents import memory_close
    from sh_platform.memory.api import person_id
    try:
        return memory_close.opening_line(plane, person_id(plane, viewer.account_id), type_)
    except (OSError, ValueError, KeyError):
        log.warning("North's memory could not be read for the opening line")
        return None


def _slot(intent: dict, slot: str) -> list[str]:
    raw = (intent.get("people") or {}).get(slot)
    items = raw if isinstance(raw, list) else [raw]
    out = []
    for x in items:
        x = x.get("id") or x.get("account_id") or x.get("person_id") if isinstance(x, dict) else x
        if x:
            out.append(str(x))
    return out


def seat_of(plane, intent: dict, viewer) -> str | None:
    """The viewer's seat in this intent, or None (no panel, no thread): see spec 08, Rules."""
    ids = _ids(plane, viewer)
    if "super_admin" in viewer.roles or not ids:
        return None
    if intent.get("state") == "draft":
        return "organiser" if intent.get("created_by") in ids else None
    me = access.Me.for_viewer(plane, viewer)  # R2: account id, then linked person, then a name nobody else shares
    for slot, name in (("organiser", "organiser"), ("sponsor", "sponsor"), ("decider", "decider"), ("owner", "owner"),
                       ("reporter", "reporter"), ("participants", "participant"), ("advisers", "adviser"), ("observers", "observer")):
        if ids & set(_slot(intent, slot)) or access._named(intent, slot, me):
            return name
    roles = access.roles_of(intent, me)
    if "company_admin" in roles:
        return "admin"
    if "affected" in roles and "content" in roles:
        return "affected"
    if "content" in roles or tier(plane, intent, viewer) == "content":  # share visitors, people named in its records (R1): read only
        return "observer"
    return None


def tier(plane, intent: dict, viewer) -> str | None:
    """R1: the one decider (visibility's matrix through store.tier_of), with people named in the intent's records and share rows."""
    return store.tier_of(intent, viewer, store.areas_of(plane, viewer))


def seat_or_refuse(plane, intent: dict, viewer) -> str:
    """The seat, else 404 when the matrix hides the intent from this person (R1), 403 when they see only its card (no panel)."""
    seat = seat_of(plane, intent, viewer)
    if seat is None:
        if "super_admin" not in viewer.roles and tier(plane, intent, viewer) is not None:
            raise NorthError(403, "You can see that this intent exists. North's panel is for people who can open it.")
        raise NorthError(404, "We could not find that intent.")
    return seat


def _name(plane, pid: str | None) -> str:
    if not pid or pid == "group":
        return "the group"
    try:
        people = profile_store.load(plane).get("people") or {}
    except (OSError, ValueError):
        return "someone"
    p = people.get(pid) or next((q for q in people.values() if links._account_of(q) == pid), None)
    cell = (p or {}).get("name")
    return str(cell.get("value") if isinstance(cell, dict) else cell or "") or "someone"


def _account(plane, pid: str) -> str:
    try:
        p = (profile_store.load(plane).get("people") or {}).get(pid)
    except (OSError, ValueError):
        p = None
    return (links._account_of(p) if p else None) or pid


def _in_intent(intent: dict, pid: str) -> bool:
    return any(pid in _slot(intent, s) for s in SLOTS)


# ---- contract, stage, clock

def _contract(intent: dict) -> dict:
    return (load_catalogue().get("types") or {}).get(intent.get("type")) or {}


def _stage(intent: dict) -> dict | None:
    return next((s for s in intent.get("stages") or [] if s.get("state") != "closed"), None)


def _stage_name(intent: dict, stage: dict | None) -> str:
    named = next((s.get("name") for s in _contract(intent).get("stages") or [] if stage and s.get("key") == stage.get("key")), None)
    return str(named or (stage or {}).get("key") or "this stage")


def _stage_end(intent: dict, stage: dict | None) -> str | None:
    """The stage's end: the written one, else its working-day share of the time box (clock.py), else the time box end."""
    if not stage:
        return None
    if stage.get("ends"):
        return stage["ends"]
    try:
        due = time_box._due(intent, stage)
    except (KeyError, TypeError, ValueError):
        due = None
    return due.isoformat() if due else (intent.get("time_box") or {}).get("ends")


def _date(x) -> date | None:
    try:
        return datetime.fromisoformat(str(x)[:10]).date() if x else None
    except ValueError:
        return None


def _plural(n: int, one: str) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {one}s"


def clock(intent: dict, now: datetime) -> dict:
    """The clock line from the intent's own time box, in working days through sh_platform/intents/clock.py so it agrees with
    StageClock. `percent_left` is None when the time box is missing."""
    tb = intent.get("time_box") or {}
    try:
        start, end = time_box.parse(tb["starts"]), time_box.parse(tb["ends"])
    except (KeyError, ValueError, TypeError):
        start = end = None
    if not start or not end or end <= start:
        return {"line": "Not available yet: no time box set (the start and end dates of the time box).", "percent_left": None, "facts": []}
    c = time_box.clock(start, end, now)
    total = c["working_days_total"]
    if c["state"] == "overdue":
        h = -c["hours_left"]
        return {"line": f"{time_box.overdue_words(h)}.", "percent_left": 0, "over": h,
                "facts": [("time box in days", total), ("days over" if h >= 24 else "hours over", h // 24 if h >= 24 else h)]}
    hours = c["unit"] == "hours"
    left = c["hours_left"] if hours else c["working_days_left"]
    return {"line": f"Day {c['day_of']} of {total}, {time_box.left_words(c)}.", "percent_left": c["percent_left"], "over": 0,
            "facts": [("time box in days", total), ("day", c["day_of"]), ("hours left" if hours else "days left", left)]}


def _facts(intent: dict, clk: dict) -> list[dict]:
    """The only figures a draft may state: the clock and one count (the guard replaces any other number). group_size 5 is the
    smallest that passes the guard; these are record counts, not company figures."""
    rows = list(clk["facts"]) + [("people on this intent", sum(len(_slot(intent, s)) for s in SLOTS))]
    rows += [("number written in the title", n) for n in re.findall(r"\d+(?:\.\d+)?", str(intent.get("title") or ""))]  # a title like "Q3 plan" is the person's own text
    return [{"id": f"fact{i}", "label": k, "value": str(v), "group_size": 5} for i, (k, v) in enumerate(rows)]


def _short(d: date | None) -> str:
    return f"{d.day} {d:%b}" if d else ""


# ---- start questions

def _answered(intent: dict, st: dict, q: dict) -> bool:
    got = intent.get("start_answers") or {}
    keys = [q["id"], *(q.get("fields") or [])]
    return any(got.get(k) not in (None, "", [], {}) for k in keys) or any(
        a.get("key") == q["id"] and a.get("answered_at") for a in st["asked"])


def missing_start(intent: dict, st: dict) -> dict | None:
    """The first required start question of the type contract not yet answered, or None."""
    return next((q for q in _contract(intent).get("start_questions") or [] if q.get("required") and not _answered(intent, st, q)), None)


# ---- the model (kernel runtime only)

def _json_text(text: str) -> str | None:
    a, b = text.find("{"), text.rfind("}")
    try:
        got = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        return None
    t = got.get("text") if isinstance(got, dict) else None
    return t.strip() if isinstance(t, str) and t.strip() else None


def _call(plane, model, gate, system: str, context: dict, question: str) -> str | None:
    """North's reply text from the kernel agent runtime, or None when the model cannot answer."""
    if model is None or gate is None:
        return None
    res = run_agent(model, ToolRegistry(gate), plane.company_id, MODULE_ID, AGENT_NAME, system, context, question,
                    recorder=RunRegistry(plane))
    return LEFT_TOKEN.sub("a colleague", res.text) if res.status == "done" else None  # a name token the gateway did not map back


def _system(kind: str) -> str:
    r = rules()
    return r["role"].strip() + "\nRules:\n" + "\n".join(f"- {x}" for x in r["rules"]) + "\n" + r["draft_prompts"][kind].strip()


def drafting_view(plane, intent: dict, clk: dict) -> dict:
    """What North may see of an intent: a fixed list of record fields, names, counts and the clock. Cards, notes, ratings and
    anything sealed or anonymous are never read, so they cannot reach a draft."""
    stage = _stage(intent)
    return {"title": intent.get("title"), "purpose": intent.get("purpose"), "type": _contract(intent).get("title"),
            "state": intent.get("state"), "stage": _stage_name(intent, stage), "stage_ends": (stage or {}).get("ends"),
            "people": {s: [_name(plane, p) for p in _slot(intent, s)] for s in SLOTS if _slot(intent, s)},
            "areas": intent.get("areas") or [], "time_box": clk["line"],
            "stages": [_stage_name(intent, s) for s in intent.get("stages") or []]}


# ---- drafts and the turn

def _draft(kind: str, stage: str | None, text: str, *, to: list[str], may: list[str], based: list[str], now: datetime,
           options: list[dict] | None = None) -> dict:
    return {"id": secrets.token_hex(6), "kind": kind, "stage": stage, "text": text, "status": "draft", "by": "north",
            "addressed_to": to, "may_confirm": may, "based_on": based, "made_at": _iso(now), "decided_by": None,
            "decided_at": None, "options": options, "picked": None, "reason": None}


def _turn(st: dict, role: str, text: str, kind: str, now: datetime, to: str = "all", by: str | None = None, **extra) -> dict:
    t = {"id": secrets.token_hex(6), "role": role, "to": to, "text": text, "at": _iso(now), "answered": None, "kind": kind,
         "by": by, **extra}
    st["turns"].append(t)
    return t


def _holder_ids(intent: dict, slot: str) -> list[str]:
    return _slot(intent, slot) or _slot(intent, "organiser")


def _effective_may(intent: dict, d: dict) -> list[str]:
    """A draft addressed to a person who has left the intent moves to the organiser."""
    live = [p for p in d["may_confirm"] if _in_intent(intent, p) or p == intent.get("created_by")]
    return live or _slot(intent, "organiser") or [intent.get("created_by")]


def _open(st: dict, *kinds: str) -> list[dict]:
    return [d for d in st["drafts"] if d["status"] == "draft" and (not kinds or d["kind"] in kinds)]


def _has(st: dict, kind: str, stage: str | None) -> bool:
    return any(d["kind"] == kind and d.get("stage") == stage for d in st["drafts"])


def _set_turn(intent: dict, st: dict, miss: dict | None, now: datetime) -> None:
    org = (_slot(intent, "organiser") or [intent.get("created_by")])[0]
    stage = _stage(intent)
    waiting = _open(st, "opening", "closure", "next")
    if miss:
        holder, what, question = org, "answer the start question", miss["lead"]
    elif waiting:
        d = waiting[0]
        holder, what, question = _effective_may(intent, d)[0], {"opening": "confirm the opening message", "closure": "confirm the closure summary",
                                                               "next": "pick what comes next"}[d["kind"]], None
    elif intent.get("state") == "closing" and (rules()["closing_holder"].get(intent.get("type")) or None):
        c = rules()["closing_holder"][intent["type"]]
        who = _holder_ids(intent, c["slot"])
        holder, what, question = who[0], c["what"], None
    elif intent.get("state") in ("open", "in_session") and stage:
        c = (rules()["turn_holders"].get(intent.get("type")) or {}).get(stage.get("key"))
        who = _holder_ids(intent, c["slot"]) if c else [org]
        holder, what, question = ("group" if len(who) > 1 else who[0]), (c["what"] if c else "carry on with this stage"), None
    else:
        st["turn"] = None
        return
    old = st["turn"] or {}
    same = old.get("holder") == holder and old.get("what") == what
    st["turn"] = {"holder": holder, "what": what, "question": question, "since": old["since"] if same else _iso(now),
                  "due": _stage_end(intent, stage)}


def _ask_start(st: dict, intent: dict, miss: dict, now: datetime) -> None:
    last = next((t for t in reversed(st["turns"]) if t["kind"] == "question" and t.get("key")), None)
    if last and last["key"] == miss["id"] and not last["answered"]:
        return
    org = (_slot(intent, "organiser") or [intent.get("created_by")])[0]
    _turn(st, "north", miss["lead"], "question", now, to=org, key=miss["id"])
    if not any(a["key"] == miss["id"] for a in st["asked"]):
        st["asked"].append({"key": miss["id"], "question": miss["lead"], "answered_at": None})


def _make_opening(plane, intent, st, stage, clk, model, gate, now) -> None:
    org = _slot(intent, "organiser") or [intent.get("created_by")]
    view = drafting_view(plane, intent, clk)
    text = _json_text(_call(plane, model, gate, _system("opening"),
                            {"intent": view, "facts": _facts(intent, clk), "contract": {"start_questions": [q["lead"] for q in _contract(intent).get("start_questions") or []]}},
                            "Write the opening message for this stage.") or "")
    if not text:
        due = _date(_stage_end(intent, stage))
        text = rules()["templates"]["opening"].format(
            stage=view["stage"], what=(rules()["turn_holders"].get(intent["type"], {}).get(stage["key"]) or {}).get("what", "carry on").capitalize(),
            due=f"Due {_short(due)}." if due else "Not available yet: no end date set for this stage.")
    st["drafts"].append(_draft("opening", stage["key"], text, to=[], may=org[:1], now=now,
                               based=["the intent record", "the type contract", "the time box"]))


def _make_closing(plane, intent, st, clk, model, gate, now) -> None:
    org = _slot(intent, "organiser") or [intent.get("created_by")]
    view = drafting_view(plane, intent, clk)
    text = _json_text(_call(plane, model, gate, _system("closure"), {"intent": view, "facts": _facts(intent, clk)},
                            "Write the closure summary.") or "") or rules()["templates"]["closure"].format(title=intent.get("title") or "this intent")
    st["drafts"].append(_draft("closure", None, text, to=[], may=org[:1], now=now, based=["the intent record", "the time box"]))
    kinds = ("initiative", "problem", "decision", "backlog", "handled", "nothing")
    labels = rules()["next_options"]
    st["drafts"].append(_draft("next", None, rules()["templates"]["next"], to=[], may=org[:1], now=now, based=["the intent record"],
                               options=[{"key": k, "label": labels[k], "reason": "optional"} for k in kinds]))


# ---- clock check and nudges

def _clock_cards(intent, st, clk, now) -> None:
    pct = clk["percent_left"]
    stage = _stage(intent)
    if pct is None or intent.get("state") not in ("open", "in_session") or not stage:
        return
    org = (_slot(intent, "organiser") or [intent.get("created_by")])[0]
    marks = sorted(rules()["clock_percent_left"], reverse=True)
    for p in marks:
        if pct > p or p in st["clock_fired"]:
            continue
        st["clock_fired"].append(p)
        text = f"At most {p} percent of the time box is left."  # the clock sentence is on the TimeCard already: said once
        if p == marks[-1] and not _open(st, "extend_close_cancel"):  # one open proposal at a time (spec 08, open question 5)
            st["drafts"].append(_draft("extend_close_cancel", stage["key"], text + " The time box may not hold. Pick one option and say why.",
                                       to=[], may=[org], now=now, based=["the time box"],
                                       options=[dict(o) for o in rules()["proposal_options"]]))
        else:
            _turn(st, "north", text, "nudge", now, to=org, card=p)
            st["nudges"].append({"to": org, "at": _iso(now), "kind": "strip", "stage": stage["key"], "text": text})


def _nudge_holder(plane, intent, st, now) -> None:
    turn, stage = st["turn"], _stage(intent)
    due = _date((turn or {}).get("due"))
    if not turn or not stage or not due or turn.get("question") or intent.get("state") not in ("open", "in_session"):
        return
    left = (due - now.date()).days
    if left > rules()["nudge_window_days"]:
        return
    who = _slot(intent, "participants") if turn["holder"] == "group" else [turn["holder"]]
    for pid in who:
        if any(n["to"] == pid and n["stage"] == stage["key"] and n["at"][:10] == _iso(now)[:10] for n in st["nudges"]):
            continue  # one nudge per person per stage per day
        when = f"by {due:%A}. {_plural(left, 'day')} left." if left >= 0 else f". It was due {due:%A}, {_plural(-left, 'day')} late."
        text = f"{_name(plane, pid).split(' ')[0]}, please {turn['what']} {when}".replace(" .", ".")
        text = text[:1].upper() + text[1:]
        st["nudges"].append({"to": pid, "at": _iso(now), "kind": "pulse", "stage": stage["key"], "text": text})
        _turn(st, "north", text, "nudge", now, to=pid)


def advance(plane, intent_id: str, *, model=None, gate=None, now: datetime | None = None) -> None:
    """North's own work: ask the missing start question, draft what is due, set the turn, check the clock (once a day), write the
    memory entry after closure. Safe to call on every open; it adds nothing that is already there."""
    now = _now(now)
    intent = _intent(plane, intent_id)
    clk = clock(intent, now)

    def work(st: dict) -> None:
        # a closed, closing or cancelled intent is read-only: no start question, nothing written to the thread for one
        miss = None if intent.get("state") in ("closed", "closing", "cancelled") else missing_start(intent, st)
        stage = _stage(intent)
        if miss:
            _ask_start(st, intent, miss, now)
        elif intent.get("state") in ("open", "in_session") and stage and not _has(st, "opening", stage["key"]):
            _make_opening(plane, intent, st, stage, clk, model, gate, now)
        elif intent.get("state") == "closing" and not _has(st, "closure", None):
            _make_closing(plane, intent, st, clk, model, gate, now)
        _set_turn(intent, st, miss, now)
        if (st["last_check"] or "")[:10] != _iso(now)[:10]:
            st["last_check"] = _iso(now)
            _clock_cards(intent, st, clk, now)
            _nudge_holder(plane, intent, st, now)

    _update(plane, intent_id, work)
    if intent.get("state") == "closed":
        _remember(plane, intent_id, intent, model, gate)


def _remember(plane, intent_id, intent, model, gate) -> None:
    """After closure North writes its memory entry (existing filters); once per intent."""
    if model is None or gate is None or _read(plane, intent_id)["memory_done"]:
        return
    org = (_slot(intent, "organiser") or [None])[0]
    st = _read(plane, intent_id)
    lines = [f"{'North' if t['role'] == 'north' else 'Person'}: {t['text']}" for t in st["turns"] if t["role"] != "system" and t["to"] in ("all", org)]
    if org and remember_for_account(plane, "north", _account(plane, org), lines, model=model, gate=gate, recorder=RunRegistry(plane),
                                    company_id=plane.company_id, module_id=MODULE_ID, conversation=intent_id) >= 0:
        _update(plane, intent_id, lambda s: s.update(memory_done=True))


# ---- what a viewer sees

def _can_see(turn: dict, ids: set[str], seat: str) -> bool:
    return seat in ("organiser", "admin") or turn["to"] in ("all", *ids) or turn.get("by") in ids


def _fdate(iso: str | None) -> str:
    return _short(_date(iso))


def _turn_line(plane, st: dict, ids: set[str], seat: str) -> dict | None:
    t = st["turn"]
    if not t:
        return {"line": "Nobody is waiting", "mine": False}
    mine = t["holder"] in ids or (t["holder"] == "group" and seat == "participant")
    since = f", since {_fdate(t['since'])}" if t.get("since") else ""
    line = f"Your turn: {t['what']}" if mine else f"Waiting for {_name(plane, t['holder'])}: {t['what']}{since}"
    return {"line": line, "mine": mine, "holder_name": _name(plane, t["holder"]), "what": t["what"], "since": t.get("since"), "due": t.get("due")}


def _draft_view(plane, intent: dict, d: dict, ids: set[str], seat: str) -> dict:
    may = _effective_may(intent, d)
    can = bool(ids & set(may)) and d["status"] == "draft"
    chip = ("Draft by North, not confirmed" if d["status"] == "draft"
            else f"Confirmed by {_name(plane, d['decided_by'])}, {_fdate(d['decided_at'])}" if d["status"] in ("confirmed", "edited")
            else "Discarded")
    return {"id": d["id"], "kind": d["kind"], "stage": d["stage"], "text": d["text"], "status": d["status"], "chip": chip,
            "based_on": d["based_on"], "options": d["options"], "can_confirm": can, "confirm_by": _name(plane, may[0]),
            "is_proposal": bool(d["options"]), "picked": d["picked"], "reason": d["reason"]}


def panel(plane, intent_id: str, viewer, *, model=None, gate=None, now: datetime | None = None, check: bool = True) -> dict:
    """The panel state for this viewer (GET /api/intents/{id}/north). Opening the panel runs North's own work."""
    now = _now(now)
    intent = _intent(plane, intent_id)
    seat = seat_or_refuse(plane, intent, viewer)
    if check:
        advance(plane, intent_id, model=model, gate=gate, now=now)
    st, ids = _read(plane, intent_id), _ids(plane, viewer)
    turn = _turn_line(plane, st, ids, seat)
    ask = st["turn"] and st["turn"].get("question")
    ended = intent.get("state") in ("closed", "cancelled")  # a closed intent's panel offers nothing to act on: no drafts, no answer box
    drafts = [] if ended else [_draft_view(plane, intent, d, ids, seat) for d in st["drafts"]
              if d["status"] == "draft" and (not d["addressed_to"] or ids & set(d["addressed_to"]) or seat in ("organiser", "admin") or ids & set(d["may_confirm"]))]
    can_answer = seat in CAN_ANSWER and not ended
    ask, turn = (None, {"line": "Nobody is waiting", "mine": False}) if ended else (ask, turn)
    mine_q = bool(ask) and turn["mine"]
    out = {
        "intent": {"id": intent_id, "title": intent.get("title"), "state": intent.get("state")},
        "head": {"name": "North", "role_line": rules()["role_lines"].get(intent.get("type"), "runs this intent with you")},
        "seat": seat, "read_only": not can_answer, "can_answer": can_answer,
        "asking": {"question": ask, "mine": turn["mine"], "holder_name": turn.get("holder_name")} if ask else None,
        "turn": turn, "clock": (lambda c: c["line"] if c["percent_left"] is None else None)(clock(intent, now)), "drafts": drafts,
        "thread": [{"id": t["id"], "role": t["role"], "text": t["text"], "at": t["at"], "kind": t["kind"],
                    "mine": t.get("by") in ids and t["role"] == "person",
                    "by_name": _name(plane, t["by"]) if t["role"] == "person" and t.get("by") not in ids else None}
                   for t in st["turns"] if _can_see(t, ids, seat)],
        "waiting": sum(1 for d in drafts if d["can_confirm"]) + (1 if mine_q else 0),
        "nudge": next(({"text": n["text"], "at": n["at"]} for n in reversed(st["nudges"]) if n["to"] in ids and n["at"][:10] == _iso(now)[:10]
                       and intent.get("state") in ("open", "in_session")), None),
        "voice": {"available": False, "reason": "Spoken replies are not set up for intents yet."},
    }
    if seat in ("organiser", "admin"):
        c = {k: sum(1 for d in st["drafts"] if d["status"] == k) for k in ("confirmed", "edited", "discarded")}
        out["footer"] = {"nudges": len(st["nudges"]), **c} if st["drafts"] else {"nudges": len(st["nudges"]),
                                                                                   "note": "Not available yet: no drafts made"}
    return out


def nudges_for(plane, viewer, now: datetime | None = None) -> list[dict]:
    """Today's open nudges for this person across the company's intents, for the Pulse builder: no draft text, only the nudge
    sentence, the intent title and stage name, and the stage end."""
    now, ids, out = _now(now), _ids(plane, viewer), []
    root = plane.path("intents")
    for f in sorted(root.glob("*/north.json")) if root.is_dir() else []:
        try:
            iid = f.parent.name
            mine = [n for n in _read(plane, iid)["nudges"] if n["to"] in ids and n["kind"] == "pulse" and n["at"][:10] == _iso(now)[:10]]
            if not mine:
                continue  # read the thread first: most intents have nothing for this person, and only these need the record
            intent = _intent(plane, iid)
            if intent.get("state") not in ("open", "in_session", "closing"):
                continue
        except (NorthError, OSError, ValueError):
            continue
        if mine:
            n = mine[-1]
            st = next((s for s in intent.get("stages") or [] if s.get("key") == n["stage"]), None)
            out.append({"intent_id": iid, "title": n["text"], "detail": f"{intent.get('title')}, {_stage_name(intent, st)}",
                        "due": _stage_end(intent, st), "at": n["at"], "record": f"intents/{iid}/intent.json"})
    return out


# ---- a person answers or asks

def north_turn(plane, intent_id: str, viewer, text: str, *, model=None, gate=None, now: datetime | None = None,
               ask: bool = False, wrong: bool = False) -> dict:
    """A person answers North's question (when it is their turn) or asks North something; North replies in the same call.
    `ask` always sends the text as a question, never as the answer to the start question; `wrong` tells the organiser North got
    something wrong (a thread line for them, nothing in the record, no model call). Returns the panel state with `reply` (North's turn)."""
    now = _now(now)
    intent = _intent(plane, intent_id)
    seat = seat_or_refuse(plane, intent, viewer)
    if seat not in CAN_ANSWER:
        raise NorthError(403, "You are reading this intent. You cannot answer.")
    text = (text or "").strip()
    if not text or len(text) > 2000:
        raise NorthError(422, "Write your answer in one to two thousand characters.")
    ids = _ids(plane, viewer)
    if wrong and ((_slot(intent, "organiser") or [intent.get("created_by")])[0] in ids):
        raise NorthError(403, "You are the organiser, so there is no one to tell. Change the text yourself.")
    me = viewer.account_id or sorted(ids)[0]
    clk = clock(intent, now)

    def person(st: dict) -> tuple[bool, dict | None]:
        t = st["turn"] or {}
        mine = not (ask or wrong) and (t.get("holder") in ids or (t.get("holder") == "group" and seat == "participant"))
        key = next((x["key"] for x in reversed(st["turns"]) if x["kind"] == "question" and x.get("key") and not x["answered"]), None) if mine and t.get("question") else None
        if wrong:
            org = (_slot(intent, "organiser") or [intent.get("created_by")])[0]
            _turn(st, "system", f"{viewer.name} says North got this wrong: {text}", "wrong", now, to=org, by=me)
            return False, None
        _turn(st, "person", text, "answer" if mine else "question", now, to="north", by=me, **({"key": key} if key else {}))
        if mine:
            for x in st["turns"]:
                if x["kind"] in ("question", "nudge") and x["to"] in ids and not x["answered"]:
                    x["answered"] = _iso(now)
        if key:
            for a in st["asked"]:
                if a["key"] == key:
                    a["answered_at"] = _iso(now)
        return mine, ({"key": key} if key else None)

    mine, started = _update(plane, intent_id, person)
    act = ACT.match(text)
    if wrong:
        out = panel(plane, intent_id, viewer, model=model, gate=gate, now=now, check=False)
        out["reply"] = rules()["wrong_noted"]
        return out
    if act:
        reply = rules()["refusals"][ACT_KIND[act.group(1).lower()]]
    elif started:
        reply = None  # the next start question or the opening draft is North's reply: advance writes it below
    else:
        st = _read(plane, intent_id)
        mem = memory_background(plane, "north", viewer.account_id) if model is not None else ""
        shown = [t for t in st["turns"] if _can_see(t, ids, "participant")]
        ctx = {"intent": drafting_view(plane, intent, clk), "facts": _facts(intent, clk),
               "background_earlier_north_replies": [t["text"] for t in shown if t["role"] == "north"][-EARLIER_REPLIES:],
               "background_earlier_person_messages": [t["text"] for t in shown if t["role"] == "person"][-EARLIER_PERSON:-1]}
        if mem:
            ctx["background_memory"] = "BACKGROUND\n" + mem + "\nEND BACKGROUND"
        reply = _call(plane, model, gate, _system("answer"), ctx, f"{LATEST} {text}")
    if reply is not None or not started:
        _update(plane, intent_id, lambda st: _turn(st, "north", reply or rules()["no_model"], "answer" if reply else "error", now,
                                                   to=me, answered=bool(reply) or None))
    if not act:
        advance(plane, intent_id, model=model, gate=gate, now=now)
    out = panel(plane, intent_id, viewer, model=model, gate=gate, now=now, check=False)
    out["reply"] = next((t["text"] for t in reversed(out["thread"]) if t["role"] == "north"), None)
    return out


# ---- confirm, discard, pick

def decide(plane, intent_id: str, viewer, draft_id: str, act: str, *, text: str | None = None, key: str | None = None,
           reason: str | None = None, model=None, gate=None, now: datetime | None = None) -> dict:
    """The named person confirms, edits, discards a draft or picks an option on a proposal. North records it; the record the draft
    is about (stage, time box, closure) is changed only by the screens that own it (01, 07, 09)."""
    now = _now(now)
    intent = _intent(plane, intent_id)
    seat = seat_or_refuse(plane, intent, viewer)
    ids, me = _ids(plane, viewer), viewer.account_id
    if intent.get("state") in ("closed", "cancelled"):
        raise NorthError(409, "This intent is closed. Nothing here is waiting for a decision.")

    def change(st: dict) -> None:
        d = next((x for x in st["drafts"] if x["id"] == draft_id), None)
        if d is None:
            raise NorthError(404, "We could not find that draft.")
        may = _effective_may(intent, d)
        if not ids & set(may):
            raise NorthError(403, f"Only {_name(plane, may[0])} can confirm this.")
        if d["status"] != "draft":
            raise NorthError(409, "This draft has already been dealt with.")
        d.update(decided_by=me, decided_at=_iso(now))
        if act == "discard":
            d["status"] = "discarded"
            _turn(st, "system", f"Draft discarded by {viewer.name}.", "draft", now)
        elif act == "pick":
            opt = next((o for o in d["options"] or [] if o["key"] == key), None)
            if opt is None:
                raise NorthError(422, "Pick one of the options.")
            if opt["reason"] == "required" and not (reason or "").strip():
                raise NorthError(422, "Say why, in a line, before you record your pick.")
            d.update(status="confirmed", picked=key, reason=(reason or "").strip() or None)
            _turn(st, "system", f"Pick recorded by {viewer.name}: {opt['label']}.", "pick", now)
        else:
            if d["options"]:
                raise NorthError(422, "Pick one of the options.")
            new = (text or "").strip()
            if new and new != d["text"]:
                d.update(status="edited", original_text=d["text"], text=new, by="person")
            else:
                d["status"] = "confirmed"
            _turn(st, "system", f"{d['kind'].capitalize()} {'edited and ' if d['status'] == 'edited' else ''}confirmed by {viewer.name}.", "draft", now)

    _update(plane, intent_id, change)
    advance(plane, intent_id, model=model, gate=gate, now=now)
    return panel(plane, intent_id, viewer, now=now, check=False)


# ---- routes

def _model(request: Request, plane):
    from sh_platform.egress.providers import ProviderError, build_model_client
    from sh_platform.settings import load_model_env
    factory = getattr(request.app.state, "north_model_factory", None)  # tests plug a stub in here
    try:
        if factory:
            return factory(plane)
        env = getattr(request.app.state, "model_env", None)
        return build_model_client(plane, dict(env) if env is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _run(request: Request, fn):
    try:
        plane = _plane(request)
        return fn(plane, _viewer(request), _model(request, plane), request.app.state.entitlements)
    except NorthError as e:
        code = {403: "not_allowed", 404: "not_found"}.get(e.status, "invalid")
        return JSONResponse({"error": code, "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "You do not have access to this."}, status_code=403)


class Said(BaseModel):
    text: str
    ask: bool = False
    wrong: bool = False


class Edit(BaseModel):
    text: str | None = None


class Pick(BaseModel):
    key: str
    reason: str | None = None


@router.get("/api/intents/{intent_id}/north")
def get_intents_by_intent_id_north(intent_id: str, request: Request):
    """Spec 08: a person who only sees that the intent exists gets no panel and no thread: `seat` null, nothing else (no refusal, so
    the page they may open shows no error). Writes still refuse them."""
    def read(p, v, m, g):
        try:
            return panel(p, intent_id, v, model=m, gate=g)
        except NorthError as e:
            if e.status != 403:
                raise
            return {"intent": {"id": intent_id}, "seat": None}
    return _run(request, read)


@router.post("/api/intents/{intent_id}/north/turns")
def post_intents_by_intent_id_north_turns(intent_id: str, body: Said, request: Request):
    return _run(request, lambda p, v, m, g: north_turn(p, intent_id, v, body.text, model=m, gate=g, ask=body.ask, wrong=body.wrong))


@router.post("/api/intents/{intent_id}/north/clock-check")
def post_intents_by_intent_id_north_clock_check(intent_id: str, request: Request):
    return _run(request, lambda p, v, m, g: panel(p, intent_id, v, model=m, gate=g))


@router.post("/api/intents/{intent_id}/north/drafts/{draft_id}/confirm")
def post_intents_by_intent_id_north_drafts_by_draft_id_confirm(intent_id: str, draft_id: str, request: Request, body: Edit | None = None):
    return _run(request, lambda p, v, m, g: decide(p, intent_id, v, draft_id, "confirm", text=body.text if body else None, model=m, gate=g))


@router.post("/api/intents/{intent_id}/north/drafts/{draft_id}/discard")
def post_intents_by_intent_id_north_drafts_by_draft_id_discard(intent_id: str, draft_id: str, request: Request):
    return _run(request, lambda p, v, m, g: decide(p, intent_id, v, draft_id, "discard", model=m, gate=g))


@router.post("/api/intents/{intent_id}/north/proposals/{draft_id}/pick")
def post_intents_by_intent_id_north_proposals_by_draft_id_pick(intent_id: str, draft_id: str, body: Pick, request: Request):
    return _run(request, lambda p, v, m, g: decide(p, intent_id, v, draft_id, "pick", key=body.key, reason=body.reason, model=m, gate=g))
