"""Railway 12 Oct: a role guard starts with U+0000, which Postgres jsonb refuses; the store swaps it out and back."""
from sh_platform.state import _NUL, _NUL_MARK, _swap


def test_nul_round_trips_and_never_reaches_postgres():
    d = {"restricted_to": [chr(0) + "sponsor", "mei"], "k" + chr(0): [{"x": "a" + chr(0) + "b"}], "n": 3, "none": None}
    out = _swap(d, _NUL, _NUL_MARK)
    assert chr(0) not in str(out)
    assert _swap(out, _NUL_MARK, _NUL) == d
