"""The tools Span and Flow may call (plan 3.2), and the propose sink (3.3). Reshaped from the earlier product's per-agent tool lists
(emitters/agent_brain.py AGENT_ONLY_TOOLS and the tool list per slug): one explicit list per agent, agent-scoped names, no policy table.

Every read tool returns a summary that passes the registry's `_summary_only`: a figure sits in a dict with its own `group_size` of five or
more, lists stay at MAX_LIST items, and no key is named rows or records. Restricted measures and sources are masked for `rt.viewer` with
the same rules the screens use. Nothing here writes. `search_reference` is listed only when the company's internet switch for Build
is on, and the loop marks what it returns as outside material.
"""
import logging
import re
from collections import Counter

from sh_platform.agents.groups import group_ok, is_figure
from sh_platform.agents.registry import MAX_LIST, ToolRefused, ToolRegistry, _summary_only
from sh_platform.build import alerts, architecture, contracts
from sh_platform.build import blueprint as B
from sh_platform.build import runner
from sh_platform.build.agents.runtime import MODULE_ID, Runtime
from sh_platform.build.proposals import KINDS
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.warehouse import LOAD_ID, LOADED_AT, _q

log = logging.getLogger(__name__)
UNAVAILABLE = {"available": False}
LOADS = 12  # change rate looks at the newest twelve loads (the plan's example "last 12 loads")
MAX_TEXT, MAX_TITLE = 2000, 200
_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_META = (LOAD_ID, LOADED_AT)


def _no(reason: str) -> dict:
    return {**UNAVAILABLE, "reason": reason}


def _cap(items: list) -> dict:
    return {"items": items[:MAX_LIST], "truncated": len(items) > MAX_LIST}


def _blueprint(plane) -> dict | None:
    doc = contracts._read(plane, "build", "blueprint.json")
    return doc if all(k in doc for k in ("model", "lineage", "rules", "access")) else None


def _hidden_codes(plane, rt: Runtime) -> set[str]:
    bp = _blueprint(plane)
    return B._hidden(bp, rt.viewer) if bp else set()


def _source_ok(plane, rt: Runtime, source: str) -> bool:
    return bool(_SAFE.match(str(source))) and source in {c["source"] for c in contracts.derive(plane)} \
        and source not in runner._hidden_sources(plane, rt.viewer)


def _readonly(plane):
    """The read-only copy of the company warehouse (the runner writes the main file), or None when nothing has landed yet."""
    import duckdb
    from sh_platform.warehouse import open_readonly
    try:
        return open_readonly(plane)
    except duckdb.Error:
        return None


def _columns(con, schema: str, table: str) -> list[tuple[str, str]]:
    return con.execute("select column_name, data_type from information_schema.columns where table_schema = ? and table_name = ? "
                       "order by ordinal_position", [schema, table]).fetchall()


# ---- Span's read tools --------------------------------------------------------------------------------------------------------------

def read_handoff(plane, rt: Runtime, intent_id: str) -> dict:
    """What the Intent Centre handed to Build (R16): charter, measures, processes, sources with quadrant and strategic flag, masked."""
    from sh_platform.intents import build_ready as BR, source_map as SM
    from sh_platform.intents.access import IntentRefused, load_intent
    if not _SAFE.match(str(intent_id)):
        return _no("No such Initiative.")
    try:
        intent = load_intent(plane, intent_id)
    except IntentRefused:
        return _no("No such Initiative.")
    hand = intent.get("build_handoff")
    if not isinstance(hand, dict):
        return _no("This Initiative has not been handed to Build yet.")
    ctx = BR.Ctx(plane, intent, rt.viewer)
    kpis = {k.get("id"): k for k in ctx.kpis or [] if isinstance(k, dict)}
    bp = _blueprint(plane) or {"model": {"facts": []}}
    grain = {m: f.get("grain") for f in bp["model"].get("facts") or [] for m in f.get("measures") or []}
    measures = [{"code": None, "name": "A restricted measure"} if ctx.sealed(kpis.get(m.get("id"), {})) else
                {"code": m.get("id"), "name": m.get("name"), "grain_text": grain.get(m.get("id")) or contracts.NOT_YET}
                for m in hand.get("catalogue") or [] if isinstance(m, dict)]
    sources = [{"name": s.get("name"), "quadrant": SM.ZONES.get(s.get("zone")) or "Not placed yet", "strategic": bool(s.get("strategic"))}
               for s in BR._mask_map(plane, intent, hand.get("source_map") or [], rt.viewer)]
    return {"charter": {"title": intent.get("title"), "question": intent.get("question") or contracts.NOT_YET},
            "measures": _cap(measures), "processes": _cap([{"name": p.get("name")} for p in hand.get("processes") or [] if isinstance(p, dict)]),
            "sources": _cap(sources)}


def _scd_text(model: dict) -> dict:
    """The model with slowly changing types as words: a bare number would need a group size."""
    dims = [{**d, "scd": f"type {d['scd']}" if d.get("scd") is not None else None} for d in model.get("dimensions") or []]
    return {"facts": _cap(list(model.get("facts") or [])), "dimensions": _cap(dims)}


def _marks(marks: dict) -> dict:
    """Each path's provenance mark with the most common mark said once (SF14b: a mark per path of a real blueprint, some 250 paths, made
    one message longer than the gateway takes)."""
    if not marks:
        return {}
    common = Counter(marks.values()).most_common(1)[0][0]
    return {"every other path": common, **{str(m): [p for p, x in marks.items() if x == m] for m in dict.fromkeys(marks.values()) if m != common}}


def read_model(plane, rt: Runtime) -> dict:
    bp = _blueprint(plane)
    if bp is None:
        return _no("There is no blueprint yet: the baseline is not signed.")
    shown = B._shown(bp, rt.viewer)
    marks = {p: (m or {}).get("mark") for p, m in (bp.get("provenance") or {}).items()}
    return {"state": bp.get("state"), "model": _scd_text(shown["model"]), "lineage": _cap(shown["lineage"]), "marks": _marks(marks)}


def read_contracts(plane, rt: Runtime) -> dict:
    hidden_src, hidden = runner._hidden_sources(plane, rt.viewer), _hidden_codes(plane, rt)
    out = []
    for c in contracts.derive(plane):
        if c["source"] in hidden_src:
            continue
        out.append({"source": c["source"], "fields": [{"name": s["field"], "type": s["type"]} for s in c["schema"]][:MAX_LIST],
                    "marts": [m for m in c["marts"] if m.split(".", 1)[-1] not in hidden],
                    "rules": [r for r in c["rules"] if r.partition(":")[0].lower() not in hidden][:MAX_LIST],
                    "depends_on": c["depends_on"], "expected": c["expected"], "sla": c["sla"], "mark": c["mark"]})
    return _cap(out)


def _table_of(con, source: str) -> str | None:
    for schema in ("silver", "bronze"):
        if _columns(con, schema, source):
            return schema
    return None


def read_profile(plane, rt: Runtime, source: str) -> dict:
    """Whole-table counts per field: empties and distinct values. Unavailable under five rows."""
    if not _source_ok(plane, rt, source):
        return _no("No such source.")
    con = _readonly(plane)
    if con is None:
        return _no("Nothing has landed yet.")
    try:
        schema = _table_of(con, source)
        if schema is None:
            return _no("Nothing has landed for this source yet.")
        cols = [(c, t) for c, t in _columns(con, schema, source) if c not in _META][:MAX_LIST]
        tbl = f"{schema}.{_q(source)}"
        n = con.execute(f"select count(*) from {tbl}").fetchone()[0]
        if not group_ok(n):
            return _no("Fewer than five rows, so nothing is shown.")
        fields = []
        for c, t in cols:
            empty, distinct = con.execute(f"select count(*) filter (where {_q(c)} is null or trim(cast({_q(c)} as varchar)) = ''), "
                                          f"count(distinct {_q(c)}) from {tbl}").fetchone()
            fields.append({"name": c, "type": t.lower(), "nulls": empty, "distinct": distinct, "group_size": n})
        return {"layer": schema, "row_count": n, "group_size": n, "fields": fields}
    finally:
        con.close()


def read_change_rate(plane, rt: Runtime, source: str, key: str) -> dict:
    """How many keys changed any other field across the newest loads of bronze (evidence for slowly changing suggestions)."""
    if not _source_ok(plane, rt, source):
        return _no("No such source.")
    con = _readonly(plane)
    if con is None:
        return _no("Nothing has landed yet.")
    try:
        cols = [c for c, _ in _columns(con, "bronze", source)]
        if key not in cols or key in _META:
            return _no("That field is not in this source.")
        rest = [c for c in cols if c not in _META and c != key] or [key]
        h = "md5(concat_ws('|', " + ", ".join(f"coalesce(cast({_q(c)} as varchar), '')" for c in rest) + "))"
        tbl = f"bronze.{_q(source)}"
        keys, changed, loads = con.execute(
            f"with l as (select {_q(LOAD_ID)} id from {tbl} group by 1 order by max({_q(LOADED_AT)}) desc limit {LOADS}), "
            f"k as (select {_q(key)} k, count(distinct {h}) v from {tbl} where {_q(LOAD_ID)} in (select id from l) group by 1) "
            f"select count(*), count(*) filter (where v > 1), (select count(*) from l) from k").fetchone()
    finally:
        con.close()
    if not group_ok(keys):
        return _no("Fewer than five keys, so nothing is shown.")
    return {"keys": keys, "keys_changed_last_n_loads": changed, "loads": loads, "group_size": keys}


def read_architecture(plane, rt: Runtime, view: str) -> dict:
    comps, _ = architecture.masked(architecture.read(plane)["components"], rt.viewer)
    if view not in architecture.VIEWS and view != "all":
        return _no("The views are data, infrastructure, enterprise or all.")
    return _cap([{"id": c["id"], "kind": c.get("kind"), "view": c.get("view"), "state": c.get("state"), "restricted": bool(c.get("restricted"))}
                 for c in comps if view == "all" or c.get("view") == view])


def read_decisions(plane, rt: Runtime, topic: str) -> dict:
    from sh_platform.build.agents import modelling
    return _cap([{"text": d["text"], "at": d.get("at")} for d in modelling.decisions(plane, str(topic))])


def read_pack(plane, rt: Runtime, topic: str) -> dict:
    from sh_platform.build.agents import modelling
    return {"passages": modelling.pick(str(topic))}


def read_queries(plane, rt: Runtime) -> dict:
    """Which marts each measure reads, from the blueprint lineage. Names only.
    ponytail: the knowledge map's consume nodes (dashboards) are not read yet; add them when a dashboard records the marts it reads."""
    bp = _blueprint(plane)
    if bp is None:
        return _no("There is no blueprint yet: the baseline is not signed.")
    marts: dict[str, dict] = {}
    for ln in B._shown(bp, rt.viewer)["lineage"]:
        if ln.get("hidden"):
            continue
        m = marts.setdefault(".".join(str(ln.get("mart", "")).split(".")[:2]), {"measures": [], "sources": []})
        for k, v in (("measures", ln.get("measure")), ("sources", ln.get("source"))):
            if v and v not in m[k]:
                m[k].append(v)
    return _cap([{"mart": k, **v, "dashboards": []} for k, v in marts.items()])


def search_reference(plane, rt: Runtime, query: str) -> dict:
    """One public-terms query to the first allowlisted host, through the gateway (the consume/market.py pattern)."""
    hosts = EgressPolicy(plane).internet_hosts()
    if not hosts:
        return _no("No outside source is listed for this company.")
    gw = rt.gateway or _internet_gateway(plane)
    try:
        text = gw.internet_query(MODULE_ID, hosts[0], str(query)[:MAX_TITLE]).text
    except EgressBlocked as e:
        log.info("A reference search was not sent (%s).", e.reason_code)
        return _no(e.message)
    return {"source": hosts[0], "text": " ".join(str(text).split())[:MAX_TEXT]}


def _internet_gateway(plane) -> EgressGateway:
    def no_model(url, body):
        raise EgressBlocked("transport_failed")  # this gateway carries internet queries only
    return EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[], transport=no_model)


# ---- Flow's read tools --------------------------------------------------------------------------------------------------------------

def read_runs(plane, rt: Runtime, source: str) -> dict:
    """The last ten runs of a source: status, checks and counts, each count carrying the run's row count as its group."""
    if not _source_ok(plane, rt, source):
        return _no("No such source.")
    out = []
    for r in [r for r in runner.read_runs(plane) if r.get("source") == source][-10:]:
        n = r.get("rows")
        out.append({"run_id": r.get("id"), "status": r.get("status"), "on_time": r.get("on_time"), "schema_ok": r.get("schema_ok"),
                    "loaded": {"row_count": n, "group_size": n} if group_ok(n) else _no("fewer than five rows"),
                    "rules": [_rule_count(x, n) for x in r.get("rules") or []][:MAX_LIST],
                    "not_run": list(r.get("not_run") or [])[:MAX_LIST], "notes": list(r.get("notes") or [])[:MAX_LIST]})
    return _cap(out)


def _rule_count(x: dict, n) -> dict:
    """A failing-row count is a figure only when it and the run's rows are five or more; under five it reads "fewer than five" (plan 3.4),
    as read_quarantine says it for the same rows (SF14)."""
    out, c = {"rule": x.get("rule"), "passed": x.get("passed")}, x.get("count")
    if group_ok(n) and group_ok(c):
        return {**out, "count": c, "group_size": n}
    return {**out, "count_text": "no rows" if not c else "fewer than five"} if group_ok(n) else out


def read_quarantine(plane, rt: Runtime, source: str) -> dict:
    """Counts of rows set aside per rule and field in `quarantine.<source>` (columns `_rule`, `_field`); never a value."""
    if not _source_ok(plane, rt, source):
        return _no("No such source.")
    con = _readonly(plane)
    if con is None:
        return _no("Nothing has landed yet.")
    try:
        cols = {c for c, _ in _columns(con, "quarantine", source)}
        if not cols:
            return _no("No rows have been set aside for this source.")
        tbl = f"quarantine.{_q(source)}"
        rule = _q("_rule") if "_rule" in cols else "'not recorded'"
        fld = _q("_field") if "_field" in cols else "'not recorded'"
        n = con.execute(f"select count(*) from {tbl}").fetchone()[0]
        groups = con.execute(f"select {rule}, {fld}, count(*) from {tbl} group by 1, 2 order by 3 desc limit {MAX_LIST}").fetchall()
    finally:
        con.close()
    by_rule = [{"rule": r, "field": f, "count": c, "group_size": c} if group_ok(c) else {"rule": r, "field": f, "count_text": "fewer than five"}
               for r, f, c in groups]
    if not group_ok(n):
        return {"total_text": "fewer than five", "by_rule": by_rule}
    return {"row_count": n, "group_size": n, "by_rule": by_rule}


def read_alerts(plane, rt: Runtime) -> dict:
    hidden_src, hidden = runner._hidden_sources(plane, rt.viewer), _hidden_codes(plane, rt)
    return _cap([{"alert_id": a.get("id"), "kind": a.get("kind"), "source": a.get("source"), "since": a.get("opened")}
                 for a in alerts._read(plane) if a.get("state") == "open" and a.get("source") not in hidden_src
                 and str(a.get("measure") or "").lower() not in hidden])


def read_dialect(plane, rt: Runtime) -> dict:
    """The stated warehouse target and, per statement, the constructs that read differently there. No SQL text leaves."""
    from sh_platform.build import dialect
    doc = dialect.build(plane)
    return {"state": doc["state"], "dialect": doc.get("dialect"), "message": doc["message"],
            "statements": [{"name": s["name"], "changed_constructs": s["changed_constructs"]} for s in doc["statements"]][:MAX_LIST]}


# ---- the propose sink (3.3): an argument check only; the caller files what it returns ---------------------------------------------

# One source of truth: the keys per kind are the proposals store's own schema.
_COMMON = set(KINDS["model_change"]["schema"]) & set(KINDS["incident_note"]["schema"]) & set(KINDS["architecture_decision"]["schema"])
KIND_KEYS = {k: set(v["schema"]) for k, v in KINDS.items()}
AGENT_KINDS = {"span": ("model_change", "architecture_decision"), "flow": ("model_change", "incident_note")}
EFFORTS = ("small", "medium", "large")


def _text(v, cap: int, name: str, required: bool = False) -> str | None:
    if v is None and not required:
        return None
    if not isinstance(v, str) or not v.strip() or len(v) > cap:
        raise ToolRefused(f"{name} must be text of up to {cap} characters.")
    return v.strip()


def _names(v, name: str) -> list[str]:
    if not isinstance(v, list) or len(v) > MAX_LIST or not all(isinstance(x, str) and 0 < len(x) <= MAX_TITLE for x in v):
        raise ToolRefused(f"{name} must be a list of short names.")
    return v


def _from_line(x, keys: tuple[str, ...]):
    """SF14b: the model writes an alternative or a cite as one text line, "option: ...; why_not: ...", since a list of objects in its own
    tool call would come back through the gateway as raw rows. An object is still accepted."""
    if not isinstance(x, str):
        return x
    m = re.fullmatch(r"\s*" + r";\s*".join(rf"{k}:\s*(.+?)" for k in keys) + r"\s*", x, re.S)
    return dict(zip(keys, m.groups())) if m else x


def _objs(v, keys: tuple[str, ...], name: str) -> list[dict]:
    v = [_from_line(x, keys) for x in v] if isinstance(v, list) else v
    if not isinstance(v, list) or len(v) > MAX_LIST or not all(isinstance(x, dict) and set(x) == set(keys) for x in v):
        raise ToolRefused(f"{name} must be a list of {{{', '.join(keys)}}}.")
    return [{k: _text(x[k], MAX_TEXT, name, True) for k in keys} for x in v]


def _evidence(v) -> dict:
    if not isinstance(v, dict) or set(v) - {"counts", "fields", "queries"}:
        raise ToolRefused("evidence holds counts, fields and queries only.")
    counts = v.get("counts") or []
    if not isinstance(counts, list) or not all(isinstance(c, dict) and set(c) == {"label", "value", "group_size"} and isinstance(c["label"], str)
                                                 and isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool)
                                                 and group_ok(c["group_size"]) for c in counts):
        raise ToolRefused("Each count is {label, value, group_size} with a group of five or more.")
    return {"counts": counts[:MAX_LIST], "fields": _names(v.get("fields") or [], "fields"), "queries": _names(v.get("queries") or [], "queries")}


def check_proposal(agent: str, kind, args) -> dict:
    """The cleaned {kind, args}, or ToolRefused naming what is wrong. Closed kinds, closed keys; the addressee is never the agent's choice."""
    if kind not in AGENT_KINDS[agent]:
        raise ToolRefused(f"kind is one of {', '.join(AGENT_KINDS[agent])}.")
    if not isinstance(args, dict):
        raise ToolRefused("args must be an object.")
    unknown = set(args) - KIND_KEYS[kind]
    if unknown:
        raise ToolRefused("Unknown keys: " + ", ".join(sorted(map(str, unknown))) + ".")
    out = {"title": _text(args.get("title"), MAX_TITLE, "title", True), "what": _text(args.get("what"), MAX_TEXT, "what", True),
           "why": _text(args.get("why"), MAX_TEXT, "why", True), "evidence": _evidence(args.get("evidence") or {})}
    impact = args.get("impact") or {}
    if not isinstance(impact, dict) or set(impact) - {"contracts", "marts", "dashboards"}:
        raise ToolRefused("impact holds contracts, marts and dashboards only.")
    out["impact"] = {k: _names(impact.get(k) or [], k) for k in ("contracts", "marts", "dashboards")}
    out["alternatives"] = _objs(args.get("alternatives") or [], ("option", "why_not"), "alternatives")
    out["cites"] = _objs(args.get("cites") or [], ("source", "passage_id"), "cites")
    if args.get("effort") is not None and args["effort"] not in EFFORTS:
        raise ToolRefused("effort is small, medium or large.")
    out["effort"] = args.get("effort")
    out["technique"] = _text(args.get("technique"), MAX_TITLE, "technique")
    for k, (typ, req) in KINDS[kind]["schema"].items():
        if k in _COMMON:
            continue
        out[k] = _names(args[k], k) if typ is list and (req or k in args) else _text(args.get(k), MAX_TITLE, k, req)
    return {"kind": kind, "args": out}


_PROPOSE_HELP = ("Suggest one change for a named person to decide. Nothing is applied. kind: {kinds}. args: title, what, why (text), "
                 "evidence {{counts: [{{label, value, group_size}}], fields: [name], queries: [name]}}, impact {{contracts, marts, dashboards}}, "
                 "alternatives as a list of text lines, each exactly like \"option: keep type 1; why_not: loses the history the catalogue needs\", "
                 "effort (small, medium, large), cites as a list of text lines, each exactly like \"source: read_pack; passage_id: kimball\"{extra}. "
                 "Use only figures from this run's tool results.")


# ---- what crosses the gateway (SF14b): lists of objects as plain text lines --------------------------------------------------------

def _bad_group(d: dict) -> bool:
    """The gateway's suppressed-figure rule (egress/rows.py): a group size under five, or a label and value with no group size."""
    return ("group_size" in d and not group_ok(d["group_size"])) or ("group_size" not in d and "label" in d and "value" in d)


def _val(v, counts) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, dict):
        return "(" + _line(v, counts) + ")"
    if isinstance(v, list):
        return ", ".join(_val(x, counts) for x in v) or "none"
    return str(v)


def _line(item, counts) -> str:
    """One item as "name: value" pairs. A figure keeps its group ("214 (group of 1180)"); a figure the gateway would suppress is not shown."""
    if not isinstance(item, dict):
        return _val(item, counts)
    g, bad = item.get("group_size"), _bad_group(item)
    parts = []
    for k, v in item.items():
        if k == "group_size":
            continue
        if is_figure(k, v) and (bad or not group_ok(g)):
            parts.append(f"{k}: not shown")
        elif is_figure(k, v):
            counts.setdefault(g, []).append(v)
            parts.append(f"{k}: {v} (group of {g})")
        else:
            parts.append(f"{k}: {_val(v, counts)}")
    return "; ".join(parts)


def _lines(o, counts):
    if isinstance(o, dict):
        return {k: _lines(v, counts) for k, v in o.items()}
    if isinstance(o, list):
        boxes = [x for x in o if isinstance(x, (dict, list))]
        if len(boxes) >= 2 and not all(isinstance(x, dict) and group_ok(x.get("group_size")) and not _bad_group(x) for x in boxes):
            return [_line(x, counts) for x in o]
        return [_lines(x, counts) for x in o]
    return o


def as_lines(context: dict) -> dict:
    """A model context with every list of objects as text lines, one per item, which the gateway's raw-rows check accepts. `facts` stays as
    it is: the agent loop reads it for the number guard, and each fact carries its own group size."""
    return {k: v if k == "facts" else _lines(v, {}) for k, v in context.items()}  # only the top-level facts: model.facts are fact tables


def tool_lines(out):
    """A tool result for the model: the registry's own summary check first (so a figure without a group is already hidden), then lists of
    objects as text lines. The figures inside those lines go along in `counts`, one object per group size, so the loop still records them as
    this run's facts for the number guard."""
    counts: dict = {}
    out = _lines(_summary_only(out), counts)
    if counts and isinstance(out, dict):
        out["counts"] = [{"group_size": g, **{f"figure_{i}": v for i, v in enumerate(dict.fromkeys(vs), 1)}}
                         for g, vs in counts.items()][:MAX_LIST]
    return out


# ---- the registries ---------------------------------------------------------------------------------------------------------------

def _add(reg: ToolRegistry, plane, rt: Runtime, name: str, func, description: str, parameters: dict[str, str], **kw) -> None:
    reg.register(MODULE_ID, name, lambda **a: tool_lines(func(plane, rt, **a)), read_only=True, description=description, parameters=parameters, **kw)


def _add_propose(reg: ToolRegistry, agent: str) -> None:
    extra = "; " + "; ".join(f"{k} also takes " + ", ".join(f"{n}{'' if r else ' (optional)'}" for n, (_, r) in KINDS[k]["schema"].items()
                                                                   if n not in _COMMON) for k in AGENT_KINDS[agent])
    reg.register(MODULE_ID, "propose", lambda kind, args: check_proposal(agent, kind, args), read_only=False, proposes=True,
                 description=_PROPOSE_HELP.format(kinds=", ".join(AGENT_KINDS[agent]), extra=extra),
                 parameters={"kind": "string", "args": "object"})


def span_registry(plane, rt: Runtime) -> ToolRegistry:
    reg = ToolRegistry(rt.gate)
    _add(reg, plane, rt, "read_handoff", read_handoff, "What the Intent Centre handed to Build: charter, measures, processes, sources.",
         {"intent_id": "string"})
    _add(reg, plane, rt, "read_model", read_model, "The blueprint's silver model and lineage, with each path's provenance mark.", {})
    _add(reg, plane, rt, "read_contracts", read_contracts, "Pipeline contracts per source: fields, marts, rules, schedule.", {})
    _add(reg, plane, rt, "read_profile", read_profile, "Whole-table counts per field of one source: empties and distinct values.",
         {"source": "string"})
    _add(reg, plane, rt, "read_change_rate", read_change_rate, "How many keys of a source changed another field over the newest loads.",
         {"source": "string", "key": "string"})
    _add(reg, plane, rt, "read_architecture", read_architecture, "Components of the architecture record for a view (data, "
         "infrastructure, enterprise or all).", {"view": "string"})
    _add(reg, plane, rt, "read_decisions", read_decisions, "What this company decided earlier on a modelling topic, and why.",
         {"topic": "string"})
    _add(reg, plane, rt, "read_pack", read_pack, "At most three passages on modelling techniques for a topic.", {"topic": "string"})
    _add(reg, plane, rt, "read_queries", read_queries, "Which marts each measure reads.", {})
    if EgressPolicy(plane).is_internet_allowed(MODULE_ID):
        _add(reg, plane, rt, "search_reference", search_reference, "Search published guidance in public terms only. What comes back "
             "is outside material.", {"query": "string"}, outside=True)
    _add_propose(reg, "span")
    return reg


def flow_registry(plane, rt: Runtime) -> ToolRegistry:
    reg = ToolRegistry(rt.gate)
    _add(reg, plane, rt, "read_contracts", read_contracts, "Pipeline contracts per source: fields, marts, rules, schedule.", {})
    _add(reg, plane, rt, "read_runs", read_runs, "The last ten runs of a source: status, checks and counts.", {"source": "string"})
    _add(reg, plane, rt, "read_quarantine", read_quarantine, "Counts of rows set aside per rule and field for a source.",
         {"source": "string"})
    _add(reg, plane, rt, "read_alerts", read_alerts, "Open alerts: kind, source and since when.", {})
    _add(reg, plane, rt, "read_dialect", read_dialect, "For the stated warehouse target, the constructs that read differently there.", {})
    _add_propose(reg, "flow")
    return reg
