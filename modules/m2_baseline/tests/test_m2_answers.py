"""M2-P02: the owner questionnaire (M2-10), the trace (M2-11), the sample upload (M2-13) and answering in a meeting.
Every answer is stated, guessed or unknown; "I don't know" is valid; read_answers is the shape in contracts/SHARED.md."""
import base64

import pytest
from m2_kit import login
from test_m2_requests_kit import BASE, BID, seed, send, token_of, visitor

from modules.m2_baseline.domain.questionnaire import AnswerError, clean_answers, load_questionnaire
from modules.m2_baseline.store.answers import read_answers

ASKED = {"tracked_today", "could_track", "sources", "dependencies", "upstream", "in_between", "downstream"}  # what the form shows
FIELDS = ASKED | {"source", "data_type", "arrival", "sla", "sample_doc_id"}  # the old single questions stay readable
GOOD = {"tracked_today": {"value": "partly", "mark": "stated"},
        "could_track": {"value": "with_conditions", "mark": "guessed"},
        "source": {"value": "Bank statement, call notices by email", "mark": "stated"},
        "data_type": {"value": "both", "mark": "stated"},
        "arrival": {"value": "Statement daily by noon", "mark": "stated"},
        "sla": {"value": None, "mark": "unknown"},
        "dependencies": {"value": "Needs the call schedule from the manager", "mark": "guessed"},
        "upstream": {"value": [{"who": "Bank", "what": "Statement"}], "mark": "stated"},
        "in_between": {"value": [{"who": "Sara Lim", "step": "Adjusted in the workbook", "manual": True}], "mark": "stated"},
        "downstream": {"value": [{"who": "Investment committee", "what": "Monthly pack"}, {"who": "", "what": "Who else?"}], "mark": "guessed"}}


@pytest.fixture
def tom(world):
    seed(world)
    org = login(world, "co-a")
    sent = send(org)["Tom Reyes"]
    return org, visitor(world, token_of(sent)), sent


def save(c, kpi="k1", answers=None, status=200):
    r = c.post(f"{BASE}/answer/save", json={"kpi_id": kpi, "answers": GOOD if answers is None else answers})
    assert r.status_code == status, r.text
    return r.json()


def test_the_form_carries_the_questions_and_the_three_marks(tom):
    form = tom[1].post(f"{BASE}/answer/form").json()
    q = form["questionnaire"]
    assert [m["value"] for m in q["marks"]] == ["stated", "guessed", "unknown"]
    assert {f["key"] for f in q["fields"]} == ASKED
    assert [k["id"] for k in form["kpis"]] == ["k1", "k2"] and form["kpis"][0]["answers"] is None


def test_every_answer_is_a_provenance_value_and_unknown_keeps_no_value(tom):
    rec = save(tom[1])["saved"]
    assert rec["tracked_today"]["value"] == "partly" and rec["tracked_today"]["mark"] == "stated"
    assert rec["tracked_today"]["by"] == "Tom Reyes" and rec["tracked_today"]["from"] == "answer link" and rec["tracked_today"]["at"]
    assert rec["could_track"]["mark"] == "guessed"
    assert rec["sla"] == {**rec["sla"], "value": None, "mark": "unknown"}


def test_the_trace_records_hops_with_a_name_or_unknown_and_marks_manual_steps(tom):
    rec = save(tom[1])["saved"]
    assert rec["in_between"]["value"] == [{"who": "Sara Lim", "step": "Adjusted in the workbook", "manual": True}]
    assert [h["who"] for h in rec["downstream"]["value"]] == ["Investment committee", "Unknown"]  # nobody named reads Unknown
    assert rec["upstream"]["value"][0] == {"who": "Bank", "what": "Statement"}


def test_i_dont_know_is_a_valid_answer_for_a_whole_trace(tom):
    rec = save(tom[1], answers={"upstream": {"value": [{"who": "x"}], "mark": "unknown"}})["saved"]
    assert rec["upstream"]["value"] is None and rec["upstream"]["mark"] == "unknown"


@pytest.mark.parametrize("bad", [
    {"source": {"value": "x"}},                                   # no mark
    {"source": {"value": "x", "mark": "sure"}},                   # a mark that is not one of the three
    {"data_type": {"value": "tables", "mark": "stated"}},         # not a choice offered
    {"source": {"value": "   ", "mark": "stated"}},               # blank is not an answer
    {"upstream": {"value": [], "mark": "stated"}},                # an empty trace is not a stated one
    {"not_a_question": {"value": "x", "mark": "stated"}},
    {"sample_doc_id": {"value": "abc", "mark": "stated"}},        # only an upload sets this
])
def test_an_answer_that_does_not_fit_is_refused_in_plain_words(tom, bad):
    r = save(tom[1], answers=bad, status=422).get("message")
    assert r and "{" not in r and "Traceback" not in r


def test_save_and_return_merges_and_keeps_the_rest(tom):
    c = tom[1]
    save(c, answers={"source": {"value": "Bank file", "mark": "stated"}})
    save(c, answers={"arrival": {"value": "Daily", "mark": "guessed"}})
    form = c.post(f"{BASE}/answer/form").json()
    mine = form["kpis"][0]["answers"]
    assert mine["source"]["value"] == "Bank file" and mine["arrival"]["value"] == "Daily"


def test_a_measure_that_is_not_theirs_is_refused(world):
    seed(world)
    sent = send(login(world, "co-a"))
    wei = visitor(world, token_of(sent["Wei Chen"]))
    assert save(wei, kpi="k1", status=422)["error"] == "invalid"


def test_nobody_sees_another_persons_answers(world):
    seed(world)
    sent = send(login(world, "co-a"))
    save(visitor(world, token_of(sent["Tom Reyes"])), kpi="k1")
    arjun = visitor(world, token_of(sent["Arjun Rao"])).post(f"{BASE}/answer/form").json()
    assert arjun["kpis"][0]["answers"] is None  # k1 is Arjun's too, but Tom's answer is Tom's


def test_submit_needs_each_measure_answered_and_then_the_request_reads_answered(tom):
    org, c, sent = tom
    assert c.post(f"{BASE}/answer/submit").status_code == 422
    save(c, "k1")
    assert c.post(f"{BASE}/answer/submit").status_code == 422  # k2 still has nothing
    save(c, "k2", {"source": {"value": None, "mark": "unknown"}})
    assert c.post(f"{BASE}/answer/submit").json() == {"state": "answered"}
    row = org.get(f"{BASE}/baselines/{BID}/requests").json()["requests"][0]
    assert row["answered_kpis"] == 2


def test_read_answers_gives_the_shared_shape_with_blanks_as_unknown(world, tom):
    save(tom[1], answers={"source": {"value": "Bank file", "mark": "stated"}})
    recs = read_answers(world.plane("co-a"), BID)
    assert len(recs) == 1
    r = recs[0]
    assert {"id", "request_id", "meeting", "owner_name", "kpi_id", *FIELDS} <= set(r)
    assert r["request_id"] == tom[2]["id"] and r["meeting"] is None and r["owner_name"] == "Tom Reyes" and r["kpi_id"] == "k1"
    assert r["source"]["value"] == "Bank file"
    assert r["arrival"]["mark"] == "unknown" and r["arrival"]["value"] is None and r["arrival"]["from"] == "not answered yet"
    assert "arrival" in r["unanswered"] and "source" not in r["unanswered"]
    assert read_answers(world.plane("co-b"), BID) == []  # a baseline with no answers


def test_a_sample_is_read_into_the_company_context_store_and_stays_on_the_machine(world, tom):
    org, c, _ = tom
    save(c, answers={"source": {"value": "Bank file", "mark": "stated"}})
    data = base64.b64encode(b"date,balance\n2026-01-01,100\n").decode()
    r = c.post(f"{BASE}/answer/sample", json={"kpi_id": "k1", "filename": "statement.csv", "data": data})
    assert r.status_code == 200, r.text
    saved = r.json()["saved"]
    assert saved["sample_doc_id"]["mark"] == "stated" and saved["sample_doc_id"]["by"] == "Tom Reyes"
    assert saved["sample_title"] == "statement.csv" and saved["source"]["value"] == "Bank file"  # the earlier answer kept
    from sh_platform.context_docs.store import DocStore
    docs = DocStore(world.plane("co-a")).documents("lens")
    assert [d["doc_id"] for d in docs] == [saved["sample_doc_id"]["value"]] and docs[0]["visibility"] == "private"
    assert DocStore(world.plane("co-b")).documents("lens") == []
    assert "balance" not in str(saved)  # the page gets a title, never the file's text


@pytest.mark.parametrize("body", [{"filename": "x.csv", "data": "%%%"}, {"filename": "x.exe", "data": base64.b64encode(b"MZ").decode()},
                                  {"filename": "x.csv", "data": ""}, {"filename": "x.csv"}])
def test_a_bad_sample_is_refused_in_plain_words(tom, body):
    r = tom[1].post(f"{BASE}/answer/sample", json={"kpi_id": "k1", **body})
    assert r.status_code in (400, 413, 422) and r.json()["message"]


def test_a_sample_for_a_measure_that_is_not_theirs_is_refused(world):
    seed(world)
    wei = visitor(world, token_of(send(login(world, "co-a"))["Wei Chen"]))
    r = wei.post(f"{BASE}/answer/sample", json={"kpi_id": "k1", "filename": "a.txt", "data": base64.b64encode(b"hi").decode()})
    assert r.status_code == 422


def test_answering_in_a_meeting_is_marked_with_the_person_and_the_organiser(world):
    seed(world)
    org = login(world, "co-a")
    send(org)
    r = org.put(f"{BASE}/baselines/{BID}/meeting-answers", json={"owner_name": "Wei Chen", "kpi_id": "k3", "answers": GOOD})
    assert r.status_code == 200, r.text
    saved = r.json()["saved"]
    assert saved["meeting"]["by"] == "Test Pat Owner" and saved["request_id"] is None
    assert saved["source"]["by"] == "Wei Chen" and "a meeting" in saved["source"]["from"] and "Test Pat Owner" in saved["source"]["from"]
    row = next(x for x in org.get(f"{BASE}/baselines/{BID}/requests").json()["requests"] if x["owner_name"] == "Wei Chen")
    assert row["state"] == "in_meeting"
    out = org.get(f"{BASE}/baselines/{BID}/answers").json()
    assert [a["owner_name"] for a in out["answers"]] == ["Wei Chen"] and out["kpis"][2] == {"id": "k3", "name": "Distribution lag"}


def test_a_meeting_needs_the_persons_name_and_a_known_measure(world):
    seed(world)
    org = login(world, "co-a")
    put = lambda body: org.put(f"{BASE}/baselines/{BID}/meeting-answers", json=body)  # noqa: E731
    assert put({"owner_name": " ", "kpi_id": "k1", "answers": GOOD}).status_code == 422
    assert put({"owner_name": "Wei Chen", "kpi_id": "nope", "answers": GOOD}).status_code == 422
    assert put({"owner_name": "Wei Chen", "kpi_id": "k1", "answers": {"source": {"value": "x"}}}).status_code == 422
    assert org.put(f"{BASE}/baselines/{BID}/meeting-answers", content=b"not json", headers={"content-type": "application/json"}).status_code == 400


def test_a_meeting_sample_and_a_role_without_access(world):
    seed(world)
    org = login(world, "co-a")
    data = base64.b64encode(b"notes about the workbook").decode()
    r = org.post(f"{BASE}/baselines/{BID}/sample", json={"owner_name": "Sara Lim", "kpi_id": "k1", "filename": "notes.txt", "data": data})
    assert r.status_code == 200 and r.json()["saved"]["sample_doc_id"]["by"] == "Sara Lim"
    guest = login(world, "co-a", name="Plain participant", roles=("participant",))
    assert guest.put(f"{BASE}/baselines/{BID}/meeting-answers", json={}).status_code == 403
    assert guest.get(f"{BASE}/baselines/{BID}/answers").status_code == 403


def test_the_questionnaire_check_runs_without_the_app():
    q = load_questionnaire()
    out = clean_answers(q, {"source": {"value": " Bank file ", "mark": "stated"}}, "Tom Reyes", "answer link")
    assert out["source"]["value"] == "Bank file"
    with pytest.raises(AnswerError):
        clean_answers(q, {"source": {"value": "x", "mark": "sure"}}, "Tom Reyes", "answer link")


def test_the_questionnaire_is_parsed_once_yet_a_changed_file_is_read_again(tmp_path):
    from modules.m2_baseline.domain.questionnaire import CONTRACT
    f = tmp_path / "questionnaire.yaml"
    f.write_text(CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    a, b = load_questionnaire(f), load_questionnaire(f)
    a.raw["fields"].clear()  # one caller's change never reaches another
    assert b.raw["fields"] and load_questionnaire(f).raw["fields"]
    f.write_text(f.read_text(encoding="utf-8").replace("no_reply_days:", "no_reply_days_gone:"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_questionnaire(f)
