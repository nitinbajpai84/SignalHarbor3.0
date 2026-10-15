"""STUDIO2 card C: Lumen offers three presentations of one tile's data. Deterministic, no model call: the options come from the table's columns, and the
pick from the words the person used ("per day" -> a trend). Each patch is applied by the client with PATCH .../tiles/{tid} (kind, measure, split, when, only, title)."""
from __future__ import annotations

from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import cx_lumen as L
from sh_platform.v1.p1_project import Refused
from sh_platform.v1 import teach as T

# what Lumen looks up in what it was taught (Settings > Teach the agents) to back each kind of option; words only, no model call
BOOK = {"trend": "line chart trend over time axis start near the data", "latest": "bar chart compare categories start at zero sorted",
        "table": "table exact figures detail lookup", "target": "bullet graph against target benchmark comparison",
        "multiples": "small multiples same scale compare groups", "area": "area chart stacked parts of a whole",
        "figure": "headline figure with a comparison prior period target"}

# what the person said -> the kind of option it points at; the first phrase found (reading the person's words left to right) wins
CUES = {
    "trend": ("per day", "per week", "per month", "per year", "daily", "weekly", "monthly", "over time", "trend", "history", "growth", "since"),
    "latest": ("compare", "versus", " vs ", "biggest", "largest", "rank", "top ", "which", "latest", "right now", "today", "current"),
    "table": ("change", "moved", "difference", "previous", "list", "the numbers", "detail"),
    "target": ("target", "budget", "goal", "against", "benchmark"),
}


def _words_said(plane, viewer, pid: str, did: str, tile: dict, text: str) -> str:
    """The person's words for this tile: what they just typed, else their last line to Lumen on this dashboard, else the tile's own title."""
    if text.strip():
        return text.strip()
    said = [x["text"] for x in L.talk(plane, viewer, pid, did) if x["by"] == "person" and x["text"]]
    return (said[-1] if said else "") or tile.get("title", "")


def _cue(said: str) -> tuple[str, str] | None:
    low = " " + said.lower() + " "
    hits = [(low.index(p), kind, p.strip()) for kind, ps in CUES.items() for p in ps if p in low]
    return min(hits)[1:] if hits else None


def options(plane, viewer, pid: str, did: str, tid: str, text: str = "") -> dict:
    rec = S.open_rec(plane, viewer, pid, did)
    tile = D._tile(rec, tid)
    names = set(tile.get("tables") or D.tables_in(plane, tile["sql"]))
    table = next((t for t in D.gold_tables(plane, pid) if t["name"] in names), None)
    if table is None:
        raise Refused(400, "Lumen can only suggest other views of a tile that reads one of this project's tables.")
    cols = table["columns"]
    spec_cols = {e.get("field") for e in (tile["spec"].get("encoding") or {}).values() if isinstance(e, dict)}
    num = [c["name"] for c in cols if c["type"].lower().startswith(S._NUM) and not c["name"].endswith("_id")]
    m = tile.get("kpi") if tile.get("kpi") in num else next(iter(num), None)
    w = S._pick(cols, None, S._DATE)
    s = next((f for f in spec_cols if f in {c["name"] for c in cols} and f not in (w, m) and f not in num), None) or S._pick(cols, None, ("varchar", "text"), skip=(w or "", m or ""))
    if not m:
        raise Refused(400, "This table has no number column, so there is nothing to draw another way.")
    nm, ns = S._words(m), S._words(s or "")
    pol = [] if not w else [("trend", f"{nm.capitalize()} over time" + (f", a line for each {ns}" if s else ""), "Shows how it moves, which a single latest figure hides.",
                            {"kind": "line", "measure": m, "when": w, **({"split": s} if s else {})})]
    if s:
        latest = None
        if w:
            latest = next(iter(D.run_sql(plane, f'select max("{w}") as latest from "{table["name"]}"')[1][0].values()))
        pol.append(("latest", f"Bars for the latest period, by {ns}" if w else f"Bars of {nm} by {ns}", "Easiest way to compare who is biggest right now.",
                    {"kind": "bar", "measure": m, "split": s, **({"when": w, "only": {"column": w, "values": [str(latest)[:10]]}} if latest is not None else {})}))
    pol.append(("table", f"A table of {nm}" + (f" with the change on the previous {S._words(w)}" if w else ""), "Exact numbers, so nothing is lost to the picture.",
                {"kind": "table", "measure": m, **({"when": w} if w else {}), "title": f"{nm.capitalize()}, by period" if w else nm.capitalize()}))
    tgt = next((c["name"] for c in cols if c["name"] != m and c["name"].startswith(("target", "budget", "benchmark", "goal")) and c["name"] in num), None)  # a number to compare against, never benchmark_code
    if "bullet" in S.KINDS and tgt:
        pol.append(("target", f"{nm.capitalize()} against {S._words(tgt)}", "Shows at a glance whether it is on target.", {"kind": "bullet", "measure": m}))
    if "small_multiples" in S.KINDS and w and s:
        pol.append(("multiples", f"A small chart for each {ns}", "One small line per group on the same scale, so each shape is clear and they still compare fairly.", {"kind": "small_multiples", "measure": m, "when": w, "split": s}))
    if w:
        pol.append(("area", f"{nm.capitalize()} as areas" + (f", stacked by {ns}" if s else ""), "Shows the total and its make-up together.", {"kind": "area", "measure": m, "when": w, **({"split": s} if s else {})}))
    pol.append(("figure", f"{nm.capitalize()} as one number", "A single figure for a header or a glance.", {"kind": "figure", "measure": m, **({"when": w} if w else {})}))

    said = _words_said(plane, viewer, pid, did, tile, text)
    cue = _cue(said)
    mark = tile["spec"].get("mark")
    cur = (mark.get("type") if isinstance(mark, dict) else mark) or ""
    if cue and any(p[0] == cue[0] for p in pol):
        pick, why = cue[0], f'You said "{cue[1]}", so '
    else:
        pick, why = pol[0][0], "Nothing in your words points one way, so "
    # offer the pick first and never repeat the presentation the tile already has when another is available
    rest = [p for p in pol if p[0] != pick and p[3]["kind"] != (cur if cur != "text" else tile["spec"].get("usermeta", {}).get("view"))]
    first = next(p for p in pol if p[0] == pick)
    three = ([first] + rest + [p for p in pol if p not in rest and p is not first])[:3]
    return {"options": [{"label": lab, "why": (why + lab[0].lower() + lab[1:] + " is the best fit.") if key == pick else ex, "patch": patch, "pick": key == pick,
                         **_book(plane, key)} for key, lab, ex, patch in three]}


def _book(plane, key: str) -> dict:
    """{book: {line, used}}: the taught rule (from Lumen's rule notes, in the office's own words, never raw book pages) that best backs this kind of
    chart, or {} when nothing taught fits. Words only, no model call; never raises."""
    import re
    from sh_platform.v1 import doc_index
    try:
        notes = {i["path"]: i for i in T._items(plane) if i["agent"] == "lumen" and i["kind"] == "note" and i["active"]}
        if not notes:
            return {}
        want = set(BOOK.get(key, key).split())
        best = None
        for h in doc_index.search(plane, list(notes), BOOK.get(key, key), limit=6):
            for rule in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])|\s\d{1,2}\.\s|\s-\s|#+", " ".join(h["text"].split())):
                rule = rule.strip(" -*#")
                score = len(want & set(re.findall(r"[a-z]+", rule.lower())))
                if 30 < len(rule) < 240 and not rule.lower().startswith(("source", "check:", "example")) and (best is None or score > best[0]):
                    best = (score, rule, h)
        if not best or best[0] < 2:
            return {}
        item = notes[best[2]["path"]]
        return {"book": {"line": best[1], "used": f"Used: {' '.join(item['title'].split())[:80]}"}}
    except Exception:  # noqa: BLE001 - the options never depend on what was taught
        return {}
