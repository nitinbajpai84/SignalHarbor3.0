"""Accuracy over time: one row per live round, from the saved round results and the corrections log.

A round is a folder of one JSON per build (r1, r2 ...). Per round: how many answers passed the strict check, how many were wrong and
said so nowhere (the dangerous ones), and how many fields people corrected. Rounds come from SH3_LIVE_DIR (dev: D:/Temp/sh3-live) or,
in the product, the plane's own v3/live folder; none of them means an empty list. The corrections log is v3/corrections.jsonl on the plane.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# A wrong answer that says it is unsure, or that nothing was found, was flagged: a person is already looking.
FLAGGED = re.compile(r"can.?t (tell|find|confirm)|cannot (tell|find|confirm)|not (sure|available|found)|no (record|data) |needs? a person|please check|unable to", re.I)


def _strict():
    sys.path.insert(0, str(REPO / "docs" / "test" / "uc-live" / "uc6-scripts"))
    try:
        import v3_persona as VP
        spec = {b["id"]: b for r in VP.all_roles().values() for b in r["builds"]}  # today's check of each build, as tools/rescore_live.py reads it
        return lambda ans, run: VP.strict(ans, (spec.get(run.get("build")) or {}).get("check") or run.get("check") or {})
    except Exception:  # noqa: BLE001 - the checker lives with the test scripts; without it the round's own recorded pass is used
        return None
    finally:
        sys.path.pop(0)


def _round_key(p: Path) -> tuple:
    m = re.fullmatch(r"r(\d+)", p.name)
    return (0, int(m[1])) if m else (1, p.name)


def _corrections(plane) -> list[dict]:
    f = plane.path("v3", "corrections.jsonl") if plane is not None else None
    if not f or not Path(f).exists():
        return []
    out = []
    for line in Path(f).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def rounds(plane=None, live_dir: Path | str | None = None) -> list[dict]:
    root = live_dir or os.environ.get("SH3_LIVE_DIR") or (plane.path("v3", "live") if plane is not None else None)
    root = Path(root) if root else None
    fixes = _corrections(plane)
    strict = _strict()
    out = []
    for d in sorted((x for x in (root.iterdir() if root and root.is_dir() else []) if x.is_dir()), key=_round_key):
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))]
        runs = [r for r in runs if isinstance(r, dict) and "build" in r]
        if not runs:
            continue
        ok = wrong = 0
        for r in runs:
            ans = str(r.get("answer") or "")
            passed = bool(strict(ans, r)["pass"]) if strict and r.get("check") else bool((r.get("check") or {}).get("pass"))
            ok += passed
            wrong += (not passed) and bool(ans.strip()) and not FLAGGED.search(ans)
        out.append({"round": d.name, "total": len(runs), "right": ok, "right_pct": round(100 * ok / len(runs), 1), "slipped": wrong,
                    "corrected": sum(1 for c in fixes if str(c.get("round")) == d.name)})
    return out
