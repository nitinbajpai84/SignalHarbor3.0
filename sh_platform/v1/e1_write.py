"""E1b: the only writer of evidence rows. Append-only: there is no update or delete function here, on purpose.

A correction is a new row whose `supersedes_*_id` points at the row it replaces, with `recorded_at` = now.
"""
from __future__ import annotations

import logging
import uuid

from sh_platform.v1 import wh

log = logging.getLogger(__name__)

# What makes two rows "the same thing" across versions. Tables not listed are checked for the same table only.
SUBJECT = {
    "valuation_observations": ("instrument_id", "portfolio_id", "valuation_date"),
    "position_snapshots": ("portfolio_id", "instrument_id", "position_date", "view_type"),
    "nav_snapshots": ("portfolio_id", "nav_period_end"),
    "market_observations": ("series_key", "observed_at"),
    "transactions": ("external_trade_id",),
}


class WriteRefused(ValueError):
    """The row is not a valid append; the message says why."""


def org_id(plane) -> str:
    """organization_id for this company. The column is a UUID; a company id that is already one is used as is,
    a slug such as "acme" maps to a fixed UUID (uuid5), so every card computes the same value."""
    try:
        return str(uuid.UUID(plane.company_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{plane.company_id}.signal-harbor"))


def _columns(plane, con, table: str) -> list[str]:
    try:
        from sh_platform.v1 import e0a_catalogue
        d = e0a_catalogue.describe(plane, table)
        if d:
            return [c["name"] for c in d["columns"]]
    except ImportError:
        log.warning("e0a_catalogue missing; using the warehouse column list for %s", table)
    return [r[0] for r in con.execute(
        "select column_name from information_schema.columns where table_schema = 'main' and table_name = ? order by ordinal_position", [table]).fetchall()]


def _refs(plane, table: str) -> list[tuple[str, str, str]]:
    """(column, referenced table, referenced column) for the foreign keys this table declares (organization_id is checked separately)."""
    try:
        from sh_platform.v1 import e0a_catalogue
        d = e0a_catalogue.describe(plane, table)
    except ImportError:
        log.warning("e0a_catalogue missing; referenced ids are not checked for %s", table)
        return []
    return [(r["from"]["columns"][0], r["to"]["table"], r["to"]["columns"][0]) for r in (d or {}).get("refs", [])
            if r["from"]["table"] == table and r["from"]["columns"][0] != "organization_id"]


def _insert(plane, con, table: str, cols: list[str], row: dict, supersedes_id: str | None, replay: bool = False) -> str:
    row = dict(row)
    sup = next((c for c in cols if c.startswith("supersedes_")), None)
    if sup and row.get(sup) and supersedes_id and str(row[sup]) != str(supersedes_id):
        raise WriteRefused("supersedes_id and the row's own supersedes link name different rows")
    if supersedes_id is None and sup:
        supersedes_id = row.get(sup)
    if not cols:
        raise WriteRefused(f"unknown table: {table}")
    unknown = sorted(set(row) - set(cols))
    if unknown:
        raise WriteRefused(f"{table} has no column {', '.join(unknown)}")
    if row.get("organization_id", org_id(plane)) not in (org_id(plane), plane.company_id):
        raise WriteRefused("organization_id must be this company")
    if "organization_id" in cols:
        row["organization_id"] = org_id(plane)
    row.setdefault("id", wh.new_id())
    if "recorded_at" in cols:
        if replay:  # only a shadow-mode replay may say when a row was recorded
            row.setdefault("recorded_at", wh.now())
        else:
            row["recorded_at"] = wh.now()
    for col, ref_table, ref_col in _refs(plane, table):
        if row.get(col) is not None and col != sup and not con.execute(
                f"select 1 from {ref_table} where {ref_col} = ?", [row[col]]).fetchone():
            raise WriteRefused(f"{col} {row[col]} is not in this warehouse")
    if supersedes_id:
        if not sup:
            raise WriteRefused(f"{table} cannot supersede a row: it has no supersedes column")
        old = con.execute(f"select * from {table} where id = ?", [supersedes_id]).fetchone()
        if old is None:
            raise WriteRefused(f"{supersedes_id} is not a row of {table}")
        olds = dict(zip([d[0] for d in con.description], old))
        for k in SUBJECT.get(table, ()):  # a correction inherits the subject it corrects
            if row.get(k) is None:
                row[k] = olds.get(k)
        diff = [k for k in SUBJECT.get(table, ()) if str(row[k]) != str(olds.get(k))]
        if diff:
            raise WriteRefused(f"supersedes a row about a different subject ({', '.join(diff)})")
        if con.execute(f"select 1 from {table} where {sup} = ?", [supersedes_id]).fetchone():
            raise WriteRefused(f"{supersedes_id} is already superseded; supersede the latest row")
        row[sup] = supersedes_id
    names = list(row)
    con.execute(f"insert into {table} ({', '.join(names)}) values ({', '.join('?' * len(names))})", [row[n] for n in names])
    return row["id"]


def record(plane, table: str, row: dict, supersedes_id: str | None = None, replay: bool = False) -> str:
    return record_many(plane, table, [row], [supersedes_id], replay)[0]


def record_many(plane, table: str, rows: list[dict], supersedes_ids: list[str | None] | None = None, replay: bool = False) -> list[str]:
    """All rows or none: one transaction. `supersedes_ids` (optional) lines up with `rows`. `replay=True` (E6c only) keeps a
    caller-supplied recorded_at; otherwise recorded_at is always now, so a late file cannot look known before the cutoff.
    ponytail: check-then-insert; two concurrent corrections of one row can still fork (no unique constraint on supersedes_*_id)."""
    with wh.connect(plane) as con:
        cols = _columns(plane, con, table)
        con.execute("begin")
        try:
            ids = [_insert(plane, con, table, cols, r, (supersedes_ids or [None] * len(rows))[i], replay) for i, r in enumerate(rows)]
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
        return ids
