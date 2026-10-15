"""B1: Span drafts the three layers from the signed intent of work, into 2.0's blueprint and architecture record.

`design(plane, rt, iid, by)` reads intents/<iid>/sow.json (must be signed) and
  1. drafts build/blueprint.json with 2.0's rule-based `blueprint_draft.draft`, its baseline inputs replaced by the SOW's kpis and catalogue
     (a signed blueprint is kept beside as blueprint.v<n>.json and the draft becomes version n+1, as blueprint.py's PUT does);
  2. regenerates build/architecture/record.json from 2.0's `architecture.project` plus the SOW's sources, landing and cleaned tables
     (components `proposed`, made by Span: a person still signs the blueprint), copying `architecture.regenerate`'s write;
  3. asks Span for the design lines through `span_design._ask` (runtime and egress gateway); with no model the rule-based lines stand, labelled;
  4. saves build/design/<iid>.json and posts a room hand-over (guarded import).

Reuse: blueprint_draft.draft (whole), blueprint.py `_drafted` env read and PUT versioning (L44-L63, L175-L178), architecture.regenerate
(L216-L247, write part), span_design._ask and rules()["fallback"]."""
import logging
import re
from datetime import datetime, timezone

from sh_platform import build_env
from sh_platform.build import architecture as A
from sh_platform.build import blueprint_draft as D
from sh_platform.build.agents import span_design
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store

log = logging.getLogger(__name__)
IID = re.compile(r"[A-Za-z0-9_-]{1,80}")
MOMENT = "sow_signed"
FROM = "Signed intent of work"
QUESTION = ('Describe the three layers drafted from this signed intent of work (landing as it arrives, the cleaned layer, report '
            'tables per measure) as one JSON object: {"lines": ["three to five sentences for the architect, naming which measures each '
            'layer serves and what is missing"]}.')


class Refused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cell(v) -> dict:
    return {"value": v, "mark": "stated"}


def _design_file(plane, iid: str):
    return plane.path("build", "design", f"{iid}.json")


def read_sow(plane, iid: str) -> dict:
    if not IID.fullmatch(iid or ""):
        raise Refused(404, "not_found", "There is no such intent.")
    try:
        sow = read_json_strict(plane.path("intents", iid, "sow.json"), dict)
    except (OSError, ValueError):
        raise Refused(409, "unreadable", "The intent of work cannot be read.") from None
    if sow is None:
        raise Refused(404, "no_sow", "This intent has no intent of work yet.")
    return sow


def read_design(plane, iid: str) -> dict | None:
    try:
        return read_json_strict(_design_file(plane, iid), dict)
    except (OSError, ValueError):
        return None


# ---- the SOW in blueprint_draft's baseline shape --------------------------------------------------------------------------------------

def baseline_inputs(sow: dict) -> tuple[list[dict], dict]:
    """(kpis, catalogue) as blueprint_draft.draft reads them: kpis with `technical` cells, the catalogue's sources, tables and fields tabs."""
    H = D.HEADS
    kpis = [{"id": k["code"], "name": k.get("name") or k["code"],
             "technical": {"grain": _cell(f"one row per {k['period']}" if k.get("period") else None),
                           "calculation": _cell(k.get("formula") or k.get("definition")), "sources": _cell(list(k.get("source_ids") or []))},
             "governance": {"personal": "no"}}
            for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")]
    cat = {"sources": [{H["src_id"]: _cell(s.get("id")), H["src_name"]: _cell(s.get("name"))} for s in sow.get("sources") or [] if isinstance(s, dict)],
           "tables": [], "fields": []}
    for t in sow.get("catalogue") or []:
        if not isinstance(t, dict) or not t.get("table"):
            continue
        cat["tables"].append({H["item_id"]: _cell(t["table"]), H["src_id"]: _cell(t.get("source_id"))})
        cat["fields"] += [{"Field ID": _cell(f"{t['table']}.{f.get('name')}"), H["field_name"]: _cell(f.get("source_field") or f.get("name")),
                           H["item_id"]: _cell(t["table"]), H["feeds"]: _cell(list(t.get("feeds_kpis") or []))}
                          for f in t.get("fields") or [] if isinstance(f, dict) and f.get("name")]
    return kpis, cat


def _blueprint(plane, sow: dict, iid: str) -> dict:
    kpis, cat = baseline_inputs(sow)
    try:
        answers = {q["key"]: q["answer"] for q in build_env.read(plane, store.raw(plane))["questions"]}
    except (OSError, ValueError, KeyError, TypeError):
        answers = {}
    doc = D.draft(kpis, cat, {}, {}, answers, [])
    src = f"{FROM} {sow.get('title') or iid}, version {sow.get('version') or 1}"
    for p in doc["provenance"].values():
        if p["mark"] == "guessed":
            p["from"] = src
    path = plane.path("build", "blueprint.json")
    with lock_for(path):
        try:
            old = read_json_strict(path, dict)
        except (OSError, ValueError):
            raise Refused(409, "unreadable", "The current blueprint cannot be read, so it was not replaced.") from None
        if old:
            if old.get("state") == "signed":  # the signed one stays beside the new version
                write_json_atomic(plane.path("build", f"blueprint.v{old['version']}.json"), old)
                doc["version"] = int(old["version"]) + 1
            else:
                doc["version"] = int(old.get("version") or 1)
        write_json_atomic(path, doc)
    return doc


# ---- the SOW's sources and tables as record components --------------------------------------------------------------------------------

def components(sow: dict, iid: str) -> dict[str, dict]:
    """{id: component} for the sources, landing and cleaned tables, in architecture.project's shape. Gold comes from the blueprint."""
    out, frm = {}, f"intents/{iid}/sow.json"
    slug = lambda t: A._slug(t).replace("-", "_")  # noqa: E731

    def add(cid, kind, label, about, sid=None):
        out[cid] = {"id": cid, "view": "data", "kind": kind, "label": label, "interfaces": [], "from": frm, "restricted": False, "may_see": None,
                    "owner_hint": None, "about": about, "refs": {"blueprint_version": None, "pipeline": None, "mart": None, "graph_node": None}}
        out[cid]["_sid"] = sid
        return out[cid]

    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")]
    for s in sow.get("sources") or []:
        if isinstance(s, dict) and s.get("id"):
            c = add(f"source:{slug(s['id'])}", "source", s.get("name") or s["id"], s.get("holds"), s["id"])
            c["owner_hint"] = s.get("owner")
    rows = [t for t in sow.get("catalogue") or [] if isinstance(t, dict) and t.get("table")]
    for t in rows:
        if t.get("layer") == "landing":
            add(f"bronze:{slug(t['table'])}", "bronze", f"landing.{slug(t['table'])}", t.get("meaning"), t.get("source_id"))
        elif t.get("layer") == "silver":
            c = add(f"silver:{slug(t['table'])}", "silver", f"silver.{slug(t['table'])}", t.get("meaning"), t.get("source_id"))
            feeds = set(t.get("feeds_kpis") or []) | {k["code"] for k in kpis if t.get("source_id") in (k.get("source_ids") or [])}
            c["interfaces"] = [{"to": f"gold:{str(code).lower()}", "kind": "writes", "contract": None} for code in sorted(feeds)]
    land = [c for c in out.values() if c["kind"] == "bronze"]
    clean = [c for c in out.values() if c["kind"] == "silver"]
    for c in out.values():
        nxt = {"source": land, "bronze": clean}.get(c["kind"], [])
        mine = [x for x in nxt if x["_sid"] == c["_sid"]] or ([x for x in clean if x["_sid"] == c["_sid"]] if c["kind"] == "source" else [])
        c["interfaces"] += [{"to": x["id"], "kind": "feeds", "contract": None} for x in mine]
    for c in out.values():
        del c["_sid"]
    return out


def _record(plane, sow: dict, iid: str) -> dict:
    """architecture.regenerate's write, over project() plus the SOW's components; new ones are proposed and made by Span."""
    proj = {**A.project(plane), **components(sow, iid)}
    path = A._file(plane, "record.json")
    with lock_for(path):
        rec = A.read(plane)
        old = {c["id"]: c for c in rec["components"]}
        added, changed, comps = [], [], []
        for cid, p in proj.items():
            o = old.pop(cid, None)
            if o is None:
                comps.append(A._fresh(p, "proposed", f"sow:{iid}"))
                added.append(cid)
                continue
            if not A._same(o, p):
                changed.append(cid)
            comps.append({**o, **{k: p[k] for k in ("view", "kind", "label", "interfaces", "refs", "restricted", "may_see", "from")}})
        comps += list(old.values())
        n = int(rec.get("version") or 0) + 1
        regen = {"moment": MOMENT, "ref": iid, "by": "Span", "at": _now()}
        rec = {"version": n, "regenerated": regen, "components": comps,
               "history": [*rec.get("history", []), {"version": n, **regen, "added": added, "changed": changed, "retired": [], "changes": []}]}
        write_json_atomic(path, rec)
        write_json_atomic(A._file(plane, f"record.v{n}.json"), rec)
        for vw in A.VIEWS:
            write_json_atomic(A._file(plane, "diagrams", f"{vw}.v{n}.json"), A.spec(rec, vw, set(added) | set(changed)))
    try:
        from sh_platform.graph.hooks import mark_dirty
        mark_dirty(plane)  # the map draws the record's components
    except Exception:  # noqa: BLE001 - the map catches up on its next rebuild
        log.warning("the map was not marked for a rebuild after Span's design")
    return rec


# ---- Span's lines ---------------------------------------------------------------------------------------------------------------------

def rule_lines(sow: dict, rec: dict) -> list[str]:
    n = lambda k: sum(1 for c in rec["components"] if c.get("kind") == k and c.get("view") == "data")  # noqa: E731
    codes = [k["code"] for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("code")]
    unclear = [k["code"] for k in sow.get("kpis") or [] if isinstance(k, dict) and k.get("status") == "unclear"]
    out = [f"Landing keeps {n('bronze')} tables exactly as they arrive from {n('source')} sources.",
           f"The cleaned layer has {n('silver')} tables, typed and without duplicates.",
           f"Report tables serve {len(codes)} measures: {', '.join(codes) or 'none yet'}."]
    if unclear:
        out.append(f"Still unclear in the intent of work: {', '.join(unclear)}. Their report tables wait for an answer.")
    return out


def design(plane, rt, iid: str, by: str) -> dict:
    sow = read_sow(plane, iid)
    if sow.get("state") != "signed":
        raise Refused(409, "sow_not_signed", "Sign the intent of work first. Span drafts the design from the signed version only.")
    bp = _blueprint(plane, sow, iid)
    rec = _record(plane, sow, iid)
    context = {"company": rt.company_name, "industry": rt.industry, "goal": sow.get("goal"),
               "measures": [{k: m.get(k) for k in ("code", "name", "definition", "unit", "period", "source_ids", "status")} for m in sow.get("kpis") or []],
               "sources": [{k: s.get(k) for k in ("id", "name", "kind", "holds")} for s in sow.get("sources") or []],
               "tables": [{k: t.get(k) for k in ("table", "layer", "meaning", "source_id", "feeds_kpis")} for t in sow.get("catalogue") or []],
               "facts": []}
    ids = {str(m.get("code")) for m in sow.get("kpis") or [] if m.get("code")} | {str(s.get("id")) for s in sow.get("sources") or [] if s.get("id")}
    d, _ = span_design._ask(plane, rt, context, QUESTION, ids)
    lines = span_design._texts(d.get("lines")) if d else []
    out = {"intent_id": iid, "sow_id": sow.get("id"), "sow_version": sow.get("version"), "by": "Span", "asked_by": by, "at": _now(),
           "lines": lines or rule_lines(sow, rec), "fallback": not lines, "message": None if lines else span_design.rules()["fallback"],
           "blueprint_version": bp["version"], "record_version": rec["version"],
           "counts": {k: sum(1 for c in rec["components"] if c.get("kind") == k and c.get("view") == "data") for k in ("source", "bronze", "silver", "gold")}}
    with lock_for(_design_file(plane, iid)):
        write_json_atomic(_design_file(plane, iid), out)
    try:
        from sh_platform.v1.room import post
        post(plane, iid, "span", "handover", f"I drafted the three layers from the signed intent of work: {out['counts']['gold']} report tables. "
             "Please review the design, then scan the sources.", to=["people"], refs=[{"kind": "sow", "id": sow.get("id") or iid}])
    except Exception:  # noqa: BLE001 - a missing room never breaks the design
        log.info("no room post for Span's design")
    return out
