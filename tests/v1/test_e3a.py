"""E3a: unsigned versions are ignored by current; effective dating picks the version in force; the proposer cannot sign;
past versions stay; the routes check the owner and signer."""
import shutil
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.settings import Settings
from sh_platform.v1 import e3_rules as R
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
MEI = Viewer("Mei Tan", frozenset({"analyst"}), False, "acc-mei")
RAJ = Viewer("Raj Iyer", frozenset({"analyst"}), False, "acc-raj")
READER = Viewer("Priya Nair", frozenset({"participant"}), False, "acc-priya")
TOL = {"abs_amount": 5000, "currency": "USD"}


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    return PlaneStore(tmp_path / "data").create("acme")


def test_unsigned_is_ignored_and_signed_is_returned(plane):
    v = R.propose(plane, MEI, "cash_tolerance", "Cash may differ by 5,000 USD per entity per day.", TOL, "2026-01-01", "tolerance")
    assert v["state"] == "draft" and v["version_number"] == 1 and v["owner"] == "Mei Tan"
    assert R.current(plane, "cash_tolerance", date(2026, 10, 8)) is None
    R.approve(plane, RAJ, v["rule_version_id"])
    got = R.current(plane, "cash_tolerance", "2026-10-08")
    assert got == {"rule_version_id": v["rule_version_id"], "parameters": TOL, "definition_text": "Cash may differ by 5,000 USD per entity per day."}
    assert R.current(plane, "nope", "2026-10-08") is None


def test_effective_dating_and_past_versions_stay(plane):
    one = R.propose(plane, MEI, "cash_tolerance", "5,000 USD.", TOL, "2026-01-01", "tolerance")
    R.approve(plane, RAJ, one["rule_version_id"])
    two = R.propose(plane, MEI, "cash_tolerance", "10,000 USD.", {"abs_amount": 10000, "currency": "USD"}, "2026-11-01")
    assert two["version_number"] == 2
    R.approve(plane, RAJ, two["rule_version_id"])
    assert R.current(plane, "cash_tolerance", "2026-10-31")["rule_version_id"] == one["rule_version_id"]    # a past run keeps its version
    assert R.current(plane, "cash_tolerance", "2026-11-01")["parameters"]["abs_amount"] == 10000
    assert R.current(plane, "cash_tolerance", "2025-12-31") is None
    assert [v["state"] for v in R.history(plane, "cash_tolerance")] == ["approved", "approved"]
    line = R.listing(plane, MEI)[0]
    assert line["rule_code"] == "cash_tolerance" and line["waiting"] == 0


def test_proposer_cannot_sign_and_others_cannot_propose(plane):
    v = R.propose(plane, MEI, "cio_materiality", "Over 100,000 USD.", {"abs_amount": 100000}, "2026-01-01", "materiality")
    with pytest.raises(Refused) as e:
        R.approve(plane, MEI, v["rule_version_id"])
    assert e.value.status == 403
    with pytest.raises(Refused):
        R.approve(plane, READER, v["rule_version_id"])
    with pytest.raises(Refused):
        R.propose(plane, READER, "cio_materiality", "Over 1.", {}, "2026-01-01")     # a participant who is not the owner does not propose
    w = R.propose(plane, RAJ, "cio_materiality", "Over 2.", {}, "2026-01-01")        # the data team proposes for the owner (UC5)
    with pytest.raises(Refused) as e:
        R.approve(plane, RAJ, w["rule_version_id"])                                  # but never signs its own proposal
    assert e.value.status == 403
    with pytest.raises(Refused):
        R.propose(plane, MEI, "new_rule", "x", {}, "2026-01-01", "wibble")           # a new rule needs a kind
    with pytest.raises(Refused):
        R.propose(plane, MEI, "cio_materiality", " ", {}, "2026-01-01")
    R.approve(plane, RAJ, v["rule_version_id"])
    with pytest.raises(Refused) as e:
        R.approve(plane, RAJ, v["rule_version_id"])                                  # already signed
    assert e.value.status == 409


@pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
def test_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    shutil.copytree(ROOT / "data" / "neera", data / "neera")
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}

    def client(email):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c

    leela, arjun = client("leela.raman.neera@example.test"), client("arjun.mehta.neera@example.test")
    body = {"definition_text": "Cash may differ by 5,000 USD.", "parameters": TOL, "effective_from": "2026-01-01", "rule_type": "tolerance"}
    r = leela.post("/api/v1/rules/cash_tolerance", json=body)
    assert r.status_code == 200 and r.json()["state"] == "draft"
    vid = r.json()["rule_version_id"]
    assert leela.post(f"/api/v1/rules/versions/{vid}/approve").status_code == 403
    assert arjun.post(f"/api/v1/rules/versions/{vid}/approve").json()["state"] == "approved"
    assert arjun.get("/api/v1/rules").json()[0]["in_force"] is True
    assert len(leela.get("/api/v1/rules/cash_tolerance/history").json()) == 1
    v2 = arjun.post("/api/v1/rules/cash_tolerance", json=body)                               # UC5: the data team proposes for the owner
    assert v2.status_code == 200 and arjun.post(f"/api/v1/rules/versions/{v2.json()['rule_version_id']}/approve").status_code == 403  # never signs it


def test_owner_of_any_role_proposes(plane):
    """UC5: the rule's owner proposes even as a participant (a risk owner); neither the owner nor the proposer signs."""
    sofia = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-sofia")
    R.propose(plane, MEI, "limit_x", "At most 5%.", {"max_pct": 5}, "2026-01-01", "limit")
    with wh.connect(plane) as con:  # hand the rule to Sofia, as the seed does for the limit rules
        con.execute("update business_rules set owner_user_id = ? where rule_code = 'limit_x'", [R._uid(con, R._org(plane), sofia)])
    v = R.propose(plane, sofia, "limit_x", "At most 6%.", {"max_pct": 6}, "2026-01-01")
    with pytest.raises(Refused):
        R.approve(plane, sofia, v["rule_version_id"])
    assert R.approve(plane, RAJ, v["rule_version_id"])["state"] == "approved"


def test_a_signed_limits_workbook_becomes_proposed_versions_and_one_action_item(plane, tmp_path, monkeypatch):
    """UC5 G-3: the signed workbook is read, not retyped: a changed line is a proposed version (never signed by the import), an
    unchanged line is left alone, a second import proposes nothing new, and the signer gets one Action item naming the difference."""
    import openpyxl
    from sh_platform.v1 import e4_cases
    opened = []
    monkeypatch.setattr(e4_cases, "open", lambda plane, fields: opened.append(fields) or "case-1")
    p = {"dimension": "single_name", "bucket": "Harborview Semiconductor", "min_pct": 0.0, "max_pct": 5.0, "portfolio_code": "EG-LIQUID"}
    v = R.propose(plane, MEI, "limit_hvs", "At most 5%.", p, "2026-01-01", "limit")
    R.approve(plane, RAJ, v["rule_version_id"])
    q = {**p, "bucket": "listed_equity", "dimension": "asset_class", "min_pct": 60.0, "max_pct": 90.0}
    R.approve(plane, RAJ, R.propose(plane, MEI, "limit_le", "60 to 90.", q, "2026-01-01", "limit")["rule_version_id"])
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Signed limits"
    for row in (["Signed investment limits"], ["Version", "v1"], ["Signed by", "Daniel Foo"], ["Signed on", "2026-01-02"], ["Effective from", "2026-01-01"], [],
                ["Rule code", "Portfolio", "Dimension", "Item or bucket", "Minimum %", "Maximum %", "Owner", "Approved by", "Definition"],
                ["limit_hvs", "EG-LIQUID", "single_name", "Harborview Semiconductor", 0, 6, "Mei Tan", "Daniel Foo", "Harborview at most 6%."],
                ["limit_le", "EG-LIQUID", "asset_class", "listed_equity", 60, 90, "Mei Tan", "Daniel Foo", "Listed equity 60 to 90."]):
        ws.append(row)
    path = tmp_path / "limits.xlsx"; wb.save(path)
    out = R.import_signed(plane, RAJ, path, "Signed limits")
    assert out["unchanged"] == ["limit_le"] and [x["rule_code"] for x in out["proposed"]] == ["limit_hvs"]
    assert out["proposed"][0]["before"]["max_pct"] == 5.0 and out["proposed"][0]["after"]["max_pct"] == 6.0
    assert R.current(plane, "limit_hvs", "2026-07-31")["parameters"]["max_pct"] == 5.0          # nothing is signed by the import
    assert len(opened) == 1 and "limit_hvs" in opened[0]["description"]
    with pytest.raises(Refused):
        R.approve(plane, RAJ, out["proposed"][0]["rule_version_id"])                           # the importer does not sign it
    again = R.import_signed(plane, RAJ, path, "Signed limits")
    assert again["waiting"] == ["limit_hvs"] and not again["proposed"] and len(opened) == 1
