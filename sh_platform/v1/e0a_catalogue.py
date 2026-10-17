"""E0a: the data model as a governed catalogue, its versions, change proposals, and the DuckDB warehouse built from it.

DBML is the source of truth. The core model ships in docs/v2/evidence-to-action-mvp.dbml; a company adds an *extension*
(new tables, or new columns on core tables) and never drops or retypes anything core. Nobody else parses DBML: the data agent
and intake call `current`, `tables`, `describe`, `has_field`, `version_of`, `ddl` and `apply` below.

Per company, under data/<company>/model/:  current.json {version}, log.json, versions/<n>/{model.dbml, extension.json,
catalogue.json, meta.json}. Version 1 is the core file, written lazily on the first read. A proposal is a version whose
state is `proposed`; approving it makes it current. The warehouse is data/<company>/warehouse/evidence.duckdb (add tables
and columns only; no constraints beyond primary keys and not null).

Extension rules (one place, here): a Table block that names a core table lists only the columns to ADD; a block for a company
table lists all its columns (a column left out is removed from the catalogue, not from the warehouse); an uploaded extension
overlays the current one by table name, so tables it does not mention stay.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from pydbml import PyDBML

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import DATA_ENGINEER, HEAD_OF_DATA, REFUSAL, seat_of

log = logging.getLogger(__name__)
CORE_FILE = Path(__file__).resolve().parents[2] / "docs" / "v2" / "evidence-to-action-mvp.dbml"
_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
_CORE_REFUSAL = "Core tables change only through a product release."
_cache: dict[tuple, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- DBML to catalogue ------------------------------------------------------------------------------------------------------------

def _plain_default(d):
    if d is None or isinstance(d, (bool, int, float, str)):
        return d
    text = str(getattr(d, "text", d)).strip().lower()
    if text in ("now()", "current_timestamp"):
        return {"expr": "now()"}
    raise Refused(400, f"The default {text!r} is not supported. Use a plain number, true or false, or now().")


def _table_dict(t, group: str, layer: str) -> dict:
    cols = [{"name": c.name, "type": str(c.type).lower(), "null": not (c.not_null or c.pk), "pk": bool(c.pk), "unique": bool(c.unique),
             "default": _plain_default(c.default), "note": c.note.text if c.note else "", "layer": layer} for c in t.columns]
    idx = [{"columns": [getattr(s, "name", str(s)) for s in i.subjects], "unique": bool(i.unique), "pk": bool(i.pk)} for i in t.indexes]
    return {"name": t.name, "group": group, "note": t.note.text if t.note else "", "layer": layer, "columns": cols, "indexes": idx}


def _ref_dicts(db, names: set[str] | None = None) -> list[dict]:
    out = []
    for r in db.refs:
        if names is None or r.table1.name in names or r.table2.name in names:
            out.append({"from": {"table": r.table1.name, "columns": [c.name for c in r.col1]},
                        "to": {"table": r.table2.name, "columns": [c.name for c in r.col2]}, "type": r.type})
    return out


def _groups_of(db) -> dict[str, str]:
    return {i.name: g.name for g in db.table_groups for i in g.items}


def _parse(text: str):
    """Parse DBML or refuse with the parser's line and message."""
    try:
        return PyDBML(text)
    except Exception as e:  # noqa: BLE001 - pydbml/pyparsing raise several unrelated types; all become one plain message
        line = getattr(e, "lineno", None)
        msg = getattr(e, "msg", None) or str(e).splitlines()[0][:200]
        raise Refused(400, f"The script could not be read{f' (line {line})' if line else ''}: {msg}") from None


def _core() -> dict:
    key = ("core", CORE_FILE.stat().st_mtime_ns)
    if key not in _cache:
        db = _parse(CORE_FILE.read_text(encoding="utf-8"))
        grp = _groups_of(db)
        _cache.clear()
        _cache[key] = {"tables": [_table_dict(t, grp.get(t.name, ""), "core") for t in db.tables], "refs": _ref_dicts(db)}
    return deepcopy(_cache[key])


# ---- extension: parse, merge, emit -----------------------------------------------------------------------------------------------

def _emit(tables: list[dict], refs: list[dict] | None = None) -> str:
    """Write catalogue tables back as DBML (used for the company extension and for parser stubs)."""
    out: list[str] = []
    for t in tables:
        out.append(f"Table {t['name']} {{")
        for c in t["columns"]:
            a = ["pk"] if c.get("pk") else ([] if c.get("null", True) else ["not null"])
            if c.get("unique"):
                a.append("unique")
            if c.get("default") is not None:
                d = c["default"]
                a.append("default: " + (f"`{d['expr']}`" if isinstance(d, dict) else str(d).lower() if isinstance(d, bool) else repr(d) if isinstance(d, str) else str(d)))
            if c.get("note"):
                a.append("note: '" + c["note"].replace("\\", "\\\\").replace("'", "\\'") + "'")
            out.append(f"  {c['name']} {c['type']}" + (f" [{', '.join(a)}]" if a else ""))
        if t.get("indexes"):
            out.append("  Indexes {")
            out += [f"    ({', '.join(i['columns'])})" + (" [unique]" if i.get("unique") else "") for i in t["indexes"]]
            out.append("  }")
        out.append("}\n")
    for r in refs or []:
        side = lambda s: f"{s['table']}.{s['columns'][0]}" if len(s["columns"]) == 1 else f"{s['table']}.({', '.join(s['columns'])})"
        out.append(f"Ref: {side(r['from'])} {r['type']} {side(r['to'])}")
    for g in sorted({t["group"] for t in tables if t.get("group")}):
        out.append(f"TableGroup {g} {{\n  " + "\n  ".join(t["name"] for t in tables if t.get("group") == g) + "\n}")
    return "\n".join(out) + "\n"


def _parse_extension(text: str, core: dict) -> dict:
    """An uploaded extension as {tables, refs} in catalogue shape. Core tables it does not define are added as stubs after the text,
    so refs to them resolve and the parser's line numbers stay the ones the person sees."""
    defined = set(re.findall(r'(?im)^\s*Table\s+"?([A-Za-z_]\w*)"?', text))
    stubs = _emit([t for t in core["tables"] if t["name"] not in defined])
    db = _parse(text + "\n" + stubs)
    grp = _groups_of(db)
    tables = [_table_dict(t, grp.get(t.name, ""), "company") for t in db.tables if t.name in defined]
    if not tables:
        raise Refused(400, "The script has no tables in it. Add at least one Table block.")
    return {"tables": tables, "refs": _ref_dicts(db, defined)}


def _overlay(ext: dict, new: dict, core_names: set[str]) -> dict:
    out = deepcopy(ext)
    for nt in new["tables"]:
        have = next((t for t in out["tables"] if t["name"] == nt["name"]), None)
        if have is None:
            out["tables"].append(deepcopy(nt))
        elif nt["name"] in core_names:  # a core-table block only adds columns
            have["columns"] += [c for c in nt["columns"] if c["name"] not in {x["name"] for x in have["columns"]}]
        else:
            out["tables"][out["tables"].index(have)] = deepcopy(nt)
    key = lambda r: (r["from"]["table"], tuple(r["from"]["columns"]), r["to"]["table"], tuple(r["to"]["columns"]))
    seen = {key(r) for r in out["refs"]}
    out["refs"] += [r for r in new["refs"] if key(r) not in seen]
    return out


def slug(name) -> str:
    """'unmatched count' / 'Allocation drift (%)' as unmatched_count / allocation_drift; a name that is already usable is returned unchanged."""
    n = str(name or "").strip()
    return n if _NAME.fullmatch(n) else re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")[:63]


def _merge(core: dict, ext: dict) -> dict:
    """Core plus company extension. Refuses any change to a core object and any name or type that cannot be built."""
    ext = deepcopy(ext)
    for et in ext["tables"]:
        for c in et.get("columns") or []:
            c["name"] = slug(c.get("name"))  # a label with spaces never blocks the plan
    tables = {t["name"]: t for t in core["tables"]}
    core_names = set(tables)
    merged = [deepcopy(t) for t in core["tables"]]
    by = {t["name"]: t for t in merged}
    for et in ext["tables"]:
        if et["name"] in core_names:
            existing = {c["name"]: c for c in tables[et["name"]]["columns"]}
            for c in et["columns"]:
                if c["name"] in existing:
                    o = existing[c["name"]]
                    if (c["type"], c["null"], c["pk"]) != (o["type"], o["null"], o["pk"]):
                        raise Refused(400, f"{et['name']}.{c['name']} is a core column. {_CORE_REFUSAL}")
                else:
                    _check_column(et["name"], c)
                    by[et["name"]]["columns"].append({**c, "layer": "company"})
        else:
            if not _NAME.fullmatch(et["name"]):
                raise Refused(400, f"'{et['name']}' is not a usable table name. Use lowercase letters, digits and underscores.")
            for c in et["columns"]:
                _check_column(et["name"], c)
            if not et["columns"]:
                raise Refused(400, f"The table {et['name']} has no columns.")
            merged.append({**deepcopy(et), "group": et.get("group") or "company", "layer": "company",
                           "columns": [{**c, "layer": "company"} for c in et["columns"]]})
    return {"tables": merged, "refs": core["refs"] + deepcopy(ext["refs"])}


def _check_column(table: str, c: dict) -> None:
    if not _NAME.fullmatch(c["name"]):
        raise Refused(400, f"'{c['name']}' on {table} is not a usable column name. Use lowercase letters, digits and underscores.")
    _duck_type(c["type"])


# ---- warehouse DDL --------------------------------------------------------------------------------------------------------------

_SIMPLE = {"uuid": "UUID", "timestamptz": "TIMESTAMPTZ", "timestamp": "TIMESTAMP", "jsonb": "JSON", "json": "JSON", "text": "VARCHAR",
           "tsvector": "VARCHAR", "int": "INTEGER", "integer": "INTEGER", "bigint": "BIGINT", "boolean": "BOOLEAN", "bool": "BOOLEAN",
           "date": "DATE", "float": "DOUBLE", "double": "DOUBLE"}


_ALIAS = {"varchar": "text", "string": "text", "char": "text", "character varying": "text", "datetime": "timestamp", "smallint": "integer",
          "real": "float", "numeric": "numeric(18,2)", "decimal": "numeric(18,2)", "number": "numeric(18,2)", "money": "numeric(18,2)"}


def norm_type(t: str) -> str:
    """FIXC: the catalogue's spelling of a type a person or Span writes (varchar, string, decimal, datetime); anything else is returned as written."""
    t = " ".join(str(t).strip().lower().split())
    return _ALIAS.get(t, t)


def _duck_type(t: str) -> str:
    t = norm_type(t)
    if t in _SIMPLE:
        return _SIMPLE[t]
    if re.fullmatch(r"(?:var)?char\(\d+\)", t):
        return "VARCHAR"
    if (m := re.fullmatch(r"(?:numeric|decimal)\((\d+),\s*(\d+)\)", t)) and int(m[1]) <= 38 and int(m[2]) <= int(m[1]):
        return f"DECIMAL({m[1]},{m[2]})"
    if m := re.fullmatch(r"vector\((\d+)\)", t):
        return f"FLOAT[{m[1]}]"
    raise Refused(400, f"The column type '{t}' is not one the warehouse can hold.")


def _default_sql(d) -> str:
    if isinstance(d, dict):
        return "now()"
    return str(d).lower() if isinstance(d, bool) else "'" + d.replace("'", "''") + "'" if isinstance(d, str) else str(d)


def _coldef(c: dict, adding: bool = False) -> str:
    sql = f'"{c["name"]}" {_duck_type(c["type"])}'
    if c.get("default") is not None:
        sql += f" default {_default_sql(c['default'])}"
    if not adding and not c.get("null", True):
        sql += " not null"
    return sql


def _create(t: dict) -> str:
    pks = [f'"{c["name"]}"' for c in t["columns"] if c.get("pk")]
    lines = [_coldef(c) for c in t["columns"]] + ([f"primary key ({', '.join(pks)})"] if pks else [])
    return f'create table if not exists "{t["name"]}" (\n  ' + ",\n  ".join(lines) + "\n)"


def ddl(catalogue: dict, dialect: str = "duckdb") -> list[str]:
    """One `create table` statement per table of the catalogue, DuckDB flavour. Types map: uuid UUID, timestamptz TIMESTAMPTZ,
    jsonb JSON, vector(n) FLOAT[n], tsvector VARCHAR, varchar(n) VARCHAR, numeric(p,s) DECIMAL(p,s)."""
    if dialect != "duckdb":
        raise ValueError(f"unsupported dialect {dialect!r}")
    return [_create(t) for t in catalogue["tables"]]


def _migrate(db_path: Path, cat: dict) -> dict:
    """Create missing tables and add missing columns to the DuckDB file. Nothing is dropped or altered."""
    created: list[str] = []
    added: list[str] = []
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        have: dict[str, set[str]] = {}
        for tn, cn in con.execute("select table_name, column_name from information_schema.columns where table_schema = 'main'").fetchall():
            have.setdefault(tn, set()).add(cn)
        for t in cat["tables"]:
            if t["name"] not in have:
                con.execute(_create(t))
                created.append(t["name"])
                continue
            for c in t["columns"]:
                if c["name"] not in have[t["name"]]:
                    con.execute(f'alter table "{t["name"]}" add column {_coldef(c, adding=True)}')
                    added.append(f"{t['name']}.{c['name']}")
        alias_layers(con, {t["name"] for t in cat["tables"]})
    except duckdb.Error as e:
        raise Refused(409, f"The warehouse could not take this change: {str(e).splitlines()[0][:200]}") from None
    finally:
        con.close()
    return {"created_tables": created, "added_columns": added}


LAYER_SCHEMAS = ("bronze", "silver", "gold")
_PREFIXED = (("bronze_", "bronze"), ("gold_", "gold"))


def alias_layers(con, silver: set[str]) -> int:
    """Layer-prefixed names for tools like DBeaver: schemas bronze/silver/gold hold views over the real tables in main
    (silver.position_snapshots, gold.<x> for gold_<x>, bronze.<x> for bronze_<x>). Real tables are never renamed. Idempotent: views
    are replaced, and views whose table is gone are dropped. Called where the warehouse is built or changed, not on reads."""
    want: dict[tuple[str, str], str] = {}
    for (t,) in con.execute("select table_name from information_schema.tables where table_schema = 'main' and table_type = 'BASE TABLE'").fetchall():
        if t in silver:
            want["silver", t] = t
        for pre, schema in _PREFIXED:
            if t.startswith(pre) and len(t) > len(pre) and t not in silver:
                want[schema, t[len(pre):]] = t
    for s in LAYER_SCHEMAS:
        con.execute(f"create schema if not exists {s}")
    old = con.execute("select table_schema, table_name from information_schema.tables where table_type = 'VIEW' and table_schema in ('bronze', 'silver', 'gold')").fetchall()
    for s, v in old:
        if (s, v) not in want:
            con.execute(f'drop view if exists {s}."{v}"')
    for (s, v), real in want.items():
        con.execute(f'create or replace view {s}."{v}" as select * from main."{real}"')  # names come from the warehouse's own catalogue
    return len(want)


def refresh_aliases(plane) -> int:
    """After a plan run or a load: bring the layer views up to date (a separate turn on the warehouse, like any other reader)."""
    from sh_platform.v1 import wh
    with wh.connect(plane) as con:
        return alias_layers(con, {t["name"] for t in current(plane)["tables"]})


def _warehouse(plane) -> Path:
    return plane.path("warehouse", "evidence.duckdb")


def apply(plane) -> dict:
    """Create or migrate the company warehouse to the approved current version (add tables and columns only)."""
    path = _warehouse(plane)
    with lock_for(path):
        res = _migrate(path, current(plane))
    _log(plane, "system", "warehouse updated", f"v{version_of(plane)}", f"{len(res['created_tables'])} tables, {len(res['added_columns'])} columns added")
    return {**res, "path": str(path)}


def _sandbox(plane, cat: dict) -> dict:
    """Apply the proposed DDL to a copy of the warehouse file (an empty one if there is none yet). Never touches the real file."""
    src = _warehouse(plane)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "evidence.duckdb"
        try:
            if src.exists():
                try:
                    shutil.copyfile(src, copy)
                except OSError:  # UC5: the running server holds the file open and Windows refuses a plain copy; copy it through DuckDB
                    from sh_platform.v1.b6_run import _fresh_sandbox
                    _fresh_sandbox(plane, copy)
            res = _migrate(copy, cat)
        except OSError:
            return {"ok": False, "message": "The warehouse file could not be copied for the check. Please try again."}
        except Refused as e:
            return {"ok": False, "message": e.message}
    return {"ok": True, "message": f"Tried on a copy of the warehouse: {len(res['created_tables'])} tables and {len(res['added_columns'])} columns would be added. It works."}


# ---- storage ----------------------------------------------------------------------------------------------------------------------

def _m(plane, *parts) -> Path:
    return plane.path("model", *parts)


def _read(path: Path, kind=dict):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        raise Refused(500, "The data model could not be read. Please try again.") from None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _log(plane, by: str, what: str, ref: str = "", note: str = "") -> None:
    path = _m(plane, "log.json")
    with lock_for(path):
        rows = _read(path, list) or []
        rows.append({"at": _now(), "by": by, "what": what, "ref": ref, "note": note})
        write_json_atomic(path, rows[-1000:])


def _write_version(plane, n: int, *, dbml: str, ext: dict, cat: dict, meta: dict) -> None:
    d = f"versions/{n}"
    write_json_atomic(_m(plane, d, "extension.json"), ext)
    write_json_atomic(_m(plane, d, "catalogue.json"), {**cat, "version": n})
    _write_text(_m(plane, d, "model.dbml"), dbml)
    write_json_atomic(_m(plane, d, "meta.json"), {"version": n, **meta})  # meta last: a version exists once its meta does


def _script(ext: dict) -> str:
    base = CORE_FILE.read_text(encoding="utf-8")
    if not ext["tables"]:
        return base
    return base + "\n\n// ---- Company extension (a block named after a core table lists only the columns added to it) ----\n" + _emit(ext["tables"], ext["refs"])


def _seed(plane) -> None:
    cur = _m(plane, "current.json")
    with lock_for(_m(plane, "log.json")):
        if _read(cur) is not None:
            return
        ext = {"tables": [], "refs": []}
        if _read(_m(plane, "versions", "1", "meta.json")) is None:
            _write_version(plane, 1, dbml=_script(ext), ext=ext, cat=_merge(_core(), ext),
                           meta={"state": "approved", "source": "core", "proposed_by": "Signal Harbor", "proposed_at": _now(),
                                 "approved_by": "Signal Harbor product release", "approved_at": _now(), "base_version": 0,
                                 "summary": "The core model that ships with the product."})
        write_json_atomic(cur, {"version": 1})
    _log(plane, "system", "core model seeded", "v1")


_reloaded: set[tuple] = set()


def reload_core(plane) -> int | None:
    """A product release that added core tables or columns reaches existing companies: the current version plus what the core now has that
    it lacks becomes a new approved version (add-only; the company extension is kept; nothing is dropped or changed). Returns the new
    version number, or None when the company already has everything."""
    key = (str(_m(plane, "current.json")), CORE_FILE.stat().st_mtime_ns)
    if key in _reloaded:
        return None
    with lock_for(_m(plane, "log.json")):
        cur_n = int(_read(_m(plane, "current.json"))["version"])
        cat, core = deepcopy(_cat(plane, cur_n)), _core()
        have = {t["name"]: t for t in cat["tables"]}
        added: list[str] = []
        for ct in core["tables"]:
            t = have.get(ct["name"])
            if t is None:
                cat["tables"].append(deepcopy(ct))
                added.append(ct["name"])
                continue
            names = {c["name"] for c in t["columns"]}
            for c in ct["columns"]:
                if c["name"] not in names:
                    t["columns"].append(deepcopy(c))
                    added.append(f"{ct['name']}.{c['name']}")
        rkey = lambda r: (r["from"]["table"], tuple(r["from"]["columns"]), r["to"]["table"], tuple(r["to"]["columns"]))
        seen = {rkey(r) for r in cat["refs"]}
        cat["refs"] += [r for r in core["refs"] if rkey(r) not in seen]
        if not added:
            _reloaded.add(key)
            return None
        ext = _read(_m(plane, "versions", str(cur_n), "extension.json")) or {"tables": [], "refs": []}
        n = max(m["version"] for m in _versions(plane)) + 1
        summary = "Product release: " + ", ".join(added[:8]) + (" and more" if len(added) > 8 else "") + " added to the core model."
        _write_version(plane, n, dbml=_script(ext), ext=ext, cat=cat,
                       meta={"state": "approved", "source": "core", "proposed_by": "Signal Harbor", "proposed_at": _now(),
                             "approved_by": "Signal Harbor product release", "approved_at": _now(), "base_version": cur_n, "summary": summary})
        for v in _versions(plane):  # only the old current is superseded; an open proposal stays and approve() asks for it to be proposed again
            if v["version"] == cur_n:
                write_json_atomic(_m(plane, "versions", str(v["version"]), "meta.json"), {**v, "state": "superseded", "superseded_by": n})
        write_json_atomic(_m(plane, "current.json"), {"version": n})
    _reloaded.add(key)
    _log(plane, "system", "core model reloaded", f"v{n}", summary)
    return n


def version_of(plane) -> int:
    _seed(plane)
    reload_core(plane)
    return int(_read(_m(plane, "current.json"))["version"])


def _cat(plane, n: int) -> dict:
    path = _m(plane, "versions", str(n), "catalogue.json")
    key = (str(path), path.stat().st_mtime_ns) if path.exists() else None
    if key and key in _cache:
        return _cache[key]
    cat = _read(path)
    if cat is None:
        raise Refused(404, "We could not find that version of the data model.")
    if key:
        _cache[key] = cat
    return cat


def current(plane) -> dict:
    """The approved current catalogue: {version, tables: [...], refs: [...]}. Agents and intake read only this."""
    return _cat(plane, version_of(plane))


def tables(plane) -> list[dict]:
    return [{"name": t["name"], "group": t["group"], "note": t["note"], "layer": t["layer"]} for t in current(plane)["tables"]]


def describe(plane, table: str) -> dict | None:
    cat = current(plane)
    t = next((t for t in cat["tables"] if t["name"] == table), None)
    if t is None:
        return None
    refs = [r for r in cat["refs"] if table in (r["from"]["table"], r["to"]["table"])]
    return {**deepcopy(t), "refs": refs}


def has_field(plane, table: str, field: str) -> bool:
    t = next((t for t in current(plane)["tables"] if t["name"] == table), None)
    return t is not None and any(c["name"] == field for c in t["columns"])


# ---- reading for the screen -----------------------------------------------------------------------------------------------------

def _versions(plane) -> list[dict]:
    _seed(plane)
    root = _m(plane, "versions")
    nums = sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit()) if root.exists() else []
    return [m for n in nums if (m := _read(_m(plane, "versions", str(n), "meta.json")))]


def versions(plane) -> list[dict]:
    cur = version_of(plane)
    return [{**m, "is_current": m["version"] == cur} for m in reversed(_versions(plane))]


def proposals(plane) -> list[dict]:
    return [m for m in versions(plane) if m["version"] > 1]


def catalogue_view(plane) -> dict:
    cat = current(plane)
    meta = next(m for m in _versions(plane) if m["version"] == cat["version"])
    groups: dict[str, list[dict]] = {}
    for t in cat["tables"]:
        groups.setdefault(t["group"] or "other", []).append(t)
    return {"version": cat["version"], "state": meta["state"], "approved_by": meta.get("approved_by"), "approved_at": meta.get("approved_at"),
            "groups": [{"name": g, "tables": ts} for g, ts in groups.items()], "layers": layers_view(plane)}


def script(plane, n: int | None = None) -> str:
    n = n or version_of(plane)
    path = _m(plane, "versions", str(int(n)), "model.dbml")
    if not path.exists():
        raise Refused(404, "We could not find that version of the data model.")
    return path.read_text(encoding="utf-8")


def proposal(plane, n: int) -> dict:
    m = next((m for m in _versions(plane) if m["version"] == n and n > 1), None)
    if m is None:
        raise Refused(404, "We could not find that proposal.")
    return m


# ---- change proposals -------------------------------------------------------------------------------------------------------------

def _who(viewer) -> tuple[str, str]:
    return viewer.name, str(viewer.account_id or viewer.name)


def _need(viewer, seat: str) -> None:
    if seat not in seat_of(viewer):
        raise Refused(403, REFUSAL[seat])


def _diff(old: dict, new: dict) -> dict:
    ot = {t["name"]: {c["name"]: c for c in t["columns"]} for t in old["tables"]}
    d = {"tables_added": [], "columns_added": [], "columns_changed": [], "tables_removed": [], "columns_removed": []}
    for t in new["tables"]:
        if t["name"] not in ot:
            d["tables_added"].append({"table": t["name"], "columns": len(t["columns"])})
            continue
        for c in t["columns"]:
            o = ot[t["name"]].get(c["name"])
            if o is None:
                d["columns_added"].append({"table": t["name"], "column": c["name"], "type": c["type"], "null": c["null"], "default": c.get("default")})
            elif (o["type"], o["null"]) != (c["type"], c["null"]):
                d["columns_changed"].append({"table": t["name"], "column": c["name"], "from": o["type"], "to": c["type"]})
    nt = {t["name"]: {c["name"] for c in t["columns"]} for t in new["tables"]}
    for tn, cols in ot.items():
        if tn not in nt:
            d["tables_removed"].append({"table": tn})
        else:
            d["columns_removed"] += [{"table": tn, "column": c} for c in cols if c not in nt[tn]]
    if not any(d.values()):
        raise Refused(400, "That makes no change to the current data model.")
    for a in d["columns_added"]:  # DuckDB cannot add a required column to a table that may already hold rows
        if not a["null"] and a["default"] is None:
            raise Refused(400, f"The new column {a['column']} on {a['table']} must be optional, or have a default value.")
    d["words"] = (
        [f"Adds the table {a['table']} with {a['columns']} column{'s' if a['columns'] != 1 else ''}." for a in d["tables_added"]]
        + [f"Adds the column {a['column']} ({a['type']}) to {a['table']}." for a in d["columns_added"]]
        + [f"Changes {a['column']} on {a['table']} from {a['from']} to {a['to']}." for a in d["columns_changed"]]
        + [f"Removes the table {a['table']} from the model (data already in the warehouse is kept)." for a in d["tables_removed"]]
        + [f"Removes the column {a['column']} from {a['table']} (data already in the warehouse is kept)." for a in d["columns_removed"]])
    return d


def _breaking(plane, d: dict) -> list[str]:
    """Sheet mappings (E0b records, data/<company>/model/mappings/*.json) that point at a field this change removes or retypes."""
    gone = {(r["table"], None) for r in d["tables_removed"]} | {(r["table"], r["column"]) for r in d["columns_removed"] + d["columns_changed"]}
    folder = _m(plane, "mappings")
    out: list[str] = []
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            m = read_json_strict(p, dict)
        except (OSError, ValueError):
            continue
        if not m or m.get("state") == "retired":
            continue
        for c in m.get("columns") or []:
            t, f = c.get("target_table"), c.get("target_field")
            if (t, None) in gone or (t, f) in gone:
                out.append(f"The sheet mapping for {m.get('file_pattern') or m.get('id') or p.stem} sends '{c.get('source') or c.get('source_column') or f}' to {t}.{f}, which this change removes or retypes.")
    return out


def propose(plane, viewer, *, dbml: str | None = None, add_table: dict | None = None, add_column: dict | None = None, note: str = "") -> dict:
    """Open a change proposal from an uploaded DBML extension, or from a small form (add_table / add_column)."""
    _need(viewer, DATA_ENGINEER)
    core = _core()
    core_names = {t["name"] for t in core["tables"]}
    cur_n = version_of(plane)
    ext_now = _read(_m(plane, "versions", str(cur_n), "extension.json"))
    if dbml is not None:
        new = _parse_extension(str(dbml), core)
        source = "upload"
    elif add_table or add_column:
        form = add_table or {**add_column, "columns": [add_column]}
        tname = str(form.get("name") if add_table else add_column.get("table") or "").strip()
        cols = [{"name": str(c.get("name") or "").strip(), "type": norm_type(c.get("type") or ""), "null": c.get("null") is not False, "pk": False,
                 "unique": False, "default": None, "note": str(c.get("note") or "").strip()} for c in (form.get("columns") or [])]
        if add_table:
            if tname in core_names or any(t["name"] == tname for t in ext_now["tables"]):
                raise Refused(400, f"There is already a table called {tname}.")
        elif tname not in core_names and not any(t["name"] == tname for t in ext_now["tables"]):
            raise Refused(404, f"There is no table called {tname}.")
        new = {"tables": [{"name": tname, "group": str(form.get("group") or "") if add_table else "", "note": str(form.get("note") or "") if add_table else "",
                           "layer": "company", "columns": cols, "indexes": []}], "refs": []}
        if add_column and any(t["name"] == tname for t in ext_now["tables"]):  # extension table: add to its own column list
            new["tables"][0]["columns"] = next(t for t in ext_now["tables"] if t["name"] == tname)["columns"] + cols
        source = "form"
    else:
        raise Refused(400, "Give a script to upload, or a table or column to add.")
    ext = _overlay(ext_now, new, core_names)
    cat = _merge(core, ext)
    diff = _diff(current(plane), cat)
    by, by_id = _who(viewer)
    meta = {"state": "proposed", "source": source, "proposed_by": by, "proposed_by_id": by_id, "proposed_at": _now(), "base_version": cur_n,
            "summary": " ".join(diff["words"])[:300], "note": str(note)[:500], "diff": diff, "breaking": _breaking(plane, diff), "sandbox": _sandbox(plane, cat)}
    with lock_for(_m(plane, "log.json")):
        n = max(m["version"] for m in _versions(plane)) + 1
        _write_version(plane, n, dbml=_script(ext), ext=ext, cat=cat, meta=meta)
    _log(plane, by, "proposed a change", f"v{n}", meta["summary"])
    return {"version": n, **meta}


def approve(plane, viewer, n: int) -> dict:
    """The head of data seat approves (ROLE1; the data engineer reads and proposes); never the person who proposed it. The sandbox runs again, then the warehouse is migrated and v<n> becomes current."""
    _need(viewer, HEAD_OF_DATA)
    by, by_id = _who(viewer)
    with lock_for(_m(plane, "log.json")):
        m = proposal(plane, n)
        if m["state"] != "proposed":
            raise Refused(409, "This proposal has already been answered.")
        if by_id == m["proposed_by_id"]:
            raise Refused(403, "You proposed this change, so someone else needs to approve it.")
        if m["base_version"] != version_of(plane):
            raise Refused(409, "The data model changed after this was proposed. Please propose it again.")
        cat = _cat(plane, n)
        box = _sandbox(plane, cat)
        if not box["ok"]:
            raise Refused(409, box["message"])
        with lock_for(_warehouse(plane)):
            _migrate(_warehouse(plane), cat)
        old = version_of(plane)
        for v in _versions(plane):  # the old current and any other open proposal built on it are superseded
            if v["version"] == old or (v["state"] == "proposed" and v["version"] != n):
                write_json_atomic(_m(plane, "versions", str(v["version"]), "meta.json"), {**v, "state": "superseded", "superseded_by": n})
        done = {**m, "state": "approved", "approved_by": by, "approved_by_id": by_id, "approved_at": _now(), "sandbox": box}
        write_json_atomic(_m(plane, "versions", str(n), "meta.json"), done)
        write_json_atomic(_m(plane, "current.json"), {"version": n})
    _log(plane, by, "approved a change", f"v{n}", m["summary"])
    return done


def reject(plane, viewer, n: int, reason: str) -> dict:
    _need(viewer, HEAD_OF_DATA)
    reason = str(reason or "").strip()
    if not reason:
        raise Refused(400, "Please say briefly why this is not right.")
    by, _ = _who(viewer)
    with lock_for(_m(plane, "log.json")):
        m = proposal(plane, n)
        if m["state"] != "proposed":
            raise Refused(409, "This proposal has already been answered.")
        done = {**m, "state": "rejected", "rejected_by": by, "rejected_at": _now(), "reason": reason[:500]}
        write_json_atomic(_m(plane, "versions", str(n), "meta.json"), done)
    _log(plane, by, "turned a change down", f"v{n}", reason[:200])
    return done


# ---- layers: bronze, silver, gold (card D1) ---------------------------------------------------------------------------------------
# silver = the current catalogue above (unchanged names). bronze and gold tables are recorded in data/<company>/model/layers.json:
# {tables: {name: {layer, source, layout, project_ids, project_slug, columns: [{name, type}], registered_at}}}.
# Bronze is registered by intake loads (E0c calls register_bronze); gold by the build pipeline once a plan is approved (register_gold).

_BRONZE, _SILVER, _GOLD = "bronze", "silver", "gold"
_PART = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def _layers_path(plane) -> Path:
    return _m(plane, "layers.json")


def _registry(plane) -> dict:
    return (_read(_layers_path(plane)) or {}).get("tables", {})


def slug_of(title: str) -> str:
    """A project title as a table-name part: lowercase letters, digits and underscores, at most 30 characters."""
    from sh_platform.v1.i6_chat import short_title  # V6: a long first sentence gives a short name for the tables too
    return re.sub(r"[^a-z0-9]+", "_", short_title(str(title)).lower()).strip("_")[:30].strip("_")


def _cols(columns) -> list[dict]:
    out = []
    for c in columns or []:
        n = str(c.get("name") or "").strip()
        if not _NAME.fullmatch(n):
            raise Refused(400, f"'{n}' is not a usable column name. Use lowercase letters, digits and underscores.")
        out.append({"name": n, "type": str(c.get("type") or "text").strip().lower()})
    return out


def _register(plane, name: str, entry: dict) -> dict:
    if name in {t["name"] for t in current(plane)["tables"]}:
        raise Refused(409, f"{name} is already a table of the data model.")
    path = _layers_path(plane)
    with lock_for(path):
        data = _read(path) or {"tables": {}}
        old = data["tables"].get(name)
        if old and (old["layer"], old.get("project_slug")) != (entry["layer"], entry.get("project_slug")):
            raise Refused(409, f"{name} is already recorded as a {old['layer']} table of another project.")
        entry["registered_at"] = old["registered_at"] if old else _now()
        entry["project_ids"] = sorted(set(old["project_ids"] if old else []) | set(entry["project_ids"]))
        entry["columns"] = entry["columns"] or (old["columns"] if old else [])
        data["tables"][name] = entry
        write_json_atomic(path, data)
    return {"name": name, **entry}


def register_bronze(plane, source_code: str, layout: str, columns=None, project_ids=()) -> dict:
    """Record bronze_<source_code>_<layout> (one table per source layout). Safe to call again: columns and projects are merged."""
    if not (_PART.fullmatch(str(source_code)) and _PART.fullmatch(str(layout))):
        raise Refused(400, "A source code and a layout use lowercase letters, digits and underscores.")
    name = f"bronze_{source_code}_{layout}"
    if not _NAME.fullmatch(name):
        raise Refused(400, f"{name} is too long to be a table name.")
    return _register(plane, name, {"layer": _BRONZE, "source": source_code, "layout": layout, "project_ids": list(project_ids),
                                   "project_slug": None, "columns": _cols(columns)})


def register_gold(plane, project_id: str, project_slug: str, name: str, columns=None) -> dict:
    """Record gold_<project_slug>_<name>, owned by one project. Called only once the project's plan is approved."""
    if not (_PART.fullmatch(str(project_slug)) and _PART.fullmatch(str(name)) and project_id):
        raise Refused(400, "A project, its short name and a table name are needed, in lowercase letters, digits and underscores.")
    full = f"gold_{project_slug}_{name}"
    if not _NAME.fullmatch(full):
        raise Refused(400, f"{full} is too long to be a table name.")
    return _register(plane, full, {"layer": _GOLD, "source": None, "layout": None, "project_ids": [project_id],
                                   "project_slug": project_slug, "columns": _cols(columns)})


def layer_of(plane, table: str) -> str | None:
    """'bronze', 'silver' or 'gold'; None for a table the catalogue does not know."""
    if (r := _registry(plane).get(table)):
        return r["layer"]
    return _SILVER if any(t["name"] == table for t in current(plane)["tables"]) else None


def tables_for_project(plane, project_id: str) -> dict:
    """{bronze: [...], silver: [...], gold: [...]} for one project: its gold tables, the bronze tables its sources land in, and all silver."""
    reg = _registry(plane)
    pick = lambda layer: sorted(n for n, r in reg.items() if r["layer"] == layer and project_id in r["project_ids"])
    return {_BRONZE: pick(_BRONZE), _SILVER: [t["name"] for t in current(plane)["tables"]], _GOLD: pick(_GOLD)}


def columns_of(plane, table: str) -> list[str] | None:
    """Column names of any catalogued table, whatever its layer (what a plan's SQL is checked against); None if unknown."""
    if (r := _registry(plane).get(table)):
        return [c["name"] for c in r["columns"]]
    t = next((t for t in current(plane)["tables"] if t["name"] == table), None)
    return [c["name"] for c in t["columns"]] if t else None


def layers_view(plane) -> dict:
    """For the Settings data model page: the three layers with their tables."""
    reg = _registry(plane)
    row = lambda n, r: {"name": n, "source": r["source"], "layout": r["layout"], "project_ids": r["project_ids"], "columns": len(r["columns"])}
    return {_BRONZE: [row(n, r) for n, r in sorted(reg.items()) if r["layer"] == _BRONZE],
            _SILVER: {"tables": len(current(plane)["tables"])},
            _GOLD: [row(n, r) for n, r in sorted(reg.items()) if r["layer"] == _GOLD]}


# the demo start: bronze for the three Evergreen feeds (seed_evergreen source codes); columns are learned when files load
DEMO_BRONZE = (("administrator", "export"), ("trading_export", "export"), ("manager_email", "statement"))


def seed_demo_bronze(plane) -> list[str]:
    return [register_bronze(plane, s, l)["name"] for s, l in DEMO_BRONZE]
