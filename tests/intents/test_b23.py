"""B23: weekly check-in review (spec 40): digest, repeats, fates, close, trends, Pulse line, anonymous scrub."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sh_platform.egress import rows

from sh_platform.intents import checkin_review as r


def it(i, kind, text, ref=None, by="u1", **kw):
    return {"id": i, "by": by, "kind": kind, "text": text, "ref": ref, "severity": kw.pop("severity", None), "count": None, "amount": None,
            "topic": kw.pop("topic", None), "fate": None, "fate_reason": None, "decided_by": None, **kw}


def week(key, items, state="ready", **kw):
    return {"week_key": key, "state": state, "participants_count": 6, "responded_count": 5, "items": items, "read_only": False, **kw}


def test_digest_groups_repeats_and_ranks_broke():
    old = week("2026-09-21", [it("a", "broke", "Custody file late", "custody")], state="closed")
    items = [it("1", "broke", "Custody file late", "custody"), it("2", "broke", "Custody file late", "custody", by="u2"),
             it("3", "broke", "Report typo", "custody"), it("4", "broke", "No link"), it("5", "ran", "Month end on time", "close"),
             it("6", "thought", "Vendor review", topic="Vendors")]
    d = r.build_digest(week("2026-09-28", items), [old])
    g = {(x["kind"], x.get("ref") or x.get("topic")): x for x in d["groups"]}
    assert g[("broke", "custody")]["item_ids"] == ["1", "2", "3"]  # two people first
    assert ("broke", None) in g and ("thought", "Vendors") in g and ("ran", "close") in g
    assert [x["seen_weeks"] for x in items[:3]] == [2, 2, 1]
    assert d["repeats"][0]["seen_in"] == ["2026-09-21"] and set(g[("broke", "custody")]["source_item_ids"]) == {"1", "2"}
    assert items[0]["people_count"] == 2


def test_split_drops_repeat_count_and_survives_redraft():
    old = week("2026-09-21", [it("a", "broke", "x late", "p")], state="closed")
    w = week("2026-09-28", [it("1", "broke", "x late", "p")])
    w["digest"] = r.build_digest(w, [old])
    r.split_repeat(w, "1")
    assert w["items"][0]["seen_weeks"] == 1 and w["digest"]["repeats"][0]["split"]
    assert r.build_digest(w, [old])["repeats"][0]["split"] is True and w["items"][0]["seen_weeks"] == 1


def test_every_broke_item_needs_a_fate_and_reason():
    w = week("2026-09-28", [it("1", "broke", "a", "p"), it("2", "ran", "b"), it("3", "thought", "c", topic="t")])
    with pytest.raises(ValueError, match="1 broke item still needs a decision"):
        r.close_week(w, "s", "jan")
    with pytest.raises(ValueError, match="Please say why"):
        r.decide(w, "1", "nothing", " ", None, "jan")
    with pytest.raises(ValueError, match="Create the Problem"):
        r.decide(w, "1", "problem", "third week", None, "jan")
    with pytest.raises(ValueError, match="link"):
        r.decide(w, "1", "handled", "covered", None, "jan")
    r.decide(w, "1", "problem", "third week", "prob_1", "jan")
    assert w["state"] == "reviewing"
    r.decide(w, "1", "nothing", "changed my mind", None, "jan")
    assert w["items"][0]["history"][0]["fate"] == "problem"


def test_undecided_close_as_nothing_with_reason_and_week_is_read_only():
    w = week("2026-09-28", [it("1", "broke", "a", "p"), it("2", "ran", "b"), it("3", "thought", "c", topic="t")])
    r.decide(w, "1", "backlog", "later", "bk_1", "jan")
    r.close_week(w, "done", "jan")
    assert [(i["fate"], i["fate_reason"]) for i in w["items"][1:]] == [("nothing", r.NOT_REVIEWED)] * 2
    assert w["state"] == "closed" and w["read_only"]
    with pytest.raises(ValueError, match="closed"):
        r.decide(w, "2", "nothing", "x", None, "jan")
    assert r.outcome_row(w)["fates"] == {"problem": 0, "backlog": 1, "handled": 0, "nothing": 2}


def test_session_clock_and_extension():
    w = week("2026-09-28", [it("1", "ran", "b")])
    t0 = r.now().replace(microsecond=0)
    r.session_act(w, "start", "jan", t0)
    assert r.clock(w, t0)["remaining_seconds"] == 1800
    with pytest.raises(ValueError, match="not up yet"):  # F30: Extend only once the time is up
        r.session_act(w, "extend", "jan", t0)
    late = t0 + timedelta(minutes=31)
    r.session_act(w, "extend", "jan", late)
    assert r.clock(w, late)["remaining_seconds"] == 9 * 60
    r.session_act(w, "end", "jan", t0)
    assert w["session"]["minutes_used"] == 0 and w["state"] == "reviewing" and r.clock(w) is None


def test_trends_not_available_below_four_closed_weeks_then_counts():
    ws = [week(f"2026-09-{d}", [it("1", "broke", "late", "custody")], state="closed") for d in (7, 14, 21)]
    t = r.trends(ws)
    assert t["available"] is False and t["reason"] == "Not available yet: trends need four closed weeks. This series has 3."
    ws.append(week("2026-09-28", [it("1", "broke", "late", "custody"), it("2", "broke", "other", "recon")], state="closed"))
    ws.append(week("2026-10-05", [it("1", "broke", "late", "custody")], state="ready"))  # open weeks are not counted
    t = r.trends(ws)
    assert t["available"] and t["closed_weeks"] == 4 and {x["process"]: x["total"] for x in t["rows"]} == {"custody": 4, "recon": 1}
    assert t["repeated"][0]["seen_weeks"] == 4 and "4 of the last 4 weeks" in t["reading"]


def test_reporter_sees_a_line_on_pulse_and_reviewer_gets_read_the_week():
    intent = {"id": "i1"}
    w = week("2026-09-28", [it("1", "ran", "ok", by="aaron")])
    assert [x["title"] for x in r.pulse_lines(intent, w, "janet", "janet")] == ["Read the week"]
    assert r.pulse_lines(intent, w, "aaron", "janet") == []
    r.close_week(w, "s", "janet")
    line = r.pulse_lines(intent, w, "aaron", "janet")[0]
    assert line["title"] == "Your items from the week of 28 Sep have a decision" and line["href"].endswith("view=mine")


def test_anonymous_author_never_leaves_the_server():
    w = week("2026-09-28", [it("1", "broke", "a", "p", by="anonymous"), it("2", "ran", "b", by="u1")])
    req = SimpleNamespace(state=SimpleNamespace(company_id="c"),
                          app=SimpleNamespace(state=SimpleNamespace(account_store=SimpleNamespace(in_company=lambda c: [{"id": "u1", "display_name": "Aaron Lyle"}]))))
    out = r._shape(w, req, {"can_decide": True})
    assert "by" not in out["items"][0] and out["items"][0]["by_name"] is None and out["items"][1]["by_name"] == "Aaron Lyle"
    assert "u1" not in str(out)


def test_digest_worded_through_the_runtime_falls_back_labelled_and_the_reviewers_words_stand(monkeypatch):
    """F10, R14: North words the digest lines and the summary through the runtime; an untraced number is dropped; a failed call keeps the
    counted lines with `fallback` so the screen says so; no author or account id is sent."""
    import json as _json
    from sh_platform.intents import north as N
    sent = []

    def fake_call(plane_, model, gate, system, context, question):
        sent.append(_json.dumps(context))
        assert rows.json_findings(_json.dumps({"context": context, "question": question}))[0] is None  # the gateway would send it
        return _json.dumps({"lines": [{"key": 0, "text": "2 people said the custody file was late, 9 times."}, {"key": 7, "text": "x"}],
                            "summary": "5 of 6 answered and 3 items came in."})
    monkeypatch.setattr(N, "_call", fake_call)
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(entitlements=object(), north_model_factory=lambda p: object())))
    w = week("2026-09-28", [it("1", "broke", "Custody file late", "custody", by="acct-u1"), it("2", "broke", "Custody file late", "custody", by="anonymous"),
                            it("3", "ran", "Month end on time", "close", by="acct-u2")])
    d = r.model_words(req, None, w, r.build_digest(w, []))
    assert d["fallback"] is False and d["groups"][0]["line"] == "2 people said the custody file was late, times."
    assert d["summary_line"] == "5 of 6 answered and 3 items came in."
    assert sent and not any(x in sent[0] for x in ("acct-", "anonymous"))
    monkeypatch.setattr(N, "_call", lambda *a: None)  # the model cannot answer: the counted lines stand, labelled
    d2 = r.model_words(req, None, w, r.build_digest(w, []))
    assert d2["fallback"] is True and d2["groups"][0]["line"].startswith('2 people said "Custody file late"')
    assert r.model_words(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())), None, w, r.build_digest(w, []))["fallback"] is True
    w["digest"] = d
    for i in ("1", "2"):
        r.decide(w, i, "nothing", "Already fixed", None, "janet")
    assert r.close_week(w, "Our own line.", "janet", edited=True)["summary"] == "Our own line."  # rule 7: the reviewer's summary is kept


def test_fate_ref_must_exist_and_severity_is_counted_and_labelled():
    """F30 (1), (2): a typed id that does not exist is refused; the week shows counts per severity, never an estimate."""
    w = week("2026-09-28", [it("1", "broke", "a", "p", severity="stopped", count=2, unit="times", amount={"value": 500, "currency": "SGD"}),
                            it("2", "broke", "b", "p", severity="slowed"), it("3", "broke", "c", "p"), it("4", "ran", "d")])
    known = {("problem", "pro-1"), ("backlog", "bl-1"), ("handled", "/centre/intent/x")}
    ok = lambda fate, ref: (fate, ref) in known  # noqa: E731
    with pytest.raises(ValueError, match="could not find"):
        r.decide(w, "1", "problem", "third week", "pro-made-up", "jan", ok)
    r.decide(w, "1", "problem", "third week", "pro-1", "jan", ok)
    r.decide(w, "2", "handled", "covered", "/centre/intent/x", "jan", ok)
    s = r.severity_summary(w["items"])
    assert s["items"] == {"stopped": 1, "slowed": 1, "cost": 0, "not_marked": 1} and s["times"] == 2 and s["amounts"] == [{"currency": "SGD", "value": 500}]
