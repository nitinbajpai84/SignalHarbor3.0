"""M1-P03 routes: the briefing (M1-05), its video slot (M1-06), Nira (M1-07) and the stage timer (M1-14).

Who is asking: the session's organiser is the signed-in account that prepared it. Everyone is a seat, found by
domain/seat_identity.seat_of (a guest's token, a bound account, or the organiser; never a body or header). Time comes from the server
clock (`app.state.m1_clock` in tests, else the real clock); the screens only show what these routes return.
All routes are declared in manifest.yaml and sh_platform/route_permissions.yaml.
"""
import functools
import logging
import math
import time

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from modules.m1_intent.agent import nira
from modules.m1_intent.tools.pack_tools import load_guidance
from modules.m1_intent.api import deps, session
from modules.m1_intent.domain import briefing as B
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import timer
from modules.m1_intent.domain.seat_identity import register_names, seat_id_of, seat_of
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.files import StoreError, WrongState, lock_for
from modules.m1_intent.store.notes import submit_all
from modules.m1_intent.store.sessions import SessionStore
from modules.m1_intent.store.transcripts import TranscriptStore
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.memory.summarise import background, remember_for_account
from sh_platform.plane import PlaneStore
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
NIRA_TURNS = 8  # MEM-2: Nira's talk with one person is summarised into memory every this many questions
_nira_talk: dict[tuple[str, str], list[str]] = {}  # ponytail: in memory, lost on restart; a stored count if a restart must not lose turns
router = APIRouter()
ORGANISERS = ("company_admin", "sponsor", "analyst")
_NO_SEAT = "You do not have a seat in this session."
_ORGANISER_ONLY = "Only the organiser can do this."


class Refuse(Exception):
    """Carries the plain answer to send instead of going on."""

    def __init__(self, response: JSONResponse):
        self.response = response


def refusing(fn):
    @functools.wraps(fn)
    async def inner(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Refuse as r:
            return r.response
    return inner


def stage_route(fn):
    """Plain answers for a refusal, then the module's usual guard for everything else."""
    return session.guarded(refusing(fn))


# ---- who and what ---------------------------------------------------------------------------------------------
class Open:
    """One session opened for one person: stores, the settings, the clock and who is asking."""

    def __init__(self, request: Request, session_id: str, read_after_close: bool = False):
        self.request = request
        self.now = float(getattr(request.app.state, "m1_clock", time.time)())
        self.settings = B.load_settings(getattr(request.app.state, "m1_contracts_dir", None))
        try:
            self.plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
        except (LookupError, ValueError):
            raise PermissionError("no company space") from None
        self.sessions = SessionStore(self.plane, clock=lambda: self.now)
        self.stages = B.StageStore(self.plane)
        self.session_id = session_id
        s = self.sessions.get(session_id)
        if s is None:
            raise Refuse(deps.not_found())
        self.s = s
        if s["state"] == "closed" and request.state.account_id is None and not read_after_close:
            raise Refuse(deps.not_found())  # a guest's token reads the result after the close (the board), nothing else
        self.organiser =s["organiser_account_id"] == request.state.account_id
        self.seat = seat_of(request, s, self.plane, read_after_close)
        if not self.organiser:
            if self.seat is None and set(request.state.roles) & set(ORGANISERS):
                raise Refuse(deps.not_found())  # another organiser of the company: the same answer as no session
            if self.seat is None or s["state"] == "draft":
                raise Refuse(deps.plain(403, "forbidden", _NO_SEAT))

    @property
    def stage(self) -> str:
        return self.s["state"]

    def only_organiser(self) -> None:
        if not self.organiser:
            raise Refuse(deps.plain(403, "forbidden", _ORGANISER_ONLY))

    def reload(self) -> None:
        self.s = self.sessions.get(self.session_id) or self.s


def _advance(o: Open) -> None:
    """Every timed stage ends by itself when its time is up and nobody extended it (M1-14, LI-M1): the briefing sends
    everyone to their rooms, the rooms close, the together stage drafts the charter from the vote. Done on every look at
    the timer, so the server clock is the only thing that decides."""
    for _ in timer.AUTO_MOVE:  # a session left alone for a long time may cross more than one stage
        stage = o.stage
        if stage not in timer.AUTO_MOVE or o.now < _ends_at(o) or not _move_on(o, stage):
            return


def _move_on(o: Open, stage: str) -> bool:
    """Moves the session out of `stage`; False when nothing moved (another look got there first, or the stage must wait)."""
    with lock_for(o.plane.path("intents", "m1_intent")):  # the store's own lock: the move and its hook happen once
        o.reload()
        if o.stage != stage:
            return False
        if stage == "together":
            from modules.m1_intent.api.charter import close_together  # not at the top: charter imports the board, which imports this file
            moved = close_together(o.request, o.plane, o.session_id)
            o.reload()
            return moved
        if stage == "private_rooms":
            submit_all(o.plane, o.session_id)  # M1-14: the notes written so far are submitted (M1-P05)
            timer.on_rooms_end(o.s)
        try:
            o.s = o.sessions.transition(o.session_id, timer.AUTO_MOVE[stage]) or o.s
        except WrongState:
            o.reload()
            return False
        if stage == "briefing":
            o.stages.start(o.session_id, "private_rooms", o.now)  # the rooms' clock starts when the briefing ends
        return True


def everyone_clear(o: Open) -> bool:
    """Every seated person but the organiser has said "clear" (the early close of the briefing); nobody to wait for is not everyone."""
    rooms = RoomStore(o.plane)
    chair = rooms.seat_of_account(o.session_id, o.s["organiser_account_id"])
    seats = [x for x in (rooms.get(o.session_id) or {"seats": []})["seats"] if x["state"] == "taken" and x != chair]
    clear = o.stages.get(o.session_id)["seats"]
    return bool(seats) and all(clear.get(seat_id_of(o.plane, o.session_id, x)) == "clear" for x in seats)


def everyone_done_in_rooms(o: Open) -> bool:
    """Every seated person but the organiser has said "I'm done" in the private rooms; nobody to wait for is not everyone."""
    rooms = RoomStore(o.plane)
    chair = rooms.seat_of_account(o.session_id, o.s["organiser_account_id"])
    seats = [x for x in (rooms.get(o.session_id) or {"seats": []})["seats"] if x["state"] == "taken" and x != chair]
    return bool(seats) and all(o.stages.rooms_done(o.session_id, seat_id_of(o.plane, o.session_id, x)) for x in seats)


def _ends_at(o: Open) -> float:
    started = o.stages.started(o.session_id, o.stage, timer.parse(o.s["updated_at"]))
    return timer.ends_at(o.stage, o.s["preparation"]["split"], started, o.stages.extensions(o.session_id, o.stage))


def _timer_view(o: Open) -> dict:
    now = timer.iso(o.now)
    if not timer.is_timed(o.stage):
        return {"stage": o.stage, "timed": False, "now": now}
    started = o.stages.started(o.session_id, o.stage, timer.parse(o.s["updated_at"]))
    exts = o.stages.extensions(o.session_id, o.stage)
    end = timer.ends_at(o.stage, o.s["preparation"]["split"], started, exts)
    warn = deps.contracts(o.request)[0].warning_seconds
    return {"stage": o.stage, "timed": True, "status": timer.status(o.now, end, warn), "started_at": timer.iso(started),
            "ends_at": timer.iso(end), "now": now, "remaining_seconds": math.ceil(max(0.0, end - o.now)),
            "warning_seconds": warn, "extensions": exts, "extension_minutes": list(o.settings.extension_minutes),
            "may_extend": o.organiser}


def _video(o: Open) -> tuple:
    """(file, content type) of the briefing video: the session's own upload, else the module's shared default unless the
    organiser chose none. (None, None) when there is no video."""
    kind = o.stages.video_type(o.session_id)
    if kind:
        return o.stages.video_file(o.session_id), kind
    default = o.settings.default_video
    return default if default and o.s["preparation"]["briefing_video"] != "none" else (None, None)


def _video_view(o: Open) -> dict:
    kind = _video(o)[1]
    if kind:
        return {"mode": "file", "content_type": kind}
    return {"mode": "none" if o.s["preparation"]["briefing_video"] == "none" else "placeholder"}


def _briefing_view(o: Open) -> dict:
    prep, status = o.s["preparation"], o.stages.status(o.session_id, o.seat)
    company = o.request.app.state.entitlements.company(o.request.state.company_id) or {}
    speech = getattr(o.request.app.state, "speech_provider", None)  # M1-P06 supplies a real one; None means the stub
    read_aloud = {"available": True} if getattr(speech, "available", False) else \
        {"available": False, "message": o.settings.read_aloud_unavailable}
    waiting = o.stage in ("lobby", "briefing") or (o.stage == "private_rooms" and status != "clear" and not o.organiser)
    out = {"stage": o.stage, "company_name": str(company.get("name", "")), "title": B.title_of(prep),
           "rules": B.build_rules(prep, o.settings), "video": _video_view(o), "read_aloud": read_aloud,
           "me": {"role": "organiser" if o.organiser else "participant", "status": status},
           "can_send": o.organiser and o.stage == "briefing", "next": "briefing" if waiting else "room"}
    if o.organiser:  # only the organiser sees how many are clear
        out.update(confirmed=o.stages.confirmed(o.session_id), seats=prep["seats"])
    return out


# ---- the briefing -----------------------------------------------------------------------------------------------
@router.get("/sessions/{session_id}/briefing")
@stage_route
async def get_briefing(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        _advance(o)
        return _briefing_view(o)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/briefing/confirm")
@stage_route
async def confirm(request: Request, session_id: str):
    raw = await deps.body_object(request)
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_READ)

    def work():
        o = Open(request, session_id)
        if raw.get("answer") not in B.ANSWERS:
            return deps.plain(422, "invalid", 'Please answer "clear" or ask Nira your question.', field="answer")
        if o.stage not in ("briefing", "private_rooms"):
            raise WrongState("The briefing is not open right now.")
        o.stages.confirm(session_id, o.seat)
        if o.stage == "briefing" and everyone_clear(o):  # "I'm clear" from everyone ends the briefing early
            _move_on(o, "briefing")
        return _briefing_view(o)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/room/done")
@stage_route
async def rooms_done(request: Request, session_id: str):
    """A participant's "I'm done" in the private rooms. When everyone but the organiser is done the rooms close early, exactly as
    the organiser's "close the rooms now" or the timer would close them (the notes written so far are submitted)."""
    raw = await deps.body_object(request)
    if raw is None or set(raw) != {"done"} or not isinstance(raw["done"], bool):
        return deps.plain(400, "bad_request", deps.BAD_READ)

    def work():
        o = Open(request, session_id)
        if o.organiser:
            raise Refuse(deps.plain(403, "forbidden", "The organiser closes the rooms. Use the close button."))  # as in together
        if o.stage != "private_rooms":
            raise WrongState("The private rooms are not open right now.")
        o.stages.set_rooms_done(session_id, o.seat, raw["done"])
        if everyone_done_in_rooms(o):
            _move_on(o, "private_rooms")
        return {"state": o.stage, "i_done": raw["done"]}
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/briefing/send")
@stage_route
async def send(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        o.only_organiser()
        if o.stage != "briefing":
            raise WrongState("Everyone can only be sent to their rooms from the briefing.")
        o.s = o.sessions.transition(session_id, "private_rooms")
        o.stages.start(session_id, "private_rooms", o.now)  # the rooms' clock starts when the organiser sends everyone
        return {"state": "private_rooms"}
    return await deps.blocking(work)


# ---- the video (M1-06) ---------------------------------------------------------------------------------------------
@router.put("/sessions/{session_id}/briefing/video")
@stage_route
async def put_video(request: Request, session_id: str):
    def check():
        o = Open(request, session_id)
        o.only_organiser()
        if o.stage not in ("draft", "lobby", "briefing"):
            raise WrongState("The briefing video can only be changed before the rooms open.")
        return o.settings
    settings = await deps.blocking(check)
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in settings.video_types:
        return deps.plain(415, "wrong_type", "That file type is not allowed. Please use a standard video file ("
                          + " or ".join(sorted(f".{e}" for e in settings.video_types.values())) + ").")
    too_big = deps.plain(413, "too_big", f"That video is too large. Please keep it under "
                                         f"{settings.max_video_bytes // (1024 * 1024)} MB.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > settings.max_video_bytes:
        return too_big
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > settings.max_video_bytes:
            return too_big
    if not data:
        return deps.plain(422, "empty", "That file is empty. Please choose a video.")

    def save():
        o = Open(request, session_id)
        if o.stage not in ("draft", "lobby", "briefing"):  # the stage may have moved while the file arrived
            raise WrongState("The briefing video can only be changed before the rooms open.")
        o.stages.save_video(session_id, bytes(data), kind)
        return {"video": _video_view(o)}
    return await deps.blocking(save)


@router.get("/sessions/{session_id}/briefing/video")
@stage_route
async def get_video(request: Request, session_id: str):
    def work():
        return _video(Open(request, session_id))
    path, kind = await deps.blocking(work)
    if path is None:
        return deps.plain(404, "not_found", "There is no briefing video for this session.")
    return FileResponse(path, media_type=kind, headers={"X-Content-Type-Options": "nosniff",
                                                        "Cache-Control": "private, no-store"})


# ---- Nira (M1-07) -------------------------------------------------------------------------------------------------
def _model_env(o: Open) -> dict:
    """Keys and SH_MODEL_* from .env and the environment; `app.state.model_env` overrides it (tests set {})."""
    override = getattr(o.request.app.state, "model_env", None)
    return dict(override) if override is not None else load_model_env()


def _model(o: Open):
    """Nira's model client for this company: built through the egress gateway (same as North), or None when no key
    is set up or a setting is wrong. Tests plug a stub in with `app.state.nira_model_factory`."""
    factory = getattr(o.request.app.state, "nira_model_factory", None)
    try:
        return factory(o.plane) if factory else build_model_client(o.plane, _model_env(o))
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def _industry_words(request: Request, company: dict) -> str:
    """The industry as plain words for the prompt: the pack's label, else the id with spaces. The raw id ("two_words")
    is not sent: once names are protected, its glued form can match a protected name part and the gateway refuses it."""
    industry = str(company.get("industry", ""))
    return load_guidance(request.app.state.packs, industry).label or industry.replace("_", " ")


@router.post("/sessions/{session_id}/nira")
@stage_route
async def ask_nira(request: Request, session_id: str):
    raw = await deps.body_object(request)
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_READ)
    kind, question = raw.get("kind"), raw.get("question", "")

    def work():
        o = Open(request, session_id)
        cfg = nira.load_rules()
        if kind not in nira.KINDS:
            return deps.plain(422, "invalid", "Please choose what you want to ask Nira.", field="kind")
        if kind == "ask":
            if not isinstance(question, str) or not question.strip():
                return deps.plain(422, "invalid", "Please write your question for Nira.", field="question")
            if len(question) > o.settings.question_max:
                return deps.plain(422, "invalid", f"Please keep your question under {o.settings.question_max} characters.",
                                  field="question")
            deps.typed(request)
            o.stages.mark_asked(session_id, o.seat)  # asking is not the same as being clear
        _advance(o)
        model = _model(o) if kind == "ask" else None  # only a question needs the egress client (None: no key set up)
        said = {"name": cfg["name"], "role": cfg["role"]}
        if model is None and kind == "ask":
            return {"available": False, **said, "text": cfg["unavailable"]}
        extra, nearly_up = "", True
        if kind == "warning" and timer.is_timed(o.stage):
            view = _timer_view(o)
            extra = f"{view['remaining_seconds']} seconds are left in this stage."
            nearly_up = view["remaining_seconds"] <= view["warning_seconds"]  # "nearly up" only inside the warning window
            if nearly_up and o.stage == "private_rooms" and o.seat:  # what the rooms' end would send for this person
                try:
                    notes = TranscriptStore(o.plane).load(session_id, o.seat)["notes"]
                except StoreError:
                    notes = []  # a damaged transcript must not stop the time warning
                extra = " ".join(p for p in (extra, N.unsent(notes, N.names_rule(o.s["preparation"]))["message"]) if p)
        company = request.app.state.entitlements.company(request.state.company_id) or {}
        if kind == "ask":  # only a typed question goes to the model (M1-P04c)
            register_names(request, o.plane, session_id)  # protected before anything leaves (M1-P05)
        account = request.state.account_id
        memory = background(o.plane, "nira", account) if kind == "ask" else ""  # MEM-2: background, never an instruction
        text = nira.ask_nira(model, request.app.state.entitlements, RunRegistry(o.plane), request.state.company_id,
                             str(company.get("name", "")), _industry_words(request, company), stage=o.stage,
                             rules=B.build_rules(o.s["preparation"], o.settings), kind=kind,
                             question=(question + "\n\n" + memory).strip() if kind == "ask" else "", extra=extra,
                             reply_max=o.settings.reply_max, instructions=cfg, nearly_up=nearly_up)
        if kind == "ask" and account:
            talk = _nira_talk.setdefault((session_id, account), [])
            talk += [f"Person: {question}", f"Nira: {text}"]
            if len(talk) >= 2 * NIRA_TURNS:
                remember_for_account(o.plane, "nira", account, talk[:], model=model, gate=request.app.state.entitlements,
                                     recorder=RunRegistry(o.plane), company_id=request.state.company_id, module_id=nira.MODULE_ID,
                                     conversation=f"Nira, session {session_id}")
                talk.clear()
        return {"available": True, **said, "text": text}
    return await deps.blocking(work)


# ---- the timer (M1-14) --------------------------------------------------------------------------------------------
@router.get("/sessions/{session_id}/timer")
@stage_route
async def get_timer(request: Request, session_id: str):
    def work():
        o = Open(request, session_id)
        _advance(o)
        return _timer_view(o)
    return await deps.blocking(work)


@router.post("/sessions/{session_id}/timer/extend")
@stage_route
async def extend(request: Request, session_id: str):
    raw = await deps.body_object(request)
    if raw is None:
        return deps.plain(400, "bad_request", deps.BAD_READ)

    def work():
        o = Open(request, session_id)
        o.only_organiser()
        _advance(o)  # a stage that has already ended cannot be extended
        if not timer.is_timed(o.stage):
            raise WrongState("This stage has no timer to extend.")
        minutes = raw.get("minutes")
        if type(minutes) is not int or minutes not in o.settings.extension_minutes:
            return deps.plain(422, "invalid", "Please choose one of the extra times on offer: "
                              + ", ".join(f"{m} minutes" for m in o.settings.extension_minutes) + ".", field="minutes")
        o.stages.started(session_id, o.stage, timer.parse(o.s["updated_at"]))
        o.stages.extend(session_id, o.stage, minutes, o.now)
        return _timer_view(o)
    return await deps.blocking(work)
