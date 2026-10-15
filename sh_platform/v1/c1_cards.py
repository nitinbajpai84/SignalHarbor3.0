"""C1 KPI cards: the signed SOW's KPIs with value, period and trend from the gold marts, shown only for periods the ops manager marked
loaded (build/ops/loaded.json); otherwise "Not available yet" with the scan report's reason. A figure opens to its run and its rows.

Reads only: intents/<iid>/sow.json, build/scan/<iid>.json, build/ops/loaded.json, warehouse/runs.json and the gold marts. Copied from 2.0:
the trend query and pipeline lookup (sh_platform/consume/measure.py `_full_trend`, `_pipeline`) and the range rule (consume/range.py)."""
from __future__ import annotations

import re

import duckdb

from sh_platform.consume.measure import _full_trend, _pipeline
from sh_platform.consume.range import CODE, PERIODS, breaks
from sh_platform.jsonfile import read_json_strict
from sh_platform.warehouse import open_readonly

NA = "Not available yet"
IID = re.compile(r"[A-Za-z0-9_-]{1,80}")
PERIOD = re.compile(r"\d{4}-\d{2}")
ROWS = 50


def _read(plane, *parts, kind=dict):
    try:
        return read_json_strict(plane.path(*parts), kind) or kind()
    except (OSError, ValueError):
        return kind()


def signed_sows(plane) -> list[dict]:
    folder = plane.path("intents")
    out = []
    for d in sorted(folder.iterdir()) if folder.is_dir() else []:
        if d.is_dir() and IID.fullmatch(d.name):
            sow = _read(plane, "intents", d.name, "sow.json")
            if sow.get("state") == "signed":
                out.append({**sow, "intent_id": sow.get("intent_id") or d.name})
    return out


def _loaded(plane) -> dict[tuple[str, str], dict]:
    """(period, source_id) -> the newest entry; a later line in the file wins."""
    out = {}
    for p in _read(plane, "build", "ops", "loaded.json").get("periods") or []:
        if isinstance(p, dict) and p.get("period"):
            out[(str(p["period"]), str(p.get("source_id") or ""))] = p
    return out


def _is_loaded(loaded: dict, period: str, sources: list[str]) -> bool:
    """Every source the KPI uses is marked loaded for the period. A KPI that names no source needs one loaded line and no not-loaded line."""
    if sources:
        return all((loaded.get((period, s)) or {}).get("state") == "loaded" for s in sources)
    states = [e.get("state") for (p, _), e in loaded.items() if p == period]
    return "loaded" in states and "not_loaded" not in states


def table_of(sow: dict, code: str) -> str | None:
    """The gold table the SOW catalogue says feeds the KPI; None when it does not say (a figure is never read from a guessed table)."""
    row = next((c for c in sow.get("catalogue") or [] if isinstance(c, dict) and c.get("layer") == "gold" and code in (c.get("feeds_kpis") or [])), None)
    if not row:
        return None
    t = str(row["table"]).lower().removeprefix("gold.")
    return t if CODE.fullmatch(t) else None


def _reason(scan: dict, code: str, loaded: dict, sources: list[str], built: bool) -> str:
    k = next((x for x in scan.get("kpis") or [] if isinstance(x, dict) and x.get("code") == code), None)
    if k and k.get("status") != "available":
        miss = "; ".join(f"{m.get('what')} (expected in {m.get('where_expected')})" for m in k.get("missing") or [] if isinstance(m, dict))
        return f"The scan found this {'partly available' if k.get('status') == 'partly' else 'not available'}" + (f": missing {miss}" if miss else "")
    agreed = scan.get("agreed")
    if isinstance(agreed, dict) and code not in (agreed.get("scope") or []):
        return "Not in the agreed scope"
    nl = [e for (p, s), e in sorted(loaded.items()) if e.get("state") == "not_loaded" and (not sources or s in sources)]
    if nl:
        return f"{nl[-1]['period']} not loaded" + (f": {nl[-1]['reason']}" if nl[-1].get("reason") else "")
    if not built:
        return "Not built yet: the warehouse holds no figures for it"
    if not k:
        return "Not scanned yet"
    return "No period has been marked loaded yet"


def card(plane, sow: dict, k: dict, scan: dict, loaded: dict) -> dict:
    code, sources = str(k.get("code")), [str(s) for s in k.get("source_ids") or []]
    table = table_of(sow, code)
    full = _full_trend(plane, table) if table else []
    shown = [t for t in full if _is_loaded(loaded, t["period"], sources)][-PERIODS:]
    head = {"code": code, "name": k.get("name") or code, "definition": k.get("definition"), "unit": k.get("unit"), "owner": k.get("owner"),
            "period_kind": k.get("period"), "table": f"gold.{table}" if table else None, "source_ids": sources}
    if not shown:
        return {**head, "latest": None, "trend": [], "range_break": False, "reason": _reason(scan, code, loaded, sources, bool(full))}
    return {**head, "latest": shown[-1], "trend": shown, "range_break": breaks(shown)["break"], "reason": None}


def build(plane) -> dict:
    loaded = _loaded(plane)
    out = []
    for sow in signed_sows(plane):
        iid = sow["intent_id"]
        scan = _read(plane, "build", "scan", f"{iid}.json")
        kpis = [card(plane, sow, k, scan, loaded) for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")]
        out.append({"intent_id": iid, "title": sow.get("title"), "signature": sow.get("signature"), "kpis": kpis})
    return {"intents": out}


def _run_for(plane, sources: list[str], period: str) -> list[dict]:
    """Per source, the first run started in or after the period: the load that brought it in."""
    runs = _read(plane, "warehouse", "runs.json").get("runs") or []
    out = []
    for s in sources:
        mine = sorted((r for r in runs if isinstance(r, dict) and r.get("source") == s and str(r.get("started") or "")[:7] >= period),
                      key=lambda r: str(r.get("started")))
        out.append({"source_id": s, "run": mine[0] if mine else None})
    return out


def _rows(plane, table: str, period: str) -> tuple[list[str], list[dict]]:
    try:
        con = open_readonly(plane)
    except duckdb.Error:
        return [], []
    try:
        cols = [c[0] for c in con.execute(f"describe gold.{table}").fetchall()]
        rows = con.execute(f'select * from gold.{table} where cast("{cols[0]}" as varchar) = ? limit {ROWS}', [period]).fetchall()
    except duckdb.Error:
        return [], []
    finally:
        con.close()
    return cols, [{c: (v if isinstance(v, (int, float, str)) or v is None else str(v)) for c, v in zip(cols, r)} for r in rows]


def figure(plane, iid: str, code: str, period: str) -> dict | None:
    """One figure's run and rows (2.0's measure page drill-down). None when the KPI is unknown or the period is not loaded."""
    if not (IID.fullmatch(iid) and PERIOD.fullmatch(period)):
        return None
    sow = next((s for s in signed_sows(plane) if s["intent_id"] == iid), None)
    k = next((x for x in (sow or {}).get("kpis") or [] if isinstance(x, dict) and x.get("code") == code), None)
    if k is None:
        return None
    c = card(plane, sow, k, {}, _loaded(plane))
    point = next((t for t in c["trend"] if t["period"] == period), None)
    if point is None:
        return None
    table = c["table"].removeprefix("gold.")
    cols, rows = _rows(plane, table, period)
    return {"intent_id": iid, "code": code, "name": c["name"], "period": period, "value": point["value"], "table": c["table"],
            "runs": _run_for(plane, c["source_ids"], period), "pipeline": _pipeline(plane, table), "columns": cols, "rows": rows}
