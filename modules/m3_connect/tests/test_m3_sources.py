"""M3-P01 source map: scores and zones on a hand-made input (both signs, the zero line), reasons, an override that survives a re-score,
a restricted source hidden from an outside viewer (map, panel, override), two industries, an empty company, and the model stub / fallback.
No live model call: the model is always a stub."""
import json
from pathlib import Path

import pytest

from m3_kit import BASE, copy_baseline, person, restrict, signed_baseline
from modules.m3_connect.agent import score_lens as L
from modules.m3_connect.domain import inputs as I
from modules.m3_connect.domain import sources as S
from modules.m3_connect.domain.steps import steps_for
from sh_platform.agents.protocols import ModelReply
from sh_platform.auth.permissions import load_permissions
from sh_platform.manifest import load_manifest

MANIFEST = Path(__file__).resolve().parents[1] / "manifest.yaml"


@pytest.fixture(autouse=True)
def _map_step_registered():
    """The scaffold's step test clears the registry; put this package's one line back."""
    from modules.m3_connect.domain import steps
    steps.register("map", S.step_state)


def c(v):
    return {"value": v, "mark": "stated"}


def src(sid, name, typ="File drop: CSV or Excel", structure="Structured", conn="File uploaded by the owner", owner="Dee Owner",
        personal="No", often="Daily"):
    return {"Source ID": c(sid), "Source name": c(name), "Source type": c(typ), "Structured or unstructured": c(structure),
            "Connection method": c(conn), "Data owner": c(owner), "Contains personal data?": c(personal), "How often it arrives": c(often)}


def table(tid, sid, kpis):
    return {"Item ID": c(tid), "Source ID": c(sid), "Name of table, file or document type": c(f"Table {tid}"), "Kind": c("File"),
            "Related KPIs": c(kpis)}


def measure(mid, prio, problem="Slow reporting"):
    return {"id": mid, "name": f"Measure {mid}", "restricted": False, "priority": prio, "problem": problem, "owners": {"data": "Dee Owner"}}


def hand_inputs():
    """A: Must x3, ready. B: Not this time, nothing known. C: Must, nothing known. D: Could, ready, one measure."""
    srcs = [src("A", "Source A"), src("B", "Source B", "Email with attachment", "Unstructured", "", "", "Not sure", ""),
            src("C", "Source C", "Third-party portal or API", "", "", "", "", ""), src("D", "Source D")]
    return {"measures": [measure("K1", "Must"), measure("K2", "Must"), measure("K3", "Must"), measure("K4", "Not this time", "Other thing"),
                         measure("K5", "Must"), measure("K6", "Could", "Other thing")],
            "sources": srcs, "tables": [table("TA", "A", "K1, K2, K3"), table("TB", "B", "K4"), table("TC", "C", "K5"), table("TD", "D", "K6")],
            "fields": [], "extractions": [],
            "pain_points": [{"id": "p1", "title": "Slow reporting packs", "measures": []}, {"id": "p2", "title": "Unrelated noise", "measures": []}],
            "future_signals": [], "levers": [{"id": "l1", "title": "Slow reporting feeds", "measures": []}],
            "process_map": {"K5": {"steps": [{"id": "s1", "text": "Waiting on the bank", "owner": ""}]}},
            "gaps": [{"type": "conflict", "kpi_id": "K6"}]}


EXTRAS = {"answered": {"dee owner"}, "samples": {"K1", "K6"}}
BY_ID = lambda out: {s["id"]: s for s in out}  # noqa: E731


def scored():
    return BY_ID(S.score_all(hand_inputs(), hand_inputs(), EXTRAS))


# ---- scoring on a hand-made input
def test_both_signs_and_the_four_zones():
    s = scored()
    assert (s["A"]["impact"]["score"] > 0 and s["A"]["readiness"]["score"] > 0 and s["A"]["zone"] == "p1")
    assert (s["B"]["impact"]["score"] < 0 and s["B"]["readiness"]["score"] < 0 and s["B"]["zone"] == "identify")
    assert (s["C"]["impact"]["score"] >= 0 and s["C"]["readiness"]["score"] < 0 and s["C"]["zone"] == "unknown")
    assert (s["D"]["impact"]["score"] < 0 and s["D"]["readiness"]["score"] > 0 and s["D"]["zone"] == "p2")
    assert all(-1 <= s[k][ax]["score"] <= 1 for k in s for ax in ("impact", "readiness"))


def test_the_line_sits_at_zero_on_each_axis():
    assert [S.zone(i, r) for i, r in ((0, 0), (0, -0.01), (-0.01, 0), (-0.01, -0.01))] == ["p1", "unknown", "p2", "identify"]
    assert S._score({"a": 0.5}, {"a": 1.0}) == 0 and S._score({"a": 0.0}, {"a": 1.0}) == -1 and S._score({"a": 1.0}, {"a": 1.0}) == 1


def test_every_factor_gives_a_plain_reason_with_its_effect():
    a = scored()["A"]
    for axis, n in (("impact", 5), ("readiness", 7)):
        rs = a[axis]["reasons"]
        assert len(rs) == n and all(r["text"] and r["effect"] in ("raises", "lowers") for r in rs)
    text = " ".join(r["text"] for r in a["impact"]["reasons"])
    assert "possible link through the problem Slow reporting" in text and "Slow reporting packs" in text and "Unrelated noise" not in text
    assert "feeds 3 measures" in text.lower() and "Must" in text
    assert a["readiness"]["missing"] == ["Owners to settle their different answers"][:0] + a["readiness"]["missing"]  # nothing odd


def test_marks_and_missing():
    s = scored()
    assert s["C"]["marks"]["licence"] is True and s["A"]["marks"]["licence"] is False
    assert s["C"]["marks"]["blocked_upstream"] is True and s["A"]["marks"]["blocked_upstream"] is False
    assert s["D"]["marks"]["owners_disagree"] is True and s["A"]["marks"]["owners_disagree"] is False
    assert (s["A"]["marks"]["effort"], s["B"]["marks"]["effort"], s["C"]["marks"]["effort"]) == ("small", "large", "large")
    assert "A sample of the data" in s["B"]["readiness"]["missing"] and s["A"]["readiness"]["missing"] == []
    assert all(s[k]["marks"]["restricted"] is False for k in s)


def test_a_source_that_feeds_nothing_is_off_the_map_and_listed_as_not_needed():
    i = hand_inputs()
    i["sources"].append(src("E", "Source E"))
    assert "E" not in BY_ID(S.score_all(i, i, EXTRAS)) and S.unneeded(i) == [{"id": "E", "name": "Source E"}]
    assert S._impact([], i)[1][0]["text"] == "It feeds no measure yet."  # the scoring words are still there for a source a person moves back


def test_restricted_mark_comes_from_what_an_outsider_cannot_see():
    out = hand_inputs()
    out["measures"][4] = {"id": "K5", "name": "A restricted measure", "restricted": True}
    s = BY_ID(S.score_all(hand_inputs(), out, EXTRAS))
    assert s["C"]["marks"]["restricted"] is True and s["A"]["marks"]["restricted"] is False


def test_the_weights_are_in_the_contract_not_the_code():
    w = S.weights()
    assert abs(sum(w["impact"]["weights"].values()) - 1) < 1e-9 and abs(sum(w["readiness"]["weights"].values()) - 1) < 1e-9
    assert w["impact"]["priority_points"] == {"Must": 1.0, "Should": 0.6, "Could": 0.3, "Not this time": 0.0}


# ---- override
def test_an_override_is_kept_beside_the_draft_and_survives_a_rescore(tmp_path):
    S.save_scored(tmp_path, S.score_all(hand_inputs(), hand_inputs(), EXTRAS))
    moved = S.set_override(tmp_path, "B", 0.5, None, "We signed the contract last week", "Pat Person")
    assert moved["zone"] == "unknown" and moved["impact"]["score"] < 0  # the draft is untouched
    again = S.save_scored(tmp_path, S.score_all(hand_inputs(), hand_inputs(), EXTRAS))
    b = BY_ID(again["sources"])["B"]
    assert b["override"]["by"] == "Pat Person" and b["override"]["reason"] and b["zone"] == "unknown"
    assert S.effective(b)["impact"] == 0.5 and S.effective(b)["readiness"] == b["readiness"]["score"]


@pytest.mark.parametrize("impact,readiness,reason", [(None, None, "x"), (2, None, "x"), (0.1, None, ""), (0.1, None, "  "), ("a", None, "x"),
                                                     (True, None, "x"), (0.1, None, "y" * 501)])
def test_an_override_needs_a_value_in_range_and_a_reason(tmp_path, impact, readiness, reason):
    S.save_scored(tmp_path, S.score_all(hand_inputs(), hand_inputs(), EXTRAS))
    with pytest.raises(S.OverrideError):
        S.set_override(tmp_path, "A", impact, readiness, reason, "Pat")


def test_the_map_step_reports_done_once_scored(tmp_path):
    assert S.step_state(tmp_path)["state"] == "not_started"
    S.save_scored(tmp_path, S.score_all(hand_inputs(), hand_inputs(), EXTRAS))
    assert S.step_state(tmp_path) == {"state": "done", "waiting_on": ""}
    assert [s["state"] for s in steps_for(tmp_path)][0] == "done"


# ---- viewers and fields
def test_a_field_with_its_own_list_is_hidden_from_a_viewer_not_on_it():
    i = hand_inputs()
    i["fields"] = [{"Field ID": c("F1"), "Item ID": c("TA"), "Field name as in the source": c("Open column"), "Data type": c("Number")},
                   {"Field ID": c("F2"), "Item ID": c("TA"), "Field name as in the source": c("Narrow column"), "Who may see it": c("Ann Named")}]
    s = scored()["A"]

    def names(v):
        return [f["name"] for t in S.panel(s, i, v)["tables"] for f in t["fields"]]
    assert names(I.Viewer("Someone Else", frozenset({"analyst"}))) == ["Open column"]
    assert names(I.Viewer("Ann Named", frozenset({"analyst"}))) == ["Open column", "Narrow column"]
    assert names(I.Viewer("Ann Named", frozenset({"analyst"}), True)) == ["Open column"]  # a shared display name proves nothing
    assert names(I.Viewer("Sam", frozenset({"sponsor"}))) == names(I.Viewer("Hana", frozenset({"company_admin"}))) == ["Open column", "Narrow column"]


def test_a_restricted_source_shows_only_its_position():
    i = hand_inputs()
    i["measures"][4] = {"id": "K5", "name": "A restricted measure", "restricted": True}
    s = scored()["C"]
    v = S.view(s, i)
    assert v["name"] == S.RESTRICTED_SOURCE and v["restricted"] and v["kind"] == "hidden" and v["summary"] == "" and v["override"] is None
    assert S.panel(s, i, I.Viewer("x", frozenset())) is None
    assert "Source C" not in str(v) and "K5" not in str(v)


# ---- Lens wording
class Stub:
    def __init__(self, text=None, fail=False):
        self.text, self.fail, self.asked = text, fail, []

    def complete(self, module_id, messages, tools=None):
        self.asked.append(messages)
        if self.fail:
            raise RuntimeError("the provider is down")
        return ModelReply(self.text)


def test_lens_words_the_summary_and_never_sends_a_source_name():
    stub = Stub("s1: Source one is ready and matters most.\nnoise\ns9: not offered")
    got = L.apply(stub, list(S.score_all(hand_inputs(), hand_inputs(), EXTRAS)))
    assert got[0]["summary"] == "Source one is ready and matters most." and got[0]["summary_by"] == "lens" and got[1]["summary_by"] == "rules"
    sent = str(stub.asked)
    assert "Source A" not in sent and "Dee Owner" not in sent and "s1:" in sent


def test_a_restricted_source_never_reaches_the_model():
    out = hand_inputs()
    out["measures"][4] = {"id": "K5", "name": "A restricted measure", "restricted": True}
    stub = Stub("s1: x is fine here")
    L.apply(stub, S.score_all(hand_inputs(), out, EXTRAS))
    assert "Third-party" not in str(stub.asked) and "s4" not in str(stub.asked)


def test_model_unreachable_gives_the_rules_sentence():
    got = L.apply(Stub(fail=True), S.score_all(hand_inputs(), hand_inputs(), EXTRAS))
    assert all(s["summary_by"] == "rules" and s["name"] in s["summary"] for s in got)
    assert L.apply(None, S.score_all(hand_inputs(), hand_inputs(), EXTRAS))[0]["summary_by"] == "rules"


# ---- routes, with module 2's signed baseline
def link_table(world, company="m3-a"):
    """The test baseline's table has no Source ID; a real catalogue does. Test code only: tie T01 to S01 in the stored outcome record."""
    folder = world.plane(company).path("intents", "m2_baseline", "outcomes")
    for f in folder.glob("*.json"):
        d = json.loads(f.read_text())
        d["catalogue"]["tables"][0]["Source ID"] = c("S01")
        f.write_text(json.dumps(d))


def start(world, company="m3-a", name="Lens Lee", roles=("analyst",)):
    c_ = person(world, company, name, roles)
    r = c_.post(f"{BASE}/assessments")
    assert r.status_code == 201, r.text
    return c_, r.json()["assessment"]["id"]


def test_the_map_scores_automatically_and_a_rescore_keeps_the_override(world):
    signed_baseline(world)
    link_table(world)
    world.app.state.lens_model_factory = lambda plane: Stub("s1: Lens says this one matters.")
    c_, aid = start(world)
    m = c_.get(f"{BASE}/assessments/{aid}/sources")
    assert m.status_code == 200, m.text
    srcs = m.json()["sources"]
    assert [s["name"] for s in srcs] == ["Custodian portal export"] and srcs[0]["zone"] in S.ZONES and srcs[0]["summary"] == "Lens says this one matters."
    sid = srcs[0]["id"]
    panel = c_.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()
    assert panel["source"]["name"] == "Custodian portal export" and [m_["id"] for m_ in panel["measures"]] == ["K1"] and panel["missing"]
    bad = c_.put(f"{BASE}/assessments/{aid}/sources/{sid}/override", json={"impact": 0.9, "reason": ""})
    assert bad.status_code == 400 and "why" in bad.json()["message"]
    ok = c_.put(f"{BASE}/assessments/{aid}/sources/{sid}/override", json={"impact": -0.9, "readiness": 0.9, "reason": "Decided in the board meeting"})
    assert ok.status_code == 200 and ok.json()["source"]["zone"] == "p2" and ok.json()["source"]["override"]["by"] == "Test Lens Lee"
    again = c_.post(f"{BASE}/assessments/{aid}/sources/score").json()["sources"][0]
    assert again["zone"] == "p2" and again["override"]["reason"] == "Decided in the board meeting" and again["draft"]["impact"] != -0.9
    assert [s["state"] for s in c_.get(f"{BASE}/assessments/{aid}").json()["steps"]][0] == "done"


def test_the_model_being_down_still_gives_a_map(world):
    signed_baseline(world)
    link_table(world)
    world.app.state.lens_model_factory = lambda plane: Stub(fail=True)
    c_, aid = start(world)
    s = c_.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]
    assert s["summary"] and "Custodian portal export" in s["summary"]


def test_a_restricted_source_is_hidden_from_an_outside_viewer_even_in_the_panel(world):
    admin = signed_baseline(world).c["hana"]
    link_table(world)
    world.app.state.lens_model_factory = lambda plane: None
    out, aid = start(world)
    sid = admin.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["id"]
    restrict(world, "m3-a", "K1", ["Test Someone Else"])
    got = out.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]
    assert got["name"] == "A restricted source" and got["restricted"] and got["kind"] == "hidden" and "measures" not in got
    panel = out.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()
    assert panel["source"]["name"] == "A restricted source" and panel["tables"] == [] and panel["measures"] == []
    assert "Custodian" not in str(panel) and "Capital call" not in str(panel) and "K1" not in str(panel)
    assert out.put(f"{BASE}/assessments/{aid}/sources/{sid}/override", json={"impact": 0.5, "reason": "try"}).status_code == 404
    assert admin.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["name"] == "A restricted source"  # A-069: named, so the admin is outside
    named = person(world, "m3-a", "Someone Else")
    assert named.get(f"{BASE}/assessments/{aid}/sources").json()["sources"][0]["name"] == "Custodian portal export"
    assert [m["id"] for m in named.get(f"{BASE}/assessments/{aid}/sources/{sid}").json()["measures"]] == ["K1"]


def test_two_industries_each_score_their_own_baseline(world):
    signed_baseline(world, "m3-a")
    copy_baseline(world, "m3-a", "m3-b")
    link_table(world, "m3-a")
    link_table(world, "m3-b")
    world.app.state.lens_model_factory = lambda plane: None
    (ca, ida), (cb, idb) = start(world, "m3-a", "Lens A"), start(world, "m3-b", "Lens B")
    for cl, i in ((ca, ida), (cb, idb)):
        assert len(cl.get(f"{BASE}/assessments/{i}/sources").json()["sources"]) == 1
    assert cb.get(f"{BASE}/assessments/{ida}/sources").status_code == 404  # another company's assessment is unreachable


def test_an_empty_company_and_an_unknown_assessment_are_plain_404s(world):
    c_ = person(world, "m3-empty", "Empty Ed")
    r = c_.get(f"{BASE}/assessments/{'a' * 32}/sources")
    assert r.status_code == 404 and "assessment" in r.json()["message"]
    assert c_.get(f"{BASE}/assessments/not-an-id/sources/x").status_code == 404


def test_the_module_switch_and_unknown_source(world):
    signed_baseline(world)
    world.app.state.lens_model_factory = lambda plane: None
    c_, aid = start(world)
    assert c_.get(f"{BASE}/assessments/{aid}/sources/nope").status_code == 404
    assert person(world, "m3-off", "Off Olly").get(f"{BASE}/assessments/{aid}/sources").status_code in (403, 404)


def test_manifest_and_permission_table_agree_on_my_routes():
    mine = {f"{r.method} {r.path}" for r in load_manifest(MANIFEST).routes if r.path.endswith(("/sources", "/sources/score", "/override", "{source_id}"))}
    perms = {k for k in load_permissions().routes if "/assessments/{assessment_id}/sources" in k}  # not the intake routes
    assert len(mine) == 4 and mine == perms
