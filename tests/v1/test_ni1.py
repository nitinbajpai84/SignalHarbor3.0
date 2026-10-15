"""NI1 (Nitin's screenshot, 9 Oct): a reply that starts with yes accepts North's proposals and is never stored as a field value; a short
answer fills the section North just asked about; the model's context passes the egress row check after two turned-down proposals; a model
that cannot be reached is said plainly. Synthetic data only."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.rows import json_findings
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import g1_access
from sh_platform.v1 import i2_north as N
from sh_platform.v1 import i6_chat as C
from sh_platform.v1 import l2_proposals as L2

MEI = Viewer("Mei Chen", frozenset({"analyst"}), False, "acc-mei")


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    monkeypatch.setattr(g1_access, "check_agent", lambda *a, **k: None)
    (tmp_path / "co").mkdir()
    return PlaneStore(tmp_path).plane_for("co")


class Say:
    """A model that answers the given JSON objects in turn, or fails when it has none left."""
    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        if not self.answers:
            raise RuntimeError("down")
        return ModelReply(text=json.dumps(self.answers.pop(0)))


def test_a_reply_starting_with_yes_accepts_the_proposals_and_is_not_stored(plane):
    m = Say({"reply": "Who reads it, and what do they decide from it?", "asked": "readers",
             "sow_patch": {"kpis": [{"name": "Return", "definition": "Growth net of fees"}]}, "covered": []},
            {"reply": "Noted. By when each month?", "asked": "frequency", "sow_patch": {}, "covered": []})
    iid = C.create(plane, MEI, "Building a new reporting for performance")
    v = C.chat(plane, iid, MEI, "performance reporting", model=m)
    assert v["proposals"]["pending"] and not v["sow"]["kpis"]
    v = C.chat(plane, iid, MEI, "yes can you build the intent of work", model=m)
    assert not v["proposals"]["pending"] and [k["name"] for k in v["sow"]["kpis"]] == ["Return"]
    assert "yes can you build" not in json.dumps(v["sow"])


def test_a_yes_with_the_model_down_fills_nothing_and_asks_again(plane):
    m = Say({"reply": "Who sees this work?", "asked": "readers", "sow_patch": {"kpis": [{"name": "Return", "definition": "d"}]}, "covered": []})
    iid = C.create(plane, MEI, "Building a new reporting for performance")
    C.chat(plane, iid, MEI, "performance reporting", model=m)
    v = C.chat(plane, iid, MEI, "yes can you build the intent of work", model=m)  # the model is down now
    assert v["sow"]["kpis"] and "template_fields" not in v["sow"] and "yes can you build" not in json.dumps(v["sow"])
    assert v["turns"][-1]["text"].startswith(C.OFFLINE)  # NM1: no model: the rules answer, and the person is told (was NAV-1: "changed nothing")


def test_a_short_answer_fills_the_section_north_asked_about(plane):
    iid = C.create(plane, MEI, "Building a new reporting for performance")
    # the fallback asked the readers question although other goals are open before it in this order
    thread = N.read_thread(plane, iid)
    thread["asked"] = "readers"
    got = C.fallback(N.read_sow(plane, iid), [], "by head of data", [], None, "readers")
    assert got["sow_patch"]["goal"] == {"readers": ["by head of data"]} and got["covered"] == ["readers"]
    assert got["asked"] != "readers"  # then it moves on


def test_the_asked_goal_is_kept_per_turn_and_given_to_the_model(plane):
    m = Say({"reply": "Who reads it, and what do they decide from it?", "asked": "readers", "sow_patch": {}, "covered": []},
            {"reply": "ok", "sow_patch": {}, "covered": []})
    iid = C.create(plane, MEI, "Building a new reporting for performance")
    C.chat(plane, iid, MEI, "performance reporting", model=m)
    assert N.read_thread(plane, iid)["asked"] == "readers"
    C.chat(plane, iid, MEI, "by head of data", model=m)
    assert json.loads(m.seen[-1][1]["content"])["context"]["question_you_just_asked_is_about"] == "readers"


def test_two_turned_down_proposals_do_not_make_the_context_look_like_rows(plane):
    m = Say({"reply": "r", "sow_patch": {"kpis": [{"name": "A", "definition": "d"}]}, "covered": []},
            {"reply": "r", "sow_patch": {"kpis": [{"name": "B", "definition": "d"}]}, "covered": []},
            {"reply": "r", "sow_patch": {}, "covered": []})
    iid = C.create(plane, MEI, "Building a new reporting for performance")
    for said in ("one", "no, wrong", "two", "no, wrong again"):
        v = C.chat(plane, iid, MEI, said, model=m) if m.answers or said.startswith("no") else v
    assert len(L2.facts(plane, iid, ("sow", "process_map")).get("turned_down_by_the_person", [])) == 2
    C.chat(plane, iid, MEI, "carry on", model=m)
    msg = m.seen[-1][1]["content"]
    assert json_findings(msg)[0] is None, "the egress gateway reads two objects in a list as rows (the cause of 'North (rules only)')"
