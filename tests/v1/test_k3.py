"""K3 (v4 card K1) The Map centre: data flow generated from records, signed swim lanes, definitions, per-source health; all filtered by access."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e0a_catalogue as E
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import e1_write as W
from sh_platform.v1 import k2_map
from sh_platform.v1 import k3_map as K
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import wh

ROOT = Path(__file__).resolve().parents[2]
ADMIN = Viewer("Ada", frozenset({"company_admin"}), False, "acc-a")
HEAD = Viewer("Hana", frozenset({"analyst"}), False, "acc-h")      # data team, sees entity 1 only
NOBODY = Viewer("Nia", frozenset({"analyst"}), False, "acc-n")     # data team, no portfolio granted
OUT = Viewer("Olive", frozenset({"participant"}), False, "acc-o")
NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def sow(title, steps, kpis=()):
    return {"id": "sow", "title": title, "state": "signed", "goal": {"line": title}, "kpis": list(kpis),
            "process": {"steps": steps, "handovers": [{"from_step": 1, "to_step": 2, "what": "Pack goes to review"}]},
            "signature": {"name": "Ada", "at": "2026-10-01T09:00:00+00:00"}, "signatures": [{"name": "Ada", "at": "2026-10-01T09:00:00+00:00"}]}


def intent(plane, iid, title, steps, sensitivity=None, team=()):
    plane.path("intents", iid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("intents", iid, "sow.json"), sow(title, steps))
    rec = P.create_project(plane, iid, title, "Ada")
    if sensitivity:
        rec.update(sensitivity=sensitivity, team=[{"name": n, "role": "member"} for n in team])
        write_json_atomic(P._ppath(plane, rec["id"]), rec)
    return rec["id"]


STEPS = [{"n": 1, "name": "Collect statements", "who": "Operations", "system": "Email", "does": "Gather manager statements by hand"},
         {"n": 2, "name": "Review", "who": "Finance", "system": "Warehouse", "does": "Check the figures"}]


def build(plane) -> dict:
    """One small family office: two sources, files, bronze, silver, gold, a dashboard, people, valuations and a break."""
    org = W.org_id(plane)
    ids = {k: str(uuid.uuid4()) for k in ("mei", "grace", "hana", "le1", "le2", "p1", "p2", "i1", "i2", "i3", "sys_a", "sys_m", "batch_a", "batch_m", "grp")}
    with wh.connect(plane) as con:
        for k, name in (("mei", "Mei Tan"), ("grace", "Grace Ong"), ("hana", "Hana")):
            con.execute("insert into users values (?,?,?,?,?,?,?,?)", [ids[k], org, "acc-h" if k == "hana" else f"x-{k}", name, f"{k}@x.test", None, True, ago(300)])
        for k, code in (("le1", "E1"), ("le2", "E2")):
            con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", [ids[k], org, code, code, "USD"])
        for k, le, code in (("p1", "le1", "P1"), ("p2", "le2", "P2")):
            con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)", [ids[k], org, ids[le], code, code, "USD"])
        for k in ("i1", "i2", "i3"):
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,?,?)", [ids[k], org, k, "fund", ago(300)])
        for k, code, name, owner, cad in (("sys_a", "administrator", "Fund administrator", "mei", "daily"), ("sys_m", "manager_email", "Manager statements by email", "grace", "monthly")):
            con.execute("insert into source_systems values (?,?,?,?,?,?,?,?,?,?,?)", [ids[k], org, code, name, "x", "file", ids[owner], None, None, cad, True])
        for b, s, when, status in (("batch_a", "sys_a", ago(4), "loaded"), ("batch_m", "sys_m", ago(10), "quarantined")):
            con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, validation_status) values (?,?,?,?,?,?)", [ids[b], org, ids[s], b, when, status])
        # valuations: i1 in P1 fresh and verified (administrator); i2 in P1 old (administrator); i3 in P2 unverified (manager statements)
        for i, p, b, vdate, status in (("i1", "p1", "batch_a", ago(5), "confirmed"), ("i2", "p1", "batch_a", ago(200), "confirmed"), ("i3", "p2", "batch_m", ago(20), "proposed")):
            rid = str(uuid.uuid4())
            con.execute("insert into source_records (id, organization_id, source_batch_id, record_type, received_at, recorded_at, raw_payload_uri, content_hash, quality_status) "
                        "values (?,?,?,?,?,?,?,?,?)", [rid, org, ids[b], "v", ago(5), ago(5), "x", "h", "ok"])
            con.execute("insert into valuation_observations (id, organization_id, instrument_id, portfolio_id, source_record_id, valuation_date, received_at, recorded_at, "
                        "value_amount, currency, valuation_type, approval_status) values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [str(uuid.uuid4()), org, ids[i], ids[p], rid, vdate.date(), ago(5), ago(5), 100, "USD", "official", status])
        for i, p in (("i1", "p1"), ("i3", "p2")):  # one open break per portfolio, one resolved
            con.execute("insert into exceptions (id, organization_id, portfolio_id, instrument_id, exception_type, title, detected_at, materiality_status, status) values (?,?,?,?,?,?,?,?,?)",
                        [str(uuid.uuid4()), org, ids[p], ids[i], "break", f"Break {p}", ago(2), "material", "new"])
        con.execute("insert into exceptions (id, organization_id, portfolio_id, exception_type, title, detected_at, materiality_status, status) values (?,?,?,?,?,?,?,?)",
                    [str(uuid.uuid4()), org, ids["p1"], "break", "Old break", ago(40), "material", "resolved"])
        con.execute("insert into access_groups values (?,?,?,?)", [ids["grp"], org, "Investment office", ""])
        con.execute("insert into access_group_memberships (id, organization_id, access_group_id, user_id, granted_at) values (?,?,?,?,?)", [str(uuid.uuid4()), org, ids["grp"], ids["hana"], ago(100)])
        con.execute("insert into access_group_scopes (id, organization_id, access_group_id, scope_type, scope_value, access_level) values (?,?,?,?,?,?)",
                    [str(uuid.uuid4()), org, ids["grp"], "legal_entity", ids["le1"], "full"])
    # landing: administrator has a good file, manager statements one good and two not accepted
    for fid, code, state, rec in (("f1", "administrator", "loaded", ago(4)), ("f2", "manager_email", "loaded", ago(60)),
                                  ("f3", "manager_email", "rejected_totals", ago(10)), ("f4", "manager_email", "quarantined", ago(9))):
        L._save(plane, {"file_id": fid, "sha256": fid, "name": f"{fid}.xlsx", "size": 1, "received_at": rec.isoformat(), "sender": "x", "source_code": code,
                        "sensitivity": "internal", "state": state, "last_load_at": rec.isoformat() if state == "loaded" else None})
    E.register_bronze(plane, "administrator", "export", [{"name": "isin", "type": "text"}])
    E.register_bronze(plane, "manager_email", "statement")
    pid = intent(plane, "rep1", "Monthly investment report", STEPS)
    plan = {"project_id": pid, "version": 1, "state": "live", "proposed_by": "Leela Raman", "sources": [{"code": "administrator_export", "kind": "structured", "files": [], "owner": "Mei Tan"}],
            "tables": [{"name": "bronze_administrator_export_valuations", "layer": "bronze", "purpose": "Valuations as landed", "depends_on": []},
                       {"name": "valuation_observations", "layer": "silver", "purpose": "Valuations", "depends_on": ["bronze_administrator_export_valuations"]},
                       {"name": "gold_monthly_report_valuation_monthly", "layer": "gold", "purpose": "Value by month", "depends_on": ["valuation_observations"]}],
            "lineage": [{"from": "bronze_administrator_export_valuations", "to": "valuation_observations"},
                        {"from": "valuation_observations", "to": "gold_monthly_report_valuation_monthly"}]}
    plane.path("build", pid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("build", pid, "plan-v1.json"), plan)
    (plane.path("build", pid) / "runs.jsonl").write_text(json.dumps({"run_id": "r1", "status": "ok", "finished": "2026-10-08T06:00:00+00:00", "steps": []}) + "\n", encoding="utf-8")
    plane.path("consume", pid, "dashboards").mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("consume", pid, "dashboards", "d1.json"), {
        "id": "d1", "title": "Net worth by month", "project_id": pid, "created_by": "Ada", "updated_at": "2026-10-08T07:00:00+00:00", "refresh": "daily",
        "audience": [ids["mei"], ids["grp"], "Ada"], "tiles": [{"id": "t1", "title": "x", "sql": "select * from gold_monthly_report_valuation_monthly", "state": "accepted"}]})
    return {"pid": pid, "ids": ids}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setattr(k2_map, "_model", lambda plane: None)
    monkeypatch.setattr(k2_map, "_kick", lambda *a, **k: None)
    monkeypatch.setattr(k2_map, "_groups", lambda plane: [])
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    return plane, build(plane)


def node(fl, nid):
    return next(n for n in fl["nodes"] if n["id"] == nid)


def test_flow_follows_the_data_from_source_to_person(world):
    plane, w = world
    fl = K.flow(plane, ADMIN)
    assert [s["id"] for s in fl["stages"]] == ["source", "file", "bronze", "silver", "gold", "dashboard", "person"]
    path = ["source:administrator", "files:administrator", "table:bronze_administrator_export", "table:bronze_administrator_export_valuations",
            "table:valuation_observations", "table:gold_monthly_report_valuation_monthly", "dash:d1", "person:Mei Tan"]
    edges = {(e["from"], e["to"]) for e in fl["edges"]}
    assert ("source:administrator", "files:administrator") in edges and ("files:administrator", "table:bronze_administrator_export") in edges
    # the plan's own source code (administrator_export) is the same source as the system's (administrator), so its bronze table hangs off it
    assert ("files:administrator", "table:bronze_administrator_export_valuations") in edges
    assert all(node(fl, n) for n in path)
    chain = ["table:bronze_administrator_export_valuations", "table:valuation_observations", "table:gold_monthly_report_valuation_monthly", "dash:d1", "person:Mei Tan"]
    assert all((a, b) in edges for a, b in zip(chain, chain[1:]))
    assert {"person:Investment office", "person:Ada"} <= {n["id"] for n in fl["nodes"]}  # a group and a name resolve to words, never an id
    assert not [n for n in fl["nodes"] if n["stage"] == "person" and len(n["label"]) >= 32]


def test_flow_box_tells_owner_last_load_what_feeds_it_and_what_it_feeds(world):
    plane, w = world
    fl = K.flow(plane, ADMIN)
    src = node(fl, "source:administrator")
    assert src["owner"] == "Mei Tan" and src["note"] == "Arrives daily" and "files:administrator" in src["feeds"]
    files = node(fl, "files:manager_email")
    assert files["note"] == "3 files, 2 not accepted" and files["last_load"].startswith("2026-")
    gold = node(fl, "table:gold_monthly_report_valuation_monthly")
    assert gold["owner"] == "Leela Raman" and gold["last_load"] == "2026-10-08T06:00:00+00:00" and gold["project_id"] == w["pid"] and gold["state"] == "live"
    assert gold["fed_by"] == ["table:valuation_observations"] and gold["feeds"] == ["dash:d1"]
    d = node(fl, "dash:d1")
    assert d["owner"] == "Ada" and d["last_load"].startswith("2026-10-08T07") and d["fed_by"] == ["table:gold_monthly_report_valuation_monthly"]
    assert gold["label"] == "Monthly report valuation monthly" and gold["table"].startswith("gold_")  # screens show the words, the name is kept for detail


def test_flow_for_someone_without_the_project_shows_nothing_of_it_and_no_raw_layers(world):
    plane, w = world
    rec = P.read(plane, w["pid"])
    rec.update(sensitivity="restricted", team=[])
    write_json_atomic(P._ppath(plane, w["pid"]), rec)
    fl = K.flow(plane, OUT)
    assert fl["nodes"] == [] and fl["edges"] == []


def test_flow_for_a_reader_of_an_open_project_has_gold_and_dashboard_but_not_sources_or_files(world):
    plane, w = world
    write_json_atomic(P._ppath(plane, w["pid"]), {**P.read(plane, w["pid"]), "sensitivity": "open"})
    fl = K.flow(plane, OUT)  # the dashboard's audience does not include Olive, so the box is hers only through the project
    assert {n["stage"] for n in fl["nodes"]} <= {"gold", "dashboard", "person"}
    assert "table:gold_monthly_report_valuation_monthly" in {n["id"] for n in fl["nodes"]}
    assert not [n for n in fl["nodes"] if n["stage"] in ("source", "file", "bronze", "silver")]
    assert "dash:d1" not in {n["id"] for n in fl["nodes"]}  # not on the audience, so not on her map


def test_cycle2_raw_feeds_ready_through_undrawn_core_tables_files_from_batches_and_the_team_sees_published_dashboards(world):
    """UC10-01, MAPA-01/02/03, UC10-06: a gold table built through position_snapshots names its raw tables; a source loaded straight into the
    warehouse has a Files box with a last load; the data team sees a published dashboard it is not shared with (not a personal draft);
    the dashboard box says when it refreshes in the header's words."""
    from sh_platform.v1 import b7_studio
    plane, w = world
    org = W.org_id(plane)
    with wh.connect(plane) as con:
        sid = str(uuid.uuid4())
        con.execute("insert into source_systems values (?,?,?,?,?,?,?,?,?,?,?)", [sid, org, "trading_export", "Trading system export", "x", "file", w["ids"]["mei"], None, None, "daily", True])
        con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, validation_status) values (?,?,?,?,?,?)",
                    [str(uuid.uuid4()), org, sid, "t1", ago(1), "loaded"])
    pid = intent(plane, "rep2", "Cash report", STEPS, "open")
    sched = {"freq": "monthly", "at": "07:00", "day": None}
    plan = {"project_id": pid, "version": 1, "state": "live", "proposed_by": "Leo", "schedule": sched,
            "sources": [{"code": "trading_export", "kind": "structured", "files": [], "owner": "Mei Tan"}],
            "tables": [{"name": "bronze_trading_export_positions", "layer": "bronze", "purpose": "As landed", "depends_on": []},
                       {"name": "gold_cash_report_cash", "layer": "gold", "purpose": "Cash", "depends_on": ["position_snapshots", "portfolios"]}],
            "lineage": [{"from": "bronze_trading_export_positions", "to": "position_snapshots"}, {"from": "position_snapshots", "to": "gold_cash_report_cash"},
                        {"from": "portfolios", "to": "gold_cash_report_cash"}]}
    plane.path("build", pid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(plane.path("build", pid, "plan-v1.json"), plan)
    plane.path("consume", pid, "dashboards").mkdir(parents=True, exist_ok=True)
    maker = "f6e3ecb18b334d86984729adf4ff898a"
    tiles = [{"id": "t1", "title": "x", "sql": "select * from gold_cash_report_cash", "state": "accepted"}]
    for did, extra in (("d2", {}), ("d3", {"personal": True})):
        write_json_atomic(plane.path("consume", pid, "dashboards", f"{did}.json"), {"id": did, "title": f"Cash {did}", "project_id": pid, "created_by": maker,
                          "updated_at": "2026-10-08T07:00:00+00:00", "refresh": "same", "audience": [], "tiles": tiles, **extra})
    fl = K.flow(plane, HEAD)
    files, bronze, gold = node(fl, "files:trading_export"), node(fl, "table:bronze_trading_export_positions"), node(fl, "table:gold_cash_report_cash")
    assert files["note"] == "1 file" and files["last_load"] and bronze["last_load"] == files["last_load"] and bronze["fed_by"] == ["files:trading_export"]
    assert gold["fed_by"] == ["table:bronze_trading_export_positions"]  # through position_snapshots, which the map does not draw
    d = node(fl, "dash:d2")
    assert d["fed_by"] == ["table:gold_cash_report_cash"] and d["note"] == b7_studio.schedule_words(sched) and d["owner"] is None  # never the account id
    assert "dash:d3" not in {n["id"] for n in fl["nodes"]}  # someone else's personal draft
    assert "dash:d2" not in {n["id"] for n in K.flow(plane, OUT)["nodes"]}  # outside the team: only what is shared with them


def test_an_empty_company_gives_an_empty_map(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("empty")
    assert K.flow(plane, ADMIN)["edges"] == [] and K.processes(plane, ADMIN) == [] and K.health(plane, ADMIN, NOW)["sources"] == []


def test_process_maps_are_the_signed_swim_lanes_the_person_may_open(world):
    plane, w = world
    draft = {"id": "d", "title": "Draft", "state": "draft", "goal": {"line": "Draft"}, "process": {"steps": STEPS, "handovers": []}}
    plane.path("intents", "draft1").mkdir(parents=True)
    write_json_atomic(plane.path("intents", "draft1", "sow.json"), draft)
    intent(plane, "secret1", "Board pack", STEPS, "restricted", ["Ada"])
    intent(plane, "internal1", "Tax review", STEPS, "internal", ["Ada"])
    got = {p["title"]: p for p in K.processes(plane, ADMIN)}
    assert set(got) == {"Monthly investment report", "Board pack", "Tax review"}  # the draft is not on the map
    rep = got["Monthly investment report"]
    assert [s["name"] for s in rep["process"]["steps"]] == ["Collect statements", "Review"] and rep["process"]["handovers"][0]["to_step"] == 2
    assert rep["owner"] == "Ada" and rep["signed_on"].startswith("2026-10-01") and rep["project_id"] == w["pid"] and not rep["locked"]
    mine = {p["title"]: p for p in K.processes(plane, OUT)}
    assert set(mine) == {"Monthly investment report", "Tax review"}  # restricted is gone
    assert mine["Tax review"]["locked"] and mine["Tax review"]["process"]["steps"] == []  # internal: the title only


def test_definitions_are_the_agreed_meanings_with_their_variants(world):
    plane, _ = world
    for iid, owner, text in (("fin", "Fiona", "Assets minus liabilities"), ("perf", "Pete", "Assets less fees")):
        plane.path("intents", iid).mkdir(parents=True, exist_ok=True)
        s = sow(iid, STEPS, [{"code": "NW", "name": "Net worth", "definition": text, "formula": "", "unit": "USD", "period": "monthly", "owner": owner, "source_ids": []}])
        write_json_atomic(plane.path("intents", iid, "sow.json"), s)
        P.create_project(plane, iid, f"Pack {iid}", "Ada")
    got = K.definitions(plane, ADMIN)
    nw = next(c for c in got if c["name"] == "Net worth")
    assert {v["owner"] for v in nw["variants"]} == {"Fiona", "Pete"}


def test_health_counts_late_stale_rejected_unverified_and_breaks_per_source(world):
    plane, _ = world
    h = K.health(plane, ADMIN, NOW)
    by = {s["code"]: s for s in h["sources"]}
    a, m = by["administrator"], by["manager_email"]
    assert (a["is_late"], a["days_late"], a["rejected"], a["stale"], a["unverified"], a["open_breaks"]) == (True, 3, 0, 1, 0, 1)  # daily, last file 4 days ago: late by 3
    # monthly statements: newest thing is 9-10 days old, within 31 days, so not late; two files not accepted and one batch quarantined
    assert (m["is_late"], m["rejected"], m["unverified"], m["stale"], m["open_breaks"]) == (False, 3, 1, 0, 1)
    assert a["owner"] == "Mei Tan" and a["name"] == "Fund administrator" and a["cadence"] == "daily"
    assert h["totals"] == {"late": 1, "rejected": 3, "open_breaks": 2}  # the resolved break is not open
    later = K.health(plane, ADMIN, NOW + timedelta(days=10))
    assert {s["code"]: (s["is_late"], s["days_late"]) for s in later["sources"]} == {"administrator": (True, 13), "manager_email": (False, None)}


def test_health_follows_e1d_and_never_shows_zero_for_what_is_not_visible(world):
    plane, _ = world
    mine = {s["code"]: s for s in K.health(plane, HEAD, NOW)["sources"]}  # Hana sees entity 1, so portfolio 1 only
    assert mine["administrator"]["stale"] == 1 and mine["administrator"]["open_breaks"] == 1
    assert mine["manager_email"]["unverified"] == 0 and mine["manager_email"]["open_breaks"] == 0  # the unverified value is in portfolio 2
    none = K.health(plane, NOBODY, NOW)
    assert all(s["stale"] is None and s["unverified"] is None and s["open_breaks"] is None for s in none["sources"]) and none["totals"]["open_breaks"] is None
    assert none["sources"][0]["rejected"] is not None  # load facts are not entity data


def test_health_is_the_data_teams_alone(world):
    plane, _ = world
    assert K.health(plane, OUT, NOW) == {"sources": [], "totals": {}, "allowed": False}


def test_a_source_that_never_sent_anything_says_so():
    # cadence known, nothing received: not "late by n days" but "nothing received yet"
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        plane = PlaneStore(Path(d)).create("quiet")
        org = W.org_id(plane)
        with wh.connect(plane) as con:
            con.execute("insert into source_systems values (?,?,?,?,?,?,?,?,?,?,?)", [str(uuid.uuid4()), org, "market_data", "Market data", "x", "file", None, None, None, "daily", True])
        s = K.health(plane, ADMIN, NOW)["sources"][0]
        assert s["never_received"] and s["last_received"] is None and not s["is_late"] and s["days_late"] is None


def test_routes_are_declared_and_the_data_team_gate_holds():
    from sh_platform.v1 import k3_routes
    paths = {r.path for r in k3_routes.router.routes}
    # the four read-only views, plus the v5 ontology and review queue (tests/v1/test_k3_onto.py)
    assert paths == {f"/api/v1/centre-map/{p}" for p in ("flow", "processes", "definitions", "health", "model", "ontology", "review", "review/approve", "review/reject")}
    text = (ROOT / "sh_platform" / "v1" / "k3.permissions.yaml").read_text(encoding="utf-8")
    assert all(f"GET /api/v1/centre-map/{p}:" in text for p in ("flow", "processes", "definitions", "health"))


def test_the_shapes_the_screens_read_are_the_ones_the_ui_fixture_holds(world):
    """ui/src/v1/k3/fixtures.json is real output (see tools in the landing note); its keys must match what the handlers return now."""
    plane, _ = world
    fx = json.loads((ROOT / "ui" / "src" / "v1" / "k3" / "fixtures.json").read_text(encoding="utf-8"))
    fl, hl = K.flow(plane, ADMIN), K.health(plane, ADMIN, NOW)
    assert set(fx["flow"]) == set(fl) and set(fx["flow"]["nodes"][0]) == set(fl["nodes"][0]) and set(fx["flow"]["edges"][0]) == set(fl["edges"][0])
    assert set(fx["health"]) == set(hl) and set(fx["health"]["sources"][0]) == set(hl["sources"][0])
    pr = K.processes(plane, ADMIN)[0]
    assert set(fx["processes"]["processes"][0]) == set(pr) and set(fx["processes"]["processes"][0]["process"]) == set(pr["process"])
