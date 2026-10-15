"""R2: the UAT sign-off. Synthetic data only. Reuses the seeded-company fixtures of tests/build_env."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "build_env"
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("uat_env_conftest", HERE / "conftest.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
seeded, planes, stub, env = _mod.seeded, _mod.planes, _mod.stub, _mod.env

from pf_kit import FAMILY  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402

URL = "/api/company/build/uat/M1/sign"


def whoami(env, role):
    c = env.login(role)
    acct = env.app.state.account_store.get_by_email(f"{role}.{FAMILY}@example.test")
    return c, acct["display_name"]


def charter(env, tester):
    plane = PlaneStore(env.app.state.settings.data_root).plane_for(FAMILY)
    p = plane.path("intents", "m1_intent", "outcomes", "c" * 32 + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"kind": "charter", "session_id": "s1", "signed_at": "2026-09-01T09:00:00+00:00"}), encoding="utf-8")
    roles = plane.path("intents", "m1_intent", "roles", "s1.json")  # where the roles route keeps them
    roles.parent.mkdir(parents=True, exist_ok=True)
    roles.write_text(json.dumps({"roles": {"tester": tester, "sponsor": "x"}}), encoding="utf-8")
    return plane.path("build", "prove.json")


def test_named_tester_signs_and_the_file_is_created_when_absent(env):
    sponsor, name = whoami(env, "sponsor")
    prove = charter(env, name)
    assert not prove.exists()
    r = sponsor.post(URL, json={"state": "signed", "note": "Checked"})
    assert r.status_code == 200 and r.json()["by"] == name
    doc = json.loads(prove.read_text(encoding="utf-8"))
    assert doc["measures"][0]["code"] == "M1" and doc["measures"][0]["uat"]["state"] == "signed" and set(doc) == {"measures"}
    assert sponsor.post(URL, json={"state": "sent_back", "note": "x"}).status_code == 409  # signed is final


def test_sent_back_needs_a_note(env):
    sponsor, name = whoami(env, "sponsor")
    charter(env, name)
    assert sponsor.post(URL, json={"state": "sent_back"}).status_code == 400
    assert sponsor.post(URL, json={"state": "sent_back", "note": "Totals differ"}).json()["state"] == "sent_back"


def test_another_person_is_refused_and_told_who_may_sign(env):
    admin, _ = whoami(env, "company_admin")
    charter(env, "Tess Tester")
    r = admin.post(URL, json={"state": "signed"})
    assert r.status_code == 403 and "Tess Tester" in r.json()["detail"]
