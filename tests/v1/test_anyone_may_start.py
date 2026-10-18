"""Anyone with a company role may start an intent and talk to North; the project's team check still guards someone else's;
only the raiser (or the sponsor) signs, so an analyst who raised it signs, and a team member who did not cannot."""
import shutil
from pathlib import Path

import pytest

from sh_platform.app import create_app
from sh_platform.settings import Settings
from tests.v1.team import on_team
from tests.v1.test_i6a import ARJUN, CREDS, LEELA, client
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
DEV = "dev.sharma.neera@example.test"  # participant
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("anyone") / "data"
    shutil.copytree(SEED, data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def test_analyst_and_participant_start_and_talk(app):
    for email in (LEELA, DEV):
        c = client(app, email)
        iid = c.post("/api/v1/intents/chat", json={"text": "Monthly returns pack"}).json()["id"]
        assert c.post(f"/api/v1/intents/{iid}/chat", json={"text": "For the board"}).status_code == 200
        assert c.post("/api/v1/intents", json={"line": "Another one"}).status_code == 200


def test_off_team_person_is_refused_on_someone_elses_intent(app):
    iid = client(app, LEELA).post("/api/v1/intents/chat", json={"text": "Private to the analyst's team"}).json()["id"]
    dev = client(app, DEV)
    assert dev.post(f"/api/v1/intents/{iid}/chat", json={"text": "hello"}).status_code == 403


def test_raiser_who_is_an_analyst_signs_and_a_team_member_cannot(app):
    leela = client(app, LEELA)
    iid = leela.post("/api/v1/intents/chat", json={"text": "Monthly returns pack"}).json()["id"]
    url = f"/api/v1/intents/{iid}/sow"
    sow = leela.get(url).json()
    assert sow["may"]["edit"] is True
    on_team(app, iid, "Dev Sharma", "builder")
    dev = client(app, DEV)
    assert dev.get(url).json()["may"]["sign"] is False
    assert dev.post(url + "/sign", json={"confirm": True, "version": sow["version"]}).status_code == 403
    r = leela.post(url + "/sign", json={"confirm": True, "version": sow["version"]})
    assert r.status_code != 403, r.text  # the raiser is let in; the draft itself may still be refused as not ready
