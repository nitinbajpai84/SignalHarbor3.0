"""SF09: Span drafts the silver model and the gold contract, the sandbox builds it, Span repairs it, and a person files it.

  start(plane, rt, by, changes="")  claims build/span/model_draft.json (state drafting) and runs the draft in a background thread
  latest(plane)                     the newest draft; a claim older than STALE_AFTER reads as failed (Lens STALE_AFTER, is_stale)
  file(plane, draft_id, by)         merges a ready draft into build/blueprint.json paths model.* and lineage.* as guessed by Span

The loop shape is copied from the earlier product's emitters/model_drafting.py run_draft (rounds, parse, normalise, check, sandbox, repair).
Reshaped: each round is one run_agent call through the egress gateway, with Span's read tools and nothing else; no room posts, no target
confirmation. The JSON reply and the retry with the reason follow module 3's compile.py `_parse` and `ask`. What reaches the model is
field names, the company's own measure definitions and whole-table counts over groups of five or more (SF01 read tools); sandbox errors
are scrubbed of values by model_build.scrub. When the model cannot be reached the rule-based blueprint stands and the draft says so (R14).
"""
import json
import logging
import re
import secrets
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sh_platform.agents.loop import run_agent
from sh_platform.build import blueprint as B
from sh_platform.build import blueprint_draft as D
from sh_platform.build import contracts, model_build
from sh_platform.build.agents import modelling
from sh_platform.build.agents import read_tools as T
from sh_platform.build.agents.runtime import MODULE_ID, SPAN, Runtime
from sh_platform.build.proposals import figures_trace
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view

log = logging.getLogger(__name__)
MAX_ROUNDS = 3  # ponytail: a fixed repair cap (plan Q6); make it a company setting if three rounds prove too few
MAX_SECONDS = 120  # wall time for the whole draft; a round is not started after this
STALE_AFTER = 300  # seconds: a drafting claim older than this was never finished (as Lens)
MAX_CHANGES = 2000
RULES = yaml.safe_load((Path(__file__).with_name("span_rules.yaml")).read_text(encoding="utf-8"))
SYSTEM = "\n".join([RULES["role"], *("- " + r for r in RULES["rules"]), "", RULES["model_format"]])
FROM = "Span's model draft"
MSG_FALLBACK = "Span could not reach the model. This is the rule-based draft."
MSG_FAILED = "Span could not make this build."
MSG_STALE = "Span did not finish this draft. Ask again."
MSG_READY = "Span's suggestion: the model builds in the sandbox. File it for signature to use it."
MSG_NO_DATA = "No model draft yet. Ask Span to draft the model."
MSG_NOTHING = "Span needs a signed blueprint and at least one landed source first."


class DraftRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(plane) -> Path:
    return plane.path("build", "span", "model_draft.json")


def _read(plane) -> dict | None:
    try:
        return read_json_strict(_path(plane), dict)
    except (OSError, ValueError):
        log.warning("Span's model draft could not be read")
        return None


def _save(plane, rec: dict) -> None:
    with lock_for(_path(plane)):
        write_json_atomic(_path(plane), rec)


def _stale(rec: dict) -> bool:
    return rec.get("state") == "drafting" and time.time() - float(rec.get("claimed_at") or 0) > STALE_AFTER


def latest(plane) -> dict:
    rec = _read(plane)
    if rec is None:
        nobody = Runtime(None, viewer=view.Viewer("", frozenset()))  # the same check start() makes: the real reason there is no draft
        ready = bool(_measures(plane, nobody) and _sources(plane, nobody))
        return {"state": "none", "message": MSG_NO_DATA if ready else MSG_NOTHING}
    if _stale(rec):
        return {**rec, "state": "failed", "message": MSG_STALE}
    return rec


# ---- gather: the measures, the sources' fields and whole-table counts (never a row or a sample value) --------------------------------

def _measures(plane, rt: Runtime) -> list[dict]:
    found, bp = B._baseline(plane), T._blueprint(plane)
    if found is None or bp is None:
        return []
    kpis = B._read(plane.path("intents", "m2_baseline", found[0], "kpis.json"))
    hidden = B._hidden(bp, rt.viewer)
    out = []
    for k in kpis if isinstance(kpis, list) else []:
        if isinstance(k, dict) and "id" in k and str(k["id"]).lower() not in hidden:
            t = k.get("technical") if isinstance(k.get("technical"), dict) else {}
            out.append({"code": str(k["id"]), "name": D.text(k.get("name")) or str(k.get("name") or k["id"]),
                        "grain_text": D.text(t.get("grain")) or contracts.NOT_YET,
                        "technical_definition": D.text(t.get("calculation")) or contracts.NOT_YET})
    return out


def _sources(plane, rt: Runtime) -> dict[str, list[tuple[str, str]]]:
    """{bronze table: [(column, type)]} for each contract source this viewer may see that has landed."""
    allowed = {c["source"] for c in T.read_contracts(plane, rt)["items"]}
    con = T._readonly(plane)
    if con is None:
        return {}
    try:
        return {s: [(c, t.lower()) for c, t in T._columns(con, "bronze", s) if c not in T._META] for s in sorted(allowed)
                if T._columns(con, "bronze", s)}
    finally:
        con.close()


def _facts(plane, rt: Runtime, sources: dict) -> list[dict]:
    facts = []
    for s in sources:
        p = T.read_profile(plane, rt, s)
        if p.get("available") is False:
            continue  # fewer than five rows: nothing about it is a fact
        n = p["group_size"]
        facts.append({"label": f"{s} rows", "value": p["row_count"], "group_size": n})
        for f in p["fields"]:
            facts += [{"label": f"{s}.{f['name']} distinct", "value": f["distinct"], "group_size": n},
                      {"label": f"{s}.{f['name']} empty", "value": f["nulls"], "group_size": n}]
    return facts


def _gather(plane, rt: Runtime) -> dict:
    sources = _sources(plane, rt)
    measures = _measures(plane, rt)
    facts = _facts(plane, rt, sources)
    question = "model " + " ".join(m["grain_text"] for m in measures)
    return {"industry": rt.industry, "measures": measures,
            "sources": [{"name": s, "fields": [{"name": c, "type": t} for c, t in cols]} for s, cols in sources.items()],
            "facts": facts, "pack": modelling.pick(question, facts),
            "decisions": [d["text"] for d in modelling.decisions(plane, "model")][:10],
            "current": T.read_model(plane, rt).get("model")}


# ---- one round ---------------------------------------------------------------------------------------------------------------------

def _parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group()) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _ask(plane, rt: Runtime, context: dict, question: str, names=()) -> tuple[dict | None, str | None, bool]:
    """(plan, why not, model reached). SF14: the names listed in the question exempt their digits from the guard anywhere in the reply, so
    the reply is checked again with those names cut out (proposals.figures_trace): a bare figure must trace to a fact."""
    res = run_agent(rt.model, T.span_registry(plane, rt), rt.company_id, MODULE_ID, SPAN, SYSTEM, T.as_lines(context), question,
                    recorder=rt.recorder)
    if res.status in ("refused", "error"):
        return None, None, False
    if res.status != "done":
        return None, "your reply did not finish; write the whole plan as one JSON object", True
    if res.numbers_replaced or not figures_trace(res.text, list(context.get("facts") or []) + res.tool_facts, [*names, json.dumps(context)]):
        return None, "your reply stated a figure that is not in the facts; state no figures", True
    plan = _parse(res.text)
    if plan is None:
        return None, "your reply could not be read as the JSON object asked for", True
    return plan, None, True


def _measure_errors(gold: dict, codes: set[str]) -> list[str]:
    return [f"mart {m.get('name')}: measure {m.get('measure')!r} is not one of the measure codes given" for m in gold["marts"]
            if m.get("measure") not in codes]


def _counts(report: dict) -> list[dict]:
    return [{"label": k, "value": v, "group_size": v} if isinstance(v, int) and v >= 5 else {"label": k, "text": "fewer than five"}
            for k, v in report.get("counts", {}).items()]


def _run(plane, rt: Runtime, rec: dict, changes: str) -> dict:
    # SF14: one stored draft is read by every company admin and analyst, so it is drafted as nobody sees it (restricted measures left out)
    rt = replace(rt, viewer=view.Viewer("", frozenset()))
    t0 = time.monotonic()
    prev = _read_ready_plan(plane) if changes else None
    try:
        ctx = _gather(plane, rt)
    except Exception:  # noqa: BLE001 - a broken record is the draft's failure, never a trace on screen
        log.exception("Span's model draft could not gather its inputs")
        return {**rec, "state": "failed", "errors": ["The records Span reads could not be opened."], "message": MSG_FAILED}
    if not ctx["measures"] or not ctx["sources"]:
        return {**rec, "state": "failed", "errors": ["There are no measures or no landed sources to draft from yet."], "message": MSG_FAILED}
    if rt.model is None:
        return {**rec, "state": "fallback", "fallback": True, "message": MSG_FALLBACK}
    cols = {s["name"]: [f["name"] for f in s["fields"]] for s in ctx["sources"]}
    codes = {m["code"] for m in ctx["measures"]}
    refs = model_build.known_refs(list(cols), list(codes))
    plan, errors = prev, None
    question = RULES["revise"].replace("{changes}", changes) if changes else "Write the silver model and the gold contract as one JSON object."
    # The number guard ignores figures that appear in the question, so the names the plan may use (whose digits are not figures) go here.
    listed = sorted(codes | set(cols) | {c for v in cols.values() for c in v} | {"scd1", "scd2"})
    names = " Names you may use: " + ", ".join(listed) + "."
    for n in range(1, MAX_ROUNDS + 1):
        if time.monotonic() - t0 > MAX_SECONDS:
            errors = (errors or []) + ["Span ran out of time for this draft."]
            break
        context = {**ctx, **({"previous": plan} if plan else {}), **({"errors": errors} if errors else {})}
        got, why, reached = _ask(plane, rt, context, (RULES["repair"] if errors else question) + names, listed)
        rec["rounds"] = n
        if not reached:
            return {**rec, "state": "fallback", "fallback": True, "message": MSG_FALLBACK}
        if got is None:
            errors = [why]
            continue
        plan = got
        model, gold = model_build.normalise(plan, cols)
        errors = model_build.check(model, gold, cols, refs) + _measure_errors(gold, codes)
        if not errors:
            report = model_build.sandbox_build(plane, rec["id"], model, gold)
            errors = report["errors"]
            rec["built"], rec["counts"] = report["built"], _counts(report)
        if not errors:
            return {**rec, "state": "ready", "plan": plan, "model": model, "gold": gold, "errors": [],
                    "open_questions": [str(q)[:300] for q in plan.get("open_questions") or []][:20], "message": MSG_READY}
    return {**rec, "state": "failed", "plan": plan, "errors": list(errors or [])[:20], "message": MSG_FAILED}  # sandbox errors are scrubbed


def _read_ready_plan(plane) -> dict | None:
    rec = _read(plane)
    return rec.get("plan") if rec and isinstance(rec.get("plan"), dict) else None


def _safe_run(plane, rt: Runtime, rec: dict, changes: str) -> dict:
    try:
        out = _run(plane, rt, rec, changes)
    except Exception:  # noqa: BLE001 - the failure is the record
        log.exception("Span's model draft failed")
        out = {**rec, "state": "failed", "errors": ["Span's draft stopped unexpectedly."], "message": MSG_FAILED}
    out.pop("claimed_at", None)
    out["drafted_at"] = _now()
    _save(plane, out)
    return out


def start(plane, rt: Runtime, by: str, changes: str = "", background: bool = True) -> dict:
    """Claim and start a draft. A draft already running (and not stale) is returned as it is. `background=False` runs it here (tests)."""
    changes = " ".join(str(changes or "").split())[:MAX_CHANGES]
    nobody = replace(rt, viewer=view.Viewer("", frozenset()))
    if not _measures(plane, nobody) or not _sources(plane, nobody):  # nothing to draft from: a plain refusal, never a failed draft
        raise DraftRefused(409, "nothing_to_draft", MSG_NOTHING)
    with lock_for(_path(plane)):
        cur = _read(plane)
        if cur and cur.get("state") == "drafting" and not _stale(cur):
            return cur
        rec = {"id": "D" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(3), "state": "drafting",
               "by_agent": SPAN, "started_by": by, "changes": changes, "claimed_at": time.time(), "started_at": _now(),
               "rounds": 0, "fallback": False, "errors": []}
        _save(plane, rec)
    if not background:
        return _safe_run(plane, rt, rec, changes)
    threading.Thread(target=lambda: _safe_run(plane, rt, rec, changes), daemon=True).start()
    return rec


# ---- file: merge a ready draft into the blueprint as guessed by Span, keeping every stated path -----------------------------------

def _as_blueprint(rec: dict, names: dict[str, str]) -> tuple[dict, list[dict]]:
    """The draft in the blueprint's own shape (SHAPES 2): model {facts, dimensions}; lineage one line per mart, plus one line per mart for
    each dimension its fact joins, so every source the model reads keeps its contract. Fact keys are the grain's own columns (the natural
    key the runner's uniqueness check reads), never a surrogate key, which is no column in the source."""
    model, gold = rec["model"], rec["gold"]
    dim_of = {d["name"]: d for d in model["dimensions"]}
    facts = [{"name": f["name"], "grain": "one row per " + " per ".join(f["grain"]), "keys": list(f["grain"]),
              "measures": [m["measure"] for m in gold["marts"] if m.get("source_fact") == f["name"] and m.get("measure")]}
             for f in model["facts"]]
    dims = [{"name": d["name"], "keys": list(d["business_key"]), "attributes": list(d.get("tracked_attributes") or []),
             "scd": 2 if d["type"] == "scd2" else 1} for d in model["dimensions"]]
    src = {e["name"]: e["source"][0] for e in model["dimensions"] + model["facts"]}
    lineage = []
    for m in gold["marts"]:
        if not m.get("measure"):
            continue
        how = f"sum of {m['field']} by month of {m['date']}" if m["op"] == "sum" else f"latest {m['field']} by {m['date']}, per month"
        table = src.get(m["source_fact"], "")
        mart = f"gold.{str(m['measure']).lower()}.{m['name']}"
        lineage.append({"measure": m["measure"], "source": names.get(table, table), "fields": [m["field"], m["date"]], "transform": how, "mart": mart})
        fact = next((f for f in model["facts"] if f["name"] == m["source_fact"]), {})
        for fk in fact.get("foreign_keys") or []:
            d = dim_of.get(fk.get("dimension"))
            if d and d["source"][0] != table:
                lineage.append({"measure": m["measure"], "source": names.get(d["source"][0], d["source"][0]),
                                "fields": [*d["business_key"], *(d.get("tracked_attributes") or [])], "transform": f"looked up on {fk.get('on')}",
                                "mart": mart})
    return {"facts": facts, "dimensions": dims}, lineage


def _owns(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + ".")


def _merge(doc: dict, model: dict, lineage: list[dict], mark: dict) -> tuple[dict, list[str]]:
    """The blueprint with Span's model and lineage, and the stated items kept. An item (a fact, a dimension, a lineage line) that holds
    any stated path stays exactly as it is and Span's item of the same name (or measure) is skipped. Old lineage for a measure Span did
    not draft stays too, so no measure loses its pipeline. Provenance moves with each kept item."""
    prov = doc.get("provenance") or {}
    stated = {p for p, m in prov.items() if (m or {}).get("mark") == "stated"}
    covered = {ln["measure"] for ln in lineage}
    moved: dict[str, dict] = {}
    skipped: list[str] = []
    new: dict[str, list] = {}
    for prefix, old, drafted, key in (("model.facts", doc["model"].get("facts") or [], model["facts"], "name"),
                                      ("model.dimensions", doc["model"].get("dimensions") or [], model["dimensions"], "name"),
                                      ("lineage", doc.get("lineage") or [], lineage, "measure")):
        keep = [(i, it) for i, it in enumerate(old) if any(_owns(p, f"{prefix}.{i}") for p in stated)
                or (prefix == "lineage" and it.get("measure") not in covered)]
        pinned = {it.get(key) for i, it in keep if any(_owns(p, f"{prefix}.{i}") for p in stated)}
        out = []
        for i, it in keep:
            j = len(out)
            out.append(it)
            for p, m in prov.items():
                if _owns(p, f"{prefix}.{i}"):
                    moved[f"{prefix}.{j}" + p[len(f"{prefix}.{i}"):]] = m
        for it in drafted:
            if it.get(key) in pinned:
                skipped.append(f"{prefix}: {it.get(key)}")
            else:
                out.append(it)
        new[prefix] = out
    doc = {**doc, "model": {**doc["model"], "facts": new["model.facts"], "dimensions": new["model.dimensions"]}, "lineage": new["lineage"]}
    prov = {p: m for p, m in prov.items() if not (_owns(p, "model") or _owns(p, "lineage"))}
    for p in D._leaves(doc["model"], "model") + D._leaves(doc["lineage"], "lineage"):
        prov[p] = moved.get(p) or dict(mark)
    return {**doc, "provenance": prov}, skipped


def file(plane, draft_id: str, by: str) -> dict:
    """Merge the ready draft into the blueprint. A signed blueprint is kept as blueprint.v<n>.json and the next version opens (as the
    blueprint PUT does). Returns the draft record with `filed`. Raises DraftRefused with a status, a code and one plain sentence."""
    with lock_for(_path(plane)):
        rec = _read(plane)
        if not rec or rec.get("id") != draft_id:
            raise DraftRefused(404, "no_draft", "There is no such draft of Span's.")
        if rec.get("state") == "filed":
            raise DraftRefused(409, "already_filed", "This draft is already filed for signature.")
        if rec.get("state") != "ready":
            raise DraftRefused(409, "not_ready", "Only a draft that builds in the sandbox can be filed.")
        with lock_for(B._file(plane)):
            doc = B._current(plane)
            if doc is None:
                raise DraftRefused(404, "no_blueprint", "There is no blueprint yet: the baseline is not signed.")
            names = {contracts.slug(ln.get("source")): ln.get("source") for ln in doc.get("lineage") or [] if ln.get("source")}
            model, lineage = _as_blueprint(rec, names)
            now = _now()
            if doc["state"] == "signed":  # the signed one stays beside the new version
                write_json_atomic(plane.path("build", f"blueprint.v{doc['version']}.json"), doc)
                doc = {**doc, "version": doc["version"] + 1, "state": "draft", "signed_by": []}
            doc, skipped = _merge(doc, model, lineage, {"mark": "guessed", "from": f"{FROM} {draft_id}", "by": SPAN, "at": now})
            write_json_atomic(B._file(plane), doc)
        rec = {**rec, "state": "filed", "filed": {"by": by, "at": now, "version": doc["version"], "skipped": skipped}}
        _save(plane, rec)
    return rec
