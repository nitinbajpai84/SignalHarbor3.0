"""B08: North as the workflow runner (spec 08). The model is a stub; nothing leaves the machine. Synthetic people only."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sh_platform.intents import north as N
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

ORG, SPO, AARON, BEA, OBS = "u-org", "u-spo", "u-aaron", "u-bea", "u-obs"
START = {k: "x" for k in ("i1", "i2", "i3", "i4", "i5", "i6")}


def at(day: int) -> datetime:
    return datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc)


def who(account: str, *roles: str) -> Viewer:
    return Viewer(account, frozenset(roles), False, account)


class Gate:
    def is_enabled(self, company_id, module_id):
        return True


class Model:
    """Plays North: JSON for a draft prompt, plain text otherwise. `calls` is everything it was sent."""
    def __init__(self, plain="Thanks, I have noted that.", draft="Add your notes before Thursday."):
        self.plain, self.draft, self.calls = plain, draft, []

    def complete(self, module_id, messages, tools=None):
        self.calls.append(messages)
        text = json.dumps({"text": self.draft}) if "ONLY one JSON object" in messages[0]["content"] else self.plain
        return SimpleNamespace(text=text, tool_calls=[])


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path).create("acme")


def make(plane, iid="i-1", **over) -> dict:
    rec = {"id": iid, "type": "initiative", "title": "Add a data source", "purpose": "Reports", "created_by": ORG, "state": "open",
           "people": {"organiser": ORG, "sponsor": SPO, "participants": [AARON, BEA], "observers": [OBS], "affected": []},
           "time_box": {"starts": "2026-10-01", "ends": "2026-10-11"}, "start_answers": dict(START),
           "stages": [{"key": "think_unfiltered", "state": "open", "ends": "2026-10-09"},
                      {"key": "define_strategically", "state": "pending"}, {"key": "build_ready", "state": "pending"}]}
    rec.update(over)
    write_json_atomic(plane.path("intents", iid, "intent.json"), rec)
    return rec


def raw(plane, iid="i-1") -> bytes:
    return plane.path("intents", iid, "intent.json").read_bytes()


def thread(plane, v, day=2):
    return [t["text"] for t in N.panel(plane, "i-1", v, now=at(day), check=False)["thread"]]


def test_stage_opening_is_a_draft_until_the_organiser_confirms(plane):
    make(plane)
    m = Model()
    p = N.panel(plane, "i-1", who(ORG), model=m, gate=Gate(), now=at(2))
    d = p["drafts"][0]
    assert (d["kind"], d["status"], d["chip"], d["text"]) == ("opening", "draft", "Draft by North, not confirmed", m.draft)
    assert d["can_confirm"] and d["based_on"]
    assert not N.panel(plane, "i-1", who(AARON), now=at(2), check=False)["drafts"][0]["can_confirm"]
    with pytest.raises(N.NorthError) as e:
        N.decide(plane, "i-1", who(AARON), d["id"], "confirm", now=at(2))
    assert e.value.status == 403
    before = raw(plane)
    out = N.decide(plane, "i-1", who(ORG), d["id"], "confirm", text="Add your notes by Wednesday.", now=at(2))
    st = N._read(plane, "i-1")["drafts"][0]
    assert (st["status"], st["original_text"], st["by"]) == ("edited", m.draft, "person")
    assert out["drafts"] == [] and raw(plane) == before  # North never writes the record


def test_opening_uses_a_template_draft_when_no_model(plane):
    make(plane)
    d = N.panel(plane, "i-1", who(ORG), now=at(2))["drafts"][0]
    assert d["status"] == "draft" and "Due 9 Oct" in d["text"]


def test_missing_start_question_is_asked_one_at_a_time(plane):
    make(plane, start_answers={})
    p = N.panel(plane, "i-1", who(ORG), now=at(2))
    assert p["asking"]["question"] == "What are you trying to achieve?" and p["asking"]["mine"] and p["waiting"] == 1
    p = N.north_turn(plane, "i-1", who(ORG), "Add a reporting data source", now=at(2))
    assert p["asking"]["question"].startswith("Whom do you need") and p["reply"] == p["asking"]["question"]
    assert thread(plane, who(ORG)).count("What are you trying to achieve?") == 1
    assert not N.panel(plane, "i-1", who(AARON), now=at(2), check=False)["asking"]["mine"]


def test_nudge_names_the_holder_and_is_sent_once_a_day(plane):
    make(plane)
    d = N.panel(plane, "i-1", who(ORG), now=at(2))["drafts"][0]
    N.decide(plane, "i-1", who(ORG), d["id"], "confirm", now=at(2))  # the turn passes to the participants
    assert N._read(plane, "i-1")["turn"]["holder"] == "group" and not N._read(plane, "i-1")["nudges"]
    N.advance(plane, "i-1", now=at(8))
    n = N.nudges_for(plane, who(AARON), at(8))
    assert len(n) == 1 and n[0]["title"] == "Someone, please add your notes to the wall by Friday. 1 day left."
    assert n[0]["detail"] == "Add a data source, Think unfiltered" and n[0]["due"] == "2026-10-09"
    assert "Draft" not in json.dumps(n)
    N.advance(plane, "i-1", now=at(8))
    assert sorted(x["to"] for x in N._read(plane, "i-1")["nudges"] if x["kind"] == "pulse") == [AARON, BEA]  # once each
    assert not N.nudges_for(plane, who(OBS), at(8))
    assert any("please add your notes" in t for t in thread(plane, who(AARON), 8))
    assert len([t for t in N._read(plane, "i-1")["turns"] if t["to"] == BEA]) == 1 and not [t for t in thread(plane, who(BEA), 8) if "Aaron" in t]


def test_clock_cards_at_fifty_and_twenty_percent(plane):
    make(plane)
    N.advance(plane, "i-1", now=at(4))  # 70 percent left: nothing
    assert N._read(plane, "i-1")["clock_fired"] == []
    N.advance(plane, "i-1", now=at(7))  # 50 percent or less left (working days): a card for the organiser, no proposal yet
    st = N._read(plane, "i-1")
    assert st["clock_fired"] == [50] and not N._open(st, "extend_close_cancel")
    assert any(t.get("card") == 50 and t["to"] == ORG for t in st["turns"])
    N.advance(plane, "i-1", now=at(7))
    assert N._read(plane, "i-1")["clock_fired"] == [50]
    N.advance(plane, "i-1", now=at(10))  # 20 percent or less left: a proposal with three options
    prop = N._open(N._read(plane, "i-1"), "extend_close_cancel")[0]
    assert [o["key"] for o in prop["options"]] == ["extend", "close", "cancel"] and prop["may_confirm"] == [ORG]
    before = raw(plane)
    with pytest.raises(N.NorthError) as e:
        N.decide(plane, "i-1", who(ORG), prop["id"], "pick", key="extend", now=at(10))
    assert e.value.status == 422  # extend needs a reason
    N.decide(plane, "i-1", who(ORG), prop["id"], "pick", key="extend", reason="The data arrives late", now=at(10))
    done = N._read(plane, "i-1")["drafts"][-1]
    assert (done["picked"], done["reason"], done["decided_by"]) == ("extend", "The data arrives late", ORG)
    assert raw(plane) == before  # 07 changes the time box, never North


def test_closure_draft_and_next_proposal_are_drafts(plane):
    make(plane, state="closing", stages=[{"key": "build_ready", "state": "closed"}])
    p = N.panel(plane, "i-1", who(ORG), model=Model(draft="The data source was agreed."), gate=Gate(), now=at(5))
    kinds = {d["kind"]: d for d in p["drafts"]}
    assert kinds["closure"]["status"] == "draft" and kinds["closure"]["chip"] == "Draft by North, not confirmed"
    assert [o["key"] for o in kinds["next"]["options"]] == ["initiative", "problem", "decision", "backlog", "handled", "nothing"]
    assert N._read(plane, "i-1")["turn"]["what"] == "confirm the closure summary"
    assert "The data source" not in json.dumps(N.nudges_for(plane, who(SPO), at(5)))


def test_north_never_signs_closes_or_acts_for_anyone(plane):
    make(plane)
    before = raw(plane)
    m = Model(plain="I have closed the intent.")
    for text, key in (("Please close this intent", "close"), ("sign it for me", "sign"), ("Extend the time box", "extend"), ("rate it", "rate")):
        out = N.north_turn(plane, "i-1", who(ORG), text, model=m, gate=Gate(), now=at(2))
        assert out["reply"] == N.rules()["refusals"][key]
    assert raw(plane) == before
    calls = len(m.calls)  # the opening draft only: no refusal went to the model
    out = N.north_turn(plane, "i-1", who(ORG), "We should close the gap on reports", model=m, gate=Gate(), now=at(2))
    assert len(m.calls) > calls  # a sentence about closing is an ordinary message
    assert raw(plane) == before and all(d["status"] == "draft" for d in N._read(plane, "i-1")["drafts"])


def test_untraced_numbers_are_replaced(plane):
    make(plane)
    out = N.north_turn(plane, "i-1", who(AARON), "How are we doing?", model=Model(plain="We have 37 notes, day 2 of 7."), gate=Gate(), now=at(2))
    assert "37" not in out["reply"] and "not available yet" in out["reply"].lower()
    assert "day 2 of 7" in out["reply"]  # clock figures come from the record


def test_sealed_and_anonymous_material_never_reaches_a_draft(plane):
    secret = "SEALEDSECRET-ZEBRA"
    rec = make(plane, notes=[{"text": secret, "sealed": True}], cards=[{"text": secret, "anonymous": True}], ratings=[{"note": secret}],
               refs={"wall_session_ids": ["w1"]})
    m = Model(draft="Opening for the group.")
    p = N.panel(plane, "i-1", who(ORG), model=m, gate=Gate(), now=at(2))
    N.north_turn(plane, "i-1", who(ORG), "Tell me about the wall", model=m, gate=Gate(), now=at(2))
    assert m.calls and secret not in json.dumps(m.calls) and secret not in json.dumps(p) and secret not in json.dumps(N._read(plane, "i-1"))
    view = N.drafting_view(plane, rec, N.clock(rec, at(2)))
    assert secret not in json.dumps(view) and {"title", "people"} <= view.keys()


def test_who_sees_the_panel(plane):
    make(plane)
    N.north_turn(plane, "i-1", who(AARON), "I will add mine tomorrow", now=at(2))
    mine = "I will add mine tomorrow"
    assert mine in thread(plane, who(AARON)) and mine not in thread(plane, who(BEA))
    assert mine in thread(plane, who(ORG)) and mine in thread(plane, who("u-admin", "company_admin"))
    assert N.panel(plane, "i-1", who(OBS), now=at(2), check=False)["read_only"]
    with pytest.raises(N.NorthError) as e:
        N.north_turn(plane, "i-1", who(OBS), "Hello", now=at(2))
    assert (e.value.status, e.value.message) == (403, "You are reading this intent. You cannot answer.")
    for stranger in (who("u-nobody"), who("u-super", "super_admin")):
        with pytest.raises(N.NorthError) as e:
            N.panel(plane, "i-1", stranger, now=at(2))
        assert e.value.status == 404


def test_a_draft_intent_is_for_its_creator_only(plane):
    make(plane, state="draft", start_answers={})
    assert N.panel(plane, "i-1", who(ORG), now=at(2))["asking"]
    with pytest.raises(N.NorthError):
        N.panel(plane, "i-1", who("u-admin", "company_admin"), now=at(2))


def test_clock_line_and_missing_time_box(plane):
    rec = make(plane)
    assert N.clock(rec, at(5))["line"] == "Day 3 of 7, 5 days left."
    assert N.clock(rec, at(14))["line"] == "Overdue by 2 working days."
    assert N.clock({}, at(5))["line"].startswith("Not available yet")


def test_title_digits_are_facts_and_leftover_name_tokens_are_scrubbed():
    facts = N._facts({"title": "Q3 plan 2027", "people": {}}, {"facts": []})
    assert {f["value"] for f in facts} >= {"3", "2027"}
    assert N.LEFT_TOKEN.sub("a colleague", "PERSON_001 and Aaron") == "a colleague and Aaron"


def named(account: str, name: str, *roles: str) -> Viewer:
    return Viewer(name, frozenset(roles), False, account)


@pytest.mark.parametrize("viewer,seat,can_answer", [
    (named("u-org", "Janet Shaw", "company_admin"), "organiser", True),
    (named("u-marcus", "Marcus Todd"), "participant", True),   # named without an account id (R2)
    (named("u-harvey", "Harvey Rowley"), "owner", True),
    (named("u-daniel", "Daniel Kerr"), "sponsor", True),
    (named("u-grace", "Grace Ward"), "adviser", True),
    (named("u-aaron", "Aaron Lyle"), "participant", True),
])
def test_everyone_the_matrix_lets_in_gets_the_panel(plane, viewer, seat, can_answer):
    make(plane, people={"organiser": {"account_id": ORG, "name": "Janet Shaw"}, "sponsor": {"name": "Daniel Kerr"},
                        "owner": {"name": "Harvey Rowley"}, "participants": [{"name": "Marcus Todd"}, {"account_id": "u-aaron", "name": "Aaron Lyle"}],
                        "advisers": [{"name": "Grace Ward"}], "observers": [], "affected": [{"account_id": "u-aff", "name": "Ann"}]})
    p = N.panel(plane, "i-1", viewer, now=at(2), check=False)
    assert (p["seat"], p["can_answer"]) == (seat, can_answer)


def test_outsider_is_not_found_and_a_card_only_reader_gets_no_panel(plane):
    make(plane, people={"organiser": {"account_id": ORG}, "sponsor": {"name": "Daniel Kerr"}, "participants": [],
                        "affected": [{"account_id": "u-aff", "name": "Ann"}]})
    with pytest.raises(N.NorthError) as e:
        N.panel(plane, "i-1", named("u-out", "Olly Out"), now=at(2), check=False)
    assert e.value.status == 404
    with pytest.raises(N.NorthError) as e:
        N.panel(plane, "i-1", named("u-aff", "Ann"), now=at(2), check=False)
    assert e.value.status == 403 and "North" in e.value.message


# ---- F27: closed intents stay quiet, the clock agrees with the stage clock, nudges reach Pulse, ask and "something is wrong"

@pytest.mark.parametrize("state", ["closed", "closing", "cancelled"])
def test_no_start_question_on_closed_closing_or_cancelled(plane, state):
    make(plane, state=state, start_answers={})
    N.advance(plane, "i-1", model=Model(), gate=Gate(), now=at(5))
    st = N._read(plane, "i-1")
    assert not [t for t in st["turns"] if t["kind"] == "question"] and not (st["turn"] or {}).get("question")


def test_clock_line_uses_working_days_like_the_stage_clock(plane):
    from sh_platform.intents import clock as C
    rec = make(plane)
    c = C.clock(C.parse("2026-10-01"), C.parse("2026-10-11"), at(8))
    assert N.clock(rec, at(8))["line"] == f"Day {c['day_of']} of {c['working_days_total']}, {c['hours_left']} hours left."


def test_nudges_reach_pulse_lines_and_the_panel(plane):
    make(plane)
    N.decide(plane, "i-1", who(ORG), N.panel(plane, "i-1", who(ORG), now=at(2))["drafts"][0]["id"], "confirm", now=at(2))
    N.advance(plane, "i-1", now=at(8))
    got = N.nudges_for(plane, who(AARON), at(8))
    assert len(got) == 1 and got[0]["intent_id"] == "i-1" and "please" in got[0]["title"]
    assert N.panel(plane, "i-1", who(AARON), model=Model(), gate=Gate(), now=at(8), check=False)["nudge"]["text"] == got[0]["title"]
    assert N.nudges_for(plane, who(OBS), at(8)) == []
    assert N.panel(plane, "i-1", who(OBS), model=Model(), gate=Gate(), now=at(8), check=False)["nudge"] is None


def test_ask_is_a_question_and_wrong_tells_the_organiser(plane):
    make(plane, start_answers={})
    N.advance(plane, "i-1", model=Model(), gate=Gate(), now=at(2))
    out = N.north_turn(plane, "i-1", who(ORG), "What is a data source?", model=Model(), gate=Gate(), now=at(2), ask=True)
    assert out["asking"] and not [a for a in N._read(plane, "i-1")["asked"] if a["answered_at"]]
    before = raw(plane)
    out = N.north_turn(plane, "i-1", who(AARON), "The date is wrong", model=Model(), gate=Gate(), now=at(3), wrong=True)
    assert "organiser has been told" in out["reply"] and raw(plane) == before
    assert any("got this wrong" in t["text"] for t in N.panel(plane, "i-1", who(ORG), model=Model(), gate=Gate(), now=at(3), check=False)["thread"])
    assert not any("got this wrong" in t["text"] for t in N.panel(plane, "i-1", who(BEA), model=Model(), gate=Gate(), now=at(3), check=False)["thread"])


def test_nudges_fire_when_stages_carry_no_end_date(plane):
    rec = make(plane)
    for s in rec["stages"]:
        s.pop("ends", None)
    rec["stages"][0]["opened_at"] = "2026-10-01T09:00:00+00:00"
    write_json_atomic(plane.path("intents", "i-1", "intent.json"), rec)
    d = N.panel(plane, "i-1", who(ORG), now=at(2))["drafts"][0]
    N.decide(plane, "i-1", who(ORG), d["id"], "confirm", now=at(2))
    assert N._stage_end(rec, rec["stages"][0]) <= "2026-10-11T09:00:00+00:00"
    N.advance(plane, "i-1", now=at(9))
    assert N.nudges_for(plane, who(AARON), at(9))
    rec["stages"][0].pop("opened_at")
    assert N._stage_end(rec, rec["stages"][0]) == "2026-10-11"  # last resort: the time box end


def test_the_organiser_cannot_post_got_this_wrong(plane):
    make(plane)
    with pytest.raises(N.NorthError) as e:
        N.north_turn(plane, "i-1", who(ORG), "The date is wrong", wrong=True, now=at(3))
    assert e.value.status == 403
