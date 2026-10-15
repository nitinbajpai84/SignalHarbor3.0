"""The intent store (spec 01): one folder per intent under the company plane, `intents/<id>/intent.json`, plus `intents/_index.json`.

Reshaped from modules/m1_intent/store/sessions.py (module-free: the kernel cannot import a module). Other cards import:
read_intent, write_intent, update_intent, create_intent, append_index, rebuild_index, read_index, list_for_viewer, tier_of, cut, areas_of, context, columns, named_in_records.
Every read-modify-write takes `lock_for(intents folder)`; the record is written first, then its index row.
"""
import dataclasses
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Callable

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import view as pview

log = logging.getLogger(__name__)

PREFIX = {"initiative": "ini", "brainstorm": "bra", "pulse": "pul", "problem": "prb", "decision": "dec"}
ID_RE = re.compile(r"(?:ini|bra|pul|prb|dec)-[0-9a-f]{32}")
STATES = ("draft", "open", "in_session", "closing", "closed", "cancelled")
SLOTS = ("organiser", "sponsor", "decider", "owner", "reporter")
LISTS = ("participants", "advisers", "affected", "observers")
# Section 3 of the brief, "Fields this feature adds" of file 01 and of the other files that write top-level keys (ruling 28).
# Other cards add a key here only when their spec file lists it.
KEYS = frozenset({
    "id", "type", "title", "purpose", "created_by", "created_at", "company", "areas", "people", "state", "time_box", "stages", "outcome",
    "closure", "ratings", "links", "share", "record", "version", "updated_at", "history", "affected_may_read", "refs", "event_count",
    "events", "catalogue_version", "start_answers", "north_proposal", "draft_updated_at", "opened_by", "backlog_ref", "build_needed",
    "build_needed_reason", "build_needed_by", "build_needed_at", "build_ready", "build_handoff", "series", "triage_note", "passes",
    "owner_picked_by", "from_item", "session",
    "define", "memory", "catalogue", "outcome_used", "rating", "nudges", "judgement", "north", "source_map", "glossary", "waiting_on", "data_sources", "processes", "converge", "late_window", "late_thoughts", "frozen_at", "people_detail", "closing_started_at", "link_log", "from_pack",
    "votes", "drafts_to_confirm", "definitions_waiting", "process_waiting", "owner_accepted_at",  # spec 13, read by the Pulse lines
    "notes", "what_we_know", "short_ref",
    "hypothesis_ref", "proving"})  # B24; 57, 58
UNREADABLE = "This intent could not be read. Please tell your administrator."
NOT_FOUND = "We could not find that."
CONFLICT = "Someone changed this intent. Please reload."


class Unreadable(Exception):
    """A record that cannot be read or fails the key check. It is never overwritten and drops out of lists."""


class VersionConflict(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def intents_dir(plane: CompanyPlane):
    return plane.path("intents")


def locked(plane: CompanyPlane):
    return lock_for(intents_dir(plane))


def new_id(type_: str) -> str:
    return f"{PREFIX[type_]}-{secrets.token_hex(16)}"


def _file(plane: CompanyPlane, intent_id: str):
    return plane.path("intents", intent_id, "intent.json")


def read_intent(plane: CompanyPlane, intent_id: str) -> dict | None:
    """The whole record, or None when the id is not an intent id or has no record. Raises Unreadable for a damaged file."""
    if not isinstance(intent_id, str) or not ID_RE.fullmatch(intent_id):
        return None
    for attempt in range(6):  # ER-14, RC-11: a read that meets a concurrent os.replace on Windows is retried, not reported as damaged
        try:
            rec = read_json_strict(_file(plane, intent_id), dict)
            break
        except PermissionError:
            if attempt == 5:
                raise Unreadable(intent_id) from None
            time.sleep(0.05)
        except (OSError, ValueError):
            raise Unreadable(intent_id) from None
    if rec is None:
        return None
    if set(rec) - KEYS or rec.get("id") != intent_id or rec.get("state") not in STATES or rec.get("type") not in PREFIX:
        raise Unreadable(intent_id)
    return rec


def write_intent(plane: CompanyPlane, rec: dict, *, create: bool = False, expected_version: int | None = None) -> dict:
    """Write `rec` under the lock: version check, key check, version bump, record, then its index row. `rec["version"]` is the
    version the caller read (override with expected_version). A create must not find an existing record. Returns rec."""
    if set(rec) - KEYS:
        raise ValueError("unknown intent field")
    with locked(plane):
        if create:
            if read_intent(plane, rec["id"]) is not None:
                raise VersionConflict()
            rec["version"] = 1
        else:
            cur = read_intent(plane, rec["id"])
            if cur is None or cur["version"] != (rec["version"] if expected_version is None else expected_version):
                raise VersionConflict()
            rec["version"] = cur["version"] + 1
        rec["updated_at"] = now_iso()
        write_json_atomic(_file(plane, rec["id"]), rec)
        append_index(plane, rec)
    return rec


def update_intent(plane: CompanyPlane, intent_id: str, version: int, change: Callable[[dict], None]) -> dict:
    """Read fresh, refuse a stale `version`, let `change(rec)` edit it (it may raise), write. The one write path for the routes."""
    with locked(plane):
        rec = read_intent(plane, intent_id)
        if rec is None:
            raise LookupError(intent_id)
        if rec["version"] != version:
            raise VersionConflict()
        change(rec)
        return write_intent(plane, rec)


def create_intent(plane: CompanyPlane, rec: dict) -> dict:
    return write_intent(plane, rec, create=True)


# ---- the index -------------------------------------------------------------------------------------------------------------

def _index_file(plane: CompanyPlane):
    return plane.path("intents", "_index.json")


def _stage_now(rec: dict) -> dict:
    return next((s for s in rec.get("stages") or [] if s.get("state") == "open"), {})


def _share_named(rec: dict) -> list[str]:
    """People a live share names: revoked and expired rows do not count (spec 11 rule 4; T28 defect B)."""
    now = datetime.now(timezone.utc).isoformat()
    return [w["person_id"] for w in (rec.get("share") or {}).get("who_may_open") or []
            if isinstance(w, dict) and w.get("person_id") and not w.get("revoked_at")
            and not (w.get("expires_at") and str(w["expires_at"]) < now)]


def _stage_name(rec: dict) -> str:
    from sh_platform.intents.lifecycle import type_def  # lifecycle imports this module
    key = _stage_now(rec).get("key")
    try:
        return next((s["name"] for s in type_def(rec["type"])["stages"] if s["key"] == key), "") if key else ""
    except (KeyError, OSError):
        return ""


def _row(rec: dict) -> dict:
    p, c, tb = rec.get("people") or {}, rec.get("closure") or {}, rec.get("time_box") or {}
    count = sum(1 for s in SLOTS if p.get(s)) + sum(len(p.get(k) or []) for k in LISTS)
    scores = [r["score"] for r in rec.get("ratings") or [] if isinstance(r.get("score"), int)]
    return {"id": rec["id"], "type": rec["type"], "title": rec.get("title", ""), "purpose": rec.get("purpose", ""), "state": rec["state"],
            "stage_key": _stage_now(rec).get("key", ""), "stage_name": _stage_name(rec), "areas": rec.get("areas") or [],
            "created_by": rec.get("created_by"), "organiser": {"name": (p.get("organiser") or {}).get("name", "")},
            "people": {**{s: p.get(s) for s in SLOTS}, **{k: p.get(k) or [] for k in LISTS}, "share_named": _share_named(rec)},
            "affected_may_read": bool(rec.get("affected_may_read")), "people_count": count,
            "starts": tb.get("starts", ""), "ends": tb.get("ends", ""), "extended": bool(tb.get("extended_by")),
            "closed_at": c.get("closed_at") if rec["state"] == "closed" else None,
            "cancelled_at": c.get("closed_at") if rec["state"] == "cancelled" else None,
            "outcome_text": (c.get("what_came_out") or c.get("summary") or "") if rec["state"] == "closed" else "",
            "next_kinds": [n.get("kind") for n in c.get("next") or []], "rating_n": len(scores),
            "rating_avg": round(sum(scores) / len(scores), 1) if len(scores) >= 3 else None,  # ratings aggregate from three (ruling 8)
            "rev": str(rec["version"]), "updated_at": rec.get("updated_at", ""), "created_at": rec.get("created_at", ""),
            "share_expires": {w["person_id"]: w.get("expires_at") for w in (rec.get("share") or {}).get("who_may_open") or []
                              if isinstance(w, dict) and w.get("person_id")},
            "body_text": f"{rec.get('title', '')} {rec.get('purpose', '')}".strip()}


SCHEMA = 2  # 2: rows carry created_at and share_expires; an older index is rebuilt on the next read


def _doc(rows: list[dict], reason: str) -> dict:
    return {"schema": SCHEMA, "built_at": now_iso(), "rebuilt_reason": reason, "rows": rows}


def _with_proving(plane: CompanyPlane, rec: dict) -> dict:
    """The index row plus spec 58's `proving` and `proving_since` (C20); a missing or unreadable Proving file adds nothing."""
    row = _row(rec)
    try:
        from sh_platform.intents import proving  # lazy: proving imports store
        row.update(proving.index_fields(proving.read_proving(plane, rec["id"])))
    except Exception:  # noqa: BLE001 - the index must never fail on Proving
        log.warning("proving fields left off the index row for %s", rec.get("id"))
    return row


def append_index(plane: CompanyPlane, rec: dict) -> None:
    """Upsert this intent's row (spec 01: kept on every write). A damaged or missing index is rebuilt from the files instead."""
    with locked(plane):
        try:
            doc = read_json_strict(_index_file(plane), dict)
        except (OSError, ValueError):
            doc = None
        if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
            rebuild_index(plane, "missing or damaged")
            return
        doc["rows"] = [r for r in doc["rows"] if r.get("id") != rec["id"]] + [_with_proving(plane, rec)]
        write_json_atomic(_index_file(plane), doc)


def _ids_on_disk(plane: CompanyPlane) -> list[str]:
    try:
        return sorted(p.name for p in intents_dir(plane).iterdir() if p.is_dir() and ID_RE.fullmatch(p.name))
    except OSError:
        return []


def rebuild_index(plane: CompanyPlane, reason: str = "rebuilt") -> dict:
    """Scan `intents/<id>/intent.json` and write the index again. An unreadable record is left out and logged."""
    with locked(plane):
        rows = []
        for i in _ids_on_disk(plane):
            try:
                rec = read_intent(plane, i)
            except Unreadable:
                log.warning("intent record %s could not be read; left out of the index", i)
                continue
            if rec:
                rows.append(_with_proving(plane, rec))
        doc = _doc(rows, reason)
        write_json_atomic(_index_file(plane), doc)
    try:  # FX5: a deleted intent leaves the map on the next graph build
        from sh_platform.graph.hooks import mark_dirty
        mark_dirty(plane)
    except Exception:  # noqa: BLE001 - the index never fails on the map
        log.warning("graph not marked for rebuild after the index rebuild")
    return doc


def read_index(plane: CompanyPlane) -> list[dict]:
    """Every row. Rebuilt when the file is missing, damaged, or the folder count differs (a crash between record and row)."""
    with locked(plane):
        try:
            doc = read_json_strict(_index_file(plane), dict)
        except (OSError, ValueError):
            doc = None
        ids = _ids_on_disk(plane)
        if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list) or doc.get("schema") != SCHEMA:
            doc = rebuild_index(plane, "missing, damaged or an older shape")
        elif {r.get("id") for r in doc["rows"]} != set(ids):
            doc = rebuild_index(plane, "folders and rows differ")
        return doc["rows"]


# ---- who may see what: file 05's matrix (visibility.py) decides; these are the store's thin adapters -----------------------

COMPANY_WIDE = "company-wide"  # the reserved area token (home.py): a company-wide intent is in every area
_SAFE = re.compile(r"[A-Za-z0-9_-]{1,80}")


def _vis():
    from sh_platform.intents import visibility  # visibility imports the request helpers; kept lazy so the store loads first
    return visibility


class _Areas(frozenset):
    """The viewer's areas (ids and names, normalised, plus the company-wide token). It carries the matrix context and the plane, so
    tier_of applies the whole table with one profile read per request."""
    ctx = None
    plane = None


def context(plane: CompanyPlane, viewer: pview.Viewer):
    """visibility.context_for once per request, with the company-wide token among the viewer's areas."""
    c = _vis().context_for(plane, viewer)
    return dataclasses.replace(c, areas=c.areas | {COMPANY_WIDE})


def areas_of(plane: CompanyPlane, viewer: pview.Viewer) -> frozenset[str]:
    """The viewer's areas by tag (profile `people.<pid>.areas` through the account link), as ids and names, plus Company-wide."""
    ctx = context(plane, viewer)
    out = _Areas({pview.norm(a) for a in ctx.areas} | set(ctx.area_names))
    out.ctx, out.plane = ctx, plane
    return out


def _named(person: dict | None, viewer: pview.Viewer) -> bool:
    if not isinstance(person, dict):
        return False
    if person.get("account_id"):
        return bool(viewer.account_id) and person["account_id"] == viewer.account_id
    return bool(person.get("name")) and not viewer.shared_name and pview.norm(person["name"]) == pview.norm(viewer.name)


def _matrix_view(rec: dict, ctx) -> dict:
    """The record or index row as visibility reads it. share.py writes the account id as `person_id`, so each share row carries the
    account it opens for; an index row's live share list (`share_named`, expiries in `share_expires`) stands in for the share block."""
    p = rec.get("people") or {}
    if "share_named" in p:
        exp = rec.get("share_expires") or {}
        rows = [{"person_id": a, "account_id": a, "expires_at": exp.get(a)} for a in p["share_named"] or []]
    else:
        rows = [{**w, "account_id": w.get("account_id") or ctx.person_accounts.get(str(w.get("person_id") or "")) or w.get("person_id")}
                for w in (rec.get("share") or {}).get("who_may_open") or [] if isinstance(w, dict)]
    return {**rec, "share": {"who_may_open": rows}}


def _cell(x):
    return x.get("value") if isinstance(x, dict) and "value" in x else x


def _flat(v) -> list[str]:
    """Every name or person id in a cell, list or role map."""
    v = _cell(v)
    if isinstance(v, dict):
        return [y for x in v.values() for y in _flat(x)]
    if isinstance(v, list):
        return [y for x in v for y in _flat(x)]
    return [v] if isinstance(v, str) and v.strip() else []


def _peek(plane: CompanyPlane, *parts: str) -> dict:
    if not all(_SAFE.fullmatch(p) or p.endswith(".json") for p in parts):
        return {}
    try:
        d = read_json_strict(plane.path(*parts), dict)
    except (OSError, ValueError):  # CrossCompanyError is a PermissionError, an OSError
        return {}
    return d if isinstance(d, dict) else {}


def named_in_records(plane: CompanyPlane, rec: dict, viewer: pview.Viewer, ctx=None) -> bool:
    """A person a record of this intent names as an owner or confirmer reads the intent as a participant, or they could not confirm what
    they are asked to: the process owner (processes.json), the source owner (the baseline's data_sources.json), the six charter roles,
    a Lens question's to_person, the governed state's named owners of the baseline's measures. Names or profile person ids both match.
    ponytail: up to five small reads per record, only when nothing else already gives content; an index of named people if lists slow."""
    if not viewer.account_id:
        return False
    ctx = ctx or _vis().context_for(plane, viewer)
    mine = {pid for pid, a in ctx.person_accounts.items() if a == viewer.account_id} | {viewer.account_id}
    me = lambda v: v in mine or (bool(viewer.name) and not viewer.shared_name and pview.norm(v) == pview.norm(viewer.name))  # noqa: E731
    iid, refs = str(rec.get("id") or ""), rec.get("refs") or {}
    found: list = [p.get("owner") for p in _peek(plane, "intents", iid, "processes.json").get("processes") or [] if isinstance(p, dict)]
    found += [q.get("to_person") or q.get("to") for q in _peek(plane, "intents", iid, "lens_questions.json").get("questions") or []
              if isinstance(q, dict)]
    sids = refs.get("wall_session_ids") or []
    if sids and isinstance(sids[0], str):
        found.append(_peek(plane, "intents", "m1_intent", "roles", f"{sids[0]}.json").get("roles"))
    for bid in refs.get("baseline_ids") or []:
        if isinstance(bid, str):
            found += [s.get("source_owner") for s in (_peek(plane, "intents", "m2_baseline", bid, "data_sources.json").get("sources") or {}).values()
                      if isinstance(s, dict)]
            found += [k.get("owners") for k in _peek(plane, "intents", "m2_baseline", bid, "governed_state.json").values() if isinstance(k, dict)]
    return any(me(v) for v in _flat(found))


def columns(rec: dict, viewer: pview.Viewer, ctx, plane: CompanyPlane | None = None) -> tuple[dict | None, dict]:
    """(the ten matrix cells or None, the view they were read from). With a plane, a person named in the intent's records holds the
    participant row (on records only; an index row has no refs)."""
    V = _vis()
    view = _matrix_view(rec, ctx)
    cols = V.columns_for(None, view, viewer, ctx)
    if (plane is not None and (cols is None or cols["content"] != "Y") and rec.get("state") != "draft" and "rev" not in rec
            and named_in_records(plane, rec, viewer, ctx)):
        p = view.get("people") or {}
        view["people"] = {**p, "participants": [*(p.get("participants") or []), {"account_id": viewer.account_id, "name": viewer.name}]}
        cols = V.columns_for(None, view, viewer, ctx)
    return cols, view


def _tier(cols: dict | None) -> str | None:
    if cols is None:
        return None
    if cols["content"] == "Y":
        return "content"
    if cols["people"] in ("all", "organiser", "speakers"):
        return "card"
    return "exists" if cols["title"] == "Y" else None  # the company admin alone: exists; the super admin alone: None (control routes)


def tier_of(rec: dict, viewer: pview.Viewer, areas: frozenset[str]) -> str | None:
    """`content`, `card`, `exists` or None (not seen at all), from file 05's matrix. Works on a record or an index row. `areas` is
    areas_of(plane, viewer); a plain set of area names still works (no person-id map, no named-in-records check)."""
    ctx = getattr(areas, "ctx", None) or _vis().Context(areas=frozenset(areas) | {COMPANY_WIDE})
    return _tier(columns(rec, viewer, ctx, getattr(areas, "plane", None))[0])


# ---- account ids never leave (SEC0 #4): another person is shown by name and person id; the viewer keeps their own account id -------------
_HEX32 = re.compile(r"[0-9a-f]{32}")
_ACCOUNT_KEYS = frozenset({"account_id", "account", "created_by", "opened_by", "by", "by_account", "from_id", "to_id", "invited_by", "person_id",
                           "decided_by", "confirmed_by", "signed_by", "target", "read_by", "revoked_by", "raised_by", "owner_picked_by"})


def refs_of(plane: CompanyPlane) -> dict[str, str]:
    """account id -> profile person id, for every profile person linked to an account."""
    from sh_platform.profile import store as pstore
    from sh_platform.profile.links import _account_of
    try:
        people = pstore.raw(plane)["people"]
    except (OSError, ValueError, KeyError):
        return {}
    return {a: pid for pid, p in people.items() if isinstance(a := _account_of(p), str) and a}


def public_ref(account_id: str, refs: dict[str, str]) -> str:
    """The person id shown for an account: the profile person id, else a one-way reference that never reveals the account."""
    import hashlib
    return refs.get(account_id) or "acct-" + hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:16]


def account_for(ref: str, refs: dict[str, str], accounts) -> str | None:
    """Back from what a screen sends (a person id, the one-way reference, or the viewer's own account id) to the account id."""
    accounts = set(accounts)
    if ref in accounts:
        return ref
    by_pid = {pid: a for a, pid in refs.items()}
    if ref in by_pid:
        return by_pid[ref]
    return next((a for a in accounts if ref.startswith("acct-") and public_ref(a, {}) == ref), None)


def mask_accounts(node, viewer: pview.Viewer, refs: dict[str, str] | None = None):
    """A copy of `node` with every other person's account id swapped for their person id (keys and values), and `is_me` on the viewer's own
    person objects. Accounts are found from the profile links (`refs`) and from the keys that carry them."""
    refs = refs or {}
    found = set(refs)

    def collect(n) -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                if k in _ACCOUNT_KEYS and isinstance(v, str) and _HEX32.fullmatch(v):
                    found.add(v)
                collect(v)
        elif isinstance(n, list):
            for x in n:
                collect(x)
    collect(node)
    found.discard(viewer.account_id)
    swap = lambda v: public_ref(v, refs) if isinstance(v, str) and v in found else v  # noqa: E731

    def walk(n):
        if isinstance(n, dict):
            out = {swap(k): walk(v) for k, v in n.items()}
            if viewer.account_id and n.get("account_id") == viewer.account_id:
                out["is_me"] = True
            return out
        if isinstance(n, list):
            return [walk(x) for x in n]
        return swap(n)
    return walk(node)


def cut(rec: dict, tier: str, viewer: pview.Viewer, ctx=None) -> dict:
    """The record at the viewer's tier. Content: the record, share tokens and others' rating authors removed. Below content:
    visibility.read_intent (the matrix columns), without the closure (b03's /content serves what_came_out and next) and, at `exists`
    (the company admin alone), without the people. A caller with no context gets the same-area reading, the least a viewer who may
    see the intent holds."""
    if tier == "content":
        out = {k: v for k, v in rec.items() if k != "share"}
        share = rec.get("share") or {}
        organiser = ((rec.get("people") or {}).get("organiser") or {})
        mine = isinstance(organiser, dict) and organiser.get("account_id") == viewer.account_id
        if mine or pview.ADMIN in viewer.roles:  # link hashes never leave the store, even for these two (SEC0 #6)
            out["share"] = {**share, **{k: [{x: y for x, y in w.items() if x not in ("token_hash", "hash")} for w in share.get(k) or []]
                                        for k in ("who_may_open", "entries")}}
        else:  # a named visitor or participant sees only that a share exists, never the log, notes or fingerprints (T28 defect A)
            # spec 11 rule 4: a visitor never sees the organiser's other shares, only that this one opens for them
            out["share"] = {"shared_with_you": any(isinstance(w, dict) and viewer.account_id and viewer.account_id in (w.get("person_id"), w.get("account_id"))
                                                   for w in share.get("who_may_open") or [])}
        lead = mine or _named((rec.get("people") or {}).get("sponsor"), viewer)
        # ratings (T09, spec 10 rule 4): everyone keeps their own; the organiser and sponsor see signed scores only, never an
        # individual anonymous one (anonymous scores reach them only through the aggregate from three)
        out["ratings"] = [r if r.get("by") == viewer.account_id else {k: v for k, v in r.items() if k != "by"}
                          for r in rec.get("ratings") or []
                          if r.get("by") == viewer.account_id or (lead and not r.get("anonymous"))]
        if not lead:
            out.pop("rating", None)
        elif isinstance(out.get("rating"), dict):  # who rated stays private even from the organiser and sponsor: counts only
            out["rating"] = {k: (len(v) if k in ("rated", "waived", "reminded") and isinstance(v, list) else v) for k, v in out["rating"].items()}
        if isinstance(out.get("closure"), dict):  # approver link hashes never leave the store
            out["closure"] = {k: v for k, v in out["closure"].items() if k != "links"}
        if rec.get("state") != "draft":  # a draft reaches its starter alone, who picked those people from the company list
            out = mask_accounts(out, viewer, {a: pid for pid, a in (getattr(ctx, "person_accounts", None) or {}).items()})
        return {**out, "tier": tier}
    V = _vis()
    ctx = ctx or V.Context(areas=frozenset(a for a in rec.get("areas") or [] if isinstance(a, str)))
    out = V.read_intent(None, _matrix_view(rec, ctx), viewer, ctx) or {"id": rec["id"], "type": rec["type"], "state": rec["state"]}
    out.pop("closure", None)
    if tier == "exists":
        out.pop("people", None)
    return {**out, "tier": tier}


def list_for_viewer(plane: CompanyPlane, viewer: pview.Viewer, *, type: str | None = None, state: str | None = None,
                    area: str | None = None, mine: bool = False, view: str | None = None) -> list[dict]:
    """List rows the viewer may see at all, newest first. `view`: running (draft, open, in session, closing), finished (closed),
    past (closed or cancelled)."""
    areas, shown = areas_of(plane, viewer), []
    group = {"running": ("draft", "open", "in_session", "closing"), "finished": ("closed",), "past": ("closed", "cancelled")}.get(view or "")
    for r in read_index(plane):
        tier = tier_of(r, viewer, areas)
        if tier is None or (type and r["type"] != type) or (state and r["state"] != state) or (group and r["state"] not in group):
            continue
        if area and pview.norm(area) not in {pview.norm(a) for a in r["areas"]}:
            continue
        if mine and not (r["created_by"] == viewer.account_id or any(_named(r["people"].get(s), viewer) for s in SLOTS)
                         or any(_named(x, viewer) for k in LISTS for x in r["people"].get(k) or [])):
            continue
        shown.append({"id": r["id"], "type": r["type"], "title": r["title"], "purpose": r["purpose"], "state": r["state"],
                      "areas": r["areas"], "organiser": r["organiser"]["name"], "time_box": {"ends": r["ends"]}, "tier": tier,
                      "updated_at": r["updated_at"]})
    return sorted(shown, key=lambda x: x["updated_at"], reverse=True)
