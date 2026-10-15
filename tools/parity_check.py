"""Run the 10 use-case checkers (tools/verify_10uc/uc1..uc10.py) against a server in simple mode and one in production mode, and compare.

    python tools/parity_check.py --simple http://127.0.0.1:8650 --production http://127.0.0.1:8651 --creds PATH --out DIR

Both servers must be started by you on the same seed (production mode one with DATABASE_URL and REDIS_URL, after tools/migrate_to_postgres.py).
For each checker it records the exit code and the fact files it wrote (DIR/<mode>/ucN/<fact>.json), then lists every difference. Times and
ids that legitimately differ per run are ignored. Exit 0 only when all ten checkers pass in both modes and nothing differs.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UCS = [f"uc{i}" for i in range(1, 11)]
VOLATILE = {"at", "time", "ts", "started", "finished", "elapsed", "elapsed_ms", "duration", "generated", "generated_at", "run_id", "created", "updated", "ran_at", "cutoff"}
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?")  # a clock time inside a quoted response


def scrub(x):
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    if isinstance(x, str):
        return STAMP.sub("<time>", x)
    return x


def run_all(base: str, creds: str, out: Path, run=subprocess.run) -> dict:
    """{uc: {"exit": int, "facts": {file name: scrubbed json}}} for one server."""
    res = {}
    for uc in UCS:
        p = run([sys.executable, str(HERE / "verify_10uc" / f"{uc}.py"), "--base", base, "--creds", creds, "--out", str(out)],
                capture_output=True, text=True, timeout=1800)
        facts = {}
        for f in sorted((out / uc).glob("*.json")) if (out / uc).is_dir() else []:
            try:
                facts[f.name] = scrub(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                facts[f.name] = "unreadable"
        res[uc] = {"exit": p.returncode, "facts": facts}
    return res


def compare(simple: dict, prod: dict) -> list[str]:
    diffs = []
    for uc in UCS:
        a, b = simple.get(uc), prod.get(uc)
        if a is None or b is None:
            diffs.append(f"{uc}: missing in one mode")
            continue
        for mode, r in (("simple", a), ("production", b)):
            if r["exit"] != 0:
                diffs.append(f"{uc}: the checker failed in {mode} mode (exit {r['exit']})")
        for name in sorted(set(a["facts"]) | set(b["facts"])):
            if name not in a["facts"] or name not in b["facts"]:
                diffs.append(f"{uc}/{name}: written in only one mode")
            elif a["facts"][name] != b["facts"][name]:
                diffs.append(f"{uc}/{name}: the facts differ between modes")
    return diffs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--simple", required=True)
    ap.add_argument("--production", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    simple = run_all(a.simple, a.creds, out / "simple")
    prod = run_all(a.production, a.creds, out / "production")
    diffs = compare(simple, prod)
    print(f"{len(UCS)} checkers, {len(diffs)} differences")
    for d in diffs:
        print("  " + d)
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
