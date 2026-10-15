"""Feeds: governed measures with gold values, per-viewer access. Synthetic data only."""
import json

from sh_platform.consume.feeds import build
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.warehouse import open_company, refresh_readonly_copy

BID = "b" * 32
ADMIN, MEI, WEI = (Viewer("Ann Admin", frozenset({"company_admin"})), Viewer("Mei Tan", frozenset({"participant"})),
                   Viewer("Wei Chen", frozenset({"participant"})))


def put(plane, rel: str, data) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def cell(v):
    return {"mark": "stated", "value": v}


def make(tmp_path):
    plane = PlaneStore(tmp_path).create("lakeside-family-office")
    put(plane, f"intents/m2_baseline/{BID}/baseline.json", {"id": BID, "state": "signed", "created_at": "2026-09-01"})
    put(plane, f"intents/m2_baseline/{BID}/kpis.json", [{"id": "NAV", "name": "Net asset value"}, {"id": "CASH", "name": "Cash held"}])
    put(plane, f"intents/m2_baseline/{BID}/governed_state.json", {
        k: {"owners": cell({"business": "Mei Tan"}), "may_see": cell(["Mei Tan"])} for k in ("NAV", "CASH")})
    con = open_company(plane)
    con.execute("create table gold.nav (period varchar, value double)")
    for i, v in enumerate([10, 11, 10, 11, 10, 11, 10, 11, 10, 50]):  # ten rows: nine are kept, the last breaks the range
        con.execute("insert into gold.nav values (?, ?)", [f"2026-{i + 1:02d}", v])
    con.close()
    refresh_readonly_copy(plane)
    return plane


def by_code(doc):
    return {m["code"]: m for m in doc["measures"]}


def test_values_come_from_the_gold_table(tmp_path):
    m = by_code(build(make(tmp_path), MEI))["NAV"]
    assert m["latest"] == {"period": "2026-10", "value": 50.0} and len(m["trend"]) == 9
    assert m["range_break"] is True and m["owner"] == "Mei Tan" and m["may_see"] is True and m["mine"] is True


def test_someone_outside_the_list_gets_no_value(tmp_path):
    m = by_code(build(make(tmp_path), WEI))["NAV"]
    assert m["latest"] is None and m["trend"] == [] and m["may_see"] is False and m["owner"] == "Mei Tan"


def test_no_mart_gives_latest_null(tmp_path):
    m = by_code(build(make(tmp_path), MEI))["CASH"]
    assert m["latest"] is None and m["trend"] == [] and m["may_see"] is True
