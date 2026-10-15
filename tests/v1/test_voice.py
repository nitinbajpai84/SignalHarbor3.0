"""V1 Voice: every company role may ask whether voice is on, have a recording written down and a reply read aloud (stub provider;
the spoken text is clipped to 1,200 characters; a provider failure is `failed: true`, never an error); without sign-in it is refused.
And what an agent reads from a dropped file: one flat line per file (file_context)."""
import base64
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from sh_platform.speech import SpeechUnavailable
from sh_platform.v1.file_context import CANT, added_line, preview_for_agent

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
DEV = "dev.sharma.neera@example.test"  # a participant: the least of the company roles
IID_SPAN = "ini-" + "5" * 32
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32


class Stub:
    name, available, note = "stub", True, ""

    def __init__(self):
        self.said, self.fail = [], False

    def transcribe(self, audio, mime):
        if self.fail:
            raise SpeechUnavailable
        return "Cash drag first"

    def speak(self, text, suppressed=None):
        if self.fail:
            raise SpeechUnavailable
        self.said.append(text)
        return b"RIFFaudio", "audio/wav"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    data = tmp_path_factory.mktemp("voice") / "data"
    shutil.copytree(ROOT / "data", data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.speech_env = {"SH_SPEECH_PROVIDER": "off"}
    return app, data


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_voice_speaks_and_listens_and_fails_quietly(world):
    app, _ = world
    c = client(app, DEV)
    app.state.v1_speech = None
    assert c.get("/api/v1/voice").json() == {"available": False, "note": "Voice is not available right now; keep typing."}
    assert c.post("/api/v1/voice/speak", json={"text": "Hello"}).json() == {"failed": True, "note": "Voice is not available right now; keep typing."}  # NM1: a failure carries the voice line

    stub = Stub()
    app.state.v1_speech = stub
    try:
        assert c.get("/api/v1/voice").json()["available"] is True
        heard = c.post("/api/v1/voice/transcribe", json={"audio": base64.b64encode(WAV).decode(), "mime": "audio/wav"})
        assert heard.status_code == 200 and heard.json() == {"text": "Cash drag first"}
        assert c.post("/api/v1/voice/transcribe", json={"audio": "not audio", "mime": "audio/wav"}).json() == {"failed": True}
        long = "This is one sentence of a long reply. " * 60
        got = c.post("/api/v1/voice/speak", json={"text": long}).json()
        assert base64.b64decode(got["audio"]) == b"RIFFaudio" and got["mime"] == "audio/wav" and got["clipped"] is True
        assert len(stub.said[-1]) <= 1200 and stub.said[-1].endswith(".")
        stub.fail = True
        assert c.post("/api/v1/voice/speak", json={"text": "Hello"}).json() == {"failed": True, "note": "Voice is not available right now; keep typing."}
        assert c.post("/api/v1/voice/transcribe", json={"audio": base64.b64encode(WAV).decode(), "mime": "audio/wav"}).json() == {"failed": True, "note": "Voice is not available right now; keep typing."}
        assert c.post("/api/v1/voice/speak", json={"nope": 1}).status_code == 400
    finally:
        app.state.v1_speech = None


def test_voice_refuses_without_sign_in(world):
    app, _ = world
    assert TestClient(app).get("/api/v1/voice").status_code in (401, 403)


def test_agents_read_dropped_files_as_flat_lines(world):
    _, data = world
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(data).plane_for("neera")
    (plane.path("landing", "cash")).mkdir(parents=True, exist_ok=True)
    plane.path("landing", "cash", "cash.csv").write_text("date,amount\n2026-09-30,100\n2026-10-31,90\n", encoding="utf-8")
    plane.path("documents").mkdir(parents=True, exist_ok=True)
    plane.path("documents", "note.txt").write_text("Fees are " + "x" * 3000, encoding="utf-8")
    files = [{"name": "cash.csv", "path": "landing/cash/cash.csv", "kind": "sample"},
             {"name": "note.txt", "path": "documents/note.txt", "kind": "document"},
             {"name": "board.png", "path": "documents/board.png", "kind": "document"}]
    lines = preview_for_agent(plane, "any", files)
    assert all(isinstance(x, str) and "\n" not in x for x in lines)
    assert lines[0] == "cash.csv (sample): columns: date,amount; values: 2026-09-30,100 | 2026-10-31,90".replace(",", ", ")
    assert lines[1].startswith("note.txt (document): Fees are") and len(lines[1]) <= len("note.txt (document): ") + 1500
    assert lines[2] == f"board.png (document): {CANT}"
    assert added_line(files[:1]) == "I added cash.csv."


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_span_takes_a_dropped_file(world):
    """Span's composer sends a file: stored where I2 stores samples, named in the turn, read as one line for the turn it arrived."""
    import json
    from tests.v1.test_a1 import SOW
    from sh_platform.v1 import a1_chat
    app, data = world
    d = data / "neera" / "intents" / IID_SPAN
    d.mkdir(parents=True, exist_ok=True)
    (d / "sow.json").write_text(json.dumps({**SOW, "intent_id": IID_SPAN}), encoding="utf-8")
    (d / "thread.json").write_text(json.dumps({"intent_id": IID_SPAN, "turns": [], "needs_done": [], "state": "sow_ready"}), encoding="utf-8")
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    c = client(app, "leela.raman.neera@example.test")
    r = c.post(f"/api/v1/build/{IID_SPAN}/blueprint/chat",
               json={"text": "", "files": [{"name": "fees.csv", "data": base64.b64encode(b"fund,fee\nA,0.5\n").decode()}]})
    assert r.status_code == 200, r.text
    person = [t for t in r.json()["turns"] if t["by"] == "person"][-1]
    assert person["text"] == "I added fees.csv." and person["did"] == ["fees.csv"]
    assert (data / "neera" / "landing" / "fees" / "fees.csv").is_file()
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(data).plane_for("neera")
    f = {"name": "fees.csv", "path": "landing/fees/fees.csv", "kind": "sample"}
    ctx = a1_chat.context(plane, IID_SPAN, a1_chat._sow(plane, IID_SPAN), a1_chat.read(plane, IID_SPAN), [f])
    assert ctx["files_now"] == ["fees.csv (sample): columns: fund, fee; values: A, 0.5"]
