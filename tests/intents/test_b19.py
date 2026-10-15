"""B19 (file 33): the seven lines traced, the 7 of 7 gate, the hand-off, and build needed: no. Plane in a temporary folder, filled from the
synthetic ardmore baseline, charter and roles files; the routes are called with the access object the dependency would build."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from sh_platform.intents import build_ready as B
from sh_platform.intents import lifecycle as L
from sh_platform.intents import store as S
from sh_platform.intents.access import IntentAccess, IntentRefused
from sh_platform.plane import PlaneStore

SRC = Path(__file__).resolve().parents[2] / "data" / "ardmore" / "intents"
BID, OID, SID = "411bf9d90e77c248aac793c882b4b37f", "00a68d916b91396870d446e9f2c44158", "03cb51711272dffcb719d96a52ed5821"
ORG = {"account_id": "a-org", "name": "Janet Shaw"}
ADMIN = SimpleNamespace(name="Janet Shaw", roles=frozenset({"company_admin"}), account_id="a-org", shared_name=False)
OUTSIDER = SimpleNamespace(name="Aaron Lyle", roles=frozenset({"participant"}), account_id="a-p", shared_name=False)
ROLES = frozenset({"organiser", "company_admin", "content"})  # Janet: organiser and company admin

SEEDED = (SRC / "m2_baseline" / BID).is_dir()


@pytest.fixture
def world(tmp_path, monkeypatch, request):
    plane = PlaneStore(tmp_path).create("ardmore")
    dst = plane.path("intents")
    seedless = request.node.name == "test_handoff_is_the_organiser_only"  # the access rule needs no baseline files
    if not SEEDED and not seedless:
        pytest.skip("the seeded Ardmore plane is not loaded")
    if SEEDED:
        for rel in (f"m2_baseline/{BID}", f"m1_intent/outcomes/{OID}.json", f"m1_intent/roles/{SID}.json"):
            s, d = SRC / rel, dst / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(s, d) if s.is_dir() else shutil.copy(s, d)
        (dst / f"m2_baseline/{BID}/data_sources.json").unlink(missing_ok=True)  # the live plane has confirmations from other walks
        roles_file = dst / f"m1_intent/roles/{SID}.json"
        roles = json.loads(roles_file.read_text())
        roles["roles"]["developer"] = "Aaron Lyle"
        roles_file.write_text(json.dumps(roles))
    rec = L.new_record("initiative", "ardmore", ORG, S.now_iso(), title="Capital calls")
    rec.update(state="closing", refs={"wall_session_ids": [], "charter_outcome_id": OID, "baseline_ids": [BID], "assessment_ids": []})
    rec["people"]["sponsor"] = {"account_id": "a-spon", "name": "Daniel Kerr"}
    S.create_intent(plane, rec)
    monkeypatch.setattr(B, "_viewer", lambda r: ADMIN)

    def access(roles=ROLES):
        return IntentAccess(S.read_intent(plane, rec["id"]), roles, plane)

    return plane, rec["id"], SimpleNamespace(), access


def put_records(plane, confirmed=True):
    iid = next(p.name for p in plane.path("intents").iterdir() if p.name.startswith("ini-"))
    (plane.path("intents", iid) / "processes.json").write_text(json.dumps(
        {"processes": [{"id": "p1", "name": "Fund a call", "status": "active", "owner": {"value": "Harvey Rowley"}, "confirmed": confirmed}]}))
    owner = {"value": "Harvey Rowley", "mark": "stated", "by": "Janet Shaw"}
    cat = json.loads((plane.path("intents", "m2_baseline", BID) / "catalogue.json").read_text())
    ids = [r["Source ID"]["value"] for r in cat["sources"]]  # every source confirmed by its named source owner
    (plane.path("intents", "m2_baseline", BID) / "data_sources.json").write_text(json.dumps(
        {"sources": {i: {"source_owner": owner, "confirmed_by": "Harvey Rowley"} for i in ids}}))


def answer(req, access, value, reason=None):
    return B.put_intents_by_intent_id_build_needed(B.Answer(build_needed=value, reason=reason), req, access())


def lines_of(req, access) -> dict:
    return {x["n"]: x for x in B.get_intents_by_intent_id_build_ready(req, access())["lines"]}


def test_seven_lines_are_traced(world):
    plane, iid, req, access = world
    v = B.get_intents_by_intent_id_build_ready(req, access())
    lines = {ln["n"]: ln for ln in v["lines"]}
    assert len(lines) == 7 and all(ln["evidence"]["record"] for ln in lines.values())
    assert lines[1]["ok"] and (lines[1]["count"], lines[1]["of"]) == (1, 1)
    assert lines[2]["ok"] and lines[2]["of"] == 12
    assert lines[3]["ok"] and lines[3]["parts"] == {"technical": 12, "catalogue": 12, "governed": 12}
    assert lines[4]["text"] == "The process map is empty. Draw it first." and not lines[4]["ok"]  # no file yet: an empty map fails
    assert not lines[5]["ok"] and (lines[5]["count"], lines[5]["of"]) == (0, 8) and lines[5]["missing"][0]["fix"] == "Fix it in the data sources"
    assert lines[6]["ok"] and lines[7]["text"].startswith("Not answered")
    assert v["n_ok"] == 4 and v["verdict"] == "incomplete" and not v["can_hand_over"]
    assert v["stops"].startswith("Line 4 stops this")


def test_a_lens_draft_never_counts_and_zero_measures_fail(world):
    plane, iid, req, access = world
    g = plane.path("intents", "m2_baseline", BID, "glossary.json")
    data = json.loads(g.read_text())
    data["entries"][0]["business_definition"].update(mark="guessed", by="Lens", agent="lens")
    g.write_text(json.dumps(data))
    ln = lines_of(req, access)[2]
    assert not ln["ok"] and ln["count"] == 11 and ln["missing"][0]["state"] == "Drafted, not yet confirmed"
    plane.path("intents", "m2_baseline", BID, "kpis.json").write_text("[]")
    ln = lines_of(req, access)[2]
    assert not ln["ok"] and ln["text"] == "No measures are on the Must or Should shelf yet."


def test_seven_of_seven_gate_and_handoff(world):
    plane, iid, req, access = world
    put_records(plane, confirmed=False)
    answer(req, access, True)
    with pytest.raises(IntentRefused) as e:  # line 4 fails: the gate holds
        B.post_intents_by_intent_id_handoff(req, access())
    assert e.value.detail["error"] == "not_build_ready"
    put_records(plane)
    v = B.post_intents_by_intent_id_build_ready_check(req, access())
    assert (v["n_ok"], v["verdict"], v["can_hand_over"]) == (7, "ready", True), [(x["n"], x["text"]) for x in v["lines"] if not x["ok"]]
    out = B.post_intents_by_intent_id_handoff(req, access())
    rec = S.read_intent(plane, iid)
    assert rec["state"] == "closing" and rec["links"]["build"] == f"build:intake-{iid}"  # the hand-off is not a closure
    h = rec["build_handoff"]
    assert (h["measure_count"], h["source_count"], h["by"]["name"]) == (12, 8, "Janet Shaw") and len(h["lines_frozen"]) == 7
    assert rec["build_ready"]["state"] == "handed_over" and out["gap_analysis_href"] == f"/centre/build/gap-analysis?from={iid}"
    events = [json.loads(x) for x in (plane.path("intents", iid) / "events.jsonl").read_text().splitlines()]
    assert (events[-1]["kind"], events[-1]["detail"]) == ("handed_to_build", {})
    ho = out["handoff"]  # R16: room 0 receives the processes and the source map, strategic flags included
    assert [x["name"] for x in ho["processes"]] == ["Fund a call"] and len(ho["source_map"]) == 8
    assert all(isinstance(x["strategic"], bool) and x["zone"] for x in ho["source_map"])
    from sh_platform.build.home import room0
    assert room0(plane)["handed_over_from"]["title"] == "Capital calls"
    with pytest.raises(IntentRefused):  # once only
        B.post_intents_by_intent_id_handoff(req, access())


def test_build_needed_no_has_no_handoff(world):
    plane, iid, req, access = world
    with pytest.raises(IntentRefused) as e:
        answer(req, access, False)
    assert e.value.detail["error"] == "reason_required"
    v = answer(req, access, False, "The charter and glossary are the outcome")
    lines = {x["n"]: x for x in v["lines"]}
    assert lines[4]["text"] == lines[5]["text"] == "Not required: no build" and lines[4]["ok"] and lines[5]["ok"]
    assert v["verdict"] == "not_needed" and not v["can_hand_over"]
    with pytest.raises(IntentRefused):
        B.post_intents_by_intent_id_handoff(req, access())
    rec = S.read_intent(plane, iid)
    assert rec["links"]["build"] is None and not rec.get("build_handoff")
    assert rec["build_needed"] is False and rec["build_needed_by"]["name"] == "Janet Shaw"
    v = answer(req, access, None)  # change the answer
    assert S.read_intent(plane, iid)["build_needed"] is None and v["verdict"] == "incomplete"


def test_a_sealed_measure_is_counted_never_named(world, monkeypatch):
    plane, iid, req, access = world
    gs = plane.path("intents", "m2_baseline", BID, "governed_state.json")
    data = json.loads(gs.read_text())
    data["K01"]["classification"]["value"] = "restricted"
    data["K01"]["owners"]["mark"] = "guessed"  # K01 now fails line 3, so it would be named
    gs.write_text(json.dumps(data))
    seen = lambda: json.dumps(B.get_intents_by_intent_id_build_ready(req, access()))  # noqa: E731
    assert "Minimum six-month funding headroom" in seen()  # the company admin may see it
    monkeypatch.setattr(B, "_viewer", lambda r: OUTSIDER)
    text = seen()
    assert "Minimum six-month funding headroom" not in text and "1 sealed measure, counted" in text


def test_handoff_is_the_organiser_only(world):
    """R15: only the organiser hands over. The sponsor, the company admin without the organiser seat and a participant are refused."""
    from sh_platform.intents.access import Me, require_intent_role
    plane, iid, req, access = world
    rec, post = S.read_intent(plane, iid), SimpleNamespace(method="POST", state=SimpleNamespace(), url=SimpleNamespace(path="/x"))
    rec["people"]["participants"] = [{"account_id": "a-p", "name": "Aaron Lyle"}]
    route = B.post_intents_by_intent_id_handoff.__defaults__[-1].dependency.__closure__[0].cell_contents
    assert route == {"organiser"}
    ok = lambda me: require_intent_role(post, rec, route, plane=plane, me=me)  # noqa: E731
    assert "organiser" in ok(Me("a-org", "Janet Shaw", frozenset({"company_admin"})))
    for me in (Me("a-spon", "Daniel Kerr", frozenset({"sponsor"})), Me("a-admin", "Another Admin", frozenset({"company_admin"})),
               Me("a-p", "Aaron Lyle", frozenset({"participant"}))):
        with pytest.raises(IntentRefused) as e:
            ok(me)
        assert e.value.status_code == 403


def test_nudge_names_the_person_and_says_when_it_was_not_sent(world):
    plane, iid, req, access = world
    with pytest.raises(IntentRefused) as e:  # line 4 is empty: nobody is named on that row
        B.post_intents_by_intent_id_build_ready_nudge(B.Nudge(line=4), req, access())
    assert e.value.detail["error"] == "no_one_named"
    put_records(plane, confirmed=False)
    out = B.post_intents_by_intent_id_build_ready_nudge(B.Nudge(line=4), req, access())
    assert out["to"] == "Harvey Rowley" and out["text"].startswith("Harvey, the build-ready check is waiting")
    assert out["sent"] is False and "not sent" in out["note"]  # the synthetic plane has no sign-in for him: the draft is shown, not sent



def test_verdict_change_writes_build_ready_changed_and_hand_over_writes_handed_to_build(tmp_path):
    from types import SimpleNamespace
    from sh_platform.intents import events
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(tmp_path).create("acme")
    v = SimpleNamespace(account_id="a-org", name="Janet")
    B._event(plane, "i1", v, "not_ready", "ready")
    B._event(plane, "i1", v, "ready", "handed_over")
    kinds = [json.loads(x)["kind"] for x in plane.path("intents", "i1", "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[-2:] == ["build_ready_changed", "handed_to_build"] and "state_changed" not in kinds
