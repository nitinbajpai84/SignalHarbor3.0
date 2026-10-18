"""W1b, domain office ("Run the office" and "Family and people"), cards 51 to 100 (docs/v3/w1/build51-office.md), proved on the real pack readers.

Built (20, with the two below): uc-052-insurance (renewals_due), uc-081-payroll (payroll_total), uc-082-covergap (cover_gap), uc-091-jml and uc-092-accessrev (access_review), uc-093-onbmgr
(onboarding_items), uc-095-sopreview (sop_age), uc-097-kycrefresh (kyc_expiry), uc-098-wordlist (terms_proposed), and on the family and controls readers with the signed office
rules (A48, A49, A54): uc-083-taxcal (tax_due), uc-085-grants (grants_used), uc-086-grantappr (grant_check), uc-087-trustdist (trust_distribution_room), uc-088-estateliq
(estate_cash_need), uc-089-expapp (approval_exceptions), uc-090-offcost (office_cost), uc-094-onbbank (account_setup), uc-100-famaccess (member_access). Their numbers come from
the recipes' output on the office loaded by sh_platform/v1/v3_pack_readers (the `office` fixture of test_w2_loader.py) and are compared with answer_keys.yaml, read from the
file, never typed.
uc-096-automation (automation_score, on the failures each SOP lists and the signed rework minutes, A51) and uc-084-taxest (tax_estimate, on the 2026 rates signed in A57,
the sold lots and the income on file) are built too: a build each, 84 with two signals. Synthetic data only."""
from __future__ import annotations

import ast
import datetime as dt
import glob
import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import v3_signals as S

_SPEC = importlib.util.spec_from_file_location("w2_loader_tests", Path(__file__).with_name("test_w2_loader.py"))
W2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(W2)
key, f2, one, KEYS, OFFICE = W2.key, W2.f2, W2.one, W2.KEYS, W2.OFFICE
office = W2.office  # the module fixture: the office files loaded through the real readers
REPO = W2.REPO
PACK = REPO / "packs" / "family_office" / "1"
CARDS = [c["id"] for c in yaml.safe_load((PACK / "use_cases_100.yaml").read_text(encoding="utf-8"))["use_cases"]
         if c.get("domain") in ("Run the office", "Family and people") and c["order"] > 50 and c["id"] in KEYS]

BUILT = ["uc-052-insurance", "uc-081-payroll", "uc-082-covergap", "uc-091-jml", "uc-092-accessrev", "uc-093-onbmgr", "uc-095-sopreview", "uc-097-kycrefresh", "uc-098-wordlist",
         "uc-083-taxcal", "uc-084-taxest", "uc-085-grants", "uc-086-grantappr", "uc-087-trustdist", "uc-088-estateliq", "uc-089-expapp", "uc-090-offcost", "uc-094-onbbank", "uc-100-famaccess", "uc-096-automation"]
NOT_BUILT: set[str] = set()  # every card of the domain is built (84 on the rates signed in A57)
RECIPE_ONLY: set[str] = set()
OWN = ["renewals_due", "payroll_total", "cover_gap", "access_review", "onboarding_items", "sop_age", "kyc_expiry", "terms_proposed"]
RULED = {  # recipe -> the signed rule codes (prefix) it reads; never a number typed in
    "grants_used": ("office_budget_grants",), "grant_check": ("office_budget_grants", "grant_min_charity_months", "cash_buffer"),
    "estate_cash_need": ("estate_tax_exemption", "estate_tax_rate"), "tax_estimate": ("tax_rate_",), "approval_exceptions": ("approver_limit_",), "office_cost": ("office_budget_",),
    "account_setup": ("signing_policy",), "member_access": ("family_access_",)}
NEW = ["tax_due", "trust_distribution_room", *RULED]


def kinds_of(card: str) -> set[str]:
    """The file kinds (folder names) in the card's input_files: '*/kind/file' or 'kind/file'."""
    return {m.group(1) for f in KEYS[card]["input_files"] if (m := re.match(r"(?:\*/)?([a-z_]+)/", f))}


def test_the_domain_has_twenty_cards_and_each_is_built_or_has_a_reason():
    assert len(CARDS) == 20, CARDS
    assert sorted(BUILT + list(NOT_BUILT) + list(RECIPE_ONLY)) == sorted(CARDS)


# ---- card 52: insurance renewals ------------------------------------------------------------------------------------------------------------

def test_card52_policies_expiring_in_60_days_match_the_key(office):
    exp = key("uc-052-insurance")
    rows = office.run("renewals_due")
    assert len(rows) == len(exp["all_policies"]) == 4
    for k in exp["all_policies"]:
        r = one(rows, policy=k["policy"])
        assert (r["policy_name"], str(r["next_renewal_date"]), r["days_left"], r["sum_insured"], r["premium"], r["currency"], bool(r["renewal_notice_received"])) == (
            k["name"], k["next_renewal"], k["days_left"], Decimal(k["sum_insured"]), Decimal(k["premium"]), k["currency"], k["renewal_notice_received"]), k["policy"]
    due = [r["policy"] for r in sorted(rows, key=lambda r: r["days_left"]) if r["due_in_60_days"]]
    assert due == [k["policy"] for k in exp["expiring_in_60_days"]] and len(due) == exp["count"]


# ---- card 81: payroll -------------------------------------------------------------------------------------------------------------------

def test_card81_the_draft_run_against_september_matches_the_key(office):
    exp = key("uc-081-payroll")
    rows = office.run("payroll_total")
    r = rows[0]
    assert (r["run_net"], r["run_employer"], r["run_total_cost"]) == (Decimal(str(exp["draft_net"])), Decimal(str(exp["draft_employer_cpf"])), Decimal(str(exp["draft_total_cost"])))
    assert (r["previous_net"], r["previous_total_cost"], r["previous_net_paid_per_bank"]) == (
        Decimal(exp["september_net"]), Decimal(exp["september_total_cost"]), Decimal(exp["september_net_paid_per_bank"]))
    assert f2(r["change_pct"]) == exp["change_pct"] and bool(r["release"]) is exp["release"]
    flags = {x["employee_name"]: x for x in rows if x["flagged"]}
    k = {f["employee"].split(" (")[0]: f for f in exp["flags"]}
    assert sorted(flags) == sorted(k) == ["Grace Ong", "Jun Tan"]
    assert flags["Grace Ong"]["flag"] == k["Grace Ong"]["kind"] and f2(flags["Grace Ong"]["gross_change_pct"]) == k["Grace Ong"]["change_pct"]
    assert flags["Jun Tan"]["flag"] == k["Jun Tan"]["kind"] and flags["Jun Tan"]["gross_pay"] == Decimal(k["Jun Tan"]["gross"])


# ---- card 82: cover gap -----------------------------------------------------------------------------------------------------------------

def test_card82_cover_against_appraisals_matches_the_key(office):
    exp = key("uc-082-covergap")
    rows = office.run("cover_gap")
    assert len(rows) == len(exp["by_asset"]) == 6
    for k in exp["by_asset"]:
        r = one(rows, asset=k["asset"])
        assert (f2(r["appraised_usd"]), f2(r["insured_usd"]), f2(r["gap_usd"]), r["status"]) == (k["appraised_usd"], k["insured_usd"], k["gap_usd"], k["status"]), k["asset"]
    assert f2(sum(r["gap_usd"] for r in rows)) == exp["total_gap_usd"]
    assert sorted(r["asset"] for r in rows if r["under_insured"]) == sorted(exp["under_insured"])
    assert sorted(r["asset"] for r in rows if r["no_policy"]) == sorted(exp["no_policy"])
    assert {float(r["rate"]) for r in rows if r["currency"] == "SGD"} == {1.34}  # the 13 Oct fixing, read from the plane


# ---- cards 91 and 92: access -----------------------------------------------------------------------------------------------------------

def test_card91_joiner_leaver_and_unapproved_access_match_the_key(office):
    exp = key("uc-091-jml")
    rows = office.run("access_review")
    assert sorted((r["person"], r["system"], r["permission"]) for r in rows if r["no_approver"]) == sorted(
        (k["person"], k["system"], k["permission"]) for k in exp["granted_without_approver"])
    assert {r["person"] for r in rows if r["leaver"]} == {exp["leaver"]}
    assert sorted(r["system"] for r in rows if r["leaver"]) == sorted(exp["leaver_access_to_remove"])
    assert {r["person"] for r in rows if r["joiner_not_requested"]} == {exp["joiner"]}
    assert sorted(r["system"] for r in rows if r["joiner_not_requested"]) == sorted(exp["joiner_access_not_requested"])


def test_card92_access_not_used_in_90_days_matches_the_key(office):
    exp = key("uc-092-accessrev")
    rows = office.run("access_review")
    assert len(rows) == exp["grants_reviewed"]
    got = sorted(((r["person"], r["system"], str(r["last_used_on"]), r["days_unused"]) for r in rows if r["unused_90"]), key=lambda x: -x[3])
    assert got == [(k["person"], k["system"], k["last_used"], k["days_unused"]) for k in exp["not_used_in_90_days"]] and len(got) == exp["count"]


# ---- card 93: onboarding ----------------------------------------------------------------------------------------------------------------

def test_card93_the_onboarding_checklist_matches_the_key(office):
    exp = key("uc-093-onbmgr")
    rows = office.run("onboarding_items")
    assert (rows[0]["items"], rows[0]["complete_items"], bool(rows[0]["ready"])) == (exp["items"], exp["complete"], exp["ready"])
    assert sorted(r["item"] for r in rows if not r["complete"]) == sorted(exp["missing"])


# ---- card 95: SOP age -------------------------------------------------------------------------------------------------------------------

def test_card95_sop_ages_match_the_key(office):
    exp = key("uc-095-sopreview")
    rows = office.run("sop_age")
    assert len(rows) == len(exp["sops"]) == 8
    for k in exp["sops"]:
        r = one(rows, sop=k["sop"])
        assert (r["owner"], str(r["last_reviewed"]), r["age_days"], bool(r["due"])) == (k["owner"], k["last_reviewed"], k["age_days"], k["due"]), k["sop"]
    assert [r["sop"] for r in sorted(rows, key=lambda r: -r["age_days"]) if r["due"]] == exp["to_review"]


# ---- card 97: KYC -----------------------------------------------------------------------------------------------------------------------

def test_card97_kyc_expiry_matches_the_key(office):
    exp = key("uc-097-kycrefresh")
    rows = office.run("kyc_expiry")
    assert len(rows) == exp["documents"]

    def view(r):
        return {"entity": r["entity"], "counterparty": r["counterparty"], "document": r["document"], "expires": str(r["expires_on"]), "days_left": r["days_left"]}
    assert [view(r) for r in sorted(rows, key=lambda r: r["days_left"]) if r["expiring_90"]] == exp["expiring_in_90_days"]
    assert [view(r) for r in rows if r["expired"]] == exp["expired"]


# ---- card 98: word list -----------------------------------------------------------------------------------------------------------------

def test_card98_words_proposed_against_the_office_list_match_the_key(office):
    exp = key("uc-098-wordlist")
    rows = office.run("terms_proposed")
    assert sorted(r["term"] for r in rows) == sorted(exp["proposed"]) and len(rows) == exp["distinct_terms"]
    assert rows[0]["proposals_made"] == exp["proposals_made"] and rows[0]["list_size"] == exp["list_size"]
    assert sorted(r["term"] for r in rows if r["in_list"]) == exp["already_in_list"]
    assert sorted(r["term"] for r in rows if r["to_add"]) == exp["to_add"]


# ---- cards 83 to 100 on the family and controls readers ------------------------------------------------------------------------------------

def test_card83_tax_items_due_and_overdue_match_the_key(office):
    exp = key("uc-083-taxcal")
    rows = office.run("tax_due")

    def view(r, d):
        return {"id": r["id"], "entity": r["entity"], "obligation": r["obligation"], "due": str(r["due"]), d: r[d], "prepared_by": r["prepared_by"], "status": r["status"]}
    assert [view(r, "days") for r in sorted(rows, key=lambda r: r["id"]) if r["due_in_60_days"]] == exp["due_in_60_days"]
    due = [r["entity"] for r in rows if r["due_in_60_days"]]
    assert {e: due.count(e) for e in due} == exp["count_by_entity"]
    assert [view(r, "days_overdue") for r in rows if r["overdue"]] == exp["overdue"]


def test_card85_grants_against_the_signed_budget_match_the_key(office):
    exp = key("uc-085-grants")
    r = office.run("grants_used")[0]
    assert {k: (bool(r[k]) if k == "paid_matches_bank" else float(r[k])) for k in exp} == exp
    assert office.one("select v.approval_status from business_rules as r join rule_versions as v on v.business_rule_id = r.id where r.rule_code = 'office_budget_grants' "
                      "order by v.version_number desc limit 1") == "approved"


def test_card86_the_grant_request_fails_every_check_as_the_key_says(office):
    exp = key("uc-086-grantappr")
    r = one(office.run("grant_check"), request=exp["request"])
    assert (f2(r["amount"]), f2(r["remaining_budget"]), r["charity_registered_months"], r["required_months"]) == (
        exp["amount"], exp["remaining_budget"], exp["charity_registered_months"], exp["required_months"])
    assert (f2(r["cash"]), f2(r["calls_due_30_days"]), f2(r["cash_after_request_and_calls"])) == (exp["holdings_usd_cash"], exp["calls_due_30_days"], exp["cash_after_request_and_calls"])
    assert {k: r[k] for k in exp["checks"]} == exp["checks"] and r["pay"] is exp["pay"] and r["fails"] == 1


def test_card87_trust_room_per_beneficiary_matches_the_key(office):
    exp = key("uc-087-trustdist")
    rows = office.run("trust_distribution_room")
    r = rows[0]
    assert str(r["trust_year_start"]) == exp["trust_year_start"]
    names = ("trust_income", "trust_expenses", "distributable_income", "payout_cap_pct", "distributable_cap")
    assert [f2(r[k]) for k in names] == [exp[k] for k in names]
    for name, k in exp["by_beneficiary"].items():
        b = one(rows, beneficiary=name)
        assert (f2(b["share_pct"]), f2(b["room"]), f2(b["paid"]), f2(b["left_to_pay"]), bool(b["over"])) == (k["share_pct"], k["room"], k["paid"], k["left"], k["over"]), name
    assert sorted(b["beneficiary"] for b in rows if b["over"]) == exp["over_distributed"]


def test_card88_the_transfer_tax_against_liquid_assets_matches_the_key(office):
    exp = key("uc-088-estateliq")
    r = office.run("estate_cash_need")[0]
    for k, c in (("estate_value", "estate_value"), ("investments_30_sep", "investments"), ("cash", "cash"), ("real_assets", "real_assets"), ("loan", "loan"),
                 ("exemption", "exemption"), ("rate", "rate"), ("transfer_tax", "transfer_tax"), ("liquid_assets_after_debt", "liquid_assets_after_debt"), ("cover", "cover")):
        assert f2(r[c]) == exp[k], k
    assert r["can_meet"] is exp["can_meet"] and str(r["period_end"]) == "2026-09-30"


def test_card89_payments_over_the_signed_limits_match_the_key(office):
    exp = key("uc-089-expapp")
    rows = office.run("approval_exceptions")
    assert len(rows) == exp["payments"]
    limits = {r["rule_code"]: float(r["l"]) for r in office.rows("select r.rule_code, json_extract_string(v.parameters, '$.limit') as l from business_rules as r join rule_versions as v "
                                                                 "on v.business_rule_id = r.id where starts_with(r.rule_code, 'approver_limit_') and v.approval_status = 'approved'")}
    assert limits == {"approver_limit_" + n.lower().replace(" ", "_"): v for n, v in exp["limits"].items()}
    got = [{"reference": r["reference"], "payee": r["payee"], "usd": f2(r["usd"]), "approver": r["approver"], "limit": f2(r["limit_usd"])}
           for r in sorted(rows, key=lambda r: -r["usd"]) if r["over_limit"]]
    assert got == exp["over_limit"]
    assert {p: sum(1 for r in rows if r["approver"] == p) for p in exp["approvals_by_person"]} == exp["approvals_by_person"]


def test_card90_cost_by_category_against_half_the_budget_matches_the_key(office):
    exp = key("uc-090-offcost")
    rows = office.run("office_cost")
    assert len(rows) == len(exp["by_category"]) == 13
    for cat, k in exp["by_category"].items():
        r = one(rows, category=cat)
        assert (f2(r["actual"]), f2(r["budget_period"]), f2(r["variance"]), bool(r["over"])) == (k["actual"], k["budget_half_year"], k["variance"], k["over"]), cat
    assert (f2(rows[0]["total_actual"]), f2(rows[0]["total_budget"]), rows[0]["uncategorised"]) == (exp["actual"], exp["budget"], exp["uncategorised"])
    assert sorted(r["category"] for r in rows if r["over"]) == sorted(exp["over_budget"])


def test_card94_signatories_against_the_signed_policy_match_the_key(office):
    exp = key("uc-094-onbbank")
    r = office.run("account_setup")[0]
    assert r["signatories"].split(", ") == exp["signatories"]
    assert (r["required_person"], r["missing_signatory"], r["meets_signing_policy"], r["approved"]) == (
        exp["required_head_of_finance"], exp["missing_signatory"], exp["meets_signing_policy"], exp["approved"])
    # the key's checklist steps (form completed, KYC, resolution, specimen signatures ...) are in no file: only the two the data decides are compared
    steps = {s["step"]: s["done"] for s in exp["steps"]}
    assert steps["Signatories meet the signing policy"] is r["meets_signing_policy"] and steps["Head of Finance approval"] is r["approved"]


def test_card100_views_against_the_signed_family_policy_match_the_key(office):
    exp = key("uc-100-famaccess")
    rows = office.run("member_access")
    for m, k in exp["by_member"].items():
        mine = [r for r in rows if r["member"] == m]
        assert {r["entity"]: r["allowed"] for r in mine if r["allowed"] != "none"} == k["allowed"], m
        assert {r["entity"]: r["granted"] for r in mine if r["granted"] != "none"} == k["granted"], m
        assert {r["entity"]: {"granted": r["granted"], "allowed": r["allowed"]} for r in mine if r["over_granted"]} == k["over_granted"], m
    assert sorted({r["member"] for r in rows if r["over_granted"]}) == exp["over_grants"]
    q = one(rows, has_request=1)
    assert {"member": q["member"], "entity": q["entity"], "level": q["requested_level"], "allowed": q["request_allowed"]} == exp["request"]


# ---- the cards that are not built: proof of the reason ------------------------------------------------------------------------------------

def test_card84_the_tax_estimate_is_the_key_and_says_the_missing_statement(office):
    """A57, A58: the rates are signed; the key counts only the statements that arrived, and Entity B's row says one never did (M02b)."""
    k, rows = key("uc-084-taxest"), office.run("tax_estimate")
    assert len(rows) == 3
    for name, e in k["by_entity"].items():
        r = one(rows, entity=name)
        assert {c: f2(r[c]) for c in e} == e, name
        assert r["bank_months_missing"] == (1 if name == "Entity B" else 0)
    assert k["statements_missing"] == ["TCB-B-USD 2026-07"] and f2(rows[0]["total_to_set_aside"]) == k["total_to_set_aside"]
    con = office.con
    con.execute("begin")
    try:  # without the signed rates there is no tax, never a guess
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where starts_with(rule_code, 'tax_rate_'))")
        assert all(r["rate_on_income"] is None and r["tax_to_set_aside"] is None for r in office.run("tax_estimate"))
    finally:
        con.execute("rollback")


def test_card96_the_automation_score_is_the_key(office):
    exp, rows = key("uc-096-automation"), office.run("automation_score")
    assert [r["sop"] for r in sorted(rows, key=lambda r: r["rank"])] == [k["sop"] for k in exp["ranking"]]
    for k in exp["ranking"]:
        r = one(rows, sop=k["sop"])
        assert {c: (f2(r[c]) if c != "slowest_manual_step" else r[c]) for c in k if c != "sop"} == {c: v for c, v in k.items() if c != "sop"}, k["sop"]
    assert one(rows, automate_next=True)["sop"] == exp["automate_next"]
    con = office.con
    con.execute("begin")
    try:  # without the signed rework minutes there is no score, never a guess
        con.execute("update rule_versions set approval_status = 'proposed' where business_rule_id in (select id from business_rules where rule_code = 'automation_rework_minutes')")
        assert all(r["score"] is None and not r["automate_next"] for r in office.run("automation_score"))
    finally:
        con.execute("rollback")


# ---- recipes: shape ---------------------------------------------------------------------------------------------------------------------

def test_every_recipe_of_the_slice_is_ready_and_reads_only_what_it_may():
    for rid in OWN + NEW:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["sql"] and r["measure"] and r["grain"] and r["tie_out"] and r["cards"] and r["why"], rid
        assert R.refusal(r, R.render(r, "t")) is None, rid
        assert ("business_rules" in r["may_read"]) is (rid in RULED), rid  # only the recipes that need a signed rule read the rules
        for code in RULED.get(rid, ()):
            assert f"'{code}" in r["sql"], (rid, code)  # the rule is read by its code, never typed in as a number


def test_new_recipes_bind_the_cards_figures_and_leave_the_others_alone():
    for n, rid in [("Policies expiring in 60 days", "renewals_due"), ("Payroll total against last month", "payroll_total"), ("Insured value less asset value", "cover_gap"),
                   ("Access given but not approved", "access_review"), ("Access not used in 90 days", "access_review"), ("Items complete and outstanding", "onboarding_items"),
                   ("SOPs by last review", "sop_age"), ("Documents expiring in 90 days", "kyc_expiry"), ("Terms proposed and accepted", "terms_proposed"),
                   ("Tax items due in 60 days", "tax_due"), ("Paid and pledged against budget", "grants_used"), ("Budget, charity check, cash", "grant_check"),
                   ("Distribution room per beneficiary", "trust_distribution_room"), ("Tax need against liquid assets", "estate_cash_need"), ("Estimated tax", "tax_estimate"),
                   ("Payments over their approval limit", "approval_exceptions"), ("Cost by type against budget", "office_cost"),
                   ("Setup steps and signatories", "account_setup"), ("Access per family member", "member_access")]:
        assert (R.match({"name": n}) or {}).get("id") == rid, n
    for n in ["Vendor contract renewals", "Payment batch", "Family allowances due", "Net worth by portfolio", "Cash by entity", "Statements missing by fund", "Called to date"]:
        assert (R.match({"name": n}) or {}).get("id") not in OWN + NEW, n


# ---- signals and builds -----------------------------------------------------------------------------------------------------------------

def signals() -> dict[str, dict]:
    out = {}
    for card in BUILT:
        for p in sorted((PACK / "signals").glob(f"{card}-*.yaml")):
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            s["trigger"] = {("on" if k is True else k): v for k, v in s["trigger"].items()}  # YAML 1.1 reads a bare `on` as true; the engine does the same
            s["_file"] = p.name
            out[s["id"]] = s
    return out


def role_ids() -> set[str]:
    ids = {r["id"] for r in yaml.safe_load((PACK / "role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
    for p in (PACK / "builds").glob("*.yaml"):
        ids |= {r["id"] for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("roles") or []}
    return ids


EXPECTED = {  # id -> (figure, severity, route, hold)
    "uc-052-insurance-due": ("renewals_due", "needs", "hr_admin", None),
    "uc-052-insurance-no-notice": ("renewals_due", "problem", "hr_admin", None),
    "uc-081-payroll-flag": ("payroll_total", "problem", "cfo", "prepare_payment"),
    "uc-082-covergap-no-policy": ("cover_gap", "problem", "hr_admin", None),
    "uc-082-covergap-under-insured": ("cover_gap", "needs", "hr_admin", None),
    "uc-091-jml-no-approver": ("access_review", "problem", "head_of_data", None),
    "uc-091-jml-leaver": ("access_review", "problem", "head_of_data", None),
    "uc-091-jml-not-requested": ("access_review", "needs", "head_of_data", None),
    "uc-092-accessrev-unused": ("access_review", "needs", "head_of_data", None),
    "uc-093-onbmgr-missing": ("onboarding_items", "problem", "ops_lead", "prepare_payment"),
    "uc-095-sopreview-due": ("sop_age", "needs", "hr_admin", None),
    "uc-097-kycrefresh-expired": ("kyc_expiry", "problem", "risk_officer", None),
    "uc-097-kycrefresh-expiring": ("kyc_expiry", "needs", "risk_officer", None),
    "uc-098-wordlist-to-add": ("terms_proposed", "needs", "head_of_data", None),
    "uc-083-taxcal-overdue": ("tax_due", "problem", "fund_accountant", None),
    "uc-083-taxcal-due": ("tax_due", "needs", "fund_accountant", None),
    "uc-084-taxest-set-aside": ("tax_estimate", "info", "cfo", None),
    "uc-084-taxest-income-gap": ("tax_estimate", "problem", "cfo", "set_tax_cash_aside"),
    "uc-086-grantappr-fails": ("grant_check", "problem", "principal", "prepare_payment"),
    "uc-087-trustdist-over": ("trust_distribution_room", "problem", "fund_accountant", "prepare_payment"),
    "uc-089-expapp-over-limit": ("approval_exceptions", "problem", "cfo", None),
    "uc-090-offcost-over": ("office_cost", "needs", "cfo", None),
    "uc-094-onbbank-signatory": ("account_setup", "problem", "cfo", "open_bank_account"),
    "uc-100-famaccess-over-granted": ("member_access", "problem", "hr_admin", "send_family_report"),
}


def ns_of(row: dict) -> dict:
    return {"doc": {k: (v if isinstance(v, (str, dt.date)) else S.num(v)) for k, v in row.items() if v is not None}}


def fires(sig: dict, row: dict) -> bool:
    """The condition on one row of the figure the signal watches, as the engine reads it (a missing field skips the signal)."""
    need = [f for i in sig["inputs"] if i["kind"] == "doc" for f in i["fields"]]
    if any(row.get(f) in (None, "") for f in need):
        return False
    funcs = {"abs": abs, "min": min, "max": max, "round": round, "last4": S.last4, "num": S.num}
    ns = {"doc": {f: row[f] if isinstance(row[f], (dt.date, Decimal, str)) else S._dec(row[f]) for f in need}}
    return bool(S.calc(sig["condition"], ns, funcs))


def test_signals_follow_the_engine_format_have_a_role_and_an_exception():
    sigs = signals()
    assert set(sigs) == set(EXPECTED)
    roles = role_ids()
    for sid, (fig, sev, route, hold) in EXPECTED.items():
        s = sigs[sid]
        assert s["_file"] == f"{sid}.yaml" and s["suggestion"] is True and s["subject"] and s["message"] and s["pain_points"]
        assert S.check(s, {r: r for r in roles}) is None, (sid, S.check(s, {r: r for r in roles}))
        assert s["trigger"] == {"on": "figure_changed", "figure": fig} and s["severity"] == sev and s["route_to"] == route, sid
        assert (s.get("hold") or {}).get("blocks") == hold and (not hold or (s["hold"]["scope"] and s["hold"]["until"])), sid
        assert not re.search(r"\b(Sam|Helen|Raj|Mei|Daniel|Grace|Sofia|Priya|Anita|Tom)\b", yaml.safe_dump(s)), sid  # a role, never a person
        tree = ast.parse(str(s["condition"]), mode="eval")
        assert all(n.func.id in {"abs", "min", "max", "round", "last4", "num"} for n in ast.walk(tree) if isinstance(n, ast.Call))
    for card in BUILT:
        assert any(sid.startswith(card + "-") and EXPECTED[sid][1] == "problem" for sid in EXPECTED) or card in ("uc-092-accessrev", "uc-095-sopreview", "uc-098-wordlist", "uc-085-grants", "uc-088-estateliq", "uc-090-offcost", "uc-096-automation"), card


@pytest.fixture(scope="module")
def figs(office) -> dict[str, list[dict]]:
    return {rid: office.run(rid) for rid in OWN + NEW}


def test_signal_fields_are_columns_of_the_figure_they_watch(office, figs):
    for sid, s in signals().items():
        have = {r["column_name"] for r in office.rows(f"select column_name from information_schema.columns where table_name = 't_{s['trigger']['figure']}'")}
        want = {f for i in s["inputs"] if i["kind"] == "doc" for f in i["fields"]}
        assert want <= have, (sid, want - have)
        for name in re.findall(r"\{doc\.([a-z_]+)", s["message"] + s["subject"] + (s.get("hold") or {}).get("scope", "")):
            assert name in want, (sid, name)


def test_each_signal_fires_on_exactly_the_rows_of_the_key(figs):
    sigs = signals()

    def who(sid, col):
        s = sigs[sid]
        return sorted(r[col] for r in figs[s["trigger"]["figure"]] if fires(s, r))

    assert who("uc-052-insurance-due", "policy") == ["POL-LIAB-03"]
    assert who("uc-052-insurance-no-notice", "policy") == ["POL-CYB-04"]
    assert who("uc-081-payroll-flag", "employee_name") == sorted(f["employee"].split(" (")[0] for f in key("uc-081-payroll")["flags"])
    assert who("uc-082-covergap-no-policy", "asset") == sorted(key("uc-082-covergap")["no_policy"])
    assert who("uc-082-covergap-under-insured", "asset") == sorted(key("uc-082-covergap")["under_insured"])
    assert who("uc-091-jml-no-approver", "person") == sorted(k["person"] for k in key("uc-091-jml")["granted_without_approver"])
    assert who("uc-091-jml-leaver", "system") == sorted(key("uc-091-jml")["leaver_access_to_remove"])
    assert who("uc-091-jml-not-requested", "system") == key("uc-091-jml")["joiner_access_not_requested"]
    assert who("uc-092-accessrev-unused", "person") == sorted(k["person"] for k in key("uc-092-accessrev")["not_used_in_90_days"])
    assert who("uc-093-onbmgr-missing", "item") == sorted(key("uc-093-onbmgr")["missing"])
    assert who("uc-095-sopreview-due", "sop") == sorted(key("uc-095-sopreview")["to_review"])
    assert who("uc-097-kycrefresh-expired", "expires_on") == [dt.date.fromisoformat(k["expires"]) for k in key("uc-097-kycrefresh")["expired"]]
    assert who("uc-097-kycrefresh-expiring", "expires_on") == [dt.date.fromisoformat(k["expires"]) for k in key("uc-097-kycrefresh")["expiring_in_90_days"]]
    assert who("uc-098-wordlist-to-add", "term") == key("uc-098-wordlist")["to_add"]
    assert who("uc-083-taxcal-overdue", "id") == [k["id"] for k in key("uc-083-taxcal")["overdue"]]
    assert who("uc-083-taxcal-due", "id") == [k["id"] for k in key("uc-083-taxcal")["due_in_60_days"]]
    assert who("uc-084-taxest-income-gap", "entity") == ["Entity B"]  # M02b: the entity whose bank statement never arrived
    assert who("uc-084-taxest-set-aside", "entity") == sorted(key("uc-084-taxest")["by_entity"])
    assert who("uc-086-grantappr-fails", "request") == [key("uc-086-grantappr")["request"]]
    assert who("uc-087-trustdist-over", "beneficiary") == key("uc-087-trustdist")["over_distributed"]
    assert who("uc-089-expapp-over-limit", "reference") == sorted(k["reference"] for k in key("uc-089-expapp")["over_limit"])
    assert who("uc-090-offcost-over", "category") == sorted(key("uc-090-offcost")["over_budget"])
    assert who("uc-094-onbbank-signatory", "missing_signatory") == [key("uc-094-onbbank")["missing_signatory"]]
    assert who("uc-100-famaccess-over-granted", "member") == key("uc-100-famaccess")["over_grants"]


def test_the_messages_carry_the_numbers_of_the_key(figs):
    sigs = signals()
    msg = S.render(sigs["uc-081-payroll-flag"]["message"], ns_of(one(figs["payroll_total"], employee_name="Grace Ong")))
    assert "gross changed" in msg and "121,521.60" in msg and "7.35" in msg and "{" not in msg
    msg = S.render(sigs["uc-082-covergap-under-insured"]["message"], ns_of(one(figs["cover_gap"], asset="Bayview Residence")))
    assert "6,343,283.58" in msg and "7,164,179.10" in msg and "-820,895.52" in msg and "{" not in msg
    msg = S.render(sigs["uc-052-insurance-no-notice"]["message"], ns_of(one(figs["renewals_due"], policy="POL-CYB-04")))
    assert "1,000,000" in msg and "2026-12-01" in msg and "49 days" in msg and "{" not in msg
    hold = S.render(sigs["uc-093-onbmgr-missing"]["hold"]["scope"], ns_of(figs["onboarding_items"][0]))
    assert hold == "Harborlight first call"
    msg = S.render(sigs["uc-086-grantappr-fails"]["message"], ns_of(figs["grant_check"][0]))
    assert "50,000.00" in msg and "35,000.00" in msg and "19 months old against 24" in msg and "-70,000.00" in msg and "{" not in msg
    msg = S.render(sigs["uc-087-trustdist-over"]["message"], ns_of(one(figs["trust_distribution_room"], beneficiary="Wen Chen")))
    assert "25,702.83" in msg and "28,000.00" in msg and "-2,297.17" in msg and "{" not in msg
    assert S.render(sigs["uc-094-onbbank-signatory"]["hold"]["scope"], ns_of(figs["account_setup"][0])) == "Evergreen Family Trust EUR account at Tidewater Commercial Bank (synthetic)"


def test_builds_are_the_built_cards_only_and_expect_numbers_from_the_key():
    builds = yaml.safe_load((PACK / "builds" / "office-51.yaml").read_text(encoding="utf-8"))
    ids = []
    for role in builds["roles"]:
        assert role["id"] in role_ids()
        for b in role["builds"]:
            ids.append(b["id"])
            assert b["say"] and b["files"] and all(f.startswith("office6m:") for f in b["files"]) and b["check"]["ask"] and b["check"]["expect"]
            assert all(glob.glob(str(OFFICE / f[len("office6m:"):])) for f in b["files"]), b["id"]
            assert b["check"]["ask"] in KEYS[b["id"]]["questions"], b["id"]
            blob = json.dumps(KEYS[b["id"]]["questions"], default=str).replace(",", "")
            for e in b["check"]["expect"]:
                assert e.replace(",", "") in blob, (b["id"], e)
                assert len(e.replace(",", "")) > 2, (b["id"], e)
    assert sorted(ids) == sorted(BUILT)
