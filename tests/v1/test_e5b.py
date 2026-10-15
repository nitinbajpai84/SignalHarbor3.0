"""E5b: brief lines and banner for the Fund A story; explain cites the amended statement page; the refusal question is refused;
a hidden portfolio is left out; the model wording is accepted only without digits. Sibling cards (E1c, E1d, E4d) are stubbed; E1a is real."""
import sys
import types
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e5_brief as B
from sh_platform.v1 import wh

UTC = timezone.utc
U = lambda n: str(uuid.uuid5(uuid.NAMESPACE_DNS, n)) if n else None  # noqa: E731  (the warehouse ids are uuids)
RV, EX = U("rv1"), U("ex1")
ISSUED_AT = datetime(2026, 10, 3, tzinfo=UTC)
PF1, PF2 = U("pf1"), U("pf2")
ALLOWED = {PF1}


def line(key, label, value, status, inst, pf=PF1, src=None):
    inst, src = U(inst), U(src)
    return {"line_key": key, "label": label, "value": Decimal(value), "currency": "USD", "status": status, "instrument_id": inst,
            "portfolio_id": pf, "metric_value_id": U(f"mv-{key}"), "source_row_id": src}


ISSUED = [line("fundA", "Evergreen Growth I", "10000000", "estimated", "fundA", src="v1"),
          line("fundB", "Evergreen Growth II", "6400000", "official", "fundB", pf=PF2),
          dict(line("total", "Total", "16400000", "official", None, pf=None), is_total=True)]
KNOWN = [line("fundA", "Evergreen Growth I", "10180000", "revised", "fundA", src="v2"),
         ISSUED[1], dict(line("total", "Total", "16580000", "revised", None, pf=None), is_total=True)]


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")

    def stub(name, **fns):
        m = types.ModuleType(f"sh_platform.v1.{name}")
        m.__dict__.update(fns)
        monkeypatch.setitem(sys.modules, f"sh_platform.v1.{name}", m)
        monkeypatch.setattr(sys.modules["sh_platform.v1"], name, m, raising=False)

    stub("e1_reports", as_issued=lambda pl, rv: ISSUED, as_known_now=lambda pl, rv: KNOWN)
    stub("e1_access", visible_portfolios=lambda pl, v: set(ALLOWED))
    stub("e4_guard", check_request=lambda t: {"refused": True, "reason": "Official figures are not changed from a question.",
                                              "review_path": "Opens a case for the authorised approver"} if "increase" in t.lower() else None)
    ALLOWED.clear()
    ALLOWED.add(PF1)
    org = U("org")
    with wh.connect(p) as con:
        con.execute("insert into reports (id, organization_id, report_code, report_name) values (?, ?, 'inv', 'September investment report')", [U("r1"), org])
        con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status, issued_at)"
                    " values (?, ?, ?, ?, '2026-09-30', ?, 'issued', ?)", [RV, org, U("r1"), U("run1"), ISSUED_AT, ISSUED_AT])
        con.execute("insert into exceptions (id, organization_id, instrument_id, exception_type, title, detected_at, materiality_status, status)"
                    " values (?, ?, ?, 'revision', 'Revised valuation affects an issued report', ?, 'material', 'new')", [EX, org, U("fundA"), wh.now()])
        con.execute("insert into exception_events (id, organization_id, exception_id, event_type, event_note, occurred_at) values (?, ?, ?, 'opened', 'CASE-0001', ?)",
                    [U("ev1"), org, EX, wh.now()])
        con.execute("insert into exception_impacts (id, organization_id, exception_id, report_version_id, metric_value_id, issued_value, draft_value, currency)"
                    " values (?, ?, ?, ?, ?, 10000000, 10180000, 'USD')", [U("im1"), org, EX, RV, U("mv-fundA")])
    return p


def add_story(p):
    org = U("org")
    with wh.connect(p) as con:
        for did, title, st, rec in [("d1", "Fund A statement", "estimate", datetime(2026, 10, 2, tzinfo=UTC)),
                                    ("d2", "Fund A amended statement", "final", datetime(2026, 10, 9, tzinfo=UTC))]:
            con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, document_type, title, original_uri,"
                        " content_hash, valuation_date, received_at, recorded_at, document_status, processing_status)"
                        " values (?,?,?,?,?,?,?,?,?,?,?,?,?)", [U(did), org, U("s"), U("g"), "statement", title, "u", did, date(2026, 9, 30), rec, rec, st, "done"])
        for fid, did, pg, ln in [("f1", "d1", 2, 14), ("f2", "d2", 2, 14)]:
            con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, page_number, line_number, confidence, review_status)"
                        " values (?,?,?,?,?,?,?,?)", [U(fid), org, U(did), "nav", pg, ln, "high", "confirmed"])
        for vid, amt, typ, did, fid, sup, rec in [("v1", 10_000_000, "manager_estimate", "d1", "f1", None, datetime(2026, 10, 2, tzinfo=UTC)),
                                                  ("v2", 10_180_000, "manager_final", "d2", "f2", "v1", datetime(2026, 10, 9, tzinfo=UTC))]:
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, evidence_document_id, extracted_field_id,"
                        " valuation_date, received_at, recorded_at, value_amount, currency, valuation_type, approval_status, supersedes_valuation_id)"
                        " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [U(vid), org, U("fundA"), PF1, U(did), U(fid), date(2026, 9, 30), rec, rec, amt, "USD", typ, "approved", U(sup)])


def test_brief_lines_and_banner(plane):
    ALLOWED.add(PF2)
    b = B.brief(plane, None, RV)
    a = next(x for x in b["lines"] if x["line_key"] == "fundA")
    assert (a["issued"], a["known_now"], a["difference"], a["status"]) == (Decimal(10_000_000), Decimal(10_180_000), Decimal(180_000), "revised")
    assert a["case_id"] == EX and next(x for x in b["lines"] if x["line_key"] == "fundB")["status"] == "official"
    assert b["banner"].startswith("2 lines below") and "Draft" not in b["banner"] and "CASE-0001" in b["banner"] and "Revised valuation affects an issued report" in b["banner"] and "manager-reported valuation" in b["banner"]
    assert b["report_name"] == "September investment report" and b["partial"] is False


def test_no_banner_when_all_official(plane, monkeypatch):
    monkeypatch.setattr(sys.modules["sh_platform.v1.e1_reports"], "as_known_now", lambda pl, rv: ISSUED)
    ALLOWED.add(PF2)
    assert B.brief(plane, None, RV)["banner"] is None


def test_hidden_portfolio_and_total_left_out(plane):
    b = B.brief(plane, None, RV)  # sees pf1 only
    assert [x["line_key"] for x in b["lines"]] == ["fundA"] and b["partial"] is True
    with pytest.raises(LookupError):
        B.explain(plane, None, RV, "fundB")
    ALLOWED.clear()
    assert B.brief(plane, None, RV)["lines"] == []  # fail closed


def test_explain_cites_the_amended_statement_page(plane):
    add_story(plane)
    r = B.explain(plane, None, RV, "fundA", "Why did this move?")
    assert not r["refused"] and r["wording"] == "rules"
    assert "180,000.00 USD" in r["answer"] and "10,180,000.00 USD" in r["answer"] and "9 Oct 2026" in r["answer"]
    assert [e["state"] for e in r["evidence"]] == ["superseded", "current"]
    cur = r["sources"][-1]
    assert (cur["title"], cur["page"], cur["line"], cur["document_status"]) == ("Fund A amended statement", 2, 14, "final")
    assert r["evidence"][-1]["source"] == "Fund A amended statement, page 2, line 14"
    assert r["case"]["id"] == EX and r["approver"] and r["next_action"].startswith("Review the case")
    assert any("fixed rules" in c for c in r["caveats"]) and r["figures"]["difference"] == Decimal(180_000)


def test_unmoved_line_says_so(plane):
    ALLOWED.add(PF2)
    r = B.explain(plane, None, RV, "fundB")
    assert "has not changed" in r["answer"] and "moved" not in r["answer"] and r["next_action"] == "No action needed."


def test_refusal_question_is_refused(plane):
    add_story(plane)
    r = B.explain(plane, None, RV, "fundA", "Increase official NAV by $180,000")
    assert r["refused"] is True and "authorised approver" in r["review_path"] and "answer" not in r


def test_model_wording_rules(plane, monkeypatch):
    add_story(plane)
    fake = types.SimpleNamespace(complete=lambda *a, **k: None)
    good = types.SimpleNamespace(status="done", text='{"answer": "{holding} changed by {difference}; see {received_date}."}')
    bad = types.SimpleNamespace(status="done", text='{"answer": "It rose by 180000."}')
    unknown = types.SimpleNamespace(status="done", text='{"answer": "{secret} rose."}')
    monkeypatch.setattr("sh_platform.v1.router.route", lambda model, *a, **k: model)
    for reply, expect in [(good, "model"), (bad, "rules"), (unknown, "rules")]:
        monkeypatch.setattr("sh_platform.agents.loop.run_agent", lambda *a, _r=reply, **k: _r)
        r = B.explain(plane, None, RV, "fundA", None, model=fake)
        assert r["wording"] == expect
        if expect == "model":
            assert r["answer"] == "Evergreen Growth I changed by 180,000.00 USD; see 9 Oct 2026."


def test_routes_are_declared():
    from sh_platform.v1 import e5b_routes
    assert {r.path for r in e5b_routes.router.routes} == {"/api/v1/brief/{rvid}", "/api/v1/brief/{rvid}/explain"}


def test_e1c_key_is_the_line_key(plane, monkeypatch):
    """E1c lines carry `key`; two lines for one instrument in two portfolios must not collide."""
    ALLOWED.add(PF2)
    a = {**ISSUED[0], "key": "holding_value|pf1|fundA"}
    b = {**ISSUED[0], "key": "holding_value|pf2|fundA", "portfolio_id": PF2}
    a.pop("line_key"), b.pop("line_key")
    monkeypatch.setattr(sys.modules["sh_platform.v1.e1_reports"], "as_issued", lambda pl, rv: [a, b])
    monkeypatch.setattr(sys.modules["sh_platform.v1.e1_reports"], "as_known_now", lambda pl, rv: [a, b])
    assert [x["line_key"] for x in B.brief(plane, None, RV)["lines"]] == ["holding_value|pf1|fundA", "holding_value|pf2|fundA"]


def test_pending_amended_statement_is_not_reported_as_unchanged(plane, monkeypatch):
    add_story(plane)
    with wh.connect(plane) as con:
        con.execute("update valuation_observations set approval_status = 'pending' where id = ?", [U("v2")])
    monkeypatch.setattr(sys.modules["sh_platform.v1.e1_reports"], "as_known_now", lambda pl, rv: ISSUED)
    r = B.explain(plane, None, RV, "fundA")
    assert "not verified yet" in r["answer"] and "10,180,000.00 USD" in r["answer"] and "has not changed" not in r["answer"]


def _fx(monkeypatch, rate):
    m = types.ModuleType("sh_platform.v1.e3_calc")
    m.fx = lambda pl, f, t, d, c=None: rate
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_calc", m)
    monkeypatch.setattr(sys.modules["sh_platform.v1"], "e3_calc", m, raising=False)


def test_currency_switch_converts_with_a_signed_rate_only(plane, monkeypatch):
    ALLOWED.add(PF2)
    with wh.connect(plane) as con:
        con.execute("update reports set reporting_currencies = 'USD,SGD'")
    _fx(monkeypatch, None)
    b = B.brief(plane, None, RV, "SGD")
    assert b["currencies"] == ["USD"] and b["currency"] == "USD" and "No signed exchange rate" in b["currency_message"]
    assert next(x for x in b["lines"] if x["line_key"] == "fundA")["issued"] == Decimal(10_000_000)
    _fx(monkeypatch, Decimal("1.35"))
    b = B.brief(plane, None, RV, "SGD")
    a = next(x for x in b["lines"] if x["line_key"] == "fundA")
    assert b["currencies"] == ["USD", "SGD"] and b["currency"] == "SGD" and a["currency"] == "SGD"
    assert (a["issued"], a["known_now"], a["difference"]) == (Decimal("13500000.00"), Decimal("13743000.00"), Decimal("243000.00"))
    assert B.brief(plane, None, RV)["currency"] == "USD"


def test_route_response_has_what_the_screen_reads(plane, monkeypatch):
    """The real JSON of GET /brief (shapes the E5c screen maps; see ui/src/v1/e5/e5.test.tsx)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.v1 import e5b_routes as R
    ALLOWED.add(PF2)
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "viewer_of", lambda request: None)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    j = TestClient(app).get(f"/api/v1/brief/{RV}", params={"currency": "SGD"}).json()
    assert {"report_name", "period_end", "issued_at", "banner", "lines", "open_cases", "currency", "currencies", "currency_message"} <= set(j)
    assert isinstance(j["banner"], str) and j["lines"][0]["issued"] == "10000000" and j["currencies"] == ["USD"]


# ---- cycle 1 fixes (a1.2, a1.3, a1.6) ------------------------------------------------------------------------------------

def test_why_did_the_total_move_names_the_lines_their_statement_and_the_case(plane):
    """a1.2: the Total is not a manager valuation; it moved because Fund A did, and CASE-0001 is open for it."""
    ALLOWED.add(PF2)
    add_story(plane)
    r = B.explain(plane, None, RV, "total")
    assert r["answer"].startswith("The total moved by +180,000.00 USD") and "16,400,000.00 USD then, 16,580,000.00 USD now" in r["answer"]
    assert "Evergreen Growth I +180,000.00 USD (10,000,000.00 USD to 10,180,000.00 USD, statement received 9 Oct 2026)" in r["answer"]
    assert "CASE-0001" in r["answer"] and "manager-reported valuation of Total" not in r["answer"] and "received on ." not in r["answer"]
    assert r["case"]["id"] == EX and r["next_action"].startswith("Review the case") and "Open a case" not in r["next_action"]
    assert not any("No source document" in c for c in r["caveats"]) and r["sources"][-1]["title"] == "Fund A amended statement"


def test_a_confirmed_amended_statement_is_said_confirmed_and_listed_once(plane):
    """a1.3: the confirm step re-records the same value from the same page; one piece of evidence, and the caveat says it is confirmed."""
    add_story(plane)
    org = U("org")
    with wh.connect(plane) as con:
        con.execute("update valuation_observations set approval_status = 'pending' where id = ?", [U("v2")])
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, evidence_document_id, extracted_field_id,"
                    " valuation_date, received_at, recorded_at, value_amount, currency, valuation_type, approval_status, supersedes_valuation_id)"
                    " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [U("v3"), org, U("fundA"), PF1, U("d2"), U("f2"), date(2026, 9, 30), datetime(2026, 10, 9, tzinfo=UTC), datetime(2026, 10, 9, 1, tzinfo=UTC),
                     10_180_000, "USD", "manager_final", "confirmed", U("v2")])
    r = B.explain(plane, None, RV, "fundA")
    assert [(e["value"], e["state"], e["approval"]) for e in r["evidence"]] == [(Decimal(10_000_000), "superseded", "approved"), (Decimal(10_180_000), "current", "confirmed")]
    assert [s["title"] for s in r["sources"]] == ["Fund A statement", "Fund A amended statement"]
    assert not any("until the manager's final statement is confirmed" in c for c in r["caveats"])
    assert any("replaced the value the report used, and it was confirmed on 9 Oct 2026" in c for c in r["caveats"])
