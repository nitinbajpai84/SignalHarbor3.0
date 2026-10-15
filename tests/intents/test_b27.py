"""B27: every row of spec 13's table makes its line from a fixture record, one line per person per intent, the cap and `more`, lines go
when the record changes, and the Weekly check-in wording. Spec 45: the whole list order and the nudge."""
import json
from datetime import datetime, timezone

import sh_platform.pulse as pulse
from sh_platform.profile import view
from sh_platform.pulse import intent_lines as L, messages

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)  # a Wednesday
AARON = view.Viewer("Aaron Lyle", frozenset({"participant"}), account_id="a-aaron")
KATIE = view.Viewer("Katie", frozenset({"analyst"}), account_id="a-katie")
JANET = view.Viewer("Janet Shaw", frozenset({"company_admin"}), account_id="a-janet")
DANIEL = view.Viewer("Daniel Kerr", frozenset({"sponsor"}), account_id="a-daniel")
HARVEY = view.Viewer("Harvey Rowley", frozenset({"owner"}), account_id="a-harvey")
ASK = {"person": {"account_id": "a-aaron"}, "what": "x", "since": "x"}


class Plane:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return self.root.joinpath(*parts)


def put(plane, rec, week=None, events=()):
    d = plane.path("intents", rec["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "intent.json").write_text(json.dumps(rec), encoding="utf-8")
    if week:
        (d / "weeks").mkdir(exist_ok=True)
        (d / "weeks" / f"{week['week_key']}.json").write_text(json.dumps(week), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def rec(id="i1", type="brainstorm", state="open", stage="choose", **kw):
    r = {"id": id, "type": type, "title": "Faster month-end close", "purpose": "close in three days", "created_by": "a-janet", "state": state,
         "areas": ["Finance"], "updated_at": "2026-10-06T10:00:00+00:00",
         "people": {"organiser": {"account_id": "a-janet", "name": "Janet Shaw"}, "sponsor": None, "decider": None, "owner": None, "reporter": None,
                    "participants": [{"account_id": "a-aaron", "name": "Aaron Lyle"}, {"account_id": "a-katie", "name": "Katie"}],
                    "advisers": [], "affected": [], "observers": []},
         "time_box": {"starts": "2026-10-05T09:00:00+00:00", "ends": "2026-10-30T09:00:00+00:00", "extended_by": []},
         "stages": [{"key": stage, "state": "open", "opened_at": "2026-10-06T09:00:00+00:00", "closed_at": None}], "closure": {}, "ratings": []}
    r.update(kw)
    return r


def people(**slots):
    return {**rec()["people"], **slots}


def trigs(plane, v):
    return [t for _, t, _, _ in L.candidates(plane, v, NOW)]


def one(plane, v, trig):
    got = [ln for _, t, _, ln in L.candidates(plane, v, NOW) if t == trig]
    assert len(got) == 1, (trig, got)
    return got[0]


def test_row_1_invited_and_row_16_count_only(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(stage="think_alone"), events=[{"at": "2026-10-06T12:00:00+00:00", "by": {"account": "a-katie"}, "status": "act"}])
    ln = one(p, AARON, "invite")
    assert (ln["id"], ln["kind"], ln["action"], ln["href"]) == ("intent:i1:invite", "invite", "Add your ideas", "/centre/intent/i1")
    assert ln["detail"] == "Janet invited you to a Brainstorm: close in three days." and ln["due"] == "2026-10-07"
    got = L.strips(p, JANET, NOW)
    assert got["waiting"][0]["title"] == "Faster month-end close: 1 of 2 have not added ideas"
    assert "Aaron" not in json.dumps(got)  # counts only, never who
    assert "invite" not in trigs(p, KATIE)  # she has acted


def test_row_2_your_turn_by_type_and_stage(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(waiting_on={"person": {"account_id": "a-janet"}, "what": "Six people added 14 ideas. Pick the one to take forward.", "since": "2026-10-06T10:00:00+00:00"}))
    ln = one(p, JANET, "turn")
    assert (ln["title"], ln["action"], ln["kind"]) == ("Your turn on Faster month-end close", "Choose the idea", "decision")
    put(p, rec(id="i2", type="pulse", stage="sort", waiting_on=ASK))
    sort = [ln for _, t, _, ln in L.candidates(p, AARON, NOW) if ln["id"] == "intent:i2:turn"][0]
    assert (sort["action"], sort["href"]) == ("Give each item a fate", "/centre/intent/i2/review")


def test_row_3_start_questions(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(state="draft", created_by="a-janet", start_answers={"b1": "x"}))
    ln = one(p, JANET, "start")
    assert ln["title"].startswith("Finish starting") and ln["detail"].startswith("4 questions are left.")
    assert ln["href"] == "/centre/intent/new?type=brainstorm&draft=i1"
    assert not L.candidates(p, AARON, NOW)  # a draft gives a line to its creator only


def test_rows_4_5_6_17(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(drafts_to_confirm=[{"id": "d1", "author": "a-aaron", "text": "x", "confirmed_by": None}]))
    assert one(p, AARON, "card")["action"] == "Check the card"
    vote = {"id": "v1", "question": "Which cluster is a Must?", "voters": ["a-aaron", "a-katie"], "cast_by": ["a-katie"], "closes": "2026-10-09", "state": "open"}
    put(p, rec(type="initiative", stage="define_strategically", votes=[vote]))
    ln = one(p, AARON, "vote")
    assert (ln["title"], ln["detail"], ln["href"], ln["action"]) == (
        "Vote: Which cluster is a Must?", "1 of 2 have voted. The vote closes Fri 9 Oct.", "/centre/intent/i1/define", "Vote")
    put(p, rec(votes=[vote]))
    assert one(p, AARON, "vote")["title"] == "Back up to three ideas in Faster month-end close"
    put(p, rec(definitions_waiting=[{"term": "Net asset value", "owner": "a-harvey", "drafted_by": "Lens", "state": "open"}],
               process_waiting=[{"id": "s1", "step": "Approve the NAV", "owner": "a-harvey", "drafted_by": "Lens", "confirmed_by": None, "state": "open"}]))
    assert one(p, HARVEY, "definition")["title"] == "A term needs your confirmation: Net asset value"
    assert one(p, HARVEY, "process")["title"] == "A process step needs your check: Approve the NAV"


def test_rows_8_and_9_time_box(tmp_path):
    p = Plane(tmp_path)
    tb = {"starts": "2026-09-24T09:00:00+00:00", "ends": "2026-10-08T21:00:00+00:00", "extended_by": []}  # 10 working days, 2 left
    put(p, rec(type="problem", stage="fix", time_box=tb))
    ln = one(p, JANET, "clock")
    assert ln["title"] == "Faster month-end close: 2 working days left of 10" and ln["kind"] == "clock" and ln["href"].endswith("/close")
    assert [s for _, t, s, _ in L.candidates(p, JANET, NOW) if t == "clock"] == ["decide"]  # the stages left need more than 2 days: will not hold
    put(p, rec(type="problem", stage="fix", time_box={**tb, "ends": "2026-10-06T09:00:00+00:00"}))
    assert one(p, JANET, "overdue")["detail"] == "It ended on Tue 6 Oct. Overdue by 1 working day. Pick one: extend, close with what we have, or cancel."
    put(p, rec(type="pulse", stage="collect", time_box={**tb, "ends": "2026-10-06T09:00:00+00:00"}))
    assert not {"clock", "overdue"} & set(trigs(p, JANET))  # a check-in week has its own clock


def test_rows_10_and_10a_closing(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(type="initiative", state="closing", stage="build_ready", people=people(sponsor={"account_id": "a-daniel", "name": "Daniel Kerr"})))
    ln = one(p, DANIEL, "closesign")
    assert (ln["kind"], ln["action"], ln["href"]) == ("signature", "Review and close", "/centre/intent/i1/close")
    assert "closeit" not in trigs(p, JANET)  # the sponsor has not signed
    put(p, rec(type="initiative", state="closing", stage="build_ready", closure={"confirmed": [{"role": "sponsor", "by": "a-daniel"}]}, people=people(sponsor={"account_id": "a-daniel"})))
    assert one(p, JANET, "closeit")["title"] == "Close Faster month-end close"
    put(p, rec(state="closing"))  # a Brainstorm needs no confirmer
    assert one(p, JANET, "closeit")["action"] == "Close it"


def test_rows_11_and_12_rating_and_share(tmp_path):
    p = Plane(tmp_path)
    closure = {"closed_at": "2026-10-05T10:00:00+00:00", "summary": "x" * 200}
    put(p, rec(state="closed", closure=closure, share={"who_may_open": [{"person_id": "a-daniel", "revoked_at": None}]}))
    ln = one(p, AARON, "rating")
    assert (ln["kind"], ln["href"], ln["due"], ln["minutes"]) == ("rating", "/centre/intent/i1/close#rate", "2026-10-12", 1)
    out = one(p, DANIEL, "outcome")
    assert (out["kind"], out["href"], len(out["detail"])) == ("outcome", "/centre/intent/i1/share", 140)
    put(p, rec(state="closed", closure={**closure, "closed_at": "2026-09-20T10:00:00+00:00"}))
    assert not L.candidates(p, AARON, NOW)  # past the window
    put(p, rec(state="closed", closure=closure, ratings=[{"by": "a-aaron", "score": 4}]))
    assert not L.candidates(p, AARON, NOW)  # already rated
    put(p, rec(type="pulse", state="closed", closure=closure))
    assert not L.candidates(p, AARON, NOW)  # a check-in is not rated
    put(p, rec(state="closed", closure=closure, affected_may_read=True, people=people(affected=["a-daniel"])))
    assert "outcome" in trigs(p, DANIEL)  # affected people, only where the switch is on


def test_row_13_weekly_checkin_wording(tmp_path):
    p = Plane(tmp_path)
    week = {"week_key": "2026-W41", "opens": "2026-10-05", "closes": "2026-10-09", "state": "collect", "items": [], "closed_at": None}
    put(p, rec(type="pulse", stage="collect", areas=["Treasury"]), week=week)
    ln = one(p, AARON, "week")
    assert (ln["title"], ln["kind"], ln["action"], ln["href"], ln["due"], ln["minutes"]) == (
        "Your week for Treasury", "request", "Answer three questions", "/centre/intent/i1/week", "2026-10-09", 5)
    assert ln["detail"] == "Three questions: what ran well, what broke or nearly broke, what is on your mind. About 5 minutes."
    assert "Pulse" not in json.dumps(ln)  # the record key is never shown
    assert "invite" not in trigs(p, AARON)  # row 13 takes over from row 1
    put(p, rec(type="pulse", stage="collect"), week={**week, "items": [{"by": "a-aaron", "kind": "ran", "text": "x"}]})
    assert "week" not in trigs(p, AARON)  # a person who answered no longer has the line


def test_rows_14_and_15(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(type="problem", stage="describe", purpose="Capital call file is late", people=people(owner={"account_id": "a-harvey"})))
    ln = one(p, HARVEY, "owner")
    assert (ln["title"], ln["action"]) == ("A problem needs an owner: Faster month-end close", "Take it") and "Janet reported it" in ln["detail"]
    put(p, rec(type="problem", stage="describe", owner_accepted_at="2026-10-06", people=people(owner={"account_id": "a-harvey"})))
    assert not L.candidates(p, HARVEY, NOW)
    opts = [{"name": "A", "notes": [{"by": "a-aaron"}, {"by": "a-katie"}]}, {"name": "B", "notes": []}]
    put(p, rec(type="decision", stage="decide", outcome={"options": opts}, people=people(decider={"account_id": "a-daniel"})))
    ln = one(p, DANIEL, "decide")
    assert (ln["detail"], ln["action"]) == ("2 advisers have given views and 2 options are set out. Choose one and give the reason.", "Decide")


def test_one_line_per_intent_in_priority_order_and_gone_when_record_changes(tmp_path):
    p = Plane(tmp_path)
    r = rec(waiting_on=ASK, votes=[{"id": "v", "question": "q", "voters": ["a-aaron"], "cast_by": [], "state": "open"}],
            drafts_to_confirm=[{"author": "a-aaron", "confirmed_by": None}])
    put(p, r)
    assert {"turn", "vote", "card", "invite"} <= set(trigs(p, AARON))
    assert [ln["id"] for rows in L.strips(p, AARON, NOW).values() for ln in rows] == ["intent:i1:turn"]  # the highest wins, the rest wait
    r["waiting_on"] = None  # the record changes: the line is gone, nothing was stored
    put(p, r)
    assert [ln["id"] for rows in L.strips(p, AARON, NOW).values() for ln in rows] == ["intent:i1:vote"]
    assert len(L.waiting(p, AARON, NOW)) == 3  # the Intent home strip keeps them all


def test_cancelled_and_other_people_get_nothing(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(state="cancelled", waiting_on=ASK))
    assert not L.candidates(p, AARON, NOW)
    put(p, rec(waiting_on=ASK))
    assert not L.candidates(p, HARVEY, NOW)


def test_cap_of_seven_and_more_count(tmp_path):
    p = Plane(tmp_path)
    L.install(pulse)
    for n in range(9):
        put(p, rec(id=f"i{n}", waiting_on=ASK, stages=[{"key": "choose", "state": "open", "opened_at": "2026-10-06T09:00:00+00:00", "due": f"2026-10-{10 + n}"}]))
    data = pulse.build(p, AARON, None, NOW)
    shown = [ln for s in data["strips"] for ln in s["lines"]]
    assert len(shown) == 7 and data["more"] == 2
    assert [ln["due"] for ln in shown] == sorted(ln["due"] for ln in shown)  # earliest due first, the latest are the ones cut


def test_group_order_signature_then_decision_then_question_then_rating(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(id="r", state="closed", closure={"closed_at": "2026-10-05T10:00:00+00:00"}))
    put(p, rec(id="q", state="draft", created_by="a-aaron"))
    put(p, rec(id="d", waiting_on=ASK))
    put(p, rec(id="s", type="decision", state="closing", people=people(decider={"account_id": "a-aaron"})))
    assert [ln["id"].split(":")[1:] for ln in L.waiting(p, AARON, NOW)] == [["s", "closesign"], ["d", "turn"], ["d", "invite"], ["q", "start"], ["r", "rating"]]


def test_nudge_draft_is_signed_north_with_chat_and_link(tmp_path):
    from sh_platform.intents import nira  # registers the message kind
    p = Plane(tmp_path)
    key = "intents/i1#nudge:choose:2026-10-07"
    m = messages.draft(p, "intent_nudge", {"to": [{"account_id": "a-katie", "name": "Katie"}], "title": "Faster month-end close", "what": "Add your ideas",
                                           "due": "2026-10-09", "link": "/centre/intent/i1", "organiser_account_id": "a-janet", "from_record": key})
    assert m["state"] == "draft" and m["subject"] == "A reminder: Faster month-end close is waiting for you"
    assert m["body"].rstrip().endswith("North") and m["link"] == "/centre/intent/i1" and len(m["chat"]) <= 240
    assert messages.draft(p, "intent_nudge", {"from_record": key, "to": []})["id"] == m["id"]  # same day, same draft
    assert len(nira.intent_nudge({"title": "T" * 400})["chat"]) == 240


def test_protect_keeps_decisions_and_yields_organiser_strips_first():
    ln = lambda i: {"id": i, "due": None, "source": {"at": None}}
    res = [("start", [ln("s1"), ln("s2")]), ("running", [ln(f"r{n}") for n in range(5)]), ("waiting", [ln("w1")]),
           ("invited", [ln("i1")]), ("decide", [ln(f"d{n}") for n in range(3)]), ("watch", [ln("x1")])]
    got = dict(L._protect(res, 7, pulse._order))
    assert len(got["decide"]) == 3 and [r["id"] for r in got["invited"]] == ["i1"] and len(got["watch"]) == 1
    assert sum(len(v) for v in got.values()) == 7 and len(got["start"]) + len(got["running"]) + len(got["waiting"]) == 2


def test_speed_guard_200_intents_each_read_once(tmp_path, monkeypatch):
    """F21: with 200 intents the organiser's Pulse opens each intent.json once (every reader shares the request's read) and stays fast."""
    import time
    from pathlib import Path
    p = Plane(tmp_path)
    L.install(pulse)
    for n in range(200):
        put(p, rec(id=f"bra-{n:032x}", state=("open", "closed", "cancelled", "closing")[n % 4], waiting_on=ASK))
    pulse.build(p, JANET, None, NOW)  # warm: first imports, and a new file's first open (a virus scan on this box) are not the reader's cost
    reads = []
    for name in ("read_text", "read_bytes"):
        plain = getattr(Path, name)
        monkeypatch.setattr(Path, name, lambda self, *a, _f=plain, **k: (reads.append(self) if self.name == "intent.json" else None, _f(self, *a, **k))[1])
    start = time.perf_counter()
    data = pulse.build(p, JANET, None, NOW)
    took = time.perf_counter() - start
    assert len(reads) == 200 and len(set(reads)) == 200, len(reads)
    assert sum(len(s["lines"]) for s in data["strips"]) == 7 and data["more"] > 0
    assert took < 1.5, took


def test_backlog_review_ranks_with_signatures_so_it_is_not_buried():  # F35
    ln = lambda i: {"id": i, "due": None, "source": {"at": None}}
    res = [("decide", [ln(f"intent:i{n}:decide") for n in range(9)] + [ln("backlog-review:bl-1")])]
    got = dict(L._protect(res, 7, pulse._order))
    assert "backlog-review:bl-1" in [r["id"] for r in got["decide"]]


def test_an_invited_person_on_an_initiative_wall_is_asked_for_cards_until_they_have_written_one(tmp_path):  # F51
    p = Plane(tmp_path)
    detail = [{"person_id": "a-aaron", "status": "invited"}, {"person_id": "a-katie", "status": "contributed"}]
    put(p, rec(type="initiative", stage="think_unfiltered", people_detail=detail))
    ln = one(p, AARON, "wallcards")
    assert (ln["id"], ln["action"], ln["href"]) == ("intent:i1:wallcards", "Add your cards", "/centre/intent/i1/wall")
    assert "wallcards" not in trigs(p, KATIE)  # she has already added a card


def _detail(person, role, status):
    return {"person_id": person, "name": person, "role": role, "status": status}


def test_w2f1_unanswered_invitation_is_a_line_on_home_and_pulse(tmp_path):
    p = Plane(tmp_path)
    put(p, rec(type="initiative", stage="think_unfiltered", people_detail=[_detail("a-aaron", "participant", "invited"), _detail("a-katie", "affected", "invited")]))
    got = L.waiting(p, AARON, NOW)
    assert [(x["action"], x["id"]) for x in got] == [("Accept or decline", "intent:i1:invitation")]  # said once, not again as "Add your cards"
    assert [x["id"] for x in L.strips(p, AARON, NOW)["invited"]] == ["intent:i1:invitation"]
    assert "invitation" not in trigs(p, KATIE)  # told, nothing asked of an affected person
    put(p, rec(type="initiative", stage="think_unfiltered", people_detail=[_detail("a-aaron", "participant", "joined")]))
    assert "invitation" not in trigs(p, AARON)


def test_w2f1_a_closed_check_in_week_asks_nothing(tmp_path):
    p = Plane(tmp_path)
    wk = {"week_key": "2026-W41", "state": "collect", "opens": "2026-10-05", "answers_close": "2026-10-07", "closes": "2026-10-09", "items": [], "answers": []}
    put(p, rec(type="pulse", stage="collect", title="Weekly"), week=wk)
    assert "week" in trigs(p, AARON)  # the last day of answers
    put(p, rec(type="pulse", stage="collect", title="Weekly"), week={**wk, "answers_close": "2026-10-06"})  # the stored state lags the calendar
    assert "week" not in trigs(p, AARON)
