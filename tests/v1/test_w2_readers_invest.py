"""Readers of the invest group (v3_pack_readers_invest): fund holdings, deal pipeline, redemption terms, second-source prices, target allocation. Real readers on the
six-month office; expected numbers come from answer_keys.yaml or from the files. Synthetic data only."""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

from sh_platform.v1 import v3_pack_readers as PK

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, OFFICE = W2.key, W2.OFFICE
office = W2.office  # the module fixture: the office loaded through the real readers

KINDS = ["fund_holdings", "deal_pipeline", "fund_documents", "market_data", "target_allocation"]
ONE = {"fund_holdings": "2026-10/fund_holdings/fund_holdings_2026-09-30.xlsx", "deal_pipeline": "2026-10/deal_pipeline/deal_pipeline_2026-10-13.csv",
       "fund_documents": "2026-04/fund_documents/kestrel_H1_redemption_terms.pdf", "market_data": "2026-10/market_data/second_source_prices_2026-09-30_and_2026-10-13.csv",
       "target_allocation": "2026-10/target_allocation/interim_targets_EG-LIQUID_2026-10-08.xlsx"}


def test_each_kind_is_recognised_from_its_content_not_its_name():
    for kind, rel in ONE.items():
        assert PK.kind_of("renamed" + Path(rel).suffix, (OFFICE / rel).read_bytes())[0] == kind
    for rel in ("2026-09/deal_pipeline/teaser_DL-02.pdf", "2026-09/deal_pipeline/teaser_DL-04.pdf"):  # a deal's teaser is the pipeline's, not a prospect
        assert PK.kind_of(Path(rel).name, (OFFICE / rel).read_bytes())[0] == "deal_pipeline"
    prospect = next((OFFICE).glob("20??-??/prospects/fund_teaser_Harborlight_Ventures_IV.pdf"))
    assert PK.kind_of(prospect.name, prospect.read_bytes())[0] == "prospects"


def test_every_kind_is_read_and_says_what_it_did(office):
    for kind in KINDS:
        r = office.report[kind]
        assert not r["not_loaded"] and r["files"] == len(list(OFFICE.glob(f"20??-??/{kind}/*"))) and r["rows"] > 0, (kind, r)


def test_fund_holdings_keep_the_same_company_in_every_fund_it_sits_in(office):
    rows = office.rows("select h.*, i.canonical_name from fund_holdings h join instruments i on i.id = h.instrument_id where h.holding_name <> 'Other holdings'")
    funds = defaultdict(set)
    for r in rows:
        funds[r["holding_name"]].add(r["canonical_name"])
    assert sorted(c for c, f in funds.items() if len(f) > 1) == sorted(key("uc-069-lookthru")["companies_in_more_than_one_fund"])
    assert len(funds["Helix Cloud Systems"]) == 3
    sums = office.rows("select instrument_id, sum(weight_pct) as w from fund_holdings group by instrument_id")
    assert len(sums) == 8 and all(float(s["w"]) == 100 for s in sums)
    assert all(r["as_at"] == W2.date(2026, 9, 30) for r in rows)


def test_deal_pipeline_is_the_five_deals_with_stage_and_the_stuck_ones_are_flagged(office):
    k = key("uc-077-deals")
    rows = office.rows("select d.* from deal_pipeline d where not exists (select 1 from deal_pipeline x where x.supersedes_deal_id = d.id)")
    assert len(rows) == 5 and sum(float(r["target_commitment"]) for r in rows) == k["total_ticket"]
    for d in k["deals"]:
        r = next(x for x in rows if x["deal_name"] == d["deal"])
        assert r["stage"] == d["stage"] and (W2.date(2026, 10, 13) - r["stage_on"]).days == d["days_in_stage"] and float(r["target_commitment"]) == d["ticket"]
    flag = " ".join(office.report["deal_pipeline"]["flagged"])
    assert all(n in flag for n in k["stuck_over_60_days"]) and "Pelican" not in flag
    # the prospect teaser's 'screening' row of Harborlight is replaced by the pipeline's stage, not counted beside it
    assert office.one("select count(*) from deal_pipeline where stage = 'screening' and id in (select supersedes_deal_id from deal_pipeline where supersedes_deal_id is not null)") == 1
    assert office.one("select count(*) from documents where document_type = 'fund_teaser'") == 3
    assert office.one("select count(*) from extracted_fields where field_name = 'first_close' and value_text = '2026-11-30'") == 1


def test_redemption_terms_are_fields_per_fund(office):
    by = {r["name"]: {x["field_name"]: x for x in office.rows("select f.field_name, f.value_text, f.value_numeric from extracted_fields f where f.document_id = ?", r["id"])}
          for r in office.rows("select d.id, i.canonical_name as name from documents d join instruments i on i.id = d.instrument_id where d.document_type = 'redemption_terms'")}
    assert set(by) == set(key("uc-078-redemption")["by_fund"])
    macro, ls = by["Kestrel Ridge Macro Fund"], by["Kestrel Ridge Equity Long/Short Fund"]
    assert (macro["redemption_frequency"]["value_text"], float(macro["notice_days"]["value_numeric"]), macro["lockup_end_date"]["value_text"]) == ("monthly", 45, "2025-03-01")
    assert (ls["redemption_frequency"]["value_text"], float(ls["notice_days"]["value_numeric"]), ls["lockup_end_date"]["value_text"]) == ("quarterly", 60, "2026-12-31")
    assert [float(x["payment_lag_days"]["value_numeric"]) for x in (macro, ls)] == [14, 30] and all(float(x["holdback_pct"]["value_numeric"]) == 5 for x in (macro, ls))
    assert float(macro["lockup_months"]["value_numeric"]) == 12
    k = key("uc-078-redemption")["by_fund"]["Kestrel Ridge Macro Fund"]  # the key's cash is the value less the holdback the terms state
    assert round(k["latest_value"] * (1 - 0.05)) == k["cash_at_payment"]


def test_second_source_prices_are_forty_observations_and_carry_the_prices_the_key_quotes(office):
    k = key("uc-057-pricecheck")
    rows = office.rows("select o.*, i.canonical_name from market_observations o join instruments i on i.id = o.instrument_id where o.observation_type = 'price_second_source'")
    assert len(rows) == k["prices_compared"] == 40 and len({(r["instrument_id"], r["observed_at"]) for r in rows}) == 40
    for x in k["over_tolerance"]:
        r = [r for r in rows if str(r["observed_at"])[:10] == x["date"] and float(r["value"]) == x["second_source_price"]]
        assert len(r) == 1 and r[0]["series_key"].endswith(".SYN")


def test_the_target_allocation_is_proposed_rules_never_signed(office):
    k = key("uc-079-rebalance")["by_class"]
    for cls, v in k.items():
        p = json.loads(office.one("select v.parameters from business_rules b join rule_versions v on v.business_rule_id = b.id where b.rule_code = ?", f"allocation_{cls}"))
        assert p["target_pct"] == v["target_pct"] and p["portfolio"] == "EG-LIQUID"
    assert office.one("select count(*) from rule_versions v join business_rules b on b.id = v.business_rule_id where b.rule_code like 'allocation_%' and v.approval_status <> 'proposed'") == 0
    assert sum(v["target_pct"] for v in k.values()) == 100
