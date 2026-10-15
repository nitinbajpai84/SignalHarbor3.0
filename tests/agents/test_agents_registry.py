import pytest

from sh_platform.agents.registry import MIN_GROUP, ToolRefused, ToolRegistry

REFUSAL = "That tool is not available."


def _reg(gate):
    r = ToolRegistry(gate)
    r.register("m1", "count_things", lambda kind: {"total": 12, "group_size": 9},
               read_only=True, description="Count things", parameters={"kind": "which kind"})
    return r


def test_min_group_is_five():
    assert MIN_GROUP == 5


def test_egress_constant_matches_if_present():
    agg = pytest.importorskip("sh_platform.egress.aggregates")
    assert agg.MIN_GROUP == MIN_GROUP


def test_non_read_only_refused_at_registration(gate):
    r = ToolRegistry(gate)
    for flag in (False, None, 1, "yes"):
        with pytest.raises(ToolRefused):
            r.register("m1", "w", lambda: {}, read_only=flag, description="d", parameters={})


def test_listing_requires_gate(gate):
    r = _reg(gate)
    assert [t["name"] for t in r.tools_for("acme", "m1")] == ["count_things"]
    assert r.tools_for("gamma", "m1") == []  # company without the module
    assert r.tools_for("acme", "m2") == []


def test_gate_rechecked_on_every_call(gate):
    r = _reg(gate)
    assert r.call("acme", "m1", "count_things", {"kind": "a"})["total"] == 12
    gate.on.discard(("acme", "m1"))  # switched off between two calls
    with pytest.raises(ToolRefused, match=REFUSAL):
        r.call("acme", "m1", "count_things", {"kind": "a"})


def test_unknown_and_switched_off_share_one_message(gate):
    r = _reg(gate)
    with pytest.raises(ToolRefused) as a:
        r.call("acme", "m1", "nope", {})
    with pytest.raises(ToolRefused) as b:
        r.call("gamma", "m1", "count_things", {"kind": "a"})
    with pytest.raises(ToolRefused) as c:
        r.call("acme", "m2", "count_things", {"kind": "a"})  # not owned by m2
    assert str(a.value) == str(b.value) == str(c.value) == REFUSAL


@pytest.mark.parametrize("args", [{}, {"kind": "a", "extra": 1}, {"other": 1}])
def test_argument_names_validated(gate, args):
    with pytest.raises(ToolRefused):
        _reg(gate).call("acme", "m1", "count_things", args)


def _one(gate, result):
    r = ToolRegistry(gate)
    r.register("m1", "t", lambda: result, read_only=True, description="d", parameters={})
    return r


@pytest.mark.parametrize("bad", [
    {"rows": [1], "group_size": 9},
    {"nested": {"records": []}, "group_size": 9},
    {"items": [{"a": i} for i in range(51)], "group_size": 9},
])
def test_raw_rows_refused(gate, bad):
    with pytest.raises(ToolRefused, match="raw rows"):
        _one(gate, bad).call("acme", "m1", "t", {})


def test_fifty_dicts_still_allowed(gate):
    items = [{"a": i, "group_size": 9} for i in range(50)]
    out = _one(gate, {"items": items, "group_size": 9}).call("acme", "m1", "t", {})
    assert len(out["items"]) == 50 and out["items"][3]["a"] == 3


def test_group_under_five_unavailable(gate):
    assert _one(gate, {"total": 3, "group_size": 4}).call("acme", "m1", "t", {}) == {"available": False}
    nested = _one(gate, {"a": {"total": 3, "group_size": 1}, "group_size": 9}).call("acme", "m1", "t", {})
    assert nested["a"] == {"available": False}
    assert _one(gate, {"total": 3, "group_size": 5}).call("acme", "m1", "t", {})["total"] == 3


def test_result_must_be_json_safe(gate):
    with pytest.raises(ToolRefused):
        _one(gate, {"x": object(), "group_size": 9}).call("acme", "m1", "t", {})


def test_outside_flag(gate):
    r = ToolRegistry(gate)
    r.register("m1", "web", lambda: {"text": "hi"}, read_only=True, description="d",
               parameters={}, outside=True)
    assert r.is_outside("m1", "web") and not r.is_outside("m1", "other")


def test_duplicate_registration_refused(gate):
    r = _reg(gate)
    with pytest.raises(ValueError):
        r.register("m1", "count_things", lambda kind: {}, read_only=True, description="d",
                   parameters={"kind": "k"})


@pytest.mark.parametrize("bad", [
    {"total": 3}, {"total": 3, "group_size": 0}, {"total": 3, "group_size": "9"},
    {"total": 3, "group_size": True}, {"total": 3.5, "group_size": None}, 7,
])
def test_numeric_aggregate_without_valid_group_fails_closed(gate, bad):
    assert _one(gate, bad).call("acme", "m1", "t", {}) == {"available": False}


def test_non_numeric_and_id_fields_need_no_group(gate):
    out = _one(gate, {"fields": ["a", "b"], "table_id": 4, "name": "x"}).call("acme", "m1", "t", {})
    assert out["fields"] == ["a", "b"]


def test_children_need_their_own_group(gate):
    out = _one(gate, {"group_size": 9, "by_region": {"north": 2, "south": 7}}).call("acme", "m1", "t", {})
    assert out == {"group_size": 9, "by_region": {"available": False}}
    out = _one(gate, {"group_size": 9, "by_region": {"north": {"n": 2, "group_size": 2},
                                                     "south": {"n": 7, "group_size": 7}}}
               ).call("acme", "m1", "t", {})
    assert out["by_region"]["north"] == {"available": False} and out["by_region"]["south"]["n"] == 7
    assert "2" not in str(out)


@pytest.mark.parametrize("key", ["Rows", "RECORDS", "data rows", "dataRows", "raw-records"])
def test_raw_keys_case_insensitive(gate, key):
    with pytest.raises(ToolRefused, match="raw rows"):
        _one(gate, {key: [], "group_size": 9}).call("acme", "m1", "t", {})


@pytest.mark.parametrize("big", [["a"] * 51, [[1]] * 51, [{"a": 1}] * 51, ["x"] * 40 + [[1]] * 11])
def test_long_lists_of_structures_refused(gate, big):
    with pytest.raises(ToolRefused, match="raw rows"):
        _one(gate, {"items": big, "group_size": 9}).call("acme", "m1", "t", {})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_refused(gate, bad):
    with pytest.raises(ToolRefused):
        _one(gate, {"total": bad, "group_size": 9}).call("acme", "m1", "t", {})


@pytest.mark.parametrize("probe", [
    {"group_size": 9, "by_region": [["north", 2], ["south", 7]]},
    {"group_size": 9, "m": [[2, 7]]},
    {"group_size": 9, "by_region": [2, 7]},
    {"group_size": 9, "by_region": ["2", "7"]},
])
def test_numbers_inside_lists_are_unavailable(gate, probe):
    out = _one(gate, probe).call("acme", "m1", "t", {})
    key = next(k for k in out if k != "group_size")
    assert out[key] == {"available": False} and out["group_size"] == 9


def test_bare_list_of_numbers_unavailable(gate):
    assert _one(gate, [2, 7]).call("acme", "m1", "t", {}) == {"available": False}


def test_lists_of_names_and_grouped_dicts_stay_allowed(gate):
    res = {"group_size": 9, "fields": ["a", "b"],
           "by": [{"n": 7, "group_size": 7}, {"n": 2, "group_size": 2}]}
    out = _one(gate, res).call("acme", "m1", "t", {})
    assert out["fields"] == ["a", "b"] and out["by"] == [{"n": 7, "group_size": 7}, {"available": False}]


@pytest.mark.parametrize("bad", [{"total": "2"}, {"total": "3.5"}, {"total": "1,200", "group_size": 3}, "5"])
def test_numeric_strings_are_figures(gate, bad):
    assert _one(gate, bad).call("acme", "m1", "t", {}) == {"available": False}


def test_numeric_string_with_group_is_kept(gate):
    assert _one(gate, {"total": "3.5", "group_size": 9}).call("acme", "m1", "t", {})["total"] == "3.5"
