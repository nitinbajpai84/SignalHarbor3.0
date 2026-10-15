"""Module 1 test kit: the real app over temporary folders, two industries, an empty company and a solo user.

Industries are arbitrary ids with tiny packs written into a temporary packs folder. No real industry wording.
"""
from pathlib import Path

import itertools
import yaml
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"
ORGANISER_ROLES = ("company_admin", "sponsor", "analyst")


def write_pack(root: Path, industry: str, problems: int) -> None:
    folder = root / industry / "1"
    folder.mkdir(parents=True)
    (folder / "pack.yaml").write_text(yaml.safe_dump({"industry": industry, "version": 1, "label": industry}))
    rows = [{"id": f"P-{i}", "question": f"{industry} question {i}",
             "typical_actions": {"label": "suggestion", "items": [f"{industry} action {i}"]}}
            for i in range(problems)]
    (folder / "problems.yaml").write_text(yaml.safe_dump({"problems": rows}))


class World:
    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.packs = tmp_path / "packs"
        write_pack(self.packs, "industry_a", 3)
        write_pack(self.packs, "industry_b", 2)  # "none" and "unlisted" have no pack on purpose
        self.settings = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret=SECRET)
        self.app = create_app(self.settings, packs_root=self.packs)
        self.app.state.speech_env = {}  # the real .env holds keys: no test may read it (a test sets its own)
        self.app.state.model_env = {}
        self.store = self.app.state.entitlements
        self.accounts = self.app.state.account_store
        for cid, industry, modules in [
            ("co-a", "industry_a", ["m1_intent"]), ("co-b", "industry_b", ["m1_intent"]),
            ("co-none", "none", ["m1_intent"]),            # an industry with no pack
            ("co-empty", "industry_a", ["m1_intent"]),     # never ran a session
            ("co-off", "industry_a", ["m2_baseline"]),     # module 1 not owned
            ("co-solo", "industry_b", ["m1_intent"]),      # one person
        ]:
            self.store.create_company(cid, cid.title(), industry, modules=modules)

    def plane(self, company_id: str):
        return PlaneStore(self.settings.data_root).plane_for(company_id)

    def login(self, name: str, company: str, roles=("company_admin",)) -> TestClient:
        acct, pw = make_test_account(self.accounts, name, company, list(roles))
        c = TestClient(self.app)
        r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
        assert r.status_code == 200, r.text
        c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
        c.account_id = acct["account_id"]  # type: ignore[attr-defined]
        return c


BASE = "/api/modules/m1_intent"


_topics = itertools.count(1)


def draft(**over) -> dict:
    # IC-2t: one open wall per topic, so each test draft gets its own topic unless the test chooses
    body = {"purpose": "Agree what we want to know about renewals", "outcome": "A signed charter", "topic": f"Topic {next(_topics)}"}
    body.update(over)
    return body
