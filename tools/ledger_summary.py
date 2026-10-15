"""Merge docs/product/ledger/*.yaml into docs/product/input_ledger.yaml, validate rows, print the totals MOAT.md needs.

Usage: python tools/ledger_summary.py [--check]   (--check validates and prints without writing the merged file
or refreshing the generated block between the ledger markers in docs/product/MOAT.md)
Exit code 1 when any row fails validation. Minutes are planning estimates, never facts.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "docs" / "product" / "ledger"
OUT = ROOT / "docs" / "product" / "input_ledger.yaml"
SPEC_DIR = ROOT / "docs" / "specs" / "intent-centre"

MODES = {"manual", "confirm", "derived", "automatic"}
JOURNEYS = {"initiative", "brainstorm", "checkin", "problem", "decision", "shared", "build", "consume", "admin"}
BUILT = MODES | {"missing"}  # missing: the spec has the input, no build was found (a feature gap)
STAGES = {"notice", "think", "decide", "build", "run", "prove", "shared"}
REQUIRED = ("id", "spec", "journey", "stage", "screen", "input", "person", "mode", "source",
            "minutes_without", "minutes_with", "basis", "claim")


def _spec_key(p: Path):
    return (0, int(p.stem)) if p.stem.isdigit() else (1, p.stem)


def load(ledger_dir: Path = LEDGER_DIR):
    rows, errors = [], []
    for f in sorted(ledger_dir.glob("*.yaml"), key=_spec_key):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        except yaml.YAMLError as e:
            errors.append(f"{f.name}: not valid YAML ({e.__class__.__name__})")
            continue
        if not isinstance(data, list):
            errors.append(f"{f.name}: top level must be a list of rows")
            continue
        for i, r in enumerate(data):
            if isinstance(r, dict):
                rows.append({**r, "_file": f.name})
            else:
                errors.append(f"{f.name}[{i}]: row is not a mapping")
    return rows, errors


def pending_specs(spec_dir: Path = SPEC_DIR, ledger_dir: Path = LEDGER_DIR):
    """Spec numbers that have a spec file but no ledger file yet."""
    have = {f.stem for f in ledger_dir.glob("*.yaml")}
    nums = {f.name.split("-", 1)[0] for f in spec_dir.glob("[0-9][0-9]-*.md")} - {"00"}
    return sorted(n for n in nums if n not in have)


def validate(rows):
    errors, seen = [], set()
    for r in rows:
        where = f"{r.get('_file', '?')}:{r.get('id', '?')}"
        for k in REQUIRED:
            if r.get(k) in (None, ""):
                errors.append(f"{where}: missing {k}")
        if r.get("mode") not in MODES:
            errors.append(f"{where}: mode {r.get('mode')!r} not in {sorted(MODES)}")
        if "built" in r and r["built"] not in BUILT:
            errors.append(f"{where}: built {r['built']!r} not in {sorted(BUILT)}")
        if r.get("mode") == "confirm" and not r.get("agent"):
            errors.append(f"{where}: confirm rows must name the agent")
        if r.get("journey") not in JOURNEYS:
            errors.append(f"{where}: journey {r.get('journey')!r} not allowed")
        if r.get("stage") not in STAGES:
            errors.append(f"{where}: stage {r.get('stage')!r} not allowed")
        for k in ("minutes_without", "minutes_with"):
            v = r.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0):
                errors.append(f"{where}: {k} must be a non-negative number, got {v!r}")
        rid = r.get("id")
        if rid in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(rid)
    return errors


def _mins(r, k):
    v = r.get(k)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def totals(rows):
    t = {"rows": len(rows), "by_mode": Counter(r.get("mode") for r in rows)}
    for dim in ("journey", "stage", "person"):
        t[f"by_{dim}"] = defaultdict(Counter)
        for r in rows:
            t[f"by_{dim}"][r.get(dim)][r.get("mode")] += 1
    t["missing"] = [r for r in rows if r.get("built") == "missing"]
    t["minutes"] = defaultdict(lambda: [0, 0, 0])  # journey -> [without, with, rows]; missing rows are gaps, not savings
    for r in rows:
        if r.get("built") == "missing":
            continue
        m = t["minutes"][r.get("journey")]
        m[0] += _mins(r, "minutes_without")
        m[1] += _mins(r, "minutes_with")
        m[2] += 1
    t["top_savings"] = sorted((r for r in rows if r.get("built") != "missing"), key=lambda r: _mins(r, "minutes_with") - _mins(r, "minutes_without"))[:25]
    t["built_differs"] = [r for r in rows if r.get("built") and r["built"] not in (r.get("mode"), "missing")]
    t["manual"] = [r for r in rows if r.get("mode") == "manual"]
    return t


def report(t) -> str:
    out = [f"rows: {t['rows']}", "", "by mode:"]
    out += [f"  {m}: {n}" for m, n in t["by_mode"].most_common()]
    for dim in ("journey", "stage", "person"):
        out += ["", f"by {dim} (total; manual/confirm/derived/automatic):"]
        for k, c in sorted(t[f"by_{dim}"].items(), key=lambda kv: -sum(kv[1].values())):
            out.append(f"  {k}: {sum(c.values())}; " + "/".join(str(c[m]) for m in ("manual", "confirm", "derived", "automatic")))
    out += ["", "minutes per journey (planning estimates; without -> with, rows):"]
    for j, (w, x, n) in sorted(t["minutes"].items(), key=lambda kv: -kv[1][0]):
        out.append(f"  {j}: {w:g} -> {x:g} ({n} rows)")
    w, x = sum(v[0] for v in t["minutes"].values()), sum(v[1] for v in t["minutes"].values())
    out.append(f"  all: {w:g} -> {x:g}")
    out += ["", "top savings (planning estimates):"]
    out += [f"  {r['id']}: {_mins(r, 'minutes_without'):g} -> {_mins(r, 'minutes_with'):g}  {r.get('claim', '')}" for r in t["top_savings"]]
    out += ["", f"build differs from spec ({len(t['built_differs'])}):"]
    out += [f"  {r['id']}: spec {r.get('mode')}, built {r['built']}  {r.get('input', '')}" for r in t["built_differs"]]
    out += ["", f"missing in build, gaps not savings ({len(t['missing'])}):"]
    out += [f"  {r['id']}: spec {r.get('mode')}  {r.get('input', '')}" for r in t["missing"]]
    out += ["", f"manual rows ({len(t['manual'])}):"]
    out += [f"  {r['id']}: {r.get('person')} | {r.get('input')}" for r in t["manual"]]
    return "\n".join(out)


MOAT = ROOT / "docs" / "product" / "MOAT.md"
START, END = "<!-- ledger:start -->", "<!-- ledger:end -->"
_COLS = ("manual", "confirm", "derived", "automatic")


def moat_tables(t) -> str:
    """Markdown tables for MOAT.md's generated block. Minutes are planning estimates."""
    def table(dim, label):
        out = [f"| {label} | rows | " + " | ".join(_COLS) + " |", "|---|---:|" + "---:|" * len(_COLS)]
        for k, c in sorted(t[f"by_{dim}"].items(), key=lambda kv: (-sum(kv[1].values()), str(kv[0]))):
            out.append(f"| {k} | {sum(c.values())} | " + " | ".join(str(c[m]) for m in _COLS) + " |")
        return out
    out = [f"Rows: **{t['rows']}**. " + ", ".join(f"{m} {t['by_mode'][m]}" for m in _COLS) + ".", "",
           "### By journey", ""] + table("journey", "journey")
    out += ["", "### By stage", ""] + table("stage", "stage")
    out += ["", "### By role", ""] + table("person", "role")
    out += ["", "### Minutes per journey (planning estimates, not measurements)", "",
            "| journey | rows | minutes without | minutes with | saved |", "|---|---:|---:|---:|---:|"]
    for j, (w, x, n) in sorted(t["minutes"].items(), key=lambda kv: -kv[1][0]):
        out.append(f"| {j} | {n} | {w:g} | {x:g} | {w - x:g} |")
    w, x = sum(v[0] for v in t["minutes"].values()), sum(v[1] for v in t["minutes"].values())
    out.append(f"| all | {t['rows'] - len(t['missing'])} | {w:g} | {x:g} | {w - x:g} |")
    out += ["", f"### Missing in the build ({len(t['missing'])} rows: feature gaps, not counted as savings)", ""]
    out += [f"- `{r['id']}` ({r.get('mode')} in spec): {r.get('input', '')}" for r in t["missing"]] or ["- none"]
    if "pending" in t:
        out += ["", f"### Specs with no ledger file yet ({len(t['pending'])})", "",
                ", ".join(t["pending"]) or "none: every spec has its rows"]
    return "\n".join(out)


def refresh_moat(t, path: Path = MOAT) -> bool:
    """Replace the generated block in MOAT.md; prose outside the markers is left alone."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    a, b = text.find(START), text.find(END)
    if a < 0 or b < a:
        return False
    path.write_text(text[:a + len(START)] + "\n" + moat_tables(t) + "\n" + text[b:], encoding="utf-8")
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows, errors = load()
    errors += validate(rows)
    if "--check" not in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        clean = [{k: v for k, v in r.items() if k != "_file"} for r in rows]
        header = "# Generated by tools/ledger_summary.py from docs/product/ledger/*.yaml. Do not edit by hand.\n" \
                 "# Minutes are planning estimates, never facts.\n"
        OUT.write_text(header + yaml.safe_dump(clean, sort_keys=False, allow_unicode=True, width=200), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    t = totals(rows)
    t["pending"] = pending_specs()
    if "--check" not in argv:
        refresh_moat(t)
    print(report(t))
    print(f"\nspecs with no ledger file yet: {', '.join(t['pending']) or 'none'}")
    if errors:
        print(f"\nvalidation errors ({len(errors)}):")
        print("\n".join(f"  {e}" for e in errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
