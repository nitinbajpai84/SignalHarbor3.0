"""Signals (sh_platform/v1/v3_signals.py, docs/v3/SIGNAL-ENGINE.md) on UC01, the capital call (docs/v3/use-cases/UC01-CAPITAL-CALL.md).
Real: the pack's five signal files, the engine, the store, the routes, the permissions. Stubbed: the facts (figures and signed rules) the loaders would supply."""
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.packs import PackLoader  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H, v3_model as M, v3_roles as R, v3_signals as SG  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

PW = "test-password-not-real"
FUND, HOLD = "Cedarpoint Ventures III", "Evergreen Holdings"
IDS = ["uc01-bank-changed", "uc01-call-arrives", "uc01-call-fits", "uc01-cash-shortfall", "uc01-paid-matched"]


def field(v, page=1, quote=None):
    return {"value": v, "page": page, "quote": quote or str(v)}


NOTICE = {"fund": field(FUND), "investor": field(HOLD), "amount": field(D("1250000"), 1, "Amount due: USD 1,250,000.00"), "currency": field("USD"),
          "due_date": field("2026-10-23"), "call_no": field("7"), "bank_account": field("Harbour Bank 4471", 2, "Account no. ending 4471")}
FACTS = {"figures": {
    "commitments": {"value": [{"fund": FUND, "investor": HOLD, "commitment": 10000000, "called": 6000000}], "receipt": {"v": 3, "status": "verified"}},
    "cash_by_entity": {"value": [{"entity": HOLD, "currency": "USD", "cash": 1230000}, {"entity": HOLD, "currency": "SGD", "cash": 1600000}], "receipt": {"v": 5, "status": "verified"}},
    "fx_rates": {"value": [{"pair": "USD/SGD", "rate": D("1.3400")}], "receipt": {"v": 1, "status": "verified"}},
    "standing_instructions": {"value": [{"fund": FUND, "account": "2209", "since": "July"}], "receipt": {"v": 2, "status": "verified"}},
    "capital_calls": {"value": [{"fund": FUND, "call_no": "7", "amount": 1250000, "due_date": "2026-10-23", "status": "Approved"}]}},
    "rules": {"cash_buffer": {"value": {"amount": 250000, "currency": "USD"}, "receipt": {"signed_by": "Daniel Foo"}},
              "changed_bank_details": {"value": {"text": "call back on a known number before paying."}, "receipt": {"signed_by": "Daniel Foo"}}}}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(M, "pack_of", lambda plane: PackLoader(M._packs_root()).load("family_office"))
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    st = AccountStore(data)
    st.create("grace@evergreen.example.test", PW, "Grace Ong", "evergreen", ["participant"])
    st.create("sam@evergreen.example.test", PW, "Sam Lee", "evergreen", ["participant"])
    plane = PlaneStore(str(data)).plane_for("evergreen").ensure()
    R.set_job(plane, "grace@evergreen.example.test", "ops_lead")
    R.set_job(plane, "sam@evergreen.example.test", "ops_clerk")
    return create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")), plane


def login(app, email) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


def arrive(plane, doc=None):
    return SG.evaluate(plane, {"trigger": "file_arrived", "kind": "capital_call_notice", "file": "cedarpoint_call_7.pdf", "doc": doc or NOTICE, "facts": FACTS})


def card(plane, sid):
    return next(r for r in SG.fired(plane) if r["signal"] == sid)


def test_expression_language_is_safe():
    ns = {"a": D("2"), "doc": {"x": D("3")}}
    assert SG.calc("a * doc.x + 1 > 6 and not (a == 3)", ns, {}) is True
    assert SG.calc("last4('ac 2209') != last4('4471')", ns, {"last4": SG.last4}) is True
    for bad in ("__import__('os').system('x')", "a.__class__", "[x for x in a]", "(lambda: 1)()", "a[0]", "open('f')"):
        with pytest.raises((ValueError, SG.Missing)):
            SG.calc(bad, ns, {})
    with pytest.raises(SG.Missing):
        SG.calc("nothing > 1", ns, {})


def test_the_library_is_five_valid_suggestions(env):
    _, plane = env
    lib = {s["id"]: s for s in SG.library(plane)}
    assert sorted(lib) == IDS
    assert all(s["error"] is None and s["suggestion"] and s["source"] == "pack" for s in lib.values()), {k: s["error"] for k, s in lib.items()}
    assert lib["uc01-bank-changed"]["severity"] == "problem" and lib["uc01-bank-changed"]["hold"]["blocks"] == "prepare_payment"


def test_uc01_the_five_signals_and_their_numbers(env):
    _, plane = env
    got = arrive(plane)
    assert sorted(r["signal"] for r in got["fired"]) == ["uc01-bank-changed", "uc01-call-arrives"]
    # 1. the call arrives: Sam logs it
    c1 = card(plane, "uc01-call-arrives")
    assert c1["route_to"] == "ops_clerk" and c1["person"]["email"] == "sam@evergreen.example.test"
    assert "USD 1,250,000" in c1["message"] and "2026-10-23" in c1["message"]
    assert any(e["kind"] == "document" and e["field"] == "amount" and e["page"] == 1 and "1,250,000" in e["quote"] for e in c1["evidence"])
    # 4. the bank account changed 2209 -> 4471: held, for Grace
    c4 = card(plane, "uc01-bank-changed")
    assert c4["severity"] == "problem" and c4["person"]["email"] == "grace@evergreen.example.test"
    assert "2209" in c4["message"] and "4471" in c4["message"] and "call back" in c4["message"]
    assert {e.get("id") for e in c4["evidence"]} >= {"standing_instructions", "changed_bank_details"}
    assert [h["id"] for h in SG.held(plane, "prepare_payment", FUND)] == [c4["id"]] and SG.held(plane, "prepare_payment", "Other Fund") == []
    # 2. Sam logs it: it fits the commitment, 2,750,000 unfunded
    assert SG.act(plane, c1["id"], "Sam Lee", "Log it")["next"]
    c2 = card(plane, "uc01-call-fits")
    assert D(c2["values"]["unfunded"]) == 2750000 and "2,750,000" in c2["message"] and c2["route_to"] == "fund_accountant"
    assert any(e.get("id") == "commitments" and e.get("v") == 3 for e in c2["evidence"])
    # 3. Helen records it: short 270,000, convert SGD 361,800
    assert SG.act(plane, c2["id"], "Helen Foo", "Record it")["next"]
    c3 = card(plane, "uc01-cash-shortfall")
    assert D(c3["values"]["short"]) == 270000 and D(c3["values"]["convert"]) == 361800
    assert "270,000" in c3["message"] and "SGD 361,800" in c3["message"] and c3["route_to"] == "cfo"
    assert c3["action"]["options"] == ["Approve", "Change", "Fund from another entity"]
    # 4 (cont). no call-back note, no release; with it the hold lifts
    with pytest.raises(ValueError):
        SG.act(plane, c4["id"], "Grace Ong", "Record the call-back")
    SG.act(plane, c4["id"], "Grace Ong", "Record the call-back", "Confirmed by call-back, 13 Oct, 15:40, spoke to fund operations")
    assert SG.held(plane, "prepare_payment", FUND) == []
    # 5. the Monday statement line matches the approved call
    st = SG.evaluate(plane, {"trigger": "file_arrived", "kind": "bank_statement", "doc": {"amount": field(1250000), "value_date": field("2026-10-23")}, "facts": FACTS})
    assert [r["signal"] for r in st["fired"]] == ["uc01-paid-matched"] and "call 7 paid" in st["fired"][0]["message"]


def test_fires_once_and_misses_are_recorded(env):
    _, plane = env
    assert len(arrive(plane)["fired"]) == 2
    assert arrive(plane)["fired"] == []  # the same signal for the same subject fires once
    assert len(SG.fired(plane)) == 2
    c = card(plane, "uc01-call-arrives")
    SG.act(plane, c["id"], "Sam Lee", dismiss=True)  # a miss
    assert arrive(plane)["fired"] == []  # a dismissed card does not come back
    s = SG.stats(plane)
    assert s["uc01-call-arrives"] == {"fired": 1, "acted": 0, "dismissed": 1, "open": 0, "hit_rate": 0.0, "last_fired": c["at"]}
    assert s["uc01-bank-changed"]["open"] == 1 and s["uc01-bank-changed"]["hit_rate"] is None
    with pytest.raises(ValueError):
        SG.act(plane, c["id"], "Sam Lee")


def test_no_alarm_when_nothing_is_wrong_and_missing_input_is_skipped(env):
    _, plane = env
    same = {**NOTICE, "bank_account": field("Harbour Bank 2209")}
    assert [r["signal"] for r in arrive(plane, same)["fired"]] == ["uc01-call-arrives"]
    assert SG.held(plane, "prepare_payment") == []
    # a call bigger than what is unfunded does not fit: no card, nothing guessed
    big = {**NOTICE, "amount": field(D("5000000")), "call_no": field("8")}
    assert SG.evaluate(plane, {"trigger": "action_done", "signal": "uc01-call-arrives", "doc": big, "facts": FACTS})["fired"] == []
    # the fund's commitment missing: skipped with the reason
    none = SG.evaluate(plane, {"trigger": "action_done", "signal": "uc01-call-arrives", "doc": {**NOTICE, "call_no": field("9")}, "facts": {}})
    assert none["skipped"] and "commitments" in none["skipped"][0]["why"]


def test_the_same_fund_under_another_spelling_matches(env):
    _, plane = env
    got = arrive(plane, {**NOTICE, "fund": field("Cedarpoint Ventures III, L.P.")})
    assert "uc01-bank-changed" in [r["signal"] for r in got["fired"]]  # the standing instructions were found by fund name, not exact text


def test_office_override_and_disable(env):
    _, plane = env
    d = SG._dir(plane) / "office"
    d.mkdir()
    (d / "uc01-call-arrives.yaml").write_text("id: uc01-call-arrives\ndisabled: true\n", encoding="utf-8")
    (d / "mine.yaml").write_text("id: mine\ntitle: Mine\ntrigger: {on: nope}\ncondition: 1 > 0\nseverity: info\nroute_to: nobody\naction: {verb: see}\nmessage: x\n", encoding="utf-8")
    lib = {s["id"]: s for s in SG.library(plane)}
    assert lib["uc01-call-arrives"]["disabled"] and lib["mine"]["error"] and lib["mine"]["source"] == "office"
    assert [r["signal"] for r in arrive(plane)["fired"]] == ["uc01-bank-changed"]


def test_routes_desk_and_permissions(env):
    app, plane = env
    arrive(plane)
    sam, grace = login(app, "sam@evergreen.example.test"), login(app, "grace@evergreen.example.test")
    lib = sam.get("/api/v3/signals").json()
    assert [s["id"] for s in lib] == IDS and next(s for s in lib if s["id"] == "uc01-bank-changed")["stats"]["open"] == 1
    open_ = sam.get("/api/v3/signals/fired?status=open").json()
    assert len(open_) == 2 and all(r["evidence"] for r in open_)
    assert any(n["kind"] == "signal" and n["severity"] == "problem" for n in H.desk(plane)["needs"])
    c4 = card(plane, "uc01-bank-changed")
    assert sam.post(f"/api/v3/signals/{c4['id']}/act", json={"note": "x"}).status_code == 403  # Sam is not the ops lead
    assert grace.post(f"/api/v3/signals/{c4['id']}/act", json={}).status_code == 409  # a call-back needs its note
    r = grace.post(f"/api/v3/signals/{c4['id']}/act", json={"choice": "Record the call-back", "note": "Confirmed by call-back, 15:40"})
    assert r.status_code == 200 and r.json()["status"] == "acted" and r.json()["by"] == "Grace Ong"
    c1 = card(plane, "uc01-call-arrives")
    assert sam.post(f"/api/v3/signals/{c1['id']}/act", json={"choice": "Log it"}).status_code == 200
    assert [r["signal"] for r in sam.get("/api/v3/signals/fired?status=open").json()] == ["uc01-call-fits"]  # acting on a card starts the next
    assert sam.post("/api/v3/signals/sg-nope/act", json={}).status_code == 404
