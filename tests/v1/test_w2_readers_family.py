"""Readers of the family group (v3_pack_readers_family): tax calendar, tax notices, grant ledger, grant requests, trust deed, estate planning. Real readers on the
six-month office; expected numbers come from answer_keys.yaml or from the files. Synthetic data only."""
from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

from sh_platform.v1 import v3_pack_readers as PK

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, OFFICE = W2.key, W2.OFFICE
office = W2.office  # the module fixture: the office loaded through the real readers

KINDS = ["tax_calendar", "tax_notices", "grant_ledger", "grant_requests", "trust_deed", "estate_planning"]
ONE = {"tax_calendar": "2026-10/tax_calendar/tax_calendar_2026-27.xlsx", "tax_notices": "2026-10/tax_notices/eci_notice_EG-HOLD_2026.pdf",
       "grant_ledger": "2026-10/grant_ledger/grant_ledger_2026.xlsx", "grant_requests": "2026-10/grant_requests/grant_request_REQ-2026-06.pdf",
       "trust_deed": "2026-04/trust_deed/evergreen_family_trust_deed.pdf", "estate_planning": "2026-10/estate_planning/transfer_tax_memo_2026.pdf"}


def fields(office, dtype: str) -> list[dict]:
    return office.rows("select f.field_name, f.value_text, f.value_numeric from documents d join extracted_fields f on f.document_id = d.id where d.document_type = ? order by f.field_name", dtype)


def rule(office, code: str) -> dict:
    return json.loads(office.one("select v.parameters from business_rules b join rule_versions v on v.business_rule_id = b.id where b.rule_code = ? order by v.version_number desc limit 1", code))


def test_each_kind_is_recognised_from_its_content_not_its_name():
    for kind, rel in ONE.items():
        assert PK.kind_of("renamed" + Path(rel).suffix, (OFFICE / rel).read_bytes())[0] == kind


def test_every_kind_is_read_and_says_what_it_did(office):
    for kind in KINDS:
        r = office.report[kind]
        assert not r["not_loaded"] and r["files"] == len(list(OFFICE.glob(f"20??-??/{kind}/*"))) and r["rows"] > 0, (kind, r)


def test_tax_calendar_gives_the_obligations_the_key_lists_and_the_overdue_one(office):
    rows = office.rows("select o.*, e.entity_code from tax_obligations o join legal_entities e on e.id = o.legal_entity_id")
    assert len(rows) == 6
    k = key("uc-083-taxcal")
    soon = sorted(r["obligation_ref"] for r in rows if 0 <= (r["due_date"] - W2.date(2026, 10, 13)).days <= 60)
    assert soon == sorted(x["id"] for x in k["due_in_60_days"])
    late = [r for r in rows if r["due_date"] < W2.date(2026, 10, 13) and r["status"] not in ("filed", "paid")]
    assert [r["obligation_ref"] for r in late] == [x["id"] for x in k["overdue"]] and late[0]["entity_code"] == "EG-B"
    assert any("TX-04" in f and "13 days overdue" in f for f in office.report["tax_calendar"]["flagged"])
    assert office.one("select count(*) from exceptions where exception_type = 'tax_overdue'") == 1


def test_the_rates_are_rules_and_the_notice_agrees_with_the_calendar(office):
    k = key("uc-084-taxest")["by_entity"]
    for code, name in (("eg_hold", "Evergreen Holdings"), ("eg_trust", "Evergreen Family Trust"), ("eg_b", "Entity B")):
        assert rule(office, f"tax_rate_{code}") == {"income": k[name]["rate_on_income"], "realised_gain": k[name]["rate_on_gains"]}
    notice = {f["field_name"]: f for f in fields(office, "tax_notice")}
    assert notice["filing_due"]["value_text"] == "2026-11-30" and float(notice["tax_rate_income"]["value_numeric"]) == 0.17
    assert not office.report["tax_notices"]["flagged"]  # the notice and the calendar agree


def test_grant_ledger_is_paid_and_pledged_and_agrees_with_the_key(office):
    k = key("uc-085-grants")
    got = {r["status"]: float(r["a"]) for r in office.rows("select status, sum(amount) as a from grants where status in ('paid', 'pledged') group by status")}
    assert got == {"paid": k["paid"], "pledged": k["pledged"]}
    assert rule(office, "grant_budget")["annual"] == k["budget"]
    assert office.one("select count(*) from grants where status = 'paid' and (paid_on is null or payment_reference is null)") == 0
    assert office.one("select count(*) from grants where status = 'pledged' and paid_on is not null") == 0
    assert any(f["field_name"] == "planned_date" for f in fields(office, "grant_ledger"))  # a pledge's date has no column: a document field


def test_the_grant_request_is_one_requested_row_and_the_facts_against_the_policy_are_flagged(office):
    k = key("uc-086-grantappr")
    r = office.rows("select * from grants where status = 'requested'")
    assert len(r) == 1 and r[0]["grant_ref"] == k["request"] and float(r[0]["amount"]) == k["amount"] and r[0]["charity_registered_on"] == W2.date(2025, 3, 1)
    assert r[0]["requested_on"] == W2.date(2026, 10, 9)  # the day of the mail that carried it
    used = office.one("select sum(amount) from grants where status in ('paid', 'pledged')")
    assert float(Decimal(300000) - used) == k["remaining_budget"]
    flag = " ".join(office.report["grant_requests"]["flagged"])
    assert f"{k['charity_registered_months']} months" in flag and "35,000" in flag
    assert office.one("select count(*) from exceptions where exception_type = 'grant_request_over_budget'") == 1
    assert office.one("select count(*) from documents where original_filename like 'grant_request%'") == 1  # the mail's attachment is not read twice
    assert office.one("select count(*) from documents d join extracted_fields f on f.document_id = d.id where d.document_type = 'email' and f.field_name = 'attachment_document_id' "
                      "and d.original_filename like '%REQ-2026-06%'") == 1


def test_trust_deed_terms_are_fields_in_the_restricted_group(office):
    k = key("uc-087-trustdist")
    f = fields(office, "trust_deed")
    shares = {x["value_text"]: float(x["value_numeric"]) for x in f if x["field_name"] == "beneficiary_share"}
    assert shares == {n: v["share_pct"] / 100 for n, v in k["by_beneficiary"].items()}
    assert [float(x["value_numeric"]) for x in f if x["field_name"] == "payout_cap_pct"] == [k["payout_cap_pct"]]
    assert office.one("select g.group_name from documents d join access_groups g on g.id = d.access_group_id where d.document_type = 'trust_deed'") == "personal"
    assert not office.rows("select 1 from information_schema.tables where table_name = 'trust_deeds'")  # no table (A44)


def test_estate_memo_gives_the_exemption_and_rate_the_key_uses(office):
    k = key("uc-088-estateliq")
    f = {x["field_name"]: x for x in fields(office, "transfer_tax_memo")}
    assert float(f["estate_tax_exemption"]["value_numeric"]) == k["exemption"] and float(f["estate_tax_rate"]["value_numeric"]) == k["rate"]
    assert rule(office, "estate_tax_exemption")["amount"] == k["exemption"] and rule(office, "estate_tax_rate")["rate"] == k["rate"]
