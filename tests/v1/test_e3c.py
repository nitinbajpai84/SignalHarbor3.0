"""E3c: the Fund A revision opens one exception with impact 180,000 on the September report; a valuation no report used opens none.
Sibling cards (E1c, E3a, E3d, E4a) are stubbed."""
import sys
import uuid
import types
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_write as W, e3_impact, wh
from tests.v1.e1_seed import seed

OPENED: list[dict] = []
I = {k: str(uuid.uuid5(uuid.NAMESPACE_DNS, k)) for k in ('old', 'new', 'other', 'other2', 'fundA', 'fundB', 'rv1', 'run1', 'mv1', 'r', 'rule1', 'pend', 'conf', 'pf', 'ev')}
UTC = timezone.utc


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("evergreen")  # a slug company, as in the demo
    OPENED.clear()
    used = {I['old']: [I['rv1']]}

    def stub(name, **fns):
        m = types.ModuleType(f"sh_platform.v1.{name}")
        m.__dict__.update(fns)
        monkeypatch.setitem(sys.modules, f"sh_platform.v1.{name}", m)
        monkeypatch.setattr(sys.modules["sh_platform.v1"], name, m, raising=False)

    stub("e1_reports", versions_using=lambda pl, t, rid: used.get(rid, []))
    stub("e3_calc", fx=lambda *a: None)
    stub("e3_rules", current=lambda pl, code, d: {"rule_version_id": "rule1", "parameters": {"abs_amount": 100000}})

    def opn(pl, fields):
        OPENED.append(fields)
        with wh.connect(pl) as con:
            eid = wh.new_id()
            con.execute("insert into exceptions (id, organization_id, exception_type, title, description, instrument_id, portfolio_id, detected_at,"
                        " materiality_status, status) values (?,?,?,?,?,?,?,?,?,?)",
                        [eid, W.org_id(pl), fields["exception_type"], fields["title"], fields["description"], fields["instrument_id"],
                         fields.get("portfolio_id"), wh.now(), "unknown", "new"])
        return eid

    stub("e4_cases", open=opn)
    org = W.org_id(p)
    seed(p, instruments=[I['fundA'], I['fundB']], portfolios=[I['pf']])
    with wh.connect(p) as con:
        con.execute("update instruments set canonical_name = 'Evergreen Growth I' where id = ?", [I['fundA']])
        for vid, amt, sup, ap in [(I['old'], 10_000_000, None, "approved"), (I['new'], 10_180_000, I['old'], "approved"), (I['other'], 5_000_000, None, "approved"),
                                  (I['other2'], 5_100_000, I['other'], "approved"), (I['pend'], 10_180_000, I['old'], "proposed"), (I['conf'], 10_180_000, I['pend'], "confirmed")]:
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, valuation_date, received_at, recorded_at,"
                        " value_amount, currency, valuation_type, approval_status, supersedes_valuation_id) values (?,?,?,?,?,?,?,?,?,?,?)",
                        [vid, org, I['fundA'] if vid in (I['old'], I['new'], I['pend'], I['conf']) else I['fundB'], date(2026, 9, 30), datetime(2026, 10, 2, tzinfo=UTC),
                         wh.now(), amt, "USD", "manager_estimate", ap, sup])
        con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status)"
                    " values (?,?,?,?,?,?,?)", [I['rv1'], org, I['r'], I['run1'], date(2026, 9, 30), datetime(2026, 10, 3, tzinfo=UTC), 'issued'])
        con.execute("insert into metric_values (id, organization_id, calculation_run_id, metric_definition_id, portfolio_id, instrument_id, reporting_date,"
                    " numeric_value, currency, value_status) values (?,?,?,?,?,?,?,?,?,?)",
                    [I['mv1'], org, I['run1'], I['r'], I['pf'], I['fundA'], date(2026, 9, 30), 10000000, 'USD', 'certified'])
    return p


def test_fund_a_revision_opens_one_exception(plane):
    eid = e3_impact.on_new_valuation(plane, I['new'])
    assert eid and len(OPENED) == 1
    f = OPENED[0]
    assert f["exception_type"] == "revision" and f["candidate_impact_amount"] == Decimal(180000) and f["impact_currency"] == "USD"
    assert f["materiality_status"] == "material" and f["materiality_rule_version_id"] == "rule1"
    with wh.connect(plane) as con:
        rows = con.execute("select report_version_id, issued_value, draft_value from exception_impacts where exception_id = ?", [eid]).fetchall()
        assert [(str(r[0]), Decimal(r[1]), Decimal(r[2])) for r in rows] == [(I['rv1'], Decimal(10_000_000), Decimal(10_180_000))]
        assert con.execute("select count(*) from nav_snapshots").fetchone()[0] == 0


def test_valuation_no_report_used_opens_none(plane):
    assert e3_impact.on_new_valuation(plane, I['other2']) is None
    assert e3_impact.on_new_valuation(plane, I['old']) is None  # supersedes nothing
    assert OPENED == []


def test_title_wording_slug_company_and_portfolio_fallback(plane):
    eid = e3_impact.on_new_valuation(plane, I['new'])  # a slug company id: impacts carry org_id, not "evergreen"
    f = OPENED[0]
    assert f["title"] == "Investigate the 180,000 USD manager-reported valuation difference for Evergreen Growth I"
    assert "P&L" not in f["description"] and "manager-reported valuation" in f["description"]
    assert f["portfolio_id"] == I['pf']  # the new row has none: the affected report line's portfolio
    with wh.connect(plane) as con:
        assert str(con.execute("select organization_id from exception_impacts where exception_id = ?", [eid]).fetchone()[0]) == W.org_id(plane)


def test_pending_then_confirmed_is_one_case(plane):
    first = e3_impact.on_new_valuation(plane, I['pend'])  # proposed row supersedes the value the report used
    assert first and len(OPENED) == 1 and "not yet verified" in OPENED[0]["description"]
    again = e3_impact.on_new_valuation(plane, I['conf'])  # confirmed row supersedes the pending one
    assert again == first and len(OPENED) == 1
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from exception_impacts where exception_id = ?", [first]).fetchone()[0] == 1
