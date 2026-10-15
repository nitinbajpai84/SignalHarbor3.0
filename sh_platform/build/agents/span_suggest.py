"""Span's suggestions to the data team (plan BUILD-AGENTS-SPAN-FLOW 3.5, requirement A). Span suggests; a named person decides.

`review(plane, rt)`: gather facts through Span's read tools, find the deterministic findings first (they are also the fallback when the
model cannot be reached), then one `run_agent` call with the `propose` sink, then `proposals.file`. Nothing is ever applied here.
A model suggestion is kept only when it names the technique, the evidence, the impact, the alternatives and the effort; a suggestion
against an earlier company decision is kept only when its "why" names the fact that changed. `proposals.file` then re-checks every
number against this run's facts, drops duplicates of open suggestions and caps the run at three. Deciding a suggestion writes the
company decision to Span's memory (proposals._remember calls modelling.remember_decision), so there is no hook here.

Rules and prompts: span_suggest_rules.yaml. Reuse: the read tools (SF01), the pack and decision memory (SF03), the proposal store (SF02),
the loop's own fact extraction (`loop._figures`), and blueprint_draft's catalogue cell readers.
"""
import logging
from collections import defaultdict
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import yaml

from sh_platform.agents.loop import _figures, run_agent
from sh_platform.build import blueprint as B
from sh_platform.build import blueprint_draft as D
from sh_platform.build import proposals
from sh_platform.build.agents import modelling
from sh_platform.build.agents import read_tools as T
from sh_platform.build.agents.runtime import MODULE_ID, SPAN, Runtime, register_names
from sh_platform.build.contracts import slug
from sh_platform.profile import view

log = logging.getLogger(__name__)
RULES_FILE = Path(__file__).with_name("span_suggest_rules.yaml")
KEY_ENDINGS = ("", "_id", "_code", "_key")  # ponytail: the dimension's key in bronze is found by name; a catalogue key column when one is recorded


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def _items(out: dict) -> list:
    """The listed items of a read tool's capped list, minus the lines a restricted measure hides."""
    items = out.get("items") or [] if isinstance(out, dict) and out.get("available") is not False else []
    return [x for x in items if not (isinstance(x, dict) and x.get("hidden"))]


def _say(name: str, words: str) -> str:
    """A name in the words of a suggestion, or plain words when the name holds a digit: the number guard reads K12 or org_03 as figures
    (it is strict on purpose), and proposals.file checks title, what and why with it. The name itself stays in subject, evidence and impact."""
    return words if any(ch.isdigit() for ch in str(name)) else str(name)


def _technique(pid: str) -> str:
    return next(e["name"] for e in modelling.load_pack() if e["id"] == pid)


def _catalogue_says_changes(plane, entity: str) -> bool:
    """A catalogue field of this entity has a valid-from or valid-to date: the value changes over time (as blueprint_draft._model reads it)."""
    found = B._baseline(plane)
    cat = B._read(plane.path("intents", "m2_baseline", found[0], "catalogue.json")) if found else None
    fields = cat.get("fields") if isinstance(cat, dict) else None
    return any(entity in D.snake(D.text(f.get(D.HEADS["field_name"]))) and (D.text(f.get(D.HEADS["valid_from"])) or D.text(f.get(D.HEADS["valid_to"])))
               for f in fields or [] if isinstance(f, dict))


# ---- gathering --------------------------------------------------------------------------------------------------------------------

def gather(plane, rt: Runtime) -> dict:
    """Everything the review reads, through the read tools (so masking and group sizes are the tools' own), plus the facts in it."""
    g = {"model": T.read_model(plane, rt), "contracts": T.read_contracts(plane, rt), "queries": T.read_queries(plane, rt),
         "profiles": {}, "change_rates": {}, "facts": []}
    for c in _items(g["contracts"]):
        g["profiles"][c["source"]] = T.read_profile(plane, rt, c["source"])
    for d in _items((g["model"].get("model") or {}).get("dimensions") or {}):
        e = str(d.get("name", "")).removeprefix("dim_")
        for c in _items(g["contracts"]):
            r = next((r | {"source": c["source"], "key": e + end} for end in KEY_ENDINGS
                      if (r := T.read_change_rate(plane, rt, c["source"], e + end)).get("available") is not False), None)
            if r:
                g["change_rates"][d["name"]] = r
                break
    for name in ("model", "contracts", "queries"):
        _figures(f"read_{name}", g[name], g["facts"])
    for src, p in g["profiles"].items():
        _figures("read_profile", p, g["facts"])
    for dim, r in g["change_rates"].items():
        _figures("read_change_rate", r, g["facts"])
    return g


def _marts_of(g: dict, source: str) -> list[str]:
    return sorted({m for c in _items(g["contracts"]) if c["source"] == source for m in c.get("marts") or []})


# ---- deterministic findings (also the fallback) -----------------------------------------------------------------------------------

def _history(plane, g: dict) -> list[dict]:
    """A dimension typed 1 whose keys changed in the newest loads, while the catalogue says the value changes: suggest type 2."""
    out = []
    for d in _items((g["model"].get("model") or {}).get("dimensions") or {}):
        r, e = g["change_rates"].get(d.get("name")), str(d.get("name", "")).removeprefix("dim_")
        if d.get("scd") != "type 1" or not r or not r.get("keys_changed_last_n_loads") or not _catalogue_says_changes(plane, e):
            continue
        changed, keys, loads = r["keys_changed_last_n_loads"], r["keys"], r["loads"]
        out.append({"kind": "model_change", "args": {
            "subject": d["name"], "technique": _technique("scd2"), "title": f"Keep the history of {_say(e, 'these')} changes",
            "what": f"Keep the history when {_say(d['name'], 'this list')} details change, so each change keeps its own row with the dates it held.",
            "why": f"{changed} of {keys} {_say(e, 'dimension')} keys changed another field over the last {loads} loads, and the catalogue says the value "
                   f"changes. Today the current setup overwrites the earlier value, so past periods read today's value.",
            "evidence": {"counts": [{"label": "keys changed in the newest loads", "value": changed, "group_size": keys},
                                    {"label": "keys", "value": keys, "group_size": keys}], "fields": [r["key"]]},
            "impact": {"contracts": [r["source"]], "marts": _marts_of(g, r["source"])},
            "alternatives": [{"option": "Keep the current setup", "why_not": "it overwrites the earlier value, so past periods change"},
                             {"option": "Keep only the previous value", "why_not": "it keeps only the last change"}],
            "effort": "small"}})
    return out


def _empties(g: dict) -> list[dict]:
    """A field a measure reads that is empty in more than the share in the rules (Q8)."""
    out, share = [], float(rules()["empty_share"])
    for ln in _items(g["model"].get("lineage") or {}):
        src = slug(ln.get("source"))
        prof = {f["name"]: f for f in (g["profiles"].get(src) or {}).get("fields") or []}
        for fld in ln.get("fields") or []:
            p = prof.get(fld)
            if not p or not p.get("group_size") or p["nulls"] / p["group_size"] <= share:
                continue
            code, mart = str(ln.get("measure") or ""), ".".join(str(ln.get("mart", "")).split(".")[:2])
            f_, s_ = _say(fld, "the field"), _say(src, "its source")
            out.append({"kind": "model_change", "args": {
                "subject": f"{mart}.{fld}", "measure": code, "technique": "A quality rule with a default member",
                "title": f"Deal with the empty {f_} values before the measure reads them",
                "what": f"Add a quality rule on {f_} in {s_}, and give rows without it a default member, so the measure does not drop them silently.",
                "why": f"{f_} is empty in {p['nulls']} of {p['group_size']} rows of {s_}, and the measure reads it.",
                "evidence": {"counts": [{"label": f"{fld} empty", "value": p["nulls"], "group_size": p["group_size"]}], "fields": [fld]},
                "impact": {"contracts": [src], "marts": [mart]},
                "alternatives": [{"option": "Leave the rows out", "why_not": "the measure then undercounts without saying so"}],
                "effort": "small"}})
    return out


def _conformed(g: dict) -> list[dict]:
    """Two marts read the same source at the same grain: a candidate for one fact with conformed dimensions."""
    model = g["model"].get("model") or {}
    grain = {m: f.get("grain") for f in _items(model.get("facts") or {}) for m in f.get("measures") or []}
    by: dict[tuple, set] = defaultdict(set)
    for ln in _items(g["model"].get("lineage") or {}):
        if grain.get(ln.get("measure")) and slug(ln.get("source")):
            by[(grain[ln["measure"]], slug(ln["source"]))].add(".".join(str(ln.get("mart", "")).split(".")[:2]))
    out = []
    for (gr, src), marts in sorted(by.items()):
        if len(marts) < 2:
            continue
        ms = sorted(marts)
        out.append({"kind": "model_change", "args": {
            "subject": f"{src} at {gr}", "technique": _technique("kimball"), "title": f"Build the report tables on {_say(src, 'one source')} from one shared table",
            "what": f"These report tables read {_say(src, 'the same source')} at the same level of detail ({_say(gr, 'one level')}). Build them from one shared "
                    f"table and shared lists of managers and funds.",
            "why": "The report tables share the level of detail and the source, so separate paths can drift apart and each fix has to be made twice.",
            "evidence": {"fields": [src], "queries": ms}, "impact": {"contracts": [src], "marts": ms},
            "alternatives": [{"option": "Keep separate paths", "why_not": "two copies of the same logic"}], "effort": "medium"}})
    return out


def findings(plane, g: dict) -> list[dict]:
    return _history(plane, g) + _empties(g) + _conformed(g)


# ---- the checks on each suggestion ------------------------------------------------------------------------------------------------

def complete(args: dict) -> bool:
    ev, im = args.get("evidence") or {}, args.get("impact") or {}
    return bool(args.get("technique") and (ev.get("counts") or ev.get("fields")) and any(im.get(k) for k in ("contracts", "marts", "dashboards"))
                and args.get("alternatives") and args.get("effort"))


def against_decision(plane, args: dict) -> bool:
    """An earlier company decision on this subject that this suggestion does not simply repeat."""
    subj, tech = str(args.get("subject") or "").lower(), str(args.get("technique") or "").lower()
    for d in modelling.decisions(plane, subj):
        t = d["text"].lower()
        if subj and subj in t and not (t.startswith("chose") and tech and tech in t):
            return True
    return False


def names_changed_fact(args: dict) -> bool:
    why, ev = str(args.get("why") or "").lower(), args.get("evidence") or {}
    cited = [str(c.get("value")) for c in ev.get("counts") or []] + [str(f).lower() for f in ev.get("fields") or []]
    return "chang" in why and any(x and x in why for x in cited)


def _from_sink(item: dict) -> dict | None:
    """The sink's model_change (keys from proposals.KINDS since SF01b), with the empty keys the tool fills in left out."""
    if not isinstance(item, dict) or item.get("kind") != "model_change":
        return None
    args = {k: v for k, v in (item.get("args") or {}).items() if v not in (None, "", [], {})}
    return ({"kind": "model_change", "args": args, **({"outside_seen": True} if item.get("outside_seen") else {})}
            if args.get("subject") else None)  # the outside flag stays on the item: proposals.file then never lets it pick the addressee


# ---- the review -------------------------------------------------------------------------------------------------------------------

def _ask(plane, rt: Runtime, g: dict, found: list[dict]):
    r = rules()
    dims = _items((g["model"].get("model") or {}).get("dimensions") or {})
    signals = {"measures": len(_items((g["model"].get("model") or {}).get("facts") or {})), "consumers": len(_items(g["queries"])),
               "many_sources": len(_items(g["contracts"])) > 1,
               "keys_changed_last_n_loads": max([x.get("keys_changed_last_n_loads") or 0 for x in g["change_rates"].values()] + [0])}
    topic = " ".join(str(d.get("name")) for d in dims)
    context = {"company": rt.company_name, "industry": rt.industry, "model": g["model"], "contracts": g["contracts"], "queries": g["queries"],
               "profiles": g["profiles"], "change_rates": g["change_rates"], "decisions": modelling.decisions(plane, topic),
               "pack": modelling.pick("slowly changing history conformed dimensions grain " + topic, signals),
               "findings": [{"subject": f["args"]["subject"], "title": f["args"]["title"]} for f in found], "facts": g["facts"]}
    register_names(plane, rt.company_name, [])
    system = r["role"] + "\n" + "\n".join(f"- {x}" for x in r["rules"])
    return run_agent(rt.model, T.span_registry(plane, rt), rt.company_id or plane.company_id, MODULE_ID, SPAN, system, T.as_lines(context), r["question"],
                     recorder=rt.recorder)


def review(plane, rt: Runtime, intent_id: str | None = None) -> dict:
    """{proposals: [filed records], fallback: bool, message: str | None}. Fallback: the model could not be reached, so only the
    deterministic findings were filed, and the screen says so in one sentence (R14)."""
    if T._blueprint(plane) is None:  # no model to review: the plain empty result, and no model call
        return {"proposals": [], "fallback": False, "message": None}
    rt = replace(rt, viewer=view.Viewer("", frozenset()))  # SF14: a filed suggestion reaches its addressee whatever they may see, so review as nobody
    g = gather(plane, rt)
    found = findings(plane, g)
    items, facts, outside, fallback, run_id = list(found), list(g["facts"]), False, True, None
    if rt.model is not None:
        res = _ask(plane, rt, g, found)
        fallback = res.status not in ("done", "could_not_finish")
        run_id = res.run_id if isinstance(res.run_id, str) else None
        facts += res.tool_facts
        for p in res.proposals:
            it = _from_sink(p)
            if it and complete(it["args"]):
                items.append(it)
                outside = outside or bool(p.get("outside_seen"))
            else:
                log.info("a suggestion was dropped: it lacks the technique, evidence, impact, alternatives or effort")
    kept = []
    for it in items:
        if against_decision(plane, it["args"]) and not names_changed_fact(it["args"]):
            log.info("a suggestion was dropped: it goes against an earlier company decision without naming the fact that changed")
            continue
        kept.append(it)
    filed = proposals.file(plane, SPAN, kept, {"run_id": run_id, "facts": facts, "outside_seen": outside, "intent_id": intent_id})
    return {"proposals": filed, "fallback": fallback, "message": rules()["fallback"] if fallback else None}
