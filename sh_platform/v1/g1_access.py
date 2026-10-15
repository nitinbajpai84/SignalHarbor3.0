"""G1 Project folder and project-level access (extends K1 and P1; docs/plan/V1-BUILD.md, Round 9).

`may_see_project(plane, viewer, pid) -> "full" | "read" | "preview" | "none"` is the one answer every project read uses.
- full: the team (the people named on the project, plus anyone in `team`) and every company_admin: read, comment, export, act.
- read: a person a comment on the project is addressed to (S10: they can always read the artefact and answer it), a person with a
  live grant (K1's grant record, kept on the project), the ops seat once the project is live, the architect seat (the head of data)
  while a build plan waits for approval (NU-16; not Restricted), and everyone signed in while the
  project is Open. Read-only for the mapping sheet and SQL: the export of the design, build pack, benchmark sheet and run book still
  needs the roles a1/b3 allow (`export_allowed`).
- preview: Internal (the team's alone), not a member: a lock with title, stage and owner, and "Request access".
- none: Restricted, not a member: nothing, except that a project with this id exists and may be requested.
A project saved before G1 has no `sensitivity`: it reads as Open (nothing changes for it); new projects start Internal.
Access requests are K1's: rows of `library/access.json` (item_id = the project id) plus a P1 comment of kind `access` addressed to the
owner (the raiser), answered from Pulse; approval is a grant on the project record, with an optional expiry, noted on the trail.
The project folder is `projects/<pid>/files/`; the library index points at each file with `project: <pid>`, and the row's grants
are kept equal to the project's team so K1/C4 decide who reads it.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException, Request

from sh_platform.jsonfile import lock_for, write_json_atomic
from sh_platform.profile.view import norm
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import k1_access as K
from sh_platform.v1 import p1_project as P
from sh_platform.v1.k1_classify import SENSITIVITIES
from sh_platform.v1.seats import ARCHITECT, HEAD_OF_DATA, OPS_MANAGER, seat_of

log = logging.getLogger(__name__)
Refused = P.Refused
DEFAULT = "internal"
SENS_NAMES = {"open": "Open", "internal": "Internal", "restricted": "Restricted"}
EXPORT_ROLES = frozenset({"company_admin", "analyst", "sponsor"})  # a1 and b3 refuse everyone else the design, mapping and sheet
GUARDED = ("design", "build_pack", "run_book", "benchmarks")
MAX_TEAM = 40
ASK = ("Who should be able to see this work: everyone in the company, only the people you name, or only you and the people you name "
       "with no preview for others?")
_ASKED = re.compile(r"who should be able to see this work", re.I)


# ---- who is who ------------------------------------------------------------------------------------------------------------------

def _me(who, viewer) -> bool:
    if not who or viewer is None:
        return False
    aid = getattr(viewer, "account_id", None)
    if aid and str(who) == aid:
        return True
    return not getattr(viewer, "shared_name", False) and norm(who) == norm(getattr(viewer, "name", ""))


def sensitivity(rec: dict) -> str:
    return rec["sensitivity"] if rec.get("sensitivity") in SENSITIVITIES else "open"


def team_of(rec: dict) -> list[dict]:
    """The people named on the project: its parts (raiser, sponsor, builder, ...) then the stored team, one row per person."""
    out, seen = [], set()
    for key, name in (rec.get("people") or {}).items():
        if isinstance(name, str) and name and norm(name) not in seen:
            seen.add(norm(name))
            out.append({"name": name, "role": key.replace("_", " "), "account_id": rec.get("raiser_id") if key == "raiser" else None})
    for m in rec.get("team") or []:
        if isinstance(m, dict) and m.get("name") and norm(m["name"]) not in seen:
            seen.add(norm(m["name"]))
            out.append({"name": m["name"], "role": m.get("role") or "member", "account_id": m.get("account_id")})
    return out


def on_team(rec: dict, viewer) -> bool:
    return any(_me(m.get("account_id"), viewer) or _me(m["name"], viewer) for m in team_of(rec))


# ---- the helper -------------------------------------------------------------------------------------------------------------------

def level(plane, viewer, rec: dict, comments: list[dict] | None = None) -> str:
    """`may_see_project` for a record already read. `comments` may be passed when the caller holds them."""
    if "company_admin" in set(getattr(viewer, "roles", ()) or ()) or on_team(rec, viewer):
        return "full"
    if K.granted(rec, viewer):
        return "read"
    if rec.get("stage") == "live" and OPS_MANAGER in seat_of(viewer):
        return "read"  # G2: after go live the ops seat reads and comments
    if sensitivity(rec) != "restricted" and HEAD_OF_DATA in seat_of(viewer):
        return "read"  # UC5: the head of data approves every build's pack and plan, so they read every project that is not Restricted
    if sensitivity(rec) != "restricted" and ARCHITECT in seat_of(viewer) and _plan_waits(plane, rec["id"]):
        return "read"  # NU-16: the head of data (architect seat) who must approve a waiting build plan can open it; Restricted stays the named people's
    mine = P.comments(plane, rec["id"]) if comments is None else comments
    if any(_me(c.get("to"), viewer) for c in mine if isinstance(c, dict)):
        return "read"  # S10: a comment addressed to a person gives them the artefact line to read and answer
    return {"open": "read", "internal": "preview"}.get(sensitivity(rec), "none")


def _plan_waits(plane, pid: str) -> bool:
    """A build plan of the project is proposed and waits for the head of data's approval."""
    from sh_platform.v1 import b6_plan as B  # deferred: b6_plan reads projects through this module's callers
    try:
        return (B.get(plane, pid) or {}).get("state") == "proposed"
    except Exception:  # noqa: BLE001 - an unreadable plan opens nothing
        return False


def may_see_project(plane, viewer, pid: str) -> str:
    try:
        return level(plane, viewer, P.read(plane, pid))
    except Refused:
        return "none"


def _owner(rec: dict) -> str:
    return (rec.get("people") or {}).get("raiser") or rec.get("started_by") or "the project owner"


def lock_row(rec: dict, lvl: str, plane=None, viewer=None) -> dict:
    """What a person who may not read the project is shown: Internal, title, stage and owner; Restricted, only that it exists."""
    out = {"id": rec["id"], "locked": True, "access": lvl, "sensitivity": sensitivity(rec), "can_request": True}
    if lvl == "preview":
        out.update(title=rec.get("title"), stage=rec.get("stage"), owner=_owner(rec))
    if plane is not None and viewer is not None:
        out["request"] = _mine(plane, viewer, rec["id"])
    return out


def require(plane, viewer, pid: str, need: str = "read") -> tuple[dict, str]:
    """(record, level) or P1.Refused 403/404. `need` is "read" or "full"."""
    rec = P.read(plane, pid)
    lvl = level(plane, viewer, rec)
    if lvl == "full" or (lvl == "read" and need == "read"):
        return rec, lvl
    if lvl in ("preview", "none"):
        raise Refused(403, f"This project is {SENS_NAMES[sensitivity(rec)]}. " + (
            f"You can see its title, stage and owner ({_owner(rec)}). Ask for access and {_owner(rec)} will answer." if lvl == "preview"
            else "Ask for access if you need it."))
    raise Refused(403, "You can read this project but not change it. Ask its owner.")


def for_intent(plane, viewer, iid: str, need: str = "read") -> str:
    """The level for an intent's project; an intent with no project yet has nothing to protect ("full")."""
    rec = P.for_intent(plane, iid)
    return "full" if rec is None else require(plane, viewer, rec["id"], need)[1]


def check_agent(plane, iid: str, viewer, error) -> None:
    """For an agent's chat entry (North, Span, Flow, Lumen): they read a project's artefacts only for a person who may see them."""
    try:
        rec = P.for_intent(plane, iid)
        lvl = level(plane, viewer, rec) if rec else "full"
    except Exception:  # noqa: BLE001 - a damaged project file never stops a conversation on its own
        log.warning("the project access check failed for %s", iid)
        return
    if lvl not in ("full", "read"):
        raise error("This project is not open to you, so the agents cannot talk to you about it. Ask the project owner for access.")


def http_gate(plane, viewer, iid: str, need: str = "read") -> None:
    """For routes that name an intent (the benchmark sheet, the source viewer): HTTP 403 in the screen's own shape."""
    try:
        for_intent(plane, viewer, iid, need)
    except Refused as e:
        raise HTTPException(e.status, {"error": "not_allowed", "message": e.message}) from None


_OPEN_PATHS = ("/project", "/pickup/", "/engineer")  # the lock row of an intent's project; pick-up and the engineer screen (each joins the team, then gates itself)


def intent_gate(request: Request) -> None:
    """A router-wide FastAPI dependency (v1 `install`): every route that names an intent, in the path or as `?iid=`, checks the project's
    access first. Reads need "read", writes "full" (the agents' chat only "read": `check_agent` decides). Fails soft when the session or
    plane cannot be had: the handler then gives its own answer."""
    iid = request.path_params.get("iid") or request.query_params.get("iid")
    if not iid or any(s in request.url.path for s in _OPEN_PATHS):
        return
    from sh_platform.build import runner
    try:
        plane, viewer = runner._company(request)
    except HTTPException:
        return
    path = request.url.path
    http_gate(plane, viewer, iid, "read" if request.method in ("GET", "HEAD") or path.endswith("/chat") else "full")


def join(plane, pid: str, name: str | None, role: str, account_id: str | None = None) -> None:
    """Add a person to the team as the work moves (builder, head of data, ops, engineer); no-op when already named. Never fails the caller."""
    if not name:
        return
    try:
        def go(r):
            if not any(norm(m["name"]) == norm(name) for m in team_of(r)):
                r["team"] = [*(r.get("team") or []), {"name": name, "role": role, "account_id": account_id}]
        P._update(plane, pid, go)
        _sync_rows(plane, pid)
    except Exception:  # noqa: BLE001
        log.warning("%s could not be added to project %s", name, pid)


def named_full(plane, rec: dict, name: str | None) -> bool:
    """A person (by name) who holds "full" on the project: on its team, or a company admin. Used to tell who may bring someone onto the team."""
    if not name:
        return False
    if any(norm(m["name"]) == norm(name) for m in team_of(rec)):
        return True
    try:
        return any(norm(p["name"]) == norm(name) and "company_admin" in p["roles"] and not p["disabled"] for p in K.directory(plane).values())
    except Exception:  # noqa: BLE001
        return False


def can_read_intent(plane, viewer, iid) -> bool:
    """True when the viewer may read the intent's project (an intent with no project has nothing to protect). For routes that list or key by intent."""
    try:
        return not isinstance(iid, str) or for_intent(plane, viewer, iid, "read") in ("full", "read")
    except Refused:
        return False


def head_of_data(plane) -> str | None:
    try:
        return next(iter(sorted(p["name"] for p in K.directory(plane).values() if "company_admin" in p["roles"] and not p["disabled"])), None)
    except Exception:  # noqa: BLE001
        return None


def data_team(plane) -> list[str]:
    """SPAN-CH2-05: the names of the data team (the analyst seat), for a plain 'who can draft it'."""
    try:
        return sorted(p["name"] for p in K.directory(plane).values() if not p["disabled"] and "analyst" in p["roles"])
    except Exception:  # noqa: BLE001
        return []


def who_can_help(plane, pid: str | None = None) -> str:
    """SPM-6, SPAN-CH-07, A16: one line naming who can act when an agent hits a limit: the data team (changes to the plan and the model),
    the company administrator (access), and the project's owner when a project is in hand. Names only, from the company's own accounts."""
    try:
        people = [p for p in K.directory(plane).values() if not p["disabled"]]
    except Exception:  # noqa: BLE001
        people = []
    team = sorted(p["name"] for p in people if "analyst" in p["roles"])
    admin = sorted(p["name"] for p in people if "company_admin" in p["roles"])
    out = []
    if team:
        out.append("the data team (" + ", ".join(team[:4]) + ") can add or change tables, accept plan changes and say where data is kept")
    if admin:
        out.append("the company administrator (" + ", ".join(admin[:2]) + ") can grant access")
    if pid:
        try:
            out.append(f"the project owner is {_owner(P.read(plane, pid))}")
        except Exception:  # noqa: BLE001 - the owner is a nicety
            pass
    return "; ".join(out) or "ask your administrator"


def export_allowed(lvl: str, kind: str, roles) -> bool:
    return lvl == "full" or kind not in GUARDED or bool(set(roles or ()) & EXPORT_ROLES)


def shown(plane, viewer, rec: dict) -> dict:
    """The project as the viewer may see it: whole, or the lock row."""
    lvl = level(plane, viewer, rec)
    if lvl not in ("full", "read"):
        return lock_row(rec, lvl, plane, viewer)
    return {**rec, "access": lvl, "sensitivity": sensitivity(rec), "team": team_of(rec),
            "grants": [{k: g.get(k) for k in ("account_id", "name", "at", "expires", "why")} for g in rec.get("grants") or [] if K._live(g)] if lvl == "full" else []}


# ---- setting the access -----------------------------------------------------------------------------------------------------------

def defaults(plane) -> dict:
    """Fields a new project starts with: Internal, the company's sponsor on the team (the raiser is on it through `people`)."""
    try:
        sponsors = sorted(p["name"] for p in K.directory(plane).values() if "sponsor" in p["roles"] and not p["disabled"])
    except Exception:  # noqa: BLE001
        sponsors = []
    return {"sensitivity": DEFAULT, "team": [{"name": n, "role": "sponsor"} for n in sponsors]}


def can_manage(rec: dict, viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ()) or _me(_owner(rec), viewer) or _me(rec.get("raiser_id"), viewer)


def _trail(plane, pid: str, by: str, to: str | None, text: str) -> None:
    """A note on the project's trail. Addressed to nobody: a note about someone's access must not itself give them access."""
    try:
        P.comment(plane, pid, "intent", None, by, None, text, kind="note")
    except Exception:  # noqa: BLE001 - the trail is a courtesy; the change stands
        log.warning("the access note could not be written to the project's trail")


def _touch(plane) -> None:
    try:
        from sh_platform.v1.m1_map import touch
        touch(plane)  # the company map follows the project's access
    except Exception:  # noqa: BLE001
        pass


def _clean_team(plane, team) -> list[dict]:
    if not isinstance(team, list) or len(team) > MAX_TEAM:
        raise Refused(400, "Name the people on the team, a role each.")
    people = K.directory(plane)
    by_name = {norm(p["name"]): (i, p) for i, p in people.items() if not p["disabled"]}
    out = []
    for m in team:
        m = m if isinstance(m, dict) else {}
        key = m.get("account_id")
        found = (key, people[key]) if key in people and not people[key]["disabled"] else by_name.get(norm(m.get("name") or ""))
        if not found:
            raise Refused(404, f"We could not find {m.get('name') or 'that person'} in your company.")
        out.append({"name": found[1]["name"], "role": " ".join(str(m.get("role") or "member").split())[:40], "account_id": found[0]})
    return list({norm(m["name"]): m for m in out}.values())


def set_access(plane, viewer, pid: str, sens: str | None = None, team=None) -> dict:
    """The owner (or a company admin) sets who may see the project and who is on its team; recorded on the trail."""
    rec = P.read(plane, pid)
    if not can_manage(rec, viewer):
        raise Refused(403, f"Only {_owner(rec)} or a company administrator can change who sees this project.")
    if sens is not None and sens not in SENSITIVITIES:
        raise Refused(400, "Choose Open, Internal or Restricted.")
    members = _clean_team(plane, team) if team is not None else None

    def go(r):
        if sens is not None:
            r["sensitivity"] = sens
        if members is not None:
            r["team"] = members
    out = P._update(plane, pid, go)
    _trail(plane, pid, viewer.name, None, f"{viewer.name} set the project to {SENS_NAMES[sensitivity(out)]}"
           + (f", team: {', '.join(m['name'] for m in team_of(out))}." if members is not None else "."))
    _sync_rows(plane, pid)
    _touch(plane)
    return shown(plane, viewer, out)


def note_answer(plane, iid: str, text: str, previous: str | None, covered_now: bool) -> None:
    """North asked the access question near the start (the intent template's `access` field); the person's answer sets the project.
    Called after each person turn; acts only when North's last turn was that question or North ticked the goal."""
    if not (covered_now or _ASKED.search(previous or "")):
        return
    t = norm(text)
    if re.search(r"no preview|only (?:me|myself)|just me|only you and|restricted|nobody else|no one else|private", t):
        sens = "restricted"
    elif re.search(r"everyone|everybody|whole company|all staff|anyone|open to all", t):
        sens = "open"
    elif re.search(r"people (?:i|you) name|named|only|team|internal|colleagues", t):
        sens = "internal"
    else:
        return  # unclear: the default stays, and the owner can change it on the project page
    rec = P.project_of(plane, iid)
    if rec is None:
        return
    mentioned = [{"name": p["name"], "role": "member", "account_id": i} for i, p in K.directory(plane).items()
                 if not p["disabled"] and norm(p["name"]) in t]

    def go(r):
        r["sensitivity"] = sens
        have = {norm(m.get("name")) for m in r.get("team") or []}
        r["team"] = [*(r.get("team") or []), *(m for m in mentioned if norm(m["name"]) not in have)]
    P._update(plane, rec["id"], go)
    _sync_rows(plane, rec["id"])
    _touch(plane)


def restrict_nodes(g, plane, iid: str) -> None:
    """The company map: a restricted project's own nodes (those no other intent drew) are a silhouette to everyone off its team.
    Company admins are on the list too, as everywhere else in G1."""
    rec = P.for_intent(plane, iid)
    if not rec or sensitivity(rec) != "restricted":
        return
    from sh_platform.graph.models import meet
    names = sorted({norm(m["name"]) for m in team_of(rec)} | {norm(p["name"]) for p in K.directory(plane).values()
                                                             if "company_admin" in p["roles"] and not p["disabled"]})  # the guard compares normalised names
    for n in g.nodes.values():
        if n.get("intents") == [iid]:
            guard = meet(g.guard(n["id"]), (names, {}))
            n["restricted_to"], n["restricted_bound"] = (guard[0], guard[1] or None) if guard else (None, None)


# ---- asking for access --------------------------------------------------------------------------------------------------------------

def _mine(plane, viewer, pid: str) -> dict | None:
    got = [r for r in K.mine(plane, viewer) if r.get("item_id") == pid]
    return {k: got[-1].get(k) for k in ("id", "state", "at", "expires")} if got else None


def request_access(plane, viewer, pid: str, reason: str = "") -> dict:
    """A K1 request addressed to the project's owner (the company admin when the owner has left), answered from Pulse."""
    rec = P.read(plane, pid)
    if level(plane, viewer, rec) in ("full", "read"):
        raise Refused(409, "You can already read this project.")
    people = K.directory(plane)
    owner = _owner(rec)
    owner_id = next((i for i, p in people.items() if norm(p["name"]) == norm(owner) and not p["disabled"]), None)
    admins = sorted((i for i, p in people.items() if "company_admin" in p["roles"] and not p["disabled"]), key=lambda i: people[i]["name"])
    to_id = owner_id or (admins[0] if admins else None)
    to = people[to_id]["name"] if to_id else owner
    row = {"id": "acc_" + secrets.token_hex(5), "item_id": pid, "item_name": rec.get("title") or pid, "project": pid, "requester_id": viewer.account_id,
           "requester": viewer.name, "to_id": to_id, "to": to, "owner_left": owner_id is None, "reason": " ".join(str(reason or "").split())[:K.MAX_REASON],
           "at": K._iso(K._now()), "state": "requested", "iid": rec["intent_id"], "p1": None, "decided_by": None, "decided_at": None,
           "decision_note": "", "expires": None}

    def go(rows):
        mine_ = [r for r in rows if r["item_id"] == pid and r["requester_id"] == viewer.account_id]
        dup = next((r for r in mine_ if r["state"] == "requested"), None) or next((r for r in mine_[-1:] if K._cooling(r)), None)
        if dup:
            return dup
        rows.append(row)
        return row
    got = K._save(plane, go)
    if got is row:
        c = P.comment(plane, pid, "intent", None, viewer.name, to, f"{viewer.name} asks for access to {rec.get('title')}. {row['reason']}".strip(), kind="access")
        if c:
            row["p1"] = {"pid": pid, "cid": c["id"]}
            K._save(plane, lambda rows: next(r for r in rows if r["id"] == row["id"]).update(p1=row["p1"]))
    return {k: got.get(k) for k in ("id", "state", "at", "to", "reason")}


def incoming(plane, viewer) -> list[dict]:
    """Open project requests this viewer may answer (the owner it was addressed to)."""
    return [r for r in K.requests(plane) if r.get("project") and r["state"] == "requested" and _me(r.get("to_id"), viewer)]


def answer(plane, viewer, pid: str, request_id: str, approve: bool, days: int | None = K.DEFAULT_DAYS, note: str = "") -> dict:
    req = next((r for r in K.requests(plane) if r["id"] == request_id and r.get("project") == pid), None)
    if req is None or not _me(req.get("to_id"), viewer):
        raise Refused(404, "We could not find that request.")  # not yours to see
    if req["state"] != "requested":
        raise Refused(409, "This request has already been answered.")
    note = " ".join(str(note or "").split())[:K.MAX_REASON]
    days = K.DEFAULT_DAYS if days is None and approve else days
    days = days if days and days > 0 else None
    if approve:
        P._update(plane, pid, lambda r: K._add_grant(r, req["requester_id"], req["requester"], viewer.name, days, req["reason"] or "Approved on request", req["id"]))
        _sync_rows(plane, pid)
    expires = next((g["expires"] for g in P.read(plane, pid).get("grants") or [] if g.get("request_id") == req["id"]), None) if approve else None

    def go(rows):
        r = next(x for x in rows if x["id"] == request_id)
        r.update(state="granted" if approve else "denied", decided_by=viewer.name, decided_at=K._iso(K._now()), decision_note=note, expires=expires)
        return r
    out = K._save(plane, go)
    if req.get("p1"):
        try:
            P.answer(plane, pid, req["p1"]["cid"], viewer.name, f"{'Approved' if approve else 'Not now'}. {note}".strip())
            P.resolve(plane, pid, req["p1"]["cid"], req["requester"])
        except Refused:
            log.warning("the access request on the project's trail could not be closed")
    return {k: out.get(k) for k in ("id", "state", "decided_by", "decided_at", "expires")}


def grant(plane, viewer, pid: str, account_id: str, days: int | None = None, why: str = "") -> dict:
    """The owner names a person who may read the project without asking."""
    rec = P.read(plane, pid)
    if not can_manage(rec, viewer):
        raise Refused(403, f"Only {_owner(rec)} or a company administrator can give access to this project.")
    p = K.directory(plane).get(account_id)
    if not p or p["disabled"]:
        raise Refused(404, "We could not find that person.")
    days = days if days and days > 0 else None
    P._update(plane, pid, lambda r: K._add_grant(r, account_id, p["name"], viewer.name, days, why or "Added by the owner", None))
    _trail(plane, pid, viewer.name, p["name"], f"{viewer.name} gave {p['name']} access to read this project"
           + (f" for {days} days." if days else " until it is taken back."))
    _sync_rows(plane, pid)
    return shown(plane, viewer, P.read(plane, pid))


def revoke(plane, viewer, pid: str, account_id: str) -> dict:
    rec = P.read(plane, pid)
    if not can_manage(rec, viewer):
        raise Refused(403, f"Only {_owner(rec)} or a company administrator can take access away.")
    gone = next((g for g in rec.get("grants") or [] if g.get("account_id") == account_id), None)
    P._update(plane, pid, lambda r: r.__setitem__("grants", [g for g in r.get("grants") or [] if g.get("account_id") != account_id]))
    K._save(plane, lambda rows: [r.update(state="revoked") for r in rows if r.get("project") == pid and r["requester_id"] == account_id and r["state"] == "granted"])
    if gone:
        _trail(plane, pid, viewer.name, gone.get("name"), f"{viewer.name} took back {gone.get('name')}'s access to this project.")
    _sync_rows(plane, pid)
    return shown(plane, viewer, P.read(plane, pid))


# ---- the project folder -----------------------------------------------------------------------------------------------------------

def folder(plane, pid: str):
    P._ppath(plane, pid)
    return plane.path("projects", pid, "files")


def _grant_rows(plane, rec: dict) -> list[dict]:
    """The row's grants: the team, every company admin, and the project's live grants (so K1 and C4 decide who reads the file)."""
    people = K.directory(plane)
    ids = {i for i, p in people.items() if "company_admin" in p["roles"] and not p["disabled"]}
    for m in team_of(rec):
        ids |= {i for i, p in people.items() if not p["disabled"] and (i == m.get("account_id") or norm(p["name"]) == norm(m["name"]))}
    out = [{"account_id": i, "name": people[i]["name"], "by": "project", "at": K._iso(K._now()), "expires": None, "why": "On the project team"} for i in sorted(ids)]
    return out + [g for g in rec.get("grants") or [] if K._live(g) and g.get("account_id") not in ids]


def _sync_rows(plane, pid: str) -> None:
    """Keep the library rows that point at the project in step with its access."""
    try:
        rec = P.read(plane, pid)
        with lock_for(L._index_path(plane)):
            rows = L._index(plane)
            mine = [r for r in rows if r.get("project") == pid]
            if not mine:
                return
            grants, sens = _grant_rows(plane, rec), sensitivity(rec)
            for r in mine:
                r.update(sensitivity=sens, grants=grants, visibility="project" if sens == "restricted" else "company")
            write_json_atomic(L._index_path(plane), rows)
    except Exception:  # noqa: BLE001 - a library hiccup never undoes the access change
        log.warning("the library rows of project %s could not be updated", pid)


def add_file(plane, viewer, pid: str, filename: str, data: bytes, kind: str = "upload") -> dict:
    """Store a file in the project's folder and point a library row at it (`project: <pid>`). Needs the full level."""
    rec, _ = require(plane, viewer, pid, "full")
    from sh_platform.v1 import i2_north as N
    name = N.checked_name(filename, data)
    sha = hashlib.sha256(data).hexdigest()
    sens = sensitivity(rec)
    with lock_for(L._index_path(plane)):
        rows = L._index(plane)
        have = next((r for r in rows if r.get("project") == pid and r.get("sha256") == sha), None)
        if have:
            return {k: have[k] for k in ("id", "name", "size", "at", "uploaded_by")}
        from sh_platform.v1 import l3_library as F  # L3: projects/<pid>/files/<folder>/<name>
        sorted_to = F.classify(name)
        dest = folder(plane, pid) / sorted_to["folder"] / name
        if dest.is_file() and dest.read_bytes() != data:
            dest = dest.with_name(f"{dest.stem}-{sha[:6]}{dest.suffix}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        item = L._item(dest.name, L._kind(dest.name, None, ""), f"{kind.capitalize()} in project {rec.get('title')}", viewer.name or "A team member",
                       viewer.account_id, sha, len(data), "project" if sens == "restricted" else "company", f"projects/{pid}/files/{sorted_to['folder']}/{dest.name}")
        item.update(folder=sorted_to["folder"], folder_by="rules", subfolder=sorted_to["subfolder"], project=pid, sensitivity=sens, grants=_grant_rows(plane, rec), topic=["Project folder"], pii={"found": False, "kinds": [], "where": []})
        rows.append(item)
        write_json_atomic(L._index_path(plane), rows)
    return {k: item[k] for k in ("id", "name", "size", "at", "uploaded_by")}


def files(plane, viewer, pid: str) -> list[dict]:
    require(plane, viewer, pid, "read")
    return [L.shown(i, viewer, plane) for i in L._index(plane) if i.get("project") == pid and L.visible(i, viewer)]


# ---- the intent template's access question -------------------------------------------------------------------------------------------

def template_field() -> dict:
    """The `access` field of the default intent-of-work template: good to have, asked second, with the defaults said out loud."""
    return {"key": "access", "label": "Who should be able to see this work", "required": False, "type": "choice",
            "help": "Everyone in the company, only the people you name, or only you and the people you name with no preview for others.",
            "choices": ["Everyone in the company", "Only the people you name", "Only you and the people you name"],
            "learn": "who may see this work: everyone in the company (Open), only the people they name (Internal), or only them and the people they name "
                     "with no preview for others (Restricted)",
            "ask": ASK, "parse": None, "default": "only the people you name, with the person who asked and the sponsor on the team"}


def place(goals: dict) -> dict:
    """North's goals with the access question second, whatever the template's order (it is asked once, near the start).
    A company whose standard template was seeded before G1 has no `access` field: the question is added from the same field."""
    if goals and "access" not in goals:
        f = template_field()
        goals = {**goals, "access": (f["learn"], f["ask"], None, f["default"])}
    if "access" not in goals or len(goals) < 3:
        return goals
    first = next(iter(goals))
    return {first: goals[first], "access": goals["access"], **{k: v for k, v in goals.items() if k not in (first, "access")}}
