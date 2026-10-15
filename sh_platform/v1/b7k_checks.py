"""STUDIO2 card B: Lumen checks the charts. Rules only, no model: each check reads a placed tile's spec, a few of its rows, and its slot.

check = {id, widget, tile, kind: counted_twice|flattened_trend|space|house_style|too_many, message, fix?: {label, patch, tile}}.
A fix's `patch` goes to PATCH DASH/tiles/{tid}. Patch fields beyond kind/measure/split/when/only/title (card A accepts them):
  scale_zero: bool   (false = the value axis starts near the data)
  size: str          (small|medium|wide|full: the tile's slot on the grid)
  stack: bool        (false = parts side by side, not stacked)
  number_format: str (currency|percent|number)"""
from __future__ import annotations

from contextlib import suppress

from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D

TOO_MANY = 9
FLAT_SPREAD = 0.25      # a line whose highest and lowest values differ by less than this share of the highest looks flat from zero
FEW_ROWS = 4
# Words that name where a figure came from; two of them as the parts of one stack means the same money is added up twice.
SOURCES = ("administrator", "trading desk", "custodian", "broker", "bank statement", "general ledger", "ledger", "back office", "front office")
SOURCE_COLUMNS = ("source", "system", "basis", "view", "origin")
MONEY = ("value", "worth", "amount", "revenue", "cost", "price", "balance", "income", "fee", "nav", "asset", "profit", "cash")
PERCENT = ("pct", "percent", "rate", "return", "yield")


def _mark(spec: dict) -> str:
    m = spec.get("mark")
    return str(m.get("type") if isinstance(m, dict) else m or "")


def _view(spec: dict) -> str:
    return str((spec.get("usermeta") or {}).get("view") or "")


def _enc(spec: dict, ch: str) -> dict:
    e = (spec.get("encoding") or {}).get(ch)
    return e if isinstance(e, dict) else {}


def _check(kind: str, item: dict, message: str, fix: dict | None = None) -> dict:
    out = {"id": f"{kind}:{item['id']}", "widget": item["id"], "tile": item.get("tile"), "kind": kind, "message": message}
    return out | ({"fix": fix | {"tile": item.get("tile")}} if fix else {})


def _source_of(v) -> str | None:
    s = str(v).lower()
    return next((w for w in SOURCES if w in s), None)


def _counted_twice(item: dict, spec: dict, rows: list[dict]) -> dict | None:
    if _mark(spec) not in ("bar", "area") or _enc(spec, "y").get("stack") is False or _enc(spec, "xOffset").get("field"):  # side by side already
        return None
    field = _enc(spec, "color").get("field")
    if not field:
        return None
    parts = list(dict.fromkeys(r.get(field) for r in rows if r.get(field) is not None))
    seen = {_source_of(p) for p in parts} - {None}
    if len(seen) < 2 and not (len(parts) >= 2 and any(c in field.lower() for c in SOURCE_COLUMNS)):
        return None
    names = " and ".join(str(p) for p in parts[:3])
    return _check("counted_twice", item, f"{item['title']} stacks {names}, which look like two views of the same money, so the total counts it twice.",
                  {"label": "Show them side by side", "patch": {"stack": False}})


def _flattened(item: dict, spec: dict, rows: list[dict]) -> dict | None:
    y = _enc(spec, "y")
    if _mark(spec) not in ("line", "area") or (y.get("scale") or {}).get("zero") is False or not y.get("field"):
        return None
    vals = [float(r[y["field"]]) for r in rows if isinstance(r.get(y["field"]), (int, float))]
    if len(vals) < 3 or min(vals) <= 0 or (max(vals) - min(vals)) / max(vals) >= FLAT_SPREAD:
        return None
    return _check("flattened_trend", item, f"{item['title']} starts its scale at zero while the values only move a little, so the trend looks flat.",
                  {"label": "Start the scale near the data", "patch": {"scale_zero": False}})


def _space(item: dict, spec: dict, rows: list[dict]) -> dict | None:
    if _view(spec) not in ("status", "table") or not rows or len(rows) > FEW_ROWS or D.SIZES.get(item.get("size"), 0) < 6:
        return None
    return _check("space", item, f"{item['title']} has {len(rows)} row{'s' if len(rows) != 1 else ''} in a large slot; it would fit as a small tile.",
                  {"label": "Make it small", "patch": {"size": "small"}})


def _house_style(item: dict, spec: dict, tile: dict) -> dict | None:
    m = str(tile.get("kpi") or "").lower()
    ch = "text" if _view(spec) == "figure" else "y"
    if not m or _view(spec) in ("table", "status") or _mark(spec) not in ("text", "line", "bar", "area") or _enc(spec, ch).get("format") or (_enc(spec, ch).get("axis") or {}).get("format"):
        return None
    fmt = "percent" if any(w in m for w in PERCENT) else "currency" if any(w in m for w in MONEY) else None
    if fmt is None:
        return None
    return _check("house_style", item, f"{item['title']} shows {m.replace('_', ' ')} without a {fmt} format.",
                  {"label": f"Apply the {fmt} format", "patch": {"number_format": fmt}})


def run(layout: dict, tiles: list[dict], rows_of) -> list[dict]:
    """The checks for a layout ({rows, items}) and its tiles; rows_of(tile) -> the tile's rows (may be empty)."""
    by_id, out = {t["id"]: t for t in tiles}, []
    shown = [i for i in layout["items"] if i.get("kind") != "note"]
    for item in shown:
        tile = by_id.get(item.get("tile"))
        if tile is None:
            continue
        spec, rows = tile["spec"], rows_of(tile)
        out += [c for c in (_counted_twice(item, spec, rows), _flattened(item, spec, rows), _space(item, spec, rows), _house_style(item, spec, tile)) if c]
    if len(shown) > TOO_MANY:
        out.append({"id": "too_many", "widget": None, "tile": None, "kind": "too_many",
                    "message": f"This dashboard has {len(shown)} tiles. More than {TOO_MANY} is hard to read at a glance; consider moving some to a second page."})
    return out


def checks(plane, viewer, pid: str, did: str) -> dict:
    rec = S.open_rec(plane, viewer, pid, did)

    def rows_of(tile: dict) -> list[dict]:
        with suppress(Exception):  # a tile whose data cannot be read is simply not checked on its figures
            return D.run_sql(plane, tile["sql"])[1]
        return []
    return {"checks": run(S._layout(dict(rec)), rec["tiles"], rows_of)}
