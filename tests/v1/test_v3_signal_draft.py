"""Harbor drafts a signal from a repeated human action (sh_platform/v1/v3_signal_draft.py, docs/v3/SIGNAL-ENGINE.md).
Real: the watcher, the drafting, the backtest, the admit and reject, the routes. Stubbed: the facts (figures and rules) the loaders would supply."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sh_platform.v1 import v3_roles as R, v3_signal_draft as SD, v3_signals as SG
from tests.v1.test_v3_signals import FACTS, FUND, NOTICE, env, field, login  # noqa: F401

GRACE, SAM = "grace@evergreen.example.test", "sam@evergreen.example.test"


def days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(autouse=True)
def facts(monkeypatch):
    monkeypatch.setattr(SG, "PROVIDER", lambda plane, kind, ref, ev: None)  # the figures come from FACTS, not a warehouse


def arrive(plane, fund, account, call_no, ago):
    doc = {**NOTICE, "fund": field(fund), "call_no": field(call_no), "bank_account": field(account)}
    SD.arrival(plane, "capital_call_notice", f"{fund}_{call_no}.pdf", doc)
    p = SD._dir(plane) / "arrivals.jsonl"  # the arrival is kept as of now; move it back so the six months window means something
    rows = SD._lines(p)
    rows[-1]["at"] = days_ago(ago)
    p.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")


def check(plane, fund, who=GRACE):
    return SD.observe(plane, "check", who, "bank_details", fund, text=f"checked bank details for {fund}", file_kind="capital_call_notice")


def test_two_repeats_make_a_draft_and_one_does_not(env):
    _, plane = env
    assert check(plane, FUND) == []  # once is not a pattern
    assert SD.listing(plane) == []
    got = check(plane, "Northgate Growth II")  # a different subject, the same kind of check
    assert len(got) == 1
    d = got[0]
    assert d["status"] == "waiting" and d["signal"]["route_to"] == "ops_lead" and d["needs"] == []
    s = d["signal"]
    assert s["trigger"] == {"on": "file_arrived", "kind": "capital_call_notice"} and s["action"]["verb"] == "call_back"
    assert s["condition"] == "last4(doc.bank_account) != last4(si.account)" and SG.check(s, SG._roles(plane)) is None
    assert d["noticed"].startswith("Harbor noticed Grace checks bank details before every payment")
    assert check(plane, "A Third Fund") == []  # no second draft for the same pattern


def test_the_notes_and_dismissals_a_person_writes_are_watched(env):
    _, plane = env
    for subject in ["Fund A call 1", "Fund B call 2"]:
        SG._watch(plane, {"signal": "x", "subject": subject, "title": "t", "person": {"email": GRACE}, "note": f"Checked bank details for {subject}",
                          "event": {"kind": "capital_call_notice"}}, "Grace Ong", False)
    assert [d["kind"] for d in SD.listing(plane)] == ["bank_details"]
    for s in ("a", "b"):
        SG._watch(plane, {"signal": "uc01-call-arrives", "subject": s, "title": "t", "person": {"email": SAM}}, "Sam Lee", True)
    assert {d["kind"] for d in SD.listing(plane)} == {"bank_details", "dismissed_uc01_call_arrives"}


def test_the_backtest_counts_what_would_have_fired(env, monkeypatch):
    _, plane = env
    d = check(plane, FUND) + check(plane, "Northgate Growth II")
    arrive(plane, FUND, "Harbour Bank 4471", "7", 10)   # differs from 2209 on file: fires
    arrive(plane, FUND, "Harbour Bank 2209", "6", 40)   # the same account: does not
    arrive(plane, FUND, "Harbour Bank 4471", "5", 90)   # fires
    arrive(plane, FUND, "Harbour Bank 4471", "1", 400)  # older than six months: not looked at
    monkeypatch.setattr(SG, "PROVIDER", lambda plane, kind, ref, ev: FACTS["figures"].get(ref) if kind == "figure" else None)
    bt = SD.backtest(plane, d[0])
    assert (bt["count"], bt["checked"]) == (2, 3)
    assert bt["examples"] == [f"{FUND} call 7", f"{FUND} call 5"]
    assert bt["line"].startswith("Would have fired 2 times in 6 months: ")


def test_a_threshold_is_never_invented(env):
    _, plane = env
    for q in ("Is cash low in Evergreen Holdings?", "Is cash low in Evergreen Trust?"):
        got = SD.observe(plane, "question", SAM, "cash_by_entity", q, figure="cash_by_entity", text=q)
    d = got[0]
    assert d["signal"]["trigger"] == {"on": "figure_changed", "figure": "cash_by_entity"}
    assert "no limit is signed" in d["needs"][0] and "cash_by_entity_limit" in d["needs"][0]
    assert "cannot" in d["backtest"]["line"]
    with pytest.raises(ValueError, match="limit signed"):
        SD.admit(plane, d["id"], "Daniel Foo")


def test_admit_adds_the_signal_to_the_library_and_it_fires(env):
    _, plane = env
    d = (check(plane, FUND) + check(plane, "Northgate Growth II"))[0]
    assert d["signal"]["id"] not in {s["id"] for s in SG.library(plane)}
    card = SD.cards(plane)[0]
    assert card["text"].endswith("Watch for it automatically?") and [a["answer"] for a in card["actions"]] == ["admit", "edit", "reject"]
    SD.edit(plane, d["id"], {"message": "Check the bank details on this notice before anything is paid."})
    assert SD.admit(plane, d["id"], "Daniel Foo")["status"] == "admitted" and SD.cards(plane) == []
    mine = {s["id"]: s for s in SG.library(plane)}[d["signal"]["id"]]
    assert mine["source"] == "office" and mine["suggestion"] is False and mine["error"] is None and mine["route_to"] == "ops_lead"
    got = SG.evaluate(plane, {"trigger": "file_arrived", "kind": "capital_call_notice", "file": "n.pdf", "doc": NOTICE, "facts": FACTS})  # 4471 against 2209 on file
    assert d["signal"]["id"] in [r["signal"] for r in got["fired"]]
    assert next(r for r in SG.fired(plane) if r["signal"] == d["signal"]["id"])["person"]["email"] == GRACE
    with pytest.raises(ValueError, match="already decided"):
        SD.reject(plane, d["id"], "x")


def test_reject_is_remembered_and_not_drafted_again(env):
    _, plane = env
    d = (check(plane, FUND) + check(plane, "Northgate Growth II"))[0]
    SD.reject(plane, d["id"], "Daniel Foo", "Grace does this only for new funds.")
    assert SD.cards(plane) == [] and SD.listing(plane, "rejected")[0]["reason"].startswith("Grace does this")
    check(plane, "Another Fund")
    check(plane, "Yet Another Fund")
    assert [x["status"] for x in SD.listing(plane)] == ["rejected"]  # still the one, still rejected
    assert d["signal"]["id"] not in {s["id"] for s in SG.library(plane)}


def test_the_routes(env):
    app, plane = env
    check(plane, FUND)
    check(plane, "Northgate Growth II")
    grace = login(app, GRACE)
    got = grace.get("/api/v3/signals/drafts").json()
    assert len(got) == 1 and got[0]["backtest"]["line"] and got[0]["status"] == "waiting"
    did = got[0]["id"]
    assert grace.post(f"/api/v3/signals/drafts/{did}/admit", json={}).status_code == 403  # the ops lead is not the decision maker
    R.set_job(plane, GRACE, "principal")
    assert grace.post("/api/v3/signals/drafts/nope/reject", json={}).status_code == 404
    r = grace.post(f"/api/v3/signals/drafts/{did}/edit", json={"route_to": "no_such_role"})
    assert r.status_code == 409 and "does not work" in r.json()["detail"]
    ok = grace.post(f"/api/v3/signals/drafts/{did}/reject", json={"reason": "no"})
    assert ok.status_code == 200 and ok.json()["status"] == "rejected"
