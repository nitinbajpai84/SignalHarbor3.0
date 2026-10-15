"""E0e: the Evergreen seed on a tmp data root. Counts, the issued report, the 12,400 break, idempotence, reset, no password printed."""
import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import wh
from tools import seed_evergreen as S


@pytest.fixture()
def root(tmp_path):
    wh.reset_cache()
    yield tmp_path / "data"
    wh.reset_cache()


def q(root, sql, *args):
    con = duckdb.connect(str(wh.path(PlaneStore(root).plane_for("evergreen"))), read_only=True)
    try:
        return con.execute(sql, list(args)).fetchall()
    finally:
        con.close()


def test_seed_builds_the_story(root, capsys):
    r = S.seed(root)
    assert r["warehouse"] == "built" and r["accounts_created"] == 7
    out = capsys.readouterr().out
    creds = (root / "_control" / "seed_credentials.txt").read_text(encoding="utf-8")
    for line in creds.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        assert line.split()[1] not in out  # passwords are never printed
    assert q(root, "select count(*) from legal_entities")[0][0] == 3
    assert q(root, "select count(*) from users")[0][0] == 7
    assert q(root, "select count(*) from instruments")[0][0] == 4
    assert {"EG Growth Fund I", "4471"} <= {x[0] for x in q(root, "select identifier_value from instrument_identifiers where mapping_status = 'approved'")}
    rules = dict(q(root, "select r.rule_code, v.parameters from business_rules r join rule_versions v on v.business_rule_id = r.id "
                         "where v.approval_status = 'approved' and v.approved_by <> r.owner_user_id"))
    assert set(rules) == {"cash_tolerance", "cio_materiality", "estimate_use", "statement_due", "fx_fixing"}
    assert '"abs_amount": 5000' in rules["cash_tolerance"]
    import json
    assert json.loads(rules["fx_fixing"])["fixing"] == "WMR_4PM" and json.loads(rules["estimate_use"])["allowed_in"] == ["investment_report"]
    assert json.loads(rules["statement_due"]) == {"business_days_after_month_end": 10}
    assert {x[0] for x in q(root, "select series_key from market_observations")} == {"FX:USDSGD:WMR_4PM"}
    assert q(root, "select count(*) from users where external_identity_id is null")[0][0] == 0


def test_fund_a_estimate_and_issued_report(root):
    S.seed(root)
    a = q(root, "select value_amount, valuation_date, received_at, approval_status from valuation_observations v "
                "join instruments i on i.id = v.instrument_id where i.canonical_name = 'Evergreen Growth I'")
    assert len(a) == 1 and a[0][0] == 10_000_000 and str(a[0][1]) == "2026-09-30" and a[0][2].day == 2 and a[0][3] == "estimated"
    assert not q(root, "select 1 from valuation_observations where value_amount = 10180000")  # the amended statement is not loaded
    lines = q(root, "select numeric_value, currency from metric_values order by numeric_value")
    assert [float(x[0]) for x in lines] == [6_400_000, 10_000_000, 41_200_000, 57_600_000]
    ver = q(root, "select status, cutoff_at, issued_at from report_versions")
    assert len(ver) == 1 and ver[0][0] == "issued" and ver[0][1].day == 3 and ver[0][2].day == 3 and ver[0][2].month == 10
    # everything the report used was recorded on or before its cutoff
    assert q(root, "select count(*) from valuation_observations v join report_versions r on true where v.recorded_at > r.cutoff_at")[0][0] == 0
    assert q(root, "select count(*) from metric_evidence")[0][0] == 3


def test_entity_b_cash_differs_by_12400(root):
    S.seed(root)
    rows = q(root, "select e.entity_code, p.view_type, sum(p.source_market_value) from position_snapshots p "
                   "join portfolios f on f.id = p.portfolio_id join legal_entities e on e.id = f.legal_entity_id "
                   "join instruments i on i.id = p.instrument_id where i.instrument_type = 'cash' group by 1, 2")
    cash = {(c, v): float(t) for c, v, t in rows}
    assert cash[("EG-B", "accounting")] - cash[("EG-B", "operational")] == 12_400
    assert cash[("EG-HOLD", "accounting")] == cash[("EG-HOLD", "operational")]
    assert 0 < cash[("EG-TRUST", "accounting")] - cash[("EG-TRUST", "operational")] < 5_000


def test_idempotent_and_reset(root):
    S.seed(root)
    before = q(root, "select (select count(*) from users), (select count(*) from source_records), (select count(*) from report_versions)")
    r = S.seed(root)
    assert r["warehouse"] == "kept" and r["accounts_created"] == 0
    assert q(root, "select (select count(*) from users), (select count(*) from source_records), (select count(*) from report_versions)") == before
    r = S.seed(root, reset=True)
    assert r["warehouse"] == "built" and r["accounts_created"] == 0
    assert q(root, "select count(*) from report_versions")[0][0] == 1


def test_report_fallback_without_e1c(root, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "sh_platform.v1.e1_reports", None)  # import fails: SQL fallback
    S.seed(root)
    assert [float(x[0]) for x in q(root, "select numeric_value from metric_values order by numeric_value")] == [6_400_000, 10_000_000, 41_200_000, 57_600_000]
    assert q(root, "select count(*) from metric_evidence where note like 'valuation_observations:%'")[0][0] == 2


def test_statement_fund_names_resolve_as_approved(root):
    from sh_platform.plane import PlaneStore
    from sh_platform.v1 import e2_match
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen")
    sysid = q(root, "select id from source_systems where source_code = 'manager_email'")[0][0]
    for name in ("Fund A - Evergreen Growth I", "Evergreen Growth I", "EG Growth Fund I", "Fund B - Evergreen Liquid Book", "Fund B - Evergreen Income II"):
        assert e2_match.resolve(plane, name, str(sysid))["status"] == "approved", name
