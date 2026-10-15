import pytest

from modules.m2_baseline.domain.provenance import prov, unknown


def test_unknown_never_carries_a_value_and_marks_are_checked():
    assert prov("x", "unknown", "Lens")["value"] is None and unknown()["mark"] == "unknown"
    assert prov("Daily by noon", "stated", "Arjun", "answer a1")["from"] == "answer a1"
    with pytest.raises(ValueError):
        prov("x", "sure", "Lens")
