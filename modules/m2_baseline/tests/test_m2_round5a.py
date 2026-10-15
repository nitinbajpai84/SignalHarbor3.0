"""Critic round 5, team A: an answer never overwrites a part; every kind of owner account confirms its own technical definitions; question
noise (blank, template, ids, duplicates, stale) is gone; Lens builds catalogue rows from the technical notes; a field's meaning is its own;
a re-added measure starts clean. Stubbed model, temporary folders, synthetic wording only."""
import json

from fastapi.testclient import TestClient
from m2_kit import BASE, login
from test_m2_catalogue_xlsx import read_book
from test_m2_technical import PAT, Stub, _visitor, catalogue, draft, kpi, part, seed, upload, url, with_model

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.store import catalogue as SC
from modules.m2_baseline.store import kpis as K
from sh_platform.auth.test_accounts import make_test_account

OLD = "Cash we would still have in the worst month."


def _item(c, world, bid, kind="definition", where="Cash cushion: definition", question="Which meaning?", **extra):
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, [A.make(kind, "Two meanings.", question, where, **extra)]))
    return c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]


def _answer(c, bid, amb, **body):
    return c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/answer"), json=body)


def _k(world, bid):
    return K.read_kpis(world.plane("co-a"), bid)[0]


# ---- 1. an answer never overwrites a part ---------------------------------------------------------------------------------------------

def test_an_answer_alone_is_recorded_on_the_question_and_changes_no_part(world):
    bid = seed(world)
    c = login(world, "co-a")
    amb = _item(c, world, bid)
    r = _answer(c, bid, amb, resolution="Cash after the reserve.")  # what the old screen sent: text only
    assert r.status_code == 200 and r.json()["changed"] is None
    k = _k(world, bid)
    assert k["definition"]["value"] == OLD and k["ambiguities"][0]["status"] == "settled" and k["ambiguities"][0]["resolution"] == "Cash after the reserve."
    assert _answer(c, bid, amb, resolution="x", part="none").status_code == 422  # settled already: nothing to answer twice


def test_a_chosen_part_takes_the_persons_own_wording_and_keeps_the_old_text(world):
    bid = seed(world)
    c = login(world, "co-a")
    amb = _item(c, world, bid)
    assert _answer(c, bid, amb, resolution="Cash after the reserve.", part="definition").status_code == 422  # a part needs the new wording
    assert _answer(c, bid, amb, resolution="Cash after the reserve.", part="definition", wording="Cash after the reserve.").status_code == 422  # the bare answer
    assert _answer(c, bid, amb, resolution="Cash after the reserve.", part="sources", wording="x").status_code == 422  # a link is made with Edit
    assert _k(world, bid)["ambiguities"][0]["status"] == "open"  # a refusal saves nothing
    wording = f"{OLD} Counted after the reserve is set aside."
    r = _answer(c, bid, amb, resolution="Cash after the reserve.", part="definition", wording=wording)
    assert r.status_code == 200 and r.json()["changed"] == "definition"
    k = _k(world, bid)
    assert (k["definition"]["value"], k["definition"]["mark"], k["definition"]["by"]) == (wording, "stated", PAT)
    assert [h["value"] for h in k["technical_history"]["definition"]] == [OLD] and k["ambiguities"][0]["part"] == "definition"
    assert "technical_history" not in json.dumps(c.get(url(bid)).json())  # the raw work list never carries it


def test_a_technical_part_keeps_its_history_and_the_screen_prefills_the_current_text(world):
    bid = seed(world)
    c = login(world, "co-a")
    c.put(url(bid, "/kpis/K01/technical"), json={"part": "calculation", "value": "1. Take F001.", "mark": "stated"})
    amb = _item(c, world, bid, "calculation", "Cash cushion: calculation (calculation) net or gross", "Net or gross?")
    s = c.get(url(bid, "/technical")).json()
    assert s["ambiguities"][0]["suggested_part"] == "calculation" and s["kpis"][0]["definition"] == OLD  # the question's own part is preselected
    r = _answer(c, bid, amb, resolution="Gross.", part="calculation", wording="1. Take F001, gross of fees.")
    cell = part(r.json(), "K01", "calculation")
    assert cell["cell"]["value"] == "1. Take F001, gross of fees." and cell["history"][0]["value"] == "1. Take F001."


def test_an_owners_reply_on_the_link_only_records_the_answer(world):
    bid = seed(world, kpis=[kpi("K01", "Cash cushion", data_owner="Arjun Rao")])
    c = login(world, "co-a")
    amb = _item(c, world, bid, "currency", "Cash cushion: currency", "Which rate?")
    link = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]["link_path"]
    r = _visitor(world, link).post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Custody rate at close."})
    assert r.status_code == 200
    k = _k(world, bid)
    assert k["ambiguities"][0]["resolution"] == "Custody rate at close." and T.parts_of(k)["currency_basis"]["mark"] == "unknown" and k["definition"]["value"] == OLD


# ---- 2. every kind of owner account confirms its own technical definitions ---------------------------------------------------------------

def _account(world, name, roles):
    acct, pw = make_test_account(world.accounts, name, "co-a", list(roles))
    c = TestClient(world.app)
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
    return c, acct


def _owned(world, who, roles):
    c, acct = _account(world, who, roles)
    bid = seed(world, kpis=[kpi("K01", "Cash cushion", data_owner=None), kpi("K02", "Old valuations", data_owner="Test Pat Owner")])
    owner = {**prov(acct["display_name"], "stated", PAT, "nominated, with an account"), "account_id": acct["account_id"]}
    for kid in ("K01",):
        K.change(world.plane("co-a"), bid, kid, lambda x: {**x, "owners": {**x["owners"], "data": owner}})
    admin = login(world, "co-a")
    for kid in ("K01", "K02"):
        for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
            admin.put(url(bid, f"/kpis/{kid}/technical"), json={"part": p, "value": v, "mark": "stated"})
    return c, bid


def test_a_participant_data_owner_sees_and_confirms_only_their_own_measure(world):
    c, bid = _owned(world, "Wei Participant", ("participant",))
    mine = c.get(url(bid, "/my-technical"))
    assert mine.status_code == 200 and [k["kpi_id"] for k in mine.json()["kpis"]] == ["K01"]  # not K02, which is Pat's
    assert "Old valuations" not in json.dumps(mine.json()) and "ambiguities" not in mine.json()
    assert c.post(url(bid, "/kpis/K02/technical/confirm")).status_code == 403  # a measure that is not theirs
    assert c.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 200
    assert c.get(url(bid, "/my-technical")).json()["kpis"][0]["confirmed"]["by"] == "Test Wei Participant"
    assert c.get(url(bid, "/technical")).status_code == 403  # the whole screen stays closed to them


def test_an_approver_data_owner_the_same(world):
    c, bid = _owned(world, "Tom Approver", ("approver",))
    assert [k["kpi_id"] for k in c.get(url(bid, "/my-technical")).json()["kpis"]] == ["K01"]
    assert c.post(url(bid, "/kpis/K02/technical/confirm")).status_code == 403
    assert c.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 200


def test_someone_who_owns_nothing_sees_nothing(world):
    c, bid = _owned(world, "Sam Participant", ("participant",))
    other, _ = _account(world, "Una Participant", ("participant",))
    assert other.get(url(bid, "/my-technical")).json()["kpis"] == [] and other.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 403


def _link_world(world, account):
    bid = seed(world)
    plane = world.plane("co-a")
    owner = prov("Arjun Rao", "stated", PAT, "nominated")
    K.change(plane, bid, "K01", lambda x: {**x, "owners": {**x["owners"], "data": {**owner, "account_id": account}}})
    admin = login(world, "co-a")
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
        admin.put(url(bid, "/kpis/K01/technical"), json={"part": p, "value": v, "mark": "stated"})
    amb = _item(admin, world, bid, "currency", "Cash cushion: currency", "Which rate?")
    return bid, admin.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]["link_path"]


def test_an_owner_with_no_account_sees_and_confirms_their_technical_definition_on_the_link(world):
    bid, link = _link_world(world, None)
    v = _visitor(world, link)
    form = v.post(f"{BASE}/answer/form").json()
    assert [t["kpi_id"] for t in form["technical"]] == ["K01"] and form["technical_sign_in"] == []
    assert next(p for p in form["technical"][0]["parts"] if p["part"] == "calculation")["cell"]["value"] == "1. Take F001."
    assert v.post(f"{BASE}/answer/technical/confirm", json={"kpi_id": "K02"}).status_code == 422  # not one of their measures
    assert v.post(f"{BASE}/answer/technical/confirm", json={"kpi_id": "K01"}).status_code == 200
    assert T.confirmed(_k(world, bid))["by"] == "Arjun Rao"


def test_an_owner_with_an_account_is_sent_to_sign_in_and_nothing_is_confirmed(world):
    bid, link = _link_world(world, "acct-someone")
    v = _visitor(world, link)
    form = v.post(f"{BASE}/answer/form").json()
    assert form["technical"] == [] and form["technical_sign_in"] == [{"kpi_id": "K01", "name": "Cash cushion"}]
    r = v.post(f"{BASE}/answer/technical/confirm", json={"kpi_id": "K01"})
    assert r.status_code == 403 and "sign in" in r.json()["message"] and T.confirmed(_k(world, bid)) is None


def test_a_change_clears_only_the_confirmation_of_that_part():
    k = kpi("K01", "Cash cushion")
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
        k = T.set_part(k, p, v, "stated", "Arjun")
    k = T.confirm(k, "Arjun")
    assert T.to_confirm(k) == [] and set(T.confirmed_parts(k)) == {"sources", "fields", "calculation"}
    k = T.set_part(k, "calculation", "1. Take F001.\n2. Sum.", "stated", "Arjun")
    assert T.confirmed(k) is None and T.to_confirm(k) == ["calculation"] and set(T.confirmed_parts(k)) == {"sources", "fields"}  # the other parts stay confirmed


# ---- 3. question noise -----------------------------------------------------------------------------------------------------------------

def test_a_blank_template_or_ids_question_is_never_stored():
    k = kpi("K01", "Cash cushion")
    bad = [A.make("other", "", "Which?", "a"), A.make("other", "What is unclear", "The question to ask", "b"), A.make("other", "x", "", "c"),
           A.make("calculation", "An input matches no field.", "Which catalogue IDs hold each input?", "d"),
           A.make("calculation", "An input matches no field.", "Which catalogue field holds each input of the calculation?", "e")]
    assert A.with_ambiguities(k, bad).get("ambiguities", []) == []
    ok = A.make("period", "No period.", "Which date is the reporting date?", "Cash cushion: period (period)")
    assert len(A.with_ambiguities(k, [*bad, ok])["ambiguities"]) == 1


def test_old_blank_and_duplicate_open_questions_are_tidied_away(world):
    bid = seed(world)
    one = A.make("period", "No period.", "Which date?", "Cash cushion: period (period) period")
    two = A.make("period", "The month end is not stated.", "Which cut-off?", "Cash cushion: period (period) the month end")
    blank = {**A.make("other", "x", "y", "z"), "text": "", "question": "what is unclear"}
    K.change(world.plane("co-a"), bid, "K01", lambda x: {**x, "ambiguities": [one, two, blank]})
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, []))
    got = _k(world, bid)["ambiguities"]
    assert [(a["id"], a["status"]) for a in got] == [(one["id"], "open"), (two["id"], "settled"), (blank["id"], "settled")]  # one decision per measure; the rest closed visibly, none deleted


def test_a_model_conflict_that_asks_for_ids_or_echoes_the_template_is_not_raised(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", "Take the closing balance per account from the statement file.")
    with_model(world, Stub("CALCULATION:\n1. Take F001.\nPERIOD: month end\n"
                           "CONFLICT: calculation | inputs | An input has no row | Which catalogue IDs hold each input? | \n"
                           "CONFLICT: other | what is unclear | what is unclear | the question to ask | \n"
                           "CONFLICT: threshold | stress limit | The limit has no number | What is the number? | "))
    s = draft(login(world, "co-a"), bid)
    assert [a["question"] for a in s["ambiguities"]] == ["What is the number?"]


def test_a_question_closes_by_itself_when_its_cause_is_gone_and_says_so(world):
    bid = seed(world)
    old = {**A.make("calculation", "The inputs match no field.", "Which catalogue IDs hold each input?", "Cash cushion: calculation (fields) inputs"), "raised_by": "Lens"}
    K.change(world.plane("co-a"), bid, "K01", lambda x: {**x, "ambiguities": [old]})  # as an earlier build left it
    c = login(world, "co-a")
    assert c.put(url(bid, "/kpis/K01/technical"), json={"part": "fields", "value": ["F001"], "mark": "stated"}).status_code == 200
    got = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    assert (got["status"], got["resolution"], got["by"], got["auto"]) == ("settled", "Closed: the catalogue now has it", "Lens", True)
    assert c.get(url(bid, "/ambiguities")).json()["counts"]["open"] == 0


def test_the_period_question_closes_when_the_period_is_stated():
    k = A.with_ambiguities(kpi("K01", "Cash cushion"), [A.make("period", "No period.", "Which date?", "Cash cushion: period (period)", cause="has:period")])
    k = T.set_part(k, "period", "month end", "stated", "Pat")
    assert k["ambiguities"][0]["status"] == "settled" and k["ambiguities"][0]["resolution"].startswith("Closed:")


def test_rephrased_findings_about_one_part_are_one_question_per_measure(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", "The month end is the reporting date. Month bucket by notice date.")
    with_model(world, Stub("CALCULATION:\n1. Take F001.\n"
                           "CONFLICT: conflict | month bucket | Glossary and notes differ on the month | Which date decides the month? | \n"
                           "CONFLICT: conflict | reporting period | Two dates are given for the period | Which date is the reporting date? | \n"
                           "CONFLICT: period | period | The period is not stated | Which cut-off? | "))
    s = draft(login(world, "co-a"), bid)
    assert sorted(a["kind"] for a in s["ambiguities"]) == ["conflict", "period"]  # three wordings, two decisions


# ---- 4. Lens builds catalogue rows from the technical notes ---------------------------------------------------------------------------

NOTES = ("Capital call tracker is an Excel workbook kept by the funds team. Its Calls sheet holds the columns notice_date, due_date and call_amount. "
         "The notice_date is the date on the call notice. A call is paid when the amount is received.")
ROWS = """SOURCES: UNKNOWN
CALCULATION:
1. Count the calls per month by due_date.
PERIOD: month end
NEW_SOURCE: Capital call tracker | Manual workbook (Excel)
NEW_TABLE: Capital call tracker | Calls
NEW_FIELD: Calls | notice_date | The date on the call notice
NEW_FIELD: Calls | due_date |
NEW_FIELD: Calls | Invented column | Made up
NEW_FIELD: Nowhere | call_amount | The amount called
"""


def test_lens_proposes_catalogue_rows_from_the_notes_guessed_with_the_title_and_the_measure_links_them(world):
    bid = seed(world, cat=None)
    upload(world, "co-a", "Capital notes", NOTES)
    with_model(world, Stub(ROWS))
    c = login(world, "co-a")
    s = draft(c, bid)
    cat, _ = SC._raw(world.plane("co-a"), bid)
    src, tbl = cat["sources"][0], cat["tables"][0]
    assert C.text_of(src["Source name"]) == "Capital call tracker" and src["Source name"]["mark"] == "guessed" and src["Source name"]["by"] == "Lens"
    assert "Capital notes" in src["Source name"]["from"] and C.text_of(src["Source type"]) == "Manual workbook (Excel)"
    assert C.text_of(tbl["Source ID"]) == "S01" and C.text_of(tbl["Related KPIs"]) == "K01"
    names = {C.text_of(f["Field name as in the source"]): f for f in cat["fields"]}
    assert set(names) == {"notice_date", "due_date"}  # a column the notes do not say, or with no table, is never made
    assert C.text_of(names["notice_date"]["Business meaning"]) == "The date on the call notice" and (names["due_date"]["Business meaning"]["mark"], names["due_date"]["Business meaning"]["from"]) == ("unknown", "Not available yet")
    assert C.text_of(names["notice_date"]["Feeds KPI"]) == "K01" and names["notice_date"]["Business meaning"]["mark"] == "guessed"
    assert [x["id"] for x in part(s, "K01", "sources")["links"]] == ["S01"] and [x["id"] for x in part(s, "K01", "fields")["links"]] == ["F001", "F002"]
    assert part(s, "K01", "fields")["cell"]["mark"] == "guessed" and "Capital notes" in part(s, "K01", "fields")["cell"]["from"]
    again = draft(c, bid, retry=True)  # a second build adds no second row
    assert len(SC._raw(world.plane("co-a"), bid)[0]["fields"]) == 2 and again["outcomes"] == {"K01": "drafted"}


def test_a_name_the_documents_do_not_say_is_not_proposed(world):
    bid = seed(world, cat=None)
    upload(world, "co-a", "Capital notes", "Nothing about files here.")
    with_model(world, Stub("CALCULATION: UNKNOWN\nNEW_SOURCE: Hidden vault | Database\nNEW_TABLE: Hidden vault | Ledger\n"))
    draft(login(world, "co-a"), bid)
    assert SC._raw(world.plane("co-a"), bid)[0]["sources"] == []


def test_rows_from_a_restricted_measure_are_personal_data_and_stay_with_its_list(world):
    pay = kpi("K01", "Bonus pool", personal="yes", may_see=[PAT])
    bid = seed(world, kpis=[pay], cat=None)
    upload(world, "co-a", "Pay notes", "The Pay workbook has a Review sheet with the columns salary_band and bonus_amount.", restricted=True)
    with_model(world, Stub("CALCULATION:\n1. Sum bonus_amount.\nPERIOD: year end\nNEW_SOURCE: Pay workbook | Manual workbook (Excel)\n"
                           "NEW_TABLE: Pay workbook | Review\nNEW_FIELD: Review | salary_band | Pay band\nNEW_FIELD: Review | bonus_amount | Bonus paid"))
    draft(login(world, "co-a"), bid)
    cat, _ = SC._raw(world.plane("co-a"), bid)
    assert C.text_of(cat["sources"][0]["Contains personal data?"]) == "Yes" and {C.text_of(f["Personal data class"]) for f in cat["fields"]} == {"Personal data"}
    assert all(C.text_of(f["Feeds KPI"]) == "K01" for f in cat["fields"])
    seen, _ = C.view_of(cat, C.guards(cat, {"K01": pay["governance"]}), C.Viewer("Test Alan Analyst", frozenset({"analyst"})), drop=True)
    assert seen["tables"] == [] and seen["fields"] == [] and seen["sources"] == []  # the analyst sees none of it


# ---- 5. a field's business meaning is its own ---------------------------------------------------------------------------------------------

def test_a_field_never_takes_the_measures_whole_definition_as_its_meaning():
    cat = C.empty_catalogue()
    k = kpi("K01", "Pay review", definition="The share of people paid within their band. It is worked out every year.")
    row = C.new_row("fields", "F001")
    row["Item ID"], row["Field name as in the source"] = prov("T01", "stated", PAT, "x"), prov("salary_band", "stated", PAT, "x")
    row["Business meaning"] = prov("The share of people paid within their band.", "stated", PAT, "kpis.json")  # what an earlier build copied
    cat["fields"].append(row)
    C._merge_item(cat, "fields", "Item ID", "Field name as in the source", "T01", "K01", prov(["salary_band"], "stated", "Mei", "answers.json"),
                  prov("salary_band", "stated", "Mei", "answers.json"), {"K01": k})
    assert len(cat["fields"]) == 1  # the same field, not a second row
    meaning = cat["fields"][0]["Business meaning"]
    assert meaning["mark"] == "unknown" and meaning["from"] == "Not available yet" and "share of people" not in json.dumps(cat)  # never the whole definition


# ---- 6. a re-added measure starts clean ---------------------------------------------------------------------------------------------------

def test_a_measure_added_again_is_not_left_out(world):
    bid = seed(world, kpis=[])
    c = login(world, "co-a")
    assert c.post(url(bid, "/kpis"), json={"suggestion_id": "K0"}).status_code == 201
    assert c.post(url(bid, "/review/K0/leave-out"), json={"reason": "Not needed this time."}).status_code == 200
    assert c.delete(url(bid, "/kpis/K0")).status_code == 200
    assert c.post(url(bid, "/kpis"), json={"suggestion_id": "K0"}).status_code == 201
    from modules.m2_baseline.store.signoff import SignoffStore
    assert "K0" not in (SignoffStore(world.plane("co-a")).read(bid)["versions"][-1].get("left_out") or {})


# ---- review round: guesses never close a question, real questions are never judged unusable, restricted rows are seen by the list ---------

def test_a_lens_guess_does_not_close_the_question_but_a_persons_value_does():
    k = A.with_ambiguities(kpi("K01", "Cash cushion"), [A.make("period", "No period.", "Which date?", "Cash cushion: period (period)", cause="has:period")])
    guessed = T.merge_draft(k, {"period": prov("month end", "guessed", "Lens", "the pack")})  # Lens guesses a period from the pack
    assert guessed["ambiguities"][0]["status"] == "open" and "auto" not in guessed["ambiguities"][0]
    assert T.set_part(guessed, "period", "month end", "guessed", "Pat")["ambiguities"][0]["status"] == "open"  # a person's guess is still a guess
    stated = T.set_part(guessed, "period", "last business day", "stated", "Pat")
    assert stated["ambiguities"][0]["status"] == "settled" and stated["ambiguities"][0]["resolution"].startswith("Closed:")
    legacy = {**kpi("K02", "X"), "ambiguities": [A.make("calculation", "Inputs.", "Which catalogue IDs hold each input?", "X: calculation (fields) inputs")]}  # as an old build stored it
    linked = T.merge_draft(legacy,
                           {"fields": prov(["F001"], "guessed", "Lens", "Capital notes")})  # a link that now exists closes a question about the link
    assert linked["ambiguities"][0]["status"] == "settled" and linked["ambiguities"][0]["resolution"] == "Closed: the catalogue now has it"


def test_an_ordinary_business_question_about_a_source_id_is_usable_and_kept():
    real = A.make("source", "Two systems hold the data.", "Which source ID is the system of record?", "Cash cushion: source (sources) record")
    assert A.usable(real) and not A.asks_for_ids(real)
    assert A.asks_for_ids(A.make("calculation", "x", "Which catalogue IDs hold each input?", "w"))
    assert A.asks_for_ids(A.make("calculation", "x", "Which catalogue rows hold the inputs?", "w"))
    assert len(A.with_ambiguities(kpi("K01", "Cash cushion"), [real])["ambiguities"]) == 1


def test_tidy_closes_an_unusable_open_item_visibly_and_never_deletes_it():
    blank = {**A.make("other", "x", "y", "z"), "text": "", "question": "what is unclear"}
    dup_a = A.make("period", "No period.", "Which date?", "Cash cushion: period (period) a")
    dup_b = A.make("period", "Not stated.", "Which cut-off?", "Cash cushion: period (period) b")
    out = A.tidy([blank, dup_a, dup_b])
    assert [a["id"] for a in out] == [blank["id"], dup_a["id"], dup_b["id"]]  # nothing deleted
    assert (out[0]["status"], out[0]["resolution"], out[0]["auto"]) == ("settled", "Closed: not a question for a person", True)
    assert out[1]["status"] == "open" and out[2]["status"] == "settled" and out[2]["resolution"].startswith("Closed:")


def test_parsed_new_names_are_cut_to_200_characters():
    long = "n" * 500
    got = T.parse_reply(f"NEW_SOURCE: {long} | {long}\nNEW_TABLE: {long} | {long}\nNEW_FIELD: {long} | {long} | {long}", {})["catalogue"]
    assert all(len(x) <= 200 for rows in got.values() for r in rows for x in r)


def test_rows_proposed_for_a_restricted_measure_are_seen_by_the_measures_list_and_nobody_else(world):
    from modules.m2_baseline.domain import handoff as H
    from modules.m2_baseline.store import technical as ST
    ALAN = "Test Alan Analyst"
    pay = kpi("K01", "Bonus pool", personal="yes", may_see=[PAT, ALAN])
    bid = seed(world, kpis=[pay], cat=None)
    upload(world, "co-a", "Pay notes", "The Pay workbook has a Review sheet with the columns salary_band and bonus_amount.", restricted=True)
    with_model(world, Stub("CALCULATION:\n1. Sum bonus_amount.\nPERIOD: year end\nNEW_SOURCE: Pay workbook | Manual workbook (Excel)\n"
                           "NEW_TABLE: Pay workbook | Review\nNEW_FIELD: Review | salary_band | Pay band\nNEW_FIELD: Review | bonus_amount | Bonus paid"))
    draft(login(world, "co-a"), bid)
    plane = world.plane("co-a")
    cat, _ = SC._raw(plane, bid)
    assert C.text_of(cat["sources"][0]["Who may see it"]) == f"{PAT}, {ALAN}" and cat["sources"][0]["Who may see it"]["mark"] == "guessed"
    assert all(C.text_of(f["Who may see it"]) == f"{PAT}, {ALAN}" for f in cat["fields"] if f.get("Who may see it"))
    listed, other = C.Viewer(ALAN, frozenset({"analyst"})), C.Viewer("Test Una Analyst", frozenset({"analyst"}))
    owner = C.Viewer(PAT, frozenset({"owner"}))
    for who, n in ((listed, 2), (owner, 2), (other, 0)):
        v = SC.view(plane, bid, who)
        assert len([r for r in v["fields"] if not r.get(C.HIDDEN)]) == n and len([r for r in v["sources"] if not r.get(C.HIDDEN)]) == min(n, 1)
        book = read_book(SC.export(plane, bid, who))
        assert ("salary_band" in json.dumps(book)) == (n > 0)
        shown = H.for_viewer({"catalogue": cat}, K.read_kpis(plane, bid), {"K01"} if n else set(), who)["catalogue"]
        assert len(shown["fields"]) == n
