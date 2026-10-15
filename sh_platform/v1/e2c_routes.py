"""E2c routes: matches waiting for a person.

- `GET /api/v1/evidence/aliases` → [{id, name_in_file, instrument_name, source_name, ...}] (proposed only)
- `POST /api/v1/evidence/aliases/{identifier_id}/approve` (→ the match {identifier_id, source_name, instrument_name, status, can_approve}) · `POST /api/v1/evidence/aliases/{identifier_id}/reject` {reason?}
- `GET /api/v1/instruments` → {instruments: [{instrument_id, name, instrument_type, asset_class, currency, names, codes}], asset_classes}
  (Settings > identifiers and Settings > instruments: every signed other name and code of each instrument, and its asset class)
- `POST /api/v1/instruments/{instrument_id}/asset-class` {asset_class} → the instrument; only an instrument without a class, only a
  class the company already uses; the next limits check counts it there.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import e2_match as M
from sh_platform.v1 import e2_screen as S
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_routes import _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()
CODES = {403: "not_allowed", 404: "not_found", 409: "conflict"}


def _answer(fn):
    try:
        return fn()
    except M.MatchRefused as e:
        return JSONResponse({"error": CODES.get(e.status, "invalid"), "message": e.message}, status_code=e.status)
    except PermissionError:
        return JSONResponse({"error": "forbidden", "message": "Your company space could not be opened. Please ask your administrator."}, status_code=403)


@router.get("/api/v1/evidence/aliases")
def aliases(request: Request):
    viewer_of(request)
    return _answer(lambda: M.proposals(_plane(request)))


@router.post("/api/v1/evidence/aliases/approve-exact")
def approve_exact(request: Request):
    """One click: every waiting match that is exactly the instrument's own name -> {approved: [names], left: n}."""
    viewer = viewer_of(request)
    return _answer(lambda: M.approve_exact(_plane(request), viewer))


@router.post("/api/v1/evidence/aliases/{identifier_id}/approve")
def approve(identifier_id: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: (M.approve_alias(_plane(request), identifier_id, viewer), S.match_of_identifier(_plane(request), identifier_id, viewer))[1])


@router.post("/api/v1/evidence/aliases/{identifier_id}/reject")
async def reject(identifier_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _json_body(request, 8192)
    return body if isinstance(body, JSONResponse) else _answer(
        lambda: M.reject_alias(_plane(request), identifier_id, viewer, str(body.get("reason") or "")))


DATA_TEAM = {"company_admin", "analyst"}


def _refuse(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": CODES.get(status, "invalid"), "message": message}, status_code=status)


def instrument_list(plane) -> dict:
    """Each instrument with its signed other names and codes (by source) and its asset class; the classes in use."""
    org = org_id(plane)
    with wh.connect(plane, read_only=True) as con:
        inst = con.execute("select id, canonical_name, instrument_type, asset_class, currency from instruments where organization_id = ? "
                           "order by canonical_name", [org]).fetchall()
        ids = con.execute("select i.instrument_id, i.identifier_type, i.identifier_value, s.source_name from instrument_identifiers i "
                          "left join source_systems s on s.id = i.source_system_id where i.organization_id = ? and i.mapping_status = 'approved' "
                          "order by i.identifier_value", [org]).fetchall()
    out = {str(r[0]): {"instrument_id": str(r[0]), "name": r[1], "instrument_type": r[2], "asset_class": r[3], "currency": r[4], "names": [], "codes": [], "contacts": []}
           for r in inst}
    for iid, typ, value, source in ids:
        row = out.get(str(iid))
        if row is None or value == row["name"]:
            continue
        if "contact" in str(typ):  # a contact is a person, not a name of the instrument: its own list (AUC3-07)
            row["contacts"].append({"value": value, "kind": "contact", "source": source})
            continue
        row["names" if "name" in str(typ) else "codes"].append({"value": value, "kind": str(typ).replace("_", " "), "source": source})
    return {"instruments": list(out.values()), "asset_classes": sorted({r[3] for r in inst if r[3]})}


def set_asset_class(plane, instrument_id: str, asset_class: str) -> dict:
    """Give a class to an instrument that has none. Raises M.MatchRefused in plain words."""
    known = instrument_list(plane)
    row = next((i for i in known["instruments"] if i["instrument_id"] == instrument_id), None)
    if row is None:
        raise M.MatchRefused(404, "There is no such instrument.")
    if row["asset_class"]:
        raise M.MatchRefused(409, f"{row['name']} already has the class {row['asset_class'].replace('_', ' ')}.")
    if asset_class not in known["asset_classes"]:
        raise M.MatchRefused(400, "Choose one of the classes the company already uses.")
    with wh.connect(plane) as con:
        con.execute("update instruments set asset_class = ? where organization_id = ? and id = ? and asset_class is null",
                    [asset_class, org_id(plane), instrument_id])
    return {**row, "asset_class": asset_class}


@router.get("/api/v1/instruments")
def instruments(request: Request):
    viewer_of(request)
    return _answer(lambda: instrument_list(_plane(request)))


@router.post("/api/v1/instruments/{instrument_id}/asset-class")
async def asset_class(instrument_id: str, request: Request):
    viewer = viewer_of(request)
    if not set(viewer.roles) & DATA_TEAM:
        return _refuse(403, "Only the data team or the administrator gives an instrument its class.")
    body = await _json_body(request, 2048)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: set_asset_class(_plane(request), instrument_id, str(body.get("asset_class") or "").strip()))
