"""E0d: copy the synthetic Evergreen Office workbooks into data/<company>/landing/inbox/ (never overwrites).
Usage: python tools/seed_e0_demo.py <company>"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tests" / "v1" / "fixtures" / "e0d" / "workbooks"


def seed(company: str, data_root: Path = ROOT / "data") -> tuple:
    dest = data_root / company / "landing" / "inbox"
    dest.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for f in sorted(SRC.glob("*.xlsx")):
        if (dest / f.name).exists():
            skipped += 1
        else:
            shutil.copy2(f, dest / f.name)
            copied += 1
    return copied, skipped


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: seed_e0_demo.py <company>")
    c, s = seed(sys.argv[1])
    print(f"{sys.argv[1]}: copied {c}, left {s} existing in data/{sys.argv[1]}/landing/inbox/")
