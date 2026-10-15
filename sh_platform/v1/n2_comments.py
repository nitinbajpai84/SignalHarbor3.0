"""N2 Comments with history. A comment hangs on one thing a person can see: a dashboard, a widget, an office line, a brief line, a case,
or any figure the trail knows (valuation, position, cash, nav, metric, tile).

Storage: `comments/events.jsonl` in the company plane, append-only. Events: add, edit, delete, raise. Nothing is rewritten, so every
earlier wording stays; the thread shown is folded from the events. An edited comment says "edited" and keeps its earlier wordings; a
deleted one says "deleted by X" and shows no words (the words stay in the file).
Who may see a thread = who may see the thing (`check`); the same check guards every write. It fails closed.
@Name (a name from the company people list) notifies that person on Today, only when they may see the thing as well.
Ids of the things: dashboard "dash-1234"; widget "dash-1234/<tile id>"; office_line and brief_line "<portfolio id>/<line key>"
(a line of the whole company, not one portfolio, uses "company/<line key>" and needs sight of every portfolio); case id or CASE-0001; trail kinds as the trail.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

log = logging.getLogger(__name__)
TRAIL_KINDS = ("valuation", "position", "cash", "nav", "metric", "tile")
KINDS = ("dashboard", "widget", "office_line", "brief_line", "case") + TRAIL_KINDS
MAX = 4000
_LOCK = threading.Lock()
ROUTE = {"dashboard": "/centre/consume/d/{}", "widget": "/centre/consume/d/{}", "case": "/centre/desk/{}"}


class Refused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ---- who may see the thing ------------------------------------------------------------------------------------------------------

def _portfolio_ok(plane, viewer, pid: str) -> bool:
    from sh_platform.v1 import e1_access
    if pid == "company":  # a whole-company line: only someone who sees every portfolio (the brief drops totals otherwise)
        with wh.connect(plane, read_only=True) as con:
            every = {str(r[0]) for r in con.execute("select id from portfolios").fetchall()}
        return e1_access.is_admin(viewer) or (bool(every) and every <= {str(p) for p in e1_access.visible_portfolios(plane, viewer)})
    return e1_access.level(plane, viewer, portfolio_id=pid) != "none"


def check(plane, viewer, kind: str, item_id: str) -> dict:
    """Prove the viewer may see the thing. Returns {id, portfolio_id, link}. Refused 400 (bad kind or id), 403 (not yours), 404 (not there)."""
    if kind not in KINDS:
        raise Refused(400, "Comments can go on a dashboard, a widget, a line or a case.")
    item_id = str(item_id or "").strip()
    if not item_id:
        raise Refused(400, "Say which one.")
    pid = None
    try:
        if kind in ("dashboard", "widget"):
            from sh_platform.v1 import cx_dash
            did = item_id.split("/")[0]
            rec = cx_dash._load(plane, cx_dash.find_pid(plane, did), did)
            if not (cx_dash.may_view(plane, viewer, rec) or ((rec.get("lifecycle") or {}).get("company_wide") and cx_dash._has_data(plane, viewer))):
                raise PermissionError
        elif kind in ("office_line", "brief_line"):
            pid, _, line = item_id.partition("/")
            if not line or (pid != "company" and not _uuid_ok(pid)):
                raise Refused(400, "A line is named by its portfolio and its key.")
            if not _portfolio_ok(plane, viewer, pid):
                raise PermissionError
            pid = None if pid == "company" else pid
        elif kind == "case":
            from sh_platform.v1 import e4_cases
            with wh.connect(plane) as con:
                item_id = e4_cases._resolve_ref(con, plane, item_id)
                row = e4_cases._row(con, item_id)
                if not e4_cases._can_see(plane, viewer, row, con):
                    raise PermissionError
            pid = str(row["portfolio_id"]) if row["portfolio_id"] else None
        else:  # a trail kind: the trail itself refuses what the person may not see
            from sh_platform.v1 import a5_trail
            a5_trail.trail(plane, viewer, kind, item_id)
    except PermissionError:
        raise Refused(403, "You do not have access to this.") from None
    except (LookupError, ValueError):
        raise Refused(404, "We could not find that.") from None
    except Refused as e:
        if e.status == 500:
            log.warning("comment target unreadable", exc_info=True)
        raise Refused(e.status, e.message) from None
    except Exception:  # noqa: BLE001 - fail closed
        log.warning("comment access check failed; denying", exc_info=True)
        raise Refused(403, "You do not have access to this.") from None
    link = ROUTE.get(kind, "").format(item_id.split("/")[0]) or None
    return {"id": item_id, "portfolio_id": pid, "link": link}


def _uuid_ok(v: str) -> bool:
    try:
        uuid.UUID(v)
        return True
    except ValueError:
        return False


# ---- storage --------------------------------------------------------------------------------------------------------------------

def _file(plane):
    return plane.path("comments", "events.jsonl")


def _append(plane, ev: dict) -> dict:
    ev = {"event": ev.pop("event"), "id": ev.pop("id", None) or uuid.uuid4().hex[:12], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **ev}
    f = _file(plane)
    with _LOCK:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev) + "\n")
    return ev


def events(plane) -> list[dict]:
    f = _file(plane)
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            log.warning("a comment line could not be read and was skipped")
    return out


# ---- people ---------------------------------------------------------------------------------------------------------------------

def people(plane) -> list[dict]:
    """The company people list: {id, name, account_id}. Only names; no email."""
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute("select id, display_name, external_identity_id from users where organization_id = ? and is_active order by display_name", [org_id(plane)]).fetchall()
    return [{"id": str(r[0]), "name": r[1], "account_id": r[2]} for r in rows if r[1]]


def mentioned(plane, text: str) -> list[dict]:
    """People named as @Name in the words (longest name first, so "@Mei Tan" is not read as "@Mei")."""
    out, taken = [], text
    for p in sorted(people(plane), key=lambda p: -len(p["name"])):
        pat = re.compile(r"@" + re.escape(p["name"]) + r"(?!\w)", re.I)
        if pat.search(taken):
            out.append(p)
            taken = pat.sub(" ", taken)
    return out


def _viewer_for(plane, person: dict):
    from sh_platform.auth.accounts import AccountStore
    from sh_platform.profile.view import Viewer
    roles: frozenset = frozenset()
    try:
        for a in AccountStore(plane.root.parent).in_company(plane.company_id):
            if a["account_id"] == person["account_id"] and not a.get("disabled"):
                roles = frozenset(a.get("roles") or [])
    except Exception:  # noqa: BLE001 - without roles the person is checked on data access alone
        log.warning("accounts could not be read for a mention", exc_info=True)
    return Viewer(person["name"], roles, False, person["account_id"])


def _notify_list(plane, kind: str, item_id: str, text: str, author_uid, already=()) -> tuple[list[str], list[str]]:
    """(user ids to tell, names left out because they cannot see the thing). The author is never told about their own comment."""
    tell, left = [], []
    for p in mentioned(plane, text):
        if p["id"] == author_uid or p["id"] in already:
            continue
        if _may(plane, p, kind, item_id):
            tell.append(p["id"])
        else:
            left.append(p["name"])
    return tell, left


def _may(plane, person: dict, kind: str, item_id: str) -> bool:
    try:
        check(plane, _viewer_for(plane, person), kind, item_id)
        return True
    except Refused:
        return False


# ---- the thread -----------------------------------------------------------------------------------------------------------------

def _me(viewer, ev: dict) -> bool:
    acc = getattr(viewer, "account_id", None)
    return bool(acc and ev.get("by_account") == acc) or (not acc and not ev.get("by_account") and ev.get("by") == getattr(viewer, "name", None))


def _admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


def _fold(evs: list[dict], key: str, viewer) -> list[dict]:
    """The comments of one thread, oldest first, folded from the events."""
    by_id: dict[str, dict] = {}
    for e in evs:
        if e["event"] == "add" and e["key"] == key:
            by_id[e["id"]] = {"id": e["id"], "parent_id": e.get("parent_id"), "by": e["by"], "at": e["at"], "text": e["text"], "edited": False,
                              "edited_at": None, "deleted": False, "deleted_by": None, "history": [], "case": None, "ticket": None,
                              "mentions": e.get("mentions", []), "_ev": e}
        elif e["event"] in ("edit", "delete", "raise") and e["comment_id"] in by_id:
            c = by_id[e["comment_id"]]
            if e["event"] == "edit":
                c["history"].append({"text": c["text"], "at": c["edited_at"] or c["at"]})
                c.update(text=e["text"], edited=True, edited_at=e["at"], mentions=e.get("mentions", c["mentions"]))
            elif e["event"] == "delete":
                c.update(deleted=True, deleted_by=e["by"], deleted_at=e["at"])
            else:
                c[e["as"]] = e["ref"]
    out = []
    for c in by_id.values():
        ev = c.pop("_ev")
        if c["deleted"]:
            c.update(text=None, history=[], mentions=[])
        c["may"] = {"reply": True, "edit": not c["deleted"] and _me(viewer, ev), "delete": not c["deleted"] and (_me(viewer, ev) or _admin(viewer)),
                    "raise": not c["deleted"] and not c["case"] and not c["ticket"]}
        out.append(c)
    return out


def thread(plane, viewer, kind: str, item_id: str) -> dict:
    """The thread on one thing. Refused 403 when the person may not see the thing: they get no words and no count."""
    t = check(plane, viewer, kind, item_id)
    key = f"{kind}:{t['id']}"
    items = _fold(events(plane), key, viewer)
    return {"kind": kind, "id": t["id"], "count": sum(1 for c in items if not c["deleted"]), "comments": items}


def _clean(text) -> str:
    text = str(text or "").strip()
    if not text:
        raise Refused(400, "Write something first.")
    if len(text) > MAX:
        raise Refused(400, f"Keep a comment under {MAX} characters.")
    return text


def _author(plane, viewer):
    with wh.connect(plane, read_only=True) as con:
        from sh_platform.v1.e1_access import user_id_of
        return user_id_of(con, viewer)


def add(plane, viewer, kind: str, item_id: str, text: str, parent_id: str | None = None) -> dict:
    t = check(plane, viewer, kind, item_id)
    text, key = _clean(text), f"{kind}:{t['id']}"
    if parent_id:
        parent = next((e for e in events(plane) if e["event"] == "add" and e["id"] == parent_id and e["key"] == key), None)
        if not parent:
            raise Refused(404, "That comment is not on this.")
        parent_id = parent.get("parent_id") or parent["id"]  # one level of replies keeps the thread readable
    uid = _author(plane, viewer)
    tell, left = _notify_list(plane, kind, t["id"], text, uid)
    ev = _append(plane, {"event": "add", "key": key, "kind": kind, "target": t["id"], "portfolio_id": t["portfolio_id"], "parent_id": parent_id,
                         "by": viewer.name, "by_account": getattr(viewer, "account_id", None), "text": text,
                         "mentions": [p["name"] for p in mentioned(plane, text)], "notify": tell})
    return {"id": ev["id"], "not_told": left, "thread": thread(plane, viewer, kind, item_id)}


def _find(plane, viewer, cid: str) -> tuple[dict, dict]:
    """(the add event, the thread-visible comment) after proving the viewer may see its thing."""
    ev = next((e for e in events(plane) if e["event"] == "add" and e["id"] == cid), None)
    if not ev:
        raise Refused(404, "We could not find that comment.")
    check(plane, viewer, ev["kind"], ev["target"])
    c = next(c for c in _fold(events(plane), ev["key"], viewer) if c["id"] == cid)
    return ev, c


def edit(plane, viewer, cid: str, text: str) -> dict:
    ev, c = _find(plane, viewer, cid)
    if c["deleted"]:
        raise Refused(409, "That comment was deleted.")
    if not _me(viewer, ev):
        raise Refused(403, "Only the person who wrote a comment can change it.")
    text = _clean(text)
    told = {u for e in events(plane) if e["event"] in ("add", "edit") and e.get("comment_id", e["id"]) == cid for u in e.get("notify", [])}
    tell, left = _notify_list(plane, ev["kind"], ev["target"], text, _author(plane, viewer), told)
    _append(plane, {"event": "edit", "comment_id": cid, "by": viewer.name, "text": text, "mentions": [p["name"] for p in mentioned(plane, text)], "notify": tell})
    return {"id": cid, "not_told": left, "thread": thread(plane, viewer, ev["kind"], ev["target"])}


def delete(plane, viewer, cid: str) -> dict:
    ev, c = _find(plane, viewer, cid)
    if c["deleted"]:
        raise Refused(409, "That comment was already deleted.")
    if not (_me(viewer, ev) or _admin(viewer)):
        raise Refused(403, "Only the person who wrote a comment, or an administrator, can delete it.")
    _append(plane, {"event": "delete", "comment_id": cid, "by": viewer.name})
    return {"id": cid, "thread": thread(plane, viewer, ev["kind"], ev["target"])}


# ---- raise as a case or a ticket -------------------------------------------------------------------------------------------------

def raise_as(plane, viewer, cid: str, as_: str = "case") -> dict:
    """"Raise as a case" opens an Action case (the thread then shows its link and the case shows the comment). `ticket` raises a ticket
    for a point that is not about money. A comment is raised once."""
    ev, c = _find(plane, viewer, cid)
    if as_ not in ("case", "ticket"):
        raise Refused(400, "Raise it as a case or a ticket.")
    if c["deleted"]:
        raise Refused(409, "That comment was deleted.")
    if c["case"] or c["ticket"]:
        raise Refused(409, "That comment was already raised.")
    text = c["text"]
    title = (" ".join(text.split())[:80]) or "Comment"
    where = f"{ev['kind'].replace('_', ' ')} {ev['target']}"
    if as_ == "case":
        from sh_platform.v1 import e4_cases
        try:
            case_id = e4_cases.open(plane, {"exception_type": "comment", "title": title, "description": f"Raised from a comment by {viewer.name} on the {where}.",
                                            "portfolio_id": ev.get("portfolio_id"), "actor": viewer})
            e4_cases.add_event(plane, case_id, viewer, "comment", f"Comment by {c['by']}: {text}")
            with wh.connect(plane, read_only=True) as con:
                number = e4_cases._number(con, case_id)
        except e4_cases.Refused as e:
            raise Refused(e.status, e.message) from None
        ref = {"id": case_id, "number": number, "link": f"/centre/desk/{case_id}"}
    else:
        from sh_platform.v1 import t2_tickets
        # the ticket carries the words, so it goes only to a named person who may see the thing; otherwise to the raiser
        to = next((p["name"] for p in mentioned(plane, text) if _may(plane, p, ev["kind"], ev["target"])), viewer.name)
        try:
            tk = t2_tickets.raise_ticket(plane, by=viewer.name, to=to, title=title, body=f"{text}\n\nOn the {where}.",
                                         links=[{"kind": "comment", "ref": cid}])
        except t2_tickets.Refused as e:
            raise Refused(getattr(e, "status", 400), getattr(e, "message", str(e))) from None
        ref = {"id": tk["id"], "number": tk["id"], "link": None}
    _append(plane, {"event": "raise", "comment_id": cid, "by": viewer.name, "as": as_, "ref": ref})
    return {"id": cid, as_: ref, "thread": thread(plane, viewer, ev["kind"], ev["target"])}


# ---- Today -----------------------------------------------------------------------------------------------------------------------

def pulse_cards(plane, con, today) -> list[dict]:
    """A card on Today for each person @named where they may see the thing (checked when the comment was written). Their own, by `recipient`."""
    from sh_platform.v1 import e5_pulse
    evs = events(plane)  # read once; this runs on every Today load
    gone = {e["comment_id"] for e in evs if e["event"] == "delete"}
    adds = {e["id"]: e for e in evs if e["event"] == "add"}
    out = []
    for e in evs:
        if e["event"] not in ("add", "edit"):
            continue
        cid = e.get("comment_id") or e["id"]
        add_ev = adds.get(cid)
        if not add_ev or cid in gone:
            continue
        for uid in e.get("notify", []):
            day = e["at"][:10]
            c = e5_pulse.card("*", f"comment:{cid}:{uid}", "comment", f"{e['by']} mentioned you in a comment", f"{e['by']} wrote to you on the {add_ev['kind'].replace('_', ' ')}.",
                              status_word="Comment", urgency="needs_me", action_type="open_comment", action="Read the comment", as_of=day, received=day,
                              link=ROUTE.get(add_ev["kind"], "").format(add_ev["target"].split("/")[0]) or None, rank=3)
            c["recipient"] = uid
            out.append(c)
    return out


try:
    from sh_platform.v1 import e5_pulse as _p
    _p.register_source(pulse_cards)
except ImportError:  # pragma: no cover - the pulse card is not installed
    log.warning("e5_pulse is not installed; mentions will not reach Today")
