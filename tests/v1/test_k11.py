"""K11 attribution on the synthetic Evergreen September 2026 data (tools/seed_10uc.py, temporary data root). Figures against docs/test/10UC-ANSWER-KEY.md (P06, P14)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sh_platform.plane import PlaneStore
from sh_platform.v1 import a5_trail, k11_attrib, k11_routes, wh
from sh_platform.v1.i2_north import Refused
from tools import seed_10uc as S

D = Decimal
SEP = (date(2026, 9, 1), date(2026, 9, 30))


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    root = tmp_path_factory.mktemp("k11")
    S.seed(root)
    plane = PlaneStore(root).plane_for("evergreen").ensure()
    ids, _ = S.EG.accounts(root)
    with wh.connect(plane, read_only=True) as con:
        pf = str(con.execute("select id from portfolios where portfolio_code = 'EG-LIQUID'").fetchone()[0])
    yield {"plane": plane, "V": S.viewers(ids), "pf": pf, "attr": k11_attrib.attribute(plane, S.viewers(ids)["Daniel Foo"], pf, "EG-LIQUID", "EG-OFFICE-BLEND", *SEP)}
    mp.undo()


def v(f):
    return D(f["value"])


def near(a, b):
    return abs(a - b) < D("1e-12")   # the Decimal chains carry 28 digits


def test_allocation_selection_interaction_add_up_to_the_active_return_to_the_basis_point(world):
    a = world["attr"]
    assert a["problems"] == [] and a["certified"] and a["version_used"]["version"] == 1
    t = a["totals"]
    assert (t["portfolio_return"]["pct"], t["benchmark_return"]["pct"], t["active_return"]["pct"]) == ("4.1667", "2.7072", "1.4595")   # P14
    parts = sum(v(t[k]) for k in ("allocation", "selection", "interaction"))
    assert abs(parts - v(t["active_return"])) < D("0.0001") and t["reconciles"]
    for s in a["sleeves"]:                      # each sleeve's three effects add to its total
        assert near(v(s["total"]), v(s["allocation"]) + v(s["selection"]) + v(s["interaction"]))
    assert near(sum(v(s["total"]) for s in a["sleeves"]), parts)
    Rb = v(t["benchmark_return"])                # Brinson-Fachler worked again from the published weights and returns
    for s in a["sleeves"]:
        wp, wb, rb = v(s["portfolio_weight"]), v(s["benchmark_weight"]), v(s["benchmark_return"])
        rp = v(s["portfolio_return"]) if s["portfolio_return"] else rb
        assert near(v(s["allocation"]), (wp - wb) * (rb - Rb)) and near(v(s["selection"]), wb * (rp - rb)) and near(v(s["interaction"]), (wp - wb) * (rp - rb))
    assert near(sum(v(s["benchmark_weight"]) for s in a["sleeves"]), 1) and t["partial"] is False


def test_sleeves_follow_the_signed_definition_and_the_answer_key_returns(world):
    by = {s["sleeve"]: s for s in world["attr"]["sleeves"]}
    assert (by["equity"]["benchmark_weight"]["pct"], by["bond"]["benchmark_weight"]["pct"], by["private"]["benchmark_weight"]["pct"]) == ("42.0000", "28.0000", "30.0000")
    assert (by["equity"]["benchmark_return"]["pct"], by["bond"]["benchmark_return"]["pct"], by["private"]["benchmark_return"]["pct"]) == ("3.5002", "0.4002", "3.7502")
    assert by["private"]["portfolio_return"] is None and v(by["private"]["selection"]) == 0 and v(by["private"]["interaction"]) == 0   # not held: allocation only
    assert D(by["private"]["active_weight"]["value"]) == D("-0.3")
    assert "other" in by                         # the convertible without an asset class sits outside the benchmark
    assert near(sum(v(s["portfolio_weight"]) for s in by.values()), 1)
    assert near(sum(v(s["contribution"]) for s in by.values()), v(world["attr"]["totals"]["portfolio_return"]))


def test_contribution_by_fund_matches_the_answer_key_movers(world):
    f = {x["name"]: x for x in world["attr"]["funds"]}
    assert near(v(f["Northwind Logistics"]["contribution"]), D(132000) / D(39552000))               # P06: +132,000 on the 39,552,000 opening value
    assert near(v(f["Silverpine Software"]["contribution"]), D(130400) / D(39552000))
    assert near(sum(v(x["contribution"]) for x in f.values()), v(world["attr"]["totals"]["portfolio_return"]))


def test_every_figure_has_a_trail_that_resolves(world):
    a = world["attr"]
    nw = next(x for x in a["funds"] if x["name"] == "Northwind Logistics")
    assert {r["as_of"] for r in nw["trail"]} == {"opening", "closing"}
    for r in nw["trail"]:
        t = a5_trail.trail(world["plane"], world["V"]["Daniel Foo"], r["kind"], r["id"])
        assert t["id"] == r["id"] and t["steps"]
    assert all(s["trail"] for s in a["sleeves"] if s["sleeve"] != "private") and all(s["benchmark_source"]["version"] == 1 for s in a["sleeves"])


def test_cap_size_and_region_say_what_is_missing(world):
    sp = world["attr"]["splits"]
    for k in ("cap_size", "region"):
        assert sp[k]["available"] is False and "No instrument carries" in sp[k]["missing"]


def test_a_benchmark_still_being_defined_gives_no_attribution(world):
    a = k11_attrib.attribute(world["plane"], world["V"]["Daniel Foo"], world["pf"], "EG-LIQUID", "EG-OFFICE-BLEND", date(2026, 10, 1), date(2026, 10, 31))
    assert a["totals"] is None and a["sleeves"] == [] and a["problems"]


def test_entity_access_applies(world, monkeypatch):
    with pytest.raises(Refused) as e:
        k11_routes.build(world["plane"], world["V"]["Daniel Foo"], "EG-NOPE", "EG-OFFICE-BLEND", "2026-09", "2026-09")
    assert e.value.status == 404
    with pytest.raises(Refused) as e:
        k11_routes.build(world["plane"], world["V"]["Daniel Foo"], "EG-LIQUID", "EG-OFFICE-BLEND", "2026-09", "2024-01")
    assert e.value.status == 400
    one = next(x for x in world["attr"]["funds"] if x["name"] == "Northwind Logistics")["instrument_id"]
    real = a5_trail._may
    monkeypatch.setattr(a5_trail, "_may", lambda plane, viewer, pid, iid=None: iid != one and real(plane, viewer, pid, iid))
    b = k11_routes.build(world["plane"], world["V"]["Daniel Foo"], "EG-LIQUID", "EG-OFFICE-BLEND", "2026-09", "2026-09")
    hidden = [x for x in b["funds"] if not x["visible"]]
    assert len(hidden) == 1 and "contribution" not in hidden[0]
    by, whole = {s["sleeve"]: s for s in b["sleeves"]}, {s["sleeve"]: s for s in world["attr"]["sleeves"]}
    m = by[hidden[0]["sleeve"]]                  # the sleeve holding the hidden fund gives nothing away
    assert m["masked"] and m["note"] == "Some funds in this sleeve are not visible to you" and m["trail"] == []
    assert all(m[k] is None for k in ("portfolio_weight", "active_weight", "portfolio_return", "contribution", "allocation", "selection", "interaction", "total"))
    assert m["benchmark_weight"] == whole[m["sleeve"]]["benchmark_weight"]   # the benchmark side is not the fund's
    shown = [s for s in b["sleeves"] if not s.get("masked")]
    assert shown and all(s == whole[s["sleeve"]] for s in shown)
    t = b["totals"]                              # totals cover only what is shown: no portfolio or active return, no residual to subtract from
    assert t["partial"] and t["portfolio_return"] is None and t["active_return"] is None and t["unexplained"] is None and t["reconciles"] is None
    for k in ("allocation", "selection", "interaction"):
        assert near(v(t[k]), sum(v(s[k]) for s in shown))
    assert near(v(t["explained"]), sum(v(s["total"]) for s in shown)) and t["benchmark_return"] == world["attr"]["totals"]["benchmark_return"]


def test_the_route_is_declared_default_deny():
    table = yaml.safe_load(Path(k11_routes.__file__).with_name("k11.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    assert "GET /api/v1/attribution" in table
