"""B14, the process map (spec 27): the draft is guessed with its source, only the owner confirms, the cap of three, the charter page data."""
import pytest

from sh_platform.intents import processes as pm
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import store
from sh_platform.profile.cards import record_card
from sh_platform.profile.view import Viewer

IID = "i-1"
SRC = {"mark": "stated", "by": "Test", "from": "Test seed"}


def viewer(name, pid, *roles):
    return Viewer(name, frozenset(roles), False, f"acct-{pid}")


JANET = viewer("Janet Shaw", "janet", "company_admin")
HARVEY = viewer("Harvey Rowley", "harvey", "owner")
AARON = viewer("Aaron Lyle", "aaron", "participant")
ZOE = viewer("Zoe Out", "zoe", "participant")


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """The draft's rule path is what these tests check; a configured model would make them slow and uneven. One test plugs a stub in."""
    from sh_platform.intents import lens
    monkeypatch.setattr(lens, "runtime_for_plane", lambda plane: lens.Runtime(None))


@pytest.fixture
def plane(tmp_path):
    p = PlaneStore(tmp_path).create("acme")
    for pid, name in (("janet", "Janet Shaw"), ("harvey", "Harvey Rowley"), ("aaron", "Aaron Lyle"), ("zoe", "Zoe Out")):
        store.record(p, f"people.{pid}.name", name, SRC)
        store.record(p, f"people.{pid}.account_id", f"acct-{pid}", SRC)
    store.record(p, "systems.pas.name", "Portfolio accounting system", SRC)
    cards = [("c1", "Fund pricing", "Prices arrive late", "Portfolio accounting system export", False),
             ("c2", "Fund pricing", "Files are fixed by hand", "", False),
             ("c3", "Capital calls", "", "", False),
             ("c4", "Payroll secrets", "Pay is wrong", "", True)]
    for cid, topic, q2, q3, sealed in cards:
        record_card(p, {"id": cid, "lane": "missing", "sealed": sealed, "anonymous": False, "author": "aaron",
                        "q2": q2 or None, "q3": q3 or None, "room": "w1"})
        store.record(p, f"cards.{cid}.topic", topic, SRC)  # the wall topic, as the seeded cards carry it
    write_json_atomic(p.path("intents", IID, "intent.json"), {
        "id": IID, "type": "initiative", "state": "open", "created_by": "acct-janet",  # person objects as the store writes them (ruling 21)
        "people": {"organiser": {"account_id": "acct-janet", "name": "Janet Shaw"}, "sponsor": None,
                   "participants": [{"account_id": "acct-aaron", "name": "Aaron Lyle"}], "advisers": [], "affected": [], "observers": []},
        "refs": {"wall_session_ids": ["w1"]}})
    return p


def version(plane):
    return pm._load(plane, IID)["version"]


def drafted(plane):
    pm.draft(plane, IID, JANET, 0)
    return pm._load(plane, IID)


def named(doc, name):
    return next(p for p in doc["processes"] if pm._v(p, "name") == name)


def live(plane, pid):
    return pm._find(pm._load(plane, IID), pid)


def test_draft_is_guessed_with_source_and_never_a_step(plane):
    doc = drafted(plane)
    p = named(doc, "Fund pricing")
    assert p["status"] == "guessed" and p["name"]["mark"] == "guessed" and p["name"]["agent"] == "lens"
    assert p["name"]["from"].startswith("Card:")
    assert p["steps"] == [] and p["owner"]["mark"] == "unknown" and p["trigger"]["mark"] == "unknown"
    assert [pm._v(b, "text") for b in p["breaks"]] == ["Prices arrive late", "Files are fixed by hand"]
    assert p["breaks"][0]["text"]["ref"] == {"kind": "card", "id": "c1"}
    assert pm._v(p, "systems") == ["pas"] and doc["drafted_from"]["cards"] == 3
    assert "Pay is wrong" not in str(doc["processes"])  # a sealed card is never drafted from


def test_redraft_keeps_a_persons_edit(plane):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    pm.patch(plane, IID, pid, AARON, doc["version"], {"op": "set", "field": "name", "value": "Month-end fund pricing"})
    out = pm.draft(plane, IID, JANET, version(plane))
    p = live(plane, pid)
    assert out["version"] == version(plane) and pm._v(p, "name") == "Month-end fund pricing" and p["status"] == "edited"
    assert len(pm._load(plane, IID)["processes"]) == 2  # no duplicate of the edited process


def test_only_the_named_owner_confirms_and_an_edit_clears_it(plane):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    pm.patch(plane, IID, pid, AARON, doc["version"], {"op": "set", "field": "owner", "value": "harvey"})
    with pytest.raises(pm.Refusal) as e:
        pm.confirm(plane, IID, pid, AARON, version(plane))
    assert e.value.status == 403 and "Only Harvey Rowley can confirm" in e.value.message
    pm.confirm(plane, IID, pid, HARVEY, version(plane))
    p = live(plane, pid)
    assert p["status"] == "confirmed" and p["confirmed"]["by"] == "Harvey Rowley" and p["confirmed"]["steps_hash"]
    pm.patch(plane, IID, pid, AARON, version(plane), {"op": "add_step", "name": "Check the pricing file"})
    p = live(plane, pid)
    assert p["status"] == "edited" and p["confirmed"] is None
    assert any(h["kind"] == "confirmation_cleared" for h in p["history"])
    with pytest.raises(pm.Refusal) as e:  # the owner is outside the committee: reads and confirms only
        pm.patch(plane, IID, pid, HARVEY, version(plane), {"op": "set", "field": "name", "value": "x"})
    assert e.value.status == 403


def test_a_link_keeps_the_confirmation_and_a_stale_version_is_refused(plane):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    pm.patch(plane, IID, pid, AARON, doc["version"], {"op": "set", "field": "owner", "value": "harvey"})
    pm.patch(plane, IID, pid, AARON, version(plane), {"op": "add_step", "name": "Receive prices"})
    pm.confirm(plane, IID, pid, HARVEY, version(plane))
    sid = live(plane, pid)["steps"][0]["id"]
    pm.patch(plane, IID, pid, AARON, version(plane), {"op": "link", "step_id": sid, "kind": "uses", "id": "m-nav"})
    assert live(plane, pid)["status"] == "confirmed"
    with pytest.raises(pm.Refusal) as e:
        pm.patch(plane, IID, pid, AARON, 0, {"op": "set", "field": "frequency", "value": "Monthly"})
    assert e.value.status == 409


def test_step_strip_keeps_order_through_add_reorder_split(plane):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    for n in ("One", "Two", "Three"):
        pm.patch(plane, IID, pid, AARON, version(plane), {"op": "add_step", "name": n})
    p = live(plane, pid)
    ids = [s["id"] for s in p["steps"]]
    assert [pm._v(s, "name") for s in p["steps"]] == ["One", "Two", "Three"]
    pm.patch(plane, IID, pid, AARON, version(plane), {"op": "reorder", "order": [ids[2], ids[0], ids[1]]})
    p = live(plane, pid)
    assert [(s["order"], pm._v(s, "name")) for s in p["steps"]] == [(1, "Three"), (2, "One"), (3, "Two")]
    out = pm.patch(plane, IID, pid, AARON, version(plane), {"op": "split", "after_step": p["steps"][0]["id"]})
    assert [pm._v(s, "name") for s in out["also"][0]["steps"]] == ["One", "Two"] and out["also"][0]["steps"][0]["order"] == 1
    assert [pm._v(s, "name") for s in out["process"]["steps"]] == ["Three"]


def test_an_agent_step_needs_a_source(plane):
    p = named(drafted(plane), "Fund pricing")
    with pytest.raises(pm.Refusal):
        pm.agent_add_step(p, "Invented", "", {})
    pm.agent_add_step(p, "From a document", "Handbook, page 4", {"kind": "document", "id": "d1"})
    assert p["steps"][0]["name"]["mark"] == "guessed"


def test_three_open_questions_per_person_and_the_rest_wait(plane):
    doc = drafted(plane)
    mine = [q for q in doc["questions"] if q["to_person"] == "aaron"]
    states = [q["state"] for q in mine]
    assert len(doc["processes"]) == 2 and len(mine) == 6 and states.count("open") == 3 and states.count("queued") == 3
    assert pm.question_budget(plane, IID, "aaron") == {"cap": 3, "open": 3, "free": 0}
    pm.answer(plane, IID, next(q for q in mine if q["state"] == "open")["id"], AARON, {"dropped_reason": "Not my area"})
    after = [q["state"] for q in pm._load(plane, IID)["questions"] if q["to_person"] == "aaron"]
    assert after.count("open") == 3 and after.count("dropped") == 1  # the next queued one moved up
    write_json_atomic(plane.path("intents", IID, "glossary.json"), {"questions": [{"state": "open", "to_person": "zoe"}] * 2})
    assert pm.question_budget(plane, IID, "zoe")["free"] == 1  # another Define file counts against the same cap


def test_an_answer_becomes_a_guessed_step_proposal(plane):
    doc = drafted(plane)
    q = next(q for q in doc["questions"] if q["topic"] == "steps" and q["state"] == "open")
    with pytest.raises(pm.Refusal):
        pm.answer(plane, IID, q["id"], HARVEY, {"answer": "x"})  # not the person asked
    pm.answer(plane, IID, q["id"], AARON, {"answer": "Prices are checked, then posted"})
    s = live(plane, q["process_id"])["steps"][0]
    assert s["name"]["mark"] == "guessed" and s["name"]["from"] == "Answer from Aaron Lyle"
    assert s["name"]["ref"] == {"kind": "person", "id": "aaron"}


def test_charter_page_shows_every_process_with_its_confirmation_label(plane):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    pm.patch(plane, IID, pid, AARON, doc["version"], {"op": "set", "field": "owner", "value": "harvey"})
    pm.confirm(plane, IID, pid, HARVEY, version(plane))
    page = pm.charter_page(plane, IID, AARON)
    rows = {p["name"]: p for g in page["groups"] for p in g["processes"]}
    assert page["title"] == "Processes involved" and page["state"] == "In confirmation"
    assert page["counts"] == {"processes": 2, "confirmed": 1}
    assert rows["Fund pricing"]["label"].startswith("Confirmed by Harvey Rowley") and rows["Fund pricing"]["owner"] == "Harvey Rowley"
    assert rows["Capital calls"]["label"] == "Not yet confirmed by its owner"


def test_who_sees_what(plane):
    drafted(plane)
    assert pm.read_map(plane, IID, JANET)["tier"] == "write"
    admin = viewer("Mei Admin", "mei", "company_admin")
    assert pm.read_map(plane, IID, admin) == {"intent_id": IID, "version": 1, "state": "Drafted", "tier": "counts",
                                              "summary": "Process map: 2 processes, 0 confirmed",
                                              "counters": {"processes": 2, "confirmed": 0}}
    with pytest.raises(pm.Refusal) as e:
        pm.read_map(plane, IID, ZOE)  # in the company, not in this intent
    assert e.value.status == 404
    with pytest.raises(pm.Refusal) as e:
        pm.draft(plane, IID, AARON, 1)
    assert e.value.status == 403


def test_a_sealed_card_link_carries_no_words_and_no_clusters_blocks_the_draft(plane, tmp_path):
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    out = pm.patch(plane, IID, pid, AARON, doc["version"], {"op": "add_break", "card_id": "c4"})
    b = out["process"]["breaks"][-1]
    assert b["sealed_card"] and b["text"]["value"] is None
    empty = PlaneStore(tmp_path / "e").create("acme2")
    write_json_atomic(empty.path("intents", IID, "intent.json"), {"id": IID, "state": "open", "people": {"organiser": "janet"}})
    store.record(empty, "people.janet.name", "Janet Shaw", SRC)
    with pytest.raises(pm.Refusal) as e:
        pm.draft(empty, IID, JANET, 0)
    assert e.value.message == "Form clusters first. Lens drafts processes from them."


def test_an_edit_that_fills_a_gap_closes_its_question_and_an_approver_only_reads(plane):
    doc = drafted(plane)
    p = named(doc, "Fund pricing")
    assert any(q["process_id"] == p["id"] and q["topic"] == "owner" and q["state"] != "dropped" for q in doc["questions"])
    pm.patch(plane, IID, p["id"], AARON, doc["version"], {"op": "set", "field": "owner", "value": "harvey"})
    pm.patch(plane, IID, p["id"], AARON, version(plane), {"op": "add_step", "name": "Receive prices"})
    qs = [q for q in pm._load(plane, IID)["questions"] if q["process_id"] == p["id"]]
    assert all(q["state"] == "dropped" and q["dropped_reason"] == "Settled by an edit." for q in qs if q["topic"] in ("owner", "steps"))
    grace = viewer("Grace Ward", "aaron", "approver")  # named as a participant, but the approver role reads
    assert pm.read_map(plane, IID, grace)["tier"] == "read"
    with pytest.raises(pm.Refusal) as e:
        pm.patch(plane, IID, p["id"], grace, version(plane), {"op": "add_step", "name": "x"})
    assert e.value.status == 403


# ---- F29: sources read, questions that can be answered, outcome counts, Pulse lines

def _enrich(plane):
    store.record(plane, "people.ethan.name", "Ethan Ng", SRC)  # no sign-in: no account_id
    store.record(plane, "people.harvey.owns", ["Fund pricing close"], SRC)
    store.record(plane, "interviews.harvey.q2", {"answer": "Each month the pricing file arrives late. First, we check the pricing. Then we load the pricing file.",
                                                "followups": [], "restricted": False}, {**SRC, "from": "Interview with Harvey Rowley"})
    record_card(plane, {"id": "c5", "lane": "missing", "sealed": False, "anonymous": False, "author": "ethan", "q2": "Pricing is slow", "room": "w1"})
    store.record(plane, "cards.c5.topic", "Treasury cash", SRC)


def test_draft_reads_interviews_and_names_owner_trigger_frequency_steps_with_sources(plane):
    _enrich(plane)
    p = named(drafted(plane), "Fund pricing")
    assert pm._v(p, "owner") == "harvey" and p["owner"]["mark"] == "guessed" and p["owner"]["from"].startswith("Profile: Harvey Rowley owns")
    assert "arrives late" in pm._v(p, "trigger") and p["trigger"]["from"] == "Interview with Harvey Rowley"
    assert pm._v(p, "frequency").lower() == "each month"
    assert len(p["steps"]) == 2
    assert all(s["name"]["mark"] == "guessed" and s["name"]["from"] == "Interview with Harvey Rowley" for s in p["steps"])
    assert pm._load(plane, IID)["drafted_from"]["interviews"] == 1


def test_questions_never_go_to_someone_without_a_sign_in(plane):
    _enrich(plane)
    doc = drafted(plane)
    treasury = named(doc, "Treasury cash")
    qs = [q for q in doc["questions"] if q["process_id"] == treasury["id"]]
    assert qs and all(q["to_person"] == "janet" and "Ethan Ng has no sign-in here" in q["text"] for q in qs)
    assert all(pm._v(plane_people(plane)[q["to_person"]], "account_id") for q in doc["questions"])


def plane_people(plane):
    return store.raw(plane)["people"]


def test_outcome_processes_is_written_with_the_map(plane):
    from sh_platform.jsonfile import read_json_strict
    drafted(plane)
    rec = read_json_strict(plane.path("intents", IID, "intent.json"), dict)
    assert rec["outcome"]["processes"] == {"count": 2, "confirmed": 0, "state": "Drafted"}


def test_pulse_lines_for_the_owner_and_the_person_asked(plane, monkeypatch):
    from sh_platform.intents import store as istore
    monkeypatch.setattr(istore, "read_index", lambda _p: [{"id": IID, "state": "open", "type": "initiative", "title": "Pricing"}])
    doc = drafted(plane)
    pid = named(doc, "Fund pricing")["id"]
    pm.patch(plane, IID, pid, JANET, doc["version"], {"op": "set", "field": "owner", "value": "harvey"})
    ids = [x["id"] for x in pm.pulse_lines(plane, HARVEY)]
    assert f"process-confirm:{IID}:{pid}" in ids
    asked = pm.pulse_lines(plane, AARON)
    assert any(x["id"] == f"process-questions:{IID}" and "question" in x["title"] for x in asked)
    assert pm.pulse_lines(plane, ZOE) == []


def test_ask_op_goes_to_a_person_who_can_answer_and_keeps_the_source_quote(plane):
    _enrich(plane)
    doc = drafted(plane)
    p = named(doc, "Fund pricing")
    assert "arrives late" in p["trigger"]["quote"]
    t = named(doc, "Treasury cash")
    n = len(doc["questions"])
    pm.patch(plane, IID, t["id"], JANET, doc["version"], {"op": "ask", "topic": "trigger"})
    again = pm._load(plane, IID)
    assert len(again["questions"]) == n  # already asked: no second question
    with pytest.raises(pm.Refusal):
        pm.patch(plane, IID, t["id"], JANET, again["version"], {"op": "ask", "topic": "colour"})


def test_model_reply_is_kept_only_where_it_names_a_real_passage(plane, monkeypatch):
    """A stub model: one process with a step the passage supports, one step the passage does not, and a figure the guard overwrote."""
    from sh_platform.intents import lens
    _enrich(plane)
    reply = ('{"processes": [{"name": "Month-end pricing", "owner": "Harvey Rowley", "trigger": "The pricing file arrives late", "frequency": null, '
             '"steps": ["Check the pricing", "Fly to the moon", "Load by not available yet"], "passage": "A"}, {"name": "Ghost", "passage": "Z"}]}')

    class Res:
        status, text = "done", reply

    monkeypatch.setattr(lens, "runtime_for_plane", lambda p: lens.Runtime(object(), recorder=None))
    monkeypatch.setattr("sh_platform.agents.loop.run_agent", lambda *a, **k: Res())
    prof, cards = pm._wall_cards(plane, pm._intent(plane, IID), JANET)
    got = pm._model_items(plane, pm.passages(prof, cards), prof)
    assert [g["name"] for g in got] == ["Month-end pricing"]  # "Z" names no passage
    assert [s["text"] for s in got[0]["steps"]] == ["Check the pricing"] and got[0]["steps"][0]["src"] == "Interview with Harvey Rowley"
    assert got[0]["owner"] is None  # the passage never names Harvey, so the owner guess is dropped


def test_an_approver_who_cannot_see_the_intent_gets_404_like_a_missing_one(plane):  # F43, SEC0 #2 and #5
    drafted(plane)
    store.record(plane, "people.gail.name", "Gail Out", SRC)
    store.record(plane, "people.gail.account_id", "acct-gail", SRC)
    gail = viewer("Gail Out", "gail", "approver")  # the approver role, but not in this intent, its area or its records
    for iid in (IID, "i-missing"):
        for call in (lambda: pm.read_map(plane, iid, gail),
                     lambda: pm.answer(plane, iid, "q-x", gail, {"answer": "", "dropped_reason": ""})):
            with pytest.raises(pm.Refusal) as e:
                call()
            assert (e.value.status, e.value.message) == (404, "We could not find that."), iid
