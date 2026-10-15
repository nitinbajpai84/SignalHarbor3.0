"""The opportunity radar (spec 57; rulings C1 to C11). One scan, three agents, all drafting; no agent opens, picks up or parks anything.

- The Watcher (data only): 56's `detect` with its own thresholds, plus a level shift or a steady drift in any gold measure over at least
  `min_periods_for_pattern` periods. Signals on measures an open Initiative or open Decision already covers group into one record.
- Lens (documents and voices): adds document and voice evidence to each record; turns a document that sets two series side by side and
  says they move together into a pattern for North to check; groups repeated wishes into one theme, counting voices (C6).
- North: writes the hypothesis (`hypotheses.py`), then the counter-evidence check over the last `counter_periods` periods. Broken: the
  record is set aside (`rejected`, C9) with the reason and the records that broke it. Holds and something already covers it: says so and
  links (a Decision link stays a proposal, C11). Holds otherwise: 56's judgement and `proposed`.
Every number in a record is traced to a warehouse row, a document or a voice. Thresholds come from the company settings (C4 defaults).
"""
import json
import logging
import math
import re
from datetime import date, datetime, timezone
from itertools import combinations

import duckdb
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from sh_platform import warehouse
from sh_platform.context_docs.api import _json_body, _plain
from sh_platform.intents import _plane, _viewer
from sh_platform.intents import hypotheses as H
from sh_platform.intents import opportunities as O
from sh_platform.jsonfile import lock_for, read_json_strict
from sh_platform.profile import areas as areas_store, store as profile_store

log = logging.getLogger(__name__)
router = APIRouter()
LENS_LABEL = {"new_revenue": "New revenue", "process_cost": "Process cost", "retention": "Retention", "risk": "Risk"}
DEFAULTS = {"theme_min_voices": 3, "counter_periods": 3, "min_periods_for_pattern": 4, "min_confidence_to_show": "fairly_sure", "scan": "daily"}  # C4, C5
RADAR_KEYS = tuple(DEFAULTS)
ACT_ROLES = {"owner", "company_admin", "sponsor", "analyst"}  # 56's routes; C3
RANK = {"unlikely": 0, "not_sure": 1, "fairly_sure": 2}
STOP = set("""about above after again against also among another anyone around back been before being below between both cannot could
did does doing done down each else even ever every everyone everything everybody from have having here into just last like look looks made
make many more most much must need never next nobody none nothing often only other others ours over same seem should since some someone
something still such take than that their them then there these they thing things this those though through under until upon very want
week weeks were what when where which while whole will with within without would your yours one two three four five the and for you our all
can not was are has had get got who how why its out any but may way per see say said says let lot less via""".split())
# C36: what each lens means for a family office, as words a measure's name, unit and keywords use. Lens's draft, confirmed by a person.
LENS_WORDS = {"new_revenue": "interest yield income idle sweep distribution dividend earn",
              "process_cost": "hours effort fee fees cost costs late manual retype rework spreadsheet chasing invoice time",
              "retention": "opens reader readers questions engagement portal trust",
              "risk": "exposure unhedged stale concentration loss missing headroom conflict exception breach"}


def _stem(w: str) -> str:
    w = w.lower()
    return (w[:-1] if len(w) > 4 and w.endswith("s") else w)[:5]


def stems(text: str, least: int = 3) -> set[str]:
    return {_stem(w) for w in re.findall(r"[A-Za-z]+", str(text or "")) if len(w) >= least and w.lower() not in STOP}


LENS_STEMS = {k: stems(v) for k, v in LENS_WORDS.items()}


def lens_of(words: str) -> str | None:
    """The lens whose words the text uses most; None when it uses none."""
    s = stems(words)
    hits = {k: len(s & v) for k, v in LENS_STEMS.items()}
    best = max(hits.values())
    return next(k for k in LENS_STEMS if hits[k] == best) if best else None


# ---- settings -----------------------------------------------------------------------------------------------------------------------
def settings(plane) -> dict:
    """The radar keys from the company's opportunity settings block; an unset key takes the C4 default and is listed as unset."""
    try:
        raw = (read_json_strict(plane.path("settings", "intent_centre.json"), dict) or {}).get("opportunity") or {}
    except (OSError, ValueError):
        raw = {}
    out, unset = {}, []
    for k, d in DEFAULTS.items():
        v = raw.get(k) if isinstance(raw, dict) else None
        ok = (v in RANK) if k == "min_confidence_to_show" else (v in ("daily", "on_read")) if k == "scan" else (isinstance(v, int) and not isinstance(v, bool) and v >= 1)
        out[k] = v if ok else d
        if not ok:
            unset.append(k)
    return {**out, "unset": unset}


# ---- what the agents read -----------------------------------------------------------------------------------------------------------
def measure_catalogue(pack) -> dict[str, dict]:
    """Measure id to {name, unit, keywords, owner_role} from the pack's kpi_tree and any measure proposals filed in the pack's folders."""
    out: dict[str, dict] = {}
    try:
        rows = list((pack.section("kpi_tree") or {}).get("kpis") or [])
    except (KeyError, AttributeError, TypeError):
        rows = []
    folder = getattr(pack, "folder", None)
    if folder is not None:
        import yaml
        for f in sorted(folder.glob("*/measures/*.yaml")):
            try:
                rows += list((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("kpis") or [])
            except (OSError, ValueError, yaml.YAMLError, AttributeError):
                log.info("a measure file could not be read")
    for k in rows:
        if isinstance(k, dict) and re.fullmatch(r"K\d+", str(k.get("id") or "")) and k["id"] not in out:
            out[k["id"]] = {"name": str(k.get("name") or k["id"]), "unit": str(k.get("unit") or ""), "keywords": [str(x) for x in k.get("keywords") or []],
                            "owner_role": str(k.get("owner_role") or "")}
    return out


def _gold(con) -> dict[str, dict[str, list[tuple[str, float]]]]:
    """Gold measure id to {group or "": [(period, value)]}. A third column (entity, custodian, reader) splits the measure into groups."""
    out: dict[str, dict] = {}
    cols: dict[str, list[str]] = {}
    for t, c in con.execute("select table_name, column_name from information_schema.columns where table_schema = 'gold' order by table_name, ordinal_position").fetchall():
        cols.setdefault(t, []).append(c)
    for t, cs in cols.items():
        if not re.fullmatch(r"k\d+", t) or "period" not in cs or "value" not in cs:
            continue
        grp = next((c for c in cs if c not in ("period", "value")), None)
        sql = f'select period, {f"{grp}" if grp else "null"}, value from gold."{t}" order by period'
        series: dict[str, list] = {}
        for p, g, v in con.execute(sql).fetchall():
            if v is not None and isinstance(v, (int, float)) and math.isfinite(float(v)):
                series.setdefault("" if g is None else str(g), []).append((str(p), float(v)))
        out[t.upper()] = series
    return out


def _silver_columns(con) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t, c, ty in con.execute("select table_name, column_name, data_type from information_schema.columns where table_schema = 'silver' order by table_name, ordinal_position").fetchall():
        out.setdefault(t, []).append(f"{c}:{ty}")
    return {t: cs for t, cs in out.items() if any(c.startswith("period:") for c in cs)}


def _num(ty: str) -> bool:
    return any(x in ty.upper() for x in ("INT", "DOUBLE", "DECIMAL", "FLOAT", "REAL", "NUMERIC"))


def documents(plane) -> list[dict]:
    """Every agent-readable shelf document as text (C10): Lens's own and the shared ones; restricted documents never."""
    from sh_platform.context_docs.store import AGENTS, DocStore
    st, out = DocStore(plane), []
    for a in AGENTS:
        for d in st._all(a):
            if d.get("restricted") or not (a == "lens" or d.get("visibility") in ("shared", "shared_full")):
                continue
            text = "\n".join(c.get("text") or "" for c in d.get("chunks") or [])
            m = re.search(r"\d{4}-\d{2}-\d{2}", d.get("filename") or "")
            out.append({"id": d["doc_id"], "agent": a, "title": d.get("title") or d.get("filename") or "A document", "text": text,
                        "at": m.group(0) if m else str(d.get("uploaded_at") or "")[:10]})
    return out


def voices(plane) -> list[dict]:
    """Wall cards, check-in items, brainstorm ideas and backlog items. Sealed cards and interview notes are never read (D-013).
    `who` is the account for a named voice and the item itself for an anonymous one (C6). `wish` marks what asks for something."""
    out = []
    cards = (profile_store.load(plane).get("cards") or {})
    val = lambda c, f: (c.get(f) or {}).get("value") if isinstance(c.get(f), dict) else c.get(f)  # noqa: E731
    for cid, c in cards.items():
        if not isinstance(c, dict) or val(c, "sealed") or val(c, "from_interview") or val(c, "withdrawn"):
            continue
        place = f"{val(c, 'room') or ''} {(c.get('lane') or {}).get('from') or ''}".lower()
        anon = bool(val(c, "anonymous"))
        out.append({"ref": f"card:{cid}", "source": "brainstorm" if "brainstorm" in place else "wall", "who": f"anon:card:{cid}" if anon else str(val(c, "author")),
                    "anonymous": anon, "text": " ".join(str(val(c, q) or "") for q in ("q1", "q2")).strip(), "wish": val(c, "lane") in ("missing", "levers"),
                    "at": str((c.get("lane") or {}).get("at") or "")[:10]})
    for wf in sorted(plane.path("intents").glob("pul-*/weeks/*.json")):
        try:
            wk = read_json_strict(wf, dict) or {}
        except (OSError, ValueError):
            continue
        for it in wk.get("items") or []:
            if not isinstance(it, dict) or it.get("unsent") or it.get("state") not in (None, "active"):
                continue
            anon = bool(it.get("anonymous")) or it.get("by") in (None, "anonymous")
            ref = f"{wf.parent.parent.name}/weeks/{wk.get('week_key') or wf.stem}#{it.get('id')}"
            out.append({"ref": ref, "source": "checkin", "who": f"anon:{ref}" if anon else str(it["by"]), "anonymous": anon, "text": str(it.get("text") or ""),
                        "wish": it.get("kind") == "thought", "kind": it.get("kind"), "at": str(wk.get("opens") or wk.get("week_key") or "")})
    try:
        backlog = (read_json_strict(plane.path("intents", "backlog.json"), dict) or {}).get("items") or []
    except (OSError, ValueError):
        backlog = []
    for b in backlog:
        if isinstance(b, dict) and b.get("id"):
            why = b.get("why_it_matters")
            out.append({"ref": f"backlog:{b['id']}", "source": "backlog", "who": str(b.get("raised_by") or f"anon:backlog:{b['id']}"), "anonymous": not b.get("raised_by"),
                        "text": f"{b.get('title') or ''} {(why or {}).get('text') if isinstance(why, dict) else why or ''}".strip(), "wish": True,
                        "at": str(b.get("raised_at") or "")[:10]})
    return out


def covers(plane, cat: dict) -> dict[str, dict]:
    """Measure id to what already covers it: an open Initiative whose hypothesis names the measure (its own or in an evidence trace),
    else an open Decision whose question names at least half of the measure's name words."""
    out: dict[str, dict] = {}
    for h in H.all_records(plane):
        v = H.latest(h)
        if h["origin"].get("kind") != "initiative":
            continue
        intent = _intent(plane, h["origin"].get("ref"))
        if not intent or intent.get("state") not in ("open", "in_session", "closing"):
            continue
        ms = {(v.get("measure") or {}).get("id")} | {m.group(1).upper() for e in v.get("evidence") or [] if (m := re.match(r"gold[/.](k\d+)", str((e.get("trace") or {}).get("ref") or ""), re.I))}
        for m in ms - {None}:
            out.setdefault(m, {"kind": "initiative", "id": intent["id"], "title": intent.get("title") or "", "areas": intent.get("areas") or [], "decider": None,
                               "hypothesis": h["id"], "primary": m == (v.get("measure") or {}).get("id")})
    for f in sorted(plane.path("intents").glob("dec-*/intent.json")):
        d = _intent(plane, f.parent.name)
        if not d or d.get("state") not in ("open", "in_session"):
            continue
        q = stems(f"{(d.get('outcome') or {}).get('question') or ''} {d.get('title') or ''}")
        for mid, meta in cat.items():
            name = stems(meta["name"])
            if mid not in out and name and len(name & q) * 2 >= len(name):
                out[mid] = {"kind": "decision", "id": d["id"], "title": d.get("title") or "", "areas": d.get("areas") or [],
                            "decider": ((d.get("people") or {}).get("decider") or {}).get("account_id"), "hypothesis": None, "primary": True}
    return out


def _intent(plane, iid) -> dict | None:
    if not isinstance(iid, str) or not re.fullmatch(r"[a-z]{3}-[0-9a-f]{8,40}", iid):
        return None
    try:
        return read_json_strict(plane.path("intents", iid, "intent.json"), dict)
    except (OSError, ValueError):
        return None


# ---- the Watcher: shifts and drifts in gold ------------------------------------------------------------------------------------------
def shift(pts: list[tuple[str, float]], need: int) -> dict | None:
    """The earliest period from which every later value sits outside the range of the values before it, with at least `need` on each side."""
    vals = [v for _, v in pts]
    for s in range(need, len(vals) - need + 1):
        lo, hi, after = min(vals[:s]), max(vals[:s]), vals[s:]
        if all(v < lo for v in after) or all(v > hi for v in after):
            return {"kind": "shift", "way": "up" if after[0] > hi else "down", "start": pts[s][0], "end": pts[-1][0], "n": len(after),
                    "before": (lo, hi), "first": pts[s - 1], "last": pts[-1]}
    return None


def drift(pts: list[tuple[str, float]], need: int) -> dict | None:
    """The longest run of at least `need` periods moving the same way each period (the latest on a tie)."""
    best, i = None, 0
    while i < len(pts) - 1:
        j, way = i, (pts[i + 1][1] > pts[i][1]) - (pts[i + 1][1] < pts[i][1])
        while way and j + 1 < len(pts) and ((pts[j + 1][1] > pts[j][1]) - (pts[j + 1][1] < pts[j][1])) == way:
            j += 1
        if way and j - i + 1 >= need and (best is None or j - i + 1 >= best["n"]):
            best = {"kind": "drift", "way": "up" if way > 0 else "down", "start": pts[i][0], "end": pts[j][0], "n": j - i + 1, "first": pts[i], "last": pts[j]}
        i = max(j, i + 1)
    return best


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v) >= 1 else f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def _signal_line(mid: str, grp: str, sig: dict) -> str:
    on = f" for {grp}" if grp else ""
    if sig["kind"] == "shift":
        side = "above" if sig["way"] == "up" else "below"
        return (f"{mid}{on} moved {sig['way']} in {sig['start']} and has stayed {side} its earlier range for {sig['n']} periods: "
                f"{_fmt(sig['first'][1])} in {sig['first'][0]}, {_fmt(sig['last'][1])} in {sig['last'][0]}.")
    return f"{mid}{on} moved {sig['way']} in each of {sig['n']} periods from {sig['start']} to {sig['end']}: {_fmt(sig['first'][1])} to {_fmt(sig['last'][1])}."


def watch_gold(gold: dict, need: int) -> dict[str, list[dict]]:
    """Measure id to its signals, one per group that shifted (preferred) or drifted."""
    out: dict[str, list[dict]] = {}
    for mid, series in gold.items():
        for grp, pts in series.items():
            sig = shift(pts, need) or drift(pts, need)
            if sig:
                out.setdefault(mid, []).append({**sig, "group": grp, "measure": mid, "points": pts})
    return out


# ---- Lens: documents, voices, claims and themes -----------------------------------------------------------------------------------------
def _mentions(text: str, meta: dict) -> bool:
    low = text.lower()
    if meta["name"].lower() in low:
        return True
    kws = {k.lower() for k in meta["keywords"] if len(k) >= 3}
    return len({k for k in kws if re.search(rf"\b{re.escape(k)}", low)}) >= 2


def doc_lines(docs: list[dict], metas: list[dict], limit: int = 4) -> list[dict]:
    hits = [d for d in docs if any(_mentions(d["text"], m) for m in metas)]
    hits.sort(key=lambda d: d["at"], reverse=True)
    return [{"record_kind": "document", "stance": "supports", "text": d["title"], "trace": {"kind": "document", "ref": d["id"], "at": d["at"]}} for d in hits[:limit]]


def voice_lines(vs: list[dict], metas: list[dict], limit: int = 6) -> list[dict]:
    hits = [v for v in vs if any(_mentions(v["text"], m) for m in metas)]
    hits.sort(key=lambda v: v["at"], reverse=True)
    return [{"record_kind": "voice", "stance": "supports", "text": v["text"][:300], "trace": {"kind": _vkind(v), "ref": v["ref"], "at": v["at"]},
             "who": v["who"], "anonymous": v["anonymous"]} for v in hits[:limit]]


def _vkind(v: dict) -> str:
    return {"checkin": "week_item", "wall": "wall", "brainstorm": "brainstorm", "backlog": "backlog"}[v["source"]]


def themes(vs: list[dict], least: int) -> list[dict]:
    """Wishes that say the same thing: two wishes join when they share a pair of words that at least `least` different voices use.
    Each theme counts distinct voices: a named person once, each anonymous item once (C6)."""
    wishes = [v for v in vs if v["wish"] and v["text"]]
    words = [stems(v["text"], 4) for v in wishes]
    pairs: dict[tuple, set[int]] = {}
    for i, ws in enumerate(words):
        for p in combinations(sorted(ws), 2):
            pairs.setdefault(p, set()).add(i)
    parent = list(range(len(wishes)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    strong = {p: ix for p, ix in pairs.items() if len({wishes[i]["who"] for i in ix}) >= least}
    for ix in strong.values():
        first = min(ix)
        for i in ix:
            parent[root(i)] = root(first)
    groups: dict[int, list[int]] = {}
    for i in {i for ix in strong.values() for i in ix}:
        groups.setdefault(root(i), []).append(i)
    out = []
    for ix in groups.values():
        members = [wishes[i] for i in sorted(ix)]
        if len({m["who"] for m in members}) < least:
            continue
        key = max((p for p in strong if strong[p] <= set(ix)), key=lambda p: (len(strong[p]), p))
        out.append({"members": members, "key": "theme:" + "+".join(key)})
    return out


def _md_table(text: str) -> tuple[list[str], list[tuple[str, list[float]]]] | None:
    """A markdown table whose first column is a month and the rest numbers: (headers, rows)."""
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines[:-1]):
        if ln.startswith("|") and re.fullmatch(r"\|[\s:|-]+\|", lines[i + 1] or "x"):
            heads = [c.strip() for c in ln.strip("|").split("|")]
            rows = []
            for r in lines[i + 2:]:
                if not r.startswith("|"):
                    break
                cells = [c.strip().replace(",", "") for c in r.strip("|").split("|")]
                if re.fullmatch(r"\d{4}-\d{2}", cells[0]) and all(re.fullmatch(r"-?\d+(\.\d+)?", c) for c in cells[1:]):
                    rows.append((cells[0], [float(c) for c in cells[1:]]))
            if len(heads) >= 3 and rows:
                return heads, rows
    return None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx, sy = math.sqrt(sum((x - mx) ** 2 for x in xs)), math.sqrt(sum((y - my) ** 2 for y in ys))
    return None if not sx or not sy else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def claims(docs: list[dict], cat: dict, gold: dict, con, silver: dict, need: int, counter: int) -> list[dict]:
    """A document that sets a measure beside another series and says they move together: the claim, and North's check of it on the
    warehouse rows. Breaks when, in the last `counter` periods, the measure sits outside the spread the claimed periods allow, or when
    the measure's own breakdown puts the excess on a different cause."""
    out = []
    say = re.compile(r"correlat|move together|moves with|track each other|go together", re.I)
    for d in docs:
        t = _md_table(d["text"]) if say.search(d["text"]) else None
        if not t or len(t[1]) < need:
            continue
        heads, rows = t
        mid = max(cat, key=lambda k: len(stems(heads[1]) & stems(f"{cat[k]['name']} {cat[k]['unit']} {' '.join(cat[k]['keywords'])}")), default=None)
        if not mid or len(stems(heads[1]) & stems(f"{cat[mid]['name']} {cat[mid]['unit']} {' '.join(cat[mid]['keywords'])}")) < 2 or "" not in gold.get(mid, {}):
            continue
        other = max(((tb, c.split(":")[0]) for tb, cs in silver.items() for c in cs if _num(c.split(":", 1)[1])),
                    key=lambda tc: len(stems(heads[2]) & stems(tc[1].replace("_", " "))), default=None)
        if not other or len(stems(heads[2]) & stems(other[1].replace("_", " "))) < 2:
            continue
        ys = dict(gold[mid][""])
        xs = {str(p): float(v) for p, v in con.execute(f'select period, "{other[1]}" from silver."{other[0]}" where "{other[1]}" is not null').fetchall()}
        claimed = [p for p, _ in rows if p in ys and p in xs]
        later = sorted(p for p in ys if p in xs and p > max(claimed, default=""))[-counter:]
        if len(claimed) < need:
            continue
        cx, cy = [xs[p] for p in claimed], [ys[p] for p in claimed]
        r_claim, r_all = _pearson(cx, cy), _pearson([xs[p] for p in sorted(set(ys) & set(xs))], [ys[p] for p in sorted(set(ys) & set(xs))])
        mx, my = sum(cx) / len(cx), sum(cy) / len(cy)
        b = sum((x - mx) * (y - my) for x, y in zip(cx, cy)) / (sum((x - mx) ** 2 for x in cx) or 1)
        spread = max(abs(y - (my + b * (x - mx))) for x, y in zip(cx, cy))
        broke = [p for p in later if abs(ys[p] - (my + b * (xs[p] - mx))) > spread]
        label = other[1].replace("_", " ")
        found, broke_by, why = [], [], []
        if broke:
            p = max(broke, key=lambda q: xs[q])
            found.append(f"In {p} {label} was {_fmt(xs[p])} yet {mid} was {_fmt(ys[p])}, outside what the claimed periods allow.")
            broke_by += [{"kind": "silver", "ref": f"silver.{other[0]}#{p}"}, {"kind": "feed", "ref": f"gold.{mid.lower()}#{p}"}]
            why.append(f"The link breaks in {p}: {label} was {_fmt(xs[p])} yet {mid} was {_fmt(ys[p])}.")
        cause = _breakdown(con, silver, gold[mid][""], sorted(claimed, key=lambda q: ys[q])[-2:], claimed)
        if cause:
            found.append(cause["text"])
            broke_by.append({"kind": "silver", "ref": cause["ref"]})
            why.append(cause["text"])
        verdict = "broken" if broke or cause else "holds"
        lens = lens_of(f"{cat[mid]['name']} {cat[mid]['unit']} {' '.join(cat[mid]['keywords'])}") or "process_cost"
        numbers = [{"label": f"Correlation over the {len(claimed)} periods the document names", "value": round(r_claim, 2) if r_claim is not None else None, "unit": "correlation",
                    "trace": {"kind": "document", "ref": d["id"], "at": d["at"]}}]
        if r_all is not None:
            numbers.append({"label": f"Correlation over all {len(set(ys) & set(xs))} periods in the warehouse", "value": round(r_all, 2), "unit": "correlation",
                            "trace": {"kind": "feed", "ref": f"gold.{mid.lower()}", "at": max(ys)}})
        out.append({"key": f"claim:{d['id']}", "kind": "data", "noticed_by": "lens", "lens": lens, "measure": mid, "metas": [cat[mid]],
                    "title": f"{mid} moves with {label}", "belief": f"{mid} rises and falls with {label}, as the document {d['title']} says.",
                    "pattern": {"text": f"A document sets {mid} beside {label} for {len(claimed)} periods and says they move together.", "periods": claimed, "numbers": numbers},
                    "touches": {"measures": [mid], "processes": [], "sources": []},
                    "evidence": [{"record_kind": "document", "stance": "supports", "text": d["title"], "trace": {"kind": "document", "ref": d["id"], "at": d["at"]}}],
                    "check": {"looked_for": [f"periods after {max(claimed)} where the link should hold and does not", f"a breakdown of {mid} that names another cause",
                                             "an open Initiative or Decision on the same measure"],
                              "found": found, "verdict": verdict, "why": " ".join(why) or "The link holds in the periods checked.", "broke_by": broke_by}})
    return out


def _breakdown(con, silver: dict, pts: list[tuple[str, float]], top: list[str], claimed: list[str]) -> dict | None:
    """A silver table whose numbers, summed per period, are the measure; the category that carries the excess in the measure's top
    claimed periods, when that is not the claimed driver."""
    want = dict(pts)
    for tb, cs in silver.items():
        texts = [c.split(":")[0] for c in cs if "VARCHAR" in c.split(":", 1)[1].upper() and not c.startswith("period:")]
        nums = [c.split(":")[0] for c in cs if _num(c.split(":", 1)[1])]
        for n in nums:
            got = dict(con.execute(f'select period, sum("{n}") from silver."{tb}" group by period').fetchall())
            if not texts or any(abs(float(got.get(p) or 0) - v) > 0.01 for p, v in want.items()):
                continue
            for tc in texts:
                rows = con.execute(f'select period, "{tc}", sum("{n}") from silver."{tb}" group by 1, 2').fetchall()
                cell = {(str(p), str(c)): float(v or 0) for p, c, v in rows}
                cats = {c for _, c in cell}
                rest = [p for p in claimed if p not in top]
                if not rest:
                    continue
                gain = {c: sum(cell.get((p, c), 0) for p in top) / len(top) - sum(cell.get((p, c), 0) for p in rest) / len(rest) for c in cats}
                c = max(gain, key=gain.get)
                if gain[c] > 0 and gain[c] * 2 >= sum(want[p] for p in top) / len(top) - sum(want[p] for p in rest) / len(rest):
                    vals = " and ".join(_fmt(cell.get((p, c), 0)) for p in sorted(top))
                    return {"text": f"{tb.replace('_', ' ').capitalize()} puts most of the extra in {' and '.join(sorted(top))} on {c} ({vals} {n}).",
                            "ref": f"silver.{tb}#{tc}={c}"}
    return None


# ---- North: hypothesis and check ---------------------------------------------------------------------------------------------------------
def _confidence(check: dict, lines: list[dict], theme: bool) -> str:
    if check["verdict"] == "broken":
        return "unlikely"
    return "fairly_sure" if theme or len({e["record_kind"] for e in lines}) >= 2 else "not_sure"


def _areas(link: dict | None, metas: list[dict], known: dict[str, str]) -> list[str]:
    got = [a for a in (link or {}).get("areas") or [] if a in known]
    if not got:
        got = [a for m in metas for a, name in known.items() if m.get("owner_role", "").lower() in (a, name.lower()) and m.get("owner_role")]
    return sorted(set(got))


def _baseline(sigs: list[dict], unit: str) -> dict | None:
    if not sigs:
        return None
    last = {s["group"]: s["points"][-1] for s in sigs}
    period = max(p for p, _ in last.values())
    value = last[""][1] if list(last) == [""] else {g: v for g, (_, v) in sorted(last.items())}
    return {"value": value, "unit": unit, "periods": [period], "trace": {"kind": "feed", "ref": f"gold.{sigs[0]['measure'].lower()}#{period}", "at": period}}


def _numbers(sigs: list[dict]) -> list[dict]:
    return [{"label": f"Periods {s['measure']}{' for ' + s['group'] if s['group'] else ''} {'stayed ' + ('above' if s['way'] == 'up' else 'below') + ' its earlier range' if s['kind'] == 'shift' else 'moved ' + s['way']}",
             "value": s["n"], "unit": "periods", "trace": {"kind": "feed", "ref": f"gold.{s['measure'].lower()}", "at": s["end"]}} for s in sigs]


def data_candidates(signals: dict, cov: dict, cat: dict, counter: int) -> list[dict]:
    """One candidate per measure, or per Initiative or Decision when several signalling measures sit under the same one."""
    groups: dict[str, list[str]] = {}
    for mid in sorted(signals):
        c = cov.get(mid)
        groups.setdefault(f"{c['kind']}:{c['id']}" if c else f"measure:{mid}", []).append(mid)
    out = []
    for key, mids in groups.items():
        link = cov.get(mids[0])
        prim = next((m for m in mids if (cov.get(m) or {}).get("primary")), mids[0])
        sigs = [s for m in [prim] + [m for m in mids if m != prim] for s in signals[m]]
        meta = cat.get(prim, {"name": prim, "unit": "", "keywords": [], "owner_role": ""})
        lines = [_signal_line(s["measure"], s["group"], s) for s in sigs]
        found, verdict, why, broke_by = [], "holds", "", []
        if link:
            found.append(f"An open {link['kind'].capitalize()} already covers {prim}: {link['title']}.")
            why = f"An open {link['kind'].capitalize()} already covers this: {link['title']}. North links to it rather than proposing a new one."
        prim_sigs = [s for s in sigs if s["measure"] == prim]
        rev = [s for s in prim_sigs if s["kind"] == "drift" and s["end"] != s["points"][-1][0]]
        if rev and len(rev) == len(prim_sigs) and not link:
            s = rev[0]
            tail = [v for p, v in s["points"] if p > s["end"]][-counter:]
            if tail:
                verdict, broke_by = "broken", [{"kind": "feed", "ref": f"gold.{prim.lower()}#{s['points'][-1][0]}"}]
                why = f"{prim} stopped moving {s['way']} after {s['end']} and has turned since, so the drift no longer holds."
                found.append(why)
        out.append({"key": key, "kind": "data", "noticed_by": "watcher", "measure": prim, "metas": [cat[m] for m in mids if m in cat], "link": link,
                    "lens": lens_of(f"{meta['name']} {meta['unit']} {' '.join(meta['keywords'])}") or "risk",
                    "title": f"{prim} {('moved ' + sigs[0]['way']) if sigs[0]['kind'] == 'shift' else 'keeps moving ' + sigs[0]['way']}" + (f", with {', '.join(m for m in mids if m != prim)}" if len(mids) > 1 else ""),
                    "belief": " ".join(lines[:3]), "baseline": _baseline(prim_sigs, meta["unit"]),
                    "pattern": {"text": lines[0], "periods": sorted({p for s in sigs for p, _ in s["points"] if s["start"] <= p <= s["end"]}), "numbers": _numbers(sigs)},
                    "touches": {"measures": mids, "processes": [], "sources": []},
                    "evidence": [{"record_kind": "data", "stance": "supports", "text": ln, "trace": {"kind": "feed", "ref": f"gold.{s['measure'].lower()}", "at": s["end"]}} for ln, s in zip(lines, sigs)],
                    "check": {"looked_for": ["an open Initiative or Decision on the same measure", f"the measure already back where it was in the last {counter} periods",
                                             "a one-off period"], "found": found, "verdict": verdict, "why": why or "The pattern holds in every period since it began.", "broke_by": broke_by}})
    return out


def theme_candidates(ths: list[dict]) -> list[dict]:
    out = []
    for t in ths:
        ms = t["members"]
        by_source = {k: sum(1 for m in ms if m["source"] == k) for k in ("wall", "checkin", "brainstorm", "backlog")}
        n = len({m["who"] for m in ms})
        words = [stems(m["text"], 4) for m in ms]
        central = max(range(len(ms)), key=lambda i: (sum(len(words[i] & w) for j, w in enumerate(words) if j != i), -len(ms[i]["text"])))
        title = re.split(r"(?<=[.!?|])\s", ms[central]["text"])[0].rstrip(" .|")[:120]  # the wish that shares most words with the others
        text = " ".join(m["text"] for m in ms)
        out.append({"key": t["key"], "kind": "theme", "noticed_by": "lens", "measure": None, "metas": [], "link": None, "lens": lens_of(text) or "process_cost",
                    "title": title, "belief": f"{n} people ask for the same thing in their own words: {title}", "baseline": None,
                    "theme": {"voices": n, "by_source": by_source},
                    "pattern": {"text": f"The same wish came up {len(ms)} times from {n} voices.", "periods": sorted({m["at"] for m in ms if m["at"]}),
                                "numbers": [{"label": "Voices", "value": n, "unit": "voices", "trace": {"kind": _vkind(ms[0]), "ref": ms[0]["ref"], "at": ms[0]["at"]}}]},
                    "touches": {"measures": [], "processes": [], "sources": []},
                    "evidence": [{"record_kind": "voice", "stance": "supports", "text": m["text"][:300], "trace": {"kind": _vkind(m), "ref": m["ref"], "at": m["at"]},
                                  "who": m["who"], "anonymous": m["anonymous"]} for m in ms],
                    "check": {"looked_for": ["the same wish already answered by an open Initiative"], "found": [], "verdict": "holds",
                              "why": "No measure carries this wish, so there is nothing to check it against beyond the voices.", "broke_by": []}})
    return out


def _start_answers(cand: dict, rec_id: str, area_names: list[str]) -> dict:
    g = lambda v: {"value": v, "mark": "guessed", "by": "North", "from": rec_id}  # noqa: E731
    out = {"goal": g(cand["belief"][:300]), "build": g("not sure"), "deadline": g("not sure")}
    if area_names:
        out["areas"] = g(", ".join(area_names))
    if cand.get("measure"):
        out["definitions"] = g(f"{cand['measure']} as the company defines it")
    return out


def _write(plane, cand: dict, known: dict[str, str], north=None) -> dict:
    """The opportunity (56 record, widened), its hypothesis and the outcome of the check, written in one go."""
    areas = _areas(cand.get("link"), cand["metas"], known)
    by = cand["noticed_by"]
    rec = O._create(plane, {"title": cand["title"], "areas": areas, "touches": cand["touches"], "pattern": {**cand["pattern"], "kind": cand["kind"], "key": cand["key"]}}, by)
    lines = [{**H.evidence_line(i + 1, e["record_kind"], e["stance"], e["text"], e["trace"], "lens" if e["record_kind"] != "data" else "watcher"),
              **({"by": "anonymous"} if e.get("anonymous") else {"by": e["who"]} if e.get("who") else {})} for i, e in enumerate(cand["evidence"])]
    check = {"at": H.now(), **{k: cand["check"][k] for k in ("looked_for", "found", "verdict", "why")}}
    conf = _confidence(check, lines, cand["kind"] == "theme")
    meta = cand["metas"][0] if cand["metas"] else None
    hyp = H.create(plane, {"kind": "opportunity", "ref": rec["id"]}, {
        "belief": cand["belief"], "lens": cand["lens"], "measure": {"id": cand["measure"], "name": meta["name"] if meta else cand["measure"]} if cand.get("measure") else None,
        "baseline": cand.get("baseline"), "confidence": conf, "evidence": lines, "counter_check": check, "theme": cand.get("theme"), "drafted_by": "rules"},
        "north", state="rejected" if check["verdict"] == "broken" else "checked")
    link = cand.get("link")
    with lock_for(O._dir(plane) / f"{rec['id']}.json"):
        rec = O.get(plane, rec["id"])
        rec.update(hypothesis_ref=H.ref(hyp), rejected=None, picked_up_as=None, linked=None, links_proposed=[])
        O._hist(rec, "lens" if by == "watcher" else by, "evidence_supports")
        rec["state"] = "under_review"
        O._hist(rec, "north", "under_review")
        O._hist(rec, "north", "hypothesis_written")
        if check["verdict"] == "broken":
            rec.update(state="rejected", rejected={"at": check["at"], "why": check["why"], "broke_by": cand["check"]["broke_by"]})
            O._hist(rec, "north", "rejected", check["why"])
        elif link:
            rec["linked"] = {"kind": link["kind"], "id": link["id"], "title": link["title"]}
            if link["kind"] == "decision":
                rec["links_proposed"] = [{"kind": "decision", "id": link["id"], "title": link["title"], "decider": link["decider"], "confirmed": False}]  # C11
            rec["judgement"] = {"fits": False, "why": check["why"], "confidence": conf, "start_answers": {}, "at": check["at"]}
            O._hist(rec, "north", "judged_no")
        else:
            j = north(rec) if north else None
            rec["judgement"] = j or {"fits": True, "why": "The pattern holds in every period North checked and nothing open covers it yet.", "confidence": conf,
                                     "start_answers": _start_answers(cand, rec["id"], [known[a] for a in areas]), "at": check["at"], "drafted_by": "rules"}
            O._hist(rec, "north", "judged_yes" if rec["judgement"]["fits"] else "judged_no")
            if rec["judgement"]["fits"]:
                rec["state"] = "proposed"
                O._hist(rec, "north", "proposed")
        O._save(plane, rec)
    return rec


def hypothesis_for_56(plane, rec: dict, cat: dict, cov: dict) -> None:
    """A 56 record without a hypothesis (the Watcher's run-log patterns, a person's raise): North writes one from the record itself."""
    ms = [str(m).upper() for m in rec["touches"]["measures"]]
    metas = [cat[m] for m in ms if m in cat]
    lens = lens_of(" ".join(f"{m['name']} {m['unit']} {' '.join(m['keywords'])}" for m in metas)) or lens_of(f"{rec['title']} {rec['pattern']['text']}") or "process_cost"
    link = next((cov[m] for m in ms if m in cov), None)
    lines = [H.evidence_line(i + 1, "data", "supports", n["label"], n["trace"], "watcher") for i, n in enumerate(rec["pattern"]["numbers"])]
    for e in rec["evidence"]:
        lines.append({**H.evidence_line(len(lines) + 1, H.record_kind_of((e.get("source") or {}).get("kind")), "counters" if e["kind"] == "disputes" else "supports",
                                        e["text"], {"kind": (e.get("source") or {}).get("kind"), "ref": (e.get("source") or {}).get("ref"), "at": e["at"]}, e["by"])})
    check = {"at": H.now(), "looked_for": ["an open Initiative or Decision on the same measure"], "found": [f"An open {link['kind']} covers it: {link['title']}."] if link else [],
             "verdict": "holds", "why": f"An open {link['kind'].capitalize()} already covers this: {link['title']}." if link else "Nothing open covers it."}
    hyp = H.create(plane, {"kind": "opportunity", "ref": rec["id"]}, {"belief": rec["pattern"]["text"], "lens": lens,
                   "measure": {"id": ms[0], "name": cat.get(ms[0], {}).get("name", ms[0])} if ms else None, "evidence": lines, "counter_check": check,
                   "confidence": _confidence(check, lines, False), "drafted_by": "rules"}, "north", state="checked")
    with lock_for(O._dir(plane) / f"{rec['id']}.json"):
        cur = O.get(plane, rec["id"])
        cur.update(hypothesis_ref=H.ref(hyp), evidence=[], linked={"kind": link["kind"], "id": link["id"], "title": link["title"]} if link else None)
        cur.setdefault("pattern", {}).setdefault("kind", "data")
        O._hist(cur, "north", "hypothesis_written")
        O._save(plane, cur)


def scan(plane, pack, today: date | None = None, north=None) -> dict:
    """One scan: the Watcher, Lens and North in turn. Writes new records only (never a second record for a pattern already on file) and
    three rows to `intents/radar/scans.jsonl`. Returns the counts."""
    s, today = settings(plane), today or datetime.now(timezone.utc).date()
    cat = measure_catalogue(pack)
    known = {a["id"]: a["name"] for a in areas_store.listing(profile_store.load(plane)) if a["status"] == "active"}
    try:
        O.run_watcher(plane, today, {k: v["name"] for k, v in cat.items()})
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("the Watcher's run-log step failed: %s", type(e).__name__)
    gold, silver, cands = {}, {}, []
    docs, vs = documents(plane), voices(plane)
    cov = covers(plane, cat)
    try:
        con = warehouse.open_readonly(plane)
    except duckdb.Error as e:
        log.info("no read-only warehouse copy: %s", type(e).__name__)
        con = None
    try:
        if con is not None:
            gold, silver = _gold(con), _silver_columns(con)
            sig = watch_gold(gold, s["min_periods_for_pattern"])
            cands += data_candidates(sig, cov, cat, s["counter_periods"])
            cands += claims(docs, cat, gold, con, silver, s["min_periods_for_pattern"], s["counter_periods"])
    finally:
        if con is not None:
            con.close()
    for c in cands:
        if c["kind"] == "data" and c["noticed_by"] == "watcher":
            have = {(e["trace"]["kind"], e["trace"]["ref"]) for e in c["evidence"]}
            c["evidence"] += [e for e in doc_lines(docs, c["metas"]) + voice_lines(vs, c["metas"]) if (e["trace"]["kind"], e["trace"]["ref"]) not in have]
    cands += theme_candidates(themes(vs, s["theme_min_voices"]))
    existing = O.all_records(plane)
    keys = {(r.get("pattern") or {}).get("key") for r in existing}
    theme_refs = [{e["ref"] for e in (H.latest(H.get(plane, (r.get("hypothesis_ref") or {}).get("id", "")) or {}) or {}).get("evidence") or [] for e in [e.get("trace") or {}]}
                  for r in existing if (r.get("pattern") or {}).get("kind") == "theme"]
    made = []
    for c in cands:
        if c["key"] in keys:
            continue
        if c["kind"] == "theme":
            refs = {e["trace"]["ref"] for e in c["evidence"]}
            if any(len(refs & old) * 2 >= len(refs) for old in theme_refs):
                continue
        made.append(_write(plane, c, known, north))
        keys.add(c["key"])
    for r in O.all_records(plane):
        if not r.get("hypothesis_ref") and r["state"] in O.LIVE:
            hypothesis_for_56(plane, r, cat, cov)
    counts = {"drafted": sum(1 for r in made if r["state"] != "rejected"), "rejected": sum(1 for r in made if r["state"] == "rejected")}
    at = H.now()
    rows = [{"at": at, "by": "watcher", "read": {"feeds": sum(len(v) for v in gold.values())}, "drafted": sum(1 for c in made if c["noticed_by"] == "watcher"), "rejected": 0},
            {"at": at, "by": "lens", "read": {"documents": len(docs), "voices": len(vs)}, "drafted": sum(1 for c in made if c["noticed_by"] == "lens"), "rejected": 0},
            {"at": at, "by": "north", "read": {"opportunities": len(made)}, "drafted": counts["drafted"], "rejected": counts["rejected"]}]
    log_file = plane.path("intents", "radar", "scans.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(log_file):
        with log_file.open("a", encoding="utf-8") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
    return {**counts, "made": [r["id"] for r in made]}


def last_scan(plane) -> dict | None:
    try:
        lines = plane.path("intents", "radar", "scans.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    rows = [json.loads(ln) for ln in lines if ln.strip().startswith("{")]
    return rows[-1] if rows else None


def scan_daily(plane, pack) -> dict | None:
    """The runner's step after the last run of the day (C5): scans once a day. Also the on-read fallback."""
    last = last_scan(plane)
    if last and str(last.get("at", ""))[:10] == datetime.now(timezone.utc).date().isoformat():
        return None
    return scan(plane, pack)


# ---- routes ------------------------------------------------------------------------------------------------------------------------------
def _pack(request: Request):
    co = request.app.state.entitlements.company(request.state.company_id) or {}
    return request.app.state.packs.load(str(co.get("industry") or "-"))


def _north(request: Request, plane):
    """North's model-backed judgement through the agent runtime and the egress gateway (R14); None falls back to the rules."""
    def go(rec: dict):
        try:
            j = O.judge(request, plane, {**rec, "evidence": O.evidence_of(plane, rec)})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            log.warning("North could not judge on the radar: %s", type(e).__name__)
            return None
        return {**j, "drafted_by": "north"} if j else None
    return go


def _card(ctx: O.Ctx, rec: dict, full: bool) -> dict:
    hyp = H.get(ctx.plane, (rec.get("hypothesis_ref") or {}).get("id", ""))
    v = H.latest(hyp) or {}
    nm = {v["measure"]["id"]: v["measure"]["name"]} if (v.get("measure") or {}).get("name") else {}
    # the pack may not know a code the baseline does: use the hypothesis's own measure name, else keep the code, never "a measure"
    w = lambda t: re.sub(r"\bK\d+\b", lambda m: "a restricted measure" if ctx.shut(m.group(0)) else ctx.names.get(m.group(0)) or nm.get(m.group(0), m.group(0)), t) if isinstance(t, str) else t  # noqa: E731
    out = {"id": rec["id"], "title": w(rec["title"]), "lens": v.get("lens"), "confidence": v.get("confidence"), "state": rec["state"],
           "dashed": rec["state"] == "proposed", "theme": {"voices": v["theme"]["voices"]} if v.get("theme") else None, "href": f"/centre/intent/backlog?opportunity={rec['id']}"}
    if not full:
        return out
    shut = any(ctx.shut(m) for m in rec["touches"]["measures"])
    mix = {k: sum(1 for e in v.get("evidence") or [] if e["record_kind"] == k) for k in ("data", "document", "voice")}
    return {**out, "belief": w(v.get("belief")), "measure": None if not v.get("measure") else ("A restricted measure" if shut else ctx.names.get(v["measure"]["id"], v["measure"]["name"])),
            "baseline": None if shut else v.get("baseline"), "target": v.get("target"), "expected_uplift": v.get("expected_uplift"),
            "uplift_missing": H.missing_uplift(v) if v else "Not available yet: no hypothesis", "expected_uplift_missing": H.missing_uplift(v) if v else "Not available yet: no hypothesis",
            "baseline_missing": None if v.get("baseline") and not shut else "Not available yet: a restricted measure" if shut else "Not available yet: no baseline" if v.get("measure") else "Not available yet: no measure for this theme",
            "target_missing": None if v.get("target") else "No target yet. Set one or leave it for the start questions.",
            "evidence_mix": mix, "review_date": v.get("review_date"), "hypothesis_ref": rec.get("hypothesis_ref"),
            "linked": rec.get("linked"), "verdict": (v.get("counter_check") or {}).get("verdict")}


def _mine(ctx: O.Ctx, rec: dict, owned: set[str]) -> bool:
    acct = ctx.viewer.account_id
    v = H.latest(H.get(ctx.plane, (rec.get("hypothesis_ref") or {}).get("id", ""))) or {}
    if acct and any(e.get("by") == acct for e in v.get("evidence") or []):
        return True
    return bool({x.lower() for k in ("measures", "sources", "processes") for x in rec["touches"][k]} & owned)


def _owned(plane, viewer) -> set[str]:
    """Measure, source and process ids the viewer owns on the map (55: owned_by edges to the viewer's person node)."""
    try:
        g = read_json_strict(plane.path("graph", "company.json"), dict) or {}
    except (OSError, ValueError):
        return set()
    me = "person:" + re.sub(r"[^a-z0-9]+", "-", str(viewer.name or "").lower()).strip("-")
    return {str(e["from"]).split(":", 1)[-1].lower() for e in g.get("edges") or [] if e.get("type") == "owned_by" and e.get("to") == me}


def radar_view(ctx: O.Ctx, scope: str, area: str | None, lens: str | None) -> dict:
    s = settings(ctx.plane)
    recs = [r for r in O.all_records(ctx.plane) if ctx.sees(r)]
    full = bool(ctx.viewer.roles & ACT_ROLES)
    if scope == "area":
        recs = [r for r in recs if not r["areas"] or area in r["areas"]]
    elif scope == "mine":
        owned = _owned(ctx.plane, ctx.viewer)
        recs = [r for r in recs if _mine(ctx, r, owned)]
    least = RANK[s["min_confidence_to_show"]]
    cards = [_card(ctx, r, full) for r in recs]
    open_cards = [c for c in cards if c["state"] in O.OPEN and RANK.get(c["confidence"] or "not_sure", 1) >= least]
    columns = [{"lens": k, "label": LENS_LABEL[k], "count": sum(1 for c in open_cards if c["lens"] == k),
                "cards": [c for c in open_cards if c["lens"] == k]} for k in LENS_LABEL if not lens or lens == k]
    aside = [{"id": r["id"], "title": O._words(ctx, r["title"]), "why": O._words(ctx, (r.get("rejected") or {}).get("why")), "broke_by": (r.get("rejected") or {}).get("broke_by") or [],
              "at": (r.get("rejected") or {}).get("at"), "href": f"/centre/intent/backlog?opportunity={r['id']}"} for r in recs if r["state"] == "rejected"]
    unset = [k for k in s["unset"] if k not in ("scan", "min_confidence_to_show")]
    last = last_scan(ctx.plane)
    return {"scope": scope, "area": area, "lens": lens, "opportunities": open_cards, "rejected": aside, "columns": columns, "nothing_noticed": not O.all_records(ctx.plane),
            "hidden_below_confidence": sum(1 for c in cards if c["state"] in O.OPEN) - len(open_cards),
            "scan": {"last_at": (last or {}).get("at"), "read": _read_counts(ctx.plane), "schedule": s["scan"],
                     "thresholds": {"total": len(RADAR_KEYS), "missing": s["unset"], "values": {k: s[k] for k in RADAR_KEYS}}},
            "notice": f"Not available yet. {len(unset)} of {len(RADAR_KEYS) - 2} radar thresholds are not set, so those checks use the company defaults." if unset else None,
            "areas": [{"id": a, "name": n} for a, n in _area_names(ctx).items()], "can_scan": ctx.admin, "can_set_thresholds": ctx.admin, "full": full}


def _read_counts(plane) -> dict | None:
    """What the last scan read, summed over its three rows (Watcher, Lens, North)."""
    try:
        lines = plane.path("intents", "radar", "scans.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    rows = [json.loads(ln) for ln in lines if ln.strip().startswith("{")]
    if not rows:
        return None
    out: dict[str, int] = {}
    for r in rows[-3:]:
        if r.get("at") == rows[-1].get("at"):
            for k, n in (r.get("read") or {}).items():
                out[k] = out.get(k, 0) + n
    return out


def _area_names(ctx: O.Ctx) -> dict[str, str]:
    return {a["id"]: a["name"] for a in areas_store.listing(profile_store.load(ctx.plane)) if a["status"] == "active" and a["id"] in ctx.areas}


@router.get("/api/intents/radar")
def get_radar(request: Request, scope: str = "lens", area: str = "", lens: str = ""):
    if scope not in ("mine", "area", "lens") or (lens and lens not in LENS_LABEL):
        return _plain(422, "scope", "Choose my line of work, an area or a business view.")

    def work(plane):
        ctx = O.Ctx(request, plane)
        if "super_admin" in ctx.viewer.roles:
            return _plain(403, "not_your_role", "The radar belongs to the company.")
        if settings(plane)["scan"] == "on_read" or last_scan(plane) is None:
            try:
                scan_daily(plane, _pack(request))
            except (OSError, ValueError, KeyError, TypeError, duckdb.Error) as e:  # a failed scan must never hide the records
                log.warning("the radar scan failed: %s", type(e).__name__, exc_info=True)
        if scope == "area" and area not in ctx.areas:
            return {**radar_view(ctx, "area", None, None), "columns": [], "message": "You are not tagged to an area. Ask your company admin." if not ctx.areas else "Pick one of your areas."}
        return radar_view(ctx, scope, area or None, lens or None)
    return O._guard(request, work)


@router.post("/api/intents/radar/scan")
async def post_radar_scan(request: Request):
    def work(plane):
        ctx = O.Ctx(request, plane)
        if not ctx.admin:
            return _plain(403, "not_your_role", "Only the company admin can run the radar now.")
        return scan(plane, _pack(request), north=_north(request, plane))
    return await run_in_threadpool(O._guard, request, work)


def _hyp_visible(ctx: O.Ctx, rec: dict) -> bool:
    origin = rec.get("origin") or {}
    if origin.get("kind") == "opportunity":
        opp = O.get(ctx.plane, origin.get("ref"))
        return bool(opp and ctx.sees(opp))
    from sh_platform.intents import visibility as vis
    intent = vis.load_intent(ctx.plane, str(origin.get("ref") or ""))
    return bool(intent and vis.may_open_content(ctx.plane, intent, ctx.viewer))


@router.get("/api/intents/hypotheses/{hyp_id}")
def get_hypothesis(request: Request, hyp_id: str):
    def work(plane):
        ctx = O.Ctx(request, plane)
        rec = H.get(plane, hyp_id)
        if rec is None or "super_admin" in ctx.viewer.roles or not _hyp_visible(ctx, rec):
            return _plain(404, "not_found", O.NOT_FOUND)
        return shape_hypothesis(ctx, rec)
    return O._guard(request, work)


def shape_hypothesis(ctx: O.Ctx, rec: dict) -> dict:
    """The record for a screen: names for codes, a document line shows its title only to whoever may open the shelf, anonymous voices unnamed."""
    w = lambda t: O._words(ctx, t)  # noqa: E731
    opp = O.get(ctx.plane, rec["origin"]["ref"]) if rec["origin"].get("kind") == "opportunity" else None
    shut = bool(opp) and any(ctx.shut(m) for m in opp["touches"]["measures"])

    def line(e):
        by = "Someone, anonymously" if e["by"] == "anonymous" else O._who(ctx.request, e["by"]) if e["by"] in O.LABEL else O._who(ctx.request, e["by"])
        return {**e, "text": w(e["text"]), "by": by}

    def ver(v):
        return {**v, "belief": w(v["belief"]), "by": O._who(ctx.request, v["by"]), "evidence": [line(e) for e in v.get("evidence") or []],
                "baseline": None if shut else v.get("baseline"), "counter_check": v.get("counter_check") and {**v["counter_check"], "why": w(v["counter_check"]["why"]),
                                                                                                          "found": [w(x) for x in v["counter_check"].get("found") or []]},
                "uplift_missing": H.missing_uplift(v), "lens_label": LENS_LABEL.get(v.get("lens"))}
    named = sorted({O._who(ctx.request, e["by"]) for e in (H.latest(rec) or {}).get("evidence") or [] if e["record_kind"] == "voice" and e["by"] not in ("anonymous", "lens", "watcher", "north")})
    versions = [ver(v) for v in rec["versions"]]
    return {"id": rec["id"], "origin": rec["origin"], "state": rec["state"], "carried_into": rec.get("carried_into") or [], "latest": versions[-1],
            "versions": versions, "voices_named": named}


@router.post("/api/intents/opportunities/{opp_id}/hypothesis")
async def post_opportunity_hypothesis(request: Request, opp_id: str):
    body = await _json_body(request, 4096)
    if isinstance(body, JSONResponse):
        return body

    def work(plane):
        ctx = O.Ctx(request, plane)
        rec = O._find(ctx, opp_id)
        if rec is None:
            return _plain(404, "not_found", O.NOT_FOUND)
        if not ctx.viewer.roles & {"owner", "analyst"}:
            return _plain(403, "opportunity_not_your_role", "Only the ops manager or the business analyst can change the hypothesis.")
        if rec["state"] in ("picked_up", "dismissed"):
            return _plain(409, "closed", "This opportunity is closed, so its hypothesis can no longer change.")
        hyp = H.get(plane, (rec.get("hypothesis_ref") or {}).get("id", ""))
        if hyp is None:
            return _plain(409, "no_hypothesis", "North has not written a hypothesis yet. It waits for Lens's evidence.")
        v, by, ch = H.latest(hyp), ctx.viewer.account_id or "unknown", {}
        if "lens" in body:
            if body["lens"] not in LENS_LABEL:
                return _plain(422, "lens", "Choose new revenue, process cost, retention or risk.")
            ch["lens"] = body["lens"]
        if "target" in body:
            t = body["target"]
            if t is None:
                ch["target"] = None
            elif not (isinstance(t, dict) and isinstance(t.get("value"), (int, float)) and not isinstance(t.get("value"), bool) and math.isfinite(t["value"])
                      and isinstance(t.get("by"), str) and O._valid_date(t["by"])):
                return _plain(422, "target", "A target needs a number and a date.")
            else:
                ch["target"] = {"value": t["value"], "unit": (v.get("measure") and (v.get("baseline") or {}).get("unit")) or None, "by": t["by"], "set_by": by}
            if not v.get("expected_uplift") or v["expected_uplift"].get("basis") == "gap_to_target":
                ch["expected_uplift"] = H.uplift_gap(v.get("baseline"), ch["target"])
        if "review_date" in body:
            if not (isinstance(body["review_date"], str) and O._valid_date(body["review_date"])):
                return _plain(422, "review_date", "A review date is needed.")
            ch["review_date"] = body["review_date"]
        if not ch:
            return _plain(422, "nothing", "Change the business view, the target or the review date.")
        H.add_version(plane, hyp["id"], ch, by)
        with lock_for(O._dir(plane) / f"{rec['id']}.json"):
            cur = O.get(plane, rec["id"])
            cur["hypothesis_ref"] = H.ref(H.get(plane, hyp["id"]))
            O._hist(cur, by, "hypothesis_changed", ", ".join(sorted(ch)))
            O._save(plane, cur)
        return O._shape(O.Ctx(request, plane), O.get(plane, rec["id"]))
    return await run_in_threadpool(O._guard, request, work)


def pulse_lines(plane, request: Request) -> list[dict]:
    """The three Pulse lines of 57 (Nira, kind decision) for the viewer."""
    from sh_platform.pulse.lines import line
    ctx, out = O.Ctx(request, plane), []
    acct = ctx.viewer.account_id
    for r in O.all_records(plane):
        if not r.get("hypothesis_ref") or not ctx.sees(r):
            continue
        href, rec_ref = f"/centre/intent/backlog?opportunity={r['id']}", f"intents/opportunities/{r['id']}.json"
        hyp = H.latest(H.get(plane, r["hypothesis_ref"]["id"])) or {}
        what = O._words(ctx, (hyp.get("measure") or {}).get("id") or r["title"])
        if "analyst" in ctx.viewer.roles and r["state"] in ("under_review", "proposed") and not r.get("linked"):
            out.append(line(f"radar:{r['id']}:hypothesis", "decision", f"North wrote a hypothesis on {what}. Check its evidence.", "", href, "Open it", rec_ref, hyp.get("at")))
        if r["state"] == "rejected" and acct and r["noticed_by"] == acct:
            out.append(line(f"radar:{r['id']}:rejected", "decision", f"North rejected a pattern: {O._words(ctx, r['title'])}. See why.", "", href, "Open it", rec_ref, (r.get("rejected") or {}).get("at")))
        for p in r.get("links_proposed") or []:
            if acct and p.get("decider") == acct and not p.get("confirmed"):
                out.append(line(f"radar:{r['id']}:decision", "decision", f"A hypothesis touches the open Decision {p['title']}.", "", href, "Open it", rec_ref, hyp.get("at")))
    return out


def install(app) -> None:
    """Called once from sh_platform/app.py, before the routes that take /api/intents/{intent_id}."""
    app.include_router(router)
