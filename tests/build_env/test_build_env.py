"""BC-1: the environment check. Synthetic data only."""
import base64

from pf_kit import FAMILY, OTHER, SYSTEMS
from sh_platform.plane import PlaneStore

URL = "/api/company/build/environment"


def answers(c):
    return {q["key"]: q["answer"] for q in c.get(URL).json()["questions"]}


def test_prefill_marks_guessed_and_unknown(env):
    admin = env.login("company_admin")
    admin.post("/api/profile/inputs/6/upload", json={"filename": "systems.csv", "data": base64.b64encode(SYSTEMS).decode()})
    a = answers(admin)
    assert a["warehouse_location"]["mark"] == "guessed" and a["arrival"]["mark"] == "guessed"
    assert "daily file" in a["arrival"]["value"] and a["arrival"]["from"]
    assert a["scheduler"]["mark"] == "unknown" and a["scheduler"]["value"] is None


def test_confirm_makes_stated_and_a_guess_never_overwrites_it(env):
    admin = env.login("company_admin")
    r = admin.put(URL, json={"answers": {"scheduler": "A cron on the office server"}})
    assert r.status_code == 200
    a = answers(admin)["scheduler"]
    assert a["mark"] == "stated" and a["value"] == "A cron on the office server" and a["by"]
    admin.post("/api/profile/inputs/6/upload", json={"filename": "s.csv", "data": base64.b64encode(b"System,Kind\nNightly Airflow,airflow\n").decode()})
    assert answers(admin)["scheduler"]["value"] == "A cron on the office server"  # the new guess is ignored
    assert env.login("analyst").put(URL, json={"answers": {"scheduler": "x"}}).status_code == 403
    assert env.login("analyst").get(URL).status_code == 200 and env.login("sponsor").get(URL).status_code == 403


def test_another_company_sees_none_of_it(env):
    env.login("company_admin").put(URL, json={"answers": {"alerts": "Email to the desk"}})
    other = env.login("company_admin", OTHER)
    assert answers(other)["alerts"]["mark"] == "unknown"
    assert env.login("company_admin").put(URL, json={"answers": {"nope": "x"}}).status_code == 422
