"""M1-P06 speech provider (D-028): selection, the dev-only rule, the way out through the egress gateway, no audio
kept. httpx.MockTransport only: no live call, no real key (the key below is a fake string)."""
import base64
import json
import logging
import math
import struct

import httpx
import pytest

from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.vault import NameVault
from sh_platform.speech import FREE_TIER_NOTE, SpeechConfig, SpeechUnavailable, build_speech, load_speech_env, status

KEY = "FAKE-speech-key-for-tests-0123"
HOST = "generativelanguage.googleapis.com"
CFG = SpeechConfig(stt_model="stt-test-model", tts_model="tts-test-model", voice="Test", style="Say this warmly:",
                   mimes=("audio/wav",), max_audio_bytes=200_000, max_chars=80)


def wav(samples) -> bytes:
    data = b"".join(struct.pack("<h", s) for s in samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


TONE = wav([int(3000 * math.sin(2 * math.pi * 220 * i / 16000)) for i in range(16000)])
SILENCE = wav([0] * 16000)


def log_lines(plane):
    p = plane.area("context") / "egress_log.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []


class Google:
    """A stand-in for the speech host: records each request, answers like the real one."""

    def __init__(self, plane=None, text="Which renewals slipped", status_code=200):
        self.requests, self.before, self.plane, self.text, self.status_code = [], [], plane, text, status_code

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        self.before.append(len(log_lines(self.plane)) if self.plane else None)
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"error": "x"})
        if "tts-test-model" in req.url.path:
            pcm = base64.b64encode(b"\x01\x00" * 100).decode()
            part = {"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": pcm}}
        else:
            part = {"text": self.text}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [part]}}]})

    def wire(self, i=-1) -> dict:
        return json.loads(self.requests[i].content)


def make(plane, google, mode="dev", env=None):
    client = httpx.Client(transport=httpx.MockTransport(google), follow_redirects=False)
    return build_speech(plane, CFG, {"GOOGLE_API_KEY": KEY} if env is None else env, mode, client=client)


# ---- selection (settings only)

def test_no_key_means_the_stub_and_typing(plane):
    p = build_speech(plane, CFG, {}, "dev")
    assert (p.name, p.available) == ("stub", False)
    with pytest.raises(SpeechUnavailable):
        p.speak("hello")
    with pytest.raises(SpeechUnavailable):
        p.transcribe(TONE, "audio/wav")


def test_a_key_in_development_selects_gemini(plane):
    p = make(plane, Google(plane))
    assert (p.name, p.available) == ("gemini", True)
    assert p.note == FREE_TIER_NOTE == "Speech is on the Gemini free tier: development and demos only"


@pytest.mark.parametrize("env", [{"GOOGLE_API_KEY": KEY, "SH_SPEECH_PROVIDER": "stub"},
                                 {"GOOGLE_API_KEY": KEY, "SPEECH_PROVIDER": "off"},
                                 {"GOOGLE_API_KEY": KEY, "SH_SPEECH_PROVIDER": "nonsense"},
                                 {"GOOGLE_API_KEY": "  ", "SH_SPEECH_PROVIDER": "gemini"}])
def test_settings_switch_speech_off_or_to_the_stub(plane, env):
    assert build_speech(plane, CFG, env, "dev").available is False


def test_the_provider_name_comes_from_either_setting_name(plane):
    for name in ("SH_SPEECH_PROVIDER", "SPEECH_PROVIDER"):
        assert build_speech(plane, CFG, {name: "gemini", "GOOGLE_API_KEY": KEY}, "dev").name == "gemini"


def test_gemini_is_refused_outside_development(plane):
    g = Google(plane)
    for mode in ("prod", "", "staging"):
        p = make(plane, g, mode=mode)
        assert p.available is False
        with pytest.raises(SpeechUnavailable):
            p.speak("hello")
        with pytest.raises(SpeechUnavailable):
            p.transcribe(TONE, "audio/wav")
    assert g.requests == []
    s = status({"GOOGLE_API_KEY": KEY, "SH_SPEECH_PROVIDER": "gemini"}, "prod")
    assert s["provider"] is None and "development" in s["problem"]


def test_status_names_the_provider_and_never_a_value():
    s = status({"GOOGLE_API_KEY": KEY}, "dev")
    assert s["provider"] == "gemini" and s["note"] == FREE_TIER_NOTE and KEY not in json.dumps(s)
    assert status({}, "dev")["provider"] is None
    assert "must be one of" in status({"SH_SPEECH_PROVIDER": "nonsense"}, "dev")["problem"]


def test_an_empty_environment_variable_beats_the_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text(f"GOOGLE_API_KEY={KEY}\nSPEECH_PROVIDER=gemini\nSH_MODE=dev\n")
    assert load_speech_env({}, f)["GOOGLE_API_KEY"] == KEY
    assert load_speech_env({"GOOGLE_API_KEY": ""}, f)["GOOGLE_API_KEY"] == ""
    assert load_speech_env({}, f)["SPEECH_PROVIDER"] == "gemini" and "SH_MODE" not in load_speech_env({}, f)


# ---- the key

def test_the_key_goes_in_a_header_only_and_never_shows_anywhere(plane, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    g = Google(plane)
    p = make(plane, g)
    p.transcribe(TONE, "audio/wav")
    p.speak("Hello there")
    for req in g.requests:
        assert req.headers["x-goog-api-key"] == KEY
        assert KEY not in str(req.url) and KEY.encode() not in req.content
    assert KEY not in repr(p) + str(vars(p)) + caplog.text
    assert KEY not in "".join(f.read_text(errors="ignore") for f in tmp_path.rglob("*") if f.is_file())
    with pytest.raises(SpeechUnavailable) as e:
        make(plane, Google(plane, status_code=500)).speak("Hello there")
    assert KEY not in str(e.value) + repr(e.value)


# ---- speech in (ported from the old voice tests, reshaped)

def test_silence_is_never_sent(plane):
    g = Google(plane)
    assert make(plane, g).transcribe(SILENCE, "audio/wav") == ""
    assert g.requests == [] and log_lines(plane) == []


def test_speech_level_audio_is_transcribed_and_no_speech_reads_as_empty(plane):
    g = Google(plane)
    p = make(plane, g)
    assert p.transcribe(TONE, "audio/wav") == "Which renewals slipped"
    assert g.requests[0].url.path == "/v1beta/models/stt-test-model:generateContent"
    g.text = "[no speech]"
    assert p.transcribe(TONE, "audio/wav") == ""


@pytest.mark.parametrize("audio,mime", [(b"", "audio/wav"), (b"RIFF....WAVE", "audio/webm"),
                                        (b"ID3 not a wav file at all", "audio/wav"), (TONE + b"\0" * 300_000, "audio/wav")],
                         ids=["empty", "wrong type", "not a wav", "too long"])
def test_audio_it_cannot_take_is_refused_without_a_call(plane, audio, mime):
    g = Google(plane)
    with pytest.raises(SpeechUnavailable):
        make(plane, g).transcribe(audio, mime)
    assert g.requests == []


# ---- the way out

def test_one_log_line_is_written_before_each_send_and_holds_no_content(plane):
    g = Google(plane)
    p = make(plane, g)
    p.transcribe(TONE, "audio/wav")
    p.speak("Hello there, this is private")
    assert g.before == [1, 2]  # the line for a call is already on disk when the call is made
    lines = log_lines(plane)
    assert [x["decision"] for x in lines] == ["sent", "sent"] and {x["host"] for x in lines} == {HOST}
    assert all(set(x) >= {"host", "bytes", "sha256", "decision"} for x in lines)
    blob = json.dumps(lines)
    assert "private" not in blob and base64.b64encode(TONE).decode()[:40] not in blob
    assert {r.url.host for r in g.requests} == {HOST}


def test_a_redirect_is_not_followed(plane):
    seen = []

    def handler(req):
        seen.append(req.url.host)
        return httpx.Response(302, headers={"location": "https://evil.example.test/x"})
    with pytest.raises(SpeechUnavailable):
        make(plane, handler).speak("Hello")
    assert seen == [HOST]


def test_registered_names_are_replaced_before_text_to_speech(plane):
    NameVault(plane).register("person", "Priya Raman")
    NameVault(plane).register("company", "Harbor Test Co")
    g = Google(plane)
    make(plane, g).speak("Priya Raman said Harbor Test Co is slipping. Write to priya@example.test.")
    sent = json.dumps(g.wire())
    for secret in ("Priya", "Raman", "Harbor Test", "priya@example.test"):
        assert secret not in sent
    assert "a colleague" in sent and "the company" in sent
    assert "Priya" not in json.dumps(log_lines(plane))


def test_figures_from_small_groups_never_leave(plane):
    g = Google(plane)
    held = SuppressedFigures()
    held.add({"label": "claims in the north", "value": 1234, "group_size": 3})
    with pytest.raises(SpeechUnavailable):
        make(plane, g).speak("There were 1234 claims.", suppressed=held)
    assert g.requests == []
    assert [x["decision"] for x in log_lines(plane)] == ["blocked"]


def test_a_failure_is_silent_and_logged_twice(plane):
    g = Google(plane, status_code=503)
    with pytest.raises(SpeechUnavailable):
        make(plane, g).speak("Hello there")
    assert [x["decision"] for x in log_lines(plane)] == ["sent", "failed"]


def test_spoken_audio_is_a_wav_and_long_text_is_clipped_at_a_sentence(plane):
    g = Google(plane)
    audio, mime = make(plane, g).speak("First thought here. Second thought is here. Third one goes on and on and on and on.")
    assert mime == "audio/wav" and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
    assert struct.unpack("<I", audio[24:28])[0] == 24000
    spoken = g.wire()["contents"][0]["parts"][0]["text"]
    assert spoken.startswith("Say this warmly:") and "Second thought is here." in spoken and "Third" not in spoken
    assert g.wire()["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Test"


# ---- no audio kept (D-018)

def test_no_audio_or_spoken_text_is_stored_or_logged(plane, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    p = make(plane, Google(plane))
    p.transcribe(TONE, "audio/wav")
    p.speak("A very private sentence about renewals")
    for f in (f for f in tmp_path.rglob("*") if f.is_file()):
        data = f.read_bytes()
        assert TONE[:200] not in data and base64.b64encode(TONE)[:60] not in data and b"private sentence" not in data
    assert "private sentence" not in caplog.text and "Which renewals" not in caplog.text
