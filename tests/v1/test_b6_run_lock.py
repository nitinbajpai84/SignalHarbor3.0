"""RN1: a sandbox run while the server holds the warehouse open (wh.serve(), the 8502 case) must work; Windows refuses to copy
a file DuckDB has open, which used to surface as a 403 "company space could not be opened"."""
import json

import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b6_run as R, wh

PID = "prj-0a0b0c09"


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    f = p.path("build", PID, "plan-v1.json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"project_id": PID, "version": 1, "state": "proposed", "tables": [
        {"name": "bronze_t_raw", "layer": "bronze", "sql": "create table bronze_t_raw as select * from (values (1, 10), (2, 20)) t(id, v)", "depends_on": []},
        {"name": "gold_t_total", "layer": "gold", "sql": "create table gold_t_total as select sum(v) as total from bronze_t_raw", "depends_on": ["bronze_t_raw"]}]}),
        encoding="utf-8")
    yield p
    wh.reset_cache()


def test_sandbox_run_while_server_holds_warehouse(plane):
    wh.serve()
    with wh.connect(plane) as con:  # the shared connection is now open, as on a long-running server
        con.execute("create table keep_me as select 7 as x")
        rec = R.run(plane, PID, "sandbox")
        assert rec["status"] == "ok", rec
        rec = R.run(plane, PID, "sandbox")  # again: the old sandbox file is replaced
        assert rec["status"] == "ok", rec
        assert not con.execute("select 1 from information_schema.tables where table_name = 'gold_t_total'").fetchone()  # live untouched
    wh.release()
    with duckdb.connect(str(plane.path("warehouse", "sandbox.duckdb"))) as sb:
        assert sb.execute("select total from gold_t_total").fetchone()[0] == 30
        assert sb.execute("select x from keep_me").fetchone()[0] == 7  # the copy has the live tables


def test_route_maps_os_error_to_busy(monkeypatch):
    import asyncio
    from sh_platform.v1 import b6_routes as BR

    monkeypatch.setattr(BR, "require_seat", lambda *a: object())
    monkeypatch.setattr(BR, "_plane", lambda r: object())

    def boom(plane, v):
        raise PermissionError(13, "Permission denied", "evidence.duckdb")
    r = asyncio.run(BR._run(None, boom))
    assert r.status_code == 503 and b"busy" in r.body

    def nospace(plane, v):
        raise PermissionError("no company space")
    assert asyncio.run(BR._run(None, nospace)).status_code == 403
