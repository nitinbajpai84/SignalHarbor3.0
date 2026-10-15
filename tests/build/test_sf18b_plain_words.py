"""SF18b: the rule-based texts Span and Flow write carry no data-modelling jargon."""
import json
import re

from sh_platform.build.agents import flow as F, span_suggest as S
from sh_platform.build.agents.runtime import Runtime
from tests.build.test_sf10_span_suggest import ADMIN, _plane as _span_plane, no_owner  # noqa: F401
from tests.build.test_sf12_flow import _run, plane  # noqa: F401  (fixture)

JARGON = re.compile(r"type [123]\b|\bscd\b|slowly changing|bronze|silver|\bgold\b|conformed|\bmarts?\b", re.I)


def _texts(p):
    a = p["args"] if "args" in p else p
    return [a.get(k, "") for k in ("title", "what", "why")] + [x["option"] + " " + x["why_not"] for x in a.get("alternatives", [])]


def test_span_fallback_findings_use_business_words(tmp_path, no_owner):
    out = S.review(_span_plane(tmp_path), Runtime(None, company_id="acme", company_name="Acme", viewer=ADMIN))
    assert out["fallback"] and out["proposals"]
    for p in out["proposals"]:
        for t in _texts(p):
            assert not JARGON.search(t), t


def test_conformed_finding_uses_business_words():
    g = {"model": {"model": {"facts": {"items": [{"name": "f", "grain": "one row per fund", "measures": ["A", "B"]}]}},
                   "lineage": {"items": [{"measure": m, "source": "Fund register", "mart": f"gold.{m.lower()}.x"} for m in ("A", "B")]}}}
    out = S._conformed(g)
    assert out
    for f in out:
        for t in _texts(f):
            assert not JARGON.search(t), t


def test_flow_run_lines_use_business_words(plane):
    run = _run(plane)
    lines, _, _ = F.run_lines(plane, {**run, "marts_ready": True}, set())
    lines += F.run_lines(plane, {**run, "marts_ready": False}, set())[0]
    assert lines
    for t in lines:
        assert not JARGON.search(t), t
