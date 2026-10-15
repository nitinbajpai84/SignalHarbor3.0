"""T1 routes: templates, the intent's template, requests, and the company admin's agent context (skills, governance, change log).

- `GET /api/v1/templates?kind=&all=` → [summary] (adopted ones; `all=1` is the admin's, with drafts and retired)
- `POST /api/v1/templates` {from_id? | kind, name, description?} → draft;  `GET|PUT /api/v1/templates/{id}` {name?, description?, fields?}
- `POST /api/v1/templates/{id}/adopt` {standard?} · `POST /api/v1/templates/{id}/retire` · `GET /api/v1/templates/examples/{eid}`
- `GET|PUT /api/v1/intents/{iid}/template` {template_id?} → {id, version, companions} (the first choice sticks)
- `PUT /api/v1/intents/{iid}/template/{kind}` {template_id} → switch the process map or definitions template (content stays)
- `POST /api/v1/template-requests` {kind?, about?, text} → request;  `GET /api/v1/admin/requests`;  `POST /api/v1/admin/requests/{id}` {state, note?}
- `GET /api/v1/admin/skills`; `PUT|DELETE /api/v1/admin/skills/{agent}/{name}` {text};  `GET|PUT /api/v1/admin/governance` {rules};  `GET /api/v1/admin/log`
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.profile.api import _plane
from sh_platform.v1 import t1_templates as T
from sh_platform.v1.i2_routes import _answer, _json_body
from sh_platform.v1.seats import viewer_of

router = APIRouter()


async def _body(request: Request, limit: int = 256 * 1024):
    return await _json_body(request, limit)


@router.get("/api/v1/templates")
def list_templates(request: Request, kind: str = "", all: str = ""):
    viewer = viewer_of(request)
    return _answer(lambda: T.listing(_plane(request), viewer, kind or None, all == "1"))


@router.get("/api/v1/templates/examples/{eid}")
def get_example(eid: str, request: Request):
    viewer_of(request)
    return _answer(lambda: T.example(_plane(request), eid))


@router.get("/api/v1/templates/{tid}")
def get_template(tid: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.get(_plane(request), viewer, tid))


@router.post("/api/v1/templates")
async def create_template(request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.create(_plane(request), viewer, body))


@router.put("/api/v1/templates/{tid}")
async def edit_template(tid: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.edit(_plane(request), viewer, tid, body))


@router.post("/api/v1/templates/{tid}/adopt")
async def adopt_template(tid: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request, 4096)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.adopt(_plane(request), viewer, tid, body.get("standard") is True))


@router.post("/api/v1/templates/{tid}/retire")
def retire_template(tid: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.retire(_plane(request), viewer, tid))


@router.get("/api/v1/intents/{iid}/template")
def intent_template(iid: str, request: Request):
    viewer_of(request)
    plane = _plane(request)

    def work():
        t = T.for_intent(plane, iid)
        return {"template": t, "missing": T.missing_required(t, T.record_for_intent(plane, iid)) if t else []}
    return _answer(work)


@router.put("/api/v1/intents/{iid}/template")
async def choose_template(iid: str, request: Request):
    viewer_of(request)
    body = await _body(request, 4096)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.choose(_plane(request), iid, body.get("template_id") or None))


@router.put("/api/v1/intents/{iid}/template/{kind}")
async def switch_template(iid: str, kind: str, request: Request):
    """Switch the process map or definitions template of an intent; what is written in the documents stays."""
    viewer_of(request)
    body = await _body(request, 4096)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.switch(_plane(request), iid, kind, str(body.get("template_id") or "")))


@router.post("/api/v1/template-requests")
async def raise_request(request: Request):
    viewer = viewer_of(request)
    body = await _body(request, 8192)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.raise_request(_plane(request), viewer, body))


@router.get("/api/v1/admin/requests")
def list_requests(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.requests(_plane(request), viewer))


@router.post("/api/v1/admin/requests/{rid}")
async def answer_request(rid: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request, 8192)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.answer_request(_plane(request), viewer, rid, str(body.get("state")), body.get("note") or ""))


@router.get("/api/v1/admin/skills")
def list_skills(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.skills(_plane(request), viewer))


@router.put("/api/v1/admin/skills/{agent}/{name}")
async def save_skill(agent: str, name: str, request: Request):
    viewer = viewer_of(request)
    body = await _body(request, 64 * 1024)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.save_skill(_plane(request), viewer, agent, name, body.get("text")))


@router.delete("/api/v1/admin/skills/{agent}/{name}")
def reset_skill(agent: str, name: str, request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.reset_skill(_plane(request), viewer, agent, name))


@router.get("/api/v1/admin/governance")
def get_governance(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: (T.need_admin(viewer), T.governance(_plane(request)))[1])


@router.put("/api/v1/admin/governance")
async def put_governance(request: Request):
    viewer = viewer_of(request)
    body = await _body(request, 64 * 1024)
    return body if isinstance(body, JSONResponse) else _answer(lambda: T.save_governance(_plane(request), viewer, body.get("rules")))


@router.get("/api/v1/admin/log")
def get_log(request: Request):
    viewer = viewer_of(request)
    return _answer(lambda: T.change_log(_plane(request), viewer))
