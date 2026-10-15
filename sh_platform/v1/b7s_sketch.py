"""STUDIO2 card D (board 4): a paper sketch of a dashboard, read on this machine and matched to the project's gold tables.

The picture is read with the local reader (rapidocr, else ocr_local's engines) and never leaves the machine; no model is called. Each box label
is matched to a gold table and number column by words (the label, plus a small synonym list) and gets a status:
possible (a table and a measure found), needs_definition (data found but ambiguous: one question), not_possible (no data held: what source is needed).
Typed `labels` replace the picture when the reader is missing."""
from __future__ import annotations

import base64
import binascii
import difflib
import functools
import logging
import re
import threading

from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import ocr_local
from sh_platform.v1 import t2_tickets
from sh_platform.v1.p1_project import Refused

log = logging.getLogger(__name__)
PICTURE_MAX = 5 * 1024 * 1024
BOXES_MAX = 30
SYN = {  # a phrase in a label -> words to look for in table and column names
    "net worth": ["net worth", "networth", "nav", "total assets", "wealth"],
    "cash": ["cash", "balance"],
    "runway": ["runway", "burn", "cash"],
    "liquidity": ["liquidity", "liquid", "cash"],
    "capital call": ["capital call", "call", "drawdown"],
    "commitment": ["commitment", "committed"],
    "uncalled": ["uncalled", "unfunded", "undrawn"],
    "manager": ["manager", "gp"],
    "index": ["index", "benchmark"],
    "performance": ["performance", "return", "irr", "tvpi", "twr", "moic"],
    "allocation": ["allocation", "weight", "asset class", "exposure"],
    "fee": ["fee", "expense", "cost"],
}
SOURCE = {  # what would have to be loaded when nothing is held
    "capital call": "capital call notices from each fund administrator",
    "uncalled": "unfunded commitment statements from the fund administrators",
    "fee": "fee statements from the managers or the custodian",
    "index": "an index price feed",
    "runway": "a cash forecast or monthly spending figures",
    "manager": "a manager list with their fund holdings",
}
STOP = {"the", "and", "of", "by", "for", "to", "in", "on", "a", "an", "our", "my", "all", "per", "vs", "total", "chart", "graph", "box"}
RANK = ("top", "best", "worst", "rank", "ranking", "leaders", "laggards", "league")
PERIOD = ("month", "year", "ytd", "mtd", "quarter", "itd", "week", "daily")
TREND = ("trend", "over time", "history", "runway", "growth", "timeline")
SPLIT = ("allocation", "mix", " by ", "split", "breakdown", "exposure") + RANK
NUM = ("tinyint", "smallint", "integer", "bigint", "hugeint", "decimal", "double", "float", "real", "numeric")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _hit(term: str, text: str) -> bool:
    if term in text:
        return True
    return len(term) > 4 and " " not in term and any(difflib.SequenceMatcher(None, term, w).ratio() >= 0.85 for w in text.split())


def _concept(label: str) -> str | None:
    n = _norm(label)
    return next((p for p in SYN if p in n or p + "s" in n), None)


def _terms(label: str) -> list[str]:
    n = _norm(label)
    out = [w for w in n.split() if w not in STOP and len(w) > 2]
    for phrase, more in SYN.items():
        if phrase in n or phrase + "s" in n:
            out += more
    return list(dict.fromkeys(out))


# ---- reading the picture -----------------------------------------------------------------------------------------------------------

_lock, _rapid = threading.Lock(), []


def _engine():
    with _lock:
        if not _rapid:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _rapid.append(RapidOCR())
            except Exception:  # noqa: BLE001 - not installed: ocr_local's other engines (text only) are tried
                _rapid.append(None)
        return _rapid[0]


def _page_png(raw: bytes) -> bytes:
    if raw[:4] != b"%PDF":
        return raw
    try:
        import fitz
        return fitz.open(stream=raw, filetype="pdf")[0].get_pixmap(dpi=150).tobytes("png")
    except Exception:  # noqa: BLE001
        raise Refused(400, "That PDF could not be read. Use a picture of the sketch, or type the box labels.") from None


@functools.lru_cache(maxsize=4)
def _lines(png: bytes) -> tuple:
    """((text, x, y, w, h), ...) read on this machine; positions are None when only a text engine is present."""
    eng = _engine()
    if eng is not None:
        res, _ = eng(ocr_local._shrink(png), use_cls=False)
        out = []
        for pts, text, _s in res or []:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            out.append((str(text), min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        return tuple(out)
    return tuple((t, None, None, None, None) for t in (ocr_local.ocr(png) or "").splitlines() if t.strip())


def read_boxes(data_b64: str) -> list[dict]:
    try:
        raw = base64.b64decode(str(data_b64), validate=True)
    except (binascii.Error, ValueError):
        raise Refused(400, "The sketch could not be read. Try another image.") from None
    if len(raw) > PICTURE_MAX:
        raise Refused(400, "That sketch is over 5 MB. Use a smaller one.")
    if not ocr_local.available():
        raise Refused(409, "This machine has no picture reader, so the sketch cannot be read. Type the box labels instead.")
    lines = _lines(_page_png(raw))
    if not lines:
        raise Refused(400, "No words could be read in that sketch. Write the labels larger, or type them.")
    return [{"label": t, "x": x, "y": y, "w": w, "h": h} for t, x, y, w, h in lines]


# ---- matching ----------------------------------------------------------------------------------------------------------------------

def _centre(b: dict) -> tuple[float, float]:
    return b["x"] + b["w"] / 2, b["y"] + b["h"] / 2


def _grid(boxes: list[dict]) -> None:
    """row/col and the headline. With positions: a new row when a box starts over 1.2 line-heights below its row's first; the headline is a clearly
    largest box, else the one nearest the middle. Without: 3 to a row in the order given, the middle one is the headline.
    ponytail: one OCR line is one box; a box of several lines reads as several boxes until lines are merged by position."""
    if all(b.get("y") is not None and b.get("w") is not None for b in boxes):
        boxes.sort(key=lambda b: (b["y"], b["x"]))
        hs = sorted(b["h"] or 1 for b in boxes)
        gap, row, top = hs[len(hs) // 2] * 1.2, -1, None
        for b in boxes:
            if top is None or b["y"] - top > gap:
                row, top = row + 1, b["y"]
            b["row"] = row
        for r in {b["row"] for b in boxes}:
            for c, b in enumerate(sorted((b for b in boxes if b["row"] == r), key=lambda b: b["x"])):
                b["col"] = c
        mx = sum(_centre(b)[0] for b in boxes) / len(boxes)
        my = sum(_centre(b)[1] for b in boxes) / len(boxes)
        near = min(boxes, key=lambda b: (_centre(b)[0] - mx) ** 2 + (_centre(b)[1] - my) ** 2)
        by_area = sorted(boxes, key=lambda b: -b["w"] * b["h"])
        big = len(boxes) > 1 and by_area[0]["w"] * by_area[0]["h"] > 1.5 * by_area[1]["w"] * by_area[1]["h"]
        rows = {r: [b for b in boxes if b["row"] == r] for r in {b["row"] for b in boxes}}
        alone = rows.get(0, [])
        if len(alone) == 1 and any(len(v) > 1 for v in rows.values()):  # a box alone across the top is the headline, as drawn
            alone[0]["headline"] = alone[0]["alone"] = True
        else:
            (by_area[0] if big else near)["headline"] = True
        for v in rows.values():
            if len(v) == 1:
                v[0]["alone"] = True
    else:
        for i, b in enumerate(boxes):
            b["row"], b["col"] = i // 3, i % 3
        boxes[len(boxes) // 2]["headline"] = True


def _candidates(tables: list[dict], terms: list[str]) -> list[tuple[int, dict, dict]]:
    out = []
    for t in tables:
        tn = _norm(t["name"].removeprefix("gold_"))
        th = sum(_hit(w, tn) for w in terms)
        for c in t["columns"]:
            if not c["type"].lower().startswith(NUM) or c["name"].endswith("_id"):
                continue
            ch = sum(_hit(w, _norm(c["name"])) for w in terms)
            if ch or th:
                out.append((3 * ch + th, t, c))
    return sorted(out, key=lambda x: -x[0])


def _kind(label: str, headline: bool, t: dict) -> str:
    """The tile kind the label asks for, if the table can show it (a line needs a date, a bar a date or a category), else a figure."""
    n = " " + _norm(label) + " "
    want = "line" if any(w in n for w in TREND) else "figure" if headline else "bar" if any(w in n for w in SPLIT) else "figure"
    kinds = [c["type"].lower() for c in t["columns"]]
    date, text = any(k.startswith(("date", "timestamp")) for k in kinds), any(k.startswith(("varchar", "text")) for k in kinds)
    return want if want == "figure" or (want == "line" and date) or (want == "bar" and (date or text)) else "figure"


def _twin(a: str, b: str) -> bool:
    cur = r"_(usd|sgd|eur|gbp|hkd|local)$"
    return re.sub(cur, "", a) == re.sub(cur, "", b) and a != b


COMPARE = ("vs", "versus", "against", "benchmark", "index", "target", "budget")


def classify(box: dict, tables: list[dict]) -> dict:
    label, n = box["label"], _norm(box["label"])
    out = {k: box[k] for k in ("id", "label", "row", "col")} | {"headline": bool(box.get("headline")), "alone": bool(box.get("alone"))}
    found = _candidates(tables, _terms(label))
    if not found:
        need = SOURCE.get(_concept(label), f"a source that holds {label.strip().lower()}; ask the data team which system has it")
        return out | {"status": "not_possible", "why": f"No table in this project holds {label.strip().lower()}.", "needs": need}
    score, t, col = found[0]
    if any(w in n.split() for w in COMPARE) or "benchmark" in n:
        nums = [c for c in t["columns"] if c["type"].lower().startswith(NUM) and not c["name"].endswith("_id")]
        tgt = next((c for c in nums if c["name"].startswith(("target", "budget", "benchmark", "goal", "plan"))), None)
        own = next((c for c in nums if c is not tgt and c["name"] not in ("difference", "gap") and not c["name"].startswith(("diff", "gap"))), None)
        if tgt and own and "bullet" in S.KINDS:
            return out | {"maps_to": {"table": t["name"], "measure": own["name"], "kind": "bullet"}, "status": "possible",
                          "why": f"{S._words(own['name']).capitalize()} against {S._words(tgt['name'])} in {S._label(t['name'])}: a bullet shows at a glance who is ahead."}
    if col["name"].endswith(("_sgd", "_eur", "_hkd")):  # house style: USD first, other currencies on request
        col = next((c for c in t["columns"] if _twin(c["name"], col["name"]) and c["name"].endswith("_usd")), col)
    out |= {"maps_to": {"table": t["name"], "measure": col["name"], "kind": _kind(label, out["headline"], t)},
            "why": f"{S._words(col['name']).capitalize()} in {S._label(t['name'])}."}
    rivals = [x for x in found[1:] if x[0] == score and not (x[1] is t and _twin(x[2]["name"], col["name"]))]  # net_worth_usd / _sgd: one figure, two currencies
    if any(w in n.split() for w in RANK) and not any(w in n for w in PERIOD):
        return out | {"status": "needs_definition", "question": "Rank by month or year to date?"}
    here = _norm(t["name"].removeprefix("gold_") + " " + col["name"])
    lost = [p for p, more in SYN.items() if (p in n or p + "s" in n) and not any(_hit(w, here) for w in more)]
    if lost:  # part of the label is not held: the nearest figure is offered, a person decides
        return out | {"status": "needs_definition", "question": f"Nothing here is called {lost[0]}; use {S._words(col['name'])} from {S._label(t['name'])} instead, or ask the data team for it?"}
    if rivals:
        opts = ", ".join(f"{S._words(c['name'])} ({S._label(tb['name'])})" for _, tb, c in [found[0]] + rivals[:3])
        return out | {"status": "needs_definition", "question": f"Which one do you mean: {opts}?"}
    return out | {"status": "possible"}


def read_sketch(plane, pid: str, body: dict) -> dict:
    labels = body.get("labels")
    if isinstance(labels, list) and labels:
        boxes = [{"label": x} if isinstance(x, str) else {k: x.get(k) for k in ("label", "x", "y", "w", "h")} for x in labels if isinstance(x, (str, dict))]
    elif isinstance(body.get("data"), str) and body["data"]:
        boxes = read_boxes(body["data"])
    else:
        raise Refused(400, "Send the sketch (data) or its box labels (labels).")
    boxes = [b | {"label": " ".join(str(b.get("label") or "").split())[:80]} for b in boxes]
    boxes = [b for b in boxes if len(b["label"]) > 1][:BOXES_MAX]
    title, boxes = _title_of(boxes)
    boxes = _attach_notes(boxes)
    if not boxes:
        raise Refused(400, "No box labels were found.")
    _grid(boxes)
    tables = D.gold_tables(plane, pid)
    ordered = sorted(boxes, key=lambda b: (b["row"], b["col"]))
    out = [classify(b | {"id": f"b{i + 1}"}, tables) | ({"note": b["note"]} if b.get("note") else {}) for i, b in enumerate(ordered)]
    return {"name": str(body.get("name") or "")[:200], "title": title, "boxes": out}


TITLE_WORDS = ("dashboard", "report", "pack", "overview", "summary", "view for")


def _title_of(boxes: list[dict]) -> tuple[str, list[dict]]:
    """The sketch's heading (the top line naming the page, e.g. "Morning dashboard for the family") is the dashboard's title, not a box."""
    if not boxes:
        return "", boxes
    top = min(boxes, key=lambda b: b.get("y") if b.get("y") is not None else boxes.index(b))
    n = _norm(top["label"])
    if any(w in n for w in TITLE_WORDS) and (top.get("y") is not None or top is boxes[0]):
        return top["label"], [b for b in boxes if b is not top]
    return "", boxes


def _attach_notes(boxes: list[dict]) -> list[dict]:
    """A side note in brackets ("(maybe later?)") belongs to the nearest box above it; it is never a box of its own."""
    notes = [b for b in boxes if b["label"].startswith("(")]
    keep = [b for b in boxes if not b["label"].startswith("(")]
    for nb in notes:
        above = [b for b in keep if nb.get("y") is not None and b.get("y") is not None and b["y"] <= nb["y"]]
        near = min(above, key=lambda b: (nb["y"] - b["y"]) ** 2 + (_centre(nb)[0] - _centre(b)[0]) ** 2) if above else (keep[-1] if keep else None)
        if near is not None:
            near["note"] = (near.get("note", "") + " " + nb["label"].strip("() ")).strip()
    return keep


# ---- building and requesting -------------------------------------------------------------------------------------------------------

def _boxes_of(body: dict) -> list[dict]:
    got = body.get("boxes")
    if not isinstance(got, list) or not got:
        raise Refused(400, "Send the boxes from the sketch.")
    if not all(isinstance(b, dict) for b in got):
        raise Refused(400, "Send the boxes themselves, as the sketch returned them, not only their ids.")
    return got


def build(plane, viewer, pid: str, did: str, body: dict) -> dict:
    """The possible boxes become tiles in the sketch's order (headline first, wide). The table and measure are checked again by build_tile."""
    all_boxes = _boxes_of(body)
    boxes = sorted((b for b in all_boxes if b.get("status") == "possible" and isinstance(b.get("maps_to"), dict)),
                   key=lambda b: (not b.get("headline"), b.get("row") or 0, b.get("col") or 0))
    rec = S._editor(plane, viewer, pid, did)
    D.begin_edit(rec, viewer)
    for b in boxes:  # one record, one save: a row is added when the grid is full
        m, size = b["maps_to"], "full" if b.get("alone") else "wide" if b.get("headline") else "medium"  # a box drawn alone across the page stays full width
        kind = m.get("kind") if m.get("kind") in S.KINDS else "figure"
        tile = S._store_tile(plane, rec, pid, S.build_tile(plane, pid, kind, str(m.get("table") or ""), m.get("measure")))
        row, col = S._first_free(S._layout(rec), size)
        S._add_item(rec, kind, tile, row, col, size)
    if isinstance(body.get("title"), str) and body["title"].strip():  # the sketch's heading names the dashboard
        rec["title"] = " ".join(body["title"].split())[:120]
    if boxes or body.get("title"):
        D._save(plane, rec)
    from sh_platform.v1 import b7h_history as H  # card A's history: the build is one step
    step = H.record_step(plane, viewer, pid, did, "", f"Built {len(boxes)} tiles from a sketch") if boxes else None
    return {"placed": len(boxes), "left_out": len(all_boxes) - len(boxes), "step": step}


def request(plane, viewer, pid: str, body: dict) -> dict:
    """One data-team ticket (t2_tickets, stage build, to the project's builder) naming what is missing or still to define."""
    todo = [b for b in _boxes_of(body) if b.get("status") in ("not_possible", "needs_definition")]
    if not todo:
        raise Refused(400, "Every box can be built; nothing to request.")
    lines = [f"- {b.get('label')}: " + (f"needs {b.get('needs')}" if b["status"] == "not_possible" else f"to define: {b.get('question')}") for b in todo[:BOXES_MAX]]
    t = t2_tickets.raise_ticket(plane, by=getattr(viewer, "name", "") or "Lumen", to="builder", project=pid, stage="build",
                                title=f"Dashboard sketch: {len(todo)} item{'s' if len(todo) != 1 else ''} to source or define",
                                body="From a sketched dashboard, these boxes cannot be built yet:\n" + "\n".join(lines))
    return {"request_id": t["id"], "items": len(todo)}
