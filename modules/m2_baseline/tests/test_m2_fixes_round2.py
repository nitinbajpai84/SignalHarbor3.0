"""Round-2 fixes N6 to N10, P5 and N12 for module 2: one source per system however it is spelled, the owner's connection words kept,
the process map's dashed steps, reworded nouns and twice-told steps, the capital-call and exposure suggestions, the column matcher,
and the model calls run in order on a small pool. Family-office example content only, synthetic."""
import threading
import time
from pathlib import Path

import yaml
from story_answers import answer, hop, kpis, row

from modules.m2_baseline.agent import lens
from modules.m2_baseline.agent import pack_text as P
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain.catalogue import text_of as t

PACK = Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1"


def names(cat):
    return {t(r["Source name"]): r for r in cat["sources"]}


def spelled_two_ways():
    """Arjun and Tom name the same three systems differently; the custodian, the administrator and the mailbox are spelled alike."""
    return [
        answer("a1", "Arjun Rao", "K01", sources=[
            row("Performance workbook (Excel)", "excel", "structured", "Investments share", "Arjun Rao", "download", "quarterly", "", "Fund returns"),
            row("Market data vendor API (Bloomberg Data License)", "api", "structured", "", "", "download", "daily", "", "Index levels"),
            row("Index provider API (S&P 500 and MSCI World)", "api", "structured", "", "", "download", "daily", "", "S&P 500 levels"),
            row("Northgate custodian daily file", "file_drop", "structured", "Finance share", "Arjun Rao", "download", "daily", "", "NGC CSV"),
            row("Bluewater administrator NAV portal", "portal", "structured", "", "", "api", "monthly", "", "NAV report")]),
        answer("a2", "Tom Ng", "K15", sources=[
            row("Performance_Workbook.xlsx", "excel", "structured", "", "", "download", "quarterly", "", "Fund returns"),
            row("Market data vendor API", "api", "structured", "", "", "download", "daily", "", "Index levels"),
            row("Index provider API", "api", "structured", "", "", "download", "daily", "", "S&P 500 levels"),
            row("Managers' statements mailbox", "email", "unstructured", "", "", "email_forward", "ad_hoc", "", "Manager statements")]),
        answer("a3", "Sara Lim", "K04", sources=[
            row("Northgate custodian daily file", "file_drop", "structured", "", "", "file_drop", "daily", "", "NGC CSV"),
            row("Managers' statements mailbox", "email", "unstructured", "capital-calls mailbox", "Sara Lim", "email_forward", "ad_hoc", "", "Call notices")]),
        answer("a4", "Lina Ho", "K18", sources=[row("Pay workbook", "excel", "structured", "HR share", "Lina Ho", "download", "quarterly", "", "Pay review", personal="yes")]),
    ]


# ---- N6: one system under two spellings is one source

def test_the_same_system_under_two_spellings_is_one_source_and_ten_names_become_seven():
    rows = spelled_two_ways()
    raw = {t(r["name"]) for a in rows for r in C.source_rows(a)}
    cat, _ = C.build(None, kpis(), rows)
    assert len(raw) == 10 and len(cat["sources"]) == 7
    got = names(cat)
    assert "Performance workbook (Excel)" in got and "Market data vendor API (Bloomberg Data License)" in got  # the longest name is shown
    assert "Index provider API (S&P 500 and MSCI World)" in got and "Performance_Workbook.xlsx" not in got


def test_matching_drops_the_suffix_the_extension_and_punctuation_and_never_merges_across_kinds():
    assert C.match_name("Performance workbook (Excel)") == C.match_name("Performance_Workbook.xlsx") == "performance workbook"
    assert C.match_name("Index-provider  API") == "index provider api"
    a = answer("x1", "Arjun Rao", "K01", sources=[row("Pay data", "excel", "structured", "", "", "download", "daily", "", "")])
    b = answer("x2", "Tom Ng", "K15", sources=[row("Pay data", "api", "structured", "", "", "api", "daily", "", "")])
    c = answer("x3", "Sara Lim", "K04", sources=[row("Pay data extract", "excel", "structured", "", "", "download", "daily", "", "")])
    cat, _ = C.build(None, kpis(), [a, b])
    assert len(cat["sources"]) == 2  # one name, two kinds: two systems
    cat, _ = C.build(None, kpis(), [a, c])
    assert len(cat["sources"]) == 1 and t(cat["sources"][0]["Source name"]) == "Pay data extract"  # a prefix with the same kind merges
    again, _ = C.build(cat, kpis(), [a, c])
    assert len(again["sources"]) == 1  # a rebuild finds the same row


# ---- N7: the owner's connection answer is kept

def test_the_owners_connection_words_are_kept_and_the_dropdown_word_used_when_it_matches():
    cat, _ = C.build(None, kpis(), spelled_two_ways())
    got = {n: t(r["Connection method"]) for n, r in names(cat).items()}
    assert got["Pay workbook"] == "I download it"  # not a dropdown word: the owner's words, never a default
    assert got["Bluewater administrator NAV portal"] == "API" and got["Managers' statements mailbox"] == "Email forwarded to us"


def test_connection_details_stay_blank_when_none_was_given():  # N7 round 3: they no longer repeat the "lands" text
    cat, _ = C.build(None, kpis(), spelled_two_ways())
    assert t(names(cat)["Pay workbook"]["Where it lands or lives"]) == "HR share"
    assert t(names(cat)["Pay workbook"]["Connection details (no passwords)"]) == ""


def test_a_download_against_a_file_drop_is_a_choice_conflict_on_the_connection_method():
    cat, conflicts = C.build(None, kpis(), spelled_two_ways())
    (c,) = [c for c in conflicts if c["column"] == "Connection method" and c["state"] == "open"]
    assert {(v["by"], v["value"]) for v in c["versions"]} == {("Arjun Rao", "I download it"), ("Sara Lim", "Scheduled file drop")}
    assert C.is_blank(names(cat)["Northgate custodian daily file"]["Connection method"])  # Lens never picks
    # Arjun and Tom, who both say "I download it" for the vendor, agree: no conflict there
    assert not [x for x in conflicts if x["row_id"] == C.row_id("sources", names(cat)["Market data vendor API (Bloomberg Data License)"])
                and x["column"] == "Connection method"]


# ---- N8: the process map

def test_a_step_a_hop_names_to_a_person_who_has_not_answered_is_dashed_even_when_they_own_no_part_of_this_measure():
    k01 = next(k for k in kpis() if k["id"] == "K01")
    mine = [answer("w1", "Arjun Rao", "K01", upstream=[hop("Wei Chen", "Risk", "Works out exposure by issuer", 1)],
                   in_between=[hop("Arjun Rao", "Finance", "Reads the pack", 2)])]
    people = [p["value"] for k in kpis() for p in k["owners"].values()]
    waiting = D.waiting_owners(k01, mine, people)
    assert "Wei Chen" in waiting and "Arjun Rao" not in waiting
    steps = D.draw(mine, None, "pack", None, None, frozenset(), waiting)["steps"]
    wei = steps[0]
    assert wei["lane"] == "Risk" and wei["ask"] == "Wei Chen" and D.mark_of(wei) == "to_confirm" and "ask" not in steps[1]


def test_a_step_said_twice_is_drawn_once_and_lists_both_who_said_it():
    said = lambda i, who: answer(i, who, "K15", in_between=[hop(who, "Investments", "Pastes levels into the workbook", 1),  # noqa: E731
                                                            hop(who, "investments team", "Pastes levels into the workbook.", 2),
                                                            hop(who, "Investments", "Checks the totals", 3)])
    mine = [said("t1", "Tom Ng"), said("m1", "Mei Tan")]
    m = D.draw(mine, None, "pack", None)
    assert [s["text"] for s in m["steps"]] == ["Pastes levels into the workbook", "Checks the totals"]
    v = D.view(m, mine)
    assert v["steps"][0]["owner"] == "Tom Ng and Mei Tan" and [s["order"] for s in v["steps"]] == [1, 2]


def test_fifteen_told_steps_for_seven_real_ones_are_drawn_as_seven():
    texts = ["Publishes index levels", "Sends the positions file", "Files the statements", "Pastes levels into the workbook", "Subtracts the benchmark",
             "Works out exposure", "Reads the committee note"]
    one = lambda i, who, ts: answer(i, who, "K15", in_between=[hop(who, "Investments", x, n) for n, x in enumerate(ts, 1)])  # noqa: E731
    mine = [one("a", "Tom Ng", texts), one("b", "Mei Tan", texts), one("c", "Sara Lim", texts[:1])]
    assert len(D.draw(mine, None, "pack", None)["steps"]) == 7


# ---- N9: suggestions for the capital-call and exposure problems

def guidance():
    return P.Guidance(None, yaml.safe_load((PACK / "kpi_tree.yaml").read_text(encoding="utf-8"))["kpis"],
                      problems=yaml.safe_load((PACK / "problems.yaml").read_text(encoding="utf-8"))["problems"])


def test_the_charter_titles_capital_calls_and_one_exposure_view_get_their_measures():
    g = guidance()
    ids = lambda title: [k["id"] for k in P.kpis_for_problem(g, {"title": title, "library_problem_id": None})]  # noqa: E731
    assert {"K01", "K04", "K05", "K06"} <= set(ids("Capital calls arrive too late"))
    assert {"K09", "K10", "K11"} <= set(ids("No single exposure view"))
    assert ids("Parking") == []


def test_word_stems_fold_plurals_and_endings():
    assert P._stems("calls call exposure exposures exposed") == {"call", "expos"}


# ---- P5: the column matcher

def pack_matching():
    feeds = yaml.safe_load((PACK / "feeds.yaml").read_text(encoding="utf-8"))["feeds"]
    syn = yaml.safe_load((PACK / "column_synonyms.yaml").read_text(encoding="utf-8"))["feeds"]
    return feeds, syn


def test_the_matcher_finds_period_return_benchmark_return_and_nav_date_and_salary_band_only_for_the_pay_measure():
    feeds, syn = pack_matching()
    all_ids = {k["id"] for k in guidance().kpis}
    k_names = {k["id"]: k["name"] for k in guidance().kpis}
    cols = [{"name": c, "type": "string"} for c in ("period_return", "benchmark_return", "nav_date", "salary_band", "valuation_date", "memo")]
    got = C.match_columns(cols, feeds, syn, all_ids, k_names)
    by = {}
    for s in got:
        by.setdefault(s["column"], set()).update(s["kpi_ids"])
    assert {"K15", "K16"} <= by["period_return"] and {"K15", "K16", "K17"} <= by["benchmark_return"]
    assert by["nav_date"] and by["valuation_date"] and "memo" not in by
    assert by["salary_band"] == {"K18"}  # a pay measure and nothing else
    only_open = C.match_columns(cols, feeds, syn, all_ids - {"K18"}, {k: n for k, n in k_names.items() if k != "K18"})
    assert "salary_band" not in {s["column"] for s in only_open}  # a measure the asker may not see is never suggested


# ---- N12: model calls on a small pool keep their order

def test_run_in_order_keeps_the_order_whichever_call_finishes_first_and_runs_two_at_a_time():
    live, peak, lock = 0, 0, threading.Lock()

    def slow_first(i):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep((6 - i) * 0.01)  # the first items finish last
        with lock:
            live -= 1
        return i * i
    assert lens.run_in_order(slow_first, list(range(6))) == [0, 1, 4, 9, 16, 25] and peak == 2
