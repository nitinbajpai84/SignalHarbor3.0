"""E0b1: Data agent skill. Tests loading and key rules."""

import pytest
from sh_platform.v1.skill_loader import load_skill, LIMIT


def test_data_skill_loads():
    """Load through skill_loader and verify it exists."""
    skill = load_skill("data")
    assert skill is not None
    assert len(skill) > 0


def test_data_skill_under_size_cap():
    """Skill text must be under 6000 characters."""
    skill = load_skill("data")
    assert len(skill) <= LIMIT, f"Skill is {len(skill)} chars, limit is {LIMIT}"


def test_v2_rules_present_in_skill():
    """Verify key v2 rules are explicitly stated in the skill text."""
    skill = load_skill("data")

    # The v2 rules from V2-BUILD.md E0b
    rules = [
        "three times",  # effective, received, recorded
        "Never overwrite",  # corrections supersede
        "Estimates apart",  # kept apart from official NAV
        "approval",  # alias approval needed
        "Control totals",  # load only when totals match
        "head of data",  # model change proposal
    ]

    for rule in rules:
        assert rule.lower() in skill.lower(), f"Rule '{rule}' not found in skill text"


def test_worked_mappings_present():
    """Verify three worked mapping examples are present."""
    skill = load_skill("data")

    tables = [
        "position_snapshots",
        "valuation_observations",
        "cash_movements",
    ]

    for table in tables:
        assert table in skill, f"Mapping example for '{table}' not found in skill text"


def test_skill_files_exist():
    """Verify all four required files exist."""
    from pathlib import Path

    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "data"
    assert skill_dir.exists(), "skills/data directory does not exist"

    required_files = ["playbook.md", "questions.md", "traps.md", "examples.md"]
    for fname in required_files:
        fpath = skill_dir / fname
        assert fpath.exists(), f"{fname} does not exist"
        assert fpath.stat().st_size > 0, f"{fname} is empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
