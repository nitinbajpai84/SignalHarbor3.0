"""Self-check of the checker fixes of cycle 1 (docs/test/TRIAGE-cycle-1.md, package C). No server: `pytest tools/verify_10uc/test_checkers.py`.
The rest of each fix is proved by running the checker against a freshly seeded server (the triage note names the run)."""
import http.cookiejar
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "e2e_10uc"))

import uc1  # noqa: E402
import uc3  # noqa: E402
import uc6  # noqa: E402
import uc7  # noqa: E402
import ui_copy  # noqa: E402


def test_a1_10_same_instant_not_same_text():
    assert uc1.same_instant("2026-10-03T10:30:00Z", "2026-10-03T18:30:00+08:00")
    assert not uc1.same_instant("2026-10-03T10:30:00Z", "2026-10-03T18:31:00+08:00")
    assert not uc1.same_instant("2026-10-03T10:30:00", "2026-10-03T10:30:00")  # no zone: not comparable
    assert not uc1.same_instant(None, "2026-10-03T10:30:00Z")


def test_a1_12_csrf_token_comes_from_the_cookie():
    jar = http.cookiejar.CookieJar()
    jar.set_cookie(http.cookiejar.Cookie(0, "sh_csrf", "tok123", None, False, "127.0.0.1", False, False, "/", True, False, None, False, None, None, {}))
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    assert uc1.csrf_of(op) == "tok123"
    assert uc1.csrf_of(urllib.request.build_opener()) == ""


def test_a1_11_liquid_book_line_found_under_either_name():
    lines = {"Evergreen Liquid Book": {"issued": "41200000"}}
    assert uc1.line_of(lines, "Liquid book")["issued"] == "41200000"
    assert uc1.line_of(lines, "Evergreen Liquid Book")["issued"] == "41200000"


def test_a3_1_pending_and_confirmed_rows_collapse():
    v = [Decimal("10000000.00"), Decimal("10180000.00000000"), Decimal("10180000.00")]
    assert uc3.distinct_steps(v) == [Decimal("10000000"), Decimal("10180000")]


def test_a6_1_a7_3_confirmed_october_calls_count_as_called():  # answer key P24 and its item 3
    c = {x["fund"]: x for x in uc6.U["commitments"]}
    assert uc6.called_now(c["C"]) == Decimal("4050000")
    assert uc6.called_now(c["D"]) == Decimal("4750000")
    assert uc6.called_now(c["E"]) == Decimal(c["E"]["called_to_date"])  # Fund E's notice is not confirmed
    assert sum(Decimal(x["commitment_amount"]) - uc6.called_now(x) for x in c.values() if x["legal_entity"] == "EG-B") == Decimal("8200000")


def test_a6_11_capital_call_case_title_may_name_the_fund():
    assert uc6.is_call_case({"title": "Fund the capital call"})
    assert uc6.is_call_case({"title": "Fund the capital call: Cedarpoint Ventures III, Entity B, due 20 Oct 2026"})
    assert not uc6.is_call_case({"title": "Cash differs"})


def test_a7_0_document_preview_may_be_a_table():
    assert uc7.prev("45 days") == "45 days"
    assert "auditor" in uc7.prev({"heading": "auditor change", "columns": ["a"]})
    assert uc7.prev(None) == ""


def test_journeys_read_refusal_and_bars_from_the_ui():
    assert ui_copy.REFUSED in (ui_copy.UI / "shell" / "copy.ts").read_text(encoding="utf-8")
    for role in ("sponsor", "approver", "participant", "analyst", "company_admin"):
        assert "Map" in ui_copy.bar_for(role)  # every role has the Map (roles.ts, 9 Oct)
    assert "Build" not in ui_copy.bar_for("sponsor") and "Build" in ui_copy.bar_for("analyst")
