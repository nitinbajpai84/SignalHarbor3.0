"""E1c: issue a report, then a revision arrives. As issued never changes; as known now shows the new value as revised;
versions_using finds the version; a re-issue supersedes; totals are re-added; unknown access fails closed."""
import sys
from datetime import date, datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_reports as R, e1_write as W, wh
from tests.v1.e1_seed import seed

FA, FB, PF, SR = wh.new_id(), wh.new_id(), wh.new_id(), wh.new_id()
CIO = wh.new_id()
CUT = datetime(2026, 10, 3, 23, 59, tzinfo=timezone.utc)


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    seed(p, instruments=[FA, FB], portfolios=[PF], sources=[SR])
    return p


def rec(plane, row, supersedes_id=None):
    return W.record(plane, "valuation_observations", row, supersedes_id=supersedes_id, replay=True)  # replay: history is back-dated


LATE = datetime(2026, 10, 9, tzinfo=timezone.utc)


def val(inst, amount, **kw):
    return {"instrument_id": inst, "portfolio_id": PF, "valuation_date": date(2026, 9, 30), "received_at": datetime(2026, 10, 2, tzinfo=timezone.utc), "recorded_at": datetime(2026, 10, 2, 1, tzinfo=timezone.utc),
            "value_amount": amount, "currency": "USD", "valuation_type": "manager_estimate", "approval_status": "approved", **kw}


def lines(a, b):
    src = lambda i: [{"table": "valuation_observations", "row_id": i}]
    return [{"metric_code": "holding_value", "portfolio_id": PF, "instrument_id": FA, "value": 10_000_000, "currency": "USD", "status": "estimated", "sources": src(a)},
            {"metric_code": "holding_value", "portfolio_id": PF, "instrument_id": FB, "value": 6_400_000, "currency": "USD", "status": "official", "sources": src(b)},
            {"metric_code": "portfolio_total", "portfolio_id": PF, "value": 16_400_000, "currency": "USD", "status": "estimated"}]


@pytest.fixture()
def issued(plane):
    a, b = rec(plane, val(FA, 10_000_000)), rec(plane, val(FB, 6_400_000))
    R.ensure_report(plane, "investment_report", "Investment report", "CIO", ["USD"])
    v = R.issue(plane, "investment_report", date(2026, 9, 30), CUT, CIO, lines(a, b))
    return v, a, b


def by(ls):
    return {(l["metric_code"], l["instrument_id"]): l for l in ls}


def test_issue_and_as_issued(plane, issued):
    v, a, b = issued
    assert R.ensure_report(plane, "investment_report", "x", "x", ["USD"]) == R.ensure_report(plane, "investment_report", "x", "x", "USD")  # idempotent
    got = by(R.as_issued(plane, v))
    assert got[("holding_value", FA)]["value"] == 10_000_000 and got[("holding_value", FA)]["status"] == "estimated"
    assert got[("portfolio_total", None)]["value"] == 16_400_000 and got[("holding_value", FA)]["sources"] == [{"table": "valuation_observations", "row_id": a}]
    assert R.versions_using(plane, "valuation_observations", a) == [v] and R.versions_using(plane, "valuation_observations", "nope") == []


def test_revision_shows_now_but_not_as_issued(plane, issued):
    v, a, b = issued
    before = R.as_issued(plane, v)
    new = rec(plane, val(FA, 10_180_000, valuation_type="manager_final", recorded_at=LATE, approval_status="confirmed"), supersedes_id=a)
    assert R.as_issued(plane, v) == before  # an issued version never changes
    now = by(R.as_known_now(plane, v))
    fa = now[("holding_value", FA)]
    assert fa["value"] == 10_180_000 and fa["status"] == "revised" and fa["issued_value"] == 10_000_000 and fa["source_now"]["row_id"] == new
    assert now[("holding_value", FB)]["status"] == "official" and now[("holding_value", FB)]["value"] == 6_400_000
    assert now[("portfolio_total", None)]["value"] == 16_580_000 and now[("portfolio_total", None)]["status"] == "revised"


def test_nothing_new_leaves_statuses_as_issued(plane, issued):
    now = by(R.as_known_now(plane, issued[0]))
    assert now[("holding_value", FA)]["status"] == "estimated" and now[("portfolio_total", None)]["value"] == 16_400_000
    assert now[("portfolio_total", None)]["status"] == "estimated"


def test_line_without_evidence_is_unverified(plane):
    R.ensure_report(plane, "r", "R", "CIO", ["USD"])
    v = R.issue(plane, "r", date(2026, 9, 30), CUT, CIO, [{"portfolio_id": PF, "instrument_id": FA, "value": 5, "currency": "USD", "status": "official"}])
    assert R.as_known_now(plane, v)[0]["status"] == "unverified"


def test_reissue_supersedes_and_versions_using_follows_the_live_one(plane, issued):
    v1, a, b = issued
    new = rec(plane, val(FA, 10_180_000, recorded_at=LATE, approval_status="confirmed"), supersedes_id=a)
    ls = lines(new, b)
    ls[0]["value"], ls[0]["status"] = 10_180_000, "official"
    v2 = R.issue(plane, "investment_report", date(2026, 9, 30), datetime.now(timezone.utc), CIO, ls)
    with wh.connect(plane) as con:
        assert con.execute("select status, supersedes_report_version_id from report_versions where id=?", [v2]).fetchone() == ("issued", v1) or str(con.execute("select supersedes_report_version_id from report_versions where id=?", [v2]).fetchone()[0]) == v1
        assert con.execute("select status from report_versions where id=?", [v1]).fetchone()[0] == "superseded"
        assert con.execute("select code_version from calculation_runs limit 1").fetchone()[0]
    assert R.versions_using(plane, "valuation_observations", a) == [] and R.versions_using(plane, "valuation_observations", new) == [v2]
    assert by(R.as_issued(plane, v1))[("portfolio_total", None)]["value"] == 16_400_000  # the old one is still readable as it went out
    assert [x["status"] for x in R.listing(plane)[0]["versions"]] == ["issued", "superseded"]


def test_route_filters_by_access_and_fails_closed(plane, issued, monkeypatch):
    from sh_platform.v1 import e1c_routes as RT

    class Fake:
        @staticmethod
        def level(plane, viewer, entity_id=None, portfolio_id=None):
            return "read" if viewer == "ok" else "none"

        @staticmethod
        def visible_portfolios(plane, viewer):
            return {PF} if viewer == "ok" else set()

    monkeypatch.setitem(sys.modules, "sh_platform.v1.e1_access", Fake)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e1_access", Fake, raising=False)
    ls = R.as_issued(plane, issued[0])
    assert all(RT._visible(plane, "ok", l) for l in ls) and not any(RT._visible(plane, "no", l) for l in ls)
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e1_access", None)  # module missing -> ImportError -> nothing shown
    monkeypatch.delattr(sys.modules["sh_platform.v1"], "e1_access", raising=False)
    with pytest.raises(ImportError):
        RT._visible(plane, "ok", ls[0])


def test_issue_refuses_late_sources_and_unverified_lines(plane):
    a = rec(plane, val(FA, 10_000_000, recorded_at=LATE))  # recorded 9 Oct, after the 3 Oct cutoff
    R.ensure_report(plane, "r", "R", "CIO", ["USD"])
    ln = {"portfolio_id": PF, "instrument_id": FA, "value": 1, "currency": "USD", "status": "estimated", "sources": [{"table": "valuation_observations", "row_id": a}]}
    with pytest.raises(ValueError, match="after the cutoff"):
        R.issue(plane, "r", date(2026, 9, 30), CUT, CIO, [ln])
    for st in ("unverified", "draft"):
        with pytest.raises(ValueError, match="unverified or draft"):
            R.issue(plane, "r", date(2026, 9, 30), CUT, CIO, [{**ln, "status": st, "sources": []}])
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from report_versions").fetchone()[0] == 0


def test_pending_revision_is_unverified_confirmed_is_revised(plane, issued):
    v, a, b = issued
    pend = rec(plane, val(FA, 10_180_000, recorded_at=LATE, approval_status="proposed"), supersedes_id=a)
    fa = by(R.as_known_now(plane, v))[("holding_value", FA)]
    assert fa["status"] == "unverified" and fa["value"] == 10_180_000 and fa["issued_value"] == 10_000_000
    rec(plane, val(FA, 10_180_000, recorded_at=LATE, approval_status="confirmed"), supersedes_id=pend)
    assert by(R.as_known_now(plane, v))[("holding_value", FA)]["status"] == "revised"


def test_one_evidence_pointer_rules_and_run_keeps_rule_versions(plane):
    a = rec(plane, val(FA, 1, source_record_id=SR))
    R.ensure_report(plane, "r", "R", "CIO", ["USD"])
    ln = {"portfolio_id": PF, "instrument_id": FA, "value": 1, "currency": "USD", "status": "estimated", "sources": [{"table": "valuation_observations", "row_id": a}]}
    R.issue(plane, "r", date(2026, 9, 30), CUT, CIO, [ln], rule_versions=["rv-1"])
    with wh.connect(plane) as con:
        for src, passage, field in con.execute("select source_record_id, document_passage_id, extracted_field_id from metric_evidence").fetchall():
            assert sum(x is not None for x in (src, passage, field)) <= 1
        assert con.execute("select rule_versions_used from calculation_runs").fetchone()[0] == '["rv-1"]'
        assert con.execute("select count(*) from approvals where report_version_id is not null and rule_version_id is null and exception_id is null").fetchone()[0] == 1


def test_issue_can_be_backdated(plane):
    R.ensure_report(plane, "r", "R", "CIO", ["USD"])
    when = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
    v = R.issue(plane, "r", date(2026, 9, 30), CUT, CIO, [{"value": 1, "currency": "USD", "status": "official"}], issued_at=when)
    with wh.connect(plane) as con:
        assert con.execute("select issued_at from report_versions where id=?", [v]).fetchone()[0] == when
        assert con.execute("select started_at, finished_at from calculation_runs").fetchone() == (when, when)
