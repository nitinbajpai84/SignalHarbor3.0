"""Harbor 3.0 industry model and language (spec: docs/v3/HARBOR-SPEC.md, "Industry model").

Every office of one industry starts on the same model, read from its pack (`packs/<industry>/<n>/model.yaml`) through the pack loader.
What an office adds, admits or says lives only in its own data plane, `<company>/v3/model.json`, and never reaches the pack or another
office. A company whose industry has no pack gets an honest empty model. Nothing here names an industry."""
from __future__ import annotations

import hashlib
import logging
import re
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
NO_PACK = "No industry model is available for this industry yet. You can still add your own words and tables."
NOT_FOUND = "I cannot find that one."


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _pid(*parts) -> str:
    return "p-" + hashlib.sha256("|".join(_slug(p) for p in parts).encode()).hexdigest()[:10]


# ---- the pack and the office layer ----------------------------------------------------------------------------------------------------

def _packs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs"


def industry_of(plane) -> str:
    """The company's industry from its profile; empty when it has none."""
    from sh_platform.entitlements import EntitlementStore
    return str((EntitlementStore(plane.root.parent).company(plane.company_id) or {}).get("industry") or "")


def pack_of(plane):
    """The company's pack, or None (no industry, or an industry with no pack: never another industry's content)."""
    from sh_platform.packs import PackLoader
    industry = industry_of(plane)
    if not industry:
        return None
    try:
        pack = PackLoader(_packs_root()).load(industry)
    except ValueError:
        return None
    return None if pack.empty else pack


def _section(pack, name: str, default):
    if pack is None:
        return default
    with suppress(KeyError):
        return pack.section(name) or default
    return default


def _path(plane) -> Path:
    return plane.path("v3", "model.json")


def layer(plane) -> dict:
    """The office layer: additions, rejected proposal ids, versions, words, corrections, golden answers."""
    try:
        doc = read_json_strict(_path(plane), dict) or {}
    except (OSError, ValueError):
        log.warning("the office model of %s could not be read; starting empty", plane.company_id)
        doc = {}
    return {k: doc.get(k) or [] for k in ("additions", "rejected", "versions", "words", "corrections", "golden")}


def _save(plane, doc: dict) -> None:
    _path(plane).parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(_path(plane), doc)


def _change(plane, who: str, change: str, edit) -> dict:
    """Apply `edit(doc)` to the office layer under a lock; a version entry records what changed and who."""
    with lock_for(_path(plane).with_suffix(".lock")):
        doc = layer(plane)
        edit(doc)
        if change:
            doc["versions"].append({"v": len(doc["versions"]) + 1, "at": _now(), "by": who, "change": change})
        _save(plane, doc)
    return doc


# ---- the model ----------------------------------------------------------------------------------------------------------------------

def _count(plane, table: str) -> int | None:
    """Rows of a ready table, read-only through the warehouse helper; None when there is no warehouse or no such table."""
    from sh_platform.v1 import wh
    if not wh.path(plane).is_file():
        return None
    try:
        with wh.connect(plane, read_only=True) as con:
            found = con.execute("select table_schema from information_schema.tables where table_name = ? and table_schema in ('main', 'silver') "
                                "order by table_schema", [table]).fetchall()
            return int(con.execute(f'select count(*) from {found[0][0]}."{table}"').fetchone()[0]) if found else None
    except Exception:  # noqa: BLE001 - a busy or odd warehouse is a count we cannot give, not a broken page
        log.warning("could not count %s for %s", table, plane.company_id)
        return None


def _mapped_columns(plane) -> list[dict]:
    """Columns of the proposed and approved 2.0 intake mappings: {source, table, field, new, sheet}."""
    from sh_platform.v1 import e0b_mappings as MP
    out = []
    for m in MP.listing(plane):
        if m.get("state") not in ("proposed", "approved"):
            continue
        for c in m.get("columns") or []:
            out.append({"source": str(c.get("source") or ""), "table": str(c.get("target_table") or ""), "field": str(c.get("target_field") or ""),
                        "new": bool(c.get("new")), "sheet": MP.col_key(m.get("sheet") or "").replace(" ", "_")})
    return [c for c in out if c["source"]]


def _prop(p: dict, origin: str) -> dict:
    return {k: v for k, v in {"name": p["name"], "label": p.get("label") or p["name"], "column": p.get("column"), "derived": p.get("derived"),
                              "from": origin}.items() if v is not None}


def _objects(pack, lay: dict) -> list[dict]:
    """Industry objects with the office's admitted additions on them; admitted additions to an unknown table make an office object."""
    objs = {}
    for o in _section(pack, "model", {}).get("objects") or []:
        objs[o["name"]] = {"name": o["name"], "label": o.get("label") or o["name"], "table": o.get("table") or o["name"], "from": "industry", "about": o.get("about") or "",
                           "properties": [_prop(p, "industry") for p in o.get("properties") or []], "relations": list(o.get("relations") or [])}
    for a in lay["additions"]:
        o = objs.setdefault(a["object"], {"name": a["object"], "label": a.get("object_label") or a["object"], "table": a["table"], "from": "office",
                                          "properties": [], "relations": []})
        o["properties"].append(_prop(a, "office"))
    return list(objs.values())


def _lands(objs: list[dict], c: dict) -> bool:
    keys = {_slug(p.get("column")) for o in objs for p in o["properties"] if p.get("column")}
    return any(o["table"] == c["table"] and any(p["name"] == c["field"] for p in o["properties"]) for o in objs) or _slug(c["source"]) in keys


def _proposals(objs: list[dict], cols: list[dict], lay: dict) -> list[dict]:
    """One per mapped column with no model property, and per new column flagged in intake (once each; answered ones are gone)."""
    done = {a["id"] for a in lay["additions"]} | set(lay["rejected"])
    by_table = {o["table"]: o for o in objs}
    out = {}
    for c in cols:
        if _lands(objs, c) or not (c["table"] or c["new"]):
            continue
        table, name = (c["table"], c["field"] or _slug(c["source"])) if c["table"] else (c["sheet"], _slug(c["source"]))
        pid = _pid(table, name)
        o = by_table.get(table)
        obj = o["name"] if o else _slug(table)
        out.setdefault(pid, {"id": pid, "text": f"Add \"{c['source']}\" to {o['label'] if o else table.replace('_', ' ')} as {name}",
                             "object": obj, "property": name, "table": table, "column": c["source"], "new_object": o is None})
    return [p for p in out.values() if p["id"] not in done]


def _model_state(plane):
    pack, lay = pack_of(plane), layer(plane)
    objs = _objects(pack, lay)
    cols = _mapped_columns(plane) if pack is not None else []
    return pack, lay, objs, cols, (_proposals(objs, cols, lay) if pack is not None else [])


def model(plane) -> dict:
    pack, lay, objs, cols, props = _model_state(plane)
    unmapped = sorted({c["source"] for c in cols if not _lands(objs, c)})
    total = len({c["source"] for c in cols})
    for o in objs:
        o["count"] = _count(plane, o["table"]) if o["from"] == "industry" else None
    for p in props:  # a proposal shows on its object, or as a proposed object when its table is new
        if p["new_object"] and not any(o["name"] == p["object"] for o in objs):
            objs.append({"name": p["object"], "label": p["table"].replace("_", " ").title(), "table": p["table"], "from": "proposed", "count": None,
                         "properties": [], "relations": []})
        next(o for o in objs if o["name"] == p["object"])["properties"].append({"name": p["property"], "label": p["column"], "column": p["column"], "from": "proposed"})
    return {"pack": {"id": pack.industry, "label": pack.label, "version": pack.version} if pack is not None else
                    {"id": industry_of(plane) or None, "label": None, "version": None},
            "objects": objs, "coverage": {"pct": round(100 * (total - len(unmapped)) / total) if total else None, "unmapped": unmapped},
            "proposals": [{k: p[k] for k in ("id", "text", "object", "property")} for p in props], "versions": lay["versions"],
            **({} if pack is not None else {"message": NO_PACK})}


def answer_proposal(plane, pid: str, answer: str, who: str) -> dict:
    """Admit adds the property to the office layer (with a version entry and who admitted it); reject hides the proposal. Raises KeyError."""
    pack, lay, objs, cols, props = _model_state(plane)
    p = next((x for x in props if x["id"] == pid), None)
    if p is None:
        raise KeyError(pid)
    if answer == "admit":
        o = next((o for o in objs if o["name"] == p["object"]), None)
        add = {"id": pid, "object": p["object"], "object_label": o["label"] if o else p["table"].replace("_", " ").title(), "table": p["table"],
               "name": p["property"], "label": p["column"], "column": p["column"], "type": "string", "synonyms": [p["column"]], "by": who, "at": _now()}
        _change(plane, who, f"{who} admitted {p['property']} on {add['object_label']}", lambda d: d["additions"].append(add))
    else:
        _change(plane, who, "", lambda d: d["rejected"].append(pid))
    return model(plane)


# ---- packs ------------------------------------------------------------------------------------------------------------------------

def packs(plane) -> dict:
    from sh_platform.packs import PackLoader
    loader, out = PackLoader(_packs_root()), []
    for industry in loader.industries():
        pk = loader.load(industry)
        questions = len(_section(pk, "intent_examples", {}).get("examples") or [])
        with suppress(KeyError):
            questions += len(pk.intents_section("checkin_questions").get("questions") or [])
        out.append({"id": industry, "label": pk.label, "objects": len(_section(pk, "model", {}).get("objects") or []), "questions": questions})
    return {"packs": out, "current": industry_of(plane) or None}


# ---- language ---------------------------------------------------------------------------------------------------------------------

def _taught(plane) -> list[dict]:
    """The teach system's always-on notes and books, with their on/off state."""
    from sh_platform.v1 import teach
    try:
        items = teach._items(plane)
    except (OSError, ValueError):
        return []
    return [{"name": i["title"], "agent": i["agent"], "books": int(i["kind"] == "file"), "always": bool(i.get("always")), "on": bool(i["active"]),
             "version": i.get("version", 1)} for i in items if i["kind"] == "file" or i.get("always")]


def _industry_words(pack) -> list[dict]:
    """Glossary synonyms and model property synonyms, shown as what the industry usually calls things."""
    pairs = []
    for t in _section(pack, "glossary", {}).get("terms") or []:
        pairs += [(s, t["term"]) for s in t.get("synonyms") or []]
    for o in _section(pack, "model", {}).get("objects") or []:
        pairs += [(s, p.get("label") or p["name"]) for p in o.get("properties") or [] for s in p.get("synonyms") or [] if _slug(s) != _slug(p["name"])]
    seen, out = set(), []
    for w, means in pairs:
        if str(w).lower() not in seen:
            seen.add(str(w).lower())
            out.append({"word": str(w), "means": str(means), "by": "from the industry", "used": 0})
    return out


def language(plane) -> dict:
    lay = layer(plane)
    office = [{"word": w["word"], "means": w["means"], "by": w.get("by") or "", "used": w.get("used", 0)} for w in lay["words"]]
    mine = {w["word"].lower() for w in office}
    return {"words": office + [w for w in _industry_words(pack_of(plane)) if w["word"].lower() not in mine],
            "corrections": [{"id": c["id"], "text": c["text"]} for c in lay["corrections"] if c.get("state", "proposed") == "proposed"],
            "golden": [{"q": g["q"], "a": g["a"], "by": g.get("by") or ""} for g in lay["golden"]], "taught": _taught(plane)}


def add_word(plane, word: str, means: str, who: str) -> dict:
    word, means = " ".join(word.split())[:80], " ".join(means.split())[:200]
    if not word or not means:
        raise ValueError("Say the word and what it means.")
    _change(plane, who, "", lambda d: d["words"].__setitem__(slice(None), [w for w in d["words"] if w["word"].lower() != word.lower()]
                                                             + [{"word": word, "means": means, "by": who, "at": _now()}]))
    return language(plane)


def propose_correction(plane, text: str, q: str = "", a: str = "") -> str:
    """For the Ask flow: queue a correction for a person to admit. With a question and answer, admitting also makes it a golden answer."""
    cid = "c-" + hashlib.sha256(f"{text}|{q}|{a}".encode()).hexdigest()[:10]
    _change(plane, "Harbor", "", lambda d: d["corrections"].append({"id": cid, "text": text, "q": q, "a": a, "state": "proposed"})
            if not any(c["id"] == cid for c in d["corrections"]) else None)
    return cid


def answer_correction(plane, cid: str, answer: str, who: str) -> dict:
    if not any(c["id"] == cid and c.get("state", "proposed") == "proposed" for c in layer(plane)["corrections"]):
        raise KeyError(cid)

    def edit(d: dict) -> None:
        c = next(c for c in d["corrections"] if c["id"] == cid)
        c["state"] = "admitted" if answer == "admit" else "rejected"
        if answer == "admit" and c.get("q") and c.get("a"):
            d["golden"].append({"q": c["q"], "a": c["a"], "by": who, "at": _now()})
    _change(plane, who, "", edit)
    return language(plane)
