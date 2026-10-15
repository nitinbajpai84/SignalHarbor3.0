"""Make one tester's private environment: a copy of the golden data root, ready for tools/serve_test.py.

    python tools/make_test_env.py t07          -> .sh-tmp/testenv/t07/data (copied from .sh-tmp/golden/data)
    python tools/make_test_env.py t07 --seed   -> .sh-tmp/testenv/t07/data seeded fresh with the ten-use-case universe (tools/seed_10uc.py)
    python tools/make_test_env.py --golden     -> rebuild the golden root by seeding the ten-use-case universe fresh

The golden root used to be copied from the live data/ folder, which does not hold the ten-use-case history; a golden made that way
fails every planted fact (cycle 1). It is now seeded fresh, in a side folder that replaces the old golden only when the seed finished.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / ".sh-tmp" / "golden" / "data"


def seed(dest: Path) -> Path:
    """Seed `dest` fresh (evergreen base, ten-use-case history, the v3 demo project) in a side folder, then swap it in."""
    tmp = dest.with_name(dest.name + ".seeding")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "seed_10uc.py"), "--data-root", str(tmp)], check=True, cwd=ROOT)
    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)
    return dest


def golden() -> Path:
    return seed(GOLDEN)


def env(name: str, fresh: bool = False) -> Path:
    dest = ROOT / ".sh-tmp" / "testenv" / name / "data"
    if fresh:
        return seed(dest)
    if not GOLDEN.exists():
        raise SystemExit("No golden data yet: run `python tools/make_test_env.py --golden` first.")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(GOLDEN, dest)
    return dest


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    print(golden() if sys.argv[1] == "--golden" else env(sys.argv[1], "--seed" in sys.argv[2:]))
