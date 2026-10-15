"""F12: confirming owners checks each slot. A slot that changes needs the person named for it, or the head of data."""
import pytest

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G

AT = "2026-10-01T00:00:00Z"
DATA = C.Viewer("Test Dee Data", frozenset({"owner"}), account_id="acct-dee")
BIZ = C.Viewer("Test Bea Business", frozenset({"owner"}), account_id="acct-bea")
HEAD = C.Viewer("Test Hal Head", frozenset({"analyst"}))
PROFILE = {"people": {"hal": {"name": {"value": "Test Hal Head", "mark": "stated"}, "is_head_of_data": {"value": True, "mark": "stated"}}}}


def kpi() -> dict:
    o = lambda n, a: {"value": n, "mark": "stated", "by": "x", "from": "x", "at": AT, "account_id": a}  # noqa: E731
    return {"id": "K1", "owners": {"business": o("Test Bea Business", "acct-bea"), "data": o("Test Dee Data", "acct-dee"),
                                   "process": {"value": None, "mark": "unknown"}}}


def cell(business="Test Bea Business", data="Test Dee Data", mark="guessed") -> dict:
    return {"value": {"business": business, "data": data, "process": None}, "mark": mark}


def test_the_data_owner_confirms_their_slot_when_the_rest_is_unchanged():
    G.check_confirm("owners", kpi(), {}, DATA, {"business": "test bea business", "data": "Test Dee Data", "process": None}, cell())


def test_the_data_owner_may_not_change_the_business_slot():
    with pytest.raises(C.CatalogueError) as e:
        G.check_confirm("owners", kpi(), {}, DATA, {"business": "Test Someone Else", "data": "Test Dee Data", "process": None}, cell())
    assert e.value.code == "forbidden" and "business owner" in e.value.message


def test_the_data_owner_may_not_clear_the_business_slot():
    with pytest.raises(C.CatalogueError):
        G.check_confirm("owners", kpi(), {}, DATA, {"business": None, "data": "Test Dee Data", "process": None}, cell())


def test_the_business_owner_may_change_their_own_slot_but_not_the_data_slot():
    G.check_confirm("owners", kpi(), {}, BIZ, {"business": "Test New Business", "data": "Test Dee Data", "process": None}, cell())
    with pytest.raises(C.CatalogueError):
        G.check_confirm("owners", kpi(), {}, BIZ, {"business": "Test Bea Business", "data": "Test Other Data", "process": None}, cell())


def test_the_work_list_nominee_counts_as_unchanged_when_the_cell_is_empty():
    G.check_confirm("owners", kpi(), {}, DATA, {"business": "Test Bea Business", "data": "Test Dee Data", "process": None}, {"value": None, "mark": "unknown"})


def test_the_head_of_data_may_change_any_slot():
    G.check_confirm("owners", kpi(), PROFILE, HEAD, {"business": "Test X", "data": "Test Y", "process": "Test Z"}, cell(mark="stated"))


def test_without_a_submitted_value_the_old_rule_holds_and_other_fields_are_untouched():
    G.check_confirm("owners", kpi(), {}, DATA)
    G.check_confirm("classification", kpi(), PROFILE, HEAD, "open", None)
    with pytest.raises(C.CatalogueError):
        G.check_confirm("classification", kpi(), {}, DATA, "open", None)
