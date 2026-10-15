"""BC-3: the Architect's deterministic first draft of build/blueprint.json (docs/plan/SHAPES.md shape 2). No model call.

Pure functions over dicts the caller has read: the signed baseline's measures (kpis.json, with their technical definitions and governance), the
catalogue (five tabs, each cell a provenance value), the module 3 scan rules and trial results, the environment check and the profile's
constraints. Every field of the draft gets a provenance mark in `provenance`, keyed by its dotted path (`lineage.0.transform`): `guessed`
with where it came from, or the environment answer's own mark when a person stated it.

Reuse: the earlier repo's emitters/model_drafting.py and architecture_drafting.py were read (copy-first). Both ask a model for a plan and then
check it against built tables; neither has a deterministic fact and dimension derivation, so nothing was copied. What carries over is the
idea (a model is drafted, never trusted, every name it uses must exist) and the checks: grain entities become dimensions, measures with the
same entities share a fact.
"""
import re
from datetime import datetime, timezone
from typing import Any

BY = "Span"  # S1: Span, the solution architect, signs the rule-based draft too (it is Span's fallback)
NOT_STATED = "Not stated"
STOP = {"one", "row", "rows", "record", "records", "each", "a", "the", "every", "entry", "entries"}
SEVERITY_OF_SCAN = {"missing_field": "block", "fill_rate": "warn", "period_gap": "warn", "missing_benchmark": "inform"}  # an assumption, see report
HEADS = {"src_id": "Source ID", "src_name": "Source name", "src_sla": "Expected arrival time or SLA", "src_freq": "How often it arrives",
         "item_id": "Item ID", "field_name": "Field name as in the source", "feeds": "Feeds KPI", "valid_from": "Valid from", "valid_to": "Valid to",
         "extract_name": "What to extract", "extract_item": "Item ID (document type)"}
SECTIONS = {"band": "Default: the first plan band", "model": "Technical definitions (grain) and catalogue fields of the signed baseline",
            "lineage": "Catalogue sources and fields, and the technical definition, of the signed baseline",
            "rules": "Module 3 scan quality rules and trial results", "access": "Governed state of the signed baseline (who may see it)",
            "schedule": "Environment check, catalogue arrivals and the profile's deadline constraints", "infra": "Environment check"}


def snake(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def val(cell: Any) -> Any:
    return cell.get("value") if isinstance(cell, dict) and cell.get("mark") != "unknown" else None


def text(cell: Any) -> str:
    v = val(cell)
    return " ".join(str(v).split()) if v is not None and not isinstance(v, (list, dict)) else ""


def ids(cell: Any) -> list[str]:
    v = val(cell)
    parts = v if isinstance(v, list) else re.split(r"[,;\s]+", str(v or ""))
    return [str(p).strip() for p in parts if str(p).strip()]


def entities(grain: str) -> list[str]:
    """'One row per account per day' -> ['account', 'day']: the things the grain names."""
    out = []
    for seg in re.split(r"\s*(?:,|;|\band\b|\bper\b|\bby\b|\bof\b)\s*", grain.lower()):
        words = [w for w in re.findall(r"[a-z0-9]+", seg)]
        if words and not all(w in STOP for w in words):
            out.append("_".join(w for w in words if w not in STOP))
    return list(dict.fromkeys(out))


def _model(kpis: list[dict], fields: list[dict]) -> dict:
    groups: dict[tuple, dict] = {}
    for k in kpis:
        grain = text((k.get("technical") or {}).get("grain"))
        ents = tuple(entities(grain))
        g = groups.setdefault(ents, {"name": "fact_" + "_".join(ents) if ents else "fact_grain_not_stated", "grain": grain or NOT_STATED,
                                     "keys": [e + "_key" for e in ents], "measures": []})
        g["measures"].append(str(k["id"]))
    dims = []
    for e in dict.fromkeys(e for ents in groups for e in ents):
        mine = [f for f in fields if e in snake(text(f.get(HEADS["field_name"]))) and not snake(text(f.get(HEADS["field_name"]))).endswith("_key")]
        changes = any(text(f.get(HEADS["valid_from"])) or text(f.get(HEADS["valid_to"])) for f in mine)
        dims.append({"name": "dim_" + e, "keys": [e + "_key"], "attributes": sorted({text(f.get(HEADS["field_name"])) for f in mine}),
                     "scd": 2 if changes else 1})
    return {"facts": list(groups.values()), "dimensions": dims}


def _lineage(kpis: list[dict], cat: dict) -> list[dict]:
    fields, items = {text(r.get("Field ID")): r for r in cat.get("fields", [])}, {}
    for r in cat.get("tables", []):
        items[text(r.get(HEADS["item_id"]))] = text(r.get(HEADS["src_id"]))
    for r in cat.get("extractions", []):  # an extraction row may stand in `fields` (technical.py)
        fields.setdefault(text(r.get("Extract ID")), {HEADS["field_name"]: r.get(HEADS["extract_name"]), HEADS["item_id"]: r.get(HEADS["extract_item"])})
    names = {text(r.get(HEADS["src_id"])): text(r.get(HEADS["src_name"])) for r in cat.get("sources", [])}
    out = []
    for k in kpis:
        code, t = str(k["id"]), k.get("technical") or {}
        wanted = ids(t.get("fields")) or [fid for fid, r in fields.items() if code in ids(r.get(HEADS["feeds"]))]
        by_source: dict[str, list[str]] = {s: [] for s in ids(t.get("sources"))}
        for fid in wanted:
            r = fields.get(fid)
            if r:
                by_source.setdefault(items.get(text(r.get(HEADS["item_id"])), "") or NOT_STATED, []).append(text(r.get(HEADS["field_name"])))
        mart = f"gold.{code.lower()}.{snake(k.get('name') or code)}"
        calc = text(t.get("calculation")) or NOT_STATED
        for sid, cols in by_source.items() or {NOT_STATED: []}.items():
            out.append({"measure": code, "source": names.get(sid) or sid, "fields": sorted(dict.fromkeys(cols)), "transform": calc, "mart": mart})
    return out


def _rules(quality: dict, trials: dict) -> list[dict]:
    out = []
    for code, rules in sorted((quality or {}).items()):
        for r in rules if isinstance(rules, list) else []:
            if isinstance(r, dict) and r.get("text"):
                out.append({"measure": str(code), "rule": str(r["text"]), "severity": SEVERITY_OF_SCAN.get(r.get("kind"), "warn"), "from": "scan"})
    for code, t in sorted((trials or {}).items()):
        res = (t or {}).get("result")
        why = (t.get("likely_reason") or t.get("missing") or "") if isinstance(t, dict) else ""
        if res == "matches":
            out.append({"measure": str(code), "rule": "Our figure matches the reported figure", "severity": "inform", "from": "trial"})
        elif res in ("gap", "cannot"):
            out.append({"measure": str(code), "severity": "warn", "from": "trial",
                        "rule": "Our figure must match the reported figure" + (f" (trial: {why})" if why else "")})
    return out


def _access(kpis: list[dict]) -> list[dict]:
    out = []
    for k in kpis:
        g = k.get("governance") if isinstance(k.get("governance"), dict) else {}
        restricted = g.get("personal") != "no" or bool(g.get("sensitive"))  # as modules/m3_connect/domain/inputs.py `_restricted`: "not sure" is closed
        out.append({"mart": f"gold.{str(k['id']).lower()}", "may_see": list(g.get("may_see") or []) if restricted else None})
    return out


def _schedule(cat: dict, arrival: str, deadlines: list[str]) -> list[dict]:
    wd = next((f"WD{m.group(1) or m.group(2)}" for d in deadlines if (m := re.search(r"working day (\d+)|\bWD ?(\d+)", d, re.I))), None)
    return [{"source": text(r.get(HEADS["src_name"])) or text(r.get(HEADS["src_id"])),
             "expected": text(r.get(HEADS["src_sla"])) or text(r.get(HEADS["src_freq"])) or arrival or NOT_STATED,
             "sla": wd or NOT_STATED, "depends_on": []} for r in cat.get("sources", [])]


def draft(kpis: list[dict], cat: dict, quality: dict, trials: dict, env: dict, constraints: list[str]) -> dict:
    """`env` is build_env.read(...)['questions'] as {key: cell}. Returns the whole blueprint, version 1, state draft."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    loc, sched = env.get("warehouse_location") or {}, env.get("scheduler") or {}
    warehouse = "plane" if "plane" in text(loc).lower() or not text(loc) else text(loc)
    runner = "airflow" if "airflow" in text(sched).lower() else "builtin"
    doc = {"version": 1, "state": "draft", "signed_by": [], "band": "now",
           "model": _model(kpis, cat.get("fields", [])), "lineage": _lineage(kpis, cat), "rules": _rules(quality, trials), "access": _access(kpis),
           "schedule": _schedule(cat, text(env.get("arrival")), constraints), "infra": {"warehouse": warehouse, "runner": runner}}
    doc["provenance"] = marks(doc, now, {"infra.warehouse": env.get("warehouse_location"), "infra.runner": env.get("scheduler")})
    return doc


def _leaves(node: Any, path: str = "") -> list[str]:
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _leaves(v, f"{path}.{k}" if path else k)]
    if isinstance(node, list) and any(isinstance(v, (dict, list)) for v in node):
        return [p for i, v in enumerate(node) for p in _leaves(v, f"{path}.{i}")]
    return [path]


def marks(doc: dict, now: str, cells: dict[str, Any]) -> dict:
    """One provenance entry per field. A field taken from an environment answer carries that answer's mark (stated stays stated)."""
    out = {}
    for p in (p for k in SECTIONS if k in doc for p in _leaves(doc[k], k)):
        c = cells.get(p)
        if isinstance(c, dict) and c.get("mark") == "stated":
            out[p] = {"mark": "stated", "from": c.get("from") or SECTIONS["infra"], "by": c.get("by") or BY, "at": c.get("at") or now}
        else:
            out[p] = {"mark": "guessed", "from": SECTIONS[p.split(".")[0]], "by": BY, "at": now}
    return out
