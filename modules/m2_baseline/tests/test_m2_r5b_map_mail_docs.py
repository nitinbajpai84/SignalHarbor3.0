"""Round 5B: process map from the measure's own technical definition, no request to the sender, restricted documents, covered measures."""
from m2_kit import BASE, login
from test_m2_requests_kit import KPIS, kpi, seed as seed_requests, send
from test_m2_signoff_kit import Team, everyone_answers, me, seed, standard_kpis

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import preread as PR
from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.store import catalogue as SC
from modules.m2_baseline.store import lens as LS
from sh_platform.context_docs.store import DocStore

PACK = {"for_kpis": ["K3", "K5"], "steps": [{"step_id": "p1", "lane": "Operations", "name": "Register the document"}]}


def measure(kid, sources, calculation, **owners):
    return {"id": kid, "name": f"Measure {kid}", "owners": {"data": prov("Wei Chen", "stated", "x"), **owners},
            "technical": {"sources": prov(sources, "guessed", "Lens", "docs"), "calculation": prov(calculation, "guessed", "Lens", "docs")}}


# ---- 4: the map comes from the measure's own technical definition, the pack only where nothing better exists

def test_two_measures_get_their_own_steps_from_their_technical_definitions_not_the_pack_path():
    names = {"S1": "Capital call tracker", "S2": "Bank file", "S9": "Hidden source"}
    a = D.from_technical(measure("K3", ["S1", "S2"], "Add the open calls; subtract the cash held"), names)
    b = D.from_technical(measure("K5", ["S2"], "Take the share held by private funds"), names)
    assert [(s["lane"], s["text"]) for s in a][:2] == [("Capital call tracker", "Provide the data for Measure K3"), ("Bank file", "Provide the data for Measure K3")]
    assert [s["text"] for s in a][2:] == ["Add the open calls", "subtract the cash held"] and {s["lane"] for s in a[2:]} == {"Wei Chen"}
    assert [s["lane"] for s in b] == ["Bank file", "Wei Chen"] and a != b
    m = D.draw([], PACK, "pack", None, None, kpi_id="K3", technical=a)
    assert {s["from"] for s in m["steps"]} == {"technical"} and "Operations" not in m["lanes"]  # the source line is the technical definition's own
    assert D.draw([], PACK, "pack", None, None, kpi_id="K3")["steps"][0]["by"] == "the pack"  # nothing better: the pack's way, for a measure it lists
    assert D.draw([], PACK, "pack", None, None, kpi_id="K9")["steps"] == []  # a measure it does not list gets nothing


def test_a_source_that_cannot_be_named_is_left_out_not_shown_as_an_id():
    steps = D.from_technical(measure("K3", ["S77", "Bank file"], "Add them up"), {})
    assert [s["lane"] for s in steps] == ["Bank file", "Wei Chen"]
    assert D.from_technical({"id": "K1", "name": "x", "owners": {}}, {}) == []


# ---- 5: nobody sends a request to the person sending the requests

def test_the_organiser_is_not_sent_a_request_for_measures_she_only_appears_on_by_a_guess(world):
    def guessed(k):
        return {**k, "owners": {**k["owners"], "business": prov("Test Zed Boss", "guessed", "Lens", "a document")}}
    seed_requests(world, kpis=[*KPIS, guessed(kpi("k4", "Own measure")), guessed(kpi("k5", "Another"))])
    assert set(send(login(world, "co-a", name="Zed Boss"))) == {"Tom Reyes", "Arjun Rao", "Sara Lim", "Wei Chen"}  # her own words naming her are still asked (round 4 test)


# ---- 6: a document that mentions personal data waits for the organiser

NOTES = b"The pay workbook has the columns salary_band and bonus_amount. Only the head of HR may see the pay file."


def upload_doc(world, text=NOTES, title="Technical notes"):
    return DocStore(world.plane("co-a")).upload("lens", "acct", "notes.md", text, title=title)["doc_id"]


def test_personal_words_are_found_from_the_generic_words_and_the_packs_own_fields():
    assert PR.personal_words("The salary_band column and the bonus", {}) == ["salary", "bonus"]
    assert PR.personal_words("Totals by fund and date", {}) == []
    parts = {"feeds": {"f": {"fields": [{"id": "client_ref", "pii": True}, {"id": "amount", "pii": False}]}}, "synonyms": {"f": {"client_ref": {"spellings": [{"spelling": "investor id"}]}}}}
    assert PR.personal_words("each row has an investor id and an amount", parts) == ["investor id"]


def test_until_decided_lens_does_not_read_the_document_for_a_measure_not_marked_personal(world):
    plane = world.plane("co-a")
    doc = upload_doc(world)
    assert "salary_band" in PR.read(plane, {}, "pay workbook salary band", restricted_ok=True)[0] or "salary band" in PR.read(plane, {}, "pay workbook salary band", restricted_ok=True)[0]
    assert PR.read(plane, {}, "pay workbook salary band", restricted_ok=False) == ("", [])  # pending: held back from every measure not marked personal
    assert LS.scans(plane)[doc]["state"] == "pending" and "salary" in LS.scans(plane)[doc]["words"]
    PR.clear(plane, doc)  # the organiser says it is not personal data
    assert "pay workbook" in PR.read(plane, {}, "pay workbook salary band", restricted_ok=False)[0]


def test_the_pre_read_names_the_document_and_the_words_and_offers_the_existing_restrict_route(world):
    doc = upload_doc(world)
    c = login(world, "co-a", name="Admin Ann")
    base = seed_baseline(world)
    row = next(d for d in c.get(f"{BASE}/baselines/{base}/preread").json()["documents"] if d["doc_id"] == doc)
    assert "salary" in row["personal_words"] and row["restrict_path"] == f"/api/agents/lens/docs/{doc}/visibility"
    assert c.post(f"{BASE}/baselines/{base}/preread/documents/{doc}/not-personal").status_code == 200
    assert "personal_words" not in next(d for d in c.get(f"{BASE}/baselines/{base}/preread").json()["documents"] if d["doc_id"] == doc)
    assert login(world, "co-a", name="Plain Pat", roles=("analyst",)).post(f"{BASE}/baselines/{base}/preread/documents/{doc}/not-personal").status_code == 403


def seed_baseline(world):
    from test_m2_glossary import seed as seed_glossary
    return seed_glossary(world, specs=[("Plain measure", "d", "no", [])])


# ---- 6: a restricted measure the sponsor cannot see is covered by its named owners, in the catalogue too

def test_the_catalogue_says_covered_by_its_named_owners_for_a_measure_the_sponsor_cannot_accept(world):
    kpis = standard_kpis()
    kpis[1] = {**kpis[1], "governance": {"personal": "yes", "sensitive": True, "may_see": [me(k) for k in ("bea", "dan", "pia")]}}
    seed(world, kpis=kpis)
    t = Team(world)
    everyone_answers(t, ("K2",))
    for who, part in (("bea", "definition"), ("dan", "source"), ("pia", "process")):
        t.c[who].post(t.url("/confirm"), json={"kpi_id": "K2", "part": part})
    assert t.c["hana"].post(f"{BASE}/baselines/{t.url().rsplit('/', 1)[1]}/catalogue/refresh").status_code == 200
    cat = SC.read_catalogue(world.plane("co-a"), t.url().rsplit("/", 1)[1])
    cell = lambda kid: C.text_of(next(r for r in cat["kpis"] if C.row_id("kpis", r) == kid)["Unknown accepted by (sponsor)"])  # noqa: E731
    assert cell("K2") == "Covered by its named owners" and cell("K1") == ""


# ---- round 5B fix round -------------------------------------------------------------------------------------------------------------

def _pmap_seed(world):
    from test_m2_process_map import PMB, seed as seed_map
    plain = {"id": "k1", "name": "Funding capacity", "governance": {"personal": "no", "sensitive": False, "may_see": []}, "owners": {},
             "technical": {"sources": prov(["Cash file"], "guessed", "Lens", "docs"), "calculation": prov("Add the Bonus pool to the cash; then report", "guessed", "Lens", "docs")}}
    secret = {"id": "k2", "name": "Bonus pool", "governance": {"personal": "yes", "sensitive": True, "may_see": ["Test Pat Owner"]}, "owners": {}}
    return PMB, seed_map(world, answers=[], kpis=[plain, secret])


def test_technical_steps_never_name_a_restricted_measure_when_drawn_and_are_filtered_again_when_read(world):
    import json
    from test_m2_process_map import MAP
    _, folder = _pmap_seed(world)
    admin = login(world, "co-a", name="Pat Owner")
    steps = lambda r: [s["text"] for s in r.json()["kpis"][0]["steps"]]  # noqa: E731
    drawn = admin.post(f"{MAP}/draw")
    assert drawn.status_code == 200 and not any("Bonus pool" in t for t in steps(drawn)) and any("report" in t for t in steps(drawn))  # drawn for the least-privileged view
    stored = json.loads((folder / "process_map.json").read_text())
    stored["k1"]["steps"].append({"id": "tech-9", "lane": "Cash file", "text": "Take the Bonus pool", "order": 9, "manual": False, "confirmed": False,
                                  "from": "technical", "state": "proposal", "by": "Lens"})  # an older map that already holds such a step
    (folder / "process_map.json").write_text(json.dumps(stored))
    sponsor = login(world, "co-a", name="Sam Sponsor", roles=("sponsor",))
    assert not any("Bonus pool" in t for t in steps(sponsor.get(MAP))) and any("report" in t for t in steps(sponsor.get(MAP)))
    assert any("Bonus pool" in t for t in steps(admin.get(MAP)))  # a person who may see the measure still sees it


# ---- a damaged scan record holds documents back; a cleared decision survives a rebuild; aliases are capped

def test_a_damaged_scan_file_holds_every_document_back_and_the_screen_says_so_plainly(world):
    plane = world.plane("co-a")
    upload_doc(world, text=b"Quarterly totals by fund and date for the committee.", title="Plain notes")
    scans = plane.path("intents", "m2_baseline") / "document_scans.json"
    scans.parent.mkdir(parents=True, exist_ok=True)
    scans.write_text("{not json")
    assert PR.read(plane, {}, "quarterly totals fund committee", restricted_ok=False) == ("", [])  # fail closed
    base = seed_baseline(world)
    r = login(world, "co-a", name="Admin Ann").get(f"{BASE}/baselines/{base}/preread")
    assert r.status_code == 200 and [d["personal_words"] for d in r.json()["documents"] if d.get("restrict_path")] == [[]]
    assert scans.read_text() == "{not json"  # never overwritten


def test_a_pay_document_does_not_reach_the_model_through_the_technical_draft_of_a_plain_measure(world):
    import test_m2_technical as TT
    bid = TT.seed(world, "co-a", [TT.kpi("K03", "Bonus pool")], cat=None)
    TT.upload(world, "co-a", "Pay notes", "## Bonus pool\n- Steps: take each target bonus and compare it with the salary_band figure.", decided=False)
    stub = TT.with_model(world, TT.Stub())
    c = login(world, "co-a")
    TT.draft(c, bid)
    assert "target bonus" not in stub.prompts  # pending: held back from a measure not marked personal
    r = c.post(TT.url(bid, "/lens/technical/redraft"), json={"kpi_id": "K03", "instruction": "Show the steps"})
    assert r.status_code == 200 and "target bonus" not in stub.prompts


def test_a_cleared_decision_survives_a_rebuild_of_the_glossary_document(world):
    from test_m2_glossary import upload
    from modules.m2_baseline.store import glossary as SG
    bid, plane = seed_baseline(world), world.plane("co-a")
    c = login(world, "co-a")
    upload(c, bid, "g.csv", b"Term,Definition\nPlain measure,The salary bonus pool of the staff.\n")
    docs = SG.read(plane, bid)["documents"]
    assert PR.review(plane, {}) == set(docs)  # pending: it mentions pay
    PR.clear(plane, docs[0])
    c.post(f"{BASE}/baselines/{bid}/glossary/build")
    new = SG.read(plane, bid)["documents"]
    assert new != docs and PR.review(plane, {}) == set()  # a new document with the same content: still cleared


def test_an_alias_is_capped():
    from modules.m2_baseline.domain import glossary as G
    terms, _ = G.parse_provided("## Cash\n- Meaning: cash in hand\n- Also: " + "x" * 400 + "\n")
    assert all(len(a) <= 120 for a in terms[0]["aliases"])


def test_lens_reads_her_own_shelf_and_norths_shared_full_but_never_norths_private(world):
    plane = world.plane("co-a")
    store = DocStore(plane)
    mine = store.upload("lens", "acct", "mine.md", b"Lens shelf passage about harbourlight custody balances.", title="Mine")["doc_id"]
    shared = store.upload("north", "acct", "shared.md", b"North shared passage about harbourlight custody statements.", title="Shared", visibility="shared_full")["doc_id"]
    private = store.upload("north", "acct", "private.md", b"North private passage about harbourlight custody secrets.", title="Private")["doc_id"]
    for d in (mine, shared, private):
        LS.set_scan(plane, d, {"words": [], "state": "cleared"})
    text, titles = PR.read(plane, {}, "harbourlight custody")
    assert set(titles) == {"Mine", "Shared"} and "secrets" not in text
    assert PR.review(plane, {}) == set()  # nothing held, and the private one is not Lens's to review



def test_a_channel_word_does_not_flag_a_document_but_pay_figures_do():
    assert PR.personal_words("Notices arrive in the shared mailbox by email, or on the phone line, to the relationship manager.", {}) == []
    assert PR.personal_words("A personal data heading alone. Contact: ops@example.test", {}) == []
    assert PR.personal_words("The salary bands and the bonus amounts by grade.", {}) == ["salary", "bonus"] or "salary" in PR.personal_words("The salary bands and the bonus amounts by grade.", {})
    assert PR.personal_words("Home address and date of birth are held.", {}) == ["home address", "date of birth"]


def test_a_pending_document_gives_nothing_to_a_non_personal_measure_even_where_the_pay_rows_sit_in_a_later_chunk(world):
    plane = world.plane("co-a")
    ordinary = "Harbourlight custody statements arrive each morning and the team reconciles them. " * 15
    rows = "\n".join(f"Row {n} | Aisha Rao | 120000 | 15000 | harbourlight reward rows" for n in range(30))  # a table with no flagged word
    doc = upload_doc(world, (ordinary + "\nExecutive emoluments and the variable pay plan follow.\n" + rows).encode(), "Mixed notes")
    assert PR.review(plane, {}) == {doc}  # flagged for the organiser
    for query in ("harbourlight custody statements reconciles", "harbourlight reward rows aisha", "executive emoluments variable pay"):
        assert PR.read(plane, {}, query, restricted_ok=False) == ("", [])  # the whole document waits
    assert "harbourlight reward rows" in PR.read(plane, {}, "harbourlight reward rows aisha", restricted_ok=True)[0]  # a personal measure: existing rule
    DocStore(plane).set_restricted("lens", doc, True)
    assert PR.read(plane, {}, "harbourlight custody statements", restricted_ok=False) == ("", [])
    DocStore(plane).set_restricted("lens", doc, False)
    PR.clear(plane, doc)  # not personal: every passage is read
    assert "reward rows" in PR.read(plane, {}, "harbourlight reward rows aisha", restricted_ok=False)[0]


def test_a_shared_summary_of_a_held_document_does_not_reach_a_non_personal_measure(world):
    plane = world.plane("co-a")
    store = DocStore(plane)
    d = store.upload("north", "acct", "pay.md", b"The executive salary schedule for harbourlight staff.", title="North pay note", visibility="shared")["doc_id"]
    store.publish_summary("north", d, "Summary: executive salary schedule for harbourlight staff.")
    assert PR.review(plane, {}) == {d}
    assert PR.read(plane, {}, "executive salary schedule harbourlight", restricted_ok=False) == ("", [])


def test_the_pay_synonyms_flag_a_document():
    for text in ("Executive emoluments for the year.", "The variable pay plan.", "An incentive for each manager.", "The comp plan for staff.", "The remuneration committee.", "Each compensation package is agreed."):
        assert PR.personal_words(text, {}), text
    assert PR.personal_words("A software package for the shared mailbox.", {}) == []


def test_lens_and_nira_say_how_many_documents_wait_for_the_organiser(world):
    doc = upload_doc(world)
    admin, other = login(world, "co-a", name="Admin Ann"), login(world, "co-a", name="Plain Pat", roles=("analyst",))
    base = seed_baseline(world)
    waiting = admin.get(f"{BASE}/baselines/{base}/lens").json()["waiting"]
    assert [(w["doc_id"], w["title"]) for w in waiting] == [(doc, "Technical notes")] and "salary" in waiting[0]["personal_words"] and waiting[0]["restrict_path"].endswith(f"/{doc}/visibility")
    assert other.get(f"{BASE}/baselines/{base}/lens").json()["waiting"] == []  # the organiser alone decides, so only she is asked
    line = admin.post(f"{BASE}/baselines/{base}/nira", json={"kind": "welcome", "step": "baselines"}).json()["text"]
    assert "1 document waits for your decision" in line
    assert "waits for your decision" not in other.post(f"{BASE}/baselines/{base}/nira", json={"kind": "welcome", "step": "baselines"}).json()["text"]
    admin.post(f"{BASE}/baselines/{base}/preread/documents/{doc}/not-personal")
    assert admin.get(f"{BASE}/baselines/{base}/lens").json()["waiting"] == []
