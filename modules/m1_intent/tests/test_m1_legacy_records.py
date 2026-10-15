"""D1: an old saved session or template without the newer preparation fields is read with defaults, never fails the list."""
import json

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.preparation import Offers, clean, default_preparation
from modules.m1_intent.store.sessions import SessionStore

S, T = C.load_session_settings(), C.load_charter_templates()
NEWER = ("names", "approver_name", "approver_account_id", "briefing_video", "north_industry_practice", "north_problem_library")


def prep():
    return clean({"purpose": "Find out why renewals slip"}, default_preparation(S, T), S, T, Offers(False, False))


def old_prep():
    return {k: v for k, v in prep().items() if k not in NEWER}


def store_for(world) -> SessionStore:
    return SessionStore(world.plane("co-a").ensure())


def test_an_old_session_without_the_newer_settings_is_read_with_defaults(world):
    st = store_for(world)
    s = st.create("acct-1", prep())
    path = world.plane("co-a").path("intents", "m1_intent", "sessions", f"{s['id']}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["preparation"] = old_prep()
    path.write_text(json.dumps(data), encoding="utf-8")
    got = st.get(s["id"])["preparation"]
    assert got["names"] == "choice" and got["approver_name"] == "" and got["approver_account_id"] is None
    assert got["north_problem_library"] is False and got["briefing_video"] == "standard"
    assert [r["id"] for r in st.list_for("acct-1")] == [s["id"]]


def test_templates_list_reads_old_records_with_defaults_and_skips_unreadable_ones(world, caplog):
    st = store_for(world)
    s = st.create("acct-1", prep())
    good = st.save_template("New", s["id"], "acct-1")
    path = world.plane("co-a").path("intents", "m1_intent", "templates.json")
    old = {"id": "a" * 32, "name": "Old", "preparation": old_prep(), "created_at": "2026-10-04T04:51:00+00:00"}
    bad = {"id": "b" * 32, "name": "Broken", "preparation": "nope", "created_at": "x"}
    path.write_text(json.dumps({"templates": [old, bad, good]}), encoding="utf-8")
    rows = st.templates()
    assert [r["id"] for r in rows] == ["a" * 32, good["id"]]
    assert rows[0]["preparation"]["names"] == "choice"
    assert "template" in caplog.text and "Broken" not in caplog.text
