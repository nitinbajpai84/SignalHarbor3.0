"""Ledger summariser: merge, validation and totals on a temp ledger."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ledger_summary", ROOT / "tools" / "ledger_summary.py")
ls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ls)

ROW = """
- id: "{id}"
  spec: "{spec}"
  journey: initiative
  stage: think
  screen: "/centre/intent/new"
  input: "Does this need a build?"
  person: organiser
  mode: {mode}
  agent: North
  source: "the goal answer"
  minutes_without: {w}
  minutes_with: 1
  basis: "estimate"
  claim: "North proposes it"
"""


def test_merge_validate_and_totals(tmp_path: Path):
    (tmp_path / "10.yaml").write_text(ROW.format(id="10.a", spec="10", mode="confirm", w=10), encoding="utf-8")
    (tmp_path / "9.yaml").write_text(ROW.format(id="9.a", spec="9", mode="manual", w=3), encoding="utf-8")
    rows, errors = ls.load(tmp_path)
    assert errors == [] and [r["id"] for r in rows] == ["9.a", "10.a"]  # numeric file order
    assert ls.validate(rows) == []
    t = ls.totals(rows)
    assert t["by_mode"] == {"manual": 1, "confirm": 1}
    assert t["minutes"]["initiative"] == [13, 2, 2]
    assert t["top_savings"][0]["id"] == "10.a"
    assert "rows: 2" in ls.report(t)


def test_bad_rows_are_caught(tmp_path: Path):
    bad = ROW.format(id="1.a", spec="1", mode="typed", w=-2) + ROW.format(id="1.a", spec="1", mode="confirm", w=2).replace("  agent: North\n", "")
    (tmp_path / "1.yaml").write_text(bad, encoding="utf-8")
    rows, _ = ls.load(tmp_path)
    errs = "\n".join(ls.validate(rows))
    assert "mode 'typed'" in errs
    assert "minutes_without must be a non-negative" in errs
    assert "duplicate id" in errs
    assert "must name the agent" in errs


def test_moat_block_refreshes_and_keeps_prose(tmp_path: Path):
    (tmp_path / "10.yaml").write_text(ROW.format(id="10.a", spec="10", mode="confirm", w=10), encoding="utf-8")
    rows, _ = ls.load(tmp_path)
    moat = tmp_path / "MOAT.md"
    moat.write_text(f"# Moat\nprose above\n{ls.START}\nstale\n{ls.END}\nprose below\n", encoding="utf-8")
    assert ls.refresh_moat(ls.totals(rows), moat)
    text = moat.read_text(encoding="utf-8")
    assert "stale" not in text and "prose above" in text and "prose below" in text
    assert "| initiative | 1 | 10 | 1 | 9 |" in text  # minutes row: without, with, saved


def test_built_missing_is_a_gap_not_a_saving(tmp_path: Path):
    rows_txt = ROW.format(id="10.a", spec="10", mode="confirm", w=10) + \
        ROW.format(id="10.b", spec="10", mode="confirm", w=50) + "  built: missing\n"
    (tmp_path / "10.yaml").write_text(rows_txt, encoding="utf-8")
    rows, _ = ls.load(tmp_path)
    assert ls.validate(rows) == []
    t = ls.totals(rows)
    assert [r["id"] for r in t["missing"]] == ["10.b"]
    assert t["minutes"]["initiative"] == [10, 1, 1]  # missing row left out of savings
    assert t["built_differs"] == [] and [r["id"] for r in t["top_savings"]] == ["10.a"]
    assert "Missing in the build (1 rows" in ls.moat_tables(t)
    bad = [{**rows[0], "built": "absent"}]
    assert "built 'absent'" in "\n".join(ls.validate(bad))


def test_pending_specs_lists_specs_without_a_ledger_file(tmp_path: Path):
    specs, ledger = tmp_path / "specs", tmp_path / "ledger"
    specs.mkdir(); ledger.mkdir()
    for name in ("00-BRIEF.md", "00-INDEX.md", "28-data.md", "29-glossary.md", "57-radar.md"):
        (specs / name).write_text("x", encoding="utf-8")
    (ledger / "29.yaml").write_text("[]", encoding="utf-8")
    assert ls.pending_specs(specs, ledger) == ["28", "57"]
    t = {**ls.totals([]), "pending": ["28", "57"]}
    assert "Specs with no ledger file yet (2)" in ls.moat_tables(t) and "28, 57" in ls.moat_tables(t)
