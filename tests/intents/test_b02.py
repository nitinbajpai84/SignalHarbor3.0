"""B02: the types catalogue matches spec 02, and North's proposal classifies a sentence."""
import re
from pathlib import Path

import pytest

from sh_platform.intents.types import classify_text, load_catalogue

SPEC = Path(__file__).resolve().parents[2] / "docs" / "specs" / "intent-centre" / "02-intent-types-catalogue.md"
DAYS = {"initiative": 10, "brainstorm": 3, "pulse": 5, "problem": 5, "decision": 2}
QUESTIONS = {"initiative": 6, "brainstorm": 5, "pulse": 4, "problem": 5, "decision": 5}


def test_yaml_equals_spec_block():
    import yaml
    block = re.search(r"```yaml\n(.*?)```", SPEC.read_text(encoding="utf-8"), re.S).group(1)
    assert load_catalogue() == yaml.safe_load(block)


def test_five_types_stages_and_questions():
    types = load_catalogue()["types"]
    assert list(types) == list(DAYS)
    for key, t in types.items():
        assert t["time_box_days"] == DAYS[key]
        assert sum(s["default_days"] for s in t["stages"]) == t["time_box_days"]
        assert len(t["start_questions"]) == QUESTIONS[key]
        assert "gap" not in " ".join(s["key"] for s in t["stages"])
        assert t["outcome"]["kind"] == key and t["open_button"] and t["chooser_line"]
    assert types["pulse"]["title"] == "Weekly check-in"


@pytest.mark.parametrize("text,kind", [
    ("Let us brainstorm ideas for the investor day", "brainstorm"),
    ("The capital call report keeps failing every Monday", "problem"),
    ("Which custodian should we choose, we must decide by Friday", "decision"),
    ("A weekly check-in for the treasury team", "pulse"),
    ("Launch a project to improve performance reporting", "initiative"),
])
def test_north_proposes_a_type(text, kind):
    p = classify_text(text)
    assert p["type"] == kind and p["confidence"] in ("Likely", "Possible") and p["title"]


def test_north_unsure_returns_no_type():
    assert classify_text("hello there")["type"] is None
