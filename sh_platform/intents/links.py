"""IC v2 (20): linking intents. One link is kept on both records (`links` plus the link log) and as events in each `events.jsonl`.

Other cards call `link_intents(plane, from_id, to_id, kind)` (closure next rows, converge, check-in fates, problem, decision).
`chain(plane, viewer, id)` walks `links.from` up and `links.to` down with a visited set, capped at MAX_STEPS.
"""
import hashlib
from datetime import datetime
import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.graph import intent_nodes  # noqa: F401  puts Intent nodes on the map at every rebuild
from sh_platform.graph.hooks import mark_dirty
from sh_platform.intents import _plane, _viewer
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.intents import events as EV  # B10's one events.jsonl writer
from sh_platform.jsonfile import read_json_strict
from sh_platform.profile import areas as areas_store
from sh_platform.profile import store as profile_store
from sh_platform.profile import view as pview

router = APIRouter()
log = logging.getLogger(__name__)

MAX_STEPS = 50  # the chain walk stops here whatever the records say
KINDS = ("initiative", "brainstorm", "pulse", "problem", "decision", "backlog", "build")
INTENT_KINDS = ("initiative", "brainstorm", "pulse", "problem", "decision")
FIRST_Q = {"initiative": "goal", "brainstorm": "statement", "pulse": None, "problem": "what", "decision": "question"}  # per-type start keys
CANCELLED_SOURCE = "This intent was cancelled. Start a new one instead."
NOT_YOURS = "Only the organiser or the sponsor can link this intent."
def log_of(rec: dict) -> list[dict]:
    """The link log (spec 20 `link_log`). Records written before it became a store key kept it under `links.log`; both are read."""
    return list(rec.get("link_log") or (rec.get("links") or {}).get("log") or [])


def _set_log(rec: dict, rows: list[dict]) -> None:
    rec["link_log"] = rows
    (rec.get("links") or {}).pop("log", None)  # moved to the top level, never kept twice


def link_id(from_id: str, to_id: str, kind: str) -> str:
    return "lnk-" + hashlib.sha1(f"{from_id}|{to_id}|{kind}".encode()).hexdigest()[:12]


def allowed(source_type: str) -> list[str]:
    """Kinds this type may lead to: `can_become` plus `can_create` of the catalogue, nothing else."""
    t = L.type_def(source_type)
    return list(dict.fromkeys([*(t.get("can_become") or []), *(t.get("can_create") or [])]))


def _who(viewer: pview.Viewer | None) -> dict:
    return {"account": viewer.account_id, "name": viewer.name, "role": ""} if viewer else {"account": None, "name": "North", "role": ""}


def note_event(plane, intent_id: str, kind: str, viewer: pview.Viewer | None, other: str | None, detail: dict) -> None:
    """One act line after the record is written. Never raises: a missing line must not undo the link (the log entry holds it)."""
    EV.try_append(plane, intent_id, kind, _who(viewer) if viewer else "north", {"store": "intents", "id": other} if other else None, detail, "act")


def may_link(rec: dict, viewer: pview.Viewer) -> bool:
    p = rec.get("people") or {}
    return S._named(p.get("organiser"), viewer) or S._named(p.get("sponsor"), viewer)


# ---- the one write -----------------------------------------------------------------------------------------------------------

def link_intents(plane, from_id: str, to_id: str, kind: str, *, by: pview.Viewer | None = None, item: dict | None = None,
                 proposed_by: str = "person", reason: str | None = None) -> str:
    """Write the link on the source, then on the target (an intent; a backlog item or a Build ref has no record of its own here),
    append `link_created` to both events files and mark the graph dirty. Idempotent: the same three always give the same link id,
    so calling it again repairs a half-written link. Raises LookupError for a missing source, ValueError for a kind not allowed."""
    if kind not in KINDS:
        raise ValueError(kind)
    lid, who, at = link_id(from_id, to_id, kind), _who(by), S.now_iso()
    hidden, written = bool(item and item.get("hidden")), []
    source_item = {"kind": item.get("kind"), "id": item.get("id"), "hidden": hidden} if item else None
    with S.locked(plane):
        src = S.read_intent(plane, from_id)
        if src is None:
            raise LookupError(from_id)
        tgt = S.read_intent(plane, to_id) if kind in INTENT_KINDS else None
        row = {"link_id": lid, "kind": kind, "source_item": source_item, "created_by": who["name"], "created_at": at,
               "proposed_by": proposed_by, "reason": reason}
        for rec, dir_, other, other_type in ((src, "to", tgt or {"id": to_id, "title": item.get("title", "") if item else ""}, kind),
                                             (tgt, "from", src, src["type"])):
            if rec is None:
                continue
            rows = log_of(rec)
            if any(r["link_id"] == lid and r["dir"] == dir_ for r in rows):
                continue
            rec.setdefault("links", {"from": None, "to": [], "build": None})
            if dir_ == "to":
                if kind == "build":
                    rec["links"]["build"] = to_id
                elif kind != "backlog" and to_id not in rec["links"]["to"]:
                    rec["links"]["to"].append(to_id)
                for n in (rec.get("closure") or {}).get("next") or []:  # the closure row this link answers keeps its ref
                    if n.get("kind") == kind and not n.get("ref"):
                        n["ref"] = to_id
                        break
            else:
                rec["links"]["from"] = from_id
            _set_log(rec, [*rows, {**row, "dir": dir_, "other": {"type": other_type, "id": other.get("id"),
                                                                 "title_at_link": other.get("title", "")}}])
            S.write_intent(plane, rec)
            written.append((rec["id"], dir_, other.get("id")))
    for iid, dir_, other in written:
        note_event(plane, iid, "link_created", by, other, {"link_id": lid, "dir": dir_, "kind": kind})
    mark_dirty(plane)
    return lid


def record_event(plane, intent_id: str, lid: str, event: str, by: pview.Viewer | None = None) -> None:
    """One link event on one intent (target_opened, target_closed, source_cancelled, target_cancelled, source_checked, ...)."""
    if S.read_intent(plane, intent_id) is None:
        raise LookupError(intent_id)
    note_event(plane, intent_id, event, by, None, {"link_id": lid})


def on_cancel(plane, intent_id: str, by: pview.Viewer | None = None) -> None:
    """Call after an intent is cancelled: only direct neighbours get an event, nothing cascades."""
    rec = S.read_intent(plane, intent_id)
    for r in log_of(rec or {}):
        other = (r.get("other") or {}).get("id")
        if r["dir"] == "to" and r["kind"] in INTENT_KINDS and other:
            record_event(plane, other, r["link_id"], "source_cancelled", by)
        elif r["dir"] == "from" and other:
            record_event(plane, other, r["link_id"], "target_cancelled", by)
    mark_dirty(plane)


def sync_cancel(plane, rec: dict) -> None:
    """Spec 20: a cancel puts `source_cancelled` or `target_cancelled` on each direct neighbour, once per link id. The cancel route
    (records.py) does not call on_cancel, so the chain read writes the missing lines, signed by the person who cancelled."""
    if rec.get("state") != "cancelled":
        return
    c, p = rec.get("closure") or {}, rec.get("people") or {}
    named = [p.get(s) for s in S.SLOTS] + [x for k in S.LISTS for x in p.get(k) or []]
    who = next(({"account": x["account_id"], "name": x["name"], "role": ""} for x in named
                 if isinstance(x, dict) and x.get("account_id") and x["account_id"] == c.get("closed_by") and x.get("name")), None)
    if who is None:
        return
    for r in log_of(rec):
        other = (r.get("other") or {}).get("id")
        if not other or r["kind"] in ("backlog", "build"):
            continue
        kind = "source_cancelled" if r["dir"] == "to" else "target_cancelled"
        if any(e.get("kind") == kind and (e.get("detail") or {}).get("link_id") == r["link_id"] for e in EV.read_events(plane, other)):
            continue
        EV.try_append(plane, other, kind, who, {"store": "intents", "id": rec["id"]}, {"link_id": r["link_id"]}, "act")


# ---- North's proposal and pre-fill -------------------------------------------------------------------------------------------

def _text(v) -> str:
    if isinstance(v, dict):
        v = v.get("idea") or v.get("text") or v.get("option") or ""
    return " ".join(str(v or "").split())


def source_text(src: dict, item_text: str | None) -> str:
    """What the new intent's first question is filled from: the item, else the source's outcome (spec 20 pre-fill table)."""
    if item_text:
        return item_text
    o, c = src.get("outcome") or {}, src.get("closure") or {}
    got = {"brainstorm": _text(o.get("chosen")), "problem": _text(o.get("what")), "decision": _text(o.get("chosen"))}.get(src["type"], "")
    # no chosen idea or option recorded: file 22 offers the source's closing words as the draft goal
    return got or (_text(c.get("what_came_out") or c.get("summary")) if src.get("state") == "closed" else "")


def title_from(text: str) -> str:
    """First 80 characters, cut back to a whole word."""
    if len(text) <= 80:
        return text
    cut = text[:80]
    return cut[:cut.rfind(" ")] if " " in cut else cut


def area_ids(plane) -> dict:
    """Area name (normalised) to area id, from the profile's areas section (05): the start screens' area pickers hold ids."""
    try:
        return {pview.norm(a["name"]): a["id"] for a in areas_store.listing(profile_store.load(plane)) if a.get("name")}
    except (OSError, ValueError, KeyError):
        return {}


def prefill(src: dict, to_kind: str, item_text: str | None = None, item_id: str | None = None, area_ids: dict | None = None,
            why: str | None = None) -> dict:
    """start_answers for the new draft, in the keys and shapes each start screen reads (22: `goal` and `areas` cells; 35: `statement`
    and `areas`; 41: `what` and `areas`; 43: `question` and `areas`). The first question from the item or outcome, the areas from the
    source (as area ids where the screen picks ids). A question with no source field is left out. Never for a private item.
    `prefilled` names, per key, where North copied it from (20 `prefilled_from`); a person's edit of the answer replaces the cell."""
    if to_kind not in FIRST_Q or not FIRST_Q[to_kind] and not src.get("areas"):
        return {}
    why = why or ("copied from the chosen idea" if src["type"] == "brainstorm" and not item_text and (src.get("outcome") or {}).get("chosen")
                  else "copied from the source")
    origin = {"intent_id": src["id"], "item_id": item_id, "why": why}
    text, first, out = source_text(src, item_text), FIRST_Q[to_kind], {}
    areas = list(src.get("areas") or [])
    if to_kind in ("initiative", "brainstorm") and area_ids:
        areas = [area_ids.get(pview.norm(a), a) for a in areas]
    if to_kind == "initiative":  # file 22 cells; North's copy is guessed until the person says it is right
        cell = lambda v: {"value": v, "mark": "guessed", "by": "North", "from": f"From {src.get('title') or 'the source'}",  # noqa: E731
                          "at": S.now_iso(), "prefilled_from": origin}
        if text:
            out["goal"] = cell({"line": text[:140], "why": ""})
        if areas:
            out["areas"] = cell(areas)
    else:
        if text and first:
            out[first] = text
        if areas:
            out["areas"] = areas
    if out:
        out["prefilled"] = {k: origin for k in out}
    return out


def resolve_item(plane, src: dict, item: dict | None) -> dict | None:
    """A check-in item is read from its week file (text, anonymous). Other items carry their kind, id and the text the screen shows."""
    if not item:
        return None
    out = {k: item.get(k) for k in ("kind", "id", "text", "week_key", "hidden")}
    if item.get("kind") == "checkin_item" and re.fullmatch(r"[0-9A-Za-z-]{1,20}", str(item.get("week_key") or "")):
        try:
            week = read_json_strict(plane.path("intents", src["id"], "weeks", f"{item['week_key']}.json"), dict) or {}
        except (OSError, ValueError):
            week = {}
        found = next((i for i in week.get("items") or [] if i.get("id") == item.get("id")), None)
        if found:
            out.update(text=found.get("text") or "", hidden=found.get("by") == "anonymous", item_kind=found.get("kind"))
    if out.get("hidden"):
        out["text"] = None
    return out


def propose(src: dict, item: dict | None) -> list[dict]:
    """The menu rows, North's pick first. Rules from records only (spec 20, Agent behaviour)."""
    kinds = allowed(src["type"])
    pick = None
    if src["type"] == "pulse" and item and item.get("item_kind") == "broke":
        pick, why = "problem", "It was reported as something that broke."
    elif src["type"] == "brainstorm" and (src.get("outcome") or {}).get("chosen"):
        pick, why = "initiative", "An idea was chosen in the session."
    elif src["type"] == "brainstorm" and src["state"] == "closed" and (src.get("closure") or {}).get("what_came_out"):
        pick, why = "initiative", "The brainstorm closed with something to carry out."
    elif src["type"] == "problem" and src["state"] == "closed":
        pick, why = "initiative", "The problem closed as bigger than a fix."
    elif src["type"] == "initiative" and item:
        pick, why = "decision", "An open choice was found while defining."
    rows = [{"kind": k, "why": why if k == pick else "", "suggested": k == pick} for k in kinds]
    return sorted(rows, key=lambda r: not r["suggested"])


# ---- creating the target -----------------------------------------------------------------------------------------------------

class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def create(plane, viewer: pview.Viewer, from_id: str, body: dict) -> dict:
    """The "Create draft" press: a draft only its creator sees, a backlog item, or the Build hand-off; then both link entries."""
    src = S.read_intent(plane, from_id)
    if src is None or S.tier_of(src, viewer, S.areas_of(plane, viewer)) is None:
        raise Refused(404, S.NOT_FOUND)
    if not may_link(src, viewer):
        raise Refused(403, NOT_YOURS)
    if src["state"] == "cancelled":
        raise Refused(409, CANCELLED_SOURCE)
    if body.get("version") != src["version"]:
        raise Refused(409, S.CONFLICT)
    kind = body.get("to_kind")
    if kind not in allowed(src["type"]):
        raise Refused(422, "This intent cannot lead to that kind.")
    item = resolve_item(plane, src, body.get("item"))
    if item and item.get("id"):
        for r in log_of(src):
            if r["dir"] == "to" and r["kind"] == kind and (r.get("source_item") or {}).get("id") == item["id"]:
                raise Refused(409, f"This item already led to {r['other'].get('title_at_link') or 'another intent'}.")
    carry = body.get("carry") or {}
    areas = [a for a in carry.get("areas", src.get("areas") or []) if isinstance(a, str) and a.strip()]
    title = " ".join(str(body.get("title") or "").split()) or title_from(source_text(src, (item or {}).get("text")) or "")
    if not title:
        raise Refused(400, "Give the new intent a title.")
    me = L.person(viewer.account_id, viewer.name)
    if kind == "backlog":
        from sh_platform.intents import backlog as B
        reason = " ".join(str(body.get("reason") or "").split())
        if not reason:
            raise Refused(400, "Add the reason")
        it = B.create_item(plane, title=title, kind="ops_problem" if src["type"] == "pulse" else "idea", area=(areas or [None])[0],
                           source={"intent_id": src["id"], "type": src["type"], "stage_ref": None,
                                   "week_key": (item or {}).get("week_key"), "week_item_id": (item or {}).get("id")},
                           raised_by=viewer.account_id or "anonymous", why=reason, quote=(item or {}).get("text") or "")
        lid = link_intents(plane, from_id, it["id"], "backlog", by=viewer, item={**(item or {}), "title": title}, reason=reason)
        return {"link_id": lid, "target": {"kind": "backlog", "id": it["id"]}}
    if kind == "build":
        if not (src.get("outcome") or {}).get("build_ready"):
            raise Refused(409, "Build cannot pick this up yet. North lists what is missing.")
        ref = f"handoff:{src['id']}"
        lid = link_intents(plane, from_id, ref, "build", by=viewer, reason=str(body.get("note") or "")[:500] or None)
        return {"link_id": lid, "target": {"kind": "build", "id": ref}}
    if not areas:
        raise Refused(400, "The source has no areas.")
    rec = L.new_record(kind, src.get("company") or "", me, S.now_iso(), title=title, purpose=src.get("purpose") or "", areas=areas,
                       link_from=from_id)
    answers = prefill(src, kind, (item or {}).get("text"), (item or {}).get("id"), area_ids(plane))
    for k, v in (body.get("start_answers") or {}).items():  # what the person changed in the panel is theirs: stated, no longer pre-filled
        if k in (FIRST_Q[kind], "areas") and k:
            answers[k] = {"value": v, "mark": "stated", "by": viewer.name, "from": "", "at": S.now_iso()} if kind == "initiative" else v
            answers.get("prefilled", {}).pop(k, None)
    rec["start_answers"] = answers
    names = {pview.norm(n) for n in carry.get("people") or [] if isinstance(n, str)}
    rec["links"]["suggested_people"] = [{"name": n, "from_intent": from_id} for n in people_names(src) if pview.norm(n) in names]
    S.create_intent(plane, rec)
    lid = link_intents(plane, from_id, rec["id"], kind, by=viewer, item=item, proposed_by=body.get("proposed_by") or "person")
    return {"link_id": lid, "target": {"kind": kind, "id": rec["id"]}}


def people_names(src: dict) -> list[str]:
    """Organiser, sponsor, owner, reporter, decider and participants by name (suggestions only; nobody is invited)."""
    p = src.get("people") or {}
    named = [p.get(s) for s in ("organiser", "sponsor", "owner", "reporter", "decider")] + list(p.get("participants") or [])
    return list(dict.fromkeys(x["name"] for x in named if isinstance(x, dict) and x.get("name")))


# ---- the chain ---------------------------------------------------------------------------------------------------------------

def _first_sentence(text: str, limit: int = 140) -> str:
    s = re.split(r"(?<=[.!?])\s", " ".join(str(text or "").split()), maxsplit=1)[0]
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


TYPE_WORD = {"initiative": "initiative", "brainstorm": "brainstorm", "pulse": "weekly check-in", "problem": "problem", "decision": "decision"}


def _short(iso) -> str:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return f"{d.day} {d.strftime('%b')}"
    except ValueError:
        return ""


def chain_sentence(steps: list[dict], build: dict | None = None) -> str:
    """One plain sentence for the chain. Sibling branches read as branches ("led to A and, separately, B"), never one line."""
    spine = [s for s in steps if s["dir"] in ("from", "self")]
    if len(steps) < 2 and not build:
        return "This intent has no links."
    by_parent: dict = {}
    for s in steps:
        if s["dir"] == "to" and s["type"] != "backlog":
            by_parent.setdefault(s["parent"], []).append(s)

    def clause(s: dict) -> str:
        d = _short(s.get("date"))
        out = f"the {TYPE_WORD.get(s['type'], s['type'])} '{s['title']}'" + (f" on {d}" if d else "")
        return out

    def kids(s: dict) -> list[dict]:
        if s["dir"] == "to":
            return by_parent.get(s["id"], [])
        i = spine.index(s)
        return [spine[i + 1]] if i + 1 < len(spine) else by_parent.get(s["id"], [])

    def walk(s: dict) -> str:
        k = kids(s)
        if not k:
            return clause(s)
        if len(k) == 1:
            return f"{clause(s)}, then {walk(k[0])}"
        parts = [walk(x) for x in k]
        return f"{clause(s)} led to {', '.join(parts[:-1])} and, separately, {parts[-1]}"

    b = _short((build or {}).get("at"))
    tail = f" It was handed to Build{f' on {b}' if b else ''}." if build else ""
    return f"This began as {walk(spine[0])}.{tail}"


def _step(rec: dict, tier: str, dir_: str, link: dict | None, parent: str | None) -> dict:
    c = rec.get("closure") or {}
    return {"id": rec["id"], "type": rec["type"], "title": rec.get("title", ""), "state": rec["state"],
            "date": c.get("closed_at") if rec["state"] in ("closed", "cancelled") else (rec.get("time_box") or {}).get("ends") or None,
            "organiser": ((rec.get("people") or {}).get("organiser") or {}).get("name"), "dir": dir_, "parent": parent, "tier": tier,
            "cancel_reason": c.get("cancel_reason") if rec["state"] == "cancelled" else None,
            "outcome_line": _first_sentence(c.get("what_came_out")) if rec["state"] == "closed" else "",
            "link": link and {"kind": link["kind"], "by": link.get("created_by"), "at": link.get("created_at"),
                              "proposed_by": link.get("proposed_by"), "item": None if (link.get("source_item") or {}).get("hidden") else link.get("source_item"),
                              "private_item": bool((link.get("source_item") or {}).get("hidden"))}}


def repair_to(plane, rec: dict) -> dict:
    """A child some other screen put in `links.to` without the link log (spec 20: North repairs on read, same link id, idempotent)."""
    logged = {(r.get("other") or {}).get("id") for r in log_of(rec) if r["dir"] == "to"}
    fixed = False
    for cid in (rec.get("links") or {}).get("to") or []:
        if cid in logged:
            continue
        try:
            child = S.read_intent(plane, cid)
        except S.Unreadable:
            continue
        if child and (child.get("links") or {}).get("from") == rec["id"]:
            link_intents(plane, rec["id"], cid, child["type"])
            fixed = True
    return S.read_intent(plane, rec["id"]) if fixed else rec


def chain(plane, viewer: pview.Viewer, intent_id: str) -> dict | None:
    """{chain, hidden, build, branches} at the viewer's tier, or None when the viewer may not see the intent. Unseen steps are not
    drawn; they count in `hidden`."""
    areas = S.areas_of(plane, viewer)
    me = S.read_intent(plane, intent_id)
    if me is None or S.tier_of(me, viewer, areas) is None:
        return None
    sync_cancel(plane, me)
    seen, hidden, steps = {intent_id}, 0, []

    def visible(rec):
        return rec and S.tier_of(rec, viewer, areas)

    up, cur = [], me
    while (cur.get("links") or {}).get("from") and len(seen) < MAX_STEPS:
        pid = cur["links"]["from"]
        if pid in seen:
            break
        seen.add(pid)
        try:
            parent = S.read_intent(plane, pid)
        except S.Unreadable:
            parent = None
        if parent is None:
            break
        sync_cancel(plane, parent)
        link = next((r for r in log_of(cur) if r["dir"] == "from"), None)
        tier = visible(parent)
        if tier:
            up.append((parent, tier, link))
        else:
            hidden += 1
        cur = parent
    steps += [_step(rec, tier, "from", None, None) for rec, tier, _ in reversed(up)]
    my_link = next((r for r in log_of(me) if r["dir"] == "from"), None)
    steps.append(_step(me, S.tier_of(me, viewer, areas), "self", my_link, (me.get("links") or {}).get("from")))

    queue = [me]
    from sh_platform.intents import backlog as B
    items = {i["id"]: i for i in B.read_items(plane)}
    while queue and len(seen) < MAX_STEPS:
        node = repair_to(plane, queue.pop(0))
        for r in log_of(node):
            if r["dir"] != "to" or len(seen) >= MAX_STEPS:
                continue
            oid = (r.get("other") or {}).get("id")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            if r["kind"] == "backlog":
                it = items.get(oid)
                if it and B.may_see(plane, viewer, it):
                    steps.append({"id": oid, "type": "backlog", "title": it["title"], "state": it["status"], "date": it.get("raised_at"),
                                  "organiser": None, "dir": "to", "parent": node["id"], "tier": "card", "cancel_reason": None,
                                  "outcome_line": "", "link": {"kind": "backlog", "by": r.get("created_by"), "at": r.get("created_at"),
                                                               "proposed_by": r.get("proposed_by"), "item": None, "private_item": False}})
                elif it:
                    hidden += 1
                continue
            if r["kind"] == "build":
                continue
            try:
                child = S.read_intent(plane, oid)
            except S.Unreadable:
                child = None
            if child is None:
                continue
            sync_cancel(plane, child)
            if (child.get("links") or {}).get("from") != node["id"]:  # half-written: repair from the source's entry
                link_intents(plane, node["id"], oid, r["kind"])
                child = S.read_intent(plane, oid)
            tier = visible(child)
            if tier:
                steps.append(_step(child, tier, "to", r, node["id"]))
                queue.append(child)
            elif child["state"] != "draft":  # someone else's draft is not even a hidden step (ruling 14)
                hidden += 1
    b = (me.get("links") or {}).get("build")
    blink = next((r for r in log_of(me) if r["kind"] == "build" and r["dir"] == "to"), None)
    build = {"ref": b, "at": (blink or {}).get("created_at"), "by": (blink or {}).get("created_by"), "blueprint": None} if b else None
    return {"chain": steps, "sentence": chain_sentence(steps, build), "hidden": hidden, "build": build, "branches": sum(1 for x in steps if x["dir"] == "to" and x["parent"] == intent_id),
            "capped": len(seen) >= MAX_STEPS, "may_link": me["state"] not in ("draft", "cancelled") and may_link(me, viewer),
            "me": viewer.name or ""}


# ---- routes ------------------------------------------------------------------------------------------------------------------

def _fail(e: Exception) -> JSONResponse:
    if isinstance(e, Refused):
        return JSONResponse({"message": e.message}, status_code=e.status)
    if isinstance(e, S.VersionConflict):
        return JSONResponse({"message": S.CONFLICT}, status_code=409)
    if isinstance(e, S.Unreadable):
        return JSONResponse({"message": S.UNREADABLE}, status_code=409)
    return JSONResponse({"message": "Not created. Nothing was changed."}, status_code=400)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.post("/api/intents/{intent_id}/links/proposal")
async def post_intents_by_intent_id_links_proposal(intent_id: str, request: Request):
    plane, viewer, body = _plane(request), _viewer(request), await _body(request)
    try:
        src = S.read_intent(plane, intent_id)
    except S.Unreadable as e:
        return _fail(e)
    if src is None or S.tier_of(src, viewer, S.areas_of(plane, viewer)) is None:
        return JSONResponse({"message": S.NOT_FOUND}, status_code=404)
    if not may_link(src, viewer):
        return JSONResponse({"message": NOT_YOURS}, status_code=403)
    if src["state"] == "cancelled":
        return JSONResponse({"message": CANCELLED_SOURCE}, status_code=409)
    item = resolve_item(plane, src, body.get("item"))
    kinds = propose(src, item)
    for k in kinds:  # "Already linked": one item, one link per kind
        hit = next((r for r in log_of(src) if r["dir"] == "to" and r["kind"] == k["kind"]
                    and (r.get("source_item") or {}).get("id") == (item or {}).get("id")), None)
        k["linked"] = {"id": hit["other"].get("id"), "title": hit["other"].get("title_at_link")} if hit else None
    pick = next((k["kind"] for k in kinds if k["suggested"]), kinds[0]["kind"] if kinds else None)
    if body.get("to_kind") in {k["kind"] for k in kinds}:  # the panel asks again when the person picks another kind
        pick = body["to_kind"]
    text = source_text(src, (item or {}).get("text"))
    answers = prefill(src, pick, (item or {}).get("text"), (item or {}).get("id"), area_ids(plane)) if pick else {}
    return {"kinds": kinds, "source": {"title": src.get("title", ""), "type": src["type"], "purpose": src.get("purpose", ""),
                                       "version": src["version"]},
            "draft": {"kind": pick, "title": title_from(text), "start_answers": [{"n": k, "answer": v, "why": answers["prefilled"][k]["why"]}
                                                       for k, v in answers.items() if k != "prefilled"],
                                      "people": people_names(src), "areas": src.get("areas") or [],
                                      "private_item": bool(item and item.get("hidden"))}}


@router.post("/api/intents/{intent_id}/links")
async def post_intents_by_intent_id_links(intent_id: str, request: Request):
    try:
        return JSONResponse(create(_plane(request), _viewer(request), intent_id, await _body(request)), status_code=201)
    except (Refused, S.VersionConflict, S.Unreadable, ValueError) as e:
        return _fail(e)


@router.post("/api/intents/{intent_id}/next")
async def post_intents_by_intent_id_next(intent_id: str, request: Request):
    """After "Close intent": create each confirmed next row that has no ref yet (initiative, problem, decision, backlog)."""
    plane, viewer = _plane(request), _viewer(request)
    try:
        src = S.read_intent(plane, intent_id)
        if src is not None and S.tier_of(src, viewer, S.areas_of(plane, viewer)) is None:
            src = None  # hidden answers exactly like missing (file 05), before any state or role check
        if src is None or src["state"] != "closed" or not may_link(src, viewer):
            raise Refused(404 if src is None else 409 if src["state"] != "closed" else 403,
                          S.NOT_FOUND if src is None else "Close the intent first." if src["state"] != "closed" else NOT_YOURS)
        made = []
        for n in (src.get("closure") or {}).get("next") or []:
            if n.get("ref") or n.get("kind") not in allowed(src["type"]) and n.get("kind") != "backlog":
                continue
            cur = S.read_intent(plane, intent_id)
            made.append(create(plane, viewer, intent_id, {"version": cur["version"], "to_kind": n["kind"], "title": src["title"],
                                                         "reason": n.get("reason"), "proposed_by": "north"}))
        return {"created": made}
    except (Refused, S.VersionConflict, S.Unreadable, ValueError) as e:
        return _fail(e)


@router.post("/api/intents/{intent_id}/links/{lid}/checked")
def post_intents_by_intent_id_links_by_link_id_checked(intent_id: str, lid: str, request: Request):
    plane, viewer = _plane(request), _viewer(request)
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable as e:
        return _fail(e)
    row = next((r for r in log_of(rec or {}) if r["link_id"] == lid and r["dir"] == "from"), None)
    if rec is None or row is None:
        return JSONResponse({"message": S.NOT_FOUND}, status_code=404)
    if not S._named((rec.get("people") or {}).get("organiser"), viewer):
        return JSONResponse({"message": "Only the organiser can do that."}, status_code=403)
    record_event(plane, intent_id, lid, "source_checked", viewer)
    return row
