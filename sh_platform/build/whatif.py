"""POST /api/company/whatif: what one driver's change moves, along the viewer's own map. Linear; nothing is saved."""
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from sh_platform.consume.feeds import _pack_names, build
from sh_platform.graph.read import graph_for
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
EDGES, BACK, DEPTH = ("moves", "measured_by"), ("uses", "fed_by"), 3  # BACK edges are followed against their arrow: field, source, measure


class Body(BaseModel):
    driver: str
    change_pct: float


class SaveBody(Body):
    note: str = ""


def _sign(e: dict) -> int | None:
    """-1 or 1 when the edge says which way it pushes (a sign, or a lowers relation); None when the map is silent."""
    if e["type"] == "lowers" or str(e.get("sign")) in ("-1", "lowers"):
        return -1
    return 1 if str(e.get("sign")) in ("1", "+1", "raises") else None


def _reach(g: dict, driver: str, pct: float) -> list[dict]:
    nodes = {n["id"]: n for n in g["nodes"] if not n.get("restricted")}
    out: dict[str, list[tuple[str, int | None]]] = {}
    for e in g["edges"]:
        if e["type"] in EDGES + BACK + ("lowers",) and not e.get("restricted") and e["from"] in nodes and e["to"] in nodes:
            a, b = (e["from"], e["to"]) if e["type"] not in BACK else (e["to"], e["from"])
            out.setdefault(a, []).append((b, _sign(e)))
    seen, frontier, moved = {driver}, [([driver], 1, False)], []
    for _ in range(DEPTH):
        nxt = []
        for path, sign, assumed in frontier:
            for to, s in out.get(path[-1], []):
                if to not in seen:
                    seen.add(to)
                    nxt.append((path + [to], sign * (s or 1), assumed or s is None))
        frontier = nxt
        for p, sign, assumed in nxt:
            if nodes[p[-1]]["type"] == "Measure":
                halves = sum(nodes[x]["type"] == "Lever" for x in p)
                moved.append({"code": p[-1], "label": nodes[p[-1]]["label"], "path": p, "change_pct": sign * pct / 2 ** halves, "assumed_direction": assumed})
    return moved


def _num(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _line(m: dict) -> str:
    """The one sentence a row reads as, kept as it was shown: 'K16 Excess return versus benchmark: 0.44 to 0.48 (assumed same way)'."""
    lat = m["latest"]
    tail = f"{_num(lat['value'])} to {_num(lat['moved_value'])}" if lat else "Not available yet"
    return f"{m['label']}: {tail}" + (" (assumed same way)" if m["assumed_direction"] else "")


def _run(request: Request, body: Body):
    try:
        plane = _plane(request)
    except PermissionError:
        raise HTTPException(403, "No company space") from None
    viewer = _viewer(request)
    g = graph_for(plane, viewer)
    nodes = {n["id"]: n["label"] for n in g["nodes"] if not n.get("restricted")}
    if body.driver not in nodes:
        raise HTTPException(404, "Not on your map")
    # every "from" figure is the Feeds figure for this viewer; a measure Feeds hides from them is left out
    feeds = {m["code"]: m for m in build(plane, viewer, _pack_names(request))["measures"]}
    moved = []
    for m in _reach(g, body.driver, body.change_pct):
        code = m["code"].split(":", 1)[-1]
        f = feeds.get(code) or feeds.get(code.upper())
        if f is not None and not f.get("may_see", True):
            continue
        lat = (f or {}).get("latest")
        m["latest"] = {"period": lat["period"], "value": lat["value"], "moved_value": round(lat["value"] * (1 + m["change_pct"] / 100), 4)} if lat and lat.get("value") is not None else None
        if f is not None:
            m["label"] = f"{code} {f['name']}" if f["name"] != code else f["name"]
        m["text"] = _line(m)
        moved.append(m)
    via = list(dict.fromkeys(nodes[x] for m in moved for x in m["path"][1:-1]))
    through = " through " + (", ".join(via[:-1]) + " and " + via[-1] if len(via) > 1 else via[0]) if via else ""
    basis = f"Follows the map from {nodes[body.driver]}{through} to the measures it feeds; a straight-line estimate."
    if any(m["assumed_direction"] for m in moved):
        basis += " Assumed to move the same way; the map does not yet say which way."
    return plane, {"driver": body.driver, "moved": moved, "basis": basis}


def _mine(plane, request: Request):
    return plane.path("context", "whatif", f"{request.state.account_id}.json")


@router.post("/api/company/whatif")
def post_api_company_whatif(request: Request, body: Body):
    return _run(request, body)[1]


@router.post("/api/company/whatif/keep")
@router.post("/api/company/whatif/save")
def post_api_company_whatif_save(request: Request, body: SaveBody):
    plane, result = _run(request, body)
    f = _mine(plane, request)
    item = {"id": secrets.token_hex(6), "driver": body.driver, "change_pct": body.change_pct, "note": body.note.strip()[:500],
            "saved_at": datetime.now(timezone.utc).isoformat(), "result": result}
    with lock_for(f):
        try:
            items = read_json_strict(f, list) or []
        except (OSError, ValueError):
            raise HTTPException(500, "Your saved scenarios could not be read") from None
        write_json_atomic(f, items + [item])
    return item


@router.get("/api/company/whatif/kept")
@router.get("/api/company/whatif/scenarios")
def get_api_company_whatif_scenarios(request: Request):
    try:
        plane = _plane(request)
        return {"scenarios": read_json_strict(_mine(plane, request), list) or []}
    except PermissionError:
        raise HTTPException(403, "No company space") from None
    except (OSError, ValueError):
        raise HTTPException(500, "Your saved scenarios could not be read") from None


@router.delete("/api/company/whatif/scenarios/{scenario_id}")
def delete_api_company_whatif_scenario(request: Request, scenario_id: str):
    try:
        f = _mine(_plane(request), request)
    except PermissionError:
        raise HTTPException(403, "No company space") from None
    with lock_for(f):
        try:
            items = read_json_strict(f, list) or []
        except (OSError, ValueError):
            raise HTTPException(500, "Your saved scenarios could not be read") from None
        keep = [x for x in items if x.get("id") != scenario_id]
        if len(keep) == len(items):
            raise HTTPException(404, "No such scenario")
        write_json_atomic(f, keep)
    return {"deleted": scenario_id}

