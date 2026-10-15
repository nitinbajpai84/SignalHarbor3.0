"""E5a: the Fund A revision gives the CIO and Operations a card each ("Revised · estimated"); cap of seven with approvals never cut;
cards are the person's own; acknowledge and dismiss (reason needed) record the outcome; access filter; no duplicate on re-run."""
import sys
import types
from datetime import date, datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e5_pulse as P
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

TODAY = date(2026, 10, 9)
NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
CIO = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-priya")
OPS = Viewer("Mei Tan", frozenset({"analyst"}), False, "acc-mei")
IDS = {k: wh.new_id() for k in ("cio", "ops", "risk", "fund", "port", "exc", "val")}
RISK = Viewer("Rita Risk", frozenset({"analyst"}), False, "acc-rita")


def ins(con, table, **row):
    con.execute(f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    monkeypatch.setattr(wh, "now", lambda plane=None: NOW)  # cards are stamped with wh.now(); keep it on TODAY, not the real date
    pl = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(pl)
    ids = IDS
    with wh.connect(pl) as con:
        for k, name, role in (("cio", "Priya Nair", "CIO"), ("ops", "Mei Tan", "Operations analyst"), ("risk", "Rita Risk", "Risk")):
            ins(con, "users", id=ids[k], organization_id=org, external_identity_id="acc-" + name.split()[0].lower(), display_name=name,
                email=k + "@x.test", business_role=role, is_active=True, created_at=NOW)
    # E1d stub: everyone sees the demo portfolio
    mod = types.ModuleType("sh_platform.v1.e1_access")
    mod.visible_portfolios = lambda plane, viewer: {ids["port"]} if viewer.name != "Rita Risk" else set()
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e1_access", mod)
    import sh_platform.v1 as pkg
    monkeypatch.setattr(pkg, "e1_access", mod, raising=False)
    return pl


def seed_fund_a(pl):
    """Fund A, a revised manager estimate, and a material revision case on it."""
    i, org = IDS, org_id(pl)
    with wh.connect(pl) as con:
        ins(con, "instruments", id=i["fund"], organization_id=org, canonical_name="Evergreen Growth I", instrument_type="fund", created_at=NOW)
        ins(con, "valuation_observations", id=i["val"], organization_id=org, instrument_id=i["fund"], valuation_date=date(2026, 9, 30),
            received_at=datetime(2026, 10, 2, tzinfo=timezone.utc), recorded_at=NOW, value_amount=10180000, currency="USD",
            valuation_type="manager_estimate", approval_status="unverified")
        ins(con, "exceptions", id=i["exc"], organization_id=org, instrument_id=i["fund"], exception_type="revision",
            title="Evergreen Growth I statement was revised", detected_at=NOW, candidate_impact_amount=180000, impact_currency="USD",
            materiality_status="material", status="new")


def test_fund_a_revision_gives_cio_and_ops_a_card(plane):
    seed_fund_a(plane)
    assert P.generate(plane, TODAY) == 2
    cio, ops = P.items(plane, CIO, TODAY), P.items(plane, OPS, TODAY)
    assert len(cio) == len(ops) == 1
    c = cio[0]
    assert c["status_word"] == "Revised · estimated" and c["effect"] == "USD 180,000" and c["as_of"] == "2026-09-30"
    assert c["received"].startswith("2026-10-02") and c["action"] == "Open case" and c["urgency"] == "needs_me" and c["link"] == f"/centre/desk/{IDS['exc']}"
    assert ops[0]["status_word"] == "Revised · estimated"
    assert P.items(plane, RISK, TODAY) == []
    assert P.generate(plane, TODAY) == 0  # run again: no duplicates


def test_status_word_follows_the_valuation(plane):
    seed_fund_a(plane)
    for appr, vtype, word in (("proposed", "manager_final", "Revised · unverified"), ("pending", "manager_final", "Revised · unverified"), ("confirmed", "manager_final", "Revised · manager final"),
                              ("confirmed", "manager_estimate", "Revised · estimated")):
        with wh.connect(plane) as con:
            con.execute("update valuation_observations set approval_status = ?, valuation_type = ?", [appr, vtype])
        P.generate(plane, TODAY)
        assert {c["status_word"] for c in P.items(plane, CIO, TODAY)} == {word}


def test_pending_revision_is_indicative_for_cio_even_when_materiality_unknown(plane):
    seed_fund_a(plane)
    with wh.connect(plane) as con:
        con.execute("update valuation_observations set approval_status = 'pending', valuation_type = 'manager_final'")
        con.execute("update exceptions set materiality_status = 'unknown'")
    P.generate(plane, TODAY)
    c = P.items(plane, CIO, TODAY)[0]
    assert c["status_word"] == "Revised · unverified" and c["urgency"] == "worth_a_look" and "Indicative, unverified" in c["text"] and "P&L" not in c["text"]
    assert P.items(plane, OPS, TODAY)[0]["urgency"] == "needs_me"  # Operations has the verification task


def test_items_make_cards_themselves_and_throttle(plane):
    seed_fund_a(plane)
    assert len(P.items(plane, CIO, TODAY)) == 1  # no generate() call by anyone
    with wh.connect(plane) as con:
        ins(con, "exceptions", id=wh.new_id(), organization_id=org_id(plane), exception_type="missing_document", title="Late",
            detected_at=NOW, materiality_status="material", status="new")
    assert len(P.items(plane, OPS, TODAY)) == 1  # inside five minutes: not regenerated
    P._LAST[str(plane.root)] -= 301
    assert len(P.items(plane, OPS, TODAY)) == 2


def test_role_filter_and_roles(plane):
    seed_fund_a(plane)
    v = P.view(plane, CIO, TODAY)
    assert v["role"] == "cio" and v["roles"] == ["cio"] and len(v["items"]) == 1
    assert P.view(plane, CIO, TODAY, "cio")["items"] == v["items"]
    with pytest.raises(P.Refused):
        P.view(plane, CIO, TODAY, "operations")


def test_statement_due_rule_key(plane, monkeypatch):
    mod = types.ModuleType("sh_platform.v1.e3_rules")
    mod.current = lambda pl, code, d: {"parameters": {"business_days_after_month_end": 10}}
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_rules", mod)
    import sh_platform.v1 as pkg
    monkeypatch.setattr(pkg, "e3_rules", mod, raising=False)
    with wh.connect(plane) as con:
        ins(con, "instruments", id=IDS["fund"], organization_id=org_id(plane), canonical_name="Evergreen Growth I", instrument_type="fund", created_at=NOW)
    P.generate(plane, date(2026, 10, 20))  # due 14 Oct; no September statement
    assert any("Statement missing" in c["headline"] and c["link"] is None for c in P.items(plane, OPS, date(2026, 10, 20)))


def test_cap_of_seven_and_approvals_never_cut(plane):
    org = org_id(plane)
    with wh.connect(plane) as con:
        for n in range(10):
            ins(con, "exceptions", id=wh.new_id(), organization_id=org, exception_type="missing_document", title=f"Missing {n}",
                detected_at=NOW, materiality_status="unknown", status="new")
        for n in range(2):
            ins(con, "approvals", id=wh.new_id(), organization_id=org, approval_type="report_issue", requested_from_user_id=IDS["ops"],
                status="requested", requested_at=NOW)
    P.generate(plane, TODAY)
    cards = P.items(plane, OPS, TODAY)
    assert sum(c["action_type"] != "approve" for c in cards) == 7 and sum(c["action_type"] == "approve" for c in cards) == 2
    assert cards[0]["action_type"] == "approve"  # approvals first
    P.dismiss(plane, OPS, cards[1]["id"], "done")  # a dismissed card frees its place; the next one comes in
    P.generate(plane, TODAY)
    assert sum(c["action_type"] != "approve" for c in P.items(plane, OPS, TODAY)) == 7


def test_acknowledge_dismiss_and_ownership(plane):
    seed_fund_a(plane)
    P.generate(plane, TODAY)
    mine, theirs = P.items(plane, CIO, TODAY)[0]["id"], P.items(plane, OPS, TODAY)[0]["id"]
    with pytest.raises(P.Refused):
        P.acknowledge(plane, CIO, theirs)
    with pytest.raises(P.Refused):
        P.dismiss(plane, OPS, theirs, "  ")
    assert P.acknowledge(plane, CIO, mine)["outcome"] == "acted"
    assert P.items(plane, CIO, TODAY)[0]["delivery_status"] == "acknowledged"
    P.dismiss(plane, OPS, theirs, "Already handled by phone")
    assert P.items(plane, OPS, TODAY) == []
    assert P.generate(plane, TODAY) == 0  # a dismissed card does not come back
    with wh.connect(plane) as con:
        assert con.execute("select outcome from pulse_items where id = ?", [theirs]).fetchone()[0] == "dismissed_with_reason"


def test_access_filter_hides_portfolio_cases(plane):
    seed_fund_a(plane)
    with wh.connect(plane) as con:
        con.execute("update exceptions set portfolio_id = ?, exception_type = 'limit_breach' where id = ?", [IDS["port"], IDS["exc"]])
    P.generate(plane, TODAY)
    assert len(P.items(plane, CIO, TODAY)) == 1  # CIO sees the portfolio
    assert P.items(plane, RISK, TODAY) == []  # Risk is not allowed the portfolio: nothing leaks


def test_routes_work(plane, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e5a_routes as R
    seed_fund_a(plane)
    P.generate(plane, TODAY)
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "viewer_of", lambda request: CIO)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    c = TestClient(app)
    items = c.get("/api/v1/pulse2/items", params={"on_date": TODAY.isoformat()}).json()["items"]
    assert len(items) == 1
    assert c.post(f"/api/v1/pulse2/items/{items[0]['id']}/dismiss", json={}).status_code == 400
    assert c.post(f"/api/v1/pulse2/items/{items[0]['id']}/dismiss", json={"reason": "not mine"}).status_code == 200


def test_a_signed_intent_sent_to_build_gives_the_data_team_a_card_and_sources_can_be_registered(plane, monkeypatch):
    import json
    d = plane.path("intents", "iw-1")
    d.mkdir(parents=True)
    (d / "sow.json").write_text(json.dumps({"title": "Monthly investment report"}), encoding="utf-8")
    (d / "send_to_build.json").write_text(json.dumps({"by": "Priya Nair", "at": "2026-10-09T08:00:00+00:00", "project_id": "prj-00000001"}), encoding="utf-8")
    monkeypatch.setattr(P, "user_ids_with_roles", lambda pl, con, roles: [IDS["ops"]])
    P.generate(plane, TODAY)
    mine = [c for c in P.items(plane, OPS, TODAY) if c["kind"] == "build"]
    assert len(mine) == 1 and mine[0]["link"] == "/centre/build/p/prj-00000001" and mine[0]["headline"] == "Monthly investment report is ready for Build"
    assert not [c for c in P.items(plane, CIO, TODAY) if c["kind"] == "build"]
    P.generate(plane, TODAY)  # once
    assert len([c for c in P.items(plane, OPS, TODAY) if c["kind"] == "build"]) == 1

    def extra(pl, con, today):
        c = P.card("*", "x:1", "dashboard", "Dashboard refreshed", "2 tiles changed.", status_word="Current", urgency="worth_a_look", action_type="open", action="Open",
                   as_of=today.isoformat(), link="/centre/consume/d/1")
        c["recipient"] = IDS["cio"]
        return [c]
    P.register_source(extra)
    P.register_source(extra)  # twice is once
    try:
        P.generate(plane, TODAY)
        assert [c["headline"] for c in P.items(plane, CIO, TODAY) if c["kind"] == "dashboard"] == ["Dashboard refreshed"]
    finally:
        P.SOURCES.remove(extra)


# ---- cycle 1 fixes (P3) ------------------------------------------------------------------------------------------------------------

def test_a8_1_a_trade_break_on_a_valued_instrument_keeps_its_own_date(plane):
    seed_fund_a(plane)
    with wh.connect(plane) as con:
        con.execute("update exceptions set exception_type = 'break', title = 'Trade not matched · Evergreen Growth I · 2026-10-06 · T5' where id = ?", [IDS["exc"]])
    P.generate(plane, TODAY)
    c = P.items(plane, OPS, TODAY)[0]
    assert c["as_of"] == "2026-10-09" and c["received"] is None     # the check's day, not the 30 Sep valuation


def test_a6_6_a_capital_call_case_reaches_finance(plane):
    org = org_id(plane)
    with wh.connect(plane) as con:
        ins(con, "users", id=wh.new_id(), organization_id=org, external_identity_id="acc-raj", display_name="Raj Patel", email="r@x.test",
            business_role="Finance", is_active=True, created_at=NOW)
        ins(con, "exceptions", id=wh.new_id(), organization_id=org, exception_type="capital_call", title="Fund the capital call", detected_at=NOW,
            materiality_status="below_threshold", status="new", due_at=datetime(2026, 10, 20, tzinfo=timezone.utc))
    P.generate(plane, TODAY)
    c = P.items(plane, Viewer("Raj Patel", frozenset({"approver"}), False, "acc-raj"), TODAY)
    assert [(x["headline"], x["urgency"]) for x in c] == [("Fund the capital call", "needs_me")]
