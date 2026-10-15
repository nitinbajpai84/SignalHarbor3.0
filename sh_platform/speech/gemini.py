"""Gemini speech (D-028: the free tier, for development and demos only). Every call leaves through the egress gateway
(allowlisted host, one log line before the send, the vault and figure checks); nothing is stored: audio and text exist
in memory for one call. The silence check and the request shape come from the earlier product's emitters/voice.py.

Speech in: the gateway carries a short description of the recording (size and a hash, never the audio); the audio
itself is added only by the transport, after the gateway's checks. Audio cannot be tokenised, so it may leave only
in development with synthetic demo data (A-034). Spoken replies: the text is checked like a model prompt, and
registered names are replaced by a neutral word first, because audio cannot be mapped back.
"""
import array
import base64
import hashlib
import io
import json
import logging
import math
import re
import wave

from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway, make_httpx_transport
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.vault import NameVault
from sh_platform.speech import FREE_TIER_NOTE, SpeechConfig, SpeechUnavailable

log = logging.getLogger(__name__)
ADAPTER = GeminiAdapter()  # the host, the key variable name and the header
NO_SPEECH = "[no speech]"
_PROMPT = ("Transcribe the speech in this recording exactly as spoken. Reply with only the transcript: no quotes, "
           f"labels, timestamps or commentary. If there is no intelligible speech, reply with exactly {NO_SPEECH}")
_TOKEN = re.compile(r"(?<![A-Za-z0-9_])([A-Z_]+)_\d{3,}(?![A-Za-z0-9_])")
_SAID = {"COMPANY": "the company", "PERSON": "a colleague"}  # any other protected detail is "a contact"


def speech_energy(wav: bytes) -> int:
    """How many 50 ms windows of a 16 kHz 16-bit WAV are louder than room noise. Measured before anything is sent:
    given one second of silence, Gemini once "transcribed" it as "no" (earlier product, emitters/voice.py)."""
    if wav[:4] != b"RIFF" or len(wav) <= 44:
        return 0
    samples = array.array("h")
    body = wav[44:]
    samples.frombytes(body[: len(body) - (len(body) % 2)])
    window = 800
    return sum(1 for i in range(0, len(samples) - window + 1, window)
               if math.sqrt(sum(x * x for x in samples[i:i + window]) / window) > 350)


def _clip(text: str, n: int) -> str:
    """At most n characters, cut at the last sentence end (or word) so a reply is never read half a word."""
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    cut = text[:n]
    end = max(cut.rfind(c) for c in ".!?")
    return cut[:end + 1] if end > 0 else cut.rsplit(" ", 1)[0]


class GeminiSpeech:
    name, available, note = "gemini", True, FREE_TIER_NOTE

    def __init__(self, plane, config: SpeechConfig, env, client=None):
        self._plane, self._cfg = plane, config
        # the key is read from `env` by NAME at call time, attached in a header and only for this host
        self._send = make_httpx_transport(ADAPTER.key_env, ADAPTER.header, ADAPTER.scheme, client=client,
                                          model_hosts=[ADAPTER.host], env=env)

    def __repr__(self) -> str:
        return "GeminiSpeech()"

    def _ask(self, model: str, described: str, wire_for, suppressed=None) -> list:
        """One guarded call; the reply parts. `described` is what the gateway checks and hashes; `wire_for(text)` builds
        the provider's request from the guarded text. Any refusal or failure is SpeechUnavailable (reason code only)."""
        if self._plane is None:
            raise SpeechUnavailable

        def transport(url: str, body: bytes) -> str:
            guarded = json.loads(body)["messages"][0]["content"]
            wire = json.dumps(wire_for(guarded), ensure_ascii=False).encode("utf-8")
            return self._send(f"https://{ADAPTER.host}/v1beta/models/{model}:generateContent", wire)
        gateway = EgressGateway(self._plane, NameVault(self._plane), EgressPolicy(self._plane),
                                model_allowlist=[ADAPTER.host], model_url=f"https://{ADAPTER.host}", transport=transport)
        try:
            raw = gateway.send_model_prompt("speech", {"messages": [{"role": "user", "content": described}]},
                                            suppressed, detokenise=False).text
            return json.loads(raw)["candidates"][0]["content"]["parts"]
        except EgressBlocked as e:
            log.info("A speech call was not made or did not finish (%s).", e.reason_code)
        except (ValueError, KeyError, IndexError, TypeError):
            log.info("A speech reply could not be read.")
        raise SpeechUnavailable

    def transcribe(self, audio: bytes, mime: str) -> str:
        c = self._cfg
        if not (audio and len(audio) <= c.max_audio_bytes and mime in c.mimes and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"):
            raise SpeechUnavailable
        if speech_energy(audio) < 4:  # under 200 ms of anything louder than room noise: nothing to send
            return ""
        described = f"audio recording of {len(audio)} bytes, sha256 {hashlib.sha256(audio).hexdigest()[:16]}"
        data = base64.b64encode(audio).decode()
        parts = self._ask(c.stt_model, described, lambda _: {"contents": [{"role": "user", "parts": [
            {"text": _PROMPT}, {"inlineData": {"mimeType": mime, "data": data}}]}]})
        text = "".join(p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)
                       and p.get("thought") is not True).strip().strip('"').strip()
        return "" if text == NO_SPEECH else text

    def speak(self, text: str, suppressed=None) -> tuple[bytes, str]:
        c = self._cfg
        if self._plane is None or not text.strip():
            raise SpeechUnavailable
        said = _TOKEN.sub(lambda m: _SAID.get(m[1], "a contact"), NameVault(self._plane).tokenise(_clip(text, c.max_chars)))
        parts = self._ask(c.tts_model, said, lambda t: {
            "contents": [{"role": "user", "parts": [{"text": f"{c.style} {t}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": c.voice}}}}}, suppressed)
        for p in parts:
            blob = p.get("inlineData") if isinstance(p, dict) else None
            if isinstance(blob, dict) and isinstance(blob.get("data"), str):
                rate = re.search(r"rate=(\d{4,6})", str(blob.get("mimeType")))
                return _wav(base64.b64decode(blob["data"]), int(rate[1]) if rate else 24000), "audio/wav"
        raise SpeechUnavailable


def _wav(pcm: bytes, rate: int) -> bytes:
    """Raw 16-bit mono PCM (what Gemini returns) as a WAV a browser can play; built in memory."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return out.getvalue()
