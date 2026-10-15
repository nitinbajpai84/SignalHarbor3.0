"""Flow builds the gold tables whose value is a formula (time-weighted return, fee ratio, …), which the built-in runner cannot express as a
sum or a latest. For each such mapping row Flow asks the model, through the runtime and the egress gateway, for one SELECT over the silver
tables of the KPI's sources that yields (period 'YYYY-MM', value double). The SQL is checked with sqlglot before it runs: one SELECT, only
silver tables the KPI may read, no functions that touch files or the network. The SQL is kept on the mapping row (`sql`, `sql_by`) so the
data engineer can read, correct or replace it; a rejected or failing SQL leaves the row unclear and says why. Never a guessed figure."""
from __future__ import annotations

import json
import logging
import re

import sqlglot
from sqlglot import exp

from sh_platform.build.contracts import slug
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.warehouse import open_company, refresh_readonly_copy

log = logging.getLogger(__name__)
PREFIX = "v1_"
MAX_SQL = 4000
FORBIDDEN = {"read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto", "copy", "attach", "install", "load", "glob",
             "httpfs", "sniff_csv", "read_text", "read_blob"}
ROLE = ("You are Flow, the data engineer. Write one DuckDB SELECT that returns the KPI's figure per month from the silver tables named: "
        "columns exactly `period` (text 'YYYY-MM') and `value` (double), one row per period, ordered by period. Use only the tables and "
        "columns given. Dates may be text: use strftime(try_cast(col as date), '%Y-%m') or the first seven characters of a 'YYYY-MM' text. "
        "Never read files or other schemas. Write no digit anywhere in the SQL (the transport rewrites digits): no numeric literals, GROUP BY "
        "and ORDER BY by column name, table and column aliases of letters only, substr by named columns only; a figure you need must come from "
        "a column. A column that already holds text like 'YYYY-MM' is the period as it is. If the columns given cannot yield this KPI without "
        "guessing what a column means, answer {\"sql\": null, \"note\": \"what is missing\"}: never assume a meaning. Answer with one JSON object only: "
        "{\"sql\": \"...\", \"note\": \"one sentence on the method\"}.")


def _mapping_path(plane, iid: str):
    return plane.path("build", "mapping", f"{iid}.json")


def _read(path, default):
    try:
        return read_json_strict(path, type(default)) if path.exists() else default
    except (OSError, ValueError):
        return default


def tables_of(con, sids: list[str]) -> dict[str, list[tuple[str, str]]]:
    """silver tables that belong to the given SOW source ids (v1_<sid> and v1_<sid>__<folder>), with their columns and types."""
    keys = {PREFIX + slug(s) for s in sids if s}
    out = {}
    for (name,) in con.execute("select table_name from information_schema.tables where table_schema = 'silver'").fetchall():
        if name in keys or any(name.startswith(k + "__") for k in keys):
            out[name] = [(c[0], c[1]) for c in con.execute(f'describe silver."{name}"').fetchall()]
    return out


def check_sql(sql: str, allowed: set[str]) -> str | None:
    """Why the SQL may not run, or None."""
    if not sql or len(sql) > MAX_SQL or ";" in sql.strip().rstrip(";"):
        return "The SQL is empty, too long or holds more than one statement."
    try:
        tree = sqlglot.parse_one(sql, read="duckdb")
    except Exception as e:  # noqa: BLE001 - sqlglot raises its own families
        return "The SQL does not parse: " + " ".join(str(e).split())[:140]
    if not isinstance(tree, exp.Select) and not isinstance(tree, exp.Union):
        return "Only a SELECT may run."
    names = {(e.alias_or_name or "").lower() for e in (tree.selects if isinstance(tree, exp.Select) else [])}
    if isinstance(tree, exp.Select) and names != {"period", "value"}:
        return "The SELECT must name exactly two columns, period and value."
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        schema, name = (t.db or "").lower(), (t.name or "").lower()
        if not schema and name in ctes:
            continue  # a WITH clause of the query itself
        if schema != "silver" or name not in allowed:
            return f"The SQL reads {schema + '.' if schema else ''}{name}, which is not one of the KPI's silver tables."
    for f in tree.find_all(exp.Func):
        if f.sql_name().lower() in FORBIDDEN or (f.name or "").lower() in FORBIDDEN:
            return f"The SQL calls {f.sql_name()}, which may not run here."
    if any(isinstance(n, (exp.Create, exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Command)) for n in tree.walk()):
        return "The SQL changes data; only a SELECT may run."
    return None


def _ask(rt, kpi: dict, row: dict, tables: dict[str, list[tuple[str, str]]]) -> dict | None:
    if rt is None or rt.model is None:
        return None
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.build.agents.runtime import FLOW, MODULE_ID
    from sh_platform.v1.egress_fit import fit
    rt = rt.routed("flow", "formula_sql", want_json=True)  # R1
    alias = {f"table {chr(ord('a') + i)}": t for i, t in enumerate(sorted(tables)[:26])}  # digit-free names: the reply guard rewrites figures
    back = {v: k for k, v in alias.items()}
    ctx = fit({"kpi": {"name": kpi.get("name"), "definition": kpi.get("definition"), "formula": kpi.get("formula"), "unit": kpi.get("unit"),
                       "period": kpi.get("period")},
               "architect_said": row.get("transformation"),
               "tables": [{"table": back[t], "columns": [f"{c} ({ty})" for c, ty in cols]} for t, cols in sorted(tables.items())]})
    try:
        res = run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id or "", MODULE_ID, FLOW, ROLE, ctx,
                        "Write the SELECT for this KPI; name tables by the alias given (silver.\"table a\" and so on).", recorder=rt.recorder)
    except Exception:  # noqa: BLE001 - a model failure leaves the row unclear
        log.warning("Flow's formula call failed")
        return None
    if res.status != "done":
        return None
    a, b = res.text.find("{"), res.text.rfind("}")
    try:
        got = json.loads(res.text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        got = None
    if isinstance(got, dict) and got.get("sql") is None and got.get("note"):
        return {"sql": None, "note": str(got["note"])[:300]}
    if not isinstance(got, dict) or not isinstance(got.get("sql"), str):
        return None
    sql = got["sql"].strip().rstrip(";").strip()
    for k, t in alias.items():  # the alias back to the real table, quoted or not
        sql = re.sub(r'silver\s*\.\s*"?' + re.escape(k) + '"?', f'silver."{t}"', sql, flags=re.I)
        sql = re.sub(r'(?<![\w."])"?' + re.escape(k) + r'"?(?![\w"])', f'silver."{t}"', sql, flags=re.I)
    return {"sql": sql, "note": str(got.get("note") or "")[:300]}


def build(plane, iid: str, rt=None) -> list[dict]:
    """For every gold value row with op formula: ask (or reuse a kept SQL), check, run into gold.<table>. Returns one result per row."""
    path = _mapping_path(plane, iid)
    sheet = _read(path, {})
    sow = _read(plane.path("intents", iid, "sow.json"), {})
    kpis = {k.get("code"): k for k in sow.get("kpis") or [] if isinstance(k, dict)}
    by_table = {str(c.get("table")).lower(): c for c in sow.get("catalogue") or [] if isinstance(c, dict) and c.get("layer") == "gold"}
    rows = [r for r in sheet.get("rows") or [] if r.get("layer") == "gold" and r.get("target_field") == "value" and r.get("op") == "formula"]
    if not rows:
        return []
    results, con = [], open_company(plane)
    try:
        for r in rows:
            table = slug(str(r.get("target_table") or "").removeprefix("gold."))
            cat = by_table.get(table) or {}
            code = next(iter(cat.get("feeds_kpis") or []), table.upper())
            kpi = kpis.get(code) or {"name": table}
            sids = list(dict.fromkeys((kpi.get("source_ids") or []) + [r.get("source_id")]))
            tables = tables_of(con, [s for s in sids if s])
            res = {"table": table, "code": code, "built": False, "why": None, "sql": None, "by": None}
            if not tables:
                res["why"] = "No silver table of the KPI's sources is loaded yet."
                results.append(res)
                continue
            kept = r.get("sql") if r.get("sql_by") == "engineer" else None  # an engineer's SQL is never redrafted
            got = {"sql": kept, "note": "kept as the engineer wrote it"} if kept else (_ask(rt, kpi, r, tables) or _ask(rt, kpi, r, tables))
            if not got:
                res["why"] = "Flow could not write the SQL (no model answer)."
                results.append(res)
                continue
            if not got.get("sql"):
                res["why"] = "Flow says the loaded columns cannot yield this KPI: " + (got.get("note") or "")
                results.append(res)
                continue
            why = check_sql(got["sql"], set(tables))
            if why:
                res.update(why=why, sql=got["sql"], by="flow")
                results.append(res)
                continue
            try:
                con.execute("begin")
                con.execute(f'create or replace table gold."{table}" as select cast(period as varchar) as period, cast(value as double) as value from ({got["sql"]}) q where period is not null order by 1')
                n = con.execute(f'select count(*) from gold."{table}" where value is not null').fetchone()[0]
                con.execute("commit")
                res.update(built=n > 0, sql=got["sql"], by="engineer" if kept else "flow", note=got.get("note"),
                           why=None if n > 0 else "The SQL ran but returned no figures.")
            except Exception as e:  # noqa: BLE001 - DuckDB's own families; the message is Flow's to read, not the person's
                con.execute("rollback")
                res.update(why="The SQL did not run: " + " ".join(str(e).split())[:200], sql=got["sql"], by="flow")
            results.append(res)
    finally:
        con.close()
    refresh_readonly_copy(plane)
    with lock_for(path):  # the SQL and its outcome go on the row, for the engineer
        sheet = _read(path, {})
        for r in sheet.get("rows") or []:
            hit = next((x for x in results if r.get("layer") == "gold" and r.get("target_field") == "value"
                        and slug(str(r.get("target_table") or "").removeprefix("gold.")) == x["table"]), None)
            if hit and hit.get("sql"):
                r["sql"], r["sql_by"] = hit["sql"], hit.get("by") or "flow"
                r["status"] = "mapped" if hit["built"] else "unclear"
                if not hit["built"]:
                    r["rule"] = (hit.get("why") or "")[:300]
        write_json_atomic(path, sheet)
    return results
