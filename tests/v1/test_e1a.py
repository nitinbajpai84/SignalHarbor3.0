"""E1a as-known-then: the Fund A story, late-loaded files, chains, every table's supersede column, bad input refused, E1d filtering."""
import sys
import types
import uuid
from datetime import datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_asof as A
from sh_platform.v1 import e1a_routes as R
from sh_platform.v1 import wh

D = lambda d, h=0: datetime(2026, 10, d, h, tzinfo=timezone.utc)  # noqa: E731


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    (tmp_path / "evergreen").mkdir()
    return PlaneStore(tmp_path).plane_for("evergreen")


U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_DNS, n)) if n else None  # noqa: E731  (the warehouse ids are uuids)


def val(plane, id, amount, received, recorded, sup=None, pf="pf1"):
    id, sup, pf = U(id), U(sup), U(pf)
    with wh.connect(plane) as con:
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at,"
                    " value_amount, currency, valuation_type, approval_status, supersedes_valuation_id) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [id, U("org"), U("fundA"), pf, "2026-09-30", received, recorded, amount, "USD", "manager_estimate", "draft", sup])


def test_fund_a_estimate_then_revision(plane):
    val(plane, "v1", 10_000_000, D(2), D(2, 9))
    val(plane, "v2", 10_180_000, D(9), D(9, 9), sup="v1")
    w = {"instrument_id": U("fundA"), "valuation_date": "2026-09-30"}
    assert A.latest(plane, "valuation_observations", w, D(3))["value_amount"] == 10_000_000
    assert A.latest(plane, "valuation_observations", w, "2026-10-03")["value_amount"] == 10_000_000  # a bare date = end of that day
    assert A.latest(plane, "valuation_observations", w, D(12))["value_amount"] == 10_180_000
    assert A.latest(plane, "valuation_observations", w, None) is not None  # no cutoff means now
    assert [str(r["id"]) for r in A.snapshot(plane, "valuation_observations", w, D(10))] == [U("v2")]
    assert A.latest(plane, "valuation_observations", w, D(1)) is None


def test_late_loaded_file_is_excluded(plane):
    val(plane, "v1", 10_000_000, D(2), D(2, 9))
    val(plane, "late", 9_900_000, D(2), D(5, 9), sup="v1")  # received before the cutoff, recorded after
    assert A.latest(plane, "valuation_observations", {"instrument_id": U("fundA")}, D(3))["id"].__str__() == U("v1")
    assert A.latest(plane, "valuation_observations", {"instrument_id": U("fundA")}, D(6))["id"].__str__() == U("late")


def test_chain_from_any_member(plane):
    val(plane, "v1", 1, D(2), D(2))
    val(plane, "v2", 2, D(3), D(3), sup="v1")
    val(plane, "v3", 3, D(4), D(4), sup="v2")
    val(plane, "other", 9, D(4), D(4))
    for start in ("v1", "v2", "v3"):
        assert [str(r["id"]) for r in A.chain(plane, "valuation_observations", U(start))] == [U("v1"), U("v2"), U("v3")]
    assert A.chain(plane, "valuation_observations", U("nope")) == []


def test_every_table_has_a_real_supersede_column_and_bad_input_is_refused(plane):
    with wh.connect(plane) as con:
        for t, col in A.SUPERSEDES.items():
            assert col in A._columns(con, t)
    with pytest.raises(A.AsOfError):
        A.snapshot(plane, "users", {}, None)
    with pytest.raises(A.AsOfError):
        A.snapshot(plane, "valuation_observations", {"id; drop table x": 1}, None)
    with pytest.raises(A.AsOfError):
        A.snapshot(plane, "valuation_observations", {}, "last tuesday")


def test_route_filter_follows_e1d(plane, monkeypatch):
    stub = types.SimpleNamespace(visible_portfolios=lambda p, v: {"pf1"})
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e1_access", stub)
    monkeypatch.setattr("sh_platform.v1.e1_access", stub, raising=False)
    rows = [{"id": "a", "portfolio_id": "pf1"}, {"id": "b", "portfolio_id": "pf2"}, {"id": "c", "portfolio_id": None}, {"id": "d"}]
    assert [r["id"] for r in R._visible(plane, None, rows)] == ["a", "d"]  # a row with no portfolio and no chain to one is hidden
    stub.visible_portfolios = lambda p, v: set()
    assert [r["id"] for r in R._visible(plane, None, rows)] == ["d"]


def test_a3_13_a_malformed_id_or_filter_is_a_plain_400_not_a_500(plane):
    val(plane, "v1", 10_000_000, D(2), D(2))   # duckdb only converts the id when the table holds rows
    with pytest.raises(A.AsOfError):
        A.chain(plane, "valuation_observations", "nope")
    with pytest.raises(A.AsOfError):
        A.snapshot(plane, "valuation_observations", {"instrument_id": "nope"}, None)
    r = R._run(lambda: A.chain(plane, "valuation_observations", "nope"))
    assert r.status_code == 400 and b"not in a form we can read" in r.body
