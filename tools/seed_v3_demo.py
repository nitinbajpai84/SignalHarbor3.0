"""Seed the v3 demo project on Evergreen Office (card X1): one project that runs through Intent, Build, Consume and Action.

Usage: python tools/seed_v3_demo.py [--data-root PATH]
Starts from tools/seed_evergreen.py (company, people, warehouse; made once, kept after). Then, each step only when it is not yet there:
  1. Intent    a signed intent of work "Monthly investment report in USD and SGD" with sources, KPIs and a swim-lane process map (project id)
  2. Build     bronze tables for the administrator and trading exports, an approved build plan (fact 5), gold tables, a sandbox run and a live run
  3. Consume   a dashboard with three accepted tiles shared with the CIO and Finance (fact 8)
Idempotent: a second run changes nothing. Writes only to the company's data plane. Synthetic data only. No model call is made.
The records are written to the formats in docs/plan/V3-CENTRES-CARDS.md (facts 5, 7, 8) so the Build and Consume cards read them as their own.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import time
from types import SimpleNamespace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.jsonfile import read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile.view import Viewer  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from sh_platform.v1 import (b1_design, b2_scan, b3_mapping, b4_load, b6_plan, b6_run, b6_span, g1_access, g4_deviations, i2_north,  # noqa: E402
                            p1_project, wh)
from tools import seed_evergreen as EG  # noqa: E402

log = logging.getLogger(__name__)
TITLE = "Monthly investment report in USD and SGD"
SLUG = "investment_report"
HOLDINGS, CASH, BENCH = f"gold_{SLUG}_holdings_monthly", f"gold_{SLUG}_cash_daily", f"gold_{SLUG}_benchmark_monthly"
BRONZE_ADMIN, BRONZE_TRADE = "bronze_administrator_positions", "bronze_trading_export_positions"
SILVER = ("position_snapshots", "valuation_observations", "portfolios", "legal_entities", "instruments", "market_observations")
FX = "FX:USDSGD:WMR_4PM"
DASH_ID = "dash-0ad2b1c7"  # C1 id rule: dash-<8 hex>; tiles t-<6 hex>
CIO, FINANCE, HEAD, ENGINEER, OPS, RISK = "Daniel Foo", "Raj Patel", "Anita Rao", "Leo Park", "Mei Chen", "Sofia Reyes"
DEMO_TODAY = date(2026, 10, 9)  # the day the demo story is set on (company setting demo_today)


def _landing_table(table: str, source: str, feeds: list[str], meaning: str, fields: list[tuple[str, str]]) -> dict:
    return {"table": table, "layer": "landing", "source_id": source, "feeds_kpis": feeds, "meaning": meaning,
            "fields": [{"name": n, "type": t, "source_field": n, "meaning": n.replace("_", " ")} for n, t in fields]}


POS = [("portfolio_code", "text"), ("instrument_name", "text"), ("position_date", "date"), ("market_value", "decimal"), ("currency", "text")]
CATALOGUE = [  # what lands, per source: the scan checks these fields against the landed files, the mapping sheet is drafted from them
    _landing_table("administrator_positions", "administrator", ["K01", "K02", "K03", "K04"], "Positions and cash as the administrator export lands them.", POS),
    _landing_table("trading_export_positions", "trading_export", ["K02"], "Cash and positions as the trading export lands them.", POS),
    _landing_table("manager_values", "manager_email", ["K01", "K03", "K04"], "Fund values read from the manager statements.",
                   [("manager_name", "text"), ("valuation_date", "date"), ("value_amount", "decimal"), ("currency", "text")]),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# the story's dates, not the seed's run time: Daniel signed the intent on 3 Oct 2026, before the 10:00 UTC cutoff of the September report
SIGNED_AT = "2026-10-03T02:00:00+00:00"


# ---------- the intent of work ----------

def _sow(iid: str) -> dict:
    steps = [
        ("Collect the exports", OPS, "Download the administrator and trading exports each morning.", ["administrator export", "trading export"], ["exports on the shared drive"], "File drop"),
        ("Check cash against the administrator", OPS, "Compare cash by entity by hand in a spreadsheet and note any gap.", ["exports"], ["cash check"], "Excel"),
        ("Collect manager statements", OPS, "Read the manager statements that arrive by email.", ["manager statements"], ["fund values"], "Email"),
        ("Convert to SGD", FINANCE, "Convert the values with the WMR 4pm USD/SGD fixing.", ["fund values", "fixing"], ["values in USD and SGD"], "Excel"),
        ("Review and approve the report", FINANCE, "Review the figures and approve the report for the CIO.", ["values in USD and SGD"], ["approved report"], "Report pack"),
        ("Read the report", CIO, "Read the monthly report and decide what to ask the managers.", ["approved report"], ["questions"], "Report pack"),
    ]
    return {
        "id": f"sow-{iid}", "intent_id": iid, "title": TITLE, "state": "signed", "version": 1,
        "goal": {"line": TITLE, "why": "The investment office needs one trusted monthly view of holdings and cash in both currencies.",
                 "readers": [CIO, FINANCE], "decisions": ["Which fund managers to question", "Whether cash needs to move between entities"],
                 "needed_by": "3rd business day of each month"},
        "process": {"steps": [{"n": i, "name": n, "who": who, "does": does, "inputs": inp, "outputs": out, "system": system}
                              for i, (n, who, does, inp, out, system) in enumerate(steps, 1)],
                    "handovers": [{"from_step": i, "to_step": i + 1, "what": steps[i - 1][4][0]} for i in range(1, len(steps))]},
        "kpis": [
            {"code": "K01", "name": "Net worth by entity", "definition": "Value of each entity's holdings at the month end, in USD and SGD.",
             "formula": "sum of holding values per entity", "unit": "USD", "period": "monthly", "owner": FINANCE, "source_ids": ["administrator", "manager_email"],
             "status": "defined", "pack_suggested": False},
            {"code": "K02", "name": "Cash by entity", "definition": "Cash of each entity per day, administrator view next to the trading view.",
             "formula": "cash balance per entity per day and view", "unit": "USD", "period": "daily", "owner": OPS, "source_ids": ["administrator", "trading_export"],
             "status": "defined", "pack_suggested": False},
            {"code": "K03", "name": "Holdings by status", "definition": "Holding value split by status: official, revised, estimated or unverified.",
             "formula": "sum of holding values per status", "unit": "USD", "period": "monthly", "owner": FINANCE, "source_ids": ["administrator", "manager_email"],
             "status": "defined", "pack_suggested": False},
            {"code": "K04", "name": "Portfolio against benchmark", "definition": "Monthly return of the holdings against the signed office benchmark EG-OFFICE-BLEND.",
             "formula": "portfolio return minus benchmark return, by month", "unit": "%", "period": "monthly", "owner": FINANCE,
             "source_ids": ["administrator", "manager_email"], "status": "defined", "pack_suggested": False},
        ],
        "sources": [
            {"id": "administrator", "code": "administrator", "name": "Fund administrator export", "kind": "file", "structure": "structured",
             "holds": "Positions, cash and NAV", "owner": OPS, "arrives": "daily", "sample_path": "", "fields": []},
            {"id": "trading_export", "code": "trading_export", "name": "Trading system export", "kind": "file", "structure": "structured",
             "holds": "Cash and positions as the desk sees them", "owner": OPS, "arrives": "daily", "sample_path": "", "fields": []},
            {"id": "manager_email", "code": "manager_email", "name": "Manager statements by email", "kind": "document", "structure": "unstructured",
             "holds": "Fund values at the month end", "owner": OPS, "arrives": "monthly", "sample_path": "", "fields": []},
        ],
        "catalogue": CATALOGUE, "governance": [{"rule": "Only the investment office sees entity figures.", "kind": "access", "applies_to": ["all"], "stated_by": CIO}],
        "unclear": [], "signature": {"name": CIO, "role": "sponsor", "at": SIGNED_AT}, "signatures": [],
        # the template's must-fill sections the parts above do not hold (T1 refuses to sign while any is empty)
        "template_fields": {
            "result": "A monthly report: net worth by entity, cash by entity and holdings by status, in USD and SGD, and the portfolio against its benchmark.",
            "success": "The report goes out by the 3rd business day with no copying by hand, and its totals agree with the administrator.",
            "unclear": "Nothing is open: the office benchmark and the fixing were settled before signing.",
            "benchmarks": "September 2026 as issued: Evergreen Growth I 10,000,000 (estimated), Evergreen Income II 6,400,000, Evergreen Liquid Book "
                          "41,200,000, total 57,600,000 USD (77,253,120 SGD at 1.3412).",
            "access": "Only the people you name"},
    }


def _thread(iid: str, at: str) -> dict:
    """The conversation that led to the signed intent: North asked, Daniel answered, North closed (no question left waiting)."""
    def t(by, name, text, need):
        return {"id": f"t_{wh.new_id()[:12]}", "by": by, "name": name, "text": text, "at": at, "need": need, "files": []}
    return {"intent_id": iid, "state": "sow_ready", "needs_done": ["goal", "readers", "frequency", "process", "kpis", "inputs", "rules", "unclear"],
            "turns": [t("person", CIO, TITLE, None), t("north", i2_north.FALLBACK_NAME, i2_north.QUESTIONS["goal"], "goal"),
                      t("person", CIO, "One trusted monthly view of holdings and cash in both currencies, for me and Raj Patel, by the 3rd business day; "
                                       "we decide which managers to question and whether cash moves between entities.", None),
                      t("north", i2_north.FALLBACK_NAME, f"The intent of work is ready. {CIO} signed it and sent it to Build; nothing is waiting here.", None)]}


def intent(plane, ids: dict[str, str]) -> dict:
    """The project (made once, found by its title), its signed intent of work and the people on it."""
    for p in p1_project.all_projects(plane):
        if p.get("title") == TITLE:
            return p
    cio = Viewer(CIO, frozenset({"sponsor"}), False, ids[CIO])
    made = i2_north.create(plane, cio, TITLE)
    iid = made["id"]
    sow = _sow(iid)
    sow["signatures"] = [{**sow["signature"], "version": 1}]
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow)
    write_json_atomic(plane.path("intents", iid, "thread.json"), _thread(iid, sow["signature"]["at"]))
    p = p1_project.project_of(plane, iid)
    for key, name in (("sponsor", CIO), ("builder", ENGINEER), ("head_of_data", HEAD), ("ops", OPS)):
        p = p1_project.set_person(plane, p["id"], key, name)
    # the approver and the risk lead read this project (steps 4 and 5 of the process are Raj's); the hand-off to Build is recorded
    for name, role in ((FINANCE, "approver"), (RISK, "participant")):
        g1_access.join(plane, p["id"], name, role, ids[name])
    write_json_atomic(plane.path("intents", iid, "send_to_build.json"), {"by": CIO, "at": sow["signature"]["at"], "project_id": p["id"]})
    return p1_project.read(plane, p["id"])


# ---------- build: bronze, plan, runs ----------

def _cols(names_types: str) -> list[dict]:
    return [{"name": n, "type": t, "from": f} for n, t, f in (x.split(":") for x in names_types.split(","))]


BRONZE_SQL = """select
  p.portfolio_code,
  i.canonical_name as instrument_name,
  s.position_date,
  s.source_market_value as market_value,
  s.currency,
  b.batch_reference as file_name,
  b.loaded_at
from position_snapshots s
join portfolios p on p.id = s.portfolio_id
join instruments i on i.id = s.instrument_id
join source_records r on r.id = s.source_record_id
join source_batches b on b.id = r.source_batch_id
join source_systems y on y.id = b.source_system_id
where y.source_code = '{code}'"""

# Gold holdings: each fund's latest value carried forward to every month end (quarterly funds), status worded the way the product does. A liquid
# book held as positions counts through its position snapshot only when that portfolio has no valuation lines of its own (the 10uc seed values the
# 20 securities one by one, so there the roll-up position is not a second holding).
HOLDINGS_SQL = f"""create or replace table {{name}} as
with months as (
  select distinct last_day(valuation_date) as month_end from valuation_observations
),
live as (
  select
    v.portfolio_id,
    v.instrument_id,
    v.valuation_date,
    v.received_at,
    v.value_amount,
    v.valuation_type,
    v.approval_status,
    v.supersedes_valuation_id
  from valuation_observations v
  where not exists (select 1 from valuation_observations x where x.supersedes_valuation_id = v.id)
    and v.approval_status <> 'rejected' and v.value_amount <> 0
  union all
  select
    s.portfolio_id,
    s.instrument_id,
    s.position_date,
    s.received_at,
    s.source_market_value,
    'administrator',
    'approved',
    null
  from position_snapshots s
  join instruments i on i.id = s.instrument_id
  where i.instrument_type <> 'cash' and s.view_type = 'investment'
    and not exists (select 1 from position_snapshots x where x.supersedes_position_id = s.id)
    and not exists (select 1 from valuation_observations v where v.portfolio_id = s.portfolio_id and v.value_amount <> 0)
),
as_at as (
  select
    m.month_end,
    v.*,
    row_number() over (partition by m.month_end, v.portfolio_id, v.instrument_id order by v.valuation_date desc, v.received_at desc) as rn
  from months m
  join live v on v.valuation_date <= m.month_end
)
select
  date_trunc('month', a.month_end)::date as report_month,
  e.entity_name as entity,
  i.canonical_name as holding,
  a.value_amount as net_worth_usd,
  a.value_amount * (
    select o.value from market_observations o
    where o.series_key = '{FX}' and o.observed_at <= a.month_end + interval 1 day
    order by o.observed_at desc limit 1
  ) as net_worth_sgd,
  case
    when a.valuation_type = 'manager_estimate' then 'estimated'
    when a.approval_status in ('pending', 'proposed') then 'unverified'
    when a.supersedes_valuation_id is not null then 'revised'
    else 'official'
  end as status
from as_at a
join portfolios p on p.id = a.portfolio_id
join legal_entities e on e.id = p.legal_entity_id
join instruments i on i.id = a.instrument_id
where a.rn = 1"""

CASH_SQL = """create or replace table {name} as
select
  s.position_date,
  e.entity_name as entity,
  case s.view_type when 'accounting' then 'administrator' when 'operational' then 'trading export' else s.view_type end as view_type,
  s.source_market_value as cash_usd,
  s.data_status as status
from position_snapshots s
join portfolios p on p.id = s.portfolio_id
join legal_entities e on e.id = p.legal_entity_id
join instruments i on i.id = s.instrument_id
where i.instrument_type = 'cash'
  and not exists (select 1 from position_snapshots x where x.supersedes_position_id = s.id)"""


def _plan(pid: str) -> dict:
    gold_dep = [*SILVER]  # depends_on is what the SQL reads (silver); the bronze links are intake edges in the lineage below
    bronze = [(BRONZE_ADMIN, "administrator", "Positions and cash as the administrator export landed them."),
              (BRONZE_TRADE, "trading_export", "Cash and positions as the trading export landed them.")]
    tables = [{"name": n, "layer": "bronze", "source": code, "layout": "positions", "purpose": purpose, "sql": "", "depends_on": [],
               "columns": _cols("portfolio_code:varchar:portfolio_code,instrument_name:varchar:instrument,position_date:date:position date,"
                                "market_value:decimal:market value,currency:varchar:currency,file_name:varchar:file,loaded_at:timestamp:loaded at")}
              for n, code, purpose in bronze]
    tables += [
        {"name": HOLDINGS, "layer": "gold", "purpose": "Month-end holdings by entity in USD and SGD with the status of each value.",
         "columns": _cols("report_month:date:valuation date,entity:varchar:legal entity,holding:varchar:instrument,net_worth_usd:decimal:value,"
                          "net_worth_sgd:decimal:value times the WMR 4pm fixing,status:varchar:approval status"),
         "sql": HOLDINGS_SQL.format(name=HOLDINGS), "depends_on": gold_dep},
        {"name": CASH, "layer": "gold", "purpose": "Cash per entity per day, administrator view next to the trading view.",
         "columns": _cols("position_date:date:position date,entity:varchar:legal entity,view_type:varchar:view,cash_usd:decimal:cash,status:varchar:data status"),
         "sql": CASH_SQL.format(name=CASH), "depends_on": ["position_snapshots", "portfolios", "legal_entities", "instruments"]},
    ]
    # K04: Span's own benchmark rule (b6_span.benchmark_table) gives the table; built like the others (create or replace)
    for b in b6_span.benchmark_table(SLUG, [{"name": "Portfolio against benchmark"}])[:1]:  # V6B: the returns table; the weights table belongs to a pack-drawn plan
        # month of a reading in UTC: a 30 Sep 16:00 UTC level is 1 Oct in Singapore and would land in October (reported to P8, b6_span)
        sql = b["sql"].replace(f"create table {b['name']} ", f"create or replace table {b['name']} ", 1).replace(
            "date_trunc('month', observed_at)", "date_trunc('month', timezone('UTC', observed_at))")
        tables.append({**b, "sql": sql,
                       "columns": _cols("portfolio_code:varchar:portfolio,benchmark_code:varchar:benchmark code,month:date:month,portfolio_return:decimal:portfolio return,"
                                        "benchmark_return:decimal:benchmark return,difference:decimal:portfolio minus benchmark")})
    # intake edges: the core silver table each bronze feed lands in (b6_plan.validate keeps these and derives the rest from depends_on)
    lineage = [{"from": BRONZE_ADMIN, "to": "position_snapshots"}, {"from": BRONZE_TRADE, "to": "position_snapshots"}]
    lineage += [{"from": s, "to": t["name"]} for t in tables if t["layer"] == "gold" for s in t["depends_on"]]
    return {"project_id": pid, "project_slug": SLUG, "version": 1,
            "sources": [{"code": "administrator", "kind": "structured", "files": ["administrator export"], "owner": OPS},
                        {"code": "trading_export", "kind": "structured", "files": ["trading export"], "owner": OPS},
                        {"code": "manager_email", "kind": "unstructured", "files": ["manager statements"], "owner": OPS}],
            "model_changes": None, "tables": tables, "lineage": lineage, "schedule": {"freq": "daily", "at": "06:00", "day": None},
            "state": "live", "proposed_by": ENGINEER, "approved_by": HEAD, "approved_at": _now(),
            "reason": "Silver is unchanged; three gold tables serve the dashboard tiles and the benchmark comparison."}


def _land_bronze(con: duckdb.DuckDBPyConnection) -> None:
    for name, code in ((BRONZE_ADMIN, "administrator"), (BRONZE_TRADE, "trading_export")):
        con.execute(f"create or replace table {name} as {BRONZE_SQL.format(code=code)}")


def _run(con: duckdb.DuckDBPyConnection, plan: dict) -> list[dict]:
    """Gold tables in dependency order; built as <table>__next and swapped in (card B4's rule: a failure leaves the old table)."""
    steps = []
    for t in plan["tables"]:
        if t["layer"] != "gold":
            continue
        t0 = time.perf_counter()
        con.execute(t["sql"].replace(f"create or replace table {t['name']} ", f"create or replace table {t['name']}__next ", 1))
        con.execute(f"drop table if exists {t['name']}")
        con.execute(f"alter table {t['name']}__next rename to {t['name']}")
        steps.append({"table": t["name"], "rows": con.execute(f"select count(*) from {t['name']}").fetchone()[0],
                      "ms": round((time.perf_counter() - t0) * 1000), "status": "ok", "error": None})
    return steps


def build(plane, pid: str, ids: dict[str, str] | None = None) -> dict:
    """The plan goes through the product's own writers: proposed by the engineer, approved by the head of data, run on a copy, then live."""
    folder = plane.path("build", pid)
    plan_path, runs_path = folder / "plan-v1.json", folder / "runs.jsonl"
    if read_json_strict(plan_path) is not None and runs_path.is_file():
        if not (folder / "log.jsonl").is_file():  # an earlier seed wrote the plan straight to disk: give it the history the pipeline room shows
            n = len(read_json_strict(plan_path)["tables"])
            for who, what, note in ((ENGINEER, "proposed a build plan", f"{n} tables"), (HEAD, "approved the build plan", ""),
                                    (ENGINEER, "plan is now built", ""), (ENGINEER, "plan is now live", "")):
                b6_plan.log(plane, pid, who, what, 1, note)
        return {"build": "kept"}
    ids = ids or EG.accounts(plane.root.parent)[0]
    leo, anita = Viewer(ENGINEER, frozenset({"analyst"}), False, ids[ENGINEER]), Viewer(HEAD, frozenset({"analyst", "head_of_data"}), False, ids[HEAD])
    with wh.connect(plane) as con:
        _land_bronze(con)
    if read_json_strict(plan_path) is None:  # (a rebuilt warehouse keeps its approved plan and only runs it again)
        b6_plan.new_version(plane, pid, _plan(pid), leo)
        b6_plan.approve(plane, anita, pid)
    runs = [b6_run.run(plane, pid, mode, by=ENGINEER) for mode in ("sandbox", "live")]
    bad = [s["error"] for r in runs for s in r["steps"] if s["error"]]
    if bad:
        raise RuntimeError("the demo build failed: " + "; ".join(bad))
    return {"build": "made", "runs": len(runs)}


# ---------- build: the rooms of the intent (Design with Span, Scan, Mapping sheet, Run log, Approval requests) ----------

def _landing(plane) -> None:
    """The three sources as files in landing/<source>/, written from the warehouse's own rows (synthetic). Once."""
    sql = {"administrator": ("administrator_positions.csv", "select portfolio_code, instrument_name, position_date, market_value, currency from " + BRONZE_ADMIN),
           "trading_export": ("trading_export_positions.csv", "select portfolio_code, instrument_name, position_date, market_value, currency from " + BRONZE_TRADE),
           "manager_email": ("manager_values.csv", "select i.manager_name, v.valuation_date, v.value_amount, v.currency from valuation_observations v "
                             "join instruments i on i.id = v.instrument_id where i.manager_name is not null order by 1, 2")}
    with wh.connect(plane) as con:
        for src, (name, q) in sql.items():
            f = plane.path("landing", src, name)
            if f.is_file():
                continue
            cur = con.execute(q)
            f.parent.mkdir(parents=True, exist_ok=True)
            with f.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow([d[0] for d in cur.description])
                w.writerows(cur.fetchall())


def _runs(plane) -> list[dict]:
    from sh_platform.build import runner
    return runner.read_runs(plane)


def rooms(plane, iid: str) -> dict:
    """Fill the old Build rooms of the signed intent through their own writers; each step only when its room is still empty."""
    out = {}
    sow_path = plane.path("intents", iid, "sow.json")
    sow = read_json_strict(sow_path)
    if not sow.get("catalogue"):  # a demo made before the catalogue was written
        write_json_atomic(sow_path, {**sow, "catalogue": CATALOGUE})
    _landing(plane)
    if b1_design.read_design(plane, iid) is None:
        b1_design.design(plane, SimpleNamespace(model=None, company_name=EG.NAME, industry="Family office"), iid, HEAD)
        out["design"] = "made"
    scan = b2_scan.read_scan(plane, iid)
    if scan is None:
        scan = b2_scan.run_scan(plane, iid)
        out["scan"] = "made"
    if not scan.get("agreed"):
        b2_scan.agree(plane, iid, [k["code"] for k in scan["kpis"] if k["status"] != "not"], HEAD)
    if b3_mapping.read(plane, iid) is None:
        b3_mapping.draft(plane, iid)
        out["mapping"] = "made"
    if not any(r.get("source", "").startswith(b4_load.PREFIX) for r in _runs(plane)):
        for c in b4_load.contracts_for(plane, iid)[0]:
            b4_load.load(plane, c)
        out["run_log"] = "made"
    if not g4_deviations.read(plane, iid):
        g4_deviations.propose(
            plane, iid, summary="read each benchmark month in UTC", about="Portfolio against benchmark (K04)",
            before="The month of a benchmark level follows Singapore time, so the 30 Sep 16:00 UTC level counts in October.",
            after="The month follows UTC, so the 30 Sep 16:00 UTC level stays in September.",
            why="The month-end level belongs to the month it closes; the report should agree with the administrator.", effect=[], by=ENGINEER)
        out["approval_request"] = "made"
    return out


# ---------- consume: the dashboard ----------

def _bar(x: str, y: str, color: str | None = None) -> dict:
    enc = {"x": {"field": x, "type": "nominal"}, "y": {"field": y, "type": "quantitative"}}
    if color:
        enc["color"] = {"field": color, "type": "nominal"}
        enc["xOffset"] = {"field": color}
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "mark": "bar", "encoding": enc}


def dashboard(plane, pid: str, ids: dict[str, str]) -> dict:
    """The maker is the engineer's account id and the audience are warehouse users.id, as C1 and C3 compare them."""
    with wh.connect(plane) as con:
        users = {n: str(i) for n, i in con.execute("select display_name, id from users").fetchall()}
    folder = plane.path("consume", pid, "dashboards")
    if (folder / f"{DASH_ID}.json").exists():  # only the seeded one: going live also drafts Lumen's starter (H10) in this folder
        return {"dashboard": "kept"}
    now = _now()
    tiles = [
        ("t-000001", "Net worth by entity", "K01", f"select entity, sum(net_worth_usd) as net_worth_usd from {HOLDINGS} where report_month = (select max(report_month) from {HOLDINGS}) group by entity order by entity",
         _bar("entity", "net_worth_usd"), f"From {HOLDINGS}."),
        ("t-000002", "Cash by entity", "K02", f"select entity, view_type, cash_usd from {CASH} where position_date = (select max(position_date) from {CASH}) order by entity, view_type",
         _bar("entity", "cash_usd", "view_type"), "Administrator view next to the trading view."),
        ("t-000003", "Holdings by status", "K03", f"select status, sum(net_worth_usd) as net_worth_usd from {HOLDINGS} where report_month = (select max(report_month) from {HOLDINGS}) group by status order by status",
         _bar("status", "net_worth_usd"), "Official, revised, estimated or unverified."),
    ]
    rec = {"id": DASH_ID, "title": TITLE, "project_id": pid,
           "tiles": [{"id": i, "title": t, "kpi": k, "sql": sql, "spec": spec, "note": note, "state": "accepted"} for i, t, k, sql, spec, note in tiles],
           "audience": [users[CIO], users[FINANCE]], "refresh": "same", "created_by": ids[ENGINEER], "updated_at": now}
    write_json_atomic(folder / f"{rec['id']}.json", rec)
    return {"dashboard": "made", "tiles": len(tiles)}


def second_month(plane) -> None:
    """A 31 Aug set of manager valuations and liquid-book positions (a little lower than 30 Sep, all official), so "why did this move" has two periods. Once."""
    with wh.connect(plane) as con:
        if con.execute("select 1 from valuation_observations where valuation_date = ?", [date(2026, 8, 31)]).fetchone():
            return
        sysid = con.execute("select id from source_systems where source_code = 'manager_email'").fetchone()[0]
        org = con.execute("select organization_id from source_systems where source_code = 'manager_email'").fetchone()[0]
        sep = con.execute("select instrument_id, portfolio_id, value_amount from valuation_observations where valuation_date = ? and not exists "
                          "(select 1 from valuation_observations x where x.supersedes_valuation_id = valuation_observations.id)", [date(2026, 9, 30)]).fetchall()
        recs = EG._batch(con, org, sysid, "manager statements 2026-08-31", EG.utc(2026, 9, 2, 5), date(2026, 8, 31),
                         [{"type": "statement", "amount": str(v * Decimal("0.94"))} for _, _, v in sep], "total value")
        liq = con.execute("select portfolio_id, instrument_id, source_market_value from position_snapshots where position_date = ? and view_type = 'investment' "
                          "and not exists (select 1 from position_snapshots x where x.supersedes_position_id = position_snapshots.id) "
                          "and instrument_id in (select id from instruments where instrument_type <> 'cash')", [date(2026, 9, 30)]).fetchall()
        asys = con.execute("select id from source_systems where source_code = 'administrator'").fetchone()[0]
        lrecs = EG._batch(con, org, asys, "liquid book 2026-08-31", EG.utc(2026, 9, 1, 6), date(2026, 8, 31),
                          [{"type": "position", "amount": str(v * Decimal("0.96"))} for _, _, v in liq], "total market value")
        for (pf, ins, v), rec in zip(liq, lrecs):
            EG.put(con, "position_snapshots", dict(
                organization_id=org, source_record_id=rec, portfolio_id=pf, instrument_id=ins, position_date=date(2026, 8, 31),
                as_of_at=EG.utc(2026, 8, 31, 16), received_at=EG.utc(2026, 9, 1, 6), recorded_at=EG.utc(2026, 9, 1, 6, 5), quantity=Decimal(1),
                source_market_value=(v * Decimal("0.96")).quantize(Decimal("1")), currency="USD", view_type="investment", data_status="official"))
        for (ins, pf, v), rec in zip(sep, recs):
            EG.put(con, "valuation_observations", dict(
                organization_id=org, instrument_id=ins, portfolio_id=pf, source_record_id=rec, valuation_date=date(2026, 8, 31),
                received_at=EG.utc(2026, 9, 2, 5), recorded_at=EG.utc(2026, 9, 2, 5, 10), value_amount=(v * Decimal("0.94")).quantize(Decimal("1")),
                currency="USD", valuation_type="manager_final", approval_status="official"))


def register(plane, pid: str) -> None:
    """Record the plan's bronze and gold tables in the catalogue (D1) through B2's own call, as approval does."""
    b6_plan._register(plane, read_json_strict(plane.path("build", pid, "plan-v1.json")))


# ---------- main ----------

def seed(data_root: Path) -> dict:
    data_root = Path(data_root)
    base = EG.seed(data_root)
    plane = PlaneStore(data_root).plane_for(EG.COMPANY).ensure()
    ids, _ = EG.accounts(data_root)
    wh.set_demo_today(plane, DEMO_TODAY)
    project = intent(plane, ids)
    second_month(plane)
    out = {**base, "project_id": project["id"], "intent_id": project["intent_id"], **build(plane, project["id"], ids)}
    register(plane, project["id"])
    out.update(rooms(plane, project["intent_id"]))
    out.update(dashboard(plane, project["id"], ids))
    p1_project.set_stage(plane, project["id"], "live")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    a = ap.parse_args(argv)
    raw = a.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed(root)
    print(f"Project {r['project_id']} ({TITLE}): build {r['build']}, dashboard {r['dashboard']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
