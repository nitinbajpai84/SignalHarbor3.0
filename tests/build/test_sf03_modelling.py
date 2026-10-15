"""SF03: Span's modelling pack, pick, and company decision memory. Synthetic data, a temporary plane."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform import memory
from sh_platform.build.agents import modelling
from sh_platform.memory import api
from sh_platform.plane import PlaneStore
from sh_platform.profile import store
from tests.test_no_hardcoded_industry import find_hardcoded

P = {"mark": "stated", "by": "Mei Tan", "from": "Access list"}


@pytest.fixture
def plane(tmp_path):
    pl = PlaneStore(tmp_path).create("family-a")
    store.record(pl, "governance.restricted_areas.hr.area", "HR", P)
    store.record(pl, "people.dan-data.name", "Dan Data", P)
    return pl


def test_pack_loads_with_required_keys_and_no_industry_words():
    pack = modelling.load_pack()
    ids = {e["id"] for e in pack}
    assert {"kimball", "data_vault", "inmon", "medallion", "obt", "transaction_fact", "periodic_snapshot",
            "accumulating_snapshot", "keys_surrogate", "keys_natural", "keys_hash"} | {f"scd{i}" for i in range(7)} <= ids
    assert all(all(k in e for k in modelling.REQUIRED) for e in pack)
    assert find_hardcoded(modelling.PACK.parent) == []


def test_pick_type_2_on_change_and_one_big_table_for_one_measure_one_consumer():
    got = modelling.pick("How should the dimension keep history?", {"keys_changed_last_n_loads": 3, "value_changes": True})
    assert got[0]["id"] == "scd2" and len(got) <= 3 and "scd1" not in [p["id"] for p in got]
    facts = [{"label": "measures", "value": 1, "group_size": 5}, {"label": "consumers", "value": 1, "group_size": 5}]
    assert modelling.pick("", facts)[0]["id"] == "obt"
    assert modelling.pick("", {}) == []
    assert len(modelling.pick("dimension history keys fact grain table snapshot", {"measures": 3})) == 3


def test_decision_written_depersonalised_figures_dropped(plane):
    line = modelling.decision_line(False, "type 2 history", "the owner dimension", "Dan Data said 214 changes is too few")
    assert modelling.remember_decision(plane, line)
    [d] = modelling.decisions(plane, "owner dimension")
    assert "Dan Data" not in d["text"] and "214" not in d["text"] and "type 2" in d["text"] and "a colleague" in d["text"]
    assert modelling.decisions(plane, "unrelated subject") == []
    assert not modelling.remember_decision(plane, "Chose type 1 for the HR dimension because it is simpler")  # restricted area


def test_tombstoned_decision_is_not_written_again(plane):
    text = "Chose type 2 history for the owner dimension because past reports must not move"
    assert modelling.remember_decision(plane, text)
    doc = memory.load(plane, "span")
    doc["entries"], doc["deleted"] = [], [{"hash": api.tomb_hash(text), "at": "2026-10-07"}]  # a company admin deleted it
    memory.save(plane, "span", None, doc)
    assert not modelling.remember_decision(plane, text)
    assert memory.load(plane, "span")["entries"] == []


def test_memory_routes_serve_span(tmp_path):
    PlaneStore(tmp_path).create("family-a")
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = SimpleNamespace(get=lambda i: None, in_company=lambda c: [])

    @app.middleware("http")
    async def auth(request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = "family-a", "a-x", ["company_admin"]
        return await call_next(request)

    app.include_router(api.router)
    c = TestClient(app)
    assert c.get("/api/memory/me/span").json()["entries"] == []
    assert c.get("/api/company/memory/span").json()["entries"] == []
    assert c.get("/api/company/memory/flow").status_code == 200
    assert c.get("/api/company/memory/nobody").status_code == 404
