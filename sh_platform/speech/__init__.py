"""Speech for the screens (M1-09, D-028): speech in (`transcribe`) and spoken replies (`speak`) behind one small shape.

A provider has `name`, `available`, `note`, `transcribe(audio, mime) -> str` and `speak(text, suppressed=None) ->
(audio bytes, mime)`. Anything that cannot be done raises SpeechUnavailable and the screens carry on in text with no
error shown. Two providers exist: `stub` (typing only) and `gemini` (the free tier: development and demos only). A
paid tier or a local engine is a new entry in `build_speech`, chosen by the setting; no screen changes.

Settings, names only (values are never printed or logged): SH_SPEECH_PROVIDER or SPEECH_PROVIDER (gemini, stub or
off; unset means gemini when GOOGLE_API_KEY exists), GOOGLE_API_KEY. Model names and limits come from the module's
contract (SpeechConfig), never from code. Gemini runs only when SH_MODE is dev (A-033).
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sh_platform.settings import _read_env_file, load_model_env

FREE_TIER_NOTE = "Speech is on the Gemini free tier: development and demos only"
PROVIDERS = ("gemini", "stub")
_NAMES = ("SH_SPEECH_PROVIDER", "SPEECH_PROVIDER", "SH_SPEECH_IN_PROD")
_OFF = ("stub", "off", "none")


class SpeechUnavailable(Exception):
    """Speech could not be used (no provider, refused by the egress checks, or the service failed). Holds no content."""


@dataclass(frozen=True)
class SpeechConfig:
    """What the module's contract says; the provider reads nothing else."""
    stt_model: str
    tts_model: str
    voice: str
    style: str
    mimes: tuple[str, ...]
    max_audio_bytes: int
    max_chars: int


class StubSpeech:
    name, available, note = "stub", False, ""

    def transcribe(self, audio: bytes, mime: str) -> str:
        raise SpeechUnavailable

    def speak(self, text: str, suppressed=None) -> tuple[bytes, str]:
        raise SpeechUnavailable


def load_speech_env(env: Mapping[str, str] | None = None, env_file: Path | None = None) -> dict[str, str]:
    """The model key (GOOGLE_API_KEY) and the speech provider names from .env and the process environment, which wins
    even when empty (so `GOOGLE_API_KEY=` switches Gemini off)."""
    env = os.environ if env is None else env
    return {**load_model_env(env, env_file), **_read_env_file(env_file or Path(".env"), lambda n: n in _NAMES),
            **{k: env[k] for k in _NAMES if k in env}}


def status(env: Mapping[str, str], mode: str) -> dict:
    """For the screens and the doctor: which provider is in use (None: typing only), its note, a problem in words, and
    `ok` (False only when a setting names a provider that does not exist). Names only, never a value."""
    key = (env.get("GOOGLE_API_KEY") or "").strip()
    want = (env.get("SH_SPEECH_PROVIDER") or env.get("SPEECH_PROVIDER") or "").strip().lower() or ("gemini" if key else "stub")
    if want in _OFF:
        return {"provider": None, "note": "", "problem": None, "ok": True}
    if want not in PROVIDERS:
        return {"provider": None, "note": "", "problem": f"SH_SPEECH_PROVIDER must be one of {', '.join(PROVIDERS)} or off.", "ok": False}
    if mode != "dev" and (env.get("SH_SPEECH_IN_PROD") or "").strip() != "1":  # A-033: dev only, unless the owner switches it on for everyone (Nitin, 13 Oct)
        return {"provider": None, "note": "", "ok": True,
                "problem": "The Gemini free tier is for development and demos only, so speech is off unless the mode is dev (SH_MODE=dev)."}
    if not key:
        return {"provider": None, "note": "", "problem": "No GOOGLE_API_KEY is set, so speech is off and typing is used.", "ok": True}
    return {"provider": "gemini", "note": FREE_TIER_NOTE, "problem": None, "ok": True}


def build_speech(plane, config: SpeechConfig, env: Mapping[str, str], mode: str, client=None):
    """The provider the settings choose. `plane` may be None to only ask `available`; `client` is an httpx client
    (tests pass a MockTransport one)."""
    if status(env, mode)["provider"] != "gemini":
        return StubSpeech()
    from sh_platform.speech.gemini import GeminiSpeech  # not at the top: gemini.py imports this module
    return GeminiSpeech(plane, config, env, client)
