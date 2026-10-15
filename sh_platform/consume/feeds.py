"""GET /api/company/feeds: the governed measures with their latest gold value, trend (up to nine periods) and range break.
Shapes: docs/plan/SHAPES.md section 6. The value is served only to viewers who pass the measure's governed access list (`may_see`)."""
import copy
import logging

import duckdb
from fastapi import APIRouter, Request

from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import governed as GS
from modules.m2_baseline.store.kpis import read_kpis
from sh_platform.consume.range import breaks, trend as _trend
from sh_platform.perf import cached
from sh_platform.profile import view
from sh_platform.profile.api import _plane, _viewer
from sh_platform.warehouse import open_readonly

log = logging.getLogger(__name__)
router = APIRouter()


def _cell(entry: dict, field: str):
    c = entry.get(field)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _open(plane):
    try:
        return open_readonly(plane)
    except duckdb.Error:
        return None


def build(plane, viewer: view.Viewer, pack_names: dict[str, str] | None = None) -> dict:
    """Cached per company, viewer and pack names until any file of the company changes; each caller gets its own copy."""
    return copy.deepcopy(cached(plane, "feeds", [plane.root], lambda: _build_open(plane, viewer, pack_names),
                                viewer=(viewer, tuple(sorted((pack_names or {}).items())))))


def _build_open(plane, viewer: view.Viewer, pack_names: dict[str, str] | None = None) -> dict:
    """One read-only warehouse connection per call, shared by the governed measures and the marts fallback."""
    con = _open(plane)
    try:
        return _build(plane, viewer, pack_names, con)
    finally:
        if con is not None:
            con.close()


def _lens(plane, code: str):
    from sh_platform.consume import lenses  # lazy: lenses imports feeds
    return lenses.lens_of(plane, str(code))["key"]


def _build(plane, viewer: view.Viewer, pack_names: dict[str, str] | None, con) -> dict:
    found = B.baselines(plane)
    base = next((b for b in found if b.get("state") == "signed"), found[0] if found else None)
    if base is None:
        return {"measures": _from_marts(con, viewer, pack_names)}  # no baseline yet: the marts that exist, named from the pack, not governed
    gov = GS._read(plane, base["id"])
    out = []
    for k in read_kpis(plane, base["id"]):
        if not isinstance(k, dict) or not k.get("id"):
            continue
        g = gov.get(k["id"]) if isinstance(gov.get(k["id"]), dict) else {}
        owner = (_cell(g, "owners") or {}).get("business") if isinstance(_cell(g, "owners"), dict) else None
        ok = view.allows(view._names(_cell(g, "may_see")), viewer)
        trend = _trend(con, str(k["id"])) if ok else []
        out.append({"code": k["id"], "name": k.get("name") or k["id"], "owner": owner,
                    "latest": trend[-1] if trend else None, "trend": trend, "range_break": breaks(trend)["break"], "may_see": ok,
                    "mine": bool(owner) and view.norm(owner) == view.norm(viewer.name),
                    "lens": _lens(plane, k["id"])})
    if not out:  # a baseline with no measures yet: show the marts that exist instead
        return {"measures": _from_marts(con, viewer, pack_names)}
    return {"measures": out}


def _from_marts(con, viewer: view.Viewer, names: dict[str, str] | None) -> list[dict]:
    """Before a baseline exists: one card per gold mart in the warehouse. Values only for the company admin (nobody is named yet, A-069)."""
    if con is None:
        return []
    try:
        tables = [r[0] for r in con.execute("select table_name from information_schema.tables where table_schema = 'gold' order by 1").fetchall()]
    except duckdb.Error:
        return []
    # not governed yet: the catalogue readers (admin, sponsor, analyst) may see the figure; participants wait for the list
    ok = view.allows(frozenset(), viewer) or bool(set(viewer.roles) & {"sponsor", "analyst"})
    out = []
    for t in tables:
        trend = _trend(con, t) if ok else []
        code = t.upper()
        out.append({"code": code, "name": (names or {}).get(code) or code, "owner": None, "latest": trend[-1] if trend else None,
                    "trend": trend, "range_break": breaks(trend)["break"], "may_see": ok, "mine": False, "governed": False, "restricted": None if ok else "Not governed yet: ask the company admin"})
    return out


def _pack_names(request: Request) -> dict[str, str]:
    rec = request.app.state.entitlements.company(request.state.company_id) or {}
    if not rec.get("industry"):
        return {}
    pack = request.app.state.packs.load(rec["industry"])
    try:
        rows = (pack.section("kpi_tree") or {}).get("kpis") or []
    except (KeyError, AttributeError):
        return {}
    return {str(r["id"]).upper(): str(r.get("name") or r["id"]) for r in rows if isinstance(r, dict) and r.get("id")}


@router.get("/api/company/feeds")
def get_api_company_feeds(request: Request) -> dict:
    return build(_plane(request), _viewer(request), _pack_names(request))
