"""K7 read path: signed definitions with status and the policy question, the monthly comparison (portfolio, per component, blend, difference,
liquid sleeve) all as Decimal strings, the version used, access (E1d) and the permissions file. Data comes from test_k7's plane."""
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from test_k7 import PF, plane, wh, K, nid, ORG, near  # noqa: F401  (plane is the fixture)
from datetime import date

from sh_platform.profile.view import Viewer
from sh_platform.v1 import k7_routes as R
from sh_platform.v1.i2_north import Refused

ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}), False, "acc-mei")
NOBODY = Viewer("Sam Roe", frozenset({"analyst"}), False, "acc-sam")


@pytest.fixture(autouse=True)
def portfolio(plane):
    with wh.connect(plane) as con:
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)",
                    [PF, ORG, nid(), "EG-LIQUID", "Liquid", "USD"])


def test_definitions_show_status_and_the_policy_question_for_an_in_progress_one(plane):
    with pytest.raises(Refused):
        K.certified_return(plane, "PRIVATE", date(2026, 8, 31), date(2026, 9, 30))   # raises the case, as the product does
    defs = {d["benchmark_code"]: d for d in R.definitions(plane)["definitions"]}
    assert defs["BLEND"]["status"] == "approved" and "notice" not in defs["BLEND"]
    p = defs["PRIVATE"]
    assert p["status"] == "in_progress" and p["notice"].startswith("In progress: not used for certified figures")
    assert p["policy_question"]["case"]["title"] == "Agree the definition of benchmark PRIVATE" and "Who decides" in p["policy_question"]["question"]
    assert defs["BLEND"]["components"][0]["weight"] == "0.5"
    assert "policy_question" not in defs["SPREAD"]


def test_reading_definitions_never_opens_a_case(plane):
    R.definitions(plane)
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from exceptions").fetchone()[0] == 0


def test_monthly_comparison_is_the_calculation_as_strings(plane):
    out = R.monthly(plane, ADMIN, PF, "BLEND", "2026-09", "2026-09")
    m = out["months"][0]
    assert out["version_used"] == {"version": 1, "status": "approved", "name": "Benchmark BLEND"} and out["portfolio"]["id"] == PF
    assert m["month"] == "2026-09" and m["period_start"] == "2026-08-31" and m["certified"] is True and m["problems"] == []
    assert near(m["benchmark"]["value"], "0.034") and m["benchmark"]["pct"] == "3.4000"
    assert near(m["portfolio"]["value"], Decimal(50_000) / Decimal(1_050_000))
    assert near(m["difference"]["value"], Decimal(m["portfolio"]["value"]) - Decimal(m["benchmark"]["value"]))
    assert {c["series_key"]: (c["weight"], c["return"]["pct"]) for c in m["components"]} == {"IDX.EQ": ("0.6", "5.0000"), "IDX.BOND": ("0.4", "1.0000")}
    assert m["liquid_sleeve"] is None                                  # no spread component: nothing to separate


def test_liquid_sleeve_is_the_unspread_components_renormalised(plane):
    start = date(2026, 1, 1)
    with wh.connect(plane) as con:
        i = nid()
        con.execute("insert into benchmark_definitions (id, organization_id, benchmark_code, benchmark_name, version_number, reporting_currency, effective_from,"
                    " calculation_method, approval_status) values (?,?, 'MIX', 'Mix', 1, 'USD', ?, 'blend', 'approved')", [i, ORG, start])
        for key, w, bps in (("IDX.EQ", "0.6", None), ("IDX.BOND", "0.2", None), ("IDX.EQ", "0.2", "300")):
            con.execute("insert into benchmark_components (id, organization_id, benchmark_definition_id, market_series_key, component_weight, spread_bps,"
                        " weight_effective_from) values (?,?,?,?,?,?,?)", [nid(), ORG, i, key, w, bps, start])
    m = R.monthly(plane, ADMIN, PF, "MIX", "2026-09", "2026-09")["months"][0]
    assert near(m["liquid_sleeve"]["value"], "0.04") and m["liquid_sleeve"]["pct"] == "4.0000"      # (0.6 * 5% + 0.2 * 1%) / 0.8
    assert near(m["liquid_sleeve"]["difference"]["value"], Decimal(m["portfolio"]["value"]) - Decimal("0.04"))


def test_in_progress_version_is_flagged_and_not_certified(plane):
    out = R.monthly(plane, ADMIN, PF, "PRIVATE", "2026-09", "2026-09")
    assert out["version_used"]["status"] == "in_progress" and out["version_used"]["notice"].startswith("In progress")
    assert out["months"][0]["certified"] is False


def test_missing_data_is_a_null_with_the_reason(plane):
    m = R.monthly(plane, ADMIN, PF, "NOLEVEL", "2026-09", "2026-09")["months"][0]
    assert m["benchmark"] is None and m["difference"] is None and "IDX.NONE" in m["problems"][0]


def test_period_and_access(plane):
    assert [x["month"] for x in R.monthly(plane, ADMIN, PF, "BLEND", "2026-08", "2026-09")["months"]] == ["2026-08", "2026-09"]
    for args in (("2026-09", "2026-08"), ("nope", "")):
        with pytest.raises(Refused) as e:
            R.monthly(plane, ADMIN, PF, "BLEND", *args)
        assert e.value.status == 400
    with pytest.raises(Refused) as e:                                   # no grant: looks the same as a portfolio that does not exist
        R.monthly(plane, NOBODY, PF, "BLEND", "2026-09", "2026-09")
    assert e.value.status == 404
    assert R.monthly(plane, ADMIN, "EG-LIQUID", "BLEND", "2026-09", "2026-09")["portfolio"]["id"] == PF   # the code works as well as the id
    with pytest.raises(Refused) as e:
        R.monthly(plane, ADMIN, "nothing", "BLEND", "2026-09", "2026-09")
    assert e.value.status == 404


def test_every_route_is_declared_with_the_agreed_roles():
    table = yaml.safe_load((Path(R.__file__).parent / "k7.permissions.yaml").read_text())["routes"]
    declared = {k.split(" ", 1)[1] for k in table}
    assert {r.path for r in R.router.routes} == declared
    assert all(set(v["roles"]) == {"sponsor", "approver", "analyst", "company_admin", "participant"} for v in table.values())
