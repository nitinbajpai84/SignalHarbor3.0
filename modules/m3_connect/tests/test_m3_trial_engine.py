"""The rule engine's operations (pure stdlib): every op, filters, periods, empty cells, groups under five."""
import pytest

from modules.m3_connect.domain import engine as E

ROWS = [{"g": "a", "v": "10", "w": "1", "d": "2026-09-01", "k": "x", "r": None},
        {"g": "a", "v": "20", "w": "2", "d": "2026-09-02", "k": "y", "r": "x"},
        {"g": "b", "v": "", "w": "3", "d": "2026-09-03", "k": "z", "r": None},
        {"g": "b", "v": "40", "w": "4", "d": "2026-09-04", "k": "w", "r": None}]


def val(rule, rows=ROWS, **kw):
    return E.run(rule, lambda s: rows, **kw)


@pytest.mark.parametrize("op,want", [("sum", 70), ("avg", 70 / 3), ("min", 10), ("max", 40), ("count", 3)])
def test_leaf_ops_skip_empty_cells_and_count_them(op, want):
    r = val({"op": op, "column": "v"})
    assert r["value"] == pytest.approx(want, abs=1e-5) and r["skipped"] == ({"v": 1} if op != "count" else {"v": 1})


def test_count_without_column_counts_rows_and_latest_first_use_the_order_column():
    assert val({"op": "count"})["value"] == 4
    assert val({"op": "latest", "column": "w", "order_by": "d"})["value"] == 4
    assert val({"op": "first", "column": "w", "period": {"column": "d"}})["value"] == 1


def test_ratio_difference_and_scale():
    ratio = {"op": "ratio", "scale": 100, "numerator": {"op": "sum", "column": "w", "filters": [{"column": "g", "op": "eq", "value": "a"}]},
             "denominator": {"op": "sum", "column": "w"}}
    assert val(ratio)["value"] == 30
    assert val({"op": "difference", "left": {"op": "sum", "column": "w"}, "right": {"op": "sum", "column": "v"}})["value"] == -60
    assert val({"op": "ratio", "numerator": {"op": "sum", "column": "w"}, "denominator": {"op": "sum", "column": "r"}})["cannot"]  # nothing there: cannot, not zero


def test_column_sums_row_by_row_and_an_empty_part_leaves_the_row_out():
    r = val({"op": "sum", "column": "v - w"})
    assert r["value"] == (10 - 1) + (20 - 2) + (40 - 4) and r["skipped"] == {"v": 1}


@pytest.mark.parametrize("flt,want", [({"column": "g", "op": "ne", "value": "a"}, 40), ({"column": "k", "op": "in", "value": ["x", "y"]}, 30),
                                      ({"column": "w", "op": "between", "value": [2, 3]}, 20), ({"column": "r", "op": "not_null"}, 20),
                                      ({"column": "k", "op": "not_in_column", "value": "r"}, 60)])
def test_filters(flt, want):
    assert val({"op": "sum", "column": "v", "filters": [flt]})["value"] == want


def test_period_window_and_strict_end():
    assert val({"op": "sum", "column": "w", "period": {"column": "d", "from": "2026-09-02", "to": "2026-09-03"}})["value"] == 5
    r = val({"op": "sum", "column": "w", "label": "index levels", "period": {"column": "d", "to": "benchmark_end", "strict": True}}, period_end="2026-09-30")
    assert r["value"] is None and r["cannot"] == "index levels missing after 4 Sep"  # a missing figure is None, never zero


def test_group_pick_and_groups_under_five_are_suppressed():
    r = val({"op": "sum", "column": "w", "group_by": "g", "pick": "max"})
    assert r["value"] == 7 and r["groups"] == [] and r["suppressed_groups"] == 2
    big = [{"g": "a" if i < 5 else "b", "w": str(i)} for i in range(11)]
    r = val({"op": "sum", "column": "w", "group_by": "g"}, big)
    assert [x["group_size"] for x in r["groups"]] == [5, 6] and r["suppressed_groups"] == 0


def test_count_groups_having_older_than_business_days():
    rows = [{"a": "p", "d": "2026-09-22"}, {"a": "p", "d": "2026-09-01"}, {"a": "q", "d": "2026-09-11"}, {"a": "q", "d": "2026-09-10"}]
    rule = {"op": "count", "group_by": "a", "having": {"column": "d", "older_than_business_days": 5}}
    assert val(rule, rows)["value"] == 1  # q's newest is 11 Sep, before 15 Sep
    assert val({"op": "count", "group_by": "a"}, rows)["value"] == 2


def test_no_rows_for_a_source_cannot_be_worked_out():
    assert E.run({"op": "sum", "column": "v", "source": "s"}, lambda s: None)["cannot"]


def test_columns_of_and_terms():
    assert E.terms("a - b + c") == [(1, "a"), (-1, "b"), (1, "c")]
    n = {"op": "ratio", "numerator": {"op": "sum", "column": "a - b", "filters": [{"column": "k", "op": "not_in_column", "value": "r"}]},
         "denominator": {"op": "count", "group_by": ["x", "y"]}}
    assert E.columns_of(n) == {"a", "b", "k", "r", "x", "y"}
