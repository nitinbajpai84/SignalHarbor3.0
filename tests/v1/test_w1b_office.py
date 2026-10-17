"""W1b, domain office ("Run the office" and "Family and people"), cards 51 to 100 (docs/v3/w1/build51-office.md), proved on the real pack readers.

Built (9): uc-052-insurance (renewals_due), uc-081-payroll (payroll_total), uc-082-covergap (cover_gap), uc-091-jml and uc-092-accessrev (access_review), uc-093-onbmgr
(onboarding_items), uc-095-sopreview (sop_age), uc-097-kycrefresh (kyc_expiry), uc-098-wordlist (terms_proposed). Their numbers come from the recipes' output on the office loaded
by sh_platform/v1/v3_pack_readers (the `office` fixture of test_w2_loader.py) and are compared with answer_keys.yaml, read from the file, never typed.
Not built (11): six read a file kind with no reader, four need a rule the office has only proposed, one a rule nobody has written; the tests below prove why and fail the day
that changes. Synthetic data only."""
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

BUILT = ["uc-052-insurance", "uc-081-payroll", "uc-082-covergap", "uc-091-jml", "uc-092-accessrev", "uc-093-onbmgr", "uc-095-sopreview", "uc-097-kycrefresh", "uc-098-wordlist"]
UNREAD = {  # card -> the file kinds of its key that still have no reader
    "uc-083-taxcal": {"tax_calendar", "tax_notices"},
    "uc-084-taxest": {"tax_calendar"},
    "uc-085-grants": {"grant_ledger"},
    "uc-086-grantappr": {"grant_ledger", "grant_requests"},
    "uc-087-trustdist": {"trust_deed"},
    "uc-088-estateliq": {"estate_planning", "trust_deed"},
}
PROPOSED = {  # card -> the rule codes (prefix) its key rests on, read by the controls readers as PROPOSED rules (A20) and not signed
    "uc-089-expapp": "approver_limit_",
    "uc-090-offcost": "office_budget_",
    "uc-094-onbbank": "signing_policy",
    "uc-100-famaccess": "family_access_",
}
NO_RULE = {"uc-096-automation"}  # 45 minutes of rework per failure: in the key's method only, in no file and no rule
OWN = ["renewals_due", "payroll_total", "cover_gap", "access_review", "onboarding_items", "sop_age", "kyc_expiry", "terms_proposed"]


def kinds_of(card: str) -> set[str]:
    """The file kinds (folder names) in the card's input_files: '*/kind/file' or 'kind/file'."""
    return {m.group(1) for f in KEYS[card]["input_files"] if (m := re.match(r"(?:\*/)?([a-z_]+)/", f))}


def test_the_domain_has_twenty_cards_and_each_is_built_or_has_a_reason():
    assert len(CARDS) == 20, CARDS
    assert sorted(BUILT + list(UNREAD) + list(PROPOSED) + list(NO_RULE)) == sorted(CARDS)


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


# ---- the cards that are not built: proof of the reason ------------------------------------------------------------------------------------

@pytest.mark.parametrize("card", sorted(UNREAD))
def test_every_unread_kind_of_an_unbuilt_card_is_still_unread(card, office):
    unread = {k for k in kinds_of(card) if k in office.report and "no reader for this kind" in office.report[k]["not_loaded"]}
    assert unread == UNREAD[card], f"{card}: the kinds without a reader changed ({sorted(unread)}); build the card (docs/v3/w1/build51-office.md)"


@pytest.mark.parametrize("card", sorted(PROPOSED))
def test_cards_whose_rule_is_only_proposed_wait_for_it_to_be_signed(card, office):
    assert not {k for k in kinds_of(card) if k in office.report and "no reader for this kind" in office.report[k]["not_loaded"]}, card  # every file is read
    rows = office.rows("select r.rule_code, v.approval_status from business_rules as r join rule_versions as v on v.business_rule_id = r.id where starts_with(r.rule_code, ?)", PROPOSED[card])
    assert rows and {r["approval_status"] for r in rows} == {"proposed"}, f"{card}: a rule is signed now ({rows}); build the card (docs/v3/w1/build51-office.md)"


def test_card96_has_no_rule_for_the_rework_minutes(office):
    assert office.one("select count(*) from business_rules where rule_code like '%rework%' or rule_code like '%automation%'") == 0
    assert "45 minutes of rework per failure" in KEYS["uc-096-automation"]["questions"]["Which process to automate"]["how"]


# ---- recipes: shape ---------------------------------------------------------------------------------------------------------------------

def test_every_recipe_of_the_slice_is_ready_and_reads_only_what_it_may():
    for rid in OWN:
        r = R.recipe(rid)
        assert r and r.get("status") != "stub" and r["sql"] and r["measure"] and r["grain"] and r["tie_out"] and r["cards"] and r["why"], rid
        assert R.refusal(r, R.render(r, "t")) is None, rid
        assert "business_rules" not in r["may_read"], rid  # no recipe of the slice leans on a rule


def test_new_recipes_bind_the_cards_figures_and_leave_the_others_alone():
    for n, rid in [("Policies expiring in 60 days", "renewals_due"), ("Payroll total against last month", "payroll_total"), ("Insured value less asset value", "cover_gap"),
                   ("Access given but not approved", "access_review"), ("Access not used in 90 days", "access_review"), ("Items complete and outstanding", "onboarding_items"),
                   ("SOPs by last review", "sop_age"), ("Documents expiring in 90 days", "kyc_expiry"), ("Terms proposed and accepted", "terms_proposed")]:
        assert (R.match({"name": n}) or {}).get("id") == rid, n
    for n in ["Vendor contract renewals", "Payment batch", "Family allowances due", "Net worth by portfolio", "Cash by entity", "Statements missing by fund", "Called to date"]:
        assert (R.match({"name": n}) or {}).get("id") not in OWN, n


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
        assert any(sid.startswith(card + "-") and EXPECTED[sid][1] == "problem" for sid in EXPECTED) or card in ("uc-092-accessrev", "uc-095-sopreview", "uc-098-wordlist"), card


@pytest.fixture(scope="module")
def figs(office) -> dict[str, list[dict]]:
    return {rid: office.run(rid) for rid in OWN}


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
