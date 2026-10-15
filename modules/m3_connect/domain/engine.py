"""The rule engine (M3-P03): runs one rule (SHARED.md, "Rules Lens compiles") over rows already on this machine. Pure stdlib, Decimal arithmetic.

A node is {op, column, filters, period, group_by, ...} or a combination {op: ratio, numerator, denominator, scale} / {op: difference, left, right}.
ops: sum avg count min max latest first (leaf), ratio, difference (combine). A leaf may carry `group_by` (a column or list) with `pick: max|min`
(the figure is the biggest/smallest group) and `having` (count only the groups whose newest `column` is older than N business days
before the newest of all). `column` may be "a - b + c" (a row with an empty part is left out and counted).
Filters: eq ne in between not_null not_contains (the text does not hold the words: "A or B" is two owners), not_in_column (the row's value is not
among the values another column holds: a notice that was replaced) and listed_in (the row's value is among the `value` column of another source's
rows, those with a `where` column filled when it is given: the funds that have a benchmark in the manager list).
An empty cell is never zero: it is left out and counted in `skipped` (by column). A figure that cannot be worked out raises Cannot with the reason.
Per-group output keeps only groups of MIN_GROUP or more; the rest are counted, never shown.
"""
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

MIN_GROUP = 5
LEAF = ("sum", "avg", "count", "min", "max", "latest", "first")
COMBINE = ("ratio", "difference")
FILTER_OPS = ("eq", "ne", "in", "between", "not_null", "not_in_column", "not_contains", "listed_in")
_SPLIT = re.compile(r"\s+([+-])\s+")


class Cannot(Exception):
    """The figure cannot be worked out; the message says what is missing, in plain words."""


def empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def num(v) -> Decimal | None:
    if empty(v) or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v).replace(",", "").strip())
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def terms(column: str) -> list[tuple[int, str]]:
    """"a - b + c" -> [(1, a), (-1, b), (1, c)]."""
    t = _SPLIT.split(column.strip())
    return [(1, t[0])] + [(1 if t[i] == "+" else -1, t[i + 1]) for i in range(1, len(t) - 1, 2)]


def label(column: str) -> str:
    return column.replace("_", " ")


def joined(node: dict) -> list[dict]:
    """The listed_in filters of a leaf: each reads another source."""
    return [f for f in node.get("filters") or [] if f.get("op") == "listed_in"]


def sources_of(node: dict) -> set[str]:
    """Every source a leaf reads: its own, and the ones its listed_in filters name."""
    return {str(node.get("source") or "")} | {str(f.get("source") or "") for f in joined(node)}


def columns_of(node: dict, others: bool = False) -> set[str]:
    """Every column a node reads in its own source, so a rule can be checked against the columns that exist. `others` adds the columns it reads in
    another source through listed_in (for who may see what)."""
    if node.get("op") in COMBINE:
        return set().union(*(columns_of(node[k], others) for k in ("numerator", "denominator", "left", "right") if isinstance(node.get(k), dict)))
    cols = {t for _, t in terms(node["column"])} if node.get("column") else set()
    cols |= {f["column"] for f in node.get("filters") or []}
    cols |= {f["value"] for f in node.get("filters") or [] if f.get("op") == "not_in_column"}
    p = node.get("period") or {}
    cols |= {p["column"]} if p.get("column") else set()
    g = node.get("group_by")
    cols |= set([g] if isinstance(g, str) else g or [])
    cols |= {node["order_by"]} if node.get("order_by") else set()
    cols |= {node["having"]["column"]} if node.get("having") else set()
    if others:
        cols |= {c for f in joined(node) for c in (f.get("value"), f.get("where")) if c}
    return cols


def leaves(node: dict):
    if node.get("op") in COMBINE:
        for k in ("numerator", "denominator", "left", "right"):
            if isinstance(node.get(k), dict):
                yield from leaves(node[k])
    else:
        yield node


def _cmp(a, b) -> int:
    x, y = num(a), num(b)
    x, y = (x, y) if x is not None and y is not None else (str(a), str(b))
    return (x > y) - (x < y)


def _keep(row: dict, f: dict, rows: list[dict]) -> bool:
    v, op = row.get(f["column"]), f["op"]
    if op == "not_null":
        return not empty(v)
    if op == "not_in_column":
        return empty(v) or v not in {r.get(f["value"]) for r in rows if not empty(r.get(f["value"]))}
    if empty(v):
        return False
    if op == "not_contains":
        return str(f["value"]).lower() not in str(v).lower()
    if op == "eq":
        return _cmp(v, f["value"]) == 0
    if op == "ne":
        return _cmp(v, f["value"]) != 0
    if op == "in":
        return any(_cmp(v, x) == 0 for x in f["value"])
    lo, hi = f["value"]
    return _cmp(v, lo) >= 0 and _cmp(v, hi) <= 0


def bdays_before(d: date, n: int) -> date:
    while n:
        d -= timedelta(1)
        n -= d.weekday() < 5
    return d


def day_words(iso: str) -> str:
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day} {d.strftime('%b')}"


def _agg(op: str, vals: list[Decimal]) -> Decimal:
    if op == "sum":
        return sum(vals, Decimal(0))
    if op == "avg":
        return sum(vals, Decimal(0)) / len(vals)
    return (min if op == "min" else max)(vals)


class Run:
    """One run of one rule: `rows(source)` gives a source's rows (None when nothing arrived); `period_end` fills a period's "benchmark_end"."""

    def __init__(self, rows, source: str = "", period_end: str | None = None, drop_deduction: bool = False):
        self.rows, self.source, self.period_end, self.drop = rows, source, period_end, drop_deduction
        self.skipped: dict[str, int] = {}
        self.seen = 0
        self.groups: list[dict] = []   # per-group output that may be shown (groups of MIN_GROUP or more)
        self.suppressed = 0            # groups left out of it for being too small
        self.picked_size: int | None = None  # rows in the group a `pick` chose (its figure is the answer, so it may be too small to show)

    def _skip(self, col: str, n: int = 1) -> None:
        self.skipped[col] = self.skipped.get(col, 0) + n

    def value(self, node: dict) -> Decimal:
        op = node.get("op")
        if op == "ratio":
            n, d = self.value(node["numerator"]), self.value(node["denominator"])
            if d == 0:
                raise Cannot("The figure it is divided by is zero.")
            scale = node.get("scale", 1)
            if isinstance(scale, bool) or scale not in (1, 100):
                raise Cannot("The rule's scale is not one Lens can use.")
            return n / d * Decimal(scale)
        if op == "difference":
            right = Decimal(0) if self.drop and node.get("deduction") else self.value(node["right"])
            return self.value(node["left"]) - right
        if op not in LEAF:
            raise Cannot("The rule uses an operation Lens cannot run.")
        return self._leaf(node)

    def _scope(self, node: dict) -> list[dict]:
        rows = self.rows(node.get("source") or self.source)
        if rows is None:
            raise Cannot("No data has arrived for this measure yet.")
        allrows = rows
        for f in node.get("filters") or []:
            rows = self._listed(rows, f) if f["op"] == "listed_in" else [r for r in rows if _keep(r, f, allrows)]
        p = node.get("period") or {}
        if p.get("column"):
            to = self.period_end if p.get("to") == "benchmark_end" else p.get("to")
            dates = [str(r[p["column"]])[:10] for r in rows if not empty(r.get(p["column"]))]
            if p.get("strict") and to and (not dates or max(dates) < to):
                what = node.get("label") or label(p["column"])
                raise Cannot(f"{what} missing after {day_words(max(dates))}" if dates else f"{what} missing")
            start = (self.period_end or "")[:8] + "01" if p.get("from") == "benchmark_start" and self.period_end else \
                None if p.get("from") == "benchmark_start" else p.get("from")
            rows = [r for r in rows if not empty(r.get(p["column"]))
                    and (not start or str(r[p["column"]])[:10] >= start) and (not to or str(r[p["column"]])[:10] <= to)]
        return rows

    def _listed(self, rows: list[dict], f: dict) -> list[dict]:
        other = self.rows(f.get("source") or "")
        if other is None:
            raise Cannot(f"The list of {label(f['value'])} has not arrived yet.")
        allowed = {str(r[f["value"]]).strip().lower() for r in other if not empty(r.get(f["value"])) and (not f.get("where") or not empty(r.get(f["where"])))}
        return [r for r in rows if not empty(r.get(f["column"])) and str(r[f["column"]]).strip().lower() in allowed]

    def _cell(self, row: dict, column: str) -> Decimal | None:
        total = Decimal(0)
        for sign, c in terms(column):
            v = num(row.get(c))
            if v is None:
                self._skip(c)
                return None
            total += sign * v
        return total

    def _leaf(self, node: dict) -> Decimal:
        op, col = node["op"], node.get("column") or ""
        rows = self._scope(node)
        self.seen = max(self.seen, len(rows))
        gb = node.get("group_by")
        gb = [gb] if isinstance(gb, str) else list(gb or [])
        if op == "count":
            return self._count(node, rows, gb)
        if op in ("latest", "first"):
            by = node.get("order_by") or (node.get("period") or {}).get("column")
            if not by:
                raise Cannot("The rule does not say which column orders the rows.")
            ordered = [(str(r[by]), v) for r in rows if not empty(r.get(by)) and (v := self._cell(r, col)) is not None]
            if not ordered:
                raise Cannot(f"There is no {label(col)} to read.")
            return (max if op == "latest" else min)(ordered, key=lambda x: x[0])[1]
        cells = [(r, v) for r in rows if (v := self._cell(r, col)) is not None]
        if not cells:
            raise Cannot(f"There is nothing in {label(col)} to work from.")
        if gb:
            groups: dict[tuple, list[Decimal]] = {}
            for r, v in cells:
                groups.setdefault(tuple(r.get(g) for g in gb), []).append(v)
            figs = {k: _agg(op, v) for k, v in groups.items()}
            self.groups = [{"group": list(k), "value": float(figs[k]), "group_size": len(groups[k])} for k in figs if len(groups[k]) >= MIN_GROUP]
            self.suppressed = sum(len(v) < MIN_GROUP for v in groups.values())
            best = (max if node.get("pick", "max") == "max" else min)(figs, key=figs.get)
            self.picked_size = len(groups[best])
            return figs[best]
        return _agg(op, [v for _, v in cells])

    def _count(self, node: dict, rows: list[dict], gb: list[str]) -> Decimal:
        col = node.get("column")
        if col:
            kept = [r for r in rows if not empty(r.get(col))]
            if len(kept) != len(rows):
                self._skip(col, len(rows) - len(kept))
            rows = kept
        if not gb:
            return Decimal(len(rows))
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            groups.setdefault(tuple(r.get(g) for g in gb), []).append(r)
        h = node.get("having")
        if h:
            newest = {k: max(str(r[h["column"]])[:10] for r in v if not empty(r.get(h["column"]))) for k, v in groups.items()
                      if any(not empty(r.get(h["column"])) for r in v)}
            if not newest:
                raise Cannot(f"There is no {label(h['column'])} to read.")
            cutoff = bdays_before(date.fromisoformat(max(newest.values())), int(h["older_than_business_days"])).isoformat()
            groups = {k: v for k, v in groups.items() if k in newest and newest[k] < cutoff}
        return Decimal(len(groups))


def run(rule: dict, rows, period_end: str | None = None, drop_deduction: bool = False) -> dict:
    """{value, skipped, rows, groups, suppressed_groups, cannot}: value is a float, or None when it cannot be worked out (never zero)."""
    r = Run(rows, rule.get("source") or "", period_end, drop_deduction)
    try:
        v, err = r.value(rule), None
    except Cannot as e:
        v, err = None, str(e)
    except (ArithmeticError, ValueError, TypeError, KeyError, AttributeError):  # a rule a model wrote badly spoils its own measure only
        v, err = None, "The rule could not be run as written."
    return {"picked_size": r.picked_size,"value": None if v is None else float(v.quantize(Decimal("0.000001"))), "skipped": r.skipped, "rows": r.seen,
            "groups": r.groups, "suppressed_groups": r.suppressed, "cannot": err}
