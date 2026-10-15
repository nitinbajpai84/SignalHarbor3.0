"""B32: pack suggestions (spec 49) for two industries and an empty company; closure memory (spec 46). Synthetic data, temporary planes."""
import re
from pathlib import Path

import pytest
import yaml

from sh_platform import memory
from sh_platform.intents import memory_close as mc
from sh_platform.intents import pack as ipack
from sh_platform.packs import SUGGESTION_LABEL, PackLoader
from sh_platform.plane import PlaneStore
from sh_platform.profile import cards, store

REPO = Path(__file__).resolve().parents[2]
P = {"mark": "stated", "by": "Test", "from": "Test"}
MARKER = "ZEBRA-PAYROLL-SEAL"


@pytest.fixture
def loader(tmp_path):
    root = tmp_path / "packs"
    for ind, ver, body in (("asset_management", 1, {"suggestions": [{"id": "am-1", "type": "decision", "title": "Pick a fund platform"}]}),):
        d = root / ind / str(ver)
        (d / "intents").mkdir(parents=True)
        (d / "pack.yaml").write_text("label: Asset management\nstatus: proposed\n", encoding="utf-8")
        (d / "problems.yaml").write_text("rows: []\n", encoding="utf-8")
        (d / "intents" / "first_intents.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return PackLoader(root)


@pytest.fixture
def fo():
    return PackLoader(REPO / "packs").load("family_office")


def test_family_office_files_load_labelled_and_without_figures(fo):
    out = ipack.first_intents(fo)
    assert out["pack"]["industry"] == "family_office" and out["label"] == SUGGESTION_LABEL
    assert len(out["items"]) == 3 and all(i["label"] == SUGGESTION_LABEL and i["source"] == "family_office@1" for i in out["items"])
    assert not any(re.search(r"\d", i["title"] + i["purpose"] + i["why"]) for i in out["items"])
    assert ipack.start_hints(fo, "initiative")["hints"]["3"].startswith("Others often say yes")
    assert ipack.start_hints(fo, "problem")["hints"] == {}
    q = ipack.checkin_questions(fo, "operations")["questions"]
    assert len(q) == 3 and ipack.checkin_questions(fo, "finance")["questions"][0]["area"] == "any"


def test_second_industry_has_only_its_own_content(loader):
    out = ipack.first_intents(loader.load("asset_management"))
    assert [i["suggestion_id"] for i in out["items"]] == ["am-1"]
    assert ipack.start_hints(loader.load("asset_management"), "initiative")["hints"] == {}  # no file: empty, not family office
    assert ipack.checkin_questions(loader.load("asset_management"))["questions"] == []


def test_empty_company_and_unknown_version_are_honest(loader):
    for pk in (loader.load("no_such_industry"), loader.load("asset_management", 99)):
        out = ipack.first_intents(pk)
        assert out["pack"] is None and out["items"] == [] and out["empty_message"].startswith("No industry knowledge")
        assert ipack.start_hints(pk, "initiative")["hints"] == {} and ipack.checkin_questions(pk)["questions"] == []


def test_picked_up_and_dismissed_leave_the_strip_for_that_person_only(fo):
    marks = [{"suggestion_id": "fo-checkin-operations", "mark": "dismissed"}, {"suggestion_id": "fo-decision-custodian", "mark": "picked_up"}]
    assert [i["suggestion_id"] for i in ipack.first_intents(fo, marks)["items"]] == ["fo-initiative-family-reporting"]
    assert len(ipack.first_intents(fo)["items"]) == 3


def test_reading_writes_nothing(tmp_path, fo):
    before = sorted(tmp_path.rglob("*"))
    ipack.first_intents(fo), ipack.start_hints(fo, "decision"), ipack.checkin_questions(fo)
    assert sorted(tmp_path.rglob("*")) == before


def test_pack_files_clean():
    bad = re.compile(r"permission|role|claude|anthropic|openai|gpt|vendor|pulse", re.I)
    for f in (REPO / "packs" / "family_office" / "1" / "intents").glob("*.yaml"):
        text = yaml.safe_dump(yaml.safe_load(f.read_text(encoding="utf-8")))  # comments and the record key `pulse` are not copy
        assert text.strip() and not bad.search(text.replace("type: pulse", "")), f.name


# ---- closure memory --------------------------------------------------------------------------------------------------------

@pytest.fixture
def plane(tmp_path):
    (tmp_path / "planes").mkdir()
    pl = PlaneStore(tmp_path / "planes").create("ardmore")
    for pid, name, acct in (("janet-shaw", "Janet Shaw", "acct-janet"), ("aaron-lyle", "Aaron Lyle", "acct-aaron")):
        store.record(pl, f"people.{pid}.name", name, P)
        store.record(pl, f"people.{pid}.account_id", acct, P)
    store.record(pl, "governance.restricted_areas.payroll.area", "Payroll", P)
    cards.record_card(pl, {"id": "c1", "lane": "tracking", "sealed": True, "anonymous": False, "author": "aaron-lyle", "q2": MARKER})
    cards.record_card(pl, {"id": "c2", "lane": "tracking", "sealed": False, "anonymous": True, "anon_key": "anon-1", "q1": "secret anonymous thought"})
    return pl


def intent(**kw):
    rec = {"id": "bra-" + "a" * 32, "type": "brainstorm", "state": "closed", "version": 1,
           "people": {"organiser": {"account_id": "acct-janet", "name": "Janet Shaw"}, "participants": [{"name": f"P{i}"} for i in range(5)]},
           "time_box": {"ends": "2026-10-09T00:00:00+00:00"},
           "closure": {"closed_by": "acct-janet", "closed_at": "2026-10-08T00:00:00+00:00", "signed": True, "next": []},
           "outcome": {"chosen": "the weekly cash view"}}
    rec.update(kw)
    return rec


def texts(plane):
    return [e["text"] for e in memory.load(plane, "north", "janet-shaw")["entries"]]


def test_entries_built_from_closure_fields_with_counts_in_words(plane):
    block = mc.write_closure_memory(plane, intent())
    assert block["state"] == "written" and block["written_at"] and len(block["by_agent"]["north"]) == 3
    assert block["by_agent"]["lens"] == block["by_agent"]["nira"] == []
    t = texts(plane)
    assert "Ran a brainstorm with five people." in t and "Chose the weekly cash view." in t
    assert not any(re.search(r"\d", x) for x in t)
    assert memory.load(plane, "north", "aaron-lyle")["entries"] == []  # participants who are not the organiser: nothing


def test_sealed_marker_and_sealed_echo_never_reach_memory(plane):
    rec = intent(outcome={"chosen": f"{MARKER} pay review"}, closure={**intent()["closure"], "next": [{"kind": "problem", "reason": "secret anonymous thought"}]})
    block = mc.write_closure_memory(plane, rec)
    assert block["filtered"] >= 2 and "Ran a brainstorm with five people." in texts(plane)
    everything = " ".join(p.read_text(encoding="utf-8") for p in (plane.path("context") / "memory").rglob("*.json"))
    assert MARKER not in everything and "secret anonymous" not in everything and "Payroll" not in everything


def test_other_peoples_names_and_cancelled_intents(plane):
    block = mc.write_closure_memory(plane, intent(outcome={"chosen": "back Aaron Lyle"}))
    assert block["filtered"] == 1 and "Chose back Aaron Lyle." not in texts(plane)
    assert mc.write_closure_memory(plane, intent(state="cancelled", id="bra-" + "b" * 32))["state"] == "skipped"
    assert mc.write_closure_memory(plane, intent(type="pulse", id="pul-" + "c" * 32))["state"] == "skipped"


def test_person_edit_kept_and_deleted_line_not_written_back(plane):
    mc.write_closure_memory(plane, intent())
    doc = memory.load(plane, "north", "janet-shaw")
    for e in doc["entries"]:
        if e["kind"] == "preference":
            e.update(text="Prefers two short sittings.", by="person")
        if e["kind"] == "decision":
            doc["deleted"] = [{"hash": mc.tomb_hash(e["text"]), "at": "2026-10-09"}]
    doc["entries"] = [e for e in doc["entries"] if e["kind"] != "decision"]
    memory.save(plane, "north", "janet-shaw", doc)
    mc.write_closure_memory(plane, intent(id="bra-" + "d" * 32))
    t = texts(plane)
    assert "Prefers two short sittings." in t and not any("Prefers to finish" in x for x in t)
    assert not any(x.startswith("Chose") for x in t)


def test_idempotent_and_opening_line_uses_memory(plane):
    first = mc.write_closure_memory(plane, intent())
    again = mc.write_closure_memory(plane, intent(memory=first))
    assert again == first
    o = mc.opening_line(plane, "janet-shaw", "brainstorm")
    assert o["line"] == "Last time you ran a brainstorm with five people, from what North remembers about you."
    assert o["preference"] == "You prefer to finish a brainstorm inside the time box."
    assert mc.opening_line(plane, "aaron-lyle") is None and mc.opening_line(plane, None) is None


# ---- F41: memory quality, tombstones, opening line, per-person pack marks ---------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sh_platform.intents import memory as imem  # noqa: E402
from sh_platform.memory import api as mapi  # noqa: E402
from sh_platform.memory import filters  # noqa: E402


def test_model_replies_and_anonymous_worries_are_never_stored(plane):
    rows = [{"kind": "fact", "text": t} for t in (
        "No conversation content has been provided from which to extract memory items.", "No information about North's work has been stored in memory.",
        'User needs to know which ops area "North" is for.', "Has an anonymous worry about reporting.", "Likes a short weekly review.")]
    assert [r["text"] for r in filters.clean(plane, rows)] == ["Likes a short weekly review."]


def test_closure_lines_are_facts_once_with_grammar(plane):
    mc.write_closure_memory(plane, intent(type="initiative", id="ini-" + "a" * 32))
    mc.write_closure_memory(plane, intent(id="bra-" + "a" * 32, closure={**intent()["closure"], "closed_at": "2026-10-10T00:00:00+00:00"}))
    mc.write_closure_memory(plane, intent(id="bra-" + "b" * 32))
    doc = memory.load(plane, "north", "janet-shaw")["entries"]
    t = [e["text"] for e in doc]
    assert "Ran an initiative with five people." in t and not any("a initiative" in x for x in t)
    assert len(t) == len({x.lower() for x in t})
    assert {e["kind"] for e in doc if e["text"].startswith("Ran a")} == {"fact"}


def test_tidy_mends_what_older_runs_stored():
    old = [{"id": "1", "kind": "open", "text": "Ran a initiative with two people.", "updated_at": "2026-10-02"},
           {"id": "2", "kind": "open", "text": "Ran a problem.", "updated_at": "2026-10-01"},
           {"id": "3", "kind": "fact", "text": "Ran a problem.", "updated_at": "2026-10-03"},
           {"id": "4", "kind": "fact", "text": "No information about North's work has been stored in memory.", "updated_at": "2026-10-04"}]
    out = {e["id"]: e for e in filters.tidy(old)}
    assert set(out) == {"1", "3"} and out["1"]["text"] == "Ran an initiative with two people." and out["1"]["kind"] == "fact"


def test_a_deleted_line_leaves_a_tombstone_and_closure_never_writes_it_back(plane):
    mc.write_closure_memory(plane, intent())
    doc = memory.load(plane, "north", "janet-shaw")
    kept = [e for e in doc["entries"] if e["kind"] != "decision"]
    new = mapi._merge(doc, [{"id": e["id"], "kind": e["kind"], "text": e["text"]} for e in kept])
    assert [d["hash"] for d in new["deleted"]] == [mc.tomb_hash("Chose the weekly cash view.")]
    memory.save(plane, "north", "janet-shaw", new)
    mc.write_closure_memory(plane, intent(id="bra-" + "e" * 32))
    assert not any(x.startswith("Chose") for x in texts(plane))


def pack_app(tmp_path, plane, *, organiser=False, admin=False, areas=()):
    store.record(plane, "people.aaron-lyle.is_organiser", organiser, P)
    app = FastAPI()
    app.state.settings = SimpleNamespace(data_root=plane.root.parent)
    app.state.packs = PackLoader(REPO / "packs")
    app.state.account_store = SimpleNamespace(in_company=lambda c: [{"account_id": "acct-aaron", "display_name": "Aaron Lyle"}], get=lambda a: None)
    app.state.entitlements = SimpleNamespace(company=lambda cid: {"industry": "family_office"})
    app.include_router(ipack.router)
    app.include_router(imem.router)

    @app.middleware("http")
    async def sign_in(request, call_next):
        request.state.account_id, request.state.company_id = "acct-aaron", "ardmore"
        request.state.roles = ["company_admin"] if admin else ["participant"]
        return await call_next(request)
    return TestClient(app)


def test_strip_marks_prefill_and_hints_over_the_routes(tmp_path, plane):
    c = pack_app(tmp_path, plane, organiser=True)
    s = c.get("/api/intents/suggestions").json()
    assert len(s["items"]) == 3 and s["may_start"] and s["dismissed_count"] == 0 and s["items"][0]["label"] == SUGGESTION_LABEL
    sid = s["items"][0]["suggestion_id"]
    assert c.post(f"/api/intents/suggestions/{sid}/dismiss").status_code == 200
    again = c.get("/api/intents/suggestions").json()
    assert [i["suggestion_id"] for i in again["items"]] == [i["suggestion_id"] for i in s["items"][1:]] and again["dismissed_count"] == 1
    assert (plane.path("intents", "_suggestion_marks") / "aaron-lyle.json").is_file()  # remembered on disk, not in the page
    c.post(f"/api/intents/suggestions/{sid}/restore")
    assert len(c.get("/api/intents/suggestions").json()["items"]) == 3
    c.post(f"/api/intents/suggestions/{sid}/picked-up", json={"intent_id": "ini-x"})
    assert sid not in [i["suggestion_id"] for i in c.get("/api/intents/suggestions").json()["items"]]
    assert c.get("/api/intents/hints/initiative").json()["hints"]["3"].startswith("Others often say yes")


def test_a_person_who_may_not_start_sees_no_cards(tmp_path, plane):
    s = pack_app(tmp_path, plane).get("/api/intents/suggestions").json()
    assert s["items"] == [] and s["may_start"] is False


def test_opening_line_route_uses_memory_or_says_nothing(tmp_path, plane):
    store.record(plane, "people.aaron-lyle.account_id", "acct-aaron", P)
    c = pack_app(tmp_path, plane, organiser=True)
    assert c.get("/api/intents/opening-line").json() == {"line": None}
    mc.write_closure_memory(plane, intent(people={"organiser": {"account_id": "acct-aaron", "name": "Aaron Lyle"}, "participants": []},
                                          closure={**intent()["closure"], "closed_by": "acct-aaron"}))
    o = c.get("/api/intents/opening-line?type=brainstorm").json()
    assert o["line"] == "Last time you ran a brainstorm, from what North remembers about you."
    assert c.get("/api/intents/opening-line?type=decision").json() == {"line": None}
