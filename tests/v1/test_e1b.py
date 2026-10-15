"""E1b: unknown column refused, supersede link checked, recorded_at set, many in one transaction, no update/delete path."""
from datetime import date, datetime, timezone

import uuid

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e1_write as W, wh
from tests.v1.e1_seed import seed


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    seed(p, instruments=[FA, FB, FC], portfolios=[PF])
    return p


FA, FB, FC, PF = wh.new_id(), wh.new_id(), wh.new_id(), wh.new_id()


def val(**kw):
    return {"instrument_id": FA, "valuation_date": date(2026, 9, 30), "received_at": datetime(2026, 10, 2, tzinfo=timezone.utc),
            "value_amount": 10_000_000, "currency": "USD", "valuation_type": "estimate", "approval_status": "approved", **kw}


def rows(plane, sql, *a):
    with wh.connect(plane) as con:
        return con.execute(sql, list(a)).fetchall()


def test_fills_id_org_recorded_at(plane):
    i = W.record(plane, "valuation_observations", val())
    org, rec = rows(plane, "select organization_id, recorded_at from valuation_observations where id = ?", i)[0]
    assert str(org) == W.org_id(plane) and rec is not None


def test_unknown_column_and_table_refused(plane):
    with pytest.raises(W.WriteRefused, match="nope"):
        W.record(plane, "valuation_observations", val(nope=1))
    with pytest.raises(W.WriteRefused, match="unknown table"):
        W.record(plane, "no_such_table", {})
    with pytest.raises(W.WriteRefused, match="this company"):
        W.record(plane, "valuation_observations", val(organization_id="other"))


def test_supersede_link_checked(plane):
    a = W.record(plane, "valuation_observations", val())
    b = W.record(plane, "valuation_observations", val(value_amount=10_180_000, valuation_type="final"), supersedes_id=a)
    assert rows(plane, "select supersedes_valuation_id from valuation_observations where id = ?", b)[0][0] == uuid.UUID(a)
    with pytest.raises(W.WriteRefused, match="not a row"):
        W.record(plane, "valuation_observations", val(), supersedes_id=wh.new_id())
    with pytest.raises(W.WriteRefused, match="different subject"):
        W.record(plane, "valuation_observations", val(instrument_id=FB), supersedes_id=b)
    with pytest.raises(W.WriteRefused, match="already superseded"):
        W.record(plane, "valuation_observations", val(), supersedes_id=a)
    with pytest.raises(W.WriteRefused, match="no supersedes column"):
        W.record(plane, "organizations", {"name": "x", "created_at": wh.now()}, supersedes_id=a)


def test_many_in_one_transaction(plane):
    assert len(W.record_many(plane, "valuation_observations", [val(), val(instrument_id=FB)])) == 2
    with pytest.raises(W.WriteRefused):
        W.record_many(plane, "valuation_observations", [val(instrument_id=FC), val(nope=1)])
    assert rows(plane, "select count(*) from valuation_observations")[0][0] == 2


def test_no_update_or_delete_path():
    assert not [n for n in dir(W) if n.lstrip("_").startswith(("update", "delete", "remove"))]


def test_correction_without_subject_inherits_it(plane):
    a = W.record(plane, "valuation_observations", val(portfolio_id=PF))
    row = {k: v for k, v in val(value_amount=10_180_000).items() if k not in ("instrument_id", "valuation_date")}
    b = W.record(plane, "valuation_observations", row, supersedes_id=a)
    assert rows(plane, "select instrument_id, portfolio_id, valuation_date from valuation_observations where id = ?", b)[0] == (uuid.UUID(FA), uuid.UUID(PF), date(2026, 9, 30))


def test_referenced_ids_must_exist(plane):
    for bad in ({"instrument_id": wh.new_id()}, {"portfolio_id": wh.new_id()}, {"source_record_id": wh.new_id()}):
        with pytest.raises(W.WriteRefused, match="is not in this warehouse"):
            W.record(plane, "valuation_observations", val(**bad))
    assert rows(plane, "select count(*) from valuation_observations")[0][0] == 0


def test_recorded_at_cannot_be_backdated_except_in_replay(plane):
    then = datetime(2026, 10, 1, tzinfo=timezone.utc)
    a = W.record(plane, "valuation_observations", val(recorded_at=then))
    b = W.record(plane, "valuation_observations", val(instrument_id=FB, recorded_at=then), replay=True)
    ra, rb = (rows(plane, "select recorded_at from valuation_observations where id = ?", i)[0][0] for i in (a, b))
    assert ra > then and rb == then


def test_two_supersede_links_must_agree(plane):
    a = W.record(plane, "valuation_observations", val())
    b = W.record(plane, "valuation_observations", val(), supersedes_id=a)
    with pytest.raises(W.WriteRefused, match="different rows"):
        W.record(plane, "valuation_observations", val(supersedes_valuation_id=a), supersedes_id=b)
