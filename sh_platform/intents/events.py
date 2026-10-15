"""The transcript and audit trail (spec 16): `intents/<id>/events.jsonl`, append-only, one line per act or draft.

Every module that makes an act calls `append_event` (or `try_append`, which logs and never raises, so the act's own route does not fail).
The log holds keys, enums and numbers only; text is read at view time through `ref` with the viewer's own cut (`register_text_resolver`).
ponytail: seq comes from reading the file; one process lock; the pointer on intent.json is best effort.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.intents import _plane, _viewer
from sh_platform.intents import store as S
from sh_platform.intents.search import tier_for
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store
from sh_platform.profile.view import Viewer, norm, sees_area, sees_rule, _key, _v

router = APIRouter()
log = logging.getLogger("sh.intents.events")

_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
AGENTS = ("north", "lens", "nira", "span", "flow")
PERSON_ONLY = frozenset({"signed", "closed", "cancelled", "extended", "rated", "definition_confirmed", "cancelled_by_admin"})
ANON_OK = frozenset({"card_added", "question_answered", "vote_cast", "card_moved", "rated", "tap_added", "note_to_organiser", "late_thought"})
CLOCK_OK = frozenset({"stage_opened", "stage_closed", "state_changed", "week_opened"})  # lines North's clock makes
AGENT_LINES = {"outcome_drafted": "north", "record_frozen": "north", "lens_run_started": "lens", "lens_run_finished": "lens",
               "span_drafted": "span", "flow_drafted": "flow"}  # agent lines, written as drafts
LINK_KINDS = frozenset({"link_created", "source_cancelled", "target_cancelled", "source_checked", "note_added", "share_requested"})  # 12 and 20
AFTER_CLOSE = frozenset({"rated", "shared", "closed", "cancelled", "stage_closed", "signed", "state_changed", "cancelled_by_admin",
                         "closing_started", "closure_edited", "closure_drafted", "closure_link_sent", "closure_link_withdrawn", "late_thought", "record_frozen"}) | LINK_KINDS  # closing trail, links
MILESTONES = frozenset({"opened", "stage_opened", "stage_closed", "extended", "signed", "closed", "cancelled", "shared"})
DETAIL = {  # the keys each kind may carry (spec 16 kinds table); `week` and `edited` ride on any kind
    "opened": {"type"}, "person_invited": {"role", "required"}, "joined": {"role", "how"}, "question_answered": {"question_key"},
    "card_added": {"lane"}, "card_moved": {"from_lane", "to_lane"}, "vote_cast": set(), "definition_confirmed": {"kind"},
    "stage_opened": {"stage", "by_clock"}, "stage_closed": {"stage", "closed_by", "by_clock"}, "extended": {"old_end", "new_end"},
    "north_drafted": {"draft_of"}, "lens_drafted": {"draft_of"}, "signed": {"what", "role", "how"}, "closed": {"incomplete", "next"}, "cancelled": {"cancel_reason"},
    "shared": {"action", "people_count"}, "rated": set(), "state_changed": {"from", "to", "by_clock"},
    "link_created": {"link_id", "dir", "kind"}, "source_cancelled": {"link_id"}, "target_cancelled": {"link_id"},
    "source_checked": {"link_id"}, "note_added": {"n"}, "share_requested": set(),
    # people (14), admin, build hand-over (33), Define (26, 27)
    "person_reminded": set(), "person_declined": {"role"}, "person_role_changed": {"role", "from"}, "person_removed": set(),
    "cancelled_by_admin": set(), "build_ready_changed": {"from", "to"}, "handed_to_build": set(),
    "shelf_refused": {"cluster", "to", "missing"}, "shelf_moved": {"cluster", "to"}, "cluster_parked": {"cluster", "to"},
    "define_session_started": {"planned_minutes"}, "define_extended": {"minutes"}, "define_closed": {"decisions_made", "decisions_of"},
    "define_reopened": set(), "define_held": set(), "define_resumed": set(),
    # the wall session (35), choose and close (37, 40), the affected (17, 19), check-in weeks (38, 39), Lens (44)
    "brainstorm_opened": {"participants"}, "session_opened": {"phase"}, "session_phase": {"to"}, "session_paused": set(), "session_resumed": set(),
    "session_closed": set(), "session_time_added": {"minutes"}, "prompt_edited": {"phase"},
    "tie_picked": {"round", "free"}, "count_closed": {"round", "people_backed"}, "outcome_drafted": {"kind"}, "outcome_confirmed": {"rounds"},
    "late_thought": {"about_kind"}, "record_frozen": set(),
    "tap_added": {"item", "signed"}, "note_to_organiser": {"signed"}, "note_answered": set(), "join_requested": {"asked_role"},
    "join_answered": {"state", "role_given"},
    "week_opened": {"week_key", "by_clock"}, "entry_submitted": {"week_key"}, "entry_updated": {"week_key"}, "series_changed": {"field"}, "series_started": set(),
    "series_paused": set(), "series_resumed": set(), "series_ended": set(), "repeat_split": {"item"}, "decision_saved": {"item", "fate"},
    "session_started": set(), "session_extended": set(), "session_ended": set(), "week_closed": {"items"},
    "closure_edited": set(), "closing_started": set(), "closure_drafted": set(), "closure_link_sent": {"role"}, "closure_link_withdrawn": set(),
    "lens_question_answered": {"question"}, "lens_send_back": {"cell", "round"}, "lens_escalated": {"cell", "round"}, "lens_reassigned": {"cell"},
    "lens_run_started": {"measures", "retry"}, "lens_run_finished": {"state"},
    # the Build agents Span and Flow, and a person's decision on their suggestion
    "span_drafted": {"what", "ref"}, "flow_drafted": {"what", "ref"}, "proposal_decided": {"pid", "decision"},
}
EXTRA = {"week", "edited"}
DRAFT_OF = {"north_drafted": {"question", "next_step", "nudge", "stage_summary", "closure", "proposal"},
            "lens_drafted": {"business_term", "technical_term", "catalogue_entry", "process_map", "data_source", "governed_state"}}
GROUPS = {"opened_closed": ("Opened and closed", ("opened", "intent_opened", "closed", "cancelled", "state_changed", "cancelled_by_admin")),
          "people": ("People", ("person_invited", "joined", "person_reminded", "person_declined", "person_role_changed", "person_removed", "join_requested", "join_answered")),
          "stages": ("Stages", ("stage_opened", "stage_closed", "extended", "week_opened", "week_closed", "define_session_started", "define_extended", "define_closed",
                                "define_reopened", "define_held", "define_resumed", "session_opened", "session_phase", "session_paused", "session_resumed", "session_closed",
                                "session_time_added", "session_started", "session_extended", "session_ended", "closing_started", "build_ready_changed", "handed_to_build")),
          "talk": ("Talk", ("question_answered", "card_added", "card_moved", "vote_cast", "tap_added", "note_to_organiser", "note_answered", "late_thought", "entry_submitted",
                            "entry_updated", "tie_picked", "count_closed", "outcome_confirmed", "prompt_edited", "brainstorm_opened", "repeat_split", "decision_saved")),
          "definitions": ("Definitions", ("definition_confirmed", "shelf_moved", "shelf_refused", "cluster_parked", "lens_question_answered", "lens_send_back",
                                          "lens_escalated", "lens_reassigned")),
          "agent": ("Agent drafts", ("north_drafted", "lens_drafted", "outcome_drafted", "record_frozen", "lens_run_started", "lens_run_finished", "closure_drafted",
                                         "span_drafted", "flow_drafted")),
          "signoff": ("Sign-off", ("signed", "closure_signed", "closed_incomplete", "closure_edited", "closure_link_sent", "closure_link_withdrawn", "series_started", "series_changed", "series_paused",
                                   "series_resumed", "series_ended", "proposal_decided")), "sharing": ("Sharing and rating", ("shared", "rated")),
          "links": ("Links", ("link_created", "source_cancelled", "target_cancelled", "source_checked", "note_added", "share_requested")),
          "other": ("Other", ())}  # lines other screens wrote with their own kinds (they bypass append_event); shown, never a 500
GROUP_OF = {k: g for g, (_n, ks) in GROUPS.items() for k in ks}
KINDS = tuple(DETAIL)
TextResolver = Callable[[CompanyPlane, str, dict, Viewer], str | None]
_RESOLVERS: dict[str, tuple[TextResolver, frozenset[str] | None]] = {}
NAMED = frozenset({"person_invited", "person_reminded", "person_role_changed", "person_removed"})  # the resolved text is a person's name and sits inside the sentence
SIGNED = {"root_cause": "root cause", "no_decision": "decision not to decide", "closure": "closing summary", "fix": "fix", "decision": "decision", "charter": "charter"}
FEW = 5


class EventRefused(ValueError):
    """The line broke an append check. Plain words, for the server log."""


def register_text_resolver(store_name: str, fn: TextResolver, kinds: "frozenset[str] | set[str] | None" = None) -> None:
    """How a line's `ref.store` turns into its words for one viewer (a wall card's text, an answer). Return None when the viewer may not read it.
    `kinds` limits the resolver to those line kinds; other lines under the same store stay plain sentences."""
    _RESOLVERS[store_name] = (fn, frozenset(kinds) if kinds else None)


def _file(plane: CompanyPlane, intent_id: str):
    if not _ID.fullmatch(str(intent_id)):
        raise EventRefused("the intent id is not valid")
    return plane.path("intents", intent_id, "events.jsonl")


def read_events(plane: CompanyPlane, intent_id: str) -> list[dict]:
    """Every readable line in order. A line that does not parse (a torn last line) is skipped; the file is never rewritten."""
    try:
        raw = _file(plane, intent_id).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    out = []
    for line in raw.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and isinstance(e.get("seq"), int):
            out.append(e)
    return out


def _check_detail(kind: str, detail: dict) -> dict:
    allowed = DETAIL[kind] | EXTRA
    detail = {k: ",".join(v) if isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v) else v for k, v in detail.items()}  # a list of enums rides as one string
    for k, v in detail.items():
        if k not in allowed:
            raise EventRefused(f"{kind} may not carry '{k}'")
        if isinstance(v, str) and len(v) > 80:
            raise EventRefused("a detail value is longer than 80 characters")
        if not (v is None or isinstance(v, (str, int, float, bool))):
            raise EventRefused("detail holds keys, enums and numbers only")
    if "draft_of" in detail and detail["draft_of"] not in DRAFT_OF[kind]:
        raise EventRefused("draft_of is not on the list for this kind")
    return dict(detail)


def append_event(plane: CompanyPlane, intent_id: str, kind: str, who: Any, ref: dict | None, detail: dict | None, act_or_draft: str, *,
                 stage: str | None = None, anonymous: bool = False, confirms: int | None = None, corrects: int | None = None,
                 sealed: bool = False) -> dict:
    """Append one line and return it. `who` is a person {account, name, role} for an act, "north" or "lens" for a draft, "north" for an
    act the clock made (detail.by_clock), None only with anonymous=True. Raises EventRefused when a check fails."""
    if kind not in DETAIL:
        raise EventRefused("unknown kind")
    if act_or_draft not in ("act", "draft"):
        raise EventRefused("status must be act or draft")
    detail = _check_detail(kind, detail or {})
    clock = bool(detail.get("by_clock"))
    agent = who if isinstance(who, str) else None
    if act_or_draft == "draft":
        own = AGENT_LINES.get(kind) == agent or (kind in DRAFT_OF and (kind == "north_drafted") == (agent == "north"))
        if not own or agent not in AGENTS:
            raise EventRefused("only an agent may write a draft line, of its own kind")
        by = None
    else:
        if kind in DRAFT_OF:
            raise EventRefused("a draft kind is written as a draft")
        if clock:
            if kind not in CLOCK_OK or agent != "north":
                raise EventRefused("only a stage or state line may be made by the clock")
            by = None
        elif agent:
            raise EventRefused("an act is a person's; an agent may only draft")
        elif anonymous:
            if kind not in ANON_OK:
                raise EventRefused("this kind cannot be anonymous")
            by = None
        elif isinstance(who, dict) and who.get("account") and who.get("name"):
            by = {"account": str(who["account"]), "name": str(who["name"]), "role": str(who.get("role") or "")}
        else:
            raise EventRefused("an act needs a named person")
    if kind in PERSON_ONLY and (by is None and not (kind == "rated" and anonymous)):
        raise EventRefused("this kind needs a person")
    ref = ref or {}
    if set(ref) - {"store", "id", "version"}:
        raise EventRefused("ref holds store, id and version only")
    ipath = plane.path("intents", intent_id, "intent.json")
    rec = read_json_strict(ipath, dict) or {}
    if rec.get("state") in ("closed", "cancelled") and kind not in AFTER_CLOSE:
        raise EventRefused("the intent is closed; only rated and shared lines may follow")
    if stage is None:
        stage = next((s.get("key") for s in rec.get("stages") or [] if isinstance(s, dict) and s.get("state") == "open"), None)
    path = _file(plane, intent_id)
    with lock_for(path):
        last = max((e["seq"] for e in read_events(plane, intent_id)), default=0)
        for pointer in (confirms, corrects):
            if pointer is not None and not 0 < pointer <= last:
                raise EventRefused("confirms and corrects must name an earlier line")
        e = {"seq": last + 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind, "status": act_or_draft, "by": by,
             "anonymous": by is None and anonymous, "agent": agent if act_or_draft == "draft" else None, "stage": stage,
             "ref": {"store": ref.get("store"), "id": ref.get("id"), "version": ref.get("version")}, "detail": detail,
             "confirms": confirms, "corrects": corrects, "sealed": bool(sealed)}
        path.parent.mkdir(parents=True, exist_ok=True)
        torn = path.exists() and path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write(("\n" if torn else "") + json.dumps(e, separators=(",", ":")) + "\n")
            f.flush()
        _point(plane, intent_id, rec, e)
    return e


def _point(plane: CompanyPlane, intent_id: str, rec: dict, e: dict) -> None:
    """The counter on the record: no version bump, no updated_at move. The log is the truth; this is rebuilt from it."""
    if not rec:
        return
    p = plane.path("intents", intent_id, "intent.json")
    try:
        with S.locked(plane):
            cur = read_json_strict(p, dict)
            if cur:
                n = len(read_events(plane, intent_id))
                cur["events"] = {"path": f"intents/{intent_id}/events.jsonl", "count": n, "last_seq": e["seq"], "last_at": e["at"]}
                cur["event_count"] = n
                write_json_atomic(p, cur)
    except (OSError, ValueError):
        log.error("the event counter on intent %s was not updated", intent_id)


def point_rec(rec: dict, e: dict | None) -> None:
    """For a writer that holds `rec` and writes it afterwards: copy the new counter into it so its write does not undo the pointer."""
    if e and isinstance(rec, dict):
        rec["event_count"] = e["seq"]
        rec["events"] = {"path": f"intents/{rec.get('id')}/events.jsonl", "count": e["seq"], "last_seq": e["seq"], "last_at": e["at"]}


def try_append(*args: Any, **kw: Any) -> dict | None:
    """append_event for the routes that make acts: a failure is logged ("event not recorded"), never raised."""
    try:
        return append_event(*args, **kw)
    except (EventRefused, OSError) as err:
        log.error("event not recorded for intent %s: %s", args[1] if len(args) > 1 else "?", err)
        return None


# ---- the cut

def _title(s: Any) -> str:
    return str(s or "").replace("_", " ").strip().capitalize()


def _restricted(plane: CompanyPlane, e: dict, viewer: Viewer) -> bool:
    """A definition or Lens line whose measure or area the profile shuts to this viewer: dropped, never stubbed."""
    if e["kind"] not in ("definition_confirmed", "lens_drafted"):
        return False
    ident = _key((e.get("ref") or {}).get("id") or "")
    gov = store.raw(plane)["governance"]
    return bool(ident) and (
        any(not sees_rule(r, viewer) for k, r in gov["field_rules"].items() if ident in {_key(k), _key(_v(r, "field") or ""), _key(_v(r, "measure") or "")})
        or any(not sees_area(a, viewer) for k, a in gov["restricted_areas"].items() if ident in {_key(k), _key(_v(a, "area") or "")}))


def _norm(e: dict) -> dict:
    """A line as the cut expects it. Other writers append to the same file by hand, so every field is defaulted here, and an anonymous
    line loses any `by` a writer left on it: no name or account id leaves through the cut."""
    anon = bool(e.get("anonymous"))
    by = e.get("by") if isinstance(e.get("by"), dict) and not anon else None
    agent = str(e["agent"]).lower() if e.get("agent") else None
    return {**e, "kind": str(e.get("kind") or ""), "status": "draft" if e.get("status") == "draft" else "act", "by": by, "anonymous": anon,
            "agent": agent, "ref": e.get("ref") if isinstance(e.get("ref"), dict) else {}, "detail": e.get("detail") if isinstance(e.get("detail"), dict) else {},
            "sealed": bool(e.get("sealed")), "at": str(e.get("at") or ""), "confirms": e.get("confirms") if isinstance(e.get("confirms"), int) else None,
            "corrects": e.get("corrects") if isinstance(e.get("corrects"), int) else None}


def _who(e: dict) -> str:
    if e["status"] == "draft":
        return f"{_title(e['agent'] or 'north')} (draft)"
    if e["by"]:
        return (str(e["by"].get("name") or "").split() or ["Someone"])[0]
    return "Anonymous" if e["anonymous"] else "North (clock)"


def _sentence(e: dict, who: str, text: str | None, resolver: bool) -> str:
    d, k = e["detail"], e["kind"]
    clock = " (clock)" if d.get("by_clock") else ""
    s = {"opened": f"{who} opened this intent", "person_invited": f"{who} invited {text or 'someone'} as {_title(d.get('role')).lower() or 'a participant'}",
         "joined": f"{who} joined as {_title(d.get('role')).lower()}".rstrip(), "question_answered": f"{who} answered a start question",
         "card_added": f"{who} added a card" + (f" to {_title(d['lane'])}" if d.get("lane") else ""),
         "card_moved": f"{who} moved a card from {_title(d.get('from_lane'))} to {_title(d.get('to_lane'))}", "vote_cast": f"{who} cast a vote",
         "definition_confirmed": f"{who} confirmed a {_title(d.get('kind')).lower() or 'new'} definition",
         "stage_opened": f"Stage opened: {_title(d.get('stage'))}{clock}", "stage_closed": f"Stage closed: {_title(d.get('stage'))}{clock}",
         "extended": f"{who} extended the time box" + (f" to {str(d['new_end'])[:10]}" if d.get("new_end") else ""),
         "north_drafted": f"North drafted the {_title(d.get('draft_of')).lower()}", "lens_drafted": f"Lens drafted the {_title(d.get('draft_of')).lower()}",
         "signed": f"{who} signed the {SIGNED.get(str(d.get('what')), str(d.get('what') or 'record').replace('_', ' '))}", "closed": f"{who} closed the intent" + (" with what we have" if d.get("incomplete") else ""),
         "cancelled": f"{who} cancelled the intent", "shared": f"{who} {'withdrew' if d.get('action') == 'withdrawn' else 'created'} a share link",
         "rated": "A rating was added", "link_created": f"{who} linked this to another intent",
         "source_cancelled": "The intent this came from was cancelled", "target_cancelled": "An intent that came from this was cancelled",
         "source_checked": f"{who} checked the cancelled source", "note_added": f"{who} added a note", "share_requested": f"{who} asked the organiser to share",
         "state_changed": f"{who} moved the intent from {_title(d.get('from'))} to {_title(d.get('to'))}{clock}" if d.get("from") else f"{who} started this intent as a draft",
         "person_reminded": f"{who} reminded {text or 'someone'} to reply",
         "person_declined": f"{who} declined to join" + (f" as {_title(d.get('role')).lower()}" if d.get("role") else ""),
         "person_role_changed": f"{who} changed {text + chr(39) + 's' if text else 'a person' + chr(39) + 's'} part to {_title(d.get('role')).lower() or 'a new one'}",
         "person_removed": f"{who} removed {text or 'someone'} from this intent",
         "closure_signed": f"{who} signed the closing summary", "closed_incomplete": f"{who} closed the intent with what we have", "intent_opened": f"{who} opened this intent", "cancelled_by_admin": f"{who} cancelled the intent as company admin",
         "build_ready_changed": f"{who} moved the hand-over to Build from {_title(d.get('from'))} to {_title(d.get('to'))}", "handed_to_build": f"{who} handed this over to Build",
         "shelf_refused": f"{who} tried to move a group to {_title(d.get('to')).lower()}, which was refused", "shelf_moved": f"{who} moved a group to {_title(d.get('to')).lower()}",
         "cluster_parked": f"{who} parked a group for later", "define_session_started": f"{who} started the Define session",
         "define_extended": f"{who} added {d.get('minutes') or 'more'} minutes to the Define session", "define_closed": f"{who} closed Define",
         "define_reopened": f"{who} reopened Define", "define_held": f"{who} put the Define session on hold", "define_resumed": f"{who} resumed the Define session",
         "brainstorm_opened": f"{who} opened the session to {d.get('participants', 'the')} people", "session_opened": f"{who} opened the session",
         "session_phase": f"{who} moved the session to {_title(d.get('to')).lower()}", "session_paused": f"{who} paused the session",
         "session_resumed": f"{who} resumed the session", "session_closed": f"{who} closed the session",
         "session_time_added": f"{who} added {d.get('minutes') or 'more'} minutes", "prompt_edited": f"{who} changed the prompt for {_title(d.get('phase')).lower()}",
         "tie_picked": f"{who} picked between tied options", "count_closed": f"{who} closed round {d['round']} of the count" if d.get("round") else f"{who} closed a round of the count",
         "outcome_drafted": "North drafted the outcome", "outcome_confirmed": f"{who} confirmed the outcome", "late_thought": f"{who} added a late thought",
         "record_frozen": "The record was frozen", "tap_added": f"{who} tapped how it feels", "note_to_organiser": f"{who} sent a note to the organiser",
         "note_answered": f"{who} answered a note", "join_requested": f"{who} asked to join", "join_answered": f"{who} answered a request to join",
         "week_opened": "A new check-in week opened", "entry_submitted": f"{who} sent a check-in", "entry_updated": f"{who} updated a check-in",
         "series_changed": f"{who} changed the check-in settings", "series_started": f"{who} started the check-ins", "series_paused": f"{who} paused the check-ins",
         "series_resumed": f"{who} resumed the check-ins", "series_ended": f"{who} ended the check-ins", "repeat_split": f"{who} split a repeated item",
         "decision_saved": f"{who} saved a decision on an item", "session_started": f"{who} started the review session",
         "session_extended": f"{who} extended the review session", "session_ended": f"{who} ended the review session", "week_closed": f"{who} closed the week",
         "closure_edited": f"{who} edited the closing summary", "closing_started": f"{who} started closing the intent",
         "closure_drafted": f"{who} asked for a draft closing summary", "closure_link_sent": f"{who} sent a sign-off link",
         "closure_link_withdrawn": f"{who} withdrew a sign-off link", "lens_question_answered": f"{who} answered a question from Lens",
         "lens_send_back": f"{who} sent a definition back to Lens", "lens_escalated": f"{who} escalated a definition to the approver",
         "lens_reassigned": f"{who} passed a Lens item to someone else", "lens_run_started": "Lens started drafting definitions",
         "lens_run_finished": "Lens finished drafting definitions",
         "span_drafted": f"Span drafted the {_title(d.get('what')).lower() or 'design'}", "flow_drafted": f"Flow drafted the {_title(d.get('what')).lower() or 'note'}",
         "proposal_decided": f"{who} {'accepted' if d.get('decision') == 'accepted' else 'declined' if d.get('decision') == 'declined' else 'answered'} a suggestion from Build"}.get(k) or f"{who}: {_title(k).lower()}"
    if k in NAMED:
        return s
    if text:
        return f"{s}: {text}"
    return f"{s} (content not open to you)" if resolver and text is None else s  # "" from a resolver: nothing to add, nothing hidden


def _stub(e: dict) -> str:
    return {"card_added": "A sealed card was added", "card_moved": "A sealed card was moved", "vote_cast": "A vote was cast on a sealed card"}.get(e["kind"], "A sealed card was changed")


def cut(plane: CompanyPlane, rec: dict, events: list[dict], viewer: Viewer, info: dict) -> list[dict]:
    """The lines this viewer may see, as display lines. `info` is tier_for's answer. Done on the server, never in the browser."""
    admin_only = info["tier"] == 1
    events = [_norm(e) for e in events]
    joined = {(e["ref"] or {}).get("id") for e in events if e["kind"] == "joined"}
    keep = []
    for e in events:
        if admin_only and (e["kind"] not in MILESTONES or e["anonymous"] or e["sealed"]):
            continue
        if _restricted(plane, e, viewer) or (info["share_only"] and e["kind"] == "person_invited" and (e["ref"] or {}).get("id") not in joined):
            continue
        keep.append(e)
    seqs = {e["seq"] for e in keep}
    confirmed = {e["confirms"]: e for e in keep if e.get("confirms") in seqs}
    corrected = {e["corrects"] for e in keep if e.get("corrects")}
    closed_seq = next((e["seq"] for e in keep if e["kind"] in ("closed", "cancelled")), None)
    out = []
    for e in keep:
        week = e["detail"].get("week")
        stage = week or e.get("stage") or ("after_closing" if closed_seq and e["seq"] > closed_seq else "before_first_stage")
        line = {"seq": e["seq"], "at": e["at"], "kind": e["kind"], "group": GROUP_OF.get(e["kind"], "other"), "status": e["status"], "stage": stage,
                "confirms": e.get("confirms"), "corrects": e.get("corrects"), "superseded": e["seq"] in corrected}
        if e["sealed"]:
            out.append({**line, "stub": _stub(e), "who": None, "sentence": _stub(e), "anonymous": False, "agent": None, "link": False})
            continue
        got = _RESOLVERS.get((e["ref"] or {}).get("store") or "")
        resolver = got[0] if got and (got[1] is None or e["kind"] in got[1]) else None
        text = resolver(plane, rec["id"], e, viewer) if resolver else None
        who = _who(e)
        c = confirmed.get(e["seq"])
        out.append({**line, "stub": None, "who": who, "anonymous": e["anonymous"],
                    "agent": e["agent"], "sentence": _sentence(e, who, text, bool(resolver)), "link": bool(text),
                    "confirmed_by": {"seq": c["seq"], "name": _who(c), "at": c["at"]} if c else None,
                    "person": (e["by"].get("name") or None) if e["by"] and e["status"] == "act" else None})
    return out


def summary(lines: list[dict], milestones_only: bool) -> dict:
    """Counts over the cut, after the cut: a hidden line is in no number."""
    named: dict[str, int] = {}
    for ln in lines:
        if ln.get("person") and ln["status"] == "act":
            named[ln["person"]] = named.get(ln["person"], 0) + 1
    return {"by_group": {g: sum(1 for ln in lines if ln["group"] == g) for g in GROUPS},
            "people": [] if milestones_only else [{"name": n, "count": c if c >= FEW else None, "few": c < FEW} for n, c in sorted(named.items())],
            "anonymous": 0 if milestones_only else sum(1 for ln in lines if ln["anonymous"]),
            "drafts": sum(1 for ln in lines if ln["status"] == "draft"), "acts": sum(1 for ln in lines if ln["status"] == "act")}


# ---- routes

def _plain(status: int, message: str) -> JSONResponse:
    error = {403: "forbidden", 404: "not_found", 409: "conflict"}.get(status, "bad_request")
    return JSONResponse({"detail": message, "error": error, "message": message}, status_code=status)


def _open(request: Request, intent_id: str):
    """(plane, viewer, record, tier info) or a JSONResponse refusal: 404 for an intent the viewer may not see, 403 without the tab."""
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        return _plain(403, "The Intent Centre is not open to you.")
    rec = read_json_strict(plane.path("intents", intent_id, "intent.json"), dict) if _ID.fullmatch(intent_id) else None
    info = tier_for(rec, viewer, S.areas_of(plane, viewer)) if rec else None
    if info is None:
        return _plain(404, "We could not find that.")
    if info["tier"] == 2 and "company_admin" in viewer.roles:
        info = {**info, "tier": 1}  # a company admin tagged to an area still gets milestones and counts (spec 16), not less than untagged
    if info["tier"] not in (1, 3):
        return _plain(403, "The history is open to the people in this intent.")
    return plane, viewer, rec, info


def _zone(plane: CompanyPlane) -> str:
    c = (store.raw(plane).get("company") or {}).get("time_zone")
    return str(c.get("value")) if isinstance(c, dict) and c.get("value") else "UTC"


@router.get("/api/intents/{intent_id}/events")
def get_intents_by_intent_id_events(request: Request, intent_id: str):
    got = _open(request, intent_id)
    if isinstance(got, JSONResponse):
        return got
    plane, viewer, rec, info = got
    q = request.query_params
    lines = cut(plane, rec, read_events(plane, intent_id), viewer, info)
    milestones = info["tier"] == 1
    kinds = {g for g in (q.get("kind") or "").split(",") if g in GROUPS}
    kinds = kinds or ({"__none__"} if q.get("kind") else set())  # every chip off: no line matches
    by, stage = q.get("by") or "", q.get("stage") or ""
    try:
        limit = max(1, min(int(q.get("limit", 100)), 100))
        after, before = int(q.get("after") or 0), int(q.get("before") or 0)
    except ValueError:
        return _plain(400, "That request was not understood.")
    want = [ln for ln in lines if (not kinds or ln["group"] in kinds) and (not stage or ln["stage"] == stage) and ln["seq"] > after and (not before or ln["seq"] < before)
            and (not by or (by == "anonymous" and ln["anonymous"]) or (by != "anonymous" and ln.get("person") == by))]
    page = sorted(want, key=lambda ln: -ln["seq"])[:limit]
    stages = [{"key": "before_first_stage", "name": "Before the first stage"}, *[{"key": str(s.get("key")), "name": _title(s.get("name") or s.get("key"))}
              for s in rec.get("stages") or [] if isinstance(s, dict) and s.get("key")], {"key": "after_closing", "name": "After closing"}]
    for s in stages:
        s["count"] = sum(1 for ln in lines if ln["stage"] == s["key"])
    sm = summary(lines, milestones)
    return {"items": page, "total": len(want), "visible": len(lines), "next": page[-1]["seq"] if len(want) > len(page) and page else None,
            "last_seq": max((ln["seq"] for ln in lines), default=0), "mode": "milestones" if milestones else "full",
            "groups": [{"key": g, "name": n, "count": sm["by_group"][g]} for g, (n, _k) in GROUPS.items()], "stages": stages, "summary": sm,
            "intent": {"title": rec.get("title"), "created_at": rec.get("created_at"), "state": rec.get("state"), "type": rec.get("type"), "closed_at": (rec.get("closure") or {}).get("closed_at")}, "zone": _zone(plane),
            "download": rec.get("state") in ("closed", "cancelled") and not milestones}


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-").lower()[:60] or "intent"


def _markdown(rec: dict, company: str, viewer: Viewer, lines: list[dict], sm: dict, zone: str) -> str:
    out = [f"# Transcript: {company}", f"**Intent:** {rec.get('title')}   **Type:** {rec.get('type')}   **Closed:** {str((rec.get('closure') or {}).get('closed_at') or '')[:10]}   "
           f"**Cut to:** {viewer.name}", "", f"Cut to what {viewer.name} may see. Times are in {zone}.", "", "## Summary"]
    out += [f"- {GROUPS[g][0]}: {n}" for g, n in sm["by_group"].items() if n]
    out += [f"- {p['name']}: {p['count'] if p['count'] is not None else 'Fewer than five'}" for p in sm["people"]]
    out += [f"- Drafted by agents: {sm['drafts']}. Done by people: {sm['acts']}", "", "## What happened"]
    for key in dict.fromkeys(ln["stage"] for ln in lines):
        out += ["", f"### {_title(key)}"] + [f"- {ln['at'][11:16]}, {ln['sentence']}" for ln in lines if ln["stage"] == key]
    c = rec.get("closure") or {}
    out += ["", "## How it ended", c.get("summary") or "Not available yet.", "", f"Why it happened: {c.get('why_it_happened') or 'Not available yet.'}",
            f"What came out: {c.get('what_came_out') or 'Not available yet.'}", "", "## Signed by"]
    out += [f"- {ln['person']}, {ln['at'][:16].replace('T', ' ')}" for ln in lines if ln["kind"] == "signed" and ln.get("person")] or ["No one signed this intent."]
    return "\n".join(out) + "\n"


def _html(md: str, title: str) -> str:
    body = "".join(f"<p>{re.sub('[<>&]', lambda m: {'<': '&lt;', '>': '&gt;', '&': '&amp;'}[m.group()], ln)}</p>" for ln in md.splitlines() if ln.strip())
    return (f"<!doctype html><meta charset='utf-8'><title>{re.sub('[<>&]', '', title)}</title>"
            "<style>body{font:14px/1.5 sans-serif;max-width:46rem;margin:2rem auto}@media print{body{margin:0}}</style>" + body)


@router.get("/api/intents/{intent_id}/transcript/download")
def get_intents_by_intent_id_transcript_download(request: Request, intent_id: str):
    got = _open(request, intent_id)
    if isinstance(got, JSONResponse):
        return got
    plane, viewer, rec, info = got
    if info["tier"] < 3 or info["share_only"]:
        return _plain(403, "The transcript is for the people in this intent.")
    if rec.get("state") not in ("closed", "cancelled"):
        return _plain(409, "The transcript can be downloaded once the intent is closed.")
    lines = [ln for ln in cut(plane, rec, read_events(plane, intent_id), viewer, info) if request.query_params.get("drafts") != "0" or ln["status"] != "draft"]
    if not lines:
        return _plain(409, "Nothing was recorded.")
    md = _markdown(rec, plane.company_id, viewer, lines, summary(lines, False), _zone(plane))
    base = f"{_safe(plane.company_id)}-{_safe(rec.get('title') or intent_id)}-transcript-{datetime.now(timezone.utc).date().isoformat()}"
    return {"files": [{"format": "md", "filename": f"{base}.md", "mime": "text/markdown", "content": md},
                      {"format": "html", "filename": f"{base}.html", "mime": "text/html", "content": _html(md, f"Transcript: {rec.get('title')}")}]}
