"""E2d screen contract: the routes answer in the shape `ui/src/v1/e2/api.ts` reads. The JSON copied into the screen's vitest
(`ui/src/v1/e2/detail.real.json`) is this test's real response; run with SH_WRITE_FIXTURES=1 to rewrite it."""
import json
import os
import sys
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e2_intake as E
from sh_platform.v1 import e4_cases as C
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id
from tests.v1.e1_seed import seed

INST, PF = str(uuid.uuid4()), str(uuid.uuid4())
MEI = Viewer("Mei Tan", frozenset({"analyst"}), False, "acc-mei")
CIO = Viewer("Priya Nair", frozenset({"sponsor"}), False, "acc-priya")
FIXTURE = Path(__file__).resolve().parents[2] / "ui" / "src" / "v1" / "e2" / "detail.real.json"
HEAD = "Evergreen Growth I\nMonthly statement\nValuation date: 30 September 2026\nBase currency: USD\n"
EST = HEAD + "\fUnits outstanding: 98,431.2\nNet asset value (estimate): USD 10,000,000.00\nStatus: Estimate\n"
AMENDED = HEAD.replace("Monthly", "Amended") + "\fUnits outstanding: 98,431.2\nNet asset value: USD 10,180,000.00\nStatus: Final\n"


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    plane = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(plane)
    with wh.connect(plane) as con:
        con.execute("insert into organizations values (?,?,?)", [org, "Acme", wh.now()])
    seed(plane, instruments=[INST], portfolios=[PF])
    with wh.connect(plane) as con:
        con.execute("update instruments set canonical_name = 'Evergreen Growth I' where id = ?", [INST])
        src = E._source(con, org, "manager_email")
        con.execute("insert into instrument_identifiers values (?,?,?,?,'name','Evergreen Growth I',null,null,'approved',null,?,now())", [wh.new_id(), org, INST, src, wh.new_id()])
        con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, valuation_date, received_at, recorded_at, value_amount,"
                    " currency, valuation_type, approval_status) values (?,?,?,?,?,?,?,?,?,?,?)",
                    [wh.new_id(), org, INST, PF, "2026-09-30", datetime(2026, 10, 2, tzinfo=timezone.utc), wh.now(), 10000000, "USD", "manager_estimate", "confirmed"])

    def impact(p, vid):  # E3c stand-in: a superseding valuation opens a revision case
        with wh.connect(p, read_only=True) as con:
            sup = con.execute("select supersedes_valuation_id from valuation_observations where id = ?", [vid]).fetchone()[0]
        return C.open(p, {"exception_type": "revision", "title": "t", "instrument_id": INST}) if sup else None
    fake = types.SimpleNamespace(on_new_valuation=impact)
    monkeypatch.setitem(sys.modules, "sh_platform.v1.e3_impact", fake)
    monkeypatch.setattr("sh_platform.v1.e3_impact", fake, raising=False)
    monkeypatch.setattr("sh_platform.v1.doc_index._slow", lambda path: False)
    from sh_platform.v1 import e2a_routes as A, e2b_routes as B, e2c_routes as M
    app, who = FastAPI(), {"v": MEI}
    for mod in (A, B, M):
        app.include_router(mod.router)
        monkeypatch.setattr(mod, "_plane", lambda req: plane)
        monkeypatch.setattr(mod, "viewer_of", lambda req: who["v"])
    return plane, TestClient(app), who


def at(day):
    return datetime(2026, 10, day, 9, tzinfo=timezone.utc)


def test_detail_list_confirm_and_match_answer_in_the_screens_shape(world):
    plane, c, who = world
    d1 = E.register(plane, None, MEI, received_at=at(2), data=EST.encode(), filename="a.txt")
    d2 = E.register(plane, None, MEI, received_at=at(9), data=AMENDED.encode(), filename="b.txt")
    for d in (d1, d2):
        got = c.post(f"/api/v1/evidence/documents/{d}/extract").json()
    assert got["exception_id"] and len(got["fields"]) == 5

    rows = c.get("/api/v1/evidence/documents").json()["documents"]
    assert [(r["id"], r["label"], r["instrument_name"]) for r in rows] == [(d2, "Current", "Evergreen Growth I"), (d1, "Superseded", "Evergreen Growth I")]

    det = c.get(f"/api/v1/evidence/documents/{d2}").json()
    assert (det["instrument_name"], det["valuation_date"], det["can_review"]) == ("Evergreen Growth I", "2026-09-30", True)
    assert [(v["label"], v["status_label"], v["value_text"], v["page"], v["line"]) for v in det["versions"]] == [
        ("Superseded", "Estimate", "USD 10,000,000.00", 2, 2), ("Current", "Final", "USD 10,180,000.00", 2, 2)]
    assert det["versions"][1]["file_url"] == f"/api/v1/evidence/documents/{d2}/original" and c.get(det["versions"][1]["file_url"]).status_code == 200
    nav = next(f for f in det["fields"] if f["field"] == "Net asset value")
    assert (nav["original"], nav["amended"], nav["state"], nav["confidence"], nav["page"]) == ("USD 10,000,000.00", "USD 10,180,000.00", "waiting", 0.9, 2)
    assert det["match"] == {"identifier_id": det["match"]["identifier_id"], "source_name": "Evergreen Growth I", "instrument_name": "Evergreen Growth I",
                            "status": "approved", "can_approve": True}
    if os.environ.get("SH_WRITE_FIXTURES"):
        FIXTURE.write_text(json.dumps(det, indent=2) + "\n", encoding="utf-8")
    assert set(json.loads(FIXTURE.read_text(encoding="utf-8"))) == set(det)  # the vitest uses this very shape

    done = c.post(f"/api/v1/evidence/fields/{nav['id']}/confirm").json()  # the answer replaces the table row, so it is a Field
    assert {k: done[k] for k in ("id", "field", "original", "amended", "state")} == {**{k: nav[k] for k in ("id", "field", "original", "amended")}, "state": "confirmed"}
    assert done["valuation_id"] and done["exception_id"]

    who["v"] = CIO  # a sponsor with no portfolio access sees nothing of the statements
    assert c.get("/api/v1/evidence/documents").json()["documents"] == []
    assert c.get(f"/api/v1/evidence/documents/{d2}").status_code == 403
    assert c.get(f"/api/v1/evidence/documents/{d2}/original").status_code == 403


def test_an_unmatched_statement_shows_its_proposed_match_and_approval_answers_a_match(world):
    plane, c, who = world
    text = EST.replace("Evergreen Growth I", "EG Growth Fund One", 1)
    d = E.register(plane, None, MEI, received_at=at(2), data=text.encode(), filename="u.txt")
    det = c.get(f"/api/v1/evidence/documents/{d}").json()
    assert det["instrument_name"] == "EG Growth Fund One" and det["match"]["status"] in ("unknown", "proposed")
    with wh.connect(plane) as con:
        src = con.execute("select source_system_id from documents where id = ?", [d]).fetchone()[0]
        ident = wh.new_id()
        con.execute("insert into instrument_identifiers values (?,?,?,?,'name','EG Growth Fund One',null,null,'proposed',null,null,null)", [ident, org_id(plane), INST, src])
    det = c.get(f"/api/v1/evidence/documents/{d}").json()
    assert det["match"] == {"identifier_id": ident, "source_name": "EG Growth Fund One", "instrument_name": "Evergreen Growth I", "status": "proposed", "can_approve": True}
    assert c.post(f"/api/v1/evidence/aliases/{ident}/approve").json() == {**det["match"], "status": "approved"}
    ids = c.post(f"/api/v1/evidence/documents/{d}/extract").json()  # the approved match now lets the statement be read into a valuation
    assert len(ids["fields"]) == 5


def test_a3_7_a_statement_headed_by_the_manager_still_shows_its_fund_match(world):
    plane, c, who = world
    text = "Northgate Partners\nCapital Account Statement\nNorthgate Partners, 12 Quay Street  |  Synthetic test document\n" + AMENDED
    d = E.register(plane, None, MEI, received_at=at(7), data=text.encode(), filename="northgate_A_amended.txt")
    m = c.get(f"/api/v1/evidence/documents/{d}").json()["match"]
    assert (m["status"], m["source_name"], m["instrument_name"]) == ("approved", "Evergreen Growth I", "Evergreen Growth I")


def test_a_list_reads_the_viewers_portfolios_once_and_keeps_fail_closed(world, monkeypatch):
    """analyst-uc4-01 / JUC1B-001: the list opened E1d once per statement (55-85 s for the approver); now once per list."""
    plane, c, who = world
    for k, day in ((1, 2), (2, 9)):
        E.register(plane, None, MEI, received_at=at(day), data=(EST if k == 1 else AMENDED).encode(), filename=f"{k}.txt")
    from sh_platform.v1 import e1_access
    calls, seen = [], {PF}
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda p, v: calls.append(1) or seen)
    who["v"] = CIO
    assert len(c.get("/api/v1/evidence/documents").json()["documents"]) == 2 and len(calls) == 1
    seen.clear()
    assert c.get("/api/v1/evidence/documents").json()["documents"] == []
