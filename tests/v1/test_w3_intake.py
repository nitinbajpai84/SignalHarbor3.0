"""W3 intake: Harbor's own intake tries the family-office pack's readers (sh_platform/v1/v3_pack_readers.py) on every file of a thread before the generic
paths. A flat dropbox (no month or kind folders) of office6m files is recognised from content and name, loaded through the readers, and each kind's run
is recorded as skill data.read-<kind>. A file no reader knows stays on the generic path; a recognised file never goes both ways.

Real: the office6m files (tests/v1/fixtures/office6m), a company plane and its warehouse, Harbor's drop folder and file registry, the readers, the
skill log. The thread is a plain object (the chain's API calls are not needed to read files). Synthetic data only."""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_pack_readers as PK
from sh_platform.v1 import wh

OFFICE = Path(__file__).resolve().parent / "fixtures" / "office6m"
FOUR = ["2026-10/bank_statements/HB_HOLD_USD_2026-09.xlsx", "2026-10/custodian_positions/positions_20261013.csv", "2026-10/notices/2026-10-13_C_call7.pdf",
        "2026-10/invoices/2026-10-01_marina_MOS-2610.pdf"]
STANDING = ["reference/master_data.json", "reference/accounts.csv", "reference/standing_instructions.csv", "reference/vendor_master.csv", "reference/fund_terms.csv",
            "reference/office_rules.csv", "reference/EG_security_master_20261008.xlsx", "reference/Evergreen_Investment_Allocation_Policy_v2026.1.pdf"]
GENERIC = b"fund,units\nSome Fund,100\nOther Fund,250\n"


def flat_thread(tmp_path, names: list[str], extra: dict[str, bytes] | None = None):
    """A company whose dropbox holds the files flat; the standing data belongs to no thread, the others to thread t-w3."""
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("w3")
    H._fp(plane).parent.mkdir(parents=True, exist_ok=True)
    reg = []
    for rel in [*names, *STANDING]:
        H.drop(plane, Path(rel).name, (OFFICE / rel).read_bytes())
        mine = rel in names
        reg.append({"name": Path(rel).name, "arrived_at": "2026-10-13T08:00:00Z", "status": "recognised" if mine else "waiting", "source": "office files" if mine else "", "thread": "t-w3" if mine else None})
    for n, data in (extra or {}).items():
        H.drop(plane, n, data)
        reg.append({"name": n, "arrived_at": "2026-10-13T08:00:00Z", "status": "recognised", "source": "fund flows", "thread": "t-w3"})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")
    return plane, types.SimpleNamespace(app=None, plane=plane, th={"id": "t-w3", "intake": {}})


def rows(plane, sql, *a):
    with wh.connect(plane) as con:
        return con.execute(sql, list(a)).fetchall()


def test_the_recognised_kind_comes_from_content_and_name_not_the_folder():
    kinds = {Path(rel).name: PK.kind_of(Path(rel).name, (OFFICE / rel).read_bytes()) for rel in FOUR}
    assert [k[0] for k in kinds.values()] == ["bank_statements", "custodian_positions", "notices", "invoices"]
    assert PK.kind_of("fund_flows.csv", GENERIC) is None  # a table no reader knows
    assert PK.kind_of("renamed_by_the_bank.xlsx", (OFFICE / FOUR[0]).read_bytes())[0] == "bank_statements"  # the name is not what decides
    assert PK.kind_of("2026-10-13_internal_sam.eml", b"From: a\nSubject: b\n\nhi") is None  # emails stay documents (v3_docs)


def test_every_file_of_the_office_is_recognised_as_its_kind_from_a_flat_name():
    from tools.gen_office6m.more import NEW_KINDS  # the kinds of the other 49 cards wait for their readers
    NEW_KINDS = [k for k in NEW_KINDS if k not in ("custody_statements", "insurance_schedule", "property_valuations", "title_deeds")]  # read by v3_pack_readers_assets
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("payment_schedule", "income_calendar", "corporate_actions", "settlement_status", "tax_lots", "realised_lots", "manager_outlook"))  # read by v3_pack_readers_treasury
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("expense_ledger", "office_budget", "payroll_drafts", "sops", "access_register", "kyc_register", "onboarding", "bank_forms", "family_access", "glossary", "break_register", "load_log"))  # read by v3_pack_readers_controls from their content; inbox and new_feed are folders of unknown files, read by folder only
    NEW_KINDS = tuple(k for k in NEW_KINDS if k not in ("tax_calendar", "tax_notices", "grant_ledger", "grant_requests", "trust_deed", "estate_planning", "fund_holdings", "deal_pipeline", "fund_documents", "market_data", "target_allocation"))  # read by v3_pack_readers_family and v3_pack_readers_invest
    seen = {}
    for p in sorted(OFFICE.rglob("*")):
        rel = p.relative_to(OFFICE).parts
        if not p.is_file() or len(rel) < 2 or p.suffix in (".eml", ".md", ".txt") or rel[1] in NEW_KINDS:
            continue
        k = PK.kind_of(p.name, p.read_bytes())
        want = rel[1] if rel[0] != "reference" else None
        assert k is not None, p
        if want:
            assert k[0] == want, (p.name, k, want)
        seen.setdefault(k[0], 0)
        seen[k[0]] += 1
    assert {"bank_statements", "custodian_positions", "notices", "administrator_nav", "invoices", "payroll", "reference"} <= set(seen)


def test_a_flat_mix_loads_through_the_readers_and_the_rows_the_cash_recipes_need_exist(tmp_path):
    plane, x = flat_thread(tmp_path, FOUR, {"fund_flows.csv": GENERIC})
    PK.intake(x)
    # the four are marked for the pack; the generic table is not, and stays in the list the generic paths read
    assert {n: v["kind"] for n, v in x.th["pack"].items()} == {"HB_HOLD_USD_2026-09.xlsx": "bank_statements", "positions_20261013.csv": "custodian_positions",
                                                               "2026-10-13_C_call7.pdf": "notices", "2026-10-01_marina_MOS-2610.pdf": "invoices"}
    assert [f["name"] for f in H.my_files(x, "source")] == ["fund_flows.csv"] and "fund_flows.csv" not in x.th["intake"]
    assert x.th["intake"] == {}  # v3_pdf's load reads every PDF listed in th["intake"]: a pack file must never be listed there
    x.hide = set()
    assert len(H.my_files(x, "source")) == 5
    lines = {d["name"]: d for d in PK.d2_files(x)}
    assert lines["2026-10-13_C_call7.pdf"]["read_as"] == "capital call or distribution notice" and lines["HB_HOLD_USD_2026-09.xlsx"]["read_as"] == "bank statement"

    n, aside = PK.load(x)
    assert (n, aside) == (4, [])
    assert {f["name"]: f["status"] for f in H.read_files(plane)}["2026-10-13_C_call7.pdf"] == "loaded"

    # the rows: the call as a noticed movement and a document with its fields, the bank's balances and lines, the positions, the invoice and the payment it asks for
    call = rows(plane, "select m.amount, m.confirmation_status, m.notice_kind, m.due_date from cash_movements m where m.movement_type = 'call'")
    assert [(float(a), s, k, str(d)) for a, s, k, d in call] == [(-1250000.0, "noticed", "capital_call", "2026-10-23")]
    assert rows(plane, "select count(*) from extracted_fields f join documents d on d.id = f.document_id where d.document_type = 'capital_call_notice' and f.field_name in ('amount', 'bank_account')")[0][0] == 2
    assert rows(plane, "select count(*) from position_snapshots s join instruments i on i.id = s.instrument_id where i.instrument_type = 'cash' and s.position_date = date '2026-09-30'")[0][0] >= 1
    assert rows(plane, "select count(*) from position_snapshots s join instruments i on i.id = s.instrument_id where i.instrument_type = 'listed_equity' and s.position_date = date '2026-10-13'")[0][0] > 5
    assert rows(plane, "select count(*) from documents where document_type = 'invoice'")[0][0] == 1
    assert rows(plane, "select count(*) from cash_movements where movement_type = 'payment' and confirmation_status = 'expected'")[0][0] >= 2  # the call and the invoice, both still to pay
    assert rows(plane, "select count(*) from legal_entities where entity_code = 'EG-HOLD'")[0][0] == 1  # the standing data was read once, from the dropbox

    # each kind ran as its own skill
    from sh_platform.v1 import v3_skills as S
    runs = [json.loads(line) for line in S._runs_path(plane).read_text(encoding="utf-8").splitlines()]
    got = {r["skill"] for r in runs if r["thread"] == "t-w3"}
    assert {"data.read-bank-statement", "data.read-custodian-positions", "data.read-notice", "data.read-invoice"} <= got and all(r["ok"] for r in runs)

    # the same files again are not read twice
    before = rows(plane, "select count(*) from cash_movements")[0][0]
    assert PK.load(x) == (4, []) and rows(plane, "select count(*) from cash_movements")[0][0] == before


def test_a_file_that_will_not_read_is_set_aside_and_the_others_still_load(tmp_path):
    plane, x = flat_thread(tmp_path, FOUR[1:])
    head = (OFFICE / FOUR[1]).read_text(encoding="utf-8").splitlines()[0]
    broken = head + "\n2026-10-13,NO-SUCH-BOOK,Anchorage Custody (synthetic),SEC-X,X.SYN,Nothing,listed_equity,1,1,1,USD\n"  # a positions file for a book the office does not have
    H.drop(plane, "positions_20261014.csv", broken.encode())
    reg = json.loads(H._fp(plane).read_text(encoding="utf-8"))
    reg.append({"name": "positions_20261014.csv", "arrived_at": "2026-10-14T08:00:00Z", "status": "recognised", "source": "office files", "thread": "t-w3"})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")
    PK.intake(x)
    assert len(x.th["pack"]) == 4
    n, aside = PK.load(x)
    assert n == 3 and [a["title"] for a in aside] == ["positions_20261014.csv did not load"] and "NO-SUCH-BOOK" in aside[0]["text"]
    assert {f["name"]: f["status"] for f in H.read_files(plane)}["positions_20261014.csv"] == "question"
    assert rows(plane, "select count(*) from cash_movements where movement_type = 'call'")[0][0] == 1  # the notice still loaded


def test_without_the_offices_standing_data_the_files_are_set_aside_in_plain_words(tmp_path):
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("w3b")
    H._fp(plane).parent.mkdir(parents=True, exist_ok=True)
    H.drop(plane, "2026-10-13_C_call7.pdf", (OFFICE / FOUR[2]).read_bytes())
    H._fp(plane).write_text(json.dumps([{"name": "2026-10-13_C_call7.pdf", "arrived_at": "2026-10-13T08:00:00Z", "status": "recognised", "source": "calls", "thread": "t-w3"}]), encoding="utf-8")
    x = types.SimpleNamespace(app=None, plane=plane, th={"id": "t-w3", "intake": {}})
    PK.intake(x)
    n, aside = PK.load(x)
    assert n == 0 and "standing data" in aside[0]["text"]
    assert rows(plane, "select count(*) from cash_movements")[0][0] == 0


def test_the_old_module_name_still_answers(tmp_path):
    from sh_platform.v1 import v3_office6m_loaders as old
    assert old.load_plane is PK.load_plane and old.parse_date is PK.parse_date


def test_files_arriving_in_later_batches_do_not_write_the_standing_data_again(tmp_path):
    plane, x = flat_thread(tmp_path, FOUR[:2])
    PK.intake(x)
    assert PK.load(x) == (2, [])
    count = lambda sql: rows(plane, sql)[0][0]  # noqa: E731
    first = [count(f"select count(*) from {t}") for t in ("bank_accounts", "source_systems", "business_rules", "rule_versions", "instruments", "legal_entities", "portfolios")]
    assert first[0] > 12 and first[1] > 1  # the twelve office accounts and the fund payees are there once

    reg = json.loads(H._fp(plane).read_text(encoding="utf-8"))
    for rel in FOUR[2:]:  # the month's other two files arrive and belong to the thread
        H.drop(plane, Path(rel).name, (OFFICE / rel).read_bytes())
        reg.append({"name": Path(rel).name, "arrived_at": "2026-10-13T08:00:00Z", "status": "recognised", "source": "office files", "thread": "t-w3"})
    H._fp(plane).write_text(json.dumps(reg), encoding="utf-8")
    x.hide = set()  # a_intake lets go of the files once the generic paths have run
    PK.intake(x)
    assert PK.load(x) == (4, [])  # the two first files are found already read; the new two are read
    after = [count(f"select count(*) from {t}") for t in ("bank_accounts", "source_systems", "business_rules", "rule_versions", "instruments", "legal_entities", "portfolios")]
    assert after[0] >= first[0] and after[2:] == first[2:]  # rules, instruments, entities, portfolios: as they were; a bank account only if the notice names a new payee
    assert count("select count(*) - count(distinct source_code) from source_systems") == 0 and after[1] >= first[1]  # a source system once, new ones only for the new kinds
    assert count("select count(*) from bank_accounts where holder_kind = 'office'") == 12
    assert count("select count(*) from cash_movements where movement_type = 'call'") == 1
    assert count("select count(*) from documents where document_type = 'policy'") == 1
