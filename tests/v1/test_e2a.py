"""E2a: a statement is registered with hash, original kept, date, status, matched fund; the same file twice is one document; an amended statement
for the same fund and date supersedes the first (by words, or by a later received date); a different date or fund does not; the chain reads oldest first."""
import sys
import types
from datetime import datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e2_intake as E
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

FUND = "00000000-0000-4000-8000-00000000000a"
EST = "Evergreen Growth I\nManager statement\nValuation date: 30 September 2026\nNet asset value 10,000,000.00 USD\nStatus: Estimate\n"
AMENDED = "Evergreen Growth I\nAmended statement\nValuation date: 30 September 2026\nNet asset value 10,180,000.00 USD\nStatus: Final\n"
OCT = "Evergreen Growth I\nManager statement\nValuation date: 31 October 2026\nNet asset value 10,300,000.00 USD\nStatus: Estimate\n"
OTHER = "Mystery Holdings Fund\nManager statement\nValuation date: 30 September 2026\nNet asset value 1.00 USD\n"


def at(day: int, month: int = 10) -> datetime:
    return datetime(2026, month, day, 9, tzinfo=timezone.utc)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(p) as con:
        con.execute("insert into organizations values (?,?,?)", [org_id(p), "Acme", wh.now()])

    def resolve(plane, name, source_id):  # E2c stub: only the Evergreen fund is approved
        ok = "evergreen growth" in name.lower()
        return {"instrument_id": FUND if ok else None, "status": "approved" if ok else "unknown", "candidates": []}
    fake = types.ModuleType("sh_platform.v1.e2_match")
    fake.resolve = resolve
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e2_match", fake)
    monkeypatch.setattr("sh_platform.v1.e2_match", fake, raising=False)  # the package attribute wins over sys.modules once the real module was imported
    monkeypatch.setattr("sh_platform.v1.doc_index._slow", lambda path: False)
    return p


def reg(plane, name, text, received):
    return E.register(plane, None, None, received_at=received, data=text.encode(), filename=name)


def row(plane, did):
    return next(d for d in E.listing(plane) if d["id"] == did)


def test_register_keeps_the_original_and_reads_the_statement(plane):
    did = reg(plane, "fund_a_sep.txt", EST, at(2))
    d = row(plane, did)
    assert (d["valuation_date"], d["document_status"], d["instrument_id"], d["document_type"]) == ("2026-09-30", "estimate", FUND, "manager_statement")
    assert plane.path(*d["original_uri"].split("/")).read_text() == EST and d["original_uri"].startswith("landing/originals/")
    assert E.supersession_of(plane, did) is None and d["current"]
    assert reg(plane, "again.txt", EST, at(3)) == did and len(E.listing(plane)) == 1          # same bytes, same document


def test_amended_statement_supersedes_the_first(plane):
    a = reg(plane, "fund_a_sep.txt", EST, at(2))
    b = reg(plane, "fund_a_sep_amended.txt", AMENDED, at(9))
    assert E.supersession_of(plane, b) == a
    assert row(plane, b)["document_status"] == "final" and row(plane, b)["current"] and not row(plane, a)["current"]
    assert [d["id"] for d in E.detail(plane, a)["chain"]] == [a, b] == [d["id"] for d in E.detail(plane, b)["chain"]]


def test_later_received_without_the_words_still_supersedes_and_unrelated_does_not(plane):
    a = reg(plane, "one.txt", EST, at(2))
    b = reg(plane, "two.txt", EST.replace("10,000,000.00", "10,050,000.00"), at(5))       # same fund and date, received later
    assert E.supersession_of(plane, b) == a and row(plane, b)["document_status"] == "revised_estimate"
    c = reg(plane, "oct.txt", OCT, at(6))                                                    # another valuation date
    assert E.supersession_of(plane, c) is None
    d = reg(plane, "other.txt", OTHER, at(7))                                                # fund not matched
    assert E.supersession_of(plane, d) is None and row(plane, d)["instrument_id"] is None and row(plane, d)["processing_status"] == "needs_match"
    assert {r["id"] for r in E.listing(plane, FUND)} == {a, b, c}


def test_unknown_document_is_refused(plane):
    with pytest.raises(E.Refused):
        E.detail(plane, "nope")
