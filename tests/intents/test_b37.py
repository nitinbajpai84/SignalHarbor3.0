"""B37: the source map. Positions from a fixture catalogue, Lens's draft versus a person's confirmation, traces, silhouettes."""
from sh_platform.intents import source_map as M
from sh_platform.intents import store as S
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.profile import view as pview

BID, NOW = "a" * 32, "2026-10-07T09:00:00+00:00"
c = lambda v: {"value": v, "mark": "stated"}  # noqa: E731


def src(i, name, personal="No", often="Monthly", lands="A shared folder", confirmed=None, see=""):
    return {"Source ID": c(i), "Source name": c(name), "Contains personal data?": c(personal), "How often it arrives": c(often),
            "Where it lands or lives": c(lands), "Confirmed by": c(confirmed), "Who may see it": c(see)}


def plane_with(tmp_path):
    plane = PlaneStore(tmp_path).create("fam").ensure()
    cat = {"sources": [src("S01", "Performance workbook", confirmed="Harvey Rowley"),     # 2 measures + all four checks: p1
                       src("S02", "Mailbox", personal="", often="", lands=""),            # 0 measures, nothing known: identify
                       src("S03", "Payroll extract", personal="Yes", see="Grace Ward"),  # restricted
                       src("S04", "Index feed", personal="", often="", lands="")],                      # 2 measures, 1 check of 4: unknown
           "tables": [{"Item ID": c("T1"), "Source ID": c("S01"), "Related KPIs": c("K1, K2")},
                      {"Item ID": c("T4"), "Source ID": c("S04"), "Related KPIs": c("K1, K2")}],
           "fields": [{"Item ID": c("T1"), "Feeds KPI": c("K1")}, {"Item ID": c("T4"), "Feeds KPI": c("K3")}],
           "kpis": [{"KPI ID": c("K1"), "KPI name": c("Headroom"), "Priority": c("must")},
                    {"KPI ID": c("K2"), "KPI name": c("Coverage"), "Priority": c("should")},
                    {"KPI ID": c("K3"), "KPI name": c("Nice to have"), "Priority": c("good to have")}]}
    write_json_atomic(plane.path("intents", "m2_baseline", BID, "catalogue.json"), cat)
    return plane


def intent():
    return {"id": "ini-" + "b" * 32, "refs": {"baseline_ids": [BID], "charter_outcome_id": None}}


def by_id(res):
    return {s["id"]: s for s in res["sources"]}


def test_positions_come_from_the_clusters_and_sources(tmp_path):
    s = by_id(M.positions(plane_with(tmp_path), intent()))
    assert (s["S01"]["impact"]["must"], s["S01"]["impact"]["should"], s["S01"]["zone"]) == (1, 1, "p1")
    assert s["S01"]["readiness"]["count"] == 4 and s["S01"]["impact"]["score"] == 0.0
    assert s["S02"]["impact"]["count"] == 0 and s["S02"]["zone"] == "identify"   # nothing fed, nothing known
    assert s["S04"]["impact"]["count"] == 2 and s["S04"]["readiness"]["count"] == 1 and s["S04"]["zone"] == "unknown"  # K3 (good to have) is not counted


def test_every_number_is_traced(tmp_path):
    s = by_id(M.positions(plane_with(tmp_path), intent()))["S01"]
    assert [m["id"] for m in s["impact"]["measures"]] == ["K1", "K2"]
    assert all(ch["trace"].startswith("catalogue") for ch in s["readiness"]["checks"])
    assert "Harvey Rowley" in s["readiness"]["checks"][1]["trace"]


def test_draft_is_guessed_and_confirmation_is_stated(tmp_path):
    plane, rec = plane_with(tmp_path), intent()
    f = M.build_file(plane, rec, None, NOW)
    cl = f["sources"]["S01"]["classification"]
    assert (cl["mark"], cl["by"], cl["value"]) == ("guessed", "Lens", {"strategic": True})
    assert f["sources"]["S02"]["classification"]["value"] == {"strategic": False}
    write_json_atomic(M.file_of(plane, rec["id"]), f)
    g = M.build_file(plane, rec, M.read_map(plane, rec["id"]), NOW,
                     {"source_id": "S02", "strategic": True, "reason": "The auditors ask for it.", "by": "Katie"})
    cl = g["sources"]["S02"]["classification"]
    assert (cl["mark"], cl["by"], cl["reason"], cl["value"]) == ("stated", "Katie", "The auditors ask for it.", {"strategic": True})
    h = M.build_file(plane, rec, g, NOW)                       # a later Lens draft never replaces a person's answer
    assert h["sources"]["S02"]["classification"]["mark"] == "stated"
    assert h["sources"]["S01"]["impact"]["mark"] == "stated" and h["sources"]["S01"]["impact"]["from"]


def test_restricted_source_is_a_silhouette(tmp_path):
    plane, rec = plane_with(tmp_path), intent()
    stranger = pview.Viewer("Aaron Lyle", frozenset({"analyst"}), False, "acct-1")
    res = M._view(plane, rec, stranger)
    sil = [s for s in res["sources"] if s["silhouette"]]
    assert sil == [{"id": "restricted-1", "name": "A restricted source", "restricted": True, "silhouette": True}]
    assert "Payroll extract" not in str(res) and res["restricted"] == 1
    named = M._view(plane, rec, pview.Viewer("Grace Ward", frozenset({"approver"}), False, "acct-2"))
    assert "S03" in by_id(named)
    # the written file keeps every source, marked restricted, so the readers can mask per viewer
    assert M.build_file(plane, rec, None, NOW)["sources"]["S03"]["restricted"] is True


def test_no_baseline_says_what_is_missing(tmp_path):
    plane = PlaneStore(tmp_path).create("fam").ensure()
    res = M.positions(plane, {"id": "ini-" + "b" * 32, "refs": {"baseline_ids": []}})
    assert res["available"] is False and "catalogue" in res["missing"] and res["sources"] == []


def test_routes_read_confirm_and_hide_from_strangers(tmp_path):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sh_platform.intents import lifecycle as L

    plane = plane_with(tmp_path)
    rec = L.new_record("initiative", "fam", L.person("acct-1", "Janet Shaw"), NOW, title="Funding view")
    rec["refs"]["baseline_ids"] = [BID]
    S.create_intent(plane, rec)
    app = FastAPI()
    app.include_router(M.router)
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = SimpleNamespace(get=lambda a: {"display_name": {"acct-1": "Janet Shaw", "acct-2": "Aaron Lyle"}[a]},
                                              in_company=lambda c: [])
    who = {"id": "acct-1"}

    @app.middleware("http")
    async def sign_in(request, call_next):
        request.state.company_id, request.state.account_id, request.state.roles = "fam", who["id"], ["company_admin"]
        return await call_next(request)

    api, url = TestClient(app), f"/api/intents/sources/map?intent_id={rec['id']}"
    got = api.get(url).json()
    assert got["written"] is False and got["can_confirm"] is True and got["restricted"] == 1  # Grace is named on S03, so the admin is like anyone else (A-069)
    assert api.post(url, json={"source_id": "S01", "strategic": True, "reason": ""}).status_code == 400
    done = api.post(url, json={"source_id": "S01", "strategic": False, "reason": "Used once a year."}).json()
    assert by_id(done)["S01"]["classification"]["mark"] == "stated" and done["written"] is True
    assert M.read_map(plane, rec["id"])["sources"]["S01"]["classification"]["by"] == "Janet Shaw"
    assert api.post(url, json={"source_id": "nope", "strategic": True, "reason": "Because it is."}).status_code == 404
    who["id"] = "acct-2"                                   # not on the intent: not even a stub
    assert api.get(url).status_code == 404 and api.get("/api/intents/sources/map").status_code == 404
