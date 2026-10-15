"""SF04: the sandbox model engine. Span's draft of the silver model and the gold contract is never trusted as written:

  1. normalise   defaults the engine needs (surrogate keys, SCD2 columns, mart op)
  2. check       every table and column it names must exist in what it builds
  3. sandbox     the whole model is BUILT in a scratch DuckDB file per draft (warehouse/sandbox/<draft_id>.duckdb) with the
                 company warehouse attached read-only, then the file is deleted. Counts only come back, and every error is
                 scrubbed of values (`scrub`) before anyone (Span included) sees it.

Copied from the earlier repo: emitters/model_drafting.py `_free_surrogate_name`, `normalise`, `_known_refs`, `check` (dashboards,
attribution and derived tables dropped) and the `sandbox_build` order; emitters/silver_transform.py scd1, scd2 and fact builders
(bronze lineage columns are CURRENT's `_load_id`/`_loaded_at`; the scd2 key may have several columns, as the scd1 fix already did).
Gold is reshaped to CURRENT's one gold shape (period 'YYYY-MM', value double; transforms.build_mart). No route, no model call."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import duckdb

from sh_platform.warehouse import LOAD_ID, LOADED_AT, _q

log = logging.getLogger(__name__)

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_DRAFT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
OPS = ("sum", "latest")
BRONZE = "co.bronze"  # the company warehouse, attached read-only as `co`


# --------------------------------------------------------------------------- normalise + check (model_drafting.py L295-L525)

def _free_surrogate_name(wanted: str, taken: set[str]) -> str:
    """A surrogate key must not be named after a column the source already has: silver copies every source column and adds the
    surrogate, so a clash writes the same column twice (DuckDB allows it silently, other warehouses refuse the table)."""
    if wanted not in taken:
        return wanted
    base = wanted[:-4] if wanted.endswith("_key") else wanted
    for candidate in (f"{base}_sk", f"{base}_surrogate_key", f"{base}_dim_key"):
        if candidate not in taken:
            return candidate
    return f"{base}_sk_{len(taken)}"


def _normalise_rationale(plan: dict[str, Any]) -> dict[str, Any]:
    """The model's rationale, taken exactly as given, never invented. No `rationale` normalises to the same empty shape."""
    r = plan.get("rationale") if isinstance(plan.get("rationale"), dict) else {}
    entities = r.get("entities") if isinstance(r.get("entities"), dict) else {}
    marts = r.get("marts") if isinstance(r.get("marts"), dict) else {}
    return {"entities": {str(k): v for k, v in entities.items() if isinstance(v, dict)},
            "marts": {str(k): v for k, v in marts.items() if isinstance(v, dict)}}


def _apply_rationale(items: list[dict[str, Any]], mapping: dict[str, Any]) -> None:
    """`description` (only when the item has none) and `provenance` from the rationale's because/from for its name."""
    for item in items:
        info = mapping.get(item.get("name"))
        if not isinstance(info, dict):
            continue
        if info.get("because") and not item.get("description"):
            item["description"] = str(info["because"])
        frm = [str(x) for x in info.get("from") or [] if str(x).strip()]
        if frm:
            item["provenance"] = frm


def normalise(plan: dict[str, Any], source_columns: dict[str, list[str]] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """plan = {"silver_model": {dimensions, facts, grain_statement?}, "gold_contract": {marts}, "rationale"?} -> (model, gold).

    dimension {name, type: scd1|scd2, business_key: [col], source: [bronze table], tracked_attributes?: [col], surrogate_key?}
    fact      {name, grain: [col], source: [bronze table], type?, foreign_keys?: [{dimension, on}]}
    mart      {name, source_fact: <silver entity>, field: <column>, op: sum|latest, date: <date column>, measure?: <code>}"""
    sm = plan.get("silver_model") if isinstance(plan.get("silver_model"), dict) else {}
    gc = plan.get("gold_contract") if isinstance(plan.get("gold_contract"), dict) else {}
    rationale = _normalise_rationale(plan)
    model: dict[str, Any] = {"grain_statement": str(sm.get("grain_statement") or ""), "dimensions": [], "facts": []}
    for d in sm.get("dimensions") or []:
        if not isinstance(d, dict):
            continue
        source_name = (list(d.get("source") or [])[:1] or [""])[0]
        taken = set((source_columns or {}).get(source_name) or [])
        entry = {"name": d.get("name"), "type": d.get("type") or "scd1", "business_key": list(d.get("business_key") or []),
                 "surrogate_key": _free_surrogate_name(d.get("surrogate_key") or f"{str(d.get('name') or 'dim').removeprefix('dim_')}_key", taken),
                 "source": [source_name] if source_name else []}
        if d.get("description"):
            entry["description"] = str(d["description"])
        if entry["type"] == "scd2":
            entry.update(effective_from="row_start_date", effective_to="row_end_date", current_flag="row_is_current",
                         tracked_attributes=list(d.get("tracked_attributes") or []))
        model["dimensions"].append(entry)
    for f in sm.get("facts") or []:
        if not isinstance(f, dict):
            continue
        entry = {"name": f.get("name"), "grain": list(f.get("grain") or []), "type": f.get("type") or "transaction",
                 "source": list(f.get("source") or [])[:1],
                 "foreign_keys": [{k: v for k, v in fk.items() if k in ("dimension", "on")} for fk in f.get("foreign_keys") or [] if isinstance(fk, dict)]}
        if f.get("description"):
            entry["description"] = str(f["description"])
        model["facts"].append(entry)
    marts = gc.get("marts")
    if isinstance(marts, dict):  # one mart written as an object instead of a list of one
        marts = [marts] if "name" in marts else list(marts.values())
    gold: dict[str, Any] = {"marts": []}
    for m in marts or []:
        if not isinstance(m, dict):
            continue
        entry = {k: m.get(k) for k in ("name", "source_fact", "field", "date", "measure", "description") if m.get(k)}
        entry["op"] = str(m.get("op") or "sum").lower()
        gold["marts"].append(entry)
    _apply_rationale(model["dimensions"] + model["facts"], rationale["entities"])
    _apply_rationale(gold["marts"], rationale["marts"])
    return model, gold


def known_refs(source_ids: list[str], measures: list[str] | None = None) -> set[str]:
    """What a rationale's `from` may name: a source the draft was given, or a measure code (model_drafting `_known_refs`)."""
    return {str(s) for s in source_ids if s} | {str(m) for m in measures or [] if m}


def _valid_ref(ref: str, known: set[str]) -> bool:
    ref = ref.strip()
    return ref in known or ref.split(":", 1)[0].strip() in known


def check(model: dict[str, Any], gold: dict[str, Any], sources: dict[str, list[str]], refs: set[str] | None = None) -> list[str]:
    """Static checks: what the sandbox build would otherwise fail on less clearly. `sources` is {bronze table: [columns]}."""
    errors: list[str] = []
    columns_of: dict[str, set[str]] = {}
    for kind, items in (("dimension", model["dimensions"]), ("fact", model["facts"])):
        for e in items:
            name = e.get("name") or ""
            if not _NAME.match(str(name)):
                errors.append(f"silver {kind} {name!r}: names are lowercase letters, digits and _")
                continue
            if name in columns_of:
                errors.append(f"silver {kind} {name}: duplicate name")
            src = (e.get("source") or [None])[0]
            if src not in sources:
                errors.append(f"silver {kind} {name}: source {src!r} is not one of the sources {sorted(sources)}")
                continue
            cols = set(sources[src])
            columns_of[name] = cols | ({e["surrogate_key"]} if kind == "dimension" else set())
            keys = e.get("business_key") if kind == "dimension" else e.get("grain")
            missing = [k for k in keys or [] if k not in cols]
            if not keys:
                errors.append(f"silver {kind} {name}: needs {'business_key' if kind == 'dimension' else 'grain'} columns")
            if missing:
                errors.append(f"silver {kind} {name}: {missing} are not columns of {src} ({sorted(cols)})")
            if kind == "dimension":
                if e.get("type") not in ("scd1", "scd2"):
                    errors.append(f"silver dimension {name}: type must be scd1 or scd2")
                if e.get("surrogate_key") in cols:
                    errors.append(f"silver dimension {name}: surrogate_key {e['surrogate_key']!r} is already a column of {src}; "
                                  f"the name must be different (e.g. {str(e['surrogate_key']).removesuffix('_key')}_sk)")
                if e.get("type") == "scd2":
                    tracked = e.get("tracked_attributes") or []
                    if not tracked or [t for t in tracked if t not in cols]:
                        errors.append(f"silver dimension {name}: type 2 needs tracked_attributes that are columns of {src}")
    for f in model["facts"]:
        for fk in f.get("foreign_keys") or []:
            if fk.get("dimension") not in {d.get("name") for d in model["dimensions"]}:
                errors.append(f"silver fact {f.get('name')}: foreign key to {fk.get('dimension')!r}, which is not a silver dimension")
            elif fk.get("on") not in columns_of.get(f.get("name"), set()):
                errors.append(f"silver fact {f.get('name')}: foreign key column {fk.get('on')!r} is not one of its columns")
    names: set[str] = set()
    for m in gold.get("marts") or []:
        name = m.get("name") or ""
        if not _NAME.match(str(name)):
            errors.append(f"mart {name!r}: names are lowercase letters, digits and _")
            continue
        if name in names:
            errors.append(f"mart {name}: duplicate name")
        names.add(name)
        if m.get("source_fact") not in columns_of:
            errors.append(f"mart {name}: source_fact {m.get('source_fact')!r} is not a silver entity")
            continue
        cols = columns_of[m["source_fact"]]
        for key in ("field", "date"):
            if m.get(key) not in cols:
                errors.append(f"mart {name}: {key} {m.get(key)!r} is not a column of {m['source_fact']}")
        if m.get("op") not in OPS:
            errors.append(f"mart {name}: op must be sum or latest")
    if not gold.get("marts"):
        errors.append("gold_contract: no marts; draft one mart per measure")
    if refs is not None:
        for item in model["dimensions"] + model["facts"] + list(gold.get("marts") or []):
            for ref in item.get("provenance") or []:
                if not _valid_ref(str(ref), refs):
                    errors.append(f"{item.get('name')}: rationale cites {ref!r}, which is not a source or measure this draft was given")
    return errors


# --------------------------------------------------------------------------- scrub

_TO_TYPE = re.compile(r"\bto ([A-Za-z]\w*)")
_SOURCE_COLUMN = re.compile(r"\bsource column (\w+)")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\W[^\"]*\"")  # any single-quoted literal; a double-quoted one unless it is a plain identifier
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
# SF14: every quoted literal goes, except a plain identifier right after "column" or "table" (Binder errors name the column to fix)
_ANY_QUOTED = re.compile(r"(?<!column )(?<!table )(?:'[^']*'|\"[^\"]*\"|\u201c[^\u201d]*\u201d|\u2018[^\u2019]*\u2019|`[^`]*`)"
                         r"|(?:(?<=column )|(?<=table ))(?:'[^']*'|\"[^\"]*\W[^\"]*\")", re.I)
_VALUE_AFTER = re.compile(r"\b(?:values?|input|string|line|candidate)\b|[{:]\s*\{", re.I)


def scrub(error: str) -> str:
    """Keep table, column and error kind; drop literals and values. Only the first line counts: DuckDB echoes the SQL and
    suggestions on later lines. A conversion error names the value it choked on, so it is rewritten whole."""
    first = str(error or "").strip().splitlines()[0] if str(error or "").strip() else ""
    if first.lower().startswith("conversion error"):
        bare = _QUOTED.sub("", first)  # a value such as 'go to market' must not be read as the type
        to, col = _TO_TYPE.search(bare), _SOURCE_COLUMN.search(bare)
        kind = (to[1] if to else "date" if re.search(r"\bdate\b", first, re.I) else "the expected type").lower()
        kind = {"int32": "integer", "int64": "bigint"}.get(kind, kind)
        return f"column {col[1]}: values do not fit type {kind}" if col else f"values do not fit type {kind}"
    first = re.split(r"\bvalues?\b\s*[:=]", first, maxsplit=1, flags=re.I)[0]
    # SF14: a value can follow these words unquoted or sit in any quotes ("with value Jade", curly quotes, "Input: {Jade"): drop every
    # quoted literal and cut at the first such word, so only the table, the column the caller names and the error kind are left
    kind, sep, rest = first.partition(": ")
    first = kind + sep + _VALUE_AFTER.split(_ANY_QUOTED.sub("", rest), maxsplit=1)[0] if sep else _VALUE_AFTER.split(_ANY_QUOTED.sub("", first), maxsplit=1)[0]
    first = _NUMBER.sub("", _QUOTED.sub("", first))
    return " ".join(first.split())[:300]


# --------------------------------------------------------------------------- builders (silver_transform.py L109-L171, L324-L333)

def _bronze_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Business columns only: the runner's two lineage columns are left out."""
    rows = con.execute("select column_name from information_schema.columns where table_catalog = 'co' and table_schema = 'bronze' and table_name = ? "
                       "order by ordinal_position", [table]).fetchall()
    return [r[0] for r in rows if r[0] not in (LOAD_ID, LOADED_AT)]


def build_scd1_dimension(con: duckdb.DuckDBPyConnection, dim: dict[str, Any]) -> int:
    """One row per business key: the latest bronze version, full overwrite."""
    bk = ", ".join(map(_q, dim["business_key"]))
    src = dim["source"][0]
    cols = _bronze_columns(con, src)
    if dim["surrogate_key"] in cols:
        raise ValueError(f"{dim['name']}: surrogate_key {dim['surrogate_key']} is already a column of {src}")
    col_list = ", ".join(map(_q, cols))
    con.execute(f"create or replace table silver.{_q(dim['name'])} as "
                f"select row_number() over (order by {bk}) as {_q(dim['surrogate_key'])}, {col_list}, {LOADED_AT} as silver_loaded_at "
                f"from (select *, row_number() over (partition by {bk} order by {LOADED_AT} desc) as rn from {BRONZE}.{_q(src)}) t where rn = 1")
    return con.execute(f"select count(*) from silver.{_q(dim['name'])}").fetchone()[0]


def build_scd2_dimension(con: duckdb.DuckDBPyConnection, dim: dict[str, Any]) -> tuple[int, int]:
    """Many rows per business key, exactly one current. A new version only when a tracked attribute changes."""
    bk = ", ".join(map(_q, dim["business_key"]))
    src = dim["source"][0]
    cols = _bronze_columns(con, src)
    col_list = ", ".join(map(_q, cols))
    hash_expr = "md5(concat_ws('|', " + ", ".join(f"cast({_q(c)} as varchar)" for c in dim["tracked_attributes"]) + "))"
    frm, to, cur = (_q(dim[k]) for k in ("effective_from", "effective_to", "current_flag"))
    over = f"over (partition by {bk} order by {LOADED_AT})"
    con.execute(f"create or replace table silver.{_q(dim['name'])} as "
                f"with ordered as (select *, {hash_expr} as attr_hash, row_number() {over} as version_seq from {BRONZE}.{_q(src)}), "
                f"changes as (select *, lag(attr_hash) {over} as prev_hash from ordered), "
                f"versions as (select * from changes where version_seq = 1 or attr_hash != prev_hash), "
                f"dated as (select *, {LOADED_AT} as {frm}, lead({LOADED_AT}) {over} as {to}, "
                f"(row_number() over (partition by {bk} order by {LOADED_AT} desc, version_seq desc) = 1) as {cur} from versions) "
                f"select row_number() over (order by {bk}, {frm}) as {_q(dim['surrogate_key'])}, {col_list}, {frm}, {to}, {cur} from dated")
    total = con.execute(f"select count(*) from silver.{_q(dim['name'])}").fetchone()[0]
    current = con.execute(f"select count(*) from silver.{_q(dim['name'])} where {cur}").fetchone()[0]
    return total, current


def build_fact(con: duckdb.DuckDBPyConnection, fact: dict[str, Any]) -> int:
    src = fact["source"][0]
    col_list = ", ".join(map(_q, _bronze_columns(con, src)))
    con.execute(f"create or replace table silver.{_q(fact['name'])} as select {col_list} from {BRONZE}.{_q(src)}")
    return con.execute(f"select count(*) from silver.{_q(fact['name'])}").fetchone()[0]


def grain_duplicates(con: duckdb.DuckDBPyConnection, fact: dict[str, Any]) -> bool:
    keys = ", ".join(map(_q, fact["grain"]))
    return con.execute(f"select count(*) - count(distinct ({keys})) from silver.{_q(fact['name'])}").fetchone()[0] > 0


def build_mart(con: duckdb.DuckDBPyConnection, mart: dict[str, Any]) -> int:
    """gold.<mart> in the one gold shape (period 'YYYY-MM', value double), as transforms.build_mart. Blank text is empty; anything
    else that does not fit raises a conversion error, which `scrub` turns into a column and a type."""
    field, day = (f"cast(nullif(trim(cast({_q(mart[k])} as varchar)), '') as {t})" for k, t in (("field", "double"), ("date", "date")))
    agg = f"sum({field})" if mart["op"] == "sum" else f"arg_max({field}, {day})"
    con.execute(f"create or replace table gold.{_q(mart['name'])} as select strftime({day}, '%Y-%m') as period, {agg}::double as value "
                f"from silver.{_q(mart['source_fact'])} where {day} is not null group by 1")
    return con.execute(f"select count(*) from gold.{_q(mart['name'])}").fetchone()[0]


# --------------------------------------------------------------------------- sandbox (model_drafting.py L525-L638)

def sandbox_path(plane, draft_id: str) -> Path:
    if not _DRAFT_ID.match(str(draft_id or "")):
        raise ValueError("invalid draft id")
    return plane.path("warehouse", "sandbox", f"{draft_id}.duckdb")


def _remove(path: Path) -> None:
    for p in (path, path.with_name(path.name + ".wal")):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            log.warning("sandbox file could not be removed")


def sandbox_build(plane, draft_id: str, model: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """Build the draft in warehouse/sandbox/<draft_id>.duckdb from the company's bronze tables (attached read-only), then delete
    the file. Returns {built: {silver: [names], gold: [names]}, counts: {name: rows}, errors: [scrubbed]}. Never writes the
    company warehouse. Stops at the first failing layer, as the earlier sandbox did: later tables read the earlier ones."""
    report: dict[str, Any] = {"built": {"silver": [], "gold": []}, "counts": {}, "errors": []}
    errors: list[str] = report["errors"]
    company = plane.path("warehouse", "company.duckdb")
    if not company.is_file():
        errors.append("no bronze tables yet: the company warehouse has no data")
        return report
    path = sandbox_path(plane, draft_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _remove(path)
    con = None
    try:
        con = duckdb.connect(str(path))
        con.execute("attach '" + str(company).replace("'", "''") + "' as co (read_only)")
        for s in ("silver", "gold"):
            con.execute(f"create schema {s}")
        have = {r[0] for r in con.execute("select table_name from information_schema.tables where table_catalog = 'co' and table_schema = 'bronze'").fetchall()}
        for e in model["dimensions"] + model["facts"]:
            if e["source"][0] not in have:
                errors.append(f"silver {e['name']}: source {e['source'][0]} has no bronze table yet")
        if errors:
            return report
        for d in model["dimensions"]:
            try:
                report["counts"][d["name"]] = build_scd2_dimension(con, d)[0] if d["type"] == "scd2" else build_scd1_dimension(con, d)
                report["built"]["silver"].append(d["name"])
            except (duckdb.Error, ValueError) as exc:
                errors.append(f"silver {d['name']}: {scrub(str(exc))}")
        for f in model["facts"]:
            try:
                report["counts"][f["name"]] = build_fact(con, f)
                report["built"]["silver"].append(f["name"])
                if grain_duplicates(con, f):
                    errors.append(f"silver {f['name']}: grain {', '.join(f['grain'])} is not unique (duplicates exist)")
            except duckdb.Error as exc:
                errors.append(f"silver {f['name']}: {scrub(str(exc))}")
        if errors:
            return report
        for m in gold.get("marts") or []:
            try:
                n = build_mart(con, m)
                report["counts"][m["name"]] = n
                report["built"]["gold"].append(m["name"])
                if not n:
                    errors.append(f"mart {m['name']}: no period could be computed ({m['date']} is empty on every row)")
            except duckdb.Error as exc:
                msg = scrub(str(exc))  # the blank-to-empty wrapper hides the column from DuckDB; the mart knows it by type
                col = {"values do not fit type double": m["field"], "values do not fit type date": m["date"]}.get(msg)
                errors.append(f"mart {m['name']}: {'column ' + col + ': ' if col else ''}{msg}")
        return report
    except duckdb.Error as exc:
        errors.append(f"sandbox: {scrub(str(exc))}")
        return report
    finally:
        if con is not None:
            con.close()
        _remove(path)
