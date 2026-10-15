"""K1 access to library items: sensitivity (open, internal, restricted), grants, requests, the preview of a locked item.

C4's `visible` still decides who sees an item at all (a private item stays invisible). K1 adds who may *read* it:
mine (always), open (everyone who sees it), granted (a grant not past its date), else the person sees a lock, a preview and may ask.
A request is `library/access.json` (the source of truth) and, when the person asked from a conversation that has a project, a P1
comment of kind `access` addressed to the owner. The owner answers from Pulse (`pulse_cards`); if the owner has left or is
disabled, a company_admin answers. An approval is a grant on the item (`grants`: who, when, why, until) and is never an agent's.
The preview of a locked item is name, topic, owner, kind, size, date, the column names of a table or the first heading of a text:
never a value, a row or body text; with personal data found it names the kinds only.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import c4_library as L
from sh_platform.v1.k1_classify import SENSITIVITIES

log = logging.getLogger(__name__)
Refused = L.Refused
DEFAULT_DAYS = 30
MAX_REASON = 300
PREVIEW = ("id", "name", "kind", "size", "at", "uploaded_by", "visibility", "sensitivity", "topic", "preview", "pii", "access", "mine", "can_change", "folder", "folder_by", "subfolder", "sorting")  # L3: the folder is on the lock row too
ASKED = ("requested", "denied")
COOLDOWN_DAYS = 7  # a declined request cannot be asked again for this long


def _cooling(r: dict) -> bool:
    return r["state"] == "denied" and (r.get("decided_at") or "") > _iso(_now() - timedelta(days=COOLDOWN_DAYS))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _apath(plane):
    return plane.path("library", "access.json")


def requests(plane) -> list[dict]:
    try:
        return read_json_strict(_apath(plane), list) or []
    except (OSError, ValueError):
        return []


def directory(plane) -> dict[str, dict]:
    """account_id -> {name, disabled, roles} for the company; {} when the accounts cannot be read."""
    try:
        from sh_platform.auth.accounts import AccountStore
        return {a["account_id"]: {"name": a["display_name"], "disabled": bool(a["disabled"]), "roles": a["roles"]}
                for a in AccountStore(plane.root.parent).in_company(plane.company_id)}
    except Exception:  # noqa: BLE001 - without the directory, nobody counts as having left
        log.warning("the company's accounts could not be read")
        return {}


# ---- the item's own fields ----------------------------------------------------------------------------------------------------------

def sens(item: dict) -> str:
    return item.get("sensitivity") if item.get("sensitivity") in SENSITIVITIES else "open"


def _live(g: dict) -> bool:
    return not g.get("expires") or str(g["expires"]) > _iso(_now())


def granted(item: dict, viewer) -> bool:
    aid = getattr(viewer, "account_id", None)
    return bool(aid) and any(g.get("account_id") == aid and _live(g) for g in item.get("grants") or [])


def can_read(item: dict, viewer) -> bool:
    """mine, open, or granted. (Seeded company items carry no sensitivity: open.)"""
    return L._mine(item, viewer) or sens(item) == "open" or granted(item, viewer)


def left(item: dict, people: dict) -> bool:
    """The owner no longer has an enabled account (a seeded item has no owner to ask: the admin answers)."""
    oid = item.get("uploaded_by_id")
    return not oid or (bool(people) and (oid not in people or people[oid]["disabled"]))


def state(item: dict, viewer, asked: list[dict] | None = None) -> str:
    if L._mine(item, viewer):
        return "mine"
    if sens(item) == "open":
        return "open"
    if granted(item, viewer):
        return "granted"
    aid = getattr(viewer, "account_id", None)
    mine = [r for r in asked or [] if r["item_id"] == item["id"] and r["requester_id"] == aid and r["state"] in ASKED]
    if not mine or (mine[-1]["state"] == "denied" and not _cooling(mine[-1])):
        return "request"
    return mine[-1]["state"]


def preview(item: dict) -> dict:
    p, pii = item.get("preview") or {}, item.get("pii") or {}
    out = {"contains_personal_data": bool(pii.get("found") and not pii.get("reviewed")), "kinds": list(pii.get("kinds") or [])}
    if not out["contains_personal_data"]:  # restricted by personal data says the kinds only, not where
        out["columns"], out["heading"] = p.get("columns"), p.get("heading")
    return out


def fields(item: dict, viewer, asked: list[dict] | None = None) -> dict:
    """What c4's `shown` adds to an item; and for a locked item the row is cut down to the preview whitelist."""
    owner = L._mine(item, viewer)
    pii = item.get("pii") or {}
    out = {"sensitivity": sens(item), "topic": item.get("topic") or [], "access": state(item, viewer, asked),
           "pii": {"found": bool(pii.get("found")), "kinds": pii.get("kinds") or [], "reviewed": bool(pii.get("reviewed")),
                   **({"where": pii.get("where") or []} if owner else {})}}
    if owner or L._admin(viewer):
        out["grants"] = [{k: g.get(k) for k in ("account_id", "name", "at", "expires", "why")} for g in item.get("grants") or []]
    return out


def lock(row: dict) -> dict:
    """The preview row of an item the viewer cannot read: the whitelist only (no note, path or hash)."""
    out = {k: row[k] for k in PREVIEW if k in row}
    out["preview"] = preview(row)
    out["locked"] = True
    return out


# ---- asking and answering --------------------------------------------------------------------------------------------------------

def _save(plane, fn) -> dict:
    path = _apath(plane)
    with lock_for(path):
        rows = requests(plane)
        out = fn(rows)
        write_json_atomic(path, rows)
    return out


def _p1(fn) -> None:
    """The P1 trail is a courtesy: a conversation without a project, or any P1 failure, never blocks the request."""
    try:
        from sh_platform.v1 import p1_project
        fn(p1_project)
    except Exception:  # noqa: BLE001
        log.warning("the access note could not be written to the project's trail")


def request_access(plane, viewer, item_id: str, reason: str = "", iid: str | None = None, people: dict | None = None) -> dict:
    item = L._find(plane, item_id, viewer)  # a private item is not there
    if can_read(item, viewer):
        raise Refused(409, "You can already use this file.")
    people = directory(plane) if people is None else people
    if iid:
        try:
            L._context_path(plane, iid)  # the conversation must exist; otherwise the request goes without a trail
        except Refused:
            iid = None
    gone = left(item, people)
    admins = sorted((i for i, p in people.items() if "company_admin" in p["roles"] and not p["disabled"]), key=lambda i: people[i]["name"])
    to_id = admins[0] if gone and admins else item.get("uploaded_by_id")
    to = people.get(to_id, {}).get("name") or item.get("uploaded_by") or "the company administrator"
    rec = {"id": "acc_" + secrets.token_hex(5), "item_id": item["id"], "item_name": item["name"], "requester_id": viewer.account_id,
           "requester": viewer.name, "to_id": to_id, "to": to, "owner_left": gone, "reason": " ".join(str(reason or "").split())[:MAX_REASON],
           "at": _iso(_now()), "state": "requested", "iid": iid or None, "p1": None, "decided_by": None, "decided_at": None,
           "decision_note": "", "expires": None}

    def go(rows):
        mine_ = [r for r in rows if r["item_id"] == item["id"] and r["requester_id"] == viewer.account_id]
        dup = next((r for r in mine_ if r["state"] == "requested"), None) or next((r for r in mine_[-1:] if _cooling(r)), None)
        if dup:
            return dup
        rows.append(rec)
        return rec
    got = _save(plane, go)
    if got is rec and iid:
        def note(p1):
            c = p1.comment(plane, iid, "intent", None, viewer.name, to, f"{viewer.name} asks to use {item['name']}. {rec['reason']}".strip(), kind="access")
            if c:
                rec["p1"] = {"pid": p1._pid_of(plane, iid), "cid": c["id"]}
                _save(plane, lambda rows: next(r for r in rows if r["id"] == rec["id"]).update(p1=rec["p1"]))
        _p1(note)
    return got


def _may_answer(item: dict, viewer, people: dict) -> bool:
    return L._mine(item, viewer) or (L._admin(viewer) and left(item, people))


def _add_grant(item: dict, who_id: str, who: str, by: str, days: int | None, why: str, request_id: str | None) -> dict:
    expires = _iso(_now() + timedelta(days=days)) if days else None
    item["grants"] = [g for g in item.get("grants") or [] if g.get("account_id") != who_id]
    g = {"account_id": who_id, "name": who, "by": by, "at": _iso(_now()), "expires": expires, "why": why[:MAX_REASON], "request_id": request_id}
    item["grants"].append(g)
    return g


def answer(plane, viewer, request_id: str, approve: bool, days: int | None = DEFAULT_DAYS, note: str = "", people: dict | None = None) -> dict:
    """The owner (or, when the owner has left, a company admin) approves or declines. `days` 0 or None: until revoked."""
    people = directory(plane) if people is None else people
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        req = next((r for r in requests(plane) if r["id"] == request_id), None)
        item = next((i for i in rows if req and i["id"] == req["item_id"]), None)
        if req is None or item is None or not _may_answer(item, viewer, people):
            raise Refused(404, "We could not find that request.")  # not yours to see
        if req["state"] != "requested":
            raise Refused(409, "This request has already been answered.")
        if req["requester_id"] == viewer.account_id:
            raise Refused(409, "Give the file a new owner instead.")  # an admin does not approve their own request
        days = DEFAULT_DAYS if days is None and approve else days
        note = " ".join(str(note or "").split())[:MAX_REASON]
        if approve:
            _add_grant(item, req["requester_id"], req["requester"], viewer.name, days if days and days > 0 else None, req["reason"] or "Approved on request", req["id"])
            write_json_atomic(L._index_path(plane), rows)
        exp = next((g["expires"] for g in item.get("grants") or [] if g.get("request_id") == req["id"]), None)

        def go(rs):
            r = next(x for x in rs if x["id"] == request_id)
            r.update(state="granted" if approve else "denied", decided_by=viewer.name, decided_at=_iso(_now()), decision_note=note, expires=exp)
            return r
        out = _save(plane, go)
    if req.get("p1"):
        def close(p1):
            p1.answer(plane, req["p1"]["pid"], req["p1"]["cid"], viewer.name, f"{'Approved' if approve else 'Not now'}. {note}".strip())
            p1.resolve(plane, req["p1"]["pid"], req["p1"]["cid"], req["requester"])
        _p1(close)
    return out


def grant(plane, viewer, item_id: str, account_id: str, days: int | None = None, why: str = "", people: dict | None = None) -> dict:
    """The owner names a person who may use the item without being asked (Internal)."""
    people = directory(plane) if people is None else people
    if account_id not in people or people[account_id]["disabled"]:
        raise Refused(404, "We could not find that person.")
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        item = L._find(plane, item_id, viewer)
        if not _may_answer(item, viewer, people):
            raise Refused(403, "Only the person who added this file can share it with named people.")
        item = next(i for i in rows if i["id"] == item_id)
        _add_grant(item, account_id, people[account_id]["name"], viewer.name, days, why or "Added by the owner", None)
        write_json_atomic(L._index_path(plane), rows)
    return L.shown(item, viewer, plane)


def revoke(plane, viewer, item_id: str, account_id: str, people: dict | None = None) -> dict:
    people = directory(plane) if people is None else people
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        item = L._find(plane, item_id, viewer)
        if not _may_answer(item, viewer, people):
            raise Refused(403, "Only the person who added this file can take access away.")
        item = next(i for i in rows if i["id"] == item_id)
        item["grants"] = [g for g in item.get("grants") or [] if g.get("account_id") != account_id]
        write_json_atomic(L._index_path(plane), rows)
    _save(plane, lambda rs: [r.update(state="revoked") for r in rs if r["item_id"] == item_id and r["requester_id"] == account_id and r["state"] == "granted"])
    return L.shown(item, viewer, plane)


def reassign(plane, viewer, item_id: str, account_id: str, people: dict | None = None) -> dict:
    """A company admin hands an item to another person when its owner has left."""
    people = directory(plane) if people is None else people
    if not L._admin(viewer):
        raise Refused(403, "Only a company administrator can give a file to someone else.")
    if account_id not in people or people[account_id]["disabled"]:
        raise Refused(404, "We could not find that person.")
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        item = next((i for i in rows if i["id"] == item_id and L.visible(i, viewer)), None)
        if item is None or not left(item, people):
            raise Refused(404, L.NOT_FOUND)
        item.update(uploaded_by=people[account_id]["name"], uploaded_by_id=account_id)
        write_json_atomic(L._index_path(plane), rows)
    return L.shown(item, viewer, plane)


def stamp(plane, item: dict, viewer, name: str, data: bytes, note: str, sensitivity, topic, reviewed: bool, model) -> None:
    """At upload: scan on the machine, propose, then take the owner's choice. Personal data forces Restricted unless the owner says it is not."""
    from sh_platform.v1 import k1_classify as C
    prop = C.propose(name, data, note, model, plane)
    pii = {k: prop["pii"][k] for k in ("found", "kinds", "where")}
    item.update(pii=pii, preview=prop["outline"], topic=clean_topics(topic) or prop["topics"], topic_by="person" if topic else prop["by"],
                sensitivity=prop["sensitivity"], grants=[])
    if sensitivity is not None:
        if sensitivity not in SENSITIVITIES:
            raise Refused(400, "Choose Open, Internal or Restricted.")
        if sensitivity != "restricted" and pii["found"] and not reviewed:
            sensitivity = "restricted"  # forced: the owner has not said it is not personal
        elif sensitivity != "restricted" and pii["found"]:
            pii["reviewed"] = {"by": viewer.name, "at": _iso(_now())}
        item["sensitivity"] = sensitivity


def clean_topics(topic) -> list[str]:
    """Up to three free labels, trimmed; the program's list is a suggestion, not a limit."""
    raw = topic if isinstance(topic, list) else [topic] if topic else []
    return list(dict.fromkeys(" ".join(str(t).split())[:40] for t in raw if str(t).strip()))[:3]


def edit(item: dict, viewer, body: dict) -> None:
    if not L._mine(item, viewer):
        raise Refused(403, "Only the person who added this file can change who may use it or what it is about.")
    if "topic" in body:
        item["topic"], item["topic_by"] = clean_topics(body["topic"]), "person"
    if "sensitivity" in body:
        set_sensitivity(item, viewer, body["sensitivity"], body.get("reviewed") is True)


def set_sensitivity(item: dict, viewer, sensitivity: str, reviewed: bool = False) -> None:
    """The owner changes it. Open or Internal on a file with personal data needs the owner's word that it is not personal (recorded)."""
    if sensitivity not in SENSITIVITIES:
        raise Refused(400, "Choose Open, Internal or Restricted.")
    if not L._mine(item, viewer):
        raise Refused(403, "Only the person who added this file can change who may use it.")
    pii = item.setdefault("pii", {"found": False, "kinds": [], "where": []})
    if sensitivity != "restricted" and pii.get("found") and not pii.get("reviewed"):
        if not reviewed:
            raise Refused(409, "This file contains personal data. Confirm you have looked and it is not personal to make it less restricted.")
        pii["reviewed"] = {"by": viewer.name, "at": _iso(_now())}
    item["sensitivity"] = sensitivity


# ---- what each person is shown ---------------------------------------------------------------------------------------------------------

def incoming(plane, viewer, people: dict | None = None) -> list[dict]:
    """Open requests this viewer may answer, oldest first."""
    people = directory(plane) if people is None else people
    items = {i["id"]: i for i in L._index(plane)}
    return [r for r in requests(plane) if r["state"] == "requested" and r["item_id"] in items and _may_answer(items[r["item_id"]], viewer, people)]


def mine(plane, viewer) -> list[dict]:
    return [r for r in requests(plane) if r["requester_id"] == getattr(viewer, "account_id", None)]


def pulse_cards(plane, viewer, people: dict | None = None, days: int = 14) -> dict:
    """{needs_you: [...], worth_a_look: [...]} in Pulse's card shape. Approve / Not now are `POST /api/v1/library/access/{request_id}`."""
    needs = [{"id": f"access:{r['id']}", "kind": "access", "project": "Library", "pid": None, "request_id": r["id"], "action": "Approve",
              "text": f"{r['requester']} asks to use {r['item_name']}." + (f" {r['reason']}" if r["reason"] else ""),
              "href": "/centre/library/access", "since": r["at"][:10]} for r in incoming(plane, viewer, people)]
    cut = _iso(_now() - timedelta(days=days))
    seen = [{"id": f"access:{r['id']}:{r['state']}", "kind": "access", "request_id": r["id"], "href": "/centre/library/access",
             "text": (f"{r['decided_by']} approved your request to use {r['item_name']}"
                      + (f", until {r['expires'][:10]}." if r.get("expires") else ", until they take it back.")) if r["state"] == "granted"
             else f"{r['decided_by']} is not able to share {r['item_name']} just now." + (f" {r['decision_note']}" if r["decision_note"] else "")}
            for r in mine(plane, viewer) if r["state"] in ("granted", "denied") and (r["decided_at"] or "") >= cut]
    return {"needs_you": needs, "worth_a_look": seen}
