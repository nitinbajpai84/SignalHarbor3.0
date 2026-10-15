"""R1: build roles at the charter. GET drafts them (Lens, guessed) under anything the organiser stated; PUT lets the organiser set any
(stated). Kept beside the charter in intents/m1_intent/roles/<session id>.json (the charter file's keys are fixed, so it is not added there)."""
from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.domain import roles as R
from modules.m1_intent.store.files import lock_for, read_json, write_json
from modules.m1_intent.store.room import RoomStore
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.profile import store as profile

router = APIRouter()
guarded = deps.guarded((LookupError, lambda e: deps.not_found()))


def _file(plane, sid: str):
    return plane.path("intents", "m1_intent", "roles", f"{sid}.json")


def _plane(request: Request):
    try:
        return PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
    except (LookupError, CrossCompanyError, ValueError):
        raise PermissionError("no company space") from None


def _current(request: Request, sid: str) -> tuple[dict, dict, object]:
    plane = _plane(request)
    s = deps.store(request).get(sid)
    if s is None:
        raise LookupError("no session")
    room = RoomStore(plane).get(sid) or {"seats": []}
    names = [x["name"] for x in room["seats"] if x["state"] == "taken" and x.get("name")]
    drafted = R.draft(profile.raw(plane).get("people") or {}, str(s["preparation"].get("approver_name") or ""), names)
    return s, R.merge(read_json(_file(plane, sid)), drafted), plane


@router.get("/sessions/{session_id}/roles")
@guarded
async def get_roles(session_id: str, request: Request):
    def work():
        s, out, _ = _current(request, session_id)
        return out | {"can_edit": s["organiser_account_id"] == request.state.account_id}
    return await deps.blocking(work)


@router.put("/sessions/{session_id}/roles")
@guarded
async def put_roles(session_id: str, request: Request):
    body = await deps.body_object(request)
    changes = R.clean(body) if body is not None else None
    if changes is None:
        return deps.plain(422, "invalid", deps.BAD_BODY)

    def work():
        s, _, plane = _current(request, session_id)
        if s["organiser_account_id"] != request.state.account_id:
            return deps.plain(403, "forbidden", "Only the organiser can name the roles.")
        name = str((request.app.state.account_store.get(request.state.account_id) or {}).get("display_name") or "The organiser")
        with lock_for(_file(plane, session_id)):
            write_json(_file(plane, session_id), R.state(read_json(_file(plane, session_id)), changes, name))
        return _current(request, session_id)[1] | {"can_edit": True}
    return await deps.blocking(work)
