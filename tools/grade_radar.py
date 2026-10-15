"""Grade the opportunity radar (spec 57) against the answer key, on a temporary copy of a company plane. Graders only: the key is read
here to mark the result and never by the radar.

Usage: python tools/grade_radar.py [--company ardmore] [--key .sh-tmp/ic/data/answer_key.yaml]
Copies data/<company>, removes the radar's own records from the copy (opportunities, their hypotheses, the scan log), runs one scan, and
prints one line per truth with PASS or FAIL and why. Exit code 0 only when every truth passes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.intents import hypotheses as H  # noqa: E402
from sh_platform.intents import opportunities as O  # noqa: E402
from sh_platform.intents import radar  # noqa: E402
from sh_platform.packs import PackLoader  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402

SYMPTOM = {"T1": "K20", "T2": "K03", "T3": "K23", "T4": "K12", "T5": "K22", "T6": "K11"}


def fresh_copy(data_root: Path, company: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sh-grade-radar-"))
    shutil.copytree(data_root / company, tmp / company, ignore=shutil.ignore_patterns("*.tmp"))
    intents = tmp / company / "intents"
    shutil.rmtree(intents / "opportunities", ignore_errors=True)
    shutil.rmtree(intents / "radar", ignore_errors=True)
    for f in (intents / "hypotheses").glob("hyp-*.json"):
        if re.fullmatch(r"hyp-\d{4,}", f.stem):
            f.unlink()
    return tmp


def grade(plane, key: dict) -> list[tuple[str, bool, str]]:
    recs = O.all_records(plane)
    hyp = {r["id"]: H.latest(H.get(plane, (r.get("hypothesis_ref") or {}).get("id", ""))) or {} for r in recs}
    seeded = {h["id"].removeprefix("hyp-"): h["origin"]["ref"] for h in H.all_records(plane) if h["origin"].get("kind") == "initiative"}
    out = []
    for t, m in SYMPTOM.items():
        truth = key["truths"][t]
        hits = [r for r in recs if m in r["touches"]["measures"] and (r.get("pattern") or {}).get("kind") != "theme" and not str((r.get("pattern") or {}).get("key", "")).startswith("claim:")]
        if not hits:
            out.append((t, False, f"no record touches {m}"))
            continue
        r = hits[0]
        lens_ok = hyp[r["id"]].get("lens") == truth["lens"]
        want = truth.get("initiative") and seeded.get(truth["initiative"])
        if t == "T6":
            link_ok = (r.get("linked") or {}).get("kind") == "decision" and r["state"] != "proposed"
            note = f"linked to Decision {(r.get('linked') or {}).get('title')!r}"
        elif want:
            link_ok = (r.get("linked") or {}).get("id") == want and r["state"] != "proposed"
            note = f"linked to {(r.get('linked') or {}).get('title')!r}"
        else:
            link_ok = r["state"] == "proposed"
            note = f"state {r['state']}"
        out.append((t, lens_ok and link_ok and len(hits) == 1, f"{r['id']} lens {hyp[r['id']].get('lens')} (key {truth['lens']}), {note}, {len(hits)} record(s) on {m}"))
    ids = {v["key"]["id"] for v in key["truths"]["T7"]["voices"]}
    themes = [r for r in recs if (r.get("pattern") or {}).get("kind") == "theme"]
    cover = [(r, {i for i in ids if any(str((e.get("trace") or {}).get("ref", "")).endswith(i) for e in hyp[r["id"]].get("evidence") or [])}) for r in themes]
    best = max(cover, key=lambda x: len(x[1]), default=(None, set()))
    split = sum(1 for _, c in cover if len(c) >= 2)
    voices = (hyp[best[0]["id"]].get("theme") or {}).get("voices") if best[0] else None
    out.append(("T7", len(best[1]) >= 6 and split == 1 and voices is not None,
                f"best theme {best[0]['id'] if best[0] else None} holds {len(best[1])} of {len(ids)} key records, {voices} voices (key 5 people), "
                f"{split} theme(s) share them, uplift {H.missing_uplift(hyp[best[0]['id']]) if best[0] else None!r}"))
    rej = [r for r in recs if r["state"] == "rejected" and "K03" in r["touches"]["measures"]]
    why = (rej[0].get("rejected") or {}).get("why", "") if rej else ""
    out.append(("T8", bool(rej) and ("2026-08" in why or "late_statement_A2" in why),
                f"{rej[0]['id'] if rej else 'no rejected record on K03'}: {why}"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Grade the radar against the answer key on a temporary copy.")
    ap.add_argument("--company", default="ardmore")
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--key", default=str(ROOT / ".sh-tmp" / "ic" / "data" / "answer_key.yaml"))
    args = ap.parse_args(argv)
    tmp = fresh_copy(Path(args.data_root), args.company)
    try:
        plane = PlaneStore(tmp).plane_for(args.company)
        res = radar.scan(plane, PackLoader(ROOT / "packs").load("family_office"))
        recs = O.all_records(plane)
        print(f"scan: {len(res['made'])} records ({res['drafted']} drafted, {res['rejected']} set aside)")
        for r in recs:
            v = H.latest(H.get(plane, (r.get("hypothesis_ref") or {}).get("id", ""))) or {}
            print(f"  {r['id']} {r['state']:<12} {v.get('lens') or '-':<13} {v.get('confidence') or '-':<11} {r['title'][:90]}")
        rows = grade(plane, yaml.safe_load(Path(args.key).read_text(encoding="utf-8")))
        for t, ok, why in rows:
            print(f"{t} {'PASS' if ok else 'FAIL'} {why}")
        print(f"grade: {sum(ok for _, ok, _ in rows)} of {len(rows)}")
        return 0 if all(ok for _, ok, _ in rows) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
