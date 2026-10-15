"""Load the illustrative demo gold tables into one company's warehouse (synthetic data only).

Usage: python tools/seed_demo_warehouse.py <company_id> [--data-root PATH]
Reads packs/family_office/1/demo_warehouse/gold.<code>.csv, creates gold.<code> in that company's
warehouse/company.duckdb and refreshes the read-only copy. Idempotent: each table is replaced, never appended.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from sh_platform.warehouse import open_company, refresh_readonly_copy  # noqa: E402

log = logging.getLogger(__name__)
DEMO_DIR = ROOT / "packs" / "family_office" / "1" / "demo_warehouse"


def seed_demo_warehouse(data_root: Path, company_id: str, demo_dir: Path = DEMO_DIR) -> dict[str, int]:
    """Rows loaded per gold table. Only this company's plane is opened."""
    plane = PlaneStore(data_root).plane_for(company_id)
    counts: dict[str, int] = {}
    con = open_company(plane)
    try:
        for f in sorted(demo_dir.glob("gold.*.csv")):
            table = f.stem  # gold.k01: a fixed file name pattern, never user input
            con.execute(f"create or replace table {table} as select * from read_csv(?, header = true)", [str(f)])
            counts[table] = con.execute(f"select count(*) from {table}").fetchone()[0]
    finally:
        con.close()
    refresh_readonly_copy(plane)
    log.info("demo gold tables for %s: %s", company_id, counts)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed illustrative demo gold tables (synthetic).")
    ap.add_argument("company_id")
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    args = ap.parse_args(argv)
    raw = args.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    try:
        counts = seed_demo_warehouse(root, args.company_id)
    except (LookupError, ValueError) as e:
        print(f"Demo warehouse not seeded: {e}")
        return 1
    print(f"Seeded {len(counts)} gold tables, {sum(counts.values())} rows, into {args.company_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
