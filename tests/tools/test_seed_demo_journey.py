"""tools/seed_demo_journey.py on a temporary company: the journey runs clean, the participant's pulse holds the live invite, and a second run
changes nothing. The company, its accounts and its profile people are synthetic and made here (what tools/seed.py and Lens would have made)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from sh_platform.auth.accounts import AccountStore
from sh_platform.entitlements import EntitlementStore
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("tool_seed_demo_journey", ROOT / "tools" / "seed_demo_journey.py")
J = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = J
_spec.loader.exec_module(J)

CO = "qd-office"
ACCOUNTS = {"Janet Shaw": "company_admin", "Daniel Kerr": "sponsor", "Katie Menon": "analyst", "Aaron Lyle": "participant",
            "Grace Ward": "approver", "Harvey Rowley": "owner"}
NO_ACCOUNT = ["Vivian Chua", "Ethan Ng", "Marcus Todd", "Priya Nair", "Samuel Ong", "Jun Wei Chia", "Nadia Hassan"]
LENS = {"mark": "stated", "by": "Lens", "from": "people.csv"}


def _company(root: Path) -> None:
    es = EntitlementStore(root)
    es.create_company(CO, "Illustrative QD Office", "family_office", modules=["m1_intent", "m2_baseline", "m3_connect"])
    es.set_centre(CO, "intent", True)
    accounts = AccountStore(root)
    for name, role in ACCOUNTS.items():
        accounts.create(f"{role}.{CO}@example.test", "not-a-real-password-0", name, CO, [role])
    plane = PlaneStore(root).plane_for(CO).ensure()
    for name in [*ACCOUNTS, *NO_ACCOUNT]:
        pid = name.lower().replace(" ", "-")
        profile_store.record(plane, f"people.{pid}.name", name, LENS)
        profile_store.record(plane, f"people.{pid}.is_head_of_data", name == "Marcus Todd", LENS)
        profile_store.record(plane, f"people.{pid}.is_sponsor", name == "Daniel Kerr", LENS)
    profile_store.record(plane, "governance.restricted_areas.pay-workbook.area", "pay workbook", LENS)
    profile_store.record(plane, "governance.restricted_areas.pay-workbook.may_see", ["Vivian Chua"], LENS)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("journey") / "data"
    _company(root)
    first = J.seed_journey(root, CO)
    return root, first


def _plane(root):
    return PlaneStore(root).plane_for(CO)


def test_the_journey_runs_clean_and_signs_the_charter_baseline_and_blueprint(seeded):
    root, r = seeded
    assert r["status"] == "seeded" and r["refused"] == [], r["refused"]
    plane = _plane(root)
    outcomes = [json.loads(f.read_text()) for f in plane.path("intents", "m1_intent", "outcomes").glob("*.json")]
    lines = [i for v in outcomes[0].values() if isinstance(v, list) for i in v if isinstance(i, dict) and i.get("so_that")]
    assert len(outcomes) == 1 and outcomes[0]["signed_at"] and len(lines) == 6, len(lines)
    base = json.loads(plane.path("intents", "m2_baseline", r["ids"]["baseline"], "baseline.json").read_text())
    kpis = json.loads(plane.path("intents", "m2_baseline", r["ids"]["baseline"], "kpis.json").read_text())
    assert base["state"] == "signed" and len(kpis) == 12 and sum(1 for k in kpis if k["governance"]["may_see"]) == 2
    blueprint = json.loads(plane.path("build", "blueprint.json").read_text())
    assert blueprint["state"] == "signed" and blueprint["signed_by"][0]["name"] == "Marcus Todd"


def _kinds(r, name):
    return {ln["kind"] for s in r["pulses"][name]["strips"] for ln in s["lines"]}


def test_the_participant_has_a_live_invite(seeded):
    assert "invite" in _kinds(seeded[1], "Aaron Lyle")


def test_the_sponsor_has_a_signature_line(seeded):
    assert "signature" in _kinds(seeded[1], "Daniel Kerr"), seeded[1]["pulses"]["Daniel Kerr"]


def test_the_prover_keeps_one_row_per_measure_and_the_two_unreported_measures_are_proved(seeded):
    root, _ = seeded
    ms = {m["code"]: m for m in json.loads(_plane(root).path("build", "prove.json").read_text())["measures"]}
    assert len(ms) == 12
    assert [p["result"] for p in ms["K02"]["periods"]] == ["match"] * 3 and ms["K02"]["uat"]["state"] == "signed"  # a two-source measure keeps its sign-off
    assert [p["result"] for p in ms["K06"]["periods"]] == ["match", "match", "not_yet"] and ms["K06"]["uat"]["state"] != "signed"


def test_a_second_run_changes_nothing_and_reset_seeds_the_same_journey_again(seeded):
    root, first = seeded
    plane = _plane(root)
    before = J._files(plane.root, plane.root / "nothing")
    assert J.seed_journey(root, CO)["status"] == "already"
    assert J._files(plane.root, plane.root / "nothing") == before
    again = J.seed_journey(root, CO, reset=True)
    assert again["status"] == "seeded" and again["done"] == first["done"] and again["refused"] == first["refused"]
    assert len(list(plane.path("intents", "m1_intent", "sessions").glob("*.json"))) == 2
