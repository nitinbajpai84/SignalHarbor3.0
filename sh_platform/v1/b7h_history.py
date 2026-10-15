"""STUDIO2 card A: talk, history and the inspector, on top of b7_studio.

- talk: Lumen's proposals are placed at once (b7_studio.ask_lumen, then accept_tile for each).
- history: `rec["steps"]` (cap 50) holds {n, at, by, said, summary, snapshot}; a snapshot is the layout, the title and a copy of each tile the layout uses,
  so a step can be restored even after its tile was replaced. `rec["step_now"]` is the n whose state is on screen. Every change calls `record_step`.
- inspector: change one tile (kind, measure, split, when, only, title), duplicate or delete a widget."""
from __future__ import annotations

import copy
import re

from sh_platform.jsonfile import lock_for
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1.p1_project import Refused

CAP = 50
TILE_KEYS = ("id", "title", "kpi", "sql", "spec", "note", "state", "tables", "build")


def _by(viewer) -> str:
    return getattr(viewer, "name", "") or D.who(viewer)


def _snapshot(rec: dict) -> dict:
    lay = S._layout(rec)
    used = {i.get("tile") for i in lay["items"]}
    return copy.deepcopy({"title": rec["title"], "layout": lay,
                          "tiles": [{k: t[k] for k in TILE_KEYS if k in t} for t in rec["tiles"] if t["id"] in used]})


def _baseline(rec: dict) -> dict:
    """The state before the first recorded step: the published version if there is one, else an empty grid.
    ponytail: a draft with content made before history existed has no earlier state to go back to."""
    pub = (rec.get("lifecycle") or {}).get("published")
    if pub:
        return copy.deepcopy({"title": pub["title"], "layout": pub.get("layout") or {"rows": 2, "items": []}, "tiles": pub.get("tiles") or []})
    return {"title": rec["title"], "layout": {"rows": 2, "items": []}, "tiles": []}


def _add_step(rec: dict, viewer, said: str, summary: str, snap: dict, back_to: int | None = None) -> int:
    steps = rec.setdefault("steps", [])
    if not steps:
        steps.append({"n": 0, "at": D._now(), "by": "", "said": "", "summary": "Started", "snapshot": _baseline(rec)})
    n = steps[-1]["n"] + 1
    steps.append({"n": n, "at": D._now(), "by": _by(viewer), "said": str(said or "")[:500], "summary": str(summary or "")[:300], "snapshot": snap,
                  **({"from": back_to} if back_to is not None else {})})
    del steps[:-CAP]
    rec["step_now"] = n
    return n


def record_step(plane, viewer, pid: str, did: str, said: str, summary: str) -> int:
    """Call after any change to a studio dashboard has been saved: keeps the state as a step and returns its number."""
    with lock_for(D._file(plane, pid, did)):
        rec = D._load(plane, pid, did)
        n = _add_step(rec, viewer, said, summary, _snapshot(rec))
        D._save(plane, rec)
        return n


def history(plane, viewer, pid: str, did: str) -> dict:
    rec = S.open_rec(plane, viewer, pid, did)
    steps = rec.get("steps") or []
    return {"steps": [{k: s[k] for k in ("n", "at", "by", "said", "summary")} for s in steps], "now": rec.get("step_now", steps[-1]["n"] if steps else 0)}


def _step(rec: dict, n) -> dict:
    s = next((x for x in rec.get("steps") or [] if x["n"] == n), None)
    if s is None:
        raise Refused(404, "There is no such step.")
    return s


def _apply(rec: dict, snap: dict) -> None:
    snap = copy.deepcopy(snap)
    have = {t["id"] for t in rec["tiles"]}
    rec["tiles"] += [t for t in snap["tiles"] if t["id"] not in have]
    rec["layout"], rec["title"] = snap["layout"], snap["title"]


def restore(plane, viewer, pid: str, did: str, n: int, said: str = "") -> dict:
    """Make step n the working copy again. The restore is itself a new step, so it can be undone."""
    with lock_for(D._file(plane, pid, did)):
        rec = S._writable(plane, viewer, pid, did)
        s = _step(rec, n)
        D.begin_edit(rec, viewer)
        before = rec.get("step_now")
        _apply(rec, s["snapshot"])
        new = _add_step(rec, viewer, said, f"Went back to step {n}", copy.deepcopy(s["snapshot"]), back_to=before)
        D._save(plane, rec)
        return {"ok": True, "step": new}


def undo(plane, viewer, pid: str, did: str) -> dict:
    """One step back: before the current step, or (when the current step was a restore) the state it replaced."""
    rec = S._writable(plane, viewer, pid, did)
    steps = rec.get("steps") or []
    now = _step(rec, rec.get("step_now", steps[-1]["n"] if steps else -1)) if steps else None
    if now is None:
        raise Refused(409, "There is nothing to undo.")
    target = now.get("from")
    if target is None:
        i = steps.index(now)
        if i == 0:
            raise Refused(409, "There is nothing to undo.")
        target = steps[i - 1]["n"]
    if not any(s["n"] == target for s in steps):
        raise Refused(409, "That earlier step is no longer kept.")
    return restore(plane, viewer, pid, did, target, "Undo")


def _titles(snap: dict) -> dict[str, tuple]:
    tiles = {t["id"]: t for t in snap["tiles"]}
    return {i["id"]: (i["title"], i.get("text"), (tiles.get(i.get("tile")) or {}).get("sql"), repr((tiles.get(i.get("tile")) or {}).get("spec"))) for i in snap["layout"]["items"]}


def compare(plane, viewer, pid: str, did: str, n: int) -> dict:
    """Step n against what is on screen now: `added` is in the dashboard now and not in step n, `removed` was in step n and is gone,
    `changed` is the same widget with other content (its title now)."""
    rec = S.open_rec(plane, viewer, pid, did)
    old, cur = _titles(_step(rec, n)["snapshot"]), _titles(_snapshot(rec))
    return {"added": [cur[w][0] for w in cur if w not in old], "removed": [old[w][0] for w in old if w not in cur],
            "changed": [cur[w][0] for w in cur if w in old and cur[w] != old[w]]}


def withdraw(plane, viewer, pid: str, did: str) -> dict:
    """A submitted dashboard goes back to a draft so it can be edited again."""
    with lock_for(D._file(plane, pid, did)):
        rec = S._editor(plane, viewer, pid, did)
        lc = D.ensure_lifecycle(rec)
        if lc["status"] != "submitted":
            raise Refused(409, "Only a dashboard waiting for approval can be withdrawn.")
        lc.update(status="draft", sent_back=None)
        D.begin_edit(rec, viewer)
        n = _add_step(rec, viewer, "", "Took it back from approval", _snapshot(rec))
        D._save(plane, rec)
        return {"ok": True, "status": "draft", "step": n}


# ---- talk ---------------------------------------------------------------------------------------------------------------------------

def talk(plane, viewer, pid: str, did: str, body: dict) -> dict:
    """Ask Lumen and put what it proposes on the grid at once: the first proposal replaces the selected widget's tile, the rest take the first free slots."""
    out = S.ask_lumen(plane, viewer, pid, did, body)
    changed: list[str] = []
    sel = body.get("widget")
    for k, p in enumerate(out.get("proposals") or []):
        if k == 0 and sel:
            rec = D._load(plane, pid, did)
            here = next((i for i in S._layout(rec)["items"] if i["id"] == sel), None)
            if here and here.get("tile") and not p.get("replaces"):
                D._tile(rec, p["id"])["replaces"] = here["tile"]
                D._save(plane, rec)
        changed.append(S.accept_tile(plane, viewer, pid, did, p["id"], {})["id"])
    said = str(body.get("text") or "")
    step = record_step(plane, viewer, pid, did, said, f"Lumen placed {len(changed)} widget{'s' if len(changed) != 1 else ''}") if changed else history(plane, viewer, pid, did)["now"]
    reply = str(out.get("reply", "")).replace("It is waiting for you: accept it or choose Not this.", "It is on the dashboard now; say what to change, or Undo.")
    return {"reply": reply.replace("I have proposed one tile", "I have placed one tile"), "changed": changed, "step": step}


# ---- inspector ----------------------------------------------------------------------------------------------------------------------

REBUILD = ("kind", "measure", "split", "when", "only")


def _with_filter(sql: str, table: str, column: str, values: list) -> str:
    """The same query with `where column in (...)` right after the table; the column was checked against the table by the caller."""
    marker = f' from "{table}"'
    i = sql.find(marker)
    if i < 0:
        raise Refused(400, "This widget cannot be filtered.")
    lit = ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)
    j = i + len(marker)
    rest = sql[j:]
    if rest.lstrip().lower().startswith("where "):  # the tile already keeps only the latest date: both conditions hold
        rest = " and " + rest.lstrip()[6:]
    return f'{sql[:j]} where "{column}" in ({lit}){rest}'


STYLE = ("scale_zero", "stack", "number_format")


def _style(plane, pid: str, tile: dict, body: dict) -> None:
    """scale_zero / stack / number_format written into the chart's y (or, for a figure, text) encoding, then the spec is checked again."""
    enc = tile["spec"].setdefault("encoding", {})
    target = enc.get("y") or enc.get("text")
    if not isinstance(target, dict):
        raise Refused(400, "This widget has no axis or figure to style.")
    if isinstance(body.get("scale_zero"), bool):
        target.setdefault("scale", {})["zero"] = body["scale_zero"]
    if isinstance(body.get("stack"), bool):
        target["stack"] = body["stack"]
    if "number_format" in body:
        if body["number_format"] not in ("currency", "percent", "number"):
            raise Refused(400, "Choose currency, percent or number.")
        target["format"] = body["number_format"]
    tile["spec"] = D.check_spec(tile["spec"], D.check_sql(plane, pid, tile["sql"])[1])


def _resize(rec: dict, item: dict | None, size) -> None:
    if item is None:
        raise Refused(404, "This tile is not on the grid.")
    if size not in D.SIZES:
        raise Refused(400, "Choose small, medium, wide or full.")
    lay = S._layout(rec)
    if D.SIZES[size] > S.free_width(lay, item["row"], item["col"], skip=item["id"]):
        raise Refused(400, "That size does not fit there. Move the widget or the one next to it first.")
    item["size"] = size


def _recipe(plane, pid: str, tile: dict, item: dict | None) -> dict:
    if isinstance(tile.get("build"), dict):
        return dict(tile["build"])
    mark = tile["spec"].get("mark")
    mark = mark.get("type") if isinstance(mark, dict) else mark
    kind = item["kind"] if item and item["kind"] in S.KINDS else (mark if mark in S.KINDS else (tile["spec"].get("usermeta") or {}).get("view"))
    tables = sorted(D.tables_in(plane, tile["sql"]))
    return {"kind": kind, "table": tables[0] if tables else ""}


def patch_tile(plane, viewer, pid: str, did: str, tid: str, body: dict) -> dict:
    with lock_for(D._file(plane, pid, did)):
        rec = S._writable(plane, viewer, pid, did)
        tile = D._tile(rec, tid)
        D.begin_edit(rec, viewer)
        item = next((i for i in S._layout(rec)["items"] if i.get("tile") == tid), None)
        title = str(body["title"]).strip()[:200] if isinstance(body.get("title"), str) and body["title"].strip() else None
        if any(body.get(k) not in (None, "") for k in REBUILD):
            r = _recipe(plane, pid, tile, item) | {k: body[k] for k in REBUILD if body.get(k) not in (None, "")}
            if r.get("kind") not in S.KINDS or not r.get("table"):
                raise Refused(400, "This widget cannot be rebuilt from its table.")
            built = S.build_tile(plane, pid, r["kind"], r["table"], r.get("measure"), r.get("when"), r.get("split"))
            only = body.get("only") or r.get("only")
            if only:
                cols = {c["name"] for t in D.gold_tables(plane, pid) if t["name"] == r["table"] for c in t["columns"]}
                vals = only.get("values") if isinstance(only, dict) else None
                if not isinstance(vals, list) or not vals or only.get("column") not in cols:
                    raise Refused(400, "Choose a column of this table and at least one value to keep.")
                built["sql"] = _with_filter(built["sql"], r["table"], only["column"], vals)
                r["only"] = {"column": only["column"], "values": vals}
            if title is None and tile.get("custom_title"):
                title = tile["title"]
            new = S._store_tile(plane, rec, pid, built | ({"title": title} if title else {}))
            new |= {"build": r, "tables": sorted(D.tables_in(plane, new["sql"])), **({"custom_title": True} if title else {})}
            if item:
                item |= {"tile": new["id"], "title": new["title"], "kind": r["kind"]}
            if item and not any(i.get("tile") == tid for i in S._layout(rec)["items"]):
                rec["tiles"].remove(tile)  # nothing shows the old version any more; the step keeps a copy
            summary = f"Changed {new['title']}"
        elif title:
            tile |= {"title": title, "custom_title": True}
            if item:
                item["title"] = title
            summary = f"Renamed to {title}"
        elif not any(k in body for k in STYLE + ("size",)):
            raise Refused(400, "Say what to change.")
        else:
            summary = f"Changed {tile['title']}"
        tile = next((t for t in rec["tiles"] if t["id"] == (item or {}).get("tile", tid)), tile)
        if any(k in body for k in STYLE):
            _style(plane, pid, tile, body)
            summary = f"Changed how {tile['title']} looks"
        if "size" in body:
            _resize(rec, item, body["size"])
            summary = f"Resized {tile['title']}"
        D._save(plane, rec)
    return {"ok": True, "step": record_step(plane, viewer, pid, did, "", summary)}


def duplicate_widget(plane, viewer, pid: str, did: str, wid: str) -> dict:
    with lock_for(D._file(plane, pid, did)):
        rec = S._writable(plane, viewer, pid, did)
        lay = S._layout(rec)
        src = next((i for i in lay["items"] if i["id"] == wid), None)
        if src is None:
            raise Refused(404, "There is no such widget.")
        D.begin_edit(rec, viewer)
        tile = None
        if src.get("tile"):
            old = D._tile(rec, src["tile"])
            tile = copy.deepcopy(old) | {"id": "t-" + S.secrets.token_hex(3)}
            rec["tiles"].append(tile)
        row, col = S._first_free(lay, src["size"])
        item = S._add_item(rec, src["kind"], tile, row, col, src["size"], src.get("text") or "")
        item["title"] = src["title"]
        D._save(plane, rec)
    return {"ok": True, "widget": item, "step": record_step(plane, viewer, pid, did, "", f"Copied {src['title']}")}


def delete_widget(plane, viewer, pid: str, did: str, wid: str) -> dict:
    """Off the grid; its tile stays in the library (as when a widget is left out of a layout save)."""
    with lock_for(D._file(plane, pid, did)):
        rec = S._writable(plane, viewer, pid, did)
        lay = S._layout(rec)
        gone = next((i for i in lay["items"] if i["id"] == wid), None)
        if gone is None:
            raise Refused(404, "There is no such widget.")
        D.begin_edit(rec, viewer)
        lay["items"].remove(gone)
        D._save(plane, rec)
    return {"ok": True, "step": record_step(plane, viewer, pid, did, "", f"Removed {gone['title']}")}
