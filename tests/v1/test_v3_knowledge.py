"""Harbor 3.0 Knowledge: an empty company answers an honest empty state; a seeded one gets people, entities, funds, sources, figures, use cases, decisions,
plain-word edges, processes and things; another company's records never appear. Real routes, store and permissions; synthetic data only."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

SOW = {"state": "signed", "goal": {"line": "Where is our cash?", "readers": ["Daniel Foo"], "decisions": ["Call capital from the trust"]},
       "kpis": [{"name": "Cash", "definition": "Cash held across entities", "period": "monthly"}, {"name": "Unfunded commitments"}],
       "sources": [{"name": "Bank statements", "holds": "Cash balances"}],
       "process": {"steps": [{"name": "Collect", "who": "Data team", "does": "Collect statements"}, {"name": "Check", "who": "Head of data", "does": "Check balances"}]}}
LIVE = {"id": "th-live", "title": "Capital calls", "stage": "live", "created": "2026-10-01T00:00:00Z", "iid": "int-1", "pid": "EV-0003", "events": [{"at": "2026-10-13T06:00:00Z", "kind": "harbor"}],
        "steps": [], "started_by": "Anita Rao", "sources": ["Bank statements"],
        "record": {"signed_by": "Anita Rao", "role": "head of data", "signed_at": "2026-10-02T00:00:00Z"},
        "exceptions": [{"title": "Late statement", "text": "Evergreen Family Trust has not sent its file"}],
        "note": {"text": "Live.", "figures": [{"label": "Cash", "value": "4.14m", "change": "-0.2m"}]}}


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c, PlaneStore(data).plane_for("evergreen")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    return client(tmp_path, monkeypatch)


def seed(plane):
    H.save(plane, LIVE)
    H.save(plane, LIVE | {"id": "th-gone", "title": "Dropped idea", "stage": "discarded", "iid": None})
    d = plane.path("intents", "int-1")
    d.mkdir(parents=True, exist_ok=True)
    (d / "sow.json").write_text(json.dumps(SOW), encoding="utf-8")
    with wh.connect(plane) as con:
        org, e1, f1, f2, c1 = (wh.new_id() for _ in range(5))
        con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency, active_from) values (?,?,'EG-T','Evergreen Family Trust','USD','2020-01-01')", [e1, org])
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, manager_name, currency, created_at) values (?,?,'Growth Fund III','fund','Acme Partners','USD',now())", [f1, org])
        con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, currency, created_at) values (?,?,'Unused Fund','fund','USD',now())", [f2, org])
        con.execute("insert into commitments (id, organization_id, legal_entity_id, instrument_id, commitment_amount, currency, committed_on, called_to_date, called_as_at, recorded_at) "
                    "values (?,?,?,?,5000000,'USD','2026-03-01',1000000,'2026-09-30',now())", [c1, org, e1, f1])


def of(k, kind):
    return {n["label"]: n for n in k["nodes"] if n["kind"] == kind}


def test_empty_company_is_honest(env):
    c, _ = env
    k = c.get("/api/v3/knowledge").json()
    assert k["empty"] is True and k["edges"] == [] and k["processes"] == []
    assert {n["kind"] for n in k["nodes"]} == {"person"} and of(k, "person")["Anita Rao"]["facts"][0]["source"] == "Accounts"
    assert [t["name"] for t in k["things"]] == ["People"]


def test_seeded_company_builds_the_map(env):
    c, plane = env
    seed(plane)
    k = c.get("/api/v3/knowledge").json()
    assert k["empty"] is False
    assert set(of(k, "entity")) == {"Evergreen Family Trust"} and set(of(k, "fund")) == {"Growth Fund III"}  # a fund nobody committed to is not shown
    assert set(of(k, "source")) == {"Bank statements"} and set(of(k, "figure")) == {"Cash", "Unfunded commitments"}
    assert set(of(k, "usecase")) == {"Capital calls"}  # the discarded thread is left out
    assert {"Call capital from the trust", "Late statement"} <= set(of(k, "decision"))
    cash = of(k, "figure")["Cash"]
    assert any("4.14m" in f["text"] and f["source"] == "Note of Capital calls" and f["at"] == "2026-10-13" for f in cash["facts"])
    assert not any("Latest" in f["text"] for f in of(k, "figure")["Unfunded commitments"]["facts"])  # never a value the note did not give
    ids = {n["label"]: n["id"] for n in k["nodes"]}
    es = {(e["from"], e["to"], e["label"]) for e in k["edges"]}
    anita, uc = ids["Anita Rao"], ids["Capital calls"]
    for e in [(anita, uc, "decides"), (ids["Daniel Foo"], uc, "reads"), (ids["Bank statements"], ids["Cash"], "feeds"), (uc, ids["Cash"], "uses"),
              (ids["Evergreen Family Trust"], ids["Growth Fund III"], "commits to"), (ids["Late statement"], ids["Evergreen Family Trust"], "waits on")]:
        assert e in es
    assert (ids["Bank statements"], ids["Unfunded commitments"], "feeds") in es  # one source in the brief: it feeds every figure
    assert k["processes"] == [{"title": "Capital calls", "lanes": ["Data team", "Head of data"], "steps": [{"lane": "Data team", "text": "Collect statements"}, {"lane": "Head of data", "text": "Check balances"}]}]
    assert all(e["label"] in {"decides", "reads", "feeds", "commits to", "uses", "waits on"} for e in k["edges"])
    assert {t["name"]: t["count"] for t in k["things"]}["Funds"] == 1


def test_another_company_never_appears(env, tmp_path):
    c, plane = env
    seed(plane)
    EntitlementStore(tmp_path / "data").create_company("othercorp", "Other Corp", "other")
    other = PlaneStore(tmp_path / "data").plane_for("othercorp")
    H.save(other, LIVE | {"id": "th-x", "title": "Secret other thread", "iid": None, "record": {"signed_by": "Zed Other"}})
    text = json.dumps(c.get("/api/v3/knowledge").json())
    assert "Secret other thread" not in text and "Zed Other" not in text and "Capital calls" in text


def test_a_thread_without_a_signed_brief_adds_no_figures(env):
    c, plane = env
    H.save(plane, {"id": "th-new", "title": "Fresh idea", "stage": "drafting", "created": "2026-10-14T00:00:00Z", "events": [], "steps": [], "note": {"figures": [{"label": "Cash", "value": "9"}]}})
    k = c.get("/api/v3/knowledge").json()
    assert set(of(k, "usecase")) == {"Fresh idea"} and not of(k, "figure")


# ---- the office's other records: figure records, recipes, signals, rules, documents, ranked use cases ---------------------------------------------------

def seed_records(plane):
    from sh_platform.v1 import v3_figstore as FS, v3_signals as SG
    from sh_platform.v1.e1_write import org_id
    ver = {"v": 1, "status": "verified", "built_from": {"kind": "recipe", "id": "cash_by_entity"}, "reads": ["position_snapshots"], "runs": [{"at": "2026-10-13T06:00:00Z", "ok": True}],
           "tie_out": {"rule": "Cash equals the cash positions", "ok": True, "at": "2026-10-13T06:00:00Z"}}
    FS._save(plane, {"id": FS.fid("Cash"), "name": "Cash", "definition": "Cash held", "grain": [], "current_v": 1, "versions": [ver, {**ver, "v": 2, "status": "held", "reason": "did not add up"}],
                     "used_by": [{"thread": "th-live", "brief": "Capital calls", "person": "Anita Rao"}]})
    d = plane.path("dropbox")
    d.mkdir(parents=True, exist_ok=True)
    H.scan  # noqa: B018 - the file list is written directly below
    plane.path("v3").mkdir(parents=True, exist_ok=True)
    H._fp(plane).write_text(json.dumps([{"name": f"stmt{i}.csv", "arrived_at": f"2026-10-0{i}T00:00:00Z", "status": "loaded", "source": "custodian positions", "thread": None} for i in range(1, 9)]), encoding="utf-8")
    org, rid, vid = org_id(plane), wh.new_id(), wh.new_id()
    with wh.connect(plane) as con:
        uid = wh.new_id()
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,'x','Anita Rao','',true,?)", [uid, org, wh.now()])
        con.execute("insert into business_rules (id, organization_id, rule_code, rule_type, owner_user_id) values (?,?,'cash_tolerance','tolerance',?)", [rid, org, uid])
        con.execute("insert into rule_versions (id, organization_id, business_rule_id, version_number, definition_text, parameters, effective_from, approval_status, approved_by, approved_at) "
                    "values (?,?,?,1,'Cash may differ by up to 5,000 per entity','{}','2026-01-01','approved',?,?)", [vid, org, rid, uid, wh.now()])
    SG._put(plane, {"id": "sg-1", "signal": "uc01-call-arrives", "title": "A capital call has arrived", "subject": "Growth Fund III call 5", "severity": "needs", "route_to": "ops_clerk",
                    "status": "open", "at": "2026-10-13T06:00:00Z", "values": {}, "evidence": []})


def test_the_office_records_join_the_map(env):
    c, plane = env
    seed(plane)
    seed_records(plane)
    k = c.get("/api/v3/knowledge").json()
    fig, ids = of(k, "figure")["Cash"], {n["label"]: n["id"] for n in k["nodes"]}
    assert fig["status"] == "verified" and fig["versions"] == 2
    assert any("Version 1 of 2" in f["text"] and f["source"] == "Figure record" and f["at"] == "2026-10-13" for f in fig["facts"])
    assert any("held" in f["text"] for f in fig["facts"]) and "Cash by entity" in of(k, "recipe")
    es = {(e["from"], e["to"], e["label"]): e for e in k["edges"]}
    assert (ids["Cash"], ids["Cash by entity"], "built from") in es and es[(ids["Cash"], ids["Cash by entity"], "built from")]["up"] == ids["Cash by entity"]
    assert (ids["Cash"], ids["Capital calls"], "used by") in es and es[(ids["Cash"], ids["Capital calls"], "used by")]["up"] == ids["Cash"]
    assert (ids["Cash"], ids["custodian positions"], "reads") in es and all(e["why"] for e in es.values() if e["from"] == ids["Cash"])
    rule = next(n for n in k["nodes"] if n["kind"] == "rule")
    assert rule["facts"][0]["source"] == "Signed rule" and (rule["id"], ids["Anita Rao"], "signed by") in es
    assert (rule["id"], ids["Cash"], "limits") in es and (ids["Cash"], rule["id"], "checked by") in es
    sig = next(n for n in k["nodes"] if n["kind"] == "signal" and n["label"] == "A capital call has arrived")
    assert sig["fired"] == 1 and sig["facts"][0]["text"] == "Fired 1 time" and sig["facts"][0]["at"] == "2026-10-13"
    assert (sig["id"], ids["Cash"], "watches") not in es  # a signal watches a figure only when its recipe is one of the office's
    assert len([n for n in k["nodes"] if n["kind"] == "file"]) == 6  # the newest six of a source are drawn, the rest counted on the source
    assert any("8 files read" in f["text"] for f in of(k, "source")["custodian positions"]["facts"])
    assert {t["name"] for t in k["things"]} >= {"Figures", "Recipes", "Rules", "Signals"}
    assert all(e["up"] in (e["from"], e["to"]) for e in k["edges"])


def test_ranked_use_cases_appear_only_with_a_figure_the_office_has(env):
    c, plane = env
    seed(plane)
    assert not [n for n in c.get("/api/v3/knowledge").json()["nodes"] if n["id"].startswith("usecase:uc-")]
    seed_records(plane)
    k = c.get("/api/v3/knowledge").json()
    card = next((n for n in k["nodes"] if n["id"].startswith("usecase:uc-")), None)
    assert card and card["stage"] == "suggested" and card["facts"][0]["source"] == "Use case library"
    labels = {e["label"] for e in k["edges"] if card["id"] in (e["from"], e["to"])}
    assert "answers with" in labels
