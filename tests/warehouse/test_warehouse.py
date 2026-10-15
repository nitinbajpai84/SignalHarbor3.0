import duckdb
import pytest

from sh_platform.plane import PlaneStore
from sh_platform import warehouse as wh


@pytest.fixture
def planes(tmp_path):
    s = PlaneStore(tmp_path)
    return s.create("alpha"), s.create("beta")


def _land(plane, name="trades.csv"):
    (plane.area("landing") / name).write_text("id,amount\n1,10\n2,20\n3,30\n", encoding="utf-8")


def test_csv_and_xlsx_land_in_bronze_with_load_columns(planes):
    a, _ = planes
    _land(a)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["k", "v"])
    ws.append(["x", 1.0])
    wb.save(a.area("landing") / "t.xlsx")
    lid = wh.load_bronze(a, "trades", "trades.csv")
    wh.load_bronze(a, "sheet", "t.xlsx")
    assert wh.counts_only(a, "bronze.trades") == {"rows": 3, "columns": 4}
    assert wh.counts_only(a, "bronze.sheet") == {"rows": 1, "columns": 4}
    con = wh.open_company(a)
    assert con.execute("select distinct _load_id from bronze.trades").fetchall() == [(lid,)]
    con.close()


def test_restricted_file_is_separate(planes):
    a, _ = planes
    _land(a)
    wh.load_bronze(a, "trades", "trades.csv")
    r = wh.open_restricted(a)
    r.execute("create table gold.secret as select 1 as x")
    r.close()
    assert (a.area("warehouse") / "restricted.duckdb").exists()
    con = wh.open_company(a)
    assert con.execute("select count(*) from information_schema.tables where table_name = 'secret'").fetchone()[0] == 0
    con.close()


def test_readonly_copy_opens_read_only(planes):
    a, _ = planes
    _land(a)
    wh.load_bronze(a, "trades", "trades.csv")
    wh.refresh_readonly_copy(a)
    ro = wh.open_readonly(a)
    assert ro.execute("select count(*) from bronze.trades").fetchone()[0] == 3
    with pytest.raises(duckdb.Error):
        ro.execute("create table bronze.nope (x int)")
    ro.close()


def test_other_company_plane_untouched_and_escape_refused(planes):
    a, b = planes
    _land(a)
    wh.load_bronze(a, "trades", "trades.csv")
    assert not (b.area("warehouse") / "company.duckdb").exists()
    with pytest.raises(PermissionError):
        wh.load_bronze(a, "trades", "../../beta/landing/x.csv")


def test_counts_only_returns_no_rows(planes):
    a, _ = planes
    _land(a)
    wh.load_bronze(a, "trades", "trades.csv")
    out = wh.counts_only(a, "bronze.trades")
    assert set(out) == {"rows", "columns"} and all(isinstance(v, int) for v in out.values())
    with pytest.raises(ValueError):
        wh.counts_only(a, "bronze.trades; drop table x")
