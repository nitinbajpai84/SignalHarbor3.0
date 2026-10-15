"""M1-P06 routes: speech in (M1-08), spoken replies and the per-person mute (M1-09). Declared in manifest.yaml.

Who is "the person": the viewer the room already uses (the organiser, or a seat holder by account or by guest token).
Anyone else, in this company or another, gets the same "not found" as for a session that does not exist. The mute is
kept per seat in the company's own plane: one flag, never audio (D-018). Audio travels as base64 inside the JSON, so
the one typed client keeps being the only caller of fetch, and lives in memory for one request.

A speech failure is never an error on screen: transcribe and speak answer 200 with `failed: true` and the person
carries on in text. Speech leaves only through sh_platform/speech (the egress gateway); in production the Gemini
provider is off (A-033), so the answer is the same "failed" and the screens show typing.
"""
import base64
import binascii
import logging
from types import SimpleNamespace

from fastapi import APIRouter, Request

from modules.m1_intent.domain.seat_identity import register_names
from modules.m1_intent.api import briefing, deps, session
from modules.m1_intent.api.room import _viewer  # who is asking: organiser, seat holder by account, or guest token
from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.store.files import read_json, write_json
from modules.m1_intent.store.room import RoomStore
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.jsonfile import lock_for
from sh_platform.plane import CrossCompanyError, PlaneStore
from sh_platform.speech import SpeechConfig, SpeechUnavailable, build_speech, load_speech_env, status

log = logging.getLogger(__name__)
router = APIRouter()
guarded = deps.guarded((R.RoomClosed, lambda e: deps.plain(409, "rooms_closed", e.message)),
                       (R.RoomError, lambda e: deps.plain(422, "invalid", e.message)), *session.EXTRA)
_BAD_AUDIO = "That recording could not be read. Please try again, or type instead."
_TOO_LONG = "That recording is too long. Please keep it shorter, or type instead."


def _env(app) -> dict:
    """The speech settings. `app.state.speech_env` overrides them (tests set it: the real .env holds a key)."""
    override = getattr(app.state, "speech_env", None)
    return dict(override) if override is not None else load_speech_env()


class Wired:
    """What Nira's read-aloud hook (briefing.py) reads off `app.state.speech_provider`: the same choice as the routes."""

    def __init__(self, app):
        self._app = app

    @property
    def available(self) -> bool:
        return status(_env(self._app), self._app.state.settings.mode)["provider"] is not None


def wire_speech(request: Request) -> None:
    """A dependency of the module's router: gives the briefing its read-aloud provider once (a test may set its own)."""
    if getattr(request.app.state, "speech_provider", None) is None:
        request.app.state.speech_provider = Wired(request.app)


def _contract(request: Request) -> tuple[SpeechConfig, dict]:
    d = C._read(getattr(request.app.state, "m1_contracts_dir", None), "speech.yaml")
    try:
        g = d["gemini"]
        cfg = SpeechConfig(stt_model=str(g["transcribe_model"]), tts_model=str(g["speak_model"]), voice=str(g["voice"]),
                           style=str(d["speak_style"]), mimes=tuple(str(m) for m in d["audio_mime_types"]),
                           max_audio_bytes=int(d["max_audio_bytes"]), max_chars=int(d["max_speak_chars"]))
        words = {"max_seconds": int(d["max_recording_seconds"]), "unavailable": str(d["unavailable_message"])}
    except (KeyError, TypeError, ValueError):
        raise C.ContractError("speech.yaml is not valid: a setting is missing.") from None
    return cfg, words


class Ctx:
    """One request: the company's plane, the session, who is asking, and the speech settings."""

    def __init__(self, request: Request, session_id: str):
        try:
            self.plane = PlaneStore(request.app.state.settings.data_root).plane_for(request.state.company_id).ensure()
        except (LookupError, CrossCompanyError, ValueError):
            raise PermissionError("no company space") from None
        self.request, self.s = request, SessionStore(self.plane).get(session_id)
        viewer = _viewer(request, RoomStore(self.plane), self.s) if self.s else None
        self.ok = viewer is not None
        self.who = "organiser" if viewer is None or viewer.seat is None else f"seat{viewer.seat['n']}"
        self.cfg, self.words = _contract(request)
        self.speech = build_speech(self.plane, self.cfg, _env(request.app), request.app.state.settings.mode,
                                   getattr(request.app.state, "speech_client", None))

    def _file(self):
        return self.plane.path("intents", "m1_intent", "voice", f"{self.s['id']}.json")

    def muted(self) -> list:
        d = read_json(self._file()) or {}
        return d["muted"] if isinstance(d.get("muted"), list) else []

    def set_on(self, on: bool) -> None:
        with lock_for(self._file()):
            muted = [w for w in self.muted() if w != self.who] + ([] if on else [self.who])
            write_json(self._file(), {"muted": sorted(muted)})

    def view(self) -> dict:
        ok = self.speech.available
        return {"available": ok, "on": self.who not in self.muted(), "message": None if ok else self.words["unavailable"],
                "note": "Speech to text is on" if self.speech.note else None, "max_seconds": self.words["max_seconds"]}


async def _open(request: Request, session_id: str):
    """(Ctx, None) or (None, the 404 answer)."""
    ctx = await deps.blocking(Ctx, request, session_id)
    return (ctx, None) if ctx.ok else (None, deps.not_found())


async def _only(request: Request, allowed: set, required: set) -> dict:
    body = await deps.body_object(request)
    if body is None or not set(body) <= allowed or not required <= set(body):
        raise R.RoomError(deps.BAD_READ)
    return body


@router.get("/sessions/{session_id}/voice")
@guarded
async def my_voice(request: Request, session_id: str):
    ctx, no = await _open(request, session_id)
    return no or await deps.blocking(ctx.view)


@router.post("/sessions/{session_id}/voice")  # POST, not PUT: the kernel lets a guest use only GET and POST
@guarded
async def set_voice(request: Request, session_id: str):
    ctx, no = await _open(request, session_id)
    if no:
        return no
    body = await _only(request, {"on"}, {"on"})
    if not isinstance(body["on"], bool):
        raise R.RoomError(deps.BAD_READ)
    await deps.blocking(ctx.set_on, body["on"])
    return await deps.blocking(ctx.view)


@router.post("/sessions/{session_id}/voice/transcribe")
@guarded
async def transcribe(request: Request, session_id: str):
    ctx, no = await _open(request, session_id)
    if no:
        return no
    R.check_stage(ctx.s["state"])  # speech becomes notes: only while the private rooms are open (M1-16)
    body = await _only(request, {"audio", "mime"}, {"audio", "mime"})
    cap = ctx.cfg.max_audio_bytes
    if not isinstance(body["audio"], str) or len(body["audio"]) > cap * 4 // 3 + 8:
        raise R.RoomError(_TOO_LONG)
    try:
        audio = base64.b64decode(body["audio"], validate=True)
    except (binascii.Error, ValueError):
        raise R.RoomError(_BAD_AUDIO) from None
    if not audio or body["mime"] not in ctx.cfg.mimes or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise R.RoomError(_BAD_AUDIO)
    if len(audio) > cap:
        raise R.RoomError(_TOO_LONG)
    try:
        text = await deps.blocking(ctx.speech.transcribe, audio, body["mime"])
    except SpeechUnavailable:
        return {"text": "", "heard": False, "failed": True}
    return {"text": text, "heard": bool(text), "failed": False}


def _say(ctx: Ctx, text: str):
    register_names(ctx.request, ctx.plane, ctx.s["id"])  # D-007 (shared helper, M1-P05)
    return ctx.speech.speak(text)


@router.post("/sessions/{session_id}/voice/speak")
@guarded
async def speak(request: Request, session_id: str):
    ctx, no = await _open(request, session_id)
    if no:
        return no
    text = R.check_text((await _only(request, {"text"}, {"text"}))["text"])
    try:
        audio, mime = await deps.blocking(_say, ctx, text)
    except SpeechUnavailable:
        return {"failed": True}
    clipped = len(" ".join(text.split())) > ctx.cfg.max_chars  # only the start was read (the clip is in the provider)
    return {"audio": base64.b64encode(audio).decode(), "mime": mime, "clipped": clipped}
