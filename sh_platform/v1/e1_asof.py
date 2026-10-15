"""E1a As-known-then queries over the append-only observation tables.

A row is current as at T when recorded_at <= T and no row that supersedes it has recorded_at <= T.
Supersession links alone define the subject, so the same code serves every table; `where` narrows the rows (equality on real columns only).
`cutoff` may be a datetime, an ISO string, or a date (a bare date means the end of that day, UTC); None means now.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from sh_platform.v1 import wh

SUPERSEDES = {
    "valuation_observations": "supersedes_valuation_id",
    "position_snapshots": "supersedes_position_id",
    "cash_movements": "supersedes_cash_movement_id",
    "nav_snapshots": "supersedes_nav_id",
    "commitments": "supersedes_commitment_id",
    "market_observations": "supersedes_observation_id",
    "transactions": "supersedes_transaction_id",
}


class AsOfError(ValueError):
    """A plain-language refusal (unknown table or column, bad cutoff)."""


def _cutoff(value) -> datetime:
    if value is None or value == "":
        return wh.now()
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00")) if "T" in value or " " in value.strip() else date.fromisoformat(value.strip())
        except ValueError:
            raise AsOfError("The cutoff is not a date or time we can read.") from None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.max, tzinfo=timezone.utc)
    raise AsOfError("The cutoff is not a date or time we can read.")


def _columns(con, table: str) -> list[str]:
    if table not in SUPERSEDES:
        raise AsOfError(f"We do not keep dated versions of '{table}'.")
    return [r[0] for r in con.execute("select column_name from information_schema.columns where table_schema = 'main' and table_name = ? order by ordinal_position", [table]).fetchall()]


def _rows(con, sql: str, params: list) -> list[dict]:
    import duckdb
    try:
        cur = con.execute(sql, params)
    except duckdb.ConversionException:   # an id or filter value of the wrong form ("nope" for a uuid) is the asker's mistake, not a crash
        raise AsOfError("That id or value is not in a form we can read.") from None
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _query(plane, table: str, where: dict | None, cutoff, one: bool, by: str = "recorded") -> list[dict]:
    at = _cutoff(cutoff)
    with wh.connect(plane, read_only=True) as con:
        cols = _columns(con, table)
        sup = SUPERSEDES[table]
        # one warehouse file per company, so no organization filter (organization_id is a uuid; company_id is a name)
        when = "coalesce(t.received_at, t.recorded_at)" if by == "received" and "received_at" in cols else "t.recorded_at"
        later = "coalesce(s.received_at, s.recorded_at)" if by == "received" and "received_at" in cols else "s.recorded_at"
        clauses, params = [f"{when} <= ?"], [at]
        for k, v in (where or {}).items():
            if k not in cols:
                raise AsOfError(f"'{table}' has no field '{k}'.")
            clauses.append(f"t.{k} is null" if v is None else f"t.{k} = ?")
            if v is not None:
                params.append(v)
        sql = (f"select t.* from {table} t where {' and '.join(clauses)} "
               f"and not exists (select 1 from {table} s where s.{sup} = t.id and {later} <= ?) "
               f"order by t.recorded_at desc, t.id" + (" limit 1" if one else ""))
        return _rows(con, sql, params + [at])


def snapshot(plane, table: str, where: dict, cutoff, by: str = "recorded") -> list[dict]:
    """Every current row matching `where` as known at `cutoff`, newest recorded first. `by="received"` (UC5): as the files had *arrived* by
    `cutoff` (a file loaded later but received before still counts); the default is as the warehouse had recorded it (the audit view)."""
    return _query(plane, table, where, cutoff, False, by)


def latest(plane, table: str, where: dict, cutoff) -> dict | None:
    """The most recently recorded current row matching `where` as known at `cutoff`. Ordered by recorded_at, not by the subject's own date:
    give the full subject; for "the latest valuation date" with a partial subject use `snapshot` and pick by date."""
    rows = _query(plane, table, where, cutoff, True)
    return rows[0] if rows else None


def chain(plane, table: str, row_id: str) -> list[dict]:
    """The whole supersession chain the row belongs to, oldest first (earlier versions, the row, later versions)."""
    with wh.connect(plane, read_only=True) as con:
        _columns(con, table)
        sup = SUPERSEDES[table]
        seen: dict[str, dict] = {}

        def get(where: str, val: str) -> list[dict]:
            return _rows(con, f"select * from {table} where {where} = ?", [val])

        todo = get("id", row_id)
        if not todo:
            return []
        while todo:
            r = todo.pop()
            if r["id"] in seen:
                continue
            seen[r["id"]] = r
            if r[sup]:
                todo += get("id", r[sup])
            todo += get(sup, r["id"])
        return sorted(seen.values(), key=lambda r: (r["recorded_at"], r["id"]))
