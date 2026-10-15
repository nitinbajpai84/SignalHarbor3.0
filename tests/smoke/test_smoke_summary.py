"""Smoke: the per-company and per-group counts printed after the pytest summary (brief item 10)."""
import re
from pathlib import Path

from smoke_helpers import GROUPS, NOT_TIED, company_of, group_of, render, tally

P = "tests/smoke/test_smoke_kernel.py::"
FAKE = [
    (P + "test_signin_me_and_menu_per_company[harbor-mutual]", "passed"),
    (P + "test_signin_me_and_menu_per_company[tidewater-capital]", "failed"),
    (P + "test_signin_me_and_menu_per_company[solo-studio]", "passed"),
    (P + "test_module_off_is_refused_by_menu_route_and_tool_and_follows_the_switch[harbor-mutual-False]", "passed"),
    (P + "test_a_user_cannot_steer_the_server_to_another_companys_plane[tidewater-capital-reads-harbor-mutual]", "error"),
    (P + "test_idle_session_gets_401_with_the_briefed_shape", "passed"),
    ("tests/smoke/test_smoke_egress.py::test_internet_is_off_by_default_and_refusals_are_logged", "failed"),
    ("tests/smoke/test_smoke_industry_tree.py::test_ui_copy_has_no_industry_word", "skipped"),
]


def test_a_failure_shows_up_under_its_company_and_its_group():
    by_company, by_group = tally(FAKE)
    assert by_company["harbor-mutual"] == {"passed": 2, "failed": 0, "skipped": 0}
    assert by_company["tidewater-capital"] == {"passed": 0, "failed": 2, "skipped": 0}  # a failure and an error
    assert by_company["solo-studio"] == {"passed": 1, "failed": 0, "skipped": 0}
    assert by_company[NOT_TIED] == {"passed": 1, "failed": 1, "skipped": 1}
    assert by_group["1 sign-in and menu"] == {"passed": 2, "failed": 1, "skipped": 0}
    assert by_group["8 egress"]["failed"] == 1 and by_group["9 no hardcoded industry"]["skipped"] == 1
    assert by_group["5 cross-company"]["failed"] == 1 and by_group["6 expired session"]["passed"] == 1
    assert sum(v["passed"] + v["failed"] + v["skipped"] for v in by_company.values()) == len(FAKE)
    assert sum(v["passed"] + v["failed"] + v["skipped"] for v in by_group.values()) == len(FAKE)


def test_the_printed_line_names_each_company_with_its_counts():
    by_company, _ = tally(FAKE)
    line = render(by_company, ["harbor-mutual", "tidewater-capital", "solo-studio", NOT_TIED])
    assert line.startswith("harbor-mutual 2 passed, 0 failed; tidewater-capital 0 passed, 2 failed; solo-studio 1 passed")
    assert line.endswith(f"{NOT_TIED} 1 passed, 1 failed, 1 skipped")


def test_company_is_read_from_the_test_id_and_windows_paths_work():
    assert company_of(P + "x[harbor-mutual-False]") == "harbor-mutual"
    assert company_of(P + "x[solo-studio-reads-harbor-mutual]") == "solo-studio"  # the first company named
    assert company_of(P + "x") == NOT_TIED
    assert group_of("tests\\smoke\\test_smoke_egress.py::anything") == "8 egress"
    assert group_of(P + "unknown_test_name") == "other"


def test_every_kernel_test_belongs_to_a_numbered_group():
    source = (Path(__file__).parent / "test_smoke_kernel.py").read_text(encoding="utf-8")
    names = set(re.findall(r"^def (test_\w+)\(", source, re.M))
    mapped = {n for ns in GROUPS.values() for n in ns}
    assert names == mapped  # a new kernel test must be added to GROUPS, or the summary would hide it
