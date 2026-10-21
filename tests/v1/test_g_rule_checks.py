"""G: rule checks on every document as it arrives (v3_rule_checks.check_documents) and a capital call matched to the payment that settled it
(e3_recon.match_calls). Synthetic data only.

1. Unit cases on stub rows: each of the seven checks fails on its own planted fault, holds the document and raises a card naming the check, the values and the person.
2. The office6m fixture through the real loader: the planted document-arrival issues (M05a, M05b, M06) are caught, each has one card, nothing else fails, and the
   figures are not disturbed (call 7 stays noticed).
3. UC01 step 6 on the same warehouse: call 7 is paid on the Monday statement and closes with no human step; one payment never settles two calls; an unpaid call
   after its due date raises one card.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import e3_recon as RECON
from sh_platform.v1 import v3_office6m_loaders as L
from sh_platform.v1 import v3_rule_checks as RC
from sh_platform.v1 import wh
from tests.v1 import test_w2_loader as W2

D = Decimal


# ---- 1. unit cases -------------------------------------------------------------------------------------------------------------------------

class Stub:
    """Just what check_documents reads from the loader."""
    def __init__(self):
        self.rows = {"documents": [], "extracted_fields": [], "commitments": [], "cash_movements": [], "bank_accounts": [], "exceptions": [], "position_snapshots": []}
        self.vendor_acct = {}
        self.ent = {"EG-HOLD": "ent-1"}
        self.md = {"entities": {"EG-HOLD": "Evergreen Holdings"}}
        self.flags = []

    def add(self, table, **kw):
        self.rows.setdefault(table, []).append({"id": str(uuid.uuid4()), **kw})
        return self.rows[table][-1]["id"]

    def person(self, name):
        return f"user-{name}"

    def note(self, kind, **kw):
        self.flags.append(kw.get("flag"))

    def call(self, no=7, amount=1250000, inv=900000, fee=350000, notice=date(2026, 10, 13), due=date(2026, 10, 23), ccy="USD", ending="2209", sr=None):
        sr = sr or f"sr-{no}-{amount}"
        d = self.add("documents", document_type="capital_call_notice", title=f"CEDA/2026/{no:03d}", document_date=notice, instrument_id="fund-C", source_record_id=sr,
                     document_status="final", received_at="2026-10-13 12:00:00+00")
        for name, text, n, c in (("fund", "Cedarpoint Ventures III", None, None), ("investor", "Evergreen Holdings", None, None), ("call_no", str(no), D(no), None),
                                 ("amount", None, D(amount), ccy), ("due_date", due.isoformat(), None, None), ("bank_account", f"SYN-0000-{ending}", None, None),
                                 ("new_investments", None, D(inv), "USD"), ("management_fee", None, D(fee), "USD")):
            self.add("extracted_fields", document_id=d, field_name=name, value_text=text, value_numeric=n, currency=c)
        self.add("cash_movements", source_record_id=sr, movement_type="call", confirmation_status="noticed", amount=-D(amount))
        return next(x for x in self.rows["documents"] if x["id"] == d)


@pytest.fixture()
def o():
    s = Stub()
    s.add("commitments", legal_entity_id="ent-1", instrument_id="fund-C", commitment_amount=D(10000000), currency="USD", called_to_date=D(6000000), called_as_at=date(2026, 9, 30))
    s.add("bank_accounts", holder_kind="payee", instrument_id="fund-C", account_ref="2209", verified_on="2026-04-01")
    return s


def one_fail(o, check):
    fails = RC.check_documents(o)
    assert [f["check"] for f in fails] == [check], fails
    return fails[0]


def test_a_clean_call_passes_and_stays_in_the_figures(o):
    d = o.call()
    assert RC.check_documents(o) == []
    assert d["document_status"] == "final" and o.rows["cash_movements"][0]["confirmation_status"] == "noticed" and o.rows["exceptions"] == []


def test_parts_must_add_up_to_the_amount(o):
    d = o.call(inv=900000, fee=300000)
    f = one_fail(o, "parts")
    assert "1,200,000" in f["words"] and "1,250,000" in f["words"] and f["who"] == "Daniel Foo"
    assert d["document_status"] == "held" and o.rows["cash_movements"][0]["confirmation_status"] == "held"
    card = o.rows["exceptions"][0]
    assert card["exception_type"] == "document_check" and "do not add up" in card["title"] and "Daniel Foo (Head of Finance)" in card["description"]


def test_due_date_must_be_after_the_notice_date(o):
    o.call(due=date(2026, 10, 13))
    f = one_fail(o, "dates")
    assert "13 October 2026" in f["words"]


def test_call_may_not_exceed_the_unfunded_commitment(o):
    o.call(amount=4100000, inv=3750000, fee=350000)  # 10,000,000 - 6,000,000 = 4,000,000 unfunded
    f = one_fail(o, "unfunded")
    assert "4,000,000" in f["words"]


def test_an_earlier_call_since_the_register_counts_as_called(o):
    o.call(no=6, amount=3000000, inv=2650000, fee=350000, notice=date(2026, 10, 1), due=date(2026, 10, 15), sr="sr-6")
    o.call(no=7, amount=1250000)  # 6,000,000 + 3,000,000 called, 1,000,000 left
    f = one_fail(o, "unfunded")
    assert "1,000,000" in f["words"]


def test_currency_must_equal_the_commitment_currency(o):
    o.call(ccy="SGD")
    f = one_fail(o, "currency")
    assert "SGD" in f["words"] and "USD" in f["words"]


def test_wire_account_must_be_the_one_on_file_and_the_call_is_not_held(o):
    d = o.call(ending="4471")
    f = one_fail(o, "account")
    assert "4471" in f["words"] and "2209" in f["words"] and f["who"] == "Grace Ong"
    assert d["document_status"] == "final" and o.rows["cash_movements"][0]["confirmation_status"] == "noticed"  # still in liquidity; the payment stays on hold by the recipe


def test_an_account_card_an_earlier_reader_raised_is_not_raised_twice(o):
    o.call(ending="4471")
    o.add("exceptions", exception_type="bank_details_changed", title="Cedarpoint Ventures III call 7 names a new account")
    one_fail(o, "account")
    assert len(o.rows["exceptions"]) == 1


def test_the_same_fund_call_number_and_amount_twice_holds_the_second(o):
    o.call(sr="sr-a")
    b = o.call(sr="sr-b")
    f = one_fail(o, "duplicate")
    assert "second time" in f["words"] and b["document_status"] == "held"
    assert [m["confirmation_status"] for m in o.rows["cash_movements"]] == ["noticed", "held"]


def statement(o, month, opening, closing, implied=None):
    d = o.add("documents", document_type="bank_statement", title=f"HB_HOLD_USD_2026-{month:02d}", instrument_id="cash-1", valuation_date=date(2026, month, 30), source_record_id=f"sr-s{month}",
              document_status="final", received_at="2026-10-13 12:00:00+00")
    for n, v in (("opening_balance", opening), ("opening_implied", opening if implied is None else implied), ("closing_balance", closing)):
        o.add("extracted_fields", document_id=d, field_name=n, value_numeric=D(v))
    return next(x for x in o.rows["documents"] if x["id"] == d)


def test_a_statement_must_open_where_the_last_one_closed(o):
    statement(o, 4, 100, 200)
    statement(o, 5, 200, 250)
    assert RC.check_documents(o) == []
    statement(o, 6, 260, 300)
    f = one_fail(o, "balance")
    assert "260" in f["words"] and "250" in f["words"]


def test_a_stale_stated_opening_is_fine_when_the_first_days_movements_imply_the_closing(o):
    statement(o, 4, 100, 200)
    statement(o, 5, 100, 250, implied=200)  # the office6m statements state a stale opening on their first day
    assert RC.check_documents(o) == []


def test_a_missing_month_is_not_compared(o):
    statement(o, 4, 100, 200)
    statement(o, 6, 999, 300)
    assert RC.check_documents(o) == []


# ---- 2. the office6m fixture through the real loader ---------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    seen = []
    real = RC.check_documents
    mp = pytest.MonkeyPatch()
    mp.setattr(RC, "check_documents", lambda x: seen.append(real(x)) or seen[-1])
    tmp = tmp_path_factory.mktemp("g")
    box = W2.office_dropbox(tmp)
    wh.reset_cache()
    plane = PlaneStore(tmp / "data").create("evergreen")
    report = L.load_plane(plane, box)
    mp.undo()
    con = wh.connect(plane)
    con.execute("set TimeZone = 'UTC'")
    yield {"plane": plane, "con": con, "fails": seen[-1], "report": report}
    con.close()


def q(con, sql, *a):
    c = con.execute(sql, list(a))
    return [dict(zip([x[0] for x in c.description], r)) for r in c.fetchall()]


def test_the_planted_document_arrival_issues_are_caught(loaded):
    got = {(f["check"], f["words"].split(" asks")[0].split(" arrives")[0]) for f in loaded["fails"]}
    assert ("account", "Cedarpoint Ventures III call 7") in got  # M05a: call 7 names 4471, the file says 2209
    assert ("account", "Lakeside Legal LLP invoice LL-2026-0828") in got  # M05b
    assert ("duplicate", "Orchard IT Services invoice INV-OIT-2606") in got  # M06
    assert len(loaded["fails"]) == 3, loaded["fails"]  # nothing else in a clean office fails: no false alarm on any call, invoice or statement


def test_each_failure_has_one_card_naming_the_person(loaded):
    cards = q(loaded["con"], "select exception_type, title from exceptions where exception_type in ('bank_details_changed', 'duplicate_invoice', 'document_check')")
    titles = sorted(c["title"] for c in cards)
    assert titles.count("Cedarpoint Ventures III call 7 names a new account") == 1
    assert titles.count("Lakeside Legal LLP invoice LL-2026-0828 names a new account") == 1
    assert sum("INV-OIT-2606" in t for t in titles) == 1
    assert not [c for c in cards if c["exception_type"] == "document_check"]  # the readers' own cards stood; no second card
    assert {f["who"] for f in loaded["fails"]} == {"Grace Ong"}


def test_call_7_stays_in_the_figures(loaded):
    r = q(loaded["con"], "select confirmation_status from cash_movements where movement_type = 'call' and due_date = date '2026-10-23' and amount < 0")
    assert [x["confirmation_status"] for x in r] == ["noticed"]
    assert not q(loaded["con"], "select 1 from documents where document_status = 'held'")


def test_the_statements_carry_their_balances(loaded):
    r = q(loaded["con"], "select count(*) n, count(*) filter (where exists (select 1 from extracted_fields f where f.document_id = d.id and f.field_name = 'closing_balance')) k "
                         "from documents d where document_type = 'bank_statement'")[0]
    assert r["n"] > 80 and r["n"] == r["k"]


# ---- 3. UC01 step 6: call 7 paid on the Monday statement -----------------------------------------------------------------------------------

def call7(con):
    return q(con, "select m.*, (select f.value_text from extracted_fields f join documents d on d.id = f.document_id where d.source_record_id = m.source_record_id and f.field_name = 'call_no') call_no "
                  "from cash_movements m where m.movement_type = 'call' and m.due_date = date '2026-10-23' and m.confirmation_status = 'noticed' and m.amount < 0")[0]


def clone(con, c, **over):
    row = {**{k: v for k, v in c.items() if k != "call_no"}, "id": str(uuid.uuid4()), **over}
    con.execute(f"insert into cash_movements ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))
    return row["id"]


def monday_payment(con, c, amount, day, ref="CC-CALL-C-7", payee="Cedarpoint Ventures"):
    """A bank line of the Monday statement: its own source record (a copy of a real bank-line record) and a confirmed outflow of the call's entity."""
    sr = q(con, "select * from source_records where record_type = 'bank_line' limit 1")[0]
    sid = str(uuid.uuid4())
    sr = {**sr, "id": sid, "external_record_id": ref, "effective_at": day}
    con.execute(f"insert into source_records ({', '.join(sr)}) values ({', '.join('?' * len(sr))})", list(sr.values()))
    cash = q(con, "select portfolio_id from cash_movements where reference = 'CC-CALL-C-5' and movement_type = 'payment' limit 1")[0]["portfolio_id"]  # the entity's cash portfolio, as April's payment used it
    pid = str(uuid.uuid4())
    row = {"id": pid, "organization_id": c["organization_id"], "source_record_id": sid, "portfolio_id": cash, "movement_type": "payment",
           "effective_date": day, "received_at": f"{day} 06:00:00+00", "recorded_at": f"{day} 06:00:00+00", "amount": -D(amount), "currency": "USD", "confirmation_status": "confirmed",
           "reference": ref, "payee_name": payee}
    con.execute(f"insert into cash_movements ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))
    return pid, sid


def test_call_7_is_paid_on_the_monday_statement_with_no_human_step(loaded):
    con, plane = loaded["con"], loaded["plane"]
    c = call7(con)
    assert c["call_no"] == "7"
    far = clone(con, c, due_date=date(2026, 12, 15))  # the same call again, due far outside the window: it must not take the payment
    twin = clone(con, c)  # a second call of the same fund, amount and date: one payment never settles both
    pid, sid = monday_payment(con, c, 1250000, date(2026, 10, 19))  # Monday 19 October, four days before the due date
    out = RECON.match_calls(plane, date(2026, 10, 19))
    assert len(out["paid"]) == 1 and out["cards"] == []
    paid = out["paid"][0]
    assert paid["payment"] == pid and paid["bank_receipt"] == sid and paid["notice_receipt"] == str(c["source_record_id"])
    assert paid["call"] in (str(c["id"]), twin) and "was paid on 19 Oct 2026" in paid["words"]
    still = {o["call"] for o in out["open"]}
    assert far in still and len(still) == 2 and paid["call"] not in still
    row = q(con, "select * from cash_movements where id = ?", paid["paid_row"])[0]
    assert row["confirmation_status"] == "confirmed" and row["supersedes_cash_movement_id"] == uuid.UUID(paid["call"]) and str(row["source_record_id"]) == sid
    assert q(con, "select confirmation_status from cash_movements where id = ?", paid["call"])[0]["confirmation_status"] == "noticed"  # the notice row keeps the notice's receipt
    assert RECON.match_calls(plane, date(2026, 10, 19))["paid"] == []  # a second run finds nothing new; the payment is spent
    # the one the payment did not settle (twin or c) is late on 26 October: one card, not two
    out = RECON.match_calls(plane, date(2026, 10, 26))
    assert len(out["cards"]) == 1
    card = q(con, "select * from exceptions where id = ?", out["cards"][0])[0]
    assert card["title"] == "Cedarpoint Ventures III call 7 not paid by 23 Oct 2026" and "Daniel Foo (Head of Finance)" in card["description"]
    assert RECON.match_calls(plane, date(2026, 10, 26))["cards"] == []
