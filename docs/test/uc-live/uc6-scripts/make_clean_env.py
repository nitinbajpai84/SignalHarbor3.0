"""UC6 run 2, Option A: a clean Evergreen Office with master data only (no ten-use-case history, cases, results or October cash).

    python docs/test/uc-live/uc6-scripts/make_clean_env.py [--root .sh-tmp/testenv/uc6-run2/data] [--today 2026-07-31]

What it writes, all through the repo's own seed pieces and product writers:
- tools/seed_evergreen.company + accounts: the company, its modules, the seven people (passwords only in _control/seed_credentials.txt).
- the master-data part of tools/seed_evergreen._seed_warehouse (copied below, the transactional part left out): organisation, users,
  entities EG-HOLD / EG-TRUST / EG-B, portfolios, access groups, source systems, instruments A, B, LIQ, CASH, identifiers, signed rules.
  Left out on purpose: market data, valuations, NAV, the 8 Oct cash (880,400 etc.) and the September report.
- tools/seed_10uc._static: funds C, D, E (and the other universe funds), managers' identifiers, the cash_call_alert_days rule, benchmark.
- tools/seed_10uc._owner: the family principal account.
- the commitment register (5 contracts signed 2021-2024) through the product writer k6_liquidity.record_commitment, because the product
  has no screen or route that loads commitments (workaround W2 in UC6-RUNBOOK.md). No calls, no called-to-date history.
- the company clock pinned to --today (wh.set_demo_today), the cycle date (workaround W1). Re-run with --today to move the calendar.
Refuses to touch the repo data/ folder.
"""
import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import e1_write, wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402
from tools import seed_10uc as SU  # noqa: E402

put, utc = EG.put, EG.utc


def master(plane, ids):
    with wh.connect(plane) as con:
        org = e1_write.org_id(plane)
        if con.execute("select count(*) from legal_entities").fetchone()[0]:
            return "kept"
        con.execute("begin")
        put(con, "organizations", dict(id=org, name=EG.NAME, created_at=utc(2026, 1, 1)))
        uid = {n: put(con, "users", dict(organization_id=org, external_identity_id=ids[n], display_name=n, email=EG.email_of(n),
                                         business_role=r, is_active=True, created_at=utc(2026, 1, 1))) for n, r, _ in EG.PEOPLE}
        cio, mei, raj, risk, head, eng = (uid[n] for n in ("Daniel Foo", "Mei Chen", "Raj Patel", "Sofia Reyes", "Anita Rao", "Leo Park"))
        ent = {c: put(con, "legal_entities", dict(organization_id=org, entity_code=c, entity_name=n, base_currency="USD", active_from=date(2020, 1, 1)))
               for c, n in (("EG-HOLD", "Evergreen Holdings"), ("EG-TRUST", "Evergreen Family Trust"), ("EG-B", "Entity B"))}
        for c, e, n in (("EG-GROWTH", "EG-HOLD", "Evergreen Growth portfolio"), ("EG-LIQUID", "EG-TRUST", "Evergreen Liquid portfolio"),
                        ("EG-B-OPS", "EG-B", "Entity B operating portfolio")):
            put(con, "portfolios", dict(organization_id=org, legal_entity_id=ent[e], portfolio_code=c, portfolio_name=n, base_currency="USD",
                                        active_from=date(2020, 1, 1)))
        for g, desc, members, level in (("Investment office", "Runs the office day to day", (cio, mei, raj, risk), "full"),
                                        ("Data team", "Loads and checks data", (head, eng), "read")):
            gid = put(con, "access_groups", dict(organization_id=org, group_name=g, description=desc))
            for e in ent.values():
                put(con, "access_group_scopes", dict(organization_id=org, access_group_id=gid, scope_type="legal_entity", scope_value=e, access_level=level))
            put(con, "access_group_scopes", dict(organization_id=org, access_group_id=gid, scope_type="document_type", scope_value="manager_statement",
                                                 access_level="read" if level == "read" else "full"))
            for m in members:
                put(con, "access_group_memberships", dict(organization_id=org, access_group_id=gid, user_id=m, granted_at=utc(2026, 1, 1), granted_by=uid["Grace Ong"]))
        sysid = {c: put(con, "source_systems", dict(organization_id=org, source_code=c, source_name=n, source_type=t, connection_method=cm,
                                                    owner_user_id=mei, permitted_use="may_index", expected_cadence=cad, is_active=True))
                 for c, n, t, cm, cad in (("administrator", "Fund administrator", "administrator", "file drop", "daily"),
                                          ("trading_export", "Trading system export", "OMS", "file drop", "daily"),
                                          ("manager_email", "Manager statements by email", "manager", "email", "monthly"),
                                          ("market_data", "Market data file", "market_data", "file drop", "daily"))}
        ins = {c: put(con, "instruments", dict(organization_id=org, canonical_name=n, instrument_type=t, asset_class=a, manager_name=m, currency="USD",
                                               created_at=utc(2026, 1, 1)))
               for c, n, t, a, m in (("A", "Evergreen Growth I", "private_fund", "private_equity", "Northgate Partners"),
                                     ("B", "Evergreen Income II", "private_fund", "private_credit", "Bluewater Capital"),
                                     ("LIQ", "Evergreen Liquid Book", "liquid_book", "listed", None), ("CASH", "Cash", "cash", "cash", None))}
        put(con, "instrument_identifiers", dict(organization_id=org, instrument_id=ins["A"], source_system_id=sysid["administrator"],
                                                identifier_type="administrator_code", identifier_value="4471", valid_from=date(2026, 1, 1),
                                                mapping_status="approved", approved_by=mei, approved_at=utc(2026, 2, 1)))
        rules = (("cash_tolerance", "tolerance", raj, "Cash may differ by up to 5,000 USD per entity per day before it needs a case.",
                  {"abs_amount": 5000, "currency": "USD", "per": "entity_day"}),
                 ("cio_materiality", "materiality", raj, "The CIO sees a change over 100,000 USD or 0.5% of a fund.", {"abs_amount": 100000, "currency": "USD", "pct_of_fund": 0.5}),
                 ("estimate_use", "policy", raj, "A manager estimate may be used in the investment report only.", {"allowed_in": ["investment_report"]}),
                 ("statement_due", "deadline", mei, "A manager statement is due within 10 business days of the period end.", {"business_days_after_month_end": 10}),
                 ("fx_fixing", "fixing", raj, "Convert with the WMR 4pm USD/SGD fixing in the market data file.", {"fixing": "WMR_4PM", "series_key": EG.FX_SERIES}))
        for code, typ, owner, text, params in rules:
            rid = put(con, "business_rules", dict(organization_id=org, rule_code=code, rule_type=typ, owner_user_id=owner))
            put(con, "rule_versions", dict(organization_id=org, business_rule_id=rid, version_number=1, definition_text=text, parameters=json.dumps(params),
                                           effective_from=date(2026, 1, 1), approval_status="approved", approved_by=cio, approved_at=utc(2026, 1, 5)))
        con.execute("commit")
    return "made"


def commitments(plane):
    from sh_platform.v1 import k6_liquidity as K6
    if K6.commitments(plane):
        return "kept"
    m = SU._maps(plane)
    for c in SU.U["commitments"]:
        K6.record_commitment(plane, {"legal_entity_id": m["ent"][c["legal_entity"]], "instrument_id": m["ins"][c["fund"]],
                                     "commitment_amount": Decimal(c["commitment_amount"]), "currency": c["currency"],
                                     "committed_on": date.fromisoformat(c["committed_on"])})
    return "made"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / ".sh-tmp" / "testenv" / "uc6-run2" / "data"))
    ap.add_argument("--today", default="2026-07-31")
    ap.add_argument("--no-commitments", action="store_true", help="run 3: commitments come from the intake of the commitments workbook")
    ap.add_argument("--clock-only", action="store_true", help="only move the company clock (between months)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if root == (ROOT / "data").resolve():
        raise SystemExit("refusing the repo data/ folder")
    root.mkdir(parents=True, exist_ok=True)
    if a.clock_only:
        wh.set_demo_today(PlaneStore(root).plane_for(EG.COMPANY), date.fromisoformat(a.today))
        print(json.dumps({"today": a.today}))
        return
    EG.company(root)
    plane = PlaneStore(root).plane_for(EG.COMPANY).ensure()
    wh.set_demo_today(plane, date.fromisoformat(a.today))
    ids, made = EG.accounts(root)
    out = {"accounts_created": made, "master": master(plane, ids)}
    out.update(SU._static(plane, ids))
    out.update(SU._owner(root, plane))
    out["commitments"] = "left to intake" if a.no_commitments else commitments(plane)
    with wh.connect(plane, read_only=True) as con:
        for t in ("legal_entities", "portfolios", "instruments", "commitments", "cash_movements", "position_snapshots", "exceptions",
                  "valuation_observations", "source_batches", "reports"):
            out[t] = con.execute(f"select count(*) from {t}").fetchone()[0]
    out["today"] = a.today
    print(json.dumps(out))


if __name__ == "__main__":
    main()
