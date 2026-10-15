"""M2-E2: the business glossary of a baseline: built from the measures, a provided glossary read and compared, a person's choice kept,
ambiguities raised, review, downloads filtered per viewer, privacy and permissions. Synthetic family-office wording only."""
import base64
import io
import zipfile

import pytest
from m2_kit import BASE, login
from test_m2_catalogue_xlsx import read_book

from modules.m2_baseline.domain import glossary as G
from modules.m2_baseline.domain import glossary_export as E
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.domain.provenance import prov
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import glossary as S
from modules.m2_baseline.store import kpis as K
from sh_platform.agents.protocols import ModelReply
from sh_platform.context_docs.store import DocStore

SPECS = [  # (name, current definition, personal, may_see)
    ("Capital calls due", "Capital calls we expect to pay in the next month.", "no", []),
    ("Net asset value", "The value of the fund gross of fees, in SGD.", "no", []),
    ("Cash buffer", "Cash held back for the next 90 days.", "no", []),
    ("Overdue notices", "Notices not paid by their due date.", "no", []),
    ("Investor count", "", "no", []),
    ("Executive pay", "Total pay of the executive team.", "yes", ["Test Pat Boss"]),
]
CSV = (b"Term,Definition,Aliases,Owner,Frequency\n"
       b"Funding calls due,Capital calls we expect to pay in the next month.,Capital calls due; Call notices,,Monthly\n"
       b"Net asset value,\"The value of the fund net of fees, in USD.\",NAV,,\n"
       b"Cash buffer,Cash held back for the next 90 days.,,,\n"
       b"Vendor rating,How we score suppliers.,,,\n"
       b"Delinquent accounts,Notices not paid by their due date.,,,\n"
       b"Executive pay,Total pay of the executive team including bonus.,,,\n"
       b"CEO compensation,What the chief executive is paid in total.,,,\n")
RESTRICTED_WORDS = (b"Executive pay", b"executive team", b"CEO compensation", b"chief executive")


class Stub:
    def __init__(self, reply="T2 = M1"):
        self.reply, self.sent = reply, []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        return ModelReply(self.reply)


def seed(world, company="co-a", specs=SPECS) -> str:
    plane = world.plane(company)
    base, _ = B.start(plane, None)
    for i, (name, definition, personal, may) in enumerate(specs):
        k = W.new_kpi(f"kpi-{i}", name, [], None, prov(definition, "stated", "Pat Owner", "the work list") if definition else None)
        k["governance"] = {"personal": personal, "sensitive": False, "may_see": may}
        k["owners"]["business"] = prov("Sara Lim", "stated", "Pat Owner", "the work list")
        K.add(plane, base["id"], k)
    return base["id"]


def gurl(bid, tail=""):
    return f"{BASE}/baselines/{bid}/glossary{tail}"


def upload(c, bid, name="glossary.csv", data=CSV, **extra):
    return c.post(gurl(bid, "/upload"), json={"filename": name, "data": base64.b64encode(data).decode(), **extra})


def entry(view, name):
    return next(e for e in view["entries"] if not e.get("hidden") and e["text"]["term"] == name)


@pytest.fixture
def stub(world):
    s = Stub()
    world.app.state.lens_model_factory = lambda plane: s
    return s


# ---- built from the baseline alone

def test_a_glossary_is_built_from_the_measures_and_everything_is_new(world):
    bid, c = seed(world), login(world, "co-a")
    assert c.get(gurl(bid)).json()["built"] is False
    v = c.post(gurl(bid, "/build")).json()
    assert v["built"] and v["counts"]["all"] == 6 and v["counts"]["new"] == 6 and v["provided"] is None
    e = entry(v, "Capital calls due")
    assert e["change"] == "new" and e["previous"]["mark"] == "unknown" and e["assumption"] == "" and e["reviewed"] is None
    assert e["term"]["mark"] == "stated" and e["business_definition"]["by"] == "Pat Owner"  # each value keeps its provenance
    assert e["owner"]["value"] == "Sara Lim" and e["personal"] == "no" and e["text"]["who"] == G.OPEN_TO_ALL
    assert entry(v, "Investor count")["text"]["definition"] == "Not available yet"  # a missing wording is never blank or zero
    assert [x["text"]["term"] for x in v["entries"]][:2] == ["Capital calls due", "Net asset value"]


# ---- a provided glossary: exact, alias and meaning matches; unchanged, changed, new

def test_a_provided_glossary_is_compared_and_unmatched_terms_are_listed(world, stub):
    bid, c = seed(world), login(world, "co-a")
    v = upload(c, bid).json()
    assert v["provided"]["title"] == "glossary.csv" and v["provided"]["by"] == "Test Pat Owner"
    calls, nav, cash = entry(v, "Capital calls due"), entry(v, "Net asset value"), entry(v, "Cash buffer")
    assert calls["change"] == "unchanged" and calls["match"] == "name" and calls["source_document"] == "glossary.csv"  # matched through an alias
    assert "Funding calls due" in calls["text"]["aliases"] and calls["frequency"]["value"] == "Monthly"
    assert nav["change"] == "changed" and "net of fees, in USD" in nav["previous"]["value"] and "gross of fees" in nav["business_definition"]["value"]
    assert nav["assumption"].endswith(".") and "\n" not in nav["assumption"] and nav["source_document"] == "glossary.csv"
    assert cash["change"] == "unchanged"
    assert entry(v, "Investor count")["change"] == "new" and "not in your glossary" in entry(v, "Investor count")["assumption"]
    assert [t["term"] for t in v["unmatched_terms"]] == ["Vendor rating", "CEO compensation"]  # the glossary's own terms with no measure, for the organiser
    assert entry(v, "Overdue notices")["match"] == "meaning" and entry(v, "Overdue notices")["change"] == "unchanged"
    assert v["counts"]["changed"] == 2 and v["counts"]["new"] == 1  # the restricted measure is counted for those who see it: the admin does
    docs = {d["description"]: d for d in DocStore(world.plane("co-a")).documents("lens")}
    assert docs["Business glossary"]["restricted"] is False and docs["Business glossary"]["visibility"] == "shared_full" and len(docs) == 1  # on Lens's shelf, readable in full  # one document; neither the original file nor a restricted part is kept


def test_the_model_gets_only_unmatched_names_and_never_a_wording_or_a_restricted_measure(world, stub):
    bid = seed(world)
    c = login(world, "co-a", "Ann Analyst", ("analyst",))
    upload(c, bid)
    sent = " ".join(str(m) for turn in stub.sent for m in turn)
    assert len(stub.sent) == 1 and "Vendor rating" in sent and "Overdue notices" in sent and "T1:" in sent
    assert "wrap" not in sent and "BEGIN QUOTED DOCUMENT TEXT" in sent  # the terms arrive as untrusted quoted content
    for secret in ("gross of fees", "net of fees", "Executive pay", "executive team", "Sara Lim"):
        assert secret not in sent


def test_without_a_model_nothing_is_guessed_and_a_refused_call_is_told(world):
    bid, c = seed(world), login(world, "co-a")
    v = upload(c, bid).json()  # no model set up
    assert entry(v, "Overdue notices")["change"] == "new" and "Vendor rating" in [t["term"] for t in v["unmatched_terms"]]

    class Refused:
        def complete(self, *a, **k):
            raise RuntimeError("refused")
    world.app.state.lens_model_factory = lambda plane: Refused()
    assert "lens_note" in c.post(gurl(bid, "/build")).json() or "lens_note" in upload(c, bid).json()


# ---- ambiguities

def test_a_contradiction_is_recorded_as_an_ambiguity_on_the_measure(world, stub):
    bid, c = seed(world), login(world, "co-a")
    upload(c, bid)
    nav = next(k for k in K.read_kpis(world.plane("co-a"), bid) if k["name"] == "Net asset value")
    amb = nav["ambiguities"]
    assert {a["kind"] for a in amb} == {"calculation", "currency"}
    a = next(a for a in amb if a["kind"] == "currency")
    assert set(a) == {"id", "kind", "text", "question", "where", "raised_by", "status", "resolution", "by", "at"}
    assert a["raised_by"] == "Lens" and a["status"] == "open" and a["resolution"] is None and "USD" in a["text"].upper() and a["where"].endswith("Net asset value")
    upload(c, bid)  # a second build adds nothing new
    assert len(next(k for k in K.read_kpis(world.plane("co-a"), bid) if k["name"] == "Net asset value")["ambiguities"]) == 2
    assert "ambiguities" not in next(k for k in K.read_kpis(world.plane("co-a"), bid) if k["name"] == "Cash buffer")


def test_owner_and_period_disagreements_are_found():
    got = G.disagreements("Reported monthly.", "Reported quarterly.", "Sara Lim", "Wei Tan", "Bank portal", "Bank portal")
    assert [k for k, _, _ in got] == ["period", "owner"]
    assert G.disagreements("Counts calls.", "Counts calls.", "", "Wei", "", "") == []  # nothing said on one side is not a contradiction


# ---- a person's choice

def test_a_choice_is_stated_by_the_person_and_survives_a_rebuild(world, stub):
    bid, c, plane = seed(world), login(world, "co-a", "Mei Reviewer"), world.plane("co-a")
    upload(c, bid)
    nav_id = next(e["kpi_id"] for e in S.read(plane, bid)["entries"] if e["term"]["value"] == "Net asset value")
    v = c.put(gurl(bid, f"/entries/{nav_id}"), json={"choice": "provided"}).json()
    e = entry(v, "Net asset value")
    assert e["business_definition"]["value"].startswith("The value of the fund net of fees") and e["business_definition"]["mark"] == "stated"
    assert e["business_definition"]["by"] == "Test Mei Reviewer" and e["decided"]["choice"] == "provided" and e["reviewed"]["by"] == "Test Mei Reviewer"
    K.change(plane, bid, nav_id, lambda k: {**k, "definition": prov("Fund value after fees, in SGD, at month end.", "stated", "Pat Owner", "work list")})
    again = c.post(gurl(bid, "/build")).json()
    e = entry(again, "Net asset value")
    assert e["business_definition"]["by"] == "Test Mei Reviewer" and "net of fees" in e["business_definition"]["value"]  # never overwritten
    assert e["proposal"]["value"].startswith("Fund value after fees") and e["proposal"]["mark"] == "guessed"  # the later draft sits beside it
    assert e["change"] == "changed" and e["reviewed"]["by"] == "Test Mei Reviewer"
    kept = c.put(gurl(bid, f"/entries/{nav_id}"), json={"choice": "ours"}).json()
    assert entry(kept, "Net asset value")["business_definition"]["value"].startswith("The value of the fund net of fees")  # "ours" keeps what stands
    edited = c.put(gurl(bid, f"/entries/{nav_id}"), json={"choice": "edited", "text": "  Fund value, net, in SGD. "}).json()
    assert entry(edited, "Net asset value")["business_definition"]["value"] == "Fund value, net, in SGD."


def test_a_choice_that_has_nothing_to_keep_is_refused_in_plain_words(world):
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    c.post(gurl(bid, "/build"))
    ids = {e["term"]["value"]: e["kpi_id"] for e in S.read(plane, bid)["entries"]}
    assert "no wording for this measure" in c.put(gurl(bid, f"/entries/{ids['Cash buffer']}"), json={"choice": "provided"}).json()["message"]
    assert "no wording in this baseline" in c.put(gurl(bid, f"/entries/{ids['Investor count']}"), json={"choice": "ours"}).json()["message"]
    assert c.put(gurl(bid, f"/entries/{ids['Cash buffer']}"), json={"choice": "edited", "text": "  "}).status_code == 422
    assert c.put(gurl(bid, "/entries/nope"), json={"choice": "ours"}).status_code == 404


# ---- review

def test_unchanged_can_be_reviewed_together_changed_and_new_one_by_one(world, stub):
    bid, c, plane = seed(world), login(world, "co-a", "Mei Reviewer"), world.plane("co-a")
    upload(c, bid)
    ready, why = S.glossary_ready(plane, bid)
    assert not ready and any("2 changed entries have not been reviewed" in w for w in why) and all("Net asset" not in w for w in why)
    v = c.post(gurl(bid, "/review-unchanged")).json()
    assert v["counts"]["reviewed"] == 3 and entry(v, "Cash buffer")["reviewed"]["by"] == "Test Mei Reviewer"  # by name, by alias and by meaning
    assert entry(v, "Net asset value")["reviewed"] is None and entry(v, "Investor count")["reviewed"] is None
    for name in ("Net asset value", "Investor count", "Executive pay"):
        c.post(gurl(bid, f"/entries/{entry(v, name)['kpi_id']}/review"))
    assert S.glossary_ready(plane, bid) == (True, [])
    K.add(plane, bid, W.new_kpi("kpi-late", "Late addition", [], None))
    ready, why = S.glossary_ready(plane, bid)
    assert not ready and "1 measure is not in the glossary yet" in why[0]
    assert c.get(gurl(bid)).json()["waiting"] == 1


def test_a_reviewed_entry_is_unreviewed_when_its_wording_changes_under_it(world):
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    c.post(gurl(bid, "/build"))
    c.post(gurl(bid, "/review-unchanged"))
    K.change(plane, bid, "kpi-2", lambda k: {**k, "definition": prov("Cash held back for six months.", "stated", "Pat", "work list")})
    assert entry(c.post(gurl(bid, "/build")).json(), "Cash buffer")["reviewed"] is None


# ---- privacy: a restricted measure is hidden for people who may not see it

def test_a_restricted_measure_is_hidden_in_the_view_the_comparison_and_both_downloads(world, stub):
    bid = seed(world)
    admin = login(world, "co-a")
    admin_view = upload(admin, bid).json()
    assert entry(admin_view, "Executive pay")["change"] == "changed"
    ann = login(world, "co-a", "Ann Analyst", ("analyst",))
    v = ann.get(gurl(bid)).json()
    assert not any(e.get("hidden") for e in v["entries"]) and len(v["entries"]) == 5  # no stub, no id, no count of what is hidden
    assert v["counts"]["all"] == 5 and v["counts"]["changed"] == 1 and "kpi-5" not in str(v) and "executive team" not in str(v)
    assert v["unmatched_terms"] == [] and "CEO compensation" not in str(v)  # an unmatched term may be about a restricted measure
    assert [t["term"] for t in admin_view["unmatched_terms"]] == ["Vendor rating", "CEO compensation"]
    x, h = ann.get(gurl(bid, "/export")), ann.get(gurl(bid, "/print"))
    assert x.status_code == h.status_code == 200
    for blob in (x.content, h.content, str(read_book(x.content)).encode()):
        assert not any(w in blob for w in RESTRICTED_WORDS)
    assert b"Executive pay" in admin.get(gurl(bid, "/print")).content  # the admin sees it
    named = login(world, "co-a", "Pat Boss", ("analyst",))
    assert b"Executive pay" in named.get(gurl(bid, "/print")).content  # so does the person named for it
    assert ann.put(gurl(bid, "/entries/kpi-5"), json={"choice": "ours"}).status_code == 404  # same answer as a measure that does not exist
    assert ann.post(gurl(bid, "/entries/kpi-5/review")).status_code == 404
    ann.post(gurl(bid, "/review-unchanged"))
    assert not next(e for e in S.read(world.plane("co-a"), bid)["entries"] if e["kpi_id"] == "kpi-5").get("reviewed")


# ---- downloads equal the view; hostile text is escaped

def test_the_downloads_say_what_the_screen_says(world, stub):
    bid, c = seed(world), login(world, "co-a")
    v = upload(c, bid).json()
    book = read_book(c.get(gurl(bid, "/export")).content)
    assert list(book) == ["Business glossary", "Changes"]
    cells = book["Business glossary"]["cells"]
    sheet = [[cells.get(f"{col}{n}", "") for col in "ABCDEFGHIJK"] for n in range(5, 5 + len(v["entries"]))]
    assert [r[0] for r in sheet] == [e["text"]["term"] for e in v["entries"]]
    assert [r[2] for r in sheet] == [e["text"]["definition"] for e in v["entries"]]
    assert [r[8] for r in sheet] == [e["text"]["change"] for e in v["entries"]]
    changes = book["Changes"]["cells"]
    assert [changes[f"{c}4"] for c in "ABCDEF"] == ["Term", "Change", "Previous (your glossary)", "New (this baseline)", "Assumption", "Decided by"]
    assert changes["A5"] == "Net asset value" and "net of fees" in changes["C5"] and "gross of fees" in changes["D5"] and changes["F5"] == "Not decided yet"
    assert "Vendor rating" in [changes.get(f"A{n}") for n in range(5, 12)] and "In your glossary only" in changes.values()
    html = c.get(gurl(bid, "/print")).content.decode()
    for e in v["entries"]:
        assert e["text"]["term"] in html and e["text"]["definition"].replace("&", "&amp;") in html.replace("&#x27;", "'")
    assert "attachment" in c.get(gurl(bid, "/export")).headers["content-disposition"]


def test_hostile_text_is_escaped_in_both_downloads(world):
    plane = world.plane("co-a")
    bid = seed(world, specs=[("<b>Net</b> asset", "=HYPERLINK(\"http://x\")", "no", [])])
    c = login(world, "co-a")
    c.post(gurl(bid, "/build"))
    html = c.get(gurl(bid, "/print")).content.decode()
    assert "<b>Net</b>" not in html and "&lt;b&gt;Net&lt;/b&gt; asset" in html
    zipped = zipfile.ZipFile(io.BytesIO(c.get(gurl(bid, "/export")).content))
    sheet = zipped.read("xl/worksheets/sheet1.xml").decode()
    assert "<b>Net</b>" not in sheet and "&lt;b&gt;Net&lt;/b&gt;" in sheet and "<f>" not in sheet
    assert f'<c r="C5" s="{E.X.BODY_TEXT}" t="inlineStr">' in sheet  # text that starts like a formula stays text
    hostile = upload(c, bid, "g.md", b"- <script>alert(1)</script>: =cmd|' /C calc'!A0\n").json()
    assert hostile["unmatched_terms"][0]["term"] == "<script>alert(1)</script>"
    assert "<script>" not in c.get(gurl(bid, "/print")).content.decode()
    assert b"<script>" not in zipfile.ZipFile(io.BytesIO(c.get(gurl(bid, "/export")).content)).read("xl/worksheets/sheet2.xml")
    assert plane  # the plane is this company's own


# ---- reading provided files

def test_the_glossary_downloaded_can_be_provided_again_as_excel(world, stub):
    bid, c = seed(world), login(world, "co-a")
    c.post(gurl(bid, "/build"))
    again = upload(c, bid, "ours.xlsx", c.get(gurl(bid, "/export")).content).json()
    assert again["counts"]["unchanged"] == 6 and again["unmatched_terms"] == []  # its own title and the Changes sheet are not read as terms


def test_word_markdown_and_text_files_are_read(world):
    bid, c = seed(world), login(world, "co-a")
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:p><w:t>Cash buffer: Cash held back for the next 90 days.</w:t></w:p>"
                                         "<w:p><w:t>Net asset value - Fund value net of fees.</w:t></w:p></w:document>")
    assert upload(c, bid, "g.docx", docx.getvalue()).json()["counts"]["unchanged"] == 1
    md = b"| Term | Definition |\n|---|---|\n| Cash buffer | Cash held back for the next 90 days. |\n"
    assert upload(c, bid, "g.md", md).json()["counts"]["unchanged"] == 1
    assert upload(c, bid, "g.txt", b"* **Cash buffer**: Cash held back for the next 90 days.\n").json()["counts"]["unchanged"] == 1
    assert upload(c, bid, "g.pdf", b"x").status_code == 422 and upload(c, bid, "g.csv", b"nothing useful here").status_code == 422
    assert upload(c, bid, "g.csv", b"").status_code == 422 and c.post(gurl(bid, "/upload"), json={"filename": "g.csv", "data": "***"}).status_code == 400
    terms, partial = G.parse_provided("## Sheet: A\nTerm | Definition\nX | one\n... (more rows)")
    assert terms[0]["term"] == "X" and partial is True


# ---- permissions, signed, other companies, industries

def test_a_signed_baseline_refuses_every_write_and_still_downloads(world, stub):
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    upload(c, bid)
    B.set_state(plane, bid, "signed")
    sent = len(stub.sent)
    for r in (c.post(gurl(bid, "/build")), upload(c, bid), c.put(gurl(bid, "/entries/kpi-0"), json={"choice": "ours"}),
              c.post(gurl(bid, "/entries/kpi-0/review")), c.post(gurl(bid, "/review-unchanged"))):
        assert r.status_code == 409 and r.json()["error"] == "signed"
    assert len(stub.sent) == sent
    assert c.get(gurl(bid)).json()["signed"] is True and c.get(gurl(bid, "/export")).status_code == 200 and c.get(gurl(bid, "/print")).status_code == 200


def test_roles_companies_and_switched_off_modules(world):
    bid = seed(world)
    for role in ("participant", "owner", "approver"):
        p = login(world, "co-a", f"Per {role}", (role,))
        assert p.get(gurl(bid)).status_code == 200 and p.post(gurl(bid, "/build")).status_code == 403 and p.get(gurl(bid, "/export")).status_code == 403
    other = login(world, "co-b")
    assert other.get(gurl(bid)).status_code == 404 and other.post(gurl(bid, "/build")).status_code == 404 and other.get(gurl(bid, "/export")).status_code == 404
    assert upload(other, bid).status_code == 404 and other.get(gurl(bid, "/print")).status_code == 404
    assert login(world, "co-off", "Off Admin").get(gurl(bid)).status_code in (403, 404)
    assert login(world, "co-a", "Admin Two").get(gurl("f" * 32)).status_code == 404
    assert login(world, "co-a", "Sam Sponsor", ("sponsor",)).post(gurl(bid, "/build")).status_code == 200
    assert login(world, "co-a", "Al Analyst", ("analyst",)).post(gurl(bid, "/build")).status_code == 200


@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none", "co-solo"])
def test_two_industries_no_pack_and_one_person_alone(world, company):
    bid, c = seed(world, company, SPECS[:3]), login(world, company)
    v = c.post(gurl(bid, "/build")).json()
    assert v["counts"]["all"] == 3 and len(c.get(gurl(bid, "/export")).content) > 500


def test_an_empty_company_has_an_honest_empty_glossary(world):
    plane = world.plane("co-a")
    base, _ = B.start(plane, None)
    c = login(world, "co-a")
    assert c.get(gurl(base["id"])).json()["built"] is False
    v = c.post(gurl(base["id"], "/build")).json()
    assert v["built"] is False and v["entries"] == [] and v["counts"]["all"] == 0
    assert S.glossary_ready(plane, base["id"]) == (False, ["The glossary has not been built yet."])
    assert c.get(gurl(base["id"], "/export")).status_code == 200 and b"Business glossary" in c.get(gurl(base["id"], "/print")).content


def test_the_glossary_is_versioned_with_the_baseline(world):
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    c.post(gurl(bid, "/build"))
    assert S.read(plane, bid)["baseline_version"] == 1
    assert (plane.path("intents", "m2_baseline", bid) / "glossary.json").exists()


# ---- fix round: undo a wrong match, long files, Lens may learn the glossary, the choice reaches the measure

def test_not_the_same_thing_undoes_the_match_and_a_rebuild_does_not_bring_it_back(world):
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    v = upload(c, bid).json()
    nav = entry(v, "Net asset value")
    c.put(gurl(bid, f"/entries/{nav['kpi_id']}"), json={"choice": "provided"})
    assert {a["kind"] for a in next(k for k in K.read_kpis(plane, bid) if k["id"] == nav["kpi_id"])["ambiguities"]} == {"calculation", "currency"}
    v = c.put(gurl(bid, f"/entries/{nav['kpi_id']}"), json={"choice": "not_same"}).json()
    e = entry(v, "Net asset value")
    assert e["change"] == "new" and e["previous"]["mark"] == "unknown" and e["reviewed"] is None and "decided" not in e and "matched_term" not in e
    assert "Net asset value" in [t["term"] for t in v["unmatched_terms"]]
    assert not next(k for k in K.read_kpis(plane, bid) if k["id"] == nav["kpi_id"]).get("ambiguities")
    for again in (c.post(gurl(bid, "/build")).json(), upload(c, bid).json()):
        assert entry(again, "Net asset value")["change"] == "new" and "Net asset value" in [t["term"] for t in again["unmatched_terms"]]
    assert c.put(gurl(bid, f"/entries/{entry(v, 'Cash buffer')['kpi_id']}"), json={"choice": "not_same"}).status_code == 200
    assert c.put(gurl(bid, "/entries/kpi-1"), json={"choice": "not_same"}).status_code == 404  # nothing matched there any more


def test_a_long_excel_glossary_is_read_beyond_forty_rows_and_a_cap_is_said_plainly(world, monkeypatch):
    bid, c = seed(world), login(world, "co-a")
    rows = [{k: "" for k in (*E.MAIN_KEYS, "previous", "assumption", "decided_by", "definition")} | {"term": f"Term {i}", "definition": f"Wording {i}.", "change": "New"} for i in range(120)]
    v = upload(c, bid, "long.xlsx", E.build_xlsx("Co", rows, [])).json()
    assert len(v["unmatched_terms"]) == 120 and "note" not in v
    monkeypatch.setattr(G, "MAX_TERMS", 3)
    v = upload(c, bid, "long.md", b"".join(f"- Term {i}: Wording {i}.\n".encode() for i in range(6))).json()
    assert len(v["unmatched_terms"]) == 3 and "first 3 terms" in v["note"]


def test_lens_can_learn_from_the_provided_glossary_until_the_organiser_restricts_it(world):
    from modules.m2_baseline.agent import lens
    bid, c, plane = seed(world), login(world, "co-a"), world.plane("co-a")
    upload(c, bid)
    text, titles = lens.preread(plane, "Funding calls due capital calls")
    assert "Funding calls due" in text and titles == ["glossary.csv"]
    open_doc = next(d for d in DocStore(plane).documents("lens") if d["description"] == "Business glossary")
    DocStore(plane).set_restricted("lens", open_doc["doc_id"], True)
    assert lens.preread(plane, "Funding calls due capital calls") == ("", [])


def test_a_chosen_wording_reaches_the_measure_so_every_screen_agrees(world, stub):
    bid, c, plane = seed(world), login(world, "co-a", "Mei Reviewer"), world.plane("co-a")
    upload(c, bid)
    nav = next(k for k in K.read_kpis(plane, bid) if k["name"] == "Net asset value")
    K.change(plane, bid, nav["id"], lambda k: {**k, "definition": prov("A guess.", "guessed", "Lens", "the pack")})
    c.post(gurl(bid, "/build"))
    v = c.put(gurl(bid, f"/entries/{nav['id']}"), json={"choice": "provided"}).json()
    want = entry(v, "Net asset value")["business_definition"]["value"]
    k = next(k for k in c.get(f"{BASE}/baselines/{bid}").json()["kpis"] if k["id"] == nav["id"])
    assert k["definition"]["value"] == want and k["definition"]["mark"] == "stated" and k["definition"]["by"] == "Test Mei Reviewer"
    c.post(f"{BASE}/baselines/{bid}/catalogue/refresh")
    cat = c.get(f"{BASE}/baselines/{bid}/catalogue").json()
    row = next(r for r in cat["kpis"] if r.get("KPI name", {}).get("value") == "Net asset value")
    assert row["Definition"]["value"] == want
    # a definition a person already stated is never replaced: the chosen wording sits beside it as a proposal
    c.put(gurl(bid, f"/entries/{nav['id']}"), json={"choice": "edited", "text": "Fund value, net, in SGD."})
    k = next(k for k in K.read_kpis(plane, bid) if k["id"] == nav["id"])
    assert k["definition"]["value"] == want and k["definition_proposal"]["value"] == "Fund value, net, in SGD." and k["definition_proposal"]["by"] == "Test Mei Reviewer"


# ---- the provided glossary is split by restriction before Lens may read it

PAY_CSV = (b"Term,Definition,Aliases,Owner,Frequency\n"
           b"Executive team size,How many people sit in the executive team.,,,\n"
           b"Executive pay,Total pay of the executive team including bonus.,,,\n"
           b"CEO compensation,What the chief executive is paid in total.,,,\n")
SPLIT_SPECS = [("Executive team size", "", "no", []), ("Executive pay", "", "yes", ["Test Pat Boss"]), ("Cash buffer", "", "no", [])]
PAY_WORDS = ("bonus", "chief executive", "paid in total")


def retrievable(plane, restricted: bool) -> str:
    from modules.m2_baseline.agent import lens
    return " ".join(c["text"] for c in lens._WithRestricted(plane).own_chunks("lens") if c["restricted"] is restricted)


def drafted_prompt(world, stub, who, kpi_name, bid):
    c = login(world, "co-a", who[0], who[1])
    kid = next(k["id"] for k in K.read_kpis(world.plane("co-a"), bid) if k["name"] == kpi_name)
    c.post(f"{BASE}/baselines/{bid}/lens/draft", json={"kpi_ids": [kid]})
    return " ".join(str(m) for turn in stub.sent for m in turn)


def test_restricted_wording_is_not_retrievable_but_the_rest_is(world, stub):
    bid, plane = seed(world, specs=SPLIT_SPECS), world.plane("co-a")
    upload(login(world, "co-a"), bid, "g.csv", PAY_CSV)
    open_text, restricted_text = retrievable(plane, False), retrievable(plane, True)
    assert "How many people sit in the executive team" in open_text and not any(w in open_text for w in PAY_WORDS)
    assert restricted_text == "" and not any(w in open_text + restricted_text for w in PAY_WORDS)  # no company document holds the pay row or the unmatched term
    assert [d["description"] for d in DocStore(plane).documents("lens")] == ["Business glossary"]
    assert "paid in total" in str(S.read(plane, bid)["unmatched_terms"])  # it stays in the glossary itself
    note = login(world, "co-a", "Org Two").get(gurl(bid)).json()
    assert note["restricted_kept"] == 2
    assert login(world, "co-a", "Ann Analyst", ("analyst",)).get(gurl(bid)).json()["restricted_kept"] == 0  # no count for those who may not see it


def test_a_draft_of_a_visible_measure_never_carries_pay_wording_to_the_model(world, stub):
    bid = seed(world, specs=SPLIT_SPECS)
    upload(login(world, "co-a"), bid, "g.csv", PAY_CSV)
    stub.sent.clear()
    stub.reply = "Counts the people in the executive team."
    sent = drafted_prompt(world, stub, ("Ann Analyst", ("analyst",)), "Executive team size", bid)
    assert "How many people sit in the executive team" in sent  # Lens did learn from the glossary
    assert not any(w in sent for w in PAY_WORDS)


def test_a_person_on_the_pay_list_sees_the_provided_wording_in_the_glossary_but_lens_is_not_given_it(world, stub):
    bid = seed(world, specs=SPLIT_SPECS)
    upload(login(world, "co-a"), bid, "g.csv", PAY_CSV)
    stub.sent.clear()
    sent = drafted_prompt(world, stub, ("Pat Boss", ("analyst",)), "Executive pay", bid)
    assert not any(w in sent for w in PAY_WORDS)
    admin = login(world, "co-a", "Org Four").get(gurl(bid)).json()
    assert "including bonus" in entry(admin, "Executive pay")["text"]["previous"]  # people who may see the measure review it here


def test_with_no_restricted_measure_everything_is_retrievable(world, stub):
    bid, plane = seed(world, specs=[s for s in SPLIT_SPECS if s[2] == "no"]), world.plane("co-a")
    upload(login(world, "co-a"), bid, "g.csv", PAY_CSV)
    assert all(w in retrievable(plane, False) for w in ("including bonus", "paid in total")) and retrievable(plane, True) == ""
    assert [d["description"] for d in DocStore(plane).documents("lens")] == ["Business glossary"]
    assert login(world, "co-a", "Org Three").get(gurl(bid)).json()["restricted_kept"] == 0


def test_a_change_of_governance_moves_the_wording_at_the_next_rebuild_both_ways(world, stub):
    bid, plane, c = seed(world, specs=SPLIT_SPECS), world.plane("co-a"), login(world, "co-a")
    upload(c, bid, "g.csv", PAY_CSV)
    ids = {k["name"]: k["id"] for k in K.read_kpis(plane, bid)}
    set_personal = lambda name, value: K.change(plane, bid, ids[name], lambda k: {**k, "governance": {**k["governance"], "personal": value}})  # noqa: E731
    set_personal("Executive pay", "no")  # relaxed
    c.post(gurl(bid, "/build"))
    assert "including bonus" in retrievable(plane, False) and "paid in total" in retrievable(plane, False)
    assert [d["description"] for d in DocStore(plane).documents("lens")] == ["Business glossary"]
    set_personal("Executive team size", "yes")  # now restricted
    c.post(gurl(bid, "/build"))
    assert "How many people sit in the executive team" not in retrievable(plane, False)
    assert retrievable(plane, True) == "" and "paid in total" not in retrievable(plane, False)  # nothing restricted is ever stored as a document


def test_a_chosen_wording_never_replaces_a_definition_a_person_stated():
    mine = prov("Our own words.", "stated", "Pat Owner", "the work list")
    k = {"definition": mine, "definition_proposal": None}
    out = G.with_chosen_definition(k, "Other words.", "Mei")
    assert out["definition"] == mine and out["definition_proposal"]["value"] == "Other words." and out["definition_proposal"]["by"] == "Mei"
    guessed_by_person = {"definition": prov("A guess.", "guessed", "Pat Owner", "meeting")}
    assert G.with_chosen_definition(guessed_by_person, "Other words.", "Mei")["definition"]["value"] == "A guess."
    by_lens = {"definition": prov("A draft.", "guessed", "Lens", "the pack")}
    assert G.with_chosen_definition(by_lens, "Other words.", "Mei")["definition"]["by"] == "Mei"
    assert G.with_chosen_definition({"definition": prov(None, "unknown", "Lens")}, "Other words.", "Mei")["definition"]["value"] == "Other words."
    assert G.with_chosen_definition(k, "our own words", "Mei") is k  # the same wording changes nothing


def test_a_document_that_cannot_be_deleted_is_closed_first_and_retried(world, monkeypatch):
    bid, plane, c = seed(world, specs=SPLIT_SPECS), world.plane("co-a"), login(world, "co-a")
    upload(c, bid, "g.csv", PAY_CSV)
    old = S.read(plane, bid)["documents"][0]

    def boom(self, agent, doc_id):
        raise OSError("disk")
    monkeypatch.setattr(DocStore, "delete", boom)
    c.post(gurl(bid, "/build"))
    assert S.read(plane, bid)["documents"][0] == old and len(S.read(plane, bid)["documents"]) == 2  # the old id is not forgotten
    store = DocStore(plane)
    assert store.get("lens", old)["restricted"] is True  # closed before the delete was tried
    monkeypatch.undo()
    c.post(gurl(bid, "/build"))
    assert old not in S.read(plane, bid)["documents"] and [d["doc_id"] for d in store.documents("lens")] == S.read(plane, bid)["documents"]
