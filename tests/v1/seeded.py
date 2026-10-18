"""The seeded demo data root the v1 tests copy from (Neera, Fresh Harbour and the control plane, from tools/seed_v1.py).

tests/v1/conftest.py seeds it once per run into a temp folder and names it in SH_TEST_SEED_ROOT, so the tests never depend on what the
repo's own data/ folder holds today (the live rounds reset it). Outside pytest it falls back to the repo's data/."""
import os
from pathlib import Path

SEED = Path(os.environ.get("SH_TEST_SEED_ROOT") or Path(__file__).resolve().parents[2] / "data")
