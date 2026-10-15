"""M1-24 the charter's "So that ..." lines: North drafts one per ticked problem from its notes (plain text, through the real
egress gateway structure check), labelled as a draft, never over a human edit; with no model the line stays blank and the
organiser is asked. Titles are sentence case and every ticked cluster reaches the charter. Stub model, no live call."""
import json

import pytest

from m1_kit import World
from modules.m1_intent.agent import charter_lines as L
from modules.m1_intent.domain import charter as C
from modules.m1_intent.tools.pack_tools import Guidance
from sh_platform.agents.protocols import ModelReply
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.model import EgressModelClient
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.packs import EmptyPack
from test_m1_board_kit import GatherStub, together

S = C.load_charter_settings()
PROBLEMS = [{"id": "k1", "title": "Calls arrive too late", "notes": ["Capital calls reach us too late to plan the cash", "We learn of calls by email"]},
            {"id": "k2", "title": "No single exposure view", "notes": ["Exposure by name takes a week"]}]
REPLY = "p1: So that funding is planned, not found.\np2: we see concentration early\nnoise line"


class Lines(GatherStub):
    """Grouping as GatherStub does; the charter-lines call (it sees "Problems and the notes") answers one line per problem."""

    def __init__(self, by_title=None, **kw):
        super().__init__(**kw)
        self.by_title, self.asked = by_title or {}, []

    def complete(self, module_id, messages, tools=None):
        if "Problems and the notes about them" in messages[1]["content"]:
            q = json.loads(messages[1]["content"])
            self.asked.append(q)
            rows = [ln[2:].split(": ", 1) for ln in q["question"].splitlines() if ln.startswith("- p")]
            return ModelReply("\n".join(f"{label}: {self.by_title[t]}" for label, t in rows if t in self.by_title))
        return super().complete(module_id, messages, tools)


# ---- the parts
def test_parse_keeps_readable_lines_makes_each_a_so_that_sentence_and_ignores_unknown_labels():
    labels = {"p1": "k1", "p2": "k2"}
    got = L.parse(REPLY + "\np9: not offered\np2: x " + "y" * 400, labels, S.so_that_max)
    assert got == {"k1": "So that funding is planned, not found.", "k2": "So that we see concentration early."}  # the prefix is added when North left it out; over-long line left out


def test_parse_reads_the_live_shapes_quoted_labels_fences_bullets_and_stray_quotes():
    """Shapes the live model sent on 4 October (synthetic text)."""
    labels = {"p1": "k1", "p2": "k2", "p3": "k3"}
    quoted = "p1': 'funding is planned, not found',\np2': 'we see concentration early'"  # label and text wrapped in quote marks
    assert L.parse(quoted, labels, S.so_that_max) == {"k1": "So that funding is planned, not found.", "k2": "So that we see concentration early."}
    fenced = "```text\n- **p1**: So that funding is planned\n* P2 = we see it early\n```\nHope this helps."
    assert L.parse(fenced, labels, S.so_that_max) == {"k1": "So that funding is planned.", "k2": "So that we see it early."}
    inner = "p1: we use one version of 'return'\np2: \"calls arrive in time\""
    assert L.parse(inner, labels, S.so_that_max) == {"k1": "So that we use one version of 'return'.", "k2": "So that calls arrive in time."}


def test_a_line_cut_off_inside_its_quote_is_left_out_and_the_whole_lines_before_it_are_kept():
    cut = "p1': 'funding is planned',\np2': 'capital call notices reach us with enough time for"
    assert L.parse(cut, {"p1": "k1", "p2": "k2"}, S.so_that_max) == {"k1": "So that funding is planned."}


def test_the_rules_ask_for_the_plain_shape_that_is_parsed():
    rules = L.load_rules()["rules"]
    assert all(isinstance(r, str) for r in rules) and any("p1: " in r and "no quote marks" in r for r in rules)


def test_sentence_case_capitalises_the_first_letter_and_keeps_the_rest():
    assert C.sentence_case("  calls arrive   too late. ") == "Calls arrive too late"
    assert C.sentence_case("APE reports lag by a month") == "APE reports lag by a month"
    assert C.sentence_case("") == ""


def test_a_human_edit_is_kept_and_a_draft_never_becomes_its_proposal():
    template = type("T", (), {"id": "full", "name": "Full", "columns": ["problem", "purpose"]})()
    base = {"id": "c1", "title": "Calls arrive too late", "priority": None, "note_count": 2, "agree_count": 0, "ticked": True,
            "library_problem_id": None, "so_that": None, "so_that_draft": False}
    first = C.build_version([{**base, "so_that": "north draft", "so_that_draft": True}], template, S, number=1, by="x", now="n", date="d", participants=1, earlier=None)
    assert first["problems"][0]["so_that_draft"] is True and first["problems"][0]["so_that_edited"] is False
    edited = C.edit_purposes(first, {"c1": "So that our own words."}, S, "x", "n")
    assert edited["problems"][0]["so_that_draft"] is False and edited["problems"][0]["so_that_edited"] is True
    again = C.build_version([{**base, "so_that": "north draft 2", "so_that_draft": True}], template, S, number=2, by="x", now="n", date="d", participants=1, earlier=edited)
    p = again["problems"][0]
    assert (p["so_that"], p["so_that_draft"], p["so_that_proposal"]) == ("So that our own words.", False, None)


def test_a_cluster_title_is_sentence_cased_when_the_result_is_read():
    row = {"id": "c1", "title": "calls arrive too late", "priority": None, "note_count": 1, "agree_count": 0, "ticked": True}
    assert C.clean_together({"clusters": [row]}, S)[0]["title"] == "Calls arrive too late"


# ---- the real gateway structure check
class Transport:
    def __init__(self):
        self.bodies = []

    def __call__(self, url, body):
        self.bodies.append(body.decode())
        return json.dumps({"text": "p1: So that funding is planned, not found.", "tool_calls": []})


@pytest.fixture
def lab(tmp_path):
    w = World(tmp_path)
    plane = w.plane("co-a").ensure()
    t = Transport()
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=["model.example.test"],
                       model_url="https://model.example.test", transport=t)
    return w, plane, t, EgressModelClient(gw)


def test_the_real_charter_lines_payload_passes_the_real_gateway_structure_check(lab):
    w, plane, t, model = lab
    got = L.draft_lines(model, w.store, RunRegistry(plane), "co-a", PROBLEMS, S.so_that_max)
    assert len(t.bodies) == 2  # one call per problem, sent not blocked (D9c: a line is drafted from its own notes only)
    assert got == {"k1": "So that funding is planned, not found.", "k2": "So that funding is planned, not found."}
    assert "Exposure by name" not in t.bodies[0] and "Capital calls reach us" not in t.bodies[1]
    user = json.loads(json.loads(t.bodies[0])["messages"][1]["content"])
    assert isinstance(user["question"], str) and "- p1: Calls arrive too late" in user["question"]
    assert "  - note: Capital calls reach us too late to plan the cash" in user["question"]
    assert "k1" not in t.bodies[0]  # the model never sees a real id


def test_no_model_nothing_to_draft_and_a_failed_call_all_leave_it_blank(lab):
    w, plane, t, model = lab
    assert L.draft_lines(None, w.store, RunRegistry(plane), "co-a", PROBLEMS, S.so_that_max) == {}
    assert L.draft_lines(model, w.store, RunRegistry(plane), "co-a", [], S.so_that_max) == {} and not t.bodies

    class Down:
        def complete(self, *a, **k):
            raise RuntimeError("the provider is down")
    assert L.draft_lines(Down(), w.store, RunRegistry(plane), "co-a", PROBLEMS, S.so_that_max) == {}


def test_the_rules_name_no_industry():
    text = L.RULES_FILE.read_text(encoding="utf-8").lower()
    industries = [d.name.replace("_", " ") for d in (L.RULES_FILE.parents[3] / "packs").iterdir() if d.is_dir()]
    assert industries and not any(i in text for i in industries)


# ---- through the routes: the real board to the charter
def _tick_both(b):
    for name in ("Calls arrive too late", "No single exposure view"):
        cid = b.cluster(name)["id"]
        assert b.org_call("POST", f"/together/clusters/{cid}/tick", json={"ticked": True}).status_code == 200


def test_the_charter_is_drafted_with_north_lines_labelled_as_drafts_and_editable(tmp_path):
    stub = Lines({"Calls arrive too late": "funding is planned, not found", "No single exposure view": "we see concentration early"})
    b = together(tmp_path, model=stub)
    _tick_both(b)
    rows = b.org_call("POST", "/charter", json={"confirm": True}).json()["charter"]["problems"]
    by = {p["title"]: p for p in rows}
    late = by["Calls arrive too late"]
    assert late["so_that"] == "So that funding is planned, not found." and late["so_that_draft"] is True and "Draft" in late["so_that_note"]
    assert late["so_that_edited"] is False
    assert len(stub.asked) == 2  # one call per problem: each sees only its own notes
    own = {q["question"].splitlines()[1]: q["question"] for q in stub.asked}
    assert "Capital calls reach us too late to plan the cash" in own["- p1: Calls arrive too late"]
    assert "Exposure by name" not in own["- p1: Calls arrive too late"] and "Capital calls" not in own["- p1: No single exposure view"]
    r = b.org_call("PUT", "/charter", json={"so_that": {late["id"]: "we fund calls from cash we planned"}})
    got = {p["id"]: p for p in r.json()["charter"]["problems"]}[late["id"]]
    assert got["so_that"] == "So that we fund calls from cash we planned." and got["so_that_draft"] is False and got["so_that_note"] is None


def test_with_no_model_the_line_is_blank_and_the_organiser_is_asked(tmp_path):
    b = together(tmp_path)  # GatherStub groups, and answers the charter call with a question: nothing readable
    _tick_both(b)
    rows = b.org_call("POST", "/charter", json={"confirm": True}).json()["charter"]["problems"]
    assert [p["so_that"] for p in rows] == [None, None] and not any(p["so_that_draft"] for p in rows)
    assert all("Ask the room" in p["so_that_note"] for p in rows)


def test_every_ticked_cluster_reaches_the_charter_even_with_no_vote(tmp_path):
    b = together(tmp_path)
    clusters = b.org_call("GET", "/board").json()["clusters"]
    assert len(clusters) == 2
    for c in clusters:  # nobody voted on either: both still ticked
        assert b.org_call("POST", f"/together/clusters/{c['id']}/tick", json={"ticked": True}).status_code == 200
    from modules.m1_intent.domain.together import read_together_result
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(b.w.settings.data_root).plane_for("co-a").ensure()
    assert {c["id"] for c in read_together_result(plane, b.sid)["ticked"]} == {c["id"] for c in clusters}
    rows = b.org_call("POST", "/charter", json={"confirm": True}).json()["charter"]
    assert {p["title"] for p in rows["problems"]} == {"Calls arrive too late", "No single exposure view"} and rows["footer"]["later"] == 0
