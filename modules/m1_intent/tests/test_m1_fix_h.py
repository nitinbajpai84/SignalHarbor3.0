"""CRITIC-M1 round 2, fix team H: Nira's session facts, the timer wording, North's stray lines, notes at close, a tied vote
on the charter, and guests reading the board and the charter after the close. The model is always a stub."""
import time

import pytest

from m1_kit import BASE
from modules.m1_intent.agent import nira, north
from modules.m1_intent.domain import charter as C
from modules.m1_intent.domain import private_room as R
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.sessions import SessionStore
from test_m1_briefing_kit import make_world, session_at, use_model
from test_m1_charter_kit import CLUSTERS, draft, put_result, ready, stand_in_result  # noqa: F401  (the autouse fixture)
from test_m1_nira import Spy, ask
from test_m1_room_kit import guest, hdr, seat_in
from test_m1_seat_wiring_kit import flow


# ---- Nira: the five questions that got "The organiser would know" ------------------------------------------------
FACTS = {
    "What is the difference between must and should?": ("Must, should, could and not this time", "must comes first, then should", "Nobody can override the votes"),
    "Can I change my note after I submit it?": ("Once a note is submitted it can no longer be changed", "Before you submit a note you can change it"),
    "Is my talk sent outside the company?": ("the model provider receives", "replaced by tokens", "Files, records and tables are never sent"),
    "What happens after we sign the charter?": ("goes to Baseline, the next module, as its starting point",),
    "Who signs, and what does the board show?": ("Only a sponsor or a company administrator can sign", "only after the private rooms close", "counts only, never words"),
}


@pytest.mark.parametrize("question", list(FACTS))
def test_each_briefing_question_reaches_nira_with_the_fact_that_answers_it(tmp_path, question):
    w = make_world(tmp_path)
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="Find our shared worries")
    spy = use_model(w, Spy("A direct answer."))
    assert ask(org, sid, question=question).status_code == 200
    facts = spy.context["session_facts"]
    assert all(f in facts for f in FACTS[question]), question
    s = spy.system.lower()
    assert "answered at once from the facts" in s and "whether a note can be changed" in s and "who signs" in s


def test_the_egress_fact_is_plain_and_honest_about_what_leaves():
    facts = " ".join(nira.load_rules()["session_facts"])
    assert "model provider receives" in facts and "replaced by tokens" in facts  # D-007
    assert "short passages from company documents" in facts and "earlier messages" in facts  # D-032, and the chat history goes too
    assert "Nothing else goes" not in facts and "speech provider" in facts


# ---- the timer warning ---------------------------------------------------------------------------------------------
def test_nearly_up_is_said_only_inside_the_warning_window():
    kw = dict(stage="briefing", rules=[], kind="warning")
    far = nira.ask_nira(None, None, None, "co", "Co", "x", extra="660 seconds are left in this stage.", nearly_up=False, **kw)
    assert far.startswith("About 11 minutes are left in this stage.") and "nearly up" not in far.lower()
    near = nira.ask_nira(None, None, None, "co", "Co", "x", extra="45 seconds are left in this stage.", nearly_up=True, **kw)
    assert "nearly up" in near and "less than a minute" in near


def test_the_route_decides_by_the_timers_own_warning_threshold(tmp_path):
    w = make_world(tmp_path)
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="x")
    far = ask(org, sid, "warning", None).json()["text"]
    assert "nearly up" not in far and "minutes are left" in far
    t = org.get(f"{BASE}/sessions/{sid}/timer").json()
    w.now[0] = t["ends_at_epoch"] - 30 if "ends_at_epoch" in t else w.now[0] + t["remaining_seconds"] - 30
    near = ask(org, sid, "warning", None).json()["text"]
    assert "nearly up" in near and "less than a minute" in near


# ---- North ---------------------------------------------------------------------------------------------------------
def test_your_company_decides_only_with_a_suggestion_never_alone_or_repeated():
    assert R.tidy_reply("Your company decides.") == R.NOTED
    assert "decides" not in R.tidy_reply("Noted, thanks. Your company decides.")
    out = R.tidy_reply("Industry practice (suggestion): the committee signs off. Your company decides. Your company decides.")
    assert out.count("company decides") == 1 and out.endswith("Your company decides.")


def test_the_code_never_deletes_a_sentence_of_the_answer():
    for text in ("It is not acceptable to share client names in this room.", "Sharing pay details is not appropriate in this room.",
                 "Understood, you have no limit today. What threshold would you consider appropriate?", "Is that acceptable to you?"):
        assert R.tidy_reply(text) == text
    out = R.tidy_reply("Industry practice (suggestion): a yearly review is appropriate for most funds. Your company decides.")
    assert out == "Industry practice (suggestion): a yearly review is appropriate for most funds.\nYour company decides."


def test_the_rules_say_all_three_things():
    prompt = north.system_prompt(practice=True, library=False)
    assert "the room adds them once, after a labelled industry-practice suggestion" in prompt
    assert "Never ask for something the person just said they do not have" in prompt and "threshold" in prompt
    assert "Never judge or approve the company's own choices" in prompt


# ---- notes ---------------------------------------------------------------------------------------------------------
def draft_note(text, **over):
    return {"id": "n1", "text": text, "state": "draft", "source": {"kind": "typed"}, "priority": None, "history": [],
            "practice_added": [], "fields": {}, **over}


def test_a_message_with_no_kind_is_an_answer_not_a_note(tmp_path):
    org, sid, people = flow(make_world(tmp_path), "co-a")
    a = people[0]
    r = a.call("POST", "/room/messages", json={"text": "Can the family council see this?"})
    assert r.status_code == 200 and r.json()["notes"] == []


def test_closing_the_rooms_submits_every_real_note_except_exact_repeats(tmp_path):
    org, sid, people = flow(make_world(tmp_path), "co-a")
    a, b = people
    texts = ["How can I trust the NAV?", "Can I trust my NAV figures?", "Who owns my team's benchmark list?"]
    for t in texts:
        a.write(t)
    a.write("Who owns my team's benchmark list?")                  # an exact repeat: the dedup keeps one
    b.write("Pay is not trusted")
    assert org.post(f"{BASE}/sessions/{sid}/rooms/close").status_code == 200
    got = sorted(n["text"] for n in org.get(f"{BASE}/sessions/{sid}/board").json()["on_its_own"])
    assert got == sorted([*texts, "Pay is not trusted"])


# ---- a tied vote on the charter -----------------------------------------------------------------------------------
TIE = {"id": "c3", "title": "Pay depends on trusted performance", "priority": None, "votes": {"must": 1, "should": 2, "could": 2, "not_this_time": 0},
       "note_count": 2, "agree_count": 1, "ticked": True, "so_that": None, "library_problem_id": None}


def tied(world):
    org, sid, code = ready(world, seats=1)
    put_result(world, "co-a", sid, [TIE, {**CLUSTERS[0], "votes": {"must": 3, "should": 0, "could": 0, "not_this_time": 0}}])
    return org, sid, code


def test_a_tie_reads_tied_and_the_organiser_can_choose_among_the_tied_options(world):
    org, sid, _ = tied(world)
    p = {x["id"]: x for x in draft(org, sid)["charter"]["problems"]}
    assert p["c3"]["priority"] is None and p["c3"]["tie"] == "Tied: must 1 · should 2 · could 2. The room decides."
    assert [o["id"] for o in p["c3"]["tied_options"]] == ["should", "could"] and p["c1"]["tie"] is None
    put = lambda body: org.put(f"{BASE}/sessions/{sid}/charter", json=body)  # noqa: E731
    assert put({"priority": {"c3": "must"}}).status_code == 422     # not one that tied
    assert put({"priority": {"c1": "could"}}).status_code == 422    # the vote decided that one: nothing overrides it (D-020)
    assert put({"priority": {"nope": "should"}}).status_code == 422
    r = put({"priority": {"c3": "should"}, "so_that": {"c3": "pay follows trusted figures"}})
    assert r.status_code == 200
    p = {x["id"]: x for x in r.json()["charter"]["problems"]}
    assert (p["c3"]["priority"], p["c3"]["priority_label"], p["c3"]["tie"]) == ("should", "Should", None)
    assert p["c1"]["priority"] == "must"
    # signed means read-only
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]["status"] == "signed"
    assert put({"priority": {"c3": "could"}}).status_code in (404, 409)


def test_a_new_draft_keeps_the_organisers_choice_for_a_tie():
    s = C.CharterSettings((("must", "Must"), ("should", "Should"), ("could", "Could"), ("not_this_time", "Not this time")), 2, 1,
                          frozenset({"sponsor"}), 72, 1000, 300)
    class T:
        id, name, columns = "t", "T", ()
    clusters = C.clean_together({"clusters": [TIE]}, s)
    first = C.build_version(clusters, T, s, number=1, by="o", now="n", date="d", participants=1, earlier=None)
    chosen = C.edit_priorities(first, {"c3": "could"}, s, "o", "n")
    second = C.build_version(clusters, T, s, number=2, by="o", now="n", date="d", participants=1, earlier=chosen)
    assert second["problems"][0]["priority"] == "could" and second["problems"][0]["priority_edited"] is True


# ---- guests after the close -----------------------------------------------------------------------------------------
def test_a_seated_guest_reads_the_charter_after_the_close_and_can_write_nothing(world):
    org, sid, code = ready(world, seats=3)
    g = guest(world)
    token, _ = seat_in(world, g, code, 1, name="Sara Guest")
    gone_token, _ = seat_in(world, guest(world), code, 2, name="Gone Guest")
    assert org.post(f"{BASE}/sessions/{sid}/seats/2/revoke").status_code == 200
    draft(org, sid)
    SessionStore(world.plane("co-a")).transition(sid, "closed")
    r = g.get(f"{BASE}/sessions/{sid}/charter", headers=hdr(token))
    assert r.status_code == 200, r.text
    c = r.json()["charter"]
    assert c["signing"]["can_sign"] is False and c["editable"] is False and r.json()["organiser"] is False
    assert g.get(f"{BASE}/sessions/{sid}/board", headers=hdr(token)).status_code == 200
    for method, path, body in (("post", "/charter/sign", None), ("put", "/charter", {"so_that": {"c1": "x"}}),
                               ("post", "/charter", None), ("post", "/charter/send", None), ("post", "/rooms/close", None),
                               ("post", "/board/group", None), ("post", "/room/messages", {"text": "hello"}),
                               ("post", "/together/clusters/c1/vote", {"option": "must"})):
        r = getattr(g, method)(f"{BASE}/sessions/{sid}{path}", headers=hdr(token), **({"json": body} if body is not None else {}))
        assert r.status_code in (401, 403, 404, 409), (path, r.status_code)
    # a token of another session, a stranger and an unseated token still get nothing
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter", headers=hdr("garbage")).status_code == 401
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter").status_code == 401
    assert guest(world).get(f"{BASE}/sessions/{sid}/board").status_code == 401
    # a revoked seat stays out
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter", headers=hdr(gone_token)).status_code == 401


def test_a_guest_of_a_closed_session_reads_only_the_charter_and_the_board(world):
    org, sid, code = ready(world, seats=2)
    g = guest(world)
    token, _ = seat_in(world, g, code, 1, name="Sara Guest")
    draft(org, sid)
    SessionStore(world.plane("co-a")).transition(sid, "closed")
    h = hdr(token)
    for path in ("/charter", "/board"):
        assert g.get(f"{BASE}/sessions/{sid}{path}", headers=h).status_code == 200, path
    for method, path, body in (("get", "/room", None), ("get", "/room/library", None), ("get", "/voice", None),
                               ("get", "/briefing", None), ("get", "/timer", None), ("get", "/together", None),
                               ("post", "/briefing/confirm", {}), ("post", "/nira", {"question": "hello"})):
        r = getattr(g, method)(f"{BASE}/sessions/{sid}{path}", headers=h, **({"json": body} if body is not None else {}))
        assert r.status_code in (401, 403, 404, 409), (path, r.status_code)


def test_a_guest_token_stops_working_thirty_days_after_the_close(world):
    org, sid, code = ready(world, seats=2)
    g = guest(world)
    token, _ = seat_in(world, g, code, 1, name="Sara Guest")
    draft(org, sid)
    now = [time.time()]
    world.app.state.m1_clock = lambda: now[0]
    SessionStore(world.plane("co-a"), clock=lambda: now[0]).transition(sid, "closed")
    url = f"{BASE}/sessions/{sid}/charter"
    assert g.get(url, headers=hdr(token)).status_code == 200
    now[0] += 29 * 86400
    assert g.get(url, headers=hdr(token)).status_code == 200
    now[0] += 2 * 86400
    assert g.get(url, headers=hdr(token)).status_code == 401
    assert g.get(f"{BASE}/sessions/{sid}/board", headers=hdr(token)).status_code == 401
