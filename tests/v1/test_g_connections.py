"""G card: Build > Connections (/api/v3/connectors) and Build > Onboarding (/api/v3/onboarding). Synthetic data only."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_connections as C  # noqa: E402
from sh_platform.v1.connectors import base  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"


class Fake:
    id, label, kind = "fake-bank", "Fake bank sandbox", "api"
    env = ("FAKE_BANK_KEY_ID",)

    def __init__(self, boom=False):
        self.boom = boom

    def fetch(self, since):
        if self.boom:
            raise RuntimeError("bank said no")
        return [base.Fetched("fake_2026-09-30.csv", b"a,b\n1,2\n", "fake bank")]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.delenv("FAKE_BANK_KEY_ID", raising=False)
    monkeypatch.setattr(C, "MODULES", ())  # only the fake registers
    monkeypatch.setattr(base, "REGISTRY", {})
    base.register(Fake())
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    st = AccountStore(data)
    st.create("sam@evergreen.example.test", PW, "Sam Lee", "evergreen", ["participant"])
    plane = PlaneStore(str(data)).plane_for("evergreen").ensure()
    return create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")), plane


def login(app, email) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def email(name):
    return EG.email_of(name)


def test_missing_settings_are_named_not_valued(env):
    _, plane = env
    row = C.listing(plane)[0]
    assert row["state"] == "needs_settings" and row["missing"] == ["FAKE_BANK_KEY_ID"] and row["last_run"] is None
    out = C.run(plane, "fake-bank")
    assert out["state"] == "needs_settings" and out["files"] == 0 and out["last_run"]
    assert not list(plane.path("dropbox").glob("*"))  # nothing fetched, nothing dropped


def test_run_drops_files_and_remembers(env, monkeypatch):
    _, plane = env
    monkeypatch.setenv("FAKE_BANK_KEY_ID", "x")
    out = C.run(plane, "fake-bank")
    assert out["state"] == "connected" and out["files"] == 1 and out["errors"] == []
    assert plane.path("dropbox", "fake_2026-09-30.csv").is_file()
    assert C.listing(plane)[0]["files"] == 1  # survives a fresh listing
    with pytest.raises(KeyError):
        C.run(plane, "nope")


def test_a_failing_connector_is_a_message_not_a_crash(env, monkeypatch):
    _, plane = env
    monkeypatch.setenv("FAKE_BANK_KEY_ID", "x")
    base.register(Fake(boom=True))
    out = C.run(plane, "fake-bank")
    assert out["state"] == "error" and "bank said no" in out["errors"][0]


def test_onboarding_is_computed_and_manual_steps_are_ticked_by_a_person(env, monkeypatch):
    _, plane = env
    ob = C.onboarding(plane)
    assert [s["id"] for s in ob["steps"]][:2] == ["discovery", "letters"] and len(ob["steps"]) == 10
    assert 0 <= ob["score"] <= 100 and sum(p["weight"] for p in ob["parts"]) == 100
    before = ob["score"]
    plane.path("dropbox").mkdir(parents=True, exist_ok=True)
    for m in range(1, 7):
        plane.path("dropbox", f"statement_2026-{m:02d}-28.csv").write_text("x", encoding="utf-8")
    monkeypatch.setenv("FAKE_BANK_KEY_ID", "x")
    C.run(plane, "fake-bank")
    ob = C.onboarding(plane)
    by = {s["id"]: s for s in ob["steps"]}
    assert by["history"]["status"] == "done" and ob["score"] > before
    assert by["ownership"]["status"] == "waiting"
    with pytest.raises(ValueError):
        C.tick(plane, "history", "Grace Ong")  # Harbor's step: nobody ticks it
    ob = C.tick(plane, "training", "Grace Ong", note="Two sessions held")
    t = {s["id"]: s for s in ob["steps"]}["training"]
    assert t["status"] == "done" and t["ticked_by"] == "Grace Ong" and t["ticked_at"] and t["detail"] == "Two sessions held"
    assert {s["id"]: s for s in C.tick(plane, "training", "Grace Ong", done=False)["steps"]}["training"]["status"] == "waiting"


def test_routes_and_permissions(env, monkeypatch):
    app, plane = env
    monkeypatch.setenv("FAKE_BANK_KEY_ID", "x")
    store = AccountStore(Path(app.state.settings.data_root))
    for who in ("Grace Ong", "Anita Rao", "Leo Park"):
        store.set_password(email(who), PW)
    sam, grace, anita, leo = (login(app, e) for e in ("sam@evergreen.example.test", email("Grace Ong"), email("Anita Rao"), email("Leo Park")))
    assert sam.get("/api/v3/connectors").json()["connectors"][0]["id"] == "fake-bank"  # everyone views
    assert sam.get("/api/v3/onboarding").status_code == 200
    assert sam.post("/api/v3/connectors/fake-bank/run").status_code == 403  # default deny
    assert leo.post("/api/v3/connectors/fake-bank/run").status_code == 403  # the data team views; the head of data runs
    assert sam.post("/api/v3/onboarding/training/tick", json={}).status_code == 403
    r = grace.post("/api/v3/connectors/fake-bank/run", json={"since": "2026-09-01"})
    assert r.status_code == 200 and r.json()["files"] == 1
    assert anita.post("/api/v3/connectors/fake-bank/run").status_code == 200
    assert grace.post("/api/v3/connectors/nope/run").status_code == 404
    assert grace.post("/api/v3/connectors/fake-bank/run", json={"since": "yesterday"}).status_code == 400
    t = grace.post("/api/v3/onboarding/golive/tick", json={"note": "Live on Monday"})
    assert t.status_code == 200 and {s["id"]: s for s in t.json()["steps"]}["golive"]["ticked_by"] == "Grace Ong"
    assert grace.post("/api/v3/onboarding/history/tick", json={}).status_code == 400
    assert grace.post("/api/v3/onboarding/zzz/tick", json={}).status_code == 404
    assert grace.get("/api/v3/connections").status_code == 200  # the Trust page's route is untouched
