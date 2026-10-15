"""B26: Lens in Define, with the model stubbed: nine kinds in order, guessed cells with a source, the cap of three, the send-back loop,
the drafting state and the failure path, and a sealed card never read."""
import json

import pytest

from sh_platform.agents.protocols import ModelReply
from sh_platform.intents import lens as L
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store

ID = "i1"
SEALED = "the secret merger plan"
ANON_AUTHOR = "ethan-ng"


class Stub:
    """Answers by what Lens was asked; records every prompt so a test can look for what must never be in one."""

    def __init__(self, fail=False):
        self.fail, self.prompts = fail, []

    def complete(self, module_id, messages, tools=None):
        self.prompts.append(json.dumps(messages))
        if self.fail:
            raise RuntimeError("down")
        q = json.loads(messages[-1]["content"])["question"]
        text = ("The monthly return of the fund." if "Draft the definition" in q or "Redraft the definition" in q else
                "SOURCES: src_a\nCALCULATION: UNKNOWN\nMISSING: the formula" if "technical definition" in q else
                "Receive the file\nCheck the file" if "steps of the process" in q else
                "net | policy\ngross | interview" if "different meaning" in q else "UNKNOWN")
        return ModelReply(text=text)


def card(text, sealed=False, anonymous=False):
    c = lambda v: {"value": v, "mark": "stated", "by": "Ethan", "at": "2026-10-06T00:00:00+00:00", "from": "A note"}  # noqa: E731
    return {"lane": c("missing"), "sealed": c(sealed), "anonymous": c(anonymous), "author": c(ANON_AUTHOR), "q1": c(text), "q2": c(None), "q3": c(None), "q4": c(None)}


@pytest.fixture
def plane(tmp_path):
    p = PlaneStore(tmp_path).create("acme")
    doc = store.empty()
    doc["cards"] = {"a": card("Fund returns arrive late"), "b": card(SEALED, sealed=True), "c": card("Returns file is wrong", anonymous=True)}
    write_json_atomic(store._file(p), doc)
    write_json_atomic(p.path("intents", ID, "intent.json"), {
        "id": ID, "people": {"organiser": "janet", "sponsor": "daniel", "approver": "grace"},
        "define": {"measures": [{"code": "M1", "name": "Fund returns"}, {"code": "M2", "name": "Fees"}]}})
    return p


def rt(model):
    return L.Runtime(model, company_id="acme", company_name="Acme")


def cells(plane):
    return L.block(L.read_intent(plane, ID))["cells"]


def test_nine_kinds_in_order_guessed_with_source(plane):
    L.run(plane, ID, rt(Stub()))
    got = cells(plane)
    assert list(got) == [f"{m}:{k}" for m in ("M1", "M2") for k in L.KINDS]  # one measure at a time, the kinds in order
    assert L.block(L.read_intent(plane, ID))["run"]["state"] == "done"
    d = got["M1:business_definition"]
    assert (d["state"], d["mark"], d["by"]) == ("guessed", "guessed", "Lens") and d["source"] and d["value"]
    assert all(c["state"] == "guessed" for c in got.values())  # nothing is ever confirmed by Lens
    assert all(c["source"] for c in got.values())  # never blank: "no source found" at worst


def test_cap_of_three_across_kinds_and_next_opens_after_an_answer(plane):
    for i, t in enumerate("abcde"):
        L.raise_question(plane, ID, to="harvey", about=f"M1:{L.KINDS[1 + i % 4]}", text=f"What is {t}?", term=t, rank=i, defer=True)
    L.open_next(plane, ID)  # the run ranks the whole batch, then opens three
    qs = L.block(L.read_intent(plane, ID))["questions"]
    assert sorted(q["state"] for q in qs) == ["open"] * 3 + ["queued"] * 2
    assert {q["term"] for q in qs if q["state"] == "open"} == {"e", "d", "c"}  # most cards first
    assert L.question_budget(plane, ID, "harvey") == 0
    L.answer_question(plane, ID, next(q["id"] for q in qs if q["term"] == "e"), "harvey", "Net of fees")
    after = L.block(L.read_intent(plane, ID))["questions"]
    assert sum(q["state"] == "open" for q in after) == 3 and next(q for q in after if q["term"] == "b")["state"] == "open"
    with pytest.raises(L.Refused):
        L.answer_question(plane, ID, qs[0]["id"], "someone-else", "x")
    L.raise_question(plane, ID, to="harvey", about="M1:owners", text="again", term="D")  # same term merges
    assert len(L.block(L.read_intent(plane, ID))["questions"]) == 5


def test_a_missing_formula_becomes_a_question_to_the_lead(plane):
    L.draft_for(plane, ID, "technical_definition", "M1", rt=rt(Stub()), name="Fund returns")
    q = L.block(L.read_intent(plane, ID))["questions"]
    assert len(q) == 1 and q[0]["to"] == "grace" and q[0]["state"] == "open"


def test_send_back_redrafts_once_then_escalates(plane):
    m = Stub()
    L.draft_for(plane, ID, "business_definition", "M1", rt=rt(m), name="Fund returns")
    with pytest.raises(L.Refused):
        L.send_back(plane, ID, "M1:business_definition", "katie", "  ", rt=rt(m))
    first = L.send_back(plane, ID, "M1:business_definition", "katie", "Say net of fees", rt=rt(m))
    assert first["outcome"] == "redrafted" and first["cell"]["redraft"]["note"] == "Say net of fees" and first["cell"]["state"] == "redrafted"
    assert any("Say net of fees" in p for p in m.prompts)
    n = len(m.prompts)
    second = L.send_back(plane, ID, "M1:business_definition", "katie", "Still wrong", rt=rt(m))
    assert second["outcome"] == "escalated" and len(m.prompts) == n  # no second redraft
    lens = L.block(L.read_intent(plane, ID))
    assert [s["round"] for s in lens["send_backs"]] == [1, 2] and lens["send_backs"][1]["escalated_to"] == "grace"
    assert lens["questions"][0]["to"] == "grace" and lens["questions"][0]["kind"] == "escalation"
    with pytest.raises(L.Refused):
        L.send_back(plane, ID, "M1:business_definition", "katie", "again", rt=rt(m))
    done = L.decide(plane, ID, "M1:business_definition", "grace", "write", "Net monthly return")
    assert done["state"] == "guessed" and done["mark"] == "stated" and done["value"] == "Net monthly return"


def test_a_lead_who_sends_back_twice_goes_to_the_sponsor(plane):
    L.draft_for(plane, ID, "business_definition", "M1", rt=rt(Stub()), name="Fund returns")
    L.send_back(plane, ID, "M1:business_definition", "grace", "one", rt=rt(Stub()))
    L.send_back(plane, ID, "M1:business_definition", "grace", "two", rt=rt(Stub()))
    assert L.block(L.read_intent(plane, ID))["send_backs"][1]["escalated_to"] == "daniel"


def test_drafting_state_failure_and_retry(plane):
    m = Stub()
    key = "M1:business_definition"
    L._change(plane, ID, lambda lens, i: lens["cells"].update({key: {"kind": "business_definition", "measure_code": "M1", "state": "drafting", "attempts": 1, "claimed_at": 9e9}}))
    got = L.draft_for(plane, ID, "business_definition", "M1", rt=rt(m))
    assert got["state"] == "drafting" and not m.prompts  # another screen holds the claim: no second call
    L._change(plane, ID, lambda lens, i: lens["cells"][key].update(claimed_at=1.0))
    assert L.cell_view(L.read_intent(plane, ID), key)["state"] == "failed"  # a stale claim is a failure
    down = L.draft_for(plane, ID, "business_definition", "M1", rt=rt(Stub(fail=True)), retry=True)
    assert down["state"] == "failed" and down["outcome"] == "unreachable" and down["attempts"] == 2
    again = L.draft_for(plane, ID, "business_definition", "M1", rt=rt(Stub(fail=True)))
    assert again["state"] == "failed" and again["attempts"] == 2  # already tried: skipped unless told to retry
    ok = L.draft_for(plane, ID, "business_definition", "M1", rt=rt(m), retry=True)
    assert ok["state"] == "guessed" and ok["attempts"] == 3


def test_no_model_leaves_cells_not_drafted(plane):
    L.run(plane, ID, rt(None))
    lens = L.block(L.read_intent(plane, ID))
    assert lens["run"]["model_set_up"] is False
    assert lens["cells"]["M1:business_definition"]["state"] == "not_drafted" and lens["cells"]["M1:business_definition"]["outcome"] == "no_model"


def test_a_run_already_on_is_left_alone(plane):
    L._change(plane, ID, lambda lens, i: lens["run"].update(state="running", started_at=L._now()))
    m = Stub()
    L._LIVE.add(ID)
    try:
        assert L.run(plane, ID, rt(m))["state"] == "running" and not m.prompts
    finally:
        L._LIVE.discard(ID)


def test_a_run_left_running_by_a_restart_can_start_again(plane):
    L._change(plane, ID, lambda lens, i: lens["run"].update(state="running", started_at=L._now()))
    m = Stub()
    assert L.run(plane, ID, rt(m))["state"] == "done" and m.prompts


def test_a_sealed_card_and_an_anonymous_author_are_never_read(plane):
    m = Stub()
    L.run(plane, ID, rt(m))
    L.send_back(plane, ID, "M1:process_steps", "katie", "shorter", rt=rt(m))
    sent = " ".join(m.prompts)
    assert "Fund returns arrive late" in sent  # a plain card is read
    assert SEALED not in sent and ANON_AUTHOR not in sent
    assert SEALED not in json.dumps(L.read_intent(plane, ID))


def test_counts_for_a_viewer_hide_other_peoples_questions(plane):
    L.raise_question(plane, ID, to="harvey", about="M1:owners", text="Who?", term="x")
    L.raise_question(plane, ID, to="katie", about="M1:owners", text="Who?", term="y")
    s = L.state_for(L.read_intent(plane, ID), account="harvey", name="Harvey", roles={"owner"})
    assert [q["text"] for q in s["my_questions"]] == ["Who?"] and s["questions"]["open_total"] == 2 and s["questions"]["mine_open"] == 1


def test_the_cap_is_shared_with_the_process_map(plane):
    write_json_atomic(plane.path("intents", ID, "processes.json"), {"questions": [{"state": "open", "to_person": "harvey"}, {"state": "open", "to_person": "harvey"}]})
    for t in "xyz":
        L.raise_question(plane, ID, to="harvey", about="M1:owners", text=f"What is {t}?", term=t, defer=True)
    L.open_next(plane, ID)
    assert sorted(q["state"] for q in L.block(L.read_intent(plane, ID))["questions"]) == ["open", "queued", "queued"]
    assert L.question_budget(plane, ID, "harvey") == 0


def test_a_placeholder_owner_is_not_an_owner(plane):
    class Placeholder(Stub):
        def complete(self, module_id, messages, tools=None):
            super().complete(module_id, messages, tools)
            return ModelReply(text="DEFINITION: The monthly return of the fund.\nOWNER: [a name]\nPRODUCER: Treasury")

    L.draft_for(plane, ID, "owners", "M1", rt=rt(Placeholder()), name="Fund returns")
    v = cells(plane)["M1:owners"]["value"]
    assert v["business_owner"]["value"] is None and v["data_owner"]["value"] == "Treasury"



# ---- F13: owner-only confirm and send back, the question card, the strip total, "Not found yet"

from types import SimpleNamespace  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class _Accounts:
    def get(self, account_id):
        return {"display_name": account_id}

    def in_company(self, company):
        return []


@pytest.fixture
def web(tmp_path):
    p = PlaneStore(tmp_path).create("co-a")
    person = lambda acct, name: {"account_id": acct, "name": name}  # noqa: E731
    write_json_atomic(p.path("intents", ID, "intent.json"), {
        "id": ID, "type": "initiative", "state": "open", "created_by": "janet",
        "people": {"organiser": person("janet", "Janet Shaw"), "sponsor": person("daniel", "Daniel Kerr"), "approver": person("grace", "Grace Ward"),
                   "participants": [person("aaron", "Aaron Lyle"), person("harvey", "Harvey Rowley"), person("ethan", "Ethan Ng")],
                   "observers": [person("grace", "Grace Ward"), person("katie", "Katie Menon")]},  # both open the intent (file 05)
        "define": {"measures": [{"code": "M1", "name": "Fund returns", "owners": {"business": {"value": "Harvey Rowley", "account_id": "harvey"}}},
                                {"code": "M2", "name": "Fees", "owners": {"business": {"value": "Ethan Ng", "account_id": "ethan"}}},
                                {"code": "M3", "name": "Cash"}]}})
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = _Accounts()
    app.include_router(L.router)

    @app.middleware("http")
    async def who(request, call_next):
        request.state.company_id, request.state.account_id = "co-a", request.headers.get("x-account", "none")
        request.state.roles = request.headers.get("x-roles", "participant").split(",")
        return await call_next(request)

    L.run(p, ID, rt(Stub()))
    return SimpleNamespace(plane=p, client=TestClient(app))


def post(web, who, roles, path, body=None):
    return web.client.post(f"/api/intents/{ID}/define/lens/cells/{path}", json=body or {}, headers={"x-account": who, "x-roles": roles})


def test_only_the_owner_named_for_an_item_confirms_or_sends_back(web):
    assert cells(web.plane)["M1:business_definition"]["owned_by"] == [{"name": "Harvey Rowley", "role": "business owner", "account_id": "harvey"}]
    for who, roles in (("aaron", "participant"), ("ethan", "owner"), ("daniel", "sponsor")):
        for path, body in (("M1:business_definition/confirm", {}), ("M1:business_definition/send-back", {"note": "no"})):
            r = post(web, who, roles, path, body)
            assert r.status_code == 403 and "named as owner" in r.json()["detail"], (who, path)
    assert post(web, "harvey", "owner", "M1:business_definition/confirm").json()["state"] == "confirmed"
    assert post(web, "ethan", "owner", "M2:business_definition/confirm").status_code == 200
    assert post(web, "harvey", "owner", "M2:business_definition/confirm").status_code == 403  # an owner of one item is not the owner of another


def test_another_owner_is_refused_but_the_organiser_and_analyst_may_act(web):
    for path, body in (("M1:business_definition/confirm", {}), ("M1:business_definition/send-back", {"note": "no"}),
                       ("M1:business_definition/not-mine", {"person": "Aaron Lyle"})):
        assert post(web, "ethan", "owner", path, body).status_code == 403, path  # Ethan owns M2, not M1
    assert post(web, "katie", "analyst", "M2:business_definition/confirm").status_code == 200
    assert post(web, "janet", "company_admin", "M1:business_definition/confirm").status_code == 200  # Janet is the intent's organiser
    assert post(web, "root", "company_admin", "M2:business_definition/confirm").status_code == 403  # a company admin who is not the organiser


def test_the_governance_lead_confirms_what_no_one_owns_and_the_governed_state(web):
    r = post(web, "grace", "approver", "M3:business_definition/confirm")
    assert r.status_code == 200, r.json()  # M3 has no named owner
    L._change(web.plane, ID, lambda lens, i: lens["cells"]["M1:governed_state"].update(value="Restricted", state="guessed"))
    assert post(web, "grace", "approver", "M1:governed_state/confirm").json()["state"] == "confirmed"
    assert post(web, "grace", "approver", "M1:business_definition/confirm").status_code == 403


def test_not_mine_hands_the_item_on_and_the_question_with_it(web):
    L.raise_question(web.plane, ID, to="harvey", about="M1:business_definition", text="What is it?", term="Monthly fund returns")
    assert post(web, "harvey", "owner", "M1:business_definition/not-mine", {"person": "Nobody Known"}).status_code == 403
    got = post(web, "harvey", "owner", "M1:business_definition/not-mine", {"person": "Aaron Lyle"}).json()
    assert got["owned_by"][0]["name"] == "Aaron Lyle"
    assert post(web, "harvey", "owner", "M1:business_definition/confirm").status_code == 403  # no longer his
    assert [q["to"] for q in L.block(L.read_intent(web.plane, ID))["questions"] if q["about_cell"] == "M1:business_definition"] == ["Aaron Lyle"]


def test_the_question_card_names_the_item_the_role_and_the_meanings(web):
    L.raise_question(web.plane, ID, to="harvey", about="M1:ambiguities", text="Which meaning of Fund returns is right?", term="Fund returns")
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "harvey", "x-roles": "owner"}).json()
    q = got["my_questions"][0]
    assert q["item"] == "Fund returns" and q["why"] == "You are named as business owner of Fund returns."
    assert q["meanings"] == [{"meaning": "net", "where": "policy"}, {"meaning": "gross", "where": "interview"}]
    assert "Harvey Rowley" in got["people"] and got["may_act"].count("M1:owners") == 1 and "M2:owners" not in got["may_act"]


def test_the_strip_total_counts_every_measure_and_a_nothing_cell_says_so(web):
    L._change(web.plane, ID, lambda lens, i: [lens["cells"].pop(k) for k in [k for k in lens["cells"] if k.startswith("M3")]])
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "janet", "x-roles": "company_admin"}).json()
    assert got["measures"] == 3 and got["total"] == 27  # not only the cells made so far
    assert any(c["outcome"] == "nothing" and c["value"] in (None, L.NOT_KNOWN) for c in got["cells"].values())  # the screen reads these as "Not found yet"


# ---- run, try again and drop: who may

def _hdr(who, roles):
    return {"x-account": who, "x-roles": roles}


def test_run_is_for_the_organiser_and_the_analyst_not_a_company_admin_as_such(web, monkeypatch):
    started = []
    monkeypatch.setattr(L, "start_in_background", lambda *a, **k: started.append(a))
    monkeypatch.setattr(L, "runtime_for_request", lambda *a, **k: None)
    url = f"/api/intents/{ID}/define/lens/run"
    assert web.client.post(url, headers=_hdr("root", "company_admin")).status_code == 403
    assert web.client.post(url, headers=_hdr("grace", "approver")).status_code == 403
    assert web.client.post(url, headers=_hdr("janet", "company_admin")).status_code == 200  # the organiser
    assert web.client.post(url, headers=_hdr("katie", "analyst")).status_code == 200
    assert len(started) == 2


def test_try_again_is_for_the_organiser_analyst_or_the_items_owner(web):
    url = f"/api/intents/{ID}/define/lens/cells/M1:business_definition/try-again"
    for who, roles in (("root", "company_admin"), ("grace", "approver"), ("ethan", "owner")):
        assert "failed" not in web.client.post(url, headers=_hdr(who, roles)).text and web.client.post(url, headers=_hdr(who, roles)).status_code == 403
    for who, roles in (("janet", "company_admin"), ("katie", "analyst"), ("harvey", "owner")):
        r = web.client.post(url, headers=_hdr(who, roles))
        assert r.status_code == 403 and "failed" in r.json()["detail"], who  # let in; the cell has not failed


def test_drop_is_for_the_approver_or_governance_lead(web):
    qid = next(q["id"] for q in L.block(L.read_intent(web.plane, ID))["questions"])
    url = f"/api/intents/{ID}/define/lens/questions/{qid}/drop"
    for who, roles in (("root", "company_admin"), ("janet", "company_admin"), ("katie", "analyst")):
        assert web.client.post(url, json={"reason": "x"}, headers=_hdr(who, roles)).status_code == 403, who
    assert web.client.post(url, json={"reason": "not needed"}, headers=_hdr("grace", "approver")).status_code == 200


# ---- F40: a stopped run resumes with only the missing cells; questions go to the named owner

def test_a_run_stopped_at_n_cells_resumes_with_only_the_rest(plane):
    L.run(plane, ID, rt(Stub()))
    done = cells(plane)
    gone = [k for k in done if k.startswith("M2")][4:]  # a restart killed the run after 9 + 4 cells
    keep = "M1:business_definition"

    def stop(lens, i):
        for k in gone:
            del lens["cells"][k]
        lens["cells"][keep].update(state="confirmed", value="My own words")
        lens["run"].update(state="running", started_at=L._now())
    L._change(plane, ID, stop)
    m = Stub()
    L.run(plane, ID, rt(m), retry=True)  # what the strip read starts
    got, run = cells(plane), L.block(L.read_intent(plane, ID))["run"]
    assert list(got) == list(done) and run["state"] == "done" and run["resumed_from"] == len(done) - len(gone)
    assert got[keep]["state"] == "confirmed" and got[keep]["value"] == "My own words"  # confirmed work is never redrafted
    assert 0 < len(m.prompts) <= len(gone)  # only the missing cells reach the model (code kinds make none)


def test_a_cell_left_drafting_by_the_dead_process_is_drafted_on_resume(plane):
    L.run(plane, ID, rt(Stub()))
    key = "M2:business_definition"
    L._change(plane, ID, lambda lens, i: (lens["cells"][key].update(state="drafting", claimed_at=9e9), lens["run"].update(state="running", started_at=L._now())))
    L.run(plane, ID, rt(Stub()), retry=True)
    run = L.block(L.read_intent(plane, ID))["run"]
    assert cells(plane)[key]["state"] == "guessed" and run["resumed_from"] == 17  # 18 cells, one claimed and lost


def test_the_strip_read_carries_a_stopped_run_on_for_the_organiser(web, monkeypatch):
    L._change(web.plane, ID, lambda lens, i: lens["run"].update(state="running", started_at=L._now()))
    started = []
    monkeypatch.setattr(L, "start_in_background", lambda plane, iid, rt_, retry=False: started.append(retry))
    monkeypatch.setattr(L, "runtime_for_request", lambda *a, **k: None)
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "aaron", "x-roles": "participant"}).json()
    assert got["run"]["state"] == "partial" and not started  # a reader who may not start it just sees the offer to try again
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "janet", "x-roles": "company_admin"}).json()
    assert started == [True] and got["run"]["state"] == "running" and got["run"]["resumed_from"] == got["drafted"]


def test_a_question_goes_to_the_owner_named_for_the_item_and_says_so(web):
    q = L.raise_question(web.plane, ID, to=None, about="M1:technical_definition", text="What is the formula?", term="Fund returns")
    assert q["to"] == "harvey" and not q.get("no_owner")
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "harvey", "x-roles": "owner"}).json()
    assert got["my_questions"][0]["why"] == "You are named as business owner of Fund returns."  # the one owner named, and the line is true


def test_with_no_owner_named_the_question_goes_to_the_governance_lead_and_says_so(web):
    q = L.raise_question(web.plane, ID, to=None, about="M3:technical_definition", text="What is the formula?", term="Cash")
    assert q["to"] == "grace" and q["no_owner"] is True
    got = web.client.get(f"/api/intents/{ID}/define/lens", headers={"x-account": "grace", "x-roles": "approver"}).json()
    assert "No owner is named for this item yet" in [x for x in got["my_questions"] if x["id"] == q["id"]][0]["why"]


# ---- F43 (SEC0 #1): Lens applies file 05's matrix; hidden answers exactly like missing, and an analyst outside the intent cannot run it

def test_lens_hides_an_intent_the_viewer_cannot_open_exactly_like_a_missing_one(web, monkeypatch):
    started = []
    monkeypatch.setattr(L, "start_in_background", lambda *a, **k: started.append(a))
    monkeypatch.setattr(L, "runtime_for_request", lambda *a, **k: None)
    missing = "ini-" + "0" * 32
    for who, roles in (("zoe", "participant"), ("max", "analyst"), ("sam", "sponsor")):  # in the company, not in this intent, no area
        hidden = web.client.get(f"/api/intents/{ID}/define/lens", headers=_hdr(who, roles))
        gone = web.client.get(f"/api/intents/{missing}/define/lens", headers=_hdr(who, roles))
        assert hidden.status_code == gone.status_code == 404 and hidden.json() == gone.json(), who
        assert "Harvey" not in hidden.text
        r = post(web, who, roles, "M3:business_definition/confirm")
        assert r.status_code == 404 and r.json() == gone.json(), who
    assert web.client.post(f"/api/intents/{ID}/define/lens/run", headers=_hdr("max", "analyst")).status_code == 404
    assert started == []  # nothing ran for the analyst who cannot open it
    assert web.client.post(f"/api/intents/{ID}/define/lens/run", headers=_hdr("katie", "analyst")).status_code == 200
