"""M2-E1: the technical definition of a measure and the open questions (ambiguities). Lens drafts from documents, the catalogue and the pack with
a stub model; nothing is invented; contradictions are raised once; people answer, ask the owner or accept a risk; ready to build is four
conditions; restricted measures, fields and documents never reach a viewer who may not see them. Two industries and an empty company.
Synthetic wording only; the answer key (document 18) is used here as expected values and is never given to Lens."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from m2_kit import BASE, login
from test_m2_catalogue_xlsx import read_book

from modules.m2_baseline.domain import ambiguities as A
from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import readiness as RD
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov, unknown
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import kpis as K
from modules.m2_baseline.store import lens as LS
from modules.m2_baseline.store import technical as ST
from sh_platform.agents.protocols import ModelReply
from sh_platform.context_docs.store import DocStore

STORY = Path(__file__).resolve().parents[3] / "packs" / "family_office" / "1" / "demo_story"
PAT, ALAN, LENA, SAM = "Test Pat Owner", "Test Alan Analyst", "Test Lena Hr", "Test Sam Sponsor"
AT = "2026-10-03T10:00:00+00:00"

CASH = """SOURCES: S01
TABLES: T01
FIELDS: F001, F002
CALCULATION:
1. Take the month-end closing balance per account from F001.
2. Convert USD at the rate held in F002.
3. Add approved inflows, subtract obligations and the reserve.
FILTERS: UNKNOWN
GRAIN: per account per month
PERIOD: month end
CURRENCY: UNKNOWN
NOTES: UNKNOWN
MISSING: the FX rate source and the rate date
CONFLICT: currency | currency basis | The FX rate source and date are not stated | Which rate, from where, on which date? | """


class Stub:
    """Answers with `reply` (text, or a function of the measure name) and remembers every prompt it was sent."""
    def __init__(self, reply=CASH):
        self.reply, self.sent = reply, []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        user = json.loads(messages[-1]["content"])
        text = self.reply(user["context"].get("kpi", "")) if callable(self.reply) else self.reply
        return ModelReply(text)

    @property
    def prompts(self) -> str:
        return json.dumps(self.sent)


def row(tab, rid, cells):
    r = C.new_row(tab, rid)
    r.update({h: prov(v, "stated", PAT, "the questionnaire", at=AT) for h, v in cells.items()})
    return r


def catalogue(extra_field_visibility=None):
    f2 = {"Item ID": "T01", "Field name as in the source": "fx_rate_used", "Feeds KPI": "K01", "Data type": "decimal"}
    if extra_field_visibility:
        f2[C.FIELD_VISIBILITY] = extra_field_visibility
    return {"sources": [row("sources", "S01", {"Source name": "Northgate Custody daily file", "Source type": "File drop", "Contains personal data?": "No"})],
            "tables": [row("tables", "T01", {"Source ID": "S01", "Name of table, file or document type": "statement", "Related KPIs": "K01"})],
            "fields": [row("fields", "F001", {"Item ID": "T01", "Field name as in the source": "closing_balance", "Feeds KPI": "K01", "Data type": "decimal", "Personal data class": "Neither"}),
                       row("fields", "F002", f2 | {"Personal data class": "Neither"})],
            "extractions": [], "kpis": [row("kpis", "K01", {})]}


def kpi(kid, name, personal="no", may_see=(), definition="Cash we would still have in the worst month.", data_owner="Test Pat Owner"):
    k = W.new_kpi(kid, name, [], None, prov(definition, "stated", PAT, "the work list") if definition else None)
    k["governance"] = {"personal": personal, "sensitive": personal == "yes", "may_see": list(may_see)}
    for role in ("business", "process"):
        k["owners"][role] = prov("Test Pat Owner", "stated", PAT, "nominated")
    if data_owner:
        k["owners"]["data"] = prov(data_owner, "stated", PAT, "nominated")
    return k


def seed(world, company="co-a", kpis=None, cat="default", state="mapping"):
    plane = world.plane(company)
    base, _ = B.start(plane, None)
    for k in kpis if kpis is not None else [kpi("K01", "Cash cushion")]:
        K.add(plane, base["id"], k)
    folder = plane.path("intents", "m2_baseline", base["id"])
    (folder / "catalogue.json").write_text(json.dumps(catalogue() if cat == "default" else cat or {t: [] for t in C.TABS}))
    if state != "mapping":
        B.set_state(plane, base["id"], state)
    return base["id"]


def url(bid, tail=""):
    return f"{BASE}/baselines/{bid}{tail}"


def with_model(world, stub):
    world.app.state.lens_model_factory = (lambda plane: stub) if stub else (lambda plane: None)
    return stub


def upload(world, company, title, text, restricted=False, decided=True):
    """`decided`: the organiser has already said the document is not personal data (a document that mentions pay waits for that, round 5B)."""
    doc = DocStore(world.plane(company)).upload("lens", "a", f"{title}.md", text.encode("utf-8") if isinstance(text, str) else text, title=title, restricted=restricted)
    if decided:
        LS.set_scan(world.plane(company), doc["doc_id"], {"words": [], "state": "cleared"})
    return doc["doc_id"]


def story(name):
    return (STORY / name).read_text(encoding="utf-8")


def part(screen, kid, name):
    return next(p for k in screen["kpis"] if k["kpi_id"] == kid for p in k["parts"] if p["part"] == name)


def kinds(screen, kid):
    return {a["kind"] for a in screen["ambiguities"] if a["kpi_id"] == kid}


def draft(c, bid, **body):
    r = c.post(url(bid, "/lens/technical"), json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---- Lens drafts the technical definition -----------------------------------------------------------------------------------------------

def test_lens_drafts_a_technical_definition_from_a_note_with_catalogue_links_and_provenance(world):
    stub = with_model(world, Stub())
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    c = login(world, "co-a")
    s = draft(c, bid)
    assert s["outcomes"] == {"K01": "drafted"} and len(stub.sent) == 1  # ONE model call for the parts and the questions
    src, calc = part(s, "K01", "sources"), part(s, "K01", "calculation")
    assert src["links"] == [{"id": "S01", "name": "Northgate Custody daily file"}] and (src["cell"]["mark"], src["cell"]["by"]) == ("guessed", "Lens")
    assert "Technical notes" in src["cell"]["from"] and "the catalogue" in src["cell"]["from"]  # where it came from: the document and the catalogue
    assert calc["cell"]["value"].startswith("1. Take the month-end closing balance per account from F001.") and "\n3. " in calc["cell"]["value"]
    assert [x["id"] for x in part(s, "K01", "fields")["links"]] == ["F001", "F002"]
    assert part(s, "K01", "filters")["cell"]["mark"] == "unknown" and part(s, "K01", "period")["cell"]["value"] == "month end"
    assert "closing_balance" in stub.prompts and "F001" in stub.prompts  # the catalogue field names reach Lens, never a value
    assert "ambiguities planted" not in stub.prompts and "Answer key" not in stub.prompts  # the answer key is not a client document


def test_nothing_is_invented_when_there_is_no_source(world):
    stub = with_model(world, Stub("CALCULATION: 1. Invent something."))
    bid = seed(world, "co-b", [kpi("K09", "Mystery measure")], cat=None)
    s = draft(login(world, "co-b"), bid)
    assert s["outcomes"] == {"K09": "nothing"} and stub.sent == []  # no passage, no catalogue row, no pack text: no model call
    calc = part(s, "K09", "calculation")["cell"]
    assert calc["mark"] == "unknown" and calc["value"] is None and calc["from"].startswith("Missing")  # unknown, and what is missing
    assert kinds(s, "K09") == {"calculation"}  # asked, never guessed


def test_a_link_to_a_row_that_does_not_exist_is_dropped_and_a_stray_figure_saves_nothing(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    c = login(world, "co-a")
    with_model(world, Stub("SOURCES: S01, S02\nTABLES: T01, T02\nCALCULATION:\n1. Take F001."))
    s = draft(c, bid)
    assert [x["id"] for x in part(s, "K01", "sources")["links"]] == ["S01"] and [x["id"] for x in part(s, "K01", "tables")["links"]] == ["T01"]
    bid2 = seed(world)
    with_model(world, Stub("CALCULATION:\n1. Multiply by 987654."))
    s = draft(c, bid2)  # a figure that is in nothing Lens was shown: the number guard replaced it, nothing is saved
    assert s["outcomes"] == {"K01": "nothing"} and part(s, "K01", "calculation")["cell"]["mark"] == "unknown"


def test_planted_contradictions_of_the_two_documents_become_ambiguities_of_the_right_kinds(world):
    """Expected values from the answer key (document 18): 2 period, 3 currency, 7 and 14 threshold and age, 10 and 15 source, 11 and 12 and 13 calculation."""
    names = ["Cash cushion", "Known obligations", "Old valuations", "Alpha", "Notices to chase", "Pay inputs matched"]
    bid = seed(world, kpis=[kpi(f"K{i}", n) for i, n in enumerate(names, 1)], cat=None)
    upload(world, "co-a", "ILFO business glossary", story("16_business_glossary_raw.md"))
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    conflicts = {
        "Known obligations": "CONFLICT: conflict | month bucket | The glossary says paid calls and the notes bucket by notice date while Sara says due date | Which date decides the month? | ",
        "Old valuations": "CONFLICT: calculation | age basis | The glossary counts days from a valuation date; the notes count quarters | Days or quarters? | ",
        "Alpha": ("CONFLICT: source | the tracker | The glossary says the tracker; the notes say the performance workbook | Which file is the source? | The performance workbook\n"
                  "CONFLICT: calculation | net or gross | Net or gross of fees is not stated | Is the return net or gross of fees, and which fees? | "),
        "Pay inputs matched": "CONFLICT: calculation | headcount | The notes use everyone in the review tab; the policy covers the investment team | Whose pay inputs are in scope? | ",
    }
    with_model(world, Stub(lambda name: conflicts.get(name, "CALCULATION: UNKNOWN\nMISSING: not stated")))
    s = draft(login(world, "co-a"), bid)
    got = {n: kinds(s, f"K{i}") for i, n in enumerate(names, 1)}
    assert "currency" in got["Cash cushion"]                                 # key 3: the FX rate source and date, "ask Tom"
    assert "conflict" in got["Known obligations"]                            # key 13: month bucket
    assert {"threshold", "calculation"} <= got["Old valuations"]             # key 7 ("our usual limit", "ask Mei") and key 14 (age basis)
    assert {"source", "calculation"} <= got["Alpha"]                         # keys 10 and 15 (the tracker) and key 1 (net or gross)
    assert "calculation" in got["Notices to chase"]                          # key 11: "Whether a Superseded row counts: ask Sara"
    assert "calculation" in got["Pay inputs matched"]                        # key 12: the denominator
    alpha = next(a for a in s["ambiguities"] if a["kind"] == "source" and a["kpi_name"] == "Alpha")
    assert alpha["suggestion"]["by"] == "Lens" and alpha["suggestion"]["mark"] == "guessed" and alpha["status"] == "open"  # a suggestion, a person decides
    assert all(set(a) >= {"id", "kind", "text", "question", "where", "raised_by", "status", "resolution", "by", "at"} and a["kind"] in A.KINDS for a in s["ambiguities"])
    assert "Answer key" not in json.dumps(world.app.state.lens_model_factory(None).sent)


def test_a_second_build_adds_no_duplicates(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    with_model(world, Stub())
    c = login(world, "co-a")
    first = draft(c, bid)
    again = draft(c, bid, retry=True)
    assert len(again["ambiguities"]) == len(first["ambiguities"]) > 0 and [a["id"] for a in again["ambiguities"]] == [a["id"] for a in first["ambiguities"]]
    c.post(url(bid, f"/kpis/K01/ambiguities/{first['ambiguities'][0]['id']}/answer"), json={"resolution": "Use the rate the Treasurer types."})
    assert len(draft(c, bid, retry=True)["ambiguities"]) == len(first["ambiguities"])  # even a settled finding is not raised again


def test_lens_does_not_try_a_measure_twice_unless_asked(world):
    stub = with_model(world, Stub())
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    c = login(world, "co-a")
    draft(c, bid)
    assert draft(c, bid)["outcomes"] == {} and len(stub.sent) == 1  # the claim: a second tab or a second open skips it
    draft(c, bid, retry=True)
    assert len(stub.sent) == 2


# ---- a person's value, answers, risk ------------------------------------------------------------------------------------------------------

def test_a_persons_part_is_never_overwritten_and_use_this_makes_the_draft_theirs(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    with_model(world, Stub())
    c = login(world, "co-a")
    r = c.put(url(bid, "/kpis/K01/technical"), json={"part": "period", "value": "last business day", "mark": "stated"})
    assert r.status_code == 200
    s = draft(c, bid)
    p = part(s, "K01", "period")
    assert p["cell"]["value"] == "last business day" and p["cell"]["by"] == PAT and p["proposal"]["value"] == "month end" and p["proposal"]["by"] == "Lens"
    s = c.post(url(bid, "/kpis/K01/technical/use"), json={"part": "period"}).json()
    p = part(s, "K01", "period")
    assert p["cell"]["value"] == "month end" and (p["cell"]["mark"], p["cell"]["by"]) == ("stated", PAT) and p["proposal"] is None


def test_an_answer_settles_the_item_and_a_chosen_part_takes_the_persons_wording_as_stated_by_them(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    with_model(world, Stub())
    c = login(world, "co-a")
    s = draft(c, bid)
    item = next(a for a in s["ambiguities"] if a["kind"] == "currency")
    r = c.post(url(bid, f"/kpis/K01/ambiguities/{item['id']}/answer"), json={"resolution": "Use the custody rate at close on the last business day.", "part": "currency_basis",
                                                                           "wording": "Custody rate at close on the last business day."})
    assert r.status_code == 200 and r.json()["changed"] == "currency_basis"
    got = next(a for a in r.json()["ambiguities"] if a["id"] == item["id"])
    assert (got["status"], got["by"]) == ("settled", PAT) and got["resolution"].startswith("Use the custody rate")
    cur = part(r.json(), "K01", "currency_basis")["cell"]
    assert (cur["value"], cur["mark"], cur["by"]) == ("Custody rate at close on the last business day.", "stated", PAT)
    assert c.post(url(bid, f"/kpis/K01/ambiguities/{item['id']}/answer"), json={"resolution": "again"}).status_code == 422  # already dealt with
    assert c.post(url(bid, f"/kpis/K01/ambiguities/{item['id']}/answer"), json={"resolution": ""}).status_code == 422


def test_an_answer_to_a_definition_question_updates_the_business_definition_only_in_the_wording_the_person_gives(world):
    k = kpi("K01", "Cash cushion", definition="")
    bid = seed(world, kpis=[k])
    plane = world.plane("co-a")
    K.change(plane, bid, "K01", lambda x: A.with_ambiguities(x, [A.make("definition", "Two meanings.", "Which meaning?", "Cash cushion: definition")]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/answer"), json={"resolution": "Cash left after obligations and the reserve.", "part": "definition",
                                                                           "wording": "Cash left after obligations and the reserve are set aside."})
    d = K.read_kpis(plane, bid)[0]["definition"]
    assert (d["value"], d["mark"], d["by"]) == ("Cash left after obligations and the reserve are set aside.", "stated", PAT)


def test_accept_as_a_known_risk_needs_the_organiser_or_sponsor_and_a_reason(world):
    bid = seed(world)
    plane = world.plane("co-a")
    K.change(plane, bid, "K01", lambda x: A.with_ambiguities(x, [A.make("threshold", "No number.", "What number?", "Cash cushion: threshold (limit)")]))
    analyst, sponsor = login(world, "co-a", "Alan Analyst", ("analyst",)), login(world, "co-a", "Sam Sponsor", ("sponsor",))
    amb = login(world, "co-a").get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    path = url(bid, f"/kpis/K01/ambiguities/{amb['id']}/accept")
    assert analyst.post(path, json={"reason": "fine"}).status_code in (403, 404)  # the route itself is for the organiser and sponsor
    assert sponsor.post(path, json={"reason": ""}).status_code == 422
    r = sponsor.post(path, json={"reason": "We will set the limit after the audit."})
    assert r.status_code == 200
    got = next(a for a in r.json()["ambiguities"] if a["id"] == amb["id"])
    assert (got["status"], got["by"], got["resolution"]) == ("accepted", SAM, "We will set the limit after the audit.")


def test_ask_the_owner_adds_the_question_to_that_owners_request_prefilled(world):
    k = kpi("K01", "Cash cushion")
    k["owners"]["data"] = prov("Arjun Rao", "stated", PAT, "nominated")
    bid = seed(world, kpis=[k])
    plane = world.plane("co-a")
    K.change(plane, bid, "K01", lambda x: A.with_ambiguities(x, [A.make("currency", "No rate date.", "Which rate, from where, on which date?", "Cash cushion: currency")]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    r = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={})
    assert r.status_code == 200
    asked = r.json()["asked"]
    assert asked["owner"] == "Arjun Rao" and "Which rate, from where, on which date?" in asked["email"]["body"] and asked["link_path"].startswith("/answer/")
    reqs = c.get(url(bid, "/requests")).json()["requests"]
    assert [q["owner_name"] for q in reqs] == ["Arjun Rao"]
    again = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]
    assert again["link_path"] is None and "Which rate" in again["email"]["body"]  # the same request: a reminder with the question, no second link
    assert next(a for a in r.json()["ambiguities"] if a["id"] == amb["id"])["status"] == "open"  # asking is not settling


def test_ask_the_owner_when_nobody_is_named_says_so(world):
    bid = seed(world, kpis=[kpi("K01", "Cash cushion", data_owner="")])
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, [A.make("currency", "No rate date.", "Which rate?", "Cash cushion: currency")]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    r = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={})
    assert r.status_code == 422 and "Nobody is named" in r.json()["message"]


# ---- ready to build -----------------------------------------------------------------------------------------------------------------

def _ready_kpi():
    k = kpi("K01", "Cash cushion")
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
        k = T.set_part(k, p, v, "stated", "Arjun Rao")
    return T.confirm(k, "Test Pat Owner")


def test_ready_to_build_is_true_only_when_all_four_conditions_hold():
    ok, why = RD.ready_to_build(_ready_kpi(), 0)
    assert ok and why == [] and RD.open_label(_ready_kpi(), 0) == "Ready to build"
    k = _ready_kpi()
    assert not RD.ready_to_build({**k, "definition": prov("Drafted", "guessed", "Lens", "the pack")}, 0)[0]          # 1: a person has not confirmed the business definition
    assert not RD.ready_to_build({**k, "technical": {**k["technical"], "calculation": prov(None, "unknown", "Lens")}}, 0)[0]  # 2: the technical definition is incomplete
    changed = T.set_part(k, "calculation", "1. Take F001.\n2. Sum it.", "stated", "Arjun Rao")
    ok, why = RD.ready_to_build(changed, 0)
    assert not ok and "data owner has not confirmed" in why[0]                                                    # 2: confirmation lapses when the parts change
    amb = A.with_ambiguities(k, [A.make("period", "x", "y", "z")])
    ok, why = RD.ready_to_build(amb, 0)
    assert not ok and "1 open question needs a person" in why[0] and RD.open_label(amb, 0) == "1 thing open"       # 3: an open ambiguity
    settled = A.settle(amb, amb["ambiguities"][0]["id"], "Month end.", "Pat")
    assert RD.ready_to_build(settled, 0)[0]                                                                      # settled is not open
    assert not RD.ready_to_build({**k, "governance": {"personal": "not_sure", "sensitive": False, "may_see": []}}, 0)[0]  # 4: governance not decided
    assert not RD.ready_to_build({**k, "governance": {"personal": "yes", "sensitive": True, "may_see": []}}, 0)[0]
    assert "1 open" in RD.ready_to_build(k, derived_open=1)[1][0]  # governance questions worked out from the catalogue count too


def test_derived_open_is_required_so_the_gate_cannot_undercount():
    import pytest
    with pytest.raises(TypeError):
        RD.ready_to_build(_ready_kpi())
    with pytest.raises(TypeError):
        RD.open_label(_ready_kpi())


def test_a_guessed_definition_or_a_guessed_technical_part_is_not_ready():
    k = _ready_kpi()
    assert not RD.ready_to_build({**k, "definition": prov("Cash we keep.", "guessed", "Test Pat Owner", "the work list")}, 0)[0]  # a person's guess is still a guess
    assert RD.ready_to_build({**k, "definition": prov("Cash we keep.", "stated", "Test Pat Owner", "the work list")}, 0)[0]
    guessed = {**k, "technical": {**k["technical"], "calculation": prov("1. Take F001.", "guessed", "Lens", "Technical notes")}}
    assert not RD.ready_to_build(guessed, 0)[0]  # an old confirmation does not make a draft the owner's
    drafted = T.merge_draft(kpi("K01", "Cash cushion"), {p: prov(v, "guessed", "Lens", "Technical notes") for p, v in
                                                           (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001."))})
    assert not RD.ready_to_build(drafted, 0)[0]
    confirmed = T.confirm(drafted, "Arjun Rao")  # the data owner's confirmation makes the required parts theirs, stated
    assert RD.ready_to_build(confirmed, 0)[0] and confirmed["technical"]["calculation"]["mark"] == "stated" and confirmed["technical"]["calculation"]["by"] == "Arjun Rao"


def test_the_gate_is_the_same_for_everyone_and_a_hidden_open_item_says_so_without_detail(world):
    cat = catalogue(extra_field_visibility=LENA)
    cat["fields"][1]["Personal data class"] = unknown(PAT)  # F002 is undecided and only Lena (and the organiser and sponsor) may see it
    bid = seed(world, kpis=[_ready_kpi()], cat=cat)
    admin, alan = login(world, "co-a"), login(world, "co-a", "Alan Analyst", ("analyst",))
    a, b = (c.get(url(bid, "/technical")).json()["kpis"][0] for c in (admin, alan))
    assert a["ready"]["ready"] is False and b["ready"]["ready"] is False and a["ready"]["label"] == b["ready"]["label"]  # the same gate, the same pill
    assert RD.OPEN_RESTRICTED in b["ready"]["reasons"] and RD.OPEN_RESTRICTED not in a["ready"]["reasons"]
    assert "fx_rate_used" not in json.dumps(b["ready"]) and "F002" not in json.dumps(b["ready"])
    pills = [c.get(url(bid)).json()["kpis"][0]["build"] for c in (admin, alan)]
    assert pills[0] == pills[1] and pills[0]["ready"] is False


def test_the_work_list_pill_and_the_data_owner_confirmation(world):
    bid = seed(world)
    owner = login(world, "co-a")  # Pat Owner is the data owner
    other = login(world, "co-a", "Alan Analyst", ("analyst",))
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
        assert owner.put(url(bid, "/kpis/K01/technical"), json={"part": p, "value": v, "mark": "stated"}).status_code == 200
    k = owner.get(url(bid)).json()["kpis"][0]
    assert k["build"]["ready"] is False and k["build"]["label"] == "1 thing open"  # only the data owner's confirmation is missing
    assert other.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 403
    assert owner.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 200
    assert owner.get(url(bid)).json()["kpis"][0]["build"] == {"ready": True, "label": "Ready to build"}
    assert owner.put(url(bid, "/kpis/K01/technical"), json={"part": "grain", "value": "per account", "mark": "stated"}).status_code == 200
    assert owner.get(url(bid)).json()["kpis"][0]["build"]["ready"] is False  # changed after confirming: confirm again


def test_a_link_only_to_a_catalogue_row_that_exists(world):
    bid = seed(world)
    r = login(world, "co-a").put(url(bid, "/kpis/K01/technical"), json={"part": "fields", "value": ["F001", "F404"], "mark": "stated"})
    assert r.status_code == 422 and "catalogue" in r.json()["message"]


# ---- privacy ------------------------------------------------------------------------------------------------------------------------------

def _two_measures(world):
    """Cash cushion (open to all) and a restricted pay measure only Lena may see; one field of the open measure only Lena may see."""
    pay = kpi("K02", "Bonus pool", personal="yes", may_see=[LENA])
    cat = catalogue(extra_field_visibility=LENA)
    cat["fields"].append(row("fields", "F003", {"Item ID": "T01", "Field name as in the source": "bonus_amount", "Feeds KPI": "K02", "Personal data class": "Personal data"}))
    cat["kpis"].append(row("kpis", "K02", {}))
    return seed(world, kpis=[kpi("K01", "Cash cushion"), pay], cat=cat)


def test_a_restricted_measure_and_field_never_reach_a_viewer_who_may_not_see_them(world):
    bid = _two_measures(world)
    plane = world.plane("co-a")
    secret = "Take bonus_amount per employee and divide by headcount."
    K.change(plane, bid, "K02", lambda k: A.with_ambiguities(T.set_part(k, "calculation", secret, "stated", LENA), [A.make("calculation", "bonus_amount has no rule.", "Which rule for bonus_amount?", "Bonus pool: calculation")]))
    K.change(plane, bid, "K01", lambda k: T.set_part(T.set_part(k, "calculation", "1. Take F002 and apply it to F001.", "stated", PAT), "fields", ["F001", "F002"], "stated", PAT))
    K.change(plane, bid, "K01", lambda k: A.with_ambiguities(k, [A.make("currency", "The fx_rate_used field has no rate date.", "What date does fx_rate_used use?", "Cash cushion: currency basis", refs=[{"tab": "fields", "id": "F002"}])]))
    stub = with_model(world, Stub("CALCULATION:\n1. Take F001."))
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    me = {"admin": login(world, "co-a"), "lena": login(world, "co-a", "Lena Hr", ("analyst",)), "alan": login(world, "co-a", "Alan Analyst", ("analyst",)),
          "sam": login(world, "co-a", "Sam Sponsor", ("sponsor",))}
    for who in ("alan", "sam"):  # an analyst and a sponsor who are not on the pay measure's list (Alan is not on the field's list either)
        c = me[who]
        s = c.get(url(bid, "/technical")).json()
        raw = json.dumps([s, c.get(url(bid, "/ambiguities")).json(), c.get(url(bid, "/lens")).json(), c.get(url(bid)).json(), c.get(url(bid, "/catalogue")).json()["technical"]])
        assert [k["kpi_id"] for k in s["kpis"]] == ["K01"]
        words = ("Bonus pool", "bonus_amount", "headcount", "F003") + (("fx_rate_used", "F002") if who == "alan" else ())
        for word in words:
            assert word not in raw.replace("A restricted measure", ""), (who, word)
        if who == "alan":  # the field's own list (the organiser and the sponsor always pass it, as in the catalogue)
            assert [x["id"] for x in part(s, "K01", "fields")["links"]] == ["F001"]  # the field is not linked for them
            assert part(s, "K01", "calculation")["withheld"] is True and part(s, "K01", "calculation")["cell"]["value"] is None  # a calculation that names it is withheld
        assert c.put(url(bid, "/kpis/K02/technical"), json={"part": "notes", "value": "x", "mark": "stated"}).status_code == 403
        draft(c, bid)
        assert not any(w in stub.prompts for w in words), (who, "the model prompt")
        stub.sent.clear()
    s = me["lena"].get(url(bid, "/technical")).json()
    assert {k["kpi_id"] for k in s["kpis"]} == {"K01", "K02"} and "bonus_amount" in json.dumps(s)  # the person who may see it still does
    assert any("fx_rate_used" in a["text"] for a in me["lena"].get(url(bid, "/ambiguities")).json()["ambiguities"])
    assert "F002" in [x["id"] for x in part(s, "K01", "fields")["links"]]


def test_a_participant_and_another_company_are_refused(world):
    bid = seed(world)
    seed(world, "co-b", [kpi("K05", "Other measure")], cat=None)
    participant = login(world, "co-a", "Pia Participant", ("participant",))
    assert participant.get(url(bid, "/technical")).status_code == 403 and participant.post(url(bid, "/lens/technical"), json={}).status_code == 403
    outsider = login(world, "co-b", "Olga Outsider")
    assert outsider.get(url(bid, "/technical")).status_code in (403, 404) and outsider.get(url(bid, "/ambiguities")).status_code in (403, 404)
    off = login(world, "co-off", "Ola Off")
    assert off.get(url(bid, "/technical")).status_code in (403, 404)


def test_a_restricted_document_is_read_only_for_a_personal_measure_and_cleared_when_it_is_relaxed(world):
    pay = kpi("K02", "Bonus pool", personal="yes", may_see=[PAT, LENA])
    bid = seed(world, kpis=[pay], cat=None)
    upload(world, "co-a", "Pay policy", "## Bonus pool\n- Source: Pay_Review_Workbook.xlsx\n- Steps: take each target bonus and compare it with the approved figure.\n- Limit: ask Lina.", restricted=True)
    stub = with_model(world, Stub("CALCULATION:\n1. Compare each target bonus with the approved figure.\nMISSING: nothing"))
    c = login(world, "co-a")
    s = draft(c, bid)
    assert stub.sent and "target bonus" in stub.prompts  # a person who may see the measure lets Lens read the restricted document
    k = K.read_kpis(world.plane("co-a"), bid)[0]
    assert k["technical"]["calculation"]["restricted"] is True and any(a.get("restricted") for a in k["ambiguities"])
    assert c.put(url(bid, "/kpis/K02/governance"), json={"personal": "no", "sensitive": False}).status_code == 200  # relaxed: everything drawn from it goes
    k = K.read_kpis(world.plane("co-a"), bid)[0]
    assert k["technical"]["calculation"]["mark"] == "unknown" and not any(a.get("restricted") for a in k["ambiguities"])
    plain_measure = seed(world, "co-b", [kpi("K03", "Bonus pool")], cat=None)
    upload(world, "co-b", "Pay policy", "## Bonus pool\n- Steps: take each target bonus.", restricted=True)
    other = with_model(world, Stub())
    draft(login(world, "co-b", "Bea Owner"), plain_measure)
    assert other.sent == []  # a restricted document is never used for a measure not marked personal


# ---- signed, the catalogue, the industries --------------------------------------------------------------------------------------------------

def test_a_signed_baseline_refuses_every_write(world):
    bid = seed(world)
    plane = world.plane("co-a")
    K.change(plane, bid, "K01", lambda x: A.with_ambiguities(x, [A.make("period", "x", "y", "Cash cushion: period")]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    B.set_state(plane, bid, "signed")
    for method, tail, body in (("put", "/kpis/K01/technical", {"part": "notes", "value": "x", "mark": "stated"}), ("post", "/kpis/K01/technical/use", {"part": "notes"}),
                               ("post", "/kpis/K01/technical/confirm", {}), ("post", "/lens/technical", {}), ("post", "/lens/technical/redraft", {"kpi_id": "K01", "instruction": "x"}),
                               ("post", f"/kpis/K01/ambiguities/{amb['id']}/answer", {"resolution": "x"}), ("post", f"/kpis/K01/ambiguities/{amb['id']}/accept", {"reason": "x"}),
                               ("post", f"/kpis/K01/ambiguities/{amb['id']}/ask", {})):
        r = getattr(c, method)(url(bid, tail), json=body)
        assert r.status_code == 409 and r.json()["error"] == "signed", tail
    assert c.get(url(bid, "/technical")).status_code == 200  # reading stays open


def test_the_catalogue_shows_the_calculation_and_the_inputs_and_the_excel_file_has_the_sheet(world):
    bid = seed(world)
    c = login(world, "co-a")
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take closing_balance."), ("period", "month end")):
        c.put(url(bid, "/kpis/K01/technical"), json={"part": p, "value": v, "mark": "stated"})
    cat = c.get(url(bid, "/catalogue")).json()
    assert cat["technical"]["kpis"]["K01"]["calculation"] == "1. Take closing_balance." and cat["technical"]["kpis"]["K01"]["sources"] == "Northgate Custody daily file"
    assert cat["technical"]["inputs"] == {"F001": ["Cash cushion"]}
    book = c.get(url(bid, "/catalogue/export"))
    assert book.status_code == 200 and "Technical definitions" in list(read_book(book.content))


def test_two_industries_and_an_empty_company(world):
    for company in ("co-a", "co-b", "co-none"):
        bid = seed(world, company, kpis=[], cat=None)
        c = login(world, company, f"Pat {company}")
        s = c.get(url(bid, "/technical")).json()
        assert s["kpis"] == [] and s["ambiguities"] == [] and s["summary"] == {"measures": 0, "drafted": 0, "ready": 0, "open": 0}
        assert draft(c, bid)["outcomes"] == {}
    bid = seed(world, "co-b", [kpi("K07", "Industry b measure")], cat=None)
    stub = with_model(world, Stub())
    s = draft(login(world, "co-b"), bid)
    assert s["outcomes"] == {"K07": "nothing"} and stub.sent == [] and kinds(s, "K07") == {"calculation"}  # nothing from another industry's pack


def test_lens_block_says_how_far_it_is(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    with_model(world, Stub())
    c = login(world, "co-a")
    before = c.get(url(bid, "/lens")).json()["technical"]
    assert before["pending"] == ["K01"] and before["drafted"] == 0
    draft(c, bid)
    t = c.get(url(bid, "/lens")).json()["technical"]
    assert t["pending"] == [] and t["drafted"] == 1 and t["say"].startswith("I drafted the technical definition for 1 of 1 measure.") and "open question" in t["say"]


def test_redraft_keeps_a_persons_part_beside_the_new_draft(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    stub = with_model(world, Stub())
    c = login(world, "co-a")
    c.put(url(bid, "/kpis/K01/technical"), json={"part": "grain", "value": "per fund", "mark": "stated"})
    r = c.post(url(bid, "/lens/technical/redraft"), json={"kpi_id": "K01", "instruction": "Make the grain per account"})
    assert r.status_code == 200 and r.json()["outcome"] == "redrafted" and "Make the grain per account" in stub.prompts
    g = part(r.json(), "K01", "grain")
    assert g["cell"]["value"] == "per fund" and g["proposal"]["value"] == "per account per month"


def test_the_shared_helper_is_the_one_the_glossary_and_governance_use():
    from modules.m2_baseline.domain import glossary as G
    from modules.m2_baseline.domain import governance_view as GV
    assert not hasattr(G, "new_ambiguity") and not hasattr(G, "with_ambiguities")  # moved, not copied
    g = GV.ambiguity("K01|measure:K01", "t", "q", "w")
    assert g["kind"] == "governance" and g["status"] == "open" and g["id"].startswith("gov-") and g["at"] is None
    assert A.with_ambiguities({"ambiguities": [g]}, [GV.ambiguity("K01|measure:K01", "t", "q", "w")])["ambiguities"] == [g]
    assert A.mentions({"text": "the Salary field"}, ["salary"]) and not A.mentions({"text": "salaries"}, ["salary"])
    assert ST.unmark_restricted({"id": "k", "ambiguities": [{"restricted": True, "id": "a"}, {"id": "b"}]})["ambiguities"] == [{"id": "b"}]


# ---- review round: ask the owner, duplicates, re-opening, hidden names ------------------------------------------------------------------------

def _asked(world, k=None, cat="default", question="Which rate, from where, on which date?", text="No rate date.", refs=None):
    k = k or kpi("K01", "Cash cushion")
    k["owners"]["data"] = prov("Arjun Rao", "stated", PAT, "nominated")
    bid = seed(world, kpis=[k], cat=cat)
    K.change(world.plane("co-a"), bid, k["id"], lambda x: A.with_ambiguities(x, [A.make("currency", text, question, f"{k['name']}: currency", refs=refs)]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    return bid, c, amb


def _visitor(world, link_path):
    v = TestClient(world.app)
    v.headers["x-session-token"] = link_path.removeprefix("/answer/")
    return v


def test_the_owner_sees_the_question_on_the_answer_page_and_the_reply_settles_it_as_their_answer(world):
    bid, c, amb = _asked(world)
    link = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]["link_path"]
    v = _visitor(world, link)  # an owner with no account, holding only the link
    form = v.post(f"{BASE}/answer/form").json()
    assert form["questions"] == [{"ambiguity_id": amb["id"], "kpi_id": "K01", "kpi_name": "Cash cushion", "text": "Which rate, from where, on which date?", "needs_sign_in": False}]
    assert v.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": "amb-nope", "resolution": "x"}).status_code == 422  # only a question put to them
    r = v.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Custody rate at close."})
    assert r.status_code == 200 and r.json()["questions"] == []
    k = K.read_kpis(world.plane("co-a"), bid)[0]
    got = k["ambiguities"][0]
    assert (got["status"], got["by"], got["resolution"]) == ("settled", "Arjun Rao", "Custody rate at close.")
    assert T.parts_of(k)["currency_basis"]["mark"] == "unknown"  # the owner's reply is recorded on the question; it never writes a part (critic round 5)
    assert v.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "again"}).status_code == 422  # settled: nothing to answer


def test_a_question_that_would_name_a_field_hidden_from_the_owner_is_worded_generically(world):
    bid, c, amb = _asked(world, cat=catalogue(extra_field_visibility=LENA), question="What date does fx_rate_used use?", text="The fx_rate_used field has no date.",
                         refs=[{"tab": "fields", "id": "F002"}])
    r = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]  # the organiser sees the field; the owner (Arjun) may not
    assert "fx_rate_used" not in r["email"]["body"] and "A question about Cash cushion needs your answer." in r["email"]["body"]
    form = _visitor(world, r["link_path"]).post(f"{BASE}/answer/form").json()
    assert form["questions"][0]["text"] == "A question about Cash cushion needs your answer." and "fx_rate_used" not in json.dumps(form)


def test_a_restricted_measures_question_is_never_sent_to_an_owner_not_on_its_list(world):
    pay = kpi("K02", "Bonus pool", personal="yes", may_see=[LENA])
    bid, c, amb = _asked(world, k=pay)
    r = c.post(url(bid, f"/kpis/K02/ambiguities/{amb['id']}/ask"), json={})
    assert r.status_code == 422 and "may not see" in r.json()["message"]
    assert c.get(url(bid, "/requests")).json()["requests"] == []  # no request, no link, no email


def test_a_question_for_an_owner_whose_link_was_withdrawn_gets_a_new_link_and_is_not_lost(world):
    bid, c, amb = _asked(world)
    first = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]
    rid = c.get(url(bid, "/requests")).json()["requests"][0]["id"]
    assert c.post(url(bid, f"/requests/{rid}/revoke")).status_code == 200
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, [A.make("currency", "No rate source.", "Which date?", "Cash cushion: currency, the rate source")]))
    second_amb = next(a for a in c.get(url(bid, "/ambiguities")).json()["ambiguities"] if a["question"] == "Which date?")
    again = c.post(url(bid, f"/kpis/K01/ambiguities/{second_amb['id']}/ask"), json={}).json()["asked"]
    assert again["link_path"] and again["link_path"] != first["link_path"]  # a new link: the dead one is never used
    assert _visitor(world, first["link_path"]).post(f"{BASE}/answer/form").status_code in (404, 409)
    form = _visitor(world, again["link_path"]).post(f"{BASE}/answer/form").json()
    assert {q["text"] for q in form["questions"]} == {"Which rate, from where, on which date?", "Which date?"}  # both questions are on the page
    assert len(c.get(url(bid, "/requests")).json()["requests"]) == 1


def test_a_rephrased_finding_is_not_raised_again_after_it_was_settled(world):
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    words = iter(["CONFLICT: conflict | period bucket | The glossary and the note disagree on the month. | Which date decides the month? | ",
                  "CONFLICT: conflict | the period bucket | Two places give different dates for the month bucket. | Notice date or due date? | "])
    with_model(world, Stub(lambda name: next(words)))
    c = login(world, "co-a")
    first = draft(c, bid)
    item = next(a for a in first["ambiguities"] if a["kind"] == "conflict")
    c.post(url(bid, f"/kpis/K01/ambiguities/{item['id']}/answer"), json={"resolution": "Due date."})
    again = draft(c, bid, retry=True)
    items = [a for a in again["ambiguities"] if a["kind"] == "conflict"]
    assert len(items) == 1 and items[0]["id"] == item["id"] and items[0]["status"] == "settled"  # one finding per measure, kind and part: Lens's wording does not decide identity


def test_a_settled_item_is_reopened_visibly_when_its_answer_is_overwritten_or_a_new_document_disagrees(world):
    bid = seed(world)
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, [A.make("period", "No period.", "Which date?", "Cash cushion: period")]))
    c = login(world, "co-a")
    amb = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/answer"), json={"resolution": "Month end.", "part": "period", "wording": "Month end."})
    assert c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]["status"] == "settled"
    c.put(url(bid, "/kpis/K01/technical"), json={"part": "period", "value": "Last business day", "mark": "stated"})
    got = c.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    assert got["status"] == "open" and got["reopened"].startswith("Re-opened: the period was changed by") and got["history"][0]["resolution"] == "Month end."  # visible, history kept
    # a document the item was not raised from now says something about it
    old = A.settle(A.with_ambiguities(kpi("K01", "Cash cushion"), [A.make("period", "x", "y", "Cash cushion: period", basis=["Notes"])]), "x", "z", "p") if False else None
    k = A.with_ambiguities(kpi("K01", "Cash cushion"), [A.make("period", "x", "y", "Cash cushion: period", basis=["Notes"])])
    k = A.settle(k, k["ambiguities"][0]["id"], "Month end.", "Pat")
    assert A.with_ambiguities(k, [A.make("period", "again", "y", "Cash cushion: period", basis=["Notes"])])["ambiguities"][0]["status"] == "settled"  # the same document: nothing changed
    k2 = A.with_ambiguities(k, [A.make("period", "again", "y", "Cash cushion: period", basis=["Notes", "Policy"])])["ambiguities"][0]
    assert k2["status"] == "open" and k2["reopened"] == "Re-opened: Policy now says something about this" and k2["history"][0]["status"] == "settled"
    assert old is None


def test_short_and_embedded_hidden_names_are_found_and_the_whole_part_is_withheld():
    assert A.mentions({"text": "the tx field is empty"}, ["tx"]) and not A.mentions({"text": "the next field"}, ["tx"])  # 2 characters: a whole word
    assert A.mentions({"text": "Salaries are missing"}, ["salary"]) is False and A.mentions({"text": "the salary_band column"}, ["salary"])  # a longer name inside a word
    k = T.set_part(kpi("K01", "Cash cushion"), "calculation", "1. Take F003 and add tx.", "stated", "Pat")
    parts = {p["part"]: p for p in T.view_parts(k, {"F001": "closing_balance"}, ["F003", "bonus_amount"])}
    assert parts["calculation"]["withheld"] and parts["calculation"]["cell"]["value"] is None  # by id
    parts = {p["part"]: p for p in T.view_parts(k, {"F001": "closing_balance"}, ["tx"])}
    assert parts["calculation"]["withheld"]  # by a name of two characters
    assert T.finding_key("Cash cushion", "conflict", "the period bucket", "x") == T.finding_key("Cash cushion", "conflict", "period bucket", "y")


def test_different_thresholds_are_different_findings_and_a_rephrasing_of_one_is_still_one(world):
    names = ["stress limit", "age limit", "the stress multiplier"]
    keys = {T.finding_key("Cash cushion", "threshold", n, "No number.") for n in names}
    assert len(keys) == 3  # the three share a part (filters) but not a subject
    bid = seed(world)
    upload(world, "co-a", "Technical notes", story("17_technical_notes_raw.md"))
    lines = "\n".join(f"CONFLICT: threshold | {n} | {t} | What is the number? | " for n, t in zip(names, ("The stress limit has no number.", "The age limit has no number.", "The multiplier has no number.")))
    with_model(world, Stub(lambda name: lines))
    c = login(world, "co-a")
    got = [a for a in draft(c, bid)["ambiguities"] if a["kind"] == "threshold" and a["raised_by"] == "Lens" and a["where"].startswith("Cash cushion: threshold (filters)")]
    assert len(got) == 3
    again = [a for a in draft(c, bid, retry=True)["ambiguities"] if a["kind"] == "threshold" and a["where"].startswith("Cash cushion: threshold (filters)")]
    assert len(again) == 3  # raised once each
    with_model(world, Stub(lambda name: "CONFLICT: threshold | age limit | Nobody wrote a number for how old is too old. | And what number? | "))
    assert len([a for a in draft(c, bid, retry=True)["ambiguities"] if "age limit" in a["where"]]) == 1  # same subject, new words: still one


def test_a_part_is_found_by_whole_words_only():
    assert T.subject_of("the management sign-off", "") == "" and T.subject_of("", "generate an internet super report") == ""
    assert T.subject_of("age limit", "") == "filters" or T.subject_of("age basis", "") == "calculation"  # "age" as a word still counts
    assert T.subject_of("the net or gross question", "") == "calculation" and T.subject_of("fx rates", "") == "currency_basis"
    assert T.finding_key("M", "calculation", "the management sign-off", "x") == "M: calculation management sign off"


# ---- an owner WITH an account answers signed in -----------------------------------------------------------------------------------------------

def _account_owner(world):
    dana = login(world, "co-a", "Dana Data", ("owner",))
    acct = next(a for a in world.accounts.in_company("co-a") if a["display_name"] == "Test Dana Data")
    k = kpi("K01", "Cash cushion")
    k["owners"]["data"] = {**prov("Test Dana Data", "stated", PAT, "nominated, with an account"), "account_id": acct["account_id"]}
    bid = seed(world, kpis=[k])
    K.change(world.plane("co-a"), bid, "K01", lambda x: A.with_ambiguities(x, [A.make("currency", "No rate date.", "Which rate, from where, on which date?", "Cash cushion: currency")]))
    admin = login(world, "co-a")
    amb = admin.get(url(bid, "/ambiguities")).json()["ambiguities"][0]
    link = admin.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]["link_path"]
    return bid, dana, amb, link


def test_a_forwarded_link_cannot_answer_for_an_owner_with_an_account(world):
    bid, dana, amb, link = _account_owner(world)
    visitor = _visitor(world, link)  # whoever holds the link, with no session
    form = visitor.post(f"{BASE}/answer/form").json()
    assert form["questions"][0]["needs_sign_in"] is True  # shown, read-only
    r = visitor.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Whatever."})
    assert r.status_code == 403 and r.json()["message"] == "Please sign in to answer this question."
    assert K.read_kpis(world.plane("co-a"), bid)[0]["ambiguities"][0]["status"] == "open"
    stranger = login(world, "co-a", "Sam Stranger", ("owner",))  # signed in, but as someone else
    stranger.headers["x-session-token"] = link.removeprefix("/answer/")
    assert stranger.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Whatever."}).status_code == 403


def test_the_owner_with_an_account_answers_signed_in_and_it_is_stated_by_them(world):
    bid, dana, amb, link = _account_owner(world)
    dana.headers["x-session-token"] = link.removeprefix("/answer/")
    assert dana.post(f"{BASE}/answer/form").json()["questions"][0]["needs_sign_in"] is False
    r = dana.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Custody rate at close."})
    assert r.status_code == 200 and r.json()["questions"] == []
    got = K.read_kpis(world.plane("co-a"), bid)[0]["ambiguities"][0]
    assert (got["status"], got["by"]) == ("settled", "Test Dana Data")


def test_an_owner_without_an_account_still_answers_by_link(world):
    bid, c, amb = _asked(world)
    link = c.post(url(bid, f"/kpis/K01/ambiguities/{amb['id']}/ask"), json={}).json()["asked"]["link_path"]
    v = _visitor(world, link)
    assert v.post(f"{BASE}/answer/form").json()["questions"][0]["needs_sign_in"] is False
    assert v.post(f"{BASE}/answer/question", json={"kpi_id": "K01", "ambiguity_id": amb["id"], "resolution": "Custody rate."}).status_code == 200


def test_a_pending_personal_document_never_reaches_the_model_for_a_non_personal_measure_until_cleared(world):
    from modules.m2_baseline.domain import preread as PR
    bid = seed(world)
    marker = "Zanzibar reconciliation rule"
    doc = upload(world, "co-a", "Pay notes", f"The salary band bonus file. {marker}: cash cushion uses the closing balance of every account each month end.", decided=False)
    stub = with_model(world, Stub())
    c = login(world, "co-a")
    draft(c, bid)  # the bulk draft
    assert c.post(url(bid, "/lens/technical/redraft"), json={"kpi_id": "K01", "instruction": "Make the grain per account"}).status_code == 200
    assert marker not in stub.prompts and "Pay notes" not in stub.prompts  # held back, both paths
    PR.clear(world.plane("co-a"), doc)  # the organiser: not personal
    draft(c, bid, retry=True)
    assert marker in stub.prompts
    before = len(stub.sent)
    assert c.post(url(bid, "/lens/technical/redraft"), json={"kpi_id": "K01", "instruction": "Make the grain per account"}).status_code == 200
    assert len(stub.sent) > before and marker in json.dumps(stub.sent[-1])


# ---- IC-3e: send a technical definition back with a note (kept beside it, the owner sees it on their list) -------------------------------

def test_send_back_records_a_note_the_data_owner_sees_and_confirming_clears_it(world):
    bid = seed(world)
    owner, boss = login(world, "co-a"), login(world, "co-a", "Sam Sponsor", ("sponsor",))
    for p, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
        assert owner.put(url(bid, "/kpis/K01/technical"), json={"part": p, "value": v, "mark": "stated"}).status_code == 200
    before = owner.get(url(bid, "/technical")).json()["kpis"][0]["parts"]
    r = boss.post(url(bid, "/measures/K01/send-back"), json={"note": "  Which   rate date?  "})
    assert r.status_code == 200 and r.json()["kpis"][0]["sent_back"]["note"] == "Which rate date?"
    mine = owner.get(url(bid, "/my-technical")).json()["kpis"][0]
    assert mine["sent_back"]["label"] == "Sent back: Which rate date?" and mine["sent_back"]["by"] == "Test Sam Sponsor"
    assert owner.get(url(bid, "/technical")).json()["kpis"][0]["parts"] == before  # the definition itself is untouched
    assert owner.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 200
    assert owner.get(url(bid, "/my-technical")).json()["kpis"][0]["sent_back"] is None


def test_send_back_needs_a_note_and_a_visible_measure(world):
    bid = seed(world)
    c = login(world, "co-a")
    assert c.post(url(bid, "/measures/K01/send-back"), json={"note": "  "}).status_code == 422
    assert c.post(url(bid, "/measures/K01/send-back"), json={"note": "x" * 301}).status_code == 422
    assert c.post(url(bid, "/measures/K99/send-back"), json={"note": "x"}).status_code == 404


def test_send_back_works_on_a_signed_baseline_and_never_edits_it(world):
    bid = seed(world)
    plane = world.plane("co-a")
    owner = login(world, "co-a")
    B.set_state(plane, bid, "signed")
    kpis_file = plane.path("intents", "m2_baseline", bid, "kpis.json")
    before = kpis_file.read_bytes()
    r = owner.post(url(bid, "/measures/K01/send-back"), json={"note": "Which rate date?"})
    assert r.status_code == 200, r.text
    assert kpis_file.read_bytes() == before
    assert owner.get(url(bid, "/my-technical")).json()["kpis"][0]["sent_back"]["label"] == "Sent back: Which rate date?"
    assert owner.post(url(bid, "/kpis/K01/technical/confirm")).status_code == 409  # everything else stays locked
