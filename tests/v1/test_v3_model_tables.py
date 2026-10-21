"""Harbor 3.0 company model additions (assumptions A1, A2): `fx_confirmations` and `expected_statements` reach an old office without losing
data, an FX confirmation PDF loads one row with its page, expected statements follow the fund's cadence or terms, and a fund nothing can
tell is asked about. Synthetic data only (the 10uc confirmations)."""
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import e0a_catalogue as C  # noqa: E402
from sh_platform.v1 import e0b_tools as T  # noqa: E402
from sh_platform.v1 import trade_intake as TI  # noqa: E402
from sh_platform.v1 import v3_expected as EX  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_pdf as V  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from sh_platform.v1.e1_write import org_id  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

FIX = ROOT / "tests" / "v1" / "fixtures" / "10uc" / "otc_confirms"
NEW = ("fx_confirmations", "expected_statements", "bank_accounts", "credit_facilities", "family_members", "vendor_contracts", "deal_pipeline", "committee_decisions")
NEW2 = ("office_expenses", "corporate_actions", "real_assets", "tax_lots", "tax_obligations", "grants", "staff_payroll", "kyc_records", "fund_holdings", "system_access_grants")  # assumptions A32 to A41
NEW = NEW + NEW2 + ("entity_ownership",)  # assumption A61
ADDED_COLS = {"cash_movements": ("bank_account_id", "counterparty_portfolio_id", "payment_stage", "payee_name", "reference"), "approvals": ("cash_movement_id",),  # assumption A18: columns added to existing tables
              "transactions": ("counterparty_name", "status_reason"), "exceptions": ("external_ref", "legal_entity_id"), "source_batches": ("arrived_on_time", "manual_fix"),  # assumptions A32 onward
              "sheet_mapping_columns": ("confidence",), "vendor_contracts": ("contract_kind", "sum_insured", "covered_asset_ref")}
OLD = "11111111-1111-4111-8111-111111111111"


@pytest.fixture()
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    return app, PlaneStore(str(data)).plane_for("evergreen")


def tables(plane) -> set[str]:
    with wh.connect(plane, read_only=True) as con:
        return {r[0] for r in con.execute("select table_name from information_schema.tables where table_schema = 'main'").fetchall()}


def columns(plane, table) -> set[str]:
    with wh.connect(plane, read_only=True) as con:
        return {r[0] for r in con.execute("select column_name from information_schema.columns where table_name = ?", [table]).fetchall()}


def test_old_office_gets_the_new_tables_and_columns_and_keeps_its_data(office):
    _, plane = office
    with wh.connect(plane) as con:
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?, ?, 'Old Fund', 'fund', now())", [OLD, org_id(plane)])
    n = C.version_of(plane)
    p = plane.path("model", "versions", str(n), "catalogue.json")  # the office as it was before this release: no such tables in its model or its warehouse
    cat = json.loads(p.read_text(encoding="utf-8"))
    cat["tables"] = [t for t in cat["tables"] if t["name"] not in NEW]
    cat["refs"] = [r for r in cat["refs"] if r["from"]["table"] not in NEW and r["to"]["table"] not in NEW]
    for t in cat["tables"]:
        t["columns"] = [c for c in t["columns"] if c["name"] not in ADDED_COLS.get(t["name"], ())]
    added = {(t, c) for t, cs in ADDED_COLS.items() for c in cs}
    cat["refs"] = [r for r in cat["refs"] if (r["from"]["table"], r["from"]["columns"][0]) not in added]
    p.write_text(json.dumps(cat), encoding="utf-8")
    with wh.connect(plane) as con:
        for t, cs in ADDED_COLS.items():
            for c in cs:
                con.execute(f"alter table {t} drop column {c}")
        for t in NEW:
            con.execute(f"drop table {t}")
    C._cache.clear()
    C._reloaded.clear()
    wh._READY.discard(str(wh.path(plane)))
    wh._SHARED.clear()
    with wh.connect(plane) as con:  # the next start
        assert con.execute("select canonical_name from instruments where id = ?", [OLD]).fetchone()[0] == "Old Fund"
    assert set(NEW) <= tables(plane)
    assert all(set(cs) <= columns(plane, t) for t, cs in ADDED_COLS.items())
    assert C.version_of(plane) == n + 1  # one new approved version, add-only
    with wh.connect(plane) as con:  # the new tables take a row with the shared columns
        con.execute("insert into bank_accounts (id, organization_id, source_record_id, received_at, recorded_at, holder_kind, account_purpose, bank_name, account_ref, status) "
                    "values (?, ?, ?, now(), now(), 'payee', 'payee', 'Harbour Bank (synthetic)', '4471', 'active')", [wh.new_id(), org_id(plane), wh.new_id()])
        con.execute("insert into office_expenses (id, organization_id, source_record_id, received_at, recorded_at, spent_on, category, currency, amount) "
                    "values (?, ?, ?, now(), now(), ?, 'Premises', 'USD', 100)", [wh.new_id(), org_id(plane), wh.new_id(), date(2026, 9, 1)])
        con.execute("insert into cash_movements (id, organization_id, source_record_id, portfolio_id, movement_type, effective_date, received_at, recorded_at, amount, currency, "
                    "confirmation_status, payment_stage, payee_name, reference) values (?, ?, ?, ?, 'payment', ?, now(), now(), 5, 'SGD', 'expected', 'scheduled', 'Synthetic Payee', 'CPF-202610')",
                    [wh.new_id(), org_id(plane), wh.new_id(), wh.new_id(), date(2026, 10, 14)])


def test_the_sql_file_and_the_model_file_name_the_same_tables_and_the_new_tables_follow_the_load_rule():
    import re
    db = (ROOT / "docs" / "v2" / "evidence-to-action-mvp.dbml").read_text(encoding="utf-8")
    ddl = (ROOT / "docs" / "v2" / "evidence-to-action-mvp.duckdb.sql").read_text(encoding="utf-8")
    assert set(re.findall(r"^Table (\w+) \{", db, re.M)) == set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \(", ddl))
    for t in NEW2:  # same organisation and load columns as fx_confirmations; a change is a new row that supersedes the old
        body = re.search(rf"CREATE TABLE IF NOT EXISTS {t} \((.*?)\n\);", ddl, re.S).group(1)
        cols = set(re.findall(r"^\s+(\w+) ", body, re.M))
        assert {"id", "organization_id", "source_record_id", "received_at", "recorded_at"} <= cols, t
        assert any(c.startswith("supersedes_") for c in cols), t


def test_fx_confirmation_pdf_loads_one_row_per_confirmation_with_its_page(office):
    app, plane = office
    names = ["FXF-2026-001_confirmation_2026-09-15.pdf", "FXF-2026-002_confirmation_2026-10-05.pdf"]
    th = {"id": "t-fx", "title": "Confirmations", "created": H.now(), "stage": "working", "events": [], "steps": [], "asked": 0, "started_by": "Helen Foo",
          "iid": "ini-test", "intake": {}}
    H.save(plane, th)
    fs = H.read_files(plane)
    for n in names:
        H.drop(plane, n, (FIX / n).read_bytes())
        fs.append({"name": n, "arrived_at": H.now(), "status": "recognised", "source": "Manager statements", "thread": "t-fx"})
    H._fp(plane).write_text(json.dumps(fs), encoding="utf-8")
    acct = next(a for a in app.state.account_store.list() if "helen" in a.email) if hasattr(app.state.account_store, "list") else None
    x = H.Ctx(app, plane, th, getattr(acct, "id", None))
    V.intake(x)
    q = V.questions(x)
    fx = [i for i in q if i["id"].startswith("pdf:harbour")]
    assert len(fx) == 1 and fx[0]["options"][:2] == ["Client sells (USD): USD 2,000,000.00", "Client buys (SGD): SGD 2,680,000.00"]  # one question for the layout
    V.answer(x, fx[0]["id"].split(":", 1)[1], fx[0]["options"][0])
    got, aside = V.load(x)
    assert got == 2 and not aside, aside
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute("select trade_reference, trade_date, value_date, currency_bought, amount_bought, currency_sold, amount_sold, rate, counterparty, "
                           "source_document_id, source_page from fx_confirmations order by trade_reference").fetchall()
    assert [r[0] for r in rows] == ["FXF-2026-001", "FXF-2026-002"]
    one = rows[0]
    assert one[1:9] == (date(2026, 9, 15), date(2026, 12, 15), "SGD", Decimal("2680000"), "USD", Decimal("2000000"), Decimal("1.34"), "Harbour Bank (synthetic)")
    assert one[9] and one[10] == 1  # the document and the page
    assert rows[1][4] == Decimal("4035600")  # the mismatched one loads as it is written; comparing it with the desk's trade is another figure


def test_a_csv_of_confirmations_maps_to_the_table():
    heads = ["Our ref", "Trade date", "Value date", "Buy ccy", "Buy amount", "Sell ccy", "Sell amount", "Forward rate", "Bank"]
    prof = {"columns": heads, "sheet": "s", "column_info": [{"name": h, "kind": "text", "date_format": None} for h in heads]}
    assert T.guess_purpose(prof) == "fx_confirmations"
    got = T._rules({**prof, "purpose": "fx_confirmations"})
    assert got["Buy amount"] == "fx_confirmations.amount_bought" and got["Sell ccy"] == "fx_confirmations.currency_sold" and got["Bank"] == "fx_confirmations.counterparty"
    assert got["Value date"] == "fx_confirmations.value_date" and got["Our ref"] == "fx_confirmations.trade_reference"


def test_sell_one_buy_other_is_a_valid_side():
    assert TI._signed("fund", "sell usd / buy sgd", Decimal(2000000), Decimal(2680000)) == (-2000000, 2680000)
    assert TI._signed("fund", "buy usd / sell sgd", Decimal(5), Decimal(7)) == (5, -7)
    assert TI._signed("fund", "sell usd / sell sgd", Decimal(5), Decimal(7)) is None  # two sells are no trade
    assert TI._signed("fund", "hold", Decimal(5), Decimal(7)) is None


def add_fund(plane, name, statements=(), terms=None, status="confirmed"):
    """A fund with a commitment, its statements received (documents with a valuation date) and, optionally, confirmed terms {field: (text, number)}."""
    org, iid = org_id(plane), wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,'fund',now())", [iid, org, name])
        con.execute("insert into commitments (id, organization_id, legal_entity_id, instrument_id, commitment_amount, currency, committed_on, recorded_at) "
                    "values (?,?,?,?,1000000,'USD',?,now())", [wh.new_id(), org, wh.new_id(), iid, date(2025, 1, 15)])
        for d in statements:
            doc(con, org, iid, f"{name} statement {d}", d)
        if terms:
            did = doc(con, org, iid, f"{name} LPA", None)
            for field, (text, num) in terms.items():
                con.execute("insert into extracted_fields (id, organization_id, document_id, field_name, value_text, value_numeric, page_number, confidence, review_status) "
                            "values (?,?,?,?,?,?,3,'high',?)", [wh.new_id(), org, did, field, text, num, status])
    return iid


def doc(con, org, iid, title, valuation_date):
    did = wh.new_id()
    con.execute("insert into documents (id, organization_id, source_system_id, access_group_id, instrument_id, document_type, title, original_uri, content_hash, "
                "valuation_date, received_at, recorded_at, document_status, processing_status) values (?,?,?,?,?,'statement',?,'x','h',?,now(),now(),'final','done')",
                [did, org, wh.new_id(), wh.new_id(), iid, title, valuation_date])
    return did


def ctx(office, tid):
    app, plane = office
    return H.Ctx(app, plane, {"id": tid, "started_by": "Helen Foo", "exceptions": []}, None)


def schedule(plane, iid):
    with wh.connect(plane, read_only=True) as con:
        return con.execute("select period_end, due_date, frequency, source, due_reason from expected_statements where instrument_id = ? order by period_end", [iid]).fetchall()


def test_expected_statements_follow_the_cadence_of_received_statements(office):
    x = ctx(office, "t-e")
    assert EX.cadence([date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)]) == "quarterly"
    assert EX.cadence([date(2026, 3, 31)]) is None  # one statement sets no cadence
    assert EX.cadence([date(2026, 3, 31), date(2026, 4, 30), date(2026, 7, 31)]) is None  # not regular
    iid = add_fund(x.plane, "Quarterly Fund III", [date(2026, 3, 31), date(2026, 6, 30)])
    out = EX.fill(x)
    rows = schedule(x.plane, iid)
    assert out["open"] == [] and {r[2] for r in rows} == {"quarterly"} and rows[0][0] == date(2026, 3, 31) and rows[-1][0] > wh.today(x.plane)
    assert all(r[1] is None and r[4] == "no terms on file" for r in rows)  # a due date is never invented
    assert rows[0][3] == "cadence of 2 statements received (2026-03-31 to 2026-06-30)"
    assert EX.fill(x)["written"] == 0  # a second load adds nothing


def test_a_fund_nothing_can_tell_is_asked_once_and_the_answer_sets_the_schedule(office):
    x = ctx(office, "t-q")
    iid = add_fund(x.plane, "Silent Fund I", [date(2026, 6, 30)])  # one statement is no cadence
    out = EX.fill(x)
    assert out["open"] == [{"id": str(iid), "name": "Silent Fund I"}] and out["written"] == 0
    assert x.th["exceptions"][0]["title"] == "How often does Silent Fund I send statements?"
    assert schedule(x.plane, iid) == []  # nothing invented
    want = {"id": f"pdf:freq-{iid}", "text": "How often does Silent Fund I send statements?", "options": ["Monthly", "Quarterly"], "assumed": None}
    assert want in EX.questions(x) and want in V.questions(x)  # Decision 2 shows it
    assert "Silent Fund I" in V.answer(x, f"freq-{iid}", "Quarterly")
    rows = schedule(x.plane, iid)
    assert rows and {r[2] for r in rows} == {"quarterly"} and rows[0][3] == "confirmed by Helen Foo" and rows[0][1] is None and rows[0][4] == "no terms on file"
    assert not any("Silent Fund I" in q["text"] for q in EX.questions(x))  # asked once
    assert EX.fill(x)["written"] == 0 and x.th["exceptions"] == []  # a person's schedule is never overridden


def test_the_question_suggests_the_known_cadence_and_the_person_still_confirms(office):
    x = ctx(office, "t-s")
    termed = add_fund(x.plane, "Pending Terms Fund", [date(2026, 6, 30)], terms={"reporting_frequency": ("Quarterly", None)}, status="pending")
    uneven = add_fund(x.plane, "Uneven Fund", [date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 7, 31), date(2026, 10, 31)])  # gaps 3, 3, 1, 3 ... majority
    lean_only = add_fund(x.plane, "Lean Fund", [date(2025, 9, 30), date(2025, 12, 31), date(2026, 1, 31), date(2026, 7, 31), date(2026, 10, 31)])  # gaps 3, 1, 6, 3
    silent = add_fund(x.plane, "Quiet Fund", [date(2026, 6, 30)])
    assert EX.lean([date(2026, 3, 31), date(2026, 4, 30), date(2026, 7, 31)]) is None  # a tie suggests nothing
    EX.fill(x)
    qs = {q["id"]: q for q in EX.questions(x)}
    q = qs[f"pdf:freq-{termed}"]
    assert q["assumed"] == "Quarterly" and q["options"] == ["Monthly", "Quarterly"] and "fund terms say quarterly (Pending Terms Fund LPA, page 3, not confirmed yet)" in q["text"]
    assert f"pdf:freq-{uneven}" not in qs  # a clear cadence was written by fill: nothing to ask
    assert qs[f"pdf:freq-{lean_only}"]["assumed"] == "Quarterly" and "5 statements received so far are quarterly" in qs[f"pdf:freq-{lean_only}"]["text"]
    assert qs[f"pdf:freq-{silent}"]["assumed"] is None  # nothing known: nothing suggested
    assert schedule(x.plane, termed) == []  # a suggestion writes nothing until the person confirms
    V.answer(x, f"freq-{termed}", q["assumed"])
    assert {r[2] for r in schedule(x.plane, termed)} == {"quarterly"} and schedule(x.plane, termed)[0][3] == "confirmed by Helen Foo"


def test_fund_terms_give_the_frequency_and_the_due_date(office):
    x = ctx(office, "t-t")
    iid = add_fund(x.plane, "Termsworth Fund", terms={"reporting_frequency": ("Quarterly", None), "statement_due_days": ("45 days", 45)})
    out = EX.fill(x)
    rows = schedule(x.plane, iid)
    assert out["written"] == len(rows) > 0 and {r[2] for r in rows} == {"quarterly"} and rows[0][3] == "fund terms: Termsworth Fund LPA, page 3"
    assert all((r[1] - r[0]).days == 45 and r[4] is None for r in rows) and all(r[0].month in (3, 6, 9, 12) for r in rows)
