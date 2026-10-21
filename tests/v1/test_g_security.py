"""W7 product security controls: TOTP, MFA enforcement at sign-in, the hash-chained audit log, encrypted backup and restore."""
import json
import os
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.auth import install_auth, mfa as MFA
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import v3_audit as A, v3_audit_routes
from tools import backup as B, restore_test as R

PW = "correct horse battery"  # synthetic


@pytest.fixture
def env(tmp_path):
    s = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret="fake-test-secret-not-real")
    app = FastAPI()
    install_auth(app, s)
    app.include_router(v3_audit_routes.router)
    plane = PlaneStore(s.data_root).create("co-a")
    app.state.account_store.create("admin@test.invalid", PW, "Ada Admin", "co-a", ["company_admin"])
    return app, plane


def login(app, otp=None):
    c = TestClient(app)
    body = {"email": "admin@test.invalid", "password": PW, **({"otp": otp} if otp else {})}
    return c, c.post("/api/auth/login", json=body)


def enrol(app):
    c = TestClient(app)
    cred = {"email": "admin@test.invalid", "password": PW}
    secret = c.post("/api/auth/mfa/start", json=cred).json()["secret"]
    r = c.post("/api/auth/mfa/confirm", json={**cred, "otp": MFA.totp(secret)})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"]


# ---- TOTP
def test_totp_rfc6238_vectors():
    key = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert MFA.totp(key, at=59) == "287082"  # RFC 6238 appendix B, 94287082 cut to 6 digits
    assert MFA.totp(key, at=1111111109) == "081804"
    assert MFA.check_totp(key, "287082", at=59) is not None
    assert MFA.check_totp(key, "287082", at=59 + 120) is None  # outside one step of drift
    assert MFA.check_totp(key, "287082", after_counter=1, at=59) is None  # a code is good once


# ---- enforcement
def test_demo_sign_in_unchanged_when_mfa_is_off(env):
    app, _ = env
    _, r = login(app)
    assert r.status_code == 200


def test_enrolled_account_needs_the_code_and_each_code_works_once(env):
    app, _ = env
    secret, _codes = enrol(app)
    assert login(app)[1].json()["error"] == "mfa_required"
    assert login(app, "000000")[1].json()["error"] == "mfa_failed"
    code = MFA.totp(secret, at=time.time() + 30)  # the next step: not the one enrolment spent
    assert login(app, code)[1].status_code == 200
    assert login(app, code)[1].status_code == 401  # replay refused


def test_recovery_codes_are_hashed_and_single_use(env):
    app, _ = env
    _, codes = enrol(app)
    stored = json.dumps(app.state.account_store.get_by_email("admin@test.invalid")["mfa"])
    assert not any(c in stored for c in codes)
    assert login(app, codes[0])[1].status_code == 200
    assert login(app, codes[0])[1].status_code == 401
    assert login(app, codes[1])[1].status_code == 200


def test_office_requirement_blocks_sign_in_until_enrolled(env):
    app, plane = env
    c, r = login(app)
    h = {"X-CSRF-Token": c.cookies["sh_csrf"]}
    assert c.put("/api/v3/security/settings", json={"mfa_required": True}, headers=h).json()["mfa_required"] is True
    assert login(app)[1].json()["error"] == "mfa_setup_required"
    enrol(app)
    assert login(app)[1].json()["error"] == "mfa_required"


# ---- audit
def test_audit_records_and_chain_detects_tampering(env):
    app, plane = env
    TestClient(app).post("/api/auth/login", json={"email": "admin@test.invalid", "password": "wrong"})
    c, _ = login(app)
    h = {"X-CSRF-Token": c.cookies["sh_csrf"]}
    c.get("/api/v3/security/settings")
    c.put("/api/v3/security/settings", json={"mfa_required": False}, headers=h)
    c.post("/api/auth/logout", headers=h)
    f = plane.path("ops", "audit.jsonl")
    acts = [r["action"] for r in A.read(f)]
    assert acts == ["login_failed", "login", "read", "settings_change", "logout"]
    assert A.verify(f)["ok"]

    lines = f.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[2])
    rec["detail"] = "edited"
    f.write_text("\n".join([*lines[:2], json.dumps(rec), *lines[3:]]) + "\n", encoding="utf-8")
    assert A.verify(f) == {**A.verify(f), "ok": False, "broken_at": 3}
    f.write_text("\n".join([*lines[:2], *lines[3:]]) + "\n", encoding="utf-8")  # a line removed
    assert A.verify(f)["ok"] is False


def test_audit_page_api_filters_and_exports_csv(env):
    app, plane = env
    c, _ = login(app)
    c.get("/api/v3/security/settings")
    got = c.get("/api/v3/audit?action=read").json()
    assert got["chain"]["ok"] and [e["action"] for e in got["entries"]] == ["read"]
    csv = c.get("/api/v3/audit/export.csv")
    assert csv.headers["content-type"].startswith("text/csv") and "# chain head" in csv.text and "login" in csv.text


def test_csv_cells_cannot_run_as_formulas():
    assert A._safe("=1+1").startswith("'") and A._safe("ok") == "ok"


def test_classify():
    assert A.classify("GET", "/api/v3/x") == "read"
    assert A.classify("GET", "/api/v1/tickets/t1/log.csv") == "export"
    assert A.classify("POST", "/api/company/build/release/sign") == "signed_decision"
    assert A.classify("PUT", "/api/company/settings/egress") == "settings_change"
    assert A.classify("GET", "/api/auth/me") is None


# ---- backup and restore
def make_plane(tmp_path):
    root = tmp_path / "plane"
    (root / "v3" / "figures").mkdir(parents=True)
    (root / "v3" / "figures" / "fig-nav.json").write_text(json.dumps({"versions": [{"v": 1, "value": 1234.5}]}))
    (root / "landing").mkdir()
    (root / "landing" / "a.csv").write_text("x,y\n1,2\n")
    return root


def test_backup_restores_and_figures_match(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_TEST_BACKUP_KEY", "synthetic-passphrase-1")
    out = B.make_backup(make_plane(tmp_path), tmp_path / "bk", B.passphrase_from("SH_TEST_BACKUP_KEY"), "co-a")
    assert out.name.startswith("co-a-") and b"fig-nav" not in out.read_bytes()  # encrypted: nothing readable inside
    assert R.main([str(out), "--key-env", "SH_TEST_BACKUP_KEY"]) == 0


def test_restore_refuses_wrong_key_and_damaged_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_TEST_BACKUP_KEY", "synthetic-passphrase-1")
    out = B.make_backup(make_plane(tmp_path), tmp_path / "bk", "synthetic-passphrase-1", "co-a")
    monkeypatch.setenv("SH_TEST_BACKUP_KEY", "a-different-passphrase")
    assert R.main([str(out), "--key-env", "SH_TEST_BACKUP_KEY"]) == 1
    monkeypatch.setenv("SH_TEST_BACKUP_KEY", "synthetic-passphrase-1")
    raw = bytearray(out.read_bytes())
    raw[-40] ^= 1
    out.write_bytes(bytes(raw))
    assert R.main([str(out), "--key-env", "SH_TEST_BACKUP_KEY"]) == 1


def test_restore_check_names_a_changed_figure(tmp_path):
    root = make_plane(tmp_path)
    man = B.manifest_of(root)
    (root / "v3" / "figures" / "fig-nav.json").write_text(json.dumps({"versions": [{"v": 1, "value": 9}]}))
    (tmp_path / "d").mkdir()
    import shutil
    shutil.copytree(root, tmp_path / "d" / "plane")
    assert any("fig-nav" in p for p in R.check(tmp_path / "d", man))
