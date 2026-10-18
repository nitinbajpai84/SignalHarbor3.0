"""Re-score a saved live round with the strict checker, offline (docs/test/uc-live/uc6-scripts/v3_persona.py: strict()).

    python tools/rescore_live.py D:/Temp/sh3-live/r7                 # the saved answers, against today's build checks
    python tools/rescore_live.py D:/Temp/sh3-live/r7 --replay        # also replay each answer on a copy of its office (D:/Temp/sh3-uc-env-<id>)
    python tools/rescore_live.py D:/Temp/sh3-live/r7 --replay --only uc-005-benefcheck uc-032-driftrep

The check of each build is read from today's builds (packs/family_office/1/builds and role_builds.yaml): expect, must_not, must_have_verdict.
A replay copies the office to a scratch folder, asks the build's question through the answer path without the model (v3_board_routes.fast), and
deletes the copy; a question the fast path leaves to the model keeps its saved text, passed through the same last pass (v3_consume.polish).
Synthetic data only; nothing in the saved round or the office is changed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "docs" / "test" / "uc-live" / "uc6-scripts")]

import v3_persona as VP  # noqa: E402


def builds() -> dict[str, dict]:
    return {b["id"]: b for r in VP.all_roles().values() for b in r["builds"]}


def saved(folder: Path) -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(folder.glob("*.json"))]


def replay(run: dict, env_root: Path, scratch: Path) -> tuple[str, str]:
    """(answer, how) for one saved run, asked again on a copy of its office: how is "fast", "model (saved, polished)" or "no office"."""
    from sh_platform.plane import PlaneStore
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import v3_board_routes as B, v3_consume as C, wh
    src = env_root / f"sh3-uc-env-{run['build']}"
    ask = (run.get("check") or {}).get("ask")
    if not src.is_dir() or not ask:
        return str(run.get("answer") or ""), "no office"
    tmp = Path(tempfile.mkdtemp(dir=scratch))
    try:
        shutil.copytree(src, tmp / "env", ignore=shutil.ignore_patterns("dropbox"))
        plane = PlaneStore(tmp / "env").plane_for("evergreen")
        wh.use(plane)
        acc = next(a for a in json.loads((tmp / "env" / "_control" / "accounts.json").read_text(encoding="utf-8")) if a["display_name"] == run["person"])
        viewer = Viewer(acc["display_name"], frozenset(acc["roles"]), False, acc["account_id"])
        th = B._live(plane, ask)
        got = B.fast(plane, viewer, ask, th and th.get("pid"))
        if got:
            return str(got.get("answer") or ""), "fast"
        return C.polish(ask, {"answer": run.get("answer") or ""})["answer"], "model (saved, polished)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--envs", type=Path, default=Path("D:/Temp"))
    ap.add_argument("--scratch", type=Path, default=Path(tempfile.gettempdir()))
    ap.add_argument("--out", type=Path, help="write every row as JSON here")
    a = ap.parse_args()
    spec = builds()
    rows = []
    for run in saved(a.folder):
        if a.only and run["build"] not in a.only:
            continue
        check = (spec.get(run["build"]) or {}).get("check") or run.get("check") or {}
        before = VP.strict(run.get("answer") or "", check) if run.get("check") else {"pass": False, "missing": ["<stopped: no answer>"], "banned": [], "verdict": False}
        row = {"build": run["build"], "ask": (run.get("check") or {}).get("ask"), "old_pass": bool((run.get("check") or {}).get("pass")), "strict": before}
        if a.replay:
            text, how = replay(run, a.envs, a.scratch) if run.get("check") else ("", "stopped")
            row |= {"replayed": text, "how": how, "after": VP.strict(text, check) if run.get("check") else before}
        rows.append(row)
        why = lambda s: "; ".join([*(f"missing {m}" for m in s["missing"]), *(f"says {b}" for b in s["banned"]), *([] if s["verdict"] else ["no verdict first"])])  # noqa: E731
        line = f"{run['build']:<26} old {'PASS' if row['old_pass'] else 'fail'} | strict {'PASS' if before['pass'] else 'fail'}"
        if a.replay:
            line += f" | after {'PASS' if row['after']['pass'] else 'fail'} ({row['how']})"
        last = row.get("after", before)
        print(line + ("" if last["pass"] else f"  <- {why(last)[:160]}"), flush=True)
    n = len(rows)
    print(f"\n{n} builds | old checker pass {sum(r['old_pass'] for r in rows)} | strict on saved answers pass {sum(r['strict']['pass'] for r in rows)}"
          + (f" | strict after replay pass {sum(r['after']['pass'] for r in rows)}" if a.replay else ""))
    if a.out:
        a.out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
