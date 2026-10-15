"""Module 2 test kit: the real app over temporary folders. Two industries with tiny packs (a KPI tree each), an
industry with no pack, a company without module 2, and one person alone. No real industry wording."""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"
BASE = "/api/modules/m2_baseline"


def write_pack(root: Path, industry: str, kpis: int) -> None:
    folder = root / industry / "1"
    folder.mkdir(parents=True)
    (folder / "pack.yaml").write_text(yaml.safe_dump({"industry": industry, "version": 1, "label": industry}))
    (folder / "kpi_tree.yaml").write_text(yaml.safe_dump({"kpis": [
        {"id": f"K{i}", "name": f"{industry} measure {i}", "definition": f"{industry} definition {i}"} for i in range(kpis)]}))


class World:
    def __init__(self, tmp_path: Path):
        self.packs = tmp_path / "packs"
        write_pack(self.packs, "industry_a", 3)
        write_pack(self.packs, "industry_b", 2)
        self.settings = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret=SECRET)
        self.app = create_app(self.settings, packs_root=self.packs)
        self.app.state.speech_env = {}
        self.app.state.model_env = {}  # the real .env holds keys: no test may reach a live model
        self.accounts = self.app.state.account_store
        for cid, industry, modules in [
            ("co-a", "industry_a", ["m1_intent", "m2_baseline"]), ("co-b", "industry_b", ["m1_intent", "m2_baseline"]),
            ("co-none", "none", ["m1_intent", "m2_baseline"]),   # an industry with no pack
            ("co-off", "industry_a", ["m1_intent"]),              # module 2 not owned
            ("co-solo", "industry_b", ["m2_baseline"]),           # one person, no module 1
        ]:
            self.app.state.entitlements.create_company(cid, cid.title(), industry, modules=modules)

    def plane(self, company_id: str):
        return PlaneStore(self.settings.data_root).plane_for(company_id).ensure()


def login(world: World, company: str, name: str = "Pat Owner", roles=("company_admin",)) -> TestClient:
    acct, pw = make_test_account(world.accounts, name, company, list(roles))
    c = TestClient(world.app)
    r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
    assert r.status_code == 200, r.text
    c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
    return c


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)
