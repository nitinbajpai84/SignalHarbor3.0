import pytest

from sh_platform.agents.guard import NOT_AVAILABLE, check_numbers

F = [{"id": "a", "label": "x", "value": 1200, "group_size": 9},
     {"id": "b", "label": "y", "value": "12.5%", "group_size": 9},
     {"id": "c", "label": "z", "value": 7, "group_size": 9},
     {"id": "d", "label": "small", "value": 41, "group_size": 4}]


def test_traced_number_kept():
    r = check_numbers("There are 1,200 items and 7 teams.", F)
    assert r.text == "There are 1,200 items and 7 teams." and r.replaced == 0 and r.ok


def test_invented_number_replaced_and_named():
    r = check_numbers("There are 99 items.", F)
    assert r.text == f"There are {NOT_AVAILABLE} items." and r.replaced == 1 and r.missing == ["99"]
    assert not r.ok


def test_group_under_five_does_not_count():
    assert check_numbers("Total 41.", F).missing == ["41"]


def test_fact_without_group_size_does_not_count():
    assert check_numbers("Total 5.", [{"id": "q", "label": "l", "value": 5}]).missing == ["5"]


@pytest.mark.parametrize("text,missing", [
    ("Up 12.5% this month", []), ("Up 12.6% this month", ["12.6%"]),
    ("It is 1200 or 1,200", []), ("It is 1,201", ["1,201"]), ("Score 7.0", []),
])
def test_percent_decimal_separator(text, missing):
    assert check_numbers(text, F).missing == missing


def test_ids_dates_ordinals_question_ignored():
    text = "1. See D-013 and K07 on 2026-10-03 in 2026.\n2) Also 55 as you asked."
    r = check_numbers(text, F, question="why is it 55?")
    assert r.missing == [] and r.text == text


def test_multiple_missing_listed():
    r = check_numbers("8 then 9 then 8", F)
    assert r.missing == ["8", "9"] and r.replaced == 3


def test_number_words_are_out_of_scope():
    assert check_numbers("There are twelve of them.", F).replaced == 0


@pytest.mark.parametrize("text,missing", [
    ("Cost USD4500", ["4500"]), ("EUR1200 paid", []), ("Rs4500 due", ["4500"]), ("x99 units", ["99"]),
    ("T1000 units", ["1000"]), ("See [99]", ["99"]), ("[D-013] ok", []),
    ("We have 1999 customers", ["1999"]), ("We have 2026 customers", ["2026"]),
    ("Founded in 1999.", []), ("Since 2020, up", []), ("In FY2026 and Q3 2026", []),
    ("by October 2026", []), ("Up -1,200 now", ["-1,200"]), ("Down 12.5% to 7", []),
    ("range 7-1200", []), ("Q3 results", []),
])
def test_b3_rules(text, missing):
    assert check_numbers(text, F).missing == missing


def test_sign_must_match():
    f = [{"id": "n", "label": "net", "value": -1200, "group_size": 9}]
    assert check_numbers("Net -1,200", f).missing == []
    assert check_numbers("Net 1,200", f).missing == ["1,200"]


def test_tool_figures_style_fact_ids_dont_matter():
    assert check_numbers("Total 5", [{"id": "tool:x", "label": "t", "value": 5, "group_size": 5}]).ok


@pytest.mark.parametrize("text,missing", [
    ("grew by 2000 units", ["2000"]), ("rose by 1950", ["1950"]), ("in 1999 cases", ["1999"]),
    ("until 2050 orders", ["2050"]), ("Q3 2050 units", ["2050"]), ("March 2000 orders", ["2000"]),
    ("in 1999 clients", ["1999"]), ("in 1999 was strong", []), ("in 1999 and 2000", ["2000"]),
    ("Sales-4500", ["4500"]), ("Revenue-2050", ["2050"]), ("D-013 P1-02 A-001 K7-12", []),
    ("On 3 March 2025 we met", []), ("On March 3, 2025 we met", []), ("on 3rd March 2025", []),
    ("March 2025 was calm", []), ("since 2020 on Monday", []),
])
def test_r2_r3_r4(text, missing):
    assert check_numbers(text, F).missing == missing


def test_kp2_drafted_brief_lines_are_left_whole_for_the_caller_to_check():
    """KP-2: North's drafted brief lines (sow_patch, process_steps) were blanked mid-sentence: "Retain the feasibility-check result for not
    available yet years", "ready by not available yet:not available yet". The caller (i6_chat.ungrounded) keeps or leaves out each line whole."""
    import json
    from sh_platform.agents.guard import unblank
    reply = json.dumps({"reply": "I drafted 37 lines.", "sow_patch": {"governance": [{"rule": "Retain the feasibility-check result for 7 years"}],
                        "process": {"steps": [{"control": "Note must be ready by 08:00"}]}}, "process_steps": [{"name": "Hold", "does": "Hold calls over 500,000"}]})
    g = check_numbers(reply, [], "")
    got = json.loads(g.text)
    assert got["sow_patch"]["governance"][0]["rule"] == "Retain the feasibility-check result for 7 years"
    assert got["sow_patch"]["process"]["steps"][0]["control"] == "Note must be ready by 08:00" and got["process_steps"][0]["does"] == "Hold calls over 500,000"
    assert got["reply"] == "I drafted not available yet lines." and g.replaced == 1  # the reply the person reads is still checked
    cut = reply[:reply.index("7 years") + 8]  # a reply cut short inside the draft has no whole draft: no exemption
    assert "not available yet" in check_numbers(cut, [], "").text.split('"sow_patch"')[1]
    assert unblank("Retain the feasibility-check result for not available yet years") == "Retain the feasibility-check result"
    assert unblank("Note must be ready by not available yet:not available yet") == "Note must be ready"
    assert unblank("Keep 7 years") == "Keep 7 years"
