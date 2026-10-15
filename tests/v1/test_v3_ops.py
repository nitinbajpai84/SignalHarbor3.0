"""Harbor 3.0 ops routes (people, runs, connections, setup) on the seeded Evergreen company and on an empty one."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import run_log, v3_harbor as H  # noqa: E402
from sh_platform.v1.c5_connect import spec as S  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"


def login(app, email, pw) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    es = EntitlementStore(data)
    es.create_company("blank", "Blank Office", "unset", modules=es.catalogue.ids)
    AccountStore(data).create("admin@blank.example.test", PW, "Bea Blank", "blank", ["company_admin"])
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    anita = "anita.rao.evergreen@example.test"
    return app, data, login(app, anita, pw[anita]), login(app, "admin@blank.example.test", PW)


def seed(data):
    plane = PlaneStore(data).plane_for("evergreen")
    rid = run_log.record(plane, "pipeline", "production", "manual", "Anita Rao",
                         [{"name": "gold", "layer": "gold", "target": "gold", "checks_passed": 3, "checks_failed": 1, "file_id": "f1"}], "ok")
    H.save(plane, {"id": "t1", "title": "Capital calls", "stage": "live", "created": "2026-10-01T00:00:00Z", "events": [], "steps": [{"n": 1, "run_id": rid}]})
    S.save(plane, "bank-mail", {"kind": "imap", "host": "mail.example.com", "schedule": "daily", "source_code": "bank",
                                "credentials": {"user": "CONN_BANK_USER", "password": "CONN_BANK_PASS"}})
    return plane, rid


def test_seeded_company(env):
    app, data, c, _ = env
    plane, rid = seed(data)
    p = c.get("/api/v3/people").json()
    assert {x["name"]: x["role"] for x in p["people"]}["Anita Rao"] == "decides"
    assert {x["name"]: x["role"] for x in p["people"]}["Leo Park"] == "does"
    assert p["autonomy"] == [{"thread": "t1", "level": "assist"}]
    assert [r["id"] for r in p["ask_rules"]][2] == "tolerance" and p["ask_rules"][2]["value"] == 5000
    assert p["usage"] == {"questions": 0, "builds": 1, "mode": "testing"}
    assert c.post("/api/v3/people/autonomy", json={"thread": "t1", "level": "auto"}).json()["autonomy"][0]["level"] == "auto"
    assert c.post("/api/v3/people/autonomy", json={"thread": "t1", "level": "loud"}).status_code == 400
    assert c.post("/api/v3/people/autonomy", json={"thread": "nope", "level": "auto"}).status_code == 404

    r = c.get("/api/v3/runs").json()["runs"]
    assert r == [{"run_id": rid, "thread": "t1", "kind": "live", "started": r[0]["started"], "files": 1, "checks_passed": 3,
                  "checks_total": 4, "result": "ok", "signed_by": "Anita Rao"}]

    conns = c.get("/api/v3/connections").json()["connections"]
    assert [x["kind"] for x in conns] == ["folder", "mailbox", "database", "api"]
    assert [x["state"] for x in conns] == ["ok", "ok", "coming", "coming"]
    assert "CONN_" not in str(conns) and conns[1]["target"] == "mail.example.com/INBOX"

    s = c.get("/api/v3/setup").json()
    assert [x["id"] for x in s["steps"] if x["done"]] == ["pack", "connection", "people", "thread", "live"]
    assert s["pack"]["id"] == "family_office"
    assert c.post("/api/v3/setup", json={"pack": "insurance"}).status_code == 409


def test_empty_company(env):
    app, data, _, c = env
    p = c.get("/api/v3/people").json()
    assert p["people"] == [{"name": "Bea Blank", "role": "does"}] and p["autonomy"] == [] and p["usage"]["builds"] == 0
    assert c.get("/api/v3/runs").json() == {"runs": []}
    conns = c.get("/api/v3/connections").json()["connections"]
    assert [x["kind"] for x in conns] == ["folder", "database", "api"] and conns[0]["last_pull"] is None
    s = c.get("/api/v3/setup").json()
    assert s["pack"] is None and [x["id"] for x in s["steps"] if x["done"]] == ["people"]
    assert c.post("/api/v3/setup", json={"pack": "nonsense"}).status_code == 400
    ok = c.post("/api/v3/setup", json={"pack": "insurance"}).json()
    assert ok["pack"]["id"] == "insurance" and ok["steps"][0]["done"]
    assert c.post("/api/v3/setup", json={"pack": "family_office"}).status_code == 409
    assert EntitlementStore(data).company("blank")["industry"] == "insurance"
