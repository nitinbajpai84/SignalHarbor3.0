"""M1-18 North's grouping on the kernel runtime: the payload really crosses the real egress gateway structure check (the
lesson of 3 October: plain text, never a list of objects), names are tokenised, figures are guarded, a failed call is
honest. Stub transport, no live call. Synthetic family-office text."""
import json
import re

import pytest

from m1_kit import World
from modules.m1_intent.agent import gather
from modules.m1_intent.domain import board as B
from modules.m1_intent.tools.pack_tools import Guidance
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.packs import EmptyPack

S = B.load_settings()
PROBLEMS = [{"id": "P-1", "question": "Where do capital calls arrive too late?"},
            {"id": "P-2", "question": "Where is exposure not seen in one place?"}]
NOTES = [{"id": f"id{i}", "text": t, "anonymous": False, "author_name": "Pat Authorname"} for i, t in enumerate([
    "Capital calls reach us too late", "We learn of capital calls by email", "Exposure by name takes a week",
    "Private funds are not in our exposure report", "Fee reports differ by manager"])]
REPLY = ("```json\n" + json.dumps({"groups": [
    {"name": "Calls arrive too late", "pack_problem_id": "P-1", "reasoning": "Same problem", "note_ids": ["n1", "n2"]},
    {"name": "No single exposure view", "pack_problem_id": "P-9", "reasoning": "Same problem", "note_ids": ["n3", "n4"]}]}) + "\n```")


class Transport:
    def __init__(self, reply=REPLY):
        self.reply, self.bodies = reply, []

    def __call__(self, url, body):
        self.bodies.append(body.decode())
        return json.dumps({"text": self.reply, "tool_calls": []})


@pytest.fixture
def lab(tmp_path):
    w = World(tmp_path)
    plane = w.plane("co-a").ensure()
    t = Transport()
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test", transport=t)
    return w, plane, t, EgressModelClient(gw)


def run(lab, notes=NOTES, settings=S, problems=PROBLEMS, north=None):
    w, plane, t, model = lab
    g = Guidance(EmptyPack("x"), problems=problems, north=north or {})
    return gather.group_notes(model, w.store, RunRegistry(plane), "co-a", settings, notes, g)


def wire(t) -> dict:
    return json.loads(t.bodies[0])


# ---- the real gateway structure check
def test_the_real_gather_payload_passes_the_real_gateway_structure_check(lab):
    g = run(lab)
    assert g.ok and len(lab[2].bodies) == 1  # sent, not blocked: the check ran on exactly this payload
    assert [x["note_ids"] for x in g.groups] == [["id0", "id1"], ["id2", "id3"]]  # labels mapped back to the notes
    made = B.apply_grouping(S, [n["id"] for n in NOTES], g.groups, g.problem_ids)
    assert [c["pack_problem_id"] for c in made] == ["P-1", None]  # P-9 was never offered


def test_the_notes_and_pack_text_go_as_plain_text_never_a_list_of_objects(lab):
    run(lab)
    msgs = wire(lab[2])["messages"]
    user = json.loads(msgs[1]["content"])
    assert isinstance(user["question"], str) and "- n1: Capital calls reach us too late" in user["question"]
    assert "- P-1: Where do capital calls arrive too late?" in user["question"]
    assert isinstance(user["context"], dict) and not any(isinstance(v, list) and v and isinstance(v[0], dict) and "group_size" not in v[0]
                                                         for v in user["context"].values())


def test_the_old_shape_a_list_of_note_objects_is_refused_by_the_same_gateway(lab):
    """Proves the test above means something: the shape the earlier gather would have sent is blocked."""
    _, _, t, model = lab
    rows = [{"id": n["id"], "text": n["text"]} for n in NOTES]
    with pytest.raises(EgressBlocked) as e:
        model.complete("m1_intent", [{"role": "system", "content": "x"}, {"role": "user", "content": json.dumps({"notes": rows})}])
    assert e.value.reason_code == "raw_rows" and not t.bodies


def test_names_leave_tokenised_and_no_author_or_id_is_sent(lab):
    w, plane, t, _ = lab
    NameVault(plane).register("person", "Quinn Registered")
    notes = [*NOTES, {"id": "id9", "text": "Quinn Registered says the calls are late", "anonymous": True}]
    assert run(lab, notes).ok
    body = t.bodies[0]
    assert "Quinn" not in body and "PERSON_" in body                       # the name is a token on the wire
    assert "Authorname" not in body and "author_name" not in body          # the author is never part of what leaves
    assert not re.search(r"id\d", json.loads(body)["messages"][1]["content"])  # the model sees n1, n2, never a real id


def test_every_run_is_recorded_without_content(lab):
    run(lab)
    reg = (lab[1].area("context") / "run_registry.jsonl").read_text(encoding="utf-8")
    assert "North" in reg and "Capital calls" not in reg and "Quinn" not in reg


# ---- what comes back
def test_parse_reads_a_fenced_block_or_bare_json_and_drops_unknown_labels():
    labels = {"n1": "a", "n2": "b"}
    bare = json.dumps({"groups": [{"name": "X", "note_ids": ["n1", "n2", "n7", 5]}]})
    assert gather.parse(bare, labels)[0]["note_ids"] == ["a", "b"]
    assert gather.parse("Here you go:\n```json\n" + bare + "\n```\nDone.", labels)[0]["note_ids"] == ["a", "b"]
    assert gather.parse("no", labels) is None and gather.parse('{"groups": 3}', labels) is None


def test_a_figure_the_people_wrote_survives_and_one_north_invented_is_replaced(lab):
    notes = [{"id": "id0", "text": "Calls come 40 days late", "anonymous": False}, {"id": "id1", "text": "Calls come late again", "anonymous": False}]
    lab[2].reply = "```json\n" + json.dumps({"groups": [{"name": "Calls 40 days late", "reasoning": "About 99 percent agree", "note_ids": ["n1", "n2"]}]}) + "\n```"
    g = run(lab, notes)
    assert g.ok and g.groups[0]["name"] == "Calls 40 days late"
    assert "99" not in g.groups[0]["reasoning"] and "not available yet" in g.groups[0]["reasoning"]


def test_a_blocked_or_failing_model_is_a_plain_failure_not_a_crash(lab):
    w, plane, t, model = lab
    class Down:
        def complete(self, *a, **k):
            raise EgressBlocked("transport_failed")
    g = gather.group_notes(Down(), w.store, RunRegistry(plane), "co-a", S, NOTES, Guidance(EmptyPack("x")))
    assert not g.ok and g.groups == [] and "try again" in g.message


def test_no_notes_means_no_model_call_and_no_model_means_unavailable(lab):
    w, plane, t, model = lab
    assert gather.group_notes(model, w.store, RunRegistry(plane), "co-a", S, [], Guidance(EmptyPack("x"))).ok and not t.bodies
    off = gather.group_notes(None, w.store, RunRegistry(plane), "co-a", S, NOTES, Guidance(EmptyPack("x")))
    assert not off.ok and "not available" in off.message


def test_notes_beyond_the_size_budget_are_not_sent_and_stay_on_their_own(lab):
    small = B.BoardSettings(S.options, S.name_chars, S.comment_chars, S.comments_per_cluster, S.min_notes, 60, 100, S.split_suffix, S.default_name)
    long_notes = [{"id": f"id{i}", "text": "Capital calls reach us too late " * 2, "anonymous": False} for i in range(5)]
    question, labels = gather.build_question(small, long_notes, Guidance(EmptyPack("x")))
    assert 0 < len(labels) < 5 and question.count("- n") == len(labels)  # the rest is left out of the call, not dropped from the board
    view = B.view([], long_notes)
    assert len(view["on_its_own"]) == 5


# ---- the instructions
def test_instructions_are_plain_and_the_industry_wording_comes_from_the_pack():
    p = gather.system_prompt({"advisor_role": "a custodian-side adviser"})
    assert "a custodian-side adviser" in p and "nothing but the json" in p and "at least two notes" in p
    assert gather.system_prompt().startswith("You are North, the industry expert")
    industries = [d.name.replace("_", " ") for d in (gather.RULES_FILE.parents[3] / "packs").iterdir() if d.is_dir()]
    assert industries and not any(i in gather.RULES_FILE.read_text(encoding="utf-8").lower() for i in industries)  # no industry named


# ---- the shapes the live model really sent (4 October; synthetic text). Its reply was cut off by the output limit
# after one or two groups, pretty-printed or compact, inside a ```json fence.
CUT_COMPACT = ('```json\n{"groups": [{"name": "Calls arrive too late", "pack_problem_id": "P-1", "note_ids": ["n1", "n2"], '
               '"reasoning": "Same problem."}, {"name": "No single exposure view", "pack_problem_id": null, "note_ids": ["n3", "n4"], "reas')
CUT_PRETTY = ('```json\n{\n  "groups": [\n    {\n      "name": "Calls arrive too late",\n      "pack_problem_id": "P-1",\n      "note_ids": [\n'
              '        "n1",\n        "n2"\n      ],\n      "reasoning": "Same problem."\n    },\n    {\n      "name": "Exposure",\n      "note_ids": [\n        "n3",\n        "n')
LABELS = {f"n{i}": f"id{i - 1}" for i in range(1, 6)}


def test_parse_keeps_every_complete_group_of_a_reply_cut_off_mid_group():
    got = gather.parse(CUT_COMPACT, LABELS)
    assert [g["name"] for g in got] == ["Calls arrive too late"] and got[0]["note_ids"] == ["id0", "id1"]
    assert [g["name"] for g in gather.parse(CUT_PRETTY, LABELS)] == ["Calls arrive too late"]
    assert gather.parse('```json\n{"groups": [{"name": "X", "note_ids": ["n1", "n', LABELS) == []  # nothing whole yet: readable, no group
    assert not gather._complete(CUT_COMPACT) and gather._complete(REPLY)


def test_parse_takes_a_bare_array_prose_around_it_and_labels_in_any_case():
    arr = 'Groups: [{"name": "X", "note_ids": ["N1", " n2 "]}] hope that helps {not json}'
    assert gather.parse(arr, LABELS)[0]["note_ids"] == ["id0", "id1"]
    tail = REPLY + "\n\nLet me know if you want changes."
    assert len(gather.parse(tail, {"n1": "a", "n2": "b", "n3": "c", "n4": "d"})) == 2 and gather._complete(tail)


class Sequence(Transport):
    """Answers the replies in turn: the live model's cut-off reply, then the next call over the notes still ungrouped."""

    def __init__(self, *replies):
        super().__init__()
        self.replies = list(replies)

    def __call__(self, url, body):
        self.bodies.append(body.decode())
        return json.dumps({"text": self.replies.pop(0), "tool_calls": []})


def _sequence_lab(tmp_path, *replies):
    w = World(tmp_path)
    plane = w.plane("co-a").ensure()
    t = Sequence(*replies)
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=["model.example.test"], model_url="https://model.example.test", transport=t)
    return w, plane, t, EgressModelClient(gw)


def test_a_cut_off_reply_is_asked_again_over_the_notes_still_ungrouped_and_none_is_lost(tmp_path):
    second = "```json\n" + json.dumps({"groups": [{"name": "No single exposure view", "note_ids": ["n1", "n2"]}]}) + "\n```"
    lab = _sequence_lab(tmp_path, CUT_COMPACT, second)
    t = lab[2]
    g = run(lab)
    assert g.ok and len(t.bodies) == 2
    assert "Exposure by name takes a week" in t.bodies[1] and "Capital calls reach us too late" not in t.bodies[1]  # only the ungrouped ones
    made = B.apply_grouping(S, [n["id"] for n in NOTES], g.groups, g.problem_ids)
    assert [(c["name"], c["note_ids"]) for c in made] == [("Calls arrive too late", ["id0", "id1"]), ("No single exposure view", ["id2", "id3"])]
    assert B.view(made, NOTES)["on_its_own"] == [B.shown(NOTES[4])]  # the fifth note is on its own, never dropped


def test_replies_cut_off_before_any_group_every_time_are_a_plain_failure(tmp_path):
    lab = _sequence_lab(tmp_path, *['```json\n{"groups": [{"name": "Calls arr'] * gather.MAX_ROUNDS)
    g = run(lab)
    assert not g.ok and g.groups == [] and len(lab[2].bodies) == gather.MAX_ROUNDS
