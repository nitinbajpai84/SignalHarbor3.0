"""M1-P01 state machine. Ported behaviour (old tests/test_intent_sessions.py): the session walks every state in
order and ends closed; a closed session cannot move again. Reshaped to the new flow (spec M1-03 to M1-30)."""
import itertools

import pytest

from modules.m1_intent.domain.states import ALLOWED, STATES, IllegalMove, can_move, move

FLOW = ["draft", "lobby", "briefing", "private_rooms", "board", "together", "signing", "closed"]


def test_states_are_the_stages_in_order_plus_paused():
    assert list(STATES) == FLOW[:-1] + ["paused", "closed"]


def test_walks_every_state_in_order_to_closed():  # ported: test_advance_walks_every_state_in_order
    s = {"state": "draft", "paused_from": None}
    for expected in FLOW[1:]:
        s = move(s, expected)
        assert s["state"] == expected


def _expected(frm: str, to: str) -> bool:
    forward = {(a, b) for a, b in zip(FLOW, FLOW[1:])}
    pause = {(f, "paused") for f in FLOW[1:-1]}  # any started stage that is not closed
    return (frm, to) in forward | pause | {("signing", "together")}  # the approver can send it back


@pytest.mark.parametrize("frm,to", list(itertools.product(STATES, STATES)))
def test_every_pair_is_allowed_or_refused_as_the_table_says(frm, to):
    if frm == "paused":
        assert not can_move("paused", to, paused_from=None)  # nowhere to resume to
        assert can_move("paused", to, paused_from="board") == (to == "board")
        return
    assert can_move(frm, to) == _expected(frm, to)
    assert ALLOWED[frm] == tuple(t for t in STATES if _expected(frm, t))


def test_refused_move_names_the_stage_in_plain_words():
    with pytest.raises(IllegalMove) as e:
        move({"state": "draft", "paused_from": None}, "board")
    assert "draft" not in str(e.value) and "cannot" in str(e.value).lower()


def test_pause_remembers_where_it_stopped_and_resume_goes_back_there():
    s = move({"state": "together", "paused_from": None}, "paused")
    assert (s["state"], s["paused_from"]) == ("paused", "together")
    with pytest.raises(IllegalMove):
        move(s, "signing")  # a paused session resumes at the same stage, nowhere else
    s = move(s, "together")
    assert (s["state"], s["paused_from"]) == ("together", None)


def test_closed_is_final_and_input_is_not_changed():
    s = {"state": "closed", "paused_from": None}
    for to in STATES:
        with pytest.raises(IllegalMove):
            move(s, to)
    d = {"state": "draft", "paused_from": None}
    move(d, "lobby")
    assert d["state"] == "draft"
