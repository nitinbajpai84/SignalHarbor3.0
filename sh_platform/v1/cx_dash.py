"""Card C1: dashboards over a project's gold tables (docs/plan/V3-CENTRES-CARDS.md, facts 4 and 8).

A dashboard is `data/<company>/consume/<project_id>/dashboards/<id>.json`:
{id, title, project_id, tiles:[{id, title, kpi, sql, spec, note, state: proposed|accepted}], audience, refresh, created_by, updated_at}.
Tile SQL is one SELECT over the project's gold tables (and silver, read-only), checked here from DuckDB's own parse tree and run
here with a 5,000-row cap. `spec` is a Vega-Lite spec without data; `tile_data` injects nothing, it returns the rows beside the spec
and the screen puts them in. Lumen (cx_lumen) proposes; a person accepts or rejects. Nothing here writes to the warehouse."""
from __future__ import annotations

import json
import logging
import re
import secrets
from contextlib import suppress
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import e0a_catalogue as cat
from sh_platform.v1 import e1_access as access
from sh_platform.v1 import p1_project, wh
from sh_platform.v1.p1_project import Refused

log = logging.getLogger(__name__)
ROW_CAP = 5000
REFRESH = ("same", "daily", "weekly")
MARKS = ("line", "bar", "area", "point", "text")
_DID = re.compile(r"^dash-[0-9a-f]{8}$")
_TID = re.compile(r"^t-[0-9a-f]{6}$")
_BAD_FN = re.compile(r"^(read_|parquet_|glob$|getenv$|current_setting$|query$|query_table$|sniff_|load_|install_|duckdb_|pragma_|which_secret$|write_)")
_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]{0,62}$")
NOT_GOLD = "A tile can only read this project's gold tables and the core model."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def who(viewer) -> str:
    return getattr(viewer, "account_id", None) or getattr(viewer, "name", "") or ""


def jsonable(v):
    if isinstance(v, (Decimal, UUID)):
        return float(v) if isinstance(v, Decimal) else str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


# ---- the project's tables ------------------------------------------------------------------------------------------------------

def _gold_names(plane, project: dict) -> list[str]:
    """The project's gold tables as the catalogue (D1) records them: gold_<project_slug>_<name>, owned by this project. UC5: once the project
    has a live plan, only the gold tables that plan still builds; a table an earlier version built is left behind, never read by a tile."""
    names = set(cat.tables_for_project(plane, project["id"])["gold"])
    from sh_platform.v1 import b6_run  # deferred: b6_run imports the studio side
    live = b6_run.latest_plan(plane, project["id"], live=True)
    built = {t["name"] for t in (live or {}).get("tables") or [] if t.get("layer") == "gold"}
    if built:  # a live plan that lists no gold tables (an older plan) filters nothing
        names &= built
    return sorted(names)


def gold_tables(plane, pid: str) -> list[dict]:
    """The project's gold tables: [{name, columns: [{name, type}], rows, refreshed}]."""
    names = _gold_names(plane, p1_project.read(plane, pid))
    out, refreshed = [], _last_refresh(plane, pid)
    with wh.connect(plane) as con:
        for n in names:
            cols = con.execute("select column_name, data_type from information_schema.columns where table_schema = 'main' and table_name = ? order by ordinal_position", [n]).fetchall()
            if cols:
                out.append({"name": n, "columns": [{"name": c, "type": t} for c, t in cols], "rows": con.execute(f'select count(*) from "{n}"').fetchone()[0], "refreshed": refreshed})
    return out


# Identity, access, agent and document tables are never readable from a tile: rows go to the whole audience with no E1d filter.
_HIDDEN = ("users", "access_", "agent_runs", "approvals", "pulse_items", "audit", "documents", "document_passages", "extracted_fields")


def _allowed(plane, pid: str) -> set[str]:
    silver = {t["name"] for t in cat.tables(plane) if not t["name"].startswith(("gold_", "bronze_") + _HIDDEN)}
    return {t["name"] for t in gold_tables(plane, pid)} | silver


# ---- SQL: one SELECT over allowed tables -------------------------------------------------------------------------------------------

def _walk(node, tables: set[str], ctes: set[str]) -> None:
    if isinstance(node, dict):
        t = node.get("type")
        if t == "BASE_TABLE":
            if node.get("catalog_name") or node.get("schema_name") not in ("", "main", None):
                raise Refused(400, NOT_GOLD)
            tables.add(node.get("table_name", ""))
        elif t == "TABLE_FUNCTION":
            raise Refused(400, "A tile cannot read files or call table functions.")
        elif node.get("class") == "FUNCTION" and _BAD_FN.match(str(node.get("function_name", "")).lower()):
            raise Refused(400, "That function is not allowed in a tile.")
        for k, v in node.items():
            if k == "cte_map":
                ctes.update(e["key"] for e in v.get("map", []))
            _walk(v, tables, ctes)
    elif isinstance(node, list):
        for v in node:
            _walk(v, tables, ctes)


def tables_in(plane, sql: str) -> set[str]:
    """The tables a SELECT reads; refuses anything but a single plain SELECT."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 8000:
        raise Refused(400, "A tile needs one SELECT query.")
    with wh.connect(plane) as con:
        raw = json.loads(con.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    if raw.get("error"):
        raise Refused(400, "A tile can only be one SELECT query; nothing is written or changed.")
    if len(raw["statements"]) != 1:
        raise Refused(400, "A tile can only be one SELECT query.")
    tables, ctes = set(), set()
    _walk(raw["statements"][0], tables, ctes)
    return tables - ctes


def check_sql(plane, pid: str, sql: str) -> tuple[list[str], list[str]]:
    """Refuse a query that is not a SELECT over the project's gold and the core model, or does not run. -> (tables, columns)"""
    used = tables_in(plane, sql)
    if not used or used - _allowed(plane, pid):
        raise Refused(400, NOT_GOLD if used else "A tile has to read at least one table.")
    return sorted(used), columns_of(plane, sql)


def columns_of(plane, sql: str) -> list[str]:
    try:
        with wh.connect(plane) as con:
            return [d[0] for d in con.execute(f"select * from ({sql.strip().rstrip(';')}) as q limit 0").description]
    except Exception as e:  # noqa: BLE001 - DuckDB raises several types; the person gets one plain sentence
        log.info("tile query refused: %s", str(e).splitlines()[0][:200])
        raise Refused(400, "That query does not run on this project's tables. Check the table and column names.") from None


def run_sql(plane, sql: str) -> tuple[list[str], list[dict], bool]:
    """Run an already-checked SELECT; returns (columns, rows, capped)."""
    with wh.connect(plane) as con:
        cur = con.execute(f"select * from ({sql.strip().rstrip(';')}) as q limit {ROW_CAP + 1}")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return cols, jsonable(rows[:ROW_CAP]), len(rows) > ROW_CAP


# ---- Vega-Lite spec: no data in it ---------------------------------------------------------------------------------------------

def _no_data(node) -> None:
    if isinstance(node, dict):
        if any(k in node for k in ("data", "datasets", "url", "transform_data")):
            raise Refused(400, "A chart spec must not carry its own data; the program supplies the rows.")
        if any(k in node for k in ("transform", "href")):
            raise Refused(400, "A chart spec is only a mark and its encoding: no transforms or links.")
        for v in node.values():
            _no_data(v)
    elif isinstance(node, list):
        for v in node:
            _no_data(v)


def check_spec(spec, columns: list[str]) -> dict:
    if not isinstance(spec, dict):
        raise Refused(400, "The chart spec could not be read.")
    _no_data(spec)
    mark = spec.get("mark")
    mark = mark.get("type") if isinstance(mark, dict) else mark
    if mark not in MARKS:
        raise Refused(400, "That chart type is not available. Use a line, bar, area, points, a number or a table.")
    for ch, enc in (spec.get("encoding") or {}).items():
        field = enc.get("field") if isinstance(enc, dict) else None
        if field and field not in columns:
            raise Refused(400, f"The chart uses a column ({field}) that the tile's data does not have.")
    return spec


# ---- dashboards ----------------------------------------------------------------------------------------------------------------

def _dir(plane, pid: str):
    p1_project.read(plane, pid)
    return plane.path("consume", pid, "dashboards")


def _file(plane, pid: str, did: str):
    if not isinstance(did, str) or not _DID.match(did):
        raise Refused(404, "There is no such dashboard.")
    return _dir(plane, pid) / f"{did}.json"


def _load(plane, pid: str, did: str) -> dict:
    try:
        rec = read_json_strict(_file(plane, pid, did), dict)
    except (OSError, ValueError):
        raise Refused(500, "The dashboard could not be read. Please ask your administrator.") from None
    if rec is None:
        raise Refused(404, "There is no such dashboard.")
    return rec


def find_pid(plane, did: str) -> str:
    """The project a dashboard belongs to, from its id alone (the read-only link carries no project)."""
    if not isinstance(did, str) or not _DID.match(did):
        raise Refused(404, "There is no such dashboard.")
    hit = next(iter(plane.path("consume").glob(f"*/dashboards/{did}.json")), None)
    if hit is None:
        raise Refused(404, "There is no such dashboard.")
    return hit.parent.parent.name


def _save(plane, rec: dict) -> dict:
    rec["updated_at"] = _now()
    rec["rev"] = int(rec.get("rev") or 0) + 1  # every save counts, so an editor holding an older copy can be told (b7_studio.set_layout)
    write_json_atomic(_file(plane, rec["project_id"], rec["id"]), rec)
    return rec


def create(plane, viewer, pid: str, title: str, refresh: str = "same", draft: bool = False, personal: bool = False) -> dict:
    title = str(title or "").strip()[:200]
    if not title:
        raise Refused(400, "Give the dashboard a title.")
    if refresh not in REFRESH:
        raise Refused(400, "Refresh can be: same as the data, daily or weekly.")
    d = _dir(plane, pid)
    rec = {"id": "dash-" + secrets.token_hex(4), "title": title, "project_id": pid, "tiles": [], "audience": [], "refresh": refresh,
           "created_by": who(viewer), "updated_at": ""}
    if personal:  # CL1: made in Consume: a personal draft, seen only by its maker; sharing goes through the Build studio approval
        rec["personal"] = True
    if draft:  # made in the Build studio: it stays out of Consume until someone else approves it (DS1)
        rec |= {"layout": {"rows": 2, "items": []}, "lifecycle": {"status": "draft", "version": 1, "published": None, "company_wide": False}}
    with lock_for(d):
        return _save(plane, rec)


def own_dashboard(plane, viewer, pid: str) -> dict:
    """The person's own dashboard on this project, made for them when they have none (private until they share it)."""
    for p in sorted(_dir(plane, pid).glob("dash-*.json")):
        with suppress(OSError, ValueError):
            rec = read_json_strict(p, dict)
            if rec and rec.get("created_by") == who(viewer) and "lifecycle" not in rec:  # a studio dashboard is never the chat's scratch pad (DS1)
                return rec
    return create(plane, viewer, pid, "My dashboard", personal=True)


def list_for(plane, viewer, pid: str) -> list[dict]:
    out = []
    for p in sorted(_dir(plane, pid).glob("dash-*.json")):
        with suppress(OSError, ValueError):
            rec = read_json_strict(p, dict)
            if rec and (view := published_view(rec)) and may_view(plane, viewer, rec):  # Consume lists the published version only (DS1)
                out.append(_summary(view))
    return out


def _summary(rec: dict) -> dict:
    return {k: rec[k] for k in ("id", "title", "project_id", "refresh", "created_by", "updated_at")} | {"tiles": len(rec["tiles"]), "accepted": sum(t["state"] == "accepted" for t in rec["tiles"])}


# ---- lifecycle: draft -> submitted -> published; an edit of a published one starts a new draft version (DS1) ---------------------
# `lifecycle` = {status: draft|submitted|published, version, published: snapshot|None, submitted_by/at, approved_by/at, sent_back, company_wide}.
# A record with no lifecycle was made before the studio: it counts as published as it stands (migrated in code, nothing rewritten).
SIZES = {"small": 3, "medium": 6, "wide": 9, "full": 12}


def ensure_lifecycle(rec: dict) -> dict:
    if rec.get("lifecycle") is None:
        rec["lifecycle"] = {"status": "published", "version": 1, "company_wide": False,
                            "published": {"version": 1, "title": rec["title"], "tiles": [t for t in rec["tiles"] if t["state"] == "accepted"], "layout": rec.get("layout"),
                                          "approved_by": rec["created_by"], "approved_at": rec.get("updated_at") or _now()}}
    return rec["lifecycle"]


def status_of(rec: dict) -> str:
    return (rec.get("lifecycle") or {}).get("status", "published")


def published_view(rec: dict) -> dict | None:
    """What Consume shows: the record as it was when last approved, or None while nothing has been approved yet."""
    lc = rec.get("lifecycle")
    if lc is None:
        return rec
    p = lc.get("published")
    return None if not p else rec | {"title": p["title"], "tiles": p["tiles"], "layout": p.get("layout"), "published_at": p["approved_at"], "version": p["version"],
                                     "company_wide": bool(p.get("company_wide"))}


def begin_edit(rec: dict, viewer=None) -> dict:
    """Call before changing a studio dashboard: a published one becomes a new draft version while the published one stays visible.
    `viewer` is kept among the version's editors, none of whom may approve it."""
    lc = ensure_lifecycle(rec)
    if lc["status"] == "submitted":
        raise Refused(409, "This dashboard is waiting for approval. Ask the approver to send it back before you change it.")
    if lc["status"] == "published":
        lc.update(status="draft", version=lc["published"]["version"] + 1, sent_back=None, editors=[])
    if viewer is not None and who(viewer) not in lc.setdefault("editors", []):
        lc["editors"].append(who(viewer))
    return lc


def submit(plane, viewer, pid: str, did: str) -> dict:
    rec = _editor(plane, viewer, pid, did)
    lc = ensure_lifecycle(rec)
    if lc["status"] != "draft":
        raise Refused(409, "Only a draft can be sent for approval.")
    if not any(i.get("tile") or i.get("text") for i in (rec.get("layout") or {}).get("items", [])):
        raise Refused(400, "Add at least one widget before you send the dashboard for approval.")
    lc.update(status="submitted", submitted_by=who(viewer), submitted_by_name=getattr(viewer, "name", ""), submitted_at=_now(), sent_back=None)
    return _save(plane, rec)


def can_approve(viewer, rec: dict) -> bool:
    """Head of data (the architect seat Build uses) or the project sponsor; never the person who made or submitted it."""
    from sh_platform.v1.seats import ARCHITECT, seat_of
    lc = rec.get("lifecycle") or {}
    mine = who(viewer) in (rec["created_by"], lc.get("submitted_by"), *(lc.get("editors") or []))
    return lc.get("status") == "submitted" and not mine and (ARCHITECT in seat_of(viewer) or "sponsor" in set(getattr(viewer, "roles", ()) or ()))


def decide_version(plane, viewer, pid: str, did: str, approve: bool, reason: str = "") -> dict:
    """Approve and publish the submitted version, or send it back with a reason."""
    rec = _load(plane, pid, did)
    lc = ensure_lifecycle(rec)
    if lc["status"] != "submitted":
        raise Refused(409, "This dashboard is not waiting for approval.")
    if who(viewer) in (rec["created_by"], lc.get("submitted_by"), *(lc.get("editors") or [])):
        raise Refused(403, "You cannot approve a dashboard you made or changed. Another person has to.")
    if not can_approve(viewer, rec):
        raise Refused(403, "Only the head of data or the project sponsor can approve a dashboard.")
    at, name = _now(), getattr(viewer, "name", "") or who(viewer)
    if approve:
        copy = lambda x: json.loads(json.dumps(x))  # noqa: E731 - a snapshot shares nothing with the draft
        lc.update(status="published", approved_by=who(viewer), approved_by_name=name, approved_at=at, sent_back=None,
                  published={"version": lc["version"], "title": rec["title"], "tiles": copy([t for t in rec["tiles"] if t["state"] == "accepted"]), "layout": copy(rec.get("layout")),
                             "approved_by": name, "approved_at": at, "submitted_by": lc.get("submitted_by_name") or lc.get("submitted_by"),
                             "company_wide": bool(lc.get("company_wide"))})
    else:
        reason = str(reason or "").strip()[:500]
        if not reason:
            raise Refused(400, "Say why you are sending it back, so the maker knows what to change.")
        lc.update(status="draft", sent_back={"reason": reason, "by": name, "at": at})
    return _save(plane, rec)


def _has_data(plane, viewer) -> bool:
    try:
        return bool(access.is_admin(viewer) or access.visible_entities(plane, viewer) or access.visible_portfolios(plane, viewer))
    except Exception:  # noqa: BLE001 - fail closed
        log.warning("data access lookup failed; denying", exc_info=True)
        return False


def get_published(plane, viewer, pid: str, did: str) -> dict:
    """The dashboard as Consume shows it: the published version, for its maker, the admin, its audience, or anyone with data access when marked company-wide."""
    rec = _load(plane, pid, did)
    view = published_view(rec)
    if view is None:
        raise Refused(404, "There is no such dashboard.")
    if not (may_view(plane, viewer, rec) or (view.get("company_wide") and _has_data(plane, viewer))):
        raise Refused(403, f"This dashboard is not shared with you; {maker_name(plane, rec)} can share it with you.")  # LQ-10: who can help
    return view


def maker_name(plane, rec: dict) -> str:
    """The display name of the person who made a dashboard (the one who can share it), or 'the person who made it'."""
    try:
        with wh.connect(plane) as con:
            got = con.execute("select display_name from users where external_identity_id = ?", [rec["created_by"]]).fetchone()
    except Exception:  # noqa: BLE001 - a name is a nicety; the refusal stands
        got = None
    return got[0] if got and got[0] else "the person who made it"


def company_reports(plane, viewer) -> list[dict]:
    """Published dashboards marked company-wide, for anyone with access to some data."""
    out = []
    if not _has_data(plane, viewer):
        return out
    for p in plane.path("consume").glob("*/dashboards/dash-*.json"):
        with suppress(OSError, ValueError, Refused, KeyError, TypeError):
            rec = read_json_strict(p, dict)
            view = published_view(rec) if rec else None
            if view and view.get("company_wide"):  # as approved, not as the working copy says
                out.append({"id": rec["id"], "title": view["title"], "project_id": rec["project_id"], "project_title": p1_project.read(plane, rec["project_id"])["title"],
                            "published_at": view["published_at"], "tiles": len(view["tiles"]), "link": f"/centre/consume/d/{rec['id']}"})
    return sorted(out, key=lambda d: d["published_at"], reverse=True)


def get(plane, viewer, pid: str, did: str) -> dict:
    rec = _load(plane, pid, did)
    if not may_view(plane, viewer, rec):
        raise Refused(403, "You do not have access to this dashboard.")
    return rec


def starter_open(viewer, rec: dict) -> bool:
    """H10: Lumen's starter draft belongs to the data team, not to one person."""
    return bool(rec.get("starter")) and bool({"company_admin", "analyst"} & set(getattr(viewer, "roles", ()) or ()))


def _editor(plane, viewer, pid: str, did: str) -> dict:
    rec = _load(plane, pid, did)
    if who(viewer) != rec["created_by"] and not starter_open(viewer, rec) and (not access.is_admin(viewer) or _personal(rec)):
        raise Refused(403, "Only the person who made the dashboard can change it.")
    return rec


# ---- audience: people or groups, each checked against E1d ---------------------------------------------------------------------------

def _reach(plane, entry: str) -> tuple[str, str, str]:
    """-> (label, kind, id) for a person (users.id, account id, display name or email) or a group (id or name) with access to some data, else refuse."""
    e = str(entry).strip()
    with wh.connect(plane) as con:
        rows = con.execute("select id, display_name, external_identity_id from users where is_active and (cast(id as varchar) = ? or external_identity_id = ? "
                           "or lower(display_name) = lower(?) or lower(email) = lower(?))", [e, e, e, e]).fetchall()
        if len({str(r[0]) for r in rows}) == 1:
            from sh_platform.profile.view import Viewer
            v = Viewer(name=rows[0][1], roles=frozenset(), account_id=rows[0][2])
            if access.visible_entities(plane, v) or access.visible_portfolios(plane, v):
                return rows[0][1], "user", str(rows[0][0])
            raise Refused(400, f"{rows[0][1]} has no access to the data in this dashboard, so they cannot be added.")
        if rows:
            raise Refused(400, f"More than one person matches {e}. Pick the person from the list.")
        g = con.execute("select id, group_name from access_groups where cast(id as varchar) = ? or lower(group_name) = lower(?)", [e, e]).fetchone()
        if g:
            if con.execute("select 1 from access_group_scopes where access_group_id = ? and access_level in ('read', 'full') limit 1", [g[0]]).fetchone():
                return g[1], "group", str(g[0])
            raise Refused(400, f"The group {g[1]} has no access to any data, so it cannot be added.")
    raise Refused(400, "That person or group could not be found.")


def people(plane, viewer) -> list[dict]:
    """The company's active people who could be added to an audience (E1d access to some data): [{id, name, role}]."""
    from sh_platform.profile.view import Viewer
    with wh.connect(plane) as con:
        rows = con.execute("select id, display_name, business_role, external_identity_id from users where is_active order by display_name").fetchall()
    out = []
    for i, name, role, acc in rows:
        v = Viewer(name=name, roles=frozenset(), account_id=acc)
        if access.visible_entities(plane, v) or access.visible_portfolios(plane, v):
            out.append({"id": str(i), "name": name, "role": role or ""})
    return out


def set_audience(plane, viewer, pid: str, did: str, audience: list, refresh: str | None = None) -> dict:
    rec = _editor(plane, viewer, pid, did)
    if _personal(rec):
        raise Refused(403, "A dashboard started in Consume is personal. To share it, send it for approval in Build.")
    if not isinstance(audience, list) or len(audience) > 200:
        raise Refused(400, "The audience must be a list of people or groups.")
    ids = list(dict.fromkeys(_reach(plane, str(a))[2] for a in audience))  # raises for anyone without access; stores users.id / group id
    if refresh is not None:
        if refresh not in REFRESH:
            raise Refused(400, "Refresh can be: same as the data, daily or weekly.")
        rec["refresh"] = refresh
    rec["audience"] = ids
    return _save(plane, rec)


def audience_view(plane, rec: dict) -> list[dict]:
    out = []
    for a in rec["audience"]:
        with suppress(Refused):
            name, kind, _ = _reach(plane, a)
            out.append({"id": a, "name": name, "kind": kind})
    return out


def _in_audience(plane, viewer, rec: dict) -> bool:
    """In the audience by name or through a group, and still with E1d access."""
    try:
        with wh.connect(plane) as con:
            uid = access.user_id_of(con, viewer)
            if not uid or not (access.visible_entities(plane, viewer) or access.visible_portfolios(plane, viewer)):
                return False
            groups = {r[0] for r in con.execute("select access_group_id from access_group_memberships where user_id = ? and (expires_at is null or expires_at > ?)", [uid, wh.now()]).fetchall()}
    except Exception:  # noqa: BLE001 - fail closed
        log.warning("audience lookup failed; denying", exc_info=True)
        return False
    return uid in rec["audience"] or bool({str(g) for g in groups} & set(rec["audience"]))


def _personal(rec: dict) -> bool:
    """CL1: made in Consume and not yet taken into the Build studio; once it has a lifecycle the studio approval rules (DS1) apply."""
    return bool(rec.get("personal")) and "lifecycle" not in rec


def may_view(plane, viewer, rec: dict) -> bool:
    """The maker, the company admin, or someone in the audience (by name or through a group) who still has E1d access."""
    if _personal(rec):  # CL1: only its maker, not even the admin
        return who(viewer) == rec["created_by"]
    if who(viewer) == (rec.get("lifecycle") or {}).get("approved_by") and published_view(rec) is not None:
        return True  # W3 walk: the person who approved it (the sponsor) sees what they approved, and approves its delivery (D4)
    return who(viewer) == rec["created_by"] or access.is_admin(viewer) or starter_open(viewer, rec) or (published_view(rec) is not None and _in_audience(plane, viewer, rec))  # DS1: a never-published draft has no audience


def shared_with(plane, viewer) -> list[dict]:
    """Dashboards of any project that others shared with this person (not their own), newest first, plus the latest issued report (SW1)."""
    out = []
    with wh.connect(plane) as con:
        names = dict(con.execute("select external_identity_id, display_name from users").fetchall())
    for p in plane.path("consume").glob("*/dashboards/dash-*.json"):
        with suppress(OSError, ValueError, Refused, KeyError, TypeError):
            rec = read_json_strict(p, dict)
            view = published_view(rec) if rec else None  # the published version only (DS1)
            if view and rec["created_by"] != who(viewer) and _in_audience(plane, viewer, rec):
                out.append({"id": rec["id"], "title": view["title"], "project_id": rec["project_id"],
                            "project_title": p1_project.read(plane, rec["project_id"])["title"], "shared_by": names.get(rec["created_by"]) or rec["created_by"],
                            "shared_at": view.get("published_at") or rec["updated_at"], "tiles": len(view["tiles"]), "link": f"/centre/consume/d/{rec['id']}"})
    return sorted(out, key=lambda d: d["shared_at"], reverse=True)


def latest_brief(plane, viewer) -> dict | None:
    """The latest issued report, only for someone who sees at least one portfolio (the brief shows only those lines). Fails closed."""
    from sh_platform.v1 import e1_reports
    try:
        if not (access.is_admin(viewer) or access.visible_portfolios(plane, viewer)):
            return None
    except Exception:  # noqa: BLE001 - fail closed
        log.warning("brief access lookup failed; hiding it", exc_info=True)
        return None
    issued = [(v, r) for r in e1_reports.listing(plane) for v in r["versions"] if v["status"] == "issued"]
    if not issued:
        return None
    v, r = max(issued, key=lambda x: str(x[0]["issued_at"]))
    return {"report_version_id": v["id"], "title": r["name"], "link": f"/centre/consume/brief/{v['id']}"}


# ---- tiles -----------------------------------------------------------------------------------------------------------------------

def add_proposal(plane, viewer, pid: str, did: str, tile: dict) -> dict:
    """A tile as proposed: checked, then stored as `proposed`. Used by Lumen and by a person writing a tile by hand."""
    rec = _editor(plane, viewer, pid, did)
    _, cols = check_sql(plane, pid, tile.get("sql"))
    t = {"id": "t-" + secrets.token_hex(3), "title": str(tile.get("title") or "")[:200] or "Untitled tile", "kpi": str(tile.get("kpi") or "")[:200],
         "sql": tile["sql"].strip(), "spec": check_spec(tile.get("spec"), cols), "note": str(tile.get("note") or "")[:500], "state": "proposed"}
    if isinstance(tile.get("recipe"), dict):  # what the tile was made from, so a follow-up ("as dots", "in blue") can change it
        t["recipe"] = tile["recipe"]
    old = next((x for x in rec["tiles"] if x["id"] == tile.get("replaces")), None)
    if old is not None:  # a new version of a tile: a proposed old one is dropped now, an accepted one when this is accepted
        t["replaces"] = old["id"]
        if old["state"] == "proposed":
            rec["tiles"].remove(old)
            t.pop("replaces")
    rec["tiles"].append(t)
    _save(plane, rec)
    return t


def _tile(rec: dict, tid: str) -> dict:
    if not isinstance(tid, str) or not _TID.match(tid):
        raise Refused(404, "There is no such tile.")
    for t in rec["tiles"]:
        if t["id"] == tid:
            return t
    raise Refused(404, "There is no such tile.")


def decide(plane, viewer, pid: str, did: str, tid: str, accept: bool) -> dict:
    """Accept a proposed tile (checked again) or drop it. An accepted tile cannot be rejected, only the proposed ones."""
    rec = _editor(plane, viewer, pid, did)
    t = _tile(rec, tid)
    if t["state"] != "proposed":
        raise Refused(409, "This tile has already been accepted.")
    if accept:
        check_spec(t["spec"], check_sql(plane, pid, t["sql"])[1])
        t["state"] = "accepted"
        old = next((x for x in rec["tiles"] if x["id"] == t.get("replaces")), None)
        if old is not None:
            rec["tiles"].remove(old)
        t.pop("replaces", None)
    else:
        rec["tiles"].remove(t)
    _save(plane, rec)
    return t | ({} if accept else {"state": "rejected"})


def _last_refresh(plane, pid: str) -> str | None:
    try:
        lines = plane.path("build", pid, "runs.jsonl").read_text(encoding="utf-8").splitlines()
        runs = [json.loads(x) for x in lines if x.strip()]
        return next((r.get("finished") for r in reversed(runs) if r.get("status") in ("ok", "done", "success", "live")), None)
    except (OSError, ValueError):
        return None


def tile_data(plane, viewer, pid: str, did: str, tid: str, published: bool = False) -> dict:
    """The tile's rows (cap 5,000) beside its spec: the screen puts the rows into the spec. `published`: read the published version (Consume)."""
    return tile_rows(plane, pid, (get_published if published else get)(plane, viewer, pid, did), tid)


def tile_rows(plane, pid: str, rec: dict, tid: str) -> dict:
    t = _tile(rec, tid)
    tables, cols = check_sql(plane, pid, t["sql"])
    columns, rows, capped = run_sql(plane, t["sql"])
    return {"tile": t, "spec": t["spec"], "columns": columns, "rows": rows, "capped": capped, "row_cap": ROW_CAP,
            "data_used": {"tables": tables, "last_refresh": _last_refresh(plane, pid)}}
