"""Sources as rows (one per system or file) and hops that lose nothing: the catalogue and the process map read these."""
import pytest
from m2_kit import login
from test_m2_answers import save
from test_m2_requests_kit import seed, send, token_of, visitor

from modules.m2_baseline.domain.questionnaire import source_rows


@pytest.fixture
def tom(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Tom Reyes"]
    return org, visitor(world, token_of(sent)), sent


ROWS = [{"name": "Performance workbook", "kind": "excel", "structure": "structured", "lands": "Investments share", "owner": "Tom Reyes",
         "connection": "manual_entry", "frequency": "quarterly", "sla": "", "tables": "Fund returns, Benchmark levels", "fields": ["period_return"],
         "personal": "no"},
        {"name": "Vendor API", "kind": "api", "structure": "both", "sla": {"value": "by 18:00", "mark": "guessed"}, "personal": "not_sure"}]


def test_sources_are_rows_each_cell_a_provenance_value_and_blank_is_an_unknown_cell(tom):
    rec = save(tom[1], answers={"sources": {"value": ROWS, "mark": "stated"}})["saved"]
    first, second = rec["sources"]["value"]
    assert first["kind"]["value"] == "excel" and first["tables"]["value"] == ["Fund returns", "Benchmark levels"]
    assert first["fields"]["value"] == ["period_return"]
    assert first["sla"]["mark"] == "unknown" and first["sla"]["value"] is None and first["name"]["by"] == "Tom Reyes"
    assert second["sla"]["mark"] == "guessed" and second["lands"]["mark"] == "unknown" and second["personal"]["value"] == "not_sure"
    assert (rec["source"]["value"], rec["data_type"]["value"]) == ("Performance workbook; Vendor API", "both")  # the old questions follow the rows
    assert rec["arrival"]["value"] == "Performance workbook: Quarterly; Vendor API: by 18:00"


@pytest.mark.parametrize("rows", [[], [{"kind": "excel"}], [{"name": "A", "kind": "spreadsheet"}], ["A"],
                                  [{"name": {"value": "A", "mark": "sure"}}]])
def test_a_source_row_that_does_not_fit_is_refused_in_plain_words(tom, rows):
    r = save(tom[1], answers={"sources": {"value": rows, "mark": "stated"}}, status=422)
    assert r["field"] == "sources" and r["message"]


@pytest.mark.parametrize("cell", [["excel"], {"value": {"a": 1}, "mark": "stated"}, {"value": ["excel"], "mark": "stated"}, 7])
def test_a_choice_cell_that_is_not_text_is_a_422_not_a_crash(tom, cell):
    r = save(tom[1], answers={"sources": {"value": [{"name": "A", "kind": cell}], "mark": "stated"}}, status=422)
    assert r["field"] == "sources" and r["message"]


@pytest.mark.parametrize("hop", [{"who": "Tom", "what": {"a": 1}}, {"who": "Tom", "what": "x", "team": ["Ops"]}, {"who": ["Tom"], "what": "x"}])
def test_a_hop_whose_words_are_not_text_is_refused_not_stringified(tom, hop):
    r = save(tom[1], answers={"upstream": {"value": [hop], "mark": "stated"}}, status=422)
    assert r["field"] == "upstream" and r["message"]


def test_a_source_row_naming_an_unknown_key_is_refused_by_that_key(tom):
    r = save(tom[1], answers={"sources": {"value": [{"name": "A", "colour": "red"}], "mark": "stated"}}, status=422)
    assert "colour" in r["message"]


def test_i_dont_know_is_valid_for_the_whole_list_of_sources(tom):
    rec = save(tom[1], answers={"sources": {"value": None, "mark": "unknown"}})["saved"]
    assert rec["sources"]["mark"] == "unknown" and rec["sources"]["value"] is None


def test_what_and_step_are_the_same_words_on_any_hop_and_nothing_is_dropped(tom):
    hops = {"in_between": {"value": [{"who": "Tom", "what": "Pastes it in", "team": "Investments", "order": "3"}], "mark": "stated"},
            "upstream": {"value": [{"who": "Bank", "step": "Sends the file", "order": 1}], "mark": "stated"}}
    rec = save(tom[1], answers=hops)["saved"]
    assert rec["in_between"]["value"] == [{"who": "Tom", "team": "Investments", "step": "Pastes it in", "order": 3, "manual": False}]
    assert rec["upstream"]["value"] == [{"who": "Bank", "what": "Sends the file", "order": 1}]


@pytest.mark.parametrize("hop", [{"who": "Tom", "what": "x", "colour": "red"}, {"who": "Tom", "what": "x", "order": "soon"},
                                 {"who": "Tom", "what": "x", "order": 0}, {"who": "Tom", "what": "x", "order": 100}])
def test_a_hop_with_an_unknown_key_or_a_bad_step_number_is_a_422_that_names_it(tom, hop):
    r = save(tom[1], answers={"in_between": {"value": [hop], "mark": "stated"}}, status=422)
    assert r["field"] == "in_between" and ("colour" in r["message"] or "step number" in r["message"])


def test_an_old_single_source_answer_reads_as_one_guessed_row():
    old = {"owner_name": "Tom", "source": {"value": "Bank portal", "mark": "stated", "by": "Tom", "from": "q", "at": "t"},
           "data_type": {"value": "structured", "mark": "stated", "by": "Tom", "from": "q", "at": "t"}}
    (row,) = source_rows(old)
    assert row["name"]["value"] == "Bank portal" and row["name"]["mark"] == "guessed" and row["structure"]["value"] == "structured"
    assert source_rows({"owner_name": "Tom", "source": {"value": None, "mark": "unknown"}}) == []
