"""DS1: the dashboard studio in Build (docs/plan/DASHBOARD-STUDIO.md). A maker arranges widgets on a 12-column grid, Lumen helps, someone else approves,
and Consume shows the published version only.

Storage and the lifecycle are cx_dash's (a dashboard file with `layout` and `lifecycle`). Here: the widget library (a widget is a tile, built from a
gold table by rules, so it is checked and run like every other tile), the grid rules, "ask Lumen for this slot" (cx_lumen.ask, then the tile is
placed), and the refresh facts of the header (b6_schedule, b6_run, and Map › Health in k3_map)."""
from __future__ import annotations

import secrets
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import lock_for
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b6_run as R
from sh_platform.v1 import b6_schedule as SCH
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1 import k3_map, p1_project
from sh_platform.v1 import mem_agent as M
from sh_platform.v1.p1_project import Refused

MAKERS = {"company_admin", "analyst"}
LUMEN = Viewer(name="Lumen", roles=frozenset({"analyst"}), account_id="lumen")  # H10: the starter draft is Lumen's own; a maker takes it over when they act on it
KINDS = ("figure", "line", "bar", "area", "table", "status", "note", *("bullet", "waterfall", "small_multiples", "calendar", "treemap", "kpi_strip"))
SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
ROWS_MAX = 40
ARCHIVE_DAYS = 14  # a never-published draft untouched this long leaves the studio's strip; kept, and shown again on request
MAP_HEALTH = "/centre/operations"
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_NUM = ("tinyint", "smallint", "integer", "bigint", "hugeint", "decimal", "double", "float", "real", "numeric")
_DATE = ("date", "timestamp")


def is_maker(viewer) -> bool:
    return bool(MAKERS & set(getattr(viewer, "roles", ()) or ()))


def _words(name: str) -> str:
    return name.replace("_", " ")


def _label(table: str) -> str:
    return _words(table.removeprefix("gold_"))


# ---- who may open what -----------------------------------------------------------------------------------------------------------

def _grid_of(tiles: list[dict]) -> dict:
    """Accepted tiles on a grid, two to a row, in the order they were made."""
    acc = [t for t in tiles if t["state"] == "accepted"]
    return {"rows": max(2, (len(acc) + 1) // 2), "items": [{"id": "w-" + secrets.token_hex(3), "kind": "lumen", "tile": t["id"], "title": t["title"], "text": "",
                                                          "row": i // 2, "col": 6 * (i % 2), "size": "medium"} for i, t in enumerate(acc)]}


def adopt(plane, pid: str) -> None:
    """OP1: dashboards made before the studio became the only place to build move into it, nothing dropped. A personal one (started in Consume) becomes
    a draft of its maker; one that was already shared keeps showing in Consume as published, and gets a grid so the studio can open it."""
    for p in sorted(D._dir(plane, pid).glob("dash-*.json")):
        with suppress(OSError, ValueError, Refused, KeyError, TypeError):
            rec = D.read_json_strict(p, dict)
            if not rec or rec.get("lifecycle") is not None:
                continue
            personal = D._personal(rec)
            rec["layout"] = rec.get("layout") or _grid_of(rec["tiles"])
            if personal:
                rec["lifecycle"] = {"status": "draft", "version": 1, "published": None, "company_wide": False, "editors": []}  # `personal` stays: see _private
            else:
                D.ensure_lifecycle(rec)
            D._save(plane, rec)


def _private(viewer, rec: dict) -> bool:
    """OP1: a personal dashboard (CL1) taken into the studio stays its maker's own while it is a draft, as it was in Consume (not even the admin)."""
    return bool(rec.get("personal")) and D.status_of(rec) == "draft" and D.who(viewer) != rec["created_by"]


def _editor(plane, viewer, pid: str, did: str) -> dict:
    rec = D._editor(plane, viewer, pid, did)
    if _private(viewer, rec):
        raise Refused(403, "Only the person who made the dashboard can change it.")
    return rec


def open_rec(plane, viewer, pid: str, did: str) -> dict:
    """The working copy, for a maker, its creator, or (once it is submitted or published) the sponsor who may have to approve it."""
    adopt(plane, pid)
    rec = D._load(plane, pid, did)
    if _private(viewer, rec):
        raise Refused(403, "You do not have access to this dashboard.")
    if is_maker(viewer) or D.who(viewer) == rec["created_by"] or (D.status_of(rec) != "draft" and "sponsor" in set(getattr(viewer, "roles", ()) or ())):
        return rec
    raise Refused(403, "You do not have access to this dashboard.")


def listing(plane, viewer, pid: str) -> list[dict]:
    """`made_by` is the maker's name; `approved_by` the approver's name, None for one published before approvals existed (adopted, OP1)."""
    adopt(plane, pid)
    names = k3_map._audience_names(plane)
    out = []
    for p in sorted(D._dir(plane, pid).glob("dash-*.json")):
        with suppress(OSError, ValueError, Refused, KeyError):
            rec = D.read_json_strict(p, dict)
            if rec and (rec.get("lifecycle") or rec["created_by"] == D.who(viewer)) and _may_list(viewer, rec):
                lc = rec.get("lifecycle") or {}
                out.append({"id": rec["id"], "title": rec["title"], "status": D.status_of(rec), "version": lc.get("version", 1), "tiles": len(rec.get("layout", {}).get("items", [])),
                            "created_by": rec["created_by"], "made_by": names.get(str(rec["created_by"])) or ("Lumen" if str(rec["created_by"]).lower().startswith("lumen") else None), "approved_by": lc.get("approved_by_name"),
                            "updated_at": rec["updated_at"], "sent_back": lc.get("sent_back"),
                            "waiting_for_you": D.can_approve(viewer, rec), "archived": _stale(rec)})
    return out


def _stale(rec: dict, now: datetime | None = None) -> bool:
    if D.status_of(rec) != "draft" or (rec.get("lifecycle") or {}).get("published"):
        return False
    with suppress(ValueError, TypeError):
        return (now or datetime.now(timezone.utc)) - datetime.fromisoformat(rec["updated_at"]) > timedelta(days=ARCHIVE_DAYS)
    return False


def _may_list(viewer, rec: dict) -> bool:
    return not _private(viewer, rec) and (is_maker(viewer) or D.who(viewer) == rec["created_by"] or D.status_of(rec) != "draft")


# ---- the grid --------------------------------------------------------------------------------------------------------------------

H_MAX = 4  # a widget is 1 to 4 rows tall; the person drags its corner to choose


def _width(item: dict) -> int:
    return D.SIZES[item["size"]]


def _h(item: dict) -> int:
    return item.get("h") or 1


def _cells(item: dict) -> set[tuple[int, int]]:
    return {(r, c) for r in range(item["row"], item["row"] + _h(item)) for c in range(item["col"], item["col"] + _width(item))}


def _check_grid(layout: dict) -> None:
    rows, taken = layout["rows"], set()
    for i in layout["items"]:
        if i["size"] not in D.SIZES or not (isinstance(_h(i), int) and 1 <= _h(i) <= H_MAX) or not (0 <= i["row"] and i["row"] + _h(i) <= rows)                 or not (0 <= i["col"] and i["col"] + _width(i) <= 12):
            raise Refused(400, "A widget does not fit on the grid there. Move it or make it smaller.")
        cells = _cells(i)
        if cells & taken:
            raise Refused(400, "Two widgets cannot share a slot. Move one of them.")
        taken |= cells


def free_width(layout: dict, row: int, col: int, skip: str | None = None) -> int:
    """How many columns are free from (row, col) to the right, up to the end of the grid or the next widget."""
    used = {cell for i in layout["items"] if i["id"] != skip for cell in _cells(i)}
    n = 0
    while col + n < 12 and (row, col + n) not in used:
        n += 1
    return n


def _fit(layout: dict, row, col, size: str) -> str:
    """The wanted size, or the largest one that fits the free space; a refusal when not even Small does."""
    if not (isinstance(row, int) and isinstance(col, int) and 0 <= row < layout["rows"] and 0 <= col < 12):
        raise Refused(400, "Choose a slot on the grid.")
    free = free_width(layout, row, col)
    sizes = [s for s, w in D.SIZES.items() if w <= min(free, D.SIZES.get(size, 6))]
    if not sizes:
        raise Refused(400, "That slot is taken or too narrow. Choose an empty slot.")
    return sizes[-1]


def _layout(rec: dict) -> dict:
    return rec.setdefault("layout", {"rows": 2, "items": []})


# ---- widgets: a tile built by rules from one gold table ---------------------------------------------------------------------------

def _pick(cols: list[dict], want, kinds: tuple[str, ...], skip: tuple = ()) -> str | None:
    names = {c["name"] for c in cols}
    if want:
        if want not in names:
            raise Refused(400, f"The column {_words(str(want))} is not in that table.")
        return want
    return next((c["name"] for c in cols if c["name"] not in skip and c["type"].lower().startswith(kinds) and not c["name"].endswith("_id")), None)


VIEW_KINDS = ("bullet", "waterfall", "small_multiples", "calendar", "treemap", "kpi_strip")
_VIEWS = ("view_type", "view", "source_view", "basis", "source_system")
_FLOW = ("amount", "movement", "flow", "call", "distribution", "fee", "paid", "inflow", "outflow", "contribution", "income", "expense", "pnl", "count", "trade")


def _latest(table: str, m, w, q) -> str:
    """' where <date> = latest' when the measure is a balance, level or rate (cash, net worth, a return): those are snapshots and adding them
    across dates counts them again. A flow (amounts, calls, fees) is summed over time, so it gets ''."""
    if not w or not m or any(f in m.lower() for f in _FLOW):
        return ""
    return f" where {q(w)} = (select max({q(w)}) from {q(table)})"
_TARGET = ("target", "benchmark", "budget", "plan", "goal")


def _view_tile(kind: str, table: str, cols: list[dict], m: str, w, s, q) -> dict:
    """E: the six richer views, drawn by ui/src/v1/cxui/Chart.tsx from fixed column aliases (the spec only says usermeta.view, so no column lookup on screen).
    Data shapes (rows the tile returns):
      bullet           name, value, target       one row per entity; the measure against its target/benchmark column (needs a column named target/benchmark/budget/plan/goal)
      waterfall        label, value              signed contribution per category, in order; an optional `kind` column of start|end|total marks absolute bars, else the screen adds the end total
      small_multiples  x, grp, value             one small line per grp value on one shared scale (needs a date and a category column)
      calendar         day, value                one row per day; the month of the newest day is drawn as a grid, cell shade = value
      treemap          label, value              one box per category, area = value (negatives and zeros are left out)
      kpi_strip        period, <measure>, ...    oldest first, up to four number columns: each is a headline (newest), its change on the one before, and a sparkline"""
    nice, tbl = _words(m).capitalize(), q(table)
    spec = lambda: {"mark": "text", "usermeta": {"view": kind}, "encoding": {}}  # noqa: E731
    def need(col, what: str) -> str:
        if not col:
            raise Refused(400, f"A {_words(kind)} view needs a {what} column. This table has none.")
        return col
    need_cat, need_day = (lambda: need(s, "category")), (lambda: need(w, "date"))
    if kind == "bullet":
        tgt = next((c["name"] for c in cols if c["name"] != m and any(k in c["name"].lower() for k in _TARGET) and c["type"].lower().startswith(_NUM)), None)
        if tgt is None:
            raise Refused(400, "A bullet view needs a target or benchmark number column next to the measure. This table has none.")
        sql = f'select {q(need_cat())} as name, sum({q(m)}) as value, sum({q(tgt)}) as target from {tbl}{_latest(table, m, w, q)} group by 1 order by 1 limit 20'
        return {"title": f"{nice} against {_words(tgt)}", "kpi": m, "sql": sql, "spec": spec()}
    if kind == "waterfall":
        return {"title": f"{nice} by {_words(need_cat())}", "kpi": m, "spec": spec(), "sql": f'select {q(s)} as label, sum({q(m)}) as value from {tbl} group by 1 order by 1 limit 12'}
    if kind == "small_multiples":
        return {"title": f"{nice} by {_words(need_cat())} over time", "kpi": m, "spec": spec(),
                "sql": f'select {q(need_day())} as x, {q(s)} as grp, sum({q(m)}) as value from {tbl} group by 1, 2 order by 2, 1 limit 400'}
    if kind == "calendar":
        return {"title": f"{nice} by day", "kpi": m, "spec": spec(), "sql": f'select cast({q(need_day())} as date) as day, sum({q(m)}) as value from {tbl} group by 1 order by 1 limit 400'}
    if kind == "treemap":
        return {"title": f"{nice} by {_words(need_cat())}", "kpi": m, "spec": spec(),
                "sql": f'select {q(s)} as label, sum({q(m)}) as value from {tbl}{_latest(table, m, w, q)} group by 1 having sum({q(m)}) > 0 order by 2 desc limit 30'}
    nums = [m] + [c["name"] for c in cols if c["name"] != m and c["type"].lower().startswith(_NUM) and not c["name"].endswith("_id")][:3]  # kpi_strip
    sel = ", ".join(f"sum({q(c)}) as {q(c)}" for c in nums)
    return {"title": f"{nice} at a glance", "kpi": m, "spec": spec(),
            "sql": f'select * from (select {q(need_day())} as period, {sel} from {tbl} group by 1 order by 1 desc limit 24) as r order by 1'}


def build_tile(plane, pid: str, kind: str, table: str, measure=None, when=None, split=None) -> dict:
    """SQL and Vega-Lite spec for one widget, from the table's own columns; the person names a table (and may name columns), no SQL is typed."""
    t = next((x for x in D.gold_tables(plane, pid) if x["name"] == table), None)
    if t is None:
        raise Refused(400, "Choose one of this project's tables.")
    cols = t["columns"]
    q = lambda c: '"' + c + '"'  # noqa: E731
    m, w = _pick(cols, measure, _NUM), _pick(cols, when, _DATE)
    s = _pick(cols, split, ("varchar", "text"), skip=(w or "", m or ""))
    if kind in ("figure", "line", "bar", "area", *VIEW_KINDS) and not m:
        raise Refused(400, "This table has no number column to show.")
    nice = _words(m or "")
    if kind == "figure":  # the newest period and the one before it, so the screen can say how much it moved
        sql = f'select {q(w)}, sum({q(m)}) as value from {q(table)} group by 1 order by 1 desc limit 2' if w else f'select sum({q(m)}) as value from {q(table)}'
        return {"title": nice.capitalize(), "kpi": m, "sql": sql, "spec": {"mark": "text", "usermeta": {"view": "figure"}, "encoding": {"text": {"field": "value", "type": "quantitative"}}}}
    if kind == "table":
        sql = f'select {", ".join(q(c["name"]) for c in cols[:8])} from {q(table)} limit 50'
        return {"title": _label(table).capitalize(), "kpi": "", "sql": sql, "spec": {"mark": "text", "usermeta": {"view": "table"}, "encoding": {}}}
    if kind == "status":  # a short list: a name, and the word that says where it stands
        words = [c["name"] for c in cols if c["type"].lower().startswith(("varchar", "text")) and not c["name"].endswith("_id")]
        if not words:
            raise Refused(400, "This table has no text column to list.")
        picked = [x for x in (words[0], next((c for c in words[1:] if "status" in c or "state" in c), words[1] if len(words) > 1 else None)) if x]
        return {"title": _label(table).capitalize() + " status", "kpi": "", "sql": f'select {", ".join(q(c) for c in picked)} from {q(table)} limit 20',
                "spec": {"mark": "text", "usermeta": {"view": "status"}, "encoding": {}}}
    if kind in VIEW_KINDS:
        return _view_tile(kind, table, cols, m, w, s, q)
    x = w if kind != "bar" and w else (s or w) if kind == "bar" else None
    if x is None:
        raise Refused(400, "A " + kind + " chart needs a date column" + (" or a category column." if kind == "bar" else ". This table has none."))
    grp = s if s and s != x else None
    views = next((c["name"] for c in cols if c["name"] in _VIEWS), None)
    two_views = kind == "bar" and grp is None and views and views != x  # two views of the same money (administrator, trading desk): side by side, never summed
    if two_views:
        grp = views
    sel = [q(x)] + ([q(grp)] if grp else []) + [f"sum({q(m)}) as {q(m)}"]
    enc = {"x": {"field": x, "type": "temporal" if x == w else "nominal"}, "y": {"field": m, "type": "quantitative"}}
    if grp:
        enc["color"] = {"field": grp, "type": "nominal"}
    if two_views:
        enc["xOffset"] = {"field": grp}
    by = f" by {_words(x if two_views else grp or x)}" if (grp or x != w) else ""
    last = _latest(table, m, w, q) if x != w else ""  # bars by category of a balance: the latest date only
    return {"title": f"{nice.capitalize()}{by}{' at the latest date' if last else ''}", "kpi": m, "spec": {"$schema": SCHEMA, "mark": {"type": kind}, "encoding": enc},
            "sql": f'select {", ".join(sel)} from {q(table)}{last} group by {", ".join(str(i + 1) for i in range(len(sel) - 1))} order by 1'}


def _store_tile(plane, rec: dict, pid: str, tile: dict) -> dict:
    """Check a built tile like any other and keep it, accepted: the maker chose it, no second tick is needed."""
    tables, cols = D.check_sql(plane, pid, tile["sql"])
    t = {"id": "t-" + secrets.token_hex(3), "title": tile["title"][:200], "kpi": str(tile.get("kpi") or "")[:200], "sql": tile["sql"], "spec": D.check_spec(tile["spec"], cols),
         "note": "", "state": "accepted", "tables": tables}
    rec["tiles"].append(t)
    return t


def _adopt(plane, viewer, pid: str, rec: dict, src_did: str, tid: str) -> dict:
    """A Lumen tile into this dashboard as an accepted tile: accepted in place when it is already here, copied (and checked again) when it is from another dashboard."""
    if src_did == rec["id"]:
        hit = next((x for x in rec["tiles"] if x["id"] == tid), None)
        if hit is None:
            raise Refused(404, "There is no such tile.")
        D.check_spec(hit["spec"], D.check_sql(plane, pid, hit["sql"])[1])
        hit["state"] = "accepted"
        hit["tables"] = sorted(D.tables_in(plane, hit["sql"]))
        return hit
    src = D._tile(D.get(plane, viewer, pid, src_did), tid)
    return _store_tile(plane, rec, pid, {k: src[k] for k in ("title", "kpi", "sql", "spec")})


def _add_item(rec: dict, kind: str, tile: dict | None, row, col, size: str, text: str = "") -> dict:
    lay = _layout(rec)
    item = {"id": "w-" + secrets.token_hex(3), "kind": kind, "tile": tile["id"] if tile else None, "title": (tile or {}).get("title") or "Note", "text": text[:1000],
            "row": row, "col": col, "size": _fit(lay, row, col, size)}
    lay["items"].append(item)
    return item


def add_widget(plane, viewer, pid: str, did: str, body: dict) -> dict:
    """Put a widget in a slot: {kind, table?, measure?, when?, split?, text?} or {kind: "lumen", dashboard_id, tile_id}, plus {row, col, size?}."""
    rec = _editor(plane, viewer, pid, did)
    D.begin_edit(rec, viewer)
    kind, size, row, col = str(body.get("kind") or ""), str(body.get("size") or "medium"), body.get("row"), body.get("col")
    _fit(_layout(rec), row, col, size)  # refuse a bad slot before any tile is made
    if kind == "note":
        text = str(body.get("text") or "").strip()
        if not text:
            raise Refused(400, "Write the note.")
        item, tile = _add_item(rec, "note", None, row, col, size, text), None
    elif kind == "lumen":
        tile = _adopt(plane, viewer, pid, rec, str(body.get("dashboard_id") or did), str(body.get("tile_id") or ""))
        item = _add_item(rec, "lumen", tile, row, col, size)
    elif kind in KINDS:
        tile = _store_tile(plane, rec, pid, build_tile(plane, pid, kind, str(body.get("table") or ""), body.get("measure"), body.get("when"), body.get("split")))
        item = _add_item(rec, kind, tile, row, col, size)
    else:
        raise Refused(400, "Choose a widget from the library.")
    D._save(plane, rec)
    return item


def set_layout(plane, viewer, pid: str, did: str, body: dict) -> dict:
    """Positions and sizes after a move, a resize, a removal or a new row: {rows?, items: [{id, row, col, size, title?, text?}], title?, company_wide?}.
    An item left out of `items` is taken off the grid (its tile stays in the library). `rev` (from the view) is the copy the editor
    started from: when someone saved since, the change is refused with 409 rather than silently overwriting theirs.
    ponytail: the lock is per process; two web processes saving in the same few ms can both pass until dashboards move to StateStore."""
    with lock_for(D._file(plane, pid, did)):
        return _set_layout(plane, viewer, pid, did, body)


CONFLICT = "Someone else changed this dashboard since you opened it. Reload to see their change, then make yours again."


def _set_layout(plane, viewer, pid: str, did: str, body: dict) -> dict:
    rec = _editor(plane, viewer, pid, did)
    if "rev" in body and body["rev"] != int(rec.get("rev") or 0):
        raise Refused(409, CONFLICT)
    D.begin_edit(rec, viewer)
    lay, sent = _layout(rec), body.get("items")
    if not isinstance(sent, list):
        raise Refused(400, "The layout could not be read.")
    by_id = {i["id"]: i for i in lay["items"]}
    items = []
    for s in sent:
        old = by_id.get(s.get("id")) if isinstance(s, dict) else None
        if old is None:
            raise Refused(400, "The layout names a widget that is not on this dashboard.")
        new = dict(old, row=s.get("row"), col=s.get("col"), size=s.get("size"))
        if "h" in s:  # rows tall, from dragging the corner
            new["h"] = s["h"]
        if old["kind"] == "note" and isinstance(s.get("text"), str):
            new["text"] = s["text"].strip()[:1000]
        if isinstance(s.get("title"), str) and s["title"].strip():
            new["title"] = s["title"].strip()[:200]
        items.append(new)
    rows = body.get("rows", lay["rows"])
    if not isinstance(rows, int) or not 1 <= rows <= ROWS_MAX:
        raise Refused(400, "A dashboard can have between 1 and 40 rows.")
    cand = {"rows": rows, "items": items}
    if any(not isinstance(i["row"], int) or not isinstance(i["col"], int) for i in items):
        raise Refused(400, "A widget needs a row and a column.")
    _check_grid(cand)
    rec["layout"] = cand
    if isinstance(body.get("title"), str) and body["title"].strip():
        rec["title"] = body["title"].strip()[:200]
    if isinstance(body.get("company_wide"), bool):
        D.ensure_lifecycle(rec)["company_wide"] = body["company_wide"]
    return D._save(plane, rec)


def _how(out: dict) -> dict:
    """How Lumen worded the answer (model or rules) and its note, passed through so the studio can say so."""
    return {"worded_by": out.get("worded_by", "rules"), **({"note": out["note"]} if out.get("note") else {})}


POINTER = "Dashboards are built in Build › Dashboard studio."


def _first_free(layout: dict, size: str = "medium") -> tuple[int, int]:
    """The first slot with room for `size`, reading rows top to bottom; a new row (up to the limit) when the grid is full."""
    need = D.SIZES[size]
    for r in range(layout["rows"]):
        for c in range(12 - need + 1):
            if free_width(layout, r, c) >= need:
                return r, c
    if layout["rows"] >= ROWS_MAX:
        raise Refused(400, "The grid is full. Remove a widget first.")
    layout["rows"] += 1
    return layout["rows"] - 1, 0


def ask_lumen(plane, viewer, pid: str, did: str, body: dict) -> dict:
    """The Consume conversation, moved here (OP1): Lumen's own ask runs on this dashboard, with its memory, its follow-ups on the last tile and its
    rules-only note. Nothing is placed: a proposal is a tile waiting for Accept or Not this (accept_tile). With a widget selected, the follow-up is about
    that widget's tile; a new version of a placed tile replaces it in place when accepted."""
    rec = _editor(plane, viewer, pid, did)
    if D.status_of(rec) == "submitted":
        D.begin_edit(rec)  # refuses with the plain sentence
    if body.get("new_talk") is True:
        return L.new_talk(plane, viewer, pid, did) | {"proposals": []}
    text, sel = str(body.get("text") or "").strip(), body.get("widget")
    if not text and not body.get("reading"):
        raise Refused(400, "Tell Lumen what you want to see.")
    here = next((i for i in _layout(rec)["items"] if i["id"] == sel), None) if sel else None
    if sel and here is None:
        raise Refused(404, "There is no such widget.")
    if here is not None and here.get("tile"):
        M.note(plane, viewer, "lumen", L._convo(pid, did), "person", "", {"project": pid, "dashboard": did, "tile": here["tile"]})  # the follow-up is about this widget
    out = L.ask(plane, viewer, pid, did, text, str(body.get("reading") or ""), body.get("no_client_figures") is True)
    return {"reply": out.get("reply", ""), "proposals": out.get("proposals") or [], "edited": bool(out.get("edited")), "remembered": out.get("remembered"),
            "trace_id": out.get("trace_id"), **_how(out)}


def _writable(plane, viewer, pid: str, did: str) -> dict:
    rec = _editor(plane, viewer, pid, did)
    if D.status_of(rec) == "submitted":
        D.begin_edit(rec)
    return rec


def accept_tile(plane, viewer, pid: str, did: str, tid: str, body: dict) -> dict:
    """Accept: the proposed tile goes in the chosen slot, or the first free one (a row is added when there is none). A new version of a tile that is
    already on the grid takes its place there."""
    rec = _writable(plane, viewer, pid, did)
    t = D._tile(rec, tid)
    old = t.get("replaces")
    lay = _layout(rec)
    here = next((i for i in lay["items"] if old and i.get("tile") == old), None)
    size, row, col = str(body.get("size") or "medium"), body.get("row"), body.get("col")
    if here is None and row is not None:
        _fit(lay, row, col, size)  # a bad slot is refused before the tile is accepted
    D.begin_edit(rec, viewer)
    D._save(plane, rec)
    D.decide(plane, viewer, pid, did, tid, True)
    rec = D._load(plane, pid, did)
    tile = D._tile(rec, tid)
    tile.setdefault("tables", sorted(D.tables_in(plane, tile["sql"])))
    lay = _layout(rec)
    item = next((i for i in lay["items"] if old and i.get("tile") == old), None)
    if item:
        item.update(tile=tile["id"], title=tile["title"], kind="lumen")
    else:
        if row is None:
            row, col = _first_free(lay, size if size in D.SIZES else "medium")
        item = _add_item(rec, "lumen", tile, row, col, size)
    D._save(plane, rec)
    return item


def reject_tile(plane, viewer, pid: str, did: str, tid: str) -> dict:
    _writable(plane, viewer, pid, did)
    return D.decide(plane, viewer, pid, did, tid, False)


# ---- the screen's one read -------------------------------------------------------------------------------------------------------

def _unplaced(plane, viewer, pid: str, rec: dict) -> list[dict]:
    """Every tile Lumen has made for this project (any dashboard the person may open) that is not on this grid."""
    placed = {i.get("tile") for i in _layout(rec)["items"]}
    out = []
    for s in D.list_for(plane, viewer, pid) + [{"id": rec["id"]}]:
        with suppress(Refused):
            r = rec if s["id"] == rec["id"] else D.get(plane, viewer, pid, s["id"])
            out += [{"dashboard_id": r["id"], "tile_id": t["id"], "title": t["title"], "state": t["state"], "reads": [_label(x) for x in t.get("tables", [])]}
                    for t in r["tiles"] if not (r["id"] == rec["id"] and t["id"] in placed)]
    return list({(o["dashboard_id"], o["tile_id"]): o for o in out}.values())


def _last_live_words(plane, pid: str) -> str:
    """UC5 N-1: with no business review of the figures, say what is on record (the latest live run), never that no run exists."""
    from sh_platform.v1 import b6_run
    live = next((r for r in b6_run.runs(plane, pid) if r.get("mode") == "live"), None)
    if not live:
        return "No live run is on record for this project yet, so Lumen could not compare the numbers."
    return (f"The latest live run, {live['run_id']} on {str(live.get('started') or '')[:10]}, finished {'ok' if live.get('status') == 'ok' else 'with a failure'}. "
            "No one has reviewed its figures against a report yet, so Lumen did not compare them.")


def _review(plane, viewer, pid: str, rec: dict, lc: dict, items: list[dict]) -> dict:
    """Design D3, for the person who approves: who built it and sent it, and "What Lumen checked", each line from a record and never worded as a pass
    when the record is missing (ok is True, False or None for not checked). Nothing here is the approver's to edit."""
    from sh_platform.v1 import b9_verify, p1_project
    fl = None
    with suppress(Exception):
        fl = b9_verify.figure_lines(plane, viewer, pid)
    shown = [i for i in items if i.get("kind") != "note"]
    unnamed = [i["title"] for i in shown if not i.get("reads")]
    reads = sorted({r for i in shown for r in i.get("reads") or []})
    people: list[str] = []
    with suppress(Exception):
        people = list(dict.fromkeys(n for n in (p1_project.read(plane, pid).get("people") or {}).values() if n))
    names = k3_map._audience_names(plane)
    month = (fl or {}).get("month_name")
    checks = [
        ({"title": f"The {month} numbers were accepted", "ok": bool(fl["accepted_by"]),
          "detail": f"Portfolio {fl['portfolio_pct']}%, benchmark {fl['benchmark_pct']}% and {fl['difference_pts']} points" + (f"; {fl['accepted_by']} accepted them." if fl["accepted_by"] else "; the business owner has not accepted them yet.")}
         if fl else {"title": "The month's numbers", "ok": None, "detail": _last_live_words(plane, pid)}),
        ({"title": "Every tile names where it comes from", "ok": not unnamed, "detail": ("Reads " + ", ".join(reads) + ".") if not unnamed else f"{len(unnamed)} tile{'s' if len(unnamed) != 1 else ''} name no source: {', '.join(unnamed[:3])}."}
         if shown else {"title": "Every tile names where it comes from", "ok": None, "detail": "There are no figure tiles on this dashboard."}),
        ({"title": "The benchmark is the signed definition", "ok": True, "detail": f"Version {fl['version']}" + (f", {fl['name']}" if fl.get("name") else "") + "."}
         if fl and fl.get("version") else {"title": "The benchmark is the signed definition", "ok": None, "detail": "No signed benchmark version is on record for this project."}),
        ({"title": "Readers are the people on the project", "ok": True, "detail": ", ".join(people) + "."}
         if people else {"title": "Readers are the people on the project", "ok": None, "detail": "The project names nobody yet."}),
    ]
    return {"built_by": names.get(str(rec["created_by"])), "submitted_by": lc.get("submitted_by_name") or lc.get("submitted_by"), "submitted_at": lc.get("submitted_at"), "checks": checks}


def view(plane, viewer, pid: str, did: str, now: datetime | None = None) -> dict:
    rec = open_rec(plane, viewer, pid, did)
    lc = D.ensure_lifecycle(dict(rec)) if rec.get("lifecycle") is None else rec["lifecycle"]
    mine = D.who(viewer) == rec["created_by"] or ("company_admin" in set(viewer.roles)) or (bool(rec.get("starter")) and is_maker(viewer))
    tables = D.gold_tables(plane, pid) if is_maker(viewer) else []
    layout = dict(_layout(dict(rec)))
    tiles = {t["id"]: t for t in rec["tiles"]}
    items = [i | {"reads": [_label(x) for x in tiles.get(i.get("tile"), {}).get("tables") or D.tables_in(plane, tiles[i["tile"]]["sql"])]} if i.get("tile") in tiles else i
             for i in layout["items"]]
    return {"id": rec["id"], "project_id": pid, "title": rec["title"], "rev": int(rec.get("rev") or 0), "status": lc["status"], "version": lc["version"], "published_version": (lc.get("published") or {}).get("version"),
            "sent_back": lc.get("sent_back"), "submitted_by": lc.get("submitted_by_name") or lc.get("submitted_by"), "submitted_at": lc.get("submitted_at"),
            "approved_by": lc.get("approved_by_name"), "approved_at": lc.get("approved_at"), "company_wide": bool(lc.get("company_wide")),
            "layout": {"rows": layout["rows"], "items": items}, "tiles": [{"id": t["id"], "title": t["title"], "state": t["state"], "spec": t["spec"], "kpi": t.get("kpi", ""), "note": t.get("note", ""), "replaces": t.get("replaces"),
                       **({"starter": True, "trail": t.get("trail")} if t.get("starter") else {})} for t in rec["tiles"]],
            "starter": rec.get("starter"),
            "talk": L.talk(plane, viewer, pid, did) if is_maker(viewer) else [],
            "can": {"edit": mine and lc["status"] != "submitted" and is_maker(viewer), "submit": mine and lc["status"] == "draft" and is_maker(viewer), "approve": D.can_approve(viewer, rec)},
            "review": _review(plane, viewer, pid, rec, lc, items) if D.can_approve(viewer, rec) else None,
            "library": {"kinds": list(KINDS), "tables": [{"name": t["name"], "label": _label(t["name"]), "columns": t["columns"]} for t in tables],
                        "lumen": _unplaced(plane, viewer, pid, rec) if is_maker(viewer) else []},
            "refresh": refresh_status(plane, pid, now)}


# ---- H10: Lumen's starter dashboard -----------------------------------------------------------------------------------------------

def _starter_of(plane, pid: str) -> dict | None:
    for p in sorted(D._dir(plane, pid).glob("dash-*.json")):
        with suppress(OSError, ValueError, Refused, KeyError, TypeError):
            rec = D.read_json_strict(p, dict)
            if rec and rec.get("starter"):
                return rec
    return None


def start_starter(plane, pid: str) -> dict | None:
    """When a pipeline goes live: Lumen's starter as a draft in the studio (once per project). Tiles wait as proposals, placed on the grid, until
    Accept; nothing is shown in Consume before an approval. None when the project has no gold figure to show yet."""
    if (had := _starter_of(plane, pid)) is not None:
        return had
    plan = L.propose_starter(plane, pid)
    if not plan["tiles"]:
        return None
    rec = D.create(plane, LUMEN, pid, "Lumen's starter dashboard", draft=True)
    did, items = rec["id"], []
    for t in plan["tiles"]:
        made = D.add_proposal(plane, LUMEN, pid, did, {k: t[k] for k in ("title", "kpi", "sql", "spec", "note", "recipe") if k in t})
        items.append((made["id"], t["place"], t["trail"]))
    rec = D._load(plane, pid, did)
    for tid, place, trail in items:
        tile = D._tile(rec, tid)
        tile |= {"starter": True, "trail": trail, "tables": sorted(D.tables_in(plane, tile["sql"]))}
        rec["layout"]["items"].append({"id": "w-" + secrets.token_hex(3), "kind": "lumen", "tile": tid, "title": tile["title"], "text": "", **place})
    if plan["checks"]:
        rec["layout"]["items"].append({"id": "w-" + secrets.token_hex(3), "kind": "note", "tile": None, "title": "Checks status", "text": plan["checks"][:1000], "row": 1, "col": 9, "size": "small"})
    rec["layout"]["rows"] = max(i["row"] for i in rec["layout"]["items"]) + 1
    rec["starter"] = {"status": "proposed", "pack_version": plan["pack_version"], "why": plan["why"], "from_intent": plan["from_intent"], "at": D._now()}
    return D._save(plane, rec)


def accept_starter(plane, viewer, pid: str, did: str) -> dict:
    """Accept as it is: every starter tile still on the grid is accepted; one the person already removed is dropped. Adding something specific or sending
    for approval goes on from here (the existing Lumen conversation and approval)."""
    rec = _writable(plane, viewer, pid, did)
    if (rec.get("starter") or {}).get("status") != "proposed":
        raise Refused(409, "There is no starter dashboard waiting for you here.")
    placed = {i.get("tile") for i in _layout(rec)["items"]}
    D.begin_edit(rec, viewer)
    D._save(plane, rec)
    for t in [t for t in rec["tiles"] if t.get("starter") and t["state"] == "proposed"]:
        D.decide(plane, viewer, pid, did, t["id"], t["id"] in placed)
    rec = D._load(plane, pid, did)
    rec["starter"] |= {"status": "accepted", "accepted_by": getattr(viewer, "name", "") or D.who(viewer), "accepted_at": D._now()}
    D._save(plane, rec)
    return view(plane, viewer, pid, did)


def delete_draft(plane, viewer, pid: str, did: str) -> None:
    """A draft that was never published goes for good. A published one (or its next version) and one waiting for approval stay: Consume or an approver relies on them."""
    with lock_for(D._file(plane, pid, did)):
        rec = _editor(plane, viewer, pid, did)
        if D.status_of(rec) != "draft" or (rec.get("lifecycle") or {}).get("published"):
            raise Refused(409, "Only a draft that was never published can be deleted.")
        D._file(plane, pid, did).unlink(missing_ok=True)


def create(plane, viewer, pid: str, title: str) -> dict:
    return D.create(plane, viewer, pid, title, draft=True)


def tile_data(plane, viewer, pid: str, did: str, tid: str) -> dict:
    return D.tile_rows(plane, pid, open_rec(plane, viewer, pid, did), tid)


# ---- refresh facts: from the project's schedule and runs, and the sources' health ---------------------------------------------------

def next_slot(sched: dict, now: datetime) -> datetime | None:
    last = SCH.last_slot(sched, now)
    if last is None:
        return None
    f = sched.get("freq")
    if f == "daily":
        return last + timedelta(days=1)
    if f == "weekly":
        return last + timedelta(days=7)
    first = (last.replace(day=1) + timedelta(days=32)).replace(day=1)  # monthly
    return first.replace(day=SCH._dom(sched), hour=last.hour, minute=last.minute)


def _short(d: datetime) -> str:
    return f"{d.day} {d.strftime('%b')}"


def schedule_words(sched: dict) -> str:
    at, f = str(sched.get("at") or "06:00"), sched.get("freq")
    if f == "weekly":
        return f"Updated every {_DAYS[SCH._weekday(sched)]} at {at} after the pipeline run"
    if f == "monthly":
        return f"Updated on day {SCH._dom(sched)} of each month at {at} after the pipeline run"
    return {"daily": f"Updated daily at {at} after the pipeline run",
            "on_arrival": "Updated after the pipeline run, which starts when a source file arrives"}.get(f, "Updated only when the pipeline is run by hand")


def refresh_status(plane, pid: str, now: datetime | None = None) -> dict:
    """What the header of every dashboard says about freshness; `warning` is set when the last run failed or a source feeding the project is late."""
    now = now or datetime.now()
    plan = R.latest_plan(plane, pid, live=True)
    sched = (plan or {}).get("schedule") or {}
    runs = [r for r in R.runs(plane, pid, 50) if r.get("mode") == "live"]
    ok = next((r for r in runs if r.get("status") == "ok"), None)
    failed = bool(runs) and runs[0].get("status") == "failed"
    nxt = next_slot(sched, now) if plan and plan.get("state") in R.LIVE_OK else None
    last = (ok or {}).get("finished") or (ok or {}).get("started")
    since = f"since {_short(datetime.fromisoformat(last).astimezone().replace(tzinfo=None))}" if last else "yet"
    late = []
    if plan:
        codes = {s.get("code") for s in plan.get("sources") or []}
        try:
            late = [s for s in k3_map.health(plane, Viewer(name="studio", roles=frozenset({"company_admin"}))).get("sources", []) if s["code"] in codes and s["is_late"]]
        except Exception:  # noqa: BLE001 - freshness must always open
            late = []
    warning = None
    if late:
        warning = f"Not refreshed {since}: " + " and ".join(f"the {s['name']} file is late" for s in late)
    elif failed:
        warning = f"The last refresh failed on {_short(datetime.fromisoformat(runs[0]['started']).astimezone().replace(tzinfo=None))}, so these figures are not refreshed {since}"
    return {"schedule": sched.get("freq"), "words": schedule_words(sched) if plan else "No pipeline yet: Build has not planned how this project is refreshed",
            "last_refreshed": last, "next": nxt.astimezone().isoformat(timespec="minutes") if nxt else None,
            "warning": warning, "link": MAP_HEALTH if warning else None, "late_sources": [s["name"] for s in late], "last_run_failed": failed}
