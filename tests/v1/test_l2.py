"""L2 proposed changes: an agent's patch waits for a yes (the document is untouched), accept applies once and leaves a resolved `change`
comment on the document line, reject leaves the document alone and hands the reason to the agent, the person's own edit survives, a pending
proposal is never document content, the words yes and no settle a proposal in chat, and only people who may write accept."""
import json
import shutil
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import i4_sow as S
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import p1_project as P1
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
CREDS = SEED / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("l2") / "data"
    shutil.copytree(SEED, data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def plane_of(app):
    return PlaneStore(Path(app.state.settings.data_root)).plane_for("neera")


class Stub:
    def __init__(self, answer: dict):
        self.answer, self.seen = answer, []

    def complete(self, module_id, messages, tools=None):
        self.seen.append(messages)
        return ModelReply(text=json.dumps(self.answer))


def north(patch, steps=None, reply="Who reads it?"):
    return {"reply": reply, "sow_patch": patch, "process_steps": steps, "covered": ["goal"], "ready": False}


NET = {"kpis": [{"name": "Net worth", "definition": "Everything owned less everything owed", "period": "monthly"}]}


def talk(app, c, stub, text, iid=None):
    app.state.build_model_factory = lambda plane: stub
    try:
        r = c.post(f"/api/v1/intents/{iid}/chat" if iid else "/api/v1/intents/chat", json={"text": text})
    finally:
        del app.state.build_model_factory
    assert r.status_code == 200, r.text
    return r.json()


def accept(c, iid, p):
    return c.post(f"/api/v1/intents/{iid}/proposals/{p['id']}/accept")


def sow_of(c, iid):
    return c.get(f"/api/v1/intents/{iid}/chat").json()["sow"]


def test_propose_leaves_the_document_alone_and_accept_applies_once_with_a_comment(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth by entity every month")
    iid = t["id"]
    p = next(x for x in t["proposals"]["pending"] if x["document"] == "sow")
    assert t["sow"]["kpis"] == [] and p["by"] == "north" and "Net worth" in json.dumps(p["changes"]) and "payload" not in p
    assert p["changes"][0]["op"] == "add" and t["turns"][-1]["text"].endswith("or tell me what is wrong.")
    assert list(plane_of(app).path("projects").glob("prj-*/proposals.json"))  # beside the project's comments

    assert accept(c, iid, p).status_code == 200
    assert accept(c, iid, p).status_code == 409  # applied once
    assert [k["name"] for k in sow_of(c, iid)["kpis"]] == ["Net worth"]

    plane = plane_of(app)
    got = [x for x in P1.comments(plane, P1.for_intent(plane, iid)["id"], "intent") if x["kind"] == "change"]
    assert len(got) == 1 and got[0]["state"] == "resolved" and got[0]["text"].startswith("North changed ") and got[0]["text"].endswith("accepted by Arjun Mehta")
    assert got[0]["line_ref"]  # the line of the document it touched


def test_two_accepts_at_once_apply_once(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth for the family")
    iid, plane = t["id"], plane_of(app)
    pid = next(x for x in t["proposals"]["pending"] if x["document"] == "sow")["id"]
    out, barrier = [], threading.Barrier(2)

    def go():
        barrier.wait()
        try:
            out.append(L2.accept(plane, iid, pid, "Arjun Mehta")["status"])
        except L2.Refused as e:
            out.append(str(e.status))
    ts = [threading.Thread(target=go) for _ in range(2)]
    [x.start() for x in ts]
    [x.join() for x in ts]
    assert sorted(out) == ["409", "accepted"]
    assert [k["name"] for k in sow_of(c, iid)["kpis"]] == ["Net worth"]
    assert len([x for x in P1.comments(plane, P1.for_intent(plane, iid)["id"], "intent") if x["kind"] == "change"]) == 1


def test_reject_leaves_the_document_and_the_reason_reaches_the_next_turn(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth by entity")
    iid = t["id"]
    p = next(x for x in t["proposals"]["pending"] if x["document"] == "sow")
    r = c.post(f"/api/v1/intents/{iid}/proposals/{p['id']}/reject", json={"reason": "We count private funds at cost"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert sow_of(c, iid)["kpis"] == []
    stub = Stub(north({}))
    talk(app, c, stub, "Anything else you need?", iid)
    ctx = json.loads(stub.seen[0][1]["content"])["context"]
    assert "We count private funds at cost" in ctx["turned_down_by_the_person"][0]  # one string each (NI1): a list of objects is rows to the gateway


def test_yes_and_no_in_chat_settle_the_pending_proposal(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth by entity monthly")
    iid = t["id"]
    t = talk(app, c, Stub(north({})), "yes", iid)
    assert [k["name"] for k in t["sow"]["kpis"]] == ["Net worth"] and t["proposals"]["pending"] == []

    t = talk(app, c, Stub(north({"kpis": [{"name": "Net worth", "definition": "Assets only"}]})), "Make it assets only", iid)
    assert len(t["proposals"]["pending"]) == 1 and t["sow"]["kpis"][0]["definition"].startswith("Everything owned")
    t = talk(app, c, Stub(north({})), "No, liabilities count too", iid)
    assert t["proposals"]["pending"] == [] and t["sow"]["kpis"][0]["definition"].startswith("Everything owned")
    assert t["proposals"]["recent"][-1]["status"] == "rejected" and "liabilities" in t["proposals"]["recent"][-1]["reason"]


def test_a_persons_own_edit_survives_a_later_proposal_even_before_the_first_is_accepted(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north({"goal": {"why": "North's first words", "needed_by": "June"}})), "A pack for the board")
    iid = t["id"]
    assert c.put(f"/api/v1/intents/{iid}/sow", json={"section": "goal", "field": "why", "value": "My own words"}).status_code == 200
    for p in t["proposals"]["pending"]:
        assert accept(c, iid, p).status_code == 200
    goal = sow_of(c, iid)["goal"]
    assert goal["why"] == "My own words" and goal["needed_by"] == "June"  # the edit made while the proposal waited stands

    t = talk(app, c, Stub(north({"goal": {"why": "North's second words", "readers": ["the board"]}})), "Who reads it? The board.", iid)
    for p in t["proposals"]["pending"]:
        assert accept(c, iid, p).status_code == 200
    goal = sow_of(c, iid)["goal"]
    assert goal["why"] == "My own words" and goal["readers"] == ["the board"]


def test_a_pending_proposal_is_not_document_content(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north({"kpis": [{"name": "Zebra index", "definition": "Stripes counted"}]})), "A zebra index")
    iid, plane = t["id"], plane_of(app)
    assert t["proposals"]["pending"]
    prj = P1.for_intent(plane, iid)
    assert "Zebra" not in json.dumps(P1.document(plane, prj["id"], "intent"))  # the numbered lines and their comments
    raw = plane.path("intents", iid, "sow.json").read_text(encoding="utf-8")
    assert "Zebra" not in raw and "Zebra" not in json.dumps(S._blocks(json.loads(raw)))
    assert "Zebra" not in json.dumps([x for x in P1.comments(plane, prj["id"]) if x["kind"] != "change"])


def test_only_people_who_may_write_accept(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth for the office")
    iid = t["id"]
    p = t["proposals"]["pending"][0]
    other = client(app, LEELA)  # not on this Internal project's team
    assert other.get(f"/api/v1/intents/{iid}/proposals").status_code == 403
    assert accept(other, iid, p).status_code == 403
    assert c.get(f"/api/v1/intents/{iid}/proposals").json()["pending"]  # the raiser may list


def test_a_change_with_no_effect_makes_no_proposal(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth monthly")
    iid = t["id"]
    for p in t["proposals"]["pending"]:
        assert accept(c, iid, p).status_code == 200
    t = talk(app, c, Stub(north(NET)), "Is that all?", iid)  # the same patch again changes nothing
    assert t["proposals"]["pending"] == [] and "proposed" not in t["turns"][-1]["text"]


# ---- fixes after review ---------------------------------------------------------------------------------------------------------

def test_pending_proposals_stack_and_one_yes_accepts_all(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth by entity every month")
    iid = t["id"]
    t = talk(app, c, Stub(north({"goal": {"readers": ["the board"]}})), "The board, monthly.", iid)
    assert len(t["proposals"]["pending"]) == 2  # the KPI is still waiting
    t = talk(app, c, Stub(north({})), "yes", iid)
    assert t["proposals"]["pending"] == [] and [k["name"] for k in t["sow"]["kpis"]] == ["Net worth"] and t["sow"]["goal"]["readers"] == ["the board"]
    assert not [p for p in t["proposals"]["recent"] if p["status"] == "replaced"]


def test_words_only_short_or_outright_messages_decide():
    assert L2.words("No, we have never measured it") is None
    assert L2.words("No, we have never measured it, but the board asks for it every single quarter") is None
    assert L2.words("No, liabilities count too") == "reject" and L2.words("no") == "reject"
    assert L2.words("Not this. We have never measured it and I would like to start from the board pack instead") == "reject"
    assert L2.words("Don't change the definition, we have always counted private funds at cost") == "reject"
    assert L2.words("Approved by the board last year") is None and L2.words("OK so the board reads it monthly") is None
    assert L2.words("yes") == "accept" and L2.words("Yes, please go ahead") == "accept" and L2.words("looks good, thanks") == "accept"


def test_a_long_no_is_an_answer_not_a_rejection(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north(NET)), "Net worth by entity monthly")
    iid = t["id"]
    t = talk(app, c, Stub(north({})), "No, we have never measured it, so there is no benchmark figure to give you today", iid)
    assert len(t["proposals"]["pending"]) == 1


def _brief_proposal(app):
    c = client(app, ARJUN)
    t = talk(app, c, Stub(north({"goal": {"why": "Brief test"}})), "A pack for the family")
    iid, plane = t["id"], plane_of(app)
    p = L2.propose(plane, iid, "brief", None, [{"op": "add", "path": "kpis/Net worth", "before": "", "after": "x"}], payload={"patch": {}, "codes": {}, "feeds": {}})
    return iid, plane, p


def test_a_signed_document_refuses_accept_and_its_pending_proposals_are_superseded(app):
    iid, plane, p = _brief_proposal(app)
    P1.signed(plane, P1.for_intent(plane, iid)["id"], "brief", "Arjun Mehta")
    with pytest.raises(L2.Refused) as e:
        L2.accept(plane, iid, p["id"], "Arjun Mehta")
    assert e.value.status == 409 and "signed" in e.value.message
    row = next(x for x in L2._read(plane, iid) if x["id"] == p["id"])
    assert row["status"] == "superseded" and "signed" in row["reason"]

    p2 = L2.propose(plane, iid, "mapping", None, [{"op": "add", "path": "rows/a/rule", "before": "", "after": "y"}], payload={})
    assert any(x["id"] == p2["id"] for x in L2.view(plane, iid)["pending"])  # the build pack is not signed
    P1.signed(plane, P1.for_intent(plane, iid)["id"], "build_pack", "Leela")
    v = L2.view(plane, iid)
    assert not [x for x in v["pending"] if x["document"] in ("brief", "mapping")]
    assert next(x for x in L2._read(plane, iid) if x["id"] == p2["id"])["status"] == "superseded"


def test_an_applying_proposal_left_by_a_crash_is_offered_again(app):
    iid, plane, p = _brief_proposal(app)
    L2._claim(plane, iid, p["id"])
    assert not [x for x in L2.pending(plane, iid) if x["id"] == p["id"]]  # being applied just now
    L2._set(plane, iid, p["id"], applying_at="2020-01-01T00:00:00+00:00")
    assert [x for x in L2.pending(plane, iid) if x["id"] == p["id"]]  # a minute on: offered again
    assert L2._claim(plane, iid, p["id"])["status"] == "applying"


def test_flow_accept_leaves_the_engineers_hand_edit_alone(app, tmp_path, monkeypatch):
    from sh_platform.v1 import f1_chat as F
    row = {"n": 1, "target_table": "t", "target_field": "f", "source_field": "a", "rule": "sum by entity, excluding trusts", "transformation": ""}
    seen = {}
    monkeypatch.setattr(F, "_path", lambda plane, iid: tmp_path / "f.json")
    monkeypatch.setattr(F, "_record", lambda plane, iid: {"answers": {}, "flagged": {}})
    monkeypatch.setattr(F, "_sheet", lambda plane, iid: {"rows": [row]})
    monkeypatch.setattr(F, "points", lambda plane, iid, rec: [])
    monkeypatch.setattr(F, "apply", lambda plane, iid, point, r, got: (seen.update(got=got) or True, ""))
    p = {"changes": [{"path": "rows/t.f/rule", "before": "sum by entity"}, {"path": "rows/t.f/transformation", "before": ""}],
         "payload": {"point": {"key": "k"}, "row": 1, "got": {"decision": "change", "rule": "sum", "transformation": "total"}, "text": "x", "who": "w"}}
    note = F.apply_proposal(None, "i", p, "Leela")
    assert "rule" in note and "rule" not in seen["got"] and seen["got"]["transformation"] == "total"
    p["changes"] = p["changes"][:1]
    p["payload"]["got"] = {"decision": "change", "rule": "sum"}
    with pytest.raises(F.M.Refusal):
        F.apply_proposal(None, "i", p, "Leela")
