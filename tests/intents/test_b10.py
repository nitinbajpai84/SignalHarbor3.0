"""B10: the events log (spec 16) and the search index (spec 15). Run: pytest -q -p no:cacheprovider tests/intents/test_b10.py"""
import ast
import json
import re
from datetime import date
from pathlib import Path

import pytest

from sh_platform.intents import events as ev
from sh_platform.intents import search as sx
from sh_platform.intents import store as S
from sh_platform.jsonfile import read_json_strict
from sh_platform.plane import PlaneStore
from sh_platform.profile import store
from sh_platform.profile.view import Viewer

JANET = {"account": "acc-janet", "name": "Janet Shaw", "role": "organiser"}
AARON = {"account": "acc-aaron", "name": "Aaron Lyle", "role": "participant"}
V = {"janet": Viewer("Janet Shaw", frozenset({"participant"}), False, "acc-janet"),
     "aaron": Viewer("Aaron Lyle", frozenset({"participant"}), False, "acc-aaron"),
     "grace": Viewer("Grace Ward", frozenset({"approver"}), False, "acc-grace"),
     "katie": Viewer("Katie", frozenset({"company_admin"}), False, "acc-katie"),
     "root": Viewer("Root", frozenset({"super_admin"}), False, "acc-root")}
TODAY = date(2026, 10, 7)


def iid(n):
    return f"bra-{n:032x}"


def rec(i, **kw):
    r = {"id": i, "version": 1, "type": "brainstorm", "title": f"Intent {i}", "purpose": "Why", "created_by": "acc-janet", "created_at": "2026-10-01T09:00:00Z",
         "areas": ["Operations"], "people": {"organiser": {"account_id": "acc-janet", "name": "Janet Shaw"}, "participants": [{"account_id": "acc-aaron", "name": "Aaron Lyle"}],
                                               "affected": [{"account_id": "acc-grace", "name": "Grace Ward"}], "observers": []},
         "state": "open", "time_box": {"starts": "2026-10-01", "ends": "2026-10-09", "extended_by": []}, "stages": [{"key": "wall", "state": "open"}],
         "closure": {}, "ratings": [], "share": {"who_may_open": []}, "updated_at": "2026-10-01T09:00:00Z"}
    r.update(kw)
    return r


@pytest.fixture
def plane(tmp_path):
    return PlaneStore(tmp_path).create("ardmore")


def save(plane, r):
    return S.create_intent(plane, r)  # the store writes the record and its index row


def add(plane, i=None, kind="card_added", who=AARON, detail=None, status="act", **kw):
    return ev.append_event(plane, i or iid(1), kind, who, {"store": "m1_wall", "id": "c1"}, detail if detail is not None else {"lane": "processes"}, status, **kw)


def test_log_is_append_only_with_next_seq_pointer_and_torn_line(plane):
    save(plane, rec(iid(1)))
    assert [add(plane)["seq"], add(plane)["seq"]] == [1, 2]
    path = plane.path("intents", iid(1), "events.jsonl")
    before = path.read_text().splitlines()
    with open(path, "a") as f:
        f.write('{"seq": 3, "kind": "car')  # a crash leaves a torn last line
    assert [e["seq"] for e in ev.read_events(plane, iid(1))] == [1, 2]
    assert add(plane)["seq"] == 3  # appended after the torn line, which stays and is skipped
    assert path.read_text().splitlines()[:2] == before
    r = read_json_strict(plane.path("intents", iid(1), "intent.json"))
    assert r["events"]["last_seq"] == 3 and r["event_count"] == 3 and r["version"] == 1
    with pytest.raises(ev.EventRefused):
        add(plane, detail={"lane": "x" * 81})
    with pytest.raises(ev.EventRefused):
        add(plane, detail={"text": "free words"})


def test_a_draft_is_never_an_act_and_an_agent_never_signs(plane):
    save(plane, rec(iid(1)))
    d = add(plane, kind="north_drafted", who="north", detail={"draft_of": "closure"}, status="draft")
    assert d["by"] is None and d["agent"] == "north" and d["status"] == "draft"
    bad = [dict(kind="card_added", who="north"), dict(kind="signed", who="north", detail={"what": "charter"}),
           dict(kind="north_drafted", who=AARON, detail={"draft_of": "closure"}, status="draft"),
           dict(kind="lens_drafted", who="north", detail={"draft_of": "business_term"}, status="draft"),
           dict(kind="north_drafted", who="north", detail={"draft_of": "poem"}, status="draft"),
           dict(kind="north_drafted", who="north", detail={"draft_of": "closure"}, status="act"),
           dict(kind="extended", who=None, anonymous=True, detail={}), dict(kind="signed", who=None, detail={"what": "charter"})]
    for b in bad:
        with pytest.raises(ev.EventRefused):
            add(plane, **b)
    c = add(plane, kind="definition_confirmed", who=JANET, detail={"kind": "business", "edited": True}, confirms=d["seq"])
    assert c["confirms"] == 1 and c["agent"] is None
    clock = add(plane, kind="stage_closed", who="north", detail={"stage": "wall", "by_clock": True})
    assert clock["by"] is None and clock["agent"] is None
    with pytest.raises(ev.EventRefused):
        add(plane, kind="card_added", who=AARON, confirms=99)
    save(plane, rec(iid(2), state="closed"))
    with pytest.raises(ev.EventRefused):
        add(plane, iid(2))  # work stops at close
    assert add(plane, iid(2), kind="rated", who=None, anonymous=True, detail={})["by"] is None
    assert ev.try_append(plane, iid(2), "card_added", AARON, None, {}, "act") is None  # logged, never raised


def lines_for(plane, who, i=None):
    i = i or iid(1)
    r = read_json_strict(plane.path("intents", i, "intent.json"))
    info = sx.tier_for(r, V[who])
    return info, ev.cut(plane, r, ev.read_events(plane, i), V[who], info)


def test_per_viewer_cuts_anonymous_sealed_restricted_and_admin(plane):
    save(plane, rec(iid(1)))
    add(plane, kind="opened", who=JANET, detail={"type": "brainstorm"})
    add(plane, who=None, anonymous=True)
    add(plane, who=AARON, sealed=True)
    ev.append_event(plane, iid(1), "definition_confirmed", JANET, {"store": "glossary", "id": "month-end"}, {"kind": "business"}, "act")
    ev.append_event(plane, iid(1), "definition_confirmed", JANET, {"store": "glossary", "id": "payroll-total"}, {"kind": "business"}, "act")
    ev.append_event(plane, iid(1), "signed", JANET, {"store": "charter", "id": "c"}, {"what": "charter"}, "act")
    store.record(plane, "governance.field_rules.payroll-total.personal", "yes", {"mark": "stated", "by": "Janet", "from": "test"})
    store.record(plane, "governance.field_rules.payroll-total.may_see", ["janet shaw"], {"mark": "stated", "by": "Janet", "from": "test"})
    raw = plane.path("intents", iid(1), "events.jsonl").read_text()
    assert "acc-" not in raw.splitlines()[1]  # the anonymous line holds no account id anywhere
    _info, aaron = lines_for(plane, "aaron")
    anon = next(ln for ln in aaron if ln["anonymous"])
    assert anon["who"] == "Anonymous" and anon["person"] is None
    sealed = next(ln for ln in aaron if ln["stub"])
    assert sealed["sentence"] == "A sealed card was added" and sealed["who"] is None and "Aaron" not in json.dumps(sealed)
    assert not any("payroll" in json.dumps(ln) for ln in aaron)  # restricted line dropped, no stub
    assert len(aaron) == 5  # opened, anonymous card, sealed stub, one definition, signed
    assert len(lines_for(plane, "janet")[1]) == 6  # the list names Janet, so she sees the restricted line
    info, admin = lines_for(plane, "katie")
    assert info["tier"] == 1 and {ln["kind"] for ln in admin} == {"opened", "signed"}
    assert sx.tier_for(read_json_strict(plane.path("intents", iid(1), "intent.json")), V["root"])["tier"] == 0
    assert lines_for(plane, "grace")[0]["tier"] == 2  # affected, no tab
    s = ev.summary(aaron, False)
    assert s["anonymous"] == 1 and all(p["few"] and p["count"] is None for p in s["people"])


def test_search_returns_only_visible_intents_and_never_sealed_or_anonymous_text(plane):
    sx.set_body_source(lambda p, i: [{"text": "Capital calls arrive late", "sealed": False, "anonymous": False},
                                     {"text": "Secret payroll worry", "sealed": True, "anonymous": False},
                                     {"text": "Anonymous worry about audit", "sealed": False, "anonymous": True}])
    try:
        save(plane, rec(iid(1), title="Onboarding review"))
        save(plane, rec(iid(2), title="Hidden draft", state="draft"))
        save(plane, rec(iid(3), title="Private matter", created_by="acc-zed", people={"organiser": {"account_id": "acc-zed", "name": "Zed"}}, areas=["Legal"]))

        def q(who, **p):
            return sx.query_index(plane, V[who], p, today=TODAY)

        assert [c["id"] for c in q("aaron")["items"]] == [iid(1)]
        assert {c["id"] for c in q("janet")["items"]} == {iid(1), iid(2)}  # her own draft
        assert q("katie")["total"] == 2 and iid(2) not in {c["id"] for c in q("katie")["items"]}  # a draft is for its starter alone
        assert q("grace")["items"][0]["purpose"] == "Why" and q("grace")["items"][0]["can_open"] is False
        hit = q("aaron", q="capital")["items"]
        assert hit and hit[0]["match"]["field"] == "card text"
        for text in ("secret payroll", "audit", "payroll"):
            assert q("janet", q=text)["items"] == []
        assert "Secret payroll" not in json.dumps(read_json_strict(plane.path("intents", "_index.json")))
        assert q("grace", q="capital")["items"] == []  # card text is searched only for readers
        assert q("aaron", q="legal")["items"] == []
        assert q("root")["items"][0]["purpose"] is None and q("root")["items"][0]["stage_name"] is None
        assert sx.query_index(plane, V["root"], {}, titles_private=True, today=TODAY)["items"][0]["title"] is None
    finally:
        sx.set_body_source(None)


def test_search_filters_facets_and_pagination(plane):
    for n in range(7):
        save(plane, rec(iid(n), title=f"Review {n}", created_at=f"2026-10-0{n + 1}T09:00:00Z", time_box={"starts": f"2026-10-0{n + 1}", "ends": "2026-10-09", "extended_by": []}, type="problem" if n % 2 else "brainstorm",
                        state="closed" if n == 6 else "open"))

    def q(**p):
        return sx.query_index(plane, V["aaron"], p, today=TODAY)

    out = q(view="home", limit="3")
    assert out["total"] == 6 and len(out["items"]) == 3 and out["next_cursor"] and out["total_visible"] == 6
    ids = [c["id"] for c in out["items"]]
    more = q(view="home", limit="3", cursor=out["next_cursor"])
    ids += [c["id"] for c in more["items"]]
    assert ids == [iid(5), iid(4), iid(3), iid(2), iid(1), iid(0)] and more["next_cursor"] is None  # newest first, no repeat, no skip
    assert q(view="past")["items"][0]["id"] == iid(6)
    f = q(view="home", type="problem")
    assert f["total"] == 3 and f["facets"]["type"] == {"problem": 3, "brainstorm": 3}  # a group counts with the others applied, not its own
    assert q(limit="0")["items"] == []
    assert q(q="revi")["total"] == 7 and q(q="revi zzz")["items"] == []  # every word, from the start of a word
    assert q(q="a")["total"] == 7  # one letter is ignored
    assert sx.working_days(date(2026, 10, 7), date(2026, 10, 12)) == 3
    assert S._row(S.create_intent(plane, rec(iid(9), ratings=[{"score": 5}, {"score": 4}])))["rating_avg"] is None  # from three ratings only


def test_lines_other_screens_wrote_by_hand_never_break_the_tab_or_leak_a_name(plane):
    save(plane, rec(iid(1)))
    add(plane)
    with open(plane.path("intents", iid(1), "events.jsonl"), "a") as f:  # affected.py, closure.py, lens.py write their own kinds by hand
        f.write(json.dumps({"seq": 2, "at": "2026-10-07T01:00:00Z", "kind": "note_to_organiser", "status": "act", "anonymous": True,
                            "by": {"account": "acc-grace", "name": "Grace Ward", "role": "affected"}}) + "\n")
        f.write(json.dumps({"seq": 3, "at": "2026-10-07T01:01:00Z", "kind": "lens_run_started", "status": "draft", "agent": "Lens", "by": {"account": "", "name": ""}}) + "\n")
        f.write(json.dumps({"seq": 4, "at": "2026-10-07T01:02:00Z", "kind": "kind_from_the_future", "status": "act", "by": {"account": "a", "name": "Aaron Lyle"}}) + "\n")
    _info, lines = lines_for(plane, "aaron")
    assert [ln["group"] for ln in lines] == ["talk", "talk", "agent", "other"]
    assert "Grace" not in json.dumps(lines) and "acc-grace" not in json.dumps(lines) and lines[1]["who"] == "Anonymous"
    assert lines[2]["agent"] == "lens" and lines[2]["person"] is None and lines[3]["sentence"] == "Aaron: kind from the future"
    assert lines_for(plane, "katie")[1] == []  # the admin's milestones never take a foreign kind


# ---- F07: one writer (spec 16, ruling R4)

SRC = Path(__file__).resolve().parents[2]
WRITERS = {"_event", "_log", "_log_alone", "try_append", "append_event", "note_event", "record_event", "put"}


# N2 (10 Oct): comments/events.jsonl is the comment store's own append-only log, written only by n2_comments._append; not an intent's log
OTHER_LOGS = {"n2_comments.py"}


def _code_files():
    return [p for root in ("sh_platform", "modules") for p in (SRC / root).rglob("*.py")
            if "tests" not in p.parts and p.name != "events.py" and p.name not in OTHER_LOGS]


def test_no_file_writes_events_jsonl_by_hand():
    """Nothing but events.py opens an events.jsonl for writing: a line that names the file may only read it."""
    bad = []
    for p in _code_files():
        text = p.read_text(encoding="utf-8")
        if "events.jsonl" in text and re.search(r"""open\([^)]*["']a["']|\.open\(["']a["']|write_text|\.write\(json""", text):
            bad.append(p.name)
    assert bad == [], bad


def test_every_kind_written_in_code_has_wording_and_a_detail_list():
    kinds = set()
    for p in _code_files():
        if "intents" not in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in WRITERS:
                kinds |= {a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str) and re.fullmatch(r"[a-z]+(_[a-z]+)+", a.value)}
                kinds |= {e.value for a in node.args if isinstance(a, ast.Tuple) for e in a.elts[:1] if isinstance(e, ast.Constant)}
    kinds -= {"north_drafted", "lens_drafted", "define_strategically"}  # the last is a stage name
    unknown = sorted(k for k in kinds if k not in ev.DETAIL and k not in {"settings_saved", "register_download", "admin_cancel", "closure_signed", "closed_incomplete"})
    assert unknown == [], unknown  # a kind written in code but missing from the kinds table would be refused at append time
    for k in ev.KINDS:
        line = ev._sentence({"kind": k, "detail": {}, "status": "act"}, "Aaron", None, False)
        assert line and line != f"Aaron: {k.replace('_', ' ')}", f"{k} has no screen wording"
    for k in ("link_created", "source_cancelled", "target_cancelled", "source_checked", "note_added", "share_requested", "person_declined", "person_role_changed",
              "person_removed", "person_reminded", "cancelled_by_admin", "build_ready_changed", "handed_to_build", "shelf_refused"):
        assert k in ev.DETAIL


def test_hand_written_kinds_go_through_the_writer_with_their_rules(plane):
    save(plane, rec(iid(1)))
    ok = [("tap_added", None, {"item": "i1", "signed": False}, True), ("note_to_organiser", None, {"signed": False}, True),
          ("late_thought", None, {"about_kind": "i"}, True), ("shelf_refused", AARON, {"cluster": "c1", "to": "must", "missing": "may_see"}, False),
          ("person_declined", AARON, {"role": "participant"}, False), ("cancelled_by_admin", JANET, {}, False)]
    for kind, who, detail, anon in ok:
        e = ev.append_event(plane, iid(1), kind, who, None, detail, "act", anonymous=anon)
        assert (e["by"] is None) == anon and e["anonymous"] == anon
    assert ev.append_event(plane, iid(1), "week_opened", "north", None, {"week_key": "2026-W41", "by_clock": True}, "act")["by"] is None
    assert ev.append_event(plane, iid(1), "lens_run_started", "lens", None, {"measures": 3, "retry": False}, "draft")["agent"] == "lens"
    assert ev.append_event(plane, iid(1), "record_frozen", "north", None, {}, "draft")["status"] == "draft"
    for bad in (dict(kind="lens_run_started", who="north", detail={}, status="draft"), dict(kind="person_removed", who=None, detail={}, status="act"),
                dict(kind="cancelled_by_admin", who=None, detail={}, status="act", anonymous=True), dict(kind="tap_added", who=AARON, detail={"text": "words"}, status="act")):
        with pytest.raises(ev.EventRefused):
            ev.append_event(plane, iid(1), bad["kind"], bad["who"], None, bad["detail"], bad["status"], anonymous=bad.get("anonymous", False))
    seqs = [e["seq"] for e in ev.read_events(plane, iid(1))]
    assert seqs == list(range(1, len(seqs) + 1))  # one counter, no repeat
    r = read_json_strict(plane.path("intents", iid(1), "intent.json"))
    assert r["events"]["count"] == len(seqs) == r["event_count"]


def test_creating_and_opening_an_intent_leave_lines(plane):
    from sh_platform.intents import records as R
    save(plane, rec(iid(1), state="open", stages=[{"key": "wall", "state": "open"}, {"key": "next", "state": "waiting"}]))
    janet = V["janet"]
    R._trail(plane, janet, S.read_intent(plane, iid(1)), {"state": "draft", "stages": {"wall": "waiting", "next": "waiting"}}, {})
    R._trail(plane, janet, S.read_intent(plane, iid(1)), {"state": "open", "stages": {"wall": "open", "next": "waiting"}}, {})  # no move, no line
    kinds = [e["kind"] for e in ev.read_events(plane, iid(1))]
    assert kinds == ["opened", "stage_opened"], kinds
    R._trail(plane, janet, S.read_intent(plane, iid(1)), {"state": "open", "stages": {"wall": "open", "next": "waiting"}}, {})
    assert [e["kind"] for e in ev.read_events(plane, iid(1))] == ["opened", "stage_opened"]  # one opened line only


def test_link_line_shows_the_other_title_only_to_those_who_may_read_it(plane):
    """F28: a link line carries the other intent's title for a content reader; others read the plain sentence with the usual note, never the title."""
    save(plane, rec(iid(1)))
    save(plane, rec(iid(2), title="Quarter close fixes", people={"organiser": {"account_id": "acc-janet", "name": "Janet Shaw"}, "participants": [], "affected": [], "observers": []}))
    ev.append_event(plane, iid(1), "link_created", JANET, {"store": "intents", "id": iid(2)}, {"link_id": "l1", "dir": "to", "kind": "from"}, "act")
    ev.append_event(plane, iid(1), "state_changed", JANET, {"store": "intent", "id": iid(1)}, {"to": "open", "from": "draft"}, "act")
    janet = [ln["sentence"] for ln in lines_for(plane, "janet")[1]]  # lines_for runs tier_for, which registers the resolver
    assert any(s.endswith(": Quarter close fixes") for s in janet) and not any("content not open to you" in s for s in janet)
    aaron = [ln["sentence"] for ln in lines_for(plane, "aaron")[1]]
    assert any("content not open to you" in s for s in aaron) and not any("Quarter close" in s for s in aaron)


def test_people_lines_name_the_person_only_by_the_people_panel_rule_and_cards_show_their_text(plane):
    """F28: invited, role-changed and removed lines name the person; a decision option and note show their text; the signed label has no raw key."""
    people = [{"person_id": "acc-aaron", "name": "Aaron Lyle", "status": "joined", "role": "participant"},
              {"person_id": "acc-grace", "name": "Grace Ward", "status": "removed", "role": "observer"}]
    save(plane, rec(iid(1), people_detail=people, outcome={"kind": "decision", "chosen": "o1", "options": [
        {"id": "o1", "name": "Hire two analysts", "notes": [{"id": "n1", "text": "Check the budget first"}]}]}))
    for kind, pid, d in (("person_invited", "acc-aaron", {"role": "participant"}), ("person_role_changed", "acc-aaron", {"role": "observer"}), ("person_removed", "acc-grace", {})):
        ev.append_event(plane, iid(1), kind, JANET, {"store": "intent_people", "id": pid}, d, "act")
    ev.append_event(plane, iid(1), "card_added", AARON, {"store": "decision_option", "id": "o1"}, {"lane": "option"}, "act")
    ev.append_event(plane, iid(1), "card_added", None, {"store": "decision_note", "id": "o1:n1"}, {"lane": "note"}, "act", anonymous=True)
    ev.append_event(plane, iid(1), "signed", JANET, {"store": "intent", "id": iid(1)}, {"what": "root_cause"}, "act")
    got = {ln["kind"]: ln["sentence"] for ln in lines_for(plane, "janet")[1]}
    assert got["person_invited"] == "Janet invited Aaron Lyle as participant"
    assert got["person_role_changed"] == "Janet changed Aaron Lyle's part to observer" and got["person_removed"] == "Janet removed Grace Ward from this intent"
    assert got["signed"] == "Janet signed the root cause"
    texts = [ln["sentence"] for ln in lines_for(plane, "janet")[1] if ln["kind"] == "card_added"]
    assert "Hire two analysts" in texts[0] and texts[1] == "Anonymous added a card to Note: Check the budget first", texts
    aaron = {ln["kind"]: ln["sentence"] for ln in lines_for(plane, "aaron")[1]}  # Aaron is named on the intent, so he reads the person still in, not the removed one
    assert "someone" in aaron["person_removed"] and "Aaron Lyle" in aaron["person_invited"]
    grace = {ln["kind"]: ln["sentence"] for ln in lines_for(plane, "grace")[1]}  # affected, no content tier: the sentence is plain
    assert all("Aaron Lyle" not in v for v in grace.values())


def test_legacy_kinds_have_wording_and_a_group_and_the_route_carries_created_at(plane):
    save(plane, rec(iid(1)))
    for k in ("closure_signed", "closed_incomplete", "intent_opened", "link_created", "target_cancelled"):
        plane.path("intents", iid(1), "events.jsonl").parent.mkdir(parents=True, exist_ok=True)
        with open(plane.path("intents", iid(1), "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"seq": len(ev.read_events(plane, iid(1))) + 1, "at": "2026-10-02T09:00:00Z", "kind": k, "by": JANET, "status": "act", "detail": {}}) + "\n")
    lines = lines_for(plane, "janet")[1]
    assert all(ln["group"] != "other" for ln in lines) and "Janet signed the closing summary" in {ln["sentence"] for ln in lines}
