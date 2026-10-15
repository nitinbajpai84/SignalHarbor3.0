"""Module 3 test kit: module 2's world (two industries, an industry with no pack) with module 3 switched on for these companies, and a
SIGNED module 2 baseline built through module 2's own sign-off kit (test code only; the module itself reads the plane by path).
No real industry wording; every person is a throwaway test account."""
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "m2_baseline" / "tests"))  # test kit of module 2, reused as it is

from m2_kit import World, login  # noqa: E402
from test_m2_signoff_kit import BID, Team, confirm_all, seed, sign_both  # noqa: E402

BASE = "/api/modules/m3_connect"
CHARTER = "c" * 32
ALL = ["m1_intent", "m2_baseline", "m3_connect"]
COMPANIES = [("m3-a", "industry_a", ALL), ("m3-b", "industry_b", ALL), ("m3-empty", "none", ALL),  # empty: nothing signed
             ("m3-off", "industry_a", ["m1_intent", "m2_baseline"]),                                # module 3 not owned
             ("m3-solo", "industry_b", ["m2_baseline", "m3_connect"])]                              # one person, no module 1


class World3(World):
    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        for cid, industry, modules in COMPANIES:
            self.app.state.entitlements.create_company(cid, cid.title(), industry, modules=modules)


@pytest.fixture
def world(tmp_path):
    return World3(tmp_path)


def write_charter(world, company: str) -> None:
    folder = world.plane(company).path("intents", "m1_intent", "outcomes")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{CHARTER}.json").write_text(json.dumps({
        "outcome_id": CHARTER, "kind": "charter", "problems": [{"id": "c1", "title": "Slow reporting", "priority": "Must"}],
        "pain_points": [{"id": "p1", "title": "Late packs", "priority": "Should"}],
        "future_signals": [{"id": "f1", "title": "Earlier warning"}], "levers": [{"id": "l1", "title": "Faster feeds"}]}))


def signed_baseline(world, company: str = "m3-a") -> Team:
    """Writes a charter and a baseline, confirms every part and signs it through module 2's routes. Returns module 2's team."""
    write_charter(world, company)
    seed(world, company)
    team = Team(world, company)
    assert team.c["hana"].post(team.url("/catalogue/refresh")).status_code == 200  # fills the catalogue's measure rows, as a real baseline has
    confirm_all(team)
    a, b = sign_both(team)
    assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
    return team


def restrict(world, company: str, kpi_id: str, may_see: list[str]) -> None:
    """After signing: module 2's stored governance says this measure is personal and only these people may see it."""
    path = world.plane(company).path("intents", "m2_baseline", BID, "kpis.json")
    rows = json.loads(path.read_text())
    for k in rows:
        if k["id"] == kpi_id:
            k["governance"] = {"personal": "yes", "sensitive": False, "may_see": may_see}
    path.write_text(json.dumps(rows))


def person(world, company: str, name: str, roles=("analyst",)):
    return login(world, company, name, roles)


def copy_baseline(world, src: str, dst: str, with_charter: bool = True) -> None:
    """The same signed baseline in another company's own plane (module 2's test accounts are one set, so a second baseline is copied, not re-signed)."""
    shutil.copytree(world.plane(src).path("intents", "m2_baseline"), world.plane(dst).path("intents", "m2_baseline"))
    if with_charter:
        write_charter(world, dst)
