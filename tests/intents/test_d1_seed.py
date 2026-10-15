"""D1: the Intent Centre demo seed runs on a temp plane, every record holds the SHAPES section 15 shape, and a second run changes nothing."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.intents import store as S  # noqa: E402
from tools import seed_demo_intents as D  # noqa: E402

# SHAPES section 15, key for key.
INTENT = {"id", "type", "title", "purpose", "created_by", "created_at", "company", "areas", "people", "state", "time_box", "stages", "outcome",
          "closure", "ratings", "links", "share", "version", "updated_at", "history", "affected_may_read", "catalogue_version", "start_answers",
          "refs", "event_count", "events"}
INTENT_EXTRA = {"record", "series"}  # brief section 3 and file 38 ("Fields this feature adds", ruling 28)
PEOPLE = {"organiser", "sponsor", "decider", "owner", "reporter", "participants", "advisers", "affected", "observers"}
OUTCOME = {"initiative": {"goal", "why", "build_needed", "definitions_exist", "build_ready"},
           "brainstorm": {"statement", "good_outcome", "session_at", "chosen", "backed", "runners_up", "ideas_kept", "dropped"},
           "pulse": {"weeks"}, "problem": {"what", "saw", "bites", "count", "amount", "owner_accepted_at", "root_cause", "fix"},
           "decision": {"question", "options", "chosen", "why"}}
CLOSURE = {"closed_by", "closed_at", "summary", "why_it_happened", "what_came_out", "next", "cancel_reason", "draft_by", "signed"}
CLOSURE_EXTRA = {"confirmed", "one_liner"}  # files 01 (confirmers, ruling 25) and 04
NEXT_KINDS = {"initiative", "problem", "decision", "backlog", "handled", "nothing"}
STAGE = {"key", "state", "opened_at", "closed_at"}
REFS = {"wall_session_ids", "charter_outcome_id", "baseline_ids", "assessment_ids"}
EVENT = {"seq", "at", "kind", "status", "by", "anonymous", "agent", "stage", "ref", "detail", "confirms", "corrects", "sealed"}
WEEK = {"week_key", "opens", "closes", "state", "items", "review", "closed_at"}
ITEM = {"id", "by", "kind", "text", "severity", "count", "amount", "ref", "fate", "fate_reason", "decided_by"}
OPP = {"id", "title", "state", "noticed_by", "noticed_at", "areas", "touches", "pattern", "evidence", "judgement", "picked_up_by", "picked_up_at",
       "became", "parked", "dismissed", "history"}
BACKLOG = {"id", "title", "kind", "area", "source", "raised_by", "raised_at", "why_it_matters", "source_quote", "taps", "review_date", "status",
           "parked", "dropped", "merged_into", "merged_from", "opened_intent", "reminded_at", "history"}
ROW = {"id", "type", "title", "purpose", "state", "stage_key", "stage_name", "areas", "created_by", "organiser", "people", "affected_may_read",
       "people_count", "starts", "ends", "extended", "closed_at", "cancelled_at", "outcome_text", "next_kinds", "rating_n", "rating_avg", "rev", "body_text"}


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    EntitlementStore(root).create_company("ardmore", "Illustrative Ardmore", "family_office", modules=["m1_intent"])
    first = D.seed(root)
    snapshot = {p: p.read_bytes() for p in (root / "ardmore" / "intents").rglob("*") if p.is_file() and p.name != "_index.json"}
    second = D.seed(root)
    return root, first, second, snapshot


def test_records_hold_the_ruled_shapes(seeded):
    root, first, _, _ = seeded
    plane = root / "ardmore" / "intents"
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in plane.glob("*/intent.json")]
    assert len(recs) == 14 and {r["type"] for r in recs} == set(OUTCOME)
    for r in recs:
        assert INTENT <= set(r) and set(r) - INTENT <= INTENT_EXTRA, r["id"]
        assert S.ID_RE.fullmatch(r["id"]) and r["state"] in S.STATES
        assert set(r["people"]) == PEOPLE
        assert set(r["outcome"]) == OUTCOME[r["type"]] | {"kind"} and r["outcome"]["kind"] == r["type"]
        assert CLOSURE <= set(r["closure"]) and set(r["closure"]) - CLOSURE <= CLOSURE_EXTRA
        assert all(n["kind"] in NEXT_KINDS and n["reason"] for n in r["closure"]["next"])
        assert all(STAGE <= set(s) for s in r["stages"]) and REFS <= set(r["refs"])
        assert all(1 <= x["score"] <= 5 and x["by"] == "anonymous" for x in r["ratings"])
        lines = [json.loads(x) for x in (plane / r["id"] / "events.jsonl").read_text(encoding="utf-8").splitlines()] if r["state"] != "draft" else []
        assert all(set(e) == EVENT for e in lines) and r["event_count"] == r["events"]["count"] == len(lines)
        if r["state"] == "closed":
            assert r["closure"]["closed_at"] and r["closure"]["one_liner"] and r["closure"]["next"]
    for w in plane.glob("*/weeks/*.json"):
        doc = json.loads(w.read_text(encoding="utf-8"))
        assert WEEK <= set(doc) and all(ITEM <= set(i) and i["kind"] in ("ran", "broke", "thought") for i in doc["items"])
        if doc["state"] == "closed":
            assert all(i["fate"] and i["fate_reason"] for i in doc["items"])
    for o in plane.glob("opportunities/*.json"):
        assert set(json.loads(o.read_text(encoding="utf-8"))) == OPP
    items = json.loads((plane / "backlog.json").read_text(encoding="utf-8"))["items"]
    assert len(items) == 4 and all(set(i) == BACKLOG for i in items)
    rows = json.loads((plane / "_index.json").read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 14 and all(ROW <= set(x) for x in rows)


def test_store_reads_every_record_and_the_card_state_is_there(seeded):
    root, first, _, _ = seeded
    from sh_platform.plane import PlaneStore
    plane = PlaneStore(root).plane_for("ardmore")
    recs = {p.key: S.read_intent(plane, p.rec["id"]) for p in first["written"]}
    assert recs["ini_cap"]["state"] == "closed" and recs["ini_cap"]["links"]["build"] and recs["ini_cap"]["refs"]["charter_outcome_id"]
    assert next(s for s in recs["i1"]["stages"] if s["state"] == "open")["key"] == "define_strategically"
    assert recs["b2"]["state"] == "closed" and recs["b2"]["outcome"]["chosen"]["text"]
    assert len(recs["w1"]["series"]["weeks"]) == 3 and recs["p2"]["state"] == "closed" and recs["dec_cap"]["state"] == "closed"
    assert recs["i3"]["state"] == "draft"
    home = first["home"]
    assert home["M02_closed_inside_time_box"]["of"] == 4 and home["M13_ratings"]["count"] == 15


def test_people_and_credentials(seeded):
    root, first, _, _ = seeded
    assert first["people"]["accounts_created"] == 55 and first["people"]["areas_added"] == 7
    creds = (root / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines()
    rows = [c.split() for c in creds if c and not c.startswith("#")]
    assert len(rows) == 55 and all(len(r) == 4 and r[3] == "ardmore" for r in rows)
    assert "mei.ling.chong.ardmore@example.test" in {r[0] for r in rows}


def test_second_run_changes_nothing(seeded):
    root, _, second, snapshot = seeded
    assert second["written"] == [] and second["backlog_added"] == 0 and second["opportunities_added"] == 0
    assert second["people"]["accounts_created"] == 0 and second["people"]["people_added"] == 0 and second["people"]["tags_set"] == 0
    now = {p: p.read_bytes() for p in (root / "ardmore" / "intents").rglob("*") if p.is_file() and p.name != "_index.json"}
    assert now == snapshot
