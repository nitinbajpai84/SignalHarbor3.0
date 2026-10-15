"""E1d access to structured data: which legal entities and portfolios a person may see in the warehouse.

A person reaches data through access groups (memberships, not expired) whose scopes name a legal entity or a portfolio with a level
(full, read; "preview" never opens structured rows). A portfolio is also seen when its legal entity is in scope. company_admin sees all.
Fail closed: no viewer match, no warehouse, any error -> nothing. Document-type scopes are for the document helpers, not read here.
Admin changes are written to `warehouse/access_admin_log.jsonl`.
"""
from __future__ import annotations

import json
import logging

from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id  # organization_id is a uuid derived from the company id

log = logging.getLogger(__name__)
RANK = {"none": 0, "read": 1, "full": 2}
_BACK = {v: k for k, v in RANK.items()}


def is_admin(viewer) -> bool:
    return "company_admin" in set(getattr(viewer, "roles", ()) or ())


def user_id_of(con, viewer) -> str | None:
    """The warehouse users.id for a viewer: external identity = account id, else display name (only when unique)."""
    acc = getattr(viewer, "account_id", None)
    if acc:
        r = con.execute("select id from users where external_identity_id = ? and is_active", [acc]).fetchall()
        if len(r) == 1:
            return str(r[0][0])
    if acc or getattr(viewer, "shared_name", False):  # an account id that matches no user never falls back to the name
        return None
    r = con.execute("select id from users where display_name = ? and is_active", [getattr(viewer, "name", "")]).fetchall()
    return str(r[0][0]) if len(r) == 1 else None


def _grants(plane, viewer) -> tuple[dict[str, int], dict[str, int], dict[str, str]] | None:
    """(entity -> rank, portfolio -> rank, portfolio -> entity) for a non-admin viewer; None on any failure."""
    try:
        with wh.connect(plane, read_only=True) as con:
            uid = user_id_of(con, viewer)
            ent: dict[str, int] = {}
            pf: dict[str, int] = {}
            if uid:
                rows = con.execute(
                    "select s.scope_type, s.scope_value, s.access_level from access_group_memberships m "
                    "join access_group_scopes s on s.access_group_id = m.access_group_id "
                    "where m.user_id = ? and (m.expires_at is null or m.expires_at > ?)",
                    [uid, wh.now()]).fetchall()
                for typ, val, lvl in rows:
                    d = ent if typ == "legal_entity" else pf if typ == "portfolio" else None
                    if d is not None and RANK.get(lvl):
                        d[val] = max(d.get(val, 0), RANK[lvl])
            owner = {str(r[0]): str(r[1]) for r in con.execute(
                "select id, legal_entity_id from portfolios").fetchall()}
        return ent, pf, owner
    except Exception:  # fail closed, but say so
        log.warning("access lookup failed; denying", exc_info=True)
        return None


def _all(plane) -> tuple[set[str], set[str]]:
    with wh.connect(plane, read_only=True) as con:
        e = {str(r[0]) for r in con.execute("select id from legal_entities").fetchall()}
        p = {str(r[0]) for r in con.execute("select id from portfolios").fetchall()}
    return e, p


def level(plane, viewer, entity_id=None, portfolio_id=None) -> str:
    """full, read or none for one entity and/or portfolio (both given: the better of the two grants). Neither given: none."""
    if entity_id is None and portfolio_id is None:
        return "none"
    if is_admin(viewer):
        return "full"
    g = _grants(plane, viewer)
    if g is None:
        return "none"
    ent, pf, owner = g
    best = 0
    if entity_id is not None:
        best = max(best, ent.get(entity_id, 0))
    if portfolio_id is not None:
        best = max(best, pf.get(portfolio_id, 0), ent.get(owner.get(portfolio_id), 0))
    return _BACK[best]


def _visible(plane, viewer, which: int) -> set[str]:
    if is_admin(viewer):
        try:
            return _all(plane)[which]
        except Exception:
            log.warning("access lookup failed; denying", exc_info=True)
            return set()
    g = _grants(plane, viewer)
    if g is None:
        return set()
    ent, pf, owner = g
    if which == 0:
        return set(ent) | {owner[p] for p in pf if p in owner}
    return set(pf) | {p for p, e in owner.items() if e in ent}


def visible_entities(plane, viewer) -> set[str]:
    return _visible(plane, viewer, 0)


def visible_portfolios(plane, viewer) -> set[str]:
    return _visible(plane, viewer, 1)


# ---- admin (company_admin only; the route checks the role, these write and log) ----

def _log(plane, viewer, action: str, **detail) -> None:
    line = {"at": wh.now().isoformat(), "by": getattr(viewer, "name", "?"), "action": action, **detail}
    with plane.path("warehouse", "access_admin_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def list_groups(plane) -> list[dict]:
    with wh.connect(plane) as con:
        out = []
        for gid, name, desc in con.execute("select id, group_name, description from access_groups order by group_name").fetchall():
            members = [{"user_id": str(u), "name": n, "expires_at": x} for u, n, x in con.execute(
                "select m.user_id, u.display_name, m.expires_at from access_group_memberships m left join users u on u.id = m.user_id "
                "where m.access_group_id = ? order by u.display_name", [gid]).fetchall()]
            scopes = [{"scope_type": t, "scope_value": v, "access_level": a} for t, v, a in con.execute(
                "select scope_type, scope_value, access_level from access_group_scopes where access_group_id = ? order by scope_type, scope_value", [gid]).fetchall()]
            out.append({"id": str(gid), "group_name": name, "description": desc, "members": members, "scopes": scopes})
        return out


def add_group(plane, viewer, group_name: str, description: str = "") -> str:
    if not group_name.strip():
        raise ValueError("group_name is needed")
    gid = wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into access_groups (id, organization_id, group_name, description) values (?,?,?,?)",
                    [gid, org_id(plane), group_name, description])
    _log(plane, viewer, "add_group", group=gid, name=group_name)
    return gid


def add_member(plane, viewer, group_id: str, user_id: str, expires_at=None) -> str:
    mid = wh.new_id()
    with wh.connect(plane) as con:
        if not con.execute("select 1 from access_groups where id = try_cast(? as uuid)", [group_id]).fetchone():
            raise LookupError("unknown group")
        if not con.execute("select 1 from users where id = try_cast(? as uuid)", [user_id]).fetchone():
            raise LookupError("unknown user")
        con.execute("delete from access_group_memberships where access_group_id = try_cast(? as uuid) and user_id = try_cast(? as uuid)", [group_id, user_id])  # re-adding renews
        con.execute("insert into access_group_memberships (id, organization_id, access_group_id, user_id, granted_at, granted_by, expires_at) values (?,?,?,?,?,?,?)",
                    [mid, org_id(plane), group_id, user_id, wh.now(), user_id_of(con, viewer), expires_at])
    _log(plane, viewer, "add_member", group=group_id, user=user_id, expires_at=str(expires_at) if expires_at else None)
    return mid


def remove_member(plane, viewer, group_id: str, user_id: str) -> bool:
    with wh.connect(plane) as con:
        n = con.execute("select count(*) from access_group_memberships where access_group_id = try_cast(? as uuid) and user_id = try_cast(? as uuid)",
                        [group_id, user_id]).fetchone()[0]
        con.execute("delete from access_group_memberships where access_group_id = try_cast(? as uuid) and user_id = try_cast(? as uuid)",
                    [group_id, user_id])
    _log(plane, viewer, "remove_member", group=group_id, user=user_id, removed=bool(n))
    return bool(n)


def add_scope(plane, viewer, group_id: str, scope_type: str, scope_value: str, access_level: str) -> str:
    if scope_type not in ("legal_entity", "portfolio", "document_type"):
        raise ValueError("scope_type must be legal_entity, portfolio or document_type")
    if access_level not in ("full", "read", "preview"):
        raise ValueError("access_level must be full, read or preview")
    if not scope_value:
        raise ValueError("scope_value is needed")
    sid = wh.new_id()
    with wh.connect(plane) as con:
        if not con.execute("select 1 from access_groups where id = try_cast(? as uuid)", [group_id]).fetchone():
            raise LookupError("unknown group")
        con.execute("delete from access_group_scopes where access_group_id = ? and scope_type = ? and scope_value = ?", [group_id, scope_type, scope_value])
        con.execute("insert into access_group_scopes (id, organization_id, access_group_id, scope_type, scope_value, access_level) values (?,?,?,?,?,?)",
                    [sid, org_id(plane), group_id, scope_type, scope_value, access_level])
    _log(plane, viewer, "add_scope", group=group_id, scope=f"{scope_type}:{scope_value}", level=access_level)
    return sid
