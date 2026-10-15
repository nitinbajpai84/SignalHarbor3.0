"""CRITIC-M2 round 4 fixes (defects 4 to 9, P3, P4, P6, P7, N10): restricted measures show no name, a plain refusal instead of a bare
404, the analyst's note on undecided privacy, tracking and wording. Synthetic data; throwaway test accounts."""
from m2_kit import BASE, login
from test_m2_signoff_kit import Team, me, seed, standard_answers, standard_kpis
from test_m2_worklist import confirm, kpi_url, seed_charter, start

RESTRICTED = "This measure is restricted to its named people."


def hidden_k1(world):
    kpis = standard_kpis()
    kpis[0] = {**kpis[0], "name": "Bonus pool SECRETNAME", "governance": {"personal": "yes", "sensitive": True, "may_see": []}}
    seed(world, kpis=kpis, answers=standard_answers())
    return Team(world)


# ---- P3: a plain refusal for a measure that exists but is hidden; an id that does not exist stays "not found"

def test_a_hidden_measure_is_refused_plainly_and_a_missing_one_is_not_found(world):
    t = hidden_k1(world)
    for who in (t.analyst, t.c["sam"]):
        r = who.post(t.url("/confirm"), json={"kpi_id": "K1", "part": "business"})
        assert r.status_code == 403 and r.json()["message"] == RESTRICTED and "SECRETNAME" not in r.text and "K1" not in r.text
        assert who.post(t.url("/confirm"), json={"kpi_id": "NOPE", "part": "business"}).status_code == 404
    r = t.analyst.put(t.url("/process-map/K1/tracking"), json={"status": "partly"})
    assert r.status_code == 403 and r.json()["message"] == RESTRICTED
    assert t.analyst.put(t.url("/process-map/NOPE/tracking"), json={"status": "partly"}).status_code == 404


# ---- P4: the analyst is told, in the same plain words as the sponsor, that measures wait for the organiser

def test_the_analyst_and_sponsor_are_told_how_many_measures_wait_for_the_organiser_without_names(world):
    admin = login(world, "co-a", "Pat Owner", ("company_admin",))
    v = start(admin, seed_charter(world))
    for kid in ("K0", "K1"):
        v = confirm(admin, v, suggestion_id=kid, problem_ids=["p1"])
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    for role in ("analyst", "sponsor"):
        body = login(world, "co-a", f"Some {role.title()}", (role,)).get(url).json()
        assert body["governance_note"] == "2 measures are visible only to the organiser until they set who may see them."
        assert all(k["name"] == "A restricted measure" for k in body["kpis"])
    assert admin.get(url).json()["governance_note"].startswith("2 measures are visible only to you")
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "no"})
    admin.put(kpi_url(v, "K1", "/governance"), json={"personal": "no"})
    assert login(world, "co-a", "Later Analyst", ("analyst",)).get(url).json()["governance_note"] is None


# ---- defect 8: the reminder subject counts the measures, never lists them

def test_the_reminder_subject_counts_the_measures_and_does_not_list_them():
    from modules.m2_baseline.domain import requests as R
    names = [f"Measure number {i}" for i in range(11)]
    mail = R.reminder_text("Wei Chen", "Mei Tan", names)
    assert mail["subject"] == "Reminder: a few questions about 11 measures" and "Measure number 3" not in mail["subject"]
    assert R.reminder_text("Wei", "Mei", ["Only one"])["subject"] == "Reminder: a few questions about 1 measure"


# ---- P6: an organisation, a team or a title typed as a person is never put in the vault as a person

EXACT = ["Northgate Custody", "Bluewater Fund Services", "Managers investor relations", "Sponsor Lakeside"]  # as they sat in the live vault
COMPANY = "Illustrative Lakeside Family Office"


def vault_entries(plane) -> list[dict]:
    from sh_platform.egress.vault import NameVault
    v = NameVault(plane)
    return list(v._parse(v._read_raw()).values())


def test_the_module_2_registrar_never_makes_these_names_people(world):
    from modules.m2_baseline.agent import lens
    plane = world.plane("co-a")
    lens.register_names(plane, COMPANY, ["Mei Tan", *EXACT])
    persons = {e["name"] for e in vault_entries(plane) if e["kind"] == "person"}
    assert "Mei Tan" in persons and not set(EXACT) & persons
    assert {"Northgate Custody", "Bluewater Fund Services", "Managers investor relations"} <= {e["name"] for e in vault_entries(plane) if e["kind"] == "company"}
    assert "Sponsor Lakeside" not in {e["name"] for e in vault_entries(plane)}  # a title and a word of the company's own name: nobody


def test_the_shared_rule_takes_the_same_names_when_they_arrive_as_people():
    """Module 1 hands every participant name straight to protected_names, so the rule itself must not call these people."""
    from sh_platform.egress.names import protected_names
    got = protected_names(COMPANY, ["Mei Tan", *EXACT])
    assert ("person", "Mei Tan") in got
    assert not [n for k, n in got if k == "person" and n in EXACT] and "Sponsor Lakeside" not in {n for _, n in got}
    assert {("company", "Northgate Custody"), ("company", "Bluewater Fund Services"), ("company", "Managers investor relations")} <= set(got)


def test_a_person_with_a_lowercase_particle_stays_a_person_with_every_part():
    from sh_platform.egress.names import protected_names
    for full, parts in (("Ian de Souza", {"Ian", "Souza"}), ("Ludwig van Beethoven", {"Ludwig", "Beethoven"}), ("Anna bin Ali", {"Anna", "Ali"})):
        got = set(protected_names("Lakeside Family Office", [full]))
        assert ("person", full) in got and {("person", p) for p in parts} <= got and ("company", full) not in got


def test_a_person_whose_name_is_in_the_companys_name_is_still_protected():
    from sh_platform.egress.names import protected_names
    got = set(protected_names("Grace Bank Ltd", ["Grace Bank"]))
    assert ("person", "Grace") in got and ("person", "Grace Bank") in got
    assert ("person", "Sponsor Lakeside") not in set(protected_names("Lakeside Family Office", ["Sponsor Lakeside"]))  # a title plus a company word is still nobody


def test_the_vault_clean_up_tool_keeps_a_person_with_a_particle(world):
    import sys
    from pathlib import Path
    from sh_platform.egress.vault import NameVault
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    import vault_clean
    plane = world.plane("co-a")
    v = NameVault(plane)
    v.register("company", COMPANY)
    for n in ("Ian de Souza", "Ian", "Souza"):
        v.register("person", n)
    vault_clean.clean(plane)
    now = {(e["kind"], e["name"]) for e in vault_entries(plane)}
    assert {("person", "Ian de Souza"), ("person", "Ian"), ("person", "Souza")} <= now and ("company", "Ian de Souza") not in now


def test_every_restricted_stub_has_the_same_state():
    from modules.m2_baseline.domain import worklist as W
    from modules.m2_baseline.domain.provenance import prov
    bare = W.new_kpi("K1", "Pay", [], None)
    drafted = {**bare, "definition": prov("A definition", "stated", "Pat")}
    asked = {**bare, "questions": [{"id": "q", "question": "Q?", "answer": prov(None, "unknown", "Lens")}]}
    assert {W.hidden(k, s)["state"] for k in (bare, drafted, asked) for s in ("draft", "review", "signed")} == {"not_started"}


def test_the_vault_clean_up_tool_moves_them_out_of_the_people(world):
    """The live vault still holds them as people; the tool (run by Nitin, never here) must fix that, and be safe to run twice."""
    import sys
    from pathlib import Path
    from sh_platform.egress.vault import NameVault
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    import vault_clean
    plane = world.plane("co-a")
    v = NameVault(plane)
    v.register("company", COMPANY)
    for n in ["Mei Tan", *EXACT]:
        v.register("person", n)
    vault_clean.clean(plane)
    now = {(e["kind"], e["name"]) for e in vault_entries(plane)}
    assert ("person", "Mei Tan") in now and not {("person", n) for n in EXACT} & now and ("company", "Northgate Custody") in now
    assert "Sponsor Lakeside" not in {n for _, n in now}
    assert vault_clean.clean(plane)["removed"] == 0


# ---- defect 4: every screen can say "signed, read-only"

def test_the_requests_catalogue_and_work_list_all_say_when_the_baseline_is_signed(world):
    from test_m2_signoff_kit import confirm_all, sign_both
    seed(world)
    t = Team(world)
    where = lambda: (t.c["hana"].get(t.url("/requests")).json()["signed"], t.c["hana"].get(f"{BASE}/baselines/{t.url().rsplit('/', 1)[1]}/catalogue").json()["signed"])  # noqa: E731
    assert where() == (False, False)
    confirm_all(t, ("K1", "K2"))
    t.c["sam"].put(t.url("/review/K2"), json={"next_step": "x"})  # K2 is not tracked today: a next step, then the sponsor accepts it
    t.c["sam"].post(t.url("/review/K2/accept"))
    a, b = sign_both(t)
    assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
    assert where() == (True, True)


# ---- defect 9: the baselines list says which charter each came from

def test_each_baseline_in_the_list_carries_its_charters_title_and_date(world):
    from test_m2_worklist import PROBLEMS
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    one = seed_charter(world, problems=PROBLEMS[:1])
    two = seed_charter(world, problems=PROBLEMS)
    start(c, one)
    start(c, two)
    out = c.get(f"{BASE}/baselines").json()
    titles = {b["charter_title"] for b in out["baselines"]}
    assert titles == {"Calls arrive too late", "Calls arrive too late and 1 more"}
    assert all(b["charter_signed_at"].startswith("2026-10-01") for b in out["baselines"])
    assert {x["title"] for x in out["charters"]} == titles
    assert start(c, None) and {b["charter_title"] for b in c.get(f"{BASE}/baselines").json()["baselines"]} >= {None}  # a baseline with no charter: none


# ---- defect 6: sign-off wording

def test_a_conflict_option_and_the_audit_use_plain_words_not_ids(world):
    from test_m2_signoff_kit import answer
    other = {**answer("K1", tracked="no", by="Test Process Pia"), "id": "z"}
    seed(world, answers=[answer("K1"), other, *standard_answers()[1:]])
    t = Team(world)
    view = t.c["hana"].get(t.url("/review")).json()
    s = next(s for k in view["kpis"] if k["id"] == "K1" for s in k["sensing"] if s["id"] == "tracked_today")
    assert s["status"] == "conflict" and {o["label"] for o in s["options"]} == {"Tracked today", "Not tracked today"}
    after = t.c["hana"].post(t.url("/signoff/settle"), json={"kpi_id": "K1", "field": "tracked_today", "value": "no"}).json()
    s = next(s for k in after["kpis"] if k["id"] == "K1" for s in k["sensing"] if s["id"] == "tracked_today")
    assert s["settled"]["label"] == "Not tracked today"
    e = next(e for e in t.c["hana"].get(t.url("/audit")).json()["entries"] if e["action"] == "settle")
    assert e["detail"] == "settled tracked today" and "_" not in e["detail"]


def test_a_measure_covered_by_its_named_owners_is_marked_so_not_left_as_not_accepted(world):
    kpis = standard_kpis()
    kpis[1] = {**kpis[1], "governance": {"personal": "yes", "sensitive": True, "may_see": [me(k) for k in ("bea", "dan", "pia")]}}  # K2: not tracked, seen by its three owners, not by the sponsor
    seed(world, kpis=kpis)
    t = Team(world)
    from test_m2_signoff_kit import everyone_answers
    everyone_answers(t, ("K2",))
    for who, part in (("bea", "definition"), ("dan", "source"), ("pia", "process")):
        t.c[who].post(t.url("/confirm"), json={"kpi_id": "K2", "part": part})
    row = lambda k: next(r for r in t.c["hana"].get(t.url("/review")).json()["kpis"] if r["id"] == k)  # noqa: E731
    assert row("K2")["review"] is not None and row("K2")["covered"] is True and row("K1")["covered"] is False


# ---- defect 7: the process map

def test_a_pack_step_is_never_labelled_manual_only_an_owner_saying_so_does():
    from modules.m2_baseline.domain import process_map as D
    pack = {"steps": [{"step_id": "p1", "lane": "Operations", "name": "Register the document", "manual": True}]}
    assert [s["manual"] for s in D.from_pack(pack, "pack")] == [False]


def test_the_maps_tracking_shows_what_the_owners_answered_while_the_map_holds_none(world):
    import json
    from test_m2_process_map import KPI, MAP, PMB, S, seed as seed_map
    answer = {"id": "a1", "owner_name": "Arjun Rao", "kpi_id": "k1", "tracked_today": S("partly")}
    seed_map(world, answers=[answer], kpis=[KPI])
    c = login(world, "co-a", "Pat Owner", ("company_admin",))
    assert c.get(MAP).json()["kpis"][0]["tracking"]["status"]["value"] == "partly"  # R4 defect 7: the review already holds it
    c.put(f"{MAP}/k1/tracking", json={"status": "tracked_now"})
    assert c.get(MAP).json()["kpis"][0]["tracking"]["status"]["value"] == "tracked_now"  # a status set on the map wins


# ---- defect 4: producer and gathered come from the owners' answers when nobody typed them

def test_producer_and_gathered_are_filled_from_the_owners_answers_and_a_typed_value_wins():
    from modules.m2_baseline.domain import worklist as W
    from modules.m2_baseline.domain.provenance import prov
    from story_answers import answers
    mine = [a for a in answers() if a["kpi_id"] == "K15"]
    k = W.new_kpi("K15", "A measure", [], None)
    got = W.with_answers(k, mine)
    assert got["producer"]["mark"] == "stated" and "Performance workbook" in got["producer"]["value"] and "Market data vendor API" in got["producer"]["value"]
    assert "Typed in by hand" in got["gathered"]["value"] and "quarterly" in got["gathered"]["value"].lower() and "Tom Ng" in got["gathered"]["by"]
    typed = {**k, "producer": prov("Our own team", "stated", "Pat")}
    assert W.with_answers(typed, mine)["producer"]["value"] == "Our own team"
    assert W.with_answers(k, []) == k  # no answers, nothing invented


def test_the_work_list_shows_the_answers_producer_to_a_viewer_who_may_see_the_measure(world):
    from m2_kit import login as _login
    admin = _login(world, "co-a", "Pat Owner", ("company_admin",))
    v = start(admin, seed_charter(world))
    v = confirm(admin, v, suggestion_id="K0", problem_ids=["p1"])
    bid = v["baseline"]["id"]
    admin.put(kpi_url(v, "K0", "/governance"), json={"personal": "no"})
    from story_answers import answer, row
    import json
    folder = world.plane("co-a").path("intents", "m2_baseline", bid)
    (folder / "answers.json").write_text(json.dumps([answer("a1", "Arjun Rao", "K0", sources=[
        row("Northgate daily file", "file_drop", "structured", "share", "Arjun Rao", "file_drop", "daily", "noon", "")])]))
    k = admin.get(f"{BASE}/baselines/{bid}").json()["kpis"][0]
    assert k["triage"]["producer"]["value"] == "Northgate daily file" and "producer" not in k["triage"]["unknown"]


def test_the_organiser_gets_no_request_unless_she_is_a_named_owner(world):
    """Defect 8: a request goes to a named owner only. The organiser sending the requests is asked about nothing she does not own."""
    import test_m2_requests_kit as K
    K.seed(world)
    org = login(world, "co-a", "Mei Tan", ("company_admin",))
    sent = K.send(org, K.BID)
    assert set(sent) == {"Tom Reyes", "Arjun Rao", "Sara Lim", "Wei Chen"}  # not "Test Mei Tan": she owns no measure here
    own = [{**k, "owners": {**k["owners"], "business": K.prov("Test Mei Tan", "stated", "Mei Tan", "work list")}} for k in K.KPIS[:1]]
    K.seed(world, bid="b" * 32, kpis=own)
    assert set(K.send(org, "b" * 32)) == {"Test Mei Tan", "Arjun Rao", "Sara Lim"}  # named: asked, as anyone is
