"""M3-P04, the rules without a server: the plan drafted from a fixture shaped like the demo answer key
(packs/family_office/1/demo_module3/README.md), the band rules, a human edit surviving a re-draft, signing and the outcome record.
Fixtures stand in for P01's sources.json and P03's findings.json (read only through inputs_for_plan)."""
import json

import pytest

from modules.m3_connect.agent import plan_lens
from modules.m3_connect.domain import accept as X
from modules.m3_connect.domain import plan as P
from modules.m3_connect.domain.plan import PlanError

NOW = "2026-10-04T10:00:00+00:00"


def src(id_, name, effort, impact=0.5, marks=(), owners=(("Dana Reyes", "data owner", "Operations"),)):
    return {"id": id_, "name": name, "kind": "spreadsheet", "effort": effort, "impact": {"score": impact, "reasons": []}, "marks": list(marks),
            "owners": [{"name": n, "role": r, "team": t} for n, r, t in owners]}


def find(mid, group, sources, reasons=(), pain=(), levers=()):
    return {"measure_id": mid, "group": group, "reasons": list(reasons), "pain_points": list(pain), "levers": list(levers), "sources": list(sources)}


# The demo answer key: K10, K09, K04 match; K12 and K15 have gaps; K16 cannot be worked out; K18 is restricted with no source.
SOURCES = [src("S1", "Performance workbook", "small", owners=(("Dana Reyes", "data owner", "Investment Operations"),)),
           src("S2", "Northgate custody file", "medium", marks=["no_sample"], owners=(("Omar Lee", "data owner", "Custody Operations"),)),
           src("S3", "Capital-calls mailbox", "small", owners=(("Priya Nair", "data owner", "Treasury"),)),
           src("S4", "Index provider feed", "large", impact=-0.4, marks=["blocked_upstream"]),
           src("S5", "Exposure workbook", "medium", owners=(("Dana Reyes", "data owner", "Investment Operations"),)),
           src("S6", "Fees feed", "medium", marks=["licence"], owners=(("Priya Nair", "data owner", "Treasury"),))]
FINDINGS = [find("K10", "ready", ["S1"], pain=["p1"]), find("K09", "ready", ["S5"], pain=["p2"]), find("K04", "ready", ["S3"], pain=["p1"]),
            find("K12", "unclear", ["S2"], ["Data stops on 22 Sep; the pack's period ends 30 Sep."], pain=["p2"]),
            find("K15", "unclear", ["S1"], ["The pack leaves fees out."], pain=["p1"]),
            find("K16", "unknown", ["S4"], ["Index levels missing from 23 to 30 Sep."]),
            find("K14", "unknown", ["S6"], ["No fee figures yet."]),
            find("K18", "unknown", [], ["No pay review file."])]
RISKS = [{"id": "R1", "kind": "ambiguity", "text": "Is the pack's period end 30 Sep?", "measures": ["K12"], "pain_points": ["p2"], "decision": None},
         {"id": "R2", "kind": "unknown", "text": "Compensation has no source.", "measures": ["K18"], "pain_points": [], "decision": None},
         {"id": "R3", "kind": "risk", "text": "Half the fee cells are empty.", "measures": ["K15"], "pain_points": [], "decision": None}]


def folder(tmp_path, findings=FINDINGS, sources=SOURCES, risks=RISKS):
    d = tmp_path / "assessments" / ("a" * 32)
    d.mkdir(parents=True)
    (d / "findings.json").write_text(json.dumps({"findings": findings, "risks": risks}))
    (d / "sources.json").write_text(json.dumps({"sources": sources}))
    return d


def drafted(d, restricted=("K18",), decided=()):
    inputs = P.inputs_for_plan(d)
    return inputs, P.draft(inputs, set(restricted), {r["id"]: "accepted" for r in inputs["risks"] if r["id"] in decided})


def by_band(items, band):
    return [i for i in items if i["band"] == band]


def test_inputs_for_plan_reads_both_files_in_one_place_and_says_when_findings_are_missing(tmp_path):
    d = folder(tmp_path)
    got = P.inputs_for_plan(d)
    assert got["ready"] and len(got["findings"]) == 8 and len(got["risks"]) == 3 and set(got["sources"]) == {"S1", "S2", "S3", "S4", "S5", "S6"}
    assert P.inputs_for_plan(tmp_path / "nothing-here") == {"ready": False, "findings": [], "risks": [], "sources": {}, "left_out": []}
    (d / "sources.json").write_text("not json")
    with pytest.raises(PlanError) as e:
        P.inputs_for_plan(d)
    assert e.value.code == "unreadable" and "/" not in e.value.message


def test_the_demo_answer_key_drafts_three_bands(tmp_path):
    inputs, items = drafted(folder(tmp_path))
    now, nxt, later = (by_band(items, b) for b in ("now", "next", "later"))
    assert sorted(m for i in now for m in i["measures"]) == ["K04", "K09", "K10"]  # the three that match
    assert {i["key"] for i in nxt} == {"next:S2", "next:S1", "next:S6"}            # K12, K15 unclear; K14 unknown with a known source
    assert sorted(m for i in later for m in i["measures"]) == ["K16", "K18"]       # low-impact source; no source and restricted
    k10 = next(i for i in now if i["measures"] == ["K10"])
    assert k10["pain_points"] == ["p1"] and k10["effort"] == "small" and k10["team"] == ["Investment Operations"]
    assert next(i for i in now if i["measures"] == ["K09"])["effort"] == "medium"
    assert [i["band"] for i in items] == sorted((i["band"] for i in items), key=["now", "next", "later"].index)


def test_now_items_have_effort_team_and_pain_points_next_items_a_blocker_and_who_unblocks(tmp_path):
    _, items = drafted(folder(tmp_path))
    k12 = next(i for i in items if i["measures"] == ["K12"])
    assert k12["blocked_by"][0] == "No sample data has arrived yet" and "Is the pack's period end 30 Sep?" in k12["blocked_by"]
    assert k12["who_unblocks"] == ["Omar Lee (data owner)"] and k12["date"] is None and k12["team"] == ["Custody Operations"]
    k14 = next(i for i in items if i["measures"] == ["K14"])
    assert k14["blocked_by"] == ["The licence for this source is not agreed"] and k14["who_unblocks"] == ["the sponsor"]  # a licence waits on the sponsor
    k15 = next(i for i in items if i["measures"] == ["K15"])
    assert k15["blocked_by"] == ["The pack leaves fees out."] and k15["who_unblocks"] == ["the source owner"]  # no mark, a plain risk: the reason


def test_later_items_say_why_and_start_as_not_planned(tmp_path):
    inputs, items = drafted(folder(tmp_path))
    k16, k18 = (next(i for i in items if i["measures"] == [m]) for m in ("K16", "K18"))
    assert k16["why_descoped"] == P.contract()["later_why"]["low_impact"] and k16["covered_by"] is None
    assert k18["why_descoped"] == P.contract()["later_why"]["restricted_undecided"] and k18["restricted"] and k18["key"] == "later:r:K18"
    view = P.band_view(items, {"K16": "Excess return"}, set(), {})
    assert view["later"][0]["date_text"] is None and view["later"][0]["covered_text"] == "not planned yet"


def test_band_rules_one_by_one(tmp_path):
    f = lambda g, s: P._finding(find("K1", g, s))  # noqa: E731
    srcs = {"S1": P._source(src("S1", "a", "small", 0.3)), "S2": P._source(src("S2", "b", "small", -0.2))}
    assert P._band(f("ready", ["S1"]), srcs, False, False)[0] == "now"
    assert P._band(f("unclear", ["S1"]), srcs, False, False)[0] == "next"
    assert P._band(f("unknown", ["S1"]), srcs, False, False)[0] == "next"          # unknown, source known
    assert P._band(f("unknown", []), srcs, False, False)[0] == "later"            # unknown, no source
    assert P._band(f("ready", ["S2"]), srcs, False, False)[0] == "later"          # low impact only
    assert P._band(f("ready", ["S1", "S2"]), srcs, False, False)[0] == "now"      # one source with impact is enough
    assert P._band(f("ready", ["S1"]), srcs, True, True)[0] == "later"            # restricted and not decided
    assert P._band(f("ready", ["S1"]), srcs, True, False)[0] == "now"             # restricted and decided


def test_a_restricted_measure_is_decided_when_its_risks_are_accepted(tmp_path):
    inputs, items = drafted(folder(tmp_path), decided=("R2",))
    assert next(i for i in items if i["measures"] == ["K18"])["why_descoped"] == P.contract()["later_why"]["no_source"]


def test_a_restricted_item_is_a_stub_for_a_viewer_outside_the_list(tmp_path):
    _, items = drafted(folder(tmp_path))
    names = {"K18": "Compensation reconciled", "K10": "Allocation"}
    outside = json.dumps(P.band_view(items, {"K10": "Allocation", "K18": "A restricted measure"}, {"K18"}, {}))
    assert "Compensation" not in outside and "A restricted measure" in outside and "Operations" not in json.dumps(
        next(i for i in P.band_view(items, names, {"K18"}, {})["later"] if i["restricted"]))
    assert "Compensation reconciled" in json.dumps(P.band_view(items, names, set(), {}))


def test_a_human_edit_survives_a_redraft_and_the_new_draft_waits_as_a_proposal(tmp_path):
    d = folder(tmp_path)
    inputs, items = drafted(d)
    key = "next:S2"
    with pytest.raises(PlanError) as e:
        P.edit_item(items, key, {"band": "later"}, "  ", "Sam", "acct-1", NOW)
    assert e.value.code == "invalid"                                       # a reason is required
    edited = P.edit_item(items, key, {"band": "later", "effort": "large", "team": "Custody Operations, Vendor Office", "date": "2026-12-01",
                                      "covered_by": "Running programme P-7"}, "The custodian needs two months", "Sam", "acct-1", NOW)
    it = next(i for i in edited if i["key"] == key)
    assert (it["band"], it["effort"], it["date"], it["team"]) == ("later", "large", "2026-12-01", ["Custody Operations", "Vendor Office"])
    assert it["edits"]["band"]["reason"] == "The custodian needs two months" and it["edits"]["band"]["by"] == "Sam" and it["edits"]["band"]["auto"] == "next"
    # the source's effort mark changes, so the fresh draft says something else
    changed = [{**s, "effort": "small"} if s["id"] == "S2" else s for s in SOURCES]
    (d / "sources.json").write_text(json.dumps({"sources": changed}))
    again = P.merge(P.draft(P.inputs_for_plan(d), {"K18"}, {}), edited)
    kept = next(i for i in again if i["key"] == key)
    assert (kept["band"], kept["effort"], kept["date"], kept["covered_by"]) == ("later", "large", "2026-12-01", "Running programme P-7")
    assert kept["proposals"] == {"effort": "small"} and kept["auto"]["effort"] == "small"  # beside it, never over it
    assert len([i for i in again if i["key"] == key]) == 1 and len(again) == len(items)


def test_an_edited_item_the_draft_no_longer_makes_stays_and_an_unedited_one_goes(tmp_path):
    d = folder(tmp_path)
    _, items = drafted(d)
    edited = P.edit_item(items, "now:S3", {"team": "Treasury"}, "Treasury owns it", "Sam", "a", NOW)
    fewer = P.draft(P.inputs_for_plan(folder(tmp_path / "x", findings=[f for f in FINDINGS if f["measure_id"] not in ("K04", "K09")])), {"K18"}, {})
    again = P.merge(fewer, edited)
    assert [i for i in again if i["key"] == "now:S3"][0].get("stale") is True
    assert not [i for i in again if i["key"] == "now:S5"]


def test_edit_checks_the_values(tmp_path):
    _, items = drafted(folder(tmp_path))
    for bad in ({"band": "soon"}, {"effort": "huge"}, {"date": "tomorrow"}, {"team": ""}, {"nothing": 1}):
        with pytest.raises(PlanError):
            P.edit_item(items, "now:S1", bad, "because", "Sam", "a", NOW)
    with pytest.raises(LookupError):
        P.edit_item(items, "now:none", {"effort": "small"}, "because", "Sam", "a", NOW)


def test_summaries_without_the_model_say_only_what_the_item_holds(tmp_path):
    _, items = drafted(folder(tmp_path))
    names = {"K10": "Private-market allocation", "K12": "Stale-valuation share"}
    now = next(i for i in items if i["measures"] == ["K10"])
    assert P.fallback_summary(now, names) == "Private-market allocation: ready to build. Effort: days."
    assert P.fallback_summary(next(i for i in items if i["measures"] == ["K12"]), names).startswith("Stale-valuation share: waiting on no sample data")
    assert P.fallback_summary(next(i for i in items if i["restricted"]), names).startswith("A restricted measure:")


class Stub:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def complete(self, module_id, messages, tools=None):
        from sh_platform.egress.model import ModelReply
        self.sent.append(messages)
        return ModelReply(self.reply)


class Gate:
    def is_enabled(self, company_id, module_id):
        return True



def test_lens_words_the_items_and_never_sends_a_restricted_measure(tmp_path):
    _, items = drafted(folder(tmp_path))
    names = {"K10": "Private-market allocation", "K09": "Single-issuer concentration", "K04": "Known obligations", "K12": "Stale-valuation share",
             "K15": "Manager performance", "K16": "Excess return", "K14": "Fees reconciled"}
    stub = Stub("I1 = Allocation is ready to build in a few days.\nI2 = Concentration is ready as well.")
    out = plan_lens.word_items(stub, Gate(), "co", company_name="Lakeside", industry="family_office", items=items, names={**names, "K18": "Compensation reconciled"})
    assert out[0]["summary"] == "Allocation is ready to build in a few days." and out[1]["summary"] == "Concentration is ready as well."
    assert out[2]["summary"] == P.fallback_summary(items[2], names)  # a line the model left out keeps the fallback
    sent = json.dumps(stub.sent)
    assert "Compensation" not in sent and "K18" not in sent and "Investment Operations" not in sent  # nothing restricted, no owner or team
    assert next(i for i in out if i["restricted"])["summary"].startswith("A restricted measure")
    off = plan_lens.word_items(None, None, "co", company_name="x", industry="y", items=items, names=names)
    assert off[0]["summary"] == P.fallback_summary(items[0], names)


def test_a_failing_model_keeps_the_fallback(tmp_path):
    _, items = drafted(folder(tmp_path))

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("down")
    out = plan_lens.word_items(Boom(), Gate(), "co", company_name="x", industry="y", items=items, names={})
    assert [i["summary"] for i in out] == [P.fallback_summary(i, {}) for i in items]


# ---- accepting and signing -------------------------------------------------------------------------------------------------------------
def test_risk_states():
    r = {"id": "R1", "rechecked_at": None}
    assert P.risk_state(r, None) == "open"
    assert P.risk_state(r, {"decision": "accepted"}) == "accepted"
    assert P.risk_state(r, {"decision": "sent_back", "at": "2026-10-04T10:00"}) == "sent_back"
    assert P.risk_state({**r, "rechecked_at": "2026-10-05T09:00"}, {"decision": "sent_back", "at": "2026-10-04T10:00"}) == "rechecked"
    assert P.risk_state({**r, "rechecked_at": "2026-10-03T09:00"}, {"decision": "sent_back", "at": "2026-10-04T10:00"}) == "sent_back"  # older than the decision
    assert P.risk_state({**r, "decision": {"state": "accepted"}}, None) == "accepted"  # a decision P03 wrote itself is read too


def test_deciding_records_who_and_when_and_never_touches_findings(tmp_path):
    d = folder(tmp_path)
    before = (d / "findings.json").read_bytes()
    risks = X.with_decisions(P.inputs_for_plan(d)["risks"], {})
    with pytest.raises(PlanError) as e:
        X.decide(d, risks, "R1", "sent_back", " ", "Sam", "a1", NOW, set())
    assert e.value.code == "invalid" and "why" in e.value.message
    X.decide(d, risks, "R1", "accepted", "fine by us", "Sam", "a1", NOW, set())
    X.decide(d, risks, "R3", "sent_back", "Please count the empty cells", "Pat", "a2", NOW, set())
    got = X.read_decisions(d)
    assert got["R1"] == {"decision": "accepted", "note": "fine by us", "by": "Sam", "account_id": "a1", "at": NOW, "history": []}
    assert got["R3"]["reason"] == "Please count the empty cells" and got["R3"]["by"] == "Pat"
    with pytest.raises(PlanError) as e:
        X.decide(d, risks, "R1", "accepted", None, "Sam", "a1", NOW, set())
    assert e.value.code == "already_decided"
    X.decide(d, risks, "R1", "sent_back", "Changed my mind", "Sam", "a1", NOW, set())
    assert X.read_decisions(d)["R1"]["history"][0]["decision"] == "accepted"      # the earlier decision is kept
    with pytest.raises(LookupError):
        X.decide(d, risks, "R9", "accepted", None, "Sam", "a1", NOW, set())
    with pytest.raises(PlanError) as e:
        X.decide(d, risks, "R2", "accepted", None, "Sam", "a1", NOW, {"K18"})
    assert e.value.code == "restricted"
    assert (d / "findings.json").read_bytes() == before


def test_accept_all_remaining_gives_each_risk_its_own_record_and_skips_what_is_hidden(tmp_path):
    d = folder(tmp_path)
    risks = X.with_decisions(P.inputs_for_plan(d)["risks"], {})
    X.decide(d, risks, "R3", "sent_back", "Count them", "Pat", "a2", NOW, set())
    got = X.decide_all(d, risks, "all reviewed", "Sam", "a1", NOW, {"K18"})
    assert (got["accepted"], got["left_hidden"], got["left"]) == (1, 1, 1) and "those people decide" in got["message"]                                 # R1 accepted; R2 is hidden from Sam; R3 stays sent back
    rec = X.read_decisions(d)
    assert set(rec) == {"R1", "R3"} and rec["R1"]["by"] == "Sam" and rec["R1"]["at"] == NOW and rec["R1"]["note"] == "all reviewed"
    again = X.decide_all(d, X.with_decisions(P.inputs_for_plan(d)["risks"], rec), None, "Hana", "a3", NOW, set())
    assert (again["accepted"], again["left_hidden"]) == (1, 0) and X.read_decisions(d)["R2"]["by"] == "Hana"


def plan_ready(d, decide_all=True):
    inputs, items = drafted(d)
    X.draft_plan(d, items, NOW, "a" * 32)
    if decide_all:
        X.decide_all(d, X.with_decisions(inputs["risks"], {}), None, "Sam", "a1", NOW, set())
    return P.inputs_for_plan(d)


FACTS = {"names": {"K10": "Allocation", "K12": "Stale share"}, "restricted": ["K18"], "baseline_outcome_id": "b" * 32, "charter_outcome_id": "c" * 32}


def test_signing_is_refused_while_a_risk_is_open_and_says_how_many(tmp_path):
    d = folder(tmp_path)
    inputs = plan_ready(d, decide_all=False)
    with pytest.raises(PlanError) as e:
        X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 0, FACTS)
    assert e.value.code == "risks_open" and "3 risks still need a decision" in e.value.message
    risks = X.with_decisions(inputs["risks"], {})
    X.decide(d, risks, "R1", "accepted", None, "Sam", "a1", NOW, set())
    X.decide(d, risks, "R2", "accepted", None, "Sam", "a1", NOW, set())
    X.decide(d, risks, "R3", "sent_back", "Count them", "Sam", "a1", NOW, set())
    with pytest.raises(PlanError) as e:
        X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 0, FACTS)
    assert "1 sent back risk is still being re-checked by Lens" in e.value.message
    assert not (tmp_path / "assessments" / "outcomes").exists()


def test_a_sent_back_risk_counts_as_decided_once_lens_has_re_checked_it(tmp_path):
    d = folder(tmp_path)
    inputs = plan_ready(d, decide_all=False)
    risks = X.with_decisions(inputs["risks"], {})
    for rid in ("R1", "R2"):
        X.decide(d, risks, rid, "accepted", None, "Sam", "a1", NOW, set())
    X.decide(d, risks, "R3", "sent_back", "Count them", "Sam", "a1", NOW, set())
    rechecked = {**json.loads((d / "findings.json").read_text())}
    rechecked["risks"][2]["rechecked_at"] = "2026-10-05T09:00:00+00:00"
    (d / "findings.json").write_text(json.dumps(rechecked))
    plan = X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 0, FACTS)
    assert [s["slot"] for s in plan["signatures"]] == ["sponsor"]


def test_sign_order_and_the_outcome_is_written_once(tmp_path):
    d = folder(tmp_path)
    inputs = plan_ready(d)
    with pytest.raises(PlanError) as e:
        X.sign(d, "Hana", "a3", {"company_admin"}, NOW, 0, FACTS)
    assert e.value.code == "no_slot"                                                # the head of data cannot go first
    with pytest.raises(PlanError) as e:
        X.sign(d, "Pat", "a2", {"analyst"}, NOW, 0, FACTS)
    assert e.value.code == "no_slot"
    first = X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 0, FACTS)
    assert first["signed_at"] is None and first["outcome_id"]
    assert not X.outcomes_dir(d).exists()                                           # nothing for module 4 yet
    with pytest.raises(PlanError) as e:
        X.sign(d, "Sam", "a1", {"sponsor", "company_admin"}, NOW, 0, FACTS)
    assert e.value.code == "already_signed"                                         # the same account cannot sign twice
    with pytest.raises(PlanError) as e:
        X.refuse_if_locked(X.read_plan(d))
    assert e.value.code == "locked" and "Sam (Sponsor)" in e.value.message          # the first signature already locks the plan
    done = X.sign(d, "Hana", "a3", {"company_admin"}, "2026-10-04T11:00:00+00:00", 0, FACTS)
    assert done["signed_at"] == "2026-10-04T11:00:00+00:00" and [s["slot"] for s in done["signatures"]] == ["sponsor", "head_of_data"]
    files = list(X.outcomes_dir(d).glob("*.json"))
    assert [f.stem for f in files] == [done["outcome_id"]]
    rec = json.loads(files[0].read_text())
    assert rec["kind"] == "plan" and rec["module"] == "m3_connect" and rec["assessment_id"] == "a" * 32 and set(rec["plan"]) == {"now", "next", "later"}
    assert rec["findings_summary"]["counts"] == {"ready": 3, "unclear": 2, "unknown": 3} and [s["name"] for s in rec["signatures"]] == ["Sam", "Hana"]
    assert {r["id"] for r in rec["accepted_risks"]} == {"R1", "R2", "R3"} and all(r["decision"]["by"] == "Sam" for r in rec["accepted_risks"] if r["id"] != "R2")
    assert [i["key"] for i in rec["plan"]["now"]] == ["now:S1", "now:S3", "now:S5"]
    with pytest.raises(PlanError) as e:
        X.sign(d, "Hana", "a3", {"company_admin"}, NOW, 0, FACTS)
    assert e.value.code == "signed" and len(list(X.outcomes_dir(d).glob("*.json"))) == 1
    # a retry never writes a second record, and never rewrites the first
    before = files[0].read_bytes()
    X.write_outcome(d, done["outcome_id"], done, X.with_decisions(inputs["risks"], X.read_decisions(d)), inputs, FACTS)
    assert files[0].read_bytes() == before


def test_the_outcome_keeps_a_restricted_measure_restricted(tmp_path):
    d = folder(tmp_path)
    inputs = plan_ready(d)
    X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 1, FACTS)
    done = X.sign(d, "Hana", "a3", {"company_admin"}, NOW, 0, {**FACTS, "names": {**FACTS["names"], "K18": "Compensation reconciled"}})
    text = (X.outcomes_dir(d) / f"{done['outcome_id']}.json").read_text()
    assert "Compensation" not in text and "No pay review file" not in text and "Compensation has no source" not in text
    rec = json.loads(text)
    assert rec["measure_names"]["K18"] == "A restricted measure" and rec["signatures"][0]["note"].startswith("covers 1 restricted measure")
    k18 = next(i for i in rec["plan"]["later"] if i["measures"] == ["K18"])
    assert k18["restricted"] and k18["summary"] == "A restricted measure" and "team" not in k18


def test_a_head_of_data_who_cannot_see_every_measure_does_not_sign(tmp_path):
    d = folder(tmp_path)
    inputs = plan_ready(d)
    X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 2, FACTS)                    # the sponsor signs for what they see
    with pytest.raises(PlanError) as e:
        X.sign(d, "Hana", "a3", {"company_admin"}, NOW, 2, FACTS)
    assert e.value.code == "not_visible"


def test_the_next_sentences(tmp_path):
    d = folder(tmp_path)
    inputs = P.inputs_for_plan(d)
    risks = lambda *s: [{"state": x} for x in s]  # noqa: E731
    assert X.next_sentence(None, risks("open", "open", "open")) == "3 risks need a decision from the sponsor."
    assert X.next_sentence(None, risks("open")) == "1 risk needs a decision from the sponsor."
    assert X.next_sentence(None, risks("accepted", "sent_back")) == "Lens is re-checking 1 risk you sent back."
    assert X.next_sentence({"signed_at": None, "signatures": []}, risks("accepted", "rechecked")) == "The plan is ready to sign. The sponsor signs next."
    assert X.next_sentence({"signed_at": None, "signatures": [{"slot": "sponsor"}]}, risks("accepted")) == "Waiting for the head of data to sign."
    assert X.next_sentence({"signed_at": "x", "signatures": []}, []) == "The plan is signed. Module 4 starts from it."
    assert X.step_state(tmp_path / "none") == {"state": "not_started"}
    got = X.step_state(d)
    assert got["state"] == "in_progress" and got["waiting_on"] == "3 risks need a decision from the sponsor." and inputs["ready"]


# ---- reviewer round: leaks, bad types, locked reads --------------------------------------------------------------------------------------
def test_the_outcome_keeps_free_text_of_a_hidden_risk_out_and_masks_source_restricted_items(tmp_path):
    srcs = [{**s, "marks": [*s["marks"], "restricted"]} if s["id"] == "S2" else s for s in SOURCES]   # S2 restricted by its mark, K12 itself is not
    d = folder(tmp_path, sources=srcs)
    inputs, items = drafted(d)
    X.draft_plan(d, items, NOW, "a" * 32)
    key = next(i["key"] for i in items if i["measures"] == ["K12"])
    X.change_plan(d, lambda p: {**p, "items": P.edit_item(p["items"], key, {"effort": "large"}, "Secret reason about Dana", "Sam", "a1", NOW)}, NOW)
    risks = X.with_decisions(inputs["risks"], {})
    X.decide(d, risks, "R2", "accepted", "Compensation for Priya is the issue", "Priya Nair", "a1", NOW, set())
    X.decide_all(d, risks, None, "Sam", "a1", NOW, set())
    X.sign(d, "Sam", "a1", {"sponsor"}, NOW, 0, FACTS)
    done = X.sign(d, "Hana", "a3", {"company_admin"}, NOW, 0, FACTS)
    text = (X.outcomes_dir(d) / f"{done['outcome_id']}.json").read_text()
    for leak in ("Compensation for Priya", "Priya Nair", "Secret reason", "Omar Lee", "Custody Operations"):
        assert leak not in text, leak
    rec = json.loads(text)
    r2 = next(r for r in rec["accepted_risks"] if r["id"] == "R2")
    assert r2["decision"] == {"decision": "accepted", "at": NOW}
    k12 = next(i for b in rec["plan"].values() for i in b if i["measures"] == ["K12"])
    assert k12["restricted"] and k12["summary"] == "A restricted measure" and "team" not in k12 and k12["edits"] == {}


def test_the_viewer_loses_owner_names_and_edit_reasons_on_a_source_restricted_item(tmp_path):
    srcs = [{**s, "marks": [*s["marks"], "restricted"]} if s["id"] == "S2" else s for s in SOURCES]
    _, items = drafted(folder(tmp_path, sources=srcs))
    k12 = next(i for i in items if i["measures"] == ["K12"])
    items = P.edit_item(items, k12["key"], {"effort": "large"}, "Because of Omar", "Sam", "a1", NOW)
    got = next(i for b in P.band_view(items, {"K12": "Stale share"}, set(), {}).values() for i in b if i["measures"] and i["measures"][0]["id"] == "K12")
    text = json.dumps(got)
    assert "Omar" not in text and "Custody Operations" not in text and got["edits"] == {} and got["team"] == []
    assert got["measures"] == [{"id": "K12", "name": "Stale share"}]


def test_edit_refuses_values_of_the_wrong_type_without_an_exception(tmp_path):
    _, items = drafted(folder(tmp_path))
    for bad in ({"band": []}, {"effort": {}}, {"team": 5}, {"team": [1]}, {"date": 20261201}, {"covered_by": ["x"]}):
        with pytest.raises(PlanError) as e:
            P.edit_item(items, "now:S1", bad, "because", "Sam", "a", NOW)
        assert e.value.code == "bad_value"
    with pytest.raises(PlanError):
        P.edit_item(items, "now:S1", {"effort": "small"}, ["x"], "Sam", "a", NOW)
