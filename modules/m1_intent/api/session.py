"""M1-P01 routes: prepare a session (M1-01), seats and time (M1-02), the contract lists the screens offer,
templates, and the link between a session and its outcome (D-026). The organiser is the signed-in person; a
draft is visible and editable by its organiser only. Declared in manifest.yaml; refused by default otherwise."""
from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.domain import profile_draft
from modules.m1_intent.domain.seat_identity import profile_viewer
from modules.m1_intent.domain.preparation import PrepError, clean, default_preparation, default_split, template_name
from modules.m1_intent.store.charter import read_outcome
from modules.m1_intent.store.files import WrongState
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.sessions import _label
from sh_platform.profile import read as read_profile

router = APIRouter()
TEXT_KEYS = ("purpose", "outcome", "approver_name")


EXTRA = ((PrepError, lambda e: deps.plain(422, "invalid", e.message, field=e.field)),)
guarded = deps.guarded(*EXTRA)


def view(store, s: dict) -> dict:
    """The session as the screens see it: no person or company ids, no file details."""
    return {"id": s["id"], "state": s["state"], "paused_from": s["paused_from"],
            "is_solo": s["preparation"]["seats"] == 1, "editable": s["state"] == "draft",
            "preparation": s["preparation"], "outcome_id": s["outcome_id"], "landing": store.landing(s),
            "created_at": s["created_at"], "updated_at": s["updated_at"], "inputs": s["inputs"]}


def _prepare(request: Request, raw: dict, base: dict) -> dict:
    settings, templates = deps.contracts(request)
    offers, _ = deps.north_offers(request)
    prep = clean(raw, base, settings, templates, offers)
    if prep["approver_account_id"]:  # a named person of this company; whether they are senior is never checked
        acct = request.app.state.account_store.get(prep["approver_account_id"])
        if not acct or acct["company_id"] != request.state.company_id or acct["disabled"]:
            raise PrepError("That person could not be chosen as the approver.", "approver_account_id")
        if not prep["approver_name"]:
            prep["approver_name"] = str(acct["display_name"] or "")[:settings.text_limits["approver_name"]]
    return prep


def _profile_draft(request: Request, settings) -> dict:
    """Prepare drafted from the company profile as this organiser may see it (restricted people and fields are already out of it)."""
    return profile_draft.build(read_profile(deps.store(request)._plane, profile_viewer(request)), settings)


@router.get("/lists")
@guarded
async def lists(request: Request):
    settings, templates = deps.contracts(request)
    _, north = await deps.blocking(deps.north_offers, request)
    draft = await deps.blocking(_profile_draft, request, settings)
    return {"seats": {"min": settings.seats_min, "max": settings.seats_max},
            "time_presets_minutes": list(settings.time_presets),
            "custom_length_minutes": {"min": settings.custom_min, "max": settings.custom_max},
            "min_stage_minutes": settings.min_stage_minutes,
            "default_length_minutes": settings.default_length_minutes,
            "default_split": default_split(settings.default_length_minutes, settings),
            "default_split_percent": settings.default_split_percent,
            "warning_seconds": settings.warning_seconds, "text_limits": settings.text_limits,
            "briefing_video_options": list(settings.briefing_video_options),
            "charter_templates": [{"id": t.id, "name": t.name, "description": t.description}
                                  for t in templates.templates],
            "default_template": templates.default_id, "north": north, "profile_draft": draft}


@router.get("/sessions")
@guarded
async def my_sessions(request: Request):
    store = deps.store(request)
    return await deps.blocking(store.list_for, request.state.account_id)


@router.post("/sessions", status_code=201)
@guarded
async def create_draft(request: Request):
    raw = await deps.body_object(request)
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    store = deps.store(request)
    settings, templates = deps.contracts(request)
    template_id = raw.pop("from_template", None)
    drafted = raw.pop("drafted", None) is True  # LI-M1: the values came from the profile and the organiser tapped "Looks right"
    typed = 0 if drafted else sum(1 for k in TEXT_KEYS if isinstance(raw.get(k), str) and raw[k].strip())

    def work():
        base = default_preparation(settings, templates)
        if template_id is not None:
            t = store.get_template(template_id)
            if t is None:
                return None
            base = {**t["preparation"], "names": "choice", "topic": None}  # the names rule is chosen for each session, never inherited
        s = store.create(request.state.account_id, _prepare(request, raw, base))
        store.count(s["id"], 1, typed)
        return view(store, store.get(s["id"]))

    made = await deps.blocking(work)
    return made if made is not None else deps.plain(404, "not_found", "We could not find that template.")


@router.get("/sessions/{session_id}")
@guarded
async def one_session(request: Request, session_id: str):
    store = deps.store(request)

    def work():
        s = store.get(session_id)
        if not s:
            return None
        if s["organiser_account_id"] == request.state.account_id:
            return view(store, s)
        seat = RoomStore(store._plane).seat_of_account(session_id, request.state.account_id)
        # a seat holder reads the name, purpose, stage and their own seat only: no other seats, no notes
        return None if seat is None else {
            "id": s["id"], "label": _label(s["preparation"]), "state": s["state"],
            "preparation": {"purpose": s["preparation"]["purpose"], "topic": s["preparation"]["topic"]},
            "seat": {"n": seat["n"], "name": seat["name"], "role": seat["role"]}}

    got = await deps.blocking(work)
    return got if got is not None else deps.not_found()


@router.put("/sessions/{session_id}")
@guarded
async def update_draft(request: Request, session_id: str):
    raw = await deps.body_object(request)
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    store = deps.store(request)

    def work():
        s = store.get(session_id)
        if s is None or s["organiser_account_id"] != request.state.account_id:
            return None
        if s["state"] != "draft":  # preparation is read-only once the session has started (M1-01)
            raise WrongState("This session has already started, so its preparation can no longer be changed.")
        deps.typed(request, sum(1 for k in TEXT_KEYS if isinstance(raw.get(k), str) and raw[k].strip() and raw[k].strip() != s["preparation"][k]))
        new = store.update_draft(session_id, request.state.account_id, _prepare(request, raw, s["preparation"]))
        return view(store, new) if new else None

    got = await deps.blocking(work)
    return got if got is not None else deps.not_found()


@router.delete("/sessions/{session_id}")
@guarded
async def delete_draft(request: Request, session_id: str):
    if request.query_params.get("confirm") != "yes":  # deleting needs an explicit human confirmation (M1-29)
        return deps.plain(400, "confirm_needed", "Please confirm that you want to delete this draft.")
    store = deps.store(request)
    done = await deps.blocking(store.delete_draft, session_id, request.state.account_id)
    return {"deleted": True} if done else deps.not_found()


@router.get("/outcomes/{outcome_id}")
@guarded
async def session_of_outcome(request: Request, outcome_id: str):
    store = deps.store(request)

    def work():
        """The outcome record (module 2's input, once the charter is signed) with the link to its session (D-026); before
        sign-off there is no record yet, only the id and where it stands."""
        s = store.get_by_outcome(outcome_id)
        if not (s and s["organiser_account_id"] == request.state.account_id):
            return None
        record = read_outcome(store._plane, outcome_id)
        link = {"id": s["id"], "state": s["state"], "landing": store.landing(s)}
        return {**record, "session": link} if record else {"outcome_id": outcome_id, "status": "in_progress", "session": link}

    got = await deps.blocking(work)
    return got if got is not None else deps.not_found()


@router.get("/templates")
@guarded
async def my_templates(request: Request):
    return await deps.blocking(deps.store(request).templates)


@router.post("/templates", status_code=201)
@guarded
async def save_template(request: Request):
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"name", "session_id"}:
        return deps.plain(400, "bad_request", deps.BAD_BODY)
    settings, _ = deps.contracts(request)
    name = template_name(raw["name"], settings)
    store = deps.store(request)
    made = await deps.blocking(store.save_template, name, raw["session_id"], request.state.account_id)
    return made if made is not None else deps.not_found()
