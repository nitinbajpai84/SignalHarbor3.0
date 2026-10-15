"""Share link and visitor view (spec 11). The organiser shares an intent with named people, an area, or a signed-in link; a visitor reads it
read only and may leave a note. Rows live in the intent record under `share` (entries, log, notes), written through the intent store.

The link mechanism is the approver link's (modules/m1_intent/store/charter.py: SHA-256 hash only, constant-time match over every row,
revoke, expiry, one answer for every miss, failure lock through LoginThrottle, header-only travel), lifted here into `digest`,
`new_token`, `match`, `gone_why` so the intent share has one definition. The charter keeps its own copy: that file is not this card's.
The company comes from the visitor's signed-in session, so no control index is needed (spec 11 names `_control/share_index.json`; skipped).
"""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from modules.m1_intent.store.notes import NoteStore
from sh_platform.auth.sessions import LoginThrottle
from sh_platform.intents import _plane, _viewer, store as S
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import CrossCompanyError
from sh_platform.profile import store as profile_store
from sh_platform.profile import view as pview
from sh_platform.public_link import full_url

log = logging.getLogger(__name__)
router = APIRouter()

TOKEN = re.compile(r"sh-((?:ini|bra|pul|prb|dec)-[0-9a-f]{32})-([A-Za-z0-9_-]{43})")
SHAREABLE = ("open", "in_session", "closing", "closed", "cancelled")
NOTE_MAX = 1000          # spec 11 open question 12: proposal, not decided
DEDUPE = timedelta(minutes=10)  # spec 11 open question 6: proposal, not decided
INVALID = ("link_invalid", "This link is not working. Please ask for a new one.", 404)
ENDED = ("share_ended", "This share has ended.", 409)
LOCKED = ("too_many_tries", "Too many tries. Please wait a minute, then open your link again.", 429)
SIGN_IN = ("sign_in", "Please sign in to open this.", 401)
NOT_FOUND = ("not_found", "We could not find that.", 404)
NOT_ORGANISER = ("forbidden", "Only the organiser can do this.", 403)
GUARD = {"draft": "This intent is a draft. Open it before you share it.",
         "cancelled": "This intent was cancelled. A share shows the reason."}
NEVER = ["Sealed cards (a count only)", "Anonymous authors (shown as Anonymous)", "Restricted measures (a count only)",
         "Other intents, the share log and other visitors' notes"]
LABELS = {"sponsor": "Sponsor", "decider": "Decider", "owner": "Owner", "reporter": "Reporter", "participants": "Participant",
          "advisers": "Adviser", "observers": "Observer", "affected": "Affected"}
# outcome keys a visitor may read (text only; every author or account key is dropped below)
OUTCOME_KEYS = ("goal", "why", "statement", "good_outcome", "chosen", "runners_up", "ideas_kept", "what", "root_cause", "fix", "question",
                "options")
HIDDEN_KEYS = frozenset({"by", "author", "account_id", "decided_by", "raised_by", "anonymous"})


class Refuse(Exception):
    def __init__(self, spec, status=None):
        self.code, self.message, self.status = spec[0], spec[1], status or spec[2]


def _plain(e: Refuse) -> JSONResponse:
    return JSONResponse({"error": e.code, "message": e.message}, status_code=e.status)


# ---- the one link mechanism -----------------------------------------------------------------------------------------------

def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(intent_id: str) -> str:
    return f"sh-{intent_id}-{secrets.token_urlsafe(32)}"


def match(entries: list[dict], token_hash: str) -> dict | None:
    found = None
    for e in entries:  # compare every link row: the time taken does not depend on which matched
        if e.get("hash") and hmac.compare_digest(e["hash"], token_hash):
            found = e
    return found


def _t(v) -> datetime:
    return datetime.fromisoformat(v)


def gone_why(e: dict, now: datetime) -> str | None:
    """Why a row no longer opens anything: `revoked`, `replaced`, `expired`, or None when it is live."""
    if e.get("state") != "live":
        return "replaced" if e.get("replaced_by") else "revoked"
    return "expired" if _t(e["expires_at"]) <= now else None


# ---- records --------------------------------------------------------------------------------------------------------------

def _end_of_day(day: str, now: datetime) -> str:
    try:
        d = date.fromisoformat(day)
    except (TypeError, ValueError):
        raise Refuse(("bad_date", "Choose when this share ends.", 422)) from None
    end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)  # company time zone is not in the profile yet: UTC
    if end <= now:
        raise Refuse(("bad_date", "Choose a date that has not passed.", 422))
    return end.isoformat()


def _sync(share: dict, now: datetime) -> None:
    """`link` is the id of the live link row; `who_may_open` is the live person rows (what the intent store reads for named access)."""
    live = [e for e in share["entries"] if not gone_why(e, now)]
    share["link"] = next((e["id"] for e in live if e["kind"] == "link"), None)
    share["who_may_open"] = [{"person_id": e["target"], "label": e.get("label", ""), "token_hash": "", "expires_at": e["expires_at"],
                              "revoked_at": None, "created_by": e["created_by"]} for e in live if e["kind"] == "person"]


def _share(rec: dict) -> dict:
    s = dict(rec.get("share") or {})
    for k in ("entries", "log", "notes"):
        s[k] = list(s.get(k) or [])
    return s


def _write(plane, intent_id: str, change) -> dict:
    for _ in range(2):  # one retry when someone else saved between the read and the write
        rec = S.read_intent(plane, intent_id)
        if rec is None:
            raise Refuse(NOT_FOUND)
        try:
            return S.update_intent(plane, intent_id, rec["version"], change)
        except S.VersionConflict:
            continue
    raise Refuse(("conflict", S.CONFLICT, 409))


def _names(accounts, company: str) -> dict:
    return {a["account_id"]: a["display_name"] for a in accounts.in_company(company)}


def _in_intent(rec: dict, acct: dict) -> bool:
    p = rec.get("people") or {}
    mine = [p.get(k) for k in ("organiser", "sponsor", "decider", "owner", "reporter")]
    for k in ("participants", "advisers", "observers") + (("affected",) if rec.get("affected_may_read") else ()):
        mine += p.get(k) or []
    return any(isinstance(x, dict) and (x.get("account_id") == acct["account_id"] or (
        not x.get("account_id") and pview.norm(x.get("name", "")) == pview.norm(acct["display_name"]))) for x in mine)


def _profile_people(plane) -> list[dict]:
    out = []
    for p in (profile_store.load(plane).get("people") or {}).values():
        out.append({"name": pview._v(p, "name") or "", "role": pview._v(p, "role") or "", "team": pview._v(p, "team") or "",
                    "account_id": pview._v(p, "account_id")})
    return out


def _person_ids(plane, viewer) -> list[str]:
    """Profile person ids linked to the viewer's account (a share row may name the person, not the account)."""
    return [pid for pid, p in (profile_store.load(plane).get("people") or {}).items()
            if viewer.account_id and pview._v(p, "account_id") == viewer.account_id]


def _teams(plane, viewer) -> list[str]:
    doc = profile_store.load(plane).get("people") or {}
    return [t for pid in _person_ids(plane, viewer) if isinstance(t := pview._v(doc[pid], "team"), str) and t]


def _areas(plane) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in _profile_people(plane):
        if p["team"]:
            a = seen.setdefault(pview.norm(p["team"]), {"area": p["team"], "head_count": 0})
            a["head_count"] += 1
    return sorted(seen.values(), key=lambda a: a["area"])


def _pickable(plane, accounts, company: str, rec: dict, now: datetime) -> list[dict]:
    prof = _profile_people(plane)
    shared = {e["target"] for e in (rec.get("share") or {}).get("entries") or [] if e["kind"] == "person" and not gone_why(e, now)}
    out = []
    for a in accounts.in_company(company):
        if a.get("disabled"):
            continue
        p = next((x for x in prof if x["account_id"] == a["account_id"] or pview.norm(x["name"]) == pview.norm(a["display_name"])), {})
        out.append({"id": a["account_id"], "name": a["display_name"], "role": p.get("role") or ", ".join(a["roles"]),
                    "department": p.get("team") or "",
                    "status": "in_intent" if _in_intent(rec, a) else "shared" if a["account_id"] in shared else "pickable"})
    return sorted(out, key=lambda x: x["name"])


def create_share(plane, accounts, company: str, rec: dict, actor: str, targets: list, day: str, now: datetime) -> tuple[dict, str | None]:
    """Writes one row per target. Returns (record, the new link's token or None). Refuses a draft, a bad date, an unknown or already-in person."""
    if rec["state"] not in SHAREABLE:
        raise Refuse(("draft", GUARD["draft"], 409))
    expires = _end_of_day(day, now)
    if not isinstance(targets, list) or not targets or len(targets) > 200:
        raise Refuse(("nothing_chosen", "Nothing chosen yet.", 422))
    people = {p["id"]: p for p in _pickable(plane, accounts, company, rec, now)}
    areas = {pview.norm(a["area"]): a for a in _areas(plane)}
    rows, token = [], None
    for t in targets:
        kind = t.get("kind") if isinstance(t, dict) else None
        base = {"id": secrets.token_hex(8), "kind": kind, "created_by": actor, "created_at": now.isoformat(), "expires_at": expires,
                "state": "live", "revoked_by": None, "revoked_at": None, "replaced_by": None,
                "version_seen": (rec.get("closure") or {}).get("closed_at") if rec["state"] == "closed" else None}
        if kind == "person":
            p = people.get(t.get("target"))
            if p is None or p["status"] == "in_intent":
                raise Refuse(("bad_person", "That person is already in this intent or could not be found.", 422))
            rows.append({**base, "target": p["id"], "label": p["name"]})
        elif kind == "area":
            a = areas.get(pview.norm(t.get("target") or ""))
            if a is None:
                raise Refuse(("bad_area", "We could not find that area.", 422))
            rows.append({**base, "target": a["area"], "label": a["area"], "head_count": a["head_count"]})
        elif kind == "link" and token is None:
            token = new_token(rec["id"])
            rows.append({**base, "target": None, "label": "Link", "hash": digest(token)})
        elif kind != "link":
            raise Refuse(("bad_target", "That could not be read. Please try again.", 422))

    def change(r):
        s = _share(r)
        for new in rows:  # one live row per person, per area, per link maker
            for old in s["entries"]:
                if old["state"] == "live" and old["kind"] == new["kind"] and old.get("target") == new["target"]:
                    old.update(state="revoked", revoked_by=actor, revoked_at=now.isoformat(), replaced_by=new["id"])
        s["entries"] += rows
        _sync(s, now)
        r["share"] = s
    return _write(plane, rec["id"], change), token


def withdraw(plane, rec: dict, actor: str, which: str, now: datetime) -> dict:
    """One row by id, or every live row with which="all"."""
    def change(r):
        s, hit = _share(r), False
        for e in s["entries"]:
            if not gone_why(e, now) and which in ("all", e["id"]):
                e.update(state="revoked", revoked_by=actor, revoked_at=now.isoformat())
                hit = True
        if not hit:
            raise Refuse(NOT_FOUND)
        _sync(s, now)
        r["share"] = s
    return _write(plane, rec["id"], change)


def mark_read(plane, rec: dict, actor: str, note_id: str, now: datetime) -> dict:
    def change(r):
        s = _share(r)
        n = next((n for n in s["notes"] if n["id"] == note_id), None)
        if n is None:
            raise Refuse(NOT_FOUND)
        n.update(read_at=n.get("read_at") or now.isoformat(), read_by=n.get("read_by") or actor)
        r["share"] = s
    return _write(plane, rec["id"], change)


# ---- the organiser's panel ------------------------------------------------------------------------------------------------

def panel(plane, accounts, company: str, company_name: str, rec: dict, now: datetime) -> dict:
    s = _share(rec)
    who = _names(accounts, company)
    log_by: dict = {}
    for l in s["log"]:
        e = next((x for x in s["entries"] if x["id"] == l["entry_id"]), {})
        row = log_by.setdefault(l["account_id"], {"name": who.get(l["account_id"], "Someone"), "first": l["at"], "last": l["at"],
                                                  "times": 0, "routes": []})
        route = {"person": "name", "area": "area", "link": "link"}.get(e.get("kind"), "")
        if route and route not in row["routes"]:
            row["routes"].append(route)  # every route the person used, in the order first used
        row["times"] += 1
        row["last"] = max(row["last"], l["at"])
        row["first"] = min(row["first"], l["at"])
    rows = [{"id": e["id"], "kind": e["kind"], "who": e.get("label", ""), "made_by": who.get(e["created_by"], ""), "made_on": e["created_at"],
             "ends_on": e["expires_at"],
             "state": {"revoked": "withdrawn", "replaced": "ended", "expired": "ended"}.get(gone_why(e, now) or "", "live"),
             "opens": sum(1 for l in s["log"] if l["entry_id"] == e["id"])} for e in s["entries"]]
    made = [e for e in s["entries"] if not e.get("replaced_by")]
    n = lambda k: sum(1 for e in made if e["kind"] == k)  # noqa: E731
    heads = [e.get("head_count") for e in made if e["kind"] == "area"]
    known = not n("link") and all(h is not None for h in heads)
    return {"intent": {"id": rec["id"], "title": rec["title"], "state": rec["state"]}, "guard": GUARD.get(rec["state"]),
            "company": company_name, "never": NEVER, "areas": _areas(plane), "people": _pickable(plane, accounts, company, rec, now),
            "entries": rows,
            "counts": {"people": n("person"), "areas": n("area"), "links": n("link"), "opened": len(log_by),
                       "of": n("person") + sum(heads) if known else None, "notes": len(s["notes"]),
                       "unread": sum(1 for x in s["notes"] if not x.get("read_at")), "live": sum(1 for r in rows if r["state"] == "live")},
            "opens": sorted(({k: v for k, v in r.items() if k != "routes"} | {"through": " and ".join(r["routes"])} for r in log_by.values()),
                            key=lambda r: r["first"]),
            "notes": [{"id": x["id"], "name": who.get(x["by"], "Someone"), "at": x["at"], "text": x["text"],
                       "read": bool(x.get("read_at"))} for x in s["notes"]]}


# ---- the visitor ----------------------------------------------------------------------------------------------------------

def _throttle(app) -> LoginThrottle:
    if getattr(app.state, "share_throttle", None) is None:
        app.state.share_throttle = LoginThrottle()
    return app.state.share_throttle


def _ground(plane, viewer, intent_id: str, token: str | None, now: datetime) -> tuple[dict, dict]:
    """(record, row) for a visitor who may open it right now. Raises Refuse INVALID (nothing matches), ENDED (matched, no longer live)."""
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        rec = None
    if rec is None or rec["state"] == "draft":
        raise Refuse(INVALID)
    entries = _share(rec)["entries"]
    if token:
        hit = match(entries, digest(token))
        mine = [hit] if hit else []
    else:
        areas, ids = S.areas_of(plane, viewer), {viewer.account_id, *_person_ids(plane, viewer)} - {None}
        areas = areas | {pview.norm(t) for t in _teams(plane, viewer)}  # the picker offers teams, the profile tags ids: either admits
        mine = [e for e in entries if (e["kind"] == "person" and e["target"] in ids)
                or (e["kind"] == "area" and pview.norm(e["target"]) in areas)]
    if not mine:
        raise Refuse(INVALID)
    live = [e for e in mine if not gone_why(e, now)]
    if not live:
        raise Refuse(ENDED)
    return rec, live[0]


def _clean(node):
    if isinstance(node, dict):
        return {k: _clean(v) for k, v in node.items() if k not in HIDDEN_KEYS}
    return [_clean(v) for v in node] if isinstance(node, list) else node


def _wall(plane, rec: dict) -> tuple[dict | None, int]:
    """(the read-only content, sealed count). No card id, no author id and no time order of anonymous cards leaves."""
    sealed = 0
    if rec["type"] == "pulse":
        items = []
        folder = plane.path("intents", rec["id"], "weeks")
        for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            w = read_json_strict(p, dict) or {}
            items += [{"week": w.get("week_key"), "kind": i.get("kind"), "text": i.get("text", ""), "fate": i.get("fate"),
                       "reason": i.get("fate_reason")} for i in w.get("items") or []]
        return ({"kind": "weeks", "items": sorted(items, key=lambda i: (i["week"] or "", i["kind"] or "", i["text"]))} if items else None), 0
    lanes = []
    for sid in (rec.get("refs") or {}).get("wall_session_ids") or []:
        if not isinstance(sid, str) or not re.fullmatch(r"[0-9a-f]{32}", sid):
            continue
        wall = read_json_strict(plane.path("intents", "m1_intent", "wall", f"{sid}.json"), dict) or {}
        # the room's own read: it applies an anonymous session's rule and carries `restricted` (sealed) from the note itself
        notes = {n["id"]: n for n in NoteStore(plane).board(sid)}
        for lane in wall.get("lanes") or []:
            named, anon = [], []
            for c in lane.get("cards") or []:
                if c.get("sealed") or notes.get(c.get("id"), {}).get("restricted") is True:
                    sealed += 1
                    continue
                n = notes.get(c.get("id"), {})
                is_anon = c.get("author") in (None, "", "Anonymous") or bool(n.get("anonymous"))
                card = {"text": n.get("text") or c.get("text") or "", "author": "Anonymous" if is_anon else c["author"]}
                (anon if is_anon else named).append(card)
            lanes.append({"lane": lane.get("lane"), "cards": named + sorted(anon, key=lambda c: c["text"])})
    return ({"kind": "wall", "lanes": lanes} if any(l["cards"] for l in lanes) else None), sealed


def visitor_payload(plane, accounts, company: str, rec: dict, entry: dict, now: datetime) -> dict:
    who, p, c = _names(accounts, company), rec.get("people") or {}, rec.get("closure") or {}
    people = [{"name": x["name"], "role": LABELS.get(k, "Organiser")} for k, x in [("organiser", p.get("organiser"))] +
              [(k, p.get(k)) for k in ("sponsor", "decider", "owner", "reporter")] if isinstance(x, dict) and x.get("name")]
    people += [{"name": x["name"], "role": LABELS[k]} for k in ("participants", "advisers", "observers", "affected") for x in p.get(k) or []
               if isinstance(x, dict) and x.get("name")]
    out = {"banner": {"organiser": (p.get("organiser") or {}).get("name", ""), "ends": entry["expires_at"]},
           "intent": {"title": rec["title"], "purpose": rec["purpose"], "type": rec["type"], "state": rec["state"], "areas": rec.get("areas") or []},
           "people": people, "stages": [], "wall": None, "outcome": None, "sealed": 0, "restricted": 0, "closure": None, "cancelled": None,
           "note_max": NOTE_MAX}
    if rec["state"] == "cancelled":
        by = c.get("closed_by") if isinstance(c.get("closed_by"), str) else ""
        out["cancelled"] = {"by": who.get(by, "" if re.fullmatch(r"[0-9a-f]{32}", by) else by),
                            "on": c.get("closed_at"), "reason": c.get("cancel_reason") or ""}
        return out
    out["stages"] = [{"key": s["key"], "name": s.get("name") or s["key"].replace("_", " "), "state": s.get("state"),
                      "opened_at": s.get("opened_at"), "closed_at": s.get("closed_at")} for s in rec.get("stages") or []]
    out["wall"], out["sealed"] = _wall(plane, rec)
    out["outcome"] = _clean({k: v for k, v in (rec.get("outcome") or {}).items() if k in OUTCOME_KEYS and v not in (None, "", [])}) or None
    if rec["state"] == "closed":
        out["closure"] = {"summary": c.get("summary", ""), "why_it_happened": c.get("why_it_happened", ""), "what_came_out": c.get("what_came_out", ""),
                          "next": [{"kind": n.get("kind"), "reason": n.get("reason", "")} for n in c.get("next") or []],
                          "closed_at": c.get("closed_at")}
    return out


def _visit(request: Request, intent_id: str | None, token: str | None, note: str | None) -> dict | JSONResponse:
    """The one visitor entry: opens (and logs) or, with `note`, writes a note. Order: sign-in, failure lock, shape, then the match."""
    app, st = request.app, request.state
    if not getattr(st, "account_id", None) or not getattr(st, "company_id", None):
        return _plain(Refuse(SIGN_IN))
    key = request.client.host if request.client else "unknown"
    throttle = _throttle(app)
    try:
        if throttle.locked(key):
            raise Refuse(LOCKED)
        if token is not None:
            m = TOKEN.fullmatch(token)
            intent_id = m.group(1) if m else None
        if not intent_id or not S.ID_RE.fullmatch(str(intent_id)):
            throttle.failed(key)
            raise Refuse(INVALID)
        try:
            plane, viewer = _plane(request), _viewer(request)
        except (PermissionError, CrossCompanyError):
            throttle.failed(key)
            raise Refuse(INVALID) from None
        now = datetime.now(timezone.utc)
        try:
            rec, entry = _ground(plane, viewer, intent_id, token, now)
        except Refuse as e:
            if e.code == INVALID[0]:
                throttle.failed(key)
            raise
        me = viewer.account_id
        if note is None:
            def change(r):
                s = _share(r)
                last = [l for l in s["log"] if l["account_id"] == me and l["entry_id"] == entry["id"]]
                if not last or now - _t(last[-1]["at"]) >= DEDUPE:
                    s["log"].append({"entry_id": entry["id"], "account_id": me, "at": now.isoformat()})
                    r["share"] = s
            _write(plane, rec["id"], change)
            return visitor_payload(plane, app.state.account_store, st.company_id, rec, entry, now)
        text = note.strip()
        if not text or len(text) > NOTE_MAX:
            raise Refuse(("bad_note", f"Write a note of up to {NOTE_MAX} characters.", 422))

        def add(r):
            s = _share(r)
            s["notes"].append({"id": secrets.token_hex(8), "entry_id": entry["id"], "by": me, "at": now.isoformat(), "text": text,
                               "read_at": None, "read_by": None})
            r["share"] = s
        _write(plane, rec["id"], add)
        return {"sent": True, "to": (rec["people"].get("organiser") or {}).get("name", "")}
    except Refuse as e:
        return _plain(e)


def visitor_open(request: Request, intent_id, token):
    return _visit(request, intent_id, token, None)


def visitor_note(request: Request, intent_id, token, text):
    return _visit(request, intent_id, token, text if isinstance(text, str) else "")


# ---- organiser routes -----------------------------------------------------------------------------------------------------

def _organiser(request: Request, intent_id: str):
    try:
        plane, viewer = _plane(request), _viewer(request)
    except (PermissionError, CrossCompanyError):
        raise Refuse(NOT_ORGANISER) from None
    try:
        rec = S.read_intent(plane, intent_id)
    except S.Unreadable:
        rec = None
    if rec is None:
        raise Refuse(NOT_FOUND)
    if not S._named((rec.get("people") or {}).get("organiser"), viewer):
        raise Refuse(NOT_FOUND if S.tier_of(rec, viewer, S.areas_of(plane, viewer)) is None else NOT_ORGANISER)
    return plane, viewer, rec


def _name(request: Request) -> str:
    return (request.app.state.entitlements.company(request.state.company_id) or {}).get("name", "your company")


def _refs(request, plane) -> dict:
    """Every company account to the person id screens see (SEC0 #4: account ids never leave, even for the organiser)."""
    refs = S.refs_of(plane)
    return {a["account_id"]: S.public_ref(a["account_id"], refs) for a in request.app.state.account_store.in_company(request.state.company_id)}


def _panel(request, plane, rec, extra=None) -> dict:
    rec = S.read_intent(plane, rec["id"])
    out = {**panel(plane, request.app.state.account_store, request.state.company_id, _name(request), rec, datetime.now(timezone.utc)),
           **(extra or {})}
    return S.mask_accounts(out, _viewer(request), _refs(request, plane))


def _run(request, intent_id, fn):
    try:
        plane, viewer, rec = _organiser(request, intent_id)
        return fn(plane, viewer, rec)
    except Refuse as e:
        return _plain(e)


def _get(request, intent_id):
    return _run(request, intent_id, lambda plane, viewer, rec: _panel(request, plane, rec))


def _post(request, intent_id, body):
    body = body if isinstance(body, dict) else {}

    def go(plane, viewer, rec):
        now = datetime.now(timezone.utc)
        if body.get("mark_read"):
            mark_read(plane, rec, viewer.account_id, str(body["mark_read"]), now)
            return _panel(request, plane, rec)
        back = {ref: a for a, ref in _refs(request, plane).items()}  # the screen picks by person id; rows keep the account
        targets = body.get("targets")
        if isinstance(targets, list):
            targets = [{**t, "target": back.get(t.get("target"), t.get("target"))} if isinstance(t, dict) and t.get("kind") == "person" else t
                       for t in targets]
        _, token = create_share(plane, request.app.state.account_store, request.state.company_id, rec, viewer.account_id,
                                targets, body.get("expires_at"), now)
        link = {"url": full_url(request, f"/centre/shared/t/{token}"), "expires_at": _end_of_day(body["expires_at"], now)} if token else None
        return _panel(request, plane, rec, {"link": link})
    return _run(request, intent_id, go)


def _withdraw(request, intent_id, which):
    def go(plane, viewer, rec):
        withdraw(plane, rec, viewer.account_id, which, datetime.now(timezone.utc))
        return _panel(request, plane, rec)
    return _run(request, intent_id, go)


@router.get("/api/intents/{intent_id}/share")
async def get_share(request: Request, intent_id: str):
    return await run_in_threadpool(_get, request, intent_id)


@router.post("/api/intents/{intent_id}/share")
async def post_share(request: Request, intent_id: str):
    try:
        body = await request.json()
    except ValueError:
        body = None
    return await run_in_threadpool(_post, request, intent_id, body)


@router.delete("/api/intents/{intent_id}/share/{token_id}")
async def delete_share(request: Request, intent_id: str, token_id: str):
    return await run_in_threadpool(_withdraw, request, intent_id, token_id)


@router.post("/api/intents/{intent_id}/share/withdraw")
async def post_withdraw(request: Request, intent_id: str):
    try:
        body = await request.json()
    except ValueError:
        body = None
    which = body.get("entry_id", "all") if isinstance(body, dict) else "all"
    return await run_in_threadpool(_withdraw, request, intent_id, str(which))


@router.post("/api/intents/{intent_id}/share/notes/{note_id}/read")
async def post_note_read(request: Request, intent_id: str, note_id: str):
    return await run_in_threadpool(_post, request, intent_id, {"mark_read": note_id})


# The visitor routes live in modules/m1_intent/api/shared.py (they must sit under /api/modules/m1_intent/). The module's api package
# is not this card's file, so the router is added to it here, once, until its __init__ includes shared.router itself.
try:
    from modules.m1_intent import api as _m1_api
    from modules.m1_intent.api import shared as _shared

    if not any(getattr(r, "path", "") == "/shared/view" for r in _m1_api.router.routes):
        _m1_api.router.include_router(_shared.router)
except ImportError:  # pragma: no cover
    log.warning("The visitor routes could not be added to module 1.")
