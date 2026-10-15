"""B15 (spec 28): data sources and technical areas. Three owner kinds kept apart, the source owner confirms, chips from the profile systems
and teams, the extras file, a closed source never reaching the wrong viewer, the intake reading the source owner. Synthetic people."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m2_baseline.api import data_sources as DS
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.store import catalogue as CS
from sh_platform.intents import sources as SRC
from sh_platform.intents import store as S
from sh_platform.plane import PlaneStore
from sh_platform.profile import store as profile_store
from sh_platform.profile import view as PV

CO, BID, IID = "ardmore", "b" * 32, "ini-" + "a" * 32
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "daniel": ("Daniel Kerr", ["sponsor"]), "aaron": ("Aaron Lyle", ["participant"]),
         "katie": ("Katie Rao", ["analyst"]), "harvey": ("Harvey Rowley", ["owner"]), "grace": ("Grace Ward", ["approver"]), "zed": ("Zed Lee", ["participant"])}
cell = lambda v, mark="stated", **kw: {"value": v, "mark": mark, "by": "Janet Shaw", "at": "2026-10-06T09:00:00+00:00", "from": "systems.csv", **kw}  # noqa: E731


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r) in ACCTS.items()]


def person(name, team):
    return {"name": cell(name), "team": cell(team)}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    folder = plane.path("intents", "m2_baseline", BID)
    folder.mkdir(parents=True)
    (folder / "baseline.json").write_text(json.dumps({"id": BID, "state": "draft"}), encoding="utf-8")
    profile_store.mutate(plane, lambda d: (
        d["people"].update({"p1": person("Harvey Rowley", "Operations"), "p2": person("Aaron Lyle", "Operations"), "p3": person("Katie Rao", "Finance")}),
        d["systems"].update({
            "portfolio": {"name": cell("Portfolio system"), "kind": cell("system"), "owner": cell("Harvey Rowley"), "lands": cell("A shared folder"),
                          "frequency": cell("Daily")},
            "payroll": {"name": cell("Payroll export"), "kind": cell("file drop"), "owner": cell("Grace Ward"), "personal_data": cell("Yes"),
                        "may_see": cell(["Grace Ward", "Janet Shaw"])}})))
    rec = {"id": IID, "type": "initiative", "title": "Month-end close", "purpose": "close in three days", "created_by": "janet", "company": CO,
           "areas": ["Operations"], "state": "open", "version": 1, "outcome": {"kind": "initiative"}, "closure": {}, "ratings": [], "links": {},
           "share": {}, "history": [], "refs": {"baseline_ids": [BID]}, "time_box": {},
           "people": {"organiser": {"account_id": "janet", "name": "Janet Shaw"}, "sponsor": {"account_id": "daniel", "name": "Daniel Kerr"},
                      "participants": [{"account_id": "aaron", "name": "Aaron Lyle"}, {"account_id": "katie", "name": "Katie Rao"}],
                      "advisers": [], "affected": [], "observers": []},
           "stages": [{"key": "data_sources", "state": "open", "opened_at": "2026-10-05T09:00:00+00:00", "closed_at": None}]}
    S.create_intent(plane, rec)
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.include_router(SRC.router)
    app.include_router(DS.router, prefix="/api/modules/m2_baseline")

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)
    return SimpleNamespace(plane=plane, c=TestClient(app), base=f"/api/intents/{IID}/data-sources")


def call(env, who, method, path="", body=None):
    r = env.c.request(method, env.base + path, json=body, headers={"x-who": who})
    return r.status_code, r.json()


def add(env, who="aaron", **cells):
    code, out = call(env, who, "POST", "", {"cells": cells})
    assert code == 200, out
    return out["id"]


def row(env, who, sid):
    code, out = call(env, who, "GET")
    assert code == 200, out
    return next(r for r in out["sources"] if r["id"] == sid)


def test_three_owners_are_three_cells_and_stored_apart(env):
    sid = add(env, name="Portfolio system", data_owner="Grace Ward", source_owner="Harvey Rowley", business_owner="Daniel Kerr")
    r = row(env, "janet", sid)
    assert {k: v["value"] for k, v in r["owners"].items()} == {"business": "Daniel Kerr", "data": "Grace Ward", "source": "Harvey Rowley"}
    cat, _ = CS._raw(env.plane, BID)
    assert C.text_of(cat["sources"][0]["Data owner"]) == "Grace Ward"        # column F stays the data owner
    extras = json.loads(env.plane.path("intents", "m2_baseline", BID, "data_sources.json").read_text(encoding="utf-8"))
    e = extras["sources"][sid]
    assert e["source_owner"]["value"] == "Harvey Rowley" and e["business_owner"]["value"] == "Daniel Kerr" and "owner" not in e
    assert "Harvey Rowley" not in json.dumps(cat)


def test_a_v1_row_seeds_a_guessed_source_owner_from_the_data_owner(env):
    CS.add_row(env.plane, BID, "sources", {"Source name": "Old workbook", "Data owner": "Jun Wei"}, "Janet Shaw")
    r = row(env, "janet", "S01")
    assert r["owners"]["source"]["value"] == "Jun Wei" and r["owners"]["source"]["mark"] == "guessed"
    assert r["owners"]["source"]["from"] == "old catalogue owner" and r["state"] != "confirmed"
    assert r["owners"]["business"]["value"] is None  # "Not named yet" on screen, never merged


def test_only_the_source_owner_confirms_and_a_change_undoes_it(env):
    sid = add(env, name="Portfolio system", source_owner="Harvey Rowley")
    code, out = call(env, "janet", "POST", f"/{sid}/confirm", {})
    assert code == 403 and out["message"] == "Only the source owner can confirm this."
    assert call(env, "katie", "POST", f"/{sid}/confirm", {})[0] == 403
    assert call(env, "harvey", "POST", f"/{sid}/confirm", {})[0] == 200
    r = row(env, "harvey", sid)
    assert r["state"] == "confirmed" and r["confirmed_by"] == "Harvey Rowley" and r["owners"]["source"]["mark"] == "stated"
    assert call(env, "aaron", "PUT", f"/{sid}", {"cells": {"frequency": "Weekly"}})[0] == 200
    r = row(env, "harvey", sid)
    assert r["state"] == "edited" and r["confirmed_by"] is None and any("was confirmed by Harvey Rowley" in h["what"] for h in r["history"])
    notes = json.loads(env.plane.path("intents", "m2_baseline", BID, "data_sources.json").read_text(encoding="utf-8"))["notices"]
    assert {"to": "Harvey Rowley", "text": "Your source changed"} == {k: notes[-1][k] for k in ("to", "text")}
    code, _ = call(env, "harvey", "POST", f"/{sid}/reassign", {"to": "Aaron Lyle"})
    assert code == 200 and row(env, "aaron", sid)["can"]["confirm"] and call(env, "harvey", "GET")[1]["sources"] == []
    assert call(env, "aaron", "POST", f"/{sid}/confirm", {})[0] == 200


def test_class_and_who_may_see_wait_for_the_governance_lead(env):
    sid = add(env, name="Custody file", data_owner="Grace Ward")
    code, out = call(env, "katie", "PUT", f"/{sid}", {"cells": {"personal": "Yes", "who_may_see": "Grace Ward"}})
    assert code == 200 and out["proposed"] == ["personal", "who_may_see"]
    r = row(env, "katie", sid)
    assert r["personal"]["value"] == "Not sure" and r["undecided"] and r["proposals"]["personal"]["by"] == "Katie Rao"
    assert r["proposals"]["personal"]["waiting_for"] == "Grace Ward"
    assert call(env, "grace", "PUT", f"/{sid}", {"cells": {"personal": "No"}})[0] == 200
    r = row(env, "grace", sid)
    assert r["personal"]["value"] == "No" and not r["undecided"] and "personal" not in r["proposals"]


def test_chips_come_from_profile_systems_and_teams(env):
    code, out = call(env, "janet", "GET")
    chips = {c["name"]: c for c in out["areas"]["chips"]}
    assert {"Portfolio system", "Operations", "Finance"} <= set(chips)
    assert chips["Operations"]["kind"] == "team" and chips["Operations"]["count"] == 2        # people in the team
    assert [w["name"] for w in chips["Portfolio system"]["who_can_say"]] == ["Harvey Rowley"]
    assert "Payroll export" in chips                                                      # the organiser sees it; a person it is shut to does not
    code, out = call(env, "katie", "GET")
    names = [c["name"] for c in out["areas"]["chips"]]
    assert "Payroll export" not in names and "A restricted area" in names
    code, out = call(env, "katie", "POST", "/areas", {"name": "Outsourced administrator", "kind": "team"})
    assert code == 200 and out["id"] == "added:outsourced-administrator"
    assert call(env, "katie", "PUT", f"/areas/{out['id']}", {"add_person": "Aaron Lyle"})[0] == 200
    chip = next(c for c in call(env, "katie", "GET")[1]["areas"]["chips"] if c["id"] == out["id"])
    assert chip["who_can_say"][0]["name"] == "Aaron Lyle" and chip["added"]
    assert call(env, "katie", "PUT", "/areas/team:finance", {"hidden_reason": "not ours"})[0] == 403
    assert call(env, "janet", "PUT", "/areas/team:finance", {"hidden_reason": ""})[0] == 422
    assert call(env, "janet", "PUT", "/areas/team:finance", {"hidden_reason": "Not a technical area"})[0] == 200
    got = call(env, "janet", "GET")[1]["areas"]
    assert "Finance" not in [c["name"] for c in got["chips"]] and [c["name"] for c in got["hidden"]] == ["Finance"]


def test_a_closed_source_reaches_only_its_list_and_is_counted(env):
    cat_id = CS.add_row(env.plane, BID, "sources", {"Source name": "Salary file", "Contains personal data?": "Yes", "Who may see it": "Grace Ward"}, "Grace Ward")
    katie, harvey, janet, grace = (call(env, w, "GET")[1] for w in ("katie", "harvey", "janet", "grace"))
    assert all(r["id"] != cat_id for r in katie["sources"]) and katie["restricted"] == 1 and "Salary file" not in json.dumps(katie)
    assert harvey["sources"] == []                                         # an owner sees only the rows they are named on
    assert [r["name"] for r in janet["sources"]] == ["Salary file"] and [r["name"] for r in grace["sources"]] == ["Salary file"]
    assert call(env, "katie", "PUT", f"/{cat_id}", {"cells": {"frequency": "Daily"}})[0] == 404   # the same answer as for a row that is not there
    assert [s["restricted"] for s in SRC.list_sources(env.plane, IID, PV.Viewer("Katie Rao", frozenset({"analyst"})))] == [True]


def test_left_out_keeps_the_row_and_needs_a_reason(env):
    sid = add(env, name="Spare file")
    assert call(env, "aaron", "PUT", f"/{sid}", {"left_out": {"reason": "x"}})[0] == 403
    assert call(env, "janet", "PUT", f"/{sid}", {"left_out": {"reason": " "}})[0] == 422
    assert call(env, "janet", "PUT", f"/{sid}", {"left_out": {"reason": "Not a source"}})[0] == 200
    out = call(env, "janet", "GET")[1]
    assert out["sources"] == [] and out["left_out"][0]["left_out"]["reason"] == "Not a source" and out["counters"]["named"] == 0
    assert call(env, "janet", "PUT", f"/{sid}", {"restore": True})[0] == 200 and call(env, "janet", "GET")[1]["counters"]["named"] == 1


def test_draft_is_guessed_never_replaces_a_person_and_needs_something_to_read(env):
    add(env, name="Portfolio system", lands="Folder X")                  # a person already named this one
    code, out = call(env, "janet", "POST", "/draft", {})
    assert code == 200 and out["drafted"] == 1 and "Lens drafted 1 source" in out["message"]
    names = {r["name"]: r for r in call(env, "janet", "GET")[1]["sources"]}
    assert names["Portfolio system"]["lands"]["value"] == "Folder X" and names["Portfolio system"]["state"] == "needs_owner"
    pay = names["Payroll export"]
    assert pay["state"] == "drafted" and pay["owners"]["source"] == {**pay["owners"]["source"], "value": "Grace Ward", "mark": "guessed"}
    assert pay["owners"]["data"]["value"] is None and pay["undecided"]    # the class is never set by Lens
    assert call(env, "katie", "POST", "/draft", {})[0] == 403
    profile_store.mutate(env.plane, lambda d: d["systems"].clear())
    cat, _ = CS._raw(env.plane, BID)
    cat["sources"].clear()
    CS._save(env.plane, BID, cat, [])
    assert call(env, "janet", "POST", "/draft", {})[1]["message"] == DS.NOTHING_TO_READ


def test_done_closes_the_stage_and_only_the_organiser_does_it(env):
    assert call(env, "daniel", "POST", "/done", {})[0] == 403
    code, out = call(env, "janet", "POST", "/done", {})
    assert code == 200 and out["stage"]["state"] == "done" and out["data_sources"]["state"] == "done"
    assert out["stage"]["opened_at"] and out["stage"]["done_at"] and out["days_to_done"] == 0  # counted from data_sources.json's own stamps


def test_a_person_outside_the_intent_gets_404_and_no_baseline_says_what_is_missing(env):
    assert call(env, "zed", "GET")[0] == 404                             # not in the intent, and not an owner, the admin or the governance lead
    S.update_intent(env.plane, IID, 1, lambda r: r["refs"].update(baseline_ids=[]))
    code, out = call(env, "janet", "GET")
    assert code == 404 and out["message"].startswith("Not available yet")
    assert SRC.list_sources(env.plane, IID) == []


def test_the_baseline_spelling_answers_too(env):
    code = env.c.request("GET", f"/api/modules/m2_baseline/baselines/{BID}/data-sources", headers={"x-who": "janet"}).status_code
    assert code == 200


def test_intake_asks_the_source_owner_first_and_says_when_it_falls_back(env):
    a = add(env, name="Portfolio system", data_owner="Grace Ward", source_owner="Harvey Rowley")
    b = add(env, name="Bank file", data_owner="Grace Ward")
    c = add(env, name="Nobody file")
    assert DS.intake_owners(env.plane, BID) == {a: {"name": "Harvey Rowley", "label": "source owner"},
                                                b: {"name": "Grace Ward", "label": "data owner, no source owner named"}}
    assert c not in SRC.intake_owners(env.plane, BID)


def test_list_sources_for_the_map(env):
    sid = add(env, name="Portfolio system", source_owner="Harvey Rowley", system_ref="systems.portfolio")
    got = SRC.list_sources(env.plane, IID)
    assert [(r["id"], r["name"], r["owners"]["source"]["value"], r["system"]["name"]) for r in got] == [(sid, "Portfolio system", "Harvey Rowley", "Portfolio system")]


def test_a_signed_baseline_keeps_the_row_but_the_owner_can_still_confirm_and_hand_over(env):
    sid = add(env, name="Portfolio system", source_owner="Harvey Rowley")
    env.plane.path("intents", "m2_baseline", BID, "baseline.json").write_text(json.dumps({"id": BID, "state": "signed"}), encoding="utf-8")
    assert call(env, "aaron", "PUT", f"/{sid}", {"cells": {"frequency": "Weekly"}})[0] == 409   # the catalogue row is read only
    assert call(env, "harvey", "POST", f"/{sid}/confirm", {})[0] == 200
    assert call(env, "harvey", "POST", f"/{sid}/problems", {"text": "Arrives late"})[0] == 200
    assert row(env, "harvey", sid)["state"] == "confirmed"
    assert call(env, "harvey", "POST", f"/{sid}/reassign", {"to": "Aaron Lyle"})[0] == 200


def test_done_adds_and_closes_the_stage_on_a_record_that_lacks_it(env):
    S.update_intent(env.plane, IID, 1, lambda r: r.update(stages=[{"key": "think_unfiltered", "state": "closed"}]))
    assert call(env, "janet", "POST", "/done", {})[0] == 200
    st = {s["key"]: s for s in S.read_intent(env.plane, IID)["stages"]}["data_sources"]
    assert st["state"] == "closed" and st["closed_at"]


def _extras(env):
    return json.loads(env.plane.path("intents", "m2_baseline", BID, "data_sources.json").read_text(encoding="utf-8"))


def test_first_confirm_opens_the_substage_and_a_second_done_keeps_its_stamps(env):
    sid = add(env, name="Portfolio system", source_owner="Harvey Rowley")
    assert _extras(env)["state"]["opened_at"]  # adding opened it; reset to prove confirm opens it too
    doc = _extras(env)
    doc["state"].update(state="not_started", opened_at=None)
    env.plane.path("intents", "m2_baseline", BID, "data_sources.json").write_text(json.dumps(doc), encoding="utf-8")
    assert call(env, "harvey", "POST", f"/{sid}/confirm", {})[0] == 200
    st = _extras(env)["state"]
    assert st["state"] != "not_started" and st["opened_at"]
    first = call(env, "janet", "POST", "/done", {})[1]["data_sources"]
    again = call(env, "janet", "POST", "/done", {})[1]["data_sources"]
    assert again["done_at"] == first["done_at"] == _extras(env)["state"]["done_at"] and again["opened_at"] == st["opened_at"]
