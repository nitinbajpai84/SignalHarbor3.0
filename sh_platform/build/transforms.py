"""Silver, gold and rule SQL for the built-in runner (DuckDB). Counts only: nothing here returns a row.

Silver typing and dedup follow the earlier repo's silver_transform in spirit (typed columns, one row per distinct record), but that file is
driven by a domain model and a dialect layer, so the logic here is a small rewrite."""
import re

from sh_platform.warehouse import LOAD_ID, LOADED_AT, _q

_TYPES = ("bigint", "double", "date")


def build_silver(con, source: str) -> list[tuple[str, str]]:
    """silver.<source> from bronze.<source>: blank text becomes null, a column takes the first type all its values fit, rows deduplicated."""
    cols = [r[0] for r in con.execute("select column_name from information_schema.columns where table_schema = 'bronze' and table_name = ? "
                                      "order by ordinal_position", [source]).fetchall() if r[0] not in (LOAD_ID, LOADED_AT)]
    typed: list[tuple[str, str]] = []
    for c in cols:
        t = "varchar"
        for cand in _TYPES:
            bad = con.execute(f"select count(*) from bronze.{source} where nullif(trim({_q(c)}), '') is not null "
                              f"and try_cast(trim({_q(c)}) as {cand}) is null").fetchone()[0]
            if not bad:
                t = cand
                break
        typed.append((c, t))
    sel = ", ".join(f"try_cast(trim({_q(c)}) as {t}) as {_q(c)}" if t != "varchar" else f"nullif(trim({_q(c)}), '') as {_q(c)}" for c, t in typed)
    con.execute(f"create or replace table silver.{source} as select distinct {sel} from bronze.{source}")
    return typed


def op_of(transform: str) -> str | None:
    t = (transform or "").lower()
    return "sum" if "sum" in t else "latest" if "latest" in t else None


def build_mart(con, source: str, table: str, measures: list[tuple[str, str, str]], typed: list[tuple[str, str]], target: str = "") -> bool:
    """gold.<table> (or <target>.gold.<table>) in the one gold shape (period 'YYYY-MM', value double); a run upserts the periods it computed
    and never drops others. False, table untouched, when there is no date column or no numeric measure. ponytail: first measure only."""
    have = dict(typed)
    d = next((c for c, t in typed if t == "date"), None)
    p = None if d else next((c for c, t in typed if t == "varchar" and c.lower() in ("period", "month", "as_of_month")), None)
    if p and con.execute(f"select count(*) from silver.{source} where {_q(p)} is not null and not regexp_matches({_q(p)}, '^\\d{{4}}-\\d{{2}}$')").fetchone()[0]:
        p = None  # a period column must hold YYYY-MM throughout
    key = d or p
    sel = [f"{'sum' if o == 'sum' else 'arg_max'}({_q(f)}{'' if o == 'sum' else ', ' + _q(key)})::double" for c, f, o in measures
           if o and have.get(f) in ("bigint", "double") and (o == "sum" or key)]
    if not sel or not key:
        return False
    name = f"{target + '.' if target else ''}gold.{table}"
    new = f"select {'strftime(' + _q(d) + ', ' + chr(39) + '%Y-%m' + chr(39) + ')' if d else _q(p)} as period, {sel[0]} as value from silver.{source} group by 1"
    if con.execute("select count(*) from information_schema.tables where table_schema = 'gold' and table_name = ? and table_catalog = ?",
                   [table, target or con.execute("select current_database()").fetchone()[0]]).fetchone()[0]:
        con.execute(f"delete from {name} where period in (select period from ({new}))")
        con.execute(f"insert into {name} by name {new}")
    else:
        con.execute(f"create table {name} as {new}")
    return True


_NUM = r"(-?\d+(?:\.\d+)?)"


def _kind(text: str) -> str | None:
    return "unique" if re.search(r"uniq|duplicate", text) else "empty" if re.search(r"empty|null|missing|blank|complete", text)         else "range" if re.search(r"range|between|within|negative|>=|<=", text) else None


def _bounds(text: str) -> tuple[float | None, float | None]:
    m = re.search(rf"{_NUM}\s*(?:to|and|-)\s*{_NUM}", text)
    return (float(m[1]), float(m[2])) if m else (0.0, None) if re.search(r"non-?negative|>=\s*0|not negative", text) else (None, None)


def _out_of_range(f: str, lo: float, hi: float | None) -> str:
    return f"({_q(f)} < {lo}" + (f" or {_q(f)} > {hi}" if hi is not None else "") + ")"


def check_rule(con, source: str, rule: str, fields: list[str], keys: list[str], typed: list[tuple[str, str]]) -> tuple[bool, int] | None:
    """(passed, count of offending rows) for a non-empty, uniqueness or range rule; None when the rule text is not one of these."""
    have, text = dict(typed), rule.lower()
    fs = [f for f in fields if f in have]
    total = con.execute(f"select count(*) from silver.{source}").fetchone()[0]
    kind = _kind(text)
    if kind == "unique":
        ks = [k for k in keys if k in have]
        if not ks:
            return None
        n = con.execute(f"select count(*) - count(distinct ({', '.join(map(_q, ks))})) from silver.{source}").fetchone()[0]
    elif kind == "empty":
        if not fs:
            return None
        n = con.execute(f"select count(*) from silver.{source} where " + " or ".join(f"{_q(f)} is null" for f in fs)).fetchone()[0]
        if not total:
            return False, 0
    elif kind == "range":
        nums = [f for f in fs if have[f] in ("bigint", "double")]
        lo, hi = _bounds(text)
        if not nums or lo is None:
            return None
        n = con.execute(f"select count(*) from silver.{source} where " + " or ".join(_out_of_range(f, lo, hi) for f in nums)).fetchone()[0]
    else:
        return None
    return n == 0, n


def _lit(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def quarantine(con, source: str, rule_id: str, rule: str, fields: list[str], keys: list[str], typed: list[tuple[str, str]],
               run_id: str) -> list[dict]:
    """Copy the silver rows that break one rule into quarantine.<source> with `_rule`, `_field` and `_run_id`, one copy per offending field
    (a uniqueness rule names its keys together and copies every row of a key that occurs more than once). Returns [{rule, field, count}].
    The table never leaves the plane; only the counts go on the run record. The caller empties the table at the start of each run."""
    have, text = dict(typed), rule.lower()
    fs, kind = [f for f in fields if f in have], _kind(text)
    if kind == "unique":
        ks = [k for k in keys if k in have]
        tails = [(", ".join(ks), f"qualify count(*) over (partition by {', '.join(map(_q, ks))}) > 1")] if ks else []
    elif kind == "empty":
        tails = [(f, f"where {_q(f)} is null") for f in fs]
    elif kind == "range":
        lo, hi = _bounds(text)
        tails = [] if lo is None else [(f, "where " + _out_of_range(f, lo, hi)) for f in fs if have[f] in ("bigint", "double")]
    else:
        tails = []
    con.execute("create schema if not exists quarantine")
    out = []
    for field, tail in tails:
        sel = f"select *, {_lit(rule_id)} as _rule, {_lit(field)} as _field, {_lit(run_id)} as _run_id from silver.{source} {tail}"
        exists = con.execute("select count(*) from information_schema.tables where table_schema = 'quarantine' and table_name = ? "
                             "and table_catalog = current_database()", [source]).fetchone()[0]
        con.execute(f"insert into quarantine.{source} by name {sel}" if exists else f"create table quarantine.{source} as {sel}")
        n = con.execute(f"select count(*) from quarantine.{source} where _rule = ? and _field = ? and _run_id = ?", [rule_id, field, run_id]).fetchone()[0]
        if n:
            out.append({"rule": rule_id, "field": field, "count": n})
    return out
