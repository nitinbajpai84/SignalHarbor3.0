"""MEM-2: the memory routes. Synthetic data; the files are written by path in the shape of docs/plan/SHAPES.md 9, not through the store."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.memory import api, summarise
from sh_platform.plane import PlaneStore
from sh_platform.profile import record

ACCOUNTS = {"a-mei": {"display_name": "Mei Tan"}, "a-wei": {"display_name": "Wei Chen"}, "a-lone": {"display_name": "Lone"}}
LENS = {"mark": "stated", "by": "Lens", "from": "A list"}


class Accounts:
    def get(self, i): return ACCOUNTS.get(i)
    def in_company(self, c): return [{"display_name": v["display_name"]} for v in ACCOUNTS.values()]


def entry(i, text): return {"id": i, "kind": "fact", "text": text, "from": [{"conversation": "c1", "at": "2026-10-01"}], "updated_at": "2026-10-01", "by": "agent"}


@pytest.fixture
def world(tmp_path):
    planes = PlaneStore(tmp_path)
    plane = planes.create("lakeside")
    for pid, acc in (("p-mei", "a-mei"), ("p-wei", "a-wei")):
        record(plane, f"people.{pid}.account_id", acc, {**LENS, "by": "Mei Tan", "at": "2026-10-01T09:00"})
    for pid, text in (("p-mei", "Mei prefers weekly reports"), ("p-wei", "Wei owns the capital calls")):
        f = plane.path("context", "memory", "north", "people", f"{pid}.json")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"entries": [entry("e-" + pid, text)], "budget": 4000}), encoding="utf-8")
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    who = {"account": "a-mei", "roles": ["participant"]}

    @app.middleware("http")
    async def auth(request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = "lakeside", who["account"], who["roles"]
        return await call_next(request)

    app.include_router(api.router)
    return TestClient(app), who, plane


def test_own_entries_only_and_another_persons_never_served(world):
    c, who, _ = world
    assert [e["text"] for e in c.get("/api/memory/me/north").json()["entries"]] == ["Mei prefers weekly reports"]
    who["account"] = "a-wei"
    assert [e["text"] for e in c.get("/api/memory/me/North").json()["entries"]] == ["Wei owns the capital calls"]
    who["account"] = "a-lone"  # no profile link: empty, and the person's own edit never reaches another file
    assert c.get("/api/memory/me/north").json()["entries"] == []
    assert c.put("/api/memory/me/north", json={"entries": [{"text": "x"}]}).status_code == 404


def test_person_edit_and_forget(world):
    c, _, plane = world
    r = c.put("/api/memory/me/north", json={"entries": [{"id": "e-p-mei", "kind": "preference", "text": "Mei prefers monthly reports"}]}).json()
    assert r["entries"][0]["by"] == "person" and r["entries"][0]["from"][0]["conversation"] == "c1"
    assert c.delete("/api/memory/me/north").json()["entries"] == []
    assert not plane.path("context", "memory", "north", "people", "p-mei.json").exists()
    assert plane.path("context", "memory", "north", "people", "p-wei.json").exists()


def test_company_memory_is_admin_only(world):
    c, who, _ = world
    assert c.get("/api/company/memory/north").status_code == 403
    assert c.put("/api/company/memory/north", json={"entries": []}).status_code == 403
    who["roles"] = ["company_admin"]
    assert c.get("/api/company/memory/north").json()["entries"] == []
    assert len(c.put("/api/company/memory/north", json={"entries": [{"text": "The fund list lives in one workbook"}]}).json()["entries"]) == 1


def test_summary_lines_are_read():
    assert summarise.parse("- fact: Uses one ledger\nnoise\nopen: Who signs off?") == [
        {"kind": "fact", "text": "Uses one ledger"}, {"kind": "open", "text": "Who signs off?"}]
