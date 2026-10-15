"""Flow, the data engineer (plan 1, rooms 2 and 3; card SF12): the run in plain words, notes on data alerts, the warehouse SQL differences,
and a model_change proposal when a run failure points at the model.

Every model call is `run_agent` through the egress gateway with counts, field names, check names and error kinds only. Rows, sample values,
file names and the quarantine table never leave: Flow reads quarantine counts, never its contents. A count under five is written "fewer
than five" and is never a fact. When the model is missing or its words fail the number guard, the deterministic lines stand (R14) and the
note says so in one sentence. Flow never runs a pipeline, applies a proposal or closes an alert.

The chain order of the deterministic lines is copied from the earlier agents/skills/engineer.md "How to work" 1-2: contract, file, bronze
rows, fields, checks, gold; name the first missing link and give every set-aside count with its check and field.
"""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sh_platform.agents.groups import group_ok
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.build import alerts, contracts, proposals, runner, schedule, transforms
from sh_platform.build.agents import read_tools
from sh_platform.build.agents.runtime import FLOW, MODULE_ID, Runtime
from sh_platform.jsonfile import read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
RULES = yaml.safe_load(Path(__file__).with_name("flow_rules.yaml").read_text(encoding="utf-8"))
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}")  # run ids become file names: letters, digits, _ and - only (seeded history runs read hist-<month>-<source>)
NO_MODEL_RUN = "Flow could not reach the model. These lines come from the run log."
NO_MODEL_INCIDENT = "Flow could not reach the model. This note comes from the run log."
NO_MODEL_DIALECT = "Flow could not reach the model. These lines come from the translation itself."
MAX_NOTE = 1200


def _system() -> str:
    return RULES["role"] + "\n" + "\n".join(f"- {r}" for r in RULES["rules"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rows(n) -> str:
    n = n or 0
    return "no rows" if n <= 0 else "fewer than five rows" if not group_ok(n) else f"{n:,} rows"


def _fact(label: str, n, total) -> list[dict]:
    """A count is a fact only when it and its group are five or more."""
    return [{"label": label, "value": n, "group_size": total}] if group_ok(n) and group_ok(total) else []


def _ask(rt: Runtime, plane, context: dict, prompt: str, registry=None, names=(), definitions: str = ""):
    """The model's words, or None (no model, an error, or a figure that does not trace). Returns (text, result). The guard reads digits in
    names (K12, org_03) as figures and ignores figures in the question, so the names the note may use are listed there (SF09's workaround).
    SF14: that also lets a bare figure equal to digits inside a name pass, so the words are checked again with the names cut out and only the
    facts (and the company's own check texts) as sources."""
    if rt.model is None:
        return None, None
    reg = registry or ToolRegistry(rt.gate)
    res = run_agent(rt.model, reg, rt.company_id or plane.company_id, MODULE_ID, FLOW, _system(), read_tools.as_lines(context), _question(prompt, names),
                    recorder=rt.recorder)
    text = " ".join((res.text or "").split())
    ok = res.status == "done" and text and not res.numbers_replaced and not text.startswith(("{", "["))         and proposals.figures_trace(text, list(context.get("facts") or []) + res.tool_facts, [*names, json.dumps(context)], definitions)
    return (text[:MAX_NOTE] if ok else None), res


def _definitions(run: dict | None) -> str:
    """The company's own check texts of a run (a range check names its bounds): figures in them may be repeated."""
    return " ".join(str(r.get("rule") or "") for r in (run or {}).get("rules") or [])


def _question(prompt: str, names) -> str:
    listed = sorted({str(n) for n in names if n})
    return RULES["prompts"][prompt] + (" Names you may use: " + "; ".join(listed) + "." if listed else "") +         " Never make up a name that contains digits."


def _masked(rid: str, hidden: set[str]) -> str:
    measure, _, text = str(rid).partition(":")
    return "a check on a restricted measure" if measure.lower() in hidden else f'the check "{text or rid}" for {measure}'


# ---- the run in plain words -----------------------------------------------------------------------------------------------------------

def _note_path(plane, run_id: str):
    return plane.path("build", "flow", "runs", f"{run_id}.json")


def read_note(plane, run_id: str) -> dict | None:
    if not RUN_ID.fullmatch(str(run_id)):
        return None
    try:
        d = read_json_strict(_note_path(plane, run_id), dict)
    except (OSError, ValueError):
        log.warning("a run note could not be read")
        return None
    return d or None


def run_lines(plane, run: dict, hidden: set[str]) -> tuple[list[str], str | None, list[dict]]:
    """(lines in chain order, the first missing link or None, facts). Built from the run record only."""
    src, n = run.get("source"), run.get("rows") or 0
    facts = _fact("rows loaded", n, n)
    failed = [r for r in run.get("rules") or [] if not r.get("passed")]
    checks = [r for r in failed if not str(r.get("rule", "")).startswith("gold.")]
    lines, link = [], None
    if src not in {c["source"] for c in contracts.derive(plane)}:
        link = "contract"
        lines.append(f"There is no contract for {src} any more, so it cannot run again until the blueprint names it.")
    elif not n and schedule.LATE_NOTE in (run.get("notes") or []):
        link = "file"
        lines.append(f"No file had landed for {src}, so nothing loaded.")
    elif not n:
        link = "bronze"
        lines.append(f"The file for {src} landed but no rows loaded.")
    else:
        lines.append(f"The cleaned layer loaded {_rows(n)} for {src}.")
    if n and run.get("schema_ok") is False:
        link = link or "fields"
        lines.append("The file is missing fields the contract expects.")
    for r in checks:
        link = link or "checks"
        lines.append(f"{_masked(r.get('rule'), hidden).capitalize()} failed on {_rows(r.get('count'))}.")
        facts += _fact(f"{r.get('rule')} failing rows", r.get("count"), n)
    for q in run.get("quarantined") or []:
        lines.append(f"{_rows(q.get('count')).capitalize()} set aside for {_masked(q.get('rule'), hidden)}, field {q.get('field')}. "
                     "They stay in the company space.")
        facts += _fact(f"{q.get('rule')} rows set aside on {q.get('field')}", q.get("count"), n)
    if n and not run.get("marts_ready"):
        link = link or "gold"
        lines.append("The report tables were not refreshed for this run.")
    elif run.get("marts_ready"):
        lines.append("The report tables were refreshed and are ready.")
    for x in run.get("not_run") or []:
        lines.append(f"{_masked(x, hidden).capitalize()} could not run: Flow cannot read that check yet.")
    lead = (f"{src} failed. The first missing link is {_LINKS[link]}." if run.get("status") == "failed" and link
            else f"{src} ran late." if run.get("status") == "late" else f"{src} ran and every check passed." if not failed else f"{src} ran.")
    return [lead] + lines, link, facts


_LINKS = {"contract": "the contract", "file": "the file", "bronze": "the rows loaded", "fields": "the fields the contract expects",
          "checks": "the checks", "gold": "the report table refresh"}


def _grain_proposals(plane, run: dict, facts: list[dict]) -> list[dict]:
    """A failed uniqueness check points at the model: one model_change for the fact's grain, addressed by proposals.file, fixed by Span."""
    bp = contracts._read(plane, "build", "blueprint.json")
    items = []
    for r in run.get("rules") or []:
        measure, _, text = str(r.get("rule", "")).partition(":")
        if r.get("passed") or transforms._kind(text.lower()) != "unique":
            continue
        fact = next((f for f in (bp.get("model") or {}).get("facts") or [] if measure in (f.get("measures") or [])), {})
        name, keys = fact.get("name") or run.get("source"), [str(k) for k in fact.get("keys") or []]
        marts = sorted({".".join(str(ln.get("mart", "")).split(".")[:2]) for ln in bp.get("lineage") or [] if ln.get("measure") == measure})
        n = r.get("count")
        args = {"subject": f"the grain of {name}", "title": f"The grain of {name} is not unique",
                "what": f"Rows of {run.get('source')} share the same {', '.join(keys) or 'key'}: {_rows(n)}. Span should redraft the grain or the keys of {name}.",
                "why": f"The blueprint says one row per {fact.get('grain') or 'record'}, but the uniqueness check failed, so a period's value can count a record twice.",
                "technique": "grain statement", "effort": "small",
                "evidence": {"counts": _fact(f"{r.get('rule')} failing rows", n, run.get("rows")), "fields": keys, "queries": []},
                "impact": {"contracts": [f"build/pipelines/{run.get('source')}.json"], "marts": marts, "dashboards": []},
                "alternatives": [{"option": "Remove the repeated rows from the source file", "why_not": "It fixes this file only; the next file can repeat keys again."}]}
        if re.fullmatch(r"[A-Za-z0-9_]{1,20}", measure):
            args["measure"] = measure
        items.append({"kind": "model_change", "args": args})
    return items


def _from_model(items: list[dict]) -> list[dict]:
    """The propose sink names the model_change target `target`; the store calls it `subject`."""
    out = []
    for it in items or []:
        args = dict(it.get("args") or {})
        if it.get("kind") == "model_change" and "target" in args:
            args["subject"] = args.pop("target")
        out.append({"kind": it.get("kind"), "args": {k: v for k, v in args.items() if v not in (None, "", [])}})
    return out


def explain_run(plane, run_id: str, rt: Runtime, *, fresh: bool = False) -> dict | None:
    """Flow's note on one run, stored at build/flow/runs/<run_id>.json; None when there is no such run or the viewer may not see its
    source. A stored note is returned as it is unless `fresh`. Called from the chain (gate 3) and from the room 2 route."""
    if not RUN_ID.fullmatch(str(run_id)):
        return None
    run = next((r for r in runner.read_runs(plane) if r.get("id") == run_id), None)
    if run is None or run.get("source") in runner._hidden_sources(plane, rt.viewer):
        return None
    if not fresh and (old := read_note(plane, run_id)):
        return old
    hidden = read_tools._hidden_codes(plane, Runtime(None))  # masked for nobody: the stored note is read by everyone who sees the run
    lines, link, facts = run_lines(plane, run, hidden)
    n = run.get("rows") or 0
    context = {"source": run.get("source"), "run": {k: run.get(k) for k in ("status", "on_time", "schema_ok")}, "facts": facts,
               "rules": [{"rule": _masked(r.get("rule"), hidden), "passed": r.get("passed"),
                          **({} if r.get("passed") or group_ok(r.get("count")) and group_ok(n) else {"count_text": _rows(r.get("count"))})}
                         for r in run.get("rules") or []],
               "set_aside": [{"rule": _masked(q.get("rule"), hidden), "field": q.get("field"),
                              **({} if group_ok(q.get("count")) and group_ok(n) else {"count_text": _rows(q.get("count"))})}
                             for q in run.get("quarantined") or []],
               "first_missing_link": _LINKS.get(link), "lines": lines}
    text, res = _ask(rt, plane, context, "run", read_tools.flow_registry(plane, rt),
                     [run.get("source"), run_id] + [r["rule"] for r in context["rules"]] + [q["field"] for q in context["set_aside"]], _definitions(run))
    items = _grain_proposals(plane, run, facts) + _from_model(res.proposals if res else [])
    filed = proposals.file(plane, FLOW, items, {"run_id": run_id, "facts": facts + (res.tool_facts if res else []), "definitions": _definitions(run),
                                                 "outside_seen": any(p.get("outside_seen") for p in (res.proposals if res else []))}) if items else []
    note = {"run_id": run_id, "source": run.get("source"), "status": run.get("status"), "by": FLOW, "at": _now(), "lines": lines,
            "first_missing_link": link, "text": text, "fallback": text is None, "sentence": None if text else NO_MODEL_RUN,
            "proposals": [p["id"] for p in filed]}
    try:
        write_json_atomic(_note_path(plane, run_id), note)
    except OSError:
        log.warning("the run note for %s could not be stored", run_id)
    return note


# ---- incident notes on data alerts ----------------------------------------------------------------------------------------------------

def _cause(plane, run: dict | None, alert: dict, hidden: set[str]) -> tuple[str, str, list[dict]]:
    src, kind = alert.get("source"), alert.get("kind")
    if kind == "missing":
        return f"No file has landed for {src} today.", f"Ask the provider of {src} for today's file again.", []
    if kind == "late":
        return f"The file for {src} arrived after its expected time.", f"Ask the provider of {src} to send the file by its agreed time.", []
    if kind == "outside_range":
        return (f"The latest value of a report table fed by {src} is outside its usual range.",
                "Check the latest period with the measure's owner before anyone uses it.", [])
    if run is None:
        return f"Today's run of {src} failed, but its record could not be read.", f"Run {src} again and check the run log.", []
    lines, link, facts = run_lines(plane, run, hidden)
    first = lines[1] if len(lines) > 1 else lines[0]
    step = {"file": f"Ask the provider of {src} for the file again.", "bronze": f"Ask the provider of {src} for a complete file.",
            "fields": f"Ask the provider of {src} for a file with every field the contract names.",
            "checks": "Look at the rows set aside, have the file corrected and run it again.",
            "gold": "Check the measure's date and value fields, then run it again."}.get(link, f"Run {src} again and check the run log.")
    return f"{_LINKS.get(link, 'the run').capitalize()} broke the chain. {first}", step, facts


def incident_note(plane, rt: Runtime, alert_id: str) -> dict | None:
    """Flow's note on one open alert, filed as an incident_note proposal to the alert's tell person (proposals.file picks the addressee).
    Returns the proposal (or the open one already filed for this alert); None when the alert is not open, its source is hidden, or
    nobody is named to tell."""
    a = next((x for x in alerts._read(plane) if x.get("id") == alert_id and x.get("state") == "open"), None)
    if a is None or a.get("source") in runner._hidden_sources(plane, rt.viewer):
        return None
    have = next((p for p in proposals.all_proposals(plane) if p.get("target") == f"alert:{alert_id}" and p.get("state") in proposals.OPEN), None)
    if have:
        return have
    run = next((r for r in reversed(runner.read_runs(plane)) if r.get("source") == a.get("source")), None)
    cause, step, facts = _cause(plane, run, a, read_tools._hidden_codes(plane, Runtime(None)))
    text, res = _ask(rt, plane, {"alert": {"kind": a.get("kind"), "source": a.get("source"), "since": a.get("opened")},
                                 "facts": facts, "cause": cause, "next_step": step}, "incident", names=
                     [a.get("source"), alert_id], definitions=_definitions(run))
    item = {"kind": "incident_note", "args": {"title": f"Flow's note on the {a.get('source')} alert", "what": text or cause, "why": cause,
                                              "alert_id": alert_id, "next_step": step}}
    filed = proposals.file(plane, FLOW, [item], {"run_id": (run or {}).get("id"), "facts": facts + (res.tool_facts if res else []),
                                                  "definitions": _definitions(run), "alert_id": alert_id})
    if not filed:
        return None
    return {**filed[0], "fallback": text is None, "sentence": None if text else NO_MODEL_INCIDENT}


# ---- warehouse SQL differences --------------------------------------------------------------------------------------------------------

def explain_dialect(plane, rt: Runtime) -> dict:
    """What differs when the runner's SQL is written for the stated warehouse. Function and type names only; no SQL text leaves."""
    d = read_tools.read_dialect(plane, rt)
    changed = sorted({c for s in d["statements"] for c in s["changed_constructs"]})
    if d["state"] not in ("ready", "failed"):
        return {"state": d["state"], "dialect": d.get("dialect"), "lines": [d["message"]], "text": None, "fallback": False, "sentence": None}
    lines = [d["message"]]
    lines += ([f"These functions and types are written differently there: {', '.join(changed)}.", "Everything else reads the same."]
              if changed else ["Every statement reads the same there."])
    text, _ = _ask(rt, plane, {"dialect": d.get("dialect"), "changed": changed}, "dialect", names=[d.get("dialect"), *changed]) \
        if changed else (None, None)
    return {"state": d["state"], "dialect": d.get("dialect"), "lines": lines, "changed": changed, "text": text,
            "fallback": bool(changed) and text is None, "sentence": NO_MODEL_DIALECT if changed and text is None else None}
