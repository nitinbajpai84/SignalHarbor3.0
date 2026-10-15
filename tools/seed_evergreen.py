"""Seed Evergreen Office, the v2 demo company (fictional, synthetic): people, entities, funds, rules, history and one issued report.

Usage: python tools/seed_evergreen.py [--data-root PATH] [--reset]
Idempotent: the company, accounts and warehouse history are made once and left alone after. `--reset` clears only this company's
warehouse and rebuilds it (accounts are kept). Passwords go only to <data_root>/_control/seed_credentials.txt and are never printed.

The story (all dates 2026): Fund A "Evergreen Growth I" is estimated at 10,000,000 USD, valued 30 Sep, received 2 Oct. The September
investment report is issued on 3 Oct with cutoff 3 Oct (A 10.00m, B 6.40m, liquid 41.20m, total 57.60m). On 8 Oct Entity B cash
differs by 12,400 USD between the administrator and the trading export. The amended statement (10,180,000) is NOT loaded: the demo
drops it in live (tools/make_e2_statements.py makes the PDF).

Facts are written with SQL and an explicit `recorded_at`, because the history is back-dated and e1_write stamps "now". The report is
written with the same rows e1_reports.issue writes, but dated 3 Oct (issue stamps "now"); no UPDATE is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.auth.accounts import AccountStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.jsonfile import lock_for  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from sh_platform.v1 import e1_write, wh  # noqa: E402
from tools.seed import DOMAIN, HEADER, _new_password  # noqa: E402

log = logging.getLogger(__name__)
COMPANY, NAME, INDUSTRY = "evergreen", "Evergreen Office", "family_office"
REPORT = "september_investment_report"
FX_SERIES = "FX:USDSGD:WMR_4PM"

# (name, business role in the office, platform role)
PEOPLE = [
    ("Daniel Foo", "Chief Investment Officer", "sponsor"),
    ("Mei Chen", "Operations lead", "owner"),  # ROLE1: the business owner, not the data team
    ("Raj Patel", "Finance", "approver"),
    ("Sofia Reyes", "Risk", "participant"),
    ("Anita Rao", "Head of data", "analyst"),
    ("Leo Park", "Data engineer", "analyst"),
    ("Grace Ong", "Company admin", "company_admin"),
]
# ROLE1: Daniel sponsor, Mei business owner (owner), Raj approver, Anita head of data (head_of_data + analyst), Leo data engineer and ops manager (analyst), Grace administrator
EXTRA_ROLES = {"Anita Rao": ["head_of_data"]}  # V6: the head of data seat (approves the design pack, the plan and the verified map), held beside analyst


def utc(y, m, d, h=0, mi=0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def email_of(name: str) -> str:
    return f"{'.'.join(name.lower().split())}.{COMPANY}@{DOMAIN}"


def put(con, table: str, row: dict) -> str:
    row = {"id": wh.new_id(), **row}
    cols = list(row)
    con.execute(f"insert into {table} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})", list(row.values()))
    return row["id"]


# ---------- platform: company and accounts ----------

def company(data_root: Path) -> bool:
    es = EntitlementStore(data_root)
    made = es.company(COMPANY) is None
    if made:
        es.create_company(COMPANY, NAME, INDUSTRY, modules=es.catalogue.ids)
    for m in es.catalogue.ids:  # a re-run switches on what is off, never off what is on
        if not es.is_enabled(COMPANY, m):
            es.set_module(COMPANY, m, True)
    return made


def accounts(data_root: Path) -> tuple[dict[str, str], int]:
    store, lines, ids = AccountStore(data_root), [], {}
    for name, _, role in PEOPLE:
        acct = store.get_by_email(email_of(name))
        if acct is None:
            password = _new_password()
            acct = store.create(email_of(name), password, name, COMPANY, [role, *EXTRA_ROLES.get(name, [])])
            lines.append(f"{email_of(name)}  {password}  {role}  {COMPANY}")
        elif set(acct["roles"]) != {role, *EXTRA_ROLES.get(name, [])} and name == "Mei Chen":  # ROLE1: an environment seeded when Mei was on the data team moves her to the owner seat
            store.set_roles(email_of(name), [role])
        elif set(EXTRA_ROLES.get(name, [])) - set(acct["roles"]):  # V6: an environment seeded before the head of data seat gets it too
            store.add_roles(email_of(name), EXTRA_ROLES[name])
        ids[name] = acct["account_id"]
    if lines:
        creds = data_root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else HEADER
            creds.write_text(old.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return ids, len(lines)


# ---------- warehouse ----------

def _batch(con, org, system, ref, received, period_end, payloads, total_measure=None):
    """A source batch with one source record per payload and control totals that add up. Returns the record ids."""
    uri = f"seed://evergreen/{ref.replace(' ', '_')}"
    bid = put(con, "source_batches", dict(
        organization_id=org, source_system_id=system, batch_reference=ref, received_at=received, loaded_at=received,
        source_period_end=period_end, content_hash=hashlib.sha256(ref.encode()).hexdigest(), storage_uri=uri,
        validation_status="loaded", validation_summary="Row count and totals match the file."))
    rids = []
    for i, p in enumerate(payloads):
        text = json.dumps(p, sort_keys=True, default=str)
        rids.append(put(con, "source_records", dict(
            organization_id=org, source_batch_id=bid, external_record_id=f"{ref}:{i + 1}", record_type=p.get("type", "row"),
            effective_at=received, received_at=received, recorded_at=received, sheet_name="Sheet1", row_number=i + 2,
            cell_range=f"A{i + 2}:H{i + 2}", raw_payload_uri=uri, content_hash=hashlib.sha256(text.encode()).hexdigest(),
            quality_status="clean")))
    put(con, "batch_control_totals", dict(organization_id=org, source_batch_id=bid, measure_name="row count",
                                          expected_value=len(payloads), loaded_value=len(payloads), tolerance=0, passed=True))
    if total_measure:
        total = sum(Decimal(str(p["amount"])) for p in payloads)
        put(con, "batch_control_totals", dict(organization_id=org, source_batch_id=bid, measure_name=total_measure,
                                              expected_value=total, loaded_value=total, tolerance=Decimal("0.01"), passed=True))
    return rids


def _calc_version() -> str:
    try:
        from sh_platform.v1 import e3_calc
        return str(e3_calc.CALC_VERSION)
    except (ImportError, AttributeError):
        return "seed-evergreen-1"


def _issue_fallback(con, org, lines, period_end, cutoff, issued_at, approver):
    """What e1_reports.issue writes (same rows, same evidence note "<table>:<row id>"), for a tree where card E1c is not installed."""
    report_id = put(con, "reports", dict(organization_id=org, report_code=REPORT, report_name="September investment report",
                                         audience="Chief Investment Officer", reporting_currencies="USD,SGD"))
    run = put(con, "calculation_runs", dict(
        organization_id=org, started_at=issued_at, finished_at=issued_at, knowledge_cutoff_at=cutoff, reporting_date=period_end,
        code_version=_calc_version(), input_manifest_uri="seed://evergreen/september", run_status="finished",
        validation_status="passed"))
    defs = {c: put(con, "metric_definitions", dict(
        organization_id=org, metric_code=c, metric_name=n, version_number=1, definition_text=t, implementation_ref="seed:sum",
        owner_user_id=approver, approval_status="approved"))
        for c, n, t in (("holding_value", "Holding value", "Value of one holding at the period end."),
                        ("portfolio_total", "Portfolio total", "Sum of the holding values."))}
    for ln in lines:
        mv = put(con, "metric_values", dict(
            organization_id=org, calculation_run_id=run, metric_definition_id=defs[ln["metric_code"]], portfolio_id=ln.get("portfolio_id"),
            instrument_id=ln.get("instrument_id"), reporting_date=period_end, numeric_value=ln["value"], currency=ln["currency"],
            value_status=ln["status"], published_at=issued_at))
        for table, row_id in ln.get("sources", []):
            src = con.execute(f"select source_record_id from {table} where id = ?", [row_id]).fetchone()[0]
            put(con, "metric_evidence", dict(organization_id=org, metric_value_id=mv, source_record_id=src,
                                             evidence_role="input", note=f"{table}:{row_id}"))
    return put(con, "report_versions", dict(
        organization_id=org, report_id=report_id, calculation_run_id=run, period_end=period_end, cutoff_at=cutoff, status="issued",
        approved_by=approver, issued_at=issued_at))


def _seed_warehouse(plane, ids: dict[str, str]) -> dict:
    with wh.connect(plane) as con:
        org = e1_write.org_id(plane)
        if con.execute("select count(*) from legal_entities").fetchone()[0]:
            return {"warehouse": "kept"}
        con.execute("begin")
        put_org = dict(id=org, name=NAME, created_at=utc(2026, 1, 1))
        put(con, "organizations", put_org)
        uid = {}
        for name, role, _ in PEOPLE:
            uid[name] = put(con, "users", dict(organization_id=org, external_identity_id=ids[name], display_name=name,
                                               email=email_of(name), business_role=role, is_active=True, created_at=utc(2026, 1, 1)))
        cio, mei, raj, risk, head, eng = (uid[n] for n in ("Daniel Foo", "Mei Chen", "Raj Patel", "Sofia Reyes", "Anita Rao", "Leo Park"))

        # entities and portfolios
        ent = {c: put(con, "legal_entities", dict(organization_id=org, entity_code=c, entity_name=n, base_currency="USD",
                                                  active_from=date(2020, 1, 1)))
               for c, n in (("EG-HOLD", "Evergreen Holdings"), ("EG-TRUST", "Evergreen Family Trust"), ("EG-B", "Entity B"))}
        pf = {c: put(con, "portfolios", dict(organization_id=org, legal_entity_id=ent[e], portfolio_code=c, portfolio_name=n,
                                             base_currency="USD", active_from=date(2020, 1, 1)))
              for c, e, n in (("EG-GROWTH", "EG-HOLD", "Evergreen Growth portfolio"), ("EG-LIQUID", "EG-TRUST", "Evergreen Liquid portfolio"),
                              ("EG-B-OPS", "EG-B", "Entity B operating portfolio"))}

        # access: entities and one document type per group
        grp = {}
        for g, desc, members, level in (("Investment office", "Runs the office day to day", (cio, mei, raj, risk), "full"),
                                        ("Data team", "Loads and checks data", (head, eng), "read")):
            grp[g] = put(con, "access_groups", dict(organization_id=org, group_name=g, description=desc))
            for e in ent.values():
                put(con, "access_group_scopes", dict(organization_id=org, access_group_id=grp[g], scope_type="legal_entity",
                                                     scope_value=e, access_level=level))
            put(con, "access_group_scopes", dict(organization_id=org, access_group_id=grp[g], scope_type="document_type",
                                                 scope_value="manager_statement", access_level="read" if level == "read" else "full"))
            for m in members:
                put(con, "access_group_memberships", dict(organization_id=org, access_group_id=grp[g], user_id=m,
                                                          granted_at=utc(2026, 1, 1), granted_by=uid["Grace Ong"]))

        # source systems
        sysid = {c: put(con, "source_systems", dict(organization_id=org, source_code=c, source_name=n, source_type=t, connection_method=cm,
                                                    owner_user_id=mei, permitted_use="may_index", expected_cadence=cad, is_active=True))
                 for c, n, t, cm, cad in (("administrator", "Fund administrator", "administrator", "file drop", "daily"),
                                          ("trading_export", "Trading system export", "OMS", "file drop", "daily"),
                                          ("manager_email", "Manager statements by email", "manager", "email", "monthly"),
                                          ("market_data", "Market data file", "market_data", "file drop", "daily"))}

        # instruments and identifiers
        ins = {c: put(con, "instruments", dict(organization_id=org, canonical_name=n, instrument_type=t, asset_class=a, manager_name=m,
                                               currency="USD", created_at=utc(2026, 1, 1)))
               for c, n, t, a, m in (("A", "Evergreen Growth I", "private_fund", "private_equity", "Northgate Partners"),
                                     ("B", "Evergreen Income II", "private_fund", "private_credit", "Bluewater Capital"),
                                     ("LIQ", "Evergreen Liquid Book", "liquid_book", "listed", None),
                                     ("CASH", "Cash", "cash", "cash", None))}
        # manager_email names exactly as tools/make_e2_statements.py prints them (Fund B's statement says "Evergreen Liquid Book", but its
        # 6.4m value is the seed's Fund B, Evergreen Income II, so that name is approved for B)
        for iid, sysc, typ, val, who in ((ins["A"], "manager_email", "manager_fund_name", "EG Growth Fund I", mei),
                                         (ins["A"], "manager_email", "manager_fund_name", "Fund A - Evergreen Growth I", mei),
                                         (ins["A"], "manager_email", "manager_fund_name", "Evergreen Growth I", mei),
                                         (ins["B"], "manager_email", "manager_fund_name", "Fund B - Evergreen Liquid Book", mei),
                                         (ins["B"], "manager_email", "manager_fund_name", "Fund B - Evergreen Income II", mei),
                                         (ins["B"], "manager_email", "manager_fund_name", "Evergreen Income II", mei),
                                         (ins["A"], "administrator", "administrator_code", "4471", mei)):
            put(con, "instrument_identifiers", dict(organization_id=org, instrument_id=iid, source_system_id=sysid[sysc], identifier_type=typ,
                                                    identifier_value=val, valid_from=date(2026, 1, 1), mapping_status="approved",
                                                    approved_by=who, approved_at=utc(2026, 2, 1)))

        # signed rules (owner proposes, the CIO signs; never the same person)
        rules = (("cash_tolerance", "tolerance", raj, "Cash may differ by up to 5,000 USD per entity per day before it needs a case.",
                  {"abs_amount": 5000, "currency": "USD", "per": "entity_day"}),
                 ("cio_materiality", "materiality", raj, "The CIO sees a change over 100,000 USD or 0.5% of a fund.",
                  {"abs_amount": 100000, "currency": "USD", "pct_of_fund": 0.5}),
                 ("estimate_use", "policy", raj, "A manager estimate may be used in the investment report only.",
                  {"allowed_in": ["investment_report"]}),
                 ("statement_due", "deadline", mei, "A manager statement is due within 10 business days of the period end.",
                  {"business_days_after_month_end": 10}),
                 ("fx_fixing", "fixing", raj, "Convert with the WMR 4pm USD/SGD fixing in the market data file.",
                  {"fixing": "WMR_4PM", "series_key": "FX:USDSGD:WMR_4PM"}))
        for code, typ, owner, text, params in rules:
            rid = put(con, "business_rules", dict(organization_id=org, rule_code=code, rule_type=typ, owner_user_id=owner))
            put(con, "rule_versions", dict(organization_id=org, business_rule_id=rid, version_number=1, definition_text=text,
                                           parameters=json.dumps(params), effective_from=date(2026, 1, 1), approval_status="approved",
                                           approved_by=cio, approved_at=utc(2026, 1, 5)))

        # market data: month-end and latest USD/SGD
        mrec = _batch(con, org, sysid["market_data"], "fx 2026-10-01", utc(2026, 10, 1, 1), date(2026, 9, 30),
                      [{"type": "fx", "amount": "1.3412"}, {"type": "fx", "amount": "1.3388"}])
        for rec, when, val in ((mrec[0], utc(2026, 9, 30, 8), "1.3412"), (mrec[1], utc(2026, 10, 8, 8), "1.3388")):
            put(con, "market_observations", dict(organization_id=org, source_record_id=rec, series_key=FX_SERIES, observation_type="fx",
                                                 observed_at=when, received_at=utc(2026, 10, 1, 1), recorded_at=utc(2026, 10, 1, 1),
                                                 value=Decimal(val), base_currency="USD", quote_currency="SGD", quality_status="clean"))

        # valuations as at 30 Sep: Fund A estimate (received 2 Oct), Fund B final, liquid book positions
        a_rec, = _batch(con, org, sysid["manager_email"], "northgate statement 2026-09-30", utc(2026, 10, 2, 5), date(2026, 9, 30),
                        [{"type": "statement", "amount": "10000000", "label": "Estimate"}], "total value")
        b_rec, = _batch(con, org, sysid["manager_email"], "bluewater statement 2026-09-30", utc(2026, 10, 1, 5), date(2026, 9, 30),
                        [{"type": "statement", "amount": "6400000", "label": "Final"}], "total value")
        val = {}
        for key, rec, recd, amount, vtype, status in (("A", a_rec, utc(2026, 10, 2, 5), 10_000_000, "manager_estimate", "estimated"),
                                                      ("B", b_rec, utc(2026, 10, 1, 5), 6_400_000, "manager_final", "approved")):
            val[key] = put(con, "valuation_observations", dict(
                organization_id=org, instrument_id=ins[key], portfolio_id=pf["EG-GROWTH"], source_record_id=rec, valuation_date=date(2026, 9, 30),
                received_at=recd, recorded_at=recd + (utc(2026, 1, 1, 0, 10) - utc(2026, 1, 1)), value_amount=Decimal(amount), currency="USD",
                valuation_type=vtype, approval_status=status))
        l_rec, = _batch(con, org, sysid["administrator"], "liquid book 2026-09-30", utc(2026, 10, 1, 6), date(2026, 9, 30),
                        [{"type": "position", "amount": "41200000"}], "total market value")
        liq = put(con, "position_snapshots", dict(
            organization_id=org, source_record_id=l_rec, portfolio_id=pf["EG-LIQUID"], instrument_id=ins["LIQ"], position_date=date(2026, 9, 30),
            as_of_at=utc(2026, 9, 30, 16), received_at=utc(2026, 10, 1, 6), recorded_at=utc(2026, 10, 1, 6, 5), quantity=Decimal(1),
            source_market_value=Decimal(41_200_000), currency="USD", view_type="investment", data_status="official"))

        # administrator NAV for the growth portfolio, 30 Sep (the official view; never touched by estimates)
        n_rec, = _batch(con, org, sysid["administrator"], "nav 2026-09-30", utc(2026, 10, 2, 6), date(2026, 9, 30),
                        [{"type": "nav", "amount": "16400000"}], "total nav")
        put(con, "nav_snapshots", dict(organization_id=org, portfolio_id=pf["EG-GROWTH"], source_record_id=n_rec, nav_period_end=date(2026, 9, 30),
                                       received_at=utc(2026, 10, 2, 6), recorded_at=utc(2026, 10, 2, 6, 5), nav_amount=Decimal(16_400_000),
                                       currency="USD", nav_status="approved_official", approved_at=utc(2026, 10, 2, 7)))

        # cash on 8 Oct, two views per entity: accounting = administrator, operational = trading export.
        # Entity B differs by 12,400 (over the 5,000 tolerance); the Trust differs by 1,800 (inside it).
        cash = (("EG-HOLD", "EG-GROWTH", 2_300_000, 2_300_000), ("EG-TRUST", "EG-LIQUID", 1_150_000, 1_148_200),
                ("EG-B", "EG-B-OPS", 880_400, 868_000))
        for view, system, ref, col, status in (("accounting", "administrator", "cash 2026-10-08 administrator", 2, "official"),
                                               ("operational", "trading_export", "cash 2026-10-08 trading export", 3, "indicative")):
            recs = _batch(con, org, sysid[system], ref, utc(2026, 10, 8, 22), date(2026, 10, 8),
                          [{"type": "cash", "amount": str(c[col])} for c in cash], "total cash")
            for c, rec in zip(cash, recs):
                put(con, "position_snapshots", dict(
                    organization_id=org, source_record_id=rec, portfolio_id=pf[c[1]], instrument_id=ins["CASH"], position_date=date(2026, 10, 8),
                    as_of_at=utc(2026, 10, 8, 16), received_at=utc(2026, 10, 8, 22), recorded_at=utc(2026, 10, 8, 22, 5),
                    quantity=Decimal(c[col]), source_market_value=Decimal(c[col]), currency="USD", view_type=view, data_status=status))

        # the September investment report, issued 3 Oct, cutoff 3 Oct
        cutoff, issued = utc(2026, 10, 3, 10), utc(2026, 10, 3, 10, 30)
        lines = [dict(metric_code="holding_value", label="Evergreen Growth I", portfolio_id=pf["EG-GROWTH"], instrument_id=ins["A"],
                      value=Decimal(10_000_000), currency="USD", status="estimated", sources=[("valuation_observations", val["A"])]),
                 dict(metric_code="holding_value", label="Evergreen Income II", portfolio_id=pf["EG-GROWTH"], instrument_id=ins["B"],
                      value=Decimal(6_400_000), currency="USD", status="official", sources=[("valuation_observations", val["B"])]),
                 dict(metric_code="holding_value", label="Liquid book", portfolio_id=pf["EG-LIQUID"], instrument_id=ins["LIQ"],
                      value=Decimal(41_200_000), currency="USD", status="official", sources=[("position_snapshots", liq)]),
                 dict(metric_code="portfolio_total", label="Total", value=Decimal(57_600_000), currency="USD", status="estimated", sources=[])]
        con.execute("commit")
    # e1_reports.issue stamps issued_at = now, but the September report was issued on 3 Oct: write the same rows with that date.
    # ponytail: replace with e1_reports.issue(..., issued_at=issued) once E1c accepts it.
    with wh.connect(plane) as con:
        _issue_fallback(con, org, lines, date(2026, 9, 30), cutoff, issued, cio)
    return {"warehouse": "built"}


def reset_warehouse(plane) -> None:
    """Delete this company's warehouse file (and its log). Only ever called on the evergreen plane."""
    assert plane.company_id == COMPANY
    for suffix in ("", ".wal"):
        p = Path(str(wh.path(plane)) + suffix)
        if p.is_file():
            p.unlink()
    wh.reset_cache()


def seed(data_root: Path, reset: bool = False) -> dict:
    data_root = Path(data_root)
    made = company(data_root)
    plane = PlaneStore(data_root).plane_for(COMPANY).ensure()
    ids, created = accounts(data_root)
    if reset:
        reset_warehouse(plane)
    out = {"company_created": made, "accounts_created": created, "accounts": len(ids), **_seed_warehouse(plane, ids)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    ap.add_argument("--reset", action="store_true", help="clear and rebuild the evergreen warehouse only")
    a = ap.parse_args(argv)
    raw = a.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed(root, a.reset)
    print(f"{NAME} ({COMPANY}): company {'created' if r['company_created'] else 'kept'}, accounts created {r['accounts_created']} of {r['accounts']}, "
          f"warehouse {r['warehouse']}.")
    print(f"Sign-in details are in: {root / '_control' / 'seed_credentials.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
