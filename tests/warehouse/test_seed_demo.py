import csv
import sys
from pathlib import Path

import yaml

from sh_platform import warehouse as wh
from sh_platform.plane import PlaneStore

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.seed_demo_warehouse import DEMO_DIR, seed_demo_warehouse  # noqa: E402

DIMS = {"k05": "vehicle", "k15": "manager", "k16": "manager"}


def _tree_ids() -> set[str]:
    return {k["id"] for k in yaml.safe_load((ROOT / "packs/family_office/1/kpi_tree.yaml").read_text("utf-8"))["kpis"]}


def test_csv_set_covers_pack_measures_with_right_columns():
    files = sorted(DEMO_DIR.glob("gold.*.csv"))
    assert len(files) == 12
    for f in files:
        code = f.stem.split(".")[1]
        assert code.upper() in _tree_ids()
        rows = list(csv.DictReader(f.open(encoding="utf-8")))
        dim = DIMS.get(code)
        assert list(rows[0]) == ["period", *([dim] if dim else []), "value"]
        assert {r["period"] for r in rows} == {f"2026-{m:02d}" for m in range(1, 10)}
    assert {c for c in DIMS} <= {f.stem.split(".")[1] for f in files}


def test_seed_creates_gold_tables_with_counts(tmp_path):
    plane = PlaneStore(tmp_path).create("alpha")
    counts = seed_demo_warehouse(tmp_path, "alpha")
    assert counts["gold.k01"] == 9 and counts["gold.k05"] == 36 and counts["gold.k15"] == 27
    assert wh.counts_only(plane, "gold.k05") == {"rows": 36, "columns": 3}
    con = wh.open_readonly(plane)
    try:
        assert con.execute("select count(*) from gold.k02").fetchone()[0] == 9
    finally:
        con.close()


def test_seed_twice_does_not_duplicate(tmp_path):
    PlaneStore(tmp_path).create("alpha")
    assert seed_demo_warehouse(tmp_path, "alpha") == seed_demo_warehouse(tmp_path, "alpha")
