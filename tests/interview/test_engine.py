"""The interview engine: drafts with source labels, the follow-up triggers and their limit, the record, and what the model is sent."""
import re
from pathlib import Path

import pytest

from iv_kit import PACK_LABEL, ROOT, StubModel
from sh_platform.interview import engine
from sh_platform.profile import store

AARON = {"id": "aaron-lyle", "name": "Aaron Lyle", "role": "Head of exposure"}
DAN = {"id": "dan-data", "name": "Dan Data", "role": "Head of data"}
SUE = {"id": "sue-sponsor", "name": "Sue Sponsor", "role": "Chair"}


def say(plane, person, text, model=None, **body):
    return engine.answer(plane, person["id"], {"text": text, **body}, model, "Lakeside")


def go_to(plane, person, qid, model=None):
    """Answers short plain answers (no trigger) until `qid` is the current question."""
    st = engine.start(plane, person)
    while st["qs"][st["i"]] != qid:
        engine.answer(plane, person["id"], {"text": "Weekly, about once a week."}, model, "Lakeside")
        st = engine.load_state(plane, person["id"])
    return st


def test_the_contract_has_q1_to_q14_with_roles_and_times():
    c = engine.contract()
    assert [q["id"] for q in c["questions"]] == [f"Q{i}" for i in range(1, 15)]
    assert c["kinds"] == {"participant": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q14"], "owner": ["Q7", "Q8", "Q9", "Q10", "Q11", "Q12", "Q14"], "sponsor": ["Q13", "Q14"]}
    assert c["minutes"] == {"participant": 10, "owner": 15, "sponsor": 5}
    assert engine.question("Q3")["text"] == "Which numbers tell you it is going well, and where do you see them today?"
    assert all(q["feeds"] for q in c["questions"])


def test_kind_follows_the_profile(plane):
    assert (engine.kind_of(plane, "Aaron Lyle"), engine.kind_of(plane, "Dan Data"), engine.kind_of(plane, "Sue Sponsor")) == ("participant", "owner", "sponsor")


def test_the_prefill_uses_profile_values_with_their_source_label(plane):
    go_to(plane, AARON, "Q3")
    card = engine.card(plane, engine.load_state(plane, "aaron-lyle"))
    assert card["mode"] == "confirm" and card["agent"] == "north"
    assert "13.32%" in card["draft"]["text"] and "Single-issuer concentration" in card["draft"]["text"] and card["draft"]["from"] == PACK_LABEL
    assert engine.load_state(plane, "aaron-lyle")["log"][-1]["text"].startswith(f"From {PACK_LABEL}: ")  # says it skipped the question
    assert engine.load_state(plane, "aaron-lyle")["log"][-1]["text"].endswith("Is that right?")
    st = engine.start(plane, DAN)  # an owner: Lens, and the system Dan owns
    card = engine.card(plane, st)
    assert card["agent"] == "lens" and card["qid"] == "Q7" and card["draft"]["text"].startswith("Custody feed: made by Dan Data, arrives as a daily file")
    assert card["draft"]["from"] == "Data landscape list"


def test_nothing_in_the_profile_means_the_question_is_asked_plainly(plane):
    card = engine.card(plane, engine.start(plane, AARON))
    assert card["mode"] == "ask" and card["draft"] is None and card["qid"] == "Q1"


def test_keeping_a_draft_records_it_as_the_persons_with_where_it_came_from(plane):
    go_to(plane, AARON, "Q3")
    out = engine.answer(plane, "aaron-lyle", {"action": "keep"}, StubModel(), "Lakeside")
    assert out["card"]["qid"] == "Q4"
    c = store.load(plane)["interviews"]["aaron-lyle"]["q3"]
    assert c["value"]["kept_draft"] is True and c["value"]["draft_from"] == PACK_LABEL and c["from"] == "Interview with Aaron Lyle"


def test_a_contradiction_with_the_pack_is_found_without_the_model(plane):
    stub = StubModel()
    go_to(plane, AARON, "Q3")
    out = say(plane, AARON, "Single-issuer concentration, in the pack. The largest name was about 12.3 percent last time.", stub)
    assert out["card"]["mode"] == "followup" and stub.sent == []
    assert out["card"]["text"] == f"From {PACK_LABEL}: Single-issuer concentration is 13.32%; you said about 12.3. Which should we use?"
    assert engine.load_state(plane, "aaron-lyle")["pending"]["trigger"] == "contradicts"


def test_a_matching_number_is_not_a_contradiction(plane):
    go_to(plane, AARON, "Q3")
    out = say(plane, AARON, "Single-issuer concentration, about 13.3 percent, in the pack.", StubModel())
    assert out["card"]["qid"] == "Q4"


def test_a_number_off_the_benchmark_asks_definition_or_period(plane):
    st = engine.start(plane, DAN)
    while st["qs"][st["i"]] != "Q11":
        engine.answer(plane, "dan-data", {"text": "Weekly, once a week."}, StubModel(), "Lakeside")
        st = engine.load_state(plane, "dan-data")
    out = say(plane, DAN, "Yes, the single-issuer concentration I reported was 11.9%.", StubModel())
    assert "different definition or a different period" in out["card"]["text"]
    assert engine.load_state(plane, "dan-data")["pending"]["trigger"] == "benchmark"


def test_a_new_system_asks_who_owns_it_and_how_it_arrives(plane):
    stub = StubModel()
    st = engine.start(plane, DAN)
    out = say(plane, DAN, "It comes from the Orbit workbook and arrives monthly.", stub)
    assert stub.sent == [] and engine.load_state(plane, "dan-data")["pending"]["trigger"] == "new_name"
    assert "Orbit workbook" in out["card"]["text"] and "Who owns it" in out["card"]["text"] and "arrive" in out["card"]["text"]


def test_a_known_system_is_not_a_new_name(plane):
    engine.start(plane, DAN)
    out = say(plane, DAN, "It comes from the Custody feed, every morning.", StubModel())
    assert out["card"]["qid"] == "Q8"


def test_a_restricted_topic_is_noted_and_not_probed(plane):
    stub = StubModel("TRIGGER: pain\nFOLLOWUP: What does that cost you?")
    engine.start(plane, AARON)
    out = say(plane, AARON, "Mostly the HR bonus pay review, it is a real pain every month.", stub)
    assert stub.sent == [] and engine.load_state(plane, "aaron-lyle")["pending"]["trigger"] == "restricted"
    assert "will not ask more" in out["card"]["text"]
    out = say(plane, AARON, "Yes, ask the HR lead, it hurts a lot.", stub)  # no further probing, even on a pain
    assert out["card"]["qid"] == "Q2" and stub.sent == []
    cell = store.load(plane)["interviews"]["aaron-lyle"]["q1"]["value"]
    assert cell["restricted"] is True and cell["followups"][0]["trigger"] == "restricted"


def test_a_restricted_area_from_the_profile_is_not_probed_either(plane):
    stub = StubModel()
    engine.start(plane, AARON)
    out = say(plane, AARON, "The HR cases take weeks to close.", stub)  # "HR" is also a listed restricted area
    assert engine.load_state(plane, "aaron-lyle")["pending"]["trigger"] == "restricted" and stub.sent == []


def test_at_most_two_follow_ups_per_question(plane):
    stub = StubModel("TRIGGER: vague\nFOLLOWUP: Can you give one recent example?", "TRIGGER: pain\nFOLLOWUP: What does it cost you each month?",
                     "TRIGGER: dependency\nFOLLOWUP: Who gives you that?")
    engine.start(plane, AARON)
    out = say(plane, AARON, "Things are slow.", stub)
    assert out["card"]["mode"] == "followup" and out["card"]["text"] == "Can you give one recent example?"
    out = say(plane, AARON, "The close.", stub)
    assert out["card"]["mode"] == "followup" and "cost" in out["card"]["text"]
    out = say(plane, AARON, "A lot of time.", stub)  # the third would be a dependency: the limit stops it
    assert out["card"]["qid"] == "Q2" and len(stub.sent) == 2
    assert [f["trigger"] for f in store.load(plane)["interviews"]["aaron-lyle"]["q1"]["value"]["followups"]] == ["vague", "pain"]


def test_the_model_cannot_put_a_figure_in_a_follow_up(plane):
    engine.start(plane, AARON)
    out = say(plane, AARON, "Things are slow.", StubModel("TRIGGER: vague\nFOLLOWUP: Is it 12.3 or 13.3?"))
    assert out["card"]["text"] == engine.FALLBACK["vague"]


def test_a_model_that_fails_just_carries_on(plane):
    class Down:
        def complete(self, *a, **k):
            raise RuntimeError("down")
    engine.start(plane, AARON)
    assert say(plane, AARON, "Things are slow.", Down())["card"]["qid"] == "Q2"


def test_no_figure_or_name_goes_to_the_model(plane):
    stub = StubModel("TRIGGER: vague\nFOLLOWUP: Can you give one example?")
    engine.start(plane, AARON)
    say(plane, AARON, "Mei Tan chases 45 late invoices and 12.5 percent are wrong, from Birch Semiconductor.", stub)
    sent = stub.everything
    assert stub.sent and not re.search(r"\d", sent) and "Mei Tan" not in sent and "[number]" in sent
    assert "13.32" not in sent and "Custody feed" not in sent  # no profile row either


def test_answers_are_recorded_with_provenance(plane):
    engine.start(plane, AARON)
    say(plane, AARON, "Whether any name is over the limit, each month.", StubModel())
    c = store.load(plane)["interviews"]["aaron-lyle"]["q1"]
    assert c["mark"] == "stated" and c["by"] == "Aaron Lyle" and c["from"] == "Interview with Aaron Lyle"
    assert c["ref"] == {"kind": "interview", "id": "aaron-lyle"} and "agent" not in c
    assert c["value"]["answer"] == "Whether any name is over the limit, each month."


def test_a_persons_own_answer_is_never_overwritten_by_a_draft(plane):
    engine.start(plane, AARON)
    say(plane, AARON, "My own words.", StubModel())
    draft = {"mark": "guessed", "by": "Lens", "agent": "lens", "from": "A document", "ref": {"kind": "document", "id": "d9"}}
    assert store.record(plane, "interviews.aaron-lyle.q1", {"answer": "a draft"}, draft) is None
    assert store.load(plane)["interviews"]["aaron-lyle"]["q1"]["value"]["answer"] == "My own words."


def test_q14_anonymous_is_recorded_without_the_name(plane):
    go_to(plane, AARON, "Q14")
    out = say(plane, AARON, "The weekly report is always late and nobody says so.", StubModel())
    assert out["card"]["mode"] == "followup" and "named, anonymous" in out["card"]["text"]
    out = say(plane, AARON, "Anonymous please.", StubModel())
    assert out["status"] == "done"
    doc = store.load(plane)["interviews"]
    assert "q14" not in doc["aaron-lyle"]
    (key,) = [k for k in doc if k.startswith("anon-")]
    c = doc[key]["q14"]
    assert c["by"] == "Anonymous" and "Aaron" not in str(c) and c["value"]["named"] is False


def test_q14_named_and_private_choices(plane):
    go_to(plane, AARON, "Q14")
    say(plane, AARON, "Please name me on this one.", StubModel())
    out = say(plane, AARON, "named", StubModel())
    assert store.load(plane)["interviews"]["aaron-lyle"]["q14"]["value"] == {"answer": "Please name me on this one.", "followups": [], "shareable": True, "named": True}
    go_to(plane, DAN, "Q14")
    say(plane, DAN, "A private worry.", StubModel())
    say(plane, DAN, "keep it private", StubModel())
    assert "q14" not in store.load(plane)["interviews"]["dan-data"]  # not shared: never in the shared profile
    assert engine.load_state(plane, "dan-data")["private"][0]["text"] == "A private worry."


def test_saying_done_stops_the_interview_and_is_not_recorded_as_an_answer(plane):
    engine.start(plane, AARON)
    say(plane, AARON, "Whether a name is over the limit.", StubModel())
    out = say(plane, AARON, "I'm done", StubModel())
    assert out["status"] == "done" and engine.load_state(plane, "aaron-lyle")["stopped_early"] is True
    assert "q2" not in store.load(plane)["interviews"]["aaron-lyle"]
    with pytest.raises(engine.Refused):
        say(plane, AARON, "one more", StubModel())


def test_a_full_run_for_each_kind_finishes(plane):
    for person in (AARON, DAN, SUE):
        st = engine.start(plane, person)
        for _ in st["qs"]:
            out = say(plane, person, "Weekly, about once a week.", StubModel())
            if out["card"] and out["card"]["qid"] == "Q14" and out["card"]["mode"] == "followup":
                out = say(plane, person, "named", StubModel())
        assert engine.load_state(plane, person["id"])["status"] == "done"


def test_progress_shows_questions_and_minutes_left(plane):
    st = go_to(plane, AARON, "Q3")
    p = engine.progress(st)
    assert (p["answered"], p["of"], p["minutes"]) == (2, 7, 10) and p["minutes_left"] == 8


# ---- the demo interviews, when present --------------------------------------------------------------------------------------


def _demo_dir() -> Path | None:
    roots = [ROOT] + [p for p in list(ROOT.parents)[:4] if (p / "local").is_dir()]  # a worktree sits a few folders below the main checkout
    return next((d for r in roots for d in sorted((r / "local").glob("*/interviews")) if d.is_dir()), None)


def test_the_demo_interviews_go_through_the_engine(plane):
    d = _demo_dir()
    if d is None:
        pytest.skip("no demo interviews in this checkout")
    for f in sorted(d.glob("*.md"))[:6]:
        text = f.read_text(encoding="utf-8")
        who = re.search(r"^# Interview: (.+)$", text, re.M)
        answers = dict(re.findall(r"^## (Q\d+)\..*?\n\n\*\*Answer:\*\* (.+)$", text, re.M | re.S))
        if not who or "Q1" not in answers:
            continue
        person = {"id": re.sub(r"[^a-z0-9]+", "-", who.group(1).lower()), "name": who.group(1), "role": ""}
        engine.start(plane, person, "participant")
        for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q14"):
            out = say(plane, person, " ".join(answers.get(q, "Nothing to add.").split()), StubModel())
            guard = 0
            while out["card"] and out["card"]["mode"] == "followup" and guard < 4:
                reply = "named" if out["card"]["qid"] == "Q14" else "It is the pack figure."
                out, guard = say(plane, person, reply, StubModel()), guard + 1
        st = engine.load_state(plane, person["id"])
        assert st["status"] == "done" and all(n <= 2 for n in st["n"].values())
        assert store.load(plane)["interviews"][person["id"]]["q1"]["value"]["answer"].startswith(answers["Q1"][:20])
