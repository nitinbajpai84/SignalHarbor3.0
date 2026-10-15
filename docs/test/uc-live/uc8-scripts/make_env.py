"""UC8 run 2: a clean test environment (Option A, clean company).

Seeds ONLY the Evergreen company, its people/accounts, master data and the core data model:
  1. tools/seed_evergreen.seed  -> company, 7 accounts, entities, portfolios, source systems, fund instruments, signed base rules,
                                   the base Sept report and 8 Oct cash rows (base company facts, no trades)
  2. tools/seed_10uc._static    -> securities (Meridian, Northwind, Bay Street, Coastal Rail, Harborview, the bond), the two FX forward
                                   instruments, their administrator/ticker identifiers, extra signed rules, the benchmark definition
Skipped on purpose: seed_10uc._history/_live/_trades/_checks/_library (the ten-use-case history, cases and results), seed_v3_demo (the demo
project and dashboard) and seed_demo_ready (demo runs, gold tables, Action items). No transactions are written.

Usage: python docs/test/uc-live/uc8-scripts/make_env.py <data_root>   (refuses a root that already has a warehouse)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from sh_platform.plane import PlaneStore  # noqa: E402
from tools import seed_10uc as U  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

root = Path(sys.argv[1]).resolve()
assert "testenv" in root.parts and root != ROOT / "data", "use a .sh-tmp/testenv/... data root"
assert not (root / "evergreen").exists() or "--again" in sys.argv, f"{root} already holds a company: delete it first"
print("evergreen:", EG.seed(root))
plane = PlaneStore(root).plane_for(EG.COMPANY).ensure()
ids, _ = EG.accounts(root)
print("master data:", U._static(plane, ids))
from sh_platform.v1 import wh  # noqa: E402
with wh.connect(plane, read_only=True) as con:
    for t in ("legal_entities", "portfolios", "source_systems", "instruments", "instrument_identifiers", "transactions", "business_rules"):
        print(f"  {t}: {con.execute(f'select count(*) from {t}').fetchone()[0]}")
print("credentials:", root / "_control" / "seed_credentials.txt")
