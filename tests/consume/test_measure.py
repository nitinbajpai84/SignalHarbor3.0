"""One measure's own page: full trend, definition, pipeline; access; unknown code. Synthetic data only."""
import pytest
from fastapi import HTTPException

from sh_platform.consume import measure
from tests.consume.test_feeds import BID, MEI, WEI, cell, make, put


def seeded(tmp_path):
    plane = make(tmp_path)
    put(plane, f"intents/m2_baseline/{BID}/kpis.json", [{"id": "NAV", "name": "Net asset value", "definition": cell("Everything we own, less debts."),
                                                          "technical": {"calculation": cell("sum of holdings minus loans")}}])
    put(plane, "build/pipelines/custody.json", {"source": "custody", "expected": "D+2 09:00", "sla": "WD8", "owner": "Mei Tan", "marts": ["gold.nav"]})
    put(plane, "warehouse/runs.json", {"runs": [{"source": "custody", "status": "late", "id": "r1"}, {"source": "custody", "status": "ok", "id": "r2"}]})
    return plane


def test_full_trend_definition_and_pipeline(tmp_path):
    m = measure.build(seeded(tmp_path), MEI, None, "NAV")
    assert len(m["trend"]) == 10 and m["latest"]["value"] == 50.0 and m["change"]["absolute"] == 40.0
    assert m["range"]["outside"] is True and "earlier periods" in m["range"]["basis"]
    assert m["definition"]["business"].startswith("Everything") and m["definition"]["technical"] == [{"label": "Calculation", "text": "sum of holdings minus loans"}]
    assert m["pipeline"]["source"] == "custody" and m["pipeline"]["last_run"]["id"] == "r2" and m["links"]["register"] == "/centre/register"


def test_outsider_gets_no_values(tmp_path):
    m = measure.build(seeded(tmp_path), WEI, None, "NAV")
    assert m["restricted"] == "Restricted: ask Mei Tan" and m["owner"] == "Mei Tan"
    assert not {"trend", "latest", "change", "definition", "pipeline"} & m.keys()


def test_unknown_code_is_404(tmp_path, monkeypatch):
    plane = seeded(tmp_path)
    monkeypatch.setattr(measure, "_plane", lambda r: plane)
    monkeypatch.setattr(measure, "_viewer", lambda r: MEI)
    monkeypatch.setattr(measure.feeds, "_pack_names", lambda r: {})
    with pytest.raises(HTTPException) as e:
        measure.get_api_company_feed("NOPE", None)
    assert e.value.status_code == 404


def test_unit_is_read_from_the_definition():
    from sh_platform.consume.measure import _unit
    assert _unit("Fees", "Total logged person-hours") == "hours"
    assert _unit("Obligations", "Sum of open amt in SGD") == "SGD"
    assert _unit("Single-issuer concentration", "Exposure (SGD) divided by asset value") == "share of total (0 to 1)"
    assert _unit("Evidence coverage", "A / B") == "ratio (0 to 1)"
    assert _unit("Alpha", "Return minus return") is None
