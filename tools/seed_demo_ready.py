"""Make the seeded Evergreen Office demo-ready: every screen has something to show (card DEMO1). Synthetic data only; no model call is made.

Usage: python tools/seed_demo_ready.py [--data-root PATH]      (called at the end of tools/seed_demo_boot.py; safe to run on any seeded root)
Runs after tools/seed_10uc.py (which holds the history, the cases, the cash break and the v3 project). Each step goes through the product's own
functions as the person the product requires (Leo Park builds and runs, Anita Rao approves plans, proposals and dashboards, Daniel Foo signs and
approves), and each step is skipped when its result is already there, so a second run changes nothing. A step that fails is reported and the others
still run (`strict=True`, used by the tests, raises instead).

  silver    a model change adds the silver table entity_cash_daily; plan v2 of the monthly investment report fills it from the two bronze exports and a
            gold table (cash gap) reads it, approved, run on a copy (test run) and live (production run): Map shows bronze -> silver -> gold
  extension a second model change (manager_fee_schedule) waits for the head of data, linked to a proposed plan v3 (Action: waiting for my approval)
  figures   a manager statement figure waiting to be confirmed (Action: Figures to confirm), read by the product's own reader
  uc4       the benchmark project (monthly performance against the office blend): intent signed, pack approved, pipeline live, starter dashboard approved
  dashboards the v3 project's starter dashboard sent for approval; the seeded dashboard stays published (Consume > Reports)
  delivery  the published dashboard goes to Consume and the Morning Note (Operations > Deliveries shows the sent records)
  markets   live API pulls (Frankfurter; FRED and Finnhub when FRED_API_KEY / FINNHUB_API_KEY are set; MAS) so Consume > Markets reads "LIVE API ..."
            The company's Internet and Connectors switches are turned on for this demo company only, and only when a provider is reachable.
            Offline: skipped, nothing is written and no "live" row is faked.
"""
from __future__ import annotations

import argparse
import contextlib
import logging
import os
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.jsonfile import read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import b6_plan as B  # noqa: E402
from sh_platform.v1 import b6_run, b7_studio, b11_builder as BU, cx_dash, d1_delivery as D1, e0a_catalogue as E, i1_company, i2_north, p1_project as P1  # noqa: E402
from sh_platform.v1 import x5_extract as X5  # noqa: E402
from tools import seed_10uc as S  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402
from tools import seed_v3_demo as V3  # noqa: E402
from tools import seed_walk_benchmark as WB  # noqa: E402

log = logging.getLogger(__name__)
CIO, HEAD, ENG, OPS = "Daniel Foo", "Anita Rao", "Leo Park", "Mei Chen"
UC4_TITLE = "Monthly performance against the office blend"
SILVER, GAP, FEES = "entity_cash_daily", f"gold_{V3.SLUG}_cash_gap", "manager_fee_schedule"
STATEMENT = "cedarpoint-ventures-iii-statement-2026-09-30-draft.md"
PROVIDERS = {  # spec id -> (provider, series, key variable); a keyed provider is used only when its key is set on the server
    "demo_frankfurter": ("frankfurter", ["USD/SGD", "EUR/USD", "EUR/SGD", "GBP/USD"], None),
    "demo_fred": ("fred", ["DGS10", "DEXSIUS"], "FRED_API_KEY"),
    "demo_finnhub": ("finnhub", ["EWS", "ACWI", "AGG"], "FINNHUB_API_KEY"),
    "demo_mas": ("mas", ["SGS2Y", "SGS5Y", "SGS10Y"], None),
}

SILVER_SQL = """insert into entity_cash_daily (portfolio_code, position_date, entity, view_type, cash_usd)
select b.portfolio_code, b.position_date, e.entity_name, 'administrator', b.market_value
from bronze_administrator_positions b
join portfolios p on p.portfolio_code = b.portfolio_code
join legal_entities e on e.id = p.legal_entity_id
join instruments i on i.canonical_name = b.instrument_name
where i.instrument_type = 'cash'
union all
select b.portfolio_code, b.position_date, e.entity_name, 'trading export', b.market_value
from bronze_trading_export_positions b
join portfolios p on p.portfolio_code = b.portfolio_code
join legal_entities e on e.id = p.legal_entity_id
join instruments i on i.canonical_name = b.instrument_name
where i.instrument_type = 'cash'"""
# One row per entity and day, the two views side by side. A repeated run adds the same lines again, so the gold table counts each distinct line once.
GAP_SQL = f"""create or replace table {GAP} as
select
  position_date,
  entity,
  sum(case when view_type = 'administrator' then cash_usd else 0 end) as administrator_usd,
  sum(case when view_type = 'trading export' then cash_usd else 0 end) as trading_usd,
  sum(case when view_type = 'administrator' then cash_usd else 0 end) - sum(case when view_type = 'trading export' then cash_usd else 0 end) as gap_usd
from (select distinct portfolio_code, position_date, entity, view_type, cash_usd from entity_cash_daily) c
group by position_date, entity"""
FEES_SQL = f"""insert into {FEES} (manager_name, fund_name, fee_basis, fee_rate)
select distinct i.manager_name, i.canonical_name, cast(null as varchar), cast(null as decimal(9,6))
from instruments i
where i.manager_name is not null"""  # no fee is made up: the rate and its basis come from each fee letter when the head of data lets the table in


def _cols(spec: str) -> list[dict]:
    return [{"name": n, "type": t, "null": True, "note": note} for n, t, note in (x.split(":") for x in re.split(r",(?![^()]*\))", spec))]


def _project(plane, title: str) -> dict | None:
    return next((p for p in P1.all_projects(plane) if p.get("title") == title), None)


def _plan_has(plane, pid: str, name: str) -> bool:
    return any(t["name"] == name for v in B.versions(plane, pid) for t in (B.get(plane, pid, v) or {}).get("tables", []))


@contextlib.contextmanager
def inline_jobs():
    """Run pipelines in this process whatever the mode: in production mode b6 runs go to the Redis queue and no worker runs during the seed. The queue
    the product uses is untouched afterwards."""
    from sh_platform import jobs
    old = jobs._Q
    jobs._Q = jobs.LocalQueue()
    try:
        yield
    finally:
        jobs._Q = old


# ---------- silver, test run and production run (items 1, 2) ----------

def silver(plane, V) -> str:
    pid = (_project(plane, V3.TITLE) or {}).get("id")
    if not pid:
        return "skipped: the monthly investment report project is not there"
    if _plan_has(plane, pid, SILVER):
        return "kept"
    leo, anita = V[ENG], V[HEAD]
    n = E.propose(plane, leo, add_table={
        "name": SILVER, "group": "Cash", "note": "Cash lines of each entity and day as the administrator and the trading export report them, cleaned and matched to the entity.",
        "columns": _cols("portfolio_code:varchar(50):portfolio,position_date:date:day,entity:varchar(200):legal entity,"
                         "view_type:varchar(40):administrator or trading export,cash_usd:decimal(18,2):cash in USD")},
        note="The monthly report needs the two cash views side by side in the company model.")["version"]
    base = B.get(plane, pid)
    tables = list(base["tables"]) + [
        {"name": SILVER, "layer": "silver", "purpose": "Cash lines per entity and day, both views, cleaned.", "columns": [], "sql": SILVER_SQL,
         "depends_on": ["bronze_administrator_positions", "bronze_trading_export_positions", "portfolios", "legal_entities", "instruments"]},
        {"name": GAP, "layer": "gold", "purpose": "Cash gap per entity and day: administrator against trading export.", "columns": [], "sql": GAP_SQL, "depends_on": [SILVER]}]
    plan = B.new_version(plane, pid, {**base, "tables": tables, "reason": "Adds the cash silver table and the cash gap."}, leo, model_changes=n)
    B.approve(plane, anita, pid, plan["version"], "Plan with the cash silver table")
    for mode in ("sandbox", "live"):  # the test run on a copy, then the production run
        rec = b6_run.run(plane, pid, mode, by=leo.name)
        if rec["status"] != "ok":
            raise RuntimeError("the pipeline run failed: " + "; ".join(s["error"] for s in rec["steps"] if s["error"]))
    return "made"


# ---------- a pending model extension linked to a plan (item 5) ----------

def extension(plane, V) -> str:
    pid = (_project(plane, V3.TITLE) or {}).get("id")
    if not pid or not _plan_has(plane, pid, SILVER):
        return "skipped: the silver step comes first"
    if _plan_has(plane, pid, FEES):
        return "kept"
    leo = V[ENG]
    n = E.propose(plane, leo, add_table={
        "name": FEES, "group": "Managers", "note": "The fee terms of each manager's funds, one row per fund, taken from the fee letters.",
        "columns": _cols("manager_name:varchar(200):manager,fund_name:varchar(200):fund,fee_basis:varchar(80):what the fee is charged on,"
                         "fee_rate:decimal(9,6):annual rate")},
        note="Net-of-fee returns against the benchmark need each manager's fee terms; none are held yet.")["version"]
    base = B.get(plane, pid)
    tables = list(base["tables"]) + [{"name": FEES, "layer": "silver", "purpose": "One row per fund, filled from the fee letters.", "columns": [],
                                      "sql": FEES_SQL, "depends_on": ["instruments"]}]
    B.new_version(plane, pid, {**base, "tables": tables, "reason": "Adds the manager fee schedule to the company model."}, leo, model_changes=n)
    return "made"


# ---------- a figure to confirm (item 4) ----------

STATEMENT_TEXT = """Cedarpoint Ventures III, L.P. (synthetic)
Quarterly statement, quarter ended 30 September 2026 (draft, not yet signed by the manager)
Net asset value of the Evergreen Office interest: USD 8,310,000
Capital called to date: USD 3,900,000
Distributions to date: USD 0
Unfunded commitment: USD 2,100,000
"""


def figures(plane, V) -> str:
    """A manager statement read on this machine whose figures need a person: the draft states no statement date, so the reader's check
    fails and the document waits in the review queue (Action: Figures to confirm). Nothing is used until it is confirmed."""
    p = _project(plane, V3.TITLE)
    if not p:
        return "skipped: the monthly investment report project is not there"
    iid = p["intent_id"]
    if any(r.get("file") == f"documents/{STATEMENT}" for r in X5._records(plane)):
        return "kept"
    if not plane.path("documents", STATEMENT).is_file():
        i1_company.upload(plane, STATEMENT, STATEMENT_TEXT.encode("utf-8"))
    t = X5.upsert(plane, iid, {
        "name": "Manager statement",
        "fields": [{"name": "statement date", "format": "date", "where_usually": "Statement date", "required": True},
                   {"name": "net asset value", "format": "number", "where_usually": "Net asset value of the Evergreen Office interest", "required": True},
                   {"name": "capital called", "format": "number", "where_usually": "Capital called to date"}],
        "checks": [{"kind": "present", "field": "statement date", "detail": "the date the manager's statement is struck at"},
                   {"kind": "present", "field": "net asset value", "detail": ""}],
        "files": [STATEMENT]}, state="confirmed")
    X5.run(plane, iid, STATEMENT, t["id"])
    return "made"


# ---------- the benchmark project, end to end (item 7) ----------

def _sow_uc4(iid: str) -> dict:
    v3 = V3._sow(iid)
    return {**WB.SOW, "id": f"sow-{iid}", "intent_id": iid, "title": UC4_TITLE, "version": 1, "state": "signed",
            "goal": {**WB.SOW["goal"], "why": "The family council reads one page a month on how the liquid portfolio did against the office blend.",
                     "decisions": ["Whether the liquid portfolio is keeping up with the office blend"]},
            "process": v3["process"], "sources": [], "catalogue": v3["catalogue"], "governance": v3["governance"], "unclear": [],
            "template_fields": v3["template_fields"],
            "signature": {"name": CIO, "role": "sponsor", "at": "2026-10-05T02:00:00+00:00"}, "signatures": [{"name": CIO, "role": "sponsor", "at": "2026-10-05T02:00:00+00:00", "version": 1}]}


def uc4(plane, V, ids) -> str:
    p = _project(plane, UC4_TITLE)
    if p and p.get("stage") == "live" and (d := b7_studio._starter_of(plane, p["id"])) and cx_dash.status_of(d) == "published":
        return "kept"
    leo, anita, daniel = V[ENG], V[HEAD], V[CIO]
    if p is None:
        made = i2_north.create(plane, daniel, UC4_TITLE)
        iid, sow = made["id"], _sow_uc4(made["id"])
        write_json_atomic(plane.path("intents", iid, "thread.json"), V3._thread(iid, sow["signature"]["at"]))
        pid = P1.project_of(plane, iid)["id"]
        for key, name in (("sponsor", CIO), ("builder", ENG), ("head_of_data", HEAD), ("ops", OPS)):  # the people first: the data team may open the project
            P1.set_person(plane, pid, key, name)
        write_json_atomic(plane.path("intents", iid, "send_to_build.json"), {"by": CIO, "at": sow["signature"]["at"], "project_id": pid})
        WB.play(plane, leo, anita, iid, sow)
    else:
        pid = p["id"]
    if (P1.read(plane, pid) or {}).get("stage") != "live":
        rounds = BU.load(plane, pid)["rounds"]  # resume an earlier boot that stopped part-way: run the approved pack on a copy again if no clean round is there
        if not rounds or rounds[-1]["state"] not in ("checked", "ran", "live"):
            BU.start(plane, leo, pid, force=True)
        try:
            BU.go_live(plane, leo, pid)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"the benchmark project stopped part-way and cannot be finished by the seed ({e}); reset the demo with seed_demo_boot.py --reset") from e  # the pipeline goes live on the pack's schedule; Lumen's starter dashboard follows
    d = b7_studio._starter_of(plane, pid) or b7_studio.start_starter(plane, pid)
    if d and cx_dash.status_of(d) != "published":
        if d["starter"]["status"] == "proposed":
            b7_studio.accept_starter(plane, leo, pid, d["id"])
        if cx_dash.status_of(cx_dash._load(plane, pid, d["id"])) == "draft":
            cx_dash.submit(plane, leo, pid, d["id"])
        cx_dash.decide_version(plane, daniel, pid, d["id"], True)
    return "made"


# ---------- dashboards waiting, published and delivered (items 4, 6) ----------

def dashboards(plane, V) -> str:
    """The v3 project's starter (made by Lumen when the pipeline went live) is accepted and sent for approval: Action, waiting for approval."""
    pid = (_project(plane, V3.TITLE) or {}).get("id")
    d = pid and b7_studio._starter_of(plane, pid)
    if not d:
        return "skipped: no starter dashboard"
    if cx_dash.status_of(d) != "draft" or (d.get("lifecycle") or {}).get("submitted_at"):
        return "kept"
    leo = V[ENG]
    if d["starter"]["status"] == "proposed":
        b7_studio.accept_starter(plane, leo, pid, d["id"])
    cx_dash.submit(plane, leo, pid, d["id"])
    return "made"


def delivery(plane, V) -> str:
    """The seeded dashboard (published, in Consume > Reports) goes to Consume and into the Morning Note: made by Leo, approved by Daniel, live."""
    pid = (_project(plane, V3.TITLE) or {}).get("id")
    if not pid:
        return "skipped: the monthly investment report project is not there"
    if D1.outbox(plane, pid):
        return "kept"
    leo, daniel = V[ENG], V[CIO]
    for kind, title in (("consume", "Monthly report in Consume"), ("morning_note", "Monthly report in the Morning Note")):
        ch = D1.create_channel(plane, leo, pid, {"kind": kind, "title": title, "dashboard_id": V3.DASH_ID, "when": "daily", "at": "07:00"})
        D1.submit_channel(plane, leo, pid, ch["id"])
        D1.decide_channel(plane, daniel, pid, ch["id"], True)
    D1.go_live(plane, leo, pid)
    for ch in D1._load(plane, pid)["channels"]:
        D1.deliver(plane, pid, ch, "go-live")
    return "made"


# ---------- live market data (item 3) ----------

def _reachable(host: str) -> bool:
    try:
        socket.create_connection((host, 443), timeout=4).close()
        return True
    except OSError:
        return False


def markets(plane, data_root: Path, F: dict | None = None) -> str:
    from sh_platform.egress.policy import EgressPolicy
    from sh_platform.entitlements import EntitlementStore
    from sh_platform.v1.c5_connect import api, spec
    use = {cid: (prov, ser) for cid, (prov, ser, key) in PROVIDERS.items() if not key or os.environ.get(key)}
    if not (F or {}).get("api_http"):  # a stub (tests) needs no network; otherwise only providers that answer a connection
        use = {cid: v for cid, v in use.items() if _reachable(api.PROVIDERS[v[0]]["host"])}
    if not use:
        return "skipped: no market data provider is reachable (offline); nothing written"
    pol = EgressPolicy(plane)
    for m in EntitlementStore(data_root).enabled_modules(EG.COMPANY):  # the Settings > Egress switches, as an administrator would set them
        pol.set_internet(m, True)
    pol.set_flag("connectors", True)
    done = []
    for cid, (prov, series) in use.items():
        sp = spec.save(plane, cid, {"kind": "api", "provider": prov, "series": series, "schedule": "daily"})
        r = api.pull(plane, sp, F)
        why = r.get("error") or {}  # the reason in words (code and message never carry a key)
        done.append(f"{prov} {r['status']} ({r['landed']} new)" + (f": {why.get('code')}: {why.get('message')}" if r["status"] != "ok" else ""))
    return "; ".join(done)


# ---------- main ----------

def _inline(f):
    with inline_jobs():
        return f()


def seed(data_root: Path, strict: bool = False, F: dict | None = None) -> dict:
    """Run every step; returns {step: what happened}. `F` = {"api_http": fn} replaces the HTTP call of the market pulls (tests)."""
    data_root = Path(data_root)
    plane = PlaneStore(data_root).plane_for(EG.COMPANY).ensure()
    ids, _ = EG.accounts(data_root)
    V = S.viewers(ids)
    out: dict[str, str] = {}
    run_inline = lambda f: (lambda: _inline(f))  # noqa: E731
    for name, fn in (("silver", run_inline(lambda: silver(plane, V))), ("extension", lambda: extension(plane, V)), ("figures", lambda: figures(plane, V)),
                     ("uc4", run_inline(lambda: uc4(plane, V, ids))), ("dashboards", lambda: dashboards(plane, V)), ("delivery", lambda: delivery(plane, V)),
                     ("markets", lambda: markets(plane, data_root, F))):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001 - one step failing must not stop the demo from booting
            if strict:
                raise
            log.exception("demo-ready step %s failed", name)
            out[name] = f"failed: {type(e).__name__}: {str(e)[:200]}"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT")
    ap.add_argument("--strict", action="store_true", help="stop at the first step that fails")
    a = ap.parse_args(argv)
    root = Path(a.data_root or os.environ.get("SH_DATA_ROOT") or "./data")
    for step, what in seed(root, a.strict).items():
        print(f"{step}: {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
