"""V1 Voice routes: speech in and spoken replies for every agent screen (North, Span, Flow, Lumen), not tied to a session.

Copied from 2.0's modules/m1_intent/api/voice.py (the settings override, the contract read, the audio checks, the `failed: true`
convention) and calling the same provider (sh_platform.speech: `build_speech`, `transcribe`, `speak`). A speech failure is never
an error: transcribe and speak answer 200 with `failed: true` and the screen carries on in text. Audio travels as base64 in JSON,
lives in memory for one request and is never stored. Spoken text is clipped to MAX_SPEAK characters (at a sentence end) and leaves
only through the provider, which goes through the egress gateway; the company's and the person's names are registered with the
vault first, as 2.0 does. Gemini runs only when SH_MODE is dev (A-033), so outside development the answer is `available: false`.

- `GET /api/v1/voice` → {available, note}
- `POST /api/v1/voice/transcribe` {audio (base64 WAV), mime} → {text} or {failed: true}
- `POST /api/v1/voice/speak` {text} → {audio (base64), mime, clipped} or {failed: true}
Tests set `app.state.v1_speech` to a provider of their own; `app.state.speech_env` overrides the settings as in 2.0.
"""
import base64
import binascii

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from modules.m1_intent.domain import contracts as M1C
from sh_platform.build.agents.runtime import register_names
from sh_platform.profile.api import _plane
from sh_platform.speech import SpeechConfig, SpeechUnavailable, build_speech, load_speech_env
from sh_platform.speech.gemini import _clip
from sh_platform.v1.seats import viewer_of

router = APIRouter()
MAX_SPEAK = 1200
UNAVAILABLE = "Voice is not available right now; keep typing."
FAILED = {"failed": True}


def _why(plane, viewer) -> str:
    """NM1: what the screen says when voice cannot be used: the model account's trouble in the wave-2 words (an administrator is told how to
    fix it, anyone else that the assistant is offline) when a provider refuses; otherwise the plain line."""
    try:
        from sh_platform.v1 import e6_trace
        return e6_trace.model_offline_line(plane, viewer) if plane is not None and e6_trace.model_trouble(plane) else UNAVAILABLE
    except Exception:  # noqa: BLE001 - a note never costs the answer
        return UNAVAILABLE


def _config(request: Request) -> SpeechConfig:
    """2.0's speech contract (modules/m1_intent/contracts/speech.yaml), with the spoken length raised to MAX_SPEAK for 1.0."""
    d = M1C._read(getattr(request.app.state, "m1_contracts_dir", None), "speech.yaml")
    g = d["gemini"]
    return SpeechConfig(stt_model=str(g["transcribe_model"]), tts_model=str(g["speak_model"]), voice=str(g["voice"]),
                        style=str(d["speak_style"]), mimes=tuple(str(m) for m in d["audio_mime_types"]),
                        max_audio_bytes=int(d["max_audio_bytes"]), max_chars=MAX_SPEAK)


def _speech(request: Request, plane):
    st = request.app.state
    if getattr(st, "v1_speech", None) is not None:
        return st.v1_speech
    env = getattr(st, "speech_env", None)
    return build_speech(plane, _config(request), dict(env) if env is not None else load_speech_env(), st.settings.mode,
                        getattr(st, "speech_client", None))


def _open(request: Request):
    """(plane, provider) or (None, None) when the company space or the speech settings cannot be read (then: not available)."""
    try:
        plane = _plane(request)
        return plane, _speech(request, plane)
    except (PermissionError, LookupError, KeyError, TypeError, ValueError, M1C.ContractError):
        return None, None


async def _body(request: Request, keys: set) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict) or not keys <= set(body) or not all(isinstance(body[k], str) for k in keys):
        raise HTTPException(400, {"error": "invalid", "message": "That could not be read. Please try again."})
    return body


@router.get("/api/v1/voice")
async def voice(request: Request):
    viewer = viewer_of(request)
    plane, speech = await run_in_threadpool(_open, request)
    ok = bool(speech is not None and speech.available)
    return {"available": ok, "note": ("Voice runs on a development service: synthetic data only." if speech.note else None) if ok
            else await run_in_threadpool(_why, plane, viewer)}


@router.post("/api/v1/voice/transcribe")
async def transcribe(request: Request):
    viewer = viewer_of(request)
    body = await _body(request, {"audio", "mime"})

    def work():
        plane, speech = _open(request)
        if speech is None or not speech.available:
            return {**FAILED, "note": _why(plane, viewer)}
        try:
            audio = base64.b64decode(body["audio"], validate=True)
        except (binascii.Error, ValueError):
            return FAILED
        if not audio or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            return FAILED
        try:
            return {"text": speech.transcribe(audio, body["mime"])}
        except SpeechUnavailable:
            return {**FAILED, "note": _why(plane, viewer)}
    return await run_in_threadpool(work)


@router.post("/api/v1/voice/speak")
async def speak(request: Request):
    viewer = viewer_of(request)
    text = (await _body(request, {"text"}))["text"]
    if not text.strip():
        raise HTTPException(400, {"error": "invalid", "message": "There is nothing to read aloud."})

    def work():
        plane, speech = _open(request)
        if speech is None or not speech.available:
            return {**FAILED, "note": _why(plane, viewer)}
        said = _clip(text, MAX_SPEAK)
        company = (request.app.state.entitlements.company(request.state.company_id) or {}).get("name") or ""
        register_names(plane, str(company), [viewer.name])  # D-007: names never leave as themselves
        try:
            audio, mime = speech.speak(said)
        except SpeechUnavailable:
            return {**FAILED, "note": _why(plane, viewer)}
        return {"audio": base64.b64encode(audio).decode(), "mime": mime, "clipped": len(said) < len(" ".join(text.split()))}
    return await run_in_threadpool(work)
