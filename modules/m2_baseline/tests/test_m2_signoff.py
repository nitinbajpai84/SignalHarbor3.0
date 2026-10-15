"""M2-23 unknowns and acceptance, M2-25 owner sign-off and countersign, M2-26 readiness, M2-27 protection of human work,
X-08 audit trail. The real app over temporary folders; the other packages' files are fixtures (test_m2_signoff_kit.py)."""
import pytest

from m2_kit import BASE, login
from modules.m2_baseline.domain import signoff as S
from modules.m2_baseline.domain.readiness import load_contract
from modules.m2_baseline.store.signoff import SignoffStore, audit_intact
from test_m2_signoff_kit import BID, Team, answer, confirm_all, everyone_answers, kpi, me, seed, sign_both, standard_answers, standard_kpis, stated


def get(team, who="sam"):
    r = team.c[who].get(team.url("/review"))
    assert r.status_code == 200, r.text
    return r.json()


def by_id(view):
    return {k["id"]: k for k in view["kpis"]}


@pytest.fixture
def team(world):
    seed(world)
    return Team(world)


# ---- the review screen (M2-23) ------------------------------------------------------------------------------------
def test_review_lists_each_kpi_with_what_is_still_unknown(team):
    k = by_id(get(team))
    assert k["K1"]["state"] == "ready" and k["K1"]["unknowns"] == []
    assert k["K2"]["state"] == "ready" and k["K2"]["tracking"]["label"] == "Not tracked today"
    assert "Source is unknown" in k["K2"]["unknowns"] and "When it arrives is unknown" in k["K2"]["unknowns"]
    assert k["K3"]["state"] == "blocked" and k["K3"]["unknowns"] == ["No business owner: the sponsor needs to name one"]


def test_review_shows_next_steps_for_what_is_not_tracked_and_the_one_page_view(team):
    sam = team.c["sam"]
    r = sam.put(team.url("/review/K2"), json={"tentative_date": "2027-03-31", "next_step": "Ask the custodian for a feed", "project": "Data hub"})
    assert r.status_code == 200
    assert by_id(r.json())["K2"]["review"] == {"tentative_date": "2027-03-31", "next_step": "Ask the custodian for a feed",
                                               "project": "Data hub", "accepted": None}
    assert [c["kpi_id"] for c in r.json()["coming"]] == ["K2"]          # the one-page view lists what is coming, and the project
    assert r.json()["coming"][0]["project"] == "Data hub"
    assert by_id(r.json())["K1"]["review"] is None                      # tracked today: nothing to plan
    assert sam.put(team.url("/review/K1"), json={"next_step": "x"}).status_code == 409
    assert sam.put(team.url("/review/K2"), json={"tentative_date": "soon"}).status_code == 422
    r = sam.put(team.url("/review/K2"), json={"tentative_date": ""})    # the date is optional
    assert r.status_code == 200 and by_id(r.json())["K2"]["review"]["tentative_date"] is None


def test_the_sponsor_accepts_unknown_for_now_and_it_records_who_and_when(team):
    team.c["sam"].put(team.url("/review/K2"), json={"next_step": "Ask the custodian"})
    assert team.c["bea"].post(team.url("/review/K2/accept")).status_code == 403       # route refuses a non-sponsor
    assert team.c["sam"].post(team.url("/review/K1/accept")).status_code == 409       # tracked today
    r = team.c["sam"].post(team.url("/review/K2/accept"))
    acc = by_id(r.json())["K2"]["review"]["accepted"]
    assert acc["by"] == me("sam") and acc["at"]
    assert team.c["sam"].post(team.url("/review/K2/accept")).status_code == 409
    changed = team.c["sam"].put(team.url("/review/K2"), json={"next_step": "A different plan"})
    assert by_id(changed.json())["K2"]["review"]["accepted"] is None                  # a new plan needs a new acceptance
    entries = team.c["sam"].get(team.url("/audit")).json()["entries"]
    assert [e["action"] for e in entries] == ["update_review", "accept", "update_review"]
    assert "withdrawn" in entries[-1]["detail"]


def test_no_owner_blocks_that_kpi_until_the_sponsor_names_one(team):
    r = team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"})
    assert r.status_code == 409 and r.json()["error"] == "no_owner" and "sponsor can name one" in r.json()["message"]
    assert team.c["bea"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": me("bea")}).status_code == 403
    r = team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": me("bea")})
    k3 = by_id(r.json())["K3"]
    assert k3["state"] == "not_ready" and k3["parts"][0]["named_by_sponsor"]          # now it needs its source and sensing answers
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"}).json()["message"] == \
        "Answer the questions for this part first."                                    # N-D
    everyone_answers(team, ["K3"])
    assert team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": "Someone Else"}).status_code == 409
    assert team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "nonsense", "name": "X"}).status_code == 422
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"}).status_code == 200


def test_the_view_says_who_is_looking_and_what_they_may_sign(team):
    assert get(team, "sam")["viewer"] == {"name": me("sam"), "sponsor": True, "can_settle": True, "slot": "sponsor"}
    assert get(team, "hana")["viewer"] == {"name": me("hana"), "sponsor": False, "can_settle": True, "slot": None}
    assert get(team, "bea")["viewer"] == {"name": me("bea"), "sponsor": False, "can_settle": False, "slot": None}
    confirm_all(team)
    team.c["sam"].post(team.url("/countersign"))
    assert get(team, "sam")["viewer"]["slot"] is None and get(team, "hana")["viewer"]["slot"] == "head_of_data"


# ---- readiness (M2-26) ----------------------------------------------------------------------------------------------
def test_readiness_is_a_checklist_and_unknown_is_allowed_but_stays_visible(team):
    v = get(team)
    assert v["ready"] is True
    assert [(i["id"], i["met"], i["required"]) for i in v["items"]] == [
        ("owners", True, True), ("source", True, True), ("sensing", True, True), ("next_steps", False, False), ("confirmations", False, False)]
    assert by_id(v)["K2"]["source"]["status"] == "unknown"                           # allowed, still shown
    assert v["can_countersign"] is False


def test_not_ready_lists_exactly_what_is_missing(world):
    seed(world, kpis=[kpi("K1", "Capital call timeliness", owners=("bea", "guess", "pia")), kpi("K2", "Exposure concentration")],
         answers=[answer("K2", source=None)])  # K2: source unknown (fine); sensing stated; K1: data owner only guessed
    v = get(Team(world))
    assert v["ready"] is False
    assert v["items"][0]["missing"] == ["Capital call timeliness: Data owner not nominated yet"]
    assert v["items"][1]["met"] and v["items"][2]["met"]                              # K1 waits on its owner before it is asked for answers
    assert by_id(v)["K1"]["state"] == "not_ready"


def test_a_guessed_or_missing_answer_is_not_an_answer_and_two_different_choices_are_never_picked(world):
    guessed = answer("K1")
    guessed["source"] = {**guessed["source"], "mark": "guessed"}
    del guessed["arrival"]
    other = answer("K2")
    twin = {**answer("K2"), "id": "a2", "source": stated("A different workbook")}
    seed(world, kpis=[kpi("K1", "Capital call timeliness"), kpi("K2", "Exposure concentration")], answers=[guessed, other, twin])
    v = get(Team(world))
    items = {i["id"]: i for i in v["items"]}
    assert items["source"]["missing"] == ["Capital call timeliness: Source: source not stated yet"]  # free text is combined, not a conflict
    assert by_id(v)["K2"]["source"]["status"] == "stated"
    assert items["sensing"]["missing"] == ["Capital call timeliness: When it arrives not answered yet"]
    assert v["ready"] is False


def test_an_empty_company_has_nothing_to_be_ready_about(world):
    seed(world, kpis=[], answers=[])
    v = get(Team(world))
    assert v["ready"] is False and v["kpis"] == [] and v["items"][0]["missing"] == ["There are no measures to baseline yet"]


# ---- owner sign-off (M2-25) -----------------------------------------------------------------------------------------
def test_each_owner_confirms_only_their_own_part(team):
    r = team.c["dan"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})      # Dan owns the source, not the definition
    assert r.status_code == 409 and r.json()["error"] == "not_your_part" and me("bea") in r.json()["message"]
    r = team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
    assert r.status_code == 200
    part = by_id(r.json())["K1"]["parts"][0]
    assert part["confirmed"]["by"] == me("bea") and part["confirmed"]["at"]
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"}).status_code == 409
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K9", "part": "definition"}).status_code == 404


def test_countersign_waits_for_readiness_then_confirmations_then_two_different_people(world):
    seed(world, kpis=[kpi("K1", "Capital call timeliness", owners=("bea", "guess", "pia"))], answers=[answer("K1")])
    team = Team(world)
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_ready"
    assert "Every measure has its three owners" in r.json()["message"]
    seed(world)                                                                         # the standard fixture is ready
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "not_confirmed"
    confirm_all(team)
    assert get(team)["can_countersign"] is True                                         # K3 is blocked, so it is not asked
    assert team.c["bea"].post(team.url("/countersign")).status_code == 403              # route: owners cannot sign the whole
    a = team.c["sam"].post(team.url("/countersign"))
    assert a.status_code == 200 and a.json()["status"] == "open" and a.json()["waiting_for"] == ["Head of data"]
    assert a.json()["locked"].startswith("the baseline is already signed by")
    assert team.c["sam"].post(team.url("/countersign")).status_code == 409              # no second signature from the same person
    b = team.c["hana"].post(team.url("/countersign"))
    assert b.json()["status"] == "signed" and [s["label"] for s in b.json()["signatures"]] == ["Sponsor", "Head of data"]
    assert all(s["name"] and s["at"] for s in b.json()["signatures"])


# ---- protection of human work (M2-27) ----------------------------------------------------------------------------
def test_signed_content_is_read_only_and_a_change_needs_a_new_version(team):
    confirm_all(team)
    sign_both(team)
    for call in (lambda: team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "process"}),
                 lambda: team.c["sam"].put(team.url("/review/K2"), json={"next_step": "x"}),
                 lambda: team.c["sam"].post(team.url("/review/K2/accept")),
                 lambda: team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": "X Y"}),
                 lambda: team.c["sam"].post(team.url("/countersign"))):
        r = call()
        assert r.status_code == 409 and r.json()["error"] in ("locked", "signed")   # the one guard answers "signed" (N-E)
        assert "new version and a new sign-off" in r.json()["message"] or r.json()["message"] == "This baseline is signed; it can no longer be changed."
    assert team.c["sam"].post(team.url("/versions")).status_code == 200
    v = get(team)
    assert v["version"] == 2 and v["status"] == "open" and v["signatures"] == [] and v["can_countersign"] is False
    assert all(p["confirmed"] is None for p in by_id(v)["K1"]["parts"])                 # every confirmation and signature is blank
    assert team.c["sam"].post(team.url("/versions")).status_code == 409                 # nothing to version: v2 is still open
    confirm_all(team)
    assert sign_both(team)[1].json()["status"] == "signed"
    entries = team.c["sam"].get(team.url("/audit")).json()["entries"]
    assert [e["action"] for e in entries].count("sign") == 4 and any(e["action"] == "new_version" for e in entries)


def test_redraft_guards_name_who_signed_or_confirmed(team):
    store = SignoffStore(team.world.plane("co-a"))
    assert store.locked_reason(BID) is None
    store.refuse_if_locked(BID, "K1", "process")                                         # nothing confirmed yet: a re-draft may run
    team.c["pia"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "process"})
    assert store.locked_reason(BID, "K1", "process") == f"the process of Capital call timeliness was confirmed by {me('pia')}"
    assert store.locked_reason(BID, "K1", "source") is None and store.locked_reason(BID, "K2", "process") is None
    with pytest.raises(S.BaselineLocked, match="Capital call timeliness was confirmed by Test Process Pia"):
        store.refuse_if_locked(BID, "K1", "process")
    confirm_all(team)
    sign_both(team)
    with pytest.raises(S.BaselineLocked, match=r"signed by Test Sponsor Sam \(Sponsor\), Test Head Hana \(Head of data\)"):
        store.refuse_if_locked(BID, "K2", "source")


def test_human_work_is_recognised_so_a_redraft_can_keep_it():
    assert S.human_touched(stated("Daily by noon")) and not S.human_touched({"value": "x", "mark": "guessed", "by": "Lens"})
    assert not S.human_touched({"value": "x", "mark": "stated", "by": "Lens"})
    assert S.step_touched({"state": "edited"}) and S.step_touched({"state": "removed"}) and not S.step_touched({"state": "proposal"})


# ---- audit trail (X-08) -----------------------------------------------------------------------------------------------
def test_every_confirm_sign_accept_and_settle_is_recorded_with_who_and_when(team):
    team.c["sam"].put(team.url("/review/K2"), json={"next_step": "Ask"})
    team.c["sam"].post(team.url("/review/K2/accept"))
    team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": me("bea")})
    confirm_all(team)
    SignoffStore(team.world.plane("co-a")).record(BID, me("sam"), "settle", kpi_id="K2", detail="two source answers settled")
    log = team.c["bea"].get(team.url("/audit")).json()                                   # anyone allowed to read the item may read it
    assert log["intact"] is True
    kinds = [e["action"] for e in log["entries"]]
    assert kinds[:3] == ["update_review", "accept", "name_owner"] and kinds.count("confirm") == 6 and kinds[-1] == "settle"
    assert all(e["by"] and e["at"] and e["version"] == 1 for e in log["entries"])
    assert [e["n"] for e in log["entries"]] == list(range(1, len(kinds) + 1))
    with pytest.raises(ValueError):
        SignoffStore(team.world.plane("co-a")).record(BID, "x", "edit_history")


def test_history_cannot_be_edited(team):
    team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
    team.c["dan"].post(team.url("/confirm"), json={"kpi_id": "K1", "part": "source"})
    for method in ("put", "post", "delete", "patch"):                                    # there is no route that changes it
        assert getattr(team.c["sam"], method)(team.url("/audit")).status_code in (403, 404, 405)
    path = team.world.plane("co-a").path("intents", "m2_baseline", BID, "signoff.json")
    import json
    doc = json.loads(path.read_text())
    assert audit_intact(doc["audit"])
    doc["audit"][0]["by"] = "Somebody Else"                                              # a hand edit of the file
    path.write_text(json.dumps(doc))
    assert team.c["sam"].get(team.url("/audit")).json()["intact"] is False
    gone = {**doc, "audit": doc["audit"][1:]}
    assert audit_intact(gone["audit"]) is False


# ---- who may do what, other companies, every industry ----------------------------------------------------------------
@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none"])
def test_the_whole_flow_works_for_each_industry_and_for_a_company_with_no_pack(world, company):
    seed(world, company)
    team = Team(world, company)
    confirm_all(team)
    assert team.c["sam"].post(team.url("/countersign")).status_code == 200
    assert team.c["hana"].post(team.url("/countersign")).json()["status"] == "signed"


def test_another_company_cannot_reach_this_baseline_and_other_roles_are_refused(world):
    seed(world, "co-a")
    team = Team(world, "co-a")
    other = login(world, "co-b", "Sponsor Sue", ("sponsor",))
    assert other.get(team.url("/review")).status_code == 404                              # co-b has no such baseline
    assert other.post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"}).status_code == 404
    assert not world.plane("co-b").path("intents", "m2_baseline", BID).exists()
    guest = login(world, "co-a", "Visitor Vic", ("participant",))
    assert guest.get(team.url("/review")).status_code == 403 and guest.post(team.url("/countersign")).status_code == 403
    off = login(world, "co-off", "Admin Off", ("company_admin",))
    assert off.get(team.url("/review")).status_code in (403, 404)
    assert team.c["sam"].get(f"{BASE}/baselines/../review").status_code in (404, 422)


def test_one_person_alone_can_confirm_all_three_parts_but_the_baseline_still_needs_two_signers(world):
    seed(world, "co-solo", kpis=[kpi("K1", "Capital call timeliness", owners=("sam", "sam", "sam"))], answers=[answer("K1", by=me("sam"))])
    solo = login(world, "co-solo", "Sponsor Sam", ("sponsor", "company_admin"))
    for part in ("definition", "source", "process"):
        assert solo.post(f"{BASE}/baselines/{BID}/confirm", json={"kpi_id": "K1", "part": part}).status_code == 200
    first = solo.post(f"{BASE}/baselines/{BID}/countersign")
    assert first.status_code == 200 and first.json()["waiting_for"] == ["Head of data"]
    again = solo.post(f"{BASE}/baselines/{BID}/countersign")
    assert again.status_code == 409 and "someone else" in again.json()["message"]


def test_contract_holds_the_rule_and_the_roles():
    c = load_contract()
    assert [p["id"] for p in c["parts"]] == ["definition", "source", "process"]
    assert [s["slot"] for s in c["countersign"]] == ["sponsor", "head_of_data"]
    assert S.slot_for(c, {"sponsor"}, set()) == "sponsor" and S.slot_for(c, {"sponsor"}, {"sponsor"}) is None


# ---- identity is the account, not the name (review B1) ---------------------------------------------------------------
def _rename(world, old_name, new_name):
    acct = next(a for a in world.accounts._read() if a["display_name"] == old_name)
    world.accounts.set_display_name(acct["email"], new_name)


def test_two_accounts_with_the_same_name_cannot_confirm_a_name_only_nomination(team):
    twin = login(team.world, "co-a", "Twin Tess", ("owner",))
    _rename(team.world, "Test Twin Tess", me("bea"))                                         # a second "Test Business Bea"
    for c in (team.c["bea"], twin):
        r = c.post(team.url("/confirm"), json={"kpi_id": "K1", "part": "definition"})
        assert r.status_code == 409 and r.json()["error"] == "ambiguous_name" and "ask your administrator" in r.json()["message"]
    assert get(team)["kpis"][0]["parts"][0]["confirmed"] is None


def test_a_renamed_account_cannot_confirm_another_accounts_part(team):
    team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": me("bea")})    # named while only Bea has the name
    everyone_answers(team, ["K3"])
    mallory = login(team.world, "co-a", "Mallory", ("owner",))
    _rename(team.world, "Test Mallory", me("bea"))                                           # now Mallory shows Bea's name
    r = mallory.post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"})
    assert r.status_code == 409 and r.json()["error"] == "not_your_part"
    assert team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"}).status_code == 200
    by = by_id(get(team))["K3"]["parts"][0]["confirmed"]
    assert by["by"] == me("bea")


def test_a_nominee_with_an_account_id_still_confirms_after_a_rename(team):
    team.c["sam"].post(team.url("/review/K3/owner"), json={"part": "definition", "name": me("bea")})
    everyone_answers(team, ["K3"])
    _rename(team.world, me("bea"), "Bea Renamed")
    r = team.c["bea"].post(team.url("/confirm"), json={"kpi_id": "K3", "part": "definition"})
    assert r.status_code == 200 and by_id(r.json())["K3"]["parts"][0]["confirmed"]["by"] == "Bea Renamed"


def test_one_person_cannot_sign_both_slots_even_under_two_names(world):
    seed(world, "co-solo", kpis=[kpi("K1", "Capital call timeliness", owners=("sam", "sam", "sam"))], answers=[answer("K1", by=me("sam"))])
    solo = login(world, "co-solo", "Sponsor Sam", ("sponsor", "company_admin"))
    for part in ("definition", "source", "process"):
        assert solo.post(f"{BASE}/baselines/{BID}/confirm", json={"kpi_id": "K1", "part": part}).status_code == 200
    assert solo.post(f"{BASE}/baselines/{BID}/countersign").status_code == 200
    _rename(world, "Test Sponsor Sam", "A Different Name")
    again = solo.post(f"{BASE}/baselines/{BID}/countersign")
    assert again.status_code == 409 and again.json()["error"] == "already_signed"


def test_the_head_of_data_cannot_sign_before_the_sponsor(team):
    confirm_all(team)
    r = team.c["hana"].post(team.url("/countersign"))
    assert r.status_code == 409 and r.json()["error"] == "no_slot" and "sponsor signs first" in r.json()["message"]
    assert get(team, "hana")["viewer"]["slot"] is None
    assert team.c["sam"].post(team.url("/countersign")).status_code == 200
    assert get(team, "hana")["viewer"]["slot"] == "head_of_data"
    assert team.c["hana"].post(team.url("/countersign")).json()["status"] == "signed"


def test_an_account_that_cannot_be_found_is_refused_not_called_a_signer(team):
    team.world.accounts._write([a for a in team.world.accounts._read() if a["display_name"] != me("sam")])
    r = team.c["sam"].post(team.url("/countersign"))
    assert r.status_code in (401, 403) and "signer" not in r.text.lower()


def test_signed_with_the_outcome_record_pending_says_so_and_a_retry_closes_it(team, monkeypatch):
    from sh_platform.process_record import ProcessRecordError, ProcessRecords
    confirm_all(team)
    team.c["sam"].post(team.url("/countersign"))
    real = ProcessRecords.complete_outcome
    monkeypatch.setattr(ProcessRecords, "complete_outcome", lambda self, oid: (_ for _ in ()).throw(ProcessRecordError("down")))
    r = team.c["hana"].post(team.url("/countersign"))
    assert r.status_code == 200 and r.json()["status"] == "signed" and r.json()["record_pending"] is True
    assert team.c["hana"].get(team.url("/handoff")).status_code == 200                  # the outcome record itself was written
    monkeypatch.setattr(ProcessRecords, "complete_outcome", real)
    r = team.c["hana"].post(team.url("/countersign"))                                   # the same action retries the closing step
    assert r.status_code == 200 and r.json()["record_pending"] is False
    assert team.c["hana"].post(team.url("/countersign")).status_code == 409             # nothing left to sign
