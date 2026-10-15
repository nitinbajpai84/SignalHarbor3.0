"""V3 G1: three agents (north, span, lumen). Skills load under the cap; the retired skill names and router keys resolve."""
import pytest

from sh_platform.v1 import router as R
from sh_platform.v1 import skill_loader as SL


@pytest.mark.parametrize("name", ["north", "span", "lumen"])
def test_skills_load_under_cap_whole(name):
    files = SL.skill_files(name)
    assert list(files)[:4] == list(SL.ORDER)  # the four core files first; extra skill files (north sop.md, lumen managers.md) follow
    full = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in files.values())
    assert 0 < len(full) <= SL.LIMIT, "nothing may be cut off by the cap"  # the examples file is last and must survive
    assert len(SL.load_skill(name)) == len(full)


def test_agents_are_four_and_old_skill_names_resolve():
    assert SL.agents() == ["lumen", "north", "span", "tally"]  # N1: Tally, the data analyst of the Action centre
    for old, new in SL.ALIASES.items():
        assert SL.load_skill(old) == SL.load_skill(new)
    assert "Span" in SL.skill_label("flow") and "Lumen" in SL.skill_label("consumer")


def test_merged_skills_keep_their_rules():
    span, lumen = SL.load_skill("span").lower(), SL.load_skill("lumen").lower()
    for s in ("never overwrite", "control totals", "head of data", "never write a digit", "manager-reported valuation difference", "quoted, untrusted"):
        assert s in span
    for s in ("vega-lite", "never write a figure", "one question per reply", "official, estimated, revised, stale, unverified"):
        assert s in lumen


def test_old_router_keys_resolve():
    for old, new in {"flow": "span", "data": "span", "intake": "span", "investigation": "span", "briefing": "lumen",
                     "consumer": "lumen", "nira": "lumen", "intent": "north", "north": "north", "span": "span", "lumen": "lumen"}.items():
        assert R.canonical_agent(old) == new
    assert R.canonical_agent("something_else") == "something_else"
    assert R.route(None, "flow", "mapping") is None
