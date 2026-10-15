"""K1 routes: the upload proposal, access requests and answers, grants, folders by topic.

- `POST /api/v1/library/proposal` {name, data, note?} -> {sensitivity, topics, pii, by, message, ...}  (nothing is stored)
- `GET /api/v1/library/topics?q=` -> {folders: [{topic, count, items}]}   (each item with the viewer's access state)
- `GET /api/v1/library/people` -> [{account_id, name}]
- `POST /api/v1/library/{id}/access` {reason?, iid?} -> request;  `GET /api/v1/library/access` -> {incoming, mine}
- `POST /api/v1/library/access/{request_id}` {approve, days?, note?} -> request (days 0: until revoked; default 30)
- `POST /api/v1/library/{id}/grants` {account_id, days?, why?};  `DELETE /api/v1/library/{id}/grants/{account_id}`
- `PUT /api/v1/library/{id}/owner` {account_id} (company_admin, when the owner has left)
- `GET /api/v1/library/pulse` -> {needs_you, worth_a_look}  (Pulse cards)
"""

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import c4_library as L
from sh_platform.v1 import k1_access as K
from sh_platform.v1 import k1_classify as C
from sh_platform.v1.i2_routes import MAX_FILE_BODY, _answer, _decode, _json_body, _model
from sh_platform.v1.seats import viewer_of

router = APIRouter()


async def _body(request: Request, limit: int = 16 * 1024):
    return await _json_body(request, limit)


def _days(body: dict, default):
    d = body.get("days", default)
    return d if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 3650 else default


@router.post("/api/v1/library/proposal")
async def proposal(request: Request):
    viewer = viewer_of(request)
    body = await _body(request, MAX_FILE_BODY)
    if isinstance(body, JSONResponse):
        return body

    def work():
        from sh_platform.v1 import i2_north as N
        plane = _plane(request)
        data = _decode(body.get("data"))
        name = N.checked_name(str(body.get("name") or ""), data)
        note = L._note(body.get("note"))
        got = C.propose(name, data, note, _model(request, plane), plane)  # K1 holds the cap of three at once
        from sh_platform.v1 import l3_library as F
        return {**got, **F.proposal(name, got, note)}  # L3: "Goes to: <folder>"
    return await run_in_threadpool(_answer, work)


@router.get("/api/v1/library/topics")  # L3 owns /folders
def topics(request: Request, q: str = ""):
    viewer = viewer_of(request)

    def work():
        by: dict[str, list] = {}
        for i in L.listing(_plane(request), viewer, q):
            for t in i.get("topic") or C.topics_for(i["name"], i.get("note") or "")[0]:
                by.setdefault(t, []).append(i)
        return {"folders": [{"topic": t, "count": len(v), "items": v} for t, v in sorted(by.items())]}
    return _answer(work)


@router.get("/api/v1/library/people")
def people(request: Request):
    viewer_of(request)
    return _answer(lambda: [{"account_id": i, "name": p["name"]} for i, p in K.directory(_plane(request)).items()
                            if not p["disabled"] and any(r in p["roles"] for r in ("company_admin", "sponsor", "analyst"))])


@router.get("/api/v1/library/access")
def access(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: {"incoming": K.incoming(_plane(request), viewer), "mine": K.mine(_plane(request), viewer)})


@router.get("/api/v1/library/pulse")
def pulse(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: K.pulse_cards(_plane(request), viewer))


@router.post("/api/v1/library/{item_id}/access")
async def ask(item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: K.request_access(_plane(request), viewer, item_id, str(body.get("reason") or ""), body.get("iid") or None))


@router.post("/api/v1/library/access/{request_id}")
async def decide(request_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: K.answer(_plane(request), viewer, request_id, body.get("approve") is True, _days(body, K.DEFAULT_DAYS), str(body.get("note") or "")))


@router.post("/api/v1/library/{item_id}/grants")
async def add_grant(item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: K.grant(_plane(request), viewer, item_id, str(body.get("account_id") or ""), _days(body, None), str(body.get("why") or "")))


@router.delete("/api/v1/library/{item_id}/grants/{account_id}")
def remove_grant(item_id: str, account_id: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: K.revoke(_plane(request), viewer, item_id, account_id))


@router.put("/api/v1/library/{item_id}/owner")
async def reassign(item_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    return _answer(lambda: K.reassign(_plane(request), viewer, item_id, str(body.get("account_id") or "")))


# ---- People and access: the company administrator gives a colleague a different role (UC5 G3: the risk owner must act on cases) ----------

ROLE_CHOICES = ("participant", "owner", "approver", "analyst", "sponsor", "company_admin")
KEEP = ("head_of_data",)  # an extra seat a person keeps when their main role changes


@router.get("/api/v1/people/roles")
def people_roles(request: Request):
    viewer = viewer_of(request)
    if "company_admin" not in viewer.roles:
        return JSONResponse({"error": "not_allowed", "message": "Only the company administrator can change roles."}, status_code=403)
    return _answer(lambda: {"choices": list(ROLE_CHOICES), "people": [
        {"account_id": i, "name": p["name"], "roles": p["roles"]} for i, p in sorted(K.directory(_plane(request)).items(), key=lambda x: x[1]["name"])
        if not p["disabled"]]})


@router.put("/api/v1/people/{account_id}/roles")
async def put_role(account_id: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    if isinstance(body, JSONResponse):
        return body
    role = str(body.get("role") or "")
    if "company_admin" not in viewer.roles:
        return JSONResponse({"error": "not_allowed", "message": "Only the company administrator can change roles."}, status_code=403)
    if role not in ROLE_CHOICES:
        return JSONResponse({"error": "invalid", "message": "Pick one of the roles in the list."}, status_code=400)
    if account_id == viewer.account_id:
        return JSONResponse({"error": "invalid", "message": "Ask another administrator to change your own role."}, status_code=400)
    store = request.app.state.account_store
    acct = store.get(account_id)
    if not acct or acct.get("company_id") != request.state.company_id:
        return JSONResponse({"error": "not_found", "message": "We could not find that person."}, status_code=404)
    store.set_roles(acct["email"], [role, *[r for r in acct["roles"] if r in KEEP]])
    from sh_platform.v1 import e1_access  # the change is on the access trail, as other access changes are
    e1_access._log(_plane(request), viewer, "set_role", person=acct.get("display_name"), roles=role)
    return {"account_id": account_id, "name": acct.get("display_name"), "roles": store.get(account_id)["roles"]}
