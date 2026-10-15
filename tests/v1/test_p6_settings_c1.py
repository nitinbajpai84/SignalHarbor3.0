"""Cycle 1, P6: the approver reads the rules register (never writes it), the register lists the benchmark versions (a4.4, P15),
Settings lists each instrument's other names and codes (a3.4, P13) and gives a class to one that has none (a5.8, P19), and the
agent runs table never shows a retired internal agent name (j-shell.5)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e2c_routes as R, e3_rules, e6_trace as T, wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused

U = lambda n: f"00000000-0000-0000-0000-{n:012d}"  # noqa: E731
KR, PRC, S1, S2 = U(11), U(12), U(1), U(2)
MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")
RAJ = Viewer("Raj Patel", frozenset({"approver"}), False, "acc-raj")
SOFIA = Viewer("Sofia Reyes", frozenset({"participant"}), False, "acc-sofia")


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(p)
    with wh.connect(p) as con:
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type) values (?, ?, 'manager_email', 'Manager statements by email', 'manager')", [S1, org])
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type) values (?, ?, 'administrator', 'Fund administrator', 'administrator')", [S2, org])
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, asset_class, created_at) values (?, ?, 'Kestrel Ridge Macro Fund', 'fund', 'hedge_fund', now())", [KR, org])
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, asset_class, created_at) values (?, ?, 'Pacific Rim Convertible 2029 note', 'convertible', null, now())", [PRC, org])
        for i, (src, typ, val, st) in enumerate([(S1, "manager_fund_name", "KR Macro Fund Ltd - Class B USD", "approved"), (S1, "manager_fund_name", "Kestrel Ridge Macro Fund", "approved"),
                                                 (S2, "administrator_code", "4481", "approved"), (S1, "manager_fund_name", "Kestrel Macro (guess)", "proposed"),
                                                 (S1, "manager_contact", "Priya Nair", "approved")]):
            con.execute("insert into instrument_identifiers values (?,?,?,?,?,?,null,null,?,null,null,null)", [U(50 + i), org, KR, src, typ, val, st])
        for n, status, eff in ((1, "approved", "2026-01-01"), (2, "in_progress", "2026-10-01")):
            con.execute("insert into benchmark_definitions (id, organization_id, benchmark_code, benchmark_name, version_number, reporting_currency, effective_from, calculation_method,"
                        " approval_status) values (?, ?, 'EG-OFFICE-BLEND', 'Evergreen office benchmark', ?, 'USD', ?, 'weighted', ?)", [U(70 + n), org, n, eff, status])
    return p


def test_approver_reads_the_register_but_cannot_propose_or_sign(plane):
    v = e3_rules.propose(plane, MEI, "cash_tolerance", "Cash may differ by 5,000 USD.", {"abs_amount": 5000}, "2026-01-01", "tolerance")
    e3_rules.need_role(RAJ)  # reads (the routes call this for the list and the history)
    assert [r["rule_code"] for r in e3_rules.listing(plane, RAJ)] == ["cash_tolerance", "EG-OFFICE-BLEND"]
    for act in (lambda: e3_rules.approve(plane, RAJ, v["rule_version_id"]), lambda: e3_rules.propose(plane, RAJ, "x", "y", {}, "2026-01-01", "policy")):
        with pytest.raises(Refused) as e:
            act()
        assert e.value.status == 403
    with pytest.raises(Refused):
        e3_rules.need_role(SOFIA)


def test_register_lists_the_benchmark_and_its_version_in_progress(plane):
    line = next(r for r in e3_rules.listing(plane, MEI) if r["rule_type"] == "benchmark")
    assert "version 1 (2026-01-01) approved" in line["definition_text"]
    assert "version 2 (2026-10-01) still in progress" in line["definition_text"]
    assert line["state"] == "draft" and line["waiting"] == 1 and line["rule_code"] == "EG-OFFICE-BLEND"


def client(plane, monkeypatch, viewer):
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: plane)
    monkeypatch.setattr(R, "viewer_of", lambda req: viewer)
    return TestClient(app)


def test_identifiers_list_other_names_and_the_administrator_code(plane, monkeypatch):
    got = client(plane, monkeypatch, MEI).get("/api/v1/instruments").json()
    kr = next(i for i in got["instruments"] if i["instrument_id"] == KR)
    assert [n["value"] for n in kr["names"]] == ["KR Macro Fund Ltd - Class B USD"]  # its own name and a mere proposal are not repeated
    assert kr["codes"] == [{"value": "4481", "kind": "administrator code", "source": "Fund administrator"}]
    assert got["asset_classes"] == ["hedge_fund"]


def test_an_instrument_without_a_class_gets_one_once(plane, monkeypatch):
    c = client(plane, monkeypatch, MEI)
    assert c.post(f"/api/v1/instruments/{PRC}/asset-class", json={"asset_class": "made_up"}).status_code == 400
    r = c.post(f"/api/v1/instruments/{PRC}/asset-class", json={"asset_class": "hedge_fund"})
    assert r.status_code == 200 and r.json()["asset_class"] == "hedge_fund"
    assert c.post(f"/api/v1/instruments/{PRC}/asset-class", json={"asset_class": "hedge_fund"}).status_code == 409
    assert c.post(f"/api/v1/instruments/{U(999)}/asset-class", json={"asset_class": "hedge_fund"}).status_code == 404
    assert client(plane, monkeypatch, SOFIA).post(f"/api/v1/instruments/{KR}/asset-class", json={"asset_class": "hedge_fund"}).status_code == 403


def test_runs_table_shows_the_agent_not_its_retired_internal_name(plane):
    for name in ("investigation", "tally", "intake"):
        with T.agent_run(plane, MEI, name, "m", "p", "t"):
            pass
    s = T.summary(plane)
    assert sorted((g["agent_type"], g["runs"]) for g in s["by_agent_day"]) == [("span", 1), ("tally", 2)]
    assert "investigation" not in {r["agent_type"] for r in s["runs"]}
    assert len(T.summary(plane, agent_type="tally")["runs"]) == 2


def test_new_routes_are_declared():
    from sh_platform.v1 import extra_permission_files
    text = "".join(p.read_text(encoding="utf-8") for p in extra_permission_files())
    for route in ("GET /api/v1/instruments:", "POST /api/v1/instruments/{instrument_id}/asset-class:"):
        assert route in text
    assert "GET /api/v1/rules: {roles: [company_admin, sponsor, analyst, approver]}" in text
