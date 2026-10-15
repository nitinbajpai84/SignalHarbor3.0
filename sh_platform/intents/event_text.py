"""Text resolvers for the What happened tab (spec 16): a line's `ref` turns into words only for a viewer who may read them.

The log keeps no text. A resolver returns None when the viewer may not read it, never an anonymous author, never sealed text.
A store is registered with the kinds it can resolve, so other lines under the same store stay plain sentences.
ponytail: reads the record on every line; fine for a log of a few hundred lines, cache per request if it is not.
"""
import logging

from sh_platform.intents import events
from sh_platform.intents import store as S
from sh_platform.plane import CompanyPlane
from sh_platform.profile.view import Viewer

log = logging.getLogger("sh.intents.event_text")
_done = False


def _readable(plane: CompanyPlane, intent_id: str, viewer: Viewer) -> dict | None:
    rec = S.read_intent(plane, intent_id)
    return rec if rec and S.tier_of(rec, viewer, S.areas_of(plane, viewer)) == "content" else None


def linked_title(plane: CompanyPlane, _own: str, e: dict, viewer: Viewer) -> str | None:
    """A link line: the other intent's title, if the viewer may open that intent's content."""
    other = _readable(plane, str((e.get("ref") or {}).get("id") or ""), viewer)
    return str(other.get("title") or "") or None if other else None


def person_name(plane: CompanyPlane, own: str, e: dict, viewer: Viewer) -> str | None:
    """A people line: the person's name, by the people panel's rule: the organiser sees everyone, a member sees those still in, others see no one."""
    rec = _readable(plane, own, viewer)
    if not rec:
        return None
    people = rec.get("people_detail") or []
    mine = next((p for p in people if p.get("person_id") == viewer.account_id), None)
    organiser = ((rec.get("people") or {}).get("organiser") or {}).get("account_id") == viewer.account_id
    p = next((p for p in people if p.get("person_id") == (e.get("ref") or {}).get("id")), None)
    if not p or not (organiser or (mine and mine.get("status") != "removed" and p.get("status") not in ("declined", "removed"))):
        return None
    return str(p.get("name") or "") or None


def chosen_option(plane: CompanyPlane, own: str, e: dict, viewer: Viewer) -> str | None:
    """A decision signed line: the option that was chosen."""
    what = (e.get("detail") or {}).get("what")
    if what == "no_decision":
        return "no option chosen"
    if what != "decision":
        return ""  # another signed line under this store: nothing to add, and nothing hidden
    out = (_readable(plane, own, viewer) or {}).get("outcome") or {}
    pick = next((o for o in out.get("options") or [] if isinstance(o, dict) and o.get("id") == out.get("chosen")), None)
    return str(pick.get("name") or "") or None if pick else None


def option_text(plane: CompanyPlane, own: str, e: dict, viewer: Viewer) -> str | None:
    """A decision option card: its name. The author is the line's business, and an anonymous line already hides it."""
    out = (_readable(plane, own, viewer) or {}).get("outcome") or {}
    o = next((o for o in out.get("options") or [] if isinstance(o, dict) and o.get("id") == (e.get("ref") or {}).get("id")), None)
    return str(o.get("name") or "") or None if o else None


def note_text(plane: CompanyPlane, own: str, e: dict, viewer: Viewer) -> str | None:
    """A decision note: its text, from the option it sits on."""
    oid, _, nid = str((e.get("ref") or {}).get("id") or "").partition(":")
    out = (_readable(plane, own, viewer) or {}).get("outcome") or {}
    o = next((o for o in out.get("options") or [] if isinstance(o, dict) and o.get("id") == oid), None)
    n = next((n for n in (o or {}).get("notes") or [] if isinstance(n, dict) and n.get("id") == nid), None)
    return str(n.get("text") or "") or None if n else None


def register() -> None:
    """Idempotent; called once from search.tier_for, which every events request runs first (no import cycle with events.py)."""
    global _done
    if _done:
        return
    _done = True
    events.register_text_resolver("intents", linked_title)
    events.register_text_resolver("intent_people", person_name, events.NAMED)
    events.register_text_resolver("intent", chosen_option, {"signed"})
    events.register_text_resolver("decision_option", option_text)
    events.register_text_resolver("decision_note", note_text)
