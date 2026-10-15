"""B18 (files 32, 34): the charter with ten pages, the sponsor's signature, versions and who does what. Synthetic people."""
import json
import secrets
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.intents import charter, lifecycle as L, store as S
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.process_record import ProcessRecords
from sh_platform.profile import store as profile_store

CO = "ardmore"
ACCTS = {"janet": ("Janet Shaw", ["company_admin"]), "daniel": ("Daniel Kerr", ["sponsor"]), "aaron": ("Aaron Lyle", ["participant"]),
         "katie": ("Katie Rao", ["analyst"]), "harvey": ("Harvey Rowley", ["owner"]), "root": ("Platform", ["super_admin"])}
NOW = "2026-10-05T09:00:00+00:00"


class Accounts:
    def get(self, aid):
        return {"display_name": ACCTS[aid][0]} if aid in ACCTS else None

    def in_company(self, company_id):
        return [{"account_id": a, "display_name": n, "roles": r, "disabled": False} for a, (n, r) in ACCTS.items() if a != "root"]


class NoPacks:
    def load(self, industry):
        raise ValueError("no pack")


def problem(pid, title, draft=False):
    return {"id": pid, "title": title, "kind": "intent", "details": [], "priority": "must", "note_count": 3,
            "votes": {"must": 3}, "tied_options": [], "priority_edited": False, "library_problem_id": None,
            "so_that": "So that capital calls are funded in time.", "so_that_edited": not draft, "so_that_draft": draft,
            "so_that_proposal": None}


def cell(v, by="Janet Shaw", mark="stated"):
    return {"value": v, "mark": mark, "by": by, "from": "test", "at": NOW}


@pytest.fixture
def env(tmp_path):
    plane = PlaneStore(tmp_path).create(CO).ensure()
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=tmp_path)
    app.state.account_store = Accounts()
    app.state.entitlements = SimpleNamespace(company=lambda cid: {})
    app.state.packs = NoPacks()
    app.include_router(charter.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        who = request.headers.get("x-who", "janet")
        request.state.account_id, request.state.company_id, request.state.roles = who, CO, ACCTS[who][1]
        return await call_next(request)

    people = {f"p-{a}": {"name": cell(n), "role": cell("Head of data" if a == "katie" else "Operations lead" if a == "harvey" else "Staff"),
                         "team": cell("Finance"), "account_id": cell(a)} for a, (n, _) in ACCTS.items() if a != "root"}
    profile_store.mutate(plane, lambda d: d["people"].update(people))
    rec = ProcessRecords(plane).start("m1_intent", "charter", "Capital calls")
    sid = secrets.token_hex(16)
    prep = {"north_industry_practice": False, "north_problem_library": False, "briefing_video": "standard", "approver_name": "",
            "approver_account_id": None, "names": "choice", "signers": None, "wall_window_days": 5, "topic": "Capital calls",
            "purpose": "Fund calls in time", "outcome": "A charter", "charter_template": "standard", "seats": 8, "length_minutes": 20,
            "split": {"briefing": 4, "individual": 10080, "together": 8}}
    write_json_atomic(plane.path("intents", "m1_intent", "sessions", f"{sid}.json"), {
        "id": sid, "organiser_account_id": "janet", "state": "signing", "paused_from": None, "preparation": prep,
        "record_session_id": rec.session_id, "outcome_id": rec.outcome_id, "created_at": NOW, "updated_at": NOW,
        "inputs": {"actions": 0, "free_text": 0, "cards_confirmed": 0, "cards_new": 0, "cards_sealed": 0}})
    version = {"version": 1, "status": "draft", "created_at": NOW, "created_by": "North", "edited_at": None, "edited_by": None,
               "template": {"id": "standard", "name": "Standard charter", "columns": ["problem", "purpose", "priority", "notes"]},
               "problems": [problem("a1", "Call notices arrive late", draft=True), problem("a2", "No view of headroom")],
               "later": [{"id": "z1", "title": "Reporting is monthly only"}], "alone": [{"text": None, "kind": "idea"}],
               "parked": [{"title": "Watch the reserve", "reason": "After year end", "review_date": "2027-01-31"}],
               "footer": {"date": "2026-10-05", "participants": 4, "notes": 9, "later": 1}, "signatures": [], "returned": None,
               "wall": {"closed_at": NOW, "lanes": [{"lane": "missing", "count": 2, "cards": [
                   {"id": "c1", "text": "Late notices", "author": "Aaron Lyle", "sealed": False},
                   {"id": "c2", "text": "", "author": "Anonymous", "sealed": False}]}]}}
    write_json_atomic(plane.path("intents", "m1_intent", "charters", f"{sid}.json"), {"session_id": sid, "versions": [version], "links": []})
    intent = L.new_record("initiative", CO, L.person("janet", "Janet Shaw"), NOW, title="Capital calls", purpose="Fund calls in time",
                          areas=["Finance"])
    intent["people"].update(sponsor=L.person("daniel", "Daniel Kerr"), participants=[L.person("aaron", "Aaron Lyle")])
    intent["refs"]["wall_session_ids"] = [sid]
    L.move(intent, "open", "janet", NOW)
    S.create_intent(plane, intent)
    return SimpleNamespace(plane=plane, c=TestClient(app), id=intent["id"], sid=sid)


def call(env, who, method, path, body=None):
    return env.c.request(method, f"/api/intents/{env.id}{path}", json=body if body is not None else {}, headers={"x-who": who})


def sign(env, who, **over):
    """Sign after "Are you the sponsor?", carrying the version and edit the signer read (as the screen does)."""
    c = call(env, "daniel", "GET", "/charter").json()["charter"]
    return call(env, who, "POST", "/charter/sign", {"confirm_sponsor": True, "version": c["version"], "edited_at": c["edited_at"], **over})


def set_build(env, value=True):
    rec = S.read_intent(env.plane, env.id)
    S.update_intent(env.plane, env.id, rec["version"], lambda r: r.update(build_needed=value))


def add_records(env):
    """A baseline with one measure, a process map and a sources tab, as the other cards write them."""
    bid = "b1"
    S.update_intent(env.plane, env.id, S.read_intent(env.plane, env.id)["version"], lambda r: r["refs"].update(baseline_ids=[bid]))
    base = ("intents", "m2_baseline", bid)
    write = lambda name, data: write_json_atomic(env.plane.path(*base, name), data)  # noqa: E731
    write("kpis.json", [{"id": "K1", "name": "Headroom", "problem_ids": ["a2"], "definition": cell("Cash less calls"),
                         "technical": {"calculation": cell("Opening cash minus calls")}}])
    write("glossary.json", {"entries": [{"kpi_id": "K1", "business_definition": cell("Cash left after calls")}]})
    write("governed_state.json", {"K1": {f: cell("x") for f in charter.GOVERNED}})
    write("catalogue.json", {"sources": [{"Source ID": cell("S1"), "Source name": cell("Bank file"), "Source type": cell("File"),
                                          "Where it lands or lives": cell("Warehouse"), "Data owner": cell("Harvey Rowley")}]})
    write_json_atomic(env.plane.path("intents", env.id, "processes.json"), {"processes": [
        {"id": "pr1", "name": cell("Call funding"), "owner": cell("Harvey Rowley"), "status": "confirmed",
         "confirmed": {"by": "Harvey Rowley", "at": NOW}, "steps": [{}, {}], "breaks": [{}]},
        {"id": "pr2", "name": cell("Notice intake"), "owner": cell("Aaron Lyle"), "status": "guessed", "steps": [], "breaks": []}]})


def test_ten_pages_assembled_and_missing_records_wait(env):
    pages = call(env, "janet", "GET", "/charter").json()["pages"]
    assert [p["key"] for p in pages] == ["intent", "wall", "problems", "measures", "processes", "sources", "roles", "build", "parked", "risks"]
    assert [p["n"] for p in pages] == list(range(1, 11))
    by = {p["key"]: p for p in pages}
    assert by["processes"]["status"] == "missing" and "Waits for file 27" in by["processes"]["text"]
    assert by["sources"]["status"] == "missing" and "Waits for file 28" in by["sources"]["text"]
    assert by["measures"]["status"] == "missing"
    assert by["wall"]["total"] == 2 and by["wall"]["anonymous"] == 1 and by["wall"]["took_part"] == ["Aaron Lyle"]
    assert [r["kind"] for r in by["parked"]["rows"]] == ["Future shelf", "Left for later", "Note"]
    add_records(env)
    by = {p["key"]: p for p in call(env, "janet", "GET", "/charter").json()["pages"]}
    assert by["processes"]["confirmed"] == 1 and by["processes"]["rows"][1]["note"] == "Not yet confirmed by its owner"
    assert by["measures"]["rows"][1]["measures"][0]["state"] == "Confirmed" and by["measures"]["rows"][0]["empty"]
    assert by["sources"]["rows"][0]["source_owner"] is None and by["sources"]["rows"][0]["state"] == "Needs source owner"
    texts = [r["text"] for r in by["risks"]["rows"]]
    assert any("Notice intake" in t for t in texts) and any("Bank file" in t for t in texts)


def test_only_the_sponsor_signs_after_the_modal_and_the_intent_moves_to_closing(env):
    assert sign(env, "janet").status_code == 403  # organiser and admin cannot
    assert sign(env, "aaron").status_code == 403
    assert call(env, "daniel", "POST", "/charter/sign", {}).status_code == 422  # the modal was not answered
    view = call(env, "daniel", "GET", "/charter").json()["charter"]
    assert view["sign_block"] == charter.BLOCK_LINES and not view["can_sign"]
    assert sign(env, "daniel").status_code == 409
    assert call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]}).status_code == 200
    assert call(env, "daniel", "GET", "/charter").json()["charter"]["sign_block"] == charter.BLOCK_BUILD
    assert sign(env, "daniel").status_code == 409
    set_build(env)
    r = sign(env, "daniel")
    assert r.status_code == 200, r.text
    c = r.json()["charter"]
    assert c["state"] == "Signed" and c["signature"]["signed_by"] == "Daniel Kerr" and c["signature"]["how"] == "in the charter"
    rec = S.read_intent(env.plane, env.id)
    assert rec["state"] == "closing" and rec["outcome"]["signed_by"] == "Daniel Kerr" and rec["outcome"]["charter_version"] == 1
    assert sign(env, "daniel").status_code == 409  # one signature per version


def test_signed_is_read_only_and_freezes_the_pages(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    add_records(env)
    S.update_intent(env.plane, env.id, S.read_intent(env.plane, env.id)["version"],
                    lambda r: r.update(build_ready={"lines": [{"key": k, "ok": False} for k, _ in charter.BUILD_LINES]}))
    assert sign(env, "daniel").status_code == 200
    build = next(p for p in call(env, "aaron", "GET", "/charter").json()["pages"] if p["key"] == "build")
    assert build["lines"][0] == {"key": "charter", "label": "Charter signed", "ok": True} and build["passing"] == 1  # line 1 passes by the signature
    assert call(env, "janet", "PUT", "/charter", {"so_that": {"a1": "So that it changes."}}).status_code == 409
    assert call(env, "janet", "PUT", "/charter/risks", {"accept": ["x"]}).status_code == 409
    view = call(env, "janet", "GET", "/charter").json()
    assert not view["charter"]["editable"] and all(p["status"] != "ok" or p.get("accept") in (None, False) for p in view["pages"])
    # a later edit in Define does not change the signed pages
    write_json_atomic(env.plane.path("intents", env.id, "processes.json"), {"processes": []})
    by = {p["key"]: p for p in call(env, "janet", "GET", "/charter").json()["pages"]}
    assert by["processes"]["status"] == "ok" and len(by["processes"]["rows"]) == 2
    assert by["measures"]["status"] == "ok" and by["measures"]["rows"][1]["measures"][0]["name"] == "Headroom"


def test_a_change_is_a_new_version_signed_again(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    sign(env, "daniel")
    assert call(env, "daniel", "POST", "/charter/versions", {}).status_code == 403  # organiser only
    r = call(env, "janet", "POST", "/charter/versions", {"comment": "Scope grew"})
    assert r.status_code == 200 and r.json()["charter"]["version"] == 2 and r.json()["charter"]["state"] == "Draft"
    assert call(env, "janet", "PUT", "/charter", {"so_that": {"a2": "So that headroom is one number."}}).status_code == 200
    assert call(env, "janet", "POST", "/charter/versions/2/discard", {}).status_code == 422  # a reason is needed
    r = call(env, "janet", "POST", "/charter/versions/2/discard", {"reason": "Scope did not grow"})
    assert r.status_code == 200 and r.json()["charter"]["version"] == 1
    assert [v["state"] for v in r.json()["versions"]] == ["Signed", "Discarded"]
    call(env, "janet", "POST", "/charter/versions", {})
    r = sign(env, "daniel")
    assert r.status_code == 200, r.text
    assert [v["state"] for v in r.json()["versions"]] == ["Superseded", "Discarded", "Signed"]
    assert r.json()["charter"]["version"] == 3 and r.json()["charter"]["of"] == 3


def test_six_roles_named_asked_accepted_or_declined(env):
    got = call(env, "janet", "GET", "/roles").json()
    assert [r["role"] for r in got["rows"]] == list(charter.ROLES)
    assert next(r for r in got["rows"] if r["role"] == "sponsor")["person"] == "Daniel Kerr"  # one source: the intent's sponsor
    assert call(env, "janet", "PUT", "/roles", {"developer": "Katie Rao"}).status_code == 422  # a person id, never free text
    assert call(env, "janet", "PUT", "/roles", {"sponsor": "p-aaron"}).status_code == 422
    assert call(env, "katie", "PUT", "/roles", {"developer": "p-katie"}).status_code in (403, 404)
    for role, pid in (("architect", "p-katie"), ("developer", "p-katie"), ("tester", "p-aaron"), ("ops", "p-harvey")):
        assert call(env, "janet", "PUT", "/roles", {role: pid}).status_code == 200
    assert call(env, "janet", "PUT", "/roles", {"informed": ["p-aaron", "p-harvey"]}).status_code == 200
    asked = call(env, "janet", "POST", "/roles/ask", {}).json()["asked"]
    assert set(asked) == {"architect", "developer", "tester", "sponsor", "ops", "informed"}
    assert call(env, "janet", "POST", "/roles/ask", {}).json()["asked"] == []  # nobody is asked twice
    assert call(env, "katie", "POST", "/roles/tester/answer", {"answer": "accept"}).status_code == 403  # not hers
    assert call(env, "katie", "POST", "/roles/developer/answer", {"answer": "accept"}).status_code == 200
    assert call(env, "harvey", "POST", "/roles/ops/answer", {"answer": "decline"}).status_code == 422  # a reason is needed
    assert call(env, "harvey", "POST", "/roles/ops/answer", {"answer": "decline", "reason": "On leave until 21 Oct"}).status_code == 200
    assert call(env, "harvey", "POST", "/roles/informed/answer", {"answer": "seen"}).status_code == 200
    state = lambda who: {r["role"]: r["answer"] for r in call(env, who, "GET", "/roles").json()["rows"]}  # noqa: E731
    assert state("janet")["developer"]["state"] == "accepted" and state("janet")["ops"]["reason"] == "On leave until 21 Oct"
    assert state("aaron")["ops"]["state"] == "declined" and state("aaron")["ops"]["reason"] is None  # the reason is the organiser's
    # naming someone else resets the answer and keeps the old one
    call(env, "janet", "PUT", "/roles", {"ops": "p-daniel"})
    assert state("janet")["ops"]["state"] == "not_asked"
    saved = json.loads(charter._roles_path(env.plane, env.sid).read_text(encoding="utf-8"))
    assert saved["answer_history"][-1]["state"] == "declined" and saved["names"]["ops"] == "Daniel Kerr"
    pages = {p["key"]: p for p in call(env, "janet", "GET", "/charter").json()["pages"]}
    assert all("reason" not in r or r["reason"] is None for r in pages["roles"]["rows"])  # page 7 never shows decline reasons


def test_a_stale_read_cannot_be_signed(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    read = call(env, "daniel", "GET", "/charter").json()["charter"]
    stale = {"confirm_sponsor": True, "version": read["version"], "edited_at": read["edited_at"]}
    assert call(env, "daniel", "POST", "/charter/sign", {"confirm_sponsor": True}).status_code == 409  # no version named
    assert sign(env, "daniel", version=99).status_code == 409
    call(env, "janet", "PUT", "/charter", {"so_that": {"a2": "So that headroom is known."}})  # the organiser edits after Daniel read it
    r = call(env, "daniel", "POST", "/charter/sign", stale)
    assert r.status_code == 409 and r.json()["message"] == charter.STALE
    assert sign(env, "daniel").status_code == 200
    assert charter.intent_for_session(env.plane, env.sid)["id"] == env.id and charter.intent_for_session(env.plane, "nope") is None


def test_a_stranger_does_not_know_the_charter_exists(env):
    assert call(env, "katie", "GET", "/charter").status_code == 404
    assert call(env, "root", "GET", "/charter").status_code == 404


# ---- F11: the module's sign route, the download and the approver link ----------------------------------------------------

def module(env, who, method, path, body=None):
    from modules.m1_intent.api import charter as M1
    if not any(getattr(r, "path", "").startswith("/api/modules/m1_intent") for r in env.c.app.routes):
        env.c.app.include_router(M1.router, prefix="/api/modules/m1_intent")
    return env.c.request(method, f"/api/modules/m1_intent/sessions/{env.sid}/charter{path}", json=body if body is not None else {}, headers={"x-who": who})


def signed(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    add_records(env)
    assert sign(env, "daniel").status_code == 200


def test_module_sign_route_refuses_an_intent_session(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    for who in ("janet", "daniel"):
        r = module(env, who, "POST", "/sign")
        assert r.status_code == 403 and r.json()["message"] == "Sign this charter on the intent's charter page. Only the sponsor signs it."
    assert S.read_intent(env.plane, env.id)["state"] == "open"


def test_download_survives_a_newer_draft_and_a_discard_and_carries_pages_4_to_10(env):
    signed(env)
    call(env, "janet", "POST", "/charter/versions", {})
    for _ in range(2):
        r = module(env, "janet", "GET", "/download")
        assert r.status_code == 200, r.text
        md = next(f for f in r.json()["files"] if f["format"] == "markdown")["content"]
        html = next(f for f in r.json()["files"] if f["format"] == "html")["content"]
        for need in ("4. Measures", "Headroom (Confirmed)", "Call funding, Confirmed by Harvey Rowley, owner Harvey Rowley",
                     "Notice intake, Guessed", "Bank file: Needs source owner", "Architect: ", "Build needed: Yes",
                     "10. Known risks", "Notice intake"):
            assert need in md and need.replace("&", "&amp;") in html, need
        assert md.index("4. Measures") < md.index("Signed by")
        call(env, "janet", "POST", "/charter/versions/2/discard", {"reason": "Not needed"})


def test_accepted_risks_are_exported_with_who_accepted(env):
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    add_records(env)
    text = next(r["text"] for r in call(env, "janet", "GET", "/charter").json()["pages"][-1]["rows"] if "Notice intake" in r["text"])
    assert call(env, "janet", "PUT", "/charter/risks", {"accept": [text]}).status_code == 200
    assert sign(env, "daniel").status_code == 200
    md = next(f for f in module(env, "janet", "GET", "/download").json()["files"] if f["format"] == "markdown")["content"]
    assert "Accepted by Janet Shaw." in md


def test_a_participant_with_no_seat_can_download_and_a_stranger_cannot(env):
    signed(env)
    assert module(env, "aaron", "GET", "/download").status_code == 200
    assert module(env, "katie", "GET", "/download").status_code == 404


def test_a_named_observer_downloads_and_page_nine_is_numbered(env):
    signed(env)
    assert module(env, "harvey", "GET", "/download").status_code == 404
    S.update_intent(env.plane, env.id, S.read_intent(env.plane, env.id)["version"],
                    lambda r: r["people"].update(observers=[L.person("harvey", "Harvey Rowley")]))
    r = module(env, "harvey", "GET", "/download")
    assert r.status_code == 200, r.text
    for f in r.json()["files"]:
        assert ("9. Parked for later" in f["content"]), f["format"]


def test_confirming_with_nothing_to_confirm_is_a_plain_refusal(env):
    r = call(env, "janet", "PUT", "/charter", {"confirm_so_that": []})
    assert r.status_code == 422 and r.json()["message"] if "message" in r.json() else r.text


def test_approval_through_the_link_moves_the_intent_to_closing(env):
    path = env.plane.path("intents", "m1_intent", "charters", f"{env.sid}.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    v = doc["versions"][0]
    v.update(status="signed", signatures=[{"name": "Grace Ward", "account_id": None, "at": NOW, "how": "approver"}])
    write_json_atomic(path, doc)
    assert S.read_intent(env.plane, env.id)["state"] == "open"
    c = call(env, "janet", "GET", "/charter").json()
    assert c["intent"]["state"] == "closing" and c["charter"]["signature"]["how"] == "by approver link"
    rec = S.read_intent(env.plane, env.id)
    assert rec["state"] == "closing" and rec["outcome"]["signed_by"] == "Grace Ward"
    assert json.loads(path.read_text(encoding="utf-8"))["versions"][0]["pages_frozen"]


def test_signing_records_the_map_moment_and_a_map_failure_never_blocks(env, monkeypatch):
    from sh_platform.graph import knowledge_map as km
    seen = []
    monkeypatch.setattr(km, "record_moment", lambda plane, moment, ref, by: seen.append((moment, ref, by)))
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    assert sign(env, "daniel").status_code == 200
    assert seen == [("charter_signed", env.id, "Daniel Kerr")]


def test_a_map_failure_does_not_block_the_signature(env, monkeypatch):
    from sh_platform.graph import knowledge_map as km

    def boom(*a):
        raise RuntimeError("map down")
    monkeypatch.setattr(km, "record_moment", boom)
    call(env, "janet", "PUT", "/charter", {"confirm_so_that": ["a1"]})
    set_build(env)
    assert sign(env, "daniel").status_code == 200 and S.read_intent(env.plane, env.id)["state"] == "closing"
