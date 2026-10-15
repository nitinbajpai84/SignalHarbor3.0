"""LOOP-L: Lumen's own tools for the agent loop (cx_lumen runs it). The shared read tools come from agent_tools.tools_for.

Read: `list_gold_tables()`, `query_figure(table, figure, group_by, period, currency, filters, month)`, `compare_periods(table, figure, group_by,
month, filters)`, `get_focus_tile()`. Propose: `propose_tile(...)`, `propose_tile_edit(...)`. A propose tool only checks and returns a tile;
cx_lumen files it as "proposed" after the run.

Rules held here:
- Only this project's gold tables, only for a person who may see the project (G1). Every name is checked against the catalogue.
- The PROGRAM writes every query (cx_lumen.figure_sql: SELECT-only, values added across rows of one date, never across dates; two views of one
  figure never added together), validates it with cx_dash.check_sql and runs it. The model never types SQL and never does arithmetic: a change
  between two periods is worked out by compare_periods.
- A group under five rows (and a total beside one) is not shown to the model (EG2). The figures it could not see are kept in `later` and the
  program writes them under the answer, on this machine, from the rows.
- Arguments (LT-5): one the model leaves out gets its default, everyday words are read ("dots" is point, "monthly" is month); an unknown
  argument or a value outside the list is refused with a message that starts with the argument name and lists what is allowed.
"""
from __future__ import annotations

import logging
import re

from sh_platform.agents.groups import group_ok
from sh_platform.agents.registry import ToolRefused, ToolRegistry
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import mem_agent as M
from sh_platform.v1.agent_tools import _one_of, _only, _plain, _text, _whole, tools_for
from sh_platform.v1.p1_project import Refused

log = logging.getLogger(__name__)
MODULE = "consume"
PERIODS = ("", "day", "week", "month", "quarter", "year")
KIND_WORDS = ("line", "bar", "area", "point", "number", "table")
MAX_GROUPS = 24
MAX_COLS = 40
_ID = re.compile(r"t-[0-9a-f]{6}")
HIDDEN = ("The person already sees every figure of this result, written by the program just above your answer. Write only one or two sentences "
          "to add what your other tools found (the causes from why_moved, the view or date used), or who could know more. Do not repeat or "
          "give any figure, and never say figures are missing, hidden or unavailable.")
_MONTH = re.compile(r"(20\d\d-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?")  # EVT-T8: a day too (8 Oct cash), not only a month
_SAY = {"dots": "point", "dot": "point", "points": "point", "scatter": "point", "bars": "bar", "column": "bar", "columns": "bar",
        "lines": "line", "areas": "area", "daily": "day", "weekly": "week", "monthly": "month", "months": "month", "quarterly": "quarter",
        "yearly": "year", "annual": "year", "annually": "year", "none": "", "null": "", "all": ""}
DEFAULTS = {
    "list_gold_tables": {}, "get_focus_tile": {},
    "query_figure": {"table": "", "figure": "", "group_by": "", "period": "", "currency": "", "filters": [], "month": ""},
    "why_moved": {"start": "", "end": "", "currency": "", "book": ""},
    "compare_periods": {"table": "", "figure": "", "group_by": "", "month": "", "filters": []},
    "propose_tile": {"title": "", "table": "", "figure": "", "kind": "", "group_by": "", "period": "", "since": 0, "color": "", "filters": []},
    "propose_tile_edit": {"tile_id": "", "mark": "", "color": "", "period": "", "since": 0, "split": "", "currency": "", "filters": []},
}
_WORDY = ("kind", "mark", "period", "color", "group_by")  # read as everyday words; split keeps "none" (drop the split)


def _refuse(prefix: str, e: Refused) -> ToolRefused:
    return ToolRefused(f"{prefix} was refused: {e.message}")


def _clean(key: str, value, default):
    if value is None:
        return default
    if key == "filters" and isinstance(value, str) and "=" in value and not value.lstrip().startswith("["):
        return [value]  # one filter passed as text
    if key == "filters" and isinstance(value, dict):
        return [f"{k}={x}" for k, v in value.items() for x in (v if isinstance(v, list) else [v])]  # {"entity": "X"}, {"manager": ["A", "B"]}
    if isinstance(value, str):
        v = value.strip()
        if key in _WORDY:
            v = _SAY.get(v.lower(), v.lower() if key != "group_by" else v)
        return v.upper() if key == "currency" else v
    return value


class Lenient:
    """The registry as the loop sees it, with Lumen's own tools taking arguments the way a model passes them (LT-5)."""

    def __init__(self, reg: ToolRegistry, tools: "LumenTools"):
        self._reg, self.lumen = reg, tools

    def __getattr__(self, name):
        return getattr(self._reg, name)

    def call(self, company_id: str, module_id: str, name: str, arguments):
        want = DEFAULTS.get(name) if module_id == MODULE else None
        if want is not None and isinstance(arguments, dict):
            extra = sorted(str(k)[:30] for k in set(arguments) - set(want))
            if extra:
                raise ToolRefused(f"arguments {', '.join(extra)} are not taken by {name}; it takes {', '.join(want) or 'none'}.")
            arguments = {k: _clean(k, arguments.get(k), v) for k, v in want.items()}
        return self._reg.call(company_id, module_id, name, arguments)


class LumenTools:
    def __init__(self, plane, viewer, pid: str, did: str | None):
        self.plane, self.viewer, self.pid, self.did = plane, viewer, pid, did
        self.later: list[str] = []  # figures the model could not see, written under the answer by the program

    def notes(self) -> str:
        return "".join(" " + x for x in dict.fromkeys(self.later))

    # ---- helpers -------------------------------------------------------------------------------------------------------------------
    def _tables(self) -> list[dict]:
        from sh_platform.v1 import g1_access
        if g1_access.may_see_project(self.plane, self.viewer, self.pid) == "none":
            raise ToolRefused("table is in a project you cannot see.")
        return D.gold_tables(self.plane, self.pid)

    def _table(self, args: dict) -> dict:
        name = _text(args, "table", 100)
        tables = self._tables()
        t = next((x for x in tables if x["name"] == name), None)
        if t is None:
            raise ToolRefused(f"table is not a gold table of this project; use one of: {', '.join(x['name'] for x in tables)}.")
        return t

    @staticmethod
    def _col(t: dict, args: dict, name: str, numeric: bool | None, empty: bool = False) -> dict | None:
        v = _text(args, name, 100, empty=empty)
        if not v:
            return None
        c = next((x for x in t["columns"] if x["name"] == v), None)
        if c is None:
            ok = [x["name"] for x in t["columns"] if numeric is None or L._is(x, L.NUM) == numeric]
            raise ToolRefused(f"{name} has no such column in {t['name']}; use one of: {', '.join(ok)}.")
        if numeric is not None and L._is(c, L.NUM) != numeric:
            raise ToolRefused(f"{name} must be a {'figure (number)' if numeric else 'name or date (not a number)'} column.")
        return c

    @staticmethod
    def _when(t: dict) -> dict | None:
        w = L.when_col(t)
        return next((c for c in t["columns"] if c["name"] == w), None)

    @staticmethod
    def _month(args: dict) -> str:
        m = _text(args, "month", 10, empty=True)
        if not _MONTH.fullmatch(m):
            raise ToolRefused("month must be '' (the latest), a month like 2026-09 or a day like 2026-10-08.")
        return m

    def _filters(self, t: dict, args: dict) -> list[str]:
        """The filters as SQL conditions (values of one column any-of: 'only Cedarpoint and Kestrel', NU-17)."""
        return L.where_of([tuple(f.split("=", 1)) for f in self._filter_list(t, args)])

    def _filter_list(self, t: dict, args: dict) -> list[str]:
        """['column=value'] with each value read against the table's own values: the same value in any case, or the one value that starts
        with the words given ('Cedarpoint' is Cedarpoint Ventures). A value that is not there is refused with the list."""
        flt = args.get("filters")
        if not isinstance(flt, list) or len(flt) > 8 or not all(isinstance(x, str) for x in flt):
            raise ToolRefused("filters must be a list of at most 8 texts like column=value (an empty list for none).")
        out = []
        for item in flt:
            col, eq, val = item.partition("=")
            c = next((x for x in t["columns"] if x["name"] == col.strip()), None)
            if not eq or c is None or L._is(c, L.NUM) or not 0 < len(val.strip()) <= 60 or any(ord(ch) < 32 for ch in val):
                raise ToolRefused("filters items must be column=value for a name column of this table, value up to 60 characters.")
            have = [str(r["v"]) for r in self._run(f'select distinct "{c["name"]}" as v from "{t["name"]}" order by 1 limit 60')]
            v = val.strip().lower()
            starts = [h for h in have if h.lower().startswith(v)]
            hit = next((h for h in have if h.lower() == v), None) or (starts[0] if len(starts) == 1 else None)
            if hit is None:  # a value the model mistyped gets the list back, never an empty answer
                raise ToolRefused(f"filters value for {c['name']} is not in the table; use one of: {', '.join(have[:12])}.")
            out.append(f"{c['name']}={hit}")
        return out

    def _figure(self, t: dict, args: dict) -> dict:
        fig = self._col(t, args, "figure", True)
        cur = _text(args, "currency", 3, empty=True).upper() if "currency" in args else ""
        if cur:
            base = L._CUR_SUFFIX.sub("", fig["name"])
            alt = next((c for c in t["columns"] if c["name"] == f"{base}_{cur.lower()}" and L._is(c, L.NUM)), None)
            if alt is None:
                raise ToolRefused(f"currency has no {cur} version of {base} in this table.")
            fig = alt
        return fig

    def _run(self, sql: str) -> list[dict]:
        try:
            D.check_sql(self.plane, self.pid, sql)
            return D.run_sql(self.plane, sql)[1]
        except Refused as e:
            raise _refuse("table", e) from None

    # ---- read tools ----------------------------------------------------------------------------------------------------------------
    def list_gold_tables(self, **a) -> dict:
        _only(a)
        try:
            from sh_platform.v1 import b6_plan as B
            purposes = {t["name"]: t.get("purpose") for t in (B.get(self.plane, self.pid) or {}).get("tables", [])}
        except Exception:  # noqa: BLE001 - the purpose is a nicety
            purposes = {}
        out = [{"name": t["name"], "purpose": str(purposes.get(t["name"]) or "gold table"),
                "columns": [f'{c["name"]} ({c["type"]})' for c in t["columns"][:MAX_COLS]]} for t in self._tables()[:MAX_GROUPS]]
        # RC2-3: an empty answer says where to look next, so a loop on the project-free route does not conclude the table does not exist
        return _plain({"tables": out}) if out else {"tables": [], "note": "This project has no gold tables yet; another project in projects_you_can_read may have them."}

    def query_figure(self, **a) -> dict:
        _only(a, "table", "figure", "group_by", "period", "currency", "filters", "month")
        t = self._table(a)
        fig = self._figure(t, a)
        grp = self._col(t, a, "group_by", False, empty=True)
        period, month = _one_of(a, "period", PERIODS), self._month(a)
        when = self._when(t)
        if (period or month) and when is None:
            raise ToolRefused("period needs a date column, and this table has none.")
        if period and grp and grp["name"] == when["name"]:
            grp = None
        where = self._filters(t, a)
        by = ([grp["name"]] if grp else []) + [v for v in L.view_cols(t, keep=(grp["name"] if grp else "",)) if not any(f.startswith(f'"{v}"') for f in where)]
        trend = bool(period)
        rows = self._run(L.figure_sql(t, fig["name"], by, trend, period or None, None, month or None, where, size=True))
        fn, wn = fig["name"], when["name"] if when else None
        total_n = sum(int(r["group_size"]) for r in rows)
        if not rows or not group_ok(total_n):
            if rows:
                self.later.append(self._rows_line(t, fn, rows, by, wn, trend, self._as_of(t, wn, month) if wn and not trend else None, self._only(t, a)))
                return {"table": t["name"], "figure": fn, "summary": "The query is valid but finds fewer than five rows in all. " + HIDDEN}
            return {"table": t["name"], "figure": fn, "summary": "The query is valid but finds no rows."}
        small = any(not group_ok(int(r["group_size"])) for r in rows)  # a total beside hidden groups would let the hidden one be subtracted
        views = [v for v in by if v != (grp["name"] if grp else None)]
        ok = [r for r in rows if group_ok(int(r["group_size"]))]  # EG2: a hidden group left in the list reads as a raw row at the gateway
        shown = [] if small else ok[-MAX_GROUPS:] if period else ok[:MAX_GROUPS]  # some parts hidden: none shown, so no part reads as the whole
        out = {"table": t["name"], "figure": fn, "group_size": total_n,
               **({} if small or views else {"total": round(sum(float(r[fn] or 0) for r in rows), 2)}),
               "groups": [{k: (str(v)[:10] if k == wn else v) for k, v in r.items()} for r in shown]}
        if wn and not trend:
            out["as_of"] = self._as_of(t, wn, month)
        if views:
            out["views"] = f"{', '.join(views)} holds two views of the same figure; they are kept apart and never added together."
        if small:
            out["hidden"] = HIDDEN
            self.later.append(self._rows_line(t, fn, rows, by, wn, trend, out.get("as_of"), self._only(t, a)))
        if trend and (gap := L.partial_periods(self.plane, t, period)):
            out["incomplete_periods"] = gap
        if len(ok) > len(shown):
            out["more"] = "more groups exist than are listed"
        return out

    def _only(self, t: dict, a: dict) -> list[str]:
        """The filter values of a query ('Entity B', 'administrator'), so the line the program writes says whose figure it is."""
        return [f.split("=", 1)[1] for f in self._filter_list(t, a)]

    def _as_of(self, t: dict, w: str, month: str) -> str:
        cap = f" where strftime(\"{w}\", '{L.month_fmt(month)}') <= '{month}'" if month else ""
        got = self._run(f'select max("{w}") as d from "{t["name"]}"{cap}')
        return str(got[0]["d"])[:10] if got and got[0]["d"] else ""

    @staticmethod
    def _rows_line(t: dict, fn: str, rows: list[dict], by: list[str], wn: str | None, trend: bool, as_of: str | None, only: list[str] = ()) -> str:
        """All the groups, in words, from the rows (for the person; never sent to the model). `only`: the filter values, named in the line."""
        label = L._plain_field(L._CUR_SUFFIX.sub("", fn)).capitalize() + (f" ({', '.join(only)})" if only else "")
        parts = [(", ".join(str(r.get(k)) for k in ([wn] if trend and wn else []) + by if r.get(k) is not None), L._num(r.get(fn))) for r in rows[-MAX_GROUPS:]]
        listed = "; ".join(f"{k} {L.fig_text(t, fn, v)}" if k else L.fig_text(t, fn, v) for k, v in parts if v is not None)  # RC2-3: a return as a percentage
        return f"{label}{f' for {L.when_words(as_of, wn)}' if as_of else ''}, from the rows: {listed}."

    def compare_periods(self, **a) -> dict:
        _only(a, "table", "figure", "group_by", "month", "filters")
        t = self._table(a)
        fig = self._figure(t, a)
        grp = self._col(t, a, "group_by", False, empty=True)
        month = self._month(a)
        if self._when(t) is None:
            raise ToolRefused("table has no date column, so there are no periods to compare.")
        try:
            ch = L.period_change(self.plane, t, fig["name"], [grp["name"]] if grp else [], month or None, self._filters(t, a))
        except Refused as e:
            raise _refuse("table", e) from None
        if ch.get("missing") or ch.get("only"):
            return {"table": t["name"], "figure": fig["name"], "summary": ch["say"]}
        n = sum(g["n"] for g in ch["groups"])
        hidden = [g for g in ch["groups"] if not group_ok(g["n"])]
        if hidden:
            self.later.append(L.change_words(L._plain_field(L._CUR_SUFFIX.sub("", fig["name"])).capitalize(), ch)[0])
        if not group_ok(n):  # too few rows for the model to see anything: the dates and the program's note only
            return {"table": t["name"], "figure": fig["name"], "from": ch["from"], "to": ch["to"], "summary": HIDDEN}
        out = {"table": t["name"], "figure": fig["name"], "from": ch["from"], "to": ch["to"], "group_size": n,
               "groups": [{**{k: str(v) for k, v in g["key"].items()}, "before": float(g["before"]), "after": float(g["after"]),
                           "change": float(g["after"] - g["before"]), "group_size": g["n"]} for g in ch["groups"] if not hidden][:MAX_GROUPS]}
        if ch.get("total") and not hidden and group_ok(n):
            out.update(before=float(ch["total"][0]), after=float(ch["total"][1]), change=float(ch["total"][1] - ch["total"][0]))
        if ch.get("views"):
            out["views"] = f"{', '.join(ch['views'])} holds two views of the same figure; they are kept apart and never added together."
        if hidden:
            out["hidden"] = HIDDEN
        return out

    def why_moved(self, **a) -> dict:
        """LQ-3: the cause of a move (price moves, trades, revisions, exchange rates), the same bridge the project-free route uses (talk.py,
        k4_office.why_moved). Its figures go into `later`, written for the person by the program."""
        from sh_platform.v1 import talk as T
        w = T._LumenAnywhere(self.plane, self.viewer)
        got = w.why_moved(**a)
        self.later += [x for x in w.later if x not in self.later]
        return got

    def get_focus_tile(self, **a) -> dict:
        _only(a)
        if not self.did:
            return {"focus": "no dashboard yet, so no tile in focus"}
        tile = L._focus_tile(self.plane, self.viewer, self.pid, self.did)
        if tile is None:
            return {"focus": "no tile on this dashboard yet"}
        return L.focus_facts(tile)

    # ---- propose tools: check and return, write nothing -----------------------------------------------------------------------------
    def propose_tile(self, **a) -> dict:
        _only(a, "title", "table", "figure", "kind", "group_by", "period", "since", "color", "filters")
        t = self._table(a)
        fig, grp = self._col(t, a, "figure", True), self._col(t, a, "group_by", False, empty=True)
        kind, period = _one_of(a, "kind", KIND_WORDS), _one_of(a, "period", PERIODS)
        since, color = _whole(a, "since", 0, 120), _one_of(a, "color", ("",) + tuple(M.COLORS))
        title = _text(a, "title", 120, empty=True)
        when = self._when(t)
        if kind in L.TIMED and when is None:
            raise ToolRefused("kind line, area and point need a date column, and this table has none.")
        if (period or since) and (when is None or kind in ("number", "table")):
            raise ToolRefused("period and since only fit a line, area, point or bars over a date column.")
        if grp and when and grp["name"] == when["name"]:
            grp = None  # LT-1: the time axis is not a split
        r = {"fig": fig["name"], "when": when["name"] if when else None, "split": grp["name"] if grp else None, "kind": kind}
        if period:
            r["period"] = period
        if since:
            r["since"] = since
        if color and kind not in ("number", "table") and not L._series(t, r):
            r["color"] = color
        if "filters" in a and (flt := self._filter_list(t, a)):
            r["filters"] = flt
        tile = L.build(t, r)
        if tile is None:
            raise ToolRefused("kind bar needs a name column to split by or a date column.")
        if title:
            tile["title"], tile["title_given"] = title, True
        tile["note"] = "Proposed by Lumen from your words."
        return self._checked(tile)

    def propose_tile_edit(self, **a) -> dict:
        _only(a, "tile_id", "mark", "color", "period", "since", "split", "currency", "filters")
        tid = _text(a, "tile_id", 20)
        if not _ID.fullmatch(tid):
            raise ToolRefused("tile_id must be a tile id like t-1a2b3c (tile_in_focus gives it).")
        tile = next((x for x in D.get(self.plane, self.viewer, self.pid, self.did)["tiles"] if x["id"] == tid), None) if self.did else None
        if tile is None:
            raise ToolRefused("tile_id is not a tile on this dashboard.")
        st = {}
        if mark := _one_of(a, "mark", ("", "line", "bar", "area", "point")):
            st["mark"] = mark
        if color := _one_of(a, "color", ("",) + tuple(M.COLORS)):
            st["color"] = color
        if period := _one_of(a, "period", PERIODS):
            st["period"] = period
        if since := _whole(a, "since", 0, 120):
            st["since"] = since
        cur = _text(a, "currency", 3, empty=True).upper()
        if cur:
            st["currency"] = cur
        split = _text(a, "split", 100, empty=True) or None
        tables = self._tables()
        if split and split != "none":
            rec = tile.get("recipe") or {}
            t = next((x for x in tables if x["name"] == rec.get("table")), None)
            if t is None or not any(c["name"] == split and not L._is(c, L.NUM) and c["name"] != rec.get("when") for c in t["columns"]):
                raise ToolRefused("split must be a name column of the tile's table, or none to remove the split.")
        flt = None
        if a.get("filters"):  # ['none'] drops the filter; [] (the default) keeps it
            rec = tile.get("recipe") or {}
            t = next((x for x in tables if x["name"] == rec.get("table")), None)
            if t is None:
                raise ToolRefused("filters cannot be read on this tile; it was not made from a figure of a gold table.")
            flt = [] if [str(x).strip().lower() for x in a["filters"]] == ["none"] else self._filter_list(t, a)
        # LT2-4: nothing to change is not a bad argument: the code (the first word, loop._reason) says no_change
        if not st and not split and flt is None:
            raise ToolRefused("no_change was asked: pass at least one of mark, color, period, since, split, currency or filters.")
        new, reply = L.revise(self.plane, tables, tile, "", st, split, flt)
        if new is None:
            raise ToolRefused("no_change needed: " + reply + " Say so to the person in one sentence; do not call again.")
        return self._checked(new)

    def _checked(self, tile: dict) -> dict:
        try:
            _, cols = D.check_sql(self.plane, self.pid, tile["sql"])
            D.check_spec(tile["spec"], cols)
        except Refused as e:
            raise _refuse("table", e) from None
        return tile


def lumen_registry(plane, viewer, pid: str, did: str | None) -> Lenient:
    """tools_for(lumen) plus Lumen's own tools, for one project and dashboard. `.lumen` is the tools object (its `later` lines)."""
    reg = tools_for(plane, viewer, "lumen", module_id=MODULE)
    t = LumenTools(plane, viewer, pid, did)
    cols = {"table": "string", "figure": "string", "group_by": "string"}
    for name, func, params, propose, text in (
        ("list_gold_tables", t.list_gold_tables, {}, False,
         "This project's gold tables: name, purpose and columns with types. No rows."),
        ("query_figure", t.query_figure, {**cols, "period": "string", "currency": "string", "filters": "array", "month": "string"}, False,
         "A figure, worked out by the program. figure: a number column; group_by: a name column or ''; month: '' for the latest date, "
         "'YYYY-MM' for the last date of that month, or 'YYYY-MM-DD' for that day (or the last date before it); period: '' for one date, or day, week, month, quarter or year for a trend (each period's "
         "last date); currency: '' or a code like SGD; filters: ['column=value'] or []. Returns the total and groups."),
        ("compare_periods", t.compare_periods, {**cols, "month": "string", "filters": "array"}, False,
         "Why a figure moved: its value at the last date of `month` ('YYYY-MM', '' for the latest) against the period before, the change, and "
         "the change of each group (group_by: a name column or ''). For one part only (a follow-up like 'and for X?'), filters: ['column=X']. "
         "The program works out every change."),
        ("get_focus_tile", t.get_focus_tile, {}, False, "The tile this conversation is about (id, table, figure, kind, split, period, colour). Use it for a follow-up."),
        ("propose_tile", t.propose_tile, {"title": "string", **cols, "kind": "string", "period": "string", "since": "number", "color": "string",
                                          "filters": "array"}, True,
         "Propose one new tile per figure (nothing is saved; the person accepts it). kind: line, bar, area, point, number or table; title: '' "
         "for a default; group_by: a name column to split by ('by' or 'per' a name) or ''; period: '', day, week, month, quarter or year; "
         "since: last months, 0 for all; color: '' or a colour name; filters: ['column=value'] for 'only X and Y' (one item per value) or []."),
        ("propose_tile_edit", t.propose_tile_edit, {"tile_id": "string", "mark": "string", "color": "string", "period": "string", "since": "number",
                                                    "split": "string", "currency": "string", "filters": "array"}, True,
         "Propose a new version of the tile in focus. Leave out (or '' / 0 / []) what stays. mark: line, bar, area or point; color: a colour "
         "name; period: day, week, month, quarter or year; since: last N months; split: a name column, or 'none'; currency: a code like SGD; "
         "filters: ['column=value'] for 'only X and Y' (one item per value), ['none'] to show all again.")):
        reg.register(MODULE, name, func, read_only=not propose, proposes=propose, description=text, parameters=params)
    if did:  # LQ-3: on a dashboard; the project-free route (talk.py, did None) registers its own why_moved under the same name
        reg.register(MODULE, "why_moved", t.why_moved, read_only=True, parameters={"start": "string", "end": "string", "currency": "string", "book": "string"},
                     description="Why net worth or the portfolios moved between two month-ends: the change and its causes (price moves, trades, "
                                 "revisions, exchange rates) with the largest lines. start, end: YYYY-MM-DD (the last day of the month before and of "
                                 "the month asked); currency: USD, SGD ...; book: '' or a book name such as liquid.")
    return Lenient(reg, t)

