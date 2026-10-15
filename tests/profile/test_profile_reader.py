"""Lens reads each input group into the profile: synthetic fixtures, the demo workspace when present, readiness, the asks, and the egress rule
(no row and no figure goes to the model)."""
from pathlib import Path

import pytest

from pf_kit import CONSTRAINTS, GOV, PACK, PEOPLE, ROOT, SAMPLE, SYSTEMS, xlsx
from sh_platform.context_docs.store import DocStore
from sh_platform.profile import Viewer, asks, read, reader, store

ADMIN = Viewer("Mei Tan", frozenset({"company_admin"}))


def up(plane, gid, name, data, model=None, **kw):
    return reader.add_upload(plane, gid, "Mei Tan", name, data, model, **kw)


def p(plane):
    return read(plane, ADMIN)


def test_people_list_fills_people_with_the_document_as_source(plane, stub):
    out = up(plane, 1, "people.csv", PEOPLE, stub)
    assert out["state"] == "read"
    people = p(plane)["people"]
    assert set(people) == {"mei-tan", "sue-sponsor", "dan-data"}
    assert people["sue-sponsor"]["is_sponsor"]["value"] is True and people["dan-data"]["is_head_of_data"]["value"] is True
    assert people["mei-tan"]["is_organiser"]["value"] is True and people["dan-data"]["manager"]["value"] == "Mei Tan"
    c = people["dan-data"]["email"]
    assert c["by"] == "Lens" and c["mark"] == "stated" and c["agent"] == "lens" and c["from"] == "people.csv" and c["ref"]["kind"] == "document" and len(c["ref"]["id"]) == 12
    assert stub.sent == []  # a list is read on this machine


def test_systems_list_fills_systems(plane, stub):
    assert up(plane, 6, "systems.csv", SYSTEMS, stub)["state"] == "read"
    s = p(plane)["systems"]["custody-feed"]
    assert s["owner"]["value"] == "Dan Data" and s["lands"]["value"] == "daily file" and s["frequency"]["value"] == "daily"
    assert "licence" not in p(plane)["systems"]["performance-workbook"]


def test_access_list_fills_governance(plane, stub):
    assert up(plane, 7, "access.csv", GOV, stub)["state"] == "read"
    g = p(plane)["governance"]
    assert g["restricted_areas"]["hr"]["area"]["value"] == "HR"
    pay = g["field_rules"]["pay"]
    assert pay["personal"]["value"] == "yes" and pay["sensitive"]["value"] is True and pay["may_see"]["value"] == ["Mei Tan"]
    assert g["field_rules"]["capital-called"]["personal"]["value"] == "no"


def test_a_reported_figure_keeps_its_document_and_page(plane, stub):
    assert up(plane, 3, "monthly_pack.csv", PACK, stub)["state"] == "read"
    f = p(plane)["reported_figures"]["single-issuer-concentration@2026-09-30"]
    assert f["figure"]["value"] == 13.32 and f["unit"]["value"] == "%" and f["period_end"]["value"] == "2026-09-30"
    assert f["figure"]["from"] == "Investment committee pack, page 4" and f["figure"]["ref"]["page"] == "page 4"


def test_an_excel_pack_names_the_sheet(plane, stub):
    up(plane, 3, "pack.xlsx", xlsx([["Measure", "Figure", "Unit"], ["Private-market allocation", 24.36, "%"]]), stub)
    f = next(iter(p(plane)["reported_figures"].values()))
    assert f["figure"]["value"] == 24.36 and f["figure"]["from"] == "pack.xlsx, sheet 1" and f["figure"]["ref"]["page"] == "sheet 1"


def test_a_word_or_pdf_pack_gives_figures_by_pattern_with_the_page():
    recs = reader._pack_lines([{"text": "Committee pack\nSingle-issuer concentration: 6.8%\nNarrative about markets.", "location": "page 3"},
                               {"text": "Known obligations due | 2,985,000 | SGD", "location": "page 6"}])
    got = {r[0].split(".")[1]: (r[1], r[3]) for r in recs if r[0].endswith(".figure")}
    assert got == {"single-issuer-concentration@page-3": (6.8, "page 3"), "known-obligations-due@page-6": (2985000, "page 6")}


def test_a_pack_in_a_form_with_no_figures_is_partly_read_with_the_reason(plane, stub):
    out = up(plane, 3, "pack.md", b"A narrative pack with no figures in it at all.", stub)
    assert out["state"] == "partly" and "no figures" in out["reason"]


def test_constraints_list_and_samples(plane, stub):
    assert up(plane, 9, "limits.csv", CONSTRAINTS, stub)["state"] == "read"
    assert p(plane)["constraints"]["licence-1"]["text"]["value"].startswith("Market data")
    assert up(plane, 8, "custody.csv", SAMPLE, stub, system="Custody feed")["state"] == "read"
    s = p(plane)["samples"]["custody-csv"]
    assert s["summary"]["value"] == {"rows": 2, "columns": ["Val Date", "Acct", "Mkt Value"]} and s["system"]["value"] == "Custody feed"
    with pytest.raises(Exception):
        up(plane, 8, "notes.md", b"free text", stub)  # a sample must be a table


def test_free_documents_go_to_lens_as_masked_passages_and_the_answer_is_a_guess(plane, stub):
    stub.text = "licence: Market data may not leave the office."
    body = (b"Data licences. The market data licence from Acme Index limits storage of prices to the office. Ask Jane Doe about renewals. "
            b"Internet access is switched off for the office network. Revenue was 4,512,300 last year.\n")
    out = up(plane, 9, "limits.md", body, stub)
    assert out["state"] == "read" and len(stub.sent) == 1
    sent = stub.everything
    assert "BEGIN QUOTED DOCUMENT TEXT" in sent and "Jane Doe" not in sent and "4,512,300" not in sent
    c = p(plane)["constraints"]["licence-1"]["text"]
    assert c["mark"] == "guessed" and c["by"] == "Lens"


def test_no_model_means_attached_and_partly_read(plane):
    out = up(plane, 2, "policy.md", b"Our investment policy sets the purpose of the office clearly and in plain words for all.", None)
    assert out["state"] == "partly" and "Press Read again" in out["reason"]


def test_a_model_that_fails_leaves_the_file_attached_and_never_raises(plane):
    class Down:
        def complete(self, *a, **k):
            raise RuntimeError("provider down")
    out = up(plane, 2, "policy.md", b"Our investment policy sets the purpose of the office clearly and in plain words for all.", Down())
    assert out["state"] == "partly"


def test_no_row_and_no_figure_goes_to_the_model(plane, stub):
    stub.text = "A sentence about the document."
    up(plane, 1, "people.csv", PEOPLE, stub)
    up(plane, 3, "pack.csv", PACK, stub)
    up(plane, 8, "custody.csv", SAMPLE, stub)
    up(plane, 7, "access.csv", GOV, stub)
    up(plane, 2, "policy.md", b"Our investment policy sets the purpose of the office clearly. Target growth is 7.5% a year. Sam Lee signs it.", stub)
    sent = stub.everything
    for secret in ("13.32", "A2", "250", "mei@example.test", "Dan Data", "Sam Lee", "7.5%", "Pay"):
        assert secret not in sent, secret
    assert len(stub.sent) == 1  # only the one free document was read by the model


def test_a_restricted_document_is_left_unread(plane, stub):
    out = up(plane, 2, "pay_policy.md", b"Pay bands for the whole office are described in this restricted document in detail.", stub, restricted=True)
    assert out["state"] == "missing" and "Not available yet" in out["reason"] and stub.sent == []


def test_held_documents_and_every_summary_stay_out_of_the_passages(plane, stub):
    """The profile reader drops other agents' shared summaries and the summary of any held document (restricted or held back)."""
    docs = DocStore(plane)
    held = docs.upload("lens", "Mei Tan", "held.md", b"Budget policy limits for the office are described here: SECRETHELDTEXT is the rule.", title="held")
    docs.publish_summary("lens", held["doc_id"], "SUMMARYOFHELD budget policy limits")
    restricted = docs.upload("lens", "Mei Tan", "r.md", b"Budget policy limits for restricted pay review in detail here.", title="r", restricted=True)
    docs.publish_summary("lens", restricted["doc_id"], "SUMMARYOFRESTRICTED budget policy limits")
    north = docs.upload("north", "Mei Tan", "n.md", b"Budget policy limits for another agent shelf in detail here.", title="n", visibility="shared")
    docs.publish_summary("north", north["doc_id"], "SUMMARYOFNORTH budget policy limits")
    ok = docs.upload("lens", "Mei Tan", "ok.md", b"Budget policy limits are set by the board each year in plain words.", title="ok")
    hits = reader.passages(plane, 2, [ok["doc_id"]])
    assert hits and all("SUMMARYOF" not in h["text"] and "SECRETHELD" not in h["text"] for h in hits)
    assert reader.passages(plane, 2, [restricted["doc_id"]]) == []  # restricted: closed, text and summary
    assert reader.passages(plane, 2, [north["doc_id"]]) == []  # another agent's shared summary is never read here


def test_a_held_attachment_is_not_sent_even_with_a_published_summary(plane, stub):
    stub.text = "a sentence"
    att = reader.attach(plane, 2, "Mei Tan", "budget.md", b"Budget policy limits are set by the board each year in plain words for all.")
    store.mutate(plane, lambda d: store.set_cell(d, "inputs.g2.documents", [att], {"mark": "stated", "by": "Mei Tan", "from": "Mei Tan", "ref": {"kind": "person", "id": "mei-tan"}}))
    DocStore(plane).publish_summary("lens", att["doc_id"], "SUMMARYOFHELD budget policy")
    out = reader.read_group(plane, 2, stub, held=[att["doc_id"]])
    assert out["state"] == "missing" and stub.sent == []
    out = reader.read_group(plane, 2, stub)  # released: now it is read, and still only its own passages go
    assert out["state"] == "read" and "SUMMARYOFHELD" not in stub.everything


def test_a_reread_replaces_drafts_but_keeps_a_persons_edit(plane, stub):
    up(plane, 1, "people.csv", PEOPLE, stub)
    store.mutate(plane, lambda d: store.set_cell(d, "people.dan-data.role", "Chief data officer",
                                                 {"mark": "stated", "by": "Dan Data", "from": "Interview with Dan Data", "ref": {"kind": "interview", "id": "q13"}}))
    reader.read_all(plane, stub)
    role = p(plane)["people"]["dan-data"]["role"]
    assert role["value"] == "Chief data officer" and role["by"] == "Dan Data"
    assert len(p(plane)["people"]) == 3


# ---- readiness and asks ---------------------------------------------------------------------------------------------------

def test_readiness_follows_the_documented_formula(plane, stub):
    r = reader.readiness(plane)
    assert r["percent"] == 0 and [g["state"] for g in r["groups"]] == ["missing"] * 9 and len(r["groups"]) == 9
    for gid, name, data in ((1, "p.csv", PEOPLE), (3, "k.csv", PACK), (6, "s.csv", SYSTEMS)):
        up(plane, gid, name, data, stub)
    up(plane, 7, "a.md", b"Some free text about access, but not a list that Lens can read as one at all.", None)  # partly: prose in group 7 is read by the model, and none is available
    r = reader.readiness(plane)
    # weights: 6 required groups x2 + 3 helpful x1 = 15; score = 3 read x2 + 1 partly x2 x0.5 = 7 -> 46.7% -> nearest 5 = 45
    assert r["percent"] == 45 and r["sentence"] == "Lens can draft about 45% of the baseline." and r["read"] == 3
    assert next(g for g in r["groups"] if g["id"] == 7)["state"] == "partly"


def test_nira_asks_the_named_holder_for_each_missing_required_group(plane, stub):
    up(plane, 1, "people.csv", PEOPLE, stub)
    todo = {a["group"]: a for a in asks.missing(plane, "Mei Tan")}
    assert set(todo) == {2, 3, 6, 7, 8}  # the required groups still missing; helpful ones are not chased
    assert todo[2]["holder"]["name"] == "Sue Sponsor" and todo[3]["holder"]["name"] == "Mei Tan"  # a key role counts as a role
    assert todo[6]["holder"]["name"] == "Dan Data" and todo[7]["holder"]["name"] == "Dan Data"
    mail = todo[3]["email"]
    assert "Mei Tan" in mail["body"] and "reporting today" in mail["subject"].lower() and "{link}" in mail["body"]
    assert "13.32" not in mail["body"]  # names and titles only


def test_no_people_list_means_the_ask_has_no_named_holder(plane):
    todo = asks.missing(plane)
    assert len(todo) == 6 and all(a["holder"] is None for a in todo) and todo[0]["group"] == 1


def test_the_link_token_is_hashed_expires_and_is_for_one_group(plane):
    from datetime import datetime, timedelta, timezone
    token = asks.mint(plane, 3)
    assert asks.TOKEN.fullmatch(token) and asks.check(plane, token) == 3
    assert token not in plane.path("context", "profile", "asks.json").read_text(encoding="utf-8")  # only its hash is kept
    assert asks.check(plane, token, datetime.now(timezone.utc) + timedelta(hours=337)) is None
    assert asks.check(plane, "pf-" + "0" * 32 + "-" + "A" * 43) is None and asks.check(plane, "garbage") is None


# ---- the demo workspace, when it is on this machine (gitignored; skipped otherwise) ---------------------------------------------

def _demo() -> Path | None:
    for base in (ROOT / "local", ROOT.parents[2] / "local"):
        d = next((x for x in sorted(base.glob("*")) if (x / "01-people").is_dir() and (x / "09-constraints").is_dir()), None) if base.is_dir() else None
        if d:
            return d
    return None


@pytest.mark.skipif(_demo() is None, reason="the local demo workspace is not on this machine")
def test_the_demo_workspace_is_read_group_by_group(plane, stub):
    d = _demo()
    stub.text = "licence: Market data may not be stored or shared until a licence is signed."
    for folder in sorted(x for x in d.iterdir() if x.is_dir() and x.name[:2].isdigit()):
        for f in sorted(x for x in folder.rglob("*") if x.is_file()):
            out = up(plane, int(folder.name[:2]), f.name, f.read_bytes(), stub, restricted="RESTRICTED" in f.name)
            assert out["state"] in ("read", "partly", "missing"), f.name
    got = {g["id"]: g for g in reader.readiness(plane)["groups"]}
    assert all(got[i]["state"] != "missing" for i in range(1, 10)), {i: got[i]["reason"] for i in got}
    prof = p(plane)
    raw = store.raw(plane)["governance"]["field_rules"]  # A-069: a rule with names on it is a silhouette to the admin; the listed people see it
    listed = {n for r in raw.values() for n in ((r.get("may_see") or {}).get("value") or [])}
    seen = {k for n in listed for k in read(plane, Viewer(n, frozenset({"analyst"})))["governance"]["field_rules"]}
    named = {k for k, r in raw.items() if (r.get("may_see") or {}).get("value")}
    assert len(seen) >= 5 and not (named & set(prof["governance"]["field_rules"]))
    assert len(prof["people"]) >= 10 and any(x["is_sponsor"]["value"] is True for x in prof["people"].values() if "is_sponsor" in x)
    assert len(prof["systems"]) >= 8 
    figs = prof["reported_figures"]
    assert len(figs) >= 30 and all(str(f["figure"]["ref"].get("page", "")).startswith("page") for f in figs.values())
    assert any("payroll" in a["name"].lower() and a["restricted"] for a in prof["inputs"]["g5"]["documents"]["value"])
    assert any(r["result"] == "held" for r in prof["inputs"]["g5"]["results"]["value"])  # the restricted SOP is left unread
    sent = stub.everything
    assert "@example.test" not in sent and "payroll" not in sent.lower()  # no email, no restricted passage reached the model


# ---- LI-MULTI: a strategy document that shares no word with the search is still read; one with nothing to quote is context ----

FOUR_MD = {"current_priorities.md": b"# Current priorities\n\n- Finish the reporting rebuild this year\n- Reduce manual work in the month end\n",
           "investment_committee_charter.md": b"# Charter\n\nThe committee meets quarterly. It approves the investment policy for the office.\n",
           "investment_policy_summary.md": b"# Policy summary\n\nThe purpose of the policy is to preserve capital and grow it steadily over time.\n",
           "known_issues.md": b"# Known issues\n\n- The custody feed arrives late on Mondays\n- Two spreadsheets disagree about the same fund\n"}


def test_four_markdown_documents_of_group_two_are_all_read(plane, stub):
    stub.text = "The office keeps a policy and a list of priorities."
    for name, body in FOUR_MD.items():
        out = up(plane, 2, name, body, stub)
    assert out["state"] == "read" and out["reason"] == "Read 4 files."
    assert [r["result"] for r in out["results"]] == ["read"] * 4
    assert reader.read_all(plane, stub)[0]["state"] == "read"  # Read again changes nothing


def test_a_document_with_nothing_to_quote_is_context_not_stuck_at_partly(plane, stub):
    out = up(plane, 2, "targets.md", b"# Targets\n\nGrowth is 7.5% a year. Spend is 4,512,300 a year. Tolerance is 2% a quarter.\n", stub)
    assert out["results"][0]["result"] == "context" and stub.sent == []
    assert out["state"] == "read"
    assert out["reason"] == "Read 1 file. It is used as context; nothing to fill in the profile."
    assert reader.read_all(plane, stub)[0]["state"] == "read"


def test_context_documents_are_counted_in_the_sentence(plane, stub):
    stub.text = "A policy."
    up(plane, 2, "policy.md", FOUR_MD["investment_policy_summary.md"], stub)
    out = up(plane, 2, "targets.md", b"Growth is 7.5% a year. Spend is 4,512,300 a year. Tolerance is 2% a quarter.\n", stub)
    assert out["state"] == "read" and out["reason"] == "Read 2 files. 1 is used as context; nothing to fill in the profile."


def test_no_model_still_means_partly_and_a_restricted_one_stays_unread(plane, stub):
    assert up(plane, 2, "a.md", FOUR_MD["known_issues.md"], None)["state"] == "partly"
    out = up(plane, 2, "pay.md", FOUR_MD["known_issues.md"], stub, restricted=True)
    assert [r["result"] for r in out["results"]] == ["read", "held"] and len(stub.sent) == 1  # the restricted one was never sent


def test_group_reason_summarizes_all_files(plane, stub):
    """Group reason summarizes counts of read files and files that gave nothing."""
    for i in range(3):
        up(plane, 3, f"pack{i}.csv", PACK, stub)
    for i in range(3):
        up(plane, 3, f"note{i}.md", b"Commentary with no figures.", stub)
    readiness_groups = reader.readiness(plane)["groups"]
    group3 = next(g for g in readiness_groups if g["id"] == 3)
    assert group3["state"] == "read"
    assert group3["reason"] == "Read 3 files; 3 gave nothing new."

def test_group_all_files_gave_nothing_preserves_reason(plane, stub):
    """When all files gave nothing, reason includes per-file guidance."""
    for i in range(3):
        up(plane, 3, f"note{i}.md", b"Just text, no figures.", stub)
    readiness_groups = reader.readiness(plane)["groups"]
    group3 = next(g for g in readiness_groups if g["id"] == 3)
    assert group3["state"] == "partly"
    assert group3["reason"] == "Lens found no figures it could read in this pack."

def test_group_with_restricted_file(plane, stub):
    """Group reason mentions restricted files left unread alongside count."""
    up(plane, 3, "restricted.csv", PACK, stub, restricted=True)
    up(plane, 3, "normal.csv", PACK, stub)
    readiness_groups = reader.readiness(plane)["groups"]
    group3 = next(g for g in readiness_groups if g["id"] == 3)
    assert group3["state"] == "read"
    assert group3["reason"] == "Read 1 file; 1 left unread."
