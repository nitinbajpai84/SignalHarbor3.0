"""Checks on the Evergreen Office six-month data set (tools/gen_office6m, tests/v1/fixtures/office6m).

1. two runs give byte-identical output (and the committed fixtures are what the generator makes today),
2. the UC01 numbers hold, read from the generated files themselves,
3. every planted mess item listed in the manifest exists in the files,
4. every top-50 use case (and the role-build uc8) has at least one input file and one answer key,
5. size and file count stay in bounds.
"""
import csv
import hashlib
import re
from pathlib import Path

import openpyxl
import pytest
import yaml
from pypdf import PdfReader

from tools.gen_office6m.__main__ import main as generate_main

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "v1" / "fixtures" / "office6m"
PACK = ROOT / "packs" / "family_office" / "1" / "use_cases_100.yaml"


def digest(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    a, b = tmp_path_factory.mktemp("office6m_a") / "office6m", tmp_path_factory.mktemp("office6m_b") / "office6m"
    generate_main(["--out", str(a)])
    generate_main(["--out", str(b)])
    return a, b


def test_two_runs_are_byte_identical(runs):
    a, b = runs
    da, db = digest(a), digest(b)
    assert da.keys() == db.keys() and len(da) > 700
    assert [k for k in da if da[k] != db[k]] == []


def test_committed_fixtures_are_current(runs):
    assert FIX.is_dir(), "run: python -m tools.gen_office6m"
    a, _ = runs
    da, df = digest(a), digest(FIX)
    assert da.keys() == df.keys(), sorted(set(da) ^ set(df))[:5]
    assert [k for k in da if da[k] != df[k]] == [], "fixtures are stale: python -m tools.gen_office6m"


def test_size_and_counts():
    files = [p for p in FIX.rglob("*") if p.is_file()]
    assert sum(p.stat().st_size for p in files) < 60 * 1024 * 1024
    kinds = {}
    for p in files:
        if re.fullmatch(r"\d{4}-\d{2}", p.relative_to(FIX).parts[0]):
            kinds[p.parent.name] = kinds.get(p.parent.name, 0) + 1
    for k, n in {"bank_statements": 80, "custodian_positions": 130, "manager_statements": 50, "notices": 15, "invoices": 20, "fx_rates": 100, "payroll": 6, "investment_reports": 12}.items():
        assert kinds.get(k, 0) >= n, (k, kinds.get(k))
    assert sorted(p.name for p in FIX.iterdir() if re.fullmatch(r"\d{4}-\d{2}", p.name)) == [f"2026-{m:02d}" for m in range(4, 11)]


def rows(xlsx, sheet):
    return list(openpyxl.load_workbook(xlsx, data_only=True)[sheet].iter_rows(values_only=True))


def pdf_text(p):
    return "\n".join(pg.extract_text() for pg in PdfReader(str(p)).pages)


def closing(entity, ccy, day):
    """Sum of the closing ledger balances of an entity's accounts in one currency, read from the October bank statements."""
    tot = 0
    for f in sorted(FIX.glob(f"2026-10/bank_statements/*_{entity}_{ccy}_2026-10_mtd.xlsx")):
        tot += next(r[5] for r in rows(f, "Daily balances")[1:] if r[0] == day)
    return tot


def keys():
    return yaml.safe_load((FIX / "answer_keys.yaml").read_text(encoding="utf-8"))["keys"]


def test_uc01_numbers_from_the_files():
    assert closing("HOLD", "USD", "2026-10-13") == pytest.approx(1230000)
    assert closing("HOLD", "SGD", "2026-10-13") == pytest.approx(1600000)
    notice = pdf_text(next(FIX.glob("2026-10/notices/2026-10-13_C_call7.pdf")))
    assert "USD 1,250,000.00" in notice and "23 October 2026" in notice and "SYN-0000-4471" in notice
    assert "Total commitment                 USD 10,000,000.00" in notice and "USD 7,250,000.00" in notice and "USD 2,750,000.00" in notice
    fx = float(list(csv.reader(open(FIX / "2026-10/fx_rates/fx_usdsgd_20261013.csv")))[1][3])
    shortfall = 1250000 + 250000 - closing("HOLD", "USD", "2026-10-13")
    assert shortfall == pytest.approx(270000) and round(shortfall * fx, 2) == 361800
    reg = rows(FIX / "2026-10/commitments/commitments_register_2026-10-13.xlsx", "Register")
    c = next(r for r in reg if r[3] == "C")
    assert c[5] == 10000000 and c[7] == 6000000 and c[9] == 1250000  # 6,000,000 called before call 7; call 7 noticed, not yet recorded
    assert c[5] - c[7] - c[9] == 2750000
    k = keys()
    q = k["uc-002-callrecord"]["questions"]["Does call 7 fit what we committed to Cedarpoint Ventures III, and what is left after it?"]["expected"]
    assert q["called_before_call_7"] == 6000000 and q["unfunded_after_call_7"] == 2750000
    q4 = k["uc-004-callcheck"]["questions"]["Can Holdings pay the Cedarpoint call on the 23rd?"]["expected"]
    assert q4["holdings_usd"] == 1230000 and q4["holdings_sgd"] == 1600000 and q4["shortfall_usd"] == 270000 and q4["sgd_to_convert"] == 361800
    cb = k["uc-005-benefcheck"]["questions"]["Cedarpoint now says to wire to an account ending 4471. Is that really them?"]["expected"]
    assert (cb["old_ending"], cb["new_ending"]) == ("2209", "4471")
    # calls 5 and 6 in April and July, paid to the account ending 2209, in the Holdings bank statements
    paid = [r for f in sorted(FIX.glob("*/bank_statements/HB_HOLD_USD_2026-0*.xlsx")) for r in rows(f, "Transactions")[1:] if r[2] == "capital_call" and "Cedarpoint Ventures III" in r[3]]
    assert [(r[0], r[5]) for r in paid] == [("2026-04-21", -1000000.0), ("2026-07-21", -1500000.0)] and all(r[3].endswith("ACCT 2209") for r in paid)


def mess_ids():
    return sorted(set(re.findall(r"^\| (M\d+[a-z]?) \|", (FIX / "MANIFEST.md").read_text(encoding="utf-8"), re.M)))


def tx(entity, ccy, month):
    out = []
    for f in sorted(FIX.glob(f"*/bank_statements/*_{entity}_{ccy}_{month}.xlsx")):
        out += rows(f, "Transactions")[1:]
    return out


def one(pattern):
    hits = sorted(FIX.glob(pattern))
    assert hits, pattern
    return hits[0]


def check_M01():
    late = [r for r in csv.DictReader(open(FIX / "received_log_all.csv")) if r["kind"] == "manager_statement" and r["status"] == "late"]
    assert len(late) >= 3


def check_M02():
    miss = [r for r in csv.DictReader(open(FIX / "received_log_all.csv")) if r["kind"] == "manager_statement" and r["status"] == "never received"]
    assert len(miss) == 1 and miss[0]["period"] == "2026-06-30" and "D_2026-06-30" in miss[0]["file"]
    assert not list(FIX.glob("*/manager_statements/cedarpoint_D_2026-06-30_*.pdf"))


def check_M02a():
    r = next(r for r in csv.DictReader(open(FIX / "received_log_all.csv")) if "HB_TRUST_SGD_2026-05" in r["file"])
    assert r["status"] == "late" and r["received_on"] > r["expected_on"]


def check_M02b():
    assert not list(FIX.glob("*/bank_statements/TCB_B_USD_2026-07.xlsx"))
    assert any(r["status"] == "never received" and r["kind"] == "bank_statement" for r in csv.DictReader(open(FIX / "received_log_all.csv")))


def check_M03():
    assert sorted(p.name for p in FIX.glob("*/manager_statements/*_amended.pdf")) == ["cedarpoint_C_2026-06-30_amended.pdf", "kestrel_H1_2026-07-31_amended.pdf", "northgate_A_2026-09-30_amended.pdf"]
    assert "10,180,000.00" in pdf_text(one("*/manager_statements/northgate_A_2026-09-30_amended.pdf"))


def check_M04():
    adm = {(r["date"], r["entity_code"], r["currency"]): float(r["administrator_cash"]) for r in csv.DictReader(open(one("2026-10/administrator_cash/administrator_cash_2026-10_mtd.csv")))}
    bank = closing("B", "USD", "2026-10-08")
    assert bank == pytest.approx(868000) and adm[("2026-10-08", "EG-B", "USD")] == pytest.approx(880400)
    assert adm[("2026-10-08", "EG-B", "USD")] - bank > 5000


def check_M05a():
    assert "SYN-0000-4471" in pdf_text(one("2026-10/notices/2026-10-13_C_call7.pdf"))
    si = {r["fund_key"]: r for r in csv.DictReader(open(FIX / "reference/standing_instructions.csv"))}
    assert si["C"]["account_last4"] == "2209" and si["C"]["callback_number"]


def check_M05b():
    assert "6029" in pdf_text(one("2026-08/invoices/2026-08-28_lakeside_LL-2026-0828.pdf"))
    assert {r["vendor"]: r["account_last4"] for r in csv.DictReader(open(FIX / "reference/vendor_master.csv"))}["Lakeside Legal LLP"] == "3047"


def check_M06():
    dup = [p for p in FIX.glob("*/invoices/*orchard*INV-OIT-2606*.pdf")]
    assert len(dup) == 2 and len({"INV-OIT-2606 " + re.search(r"Amount due: (.*)", pdf_text(p)).group(1) for p in dup}) == 1


def check_M07():
    day = next(p for p in sorted(FIX.glob("*/trading_export/trading_export_2026*.csv")) if "-R," in p.read_text())
    ids = [r["external_trade_id"] for r in csv.DictReader(open(day))]
    base = next(i for i in ids if i.endswith("-R"))[:-2]
    assert base in ids


def check_M08():
    t = pdf_text(one("2026-06/notices/2026-06-10_G_call3.pdf"))
    assert "28,125.00" in t
    terms = {r["fund_key"]: r for r in csv.DictReader(open(FIX / "reference/fund_terms.csv"))}["G"]
    assert float(terms["commitment_usd"]) * float(terms["fee_pct_of_commitment_per_billing"]) / 100 == pytest.approx(18750)


def check_M09():
    assert not list(FIX.glob("*/fx_confirmations/FXS-20260602-HOLD*"))
    assert list(FIX.glob("*/fx_confirmations/FXS-20260416-HOLD*"))
    assert any("FX-FXS-20260602-HOLD" in p.read_text() for p in FIX.glob("2026-06/trading_export/trading_export_20260602.csv"))
    assert any(r[1] == "FXS-20260602-HOLD" for r in tx("HOLD", "USD", "2026-06"))


def check_M10():
    assert "sell USD / buy SGD" in one("2026-10/trading_export/trading_export_20261005.csv").read_text()


def check_M11a():
    first = open(one("2026-08/custodian_transactions/transactions_2026-07.csv")).read().splitlines()[1].split(",")[0]
    assert re.fullmatch(r"\d\d/\d\d/\d{4}", first)


def check_M11b():
    assert "09/24/2026" in pdf_text(one("2026-09/notices/2026-09-10_K_distribution.pdf"))


def check_M12():
    r = rows(one("*/loan_statements/loan_statement_TL-B-01_2026-09.xlsx"), "Loan")[1]
    assert r[5] == -2800000


def check_M13():
    ap = list(csv.DictReader(open(FIX / "2026-08/approvals/approvals_2026-08.csv")))
    assert [r["payment_ref"] for r in ap if not r["approved_by"]] == ["CC-CALL-F-2"] and all(float(r["amount_usd"]) > 500000 for r in ap)


def check_M14():
    assert not list(FIX.glob("2026-06/fx_rates/fx_usdsgd_20260603.csv")) and list(FIX.glob("2026-06/fx_rates/fx_usdsgd_20260602.csv")) and list(FIX.glob("2026-06/fx_rates/fx_usdsgd_20260604.csv"))


def check_M15():
    t = pdf_text(one("2026-10/invoices/2026-10-05_cust_FEE-CUST-Q3.pdf"))
    assert "6,180.00" in t and "0.06%" in t


def check_M16():
    rows_ = list(csv.DictReader(open(one("2026-10/administrator_trades/administrator_trades_2026-10.csv"))))
    assert {r["external_trade_id"]: r["administrator_quantity"] for r in rows_}["T-20261002-003"] == "10200.0"
    assert "T-20261006-005" not in {r["external_trade_id"] for r in rows_}
    assert "1.3452" in pdf_text(one("2026-10/fx_confirmations/FXF-2026-002_confirmation.pdf"))


def check_M17():
    assert any(r["security_id"] == "SEC-PRC29" and r["asset_class"] == "" for r in csv.DictReader(open(one("2026-09/custodian_positions/positions_20260930.csv"))))


def check_M18():
    h = lambda f: [c.value for c in next(openpyxl.load_workbook(f)["Positions"].iter_rows(min_row=1, max_row=1))]
    assert "Valuation Amount (USD)" in h(one("*/administrator_nav/administrator_export_2026-06.xlsx")) and "Market Value" in h(one("*/administrator_nav/administrator_export_2026-05.xlsx"))


def check_M19():
    assert "275,000.00" in pdf_text(one("2026-07/notices/2026-07-07_A_distribution.pdf"))
    assert any(r[1].startswith("DI-DIST-A") and r[5] == 262500 for r in tx("HOLD", "USD", "2026-07"))


def check_M19b():
    assert not [r for r in tx("TRUST", "USD", "2026-09") if "Ethan" in r[3]] and [r for r in tx("TRUST", "USD", "2026-09") if "Wen Chen" in r[3]]


def check_M20():
    items = rows(one("2026-09/audit/audit_request_2026-09-22.xlsx"), "Sample")[1:]
    assert len(items) == 8 and items[-1][4] == "no" and items[-1][3] == 9500000


def check_M21():
    a, b = pdf_text(one("*/ddq/cedarpoint_ddq_2025.pdf")).splitlines(), pdf_text(one("*/ddq/cedarpoint_ddq_2026.pdf")).splitlines()
    assert sum(1 for x, y in zip(a[3:11], b[3:11]) if x != y) == 5


def csvrows(pattern):
    return list(csv.DictReader(open(one(pattern), encoding="utf-8")))


def check_M22():
    assert any("TT IN REF 7741XQ" in r[3] and r[5] == 48250 for r in tx("HOLD", "USD", "2026-08"))
    assert any("ACH DEBIT MERCHANT 55201" in r[3] for r in tx("HOLD", "USD", "2026-09")) and any("CHEQUE 000417" in r[3] for r in tx("B", "USD", "2026-10_mtd"))


def check_M23():
    r = csvrows("2026-10/settlement_status/settlement_report_2026-10-13.csv")
    assert [x["trade_ref"] for x in r if x["status"] == "failed"] == ["BR2-20261002-001", "BR2-20261007-002"] and all(x["cash_booked"] == "no" for x in r if x["status"] == "failed")


def check_M24():
    t = pdf_text(one("2026-10/custody_statements/custody_statement_2026-09-30.pdf"))
    assert "Note BSU" in t and "+1,250" in t and "Note RWP" in t and "-400" in t


def check_M25():
    pos = {r["security_id"]: float(r["price"]) for r in csv.DictReader(open(one("2026-09/custodian_positions/positions_20260930.csv")))}
    sec = {(r["date"], r["security_id"]): float(r["price"]) for r in csvrows("2026-10/market_data/second_source_prices_*.csv")}
    assert abs(pos["SEC-KFT"] / sec[("2026-09-30", "SEC-KFT")] - 1) > 0.005 and abs(pos["SEC-KFB30"] / sec[("2026-09-30", "SEC-KFB30")] - 1) > 0.005 and abs(pos["SEC-HVS"] / sec[("2026-09-30", "SEC-HVS")] - 1) < 0.005


def check_M26():
    r = csvrows("2026-10/break_register/break_register_2026-10-13.csv")
    assert len(r) == 6 and {x["status"] for x in r} == {"open"} and min(x["detected_on"] for x in r) == "2026-06-05"


def check_M27():
    assert sorted(p.name for p in FIX.glob("2026-10/inbox/*")) == ["IMG_2210.pdf", "INV-OIT-2610.pdf", "account_extract.xlsx", "data_export.xlsx", "scan_0412.pdf"]


def check_M28():
    assert "20 August 2024" in pdf_text(one("2026-04/property_valuations/valuation_RA-03_2024-08-20.pdf")) and "30 September 2025" in pdf_text(one("2026-04/property_valuations/valuation_RA-05_2025-09-30.pdf"))


def check_M29():
    assert "Registered proprietor: Lin Chen" in pdf_text(one("2026-04/title_deeds/title_deed_RA-04.pdf")) and "Evergreen Holdings" in pdf_text(one("2026-04/title_deeds/title_deed_RA-01.pdf"))


def check_M30():
    t = pdf_text(one("2026-10/insurance_schedule/insurance_schedule_2026-10-01.pdf"))
    assert "POL-ART-02" in t and "sum insured USD 2,000,000.00" in t and "RA-02" not in t


def check_M31():
    r = rows(one("2026-10/fund_holdings/fund_holdings_2026-09-30.xlsx"), "Holdings")[1:]
    assert sorted(x[0] for x in r if x[2] == "Helix Cloud Systems") == ["A", "C", "F"] and sorted(x[0] for x in r if x[2] == "Harborview Semiconductor") == ["A", "C"]


def check_M32():
    d_ = {r[0]: r[2] for r in rows(one("2026-10/payroll_drafts/payroll_run_2026-10_draft.xlsx"), "Draft")[1:]}
    s_ = {r[0]: r[2] for r in rows(one("2026-09/payroll/payroll_2026-09.xlsx"), "Payroll")[1:]}
    assert "Jun Tan (contractor)" in d_ and "Jun Tan (contractor)" not in s_ and d_["Grace Ong"] == pytest.approx(s_["Grace Ong"] * 1.2)


def check_M33():
    r = {x[0]: x for x in rows(one("2026-10/tax_calendar/tax_calendar_2026-27.xlsx"), "Obligations")[1:]}
    assert r["TX-04"][3] == "2026-09-30" and r["TX-04"][7] == "not filed"


def check_M34():
    t = pdf_text(one("2026-10/grant_requests/grant_request_REQ-2026-06.pdf")); g = rows(one("2026-10/grant_ledger/grant_ledger_2026.xlsx"), "Grants")[1:]
    assert "USD 50,000.00" in t and "1 March 2025" in t and sum(r[3] for r in g) == 265000


def check_M35():
    f = one("2026-10/expense_ledger/expense_ledger_2026-04_to_2026-09.xlsx"); led = rows(f, "Ledger")[1:]; lim = dict(rows(f, "Approval limits")[1:])
    assert sorted(r[7] for r in led if r[6] > lim[r[8]]) == ["BAL-2026-051", "LL-2026-0708"]


def check_M36():
    r = csvrows("2026-10/access_register/access_register_2026-10-13.csv")
    assert sorted((x["person"], x["system"]) for x in r if not x["approved_by"]) == [("Sam Lee", "OMS"), ("Wei Tan", "Harbour Bank portal")] and len([x for x in r if x["person"] == "J. Ng"]) == 3
    assert sum(1 for x in r if x["last_used"] < "2026-07-15" and x["person"] != "J. Ng") == 3 and list(FIX.glob("2026-10/access_register/*.eml"))


def check_M37():
    r = csvrows("2026-10/onboarding/onboarding_checklist_Harborlight.csv")
    assert [x["item"][:12] for x in r if x["status"] == "missing"] == ["Bank details", "Statement sc"]


def check_M38():
    t = pdf_text(one("2026-10/bank_forms/account_opening_form_TCB_TRUST_EUR.pdf"))
    assert "Raj Patel" in t and "Grace Ong" in t and "Daniel Foo" not in t and "Head of Finance" in pdf_text(one("2026-10/bank_forms/signing_policy_2026.pdf"))


def check_M39():
    old = [p.name for p in sorted(FIX.glob("2026-10/sops/*.md")) if re.search(r"Last reviewed: (\d{4}-\d\d-\d\d)", p.read_text()).group(1) < "2025-10-13"]
    assert old == ["sop_new-bank-account.md", "sop_payroll-release.md", "sop_vendor-payment-run.md"]


def check_M40():
    r = csvrows("2026-10/kyc_register/kyc_register_2026-10-13.csv")
    assert sum(1 for x in r if x["expires"] < "2026-10-13") == 1 and sum(1 for x in r if "2026-10-13" <= x["expires"] <= "2027-01-11") == 3


def check_M41():
    e = one("2026-10/glossary/2026-10-06_word_proposal.eml").read_text()
    terms = " ".join(r["term"] + " " + r["aliases"] for r in csvrows("2026-10/glossary/office_words_2026-10-01.csv"))
    assert "dry powder" in e and "dry powder" in terms and "stub period" not in terms and "stub period" in one("2026-10/glossary/word_review_2026-10-08.md").read_text()


def check_M42():
    h = open(one("2026-10/new_feed/pinnacle_custody_positions_2026-10-12.csv")).readline().strip().split(",")
    assert len(h) == 10 and "Value" in h and "Dt" in h


def check_M43():
    r = csvrows("2026-10/family_access/family_view_grants_2026-10-13.csv")
    assert {"member": "Wen Chen", "entity": "EG-B", "level": "full", "granted_on": "2026-01-15"} in r and "Wen Chen: Evergreen Holdings none, Evergreen Family Trust summary, Entity B none" in pdf_text(one("2026-10/family_access/family_access_policy_2026.pdf"))


def check_M44():
    assert len(list(FIX.glob("*/manager_news/*.eml"))) == 2 and "resigned" in one("2026-08/manager_news/2026-08-18_saltmarsh_personnel.eml").read_text()


def check_M45():
    assert "Respond by: 22 October 2026" in pdf_text(one("2026-10/corporate_actions/2026-10-08_TWE_tender_offer.pdf")) and "mandatory" in pdf_text(sorted(FIX.glob("2026-10/corporate_actions/*_dividend.pdf"))[0])


def check_M46():
    r = {x["deal"]: x for x in csvrows("2026-10/deal_pipeline/deal_pipeline_2026-10-13.csv")}
    assert r["DL-02"]["stage_entered"] == "2026-07-28" and r["DL-04"]["stage_entered"] == "2026-06-15"


def check_M47():
    assert "Wen Chen 8 percent" in pdf_text(one("2026-04/trust_deed/evergreen_family_trust_deed.pdf"))


MESS_CHECKS = {k[len("check_"):]: v for k, v in dict(globals()).items() if k.startswith("check_M")}


def test_every_mess_id_in_the_manifest_has_a_check():
    assert mess_ids() == sorted(MESS_CHECKS), set(mess_ids()) ^ set(MESS_CHECKS)


@pytest.mark.parametrize("mid", sorted(MESS_CHECKS))
def test_planted_mess_exists(mid):
    MESS_CHECKS[mid]()


def top50():
    y = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    return [u["id"] for u in sorted((u for u in y["use_cases"] if u.get("priority") and u["priority"] <= 50), key=lambda u: u["priority"])]


def test_top50_have_inputs_and_keys():
    ids, k = top50(), keys()
    assert len(ids) == 50
    for i in ids + ["uc8-trades-vs-admin"]:
        assert i in k, f"no answer key for {i}"
        assert k[i]["questions"], i
        hits = [p for g in k[i]["input_files"] for p in FIX.glob(g)]
        assert hits, f"no input file for {i}: {k[i]['input_files']}"
        for q in k[i]["questions"].values():
            assert q["expected"] is not None and q["how"], i


def test_old_keys_still_hold():
    k = keys()
    assert k["uc1-why-nav-moved"]["questions"]["Why did Fund A move since the issued September report?"]["expected"]["amended"] == 10180000
    b = k["uc4-vs-benchmark"]["questions"]["How did the liquid portfolio do against the benchmark in September 2026?"]["expected"]
    assert (b["portfolio_return_pct"], b["benchmark_return_pct"]) == (4.1667, 2.7072)
    assert k["morning-networth-note"]["questions"]["What are we worth in the latest report?"]["expected"]["total_usd"] == 57600000
    assert k["uc6-uncalled"]["questions"]["How much is uncalled across all commitments?"]["expected"]["uncalled_after_call_7"] == 14600000
    brk = k["uc2-recon-break-desk"]["questions"]["Which entity has a cash break on 8 October and by how much?"]["expected"]
    assert (brk["entity"], brk["difference"]) == ("Entity B", 12400)
    assert k["uc5-limits"]["questions"]["Which holding is over its single-name limit?"]["expected"]["pct_of_portfolio"] == 5.75
    assert k["uc3-statements-inbox"]["questions"]["Which statement is missing and how overdue is it?"]["expected"]["missing"][0]["business_days_overdue_9_oct"] == 63


def test_other_cards_have_inputs_and_keys():
    y = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    others = [u["id"] for u in y["use_cases"] if not (u.get("priority") and u["priority"] <= 50)]
    assert len(others) == 50
    k = keys()
    for i in others:
        assert i in k, f"no answer key for {i}"
        assert k[i]["questions"], i
        assert [p for g in k[i]["input_files"] for p in FIX.glob(g)], f"no input file for {i}: {k[i]['input_files']}"
        for q in k[i]["questions"].values():
            assert q["expected"] is not None and q["how"], i
    assert len(k) == 101  # the 100 cards plus uc-101-ownership (A61)


def test_signed_rules_of_cards_51_to_100_agree_with_the_keys():
    """A48 onward: every rule a card 51-100 needs is signed in reference/office_rules.csv with the value its answer key already uses."""
    import json
    rows = list(csv.DictReader((FIX / "reference" / "office_rules.csv").open(encoding="utf-8")))
    signed = {r["rule"]: json.loads(r["parameters"]) for r in rows if r["approval_status"] == "approved" and r["parameters"]}
    ex = lambda cid: next(iter(keys()[cid]["questions"].values()))["expected"]  # noqa: E731
    assert {k[len("approver_limit_"):]: v["limit"] for k, v in signed.items() if k.startswith("approver_limit_")} == {n.lower().replace(" ", "_"): v for n, v in ex("uc-089-expapp")["limits"].items()}
    assert {k: v["annual"] for k, v in signed.items() if k.startswith("office_budget_")} == {"office_budget_" + re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_"): 2 * v["budget_half_year"] for c, v in ex("uc-090-offcost")["by_category"].items()}
    fc = ex("uc-072-cashfc")
    assert (signed["forecast_call_assumption"]["amount"], signed["forecast_floor"]["amount"]) == (fc["monthly_call_assumption"], fc["floor"])
    assert signed["price_tolerance_pct"]["max_pct"] == ex("uc-057-pricecheck")["tolerance_pct"]
    assert {k: signed["manager_score_weights"][k] for k in ("returns", "fees", "timeliness", "watch")} == ex("uc-076-scorecard")["weights"]
    allowed = {(m, e): lv for m, v in ex("uc-100-famaccess")["by_member"].items() for e, lv in v["allowed"].items()}
    assert sum(1 for k, v in signed.items() if k.startswith("family_access_") and v["level"] != "none") == len(allowed) and all(v["level"] in ("none", "summary", "full") for k, v in signed.items() if k.startswith("family_access_"))
    assert signed["signing_policy"] == {"min_signatories": 2, "required_role": "Head of Finance"} and signed["ladder_window_days"] == {"days": 90} and signed["automation_rework_minutes"]["minutes_per_failure"] == 45
    assert not any(k.startswith("allocation_") for k in signed), "the interim targets of card 79 are proposed, not signed (its key says so)"
    deals = ex("uc-077-deals")["deals"]  # A55: the stage limit of card 77; stuck exactly when the days in stage are above it
    assert all(d["stuck"] == (d["days_in_stage"] > signed["deal_stage_limit_days"]["days"]) for d in deals) and signed["deal_stage_limit_days"] == {"days": 60}


def test_signed_family_rules_of_cards_86_and_88_agree_with_the_keys():
    """A54: the charity age of card 86 and the transfer tax of card 88 are signed with the values their answer keys use."""
    import json
    rows = list(csv.DictReader((FIX / "reference" / "office_rules.csv").open(encoding="utf-8")))
    signed = {r["rule"]: json.loads(r["parameters"]) for r in rows if r["approval_status"] == "approved" and r["parameters"]}
    ex = lambda cid: next(iter(keys()[cid]["questions"].values()))["expected"]  # noqa: E731
    assert signed["grant_min_charity_months"] == {"months": ex("uc-086-grantappr")["required_months"]}
    assert signed["estate_tax_exemption"] == {"amount": ex("uc-088-estateliq")["exemption"], "currency": "USD"} and signed["estate_tax_rate"] == {"rate": ex("uc-088-estateliq")["rate"]}
    by = ex("uc-084-taxest")["by_entity"]  # A57: the 2026 tax rates of card 84, signed v2 with the values its key uses
    for code, name in (("eg_hold", "Evergreen Holdings"), ("eg_trust", "Evergreen Family Trust"), ("eg_b", "Entity B")):
        assert signed[f"tax_rate_{code}"] == {"income": by[name]["rate_on_income"], "realised_gain": by[name]["rate_on_gains"]}
