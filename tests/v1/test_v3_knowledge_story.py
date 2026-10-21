"""Harbor 3.0 Knowledge, the use case story: a small office with three use cases, two of which share a figure. The story layers top to bottom, the shared marks,
the domain grouping, the logical relations, the physical path of one KPI, the decisions list and permissions. Real routes, store and permissions; synthetic data only."""
import json
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_figstore as FS  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_knowledge_story as S  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from sh_platform.v1.e1_write import org_id  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

A, B, C = "t-a", "t-b", "t-c"
ASSUME = "The rate is the day's WMR fixing."


def login(tmp_path, data, who="anita.rao.evergreen@example.test"):
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    assert c.post("/api/auth/login", json={"email": who, "password": pw[who]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    return c


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    S._KEPT.clear()
    S._SIG.clear()
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    return login(tmp_path, data), PlaneStore(data).plane_for("evergreen"), data


def thread(tid, title, stage, kpis, started_by, figs=None, **more):
    return {"id": tid, "title": title, "stage": stage, "created": "2026-10-21T08:00:00Z", "started_by": started_by, "pid": "prj-" + tid, "steps": [],
            "events": [{"at": "2026-10-21T08:00:00Z", "kind": "person", "text": f"Question of {title}", "by": "You"},
                       {"at": "2026-10-21T08:05:00Z", "kind": "decision_done", "text": "Confirmed.", "by": "Harbor"}],
            "record": {"signed_by": started_by, "role": "sponsor", "signed_at": "2026-10-21T08:05:00+00:00", "version": 1},
            "figs": {k: {"id": FS.fid(k), "v": 1, "reused": r} for k, r in kpis.items()}, "figures": figs or [], "rules": ["Over 500,000 needs Daniel"] if tid == A else [],
            "sources": ["Bank statements"], "note": {"figures": [{"label": "x", "value": "1"}]} if stage == "live" else None, **more}


def figure(name, rid, reads, used_by, status="verified"):
    ver = {"v": 1, "status": status, "built_from": {"kind": "recipe", "id": rid}, "reads": reads, "approved_by": "Anita Rao", "runs": [{"at": "2026-10-21T09:00:00Z", "ok": True, "rows": 3}],
           "assumptions": [{"text": ASSUME, "source": "person", "at": "x"}, {"text": "It may read only: cash_movements, instruments.", "source": "ASSUMPTIONS A8", "at": "x"}]}
    FS._save(plane_of[0], {"id": FS.fid(name), "name": name, "definition": f"{name} means something", "grain": [], "current_v": 1, "versions": [ver],
                           "used_by": [{"thread": t, "brief": t, "person": "x"} for t in used_by]})


plane_of: list = []


def seed(plane):
    plane_of[:] = [plane]
    H.save(plane, thread(A, "Can Holdings pay the call?", "live", {"Cash after calls due": False, "Call payment status": False}, "Anita Rao", figs=[
        {"kpi": "Cash after calls due", "table": "gold_a_cash_after_calls", "words": "cash after calls", "rows": 6, "ok": True},
        {"kpi": "Call payment status", "table": "gold_a_call_payment_status", "words": "call payment status", "rows": 11, "ok": True}]))
    H.save(plane, thread(B, "Log a call notice", "decision2", {"Call payment status": True}, "Daniel Foo"))  # reuses the figure of A: it has no table of its own
    H.save(plane, thread(C, "Net worth note", "live", {"Net worth": False}, "Daniel Foo", figs=[{"kpi": "Net worth", "table": "gold_c_net_worth", "words": "net worth", "rows": 4, "ok": True}]))
    H.save(plane, thread("t-gone", "Dropped", "discarded", {}, "Daniel Foo"))
    figure("Cash after calls due", "cash_after_calls", ["cash_movements", "bank_accounts", "business_rules"], [A])
    figure("Call payment status", "call_payment_status", ["cash_movements", "instruments"], [A, B])
    figure("Net worth", "net_worth", ["position_snapshots"], [C])
    org, uid, rid, vid = org_id(plane), wh.new_id(), wh.new_id(), wh.new_id()
    with wh.connect(plane) as con:
        con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,'x','Daniel Foo','',true,?)", [uid, org, wh.now()])
        con.execute("insert into business_rules (id, organization_id, rule_code, rule_type, owner_user_id) values (?,?,'cash_buffer','policy',?)", [rid, org, uid])
        con.execute("insert into rule_versions (id, organization_id, business_rule_id, version_number, definition_text, parameters, effective_from, approval_status, approved_by, approved_at) "
                    "values (?,?,?,2,'Keep a 250,000 USD cash buffer per entity','{}','2026-01-01','approved',?,?)", [vid, org, rid, uid, wh.now()])
        e1, e2 = wh.new_id(), wh.new_id()
        for e, code in ((e1, "EG-T"), (e2, "EG-H")):
            con.execute("insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency, active_from) values (?,?,?,?,'USD','2020-01-01')", [e, org, code, code])
    S._KEPT.clear()


def get(c, path):
    r = c.get("/api/v3/knowledge" + path)
    assert r.status_code == 200, r.text
    return r.json()


def by_id(items):
    return {i["id"]: i for i in items}


def test_the_story_runs_from_who_asked_to_the_sources(env):
    c, plane, _ = env
    seed(plane)
    s = get(c, f"/usecase/{A}")
    assert s["who"] == {"name": "Anita Rao", "role": "analyst, head of data", "at": "2026-10-21"} and s["asked"] == "Question of Can Holdings pay the call?"
    assert s["stage_label"] == "Live" and s["domain"] == {"id": "cash", "name": "Capital calls and cash"} and s["conversation"] == f"/v3/thread/{A}"
    kinds = {i["kind"] for i in s["decisions"]}
    assert {"brief", "rule", "brule", "assumption"} <= kinds
    brief = next(i for i in s["decisions"] if i["kind"] == "brief")
    assert brief["sub"] == "Anita Rao · version 1"
    rule = by_id(s["decisions"])["rule:cash_buffer"]  # the signed rule the recipe's SQL reads, with its version and signer
    assert rule["sub"] == "Rule · version 2 · Daniel Foo" and {"k": "What it says", "v": "Keep a 250,000 USD cash buffer per entity"} in rule["detail"]
    assert any(i["label"] == "Over 500,000 needs Daniel" for i in s["decisions"] if i["kind"] == "brule")
    asm = next(i for i in s["decisions"] if i["kind"] == "assumption" and "WMR" in i["label"])
    assert asm["sub"] == "Assumed · You said"
    assert [i["label"] for i in s["decisions"] if i["kind"] == "assumption"] and any(i["label"] == "It may read only: cash movements, instruments." for i in s["decisions"]), [i["label"] for i in s["decisions"]]  # a table is named in the office words
    assert [(k["label"], k["status"]) for k in s["kpis"]] == [("Call payment status", "verified"), ("Cash after calls due", "verified")]
    kpi = by_id(s["kpis"])["kpi:fig-cash-after-calls-due"]
    assert kpi["links"] == [{"label": "Open the figure page", "to": "/v3/knowledge/figures/fig-cash-after-calls-due"}]
    assert {"k": "Built from", "v": "recipe Cash after calls due"} in kpi["detail"]
    assert sorted(i["label"] for i in s["gold"]) == ["call payment status", "cash after calls"]  # the rows are counted from the warehouse, which has no such table here: none are shown
    assert {i["id"] for i in s["silver"]} == {"silver:cash_movements", "silver:bank_accounts", "silver:business_rules", "silver:instruments"}
    assert "cash movements" in {i["label"] for i in s["silver"]} and all(" " in i["label"] or "_" not in i["label"] for i in s["silver"])
    assert [b["label"] for b in s["bronze"]] == ["Bank statements"]
    assert {u["kind"] for u in s["used_by"]} == {"board", "note", "signal"}
    ids = {i["id"] for k in ("decisions", "kpis", "gold", "silver", "bronze", "used_by") for i in s[k]}
    assert s["edges"] and all(a in ids and b in ids for a, b in s["edges"])
    assert ["gold:gold_a_cash_after_calls", "kpi:fig-cash-after-calls-due"] in [list(e) for e in s["edges"]]
    assert ["rule:cash_buffer", "kpi:fig-cash-after-calls-due"] in [list(e) for e in s["edges"]]
    assert ["silver:bank_accounts", "gold:gold_a_cash_after_calls"] in [list(e) for e in s["edges"]]
    assert get(c, f"/usecase/{A}") == s  # the same order every time


def test_a_figure_two_use_cases_share_is_marked_on_both(env):
    c, plane, _ = env
    seed(plane)
    a, b = get(c, f"/usecase/{A}"), get(c, f"/usecase/{B}")
    shared = {"id": B, "title": "Log a call notice"}
    assert by_id(a["kpis"])["kpi:fig-call-payment-status"]["shared"] == [shared]
    assert by_id(a["kpis"])["kpi:fig-cash-after-calls-due"]["shared"] == []  # only A uses it
    assert by_id(b["kpis"])["kpi:fig-call-payment-status"]["shared"] == [{"id": A, "title": "Can Holdings pay the call?"}]
    assert by_id(a["silver"])["silver:cash_movements"]["shared"] == [shared] and by_id(a["silver"])["silver:bank_accounts"]["shared"] == []
    assert by_id(a["gold"])["gold:gold_a_call_payment_status"]["shared"] == [shared]  # B answers from A's ready table; it has none of its own
    assert by_id(b["gold"])["gold:gold_a_call_payment_status"]["shared"] == [{"id": A, "title": "Can Holdings pay the call?"}]
    assert by_id(a["decisions"])["rule:cash_buffer"]["shared"] == []  # B reads no rule
    assert by_id(a["bronze"])["bronze:bank-statements"]["shared"] == [shared, {"id": C, "title": "Net worth note"}]  # the brief's source is named by all three


def test_use_cases_group_by_the_domain_of_their_recipes(env):
    c, plane, _ = env
    seed(plane)
    u = get(c, "/usecases")
    assert u["total"] == 3  # the discarded thread is left out
    assert [(g["domain"], g["name"], [i["title"] for i in g["items"]]) for g in u["groups"]] == [
        ("cash", "Capital calls and cash", ["Can Holdings pay the call?", "Log a call notice"]), ("hold", "Holdings and risk", ["Net worth note"])]
    assert [d["id"] for d in u["domains"]] == ["cash", "invest", "hold", "report", "operate", "family", "office", "other"]
    assert next(i for g in u["groups"] for i in g["items"] if i["id"] == B)["live"] is False
    assert S._domain_of(["cash_after_calls", "call_payment_status", "net_worth"]) == "cash" and S._domain_of([]) == "other"
    d = get(c, "/domain/cash")
    assert d["name"] == "Capital calls and cash" and [x["id"] for x in d["usecases"]] == [A, B] and d["people"] == 2
    kp = {i["label"]: i["cols"] for i in d["rows"]["kpis"]["items"]}
    assert kp == {"Call payment status": [0, 1], "Cash after calls due": [0]}  # the shared figure spans both columns
    assert {i["label"]: i["cols"] for i in d["rows"]["silver"]["items"]}["cash movements"] == [0, 1]
    assert d["rows"]["gold"]["items"] and [o["id"] for o in d["others"] if o["count"]] == ["hold"]
    assert get(c, "/domain/office")["usecases"] == []
    assert c.get("/api/v3/knowledge/domain/nowhere").status_code == 404 and c.get("/api/v3/knowledge/usecase/nope").status_code == 404


def test_the_logical_model_has_plain_relations_and_the_kpis_that_read_each_object(env):
    c, plane, _ = env
    seed(plane)
    m = get(c, "/model/logical")
    objs = by_id([{**o, "id": o["id"]} for o in m["objects"]])
    assert {"entity", "bank_account", "family_member", "ownership", "position", "cash_movement", "commitment", "document"} <= set(objs)
    rel = {(o["id"], r["to"]): r["label"] for o in m["objects"] for r in o["relations"]}
    assert rel[("entity", "bank_account")] == "banks with" and rel[("ownership", "entity")] == "a share of" and rel[("position", "portfolio")] == "held in"
    assert rel[("family_member", "ownership")] == "holds" and rel[("document", "instrument")] == "evidence for"
    assert all(r["to_label"] for o in m["objects"] for r in o["relations"]) and objs["cash_movement"]["about"] == "calls, payments, transfers"
    assert objs["entity"]["count"] == 2 and objs["cash_movement"]["table"] == "cash movements"
    assert {k["name"] for k in objs["cash_movement"]["kpis"]} == {"Cash after calls due", "Call payment status"}
    assert [k["name"] for k in objs["position"]["kpis"]] == ["Net worth"] and objs["document"]["kpis"] == []
    assert any(p["label"] == "Entity name" for p in objs["entity"]["properties"])


def test_the_physical_model_lights_one_kpis_path(env):
    c, plane, _ = env
    seed(plane)
    p = get(c, "/model/physical")
    assert p["path"] is None and p["picked"] is None
    assert [k["id"] for k in p["kpis"]["items"]] == ["fig-call-payment-status", "fig-cash-after-calls-due", "fig-net-worth"]
    assert {g["label"] for g in p["gold"]["items"]} == {"cash after calls", "call payment status", "net worth"}
    assert p["silver"]["total"] == len(p["silver"]["items"]) and "gold_a_cash_after_calls" not in json.dumps(p["silver"])
    one = get(c, "/model/physical?kpi=fig-cash-after-calls-due")
    assert one["path"] == {"gold": ["gold:gold_a_cash_after_calls"], "silver": ["silver:bank_accounts", "silver:business_rules", "silver:cash_movements"], "bronze": ["bronze:bank-statements"]}
    assert one["picked"]["usecases"] == [{"id": A, "title": "Can Holdings pay the call?", "who": "Anita Rao"}]
    assert {u["kind"] for u in one["picked"]["used_by"]} == {"board", "note", "signal"}  # the pack signal that watches cash after calls
    shared = get(c, "/model/physical?kpi=fig-call-payment-status")  # a shared figure: its path follows both use cases
    assert [u["id"] for u in shared["picked"]["usecases"]] == [A, B] and shared["path"]["gold"] == ["gold:gold_a_call_payment_status"]
    assert get(c, "/model/physical?kpi=nothing")["path"] is None


def test_decisions_lists_rules_decisions_and_assumptions_with_the_use_cases_they_affect(env):
    c, plane, _ = env
    seed(plane)
    d = get(c, "/decisions")
    items = by_id(d["items"])
    assert d["counts"]["rule"] >= 2 and d["counts"]["decision"] >= 3 and d["counts"]["assumption"] >= 2
    cash = items["rule:cash_buffer"]
    assert cash["kind"] == "rule" and cash["usecases"] == [{"id": A, "title": "Can Holdings pay the call?"}] and cash["sub"] == "Rule · version 2 · Daniel Foo"
    asm = next(i for i in d["items"] if "WMR" in i["label"])
    assert asm["kind"] == "assumption" and [u["id"] for u in asm["usecases"]] == [A, B, C]  # every thread that uses a figure with it
    assert items[f"brief:{A}"]["kind"] == "decision" and items[f"brief:{A}"]["usecases"] == [{"id": A, "title": "Can Holdings pay the call?"}]
    assert [i["kind"] for i in d["items"]] == sorted((i["kind"] for i in d["items"]), key=["rule", "decision", "assumption"].index)
    assert get(c, "/decisions") == d


def test_an_empty_office_answers_honestly(env):
    c, _, _ = env
    u = get(c, "/usecases")
    assert u["groups"] == [] and u["total"] == 0 and len(u["domains"]) == 8
    assert get(c, "/decisions")["counts"] == {"rule": 0, "decision": 0, "assumption": 0}


def test_only_this_company_and_every_company_role_may_read(env, tmp_path):
    c, plane, data = env
    seed(plane)
    from sh_platform.entitlements import EntitlementStore
    EntitlementStore(data).create_company("othercorp", "Other Corp", "other")
    H.save(PlaneStore(data).plane_for("othercorp"), thread("t-x", "Secret other thread", "live", {}, "Zed Other"))
    paths = ["/usecases", f"/usecase/{A}", "/domain/cash", "/model/logical", "/model/physical", "/decisions"]
    for who in ("sofia.reyes.evergreen@example.test", "daniel.foo.evergreen@example.test", "grace.ong.evergreen@example.test", "raj.patel.evergreen@example.test", "mei.chen.evergreen@example.test"):
        cc = login(tmp_path, data, who)
        for p in paths:
            assert cc.get("/api/v3/knowledge" + p).status_code == 200, (who, p)
    text = json.dumps([get(c, p) for p in paths])
    assert "Secret other thread" not in text and "Zed Other" not in text
    assert c.get("/api/v3/knowledge/usecase/t-x").status_code == 404
    anon = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    for p in paths:
        assert anon.get("/api/v3/knowledge" + p).status_code in (401, 403)


def test_every_route_is_declared_in_the_permissions_file():
    from sh_platform.v1 import v3_knowledge_story_routes as R
    declared = set(yaml.safe_load((ROOT / "sh_platform" / "v1" / "v3_knowledge_story.permissions.yaml").read_text(encoding="utf-8"))["routes"])
    assert {f"GET {r.path}" for r in R.router.routes} == declared


# ---- review fixes: short titles, unblanked brief lines, bronze by kind ------------------------------------------------------------------

def test_a_use_case_is_titled_by_what_was_asked_not_the_first_words_typed(env):
    c, plane, _ = env
    seed(plane)
    said = ("Daniel's team just handed me the Cedarpoint call 7 notice. Before I record it, tell me whether it fits what we committed to "
            "Cedarpoint Ventures III, what is left after it, and whether the fee part is what the fund terms say.")
    H.save(plane, {**thread("t-d", "Daniel's team just handed me", "live", {}, "Helen Foo"), "brief": {"question": said},
                   "events": [{"at": "2026-10-21T08:00:00Z", "kind": "person", "text": said, "by": "You"}]})
    asked = "A Cedarpoint call is due on the 23rd. I want to know in one answer whether Holdings can pay it from its own cash after the 250,000 buffer."
    H.save(plane, {**thread("t-e", "Call payment feasibility", "live", {"Call payment feasibility": False}, "Helen Foo"), "brief": {"question": asked},
                   "events": [{"at": "2026-10-21T08:00:00Z", "kind": "person", "text": asked, "by": "You"}]})  # a figure's name is no title
    S._KEPT.clear()
    titles = {i["id"]: i["title"] for g in get(c, "/usecases")["groups"] for i in g["items"]}
    assert titles["t-d"] == "Check the Cedarpoint call 7 notice" and titles["t-e"] == "Can Holdings pay the Cedarpoint call"
    assert titles[B] == "Log a call notice"  # North's own short title stays
    assert get(c, "/usecase/t-d")["title"] == "Check the Cedarpoint call 7 notice"
    assert next(t for t in c.get("/api/v3/threads").json()["threads"] if t["id"] == "t-d")["title"] == "Check the Cedarpoint call 7 notice"  # the Desk too
    for typed, want in (("Every morning I check cash for each entity: administrator against the bank. Anything over 5,000 is a break.", "Check cash for each entity every morning"),
                        ("I want to test the liquid book against our signed limits every month: no single name over 5 percent.", "Test the liquid book against our signed limits"),
                        ("Each morning I would like a short note: what we are worth.", "A short note each morning"),
                        ("The administrator renamed a column. Show me which column changed, what it was called before.", "Which column changed")):
        got = H.ask_title(typed)
        assert got == want and len(got) <= H.TITLE_MAX, (typed, got)


def test_a_brief_line_an_older_guard_blanked_is_said_without_the_number(env):
    c, plane, _ = env
    seed(plane)
    H.save(plane, thread("t-f", "Keep the feasibility check", "live", {}, "Helen Foo", rules=["Retain the feasibility‑check result for not available yet years"]))
    S._KEPT.clear()
    lines = [i["label"] for i in get(c, "/usecase/t-f")["decisions"] if i["kind"] == "brule"]
    assert lines == ["Retain the feasibility‑check result"]
    assert "not available yet" not in json.dumps(get(c, "/decisions"))


def test_bronze_is_grouped_by_the_kind_of_file_in_plain_words(env):
    c, plane, _ = env
    seed(plane)
    files = {"fx_usdsgd_20260901.csv": b"date,pair,fixing\n2026-09-01,USDSGD,1.29\n", "fx_usdsgd_20260902.csv": b"date,pair,fixing\n2026-09-02,USDSGD,1.30\n",
             "2026-09-01_call_D_5.eml": b"Subject: Capital call 5\n\nPlease pay.\n", "mt EG-LIQUID.txt": b"nothing a reader knows\n"}
    for name, data in files.items():
        H.drop(plane, name, data)
    plane.path("v3", "files.json").write_text(json.dumps([{"name": n, "arrived_at": "2026-10-21T08:00:00Z", "status": "loaded", "source": n.split("_")[0], "thread": A}
                                                          for n in files]), encoding="utf-8")
    S._KEPT.clear()
    bronze = {b["label"]: b["sub"] for b in get(c, f"/usecase/{A}")["bronze"]}
    assert bronze["FX fixings"] == "2 files · csv" and bronze["Emails"] == "1 file · eml" and "Notes and other documents" in bronze
    assert bronze["Bank statements"] == "named in the brief, no file yet" and not any("EG-LIQUID" in b or "fx " in b for b in bronze)
    p = get(c, "/model/physical")
    assert [(b["label"], b["rows"]) for b in p["bronze"]["items"]][0] == ("FX fixings", 2) and p["bronze"]["total"] == 4
    one = get(c, "/model/physical?kpi=fig-cash-after-calls-due")  # the path still lights the kinds this use case read
    assert {"bronze:fx-fixings", "bronze:emails"} <= set(one["path"]["bronze"]) and {"bronze:fx-fixings", "bronze:emails"} <= {b["id"] for b in one["bronze"]["items"]}
