"""SF07: the runner's silver and gold SQL, written for the warehouse the company named. DuckDB text from the same builders the runner uses
(transforms.build_silver and build_mart, recorded and not executed), then sqlglot transpile. A draft only: nothing connects anywhere
and no model is called. Names of changed constructs are function and type names, never a literal from the SQL."""
import logging
import re

import duckdb
import sqlglot
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlglot import exp

from sh_platform import build_env
from sh_platform.build import contracts, runner, transforms
from sh_platform.profile import store
from sh_platform.profile.api import _plane
from sh_platform.warehouse import _file

log = logging.getLogger(__name__)
router = APIRouter()
# One place: words in the stated answer -> sqlglot dialect. First hit wins. ponytail: substring match, no fuzzy spelling.
DIALECTS = {"snowflake": "snowflake", "bigquery": "bigquery", "big query": "bigquery", "redshift": "redshift", "databricks": "databricks",
            "spark": "spark", "synapse": "tsql", "sql server": "tsql", "postgres": "postgres", "mysql": "mysql", "trino": "trino",
            "clickhouse": "clickhouse", "oracle": "oracle", "duckdb": "duckdb"}
_HEAD = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]*(?=\()")


class _Recorder:
    """A connection stand-in: selects run on the real (read-only) connection; anything that writes is recorded and not run."""
    def __init__(self, con):
        self.con, self.sql = con, []

    def execute(self, sql, params=None):
        low = sql.lstrip().lower()
        if "information_schema.tables" in low and "'gold'" in low:  # always show the first build: a plain create
            return duckdb.connect(":memory:").execute("select 0")
        if low.startswith("select"):
            return self.con.execute(sql, params) if params else self.con.execute(sql)
        self.sql.append(sql)
        return duckdb.connect(":memory:").execute("select 0")


def target(plane) -> str | None:
    """The stated answer to warehouse_target, or None. A guess never counts."""
    q = next((x for x in build_env.read(plane, store.raw(plane))["questions"] if x["key"] == "warehouse_target"), None)
    a = q["answer"] if q else {}
    return str(a["value"]).strip() if a.get("mark") == "stated" and a.get("value") else None


def dialect_of(answer: str) -> str | None:
    low = answer.lower()
    return next((d for w, d in DIALECTS.items() if w in low), None)


def duckdb_statements(plane) -> list[dict]:
    """[{name, source, sql}] in DuckDB text, per source with a bronze table in the read-only copy; none when nothing has landed yet."""
    try:
        con = duckdb.connect(str(_file(plane, "company.readonly.duckdb")), read_only=True)
    except duckdb.Error:
        return []
    bp = contracts._read(plane, "build", "blueprint.json")
    out = []
    try:
        for c in contracts.derive(plane):
            src = c["source"]
            if not con.execute("select count(*) from information_schema.tables where table_schema = 'bronze' and table_name = ?", [src]).fetchone()[0]:
                continue
            rec = _Recorder(con)
            typed = transforms.build_silver(rec, src)
            out.append({"name": f"{src}: silver", "source": src, "sql": rec.sql[-1]})
            tables, restricted, _ = runner._marts(bp, src)
            for t, ms in tables.items():
                n = len(rec.sql)
                if transforms.build_mart(rec, src, t, ms, typed, "r" if t in restricted else "") and len(rec.sql) > n:
                    out.append({"name": f"{src}: gold.{t}", "source": src, "sql": rec.sql[-1]})
    finally:
        con.close()
    return out


def _head(node: exp.Expression, dialect: str) -> str:
    if isinstance(node, exp.DataType):
        return node.sql(dialect=dialect).upper()
    m = _HEAD.match(node.sql(dialect=dialect))
    return m[0].strip().upper() if m else ""


def changed_constructs(sql: str, dialect: str) -> list[str]:
    """Function and type names that read differently in the target, as 'duckdb name to target name'. Names only, never a literal."""
    out = set()
    for n in sqlglot.parse_one(sql, read="duckdb").find_all(exp.Func, exp.DataType):
        a, b = _head(n, "duckdb"), _head(n, dialect)
        if a and b and a != b:
            out.add(f"{a.lower()} to {b.lower()}")
    return sorted(out)


def build(plane) -> dict:
    """state: none (no stated target), unsupported, empty (nothing landed yet), failed (names the statement) or ready."""
    ans = target(plane)
    if not ans:
        return {"state": "none", "target": None, "statements": [], "message": "No warehouse target has been stated, so there is nothing to translate."}
    d = dialect_of(ans)
    if not d:
        return {"state": "unsupported", "target": ans, "statements": [], "message": f"Not available yet: Span and Flow cannot write SQL for {ans} yet."}
    stmts, done = duckdb_statements(plane), []
    if not stmts:
        return {"state": "empty", "target": ans, "dialect": d, "statements": [], "message": "Nothing has landed yet, so there is no SQL to translate."}
    for s in stmts:
        try:
            sql = sqlglot.transpile(s["sql"], read="duckdb", write=d, pretty=True)[0]
            done.append({"name": s["name"], "source": s["source"], "sql": sql, "changed_constructs": changed_constructs(s["sql"], d)})
        except sqlglot.errors.SqlglotError:
            log.warning("dialect %s failed on %s", d, s["name"])
            return {"state": "failed", "target": ans, "dialect": d, "statements": done, "failed": s["name"],
                    "message": f"{s['name']} could not be written for {ans}. The statements before it are shown."}
    return {"state": "ready", "target": ans, "dialect": d, "statements": done, "message": "A draft for your warehouse. Nothing has been run there."}


def as_text(doc: dict) -> str:
    head = f"-- DRAFT. SQL for {doc['target']} ({doc['dialect']}), written from the built-in runner. Nothing has been run in your warehouse. Check before use.\n"
    return head + "\n".join(f"\n-- {s['name']}\n{s['sql'].rstrip(';')};" for s in doc["statements"]) + "\n"


@router.get("/api/company/build/dialect")
def get_dialect(request: Request):
    return build(_plane(request))


@router.get("/api/company/build/dialect/download")
def download(request: Request):
    doc = build(_plane(request))
    if doc["state"] != "ready":
        return JSONResponse({"error": "not_ready", "message": doc["message"]}, status_code=409)
    return PlainTextResponse(as_text(doc), headers={"Content-Disposition": 'attachment; filename="warehouse-sql-draft.sql"'})
