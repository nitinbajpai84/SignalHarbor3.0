"""M1-09 (and the speech part of M1-08) through the real app: speech in with correction, spoken replies, per-person
mute, silent fallback, the dev-only rule, who may use it, nothing stored. httpx.MockTransport only: no live call.
The real .env holds a key, so every test points the speech settings at its own fake environment."""
import base64
import json
import logging
import math
import struct
from pathlib import Path

import httpx
import pytest
import yaml

from m1_kit import BASE, draft
from modules.m1_intent.store.sessions import SessionStore
from sh_platform.settings import Settings
from test_m1_room_kit import all_text, guest, hdr, new_session, seat_in, start_room as open_link

KEY = "FAKE-speech-key-for-tests-0123"
HOST = "generativelanguage.googleapis.com"
UNAVAILABLE = "North's voice is not available right now; keep typing."
ORDER = ("draft", "lobby", "briefing", "private_rooms", "board", "together", "signing", "closed")


def wav(samples) -> bytes:
    data = b"".join(struct.pack("<h", s) for s in samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


TONE = wav([int(3000 * math.sin(2 * math.pi * 220 * i / 16000)) for i in range(16000)])
SILENCE = wav([0] * 16000)


class Google:
    def __init__(self, status_code=200, text="Renewals slipped in April"):
        self.requests, self.status_code, self.text = [], status_code, text

    def __call__(self, req):
        self.requests.append(req)
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={})
        if "tts" in req.url.path:
            part = {"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(b"\x01\x00" * 50).decode()}}
        else:
            part = {"text": self.text}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [part]}}]})


def advance(world, company, sid, stage):
    store = SessionStore(world.plane(company))
    for nxt in ORDER[ORDER.index(store.get(sid)["state"]) + 1:ORDER.index(stage) + 1]:
        store.transition(sid, nxt)


def speech_on(world, google=None):
    """The fake environment: a fake key and a stand-in for the speech host."""
    google = google or Google()
    world.app.state.speech_env = {"GOOGLE_API_KEY": KEY}
    world.app.state.speech_client = httpx.Client(transport=httpx.MockTransport(google), follow_redirects=False)
    return google


@pytest.fixture(autouse=True)
def fake_environment(world):
    world.app.state.speech_env = {}  # typing only until a test switches speech on
    world.app.state.model_env = {}   # no model key either


def session(world, c, company="co-a", stage="private_rooms", **prep):
    r = c.post(f"{BASE}/sessions", json=draft(**prep))
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    advance(world, company, sid, stage)
    return sid


def voice(sid, what=""):
    return f"{BASE}/sessions/{sid}/voice{what}"


def say(c, sid, audio=TONE, mime="audio/wav", **kw):
    return c.post(voice(sid, "/transcribe"), json={"audio": base64.b64encode(audio).decode(), "mime": mime}, **kw)


def read_aloud(c, sid, text="Who is affected?", **kw):
    return c.post(voice(sid, "/speak"), json={"text": text}, **kw)


# ---- typing only (no provider)

def test_with_no_provider_speech_is_off_in_plain_words_and_typing_still_works(world):
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    v = c.get(voice(sid)).json()
    assert v["available"] is False and v["message"] == UNAVAILABLE and v["on"] is True and v["note"] is None
    assert say(c, sid).json() == {"text": "", "heard": False, "failed": True}
    assert read_aloud(c, sid).json() == {"failed": True}
    r = c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Renewals slipped in April", "kind": "note"})
    assert r.status_code == 200 and r.json()["notes"][0]["text"] == "Renewals slipped in April"  # text is always there


def test_a_provider_name_that_does_not_exist_means_typing_only(world):
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    world.app.state.speech_env = {"GOOGLE_API_KEY": KEY, "SH_SPEECH_PROVIDER": "nonsense"}
    assert c.get(voice(sid)).json()["available"] is False


# ---- speech in, with correction

def test_speech_becomes_text_the_person_corrects_before_it_is_used(world):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    v = c.get(voice(sid)).json()
    assert v["available"] is True and v["message"] is None and v["max_seconds"] == 120
    assert v["note"] == "Speech to text is on"
    r = say(c, sid)
    assert r.status_code == 200 and r.json() == {"text": "Renewals slipped in April", "heard": True, "failed": False}
    assert [x.url.host for x in g.requests] == [HOST] and g.requests[0].headers["x-goog-api-key"] == KEY
    # nothing was saved by listening: the transcript is untouched until the person sends the corrected text
    assert c.get(f"{BASE}/sessions/{sid}/room").json()["turns"] == []
    sent = c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Renewals slipped in May", "kind": "note"})
    assert sent.json()["notes"][0]["text"] == "Renewals slipped in May"


def test_silence_says_nothing_was_heard_and_sends_nothing(world):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    assert say(c, sid, SILENCE).json() == {"text": "", "heard": False, "failed": False}
    assert g.requests == []


def test_speech_in_works_only_while_the_private_rooms_are_open(world):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    for stage in ("lobby", "briefing", "board", "together", "closed"):
        sid = session(world, c, stage=stage)
        r = say(c, sid)
        assert r.status_code == 409 and r.json()["error"] == "rooms_closed", stage
    assert g.requests == []


@pytest.mark.parametrize("body,why", [
    ({"audio": "!!not base64!!", "mime": "audio/wav"}, "not base64"),
    ({"audio": "", "mime": "audio/wav"}, "empty"),
    ({"audio": base64.b64encode(TONE).decode(), "mime": "audio/webm"}, "wrong type"),
    ({"audio": base64.b64encode(b"ID3 not a wav file at all").decode(), "mime": "audio/wav"}, "not a recording"),
    ({"audio": base64.b64encode(TONE + b"\0" * 4_000_000).decode(), "mime": "audio/wav"}, "too long"),
    ({"audio": base64.b64encode(TONE).decode()}, "no type"),
    ({"audio": base64.b64encode(TONE).decode(), "mime": "audio/wav", "extra": 1}, "extra field"),
    ([], "not an object"),
])
def test_a_recording_that_cannot_be_taken_is_refused_in_plain_words_without_a_call(world, body, why):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    r = c.post(voice(sid, "/transcribe"), json=body)
    assert r.status_code == 422, why
    assert r.json()["message"] and "Traceback" not in r.text and "{" not in r.json()["message"]
    assert g.requests == []


# ---- spoken replies

def test_a_reply_is_spoken_through_the_gateway_with_names_replaced_and_text_untouched(world):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": "Renewals slipped", "kind": "note"})
    r = read_aloud(c, sid, "Pat Organiser, who at Co-A is affected?")
    body = r.json()
    assert r.status_code == 200 and body["mime"] == "audio/wav" and base64.b64decode(body["audio"])[:4] == b"RIFF"
    sent = g.requests[-1].content.decode()
    assert "Pat" not in sent and "Organiser" not in sent and "Co-A" not in sent and "a colleague" in sent
    log = (world.plane("co-a").area("context") / "egress_log.jsonl").read_text()
    assert HOST in log and "Pat" not in log and "affected" not in log
    assert [t["text"] for t in c.get(f"{BASE}/sessions/{sid}/room").json()["turns"]][0] == "Renewals slipped"


def test_seated_peoples_names_are_registered_before_a_reply_is_spoken(world):
    g = speech_on(world)
    org = world.login("Pat Organiser", "co-a")
    sid = new_session(org, seats=3)
    code = open_link(org, sid)
    advance(world, "co-a", sid, "private_rooms")
    seat_in(world, guest(world), code, 1, name="Zelda Quillfeather")
    assert read_aloud(org, sid, "Zelda Quillfeather will follow up.").status_code == 200
    sent = g.requests[-1].content.decode()
    assert "Zelda" not in sent and "Quillfeather" not in sent and "a colleague" in sent


def test_a_clipped_reply_says_so_and_a_short_one_does_not(world):
    speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    assert read_aloud(c, sid, "Short one.").json()["clipped"] is False
    assert read_aloud(c, sid, "A sentence here. " * 30).json()["clipped"] is True


def test_a_failing_speech_service_is_silent(world):
    speech_on(world, Google(status_code=503))
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    r = read_aloud(c, sid)
    assert r.status_code == 200 and r.json() == {"failed": True}
    assert say(c, sid).json() == {"text": "", "heard": False, "failed": True}


def test_a_reply_that_is_empty_or_too_long_for_the_page_is_refused_plainly(world):
    speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    assert read_aloud(c, sid, "  ").status_code == 422
    assert read_aloud(c, sid, "x " * 3000).status_code == 422
    assert c.post(voice(sid, "/speak"), json={"text": "hi", "voice": "other"}).status_code == 422


# ---- development and demos only

def test_gemini_does_not_run_outside_development_and_the_screens_fall_back_to_typing(world):
    g = speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    world.app.state.settings = Settings(mode="prod", data_root=world.settings.data_root, session_secret="x" * 40)
    v = c.get(voice(sid)).json()
    assert v["available"] is False and v["message"] == UNAVAILABLE and v["note"] is None
    assert say(c, sid).json()["failed"] is True and read_aloud(c, sid).json() == {"failed": True}
    assert g.requests == []


def test_nira_read_aloud_hook_follows_the_same_provider(world):
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    assert c.get(f"{BASE}/sessions/{sid}/briefing").json()["read_aloud"]["available"] is False
    speech_on(world)
    assert c.get(f"{BASE}/sessions/{sid}/briefing").json()["read_aloud"]["available"] is True
    assert world.app.state.speech_provider.available is True


# ---- mute, per person

def test_mute_is_remembered_per_seat_and_holds_no_audio(world):
    speech_on(world)
    org = world.login("Pat Organiser", "co-a")
    sid = new_session(org, seats=3)
    code = open_link(org, sid)
    advance(world, "co-a", sid, "private_rooms")
    t1, _ = seat_in(world, guest(world), code, 1, name="Ada Example")
    t2, _ = seat_in(world, guest(world), code, 2, name="Bo Example")
    g = guest(world)
    assert g.post(voice(sid), json={"on": False}, headers=hdr(t1)).json()["on"] is False
    assert g.get(voice(sid), headers=hdr(t1)).json()["on"] is False
    assert g.get(voice(sid), headers=hdr(t2)).json()["on"] is True       # another seat is unaffected
    assert org.get(voice(sid)).json()["on"] is True                      # so is the organiser
    assert org.post(voice(sid), json={"on": False}).json()["on"] is False
    assert g.post(voice(sid), json={"on": True}, headers=hdr(t1)).json()["on"] is True
    assert org.get(voice(sid)).json()["on"] is False
    for bad in ({"on": "no"}, {}, {"on": False, "x": 1}, {"on": 0}):
        assert org.post(voice(sid), json=bad).status_code == 422
    stored = all_text(world.settings.data_root)
    assert "RIFF" not in stored and base64.b64encode(TONE).decode()[:30] not in stored


# ---- who may use it

def test_only_the_seats_own_person_may_use_voice(world):
    speech_on(world)
    org = world.login("Pat Organiser", "co-a")
    sid = new_session(org, seats=3)
    code = open_link(org, sid)
    advance(world, "co-a", sid, "private_rooms")
    mine, _ = seat_in(world, guest(world), code, 1)
    other_sid = session(world, world.login("Other Organiser", "co-a"))
    sid_b = session(world, world.login("Bea Organiser", "co-b"), company="co-b")
    third, cy = world.login("Third Organiser", "co-a"), world.login("Cy Organiser", "co-b")
    routes = [("get", "", None), ("post", "", {"on": False}), ("post", "/transcribe", {"audio": base64.b64encode(TONE).decode(), "mime": "audio/wav"}),
              ("post", "/speak", {"text": "hi"})]

    def call(c, s, method, tail, body, **kw):
        return getattr(c, method)(voice(s, tail), **({"json": body} if body is not None else {}), **kw)
    for method, tail, body in routes:
        # a signed-out browser, and a browser with a token for another session, get the signed-out answer
        assert call(guest(world), sid, method, tail, body).status_code == 401
        assert call(guest(world), sid, method, tail, body, headers=hdr("0" * 32 + "." + "A" * 43)).status_code == 401
        # another organiser of the same company, a person of another company, and the same organiser asking for
        # somebody else's session all get the same "not found"
        assert call(third, sid, method, tail, body).status_code == 404
        assert call(cy, sid, method, tail, body).status_code == 404
        assert call(org, other_sid, method, tail, body).status_code == 404
        assert call(org, sid_b, method, tail, body).status_code == 404
        # a token holder cannot reach another session
        assert call(guest(world), other_sid, method, tail, body, headers=hdr(mine)).status_code in (401, 404)
        # the right person can
        assert call(guest(world), sid, method, tail, body, headers=hdr(mine)).status_code == 200
    # a role with no access to the module is refused
    assert world.login("Ann Approver", "co-a", roles=("approver",)).get(voice(sid)).status_code == 403


def test_a_guest_can_speak_into_their_own_private_room(world):
    g = speech_on(world)
    org = world.login("Pat Organiser", "co-a")
    sid = new_session(org, seats=3)
    code = open_link(org, sid)
    advance(world, "co-a", sid, "private_rooms")
    token, _ = seat_in(world, guest(world), code, 1, name="Ada Example")
    r = say(guest(world), sid, headers=hdr(token))
    assert r.status_code == 200 and r.json()["text"] == "Renewals slipped in April"
    advance(world, "co-a", sid, "board")
    assert say(guest(world), sid, headers=hdr(token)).status_code == 409
    assert len(g.requests) == 1


# ---- nothing kept, every company shape

def test_no_audio_or_spoken_text_is_stored_or_logged(world, caplog):
    caplog.set_level(logging.DEBUG)
    speech_on(world)
    c = world.login("Pat Organiser", "co-a")
    sid = session(world, c)
    say(c, sid)
    read_aloud(c, sid, "A private sentence about renewals")
    stored = all_text(world.settings.data_root)
    assert "private sentence" not in stored and "Renewals slipped in April" not in stored
    assert base64.b64encode(TONE).decode()[:30] not in stored and KEY not in stored
    assert "private sentence" not in caplog.text and KEY not in caplog.text
    assert "RIFF" not in stored


@pytest.mark.parametrize("company,seats", [("co-a", 3), ("co-b", 3), ("co-none", 3), ("co-empty", 2), ("co-solo", 1)])
def test_voice_works_for_two_industries_an_empty_company_and_a_solo_run(world, company, seats):
    speech_on(world)
    c = world.login("Pat Organiser", company)
    sid = session(world, c, company=company, seats=seats)
    assert c.get(voice(sid)).json()["available"] is True
    assert say(c, sid).json()["heard"] is True and "audio" in read_aloud(c, sid).json()


def test_the_speech_routes_are_declared_and_open_to_seated_guests():
    root = Path(__file__).resolve().parents[3]
    table = yaml.safe_load((root / "sh_platform" / "route_permissions.yaml").read_text(encoding="utf-8"))["routes"]
    manifest = yaml.safe_load((root / "modules" / "m1_intent" / "manifest.yaml").read_text(encoding="utf-8"))["routes"]
    declared = {f"{r['method']} {r['path']}" for r in manifest}
    base = "/api/modules/m1_intent/sessions/{session_id}/voice"
    for key in (f"GET {base}", f"POST {base}", f"POST {base}/transcribe", f"POST {base}/speak"):
        assert key in declared and table[key]["guest"] is True and "participant" in table[key]["roles"], key
