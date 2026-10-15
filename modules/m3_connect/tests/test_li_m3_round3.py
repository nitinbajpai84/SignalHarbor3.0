"""LI-M3 fix round 3: a measure fed by a source that is shut for a viewer is treated exactly like a restricted measure, on every route and in
every shared record (plan, signed outcome). Synthetic data only; the marker string stands for text derived from a restricted sample."""
import json

from m3_kit import BASE, person
from modules.m3_connect.agent import plan_lens
from test_li_m3 import demo_world, put_sample, restrict
from test_m3_intake import payload
from test_m3_intake import url as intake_url

MARK = "ZETA-MARKER"
LISTED = ("Test Somebody Else", "Test Hana Head")  # the people who may see the restricted sample (the head of data signs, so must be on it)
SOURCES = {"sources": [{"id": "S01", "name": "Performance workbook", "kind": "spreadsheet", "effort": "small", "impact": {"score": 0.6, "reasons": []},
                        "marks": [], "owners": [], "measures": ["K10"]}]}
FINDINGS = {"measures": {"K10": {"measure": "K10", "group": "unclear", "pain_points": [], "levers": [], "sources": ["S01"],
                                 "reasons": [f"Lens and your figure differ. The data ends on 2026-03-31. {MARK} is empty in 14 of 40 rows."]}},
            "risks": [{"id": "R1", "kind": "risk", "text": f"The figure may be off: {MARK}.", "measures": ["K10"], "pain_points": []}], "left_out": []}


def plan_url(aid, tail):
    return f"{BASE}/assessments/{aid}{tail}"


def shared(adir):
    """The records built from the findings and shared by everyone: the plan, the decisions and the outcome for module 4."""
    files = [adir / "plan.json", adir / "decisions.json", *(adir.parents[1] / "outcomes").glob("*.json")]
    return " ".join(p.read_text(errors="ignore") for p in files)


def write_inputs(adir):
    (adir / "sources.json").write_text(json.dumps(SOURCES))
    (adir / "findings.json").write_text(json.dumps(FINDINGS))


def placed(world, with_findings=True):
    """The listed person places the restricted sample on S01; findings hold the marker in a gap reason and a risk."""
    c, aid = demo_world(world)  # Lens Lee, an analyst, is not on any list
    put_sample(world, system="Performance workbook")
    restrict(world, "Performance workbook", LISTED)
    listed = person(world, "m3-a", "Somebody Else")
    key = listed.get(intake_url(aid, "/requests")).json()["to_confirm"][0]["key"]
    assert listed.post(intake_url(aid, "/sources/S01/upload"), json={"profile_sample": key}).status_code == 200
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    if with_findings:
        write_inputs(adir)
    return c, aid, listed, adir


def sign_both(world, aid, listed, head):
    assert listed.post(plan_url(aid, "/risks/R1/decision"), json={"decision": "accepted"}).status_code == 200
    sponsor = person(world, "m3-a", "Sam Sponsor", ("sponsor",))
    assert sponsor.post(plan_url(aid, "/plan/sign")).status_code == 200
    done = head.post(plan_url(aid, "/plan/sign"))
    assert done.status_code == 200 and done.json()["signed_at"], done.text


def outsider_sees_nothing(outsider, aid):
    for tail in ("/plan", "/risks"):
        assert MARK not in outsider.get(plan_url(aid, tail)).text, tail
    risks = outsider.get(plan_url(aid, "/risks")).json()
    assert [(r["restricted"], r["text"]) for r in risks["risks"]] == [(True, "A restricted measure")]
    assert outsider.post(plan_url(aid, "/risks/R1/decision"), json={"decision": "accepted"}).status_code == 403
    plan = outsider.get(plan_url(aid, "/plan")).json()
    assert [i["summary"] for b in plan["bands"].values() for i in b] == ["A restricted measure"] and plan["restricted_hidden"] == 1


# ---- the reviewer's three probes -------------------------------------------------------------------------------------------------------------
def test_probe_outsider_never_sees_a_restricted_samples_text_in_plan_risks_or_signed_outcome(world):
    outsider, aid, listed, adir = placed(world)
    outsider_sees_nothing(outsider, aid)  # the outsider's own first view drafts the plan
    sign_both(world, aid, listed, person(world, "m3-a", "Hana Head", ("company_admin",)))
    assert MARK not in outsider.get(plan_url(aid, "/outcome")).text
    assert MARK not in shared(adir)  # not in plan.json, decisions, or the outcome record module 4 reads
    own = listed.get(plan_url(aid, "/risks")).text
    assert MARK in own  # the listed person still sees what they may see


def test_probe_head_of_data_drafting_first_leaves_the_same_shared_record(world):
    outsider, aid, listed, adir = placed(world)
    head = person(world, "m3-a", "Hana Head", ("company_admin",))
    assert head.get(plan_url(aid, "/plan")).status_code == 200  # a viewer who may see the sample drafts first
    assert MARK not in (adir / "plan.json").read_text()
    outsider_sees_nothing(outsider, aid)
    sign_both(world, aid, listed, head)
    assert MARK not in outsider.get(plan_url(aid, "/outcome")).text and MARK not in shared(adir)


def test_probe_a_restriction_added_after_adoption_and_drafting_does_not_reach_the_outcome(world):
    c, aid = demo_world(world)
    put_sample(world, system="Performance workbook")
    assert [f["source_id"] for f in c.get(intake_url(aid, "/requests")).json()["from_profile"]] == ["S01"]  # open when adopted
    adir = world.plane("m3-a").path("intents", "m3_connect", "assessments", aid)
    write_inputs(adir)
    assert MARK in c.get(plan_url(aid, "/plan")).text  # nothing is restricted yet: the plan is drafted with the reason
    assert c.post(plan_url(aid, "/risks/R1/decision"), json={"decision": "accepted"}).status_code == 200
    restrict(world, "Performance workbook", LISTED)  # then the restriction arrives
    for tail in ("/plan", "/risks"):
        assert MARK not in c.get(plan_url(aid, tail)).text, tail
    sponsor, head = person(world, "m3-a", "Sam Sponsor", ("sponsor",)), person(world, "m3-a", "Hana Head", ("company_admin",))
    assert sponsor.post(plan_url(aid, "/plan/sign")).status_code == 200
    assert head.post(plan_url(aid, "/plan/sign")).json()["signed_at"]
    assert MARK not in c.get(plan_url(aid, "/outcome")).text
    outcomes = (adir.parents[1] / "outcomes")
    assert MARK not in " ".join(p.read_text() for p in outcomes.glob("*.json"))


def test_the_closed_view_marks_the_item_restricted_and_blanks_what_it_stores(world):
    outsider, aid, listed, adir = placed(world)
    outsider.get(plan_url(aid, "/plan"))
    item = json.loads((adir / "plan.json").read_text())["items"][0]
    assert item["restricted"] is True and item["blocked_by"] == [] and item["reasons"] == [] and item["summary"].startswith("A restricted measure") and MARK not in item["summary"]
    assert item["who_unblocks"] == []


# ---- nothing restricted reaches the model through the plan wording ---------------------------------------------------------------------------
class Stub:
    def __init__(self):
        self.sent = []

    def complete(self, module_id, messages, tools=None):
        from sh_platform.egress.model import ModelReply
        self.sent.append(messages)
        return ModelReply("I1 = Waits for something.")


def test_a_restricted_items_reasons_never_reach_the_model(world):
    outsider, aid, listed, adir = placed(world)
    stub = Stub()
    world.app.state.lens_model_factory = lambda plane: stub
    assert outsider.post(plan_url(aid, "/plan/draft")).status_code == 200
    assert MARK not in json.dumps(stub.sent) and "ends on 2026-03-31" not in json.dumps(stub.sent)


def test_word_items_is_never_given_the_reasons_of_a_restricted_item():
    item = {"key": "next:r:K10", "band": "next", "measures": ["K10"], "restricted": True, "blocked_by": [MARK], "reasons": [MARK], "summary": "", "why_descoped": None}

    class Gate:
        def __getattr__(self, name):
            raise AssertionError("a restricted item must not make a call")
    out = plan_lens.word_items(Stub(), Gate(), "c", company_name="X", industry="y", items=[item], names={"K10": "Ten"})
    assert out[0]["summary"] == "A restricted measure: waiting on a decision." and MARK not in json.dumps(out[0]["summary"])


# ---- uploads on a source with a shut mark -----------------------------------------------------------------------------------------------------
def test_an_outsider_cannot_overwrite_a_restricted_sample_but_the_listed_person_can(world):
    outsider, aid, listed, adir = placed(world, with_findings=False)
    folder = adir / "intake" / "S01"
    before = {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    refused = outsider.post(intake_url(aid, "/sources/S01/upload"), json=payload("performance_workbook.xlsx"))
    assert refused.status_code == 409 and "restricted" in refused.json()["message"].lower()
    assert {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before
    key = next(iter(json.loads((folder / "from_profile.json").read_text())["files"]))["key"]
    again = outsider.post(intake_url(aid, "/sources/S01/upload"), json={"profile_sample": key})
    assert again.status_code in (404, 409) and {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before
    ok = listed.post(intake_url(aid, "/sources/S01/upload"), json=payload("performance_workbook.xlsx"))
    assert ok.status_code == 200 and ok.json()["profile"]["tables"]
    assert not (folder / "from_profile.json").exists() or not json.loads((folder / "from_profile.json").read_text())["files"]  # the mark is cleared
    assert outsider.get(intake_url(aid, "/sources/S01/profile")).json()["profile"]["tables"]  # it is the listed person's own upload now


# ---- sources_seen (non-blocking 1 of review 3) -------------------------------------------------------------------------------------------------
def test_findings_names_no_source_that_is_shut_for_the_viewer(world):
    outsider, aid, listed, adir = placed(world)
    doc = {**FINDINGS, "risks": [{"id": "RS", "kind": "risk", "source": "S01", "text": f"Source note {MARK}.", "measures": [], "pain_points": []}]}
    (adir / "findings.json").write_text(json.dumps(doc))
    got = outsider.get(plan_url(aid, "/findings")).json()
    assert MARK not in json.dumps(got) and [r["text"] for r in got["risks"]] == ["A restricted source has something open."]
    assert got["risks"][0]["source"] is None and got["risks"][0]["id"] != "RS"
    mine = listed.get(plan_url(aid, "/findings")).json()
    assert [r["text"] for r in mine["risks"]] == [f"Source note {MARK}."] and mine["risks"][0]["source"] == "S01"
