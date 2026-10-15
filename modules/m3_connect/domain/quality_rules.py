"""Data-quality facts from the scan, recorded as quality rules on the catalogue entry of each measure a source feeds.

A rule is a proposal beside module 2's signed catalogue, never an edit of it: it is written to
intents/m2_baseline/<baseline_id>/quality_rules.json (the reverse of inputs.py, which reads module 2's signed outcome by path; this module never
imports module 2). The file is `{"rules": {measure_id: [rule]}}`; a rule is
`{id, source_id, kind, column, text, figure, state, by, provenance: {from, at}}` (shape in module 2's contracts/catalogue.yaml, `quality_rules`).

Lens writes `state: proposal, by: Lens`. A scan again replaces Lens's own proposals for that source and keeps every other rule (a person's
edit, rule 7). Who may see a rule is decided on reading: `visible` keeps a rule only for a measure and a source the reader may see (inputs.py).
"""
import logging
import re
from pathlib import Path

from modules.m3_connect.domain import inputs as I
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
LENS = "Lens"
PROPOSAL = "proposal"
FILL, PERIOD, MISSING, BENCHMARK = "fill_rate", "period_gap", "missing_field", "missing_benchmark"
KIND_OF_GAP = {"half_empty": FILL, "some_empty": FILL, "period_short": PERIOD, "missing_column": MISSING}
_HASH_PREFIX = re.compile(r"^[0-9a-f]{8}_")


def _table_of(profile: dict, gap: dict) -> dict | None:
    tables = profile.get("tables") or []
    fid = gap.get("field_id")
    return next((t for t in tables if fid and any(c.get("field_id") == fid for c in t["columns"])), None) or \
        next((t for t in tables if gap.get("table") and t.get("name") == gap["table"]), None)


def _figure(kind: str, gap: dict, table: dict | None) -> dict:
    if kind == FILL:
        col = next((c for c in (table or {}).get("columns", []) if gap.get("field_id") and c.get("field_id") == gap["field_id"]
                    or c.get("name") == gap.get("column")), None)
        if col:
            return {"fill": col["fill"], "empty": col["nulls"], "of": col["nulls"] + col["non_empty"]}
        return {"fill": gap.get("fill")}
    if kind == PERIOD:
        return {"data_to": ((table or {}).get("date_range") or {}).get("to"), "period_to": gap.get("period_to")}
    return {"found": False}


def rules_for_source(profile: dict, source_id: str, period: dict, at: str) -> dict[str, list[dict]]:
    """{measure_id: [rule]} from the scan's gaps. A gap names the measures it hurts; one that names none (a column no measure uses) gives no rule."""
    out: dict[str, list[dict]] = {}
    for gap in profile.get("gaps") or []:
        kind = KIND_OF_GAP.get(gap.get("kind"))
        if kind is None:
            continue  # a file that has not arrived is not a quality fact
        table = _table_of(profile, gap)
        if any(c.get("personal") and (c.get("field_id") == gap.get("field_id") or c.get("name") == gap.get("column")) for c in (table or {}).get("columns", [])):
            continue  # a personal column is never named in a rule
        name = _HASH_PREFIX.sub("", (table or {}).get("file") or "") or "this source"
        figure = _figure(kind, {**gap, "period_to": period.get("to")}, table)
        for mid in gap.get("measures") or []:
            out.setdefault(mid, []).append({
                "id": f"{source_id}:{kind}:{gap.get('column') or gap.get('field_id') or ''}", "source_id": source_id, "kind": kind,
                "column": gap.get("column"), "text": gap["text"], "figure": figure, "state": PROPOSAL, "by": LENS,
                "provenance": {"from": f"the scan of {name}", "at": at}})
    return out


def benchmark_rules(benchmarks: dict, measure_ids: list[str], at: str) -> dict[str, list[dict]]:
    """A measure with no benchmark figure gets a rule (a benchmark belongs to no source, so source_id is None)."""
    have = (benchmarks or {}).get("measures") or {}
    return {m: [{"id": f"benchmark:{m}", "source_id": None, "kind": BENCHMARK, "column": "benchmark", "figure": {"found": False},
                 "text": "No benchmark figure has been given for this measure.", "state": PROPOSAL, "by": LENS,
                 "provenance": {"from": "the benchmark file" if (benchmarks or {}).get("file") else "the scan: no benchmark file yet", "at": at}}]
            for m in measure_ids if not have.get(m)}


def _path(plane, baseline_id: str) -> Path:
    if not (isinstance(baseline_id, str) and I._HEX.fullmatch(baseline_id)):
        raise ValueError("no baseline")
    return plane.path("intents", "m2_baseline", baseline_id, "quality_rules.json")


def read(plane, baseline_id: str) -> dict[str, list[dict]]:
    doc = read_json_strict(_path(plane, baseline_id), dict) or {}
    return doc.get("rules") or {}


def replace(plane, baseline_id: str, source_id: str | None, fresh: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Swaps Lens's earlier proposals for this source (None: the benchmark ones) for `fresh`; every other rule stays."""
    path = _path(plane, baseline_id)
    with lock_for(path.parent):
        old = read(plane, baseline_id)
        mine = lambda r: r.get("by") == LENS and r.get("state") == PROPOSAL and r.get("source_id") == source_id  # noqa: E731
        kept = {m: [r for r in rs if not mine(r)] for m, rs in old.items()}
        out = {m: kept.get(m, []) + fresh.get(m, []) for m in kept.keys() | fresh.keys()}
        out = {m: rs for m, rs in out.items() if rs}
        write_json_atomic(path, {"rules": out})
    return out


def record_scan(plane, baseline_outcome: dict | None, source_id: str, profile: dict, at: str) -> int:
    """After a scan: writes the rules for the measures this source feeds. The profile is the unfiltered scan.
    Nothing is written when no baseline is signed. Returns how many rules the source now has."""
    if not baseline_outcome:
        return 0
    fresh = rules_for_source(profile, source_id, profile.get("period") or {}, at)
    return sum(map(len, replace(plane, baseline_outcome["baseline_id"], source_id, fresh).values()))


def visible(rules: dict[str, list[dict]], inputs: dict) -> dict[str, list[dict]]:
    """The rules this reader may see: `inputs` is `read_inputs` for this reader, so a restricted measure and a source behind a list are gone."""
    live = {m["id"] for m in inputs["measures"] if not m.get("restricted")}
    open_sources = {I._t(s.get("Source ID")) for s in inputs["sources"]}
    out = {m: [r for r in rs if r.get("source_id") is None or r["source_id"] in open_sources] for m, rs in rules.items() if m in live}
    return {m: rs for m, rs in out.items() if rs}
