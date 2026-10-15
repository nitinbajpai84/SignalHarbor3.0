"""W2F4: one clock. The box, the stage and the home card read the same words; a Decision has one deadline."""
from datetime import datetime, timezone

from sh_platform.intents import clock, home

UTC = timezone.utc
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)  # a Wednesday


def d(day, hour=12):
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def rec(kind="decision", state="open", ends=9, stage_due=8):
    return {"type": kind, "state": state, "time_box": {"starts": d(5).isoformat(), "ends": d(ends, 9).isoformat()},
            "stages": [{"key": "options", "opened_at": d(5).isoformat(), "due": d(stage_due, 9).isoformat()}]}


def test_overdue_hours_never_beside_days_left():
    c = clock.clock(d(5), d(7, 6), NOW)
    assert c["state"] == "overdue" and c["words"] == "Overdue by 6 hours"
    assert clock.clock(d(5), d(12), NOW)["words"] == "3 days left"  # Friday 12:00 is 2.5 working days away


def test_never_zero_days_left_while_time_remains():
    c = clock.clock(d(5), d(7, 13), NOW)
    assert c["words"] == "1 hour left" and c["working_days_left"] == 1


def test_decision_has_one_deadline():
    r = rec()
    assert clock._due(r, r["stages"][0]) == clock.parse(r["time_box"]["ends"])
    assert clock._due({**r, "type": "initiative"}, r["stages"][0]) == clock.parse(r["stages"][0]["due"])


def test_home_card_reads_the_clock_words():
    r = rec()
    words, _, _ = home._days(r, NOW, UTC)
    assert words == clock.clock(d(5), d(9, 9), NOW)["words"]
    assert home._days(rec(state="closed"), NOW, UTC)[0] == "Closed"
    assert home._days(rec(ends=7), d(8), UTC)[0].startswith("Overdue by")
