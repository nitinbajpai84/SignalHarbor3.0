"""I5: the catalogue from files and documents (main path with the model off, the model path with a stub, and one refusal)."""
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from sh_platform.build.agents.runtime import Runtime
from sh_platform.graph.models import Graph
from sh_platform.jsonfile import read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.v1 import catalogue_scan as C
from sh_platform.v1.i5_docs import BY_MODEL, BY_RULES
from sh_platform.v1.i5_graph import add_sow_nodes

FIX = Path(__file__).parent / "fixtures" / "i5"
IID = "a1b2c3d4e5f6"


@pytest.fixture
def plane(tmp_path, monkeypatch) -> CompanyPlane:
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    p = CompanyPlane("neera", tmp_path / "neera")
    (p.root / "landing" / "custody").mkdir(parents=True)
    (p.root / "documents").mkdir()
    shutil.copy(FIX / "custody_positions.csv", p.root / "landing" / "custody")
    for f in ("investment_policy.md", "reporting_policy.md"):
        shutil.copy(FIX / f, p.root / "documents")
    wb = Workbook()
    wb.active.title = "Fees"
    wb.active.append(["portfolio", "fee_rate"])
    wb.active.append(["Growth", 0.0075])
    cash = wb.create_sheet("Cash")
    cash.append(["as_at", "balance", "currency"])
    cash.append(["2025-09-30", 5000, "GBP"])
    wb.save(p.root / "landing" / "fees_and_cash.xlsx")
    write_json_atomic(p.path("intents", IID, "sow.json"), {
        "id": "sow1", "intent_id": IID, "title": "Know our returns", "state": "draft", "version": 1,
        "goal": {"line": "Monthly returns net of fees", "why": "", "readers": [], "decisions": [], "needed_by": ""},
        "process": {"steps": [], "handovers": []},
        "kpis": [{"code": "TWR", "name": "Time-weighted return", "definition": "", "formula": "", "unit": "%", "period": "month", "owner": "",
                  "source_ids": ["src-custody"], "status": "unclear", "pack_suggested": False}],
        "sources": [{"id": "src-custody", "name": "custody positions", "kind": "file", "holds": "", "sample_path": "landing/custody/custody_positions.csv",
                     "owner": "", "fields": [{"name": "quantity", "type": "", "example": "", "meaning": "Units held, as the person said"}]}],
        "catalogue": [], "governance": [], "unclear": [], "signature": None})
    write_json_atomic(p.path("intents", IID, "thread.json"), {"intent_id": IID, "needs_done": [], "state": "open", "turns": [
        {"id": "t1", "by": "person", "name": "Arjun Mehta", "text": "Here are our files", "at": "2026-10-07T10:00:00Z", "need": "inputs",
         "files": [{"name": "fees_and_cash.xlsx", "path": "landing/fees_and_cash.xlsx", "kind": "sample"},
                   {"name": "investment_policy.md", "path": "documents/investment_policy.md", "kind": "document"},
                   {"name": "reporting_policy.md", "path": "documents/reporting_policy.md", "kind": "document"},
                   {"name": "escape.csv", "path": "../other/escape.csv", "kind": "sample"}]}]})
    return p


def test_scan_writes_sources_catalogue_and_map(plane):
    out = C.scan(plane, IID)
    sow = read_json_strict(plane.path("intents", IID, "sow.json"), dict)
    assert out["sow"] == sow and out["skipped"] == [{"file": "../other/escape.csv", "why": "The file could not be found or read."}]
    src = {s["id"]: s for s in sow["sources"]}
    custody = src["src-custody"]  # the SOW's own source keeps its id and the person's words
    f = {x["name"]: x for x in custody["fields"]}
    assert f["quantity"]["meaning"] == "Units held, as the person said" and f["quantity"]["type"] == "integer"
    assert f["market_value"]["type"] == "decimal" and f["as_at"]["type"] == "date"
    assert f["client_email"]["example"] == ""  # no example kept for a personal-data column
    assert "read in investment_policy.md" in f["market_value"]["meaning"]
    assert custody["owner"] == "Leela Raman"
    docs = [s for s in sow["sources"] if s["kind"] == "document"]
    assert len(docs) == 2 and all(d["read"]["by"] == BY_RULES for d in docs)
    ips = next(d for d in docs if d["sample_path"].endswith("investment_policy.md"))
    twr = next(d for d in ips["read"]["definitions"] if d["term"] == "Time-weighted return")
    assert twr["file"] == "investment_policy.md" and "net of fees" in twr["quote"]
    assert {r["kind"] for r in ips["read"]["rules"]} == {"retention", "access", "approval"}
    assert any(s["name"] == "Custodian Portal" for s in ips["read"]["systems"])
    tables = {c["table"]: c for c in sow["catalogue"]}
    assert set(tables) == {"custody_positions", "fees_and_cash_fees", "fees_and_cash_cash", "twr"}  # twr: the gold table per linked KPI
    assert tables["custody_positions"]["feeds_kpis"] == ["TWR"] and tables["custody_positions"]["layer"] == "landing"
    assert [u["about"] for u in sow["unclear"]] == ["Time-weighted return"]  # two documents disagree: asked, never guessed
    assert plane.path("graph", "dirty").exists()
    assert C.scan(plane, IID)["unclear_added"] == 0  # a second scan adds nothing twice

    g = Graph()
    add_sow_nodes(g, plane, {})
    kinds = {(e["from"], e["to"], e["type"]) for e in g.edges.values()}
    assert (f"intent:{IID}", f"problem:sow-{IID}", "solves") in kinds
    assert (f"problem:sow-{IID}", "source:src-custody", "uses") in kinds
    assert ("source:src-custody", "measure:TWR", "feeds") in kinds
    assert ("source:src-custody", "table:custody_positions", "feeds") in kinds
    assert ("table:custody_positions", "measure:TWR", "feeds") in kinds
    assert (f"source:{ips['id']}", "measure:TWR", "defines") in kinds


def test_model_reads_documents_through_the_runtime(plane):
    class Stub:
        def complete(self, module_id, messages, tools=None):
            assert "BEGIN QUOTED DOCUMENT TEXT" in messages[1]["content"]
            return SimpleNamespace(text="definition | Cash drag | the cost of holding cash | cash held earns less\nsystem | General Ledger | from the ledger", tool_calls=[])
    rt = Runtime(Stub(), company_id="neera")
    sow = C.scan(plane, IID, rt=rt)["sow"]
    doc = next(s for s in sow["sources"] if s["kind"] == "document")
    assert doc["read"]["by"] == BY_MODEL and doc["read"]["definitions"][0]["term"] == "Cash drag"


def test_signed_sow_is_refused(plane):
    p = plane.path("intents", IID, "sow.json")
    write_json_atomic(p, {**read_json_strict(p, dict), "state": "signed"})
    with pytest.raises(C.Refused):
        C.scan(plane, IID)
    assert read_json_strict(p, dict)["catalogue"] == []
