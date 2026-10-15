"""B22: the Weekly check-in series (38) and the reporter's entry (39), on a temporary company plane."""
import json
from datetime import datetime, timezone

import pytest

from sh_platform.intents import checkin as C, lifecycle as L, store as S
from sh_platform.plane import CompanyPlane
from sh_platform.profile import view as pview

NAMES = (("acc-janet", "Janet Shaw"), ("acc-aaron", "Aaron Lyle"), ("acc-harvey", "Harvey Rowley"))
PEOPLE = [{"id": a, "name": n, "role": "Analyst", "tagged": True, "has_account": True} for a, n in NAMES]
AREAS = [{"id": "fund-operations", "name": "Fund Operations", "kind": "operations_area", "status": "active", "from": ""}]
V = {n: pview.Viewer(n, frozenset({"participant"}), False, a) for a, n in NAMES}


def T(d, h=9):
    return datetime(2026, 10, d, h, tzinfo=timezone.utc)  # 5 Oct 2026 is a Monday


@pytest.fixture
def world(tmp_path, monkeypatch):
    plane = CompanyPlane("ardmore", tmp_path)
    monkeypatch.setattr(C, "setup_options", lambda p, area: {"areas": AREAS, "people": PEOPLE, "minimum": 2, "extra_max": 240})
    box = {"who": V["Janet Shaw"]}
    monkeypatch.setattr(C, "_plane", lambda r: plane)
    monkeypatch.setattr(C, "_viewer", lambda r: box["who"])
    rec = L.new_record("pulse", "ardmore", L.person("acc-janet", "Janet Shaw"), T(5).isoformat())
    S.create_intent(plane, rec)
    return plane, rec["id"], box


def settings(plane, iid, body):
    rec = S.read_intent(plane, iid)
    C._apply_settings(plane, rec, body, V["Janet Shaw"])
    S.write_intent(plane, rec)


def start(plane, iid, box, now=T(5)):
    box["who"] = V["Janet Shaw"]
    settings(plane, iid, {"area": "Fund Operations", "reporters": ["acc-aaron", "acc-harvey"], "close_day": "fri", "reviewer": "acc-janet",
                          "extra_prompt": "What did you wait on that you should not have?"})
    return C._act(None, iid, "start", {}, now)


def test_four_setup_questions_and_the_start_rules(world):
    plane, iid, box = world
    assert [q["id"] for q in L.type_def("pulse")["start_questions"]] == ["p1", "p2", "p3", "p4"]
    settings(plane, iid, {"area": "Fund Operations"})
    with pytest.raises(C.Refuse, match="at least 2"):
        C._act(None, iid, "start", {}, T(5))  # question 2 not answered
    with pytest.raises(C.Refuse):
        C._apply_settings(plane, S.read_intent(plane, iid), {"extra_prompt": "x" * 241}, V["Janet Shaw"])
    out = start(plane, iid, box)
    rec = S.read_intent(plane, iid)
    assert out["state"] == "open" and rec["title"] == "Check-in: Fund Operations" and rec["series"]["close_day"] == "fri"
    prompts = C._prompts(rec["series"])
    assert len(prompts) == 4 and prompts[-1]["lead"].startswith("What did you wait") and prompts[-1]["kind"] == "thought"
    assert rec["series"]["current_week"] == "2026-W41" and [s["key"] for s in rec["stages"]] == ["running"]


def test_next_week_opens_by_the_clock_even_if_review_is_late(world):
    plane, iid, box = world
    start(plane, iid, box)
    w = C.read_week(plane, iid, "2026-W41")
    assert (w["opens"], w["answers_close"], w["review_day"], w["closes"]) == ("2026-10-05", "2026-10-07", "2026-10-08", "2026-10-09")
    assert C.tick(plane, iid, T(9))["series"]["current_week"] == "2026-W41"  # Friday: the same week
    rec = C.tick(plane, iid, T(12))  # Monday, the next working day after the close day; nobody reviewed anything
    assert rec["series"]["weeks"] == ["2026-W41", "2026-W42"] and rec["series"]["current_week"] == "2026-W42"
    assert C.read_week(plane, iid, "2026-W41")["state"] == "closing" and C.read_week(plane, iid, "2026-W42")["state"] == "collect"
    assert [p["name"] for p in C.read_week(plane, iid, "2026-W42")["people"]] == ["Aaron Lyle", "Harvey Rowley"]
    assert len(C.tick(plane, iid, T(12))["series"]["weeks"]) == 2  # a second reader opens no second week
    C._act(None, iid, "pause", {}, T(13))  # the open week finishes; nothing new opens until resume
    assert len(C.tick(plane, iid, T(26))["series"]["weeks"]) == 2
    assert C._act(None, iid, "resume", {}, T(26))["series"]["next_week_opens"] == "2026-10-27"
    with pytest.raises(C.Refuse, match="reason"):
        C._act(None, iid, "end", {}, T(27))
    C._act(None, iid, "end", {"reason": "The area is closing"}, T(27))
    assert S.read_intent(plane, iid)["state"] == "closing" and C.read_week(plane, iid, "2026-W42")["state"] == "closing"


def add(plane, iid, box, who, kind, text, now=T(6), **kw):
    box["who"] = V[who]
    return C._write_entry(None, iid, None, [{"op": "add", "kind": kind, "text": text, **kw}], False, now)


def test_items_shape_severity_only_by_the_person_and_anonymous_per_item(world):
    plane, iid, box = world
    start(plane, iid, box)
    add(plane, iid, box, "Aaron Lyle", "ran", "Mailbox loaded on time")
    add(plane, iid, box, "Aaron Lyle", "broke", "Custodian file came late twice")
    out = add(plane, iid, box, "Aaron Lyle", "thought", "Key-person risk on month end", anonymous=True)
    broke = next(i for i in out["items"] if i["kind"] == "broke")
    assert broke["severity"] is None and broke["count"] is None and broke["amount"] is None and broke["fate"] is None  # never filled for them
    with pytest.raises(C.Refuse):  # severity belongs to a line about something that broke
        C._write_entry(None, iid, None, [{"op": "update", "id": out["items"][0]["id"], "severity": "slowed"}], False, T(6))
    out = C._write_entry(None, iid, None, [{"op": "update", "id": broke["id"], "severity": "slowed", "count": 2, "unit": "times"}], True, T(6))
    assert next(i for i in out["items"] if i["kind"] == "broke")["severity"] == "slowed" and out["status"] == "submitted"
    w = C.read_week(plane, iid, "2026-W41")
    assert {"id", "by", "kind", "text", "severity", "count", "amount", "ref", "fate", "fate_reason", "decided_by"} <= set(w["items"][0])
    anon = [i for i in w["items"] if i["anonymous"]]
    assert len(anon) == 1 and anon[0]["by"] is None and anon[0]["by_name"] is None
    assert all(i["by"] == "acc-aaron" for i in w["items"] if not i["anonymous"])  # anonymity is per item
    rec = S.read_intent(plane, iid)
    assert C.entry_view(plane, rec, w, V["Harvey Rowley"], T(6))["items"] == []  # another reporter sees none of it
    w["state"] = "review"
    C.write_week(plane, iid, w)
    shown = [C._shown(i) for i in w["items"] if i["state"] == "active"]
    assert "Anonymous" in json.dumps(shown) and "acc-aaron" not in json.dumps(shown)
    assert next(c for c in shown if c["kind"] == "thought")["provenance"] == "Stated, name hidden"
    assert len(C._own_items(plane, rec, w, V["Aaron Lyle"])) == 3  # the author finds the anonymous one through their own file
    assert rec["ratings"] == [] and L.type_def("pulse")["rated"] is False and "rating" not in json.dumps(w)  # never rated
    with pytest.raises(C.Refuse, match="closed"):  # answers have closed on Thursday
        add(plane, iid, box, "Harvey Rowley", "ran", "Too late", now=T(8))


def test_prefill_is_guessed_and_the_person_confirms(world):
    plane, iid, box = world
    start(plane, iid, box)
    (plane.root / "warehouse").mkdir(exist_ok=True)
    runs = [{"id": f"r{n}", "source": "capital_calls_mailbox", "started": f"2026-10-0{n}T07:00:00+00:00", "on_time": n != 7,
             "status": "ok", "owner": "Aaron Lyle", "rows": 10} for n in (5, 6, 7)]
    (plane.root / "warehouse" / "runs.json").write_text(json.dumps({"runs": runs}), encoding="utf-8")
    (plane.root / "build").mkdir(exist_ok=True)
    alert = {"id": "x:failed", "kind": "failed", "source": "bank_feed", "owner": "Aaron Lyle", "state": "open", "opened": "2026-10-06", "at": None}
    (plane.root / "build" / "alerts.json").write_text(json.dumps({"alerts": [alert]}), encoding="utf-8")
    w = C.read_week(plane, iid, "2026-W41")
    drafts = C.drafts_for(plane, w, V["Aaron Lyle"])
    assert [(d["kind"], d["text"]) for d in drafts] == [("ran", "Capital calls mailbox: 2 of 3 loads on time"), ("broke", "Bank feed: failed its checks")]
    assert C.drafts_for(plane, w, V["Harvey Rowley"]) == []  # only what the person owns
    box["who"] = V["Aaron Lyle"]
    out = C._write_entry(None, iid, None, [{"op": "keep_all"}], False, T(6))
    assert [i["mark"] for i in out["items"]] == ["guessed", "guessed"] and all(i["severity"] is None and i["count"] is None for i in out["items"])
    w = C.read_week(plane, iid, "2026-W41")
    assert C._open_drafts(plane, w, V["Aaron Lyle"], C._sub(w, V["Aaron Lyle"])) == []
    ids = [i["id"] for i in out["items"]]
    out = C._write_entry(None, iid, None, [{"op": "confirm", "id": ids[0]}, {"op": "update", "id": ids[1], "text": "Bank feed failed, fixed Wednesday"}], False, T(6))
    assert [i["mark"] for i in out["items"]] == ["stated", "stated"] and out["guessed"] == 0


class _Clock(datetime):  # the routes read the real clock; the seeded week 2026-W41 must still be open
    @classmethod
    def now(cls, tz=None):
        return T(6)


def test_weeks_route_counts_for_all_names_for_the_reviewer_only(world, monkeypatch):
    plane, iid, box = world
    monkeypatch.setattr(C, "datetime", _Clock)
    start(plane, iid, box)
    add(plane, iid, box, "Aaron Lyle", "ran", "Mailbox on time")
    C._write_entry(None, iid, None, [], True, T(6))
    box["who"] = V["Janet Shaw"]
    d = C.get_intents_by_intent_id_weeks(iid, None)
    assert d["not_answered"] == ["Harvey Rowley"] and d["weeks"][0]["answered"] == 1 and d["setup"]["preview"]["closes"]
    box["who"] = V["Harvey Rowley"]
    d = C.get_intents_by_intent_id_weeks(iid, None)
    assert d["not_answered"] is None and "setup" not in d and d["participant"] is True
    answers = C.post_intents_by_intent_id_weeks_by_week_key_answers(iid, "2026-W41", {"lines": {"broke": "Late file"}, "anonymous": ["broke"]}, None)
    assert answers["status"] == "submitted" and answers["items"][0]["anonymous"] is True


def test_weeks_route_answers_on_a_fresh_draft_with_no_query(world):
    _, iid, _ = world
    d = C.get_intents_by_intent_id_weeks(iid, None)  # called as the route is, with no query
    assert d["state"] == "draft" and d["series"] is None and d["weeks"] == [] and d["setup"]["preview"]["closes"]


def test_record_shows_a_reporter_only_their_own_items_while_answers_are_open(world, monkeypatch):
    plane, iid, box = world
    start(plane, iid, box)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return T(6)
    monkeypatch.setattr(C, "datetime", Clock)
    box["who"] = V["Aaron Lyle"]
    out = C.get_intents_by_intent_id_pulse_record(iid, None, "2026-W41")  # N3, spec 39: a reporter reads only their own items while answers are open
    assert not hasattr(out, "status_code") or out.status_code == 200
    body = out if isinstance(out, dict) else json.loads(out.body)
    assert all((it.get("by") in (None, V["Aaron Lyle"].account_id)) or it.get("mine") for it in body.get("items", []))
    box["who"] = V["Janet Shaw"]  # the reviewer reads it while it fills
    assert C.get_intents_by_intent_id_pulse_record(iid, None, "2026-W41")["week"]["state"] == "collect"
