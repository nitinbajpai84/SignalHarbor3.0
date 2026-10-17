"""Measure the judge on the held-out cases (tests/v1/fixtures/judge_heldout.json): how often the two models agree, and how many agreed answers
are wrong against the answer keys. Live models; run on a COPY of an office (its mode picks the two models). The judge's cache there is cleared first.

    python tools/judge_eval.py <office root copy> [--out result.json]

A key of null means the right outcome is no agreed pick (the person is asked). Round 9 prep, before the evidence standards (the old questions and
standards, kept in the case file as old_standards): 11 of 19 agreed (58%), none of them wrong.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out")
    a = ap.parse_args()
    from sh_platform.plane import PlaneStore
    from sh_platform.v1 import v3_judge as J
    data = json.loads((ROOT / "tests" / "v1" / "fixtures" / "judge_heldout.json").read_text(encoding="utf-8"))
    plane = PlaneStore(Path(a.root)).plane_for("evergreen")
    shutil.rmtree(plane.path("v3", "judge"), ignore_errors=True)
    rows = []
    for c in data["cases"]:
        r = J.ask_kind(plane, c["kind"], c["subject"], c["options"], c["evidence"], thread="eval", person=False, describe=c.get("describe"))
        got = r["answer"] if r["agreed"] else None
        rows.append({"id": c["id"], "kind": c["kind"], "key": c["key"], "agreed": r["agreed"], "answer": got, "wrong": r["agreed"] and got != c["key"],
                     "opinions": [{k: o.get(k) for k in ("model", "answer", "why")} for o in r.get("opinions") or []]})
        print(f"{'AGREE' if r['agreed'] else 'split'} {'WRONG' if rows[-1]['wrong'] else 'ok   '} {c['id'][:60]:60} -> {got!r} key {c['key']!r}", flush=True)
    n, ag = len(rows), sum(r["agreed"] for r in rows)
    summary = {"cases": n, "agreed": ag, "agreement_rate": round(ag / n, 3) if n else 0, "agreed_wrong": sum(r["wrong"] for r in rows),
               "right_outcome": sum((r["answer"] == r["key"]) for r in rows),
               "by_kind": {k: {"cases": sum(r["kind"] == k for r in rows), "agreed": sum(r["agreed"] for r in rows if r["kind"] == k),
                               "wrong": sum(r["wrong"] for r in rows if r["kind"] == k)} for k in dict.fromkeys(r["kind"] for r in rows)},
               "spent_usd": J.spent(plane, "eval")}
    print(json.dumps(summary, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
