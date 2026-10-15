"""FIX-J (the critic's last conditions): "So that" lines checked before signing, saved-but-unsent notes at the one-minute
warning, North not repeating itself or asking what is already said, one automatic retry, the short-task thinking
budget, and notes left on their own on the charter. Stub models, synthetic text, no live call."""
import json

import pytest

from m1_kit import BASE
from modules.m1_intent.agent import gather, north, short_model
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import notes as N
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.tools.pack_tools import Guidance, ground, ground_text
from sh_platform.agents.protocols import ModelReply
from sh_platform.egress.providers.gemini import GeminiAdapter
from sh_platform.egress.providers.openrouter import OpenRouterAdapter
from sh_platform.packs import EmptyPack
from test_m1_board_kit import NOTES, together
from test_m1_briefing_kit import T0, make_world, seated, session_at
from test_m1_charter_lines import Lines
from test_m1_north import StubModel, ask, guid, turns
from test_m1_private_room_api import a, room, start_room, use_model  # noqa: F401  (`a` is a fixture)
from test_m1_seat_wiring_kit import flow, new_world

SAID = {"Calls arrive too late": "funding is planned, not found", "No single exposure view": "we see concentration early"}


# ---- 1. "So that" lines are full sentences, and an unchecked North draft cannot be signed
def test_a_purpose_line_is_always_a_full_so_that_sentence():
    assert C.with_so_that("we know what the data means") == "So that we know what the data means."
    assert C.with_so_that("So that we can say if alpha is real.") == "So that we can say if alpha is real."
    assert C.with_so_that("so that: Treasury has ten days") == "So that Treasury has ten days."  # a name keeps its capital
    assert C.with_so_that("Capital calls are paid on time") == "So that Capital calls are paid on time."  # not an opener we know: left as written
    assert C.with_so_that("APE reports are trusted") == "So that APE reports are trusted."  # an acronym keeps its capitals
    assert C.with_so_that("  ") == ""


def draft_charter(tmp_path, **kw):
    b = together(tmp_path, model=Lines(SAID), **kw)
    for name in SAID:
        assert b.org_call("POST", f"/together/clusters/{b.cluster(name)['id']}/tick", json={"ticked": True}).status_code == 200
    return b, b.org_call("POST", "/charter", json={"confirm": True}).json()["charter"]


def test_signing_is_refused_while_any_line_is_an_unconfirmed_north_draft(tmp_path):
    b, c = draft_charter(tmp_path)
    assert all(p["so_that_draft"] and p["so_that"].startswith("So that ") for p in c["problems"])
    r = b.org_call("POST", "/charter/sign")
    assert r.status_code == 409 and r.json()["error"] == "unchecked_lines"
    assert r.json()["message"] == "Check the drafted 'So that' lines first."
    assert b.org_call("GET", "/charter").json()["charter"]["signing"]["signed"] == 0  # nothing was signed
    assert b.org_call("POST", "/charter/send").status_code == 409  # nor sent to an approver unchecked


def test_use_this_line_confirms_a_draft_as_it_is_and_an_edit_clears_the_flag_too(tmp_path):
    b, c = draft_charter(tmp_path)
    first, second = (p["id"] for p in c["problems"])
    r = b.org_call("PUT", "/charter", json={"confirm_so_that": [first]})
    assert r.status_code == 200
    got = {p["id"]: p for p in r.json()["charter"]["problems"]}
    assert got[first]["so_that_draft"] is False and got[first]["so_that_edited"] is True and got[first]["so_that"] == c["problems"][0]["so_that"]
    assert got[first]["so_that_note"] is None and got[second]["so_that_draft"] is True
    assert b.org_call("POST", "/charter/sign").status_code == 409  # the other line is still a draft
    r = b.org_call("PUT", "/charter", json={"so_that": {second: "our exposure is seen early"}})  # an edit: also gets its "So that"
    assert {p["id"]: p for p in r.json()["charter"]["problems"]}[second]["so_that"] == "So that our exposure is seen early."
    signed = b.org_call("POST", "/charter/sign")
    assert signed.status_code == 200 and signed.json()["charter"]["signing"]["signed"] == 1


def test_use_this_line_refuses_what_is_not_a_north_draft(tmp_path):
    b, c = draft_charter(tmp_path)
    first = c["problems"][0]["id"]
    assert b.org_call("PUT", "/charter", json={"confirm_so_that": ["nope"]}).status_code == 422
    assert b.org_call("PUT", "/charter", json={"confirm_so_that": []}).status_code == 422
    assert b.org_call("PUT", "/charter", json={"confirm_so_that": [first]}).status_code == 200
    again = b.org_call("PUT", "/charter", json={"confirm_so_that": [first]})  # already confirmed
    assert again.status_code == 422 and again.json()["message"]


def test_a_charter_with_no_drafted_line_signs_as_before(tmp_path):
    b = together(tmp_path)  # GatherStub drafts nothing: the lines are blank, the organiser is asked
    for c in b.org_call("GET", "/board").json()["clusters"]:
        b.org_call("POST", f"/together/clusters/{c['id']}/tick", json={"ticked": True})
    b.org_call("POST", "/charter", json={"confirm": True})
    assert b.org_call("POST", "/charter/sign").status_code == 200


# ---- notes left on their own show on the charter
def test_a_note_left_on_its_own_shows_as_left_for_later_with_its_words_or_only_a_count_if_anonymous(tmp_path):
    b, c = draft_charter(tmp_path)
    assert b.org_call("GET", "/charter").json()["charter"]["alone"] == [{"text": "Fee reports differ by manager and cannot be compared", "kind": "intent", "author_name": "Ben Guest"}]  # by name: the name shows
    anon = [(t, i == len(NOTES) - 1 or an) for i, (t, an) in enumerate(NOTES)]  # the lone note is anonymous
    b2, _ = draft_charter(tmp_path / "second", notes=anon)
    assert b2.org_call("GET", "/charter").json()["charter"]["alone"] == [{"text": None, "kind": "intent"}]  # anonymous: no name, no words


# ---- 2. saved-but-unsent notes at the warning
def test_the_unsent_message_counts_the_drafts_and_says_what_the_rooms_end_will_do():
    drafts = [{"state": "draft", "text": "a", "anonymous": False}, {"state": "draft", "text": "b", "anonymous": False}, {"state": "submitted", "text": "c"}]
    u = N.unsent(drafts)
    assert (u["count"], u["named"]) == (2, 0)  # A-045: never sent, never confirmed, so anonymous
    assert u["message"] == "You have 2 notes not yet sent. If you do not send them, they go to the board anonymously."
    assert N.unsent(drafts[:1])["message"] == "You have 1 note not yet sent. If you do not send it, it goes to the board anonymously."
    assert N.unsent(drafts, "named")["message"] == "You have 2 notes not yet sent. When time ends they go to the board under your name."
    assert "without your name" in N.unsent(drafts, "anonymous")["message"]
    assert N.unsent([{"state": "draft", "text": "a"}], "anonymous")["named"] == 0  # the session's own rule makes it anonymous
    assert N.unsent([{"state": "submitted"}]) == {"count": 0, "named": 0, "message": None}


def test_the_room_view_tells_a_person_what_is_unsent_and_it_follows_the_anonymous_choice(tmp_path):
    w = new_world(tmp_path)
    org, sid, (ada, ben) = flow(w, "co-a")
    assert ada.room()["unsent"] == {"count": 0, "named": 0, "message": None}
    n1, n2 = ada.write("Calls arrive too late"), ada.write("Exposure takes a week")
    u = ada.room()["unsent"]
    assert (u["count"], u["named"]) == (2, 0) and "If you do not send them, they go to the board anonymously" in u["message"]
    assert ben.room()["unsent"]["count"] == 0  # only your own notes
    for n in (n1, n2):  # what "Make them anonymous" does, one note at a time
        assert ada.save(n, anonymous=True).status_code == 200
    u = ada.room()["unsent"]
    assert (u["count"], u["named"]) == (2, 0)
    assert ada.submit(n1).status_code == 200
    assert ada.room()["unsent"]["count"] == 1


def test_nira_says_the_same_at_the_warning_and_only_then(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: StubModel(ModelReply("Who is affected?"))
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "private_rooms")
    ann = seated(w, "co-a", "Ann")
    for text in ("Calls arrive too late", "Exposure takes a week"):
        assert ann.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": text, "kind": "note"}).status_code == 200
    warn = lambda: ann.post(f"{BASE}/sessions/{sid}/nira", json={"kind": "warning"}).json()["text"]  # noqa: E731
    w.now[0] = T0 + 60 * 8 - 300
    assert "not yet sent" not in warn()  # well before the warning: only the time left
    w.now[0] = T0 + 60 * 8 - 30
    text = warn()
    assert "You have 2 notes not yet sent." in text and "anonymously" in text
    assert "less than a minute" in text


# ---- 3. North does not repeat itself, and does not ask what is already said
def test_nearly_the_same_reply_is_found_by_word_overlap():
    a_ = "That is a finding to be checked later. Who sets the limit today?"
    assert R.same_reply(a_, a_) and R.same_reply(a_, a_.upper() + " ")
    assert R.same_reply("one two three four five six seven eight nine ten", "one two three four five six seven eight nine eleven")
    assert not R.same_reply(a_, "Understood. Who reviews the manager fee list?")
    assert not R.same_reply("", "x")


def test_a_repeated_reply_is_asked_again_once_with_a_note_and_the_new_reply_is_used(world):
    same = "Understood, I have noted that. Who sets the limit today?"
    m = StubModel(ModelReply(same), ModelReply("Thanks. What would a limit protect you from?"))
    text, answered = ask(world, m, "We have no limit at all", history=[("person", "x"), ("north", same)])
    assert answered and text == "Thanks. What would a limit protect you from?" and len(m.calls) == 2
    assert "say something new" in json.loads(m.calls[1]["messages"][1]["content"])["question"].lower()
    assert "say something new" not in json.loads(m.calls[0]["messages"][1]["content"])["question"].lower()


def test_if_it_is_still_the_same_the_reply_is_a_short_read_back_of_the_persons_message(world):
    same = "Understood, I have noted that. Who sets the limit today?"
    m = StubModel(ModelReply(same))
    text, answered = ask(world, m, "We have no limit at all, that is the problem", history=[("person", "x"), ("north", same)])
    assert answered and len(m.calls) == 2
    assert text == "So you are saying: We have no limit at all, that is the problem. Did I get that right?"


def test_a_failed_second_attempt_shows_the_plain_failure_not_a_read_back(world):
    same = "Understood. Who sets the limit today?"
    m = StubModel(ModelReply(same), ModelReply(""))  # the second call cannot finish
    text, answered = ask(world, m, "We have no limit", history=[("person", "x"), ("north", same)])
    assert answered is False and "could not finish" in text


def test_a_reply_that_is_not_a_repeat_costs_one_call(world):
    m = StubModel(ModelReply("Who is affected?"))
    ask(world, m, "Renewals slipped", history=[("person", "x"), ("north", "Something else entirely.")])
    assert len(m.calls) == 1


KPIS = [{"id": "K1", "name": "Renewal retention rate", "definition": "Share of policies renewed"},
        {"id": "K2", "name": "Claims backlog days", "definition": "Days a claim waits"}]
DEFAULTS = {"K1": {"customer_decides": [{"question": "Which cohort counts as renewed?"}], "usual_practice": [{"text": "Reviewed monthly"}]},
            "K2": {"customer_decides": [{"question": "Which FX basis is approved?"}], "usual_practice": [{"text": "Reviewed weekly"}]}}


def test_the_company_decides_question_is_offered_for_the_best_match_only():
    g = Guidance(EmptyPack("x"), kpis=KPIS, defaults=DEFAULTS)
    said = ["renewal retention slipped and the claims backlog grew"]
    kpis = ground(g, said)["kpis"]
    assert set(kpis) == {"Renewal retention rate", "Claims backlog days"}
    assert "your_company_decides" in kpis["Renewal retention rate"] and "your_company_decides" not in kpis["Claims backlog days"]
    assert "FX basis" not in ground_text(g, said)  # the off-topic question is not offered
    assert "your company decides" not in ground_text(g, said, decides=False).lower()


def test_the_pack_text_no_longer_ends_with_the_line_the_model_copied_onto_every_reply():
    g = Guidance(EmptyPack("x"), kpis=KPIS, defaults=DEFAULTS)
    assert not ground_text(g, ["renewal retention slipped"]).rstrip().endswith("Your company decides.")


def test_a_question_matched_only_on_older_messages_brings_no_company_decides_question(world):
    m = StubModel(ModelReply("Understood."))
    g = Guidance(EmptyPack("x"), kpis=KPIS, defaults=DEFAULTS, problems=[{"id": "P", "question": "q"}])
    ask(world, m, "It is the same every week", practice=True, history=[("person", "renewal retention slipped"), ("north", "ok")], guidance=g)
    guidance = json.loads(m.calls[0]["messages"][1]["content"])["context"]["industry_guidance"]
    assert "Which cohort" not in guidance and "your company decides" not in guidance.lower()


def test_company_decides_is_said_once_in_a_chat_and_only_after_a_labelled_suggestion():
    sug = "Industry practice (suggestion): the committee approves it."
    assert R.tidy_reply(sug).endswith("Your company decides.")
    assert "company decides" not in R.tidy_reply(sug, said_before=True).lower()  # said earlier in this chat
    assert "company decides" not in R.tidy_reply("Noted. Who is affected?").lower()  # no suggestion, no sentence
    assert R.tidy_reply("Your company decides: Which cohort counts as renewed?") == "Which cohort counts as renewed?"
    assert R.said_decides(["Hello", sug + "\nYour company decides."]) and not R.said_decides(["Hello"])


def test_company_decides_is_not_added_again_after_an_earlier_reply_said_it(world):
    m = StubModel(ModelReply("Industry practice (suggestion): reviewed yearly."))
    text, _ = ask(world, m, "How often is it reviewed?", history=[("person", "x"), ("north", "Industry practice (suggestion): approved by the committee.\nYour company decides.")])
    assert "company decides" not in text.lower() and text.startswith("Industry practice (suggestion): reviewed yearly")


def test_a_question_that_reuses_the_persons_nouns_is_never_removed_by_code(world):
    q = "Which benchmark does the bonus pool use for the return figure?"
    m = StubModel(ModelReply(q))
    text, answered = ask(world, m, "The bonus pool depends on the return figure and the benchmark")
    assert answered and text == q  # only the rule in north_rules.yaml asks North not to ask what is known


def test_a_draft_that_repeats_a_submitted_note_is_not_counted_as_unsent():
    notes = [{"state": "submitted", "text": "Calls arrive  too late"}, {"state": "draft", "text": "calls arrive too late"},
             {"state": "draft", "text": "Exposure takes a week"}, {"state": "draft", "text": "exposure takes a WEEK"}]
    assert N.unsent(notes)["count"] == 1  # a repeat of a sent note, and the second of two equal drafts, are not unsent


def test_the_rules_say_never_ask_what_is_known_and_never_repeat():
    p = north.system_prompt(practice=True, library=False)
    assert "Never ask a question whose answer is already in the person's own message" in p
    assert "Never repeat your previous reply" in p


# ---- 4. one automatic retry before the person sees a failure
def test_a_turn_that_fails_once_is_retried_and_the_person_sees_the_answer(a):
    world, c = a
    boom = {"n": 0}

    def flaky(messages):
        boom["n"] += 1
        if boom["n"] == 1:
            raise RuntimeError("the provider is down")
        return ModelReply("Thanks. Who is affected?")
    m = use_model(world, StubModel(flaky))
    sid = start_room(world, c, "co-a")
    v = c.post(f"{room(sid)}/messages", json={"text": "Renewals slipped", "kind": "note"}).json()
    assert v["turns"][-1]["answered"] is True and v["turns"][-1]["text"] == "Thanks. Who is affected?"
    assert len(m.calls) == 2 and "went wrong" not in json.dumps(v)


def test_a_turn_that_cannot_finish_is_retried_too_and_fails_plainly_only_after_the_second_try(a):
    world, c = a
    m = use_model(world, StubModel(ModelReply("")))  # never an answer: "could not finish"
    sid = start_room(world, c, "co-a")
    v = c.post(f"{room(sid)}/messages", json={"text": "Renewals slipped", "kind": "note"}).json()
    last = v["turns"][-1]
    assert last["answered"] is False and "could not finish" in last["text"] and len(m.calls) == 2
    assert len(v["notes"]) == 1  # the note is saved either way


def test_a_good_turn_is_not_retried(a):
    world, c = a
    m = use_model(world, StubModel(ModelReply("Who is affected?")))
    sid = start_room(world, c, "co-a")
    c.post(f"{room(sid)}/messages", json={"text": "Renewals slipped", "kind": "note"})
    assert len(m.calls) == 1


# ---- 5. short tasks get a small thinking budget; North's conversation keeps the default
def test_gemini_carries_a_thinking_budget_only_when_asked():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    _, plain = GeminiAdapter().format_request("gemini-2.5-flash", msgs, None)
    assert "thinkingConfig" not in plain["generationConfig"]
    _, short = GeminiAdapter(thinking_budget=512).format_request("gemini-2.5-flash", msgs, None)
    assert short["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 512}
    assert short["generationConfig"]["maxOutputTokens"] == plain["generationConfig"]["maxOutputTokens"]


def test_the_short_task_client_sets_the_budget_on_gemini_only(world, monkeypatch):
    plane = world.plane("co-a").ensure()
    seen = []
    monkeypatch.setattr(short_model, "model_transport", lambda choice, **k: seen.append(choice) or (lambda url, body: ""))
    assert short_model.build_short_client(plane, {}) is None  # no key: no client, as build_model_client
    assert short_model.build_short_client(plane, {"GOOGLE_API_KEY": "not-a-real-key"}) is not None
    assert short_model.build_short_client(plane, {"SH_MODEL_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "not-a-real-key"}) is not None
    gemini, other = seen
    assert isinstance(gemini.adapter, GeminiAdapter) and gemini.adapter.thinking_budget == short_model.THINKING_BUDGET == 512
    assert isinstance(other.adapter, OpenRouterAdapter)


def test_the_grouping_names_are_short_noun_phrases_by_rule():
    rules = " ".join(gather.load_rules()["rules"])
    assert "3 to 7 words" in rules and "never a quote of a note" in rules
