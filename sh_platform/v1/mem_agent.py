"""Agent memory (Nitin, 9 Oct): one memory for every agent (North, Span, Lumen, Tally), in the company's own data plane.

Short term, per conversation (agent + person + project/dashboard/case/intent): the last TURNS turns and the focus object (the last tile, plan
change, case or draft), so "make it dots" resolves against the tile just proposed.
Long term, per person (preferences, facts they told an agent, corrections) and per company (agreed words, linked to the K2 definitions rather
than copied). Each item keeps its source (the words, the agent, the conversation), time and how sure: `said` (explicit), `inferred` (from a
follow-up) or `model` (proposed by the model through egress, shown to the person first).

Files (data/<company>/memory/v1/): people/<hash of person>.json, company.json, convo/<hash>.json. Items are append-only: a change adds an item
that `supersedes` the old one; forgetting adds a tombstone and blanks the old item's words (the one in-place edit). Nobody opens another
person's file: the name of the file is derived from the signed-in person, never from a request. Rules write first; the model proposes only
through the egress gateway (`propose`) and what it proposes is shown as "I will remember: ...". No figure, email or restricted name is kept
(the filters of sh_platform.memory), so nothing stored can break the egress rules when it is read back into a prompt.

Hooks for any agent (Tally too): `lines(plane, agent, viewer, {"convo": <id>, "text": <message>})` -> strings for the prompt context, and
`after_turn(plane, agent, viewer, convo, text, reply, focus)` -> the "I will remember" lines to show."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone

from sh_platform.settings import model_is_off
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1.p1_project import Refused

log = logging.getLogger(__name__)
AGENTS = ("north", "span", "lumen", "tally")
NAMES = {"north": "North", "span": "Span", "lumen": "Lumen", "tally": "Tally", "company": "the company"}
KINDS = ("preference", "fact", "correction", "term")
EDITORS = frozenset({"company_admin", "analyst"})
TURNS = 12
RECALL_MAX = 8
MAX_TEXT = 300

COLORS = {"blue": "#2563eb", "red": "#dc2626", "green": "#16a34a", "orange": "#ea580c", "purple": "#7c3aed", "teal": "#0d9488",
          "pink": "#db2777", "yellow": "#ca8a04", "grey": "#6b7280", "gray": "#6b7280", "black": "#111827"}
PERIODS = {"daily": "day", "weekly": "week", "monthly": "month", "quarterly": "quarter", "yearly": "year", "annually": "year", "annual": "year"}
MARKS = (("point", r"\b(dots?|dotted|points?|scatter)\b"), ("bar", r"\bbars?\b|\bcolumn (?:chart|graph)s?\b"), ("area", r"\barea\b"),
         ("line", r"\blines?\b|\bline (?:chart|graph)\b"))
_ALWAYS = re.compile(r"\b(always|from now on|by default|going forward|in future|i (?:prefer|like)|remember (?:that|to))\b", re.I)
_CORR = re.compile(r"^\s*(no|nope|actually|correction|that'?s (?:not right|wrong|incorrect)|not quite|i meant|i said)\b[ ,:.-]*", re.I)
_CCY = r"(usd|sgd|eur|gbp|hkd|aud|inr|jpy|cny|chf)"
# lumen-memory-02: "I prefer SGD", "SGD only", "show me SGD" are a currency preference too, not only "in SGD" / "SGD figures"
_CURRENCY = re.compile(r"\b(?:in|using|as|prefer|like|want|use|show(?: me)?|keep(?: it)?|switch to|everything in)\s+(?:the\s+)?(?:figures\s+in\s+)?" + _CCY + r"\b"
                       r"|\b" + _CCY + r"\s+(?:figures|amounts|please|only|values|numbers)\b", re.I)
_PERIOD_NOT = re.compile(r"\b(?:rather than|instead of|not|and not|no longer)\s+(?:daily|weekly|monthly|quarterly|yearly|annual\w*|by (?:day|week|month|quarter|year)|per (?:day|week|month|quarter|year))", re.I)
_PERIOD = re.compile(r"\b(daily|weekly|monthly|quarterly|yearly|annually)\b|\b(?:by|per|each|every)\s+(day|week|month|quarter|year)\b", re.I)
_ANSWERS = (("short", r"\b(short|brief|concise)\b"), ("detailed", r"\b(detail\w*|in depth|thorough)\b"), ("bullets", r"\bbullets?\b"))
# NM-4: "keep answers to three lines" is an answer-style preference ("at most three lines"), not a fact
_LINES = re.compile(r"\b(?:to|in|at most|max(?:imum)?|under|within|no more than)\s+(one|two|three|four|five|\d)\s+(lines?|sentences?|bullets?|paragraphs?)\b", re.I)
# NM-4: a request for work ("I want a quarterly review", "we need a report") is the intent itself, never a memory; only lasting ways of working
_STATES = re.compile(r"\b(i|we) (usually|normally|tend to|like|prefer|hate|dislike|always)\b|\b(my|our) (team|boss|manager|committee|board|process|way)\b", re.I)
# NM-1: a fact the person states about themselves: what they look after, own, sign off, report to
# NM2-2: a lead-in before the fact ("A fact about me: I look after ...", "For the record, I ...", "FYI I ...") is allowed too
_LEAD_IN = (r"(?:(?:(?:a|one|another|some)\s+)?(?:fact|thing|note|detail)s?\s+about\s+me[,:.-]*\s+|for the record[,:]?\s+|fyi[,:]?\s+|"
            r"by the way[,:]?\s+|just so you know[,:]?\s+|(?:please\s+)?(?:remember|note)(?:\s+that)?[,:]?\s+)")
_ABOUT_ME = re.compile(r"^\s*(?:" + _LEAD_IN + r")*(?:i|i'm|i am)\s+(?:also\s+|the one who\s+)?"
                       r"(?:look after|looks after|am responsible for|responsible for|handle|manage|run|cover|own|sign off|approve|report to|"
                       r"work (?:on|with|in|for)|lead|head|am in charge of|in charge of|am the|the)\b", re.I)
_SWAP = (("i'm", "you're"), ("i am", "you are"), ("i", "you"), ("my", "your"), ("me", "you"), ("mine", "yours"), ("myself", "yourself"),
         ("we", "you"), ("our", "your"), ("am", "are"))
# EVT-T12: a question ("What do you remember about how I like my charts?") is asked, not told: nothing in it is kept
_QUESTION = re.compile(r"\?\s*$|^\s*(?:what|which|how|when|where|why|who)\b", re.I)
# lumen-memory-c1-08: a sentence that states a team decision ("decision: from now on the report goes out monthly, in SGD") is the project's,
# not the person's chart preference
_DECISION = re.compile(r"\b(?:decision|decided|we agreed|agreed that|goes out|go out|is sent|are sent|will be sent|signed off)\b", re.I)
_SINCE = re.compile(r"\b(?:last|past)\s+(\d{1,2})\s+months?\b|\b(?:last|past)\s+(year)\b|\b(?:last|past)\s+(quarter)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def who(viewer) -> str:
    """The person's key: the account, else the display name only when no other account shares it (two people never share a memory)."""
    if getattr(viewer, "account_id", None):
        return viewer.account_id
    return "" if getattr(viewer, "shared_name", False) else (getattr(viewer, "name", "") or "")


def _h(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _pfile(plane, viewer):
    if not who(viewer):
        raise Refused(403, "Sign in to see what the agents remember about you.")
    return plane.path("memory", "v1", "people", _h(who(viewer)) + ".json")


def _cfile(plane):
    return plane.path("memory", "v1", "company.json")


def _load(path) -> dict:
    doc = read_json_strict(path, dict)
    return doc if doc and isinstance(doc.get("items"), list) else {"items": []}


def live(doc: dict) -> list[dict]:
    """The items nothing has replaced or forgotten, oldest first."""
    gone = {i["supersedes"] for i in doc["items"] if i.get("supersedes")}
    return [i for i in doc["items"] if i["id"] not in gone and not i.get("forgotten")]


def _clean(text) -> str:
    return " ".join(str(text or "").split())[:MAX_TEXT]


def _keepable(plane, text: str) -> bool:
    """Free text is kept only when it holds no figure, email, account number or restricted name (the filters the old memory uses)."""
    from sh_platform.memory import filters
    try:
        terms = filters.restricted_terms(plane)  # a plane without a profile reads as empty, so a failure here is a broken profile
    except Exception:  # noqa: BLE001 - fail closed: without the restricted names nothing free is kept
        log.warning("restricted names could not be read; nothing is kept")
        return False
    return bool(text) and not filters.junk(text) and filters.allowed(text, terms)


def _view(i: dict, scope: str) -> dict:
    return {"id": i["id"], "scope": scope, "agent": i.get("agent"), "agent_name": NAMES.get(i.get("agent"), i.get("agent")), "kind": i["kind"],
            "text": i["text"], "sure": i.get("sure"), "at": i["at"], "source": i.get("source") or {}}


# ---- long term: write ----------------------------------------------------------------------------------------------------

def _put(path, scope: str, agent: str, kind: str, key: str | None, value, text: str, source: dict | None, sure: str, replace: str | None = None) -> tuple[dict, bool]:
    if agent not in AGENTS + ("company",) or kind not in KINDS:
        raise Refused(400, "That cannot be remembered.")
    text = _clean(text)
    if not text:
        raise Refused(400, "There is nothing to remember in that.")
    with lock_for(path):
        doc = _load(path)
        now = live(doc)
        same = next((i for i in now if (key and i.get("key") == key and i.get("value") == value) or (not key and i["kind"] == kind and i["text"].lower() == text.lower())), None)
        if same and not replace:
            return same, False
        old = replace or next((i["id"] for i in now if key and i.get("key") == key and i.get("agent") == agent), None)  # a10.2: one agent never replaces another's
        item = {"id": "m-" + secrets.token_hex(4), "scope": scope, "agent": agent, "kind": kind, "key": key, "value": value, "text": text,
                "source": source or {}, "sure": sure, "at": _now(), "supersedes": old}
        doc["items"].append(item)
        write_json_atomic(path, doc)
        return item, True


def remember(plane, viewer, agent: str, kind: str, text: str, key: str | None = None, value=None, source: dict | None = None, sure: str = "said") -> tuple[dict, bool]:
    """One item about this person. (item, new): new is False when the same thing is already remembered."""
    return _put(_pfile(plane, viewer), "person", agent, kind, key, value, text, source, sure)


def _editor(viewer) -> None:
    if not (set(getattr(viewer, "roles", ()) or ()) & EDITORS):
        raise Refused(403, "Only the company administrator or an analyst can change what the company remembers.")


def remember_company(plane, viewer, text: str = "", term: str = "", concept_id: str = "") -> dict:
    """A company item: a free line of text, or an agreed word linked to a K2 concept (the definition stays in K2; this holds only the link)."""
    _editor(viewer)
    src = {"by": who(viewer), "at": _now()}
    if term or concept_id:
        term, concept_id = _clean(term), _clean(concept_id)
        if not term or not concept_id:
            raise Refused(400, "Give the word and the definition it points to.")
        if not _keepable(plane, term):
            raise Refused(400, "That cannot be kept: no figures, emails or restricted names.")
        return _put(_cfile(plane), "company", "company", "term", "term:" + term.lower(), concept_id, f"{term} means what the company defines as {concept_id}", src, "said")[0]
    if not _keepable(plane, _clean(text)):
        raise Refused(400, "That cannot be kept: no figures, emails or restricted names.")
    return _put(_cfile(plane), "company", "company", "fact", None, None, text, src, "said")[0]


def _find(doc: dict, item_id: str) -> dict:
    it = next((i for i in live(doc) if i["id"] == item_id), None)
    if it is None:
        raise Refused(404, "There is no such memory.")
    return it


def forget(plane, viewer, item_id: str, company: bool = False) -> None:
    """Remove one item for good: the words are blanked and a tombstone added, so recall never returns it."""
    if company:
        _editor(viewer)
    path = _cfile(plane) if company else _pfile(plane, viewer)
    with lock_for(path):
        doc = _load(path)
        old = _find(doc, item_id)
        ids = {i["id"]: i for i in doc["items"]}
        it = old
        while it is not None:  # the earlier versions it replaced hold the same words: blank the whole chain
            it.update(text="", value=None, source={}, redacted=True)
            it = ids.get(it.get("supersedes"))
        doc["items"].append({"id": "m-" + secrets.token_hex(4), "kind": old["kind"], "forgotten": True, "supersedes": old["id"], "at": _now(), "text": ""})
        write_json_atomic(path, doc)


def correct(plane, viewer, item_id: str, text: str, company: bool = False) -> dict:
    """The person's own words replace the item. A preference keeps its effect when the new words still say the same kind of thing."""
    if company:
        _editor(viewer)
    text = _clean(text)
    path = _cfile(plane) if company else _pfile(plane, viewer)
    doc = _load(path)
    old = _find(doc, item_id)
    if not _keepable(plane, text):
        raise Refused(400, "That cannot be kept: no figures, emails or restricted names.")
    key, value = old.get("key"), old.get("value")
    if old["kind"] == "preference":
        got = next((p for p in extract(text, True) if p["key"] == key), None)
        value = got["value"] if got else None
        key = key if got else None
    item, _ = _put(path, old["scope"], old["agent"], old["kind"], key, value, text,
                   {"corrected_by": who(viewer), "was": old["id"]}, "said", replace=item_id)
    return item


# ---- long term: read --------------------------------------------------------------------------------------------------------

def mine(plane, viewer) -> list[dict]:
    return [_view(i, "person") for i in reversed(live(_load(_pfile(plane, viewer))))]


def company_items(plane) -> list[dict]:
    out = []
    for i in reversed(live(_load(_cfile(plane)))):
        v = _view(i, "company")
        if i["kind"] == "term":
            v["text"] = _term_text(plane, i) or v["text"]
        out.append(v)
    return out


def _term_text(plane, i: dict) -> str:
    """The agreed word, spelled from the K2 definition it links to (never a copy kept here)."""
    try:
        from sh_platform.v1 import k2_map
        word = i["key"].split(":", 1)[1]
        c = next((c for c in k2_map.concepts(plane, _Open()) if c["id"] == i["value"]), None)
        return f"{word} means {c['name']} on the company map" if c else ""
    except Exception:  # noqa: BLE001 - a missing map leaves the stored line
        return ""


class _Open:
    """The reader K2 needs when a company word is spelled out: the word is the company's own, shown to everyone in it."""
    roles = frozenset({"company_admin"})
    name = "company memory"
    account_id = "company-memory"


def preferences(plane, viewer) -> dict:
    """{key: value} of this person's live preferences, the ones that change how a tile or an answer looks."""
    try:
        return {i["key"]: i["value"] for i in live(_load(_pfile(plane, viewer))) if i["kind"] == "preference" and i.get("key")}
    except (OSError, ValueError, Refused):
        log.warning("the memory could not be read; no preference is applied")
        return {}


# ---- short term ---------------------------------------------------------------------------------------------------------------

def _convo_file(plane, viewer, agent: str, convo: str):
    return plane.path("memory", "v1", "convo", _h(f"{agent}|{who(viewer)}|{convo}") + ".json")


def convo(plane, viewer, agent: str, convo_id: str) -> dict:
    try:
        doc = read_json_strict(_convo_file(plane, viewer, agent, convo_id), dict)
    except (OSError, ValueError):
        doc = None
    return doc or {"turns": [], "focus": None}


def note(plane, viewer, agent: str, convo_id: str, by: str, text: str, focus: dict | None = None) -> None:
    """Keep a turn (the last TURNS) and, when given, the focus object the next follow-up resolves against."""
    path = _convo_file(plane, viewer, agent, convo_id)
    with lock_for(path):
        doc = convo(plane, viewer, agent, convo_id)
        if text:
            doc["turns"] = (doc["turns"] + [{"by": by, "text": _clean(text), "at": _now()}])[-TURNS:]
        if focus is not None:
            doc["focus"] = focus
        write_json_atomic(path, doc)


def clear_convo(plane, viewer, agent: str, convo_id: str) -> None:
    """A fresh talk: the short-term thread the model reads is emptied; what is remembered long term stays."""
    path = _convo_file(plane, viewer, agent, convo_id)
    with lock_for(path):
        write_json_atomic(path, {"turns": [], "focus": None})


def focus(plane, viewer, agent: str, convo_id: str) -> dict | None:
    return convo(plane, viewer, agent, convo_id).get("focus")


# ---- reading words ------------------------------------------------------------------------------------------------------------

def second_person(text: str) -> str:
    """NM-1: "I look after the Singapore entities" -> "You look after the Singapore entities" (the memory speaks to the person)."""
    out = text.strip().rstrip(".!")
    for a, b in _SWAP:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, flags=re.I)
    out = re.sub(r"^\s*(?:(?:(?:a|one|another|some)\s+)?(?:fact|thing|note|detail)s?\s+about\s+you[,:.-]*\s+|for the record[,:]?\s+|fyi[,:]?\s+|"
                 r"by the way[,:]?\s+|just so you know[,:]?\s+|(?:please\s+)?(?:remember|note)(?:\s+that)?[,:]?\s+)+", "", out, flags=re.I)
    return out[:1].upper() + out[1:] if out else out


def parse_style(text: str) -> dict:
    """What a message says about how a chart should look: mark, color, period, currency, since (months). Empty when it says none of that."""
    low = (text or "").lower()
    out: dict = {}
    marks = re.sub(rf"\b({'|'.join(COLORS)})\s+(lines?)\b", r"\1", low)  # lumen-memory-02: "blue lines" is a colour, not a line chart
    marks = re.sub(r"\b(one|two|three|four|five|\d+)\s+lines?\b", " ", marks)  # "answers of three lines" is a length, not a chart
    for mark, rx in MARKS:
        if re.search(rx, marks):
            out["mark"] = mark
            break
    c = next((w for w in COLORS if re.search(rf"\b{w}\b", low)), None)
    if c:
        out["color"] = c
    m = _PERIOD.search(_PERIOD_NOT.sub(" ", low))
    if m:
        out["period"] = PERIODS.get(m.group(1) or "", m.group(2))
    m = _CURRENCY.search(low)
    if m:
        out["currency"] = (m.group(1) or m.group(2)).upper()
    m = _SINCE.search(low)
    if m:
        out["since"] = int(m.group(1)) if m.group(1) else 12 if m.group(2) else 3
    return out


def extract(text: str, durable: bool, follow_up: bool = False, agent: str = "lumen") -> list[dict]:
    """The preferences a message states, by rules. {key, value, label, sure}. A mark is kept only when said to be lasting; colour, period and
    currency are also kept from a follow-up that changes them. Answer style needs a lasting phrase."""
    st = parse_style(text) if agent == "lumen" else {}  # how a chart looks is Lumen's business; only answer style is everyone's
    if not (durable or follow_up):
        return []
    out = []
    if st.get("color"):
        out.append({"key": "lumen.color", "value": st["color"], "label": f"you like {st['color']} for chart lines"})
    if st.get("currency"):
        out.append({"key": "lumen.currency", "value": st["currency"], "label": f"you like figures in {st['currency']}"})
    if st.get("period"):
        out.append({"key": "lumen.period", "value": st["period"], "label": f"you like figures by {st['period']}"})
    if durable and st.get("mark"):
        out.append({"key": "lumen.mark", "value": st["mark"], "label": f"you like {'dots' if st['mark'] == 'point' else st['mark'] + 's'} for charts"})
    if durable:
        n = _LINES.search(text)
        a = next((v for v, rx in _ANSWERS if re.search(rx, text.lower())), None)
        if n and re.search(r"\b(answers?|replies|reply|explain\w*|keep|responses?)\b", text.lower()):
            v = f"at most {n.group(1).lower()} {n.group(2).lower()}"
            out.append({"key": "answers.style", "value": v, "label": f"you like answers of {v}"})
        elif a and re.search(r"\b(answers?|replies|reply|explain\w*|responses?)\b", text.lower()):
            out.append({"key": "answers.style", "value": a, "label": f"you like {a} answers"})
    return [{**p, "sure": "said" if durable else "inferred"} for p in out]


def learn(plane, viewer, agent: str, text: str, convo_id: str = "", follow_up: bool = False, model=None) -> list[str]:
    """Write what the words say: preferences, a correction, or a lasting instruction. Returns the lines to show as "I will remember: ..."
    (only for what is new). Never raises: a memory failure must not stop the conversation."""
    try:
        text = _clean(text)
        if not text or not who(viewer):
            return []
        src = {"said": text if _keepable(plane, text) else "", "convo": convo_id, "agent": agent}  # a message with a figure or name is not kept as the source
        parts = [x for x in re.split(r"(?<=[.!?;])\s+", text) if x.strip() and not _QUESTION.search(x)]  # EVT-T12: questions keep nothing
        text = " ".join(parts)
        if not text:
            return []
        durable = bool(_ALWAYS.search(text))
        shown = []
        prefs, seen = [], set()
        for part in parts:  # a10.3: "from now on" makes its own sentence lasting, not the one-off request beside it
            if _DECISION.search(part):
                continue  # c1-08: a decision about a report is kept by the talk's summary, never as the person's preference
            for p in extract(part, bool(_ALWAYS.search(part)), follow_up, agent):
                if p["key"] not in seen:
                    seen.add(p["key"])
                    prefs.append(p)
        for p in prefs:
            _, new = remember(plane, viewer, agent, "preference", "Prefers: " + p["label"].replace("you like ", ""), p["key"], p["value"], src, p["sure"])
            if new:
                shown.append(p["label"])
        about = [p for p in parts if _ABOUT_ME.search(p) and _keepable(plane, p)]
        for part in about:  # NM-1: what the person says about themselves is a fact, kept in their words turned to "you"
            line = second_person(part)
            _, new = remember(plane, viewer, agent, "fact", line, None, None, src, "said")
            if new:
                shown.append(line)
        if not prefs and not about and _keepable(plane, text) and not _DECISION.search(text):
            kind = "correction" if _CORR.search(text) else "preference" if durable else None  # NM-4: a lasting instruction is how they like to work
            if kind:
                line = _CORR.sub("", text) if kind == "correction" else second_person(text)
                _, new = remember(plane, viewer, agent, kind, line, None, None, src, "said")
                if new:
                    shown.append(line)
        if not shown and model is not None and _STATES.search(text):  # the model only reads a message that states something about the person
            shown = propose(plane, viewer, agent, text, model, convo_id)
        return shown
    except Exception:  # noqa: BLE001
        log.warning("memory could not learn from a message", exc_info=True)
        return []


def propose(plane, viewer, agent: str, text: str, model, convo_id: str = "") -> list[str]:
    """The model proposes lasting items from a message that states one; only through the egress gateway (run_agent), names tokenised by it.
    Whatever it proposes passes the same keep rules and is returned to be shown as "I will remember"."""
    import json
    import os
    if model is None or model_is_off():
        return []
    try:
        from sh_platform.agents.loop import run_agent
        from sh_platform.agents.registry import ToolRegistry
        from sh_platform.agents.runs import RunRegistry
        from sh_platform.build.agents.runtime import OpenGate
        from sh_platform.v1.egress_fit import fit
        from sh_platform.v1.router import route
        if model == "auto":
            from sh_platform.egress.providers import build_model_client
            model = build_model_client(plane)
        from sh_platform.v1 import e6_trace
        from sh_platform.v1.agent_tools import AGENT_MODULE
        model = route(model, agent, "summary", "", plane, want_json=True)
        if model is None:
            return []
        system = ('You note what a person wants remembered about themselves and how they like to work. Reply with ONLY JSON {"items": '
                  '[{"kind": "preference|fact|correction", "text": "<one short sentence starting with You, no figure, no name>"}]}; '
                  '{"items": []} when there is nothing lasting. A request for work (a report, a review, a dashboard, a change) is NOT '
                  'something to remember: it is handled as a request. Only a lasting preference, a fact about the person (what they look '
                  'after, who they report to) or a correction.')
        with e6_trace.joined():  # NM-7/SS-9: one trace per answer: this call is a step of the answer it follows
            res = run_agent(model, ToolRegistry(OpenGate()), plane.company_id, AGENT_MODULE.get(agent, "m1_intent"),
                            f"{NAMES.get(agent, agent)} memory", system, fit({"said": text[:500]}), "What, if anything, should be remembered?",
                            recorder=RunRegistry(plane))
        if res.status != "done" or res.numbers_replaced:  # a reply that states a figure is not a thing to remember
            return []
        a, b = res.text.find("{"), res.text.rfind("}")
        got = json.loads(res.text[a:b + 1]).get("items") or []
        shown = []
        for g in got[:3]:
            t, k = _clean(g.get("text")).rstrip("."), g.get("kind")
            if re.match(r"^(they|the person|the user|he|she|someone)\b", t, re.I) or \
                    re.search(r"\b(wants?|needs?) (a|an|the|to build|to get)\b|\basked for\b|\brequests?\b", t, re.I):
                continue  # NM-4: third-person lines ("They want a quarterly review ...") and requests for work are not memories
            if k in ("preference", "fact", "correction") and _keepable(plane, t):
                _, new = remember(plane, viewer, agent, k, t, None, None, {"said": _clean(text) if _keepable(plane, _clean(text)) else "", "convo": convo_id, "agent": agent}, "model")
                if new:
                    shown.append(t)
        return shown
    except Exception:  # noqa: BLE001 - any failure leaves nothing remembered
        log.warning("the model's memory proposal failed", exc_info=True)
        return []


# ---- recall -------------------------------------------------------------------------------------------------------------------

def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) > 2}


def recall(plane, agent: str, viewer, context: dict | None = None) -> dict:
    """The few items that matter for this turn: {preferences, items, company, turns, focus}. A preference keyed for another agent is left out;
    facts and corrections are shared by every agent. Ranked by the agent that learned it, overlap with the message, then recency."""
    ctx = context or {}
    want = _words(ctx.get("text", ""))
    try:
        mine_ = live(_load(_pfile(plane, viewer)))
        theirs = live(_load(_cfile(plane)))
    except (OSError, ValueError, Refused):
        log.warning("the memory could not be read; the agent goes without it")
        return {"preferences": {}, "items": [], "company": [], "turns": [], "focus": None}
    other = tuple(a + "." for a in AGENTS if a != agent)

    def rank(i):
        return ((i.get("agent") == agent) * 2 + len(want & _words(i["text"])) * 3, i["at"])
    pick = sorted((i for i in mine_ if not (i.get("key") or "").startswith(other)), key=rank, reverse=True)[:RECALL_MAX]
    c = convo(plane, viewer, agent, ctx["convo"]) if ctx.get("convo") else {"turns": [], "focus": None}
    return {"preferences": {i["key"]: i["value"] for i in pick if i["kind"] == "preference" and i.get("key")},
            "items": [_view(i, "person") for i in pick],
            "company": [{**_view(i, "company"), "text": (_term_text(plane, i) if i["kind"] == "term" else "") or i["text"]}
                        for i in sorted(theirs, key=lambda i: (len(want & _words(i["text"])), i["at"]), reverse=True)[:4]],
            "turns": c["turns"], "focus": c["focus"]}


def lines(plane, agent: str, viewer, context: dict | None = None) -> list[str]:
    """The recall as plain strings for a prompt. Strings only: the egress row guard refuses a list of records, and these are no records."""
    r = recall(plane, agent, viewer, context)
    out = [f"The person asked earlier (by {NAMES.get(i.get('agent'), 'an agent')}): {i['text']}" if i["kind"] == "correction" else f"About this person: {i['text']}"
           for i in r["items"]]
    out += [f"The company agreed: {i['text']}" for i in r["company"]]
    if r["focus"]:
        out.append("Last thing in focus: " + ", ".join(f"{k} {v}" for k, v in r["focus"].items() if isinstance(v, (str, int))))
    return out[: RECALL_MAX + 4]


def after_turn(plane, agent: str, viewer, convo_id: str, text: str, reply: str = "", focus: dict | None = None, follow_up: bool = False, model=None) -> list[str]:
    """The one call an agent makes after a turn: keep the turns and focus (short term), learn from the words (long term). Returns the
    "I will remember" lines."""
    try:
        note(plane, viewer, agent, convo_id, "person", text, focus)
        if reply:
            note(plane, viewer, agent, convo_id, agent, reply)
    except Exception:  # noqa: BLE001
        log.warning("the turn could not be kept", exc_info=True)
    return learn(plane, viewer, agent, text, convo_id, follow_up, model)


def remember_line(shown: list[str]) -> str:
    items = [s.strip().rstrip(".;!") for s in shown if s and s.strip()]
    return ("I will remember: " + "; ".join(items) + ". You can change or remove this under Settings, What the agents remember about you.") if items else ""
