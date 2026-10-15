"""B3 Mapping sheet: `build/mapping/<iid>.json`, one row per target field, drafted from the signed SOW catalogue, the scan report and the
pipeline contracts (sh_platform.build.contracts.derive). Span proposes the transformations through the runtime (`run_agent`, the egress
gateway); when the model is off or its answer does not parse, a rule-based transformation stands and the sheet says so (`fallback`).
People edit rows; nothing here signs or runs anything.

Reuse (D-031): the contract shape and `slug` from sh_platform.build.contracts; Span's call shape from build/agents/span_suggest._ask; the
workbook's look (navy header, frozen header row, widths, text cells kept as text) from 2.0 modules/m2_baseline/domain/xlsx_export.py,
written with openpyxl here instead of raw XML.
"""
from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath

from sh_platform.build import contracts
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
LAYERS = ("landing", "silver", "gold")
STATUSES = ("mapped", "unclear")
EDITABLE = ("source_id", "source_table", "source_field", "transformation", "rule", "test", "status")
MAX_CELL = 500
IID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
FALLBACK = "Span could not reach the model. The transformations come from the field types and names."
COLUMNS = [("n", "No.", 6), ("layer", "Layer", 10), ("target_table", "Target table", 26), ("target_field", "Target field", 24),
           ("source_id", "Source", 18), ("source_table", "Source table", 26), ("source_field", "Source field", 22),
           ("transformation", "Transformation", 48), ("rule", "Rule", 36), ("test", "Test", 32), ("status", "Status", 10)]
SPAN_ROLE = ("You are Span, the solution architect. For each target field of a mapping sheet, propose the transformation from its source field "
             "in one short plain sentence a data engineer can build. Use only the names given. Never invent a source.")
SPAN_QUESTION = ('Answer with one JSON object only: keys are the given "key" values; each value is an object {"source_field": "<one field name '
                 'from source_fields>", "op": "sum" | "latest" | "formula", "transformation": "<one sentence a data engineer can build; never '
                 'write a table name, say the target field>"}. For a gold value: "sum" when the figure is the total of the field over the period, '
                 '"latest" when it is the field\'s last value in the period, "formula" when it needs more than one field or a calculation '
                 "(then say the calculation in the sentence). For a gold period: the period or date field, op \"latest\".")


class NotFound(Exception):
    pass


class Refusal(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check(iid: str) -> str:
    if not isinstance(iid, str) or not IID.match(iid):
        raise NotFound("No such intent.")
    return iid


def _read(plane, *parts):
    try:
        return read_json_strict(plane.path(*parts), dict)
    except (OSError, ValueError):
        log.warning("could not read %s", "/".join(parts))
        return None


def path(plane, iid: str):
    return plane.path("build", "mapping", f"{_check(iid)}.json")


def _meta_path(plane, iid: str):
    return plane.path("build", "mapping", f"{_check(iid)}.meta.json")


def read(plane, iid: str) -> dict | None:
    sheet = _read(plane, "build", "mapping", f"{_check(iid)}.json")
    if sheet is None:
        return None
    meta = _read(plane, "build", "mapping", f"{iid}.meta.json") or {}
    return {"sheet": sheet, "fallback": bool(meta.get("fallback")), "message": FALLBACK if meta.get("fallback") else None,
            "drafted_at": meta.get("at")}


# ---- the rule-based draft (also the fallback) -------------------------------------------------------------------------------------

def _kind(t: str) -> str:
    t = str(t or "").lower()
    return ("date" if "date" in t or "time" in t else "number" if any(w in t for w in ("int", "dec", "num", "float", "money", "amount", "percent"))
            else "text")


def _transformation(layer: str, field: dict, src_field: str, kpis: list[dict]) -> str:
    name, kind = str(field.get("name") or ""), _kind(field.get("type"))
    if not src_field:
        return "Not available yet: no source field is named."
    if layer == "landing":
        return f"Load {src_field} as it arrives."
    if layer == "gold":
        k = next((k for k in kpis if k.get("formula") and (name.lower() in str(k.get("formula")).lower() or name.lower() == str(k.get("code")).lower())), None)
        if k:
            return f"Compute {k.get('name') or k.get('code')}: {k['formula']}."
        return f"Sum {src_field} by period from silver." if kind == "number" else f"Carry {src_field} from silver."
    steps = [] if src_field == name else [f"Rename {src_field} to {name}"]
    steps.append({"date": "parse as a date (year-month-day)", "number": "cast to a decimal number", "text": "trim spaces"}[kind])
    text = ", ".join(steps) + "."
    return text[0].upper() + text[1:]


def _test(field: dict, layer: str) -> str:
    kind = _kind(field.get("type"))
    if layer == "landing":
        return "Row count equals the file's row count."
    return {"date": "Is a valid date; not empty.", "number": "Is a number; not empty.", "text": "Not empty."}[kind]


def draft_rows(plane, sow: dict, scan: dict | None) -> list[dict]:
    sources = {s.get("id"): s for s in sow.get("sources") or [] if isinstance(s, dict)}
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict)]
    status = {k.get("code"): k.get("status") for k in (scan or {}).get("kpis") or [] if isinstance(k, dict)}
    scope = set(((scan or {}).get("agreed") or {}).get("scope") or [])
    contract = {c["source"]: c for c in contracts.derive(plane)}
    rows: list[dict] = []
    for t in sow.get("catalogue") or []:
        if not isinstance(t, dict):
            continue
        feeds = [c for c in t.get("feeds_kpis") or [] if c]
        if scope and feeds and not scope & set(feeds):
            continue  # the decision maker agreed a scope that leaves this table out
        layer = t.get("layer") if t.get("layer") in LAYERS else "silver"
        sid = str(t.get("source_id") or "")
        src = sources.get(sid) or {}
        c = contract.get(contracts.slug(sid)) or contract.get(contracts.slug(src.get("name") or "")) or {}
        paths = [str(p) for p in (src.get("paths") or ([src["sample_path"]] if src.get("sample_path") else []))]
        tname = str(t.get("table") or "")
        hit = next((p for p in paths if tname == contracts.slug(PurePosixPath(p).name) or tname.startswith(contracts.slug(PurePosixPath(p).name) + "_")), None)
        src_table = PurePosixPath(hit or paths[0]).name if paths else c.get("pattern") or src.get("name") or ""
        rules = [r.partition(":")[2].strip() for r in c.get("rules") or [] if r.partition(":")[0] in feeds]
        rules += [g.get("rule") for g in sow.get("governance") or [] if isinstance(g, dict) and t.get("table") in (g.get("applies_to") or [])]
        blocked = feeds and status and all(status.get(f) == "not" for f in feeds)
        own = [k for k in kpis if k.get("code") in feeds]
        for f in t.get("fields") or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            sf = str(f.get("source_field") or "")
            rows.append({"n": len(rows) + 1, "layer": layer, "target_table": str(t.get("table") or ""), "target_field": str(f["name"]),
                         "source_id": sid, "source_table": src_table, "source_field": sf,
                         "transformation": _transformation(layer, f, sf, own), "rule": "; ".join(r for r in rules if r),
                         "test": _test(f, layer), "status": "unclear" if not sf or sid not in sources or blocked else "mapped",
                         "_type": str(f.get("type") or ""), "_meaning": str(f.get("meaning") or "")})
    return rows


# ---- Span ---------------------------------------------------------------------------------------------------------------------------

BATCH = 8


def _letters(i: int) -> str:
    out = ""
    while True:
        out = chr(ord("a") + i % 26) + out
        i = i // 26 - 1
        if i < 0:
            return out


def _span(plane, rt, rows: list[dict], kpis: list[dict], sow_sources: list[dict] | None = None) -> dict[str, dict] | None:
    """{key: transformation} from the model, or None (no model, an error, or an answer that is not the asked JSON)."""
    if rt is None or rt.model is None or not rows:
        return None
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.build.agents import read_tools as T
    from sh_platform.build.agents.runtime import MODULE_ID, SPAN, register_names
    real = [f"{r['target_table']}.{r['target_field']}" for r in rows if r["layer"] != "landing"]
    alias = {_letters(i): k for i, k in enumerate(dict.fromkeys(real))}  # digit-free keys: the reply guard rewrites untraced figures
    back = {v: k for k, v in alias.items()}
    asked = [{"key": back[f"{r['target_table']}.{r['target_field']}"], "target": f"{r['target_table']}.{r['target_field']}", "layer": r["layer"],
              "type": r["_type"], "meaning": r["_meaning"], "source": r["source_id"], "source_field": r["source_field"] or "not named yet"}
             for r in rows if r["layer"] != "landing"]
    if not asked:
        return None
    sources = {s.get("id"): s for s in (sow_sources or []) if isinstance(s, dict)}
    fields = [{"source": sid, "fields": [f.get("name") for f in (sources.get(sid) or {}).get("fields") or []][:60]}
              for sid in sorted({a["source"] for a in asked}) if sid in sources]
    context = {"company": rt.company_name, "industry": rt.industry, "fields": asked, "source_fields": fields,
               "kpis": [{"code": k.get("code"), "name": k.get("name"), "formula": k.get("formula"), "unit": k.get("unit")} for k in kpis],
               "facts": []}
    register_names(plane, rt.company_name, [])
    rt = rt.routed("span", "mapping", "", plane, want_json=True)  # R1
    got: dict = {}
    for i in range(0, len(asked), BATCH):  # a few rows per call: a long answer gets cut and then does not parse
        part = {**context, "fields": asked[i:i + BATCH]}
        try:
            res = run_agent(rt.model, ToolRegistry(rt.gate), rt.company_id or plane.company_id, MODULE_ID, SPAN, SPAN_ROLE, T.as_lines(part),
                            SPAN_QUESTION, recorder=rt.recorder)
        except Exception:  # noqa: BLE001 - a model failure leaves the rule-based draft standing
            log.warning("Span's mapping draft failed")
            continue
        if res.status != "done":
            continue
        a, b = (res.text or "").find("{"), (res.text or "").rfind("}")
        try:
            piece = json.loads(res.text[a:b + 1]) if 0 <= a < b else None
        except ValueError:
            piece = None
        if isinstance(piece, dict):
            got.update(piece)
        else:
            log.warning("Span's mapping answer for rows %d to %d was not a JSON object", i + 1, i + BATCH)
    if not got:
        return None
    keys, out = {a["key"] for a in asked}, {}
    if not (keys | set(alias.values())) & set(got):
        log.warning("Span's mapping answer named none of the %d asked keys; its keys start %s", len(keys), sorted(got)[:3])
    for k, v in got.items():
        k = alias.get(k, k)  # the model answers by alias; a real key is accepted too
        if k not in alias.values():
            continue
        if isinstance(v, dict):
            t, sf, op = str(v.get("transformation") or ""), str(v.get("source_field") or ""), str(v.get("op") or "").lower()
        else:
            t, sf, op = str(v or ""), "", ""
        t = re.sub(r"k?not available yet\.(value|period)", r"the target ", t, flags=re.I)  # a target the model named by code
        t = re.sub(r"src[_-](?:[a-z]*not available yet)+[a-z]*", "the source", t, flags=re.I)  # a source id with digits
        if t.strip() and contracts.NOT_YET not in t:
            out[k] = {"transformation": " ".join(t.split())[:MAX_CELL], "source_field": " ".join(sf.split())[:MAX_CELL].split(",")[0].strip(),
                      "op": op if op in ("sum", "latest", "formula") else ""}
    return out


def draft(plane, iid: str, rt=None) -> dict:
    """Draft (or redraft) the sheet from the signed SOW. Version goes up by one on every draft. A row a person edited keeps their values
    (rule 7: a draft never overwrites a human edit)."""
    sow = _read(plane, "intents", _check(iid), "sow.json")
    if not sow:
        raise NotFound("No intent of work for this intent.")
    if sow.get("state") != "signed":
        raise Refusal("The intent of work is not signed yet, so Span cannot draft the mapping sheet.")
    scan = _read(plane, "build", "scan", f"{iid}.json")
    rows = draft_rows(plane, sow, scan)
    by_model = _span(plane, rt, rows, [k for k in sow.get("kpis") or [] if isinstance(k, dict)], sow.get("sources"))
    sources = {s.get("id") for s in sow.get("sources") or [] if isinstance(s, dict)}
    for r in rows:
        t = (by_model or {}).get(f"{r['target_table']}.{r['target_field']}")
        if t:
            r["transformation"] = t["transformation"]
            if t["source_field"] and not r["source_field"]:
                r["source_field"] = t["source_field"]
            if t["op"]:
                r["op"] = t["op"]
            if r["source_field"] and r["source_id"] in sources:
                # a formula the built-in runner cannot express stays unclear: the data engineer writes it (never a guessed figure)
                r["status"] = "unclear" if r["layer"] == "gold" and r["target_field"] == "value" and t["op"] == "formula" else "mapped"
        r.pop("_type"), r.pop("_meaning")
    p = path(plane, iid)
    with lock_for(p):
        old = _read(plane, "build", "mapping", f"{iid}.json") or {}
        edited = set((_read(plane, "build", "mapping", f"{iid}.meta.json") or {}).get("edited") or [])
        kept = {_key(r): r for r in old.get("rows") or [] if isinstance(r, dict) and _key(r) in edited}
        for r in rows:
            r.update({k: kept[_key(r)][k] for k in EDITABLE if _key(r) in kept and k in kept[_key(r)]})
        sheet = {"intent_id": iid, "version": int(old.get("version") or 0) + 1, "rows": rows}
        write_json_atomic(p, sheet)
        write_json_atomic(_meta_path(plane, iid), {"fallback": by_model is None, "at": _now(), "edited": sorted(edited & {_key(r) for r in rows})})
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    _room(plane, iid, sheet)
    return read(plane, iid)


def _key(r: dict) -> str:
    return f"{r.get('target_table')}.{r.get('target_field')}"


def _room(plane, iid: str, sheet: dict) -> None:
    unclear = sum(r["status"] == "unclear" for r in sheet["rows"])
    try:
        from sh_platform.v1 import room
        room.post(plane, iid, "span", "handover", f"The mapping sheet is drafted: {len(sheet['rows'])} rows, {unclear} unclear. "
                  "Flow can load the mapped rows once the architect has checked them.", to=["flow", "people"],
                  refs=[{"kind": "mapping", "id": iid}])
    except Exception:  # a missing or broken room never breaks the sheet
        log.warning("the room post for the mapping sheet failed")


def edit_row(plane, iid: str, n: int, body: dict) -> dict:
    p = path(plane, iid)
    with lock_for(p):
        sheet = _read(plane, "build", "mapping", f"{iid}.json")
        if not sheet:
            raise NotFound("There is no mapping sheet for this intent yet.")
        row = next((r for r in sheet.get("rows") or [] if r.get("n") == n), None)
        if row is None:
            raise NotFound("No such row.")
        change = {k: body[k] for k in EDITABLE if k in body}
        if not change:
            raise Refusal("Nothing to change.")
        for k, v in change.items():
            if not isinstance(v, str) or len(v) > MAX_CELL:
                raise Refusal(f"{k.replace('_', ' ').capitalize()} must be text of at most {MAX_CELL} characters.")
        if "status" in change and change["status"] not in STATUSES:
            raise Refusal("Status is mapped or unclear.")
        row.update({k: v.strip() for k, v in change.items()})
        write_json_atomic(p, sheet)
        meta = _read(plane, "build", "mapping", f"{iid}.meta.json") or {}
        meta["edited"] = sorted(set(meta.get("edited") or []) | {_key(row)})
        write_json_atomic(_meta_path(plane, iid), meta)
        try:  # the company map follows every write that changes what it shows
            from sh_platform.v1.m1_map import touch; touch(plane)
        except ImportError:
            pass
    return row


# ---- the workbook -----------------------------------------------------------------------------------------------------------------------

def xlsx(sheet: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Mapping"
    ws.append([h for _, h, _ in COLUMNS])
    for i, (_, _, w) in enumerate(COLUMNS, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
        c = ws.cell(1, i)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="052A52")
    for r in sheet.get("rows") or []:
        ws.append([r.get(k, "") for k, _, _ in COLUMNS])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(c.value, str) and c.value[:1] in ("=", "+", "-", "@"):
                c.quotePrefix = True  # text that starts like a formula stays text (2.0 BODY_TEXT)
                c.data_type = "s"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
