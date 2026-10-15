"""Seed Signal Harbor 1.0: control plane and people, Neera (ten people, data loaded) with its sample files and documents, Fresh Harbour.

Usage: python tools/seed_v1.py [--data-root PATH]
Idempotent and never deletes or overwrites. Sample files come from tools/samples/neera/ (D1) into <data>/neera/landing/, documents from
tools/documents/neera/ (D2) into <data>/neera/documents/; a missing folder is skipped. Passwords go only to _control/seed_credentials.txt.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.settings import load_settings  # noqa: E402
from tools import seed, seed_fresh, seed_neera  # noqa: E402


def restore(src: Path, dst: Path) -> int:
    """Copy files under src into dst keeping the sub-folders; skip any already there. Returns files copied."""
    if not src.is_dir():
        return 0
    n = 0
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        t = dst / f.relative_to(src)
        if not t.exists():
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    return n


def seed_all(data_root: Path) -> dict:
    data_root = Path(data_root)
    out = {"control": seed.seed(data_root)}
    out["neera"] = seed_neera.seed(data_root, log=lambda *_: None)
    out["fresh"] = seed_fresh.seed(data_root)
    out["samples"] = restore(ROOT / "tools" / "samples" / "neera", data_root / "neera" / "landing")
    out["documents"] = restore(ROOT / "tools" / "documents" / "neera", data_root / "neera" / "documents")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    a = ap.parse_args(argv)
    raw = a.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed_all(root)
    print(f"Control plane: {r['control']['companies']} companies and {r['control']['accounts']} accounts created. "
          f"Neera: {r['neera']['accounts']['total']} accounts. Fresh Harbour: account "
          f"{'created' if r['fresh']['account_created'] else 'already there'}.")
    print(f"Sample files restored: {r['samples']}. Documents restored: {r['documents']}.")
    print(f"Sign-in details are in: {root / '_control' / 'seed_credentials.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
