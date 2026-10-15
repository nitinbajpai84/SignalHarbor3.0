"""IC v2 (27): the process map. One file per intent, `intents/<id>/processes.json`, every field a provenance cell (profile/store.py).

Lens drafts processes from the wall cards (never a step: no source lists steps in order today), people edit, the named owner confirms,
and the confirmed map goes into the charter as the "Processes involved" page. The rules live in `Refusal` checks in the domain functions;
the routes only open the plane, the viewer and the file.

`question_budget(plane, intent_id, person)` is the one shared cap of three open questions per person across Define (process map,
glossary, catalogue and governed state): it counts `questions[]` with state "open" in every `intents/<id>/*.json`. The glossary,
catalogue and governed-state cards call it before they send a question.
"""
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.intents import _plane, _viewer
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import store, view

log = logging.getLogger(__name__)
router = APIRouter()
CAP = 3
FIELDS = ("name", "owner", "trigger", "frequency", "inputs", "outputs")
CONFIRM_CLEARING = frozenset(FIELDS)  # an edit to any of these (or the steps) clears a confirmation; links do not
STEP_FIELDS = ("name", "actor", "systems", "inputs", "outputs")
LIST_FIELDS = frozenset({"inputs", "outputs", "systems"})
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
UNSORTED = "unsorted"
NO_WORDS = "1 sealed card"
NOT_YET = "not available yet"  # what the number guard writes over a figure it cannot trace


class Refusal(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _slug(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or UNSORTED


def _v(item: dict | None, key: str) -> Any:
    c = (item or {}).get(key)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


# ---- cells -------------------------------------------------------------------------------------------------------------------------

def _cell(value: Any, mark: str, by: str, src: str, ref: dict | None = None, agent: str | None = None) -> dict:
    """A profile cell. `card` is not a profile ref kind (open question 4), so the pointer is attached here after the check."""
    out = store.cell(value, {"mark": mark, "by": by, "from": src, "agent": agent})
    if ref:
        out["ref"] = ref
    return out


def _unknown(who: str = "Lens", agent: str | None = "lens") -> dict:
    return _cell(None, "unknown", who, "Not known yet", agent=agent)


def _stated(value: Any, who: "Ctx", src: str) -> dict:
    return _cell(value, "stated", who.name or "A team member", src)


def _guessed(value: Any, src: str, ref: dict, quote: str | None = None) -> dict:
    """`quote` is the passage the value came from, kept so the screen can show it when the source is clicked."""
    out = _cell(value, "guessed", "Lens", src, ref, "lens")
    if quote:
        out["quote"] = _short(quote, 240)
    return out


# ---- who is asking -----------------------------------------------------------------------------------------------------------------

class Ctx:
    """The caller, resolved against the intent: tier is write | read | own | counts."""
    def __init__(self, viewer: view.Viewer, person: str, tier: str, organiser: bool):
        self.viewer, self.person, self.tier, self.organiser = viewer, person, tier, organiser
        self.name, self.roles = viewer.name, viewer.roles

    @property
    def can_edit(self) -> bool:
        return self.tier == "write"

    @property
    def can_draft(self) -> bool:
        return self.tier == "write" and (self.organiser or bool(self.roles & {"sponsor", "analyst"}))


def _tokens(x: Any) -> set[str]:
    if isinstance(x, str):
        return {view.norm(x)} if x.strip() else set()
    if isinstance(x, dict):
        return set().union(*(_tokens(v) for v in x.values() if isinstance(v, (str, list, dict)))) if x else set()
    if isinstance(x, list):
        return set().union(*(_tokens(v) for v in x)) if x else set()
    return set()


def _path(plane, iid: str, *rest: str):
    if not _ID.fullmatch(iid or ""):
        raise Refusal(404, "We could not find that.")
    try:
        return plane.path("intents", iid, *rest)
    except CrossCompanyError:
        raise Refusal(404, "We could not find that.") from None


def _intent(plane, iid: str) -> dict:
    try:
        rec = read_json_strict(_path(plane, iid, "intent.json"), dict)
    except (OSError, ValueError):
        raise Refusal(404, "We could not find that.") from None
    if rec is None:
        raise Refusal(404, "We could not find that.")
    return rec


def _person_id(people: dict, viewer: view.Viewer) -> str:
    for pid, p in people.items():
        if viewer.account_id and _v(p, "account_id") == viewer.account_id:
            return pid
    for pid, p in people.items():
        if view.norm(_v(p, "name") or "") == view.norm(viewer.name) and not viewer.shared_name:
            return pid
    return ""


def _context(plane, iid: str, viewer: view.Viewer, doc: dict | None = None) -> tuple[dict, Ctx]:
    rec = _intent(plane, iid)
    people = store.raw(plane)["people"]
    person = _person_id(people, viewer)
    me = {view.norm(viewer.account_id or ""), view.norm(viewer.name)} | ({person} if person else set())
    me.discard("")
    ppl = rec.get("people") or {}

    def named(*slots: str) -> bool:
        return any(me & _tokens(ppl.get(s)) for s in slots)

    if rec.get("state") == "draft" and not (me & _tokens(rec.get("created_by"))):
        raise Refusal(404, "We could not find that.")
    from sh_platform.intents import store as S  # lazy: visibility first (file 05), before any role grants a tier
    seen = S.tier_of(rec, viewer, S.areas_of(plane, viewer))
    if seen is None:
        raise Refusal(404, "We could not find that.")
    organiser = named("organiser")
    doc = doc if doc is not None else _load(plane, iid)
    owns = any(p["owner"] and view.norm(_v(p, "owner") or "") == person for p in doc["processes"]) if person else False
    asked = any(q["to_person"] == person for q in doc["questions"]) if person else False
    if named("organiser", "sponsor") or (named("participants", "advisers") and "approver" not in viewer.roles):
        tier = "write"  # an approver reads the map at sign-off, even when also listed as a participant (spec 27, Grace)
    elif named("observers") or ("approver" in viewer.roles and seen == "content") or (named("affected") and rec.get("affected_may_read")):
        tier = "read"
    elif owns or asked:
        tier = "own"
    elif "company_admin" in viewer.roles or named("affected"):
        tier = "counts"
    else:
        raise Refusal(404, "We could not find that.")
    return rec, Ctx(viewer, person, tier, organiser)


# ---- the file ----------------------------------------------------------------------------------------------------------------------

def _blank_doc(iid: str) -> dict:
    return {"version": 0, "intent_id": iid, "drafted_at": None, "drafted_from": {"cards": 0, "interviews": 0, "documents": 0},
            "processes": [], "questions": []}


def _load(plane, iid: str) -> dict:
    try:
        doc = read_json_strict(_path(plane, iid, "processes.json"), dict)
    except (OSError, ValueError):
        raise Refusal(500, "The process map could not be read. Please ask your administrator.") from None
    return doc if doc is not None else _blank_doc(iid)


def _write(plane, iid: str, version: int, change) -> Any:
    """Read, check the version, change, write whole, under the file's lock. 409 on a stale version."""
    path = _path(plane, iid, "processes.json")
    with lock_for(path):
        doc = _load(plane, iid)
        if version != doc["version"]:
            raise Refusal(409, "Someone changed the process map. Reload it and try again.")
        out = change(doc)
        _settle(plane, iid, doc)
        doc["version"] += 1
        write_json_atomic(path, doc)
    _point_intent_at_file(plane, iid, doc)
    return out


def _point_intent_at_file(plane, iid: str, doc: dict) -> None:
    """`refs.processes_file` and `outcome.processes` {count, confirmed, state} on the intent record (ids and counts, never a copy of the map);
    the record's own version is left to its owner, and a closed intent keeps the counts it closed with."""
    path = _path(plane, iid, "intent.json")
    c = counters(doc)
    counts = {"count": c["processes"], "confirmed": c["confirmed"], "state": c["state"]}
    with lock_for(path):
        rec = read_json_strict(path, dict)
        if not isinstance(rec, dict):
            return
        want_ref = f"intents/{iid}/processes.json"
        closed = rec.get("state") in ("closed", "cancelled")
        if (rec.get("refs") or {}).get("processes_file") != want_ref or (not closed and (rec.get("outcome") or {}).get("processes") != counts):
            rec["refs"] = {**(rec.get("refs") or {}), "processes_file": want_ref}
            if not closed:
                rec["outcome"] = {**(rec.get("outcome") or {}), "processes": counts}
            write_json_atomic(path, rec)


def _history(p: dict, ctx: Ctx, kind: str, field: str | None = None, was: Any = None) -> None:
    row = {"by": ctx.name, "at": _now(), "kind": kind, "field": field}
    if was is not None:
        row["was"] = was
    p["history"].append(row)


# ---- question cap ------------------------------------------------------------------------------------------------------------------

def question_budget(plane, intent_id: str, person: str, doc: dict | None = None) -> dict:
    """Open questions this person already holds across Define for this intent, against the shared cap of three (A-045, ruling 9).
    `doc` stands in for processes.json while a write is in flight. Returns {cap, open, free}."""
    me, n = view.norm(person), 0
    folder = _path(plane, intent_id)
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if f.name == "processes.json" and doc is not None:
            data = doc
        else:
            try:
                data = read_json_strict(f, dict)
            except (OSError, ValueError):
                continue
        qs = (data or {}).get("questions") if isinstance(data, dict) else None
        n += sum(1 for q in qs or [] if isinstance(q, dict) and q.get("state") == "open" and view.norm(q.get("to_person") or "") == me)
    if doc is not None and not (folder / "processes.json").exists():
        n += sum(1 for q in doc["questions"] if q["state"] == "open" and view.norm(q["to_person"]) == me)
    return {"cap": CAP, "open": n, "free": max(0, CAP - n)}


def _promote(plane, iid: str, doc: dict) -> None:
    """Queued to open, in the order asked, while the person has fewer than three open."""
    for q in doc["questions"]:
        if q["state"] == "queued" and question_budget(plane, iid, q["to_person"], doc)["free"] > 0:
            q["state"] = "open"


def _settle(plane, iid: str, doc: dict) -> None:
    """Lens re-checks after every write: a waiting question whose gap an edit has filled (owner, trigger, steps) is closed, and the next queued one moves up."""
    by_id = {p["id"]: p for p in doc["processes"]}
    for q in doc["questions"]:
        p = by_id.get(q["process_id"])
        filled = p is None or p["status"] == "removed" or (q["topic"] in ("owner", "trigger") and _v(p, q["topic"]) is not None)             or (q["topic"] == "steps" and bool(p["steps"]))
        if q["state"] in ("open", "queued") and filled:
            q["state"], q["dropped_reason"] = "dropped", "Settled by an edit."
    _promote(plane, iid, doc)


def _ask(doc: dict, p: dict, topic: str, to: str, text: str, step_id: str | None = None) -> None:
    if not to or any(q["process_id"] == p["id"] and q["topic"] == topic and q["state"] != "dropped" for q in doc["questions"]):
        return
    doc["questions"].append({"id": _new_id("q"), "process_id": p["id"], "step_id": step_id, "topic": topic, "to_person": to, "text": text,
                             "state": "queued", "asked_at": _now(), "answered_at": None, "answer": None, "dropped_reason": None})


# ---- the draft ---------------------------------------------------------------------------------------------------------------------

def _wall_cards(plane, rec: dict, viewer: view.Viewer) -> tuple[dict, dict]:
    """The viewer's cut of the profile and the cards of this intent's wall (all cards when the record names no wall yet)."""
    prof = view.read(plane, viewer)
    rooms = set((rec.get("refs") or {}).get("wall_session_ids") or [])
    cards = {k: c for k, c in prof["cards"].items() if not rooms or _v(c, "room") in rooms or c.get("sealed") is True}
    return prof, cards


def _cluster_of(c: dict) -> str:
    return str(_v(c, "cluster") or _v(c, "topic") or "").strip()


def clusters(cards: dict) -> list[dict]:
    """Cluster is the card's cluster cell, else its topic (decision: the wall topic is the cluster until North names others)."""
    out: dict[str, dict] = {}
    for c in cards.values():
        name = _cluster_of(c) if "silhouette" not in c else ""
        if name:
            out.setdefault(_slug(name), {"id": _slug(name), "name": name, "cards": 0})["cards"] += 1
    return sorted(out.values(), key=lambda x: x["name"])


def _short(text: str, n: int = 60) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "..."


_SENT = re.compile(r"(?<=[.;!?])\s+")
_STOP = frozenset("the and for with from that this have are was were into over than when then about their there which".split())
_TRIGGER = re.compile(r"\b(when|once|after|before|as soon as|arrives?|arrived|each time|whenever)\b", re.I)
_FREQ = re.compile(r"\b(daily|weekly|monthly|quarterly|annually|every (?:day|week|month|quarter|year|working day)|each (?:day|week|month|quarter|year)"
                   r"|a few times a year|once a (?:day|week|month|quarter|year))\b", re.I)
_STEP = re.compile(r"^(?:first|next|finally|then|after that)\b[,:]?\s*(.+)$|\bthen\s+(?:we\s+|i\s+)?(.+)$", re.I)
_EMPTY = re.compile(r"^(nothing|no more|none|not available)", re.I)
MODEL_SAYS = ("You read short passages from a family office (cards, interviews, documents) and list the business processes they describe. "
              'Reply with JSON only: {"processes": [{"name": str, "owner": a person\'s name or null, "trigger": str or null, '
              '"frequency": str or null, "steps": [str], "passage": the letter of the passage this comes from}]}. '
              "Use only what a passage says. If it gives no steps, trigger, owner or frequency, use null or []. Never invent a step.")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", str(text).lower()) if w not in _STOP}


def _answer_text(v: Any) -> str:
    if isinstance(v, dict):
        return " ".join([str(v.get("answer") or "")] + [str(f.get("answer") or "") for f in v.get("followups") or [] if isinstance(f, dict)]).strip()
    return str(v or "").strip()


def passages(prof: dict, cards: dict) -> list[dict]:
    """What Lens may read for this viewer: wall cards (never a sealed or silhouette one), interview answers and document summaries."""
    out: list[dict] = []
    for cid, c in cards.items():
        if "silhouette" in c or _v(c, "sealed") is True:
            continue
        text = " ".join(str(_v(c, q) or "") for q in ("q1", "q2", "q3")).strip()
        if text:
            author = _v(c, "author") if _v(c, "anonymous") is not True else ""
            out.append({"kind": "card", "label": f"Card: {_short(_v(c, 'q1') or _v(c, 'topic') or text)}", "ref": {"kind": "card", "id": cid}, "text": text,
                        "cluster": _slug(_cluster_of(c)), "author": author if author in prof["people"] else ""})
    for pid, iv in prof["interviews"].items():
        rows = [_answer_text(_v(iv, q)) for q in sorted(k for k in iv if re.fullmatch(r"q\d+", k))]
        text = " ".join(t for t in rows if t and not _EMPTY.match(t))
        if text:
            name = _v(prof["people"].get(pid) or {}, "name")
            out.append({"kind": "interview", "label": f"Interview with {name}" if name else "An interview", "ref": {"kind": "interview", "id": pid},
                        "text": text, "cluster": "", "author": ""})
    for gid, grp in prof["inputs"].items():
        summary = _v(grp, "summary")
        docs = [d for d in (_v(grp, "documents") or []) if isinstance(d, dict) and not d.get("restricted")]
        if isinstance(summary, str) and summary.strip() and docs:
            out.append({"kind": "document", "label": f"Document: {docs[0].get('name')}", "ref": {"kind": "document", "id": str(docs[0].get("id") or gid)},
                        "text": summary.strip(), "cluster": "", "author": ""})
    return out


def _owner_from_profile(prof: dict, words: set[str]) -> dict | None:
    """A person whose `owns` line in the company profile shares a word with this process."""
    for pid, p in prof["people"].items():
        owns = _v(p, "owns")
        for line in owns if isinstance(owns, list) else [owns] if owns else []:
            if words & _words(line) and _v(p, "name"):
                return {"pid": pid, "src": f"Profile: {_v(p, 'name')} owns '{_short(line)}'", "ref": {"kind": "person", "id": pid}, "quote": str(line)}
    return None


def _rule_items(ps: list[dict], items: dict, prof: dict) -> None:
    """No model: enrich each card item from sentences of the interviews and documents that share its words. A step only from an ordering word."""
    for it in items.values():
        words = _words(it["name"])
        it["owner"] = _owner_from_profile(prof, words)
        for p in (x for x in ps if x["kind"] != "card"):
            for sent in _SENT.split(p["text"]):
                if not (words & _words(sent)):
                    continue
                src = {"src": p["label"], "ref": p["ref"]}
                if it["trigger"] is None and _TRIGGER.search(sent):
                    it["trigger"] = {"text": _short(sent, 160), "quote": sent, **src}
                m = _FREQ.search(sent)
                if it["frequency"] is None and m:
                    it["frequency"] = {"text": m.group(0), "quote": sent, **src}
                m = _STEP.search(sent.strip())
                if m:
                    it["steps"].append({"text": _short(next(g for g in m.groups() if g), 100), "quote": sent, **src})


def _model_items(plane, ps: list[dict], prof: dict, rt=None) -> list[dict] | None:
    """Lens through the agent runtime and the egress gateway. None when there is no model or the call failed (the rules draft instead).
    A reply is kept only where it points at a passage that exists and shares words with what it states: no passage, no value."""
    if not ps:
        return None
    from modules.m2_baseline.agent import lens as agent
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.intents import lens
    rt = rt or lens.runtime_for_plane(plane)
    if rt.model is None:
        return None
    seen_text: set[str] = set()
    shown = []
    for p in sorted(ps, key=lambda x: x["kind"] == "card"):  # interviews and documents first; a card repeated word for word once
        if p["text"] not in seen_text and len(shown) < 26:
            seen_text.add(p["text"])
            shown.append(p)
    body = "\n".join(f"[{chr(65 + i)}] {p['text'][:350]}" for i, p in enumerate(shown))
    try:
        res = run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id, agent.MODULE_ID, agent.AGENT_NAME, MODEL_SAYS,
                        {"company": rt.company_name, "passages": body}, "List the processes.", recorder=rt.recorder)
        if res.status != "done":
            return None
        data = json.loads(res.text[res.text.index("{"): res.text.rindex("}") + 1])
    except (ValueError, OSError, agent.ModelUnreachable):
        return None
    by_name = {view.norm(_v(p, "name") or ""): pid for pid, p in prof["people"].items()}
    out = []
    for raw in (data.get("processes") if isinstance(data, dict) else None) or []:
        try:
            p = shown[ord(str(raw.get("passage") or "?").strip()[:1].upper()) - 65]
        except (TypeError, ValueError, IndexError, AttributeError):
            continue
        name = str(raw.get("name") or "").strip()
        if not name or NOT_YET in name.lower():
            continue
        src = {"src": p["label"], "ref": p["ref"], "quote": p["text"]}
        ok = lambda t: bool(t) and NOT_YET not in t.lower() and bool(_words(t) & _words(p["text"]))  # noqa: E731
        trig, freq, who = str(raw.get("trigger") or "").strip(), str(raw.get("frequency") or "").strip(), str(raw.get("owner") or "")
        pid = by_name.get(view.norm(who))
        out.append({"name": _short(name, 80), "cluster": p["cluster"], "passage": p, "trigger": {"text": trig, **src} if ok(trig) else None,
                    "frequency": {"text": freq, **src} if ok(freq) else None,
                    "owner": {"pid": pid, "src": p["label"], "ref": p["ref"], "quote": p["text"]} if pid and view.norm(who) in view.norm(p["text"]) else None,
                    "steps": [{"text": _short(str(t), 100), **src} for t in raw.get("steps") or [] if ok(str(t))]})
    return out


def _lens_draft(plane, rec: dict, prof: dict, cards: dict, organiser: str, rt=None) -> tuple[list[dict], dict]:
    """Candidate processes, each field guessed with its source. The model reads cards, interviews and documents (rules do when it cannot).
    A card topic is only an anchor for its break lines: once the model names real processes, an anchor with nothing left is dropped."""
    systems = {sid: _v(s, "name") for sid, s in prof["systems"].items() if _v(s, "name")}
    ps = passages(prof, cards)
    found: dict[str, dict] = {}
    n_cards = 0
    for cid, c in cards.items():
        topic = str(_v(c, "topic") or "").strip()
        if "silhouette" in c or not topic or _v(c, "sealed") is True:
            continue  # a sealed card the viewer may not see is never drafted from; its words are never quoted
        n_cards += 1
        cluster = _cluster_of(c)
        item = found.setdefault(f"{_slug(cluster)}:{_slug(topic)}", {
            "key": f"{_slug(cluster)}:{_slug(topic)}", "cluster": _slug(cluster), "name": topic, "ref": {"kind": "card", "id": cid}, "breaks": [], "systems": [],
            "author": "", "owner": None, "trigger": None, "frequency": None, "steps": []})
        author = _v(c, "author") if _v(c, "anonymous") is not True else ""
        item["author"] = item["author"] or (author if author in prof["people"] else "")
        q2 = str(_v(c, "q2") or "").strip()
        if q2:
            item["breaks"].append({"card_id": cid, "text": q2})
        q3 = str(_v(c, "q3") or "").lower()
        item["systems"] += [sid for sid, name in systems.items() if q3 and name.lower() in q3 and sid not in item["systems"]]
    mine, by = _model_items(plane, ps, prof, rt), "model"
    if mine:
        anchors = list(found.values())
        for m in mine:
            cid = m["passage"]["ref"]["id"] if m["passage"]["kind"] == "card" else None
            key = f"{m['cluster'] or (anchors[0]['cluster'] if anchors else UNSORTED)}:{_slug(m['name'])}"
            it = found.setdefault(key, {"key": key, "cluster": key.split(":", 1)[0], "name": m["name"], "ref": m["passage"]["ref"], "breaks": [], "systems": [],
                                        "author": m["passage"]["author"], "owner": None, "trigger": None, "frequency": None, "steps": []})
            it.update({k: m[k] for k in ("owner", "trigger", "frequency", "steps")})
            for a in anchors:  # the card's own words move to the process it describes
                moved = [b for b in a["breaks"] if cid and b["card_id"] == cid]
                it["breaks"] += moved
                a["breaks"] = [b for b in a["breaks"] if b not in moved]
        for k in [k for k, v in found.items() if v in anchors and not v["breaks"] and not v["systems"]]:
            del found[k]
    else:
        by = "rules"
        _rule_items(ps, found, prof)
    return list(found.values()), {"cards": n_cards, "interviews": sum(1 for p in ps if p["kind"] == "interview"),
                                  "documents": sum(1 for p in ps if p["kind"] == "document"), "drafted_by": by}


def _new_process(cluster: str, ctx: Ctx, status: str) -> dict:
    who, agent = ("Lens", "lens") if status == "guessed" else (ctx.name or "A team member", None)
    return {"id": _new_id("p"), "cluster": cluster or UNSORTED, "key": None,
            "name": _unknown(who, agent), "owner": _unknown(who, agent), "trigger": _unknown(who, agent), "frequency": _unknown(who, agent),
            "inputs": _unknown(who, agent), "outputs": _unknown(who, agent), "systems": _unknown(who, agent),
            "steps": [], "breaks": [], "status": status, "confirmed": None, "removed": None, "created_by": who, "history": []}


def draft(plane, iid: str, viewer: view.Viewer, version: int, rt=None) -> dict:
    rec, ctx = _context(plane, iid, viewer)
    if not ctx.can_draft:
        raise Refusal(403, "Only the organiser, the sponsor or the analyst can ask Lens to draft.")
    prof, cards = _wall_cards(plane, rec, viewer)
    if not clusters(cards):
        raise Refusal(422, "Form clusters first. Lens drafts processes from them.")
    asked = _organiser_person(plane, rec)

    def change(doc: dict) -> dict:
        items, seen = _lens_draft(plane, rec, prof, cards, "", rt)
        made = 0
        for it in items:
            src, ref = f"Card: {_short(it['name'])}", it["ref"]
            p = next((x for x in doc["processes"] if x.get("key") == it["key"] and x["status"] != "removed"), None)
            if p is None:
                p = _new_process(it["cluster"], ctx, "guessed")
                p["key"], p["created_by"] = it["key"], "Lens"
                p["name"] = _guessed(it["name"], src, ref)
                doc["processes"].append(p)
                _history(p, Ctx(view.Viewer("Lens", frozenset()), "", "write", False), "drafted", "name")
                made += 1
            sys_c = p["systems"]
            if it["systems"] and (sys_c["mark"] == "unknown" or (sys_c.get("agent") == "lens" and sys_c["mark"] == "guessed")):
                p["systems"] = _guessed(it["systems"], src, ref)
            for field, found in (("owner", it["owner"] and {**it["owner"], "text": it["owner"]["pid"]}), ("trigger", it["trigger"]), ("frequency", it["frequency"])):
                if found and p[field]["mark"] == "unknown" and not str(p[field].get("from")).startswith("Cleared"):
                    p[field] = _guessed(found["text"], found["src"], found["ref"], found.get("quote"))  # an unknown cell a person cleared stays cleared
            if it["steps"] and not p["steps"]:  # a redraft never rewrites steps a person has
                for st in it["steps"]:
                    agent_add_step(p, st["text"], st["src"], st["ref"], st.get("quote"))
            have = {b["card_id"] for b in p["breaks"]}
            for b in it["breaks"]:
                if b["card_id"] not in have:  # a redraft adds; it never rewrites a line a person wrote
                    p["breaks"].append({"id": _new_id("b"), "card_id": b["card_id"], "sealed_card": False,
                                        "text": _guessed(b["text"], f"Card: {_short(b['text'])}", {"kind": "card", "id": b["card_id"]})})
            people = _people_ids(plane)
            to, note = _answerer(people, [_v(p, "owner"), it["author"], *asked])
            lead = f"{note} " if note else ""
            if _v(p, "owner") is None:
                _ask(doc, p, "owner", to, f"{lead}Who owns the process '{_v(p, 'name')}'?")
            if _v(p, "trigger") is None:
                _ask(doc, p, "trigger", to, f"{lead}What starts '{_v(p, 'name')}'?")
            if not p["steps"]:
                _ask(doc, p, "steps", to, f"{lead}What are the steps of '{_v(p, 'name')}', in order? Lens does not guess steps.")
        for q in doc["questions"]:  # a question waiting for someone who cannot sign in goes to the next person who can
            people = _people_ids(plane)
            if q["state"] in ("open", "queued") and not _v(people.get(q["to_person"]) or {}, "account_id"):
                p = next((x for x in doc["processes"] if x["id"] == q["process_id"]), None)
                to, note = _answerer(people, [it["author"] for it in items if p and it["key"] == p.get("key")] + asked)
                if to:
                    q["to_person"], q["text"] = to, f"{note} {q['text']}" if note else q["text"]
        doc["drafted_at"], doc["drafted_from"] = _now(), seen
        _promote(plane, iid, doc)
        return {"new": made}

    out = _write(plane, iid, version, change)
    return {**out, **read_map(plane, iid, viewer)}


def _answerer(people: dict, candidates: list) -> tuple[str, str]:
    """Who a question goes to: the first of these people who has a sign-in, so it can be answered. Never someone who cannot sign in.
    The note names the first candidate who could not be asked, so the person who gets it knows whom to ask."""
    first = next((c for c in candidates if c and c in people), None)
    for c in candidates:
        if c and c in people and _v(people[c], "account_id"):
            skipped = _v(people[first], "name") if first and first != c else None
            return c, f"{skipped} has no sign-in here, so please ask them." if skipped else ""
    return "", ""


def _organiser_person(plane, rec: dict) -> list[str]:
    toks = _tokens((rec.get("people") or {}).get("organiser"))
    people = store.raw(plane)["people"]
    return [pid for pid, p in people.items() if toks & {view.norm(pid), view.norm(_v(p, "name") or ""), view.norm(_v(p, "account_id") or "")}] or sorted(toks)


# ---- edits -------------------------------------------------------------------------------------------------------------------------

def _find(doc: dict, pid: str, live: bool = True) -> dict:
    p = next((x for x in doc["processes"] if x["id"] == pid), None)
    if p is None or (live and p["status"] == "removed"):
        raise Refusal(404, "We could not find that process.")
    return p


def _steps_hash(p: dict) -> str:
    rows = [[s["order"], _v(s, "name"), _v(s, "actor"), _v(s, "systems"), _v(s, "inputs"), _v(s, "outputs")] for s in p["steps"]]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _touched(p: dict, ctx: Ctx, kind: str, field: str | None = None, was: Any = None) -> None:
    """A person changed what the owner confirms (or drafted): status edited, confirmation cleared and kept in history."""
    if p["confirmed"]:
        p["history"].append({"by": ctx.name, "at": _now(), "kind": "confirmation_cleared", "field": field, "was": p["confirmed"]})
        p["confirmed"] = None
    p["status"] = "edited"
    _history(p, ctx, kind, field, was)


def _need_edit(ctx: Ctx) -> None:
    if not ctx.can_edit:
        raise Refusal(403, "You can read this map but not change it.")


def _people_ids(plane) -> dict:
    return store.raw(plane)["people"]


def _set_field(p: dict, ctx: Ctx, field: str, value: Any, people: dict) -> None:
    if field not in FIELDS:
        raise Refusal(422, "That field cannot be edited.")
    if field in LIST_FIELDS:
        value = [str(x).strip() for x in (value if isinstance(value, list) else [value]) if str(x).strip()] or None
    else:
        value = str(value or "").strip() or None
    if field == "name" and not value:
        raise Refusal(422, "Name this process.")
    if field == "owner" and value and value not in people:
        raise Refusal(422, "Pick a person from the company profile.")
    was = _v(p, field)
    if was == value:
        return
    src = f"Edited by {ctx.name}" if p[field]["mark"] != "unknown" else f"Added by {ctx.name}"
    p[field] = _stated(value, ctx, src) if value is not None else _cell(None, "unknown", ctx.name or "A team member", f"Cleared by {ctx.name}")
    _touched(p, ctx, "edited", field, was)


def _step(doc_p: dict, step_id: str) -> dict:
    s = next((x for x in doc_p["steps"] if x["id"] == step_id), None)
    if s is None:
        raise Refusal(404, "We could not find that step.")
    return s


def _renumber(p: dict) -> None:
    for i, s in enumerate(p["steps"], 1):
        s["order"] = i


def new_step(name: str, ctx: Ctx, src: str | None = None, agent_ref: dict | None = None, actor: str | None = None) -> dict:
    """A step. Lens may write one only with a `from` and a `ref` on its cell (no invented step); a person needs only their name."""
    if not str(name or "").strip():
        raise Refusal(422, "Name the step.")
    return {"id": _new_id("s"), "order": 0,
            "name": _stated(name.strip(), ctx, src or f"Added by {ctx.name}") if agent_ref is None else _guessed(name.strip(), src or "", agent_ref),
            "actor": _stated(actor, ctx, f"Added by {ctx.name}") if actor else _unknown(ctx.name or "A team member", None),
            "systems": _unknown(ctx.name or "A team member", None), "inputs": _unknown(ctx.name or "A team member", None),
            "outputs": _unknown(ctx.name or "A team member", None), "produces": [], "uses": [], "sources": []}


def agent_add_step(p: dict, name: str, src: str, ref: dict, quote: str | None = None) -> None:
    """The server check for an agent write to `steps` (spec rule): refused without a plain `from` and a machine `ref`."""
    if not str(src or "").strip() or not ref or not ref.get("id"):
        raise Refusal(422, "A step Lens writes needs the source it came from.")
    p["steps"].append({**new_step("x", Ctx(view.Viewer("Lens", frozenset()), "", "write", False)), "name": _guessed(name, src, ref, quote)})
    _renumber(p)


def _apply(plane, doc: dict, p: dict, ctx: Ctx, ch: dict) -> list[dict]:
    """One change to one process. Returns other processes it created or removed (split, merge)."""
    op = ch.get("op")
    people = _people_ids(plane)
    if op == "set":
        _set_field(p, ctx, str(ch.get("field")), ch.get("value"), people)
    elif op == "add_step":
        s = new_step(str(ch.get("name") or ""), ctx, actor=ch.get("actor"))
        after = next((i for i, x in enumerate(p["steps"]) if x["id"] == ch.get("after")), len(p["steps"]) - 1)
        p["steps"].insert(after + 1, s)
        _renumber(p)
        _touched(p, ctx, "step_added", "steps")
    elif op == "edit_step":
        s, f = _step(p, str(ch.get("step_id"))), str(ch.get("field"))
        if f not in STEP_FIELDS:
            raise Refusal(422, "That field cannot be edited.")
        v = ch.get("value")
        v = ([str(x).strip() for x in (v if isinstance(v, list) else [v]) if str(x).strip()] or None) if f in LIST_FIELDS else (str(v or "").strip() or None)
        if f == "name" and not v:
            raise Refusal(422, "Name the step.")
        was = _v(s, f)
        if was != v:
            s[f] = _stated(v, ctx, f"Edited by {ctx.name}") if v is not None else _unknown(ctx.name or "A team member", None)
            _touched(p, ctx, "step_edited", f"steps.{f}", was)
    elif op == "remove_step":
        s = _step(p, str(ch.get("step_id")))
        p["steps"].remove(s)
        _renumber(p)
        _touched(p, ctx, "step_removed", "steps", _v(s, "name"))
    elif op == "reorder":
        order = ch.get("order") or []
        if sorted(order) != sorted(s["id"] for s in p["steps"]):
            raise Refusal(422, "The order must list every step once.")
        p["steps"].sort(key=lambda s: order.index(s["id"]))
        _renumber(p)
        _touched(p, ctx, "steps_reordered", "steps")
    elif op == "split":
        i = next((k for k, s in enumerate(p["steps"]) if s["id"] == ch.get("after_step")), None)
        if i is None or i >= len(p["steps"]) - 1:
            raise Refusal(422, "Split after a step that has another step after it.")
        twin = _new_process(p["cluster"], ctx, "edited")
        twin["history"] = [dict(h) for h in p["history"]]
        twin["owner"] = p["owner"]
        twin["name"] = _stated(f"{_v(p, 'name')} (second part)", ctx, f"Split from '{_v(p, 'name')}' by {ctx.name}")
        twin["steps"], p["steps"] = p["steps"][i + 1:], p["steps"][: i + 1]
        _renumber(p), _renumber(twin)
        doc["processes"].append(twin)
        _touched(p, ctx, "split", "steps"), _touched(twin, ctx, "split", "steps")
        return [twin]
    elif op == "merge":
        other = _find(doc, str(ch.get("with")))
        if other is p:
            raise Refusal(422, "Pick another process to merge with.")
        p["steps"] += other["steps"]
        p["breaks"] += other["breaks"]
        _renumber(p)
        other["steps"], other["breaks"] = [], []
        other["status"], other["confirmed"] = "removed", None
        other["removed"] = {"by": ctx.name, "at": _now(), "reason": f"Merged into '{_v(p, 'name')}'"}
        _history(other, ctx, "merged_into", "steps"), _touched(p, ctx, "merged", "steps")
        return [other]
    elif op == "link":
        s, kind, ident = _step(p, str(ch.get("step_id"))), str(ch.get("kind")), str(ch.get("id") or "").strip()
        if kind not in ("produces", "uses", "sources") or not _ID.fullmatch(ident):
            raise Refusal(422, "Pick a measure or a data source to link.")
        if ch.get("remove"):
            s[kind] = [x for x in s[kind] if x != ident]
        elif ident not in s[kind]:
            s[kind].append(ident)
        _history(p, ctx, "link_removed" if ch.get("remove") else "linked", f"steps.{kind}")  # links never clear a confirmation
    elif op == "ask":
        topic = str(ch.get("topic") or "")
        if topic not in ("owner", "trigger", "steps"):
            raise Refusal(422, "Lens can ask about the owner, the trigger or the steps.")
        people = _people_ids(plane)
        to, note = _answerer(people, [_v(p, "owner"), *_organiser_person(plane, ch["rec"])])
        if not to:
            raise Refusal(422, "Nobody who can sign in is named for this process yet.")
        what = {"owner": "Who owns", "trigger": "What starts", "steps": "What are the steps of"}[topic]
        _ask(doc, p, topic, to, f"{note + ' ' if note else ''}{what} '{_v(p, 'name')}'{', in order' if topic == 'steps' else ''}?")
        _history(p, ctx, "asked", topic)
    elif op == "add_break":
        p["breaks"].append(_break(plane, ctx, ch))
        _history(p, ctx, "break_added", "breaks")
    elif op == "remove_break":
        b = next((x for x in p["breaks"] if x["id"] == ch.get("break_id")), None)
        if b is None:
            raise Refusal(404, "We could not find that line.")
        p["breaks"].remove(b)
        _history(p, ctx, "break_removed", "breaks")
    else:
        raise Refusal(422, "That change is not one this map knows.")
    return []


def _break(plane, ctx: Ctx, ch: dict) -> dict:
    """Where it breaks today: a wall card the viewer may read (a sealed one keeps no words), or the person's own words."""
    cid = ch.get("card_id")
    if not cid:
        text = str(ch.get("text") or "").strip()
        if not text:
            raise Refusal(422, "Write the line or pick a card.")
        return {"id": _new_id("b"), "card_id": None, "sealed_card": False, "text": _stated(text, ctx, f"In {ctx.name}'s words")}
    c = view.read(plane, ctx.viewer)["cards"].get(str(cid))
    if c is None:
        raise Refusal(404, "We could not find that card.")
    if "silhouette" in c:
        return {"id": _new_id("b"), "card_id": cid, "sealed_card": True, "text": _cell(None, "unknown", ctx.name or "A team member", "A sealed card")}
    words = str(_v(c, "q2") or _v(c, "q1") or _v(c, "topic") or "").strip()
    if not words:
        raise Refusal(422, "That card has no words to link.")
    return {"id": _new_id("b"), "card_id": cid, "sealed_card": _v(c, "sealed") is True,
            "text": _cell(words, "stated", ctx.name or "A team member", f"From card: '{_short(words)}'", {"kind": "card", "id": str(cid)})}


def patch(plane, iid: str, pid: str, viewer: view.Viewer, version: int, change: dict) -> dict:
    rec, ctx = _context(plane, iid, viewer)
    _need_edit(ctx)

    def work(doc: dict) -> dict:
        p = _find(doc, pid)
        also = _apply(plane, doc, p, ctx, {**change, "rec": rec} if change.get("op") == "ask" else change)
        return {"process": p, "also": also}

    out = _write(plane, iid, version, work)
    return {**out, "version": _load(plane, iid)["version"]}


def add_process(plane, iid: str, viewer: view.Viewer, version: int, body: dict) -> dict:
    _, ctx = _context(plane, iid, viewer)
    _need_edit(ctx)
    people = _people_ids(plane)

    def work(doc: dict) -> dict:
        p = _new_process(_slug(body.get("cluster")) if body.get("cluster") else UNSORTED, ctx, "edited")
        _history(p, ctx, "created", "name")
        for f in FIELDS:
            if body.get(f) not in (None, "", []):
                _set_field(p, ctx, f, body[f], people)
        if _v(p, "name") is None:
            raise Refusal(422, "Name this process.")
        doc["processes"].append(p)
        p["history"] = [h for h in p["history"] if h["kind"] == "created"] + [h for h in p["history"] if h["kind"] != "created"]
        return {"process": p}

    out = _write(plane, iid, version, work)
    return {**out, "version": _load(plane, iid)["version"]}


def remove(plane, iid: str, pid: str, viewer: view.Viewer, version: int, reason: str) -> dict:
    _, ctx = _context(plane, iid, viewer)
    _need_edit(ctx)
    if not str(reason or "").strip():
        raise Refusal(422, "Say why this process is removed.")

    def work(doc: dict) -> dict:
        p = _find(doc, pid)
        p["status"], p["confirmed"] = "removed", None
        p["removed"] = {"by": ctx.name, "at": _now(), "reason": reason.strip()}
        _history(p, ctx, "removed")
        return {"process": p}

    return _write(plane, iid, version, work)


def _is_owner(p: dict, ctx: Ctx) -> bool:
    o = view.norm(_v(p, "owner") or "")
    return bool(o) and bool(ctx.person) and o == ctx.person


def confirm(plane, iid: str, pid: str, viewer: view.Viewer, version: int) -> dict:
    _, ctx = _context(plane, iid, viewer)

    def work(doc: dict) -> dict:
        p = _find(doc, pid)
        if not _is_owner(p, ctx):
            who = _person_name(plane, _v(p, "owner"))
            raise Refusal(403, f"Only {who} can confirm this." if who else "This process has no owner yet, so nobody can confirm it.")
        p["confirmed"] = {"by": ctx.name, "at": _now(), "steps_hash": _steps_hash(p)}
        p["status"] = "confirmed"
        _history(p, ctx, "confirmed")
        return {"process": p}

    return _write(plane, iid, version, work)


def handover(plane, iid: str, pid: str, viewer: view.Viewer, version: int, to_person: str) -> dict:
    _, ctx = _context(plane, iid, viewer)
    if to_person not in _people_ids(plane):
        raise Refusal(422, "Pick a person from the company profile.")

    def work(doc: dict) -> dict:
        p = _find(doc, pid)
        if not _is_owner(p, ctx):
            raise Refusal(403, "Only the owner can pass a process on.")
        was = _v(p, "owner")
        p["owner"] = _stated(to_person, ctx, f"Passed on by {ctx.name}")
        _touched(p, ctx, "handed_over", "owner", was)
        return {"process": p}

    return _write(plane, iid, version, work)


def _person_name(plane, pid: str | None) -> str:
    return str(_v(store.raw(plane)["people"].get(pid or "", {}), "name") or "")


def answer(plane, iid: str, qid: str, viewer: view.Viewer, body: dict) -> dict:
    _, ctx = _context(plane, iid, viewer)
    text, why = str(body.get("answer") or "").strip(), str(body.get("dropped_reason") or "").strip()
    if bool(text) == bool(why):
        raise Refusal(422, "Write an answer, or say why you cannot answer.")

    def work(doc: dict) -> dict:
        q = next((x for x in doc["questions"] if x["id"] == qid), None)
        if q is None:
            raise Refusal(404, "We could not find that question.")
        if not ctx.person or view.norm(q["to_person"]) != ctx.person:
            raise Refusal(403, "Only the person asked can answer this question.")
        if q["state"] != "open":
            raise Refusal(409, "That question is not waiting for an answer.")
        p = _find(doc, q["process_id"], live=False)
        src = f"Answer from {ctx.name}"
        if why:
            q["state"], q["dropped_reason"] = "dropped", why
        else:
            q["state"], q["answer"] = "answered", _stated(text, ctx, src)
            ref = {"kind": "person", "id": ctx.person}
            if q["topic"] == "steps":  # Lens turns the answer into a proposal, guessed, source the answer; the words stay the person's
                agent_add_step(p, text, src, ref)
                _touched(p, ctx, "step_proposed", "steps")
            elif q["topic"] == "trigger":
                p["trigger"] = _stated(text, ctx, src)
                _touched(p, ctx, "edited", "trigger")
        q["answered_at"] = _now()
        _promote(plane, iid, doc)
        return {"question": q}

    version = body.get("version")
    return _write(plane, iid, _load(plane, iid)["version"] if version is None else int(version), work)


# ---- reading -----------------------------------------------------------------------------------------------------------------------

def map_state(doc: dict) -> str:
    live = [p for p in doc["processes"] if p["status"] != "removed"]
    if not live:
        return "Not drafted"
    done = sum(1 for p in live if p["confirmed"])
    return "Confirmed" if done == len(live) else "In confirmation" if done else "Drafted"


def counters(doc: dict) -> dict:
    live = [p for p in doc["processes"] if p["status"] != "removed"]
    qs = doc["questions"]
    steps = [s for p in live for s in p["steps"]]
    breaks = [b for p in live for b in p["breaks"]]
    measures = {m for s in steps for m in (*s["produces"], *s["uses"])}
    per: dict[str, int] = {}
    for p in live:
        per[p["cluster"]] = per.get(p["cluster"], 0) + 1
    return {"processes": len(live), "confirmed": sum(1 for p in live if p["confirmed"]),
            "guessed": sum(1 for p in live if p["status"] == "guessed"), "edited": sum(1 for p in live if p["status"] == "edited"),
            "steps": len(steps), "steps_unknown": sum(1 for q in qs if q["topic"] == "steps" and q["state"] in ("queued", "open")),
            "questions_open": sum(1 for q in qs if q["state"] == "open"), "questions_queued": sum(1 for q in qs if q["state"] == "queued"),
            "without_owner": sum(1 for p in live if _v(p, "owner") is None),
            "breaks_on_cards": sum(1 for b in breaks if b["card_id"]), "breaks_own_words": sum(1 for b in breaks if not b["card_id"]),
            "measures_linked": len(measures), "sources_linked": len({x for s in steps for x in s["sources"]}),
            "measures_without_process": None, "measures_note": "Not available yet. The catalogue has no measures.",
            "per_cluster": per, "state": map_state(doc)}


def outcome_counts(plane, iid: str) -> dict:
    """`outcome.processes` for the close route (01): {count, confirmed, state}."""
    doc = _load(plane, iid)
    c = counters(doc)
    return {"count": c["processes"], "confirmed": c["confirmed"], "state": c["state"]}


def _whole_cards(plane, viewer: view.Viewer) -> set[str]:
    return {k for k, c in view.read(plane, viewer)["cards"].items() if "silhouette" not in c}


def _cut_break(b: dict, whole: set[str]) -> dict:
    if b["sealed_card"] and b["card_id"] not in whole:
        return {**b, "text": _cell(None, "unknown", "Not shown", NO_WORDS), "hidden": NO_WORDS}
    return b


def _cut_process(p: dict, whole: set[str]) -> dict:
    return {**p, "breaks": [_cut_break(b, whole) for b in p["breaks"]]}


def _link_options(plane, iid: str, rec: dict, viewer: view.Viewer) -> dict:
    """What the step pickers offer: the measures of the intent's catalogue and its data sources, as {id, label}. None while the intent has no baseline."""
    ids = (rec.get("refs") or {}).get("baseline_ids") or []
    out: dict = {"measures": None, "sources": None}
    if not ids:
        return out
    from sh_platform.intents import catalogue as cat, sources as src  # late: both import this package
    try:
        rows = cat.catalogue_view(plane, str(ids[-1]), cat.C.Viewer(viewer.name, viewer.roles, viewer.shared_name, viewer.account_id)).get("rows", [])
        out["measures"] = [{"id": r["code"], "label": r.get("label") or r["code"]} for r in rows if r.get("code")]
    except Exception:  # a picker that cannot load reads "Not available yet"; the map still opens
        log.warning("process map: catalogue picker unavailable", exc_info=True)
    try:
        out["sources"] = [{"id": r["id"], "label": r.get("name") or r["id"]} for r in src.list_sources(plane, iid, viewer) if not r.get("restricted")]
    except Exception:
        log.warning("process map: data source picker unavailable", exc_info=True)
    return out


def read_map(plane, iid: str, viewer: view.Viewer) -> dict:
    rec, ctx = _context(plane, iid, viewer)
    doc = _load(plane, iid)
    c = counters(doc)
    base = {"intent_id": iid, "version": doc["version"], "state": c["state"], "tier": ctx.tier}
    if ctx.tier == "counts":
        return {**base, "summary": f"Process map: {c['processes']} processes, {c['confirmed']} confirmed", "counters": {"processes": c["processes"], "confirmed": c["confirmed"]}}
    prof, cards = _wall_cards(plane, rec, viewer)
    whole = _whole_cards(plane, viewer)
    own = ctx.tier == "own"
    procs = [_cut_process(p, whole) for p in doc["processes"] if not own or _is_owner(p, ctx)]
    qs = [q for q in doc["questions"] if not own or view.norm(q["to_person"]) == ctx.person]
    cl = clusters(cards)
    known = {x["id"] for x in cl}
    cl += [{"id": p["cluster"], "name": p["cluster"].replace("-", " ").capitalize() if p["cluster"] != UNSORTED else "No cluster yet", "cards": 0}
           for p in {p["cluster"]: p for p in procs}.values() if p["cluster"] not in known]
    people = {pid: {"name": _v(p, "name"), "role": _v(p, "role")} for pid, p in prof["people"].items() if _v(p, "name")}
    return {**base, "drafted_at": doc["drafted_at"], "drafted_from": doc["drafted_from"], "processes": procs, "questions": qs,
            "clusters": cl, "people": people, "systems": {k: _v(s, "name") for k, s in prof["systems"].items() if _v(s, "name")},
            "counters": c, "budget": question_budget(plane, iid, ctx.person) if ctx.person else None,
            "me": {"person": ctx.person, "name": ctx.name, "can_edit": ctx.can_edit, "can_draft": ctx.can_draft,
                   "cards": {k: (_v(x, "topic") or _v(x, "q1") or "") for k, x in cards.items() if "silhouette" not in x} if ctx.can_edit else {},
                   "owns": [p["id"] for p in doc["processes"] if _is_owner(p, ctx) and p["status"] != "removed"]},
            "link_options": _link_options(plane, iid, rec, viewer) if ctx.can_edit else {"measures": None, "sources": None},
            "draft_blocked": None if cl else "Form clusters first. Lens drafts processes from them."}


def charter_page(plane, iid: str, viewer: view.Viewer) -> dict:
    """The "Processes involved" page: every process shown; a guessed or edited one carries "Not yet confirmed by its owner"."""
    rec, ctx = _context(plane, iid, viewer)
    if ctx.tier == "counts" and rec.get("state") != "closed":
        raise Refusal(403, "The charter page opens once the intent is closed.")
    doc = _load(plane, iid)
    whole = _whole_cards(plane, viewer)
    groups: dict[str, list] = {}
    for p in doc["processes"]:
        if p["status"] == "removed":
            continue
        who = _person_name(plane, _v(p, "owner"))
        c = p["confirmed"]
        groups.setdefault(p["cluster"], []).append({
            "id": p["id"], "name": _v(p, "name"), "owner": who or None, "status": p["status"], "confirmed": bool(c),
            "label": f"Confirmed by {c['by']}, {c['at'][:10]}" if c else "Not yet confirmed by its owner",
            "trigger": _v(p, "trigger"), "frequency": _v(p, "frequency"), "steps": [_v(s, "name") for s in p["steps"]],
            "systems": _v(p, "systems") or [], "breaks": [b.get("hidden") or _v(b, "text") for b in (_cut_break(b, whole) for b in p["breaks"])]})
    c = counters(doc)
    return {"title": "Processes involved", "state": c["state"], "counts": {"processes": c["processes"], "confirmed": c["confirmed"]},
            "groups": [{"cluster": k, "processes": v} for k, v in groups.items()],
            "empty": "No process is mapped for this initiative yet." if not groups else None}


def pulse_lines(plane, viewer: view.Viewer) -> list[dict]:
    """Pulse (spec 27, Nira): "Confirm the process ..." for the owner and "You have n questions about a process" for the person asked.
    Only live Initiatives (not draft, closed or cancelled) that already have a process file are opened; a person sees their own lines only."""
    if "super_admin" in viewer.roles or not viewer.account_id:
        return []
    from sh_platform.intents import store as istore
    from sh_platform.pulse.lines import line
    person = _person_id(store.raw(plane)["people"], viewer)
    if not person:
        return []
    out = []
    for row in istore.read_index(plane):
        if row.get("state") in ("draft", "closed", "cancelled") or row.get("type") != "initiative":
            continue
        try:
            if not _path(plane, row["id"], "processes.json").exists():
                continue
            doc = _load(plane, row["id"])
        except Refusal:
            continue
        base = f"/centre/intent/{row['id']}/define?tab=process-map"
        for p in doc.get("processes") or []:
            if p["status"] != "removed" and not p["confirmed"] and _v(p, "owner") == person and _v(p, "name"):
                out.append(line(f"process-confirm:{row['id']}:{p['id']}", "decision", f"Confirm the process '{_v(p, 'name')}'",
                                f"{row.get('title') or 'An initiative'} asks you to confirm it.", f"{base}&process={p['id']}", "Open it",
                                f"intents/{row['id']}/processes.json", doc.get("drafted_at")))
        n = sum(1 for q in doc.get("questions") or [] if q["state"] == "open" and view.norm(q["to_person"]) == person)
        if n:
            out.append(line(f"process-questions:{row['id']}", "request", f"You have {n} question{'s' if n != 1 else ''} about a process",
                            row.get("title") or "An initiative", base, "Answer", f"intents/{row['id']}/processes.json", doc.get("drafted_at")))
    return out


# ---- routes ------------------------------------------------------------------------------------------------------------------------

class Versioned(BaseModel):
    version: int


class NewProcess(Versioned):
    name: str
    cluster: str | None = None
    owner: str | None = None
    trigger: str | None = None
    frequency: str | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None


class Change(Versioned):
    change: dict


class Removal(Versioned):
    reason: str


class Handover(Versioned):
    to_person: str


class Answer(BaseModel):
    version: int | None = None
    answer: str | None = None
    dropped_reason: str | None = None


def _go(fn):
    try:
        return fn()
    except Refusal as e:
        err = {"error": "not_allowed"} if e.status == 403 else {}
        return JSONResponse({**err, "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


@router.get("/api/intents/{intent_id}/processes")
def get_intents_by_intent_id_processes(intent_id: str, request: Request):
    return _go(lambda: read_map(_plane(request), intent_id, _viewer(request)))


@router.post("/api/intents/{intent_id}/processes")
def post_intents_by_intent_id_processes(intent_id: str, body: NewProcess, request: Request):
    return _go(lambda: add_process(_plane(request), intent_id, _viewer(request), body.version, body.model_dump(exclude={"version"})))


@router.post("/api/intents/{intent_id}/processes/draft")
def post_intents_by_intent_id_processes_draft(intent_id: str, body: Versioned, request: Request):
    from sh_platform.intents import lens  # late: lens imports this package
    plane = _plane(request)
    return _go(lambda: draft(plane, intent_id, _viewer(request), body.version, lens.runtime_for_request(request, plane)))


@router.get("/api/intents/{intent_id}/processes/charter-page")
def get_intents_by_intent_id_processes_charter_page(intent_id: str, request: Request):
    return _go(lambda: charter_page(_plane(request), intent_id, _viewer(request)))


@router.patch("/api/intents/{intent_id}/processes/{process_id}")
def patch_intents_by_intent_id_processes_by_process_id(intent_id: str, process_id: str, body: Change, request: Request):
    return _go(lambda: patch(_plane(request), intent_id, process_id, _viewer(request), body.version, body.change))


@router.delete("/api/intents/{intent_id}/processes/{process_id}")
def delete_intents_by_intent_id_processes_by_process_id(intent_id: str, process_id: str, body: Removal, request: Request):
    return _go(lambda: remove(_plane(request), intent_id, process_id, _viewer(request), body.version, body.reason))


@router.post("/api/intents/{intent_id}/processes/{process_id}/confirm")
def post_intents_by_intent_id_processes_by_process_id_confirm(intent_id: str, process_id: str, body: Versioned, request: Request):
    return _go(lambda: confirm(_plane(request), intent_id, process_id, _viewer(request), body.version))


@router.post("/api/intents/{intent_id}/processes/{process_id}/handover")
def post_intents_by_intent_id_processes_by_process_id_handover(intent_id: str, process_id: str, body: Handover, request: Request):
    return _go(lambda: handover(_plane(request), intent_id, process_id, _viewer(request), body.version, body.to_person))


@router.post("/api/intents/{intent_id}/process-questions/{question_id}/answer")
def post_intents_by_intent_id_process_questions_by_question_id_answer(intent_id: str, question_id: str, body: Answer, request: Request):
    return _go(lambda: answer(_plane(request), intent_id, question_id, _viewer(request), body.model_dump()))
