"""Regressions of test cycle 2 (passed in cycle 1, failed in cycle 2). Synthetic data only.

1. hr_admin: a process ask went down the data path, because North's gap-fill drafts (accepted before Decision 1 since the sign-off fix) put
   formula figures in the brief that the model had not marked as suggestions.
2. head_of_data: a ready table with a row per portfolio and a NULL figure in each counted as "has rows", so the figure was never redesigned on the
   loaded positions and the answer fell to Lumen.
3. cio, fund_accountant: an .eml sent as message/rfc822 arrived at intake as an empty file ("That file is empty.").
"""
import hashlib
import json
from contextlib import contextmanager
from types import SimpleNamespace

import duckdb
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.v1 import l2_proposals as L2
from sh_platform.v1 import v3_figures as F
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_process as P
from sh_platform.v1.e0c_routes import _multipart

EML = (b"From: Example Manager <ir@example.test>\nTo: Ops <ops@example.test>\nSubject: Revision notice\nContent-Type: text/plain; charset=\"utf-8\"\n"
       b"MIME-Version: 1.0\n\nThe amended statement replaces the estimate.\n  Amended: USD 10,180,000\n")


# ---- 3. an email file keeps its bytes through the form upload --------------------------------------------------------------------

def test_an_eml_sent_as_message_rfc822_keeps_its_exact_bytes():
    app = FastAPI()

    @app.post("/up")
    async def up(request: Request):
        form = await _multipart(request)
        return {"name": form["filename"], "sha": hashlib.sha256(form["data"]).hexdigest(), "source_code": form.get("source_code"), "n": len(form["files"])}

    c = TestClient(app)
    for ctype in ("message/rfc822", "application/octet-stream", "text/csv"):
        got = c.post("/up", files={"file": ("04_revision_notice.eml", EML, ctype)}, data={"source_code": "fund_a"}).json()
        assert got == {"name": "04_revision_notice.eml", "sha": hashlib.sha256(EML).hexdigest(), "source_code": "fund_a", "n": 1}, ctype
    binary = bytes(range(256)) * 4 + b"\r\n--not-the-boundary\r\n"  # a body with CRLFs and dashes of its own is cut only at the real boundary
    got = c.post("/up", files={"file": ("book.xlsx", binary)}).json()
    assert got["sha"] == hashlib.sha256(binary).hexdigest()


# ---- 1. a process ask stays process-only when the figures are North's own fill -----------------------------------------------

ASK = "I want the steps written down properly: who does what, in which system, and a procedure document I can hand a new joiner."
FILLED = {"name": "Net worth", "formula": "Sum of asset values - sum of liabilities", "pack_suggested": False, "status": "defined"}


def _office(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("acme")
    plane.path("v3").mkdir(parents=True, exist_ok=True)
    plane.path("v3", "files.json").write_text(json.dumps([{"name": "month_end_process_narrative.md", "status": "recognised", "thread": "t-1", "source": ""},
                                                          {"name": "handover_email.txt", "status": "waiting", "thread": None, "source": ""}]))
    return plane


def _propose(plane, text, kpis):
    L2.propose(plane, "ini-1", "sow", None, [{"op": "add", "path": f"kpis/{k['name']}", "after": k["name"]} for k in kpis],
               payload={"sow_patch": {"kpis": kpis}, "process_steps": None, "text": text, "who": "Priya Nair"})


def test_figures_north_filled_with_the_usual_practice_do_not_make_a_process_ask_a_data_build(tmp_path):
    plane = _office(tmp_path)
    sow = {"intent_id": "ini-1", "title": "Month-end investment report", "goal": {"line": ASK}, "kpis": [FILLED]}
    _propose(plane, H.FILL + "The figures, and how you work each one out today", [FILLED])
    assert P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, sow)
    _propose(plane, "We also report net worth each month as assets less liabilities.", [FILLED])  # the person's own words name it: it counts
    assert not P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, sow)


def test_a_figure_with_no_proposal_behind_it_still_counts(tmp_path):
    plane = _office(tmp_path)
    assert not P.is_process(plane, {"id": "t-1", "iid": "ini-1"}, {"intent_id": "ini-1", "title": "x", "goal": {"line": ASK}, "kpis": [FILLED]})


# ---- 2. a ready table whose figure column is all NULL is not a filled table -------------------------------------------------------

def _copy_with(tmp_path, value):
    (tmp_path / "warehouse").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(tmp_path / "warehouse" / "sandbox.duckdb"))
    con.execute("create table gold_kpis (portfolio_id varchar, net_worth decimal(38, 8))")
    con.execute("insert into gold_kpis values ('p1', ?), ('p2', ?)", [value, value])
    con.close()
    return SimpleNamespace(path=lambda *p: tmp_path.joinpath(*p))


KPI = {"name": "Net worth by portfolio"}
GOLD = [{"name": "gold_kpis", "columns": [{"name": "portfolio_id", "type": "VARCHAR"}, {"name": "net_worth", "type": "DECIMAL(38,8)"}]}]


def test_rows_with_no_value_for_the_figure_are_not_a_filled_ready_table(tmp_path):
    assert not F.valued(_copy_with(tmp_path / "a", None), KPI, GOLD)
    assert F.valued(_copy_with(tmp_path / "b", 41200000), KPI, GOLD)


def test_after_the_load_a_figure_with_only_null_values_gets_a_ready_table_designed(tmp_path, monkeypatch):
    plane = _copy_with(tmp_path, None)
    asked = []
    monkeypatch.setattr(F, "kpis_of", lambda plane, iid: [KPI])
    monkeypatch.setattr(F, "table_rows", lambda plane, copy=False: {"position_snapshots": 344, **({"gold_kpis": 2} if copy else {})})  # the table has rows
    monkeypatch.setattr(F, "fact_names", lambda: {"position_snapshots"})
    monkeypatch.setattr(F, "design", lambda x, todo, filled: (asked.extend(k["name"] for k in todo), ([], {}))[1])

    @contextmanager
    def record(*a, **k):
        yield {}
    from sh_platform.v1 import v3_skills
    monkeypatch.setattr(v3_skills, "record", record)
    x = SimpleNamespace(plane=plane, th={"id": "t-1", "iid": "ini-1", "pid": "prj-1"},
                        api=lambda who, m, path, body=None, soft=False: {"pack": {"target": {"gold": GOLD}, "state": "approved"}})
    F.cover(x, "loaded")
    assert asked == ["Net worth by portfolio"]
