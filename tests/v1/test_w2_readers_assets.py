"""W2 readers, assets group (cards 52, 56, 65, 66, 82, 88): property valuations, title deeds, the insurance schedule and the custody statement are read by
the real pack readers from the office6m folders and compared with the answer keys (read from the file, never typed here). Nothing is stubbed. Synthetic data only."""
from __future__ import annotations

from decimal import Decimal

from sh_platform.v1 import v3_pack_readers as PK
from tests.v1.test_w2_loader import OFFICE, f2, key, office  # noqa: F401 - the office fixture loads the folders through the real loader

HEADS = ("select r.asset_ref, r.asset_name, r.asset_type, r.appraised_value, r.currency, r.appraised_on, r.title_holder_name, e.entity_name from real_assets r "
         "left join legal_entities e on e.id = r.legal_entity_id where not exists (select 1 from real_assets x where x.supersedes_real_asset_id = r.id) order by r.asset_ref")


def test_the_four_kinds_are_recognised_from_content_alone():
    for kind, folder in (("property_valuations", "2026-04"), ("title_deeds", "2026-04"), ("insurance_schedule", "2026-10"), ("custody_statements", "2026-10")):
        p = next((OFFICE / folder / kind).glob("*.pdf"))
        assert PK.kind_of("renamed_by_someone.pdf", p.read_bytes()) == (kind, "renamed_by_someone.pdf")


def test_every_file_of_the_four_kinds_is_read_and_none_is_left_without_a_reader(office):
    for kind, n in (("property_valuations", 7), ("title_deeds", 3), ("insurance_schedule", 1), ("custody_statements", 1)):
        r = office.report[kind]
        assert r["files"] == n and r["rows"] > 0 and not r["not_loaded"], (kind, r)


def test_card_65_the_register_has_the_latest_appraisal_of_each_asset_and_who_holds_the_title(office):
    k = key("uc-065-realassets")["assets"]
    rows = {r["asset_ref"]: r for r in office.rows(HEADS)}
    assert set(rows) == {a["id"] for a in k}
    for a in k:
        r = rows[a["id"]]
        assert (r["asset_name"], r["asset_type"], f2(r["appraised_value"]), r["currency"], str(r["appraised_on"]), r["title_holder_name"], r["entity_name"]) == \
               (a["name"], a["type"], f2(a["latest_value"]), a["currency"], a["appraised"], a["title_holder"], a["entity"]), a["id"]
        if a["currency"] == "SGD":  # the recipe converts at the 13 Oct fixing, 1.3400
            assert f2(Decimal(r["appraised_value"]) / Decimal("1.34")) == f2(a["value_usd"])


def test_card_65_66_a_newer_appraisal_supersedes_the_older_and_the_old_one_stays_as_history(office):
    two = office.rows("select appraised_on, supersedes_real_asset_id is not null as chained, id from real_assets where asset_ref = 'RA-01' order by appraised_on")
    assert [str(r["appraised_on"]) for r in two] == ["2024-11-20", "2025-11-18"] and [r["chained"] for r in two] == [False, True]
    assert office.one("select supersedes_real_asset_id from real_assets where asset_ref = 'RA-01' and appraised_on = date '2025-11-18'") == two[0]["id"]
    assert office.one("select count(*) from real_assets") == 7


def test_card_65_a_title_in_a_personal_name_is_an_exception_and_only_that_one_is(office):
    ex = office.rows("select title, external_ref from exceptions where exception_type = 'title_mismatch'")
    assert [e["external_ref"] for e in ex] == ["RA-04"] and "Lin Chen" in ex[0]["title"]
    assert any("RA-04" in f and "Lin Chen" in f for f in office.report["title_deeds"]["flagged"] + office.report["property_valuations"]["flagged"])


def test_card_66_appraisals_older_than_a_year_are_flagged_and_the_current_ones_are_not(office):
    stale = {f.split(":")[0] for f in office.report["property_valuations"]["flagged"] if "(M28)" in f}
    k = {a["id"]: a for a in key("uc-066-propreval")["by_asset"]}
    assert stale == {i for i, a in k.items() if a["due"]} == {"RA-03", "RA-05"}


def test_card_52_the_policies_carry_sum_insured_premium_renewal_and_the_asset_they_cover(office):
    rows = {r["contract_ref"]: r for r in office.rows("select * from vendor_contracts where contract_kind = 'insurance'")}
    for p in key("uc-052-insurance")["all_policies"]:
        r = rows[p["policy"]]
        assert (r["service"], str(r["next_renewal_date"]), f2(r["sum_insured"]), f2(r["annual_cost"]), r["currency"]) == (p["name"], p["next_renewal"], f2(p["sum_insured"]), f2(p["premium"]), p["currency"])
    assert {k: v["covered_asset_ref"] for k, v in rows.items()} == {"POL-HOME-01": "RA-01", "POL-ART-02": "RA-03", "POL-LIAB-03": None, "POL-CYB-04": None}


def test_card_52_a_renewal_with_no_notice_is_raised_and_the_notices_that_agree_with_the_schedule_are_not(office):
    ex = {e["external_ref"]: e["exception_type"] for e in office.rows("select exception_type, external_ref from exceptions where exception_type in ('renewal_notice_missing', 'premium_currency_mismatch')")}
    assert ex == {"POL-CYB-04": "renewal_notice_missing"}  # POL-LIAB-03's notice is in USD like the schedule (the old reader wrote SGD on every notice field, now the notice's own currency)
    assert {r["policy"]: r["renewal_notice_received"] for r in key("uc-052-insurance")["all_policies"]}["POL-CYB-04"] is False
    ccy = {r["value_text"]: r["currency"] for r in office.rows("select f.value_text, g.currency from extracted_fields f join extracted_fields g on g.document_id = f.document_id and g.field_name = 'renewal_premium' where f.field_name = 'policy'")}
    assert ccy["POL-LIAB-03"] == "USD" and ccy["POL-HOME-01"] == "SGD"


def test_card_52_30_insurance_does_not_become_a_vendor_renewal(office):
    got = office.run("renewals_vendors")
    assert len(got) == key("uc-030-vendors")["count"] and not any(r["contract_ref"] and r["contract_ref"].startswith("POL-") for r in got)


def test_card_56_the_statement_is_kept_as_the_custodians_own_figures_and_does_not_move_a_snapshot(office):
    q = {r["value_text"]: Decimal(r["value_numeric"]) for r in office.rows("select value_text, value_numeric from extracted_fields where field_name = 'custody_quantity'")}
    assert len(q) == 20 and q["Bay Street Utilities"] == 41250 and q["Redwood Pharma"] == 39600
    assert any(n.startswith("Harbour Treasury Note 2029") for n in q)  # the name cut at the column width is the security master's name again
    notes = office.rows("select value_text, value_numeric from extracted_fields where field_name = 'custodian_note' order by value_text")
    assert [(n["value_text"].split(":")[0], int(n["value_numeric"])) for n in notes] == [("Bay Street Utilities", 1250), ("Redwood Pharma", -400)]
    assert office.one("select count(*) from position_snapshots s join source_records r on r.id = s.source_record_id where r.raw_payload_uri like '%custody_statements%'") == 0


def test_card_56_the_statement_against_the_administrator_gives_exactly_the_two_breaks_of_the_key(office):
    adm = {r["canonical_name"]: Decimal(r["quantity"]) for r in office.rows(
        "select i.canonical_name, s.quantity from position_snapshots s join instruments i on i.id = s.instrument_id join portfolios p on p.id = s.portfolio_id "
        "where p.portfolio_code = 'EG-LIQUID' and s.view_type = 'accounting' and s.position_date = date '2026-09-30' and not exists "
        "(select 1 from position_snapshots x where x.supersedes_position_id = s.id)")}
    cust = {r["value_text"]: Decimal(r["value_numeric"]) for r in office.rows("select value_text, value_numeric from extracted_fields where field_name = 'custody_quantity'")}
    diff = {n: adm[n] - q for n, q in cust.items() if n in adm and adm[n] != q}
    k = {b["security"]: b["difference"] for b in key("uc-056-custrecon")["breaks"]}
    assert len([n for n in cust if n in adm]) == key("uc-056-custrecon")["holdings_compared"] and {n: int(v) for n, v in diff.items()} == k
