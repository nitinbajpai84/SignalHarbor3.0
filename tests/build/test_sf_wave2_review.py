"""SF15: wave 2 review. One end-to-end run per company shape over SF09 to SF14b, through the real routes and the real chain, with a scripted model
(no live call, no server, synthetic data, tmp planes). Per shape: hand-off, Span's target, model draft, file, the change note's gate 1,
design drafted then signed in the same act as the blueprint, Span's suggestion (a change note opens on accept), a failed run (Flow's note and
quarantine counts), an alert (the incident note). Shapes: family office, asset management, an empty company, one person alone.
Also: no cell value from any landed file reaches any model payload, over the whole run."""
import json
import os
import re
import time
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sh_platform import warehouse as wh
from sh_platform.agents.protocols import ModelReply, ToolCall
from sh_platform.build import alerts, architecture as A, blueprint as B, blueprint_draft as BD, chain as C, contracts, design_doc, ops, proposals as P, runner
from sh_platform.build.agents import flow, modelling, routes as RT, span_model
from sh_platform.build.agents.runtime import Runtime
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from tests.build.test_sf13_routes import Ent

INTENT = "ini-" + "sf15" * 8
BID = "b" * 32
NAMES = {"architect": "Aaron Lyle", "head_of_department": "Grace Ward", "developer": "Katie Menon", "tester": "Mei Ling Chong", "ops": "Harvey Rowley"}
PEOPLE = {n.lower().replace(" ", "-"): {"name": {"value": n}, "role": {"value": "Analyst"}, "team": {"value": "Risk"}}
          for n in [*NAMES.values(), "Janet Shaw", "Daniel Kerr"]}
WHO = {"aaron": Viewer("Aaron Lyle", frozenset({"participant"})), "grace": Viewer("Grace Ward", frozenset({"approver"})),
       "katie": Viewer("Katie Menon", frozenset({"analyst"})), "mei": Viewer("Mei Ling Chong", frozenset({"owner"})),
       "harvey": Viewer("Harvey Rowley", frozenset({"owner"})), "janet": Viewer("Janet Shaw", frozenset({"company_admin"}), account_id="acct-janet"),
       "daniel": Viewer("Daniel Kerr", frozenset({"sponsor"}))}
# the two full shapes: same code, different words and columns
SHAPES = {
    "family office": dict(co="fo-e2e", industry="family office", title="Valuation chase protocol", question="Why are private fund valuations stale?",
                          measure="Stale private fund valuations", code="K12", fact="valuations", dim="funds", key="fund_id", val="nav", attr="manager",
                          cells=["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"], people=["Ann", "Ben", "Cat", "Dee", "Eve", "Fay"], source="Custodian statements"),
    "asset management": dict(co="am-e2e", industry="asset management", title="Fee reconciliation", question="Why do fees differ from the invoices?",
                             measure="Unreconciled fee share", code="K07", fact="fees", dim="mandates", key="mandate_id", val="fee", attr="desk",
                             cells=["Atlas", "Borealis", "Cedar", "Dune", "Ember", "Fjord"], people=["Gus", "Hal", "Ivy", "Jon", "Kim", "Lou"], source="Fee invoices"),
}
SECRET = "ZZ-SECRET-QQ"  # a cell value that appears only in the failing file


def _w(plane, rel, doc):
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def _r(plane, rel):
    return json.loads(plane.path(*rel.split("/")).read_text(encoding="utf-8"))


def _land(plane, source, name, text, when=None):
    plane.area("landing").mkdir(parents=True, exist_ok=True)
    f = plane.path("landing", name)
    f.write_text(text, encoding="utf-8")
    if when:
        os.utime(f, (when, when))
    return f


def _csv(head, rows):
    return ",".join(head) + "\n" + "".join(",".join(str(c) for c in r) + "\n" for r in rows)


def _seed_data(plane, s):
    k, v, a = s["key"], s["val"], s["attr"]
    ids = [f"E{i}" for i in range(1, 7)]
    fact = [[i, d, 100 + n * 10 + m, s["people"][n], f"r{m}{n}"] for m, d in enumerate(("2026-07-31", "2026-08-31")) for n, i in enumerate(ids)]  # 12 rows, 6 keys
    dim = [[i, s["cells"][n], s["people"][n]] for n, i in enumerate(ids)]
    _land(plane, s["fact"], f"{s['fact']}_2026_08.csv", _csv([k, "period_end", v, a, "ref"], fact))
    _land(plane, s["dim"], f"{s['dim']}_2026_08.csv", _csv([k, "name", a], dim))
    wh.load_bronze(plane, s["fact"], f"{s['fact']}_2026_08.csv")
    wh.load_bronze(plane, s["dim"], f"{s['dim']}_2026_08.csv")
    wh.refresh_readonly_copy(plane)


def _blueprint(s):
    code, v, k = s["code"], s["val"], s["key"]
    doc = {"version": 1, "state": "draft", "signed_by": [], "band": "now", "infra": {"warehouse": "plane", "runner": "builtin"},
           "model": {"facts": [{"name": "fact_month", "grain": f"one row per {k[:-3]} per month", "keys": ["k"], "measures": [code]}],
                     "dimensions": [{"name": f"dim_{k[:-3]}", "keys": ["k"], "attributes": [s["attr"]], "scd": 1}]},
           "lineage": [{"measure": code, "source": s["fact"].capitalize(), "fields": [v], "transform": f"sum of {v}", "mart": f"gold.{code.lower()}.{v}"},
                       {"measure": code, "source": s["dim"].capitalize(), "fields": [s["attr"]], "transform": "Not stated", "mart": f"gold.{code.lower()}.{v}"}],
           "rules": [{"measure": code, "rule": f"{v} is not empty", "severity": "block", "from": "scan"},
                     {"measure": code, "rule": "ref is unique", "severity": "block", "from": "scan"}],
           "access": [{"mart": f"gold.{code.lower()}", "may_see": None}], "schedule": []}
    doc["provenance"] = BD.marks(doc, "2026-10-01T00:00:00+00:00", {})
    return doc


def _plan(s):
    k, v, code = s["key"], s["val"], s["code"]
    ent = k[:-3]
    return {"silver_model": {"dimensions": [{"name": f"dim_{ent}", "type": "scd2", "business_key": [k], "source": [s["dim"]], "tracked_attributes": [s["attr"]]}],
                             "facts": [{"name": "fact_month", "grain": [k, "period_end"], "source": [s["fact"]],
                                        "foreign_keys": [{"dimension": f"dim_{ent}", "on": k}]}]},
            "gold_contract": {"marts": [{"name": v, "source_fact": "fact_month", "field": v, "op": "sum", "date": "period_end", "measure": code}]},
            "rationale": {"entities": {f"dim_{ent}": {"because": "the manager changes", "from": [s["dim"]]}}}}


def _intent(s, who):
    names = NAMES if who == "team" else {r: "Janet Shaw" for r in NAMES}
    return {"id": INTENT, "type": "initiative", "title": s["title"], "question": s["question"], "areas": ["risk"], "refs": {"wall_session_ids": ["s1"]},
            "links": {"build": "build:a1"}, "people": {"organiser": {"account_id": "acct-janet", "name": "Janet Shaw"}},
            "build_handoff": {"by": {"name": "Janet Shaw"}, "at": "2026-09-02T00:00:00+00:00",
                              "catalogue": [{"id": s["code"], "name": s["measure"], "priority": "must"}],
                              "processes": [{"id": "p1", "name": "Monthly chase", "owner": "Harvey Rowley"}],
                              "source_map": [{"id": "s1", "name": s["source"], "zone": "p1", "strategic": True}]}}, names


class Script:
    """The scripted model: one reply per kind of question, chosen from the question in the payload. Keeps every payload it was sent."""

    def __init__(self, s, plane):
        self.s, self.plane, self.sent, self.reviews = s, plane, [], 0

    def complete(self, module_id, messages, tools=None):
        text = json.dumps(messages)
        self.sent.append(text)
        s, has_tool = self.s, any(m.get("role") == "tool" for m in messages)
        if "Draft the target architecture" in text:
            return ModelReply(json.dumps({"placements": [{"id": "history-mart", "kind": "gold", "label": "Fee history mart", "view": "data",
                                                          "interfaces": [{"to": f"gold:{s['code'].lower()}", "kind": "reads"}], "why": "keeps the monthly history"}],
                                          "lines": ["One new mart keeps the monthly history beside the existing one."]}), [])
        if "Write the decision records and the risks" in text:
            place = next((x.get("placement") for n in C.all_notes(self.plane) for x in n["sections"]["decisions"] if x.get("placement")), None)
            dec = [{"placement": place, "options": ["Main file", "Restricted file"], "chosen": "Main file", "why": "no access list is recorded for this mart",
                    "follows": "Query tools read it from the read-only copy", "provenance": [f"gold:{s['code'].lower()}"]}] if place else []
            return ModelReply(json.dumps({"decisions": dec, "risks": ["Late files delay the mart"]}), [])
        if "Write the prose sections of the design document" in text:
            return ModelReply(json.dumps({"purpose": ["This work answers the charter question."], "target": ["One mart per measure."], "model": ["A star with one fact."],
                                          "decisions": [], "risks": ["Late files delay the mart."]}), [])
        if "Write the silver model" in text or "silver_model" in text and "errors" in text:
            return ModelReply(json.dumps(_plan(s)), [])
        if "Suggest at most three modelling changes" in text and not has_tool:
            self.reviews += 1
            args = {"subject": "fact_month", "measure": s["code"], "technique": "Periodic snapshot fact", "title": "Snapshot the month",
                    "what": "Keep one snapshot row per entity per month.", "why": "The monthly figure is read at month end.",
                    "evidence": {"fields": [s["key"]]}, "impact": {"contracts": [s["fact"]], "marts": [f"gold.{s['code'].lower()}"]},
                    "alternatives": [{"option": "Transaction fact", "why_not": "there are no events"}], "effort": "medium"}
            return ModelReply("", [ToolCall("propose", {"kind": "model_change", "args": args})])
        if "Explain this run" in text:
            return ModelReply("The run failed its checks. Some rows were set aside and the gold tables were not built.", [])
        if "likely cause of this alert" in text:
            return ModelReply("The latest file has empty values. Ask the sender for a corrected file.", [])
        return ModelReply("Done.", [])


def _world(tmp_path, monkeypatch, shape):
    """(plane, as_, model, s). `shape` is a SHAPES key, 'empty' or 'alone' (the family office with one person in every role)."""
    s = SHAPES.get(shape) or SHAPES["family office"]
    plane = PlaneStore(tmp_path).create(s["co"] if shape in SHAPES else shape)
    model = Script(s, plane)
    me = {"v": WHO["aaron"]}
    app = FastAPI()
    C.install(app)
    app.include_router(RT.router)
    app.include_router(B.router)
    app.include_router(P.router)
    app.state.entitlements, app.state.build_model_factory = Ent(), (lambda p: model)

    @app.middleware("http")
    async def company(request: Request, call_next):
        request.state.company_id = plane.company_id
        return await call_next(request)
    for mod in (C, A, RT, B, P):
        monkeypatch.setattr(mod, "_plane", lambda r: plane)
        monkeypatch.setattr(mod, "_viewer", lambda r: me["v"])
    monkeypatch.setattr(B, "_name", lambda r: me["v"].name)
    monkeypatch.setattr(RT, "_spawn", lambda fn: fn())  # background work runs inline
    from sh_platform.build.agents import runtime as R
    monkeypatch.setattr(R, "runtime_for_plane", lambda pl, viewer=None: Runtime(model, company_id=pl.company_id, company_name="Synthetic Co", industry=s["industry"]))
    if shape != "empty":
        who = "alone" if shape == "alone" else "team"
        intent, names = _intent(s, who)
        people = PEOPLE if who == "team" else {"janet-shaw": PEOPLE["janet-shaw"]}
        _seed_data(plane, s)
        _w(plane, f"intents/m2_baseline/{BID}/baseline.json", {"state": "signed", "created_at": "2026-09-01"})
        _w(plane, f"intents/m2_baseline/{BID}/kpis.json", [{"id": s["code"], "name": {"value": s["measure"], "mark": "stated"},
                                                         "technical": {"grain": {"value": "one row per entity per month", "mark": "stated"},
                                                                       "calculation": {"value": f"sum of {s['val']}", "mark": "stated"}}}])
        _w(plane, "build/blueprint.json", _blueprint(s))
        contracts.ensure(plane)  # the pipelines exist when the change note opens (the developer room has been visited)
        _w(plane, "build/prove.json", {"band": "now", "release": {"state": "draft"}, "measures": [
            {"code": s["code"], "periods": [{"period": "2026-07", "result": "match"}], "uat": {"state": "signed", "by": "X", "at": "2026-09-05T00:00:00+00:00"}}]})
        _w(plane, "intents/m3_connect/outcomes/o1.json", {"outcome_id": "o1", "kind": "plan", "assessment_id": "a1", "signed_at": "2026-09-01T00:00:00+00:00",
                                                          "accepted_risks": [{"measures": [s["code"]], "text": "Statements arrive late"}]})
        _w(plane, "intents/m1_intent/roles/s1.json", {"roles": {}, "names": names})
        _w(plane, "intents/hypotheses/h1.json", {"id": "h1", "origin": {"kind": "initiative", "ref": INTENT}, "versions": [
            {"belief": "Chasing lowers the share", "measure": {"id": s["code"], "name": s["measure"]}, "baseline": {"value": 0.33, "periods": ["2026-05"]},
             "target": {"value": 0.1, "by": "2026-11-30"}, "review_date": "2026-11-30"}]})
        from sh_platform.intents import store as istore
        from sh_platform.profile import store as pstore
        monkeypatch.setattr(istore, "read_index", lambda p: [{"id": INTENT, "type": "initiative"}])
        monkeypatch.setattr(istore, "read_intent", lambda p, i: intent if i == INTENT else None)
        real = pstore.raw
        monkeypatch.setattr(pstore, "raw", lambda p: {**real(p), "people": people})  # the real empty profile, with the team in it

    def as_(who):
        me["v"] = WHO[who]
        return TestClient(app)
    return plane, as_, model, s


def _bp(plane):
    return _r(plane, "build/blueprint.json")


@pytest.fixture(params=sorted(SHAPES))
def full(request, tmp_path, monkeypatch):
    return _world(tmp_path, monkeypatch, request.param)


def _wait_draft(c, tries=120):
    """The model draft runs in its own thread; poll the route as the page does."""
    for _ in range(tries):
        d = c.get("/api/company/build/span/model-draft").json()
        if d["state"] != "drafting":
            return d
        time.sleep(0.25)
    return d


def _owners(plane, as_, who="grace"):
    for cid in _r(plane, "build/changes/C-0001.json")["components"]["added"]:
        if cid.startswith("gold:"):
            as_(who).put(f"/api/company/build/architecture/components/{cid}", json={"owner": "harvey-rowley"})


def _bad_file(plane, s):
    """The next landing: 6 empty values, one key twice (two rows), the rest fine; one cell holds a value only this file has."""
    rows = [["E1", "2026-09-30", 10, SECRET, "x1"], ["E1", "2026-09-30", 11, "x", "x1"]] + [[f"E{i}", "2026-09-30", "", "x", f"x{i}"] for i in range(2, 8)] + \
           [["E8", "2026-09-30", 20, "x", "x8"], ["E9", "2026-09-30", 30, "x", "x9"], ["E10", "2026-09-30", 40, "x", "xa"], ["E11", "2026-09-30", 50, "x", "xb"]]
    _land(plane, s["fact"], f"{s['fact']}_2026_09.csv", _csv([s["key"], "period_end", s["val"], s["attr"], "ref"], rows), (datetime.now() + timedelta(days=1)).timestamp())


def test_the_whole_chain_with_span_and_flow(full, monkeypatch):
    plane, as_, model, s = full
    # 1. the hand-off opens the change note; gate 1 is Span's (decision lines and risks), the rule lines stay
    ch = as_("aaron").get("/api/company/build/changes").json()["changes"]
    assert [c["id"] for c in ch] == ["C-0001"] and ch[0]["step"] == 1
    note = as_("aaron").get("/api/company/build/changes/C-0001").json()
    assert note["can_act"] and note["drafting_note"] is None
    assert note["sections"]["what_changes"] and model.sent  # the note has its rule lines, and Span was asked
    assert "Late files delay the mart" in [x["text"] for x in note["sections"]["risks"]]
    # 2. room 0: the target. Nothing yet, then the architect asks Span; nobody else may
    first = as_("mei").get("/api/company/build/span/target").json()
    assert first["draft"] is None and first["empty"]
    assert as_("katie").post("/api/company/build/span/target", json={}).status_code == 403
    r = as_("aaron").post("/api/company/build/span/target", json={"intent_id": INTENT})
    assert r.status_code == 200 and r.json()["fallback"] is False and r.json()["saved"], r.text
    got = as_("mei").get("/api/company/build/span/target").json()
    assert "history-mart" in json.dumps(got)
    # 3. a person states the fact's key first; Span's draft is then filed around it and leaves it as it is (rule 7)
    assert as_("aaron").put("/api/company/build/blueprint", json={"path": "model.facts.0.keys", "value": ["ref"]}).status_code == 200
    # the model draft: runs, is ready, and files as Span's guess; a second filing is refused
    assert as_("aaron").post("/api/company/build/span/model-draft", json={}).status_code == 202
    d = _wait_draft(as_("aaron"))
    assert d["state"] == "ready" and d["fallback"] is False, d
    assert all(c.get("group_size", 5) >= 5 for c in d["counts"])
    f = as_("aaron").post(f"/api/company/build/span/model-draft/{d['id']}/file")
    assert f.status_code == 200 and f.json()["state"] == "filed" and f.json()["filed"]["skipped"]
    assert as_("aaron").post(f"/api/company/build/span/model-draft/{d['id']}/file").status_code == 409
    bp = _bp(plane)
    assert [x["name"] for x in bp["model"]["facts"]] == ["fact_month"] and bp["model"]["dimensions"][0]["scd"] == 2
    assert bp["model"]["facts"][0]["keys"] == ["ref"] and bp["provenance"]["model.facts.0.keys"] == {**bp["provenance"]["model.facts.0.keys"], "mark": "stated", "by": "Aaron Lyle"}
    assert bp["state"] == "draft" and bp["rules"]  # filing signs nothing and leaves the rules
    spans = [m for p, m in bp["provenance"].items() if p.startswith(("model", "lineage")) and m["mark"] != "stated"]
    assert spans and all(m["mark"] == "guessed" and m["by"] == "Span" for m in spans)
    # 4. room 1: the design document, Span's prose over the records, a draft
    r = as_("aaron").post("/api/company/build/design/redraft")
    assert r.status_code == 202, r.text  # runs beside the request (inline in the test)
    d = as_("mei").get("/api/company/build/design").json()
    assert d["fallback"] is False and d["doc"]["state"] == "draft" and set(d["diagrams"]) <= set(RT.KINDS) and d["diagrams"]
    assert d["doc"]["sections"]["purpose"][0]["text"] == "This work answers the charter question." and not d.get("diagram_errors")
    page = as_("mei").get("/api/company/build/design/download")
    assert page.status_code == 200 and "attachment" in page.headers["content-disposition"] and "<script" not in page.text.lower() and "http" not in page.text.split("<body", 1)[-1].replace("https://www.w3.org/2000/svg", "")
    # 5. approval: the head of department signs the change, the blueprint and the design in one act; Span reviews once after
    assert as_("aaron").post("/api/company/build/changes/C-0001/send").json()["step"] == 2
    _owners(plane, as_)
    assert as_("aaron").post("/api/company/build/changes/C-0001/approve").status_code == 403
    r = as_("grace").post("/api/company/build/changes/C-0001/approve")
    assert r.status_code == 200 and r.json()["state"] == "building", r.text
    doc = design_doc.read(plane)
    assert doc["state"] == "signed" and doc["signed_by"][0]["name"] == "Grace Ward" and _bp(plane)["state"] == "signed" and plane.path("build", "design", "design.v1.json").is_file()
    v1 = plane.path("build", "design", "design.v1.json").read_bytes()
    assert as_("aaron").put("/api/company/build/design/lines", json={"section": "purpose", "index": 0, "text": "Late edit"}).status_code == 200
    assert plane.path("build", "design", "design.v1.json").read_bytes() == v1  # the signed version is never touched
    nxt = design_doc.read(plane)
    assert nxt["version"] == 2 and nxt["state"] == "draft" and nxt["sections"]["purpose"][0]["mark"] == "stated"  # an edit opens the next draft
    # 6. the suggestion: filed to the blueprint signer by the review after the signature; accepting opens a change note and writes a decision
    assert model.reviews >= 1
    mine = as_("grace").get("/api/company/build/proposals").json()
    items = mine if isinstance(mine, list) else mine.get("proposals") or mine.get("items") or []
    assert len(items) == 1 and items[0]["kind"] == "model_change" and items[0]["by_agent"] == "Span" and items[0]["to"] == "Grace Ward", mine
    pid = items[0]["id"]
    assert [x["can_decide"] for x in as_("katie").get("/api/company/build/proposals").json()["proposals"]] == [False]  # an analyst reads it, Grace decides
    assert [x["can_decide"] for x in as_("grace").get("/api/company/build/proposals").json()["proposals"]] == [True]
    assert as_("mei").get("/api/company/build/proposals").json()["proposals"] == []  # a tester is not shown it
    assert as_("katie").post(f"/api/company/build/proposals/{pid}/accept").status_code in (403, 404)  # not the addressee
    acc = as_("grace").post(f"/api/company/build/proposals/{pid}/accept")
    assert acc.status_code == 200 and acc.json()["state"] == "accepted", acc.text
    opened = acc.json()["result"]["change_id"]
    n2 = _r(plane, f"build/changes/{opened}.json")
    assert opened == "C-0002" and n2["source"]["id"] == pid and n2["state"] == "with_architect"
    assert any(t.startswith("Chose Periodic snapshot fact") for t in [x["text"] for x in modelling.decisions(plane)])
    assert _bp(plane)["model"]["dimensions"][0]["scd"] == 2  # accepting changed no model; a person builds the change
    # 7. a failed run: Flow's note, the counts of rows set aside, a model_change naming Span for the grain
    _bad_file(plane, s)
    run = runner.run_pipeline(plane, next(c for c in contracts.ensure(plane) if c["source"] == s["fact"]))
    assert run["status"] == "failed" and run["not_run"] == []
    held = {(q["field"], q["count"]) for q in run["quarantined"]}
    assert (s["val"], 6) in held and ("ref", 2) in held
    r = as_("katie").get(f"/api/company/build/flow/runs/{run['id']}")
    assert r.status_code == 200, r.text
    note = r.json()
    assert note["fallback"] is False and note["text"].startswith("The run failed")
    lines = " ".join(note["lines"])
    assert "6 rows set aside" in lines and "fewer than five" in lines and note["first_missing_link"] == "checks"
    assert as_("katie").post(f"/api/company/build/flow/runs/{run['id']}/explain").status_code == 200
    con = wh.open_readonly(plane)
    try:
        assert con.execute("select count(*) from quarantine." + s["fact"]).fetchone()[0] == 8
    finally:
        con.close()
    # 8. the alert: Flow's incident note goes to the person the alert names; accepting acknowledges, never closes
    ops.build(plane, WHO["harvey"], date.today())  # the Watcher's daily read stores the alerts
    open_alerts = [a for a in alerts._read(plane) if a.get("state") == "open" and a.get("source") == s["fact"]]
    assert open_alerts, "the failed run raised no alert"
    got = as_("katie").get("/api/company/build/flow/incidents").json()
    inc = [i["note"] for i in got["incidents"] if open_alerts[0]["id"] in (i.get("alert"), i["note"].get("alert_id"))]  # SF09b: the dimension's own pipeline has alerts too
    assert inc and inc[0]["kind"] == "incident_note" and inc[0]["to"] == "Katie Menon", got
    ip = inc[0]["id"]
    assert as_("mei").post(f"/api/company/build/proposals/{ip}/accept").status_code in (403, 404)
    assert as_("katie").post(f"/api/company/build/proposals/{ip}/accept").status_code == 200
    now_open = [a for a in alerts._read(plane) if a["id"] == open_alerts[0]["id"]][0]
    assert now_open["state"] != "open" and now_open["state"] != "closed"
    # 9. nothing from any landed file reached the model: no cell value, no file name, in any payload of the whole run
    blob = "\n".join(model.sent)
    leaked = [v for v in (*s["cells"], *s["people"], SECRET) if re.search(rf"{re.escape(v)}", blob)]  # whole words: "Eve" is not "every"
    assert model.sent and not leaked, leaked
    assert f"{s['fact']}_2026" not in blob and ".csv" not in blob


def test_an_empty_company_shows_empty_states_everywhere(tmp_path, monkeypatch):
    plane, as_, model, _ = _world(tmp_path, monkeypatch, "empty")
    c = as_("janet")
    assert c.get("/api/company/build/changes").json()["changes"] == []
    t = c.get("/api/company/build/span/target").json()
    assert t["draft"] is None and t["fallback"] is False and t["empty"]
    assert c.get("/api/company/build/span/model-draft").json()["state"] == "none"
    d = c.get("/api/company/build/design").json()
    assert d["doc"] is None and d["empty"] and d["diagrams"] == {}
    assert c.get("/api/company/build/design/download").status_code == 200
    assert c.get("/api/company/build/flow/incidents").json() == {"incidents": [], "fallback": False}
    assert c.get("/api/company/build/proposals").json()["proposals"] == []
    assert c.get(f"/api/company/build/flow/runs/{'a' * 32}").status_code == 404
    assert c.post("/api/company/build/design/redraft").status_code == 409
    assert c.post("/api/company/build/span/target", json={}).status_code == 422  # no Initiative to draft for
    assert c.post("/api/company/build/span/review").json() == {"proposals": [], "fallback": False, "message": None}
    assert flow.explain_run(plane, "0" * 32, Runtime(model)) is None
    r = c.post("/api/company/build/span/model-draft", json={})  # asked anyway: a plain refusal, no failed draft and no Pulse line
    assert r.status_code == 409 and r.json()["error"] == "nothing_to_draft", r.text
    assert c.get("/api/company/build/span/model-draft").json()["state"] == "none"
    assert model.sent == []  # SF09b: neither the review nor the draft asks the model anything on an empty company


def test_a_span_filed_model_lets_the_runner_check_the_grain(tmp_path, monkeypatch):
    plane, as_, model, s = _world(tmp_path, monkeypatch, "family office")
    as_("aaron").get("/api/company/build/changes")  # the change note names Aaron as the architect
    assert as_("aaron").post("/api/company/build/span/model-draft", json={}).status_code == 202
    assert as_("aaron").post(f"/api/company/build/span/model-draft/{_wait_draft(as_('aaron'))['id']}/file").status_code == 200
    _bad_file(plane, s)
    run = runner.run_pipeline(plane, next(c for c in contracts.ensure(plane) if c["source"] == s["fact"]))
    assert run["not_run"] == []


def test_a_second_model_draft_after_filing_still_sees_every_source(tmp_path, monkeypatch):
    plane, as_, model, s = _world(tmp_path, monkeypatch, "family office")
    as_("aaron").get("/api/company/build/changes")
    for _ in range(2):
        assert as_("aaron").post("/api/company/build/span/model-draft", json={}).status_code == 202
        d = _wait_draft(as_("aaron"))
        assert d["state"] == "ready", d
        as_("aaron").post(f"/api/company/build/span/model-draft/{d['id']}/file")


def test_one_person_alone_can_draft_and_run_but_cannot_approve_their_own_design(tmp_path, monkeypatch):
    from sh_platform.consume import cards
    monkeypatch.setattr(cards, "data_owner", lambda p, code: "Janet Shaw")
    plane, as_, model, s = _world(tmp_path, monkeypatch, "alone")
    me = as_("janet")
    note = me.get("/api/company/build/changes/C-0001") if me.get("/api/company/build/changes").json()["changes"] else None
    assert note is not None and note.json()["can_act"]
    assert me.post("/api/company/build/span/target", json={"intent_id": INTENT}).json()["saved"]
    assert me.post("/api/company/build/span/model-draft", json={}).status_code == 202
    draft = _wait_draft(me)
    assert draft["state"] == "ready" and me.post(f"/api/company/build/span/model-draft/{draft['id']}/file").status_code == 200
    assert me.post("/api/company/build/design/redraft").status_code == 202
    assert me.post("/api/company/build/changes/C-0001/send").json()["step"] == 2
    r = me.post("/api/company/build/changes/C-0001/approve")  # C25: one person may hold two gates except approving their own architecture
    assert r.status_code == 403 and r.json()["code" if "code" in r.json() else "error"] == "own_design"
    assert design_doc.read(plane)["state"] == "draft" and _bp(plane)["state"] == "draft"
    rv = me.post("/api/company/build/span/review").json()  # the data owner is the addressee, so a review still files for her
    assert [p["to"] for p in rv["proposals"]] == ["Janet Shaw"] and rv["proposals"][0]["by_agent"] == "Span"
    pid = rv["proposals"][0]["id"]
    assert me.post(f"/api/company/build/proposals/{pid}/accept").status_code in (200, 409)
    _bad_file(plane, s)
    run = runner.run_pipeline(plane, next(c for c in contracts.ensure(plane) if c["source"] == s["fact"]))
    assert run["status"] == "failed" and me.get(f"/api/company/build/flow/runs/{run['id']}").json()["text"].startswith("The run failed")
    ops.build(plane, WHO["janet"], date.today())
    inc = [i["note"] for i in me.get("/api/company/build/flow/incidents").json()["incidents"]]
    assert inc and inc[0]["to"] == "Janet Shaw"
    assert me.post(f"/api/company/build/proposals/{inc[0]['id']}/accept").status_code == 200
