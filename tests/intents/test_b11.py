"""B11: the Initiative's six start questions and the open check (file 22). Synthetic data only."""
from datetime import date

from sh_platform.intents.initiative import QUESTIONS, add_working_days, check_open, working_days


def cell(value):
    return {"value": value, "mark": "stated", "by": "Janet Shaw", "from": "", "at": "2026-10-07T09:00:00Z"}


def ready() -> dict:
    return {"title": "Faster quarterly client report", "stages": [{"key": "think_unfiltered", "ref": {"kind": "wall_session", "id": "s1"}}],
            "start_answers": {"goal": cell({"line": "Cut the days to produce the quarterly client report", "why": "The family council waits two weeks for it."}),
                              "people": cell({"sponsor": {"account_id": None, "name": "Daniel Kerr"}, "participants": [], "affected": [], "just_me": False}),
                              "build": cell("not_sure"), "definitions": cell("some"), "areas": cell(["Investments"]), "deadline": cell("2026-10-21")}}


def test_six_questions_in_order_all_required():
    assert [q["key"] for q in QUESTIONS] == ["goal", "people", "build", "definitions", "areas", "deadline"]
    assert QUESTIONS[0]["lead"] == "What are you trying to achieve?"
    assert QUESTIONS[5]["lead"] == "When must this be decided by?"
    assert all(q["required"] for q in QUESTIONS)


def test_check_open_names_the_first_missing_item():
    assert check_open(ready()) is None
    i = ready(); i["start_answers"]["goal"]["value"]["why"] = "short"
    assert check_open(i) == "A few words on why will help the people you invite."
    i = ready(); i["start_answers"]["people"]["value"] = {"participants": [], "sponsor": None, "just_me": False}
    assert check_open(i) == "Name the people to involve, or choose Just me for now."
    i["start_answers"]["people"]["value"]["just_me"] = True
    assert check_open(i) is None
    i = ready(); i["start_answers"]["areas"]["value"] = []
    assert check_open(i) == "Pick at least one area."
    i = ready(); i["stages"] = [{"key": "think_unfiltered"}]
    assert check_open(i) == "The wall is not prepared yet. Try again."


def test_working_days_skip_weekends():
    wed = date(2026, 10, 7)
    assert add_working_days(wed, 10) == date(2026, 10, 21)
    assert working_days(wed, date(2026, 10, 21)) == 10
    assert add_working_days(date(2026, 10, 9), 1) == date(2026, 10, 12)  # Friday to Monday


def test_open_record_is_flat_with_the_wall_ref():
    from datetime import timezone
    from sh_platform.intents import lifecycle as L
    from sh_platform.intents.initiative import open_record

    rec = L.new_record("initiative", "ardmore", L.person("acc-janet", "Janet Shaw"), "2026-10-07T09:00:00+00:00")
    rec.update(start_answers=ready()["start_answers"])
    rec["start_answers"]["goal"]["mark"] = "guessed"
    open_record(rec, {"kind": "wall_session", "id": "s1"}, "Faster report", {"text": "Here is what I understood.", "mark": "guessed"},
                "acc-janet", "Janet Shaw", "2026-10-07T09:00:00+00:00", {}, timezone.utc)
    assert rec["state"] == "open"
    assert rec["stages"][0]["key"] == "think_unfiltered" and rec["stages"][0]["ref"] == {"kind": "wall_session", "id": "s1"}
    o = rec["outcome"]
    assert o["kind"] == "initiative" and o["goal"].startswith("Cut the days") and o["build_needed"] == "not_sure" and o["definitions_exist"] == "some"
    assert not any(k in o for k in ("initiative", "problem", "brainstorm"))  # ruling 16: no nesting by type
    assert o["decide_by"] == {"date": "2026-10-21", "working_days": 10}
    assert rec["time_box"]["ends"].startswith("2026-10-21")
    assert rec["start_answers"]["goal"]["mark"] == "guessed"  # the mark survives the open
    assert rec["refs"]["wall_session_ids"] == ["s1"]


def test_a_draft_is_its_creators_alone():
    import pytest
    from sh_platform.intents import lifecycle as L
    from sh_platform.intents.initiative import _draft_of

    rec = L.new_record("initiative", "ardmore", L.person("acc-janet", "Janet Shaw"), "2026-10-07T09:00:00+00:00")
    _draft_of(rec, "acc-janet")
    with pytest.raises(L.Refused) as e:
        _draft_of(rec, "acc-aaron")
    assert e.value.status == 403
    rec["state"] = "open"
    with pytest.raises(L.Refused):
        _draft_of(rec, "acc-janet")
