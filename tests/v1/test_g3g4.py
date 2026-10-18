"""G3 the benchmark sheet and G4 deviations: rows from the person's words and from a dropped report (values copied by the program), a row with
no figure blocks signing, the raiser signs, Flow compares each row at its own granularity, and a change of source needs the head of data's
"approved" before it is made, then stands as a signed amendment to the system design."""
import json
import shutil
import types
from datetime import date
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.settings import Settings
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import g3_sheet as G3
from sh_platform.v1 import g4_deviations as G4
from sh_platform.v1 import p1_project as P1
from sh_platform.v1 import p4_benchmarks as P4
from tests.v1.seeded import SEED

ROOT = Path(__file__).resolve().parents[2]
PW = "g3g4-test-only-password"
IID = "g3test"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path / "data"
    shutil.copytree(SEED, data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    for who in ("arjun.mehta", "leela.raman", "priya.nair"):
        app.state.account_store.set_password(f"{who}.neera@example.test", PW)
    co = data / "neera"
    (co / "intents" / IID).mkdir(parents=True, exist_ok=True)
    (co / "intents" / IID / "sow.json").write_text(json.dumps({"intent_id": IID, "state": "signed", "kpis": [
        {"code": "K01", "name": "Net worth", "owner": "Arjun Mehta"}, {"code": "K02", "name": "Cash drag"}],
        "catalogue": [{"table": "gold.g3_nw", "layer": "gold", "feeds_kpis": ["K01"]}]}))
    plane = types.SimpleNamespace(path=lambda *p: co.joinpath(*p), company_id="neera")
    pid = P1.create_project(plane, IID, "Net worth", "Arjun Mehta")["id"]
    P1.set_person(plane, pid, "sponsor", "Priya Nair")
    P1.set_person(plane, pid, "head_of_data", "Leela Raman")
    return app, co, plane, pid


def _client(app, who):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": f"{who}.neera@example.test", "password": PW}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def _doc(co, plane, name, text, **extra):
    """A company document in documents/ with its library row (the library index is what says who may read it)."""
    from sh_platform.jsonfile import write_json_atomic
    from sh_platform.v1 import c4_library as L
    (co / "documents").mkdir(exist_ok=True)
    (co / "documents" / name).write_text(text, encoding="utf-8")
    rows = L._index(plane)
    rows[:] = [r for r in rows if r.get("path") != f"documents/{name}"]
    rows.append({**L._item(name, "document", "", "Seeded", "", "x", len(text), "company", f"documents/{name}"), **extra})
    write_json_atomic(L._index_path(plane), rows)


class Conn:
    """A shared in-memory warehouse whose close does nothing, so one test can read it twice."""
    def __init__(self):
        self.con = duckdb.connect(":memory:")

    def execute(self, *a):
        return self.con.execute(*a)

    def close(self):
        pass


def test_sheet_from_words_blocks_signing_until_every_row_has_a_figure(world):
    app, co, plane, pid = world
    sow = json.loads((co / "intents" / IID / "sow.json").read_text())
    text = "Net worth by entity for September 2026:\nTan Family Trust 12,400,000\nLim Holdings 8,100,000"
    G3.from_talk(plane, IID, sow, [{"name": "Net worth", "benchmark": "given"}], text, "Arjun Mehta", False, date(2026, 10, 8))
    rows = G3.read(plane, IID)["rows"]
    assert [(r["dims"]["entity"], r["reported"]) for r in rows] == [("Tan Family Trust", 12400000.0), ("Lim Holdings", 8100000.0)]
    assert sow["kpis"][0]["benchmark"]["sheet"] and len(sow["kpis"][0]["benchmark"]["rows"]) == 2  # the old field points at the rows

    G3.from_talk(plane, IID, sow, [{"name": "Cash drag", "benchmark_by": ["account", "month"]}], "Cash drag by account by month", "Arjun Mehta",
                 False, date(2026, 10, 8))
    gap = next(r for r in G3.read(plane, IID)["rows"] if r["code"] == "K02")
    assert gap["reported"] is None and gap["status"] == "needs figure"

    c = _client(app, "arjun.mehta")
    r = c.post(f"/api/v1/build/{IID}/benchmarks/sheet/sign")
    assert r.status_code == 409 and "no reported figure" in r.json()["detail"]
    assert _client(app, "leela.raman").post(f"/api/v1/build/{IID}/benchmarks/sheet/sign").status_code == 409  # not the raiser
    assert c.post(f"/api/v1/build/{IID}/benchmarks/sheet/rows/{gap['id']}", json={"reported": "950"}).status_code == 200
    s = c.post(f"/api/v1/build/{IID}/benchmarks/sheet/sign")
    assert s.status_code == 200 and s.json()["sheet"]["state"] == "signed"
    assert next(a for a in P1.read(plane, pid)["artefacts"] if a["kind"] == "benchmarks")["signed_by"] == "Arjun Mehta"
    doc = P1.export(plane, pid, "benchmarks", "xlsx")
    assert doc[0][:2] == b"PK" and doc[2].endswith("benchmarks.xlsx")


def test_report_dropped_in_is_read_by_the_program(world):
    app, co, plane, pid = world
    _doc(co, plane, "sept_report.md", "# Family report\n\n| Entity | Month | Net worth |\n|---|---|---|\n"
                                                     "| Tan Family Trust | 2026-09 | 12,400,000 |\n| Lim Holdings | 2026-09 | 8,100,000 |\n")
    c = _client(app, "arjun.mehta")
    r = c.post(f"/api/v1/build/{IID}/benchmarks/sheet/read", json={"file": "sept_report.md"})
    assert r.status_code == 200, r.text
    rows = r.json()["sheet"]["rows"]
    assert [(x["dims"], x["reported"]) for x in rows] == [({"entity": "Tan Family Trust", "period": "2026-09"}, 12400000.0),
                                                           ({"entity": "Lim Holdings", "period": "2026-09"}, 8100000.0)]
    assert "sept_report.md, line" in rows[0]["source"] and rows[0]["source_doc"] == "documents/sept_report.md"
    assert c.post(f"/api/v1/build/{IID}/benchmarks/sheet/read", json={"file": "nope.md"}).status_code == 404


def test_deviation_needs_approval_then_stands_as_an_amendment(world, monkeypatch):
    app, co, plane, pid = world
    P1.set_person(plane, pid, "builder", "Leela Raman")  # G1: Internal is the team's alone
    P1.set_person(plane, pid, "head_of_data", "Priya Nair")  # Leela raises below and must not approve her own request
    G3.upsert(plane, IID, [{"code": "K01", "kpi": "Net worth", "dims": {"period": "2026-09", "entity": "Lim Holdings"}, "reported": 8100000.0,
                            "expected": 8100000.0, "tolerance": 81000.0, "source": "said by Arjun Mehta", "stated_by": "Arjun Mehta"}])
    wh = Conn()
    wh.execute("create schema gold")
    wh.execute("create table gold.g3_nw (as_of varchar, entity varchar, value double)")
    wh.execute("insert into gold.g3_nw values ('2026-09-30', 'Lim Holdings', 7000000)")
    monkeypatch.setattr("sh_platform.warehouse.open_readonly", lambda plane: wh)
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": [
        {"n": 1, "layer": "gold", "target_table": "gold.g3_nw", "target_field": "value", "source_id": "custodian", "source_table": "custodian",
         "source_field": "mv", "transformation": "sum", "rule": "", "test": "", "status": "mapped"}]}))

    rows = P4.verify(plane, IID)
    assert rows[0]["got"] == 7000000.0 and rows[0]["met"] is False and rows[0]["label"] == "Lim Holdings"
    ref = P4._ref(rows[0])
    assert ref.startswith("benchmark:K01:2026-09:br_")

    assert G4.classify({"rule": "re-read"}) == "own_fix"  # keeps the design: Flow just runs again
    c = _client(app, "leela.raman")
    own = c.post(f"/api/v1/build/{IID}/deviations", json={"summary": "re-read the file", "after": "the same", "why": "a retry",
                                                           "change": {"rule": "x"}, "mapping_row": 1})
    assert own.status_code == 409 and "runs the load again" in own.json()["detail"]
    body = {"summary": "take Net worth from the statements instead of the custodian file", "about": "Net worth", "before": "custodian file, field mv",
            "after": "statements, field closing_value", "why": "the custodian file misses the Lim Holdings trust", "effect": [ref],
            "effect_labels": ["Net worth (Lim Holdings)"], "change": {"source_id": "statements", "source_field": "closing_value"}, "mapping_row": 1}
    made = c.post(f"/api/v1/build/{IID}/deviations", json=body)
    assert made.status_code == 200, made.text
    dev = made.json()["deviation"]
    assert dev["kind"] == "source" and [a["name"] for a in dev["asks"]] == ["Priya Nair"] and dev["by"] == "Leela Raman"
    cm = next(x for x in P1.comments(plane, pid, "build_pack") if x["kind"] == "approval")
    assert cm["to"] == "Priya Nair" and cm["text"].startswith("Leela Raman asks to take Net worth from the statements")

    def mapping():
        return json.loads((co / "build" / "mapping" / f"{IID}.json").read_text())["rows"][0]
    assert mapping()["source_id"] == "custodian"  # nothing changes before the answer
    assert c.post(f"/api/v1/build/{IID}/deviations", json=body).status_code == 409  # not asked twice
    assert "waiting for approval" in P4.sign_block(plane, IID)

    assert c.post(f"/api/v1/build/{IID}/deviations/{dev['id']}/decide", json={"decision": "approved"}).status_code == 403  # B3: not the raiser's to approve
    assert _client(app, "arjun.mehta").post(f"/api/v1/build/{IID}/deviations/{dev['id']}/decide", json={"decision": "approved"}).status_code == 403
    with pytest.raises(P1.Refused):
        P1.answer(plane, pid, cm["id"], "Priya Nair", "ok")  # bare "ok" is not an approval
    with pytest.raises(P1.Refused):
        G4.decision("yes")
    assert mapping()["source_id"] == "custodian"

    ok = _client(app, "priya.nair").post(f"/api/v1/build/{IID}/deviations/{dev['id']}/decide", json={"decision": "approved", "reason": "agreed"})
    assert ok.status_code == 200, ok.text
    assert mapping()["source_id"] == "statements" and mapping()["source_field"] == "closing_value"
    done = G4.read(plane, IID)[0]
    assert done["status"] == "implemented" and done["amendment"]
    am = json.loads((co / "build" / "blueprint_conversation" / f"{IID}.json").read_text())["amendments"]
    assert am[0]["version"] == "A1" and am[0]["signed_by"] == "Priya Nair" and am[0]["after"] == "statements, field closing_value"
    assert "K01" in P4.sign_block(plane, IID)  # B2: approval proves nothing until a reload reads the figure (or the miss is answered and resolved)
    assert any("A1" in s["lines"][0]["text"] for s in P1.document(plane, pid, "design")["sections"] if s["heading"].startswith("5."))


def test_not_approved_keeps_the_miss_open_with_the_reason(world):
    app, co, plane, pid = world
    dev = G4.propose(plane, IID, summary="drop the Lim Holdings row", about="Net worth", before="row present", after="row dropped", why="no source",
                     effect=["benchmark:K01:2026-09"], drop_sheet_row="br_none", business_definition=True)
    assert [a["name"] for a in dev["asks"]] == ["Leela Raman", "Arjun Mehta"]  # a business definition also goes to the raiser
    P1.answer(plane, pid, dev["asks"][1]["cid"], "Arjun Mehta", "Not approved: that row is how I report")
    d = G4.read(plane, IID)[0]
    assert d["status"] == "declined" and d["reason"] == "that row is how I report"
    assert G4.declined(plane, IID)[0]["reason"] == "that row is how I report" 
    other = next(x for x in P1.comments(plane, pid, "build_pack") if x["to"] == "Leela Raman" and x["kind"] == "approval")
    assert other["state"] == "resolved"


def test_failed_implementation_stays_approved_not_made(world):
    app, co, plane, pid = world
    P1.set_person(plane, pid, "head_of_data", "Priya Nair")
    dev = G4.propose(plane, IID, summary="change the source", about="Net worth", before="a", after="b", why="w", effect=["benchmark:K01:2026-09"],
                     change={"source_field": "x"}, mapping_row=99, by="Leela Raman")  # no mapping file: the change cannot be made
    P1.answer(plane, pid, dev["asks"][0]["cid"], "Priya Nair", "Approved")
    d = G4.read(plane, IID)[0]
    assert d["status"] == "approved" and d["implement_error"]
    assert "approved, not yet made" in G4.pending_block(plane, IID)
    assert not (co / "build" / "blueprint_conversation" / f"{IID}.json").exists()  # N2: no amendment before the change is made
    G4.make_now(plane, IID, dev["id"], "Leela Raman")  # still cannot be made: the mapping is still missing
    assert G4.read(plane, IID)[0]["status"] == "approved"
    (co / "build" / "mapping").mkdir(parents=True, exist_ok=True)
    (co / "build" / "mapping" / f"{IID}.json").write_text(json.dumps({"intent_id": IID, "version": 1, "rows": [
        {"n": 99, "layer": "gold", "target_table": "gold.g3_nw", "target_field": "value", "source_id": "a", "source_table": "a",
         "source_field": "mv", "transformation": "sum", "rule": "", "test": "", "status": "mapped"}]}))
    G4.make_now(plane, IID, dev["id"], "Leela Raman")  # N2: "Make it now" re-runs it, then the amendment is signed
    d = G4.read(plane, IID)[0]
    assert d["status"] == "implemented" and d["amendment"] and G4.pending_block(plane, IID) is None
    assert len(json.loads((co / "build" / "blueprint_conversation" / f"{IID}.json").read_text())["amendments"]) == 1
    with pytest.raises(P1.Refused):
        G4.make_now(plane, IID, dev["id"], "Leela Raman")


def test_a_sheet_row_that_no_longer_exists_is_not_recorded_as_made(world):
    app, co, plane, pid = world
    P1.set_person(plane, pid, "head_of_data", "Priya Nair")
    dev = G4.propose(plane, IID, summary="drop a row", about="Net worth", before="a", after="b", why="w", effect=["benchmark:K01:2026-09"],
                     drop_sheet_row="br_gone", by="Leela Raman")
    P1.answer(plane, pid, dev["asks"][0]["cid"], "Priya Nair", "Approved")  # N6
    assert G4.read(plane, IID)[0]["status"] == "approved"


def test_no_head_of_data_is_refused_not_sent_to_the_raiser(world):
    app, co, plane, pid = world
    P1.set_person(plane, pid, "head_of_data", None)
    with pytest.raises(P1.Refused) as e:
        G4.propose(plane, IID, summary="s", about="a", before="b", after="c", why="w", effect=[], change={"source_field": "x"})
    assert e.value.status == 409 and "head of data" in e.value.message


def test_a_locked_document_is_not_read_into_the_sheet(world):
    app, co, plane, pid = world
    _doc(co, plane, "board.md", "Net worth: 12,400,000\n", sensitivity="restricted", uploaded_by_id="someone-else")
    c = _client(app, "leela.raman")
    r = c.post(f"/api/v1/build/{IID}/benchmarks/sheet/read", json={"file": "board.md"})
    assert r.status_code == 403 and "locked" in r.json()["detail"]["message"]
    assert c.get(f"/api/v1/build/{IID}/benchmarks/sheet/doc", params={"file": "documents/board.md"}).status_code == 403
    assert G3.read(plane, IID)["rows"] == []


def test_source_keeps_no_line_text_and_the_viewer_shows_the_line(world):
    app, co, plane, pid = world
    _doc(co, plane, "r.md", "# R\n\nNet worth: 12,400,000\n")
    c = _client(app, "arjun.mehta")
    row = c.post(f"/api/v1/build/{IID}/benchmarks/sheet/read", json={"file": "r.md"}).json()["sheet"]["rows"][0]
    assert row["source"] == "r.md, line 2" and "12,400,000" not in row["source"]
    doc = c.get(f"/api/v1/build/{IID}/benchmarks/sheet/doc", params={"file": row["source_doc"], "line": row["line"]}).json()
    assert doc["lines"][row["line"] - 1]["text"] == "Net worth: 12,400,000"


def test_a_sheet_with_nobody_to_sign_and_two_figures_on_a_line(world):
    app, co, plane, pid = world
    assert G3._figures("Tan Family Trust 12,400,000 and Lim Holdings 8,100,000") == ["Tan Family Trust 12,400,000 ", " Lim Holdings 8,100,000"]
    assert G3._figures("Net worth 12,400,000 expected 12,300,000") == ["Net worth 12,400,000 expected 12,300,000"]
    sow = json.loads((co / "intents" / IID / "sow.json").read_text())
    G3.from_talk(plane, IID, sow, [{"name": "Net worth", "benchmark": "given"}], "Net worth by entity for September 2026: Tan 12,400,000 and Lim 8,100,000",
                 "Arjun Mehta", False, date(2026, 10, 8))
    assert [r["reported"] for r in G3.read(plane, IID)["rows"]] == [12400000.0, 8100000.0]
    assert "Nobody is named" in G3.sign_block(plane, "g3nobody", "Leela Raman")  # an intent with no project: nobody can sign


def test_participant_does_not_read_the_benchmark_artefact(world):
    from sh_platform.profile.view import Viewer
    from sh_platform.v1 import g1_access as G1
    app, co, plane, pid = world
    pat = Viewer("Pat Lee", frozenset({"participant"}), False, "acc-pat")  # G1: an Internal project shows a participant only its lock
    assert G1.may_see_project(plane, pat, pid) == "preview"
    with pytest.raises(P1.Refused):
        G1.require(plane, pat, pid)
    assert G1.may_see_project(plane, Viewer("Dev Other", frozenset({"analyst"}), False, "acc-d"), pid) == "preview"
    assert P1.document(plane, pid, "benchmarks")["kind"] == "benchmarks"
