"""K4: commitments, capital call and distribution notices (E2b reads, a person confirms), the Finance case for a call due soon, the core
model reload for existing companies, and the liquidity forecast (k6_liquidity)."""
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import e1_write, e2_extract as X, k6_liquidity as K, wh
from sh_platform.v1.e1_write import org_id
from sh_platform.v1.i2_north import Refused
from tests.v1.e1_seed import LE, seed

INST, SRC, GRP, PF, CASH, CASH_PF, SRC_REC = (str(uuid.uuid4()) for _ in range(7))
MEI = Viewer("Mei Tan", frozenset({"analyst"}), False, "acc-mei")
TODAY = date.today()
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def call_text(due: date, amount="250,000.00", kind="Capital call notice") -> str:
    return f"Evergreen Growth I - {kind}\nFund name: Evergreen Growth I\nDue date: {due.isoformat()}\nCapital required: USD {amount}\nBase currency: USD\n"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(plane) as con:
        con.execute("insert into organizations values (?,?,?)", [org_id(plane), "Acme", wh.now()])
    seed(plane, instruments=[INST, CASH], portfolios=[PF], sources=[SRC_REC])
    with wh.connect(plane) as con:
        con.execute("update instruments set instrument_type = 'cash', canonical_name = 'Cash USD' where id = ?", [CASH])
        con.execute("update instruments set canonical_name = 'Evergreen Growth I' where id = ?", [INST])
    monkeypatch.setattr("sh_platform.v1.e3_rules.current", lambda plane, code, on: None)  # no signed alert rule: the default of 30 days
    return plane


def add_doc(plane, name, text, instrument=INST):
    p = plane.path("landing", "originals", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    did = wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, instrument_id, document_type, title, original_filename,"
                    " original_uri, content_hash, received_at, recorded_at, document_status, processing_status) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [did, org_id(plane), SRC, GRP, instrument, "manager_notice", name, name, f"landing/originals/{name}", name,
                     datetime.now(timezone.utc), wh.now(), "final", "new"])
    return did


def fields(plane, did):
    return {f["field_name"]: f for f in X.fields_of(plane, did)}


def commit(plane, amount="1000000", entity=LE, instrument=INST, ccy="USD"):
    return K.record_commitment(plane, {"legal_entity_id": entity, "instrument_id": instrument, "commitment_amount": Decimal(amount),
                                       "currency": ccy, "committed_on": date(2025, 1, 15)})


def moves(plane):
    with wh.connect(plane) as con:
        cur = con.execute("select id, amount, currency, confirmation_status, notice_kind, due_date, commitment_id, supersedes_cash_movement_id, portfolio_id"
                          " from cash_movements order by recorded_at, id")
        return [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]


def cases(plane):
    with wh.connect(plane) as con:
        return con.execute("select exception_type, title, accounting_view_affected, status from exceptions").fetchall() if False else \
            con.execute("select exception_type, title, impact_currency, candidate_impact_amount, portfolio_id from exceptions").fetchall()


# ---- the core model change reaches existing companies -----------------------------------------------------------------------------

def test_core_reload_adds_commitments_to_a_company_made_before(tmp_path, monkeypatch):
    old = tmp_path / "old.dbml"
    text = E.CORE_FILE.read_text(encoding="utf-8")
    text = re.sub(r"Table commitments \{.*?\n\}\n", "", text, flags=re.S)
    text = re.sub(r"  (due_date|notice_kind|commitment_id) .*\n", "", text)
    text = text.replace("  commitments\n", "")
    old.write_text(text, encoding="utf-8")
    plane = PlaneStore(tmp_path / "data").create("old")
    wh.reset_cache()
    new_core = E.CORE_FILE
    monkeypatch.setattr(E, "CORE_FILE", old)
    assert E.version_of(plane) == 1 and not E.has_field(plane, "cash_movements", "due_date") and E.describe(plane, "commitments") is None
    with wh.connect(plane) as con:  # an existing row the release must not disturb
        con.execute("insert into organizations values (?,?,?)", [org_id(plane), "Old", wh.now()])
    monkeypatch.setattr(E, "CORE_FILE", new_core)
    E._reloaded.clear()
    wh.reset_cache()
    assert E.version_of(plane) == 2
    assert E.has_field(plane, "cash_movements", "due_date") and E.has_field(plane, "cash_movements", "commitment_id") and E.describe(plane, "commitments")
    meta = [v for v in E.versions(plane) if v["version"] == 2][0]
    assert meta["state"] == "approved" and meta["is_current"] and "commitments" in meta["summary"]
    assert [v for v in E.versions(plane) if v["version"] == 1][0]["state"] == "superseded"
    with wh.connect(plane) as con:  # the warehouse was migrated add-only
        cols = {r[0] for r in con.execute("select column_name from information_schema.columns where table_name = 'cash_movements'").fetchall()}
        assert {"due_date", "notice_kind", "commitment_id"} <= cols
        assert con.execute("select count(*) from organizations").fetchone()[0] == 1 and con.execute("select count(*) from commitments").fetchone()[0] == 0
    E._reloaded.clear()
    assert E.version_of(plane) == 2  # nothing more to add: no third version


def test_a_new_company_starts_with_the_new_core_and_no_extra_version(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("fresh")
    assert E.version_of(plane) == 1 and E.describe(plane, "commitments")["columns"][0]["name"] == "id"


# ---- commitments ------------------------------------------------------------------------------------------------------------------

def test_commitments_are_append_only_and_show_called_and_uncalled(world):
    plane = world
    first = commit(plane, "1000000")
    with pytest.raises(Refused):
        K.record_commitment(plane, {"legal_entity_id": LE, "instrument_id": INST, "commitment_amount": 0, "currency": "USD", "committed_on": "2025-01-01"})
    with pytest.raises(Refused):
        K.record_commitment(plane, {"legal_entity_id": str(uuid.uuid4()), "instrument_id": INST, "commitment_amount": 5, "currency": "USD", "committed_on": "2025-01-01"})
    second = K.record_commitment(plane, {"legal_entity_id": LE, "instrument_id": INST, "commitment_amount": Decimal("1200000"), "currency": "USD",
                                         "committed_on": "2025-06-01"}, supersedes_id=first)
    cur = K.commitments(plane)
    assert len(cur) == 1 and cur[0]["id"] == second and cur[0]["commitment_amount"] == Decimal("1200000") and cur[0]["uncalled"] == Decimal("1200000")
    with wh.connect(plane) as con:
        assert con.execute("select count(*) from commitments").fetchone()[0] == 2  # the first row stays


# ---- reading and confirming a notice ----------------------------------------------------------------------------------------------

def test_a_call_notice_is_read_with_page_and_line_and_the_amount_waits(world):
    plane = world
    com = commit(plane)
    due = TODAY + timedelta(days=10)
    did = add_doc(plane, "call.txt", call_text(due))
    ids = X.extract(plane, did, MEI)
    f = fields(plane, did)
    assert len(ids) == len(f) and {"notice_kind", "call_amount", "due_date", "fund", "currency"} <= set(f)
    assert f["notice_kind"]["value_text"] == "call" and (f["notice_kind"]["page_number"], f["notice_kind"]["line_number"]) == (1, 1)
    assert f["call_amount"]["value_numeric"] == "250000.0000000000" and f["call_amount"]["currency"] == "USD" and f["call_amount"]["line_number"] == 4
    assert f["call_amount"]["review_status"] == "pending" and f["due_date"]["value_text"] == due.isoformat() and f["fund"]["value_text"] == "Evergreen Growth I"
    m = moves(plane)  # read: a noticed movement per commitment, tied to the commitment, not yet a case
    assert len(m) == 1 and m[0]["confirmation_status"] == "noticed" and m[0]["notice_kind"] == "call" and str(m[0]["commitment_id"]) == com
    assert m[0]["amount"] == Decimal("250000") and m[0]["due_date"] == due and not cases(plane)
    assert sorted(X.extract(plane, did, MEI)) == sorted(ids) and len(moves(plane)) == 1  # a second read adds nothing


def test_confirming_a_call_due_soon_supersedes_the_noticed_row_and_opens_a_finance_case(world):
    plane = world
    com = commit(plane)
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=12)))
    X.extract(plane, did, MEI)
    done = X.confirm(plane, fields(plane, did)["call_amount"]["id"], MEI)
    assert done["review_status"] == "confirmed" and len(done["cash_movement_ids"]) == 1 and done["exception_id"]
    m = moves(plane)
    assert [r["confirmation_status"] for r in m] == ["noticed", "confirmed"] and str(m[1]["supersedes_cash_movement_id"]) == str(m[0]["id"])
    assert str(m[1]["commitment_id"]) == com and str(m[1]["id"]) == done["cash_movement_ids"][0]
    (kind, title, ccy, amount, pf), = cases(plane)
    assert (kind, ccy, amount) == ("capital_call", "USD", Decimal("250000")) and str(pf) == PF
    # a6.11: the title names the fund, the entity and the due date, like "Cash differs · Entity B · 2026-10-08"
    assert title.startswith("Fund the capital call · Evergreen Growth I · ") and title.endswith(f" · {(TODAY + timedelta(days=12)).isoformat()}") and title.count(" · ") == 3
    with wh.connect(plane) as con:
        desc = con.execute("select description from exceptions").fetchone()[0]
        afc = con.execute("select count(*) from exception_events where event_type = 'accounting_affected'").fetchone()[0]
    assert "250,000.00 USD" in desc and "page 1, line 4" in desc and afc == 1  # Finance is pulled in
    K.alert_if_due(plane, {**m[1], "instrument_id": INST, "currency": "USD"}, MEI)  # a later notice for the same call joins the open case
    assert len(cases(plane)) == 1


def test_a_corrected_amount_is_the_one_recorded(world):
    plane = world
    commit(plane)
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=45)))
    X.extract(plane, did, MEI)
    done = X.confirm(plane, fields(plane, did)["call_amount"]["id"], MEI, "240,000")
    assert done["review_status"] == "corrected" and moves(plane)[-1]["amount"] == Decimal("240000")
    assert not cases(plane) and done["exception_id"] is None  # due in 45 days: outside the 30-day window


def test_the_signed_alert_window_decides_the_case(world, monkeypatch):
    plane = world
    commit(plane)
    monkeypatch.setattr("sh_platform.v1.e3_rules.current", lambda p, code, on: {"parameters": {"days": 90}} if code == "cash_call_alert_days" else None)
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=60)))
    X.extract(plane, did, MEI)
    assert X.confirm(plane, fields(plane, did)["call_amount"]["id"], MEI)["exception_id"]
    monkeypatch.setattr("sh_platform.v1.e3_rules.current", lambda p, code, on: {"parameters": {"days": 7}})
    d2 = add_doc(plane, "call2.txt", call_text(TODAY + timedelta(days=20), "90,000.00"))
    X.extract(plane, d2, MEI)
    assert X.confirm(plane, fields(plane, d2)["call_amount"]["id"], MEI)["exception_id"] is None


def test_a_distribution_notice_is_recorded_without_a_case_and_a_recallable_one_is_named(world):
    plane = world
    commit(plane)
    text = ("Evergreen Growth I - Distribution notice\nFund name: Evergreen Growth I\nDue date: {d}\nDistribution amount: USD 80,000.00\n"
            "Base currency: USD\n{extra}")
    did = add_doc(plane, "dist.txt", text.format(d=(TODAY + timedelta(days=5)).isoformat(), extra=""))
    X.extract(plane, did, MEI)
    f = fields(plane, did)
    assert f["notice_kind"]["value_text"] == "distribution" and f["distribution_amount"]["currency"] == "USD" and "call_amount" not in f
    done = X.confirm(plane, f["distribution_amount"]["id"], MEI)
    assert done["exception_id"] is None and not cases(plane)
    assert moves(plane)[-1]["notice_kind"] == "distribution" and moves(plane)[-1]["confirmation_status"] == "confirmed"
    d2 = add_doc(plane, "dist2.txt", text.format(d=(TODAY + timedelta(days=9)).isoformat(), extra="This distribution is recallable.\n"))
    X.extract(plane, d2, MEI)
    assert fields(plane, d2)["notice_kind"]["value_text"] == "recallable" and moves(plane)[-1]["notice_kind"] == "recallable"
    d3 = add_doc(plane, "dist3.txt", text.format(d=(TODAY + timedelta(days=9)).isoformat(), extra="This distribution is non-recallable.\n"))
    X.extract(plane, d3, MEI)
    assert fields(plane, d3)["notice_kind"]["value_text"] == "distribution"


def test_confirm_without_a_commitment_is_refused_and_the_field_stays_pending(world):
    plane = world
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=10)))
    X.extract(plane, did, MEI)
    assert not moves(plane)  # no commitment: nothing recorded on read
    amount = fields(plane, did)["call_amount"]["id"]
    with pytest.raises(Refused) as e:
        X.confirm(plane, amount, MEI)
    assert "commitment" in e.value.message and fields(plane, did)["call_amount"]["review_status"] == "pending"
    commit(plane)
    assert X.confirm(plane, amount, MEI)["cash_movement_ids"]


def test_two_commitments_share_the_notice_by_size_and_the_cents_add_up(world):
    plane = world
    with wh.connect(plane) as con:
        e2, p2 = str(uuid.uuid4()), str(uuid.uuid4())
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", [e2, org_id(plane), "LE2", "Second", "SGD"])
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)",
                    [p2, org_id(plane), e2, "P2", "Second portfolio", "SGD"])
    commit(plane, "1000000")
    commit(plane, "2000000", entity=e2)
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=40), "100,001.00"))
    X.extract(plane, did, MEI)
    m = moves(plane)
    assert len(m) == 2 and sum(r["amount"] for r in m) == Decimal("100001.00")
    assert sorted(r["amount"] for r in m) == [Decimal("33333.67"), Decimal("66667.33")]
    assert {str(r["portfolio_id"]) for r in m} == {PF, p2}


def test_a_statement_is_read_as_before(world):
    plane = world
    did = add_doc(plane, "st.txt", "Evergreen Growth I - Monthly statement\nValuation date: 30 September 2026\nBase currency: USD\n"
                                   "Net asset value (estimate): USD 10,000,000.00\nCapital required: USD 50,000.00\nStatus: Estimate\n")
    X.extract(plane, did, MEI)
    f = fields(plane, did)
    assert "notice_kind" not in f and f["call_amount"]["review_status"] == "confirmed" and not moves(plane)


def test_capital_called_to_date_in_a_statement_is_not_a_notice(world):
    plane = world
    did = add_doc(plane, "st2.txt", "Evergreen Growth I - Quarterly statement\nValuation date: 30 September 2026\nBase currency: USD\n"
                                    "Net asset value: USD 10,000,000.00\nTotal capital called to date: USD 600,000.00\nDue date: 2026-12-01\nStatus: Final\n")
    X.extract(plane, did, MEI)
    assert "notice_kind" not in fields(plane, did) and not moves(plane)


def test_a_far_unconfirmed_call_is_still_flagged_and_a_shared_notice_is_marked_estimated(world):
    plane = world
    c = commit(plane, "1000000")
    put_move(plane, "call", "5000", TODAY + timedelta(days=120), status="noticed", com=c)
    e = K.forecast(plane, TODAY)["entities"][0]
    assert len(e["unconfirmed"]) == 1 and e["unconfirmed"][0]["estimated"] is False


# ---- the forecast -----------------------------------------------------------------------------------------------------------------

def put_cash(plane, amount, ccy="USD", view="accounting", pf=PF, on=None):
    return e1_write.record(plane, "position_snapshots", {"source_record_id": SRC_REC, "portfolio_id": pf, "instrument_id": CASH,
                                                          "position_date": on or TODAY, "as_of_at": NOW, "received_at": NOW, "source_market_value": Decimal(amount),
                                                          "currency": ccy, "view_type": view, "data_status": "official"})


def put_move(plane, kind, amount, due, status="confirmed", com=None, ccy="USD"):
    return e1_write.record(plane, "cash_movements", {"source_record_id": SRC_REC, "portfolio_id": PF, "instrument_id": INST, "movement_type": kind if kind != "recallable" else "distribution",
                                                      "effective_date": due, "received_at": NOW, "amount": Decimal(amount), "currency": ccy, "confirmation_status": status,
                                                      "due_date": due, "notice_kind": kind, "commitment_id": com})


def test_forecast_buckets_after_call_cash_and_unconfirmed_flags(world, monkeypatch):
    plane = world
    com = commit(plane, "2000000")
    put_cash(plane, "900000", view="operational")
    put_cash(plane, "1000000", view="accounting")  # the administrator's figure wins over the trading export
    put_move(plane, "call", "100000", TODAY + timedelta(days=10), com=com)
    put_move(plane, "call", "200000", TODAY + timedelta(days=45), "noticed", com=com)
    put_move(plane, "call", "50000", TODAY + timedelta(days=75), "expected", com=com)
    put_move(plane, "call", "999", TODAY + timedelta(days=20), "cancelled", com=com)
    put_move(plane, "call", "30000", TODAY - timedelta(days=3), com=com)
    put_move(plane, "distribution", "40000", TODAY + timedelta(days=20))
    put_move(plane, "recallable", "10000", TODAY + timedelta(days=50))
    put_move(plane, "call", "7000", TODAY + timedelta(days=200), com=com)  # beyond 90 days: not in a bucket
    out = K.forecast(plane, TODAY)
    (e,) = out["entities"]
    b = {x["key"]: x for x in e["buckets"]}
    assert e["entity_code"] == "LE" and e["currency"] == "USD" and e["available_cash"] == Decimal("1000000")
    assert (b["30"]["calls"], b["30"]["distributions"], b["30"]["cash_after_calls"]) == (Decimal("100000"), Decimal("40000"), Decimal("900000"))
    assert (b["60"]["calls"], b["60"]["distributions"], b["60"]["cash_after_calls"]) == (Decimal("200000"), Decimal("10000"), Decimal("700000"))
    assert (b["90"]["calls"], b["90"]["cash_after_calls"]) == (Decimal("50000"), Decimal("650000"))
    assert b["overdue"]["calls"] == Decimal("30000") and b["overdue"]["cash_after_calls"] is None
    assert [i["status"] for i in b["60"]["items"] if i["kind"] == "call"] == ["noticed"] and any(i["recallable"] for i in b["60"]["items"])
    assert sorted(i["amount"] for i in e["unconfirmed"]) == [Decimal("50000"), Decimal("200000")]  # unconfirmed calls flagged
    assert e["uncalled"] == Decimal("2000000") - Decimal("100000") - Decimal("30000") - Decimal("7000") and not e["problems"]
    assert all(i["source_record_id"] for x in e["buckets"] for i in x["items"])  # every figure points at its record


def test_forecast_is_as_known_at_the_cutoff_and_follows_a_correction(world):
    plane = world
    com = commit(plane)
    first = put_move(plane, "call", "100000", TODAY + timedelta(days=10), "noticed", com=com)
    before = wh.now()
    e1_write.record(plane, "cash_movements", {"source_record_id": SRC_REC, "portfolio_id": PF, "instrument_id": INST, "movement_type": "call", "effective_date": TODAY + timedelta(days=10),
                                              "received_at": NOW, "amount": Decimal("120000"), "currency": "USD", "confirmation_status": "confirmed",
                                              "due_date": TODAY + timedelta(days=10), "notice_kind": "call", "commitment_id": com}, supersedes_id=first)
    now = K.forecast(plane, TODAY)["entities"][0]["buckets"][1]
    then = K.forecast(plane, TODAY, cutoff=before)["entities"][0]["buckets"][1]
    assert (now["calls"], then["calls"]) == (Decimal("120000"), Decimal("100000")) and len(now["items"]) == 1 and then["items"][0]["status"] == "noticed"


def test_forecast_converts_with_the_signed_rate_and_never_guesses(world, monkeypatch):
    plane = world
    com = commit(plane)
    put_cash(plane, "1000000")
    put_move(plane, "call", "100000", TODAY + timedelta(days=10), com=com, ccy="EUR")
    out = K.forecast(plane, TODAY)["entities"][0]  # no signed rate EUR to USD: the call is left out and named
    assert out["buckets"][1]["calls"] == 0 and out["problems"] and "EUR to USD" in out["problems"][0]
    monkeypatch.setattr("sh_platform.v1.e3_calc.fx", lambda p, f, t, on, cut=None: Decimal("1.10") if (f, t) == ("EUR", "USD") else Decimal("0.75") if (f, t) == ("USD", "SGD") else None)
    ok = K.forecast(plane, TODAY)["entities"][0]
    assert ok["buckets"][1]["calls"] == Decimal("110000.00") and not ok["problems"]
    sgd = K.forecast(plane, TODAY, currency="SGD")["entities"][0]
    assert sgd["currency"] == "SGD" and sgd["available_cash"] == Decimal("750000.00")


def test_forecast_shows_only_the_entities_the_viewer_may_see(world, monkeypatch):
    plane = world
    with wh.connect(plane) as con:
        e2 = str(uuid.uuid4())
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", [e2, org_id(plane), "LE2", "Second", "USD"])
    monkeypatch.setattr("sh_platform.v1.e1_access.visible_entities", lambda p, v: {e2})
    assert [e["entity_code"] for e in K.forecast(plane, TODAY)["entities"]] == ["LE", "LE2"]  # no viewer: everything (a program call)
    assert [e["entity_code"] for e in K.forecast(plane, TODAY, viewer=MEI)["entities"]] == ["LE2"]
    monkeypatch.setattr("sh_platform.v1.e1_access.visible_entities", lambda p, v: set())
    assert K.forecast(plane, TODAY, viewer=MEI)["entities"] == []


def test_a_paid_past_call_is_not_overdue_but_still_counted_as_called(world):
    plane = world
    com = commit(plane, "2000000")
    put_cash(plane, "1000000", view="accounting")
    put_move(plane, "call", "30000", TODAY - timedelta(days=3), "paid", com=com)
    put_move(plane, "call", "20000", TODAY - timedelta(days=2), com=com)
    (e,) = K.forecast(plane, TODAY)["entities"]
    b = {x["key"]: x for x in e["buckets"]}
    assert b["overdue"]["calls"] == Decimal("20000") and e["uncalled"] == Decimal("2000000") - Decimal("50000") and not e["unconfirmed"]


# ---- cycle 1 fixes (a6.7-a6.10, j-uc6a.2, j-uc6a.3) ------------------------------------------------------------------------------

def test_shortfall_is_said_in_words_beside_the_cash_after_confirmed_calls_only(world):
    plane = world
    com = commit(plane, "6000000")
    put_cash(plane, "880400")
    put_move(plane, "call", "450000", TODAY + timedelta(days=11), com=com)
    put_move(plane, "call", "600000", TODAY + timedelta(days=21), "noticed", com=com)
    put_move(plane, "distribution", "320000", TODAY + timedelta(days=38), "noticed")
    (e,) = K.forecast(plane, TODAY)["entities"]
    b = {x["key"]: x for x in e["buckets"]}
    assert (b["30"]["cash_after_calls"], b["30"]["cash_after_confirmed_calls"]) == (Decimal("-169600"), Decimal("430400"))
    assert e["warnings"] == [f"Shortfall: {e['entity_name']} is short by 169,600.00 USD within 30 days if every call is paid, including the Evergreen Growth I "
                             "call, not confirmed yet; after the confirmed calls alone 430,400.00 USD remains."]
    assert [i["amount"] for i in e["unconfirmed_distributions"]] == [Decimal("320000")] and b["overdue"]["label"] == "Past due, not marked paid"
    (c,) = K.commitments(plane)
    assert c["called"] == c["called_due_later"] == Decimal("450000")  # counted once confirmed (answer key), and said to be not due yet
    assert c["called_note"] == f"Includes 450,000.00 USD called for {(TODAY + timedelta(days=11)):%d %b %Y}, not due yet."


def test_a_call_in_the_forecast_names_its_notice_page_and_line(world):
    plane = world
    commit(plane)
    did = add_doc(plane, "call.txt", call_text(TODAY + timedelta(days=12)))
    X.extract(plane, did, MEI)
    X.confirm(plane, fields(plane, did)["call_amount"]["id"], MEI)
    (i,) = [i for x in K.forecast(plane, TODAY)["entities"][0]["buckets"] for i in x["items"]]
    assert (i["document_id"], i["document_title"], i["page"], i["line"]) == (did, "call.txt", 1, 4) and i["received_at"]


def test_a_late_confirmed_call_already_in_the_file_keeps_the_file_called_figure(world, monkeypatch):  # UC6 H2: EG-B uncalled 8.9m
    plane = world
    srcs = {k: str(uuid.uuid4()) for k in "CDE"}
    seed(plane, sources=list(srcs.values()))
    commitments = {"C": ("6000000", "3600000"), "D": ("5000000", "4500000"), "E": ("10000000", "4000000")}  # commitment, called per the file
    com = {k: K.record_commitment(plane, {"legal_entity_id": LE, "instrument_id": INST, "commitment_amount": Decimal(amt), "currency": "USD",
                                          "committed_on": date(2025, 1, 15), "source_record_id": srcs[k]}) for k, (amt, _) in commitments.items()}
    filed = {srcs[k]: (Decimal(called), "commitments_schedule_2026-08-31.xlsx", date(2026, 8, 31)) for k, (_, called) in commitments.items()}
    monkeypatch.setattr(K, "_file_called", lambda con, sid, grids: filed.get(str(sid)))
    # the Cedarpoint call of 300,000 (due 23 Jul, paid) was noticed in July and received on 12 Aug: the 31 Aug file already counts it
    e1_write.record(plane, "cash_movements", {"source_record_id": SRC_REC, "portfolio_id": PF, "instrument_id": INST, "movement_type": "call",
                                              "effective_date": date(2026, 7, 23), "received_at": datetime(2026, 8, 12, tzinfo=timezone.utc),
                                              "amount": Decimal("300000"), "currency": "USD", "confirmation_status": "confirmed",
                                              "due_date": date(2026, 7, 23), "notice_kind": "call", "commitment_id": com["D"]})
    cur = {c["id"]: c for c in K.commitments(plane)}
    assert cur[com["D"]]["called"] == Decimal("4500000") and cur[com["D"]]["uncalled"] == Decimal("500000")
    assert sum(c["uncalled"] for c in cur.values()) == Decimal("8900000")  # EG-B: 2.4m + 0.5m + 6.0m
