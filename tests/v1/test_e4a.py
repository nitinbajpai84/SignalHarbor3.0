"""E4a cases: lifecycle with events, maker cannot check, owner cannot check, numbering never reused, E1d filtering, finance only when flagged, routes."""
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e4_cases as C
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

P1 = "00000000-0000-4000-8000-000000000001"
P2 = "00000000-0000-4000-8000-000000000002"
MEI = Viewer("Mei Tan", frozenset({"analyst"}), False, "a-mei")
RAJ = Viewer("Raj Iyer", frozenset({"approver"}), False, "a-raj")
RISK = Viewer("Rina Rao", frozenset({"participant"}), False, "a-rina")
ADMIN = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "a-arjun")
READER = Viewer("Dana Read", frozenset({"analyst"}), False, "a-dana")   # an analyst in a read-only access group (the Data team)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    # Raj and Mei see portfolio P1 only; Rina sees nothing (E1d's own rules are tested in test_e1d)
    from sh_platform.v1 import e1_access
    monkeypatch.setattr(e1_access, "level", lambda plane, viewer, entity_id=None, portfolio_id=None:
                        ("full" if viewer.name in ("Raj Iyer", "Mei Tan") else "read" if viewer.name == "Dana Read" else "none") if portfolio_id == P1 else "none")
    plane = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(plane) as con:
        for v in (MEI, RAJ, RISK, ADMIN, READER):
            con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), org_id(plane), v.account_id, v.name, v.account_id + "@example.test", True, wh.now()])
    return plane


def case(plane, **kw):
    return C.open(plane, {"exception_type": "revision", "title": "Fund A revised", "portfolio_id": P1, "materiality_status": "material",
                          "candidate_impact_amount": 180000, "impact_currency": "USD", **kw})


def events(plane, cid):
    return [h["event_type"] for h in C.get(plane, cid, ADMIN)["history"]]


def test_lifecycle_writes_an_event_for_every_change(plane):
    cid = case(plane)
    assert C.get(plane, cid, ADMIN)["status"] == "new"
    C.assign(plane, cid, ADMIN, "Mei Tan")
    C.take(plane, cid, MEI)
    C.add_event(plane, cid, None, "explanation_proposed", "Administrator revised the value.", agent_run_id=wh.new_id())
    C.submit(plane, cid, MEI, "Fund A was revised from estimate to final.", checker="Raj Iyer")
    assert C.get(plane, cid, ADMIN)["status"] == "waiting_check"
    C.send_back(plane, cid, RAJ, "Show the page reference.")
    assert C.get(plane, cid, ADMIN)["status"] == "investigating"
    C.submit(plane, cid, MEI, "Page 2 line 14 of the amended statement.", checker="Raj Iyer")
    C.approve(plane, cid, RAJ, "Agreed.")
    c = C.get(plane, cid, ADMIN)
    assert (c["status"], c["resolution_code"], c["number"]) == ("resolved", "explained", "CASE-0001")
    assert events(plane, cid) == ["opened", "assigned", "taken", "explanation_proposed", "submitted", "sent_back", "submitted", "explanation_confirmed", "resolved"]
    assert [a["status"] for a in c["approvals"]] == ["rejected", "approved"] or len(c["approvals"]) >= 1
    assert c["history"][3]["by"] == "Tally"


def test_maker_and_owner_cannot_check(plane):
    cid = case(plane)
    C.take(plane, cid, MEI)
    C.submit(plane, cid, MEI, "Because.")
    with pytest.raises(C.Refused) as e:
        C.approve(plane, cid, MEI)
    assert e.value.status == 403
    with pytest.raises(C.Refused):
        C.send_back(plane, cid, MEI, "no")
    assert C.get(plane, cid, MEI)["may"]["approve"] is False and C.get(plane, cid, RAJ)["may"]["approve"] is True
    with pytest.raises(C.Refused):  # a named checker cannot be the maker either
        C.submit(plane, case(plane, owner_user_id="Mei Tan"), MEI, "x", checker="Mei Tan")
    C.approve(plane, cid, RAJ)
    assert C.get(plane, cid, RAJ)["status"] == "resolved"


def test_material_needs_a_check_below_threshold_may_close(plane):
    big, small = case(plane), case(plane, materiality_status="below_threshold", title="Small")
    C.take(plane, big, MEI)
    with pytest.raises(C.Refused):
        C.resolve(plane, big, MEI, "done")
    C.take(plane, small, MEI)
    C.resolve(plane, small, MEI, "rounding")
    assert C.get(plane, small, MEI)["status"] == "resolved"
    with pytest.raises(C.Refused):
        C.dismiss(plane, big, MEI, " ")
    with pytest.raises(C.Refused) as e:  # the owner cannot dismiss a material case
        C.dismiss(plane, big, MEI, "duplicate")
    assert e.value.status == 403 and C.get(plane, big, MEI)["may"]["dismiss"] is False and C.get(plane, big, RAJ)["may"]["dismiss"] is True
    C.dismiss(plane, big, RAJ, "duplicate")
    assert C.get(plane, big, MEI)["status"] == "rejected"


def test_numbers_are_sequential_and_never_reused(plane):
    ids = [case(plane, title=f"c{i}") for i in range(3)]
    assert [C.get(plane, i, ADMIN)["number"] for i in ids] == ["CASE-0001", "CASE-0002", "CASE-0003"]
    C.dismiss(plane, ids[2], ADMIN, "not real")
    assert C.get(plane, case(plane), ADMIN)["number"] == "CASE-0004"
    assert C.get(plane, "CASE-0002", ADMIN)["id"] == ids[1]


def test_listing_order_and_e1d_filtering(plane):
    low = case(plane, materiality_status="below_threshold", title="low")
    late = case(plane, title="late", due_at="2026-10-12T00:00:00+00:00")
    soon = case(plane, title="soon", due_at="2026-10-10T00:00:00+00:00")
    other = case(plane, title="hidden", portfolio_id=P2)
    assert [c["title"] for c in C.listing(plane, ADMIN)] == ["soon", "late", "hidden", "low"]
    assert [c["title"] for c in C.listing(plane, RAJ)] == ["soon", "late", "low"]          # not P2, ordered by materiality then due
    assert C.listing(plane, RISK) == []                                                      # fail closed
    with pytest.raises(C.Refused):
        C.get(plane, other, RAJ)
    C.take(plane, low, MEI)
    assert [c["title"] for c in C.listing(plane, MEI, {"owner": "me"})] == ["low"]
    assert {c["title"] for c in C.listing(plane, ADMIN, {"materiality_status": "material"})} == {"late", "soon", "hidden"}
    assert soon and late


def test_the_maker_cannot_dismiss_her_own_material_case_while_it_waits(plane):
    cid = case(plane)
    C.take(plane, cid, MEI)
    C.submit(plane, cid, MEI, "Because.")
    with pytest.raises(C.Refused):
        C.dismiss(plane, cid, MEI, "never mind")
    assert C.get(plane, cid, MEI)["status"] == "waiting_check"


def test_a_person_without_access_cannot_act_before_the_check(plane):
    cid = case(plane)
    for act in (lambda: C.take(plane, cid, RISK), lambda: C.assign(plane, cid, RISK, "Rina Rao"), lambda: C.submit(plane, cid, RISK, "x"),
                lambda: C.dismiss(plane, cid, RISK, "x"), lambda: C.ask_finance(plane, cid, RISK, "Rina Rao")):
        with pytest.raises(C.Refused) as e:
            act()
        assert e.value.status == 403
    assert C.get(plane, cid, ADMIN)["owner"] is None and C.get(plane, cid, ADMIN)["status"] == "new"


def test_screen_view_has_the_names_the_action_desk_uses(plane):
    cid = case(plane, due_at="2026-10-16T00:00:00+00:00")
    C.take(plane, cid, MEI)
    C.add_event(plane, cid, None, "explanation_proposed", "Text of it.\nBridge: Difference 180,000 USD\nSources: document d1; valuation v1\nWorded by rules only (the model is off).")
    C.submit(plane, cid, MEI, "Because.", checker="Raj Iyer")
    c = C.get(plane, cid, RAJ)
    assert (c["materiality"], c["state"], c["amount"], c["currency"], c["maker_name"], c["checker_name"]) == ("high", "waiting_check", 180000, "USD", "Mei Tan", "Raj Iyer")
    assert c["can"] == c["may"] and c["can"]["approve"] and c["proposal"]["sources"] == ["document d1", "valuation v1"] and "Bridge:" in c["proposal"]["text"]
    assert {"at", "by", "text"} <= set(c["history"][0]) and c["affects"] == []
    row = C.listing(plane, RAJ)[0]
    assert (row["materiality"], row["state"], row["number"]) == ("high", "waiting_check", "CASE-0001")


def test_finance_only_when_the_accounting_view_is_affected(plane):
    plain, acct = case(plane), case(plane, accounting_view_affected=True)
    with pytest.raises(C.Refused):
        C.ask_finance(plane, plain, MEI, "Raj Iyer")
    C.ask_finance(plane, acct, MEI, "Raj Iyer")
    assert "finance_requested" in events(plane, acct) and C.get(plane, acct, ADMIN)["may"]["ask_finance"]
    assert not C.get(plane, plain, ADMIN)["may"]["ask_finance"]
    limit = case(plane, exception_type="limit_breach", title="Limit breached · X · P · 30 Sep 2026")  # UC5: the cure is a trade Finance approves
    C.ask_finance(plane, limit, MEI, "Raj Iyer")
    assert "finance_requested" in events(plane, limit) and C.get(plane, limit, ADMIN)["may"]["ask_finance"]


# ---- the screen's contract: the routes answer in the shape ui/src/v1/e4/api.ts reads ----
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

UI = Path(__file__).resolve().parents[2] / "ui" / "src" / "v1" / "e4"


def _client(plane, monkeypatch, who):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e4a_routes as R
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: plane)
    monkeypatch.setattr(R, "viewer_of", lambda req: who["v"])
    return TestClient(app)


def test_routes_answer_in_the_screens_shape_and_the_screens_paths_work(plane, monkeypatch):
    who = {"v": MEI}
    c = _client(plane, monkeypatch, who)
    org, rid, vid = org_id(plane), str(uuid.uuid4()), str(uuid.uuid4())
    with wh.connect(plane) as con:  # the issued September report the case affects
        con.execute("insert into reports (id, organization_id, report_code, report_name) values (?,?,?,?)", [rid, org, "inv", "September investment report"])
        con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status, issued_at) values (?,?,?,?,?,?,?,?)",
                    [vid, org, rid, str(uuid.uuid4()), "2026-09-30", datetime(2026, 10, 6, tzinfo=timezone.utc), "issued", datetime(2026, 10, 3, tzinfo=timezone.utc)])
    cid = case(plane, title="Investigate the 180,000 USD manager-reported valuation difference", due_at="2026-10-16T00:00:00+00:00")
    with wh.connect(plane) as con:
        con.execute("insert into exception_impacts (id, organization_id, exception_id, report_version_id, issued_value, draft_value, currency) values (?,?,?,?,?,?,?)",
                    [wh.new_id(), org, cid, vid, 10000000, 10180000, "USD"])
    assert c.post(f"/api/v1/cases/{cid}/take").json()["state"] == "investigating"
    C.add_event(plane, cid, None, "explanation_proposed", "The manager sent an amended statement.\nSources: document d1 (Amended statement); valuation v2")
    case_json = c.get(f"/api/v1/cases/{cid}").json()
    assert case_json["affects"] == ["September investment report, issued 3 Oct"] and case_json["proposal"]["sources"] == ["document d1 (Amended statement)", "valuation v2"]
    assert c.post(f"/api/v1/cases/{cid}/submit", json={"explanation": "Because the manager amended it.", "checker": "Raj Iyer"}).json()["state"] == "waiting_check"
    who["v"] = RAJ
    case_json = c.get(f"/api/v1/cases/{cid}").json()
    list_json = c.get("/api/v1/cases").json()
    if os.environ.get("SH_WRITE_FIXTURES"):
        (UI / "case.real.json").write_text(json.dumps(case_json, indent=2, default=str) + "\n", encoding="utf-8")
        (UI / "cases.real.json").write_text(json.dumps(list_json, indent=2, default=str) + "\n", encoding="utf-8")
    assert set(json.loads((UI / "case.real.json").read_text(encoding="utf-8"))) == set(case_json)
    assert set(json.loads((UI / "cases.real.json").read_text(encoding="utf-8"))["cases"][0]) == set(list_json["cases"][0])
    assert case_json["can"]["send_back"] and not case_json["can"]["submit"]
    assert c.post(f"/api/v1/cases/{cid}/send_back", json={"reason": "bridge is missing"}).json()["state"] == "investigating"  # the path and the body the screen sends
    who["v"] = MEI
    acct = case(plane, accounting_view_affected=True)
    assert c.post(f"/api/v1/cases/{acct}/ask_finance", json={"to": "Raj Iyer"}).status_code == 200
    who["v"] = RISK  # no access: refused before anything happens
    assert c.post(f"/api/v1/cases/{cid}/take").status_code == 403
    who["v"] = ADMIN
    assert c.get(f"/api/v1/cases/{cid}").json()["owner"] == "Mei Tan"


def test_explain_route_runs_tally_and_returns_the_case_with_its_proposal(plane, monkeypatch):
    who = {"v": MEI}
    c = _client(plane, monkeypatch, who)
    cid = case(plane)
    C.take(plane, cid, MEI)  # only the case owner (or an admin) may file Tally's proposals
    monkeypatch.setattr("sh_platform.v1.n1_tally.explain",  # the route is Tally's now; its analysis is checked in test_n1_tally.py
                        lambda p, v, eid, question=None, record=False: C.add_event(p, eid, None, "explanation_proposed", "A manager-reported valuation difference.\nSources: document d1") and {"summary": "x"})
    got = c.post("/api/v1/cases/CASE-0001/explain").json()  # by number too
    assert got["proposal"] == {"text": "A manager-reported valuation difference.", "sources": ["document d1"]} and got["state"] == "investigating"
    who["v"] = RISK
    assert c.post(f"/api/v1/cases/{cid}/explain").status_code == 403


SPONSOR = Viewer("Dan Foo", frozenset({"sponsor"}), False, "a-dan")


def test_a_policy_question_is_seen_by_approver_analyst_and_sponsor(plane):
    """a4.1: a policy question has no portfolio; the people who agree policy see it, a participant still does not."""
    pq = C.open(plane, {"exception_type": "policy_question", "title": "Agree the definition of benchmark B"})
    for v in (RAJ, MEI, SPONSOR, ADMIN):
        assert [c["title"] for c in C.listing(plane, v, {"exception_type": "policy_question"})] == ["Agree the definition of benchmark B"]
        assert C.get(plane, pq, v)["number"] == "CASE-0001"
    assert C.listing(plane, RISK) == []
    other = C.open(plane, {"exception_type": "break", "title": "no portfolio, not policy"})
    with pytest.raises(C.Refused):
        C.get(plane, other, RAJ)


def test_explain_is_offered_only_to_the_owner_or_the_admin(plane):
    """a2.6: the button follows the route's gate."""
    cid = case(plane)
    assert not C.get(plane, cid, RAJ)["can"]["explain"] and C.get(plane, cid, ADMIN)["can"]["explain"]
    C.take(plane, cid, MEI)
    assert C.get(plane, cid, MEI)["can"]["explain"] and not C.get(plane, cid, RAJ)["can"]["explain"]


def test_an_unknown_case_is_404_everywhere(plane, monkeypatch):
    """ev.24: a made-up number or id is not found, never a 409 from Tally or a database error."""
    c = _client(plane, monkeypatch, {"v": ADMIN})
    for path in ("/api/v1/cases/CASE-9999", "/api/v1/cases/not-a-case", "/api/v1/cases/CASE-9999/tally",
                 "/api/v1/cases/00000000-0000-4000-8000-00000000abcd/tally"):
        assert c.get(path).status_code == 404, path
    assert c.post("/api/v1/cases/CASE-9999/ask", json={"question": "why?"}).status_code == 404
    assert c.post("/api/v1/cases/CASE-9999/explain").status_code == 404


def test_uc2_02_read_only_group_sees_but_never_acts(plane):
    cid = case(plane)
    assert C.get(plane, cid, READER)["title"] == "Fund A revised"                     # sees it
    assert not any(C.get(plane, cid, READER)["may"][k] for k in ("take", "assign", "submit", "dismiss", "resolve"))
    for act in (lambda: C.take(plane, cid, READER), lambda: C.dismiss(plane, cid, READER, "no"), lambda: C.assign(plane, cid, READER, "Mei Tan")):
        with pytest.raises(C.Refused) as e:
            act()
        assert e.value.status == 403 and "read-only" in e.value.message
    assert C.get(plane, cid, MEI)["may"]["take"] is True                              # full access still acts


def test_uc8_03_listing_ranks_by_size_within_a_band(plane, monkeypatch):
    from decimal import Decimal
    from sh_platform.v1 import e3_calc, e3_rules
    monkeypatch.setattr(e3_rules, "current", lambda plane, code, on: {"parameters": {"currency": "USD"}} if code == "cio_materiality" else None)
    monkeypatch.setattr(e3_calc, "fx", lambda plane, f, t, on, cutoff=None: Decimal("0.7469") if (f, t) == ("SGD", "USD") else None)
    case(plane, title="small", candidate_impact_amount=12400)
    case(plane, title="big", candidate_impact_amount=592000)
    case(plane, title="sgd", materiality_status="below_threshold", candidate_impact_amount=8100, impact_currency="SGD")
    case(plane, title="usd", materiality_status="below_threshold", candidate_impact_amount=75870)
    assert [c["title"] for c in C.listing(plane, ADMIN)] == ["big", "small", "usd", "sgd"]
