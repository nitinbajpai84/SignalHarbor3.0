"""The one range rule. Synthetic data only."""
from sh_platform.consume.range import breaks


def t(*vals: float) -> list[dict]:
    return [{"period": f"2026-{i + 1:02d}", "value": v} for i, v in enumerate(vals)]


def test_a_value_far_outside_its_history_breaks():
    r = breaks(t(100, 104, 98, 102, 99, 101, 103, 160))
    assert r["break"] is True and "spreads" in r["basis"]


def test_a_value_inside_its_history_does_not_break():
    assert breaks(t(100, 104, 98, 102, 99, 101, 103, 105))["break"] is False
    assert breaks(t(100, 104, 98, 102, 99, 103))["break"] is False  # only five earlier periods: no range yet


def test_a_tiny_spread_uses_the_share_of_the_mean():
    flat = (100.0,) * 6 + (100.001,)
    assert breaks(t(*flat, 110))["break"] is False  # 10 percent: inside the share
    r = breaks(t(*flat, 130))
    assert r["break"] is True and "tiny" in r["basis"]


def test_the_basis_says_the_same_as_the_verdict():
    assert breaks(t(100, 104, 98, 102, 99, 101, 103, 160))["basis"].startswith("more than")
    assert breaks(t(100, 104, 98, 102, 99, 101, 103, 105))["basis"].startswith("within")
