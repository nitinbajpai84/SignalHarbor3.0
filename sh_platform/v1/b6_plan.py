"""B2: the build plan of a project, its checks, its approval.

One JSON record per plan version at `data/<company>/build/<project_id>/plan-v<n>.json`:
  {project_id, version, sources: [{code, kind: structured|unstructured, files, owner}], model_changes: <E0a proposal number or null>,
   tables: [{name, layer: bronze|silver|gold, purpose, columns: [{name, type, from}], sql, depends_on}], lineage: [{from, to}],
   schedule: {freq, at, day}, state: draft|proposed|approved|rejected|built|live, proposed_by, approved_by, approved_at, reason, notes}
Bronze tables carry no SQL (an intake load fills them). Silver tables are existing core tables filled by one `insert ... select`.
Gold tables are `create table ... as select`. Every statement is parsed (sqlglot, DuckDB) and every table and column is checked against
the data model before the plan is saved; the program, not the writer, derives gold columns and the lineage.
Approval: the head of data seat, never the proposer; approving the plan also approves its linked E0a model change.
Every approval, rejection and state change is appended to `build/<pid>/log.jsonl`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1.i2_north import Refused
from sh_platform.v1.seats import HEAD_OF_DATA, REFUSAL, seat_of

STATES = ("draft", "proposed", "approved", "rejected", "built", "live")
NEXT = {"approved": {"built"}, "built": {"live", "built"}, "live": {"built", "live"}}  # moves other cards (the runner) may make
FREQ = ("daily", "weekly", "monthly", "on_arrival")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
_PID = re.compile(r"^prj-[0-9a-f]{8}$")
_BAD = (exp.Drop, exp.Delete, exp.Update, exp.Alter, exp.Command, exp.Merge, exp.TruncateTable, exp.Attach, exp.Copy)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def who(viewer) -> tuple[str, str]:
    return E._who(viewer)


# ---- records ---------------------------------------------------------------------------------------------------------------------

def folder(plane, pid: str):
    if not isinstance(pid, str) or not _PID.match(pid):
        raise Refused(404, "There is no such project.")
    d = plane.path("build", pid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def versions(plane, pid: str) -> list[int]:
    return sorted(int(m.group(1)) for p in folder(plane, pid).glob("plan-v*.json") if (m := re.fullmatch(r"plan-v(\d+)\.json", p.name)))


def get(plane, pid: str, version: int | None = None) -> dict | None:
    vs = versions(plane, pid)
    n = version or (vs[-1] if vs else None)
    if n is None or n not in vs:
        return None
    try:
        return read_json_strict(folder(plane, pid) / f"plan-v{n}.json", dict)
    except (OSError, ValueError):
        raise Refused(409, "The build plan cannot be read. Please try again.") from None


def _save(plane, plan: dict) -> dict:
    write_json_atomic(folder(plane, plan["project_id"]) / f"plan-v{plan['version']}.json", plan)
    return plan


def log(plane, pid: str, by: str, what: str, version: int | None = None, note: str = "") -> None:
    with lock_for(folder(plane, pid) / "log.jsonl"), open(folder(plane, pid) / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), "by": by, "what": what, "version": version, "note": note[:300]}) + "\n")


def read_log(plane, pid: str) -> list[dict]:
    p = folder(plane, pid) / "log.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def new_version(plane, pid: str, plan: dict, viewer, *, model_changes=None) -> dict:
    """Save `plan` as the next version, proposed by the viewer and waiting for the head of data. Checks it first."""
    by, by_id = who(viewer)
    with lock_for(folder(plane, pid)):
        vs = versions(plane, pid)
        plan = {**plan, "project_id": pid, "version": (vs[-1] if vs else 0) + 1, "state": "proposed", "proposed_by": by, "proposed_by_id": by_id,
                "proposed_at": now(), "approved_by": None, "approved_at": None, "reason": "",
                "model_changes": model_changes if model_changes is not None else plan.get("model_changes")}
        plan = validate(plane, plan)
        _save(plane, plan)
    log(plane, pid, by, "proposed a build plan", plan["version"], f"{len(plan['tables'])} tables")
    return plan


# ---- checks ----------------------------------------------------------------------------------------------------------------------

def _catalogue(plane, plan: dict) -> dict[str, dict[str, str]]:
    """{table: {column: type}} of the current data model, plus what the plan's linked model change would add."""
    cat = E.current(plane)
    n = plan.get("model_changes")
    if n:
        try:
            cat = E._cat(plane, int(n))
        except Exception:  # noqa: BLE001 - a missing proposal file is a plain refusal below, not a crash
            raise Refused(409, f"The model change {n} linked to this plan cannot be found.") from None
    return {t["name"]: {c["name"]: str(c["type"]).lower() for c in t["columns"]} for t in cat["tables"]}


def _out_type(sel, schema: dict, name: str, node) -> str:
    if isinstance(node, exp.Alias):
        node = node.this
    if isinstance(node, exp.Column):
        for t in sel.find_all(exp.Table):
            if t.alias_or_name == node.table or t.name == node.table:
                got = schema.get(t.name, {}).get(node.name)
                if got:
                    return got
        return "varchar"
    if isinstance(node, (exp.Sum, exp.Avg)):
        return "double"
    if isinstance(node, exp.Count):
        return "bigint"
    if isinstance(node, exp.Cast) and node.to is not None:  # V6B: a cast says its type (decimal(18,2), date, varchar), so a gold column is typed, not all varchar
        return node.to.sql(dialect="duckdb").lower().replace(", ", ",")
    return "date" if isinstance(node, exp.DateTrunc) and "date" in node.sql().lower() else "varchar"


@lru_cache(maxsize=1)
def _warehouse_functions() -> frozenset[str]:
    """Every function name the warehouse (DuckDB) knows, read from DuckDB itself."""
    import duckdb
    with duckdb.connect() as con:
        return frozenset(r[0].lower() for r in con.execute("select distinct function_name from duckdb_functions()").fetchall())


def _bind(name: str, sel, schema: dict[str, dict[str, str]]) -> None:
    """Bind the select in DuckDB against empty copies of the tables it reads. sqlglot's qualify sees every table of a FROM at once, so
    `join cash_movements cm on cm.portfolio_id = p.id` before `join portfolios p` passed it; DuckDB binds joins left to right and stopped the run
    on the copy (c2 ops_lead: Referenced table "p" not found; then: column "likely_cause" must appear in the GROUP BY clause; then: a literal
    'Entity B' compared with an id, Could not convert string 'Entity B' to INT128). With the model's types each table gets one row of nulls and the
    select runs, so a literal that cannot be cast shows. A binder or conversion error refuses; a type mismatch does not, as a gold table's column
    types here are the plan check's guess. Anything else is left to the run, which has the data."""
    import duckdb
    typed = True
    with duckdb.connect() as con:
        for t, cols in schema.items():
            body = ", ".join(f'"{c}" {ty}' for c, ty in cols.items())
            try:
                con.execute(f'create table "{t}" ({body})')
                con.execute(f'insert into "{t}" default values')
            except duckdb.Error:  # a type DuckDB does not know: text keeps the names bindable
                typed = False
                con.execute(f'drop table if exists "{t}"')
                con.execute(f'create table "{t}" ({", ".join(chr(34) + c + chr(34) + " varchar" for c in cols)})')
        try:
            con.execute(("" if typed else "explain ") + sel.sql(dialect="duckdb"))
        except (duckdb.BinderException, duckdb.ConversionException) as e:
            msg = " ".join(str(e).split())
            if isinstance(e, duckdb.ConversionException) or not re.search(r"No function matches|Cannot compare|cannot be cast|Cannot mix|type", msg, re.I):
                raise Refused(400, f"The SQL for {name} does not run in the warehouse (DuckDB): {msg[:300]}") from None
        except duckdb.Error:  # noqa: S110 - anything else (a type, a cast) is the run's to report with the data in hand
            pass


def _check_sql(table: dict, schema: dict, known: set[str]) -> tuple[list[dict], set[str]]:
    """Parse one table's SQL; return its output columns and the tables it reads. Refuses anything that is not a plain select into the table."""
    name, sql = table["name"], str(table.get("sql") or "").strip().rstrip(";")
    try:
        stmts = sqlglot.parse(sql, dialect="duckdb")
    except SqlglotError as e:
        raise Refused(400, f"The SQL for {name} could not be read: {str(e).splitlines()[0][:160]}") from None
    if len(stmts) != 1 or stmts[0] is None:
        raise Refused(400, f"The SQL for {name} must be exactly one statement.")
    st = stmts[0]
    if st.find(*_BAD) is not None or not isinstance(st, (exp.Create, exp.Insert)):
        raise Refused(400, f"The SQL for {name} may only create a table from a select or insert from a select. It cannot drop, delete or update.")
    sel = st.expression
    unknown = sorted({f.name for f in st.find_all(exp.Anonymous) if f.name.lower() not in _warehouse_functions()})
    if unknown:  # c1 fund_accountant: Postgres's uuid_generate_v4() passed this check and stopped the run on the copy
        raise Refused(400, f"The SQL for {name} calls {', '.join(unknown)}, which the warehouse (DuckDB) does not have. Use a DuckDB function instead.")
    if isinstance(st, exp.Create) and (str(st.args.get("kind")).upper() != "TABLE" or not isinstance(sel, exp.Query)):
        raise Refused(400, f"The SQL for {name} must be create table as select.")
    if isinstance(st, exp.Insert) and not isinstance(sel, exp.Query):
        raise Refused(400, f"The SQL for {name} must insert from a select.")
    target = st.this.this if isinstance(st.this, exp.Schema) else st.this
    if getattr(target, "name", "") != name:
        raise Refused(400, f"The SQL for {name} writes to a different table ({getattr(target, 'name', '?')}).")
    ctes = {c.alias for c in sel.find_all(exp.CTE)}
    reads = {t.name for t in sel.find_all(exp.Table) if t.name not in ctes}
    for r in sorted(reads):
        if r not in schema:
            raise Refused(400, f"{name} reads {r}, which is not in the data model or earlier in this plan.")
        if r not in table["depends_on"]:
            raise Refused(400, f"{name} reads {r} but does not list it under depends_on.")
    try:
        q = qualify(sel.copy(), schema={t: schema[t] for t in reads}, dialect="duckdb", validate_qualify_columns=True)
    except SqlglotError as e:
        has = "; ".join(f"{t} has {', '.join(list(schema[t])[:25])}" for t in sorted(reads))[:700]  # SPAN-CH2-02: the next draft can be right
        raise Refused(400, f"The SQL for {name} uses a column that is not in the data model: {str(e).splitlines()[0][:160]}. {has}.") from None
    _bind(name, sel, {t: schema[t] for t in reads})
    first = q if isinstance(q, exp.Select) else q.find(exp.Select)
    cols = [{"name": n, "type": _out_type(first, schema, n, p), "from": ", ".join(sorted({f"{c.table}.{c.name}" for c in p.find_all(exp.Column)}))}
            for n, p in zip(q.named_selects, first.expressions)]
    if isinstance(st, exp.Insert):
        want = [c.name for c in st.this.expressions] if isinstance(st.this, exp.Schema) else []
        miss = [c for c in want if c not in schema.get(name, {})]
        if miss:
            raise Refused(400, f"{name} has no column {', '.join(miss)} in the data model.")
        if want and len(want) != len(cols):
            raise Refused(400, f"The insert into {name} lists {len(want)} columns but selects {len(cols)}.")
    return cols, reads


def validate(plane, plan: dict, new: set[str] | frozenset = frozenset()) -> dict:
    """Check a whole plan and return it with program-derived gold columns and lineage. Raises Refused with the first plain problem.
    `new`: names of tables being added now (a chat draft); they also must read a table and read every table they depend on (SS-6). Tables
    already in a saved plan are not held to that, so an approved plan never fails a later check."""
    schema = _catalogue(plane, plan)
    core = set(schema)
    tables = [dict(t, depends_on=list(t.get("depends_on") or [])) for t in plan.get("tables") or []]
    if not tables:
        raise Refused(400, "The plan has no tables.")
    names = [t["name"] for t in tables]
    if len(set(names)) != len(names):
        raise Refused(400, "Two tables in the plan have the same name.")
    for t in tables:
        if not _NAME.fullmatch(str(t.get("name") or "")):
            raise Refused(400, f"'{t.get('name')}' is not a usable table name. Use lowercase letters, digits and underscores.")
        want = {"bronze": "bronze_", "gold": "gold_"}.get(t.get("layer"))
        if t.get("layer") not in ("bronze", "silver", "gold") or (want and not t["name"].startswith(want)):
            raise Refused(400, f"{t['name']} is on the wrong layer or has the wrong name for it (bronze_..., gold_...).")
        if t["layer"] == "silver" and t["name"] not in core:
            raise Refused(400, f"{t['name']} is not a table in the data model. A new table needs a model change first.")
        if t["layer"] == "bronze" and (t.get("sql") or t["depends_on"]):
            raise Refused(400, f"{t['name']} is raw data landed by intake; it has no SQL and depends on nothing.")
    done: dict[str, dict] = {}
    pending = list(tables)
    plan_schema = dict(schema)
    for t in tables:  # raw tables first: their columns are declared, not derived
        if t["layer"] == "bronze":
            plan_schema[t["name"]] = {c["name"]: str(c.get("type") or "varchar").lower() for c in t.get("columns") or []}
            if not plan_schema[t["name"]]:
                raise Refused(400, f"{t['name']} lists no columns.")
            done[t["name"]] = t
    pending = [t for t in tables if t["name"] not in done]
    while pending:
        ready = [t for t in pending if all(d in done or (d in core and d not in names) for d in t["depends_on"])]
        if not ready:
            raise Refused(400, "The tables depend on each other in a circle, or on a table that does not exist: " + ", ".join(t["name"] for t in pending))
        for t in ready:
            if t["name"] in t["depends_on"]:
                raise Refused(400, f"{t['name']} reads itself.")
            if not str(t.get("sql") or "").strip():
                raise Refused(400, f"{t['name']} has no SQL.")
            scope = {k: v for k, v in plan_schema.items() if k != t["name"] or t["layer"] == "silver"}
            cols, reads = _check_sql(t, scope, set(scope))
            if t["name"] in new and t["layer"] == "gold" and not reads:  # SS-6: values typed into the SQL are not a table built from the data
                raise Refused(400, f"{t['name']} reads no table. A gold table is built from the data model's tables, never from values written into the SQL.")
            if t["name"] in new and (unread := [d for d in t["depends_on"] if d not in reads]):
                raise Refused(400, f"{t['name']} lists {', '.join(unread)} under depends_on but never reads it.")
            if t["layer"] == "gold":
                t["columns"] = cols
                plan_schema[t["name"]] = {c["name"]: c["type"] for c in cols}
            else:
                t["columns"] = [{"name": c["name"], "type": c["type"], "from": c["from"]} for c in cols]
            done[t["name"]] = t
        pending = [t for t in pending if t["name"] not in done]
    sc = plan.get("schedule") or {}
    if sc.get("freq", "daily") not in FREQ:
        raise Refused(400, "The schedule must be daily, weekly, monthly or on arrival.")
    lineage = _intake_edges(plan, tables, core) + [{"from": d, "to": t["name"]} for t in tables for d in t["depends_on"]]
    return {**plan, "tables": tables, "lineage": lineage, "schedule": {"freq": sc.get("freq", "daily"), "at": sc.get("at", "06:00"), "day": sc.get("day")}}


def _intake_edges(plan: dict, tables: list[dict], core: set[str]) -> list[dict]:
    """Bronze -> silver edges the plan states for core silver tables it does not rebuild (intake fills them, so no SQL shows the link).
    Kept only when the catalogue agrees: `from` is a bronze table of this plan, `to` a table of the data model outside the plan."""
    bronze = {t["name"] for t in tables if t["layer"] == "bronze"}
    planned = {t["name"] for t in tables}
    out = []
    for e in plan.get("lineage") or []:
        a, b = e.get("from"), e.get("to")
        if a in bronze and b in core and b not in planned and {"from": a, "to": b} not in out:
            out.append({"from": a, "to": b})
    return out


def upstream(plan: dict, table: str) -> set[str]:
    """Every table that feeds `table`, through the plan's lineage and its depends_on: gold -> silver -> bronze."""
    edges = [(e["from"], e["to"]) for e in plan.get("lineage") or []]
    edges += [(d, t["name"]) for t in plan.get("tables") or [] for d in t.get("depends_on") or []]
    seen: set[str] = set()
    todo = [table]
    while todo:
        n = todo.pop()
        for a, b in edges:
            if b == n and a not in seen:
                seen.add(a)
                todo.append(a)
    return seen


# ---- approval and states -----------------------------------------------------------------------------------------------------------

def _linked(plane, plan: dict) -> dict | None:
    n = plan.get("model_changes")
    return E.proposal(plane, int(n)) if n else None


def _need_head(viewer) -> None:
    if HEAD_OF_DATA not in seat_of(viewer):
        raise Refused(403, REFUSAL[HEAD_OF_DATA])


def approve(plane, viewer, pid: str, version: int | None = None, note: str = "") -> dict:
    """The head of data approves the plan and, in the same step, its linked model change. Never the proposer. An optional note (design C2) stays with the approval."""
    _need_head(viewer)
    by, by_id = who(viewer)
    with lock_for(folder(plane, pid)):
        plan = get(plane, pid, version)
        if plan is None:
            raise Refused(404, "There is no build plan to approve.")
        if plan["state"] != "proposed":
            raise Refused(409, f"This plan is {plan['state']}, so it cannot be approved now.")
        if by_id == plan.get("proposed_by_id"):
            raise Refused(403, "You proposed this plan, so someone else needs to approve it.")
        plan = validate(plane, plan)  # the model may have moved since it was proposed
        m = _linked(plane, plan)
        if m and m["state"] == "proposed":
            E.approve(plane, viewer, int(plan["model_changes"]))  # refuses when it cannot be approved; the plan then stays proposed
        elif m and m["state"] != "approved":
            raise Refused(409, f"The model change linked to this plan is {m['state']}. Please propose the plan again.")
        _register(plane, plan)
        note = " ".join(str(note or "").split())[:300]
        plan.update(state="approved", approved_by=by, approved_at=now(), reason="", **({"approval_note": note} if note else {}))
        _save(plane, plan)
    log(plane, pid, by, "approved the build plan" + (" and its model change" if m else ""), plan["version"], note)
    try:
        from sh_platform.v1 import p1_project as P1
        P1.set_stage(plane, pid, "designed")
    except Exception:  # noqa: BLE001 - the stage label is a convenience; the approval stands
        pass
    return plan


def _register(plane, plan: dict) -> None:
    """Tell the catalogue (D1) about the plan's bronze and gold tables. Only called on approval; D1 does not check it."""
    pid, slug = plan["project_id"], plan.get("project_slug") or E.slug_of(plan["project_id"])
    for t in plan["tables"]:
        cols = [{"name": c["name"], "type": c["type"]} for c in t["columns"]]
        if t["layer"] == "bronze" and t.get("source") and t.get("layout"):
            E.register_bronze(plane, t["source"], t["layout"], cols, [pid])
        elif t["layer"] == "gold":
            E.register_gold(plane, pid, slug, t["name"][len(f"gold_{slug}_"):], cols)


def reject(plane, viewer, pid: str, reason: str, version: int | None = None) -> dict:
    _need_head(viewer)
    reason = str(reason or "").strip()
    if not reason:
        raise Refused(400, "Please say briefly why this plan is not right.")
    by, _ = who(viewer)
    with lock_for(folder(plane, pid)):
        plan = get(plane, pid, version)
        if plan is None or plan["state"] != "proposed":
            raise Refused(409, "Only a plan waiting for approval can be sent back.")
        m = _linked(plane, plan)
        if m and m["state"] == "proposed":
            E.reject(plane, viewer, int(plan["model_changes"]), reason)
        plan.update(state="rejected", reason=reason[:500], approved_by=None, approved_at=None)
        _save(plane, plan)
    log(plane, pid, by, "sent the build plan back", plan["version"], reason)
    return plan


def set_state(plane, pid: str, state: str, by: str, version: int | None = None) -> dict:
    """For the pipeline runner: approved -> built -> live. Nothing else may move a plan this way."""
    with lock_for(folder(plane, pid)):
        plan = get(plane, pid, version)
        if plan is None or state not in NEXT.get(plan["state"], set()):
            raise Refused(409, f"A plan that is {plan['state'] if plan else 'missing'} cannot become {state}.")
        plan["state"] = state
        _save(plane, plan)
    log(plane, pid, by, f"plan is now {state}", plan["version"])
    return plan


def set_schedule(plane, pid: str, schedule: dict, by: str, version: int | None = None) -> dict:
    """The schedule can change on an approved or live plan without a new approval; it is logged."""
    with lock_for(folder(plane, pid)):
        plan = get(plane, pid, version)
        if plan is None or plan["state"] not in ("approved", "built", "live"):
            raise Refused(409, "Only an approved plan can be scheduled.")
        plan["schedule"] = validate(plane, {**plan, "schedule": {**plan["schedule"], **schedule}})["schedule"]
        _save(plane, plan)
    log(plane, pid, by, "changed the schedule", plan["version"], json.dumps(plan["schedule"]))
    return plan
