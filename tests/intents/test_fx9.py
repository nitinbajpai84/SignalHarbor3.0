"""FX9: the cycle carries the hypothesis (57) into the Initiative and Brainstorm starts (22, 35), What next (37) and the charter (32)."""
import pytest

from sh_platform.intents import charter as CH, converge as CV, hypotheses as H, initiative as I, lifecycle as L, opportunities as O, store as S
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import view as pview

NOW = "2026-10-07T09:00:00+00:00"
HARVEY = pview.Viewer("Harvey Rowley", frozenset({"owner"}), False, "acc-harvey")
JANET = pview.Viewer("Janet Shaw", frozenset({"company_admin"}), False, "acc-janet")


@pytest.fixture
def plane(tmp_path):
    p = CompanyPlane("ardmore", tmp_path)
    hyp = H.create(p, {"kind": "opportunity", "ref": "opp-0001"}, {
        "belief": "Statements arrive late and slow the monthly pack", "lens": "process_cost", "measure": {"id": "K03", "name": "Days to pack"},
        "baseline": {"value": 9, "unit": "days", "periods": ["2026-09"], "trace": {"kind": "feed", "ref": "gold.k03#2026-09", "at": "2026-09"}},
        "target": {"value": 5, "unit": "days", "by": "2026-10-14", "set_by": "Harvey"}, "review_date": "2026-10-14",
        "evidence": [H.evidence_line(1, "data", "supports", "Pack days rose from 6 to 9 in four periods", {"kind": "feed", "ref": "gold.k03", "at": "2026-09"}, "watcher")]},
        "north", state="checked")
    for oid, as_ in (("opp-0001", "initiative"), ("opp-0002", "brainstorm")):
        write_json_atomic(O._dir(p) / f"{oid}.json", {"id": oid, "title": "Pack days moved up", "state": "picked_up", "areas": ["operations"],
                          "pattern": {"text": "K03 moved up", "kind": "data"}, "picked_up_by": "acc-harvey", "picked_up_as": as_, "became": None,
                          "hypothesis_ref": H.ref(hyp), "history": []})
    return p


def draft(plane, kind, who=HARVEY):
    return S.create_intent(plane, L.new_record(kind, "ardmore", L.person(who.account_id, who.name), NOW))


def test_initiative_start_carries_the_hypothesis(plane):
    d = draft(plane, "initiative")
    rec = I.carry(plane, HARVEY, d["id"], "opp-0001", d["version"], NOW)
    a = rec["start_answers"]
    assert rec["hypothesis_ref"] == {"id": "hyp-0001", "version": 1} and rec["title"].startswith("Statements arrive late")
    assert a["goal"]["value"]["line"].startswith("Statements") and "target 5 days" in a["goal"]["value"]["why"]
    assert {a[k]["mark"] for k in a} == {"guessed"} and a["areas"]["value"] == ["operations"] and a["deadline"]["value"] == "2026-10-14"
    assert a["definitions"]["terms"] == ["Days to pack"] and a["goal"]["from"] == "The opportunity: Pack days moved up"
    assert O.get(plane, "opp-0001")["became"] == d["id"]
    h = H.get(plane, "hyp-0001")
    assert h["state"] == "carried" and h["carried_into"] == [{"intent": d["id"], "version": 1}]
    assert I.carry(plane, HARVEY, d["id"], "opp-0001", rec["version"], NOW)["version"] == rec["version"]  # opening again changes nothing
    other = draft(plane, "initiative")
    with pytest.raises(L.Refused):  # one opportunity becomes one intent
        I.carry(plane, HARVEY, other["id"], "opp-0001", other["version"], NOW)


def test_only_the_picker_on_their_own_draft_of_the_picked_type(plane):
    mine = draft(plane, "initiative", JANET)
    with pytest.raises(L.Refused):  # Janet did not pick it up
        I.carry(plane, JANET, mine["id"], "opp-0001", mine["version"], NOW)
    with pytest.raises(LookupError):  # not Harvey's draft
        I.carry(plane, HARVEY, mine["id"], "opp-0001", mine["version"], NOW)
    wrong = draft(plane, "initiative")
    with pytest.raises(L.Refused):  # picked up as a Brainstorm
        I.carry(plane, HARVEY, wrong["id"], "opp-0002", wrong["version"], NOW)


def test_brainstorm_carries_and_its_initiative_inherits(plane):
    b = draft(plane, "brainstorm")
    rec = I.carry(plane, HARVEY, b["id"], "opp-0002", b["version"], NOW)
    a = rec["start_answers"]
    assert a["statement"].startswith("Statements") and a["good_outcome"] == "Days to pack reaches 5 days by 2026-10-14." and a["areas"] == ["operations"]
    assert a["carried"]["values"]["statement"] == a["statement"] and rec["hypothesis_ref"]["id"] == "hyp-0001"
    assert CV.prefill(rec)["hypothesis_ref"]["id"] == "hyp-0001"  # What next (37) names it
    child = L.new_record("initiative", "ardmore", L.person("acc-harvey", "Harvey Rowley"), NOW, link_from=b["id"])
    assert I.inherited_ref(plane, child) == {"id": "hyp-0001", "version": 1}
    I.mark_carried(plane, I.inherited_ref(plane, child), child["id"])
    assert [c["intent"] for c in H.get(plane, "hyp-0001")["carried_into"]] == [b["id"], child["id"]]


def test_charter_success_measures_from_the_hypothesis(plane):
    d = draft(plane, "initiative")
    rec = I.carry(plane, HARVEY, d["id"], "opp-0001", d["version"], NOW)
    s = CH.success_measures(plane, rec)
    assert s["label"] == "From the hypothesis" and s["measure"]["name"] == "Days to pack" and s["target"]["value"] == 5 and s["text"] is None
    CH.edit_success(plane, rec, {"target": 4, "review_date": "2026-10-21"}, "Harvey Rowley")
    s = CH.success_measures(plane, rec)
    assert s["target"]["value"] == 4 and s["target"]["by"] == "2026-10-21" and s["hypothesis"]["version"] == 2
    assert H.get(plane, "hyp-0001")["versions"][0]["target"]["value"] == 5  # the earlier version stays as it was
    with pytest.raises(Exception):
        CH.edit_success(plane, rec, {"target": "lots"}, "Harvey Rowley")
    assert CH.success_measures(plane, {"id": "x"}) is None
