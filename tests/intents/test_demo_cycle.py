"""The demo cycle pack (packs/family_office/1/demo_cycle, synthetic) holds together: schema, windows, no future dates,
daily rows that add up to the monthly rows July to September 2026, gold equal to the source tables it reads, and every
evidence id in the answer key present in the pack. Folders that have not landed yet are skipped, never failed."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DC = ROOT / "packs" / "family_office" / "1" / "demo_cycle"
KEY = ROOT / ".sh-tmp" / "ic" / "data" / "answer_key.yaml"

PERIODS = [f"2025-{m:02d}" for m in (9, 10, 11, 12)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAY0, DAY1 = "2026-07-01", "2026-10-06"
HOLIDAYS = {"2026-08-10"}
DAILY_MONTHS = ("2026-07", "2026-08", "2026-09")
ISO = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
pytestmark = pytest.mark.skipif(not DC.is_dir(), reason="demo_cycle not there yet")


def rows(rel: str) -> list[dict]:
    f = DC / rel
    if not f.is_file():
        pytest.skip(f"{rel} not there yet")
    with f.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def all_csvs() -> list[Path]:
    return sorted(DC.rglob("*.csv"))


def close(a, b, tol=0.011) -> bool:
    return abs(float(a) - float(b)) <= tol


# ---- schema ------------------------------------------------------------------------------------------------------------------

MASTER = {  # column name -> (master file, id column)
    "account_id": ("master/accounts.csv", "account_id"), "entity_id": ("master/entities.csv", "entity_id"),
    "holding_id": ("master/holdings.csv", "holding_id"), "fund_id": ("master/holdings.csv", "holding_id"),
    "custodian_id": ("master/custodians.csv", "custodian_id"), "admin_id": ("master/administrators.csv", "admin_id"),
    "administrator_id": ("master/administrators.csv", "admin_id"), "issuer_group_id": ("master/issuer_groups.csv", "issuer_group_id"),
}


def test_every_csv_has_a_header_rows_and_square_shape():
    bad = []
    for f in all_csvs():
        with f.open(newline="", encoding="utf-8") as fh:
            data = list(csv.reader(fh))
        if not data or not all(h.strip() for h in data[0]) or len(data) < 2:
            bad.append(f"{f.relative_to(DC)}: no header or no rows")
        elif any(len(r) != len(data[0]) for r in data[1:] if r):
            bad.append(f"{f.relative_to(DC)}: ragged rows")
    assert not bad, bad


def test_ids_resolve_to_master():
    known = {col: {r[idc] for r in rows(mf)} for col, (mf, idc) in MASTER.items()}
    bad = []
    for f in all_csvs():
        rel = f.relative_to(DC).as_posix()
        if rel.startswith("master/"):
            continue
        for r in rows(rel):
            for col, ids in known.items():
                v = (r.get(col) or "").strip()
                if v and v not in ids:
                    bad.append(f"{rel}: {col}={v}")
    assert not bad, sorted(set(bad))[:20]


def test_master_counts():
    assert len(rows("master/holdings.csv")) == 40
    assert [r["account_id"] for r in rows("master/accounts.csv")] == [f"B0{i}" for i in range(1, 9)]
    assert {r["entity_id"] for r in rows("master/entities.csv")} == {f"E0{i}" for i in range(1, 6)}


# ---- windows and dates -------------------------------------------------------------------------------------------------------

def test_monthly_periods_inside_the_window():
    bad = []
    for f in all_csvs():
        rel = f.relative_to(DC).as_posix()
        for r in rows(rel):
            for col in ("period", "delivery_month"):
                if r.get(col) and r[col] not in PERIODS:
                    bad.append(f"{rel}: {col}={r[col]}")
    assert not bad, sorted(set(bad))[:20]


DAILY = {  # file -> (date column, business days only)
    "treasury/daily_cash_balances.csv": ("balance_date", False), "treasury/daily_mmf_balances.csv": ("balance_date", False),
    "custody/daily_fee_accruals.csv": ("date", False), "engagement/portal_events_daily.csv": ("timestamp", False),
    "fx/daily_rates.csv": ("date", True), "valuations/daily_prices.csv": ("date", True), "valuations/volatility_daily.csv": ("date", True),
    "landing/file_arrival_log.csv": ("arrival_date", True), "reporting/effort_log_daily.csv": ("date", True),
}


@pytest.mark.parametrize("rel", sorted(DAILY))
def test_daily_files_inside_the_window(rel):
    col, business = DAILY[rel]
    days = {r[col][:10] for r in rows(rel)}
    assert min(days) >= DAY0 and max(days) <= DAY1, (min(days), max(days))
    if business:
        off = sorted(d for d in days if date.fromisoformat(d).weekday() >= 5 or d in HOLIDAYS)
        assert not off, off


def test_cash_every_calendar_day_every_account():
    seen = defaultdict(set)
    for r in rows("treasury/daily_cash_balances.csv"):
        seen[r["account_id"]].add(r["balance_date"])
    assert sorted(seen) == [f"B0{i}" for i in range(1, 9)]
    assert all(len(v) == 98 for v in seen.values()), {k: len(v) for k, v in seen.items()}


PLANNED = {"review_date", "target_date", "due", "due_date", "due_at", "ends"}  # ruling: plan dates may be later, observed data may not


def _observed(node, parent: str = "") -> list[str]:
    """Strings in a JSON tree, minus planned fields (review_date, target_date, due dates, time_box.ends, target.by)."""
    if isinstance(node, dict):
        return [s for k, v in node.items() if k not in PLANNED and not (parent == "target" and k == "by") for s in _observed(v, k)]
    if isinstance(node, list):
        return [s for v in node for s in _observed(v, parent)]
    return [node] if isinstance(node, str) else []


def test_no_date_after_today_anywhere():
    bad = []
    for f in sorted(DC.rglob("*")):
        if f.is_file() and f.name != "README.md" and f.suffix in (".csv", ".json", ".md", ".txt", ".eml", ".yaml"):
            body = f.read_text(encoding="utf-8", errors="replace")
            texts = _observed(json.loads(body)) if f.suffix == ".json" else [body]
            late = {d for t in texts for d in ISO.findall(t) if d > DAY1}
            if late:
                bad.append(f"{f.relative_to(DC)}: {sorted(late)[:3]}")
    assert not bad, bad


# ---- daily rows add up to the monthly rows, July to September 2026 ------------------------------------------------------------

def last_by(rs, key, day, val):
    out = {}
    for r in sorted(rs, key=lambda r: r[day]):
        out[(r[day][:7],) + tuple(r[k] for k in key)] = r[val]
    return out


def test_cash_month_end_equals_last_daily_balance():
    last = last_by(rows("treasury/daily_cash_balances.csv"), ("account_id",), "balance_date", "closing_balance")
    bad = [(r["period"], r["account_id"]) for r in rows("treasury/monthly_cash_balances.csv")
           if r["period"] in DAILY_MONTHS and not close(r["month_end_balance"], last[(r["period"], r["account_id"])])]
    assert not bad, bad


def test_custody_month_end_and_fees_equal_daily():
    daily = rows("custody/daily_fee_accruals.csv")
    last = last_by(daily, ("custodian_id",), "date", "assets_under_custody_sgd")
    fees = defaultdict(float)
    for r in daily:
        fees[(r["date"][:7], r["custodian_id"])] += float(r["accrual_sgd"])
    bad = [(r["period"], r["custodian_id"], "assets") for r in rows("custody/assets_under_custody_monthly.csv")
           if r["period"] in DAILY_MONTHS and not close(r["assets_month_end_sgd"], last[(r["period"], r["custodian_id"])])]
    bad += [(r["period"], r["custodian_id"], "fee") for r in rows("custody/monthly_invoices.csv")
            if r["period"] in DAILY_MONTHS and not close(r["fee_sgd"], fees[(r["period"], r["custodian_id"])], 0.5)]
    assert not bad, bad


def test_report_opens_equal_page_one_views():
    n = defaultdict(int)
    for r in rows("engagement/portal_events_daily.csv"):
        if r["page"] == "1":
            n[(r["timestamp"][:7], r["reader"])] += 1
    bad = [(r["period"], r["reader"]) for r in rows("engagement/report_opens_monthly.csv")
           if r["period"] in DAILY_MONTHS and int(r["report_opens"]) != n[(r["period"], r["reader"])]]
    assert not bad, bad


def test_effort_minutes_equal_daily_sum():
    n = defaultdict(int)
    for r in rows("reporting/effort_log_daily.csv"):
        n[(r["date"][:7], r["cause"])] += int(r["minutes"])
    bad = [(r["period"], r["cause"]) for r in rows("reporting/effort_log_monthly.csv")
           if r["period"] in DAILY_MONTHS and int(r["minutes"]) != n[(r["period"], r["cause"])]]
    assert not bad, bad


def test_month_end_rates_equal_last_daily_rate():
    daily = rows("fx/daily_rates.csv")
    bad = []
    for r in rows("fx/month_end_rates.csv"):
        if r["period"] in DAILY_MONTHS:
            last = max((d for d in daily if d["date"].startswith(r["period"])), key=lambda d: d["date"])
            bad += [(r["period"], c) for c in ("usd_sgd", "eur_sgd", "hkd_sgd") if not close(r[c], last[c], 1e-4)]
    assert not bad, bad


def test_month_end_prices_and_volatility_equal_daily():
    last = last_by(rows("valuations/daily_prices.csv"), ("holding_id",), "date", "close_price_local")
    bad = [(r["period"], r["holding_id"]) for r in rows("valuations/month_end_prices.csv")
           if r["period"] in DAILY_MONTHS and not close(r["close_price_local"], last[(r["period"], r["holding_id"])], 1e-4)]
    vol = defaultdict(list)
    for r in rows("valuations/volatility_daily.csv"):
        vol[r["date"][:7]].append(float(r["market_volatility_index"]))
    bad += [(r["period"], "volatility") for r in rows("valuations/volatility_monthly.csv")
            if r["period"] in DAILY_MONTHS and not close(r["market_volatility_index"], sum(vol[r["period"]]) / len(vol[r["period"]]), 0.01)]
    assert not bad, bad


# ---- gold equals the source table it reads ----------------------------------------------------------------------------------

def gold(code: str) -> dict:
    """period -> value, summed over the breakdown column (entity, vehicle) where the file has one."""
    out = defaultdict(float)
    for r in rows(f"gold/{code}.csv"):
        out[r["period"]] += float(r["value"])
    return out


def summed(rel: str, col: str, count: bool = False, by: str = "period") -> dict:
    out = defaultdict(float)
    for r in rows(rel):
        out[r[by][:7]] += 1 if count else float(r[col])
    return out


SOURCES = {
    "k03": lambda: summed("reporting/effort_log_monthly.csv", "hours"),
    "k11": lambda: {r["period"]: float(r["k11_unhedged_fx_exposure_sgd"]) for r in rows("fx/monthly_fx_measures.csv")},
    "k12": lambda: {r["period"]: float(r["stale_valuation_share"]) for r in rows("valuations/stale_valuation_monthly.csv")},
    "k20": lambda: summed("treasury/monthly_idle_cash.csv", "cash_above_floor"),
    "k21": lambda: summed("treasury/monthly_interest.csv", "total_interest_sgd"),
    "k23": lambda: summed("engagement/report_opens_monthly.csv", "report_opens"),
    "k24": lambda: summed("engagement/questions_log.csv", "", count=True, by="date"),
    "k25": lambda: {p: float(sum(1 for r in rows("administrators/statements.csv") if r["delivery_month"] == p and r["late_flag"] == "Y"))
                    for p in PERIODS},
    "k26": lambda: {r["period"]: float(r["k26_hedging_cost_sgd"]) for r in rows("fx/monthly_fx_measures.csv")},
    "k27": lambda: {r["period"]: float(r["k27_unhedged_fx_loss_sgd"]) for r in rows("fx/monthly_fx_measures.csv")},
}


@pytest.mark.parametrize("code", [f"k{i:02d}" for i in range(1, 28)])
def test_gold_has_thirteen_periods(code):
    periods = {r["period"] for r in rows(f"gold/{code}.csv")}
    assert periods == set(PERIODS) - ({"2025-09"} if code in ("k15", "k16") else set()), sorted(periods)


@pytest.mark.parametrize("code", sorted(SOURCES))
def test_gold_equals_its_source(code):
    g, s = gold(code), SOURCES[code]()
    bad = {p: (g.get(p), round(s.get(p, 0), 4)) for p in PERIODS if not close(g.get(p, float("nan")), s.get(p, 0), max(0.011, abs(s.get(p, 0)) * 1e-4))}
    assert not bad, bad


def test_gold_k22_equals_custody():
    src = {(r["period"], r["custodian_id"]): r["k22_custody_fee_bp_annualised"] for r in rows("custody/k22_monthly.csv")}
    bad = [(r["period"], r["custodian_id"]) for r in rows("gold/k22.csv") if not close(r["value"], src[(r["period"], r["custodian_id"])], 0.0001)]
    assert not bad and len(src) == 39, bad


# ---- the answer key: every evidence, voice and document it names exists in the pack ------------------------------------------

def _json_ids(node) -> set:
    if isinstance(node, dict):
        return ({node["id"]} if isinstance(node.get("id"), str) else set()) | {i for v in node.values() for i in _json_ids(v)}
    if isinstance(node, list):
        return {i for v in node for i in _json_ids(v)}
    return set()


def _found(ref: dict) -> str | None:
    """None when {file, key} resolves: a CSV row matching every key column, a JSON object with that id, or a document with no key."""
    f = DC / ref["file"]
    if not f.is_file():
        return f"{ref['file']}: no such file"
    key = ref.get("key")
    if not key:
        return None
    if f.suffix == ".csv":
        ok = any(all(r.get(c) == str(v) for c, v in key.items()) for r in rows(ref["file"]))
    else:
        ok = key.get("id") in _json_ids(json.loads(f.read_text(encoding="utf-8")))
    return None if ok else f"{ref['file']}: no row {key}"


def test_every_evidence_voice_and_document_in_the_answer_key_exists():
    if not KEY.is_file():
        pytest.skip("answer_key.yaml not there yet")
    import yaml
    truths = yaml.safe_load(KEY.read_text(encoding="utf-8"))["truths"]
    assert sorted(truths) == [f"T{i}" for i in range(1, 9)]
    refs = [r if isinstance(r, dict) else {"file": r} for t in truths.values()
            for r in (t.get("evidence") or []) + (t.get("voices") or []) + (t.get("documents") or [])]
    assert len(refs) > 50, len(refs)
    missing = [m for m in map(_found, refs) if m]
    assert not missing, missing[:30]


def test_loader_refreshes_the_reported_side_and_keeps_signatures(tmp_path):
    """FX10: the Prove comparison reads the same pack data on both sides after a load; a re-run writes nothing new; signatures stay."""
    from sh_platform.build.prove import _merge
    from sh_platform.plane import PlaneStore
    from sh_platform.profile import record
    from sh_platform.warehouse import open_company, refresh_readonly_copy
    from tools.seed_demo_cycle import load_reported
    plane = PlaneStore(tmp_path).create("fx10-co").ensure()
    con = open_company(plane)
    con.execute("create table gold.k01 (period varchar, value double)")
    con.execute("insert into gold.k01 values ('2026-09', 148.5)")
    con.close()
    refresh_readonly_copy(plane)
    for k, v in (("measure", "K01"), ("figure", 21.4), ("unit", "%"), ("period_end", "2026-09-30")):
        record(plane, f"reported_figures.f1.{k}", v, {"mark": "stated", "by": "Lens", "from": "a pack"})
    plane.path("build").mkdir(parents=True, exist_ok=True)
    plane.path("build", "blueprint.json").write_text(json.dumps({"lineage": [{"measure": "K01", "mart": "gold.k01.value", "transform": "sum"}]}), encoding="utf-8")
    signed = {"state": "signed", "by": "Tess", "at": "2026-10-01", "note": "ok"}
    plane.path("build", "prove.json").write_text(json.dumps({"measures": [{"code": "K01", "uat": signed, "periods": [
        {"period": "2026-09", "ours": 21.4, "reported": 21.4, "result": "match", "reason": None, "accepted_by": None}]}]}), encoding="utf-8")
    first = load_reported(plane, DC)
    assert first["cells"] == 2 and first["match"] == 1 and first["gap"] == 0 and first["signed"] == 1 and first["checks"] == 1
    m = _merge(plane, json.loads(plane.path("build", "prove.json").read_text(encoding="utf-8")))["measures"][0]
    assert m["periods"][0]["reported"] == 148.5 and m["uat"] == signed
    assert load_reported(plane, DC) == {**first, "cells": 0}
