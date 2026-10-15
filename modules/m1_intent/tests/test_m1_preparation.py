"""M1-01 and M1-02: preparation values. Limits, presets, templates all come from the contract files."""
import shutil
from pathlib import Path

import pytest
import yaml

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.preparation import Offers, PrepError, clean, default_preparation, default_split

NOBODY = Offers(practice=False, problem_library=False)
EVERYTHING = Offers(practice=True, problem_library=True)


def kit(dir=None):
    return C.load_session_settings(dir), C.load_charter_templates(dir)


def make(raw=None, base=None, offers=NOBODY, dir=None):
    s, t = kit(dir)
    return clean(raw or {}, base if base is not None else default_preparation(s, t), s, t, offers)


def test_defaults_come_from_the_contract_and_are_a_solo_session():
    p = make({"purpose": "Why do renewals slip?"})
    s, t = kit()
    assert p["seats"] == s.seats_min == 1
    assert p["length_minutes"] == s.default_length_minutes
    assert sum(p["split"].values()) == p["length_minutes"]
    assert p["charter_template"] == t.default_id
    assert (p["north_industry_practice"], p["north_problem_library"]) == (False, False)


@pytest.mark.parametrize("seats", [0, 11, -1, 100])
def test_seats_outside_one_to_ten_are_refused_in_plain_words(seats):  # M1-02
    with pytest.raises(PrepError) as e:
        make({"purpose": "x", "seats": seats})
    assert "1" in e.value.message and "10" in e.value.message and e.value.field == "seats"


@pytest.mark.parametrize("seats", ["3", 2.5, True, None])
def test_seats_must_be_a_whole_number(seats):
    with pytest.raises(PrepError):
        make({"purpose": "x", "seats": seats})


@pytest.mark.parametrize("seats", [1, 2, 10])
def test_seats_in_range_are_accepted(seats):
    assert make({"purpose": "x", "seats": seats})["seats"] == seats


def test_split_must_add_up_to_the_length_and_the_message_says_so():  # M1-02
    with pytest.raises(PrepError) as e:
        make({"purpose": "x", "length_minutes": 30, "split": {"briefing": 5, "individual": 10, "together": 10}})
    assert "add up" in e.value.message and "30" in e.value.message and e.value.field == "split"


def test_changing_the_length_without_a_split_recomputes_the_default_split():
    p = make({"purpose": "x", "length_minutes": 30})
    assert sum(p["split"].values()) == 30 and all(v >= 1 for v in p["split"].values())
    assert default_split(5, kit()[0]) == {"briefing": 1, "individual": 2, "together": 2}


def test_a_client_that_sends_the_new_length_with_the_old_default_split_gets_the_scaled_split():
    old = default_preparation(*kit())["split"]                       # the 20-minute 4/8/8
    p = make({"purpose": "x", "length_minutes": 30, "split": old})   # used to be refused (422) as adding up to 20
    assert p["split"] == {"briefing": 6, "individual": 12, "together": 12}
    mine = {"briefing": 10, "individual": 10, "together": 10}
    assert make({"purpose": "x", "length_minutes": 30, "split": mine})["split"] == mine   # a split the person chose is kept


def test_every_part_needs_at_least_the_contract_minimum():
    with pytest.raises(PrepError):
        make({"purpose": "x", "length_minutes": 10, "split": {"briefing": 0, "individual": 5, "together": 5}})


def test_presets_and_custom_length():
    assert kit()[0].time_presets == (5, 10, 20, 30)
    assert make({"purpose": "x", "length_minutes": 45})["length_minutes"] == 45  # custom
    for bad in (4, 121, "20", True):
        with pytest.raises(PrepError):
            make({"purpose": "x", "length_minutes": bad})


def test_purpose_is_required_and_text_is_capped_and_clean():
    for bad in ("", "   ", None, 5, "x" * 501, "bad\x00text"):
        with pytest.raises(PrepError):
            make({"purpose": bad})
    assert make({"purpose": "  keep me  "})["purpose"] == "keep me"


def test_unknown_keys_and_unknown_template_are_refused():
    with pytest.raises(PrepError):
        make({"purpose": "x", "state": "closed"})
    with pytest.raises(PrepError):
        make({"purpose": "x", "charter_template": "no-such-template"})


def test_north_offers_follow_the_pack():
    with pytest.raises(PrepError) as e:
        make({"purpose": "x", "north_industry_practice": True})  # a pack with nothing to offer
    assert "industry" in e.value.message.lower()
    p = make({"purpose": "x", "north_industry_practice": True, "north_problem_library": True}, offers=EVERYTHING)
    assert p["north_industry_practice"] and p["north_problem_library"]
    with pytest.raises(PrepError):
        make({"purpose": "x", "north_problem_library": "yes"}, offers=EVERYTHING)


def test_briefing_video_is_one_of_the_contract_options():
    assert make({"purpose": "x", "briefing_video": "none"})["briefing_video"] == "none"
    with pytest.raises(PrepError):
        make({"purpose": "x", "briefing_video": "movie.mp4"})


def test_approver_is_free_text_and_never_checked_for_a_title():  # D-014
    p = make({"purpose": "x", "approver_name": "Chief Anybody"})
    assert p["approver_name"] == "Chief Anybody" and p["approver_account_id"] is None
    with pytest.raises(PrepError):
        make({"purpose": "x", "approver_name": "n" * 121})


def test_a_change_of_contract_file_changes_the_behaviour(tmp_path):
    """Presets, limits and templates are read from the contract: edit a temp copy, the rules follow."""
    copy = tmp_path / "contracts"
    shutil.copytree(C.DEFAULT_DIR, copy)
    f = copy / "intent_session.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    data["seats"]["max"] = 4
    data["time_presets_minutes"] = [7, 14]
    f.write_text(yaml.safe_dump(data), encoding="utf-8")
    t = copy / "charter_templates.yaml"
    tdata = yaml.safe_load(t.read_text(encoding="utf-8"))
    tdata["templates"].append({"id": "extra", "name": "Extra", "description": "d", "columns": ["problem"]})
    t.write_text(yaml.safe_dump(tdata), encoding="utf-8")
    assert make({"purpose": "x", "seats": 4}, dir=copy)["seats"] == 4
    with pytest.raises(PrepError):
        make({"purpose": "x", "seats": 5}, dir=copy)  # over the new limit
    assert kit(copy)[0].time_presets == (7, 14)
    assert make({"purpose": "x", "charter_template": "extra"}, dir=copy)["charter_template"] == "extra"
    assert Path(C.DEFAULT_DIR, "intent_session.yaml").read_text(encoding="utf-8") != f.read_text(encoding="utf-8")


def test_a_broken_contract_is_refused_with_a_plain_message(tmp_path):
    (tmp_path / "intent_session.yaml").write_text("seats: nonsense", encoding="utf-8")
    shutil.copy(Path(C.DEFAULT_DIR, "charter_templates.yaml"), tmp_path)
    with pytest.raises(C.ContractError) as e:
        C.load_session_settings(tmp_path)
    assert "intent_session.yaml" in str(e.value)
