"""E0d: score the data agent (card E0b) against the synthetic evaluation set.
Usage: python tools/eval_data_agent.py <company> [--baseline] [--bar 0.8] [--dir tests/v1/fixtures/e0d]
The company must already exist in the entitlement store (the agent opens its plane); run it from the repo root or anywhere.
Contract (E0b2 landed), imported lazily; a missing module exits 2:
  sh_platform.v1.e0b_tools.profile_sheet(path) -> dict
      {"sheet": str, "header_row": int, "columns": [str], "status": "final"|"in_progress"}
  sh_platform.v1.e0b_tools.propose_mapping(plane, profile) -> dict
      {"columns": {source_column: "table.field" | "ignore" | {"target": ..., "transform": {...}}},
       "status": "final"|"in_progress", "totals_match": bool|None}   # False = stated totals do not add up
`plane` is the company slug. --baseline scores a trivial exact-column-name mapper instead of the agent."""
import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "v1" / "fixtures" / "e0d"
DBML = ROOT / "docs" / "v2" / "evidence-to-action-mvp.dbml"
PREFERRED = ["position_snapshots", "valuation_observations", "cash_movements", "nav_snapshots", "market_observations",
             "benchmark_components"]


def dbml_fields(path: Path = DBML) -> dict:
    """{table: [field, ...]} by a simple scan; index and note blocks are skipped."""
    out, cur = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"Table (\w+) \{", line)
        if m:
            cur = out.setdefault(m.group(1), [])
        elif cur is not None and line.startswith("}"):
            cur = None
        elif cur is not None:
            f = re.match(r"  (\w+) [\w(),]+", line)
            if f:
                cur.append(f.group(1))
    return out


def baseline_profile(path: Path) -> dict:
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    hdr = next((i for i, r in enumerate(rows[:15]) if sum(isinstance(c, str) for c in r) >= 3), 0)
    cols = [c for c in rows[hdr] if c is not None]
    text = " ".join(str(c) for r in rows for c in r if isinstance(c, str)).lower() + ws.title.lower()
    stated = next((r for r in rows[hdr + 1:] if isinstance(r[0], str) and r[0].lower().startswith("total")), None)
    match = None
    if stated:
        body = rows[hdr + 1:rows.index(stated)]
        match = all(abs(sum(r[i] for r in body if isinstance(r[i], (int, float))) - v) < 0.5
                    for i, v in enumerate(stated) if isinstance(v, (int, float)))
    return {"sheet": ws.title, "header_row": hdr + 1, "columns": cols, "totals_match": match,
            "status": "in_progress" if ("in progress" in text or "draft" in text) else "final"}


def baseline_mapping(plane: str, profile: dict) -> dict:
    fields = dbml_fields()
    lookup = {}
    for t in reversed(PREFERRED):  # first preferred table wins
        for f in fields[t]:
            lookup[f] = f"{t}.{f}"
    cols = {c: lookup.get(re.sub(r"\W+", "_", str(c).strip().lower()), "ignore") for c in profile["columns"]}
    return {"columns": cols, "status": profile["status"], "totals_match": profile.get("totals_match")}


def load_agent():
    try:
        from sh_platform.v1 import e0b_tools
        return e0b_tools.profile_sheet, e0b_tools.propose_mapping
    except ImportError as e:
        print(f"data agent could not be imported: {e}", file=sys.stderr)
        sys.exit(2)


def _norm(v):
    return v if isinstance(v, dict) else {"target": v}


def score(company: str, profile_sheet, propose_mapping, folder: Path = FIX) -> dict:
    known = {f"{t}.{f}" for t, fs in dbml_fields().items() for f in fs}
    per = {}  # trap -> [right, total]
    inv = right_status = n_status = caught = n_totals = struct = n_files = 0
    for ep in sorted((folder / "expected").glob("*.json")):
        exp = json.loads(ep.read_text(encoding="utf-8"))
        n_files += 1
        prof = profile_sheet(folder / "workbooks" / exp["workbook"])
        prop = propose_mapping(company, prof)
        struct += prof.get("sheet") == exp["sheet"] and prof.get("header_row") == exp["header_row"]
        got = {k: _norm(v) for k, v in prop.get("columns", {}).items()}
        right = 0
        for col, want in exp["columns"].items():
            g = got.get(col, {})
            right += g.get("target") == want["target"] and all(
                (g.get("transform") or {}).get(k) == v for k, v in (want.get("transform") or {}).items())
        inv += sum(g.get("target") not in (None, "ignore") and g.get("target") not in known for g in got.values())
        for tr in exp["traps"]:
            s = per.setdefault(tr, [0, 0])
            s[0] += right
            s[1] += len(exp["columns"])
        if "in_progress" in exp["traps"]:
            n_status += 1
            right_status += prop.get("status") == "in_progress"
        if "totals_mismatch" in exp["traps"]:
            n_totals += 1
            caught += prop.get("totals_match") is False
    tot = [sum(v[0] for v in per.values()), sum(v[1] for v in per.values())]
    return {"files": n_files, "structure_ok": struct, "mapping_by_trap": {k: v[0] / v[1] for k, v in sorted(per.items())},
            "mapping_accuracy": tot[0] / tot[1] if tot[1] else 0.0, "invented_targets": inv,
            "in_progress_caught": f"{right_status}/{n_status}", "totals_mismatch_caught": f"{caught}/{n_totals}",
            "clean": inv == 0 and right_status == n_status and caught == n_totals}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("company")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--bar", type=float, default=0.8, help="minimum mapping accuracy for the real agent")
    ap.add_argument("--dir", type=Path, default=FIX)
    a = ap.parse_args(argv)
    fns = (baseline_profile, baseline_mapping) if a.baseline else load_agent()
    r = score(a.company, *fns, folder=a.dir)
    print(f"{'baseline' if a.baseline else 'data agent'} on {r['files']} workbooks for {a.company}")
    print(f"  sheet and header row right: {r['structure_ok']}/{r['files']}")
    for k, v in r["mapping_by_trap"].items():
        print(f"  mapping accuracy, trap {k:<20} {v:6.1%}")
    print(f"  mapping accuracy overall           {r['mapping_accuracy']:6.1%}")
    print(f"  invented targets                   {r['invented_targets']}")
    print(f"  in-progress sheets recognised      {r['in_progress_caught']}")
    print(f"  totals mismatches caught           {r['totals_mismatch_caught']}")
    if a.baseline:
        return 0
    ok = r["mapping_accuracy"] >= a.bar and r["clean"]
    print("PASS" if ok else f"BELOW BAR ({a.bar:.0%} mapping, no invented targets, every trap caught)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
