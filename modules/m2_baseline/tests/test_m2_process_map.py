"""M2-P03: the process map drawn from the owners' answers (M2-12, M2-21, M2-22). Ported and adapted from the earlier
product's tests/test_baseline.py (pack steps are proposals, a redraw keeps validated, edited and removed steps)."""
import json
import re

import pytest
import yaml
from m2_kit import BASE, login

from modules.m2_baseline.domain import process_map as D
from modules.m2_baseline.domain.provenance import prov, unknown

PMB = "d" * 32  # a real baseline id is 32 hex characters
MAP = f"{BASE}/baselines/{PMB}/process-map"
S = lambda v, by="Arjun Rao": prov(v, "stated", by, "meeting")  # noqa: E731
G = lambda v: prov(v, "guessed", "Arjun Rao", "meeting")  # noqa: E731

KPI = {"id": "k1", "name": "Funding capacity", "governance": {"personal": "no", "sensitive": False, "may_see": []}}
ANSWER = {"id": "a1", "owner_name": "Arjun Rao", "kpi_id": "k1",
          "upstream": S([{"who": S("Bank"), "what": S("Sends statement, daily")}]),
          "in_between": S([{"who": S("Finance"), "step": S("Downloads file"), "manual": S(False)},
                           {"who": S("Finance"), "step": S("Adjusts in workbook"), "manual": S(True)},
                           {"who": S("Investments"), "step": G("Checks the figure"), "manual": S(False)}]),
          "downstream": S([{"who": S("Committee"), "what": S("Reads the monthly pack")}])}
PACK_DEFAULT = {"steps": [{"step_id": "p1", "lane": "Operations", "name": "Register the document", "manual": True},
                          {"step_id": "p2", "lane": "Committee", "name": "Approve"}]}


def seed(world, company="co-a", answers=(ANSWER,), kpis=(KPI,), state="mapping"):
    folder = world.plane(company).path("intents", "m2_baseline", PMB)
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in (("kpis.json", list(kpis)), ("answers.json", list(answers)),
                       ("baseline.json", {"id": PMB, "charter_outcome_id": "o", "state": state, "created_at": "now"})):
        (folder / name).write_text(json.dumps(data))
    return folder


def put_pack_default(world, industry="industry_a"):
    (world.packs / industry / "1" / "process_map_default.yaml").write_text(yaml.safe_dump(PACK_DEFAULT))


def kpi_view(c):
    return c.get(MAP).json()["kpis"][0]


# ---- the drawing (domain)

def test_steps_come_from_the_answers_in_order_with_lanes_manual_marks_and_the_answer_they_came_from():
    m = D.draw([ANSWER], None, "pack", None)
    assert [(s["lane"], s["text"]) for s in m["steps"]] == [
        ("Bank", "Sends statement, daily"), ("Finance", "Downloads file"), ("Finance", "Adjusts in workbook"),
        ("Investments", "Checks the figure"), ("Committee", "Reads the monthly pack")]
    assert m["lanes"] == ["Bank", "Finance", "Investments", "Committee"]
    assert [s["manual"] for s in m["steps"]] == [False, False, True, False, False]
    assert [s["confirmed"] for s in m["steps"]] == [True, True, True, False, True]  # the guessed one is dashed
    assert [s["order"] for s in m["steps"]] == [1, 2, 3, 4, 5]
    assert {s["from"] for s in m["steps"]} == {"a1"} and all(s["state"] == "proposal" and s["by"] == "Lens" for s in m["steps"])
    assert all(set(s) == {"id", "lane", "text", "order", "manual", "confirmed", "from", "state", "by"} for s in m["steps"])


def test_only_what_an_owner_mentioned_is_drawn_a_gap_stays_a_to_confirm_step_and_unknown_draws_nothing():
    a = {"id": "a2", "owner_name": "Sara", "kpi_id": "k1", "upstream": unknown(),
         "in_between": S([{"who": S("Finance"), "step": unknown(), "manual": S(True)}, {"who": unknown(), "step": unknown()}]),
         "downstream": S([{"who": unknown(), "what": S("Reads the pack")}])}
    steps = D.draw([a], PACK_DEFAULT, "pack", None)["steps"]
    assert [(s["lane"], s["text"], s["confirmed"]) for s in steps] == [
        ("Finance", "To confirm: what Finance does here", False), (D.NO_LANE, "Reads the pack", False)]
    assert steps[0]["manual"] is True  # said to be manual, even though the wording is missing


def test_with_no_answers_the_pack_default_seeds_guessed_proposals_and_with_answers_it_does_not():
    seeded = D.draw([], PACK_DEFAULT, "pack: Family office", None)["steps"]
    assert [(s["lane"], s["manual"], s["confirmed"], s["from"], s["by"]) for s in seeded] == [
        ("Operations", False, False, "pack: Family office", "the pack"), ("Committee", False, False, "pack: Family office", "the pack")]  # R4 defect 7: the pack's "manual" is not an owner's word
    assert {D.mark_of(s) for s in seeded} == {"guessed"}
    assert not any(s["from"].startswith("pack") for s in D.draw([ANSWER], PACK_DEFAULT, "pack", None)["steps"])
    assert D.draw([], None, "pack", None) == {"lanes": [], "steps": []}  # nothing to go on: an empty map, not an invention


def test_a_redraw_keeps_validated_edited_removed_and_added_steps_and_replaces_the_rest():
    m = D.draw([ANSWER], None, "pack", None)
    ids = [s["id"] for s in m["steps"]]
    D.validate_step(m, ids[0], "Pat")
    D.edit_step(m, ids[1], "Pat", text="Downloads the file by hand", manual=True)
    D.remove_step(m, ids[2], "Pat")
    D.add_step(m, "Tax adviser", "Reviews the figure", False, "Pat")
    changed = {**ANSWER, "upstream": S([{"who": S("Bank"), "what": S("Sends a different statement")}])}
    again = D.draw([changed], None, "pack", m)
    by_id = {s["id"]: s for s in again["steps"]}
    assert by_id[ids[0]]["state"] == "validated" and by_id[ids[0]]["text"] == "Sends statement, daily"  # the person's version stays
    assert by_id[ids[1]]["text"] == "Downloads the file by hand" and by_id[ids[1]]["state"] == "edited"
    assert by_id[ids[2]]["state"] == "removed" and "Adjusts in workbook" not in D.view(again, [ANSWER])["steps"].__str__()
    assert by_id["added-1"]["from"] == "added by Pat" and by_id["added-1"]["confirmed"]
    assert by_id[ids[3]]["state"] == "proposal"


def test_validate_edit_remove_need_a_person_and_a_known_step():
    m = D.draw([ANSWER], None, "pack", None)
    with pytest.raises(ValueError):
        D.validate_step(m, "a1-u0", " ")
    with pytest.raises(KeyError):
        D.remove_step(m, "nope", "Pat")
    with pytest.raises(ValueError):
        D.add_step(m, "", "x", False, "Pat")


def test_the_view_counts_what_lens_says_and_hides_removed_steps():
    m = D.draw([ANSWER], None, "pack", None)
    D.remove_step(m, "a1-d0", "Pat")
    v = D.view(m, [ANSWER])
    assert v["counts"] == {"answers": 1, "to_confirm": 1, "manual": 1} and v["removed"] == 1 and len(v["steps"]) == 4
    assert v["steps"][0]["owner"] == "Arjun Rao" and v["steps"][3]["mark"] == "to_confirm" and v["steps"][0]["mark"] == "stated"


# ---- tidy: Lens only rewords, through a model it is handed

class Words:
    def __init__(self, reply="", fail=False):
        self.reply, self.fail, self.sent = reply, fail, []

    def complete(self, module_id, messages, tools=None):
        from sh_platform.agents.protocols import ModelReply
        self.sent.append(messages)
        if self.fail:
            raise RuntimeError("provider down")
        return ModelReply(self.reply)


class Echo(Words):
    """A reword that keeps every word: each numbered step comes back with " (tidied)" added."""
    def complete(self, module_id, messages, tools=None):
        from sh_platform.agents.protocols import ModelReply
        self.sent.append(messages)
        return ModelReply("\n".join(re.sub(r"^\d+\. ", "", ln) + " (tidied)" for ln in messages[-1]["content"].splitlines()))


def test_a_reword_that_changes_a_noun_keeps_the_original_wording():
    """The story's corruption: "Call notices" came back as "Access notices"."""
    assert D.keeps_words("Call notices", "Call notices") and not D.keeps_words("Call notices", "Access notices")
    assert D.keeps_words("Pastes levels into the workbook", "Pastes the levels into workbook") and not D.keeps_words("Call dates", "Access dates")
    got = D.tidy_texts(Words("Access notices\nSends the positions file daily"), ["Call notices", "Sends positions file"])
    assert got == ["Call notices", "Sends the positions file daily"]


def test_tidy_rewords_only_untouched_steps_and_any_odd_reply_keeps_the_original_wording():
    original = [s["text"] for s in D.draw([ANSWER], None, "pack", None)["steps"]]
    assert [s["text"] for s in D.draw([ANSWER], None, "pack", None, Echo())["steps"]] == [f"{t} (tidied)" for t in original]
    for bad in (Words("only one line"), Words(fail=True), Words("\n".join("long " * 60 for _ in range(5)))):
        assert [s["text"] for s in D.draw([ANSWER], None, "pack", None, bad)["steps"]] == original
    m = D.draw([ANSWER], None, "pack", None)
    D.edit_step(m, "a1-u0", "Pat", text="Mine")
    assert D.draw([ANSWER], None, "pack", m, Words("\n".join(f"T{i}" for i in range(4))))["steps"][0]["text"] == "Mine"


# ---- the routes

def test_draw_then_read_shows_the_map_with_lens_counts_and_signed_baselines_are_never_redrawn(world):
    seed(world)
    c = login(world, "co-a")
    assert not kpi_view(c)["drawn"] and kpi_view(c)["steps"] == []
    r = c.post(f"{MAP}/draw")
    assert r.status_code == 200
    k = r.json()["kpis"][0]
    assert k["drawn"] and k["lanes"] == ["Bank", "Finance", "Investments", "Committee"] and k["counts"] == {"answers": 1, "to_confirm": 1, "manual": 1}
    assert [s["tracking"] for s in k["steps"]] == [None] * 5 and k["tracking"]["status"]["mark"] == "unknown"
    assert c.get(MAP).json()["kpis"][0]["steps"] == k["steps"]
    seed(world, state="signed")
    r = c.post(f"{MAP}/draw")
    assert r.status_code == 409 and r.json()["error"] == "signed"
    assert c.post(f"{MAP}/k1/steps", json={"lane": "A", "text": "b"}).status_code == 409
    assert c.get(MAP).json()["signed"] is True


def test_people_validate_edit_remove_and_add_and_a_redraw_keeps_it_all(world):
    seed(world)
    c = login(world, "co-a", name="Pat Owner")
    c.post(f"{MAP}/draw")
    k = c.post(f"{MAP}/k1/steps/a1-i2/validate").json()
    assert next(s for s in k["steps"] if s["id"] == "a1-i2")["state"] == "validated" and k["steps"][0]["by"] == "Lens"
    assert next(s for s in k["steps"] if s["id"] == "a1-i2")["by"] == "Test Pat Owner"
    k = c.put(f"{MAP}/k1/steps/a1-i0", json={"text": "Adjusts it by hand", "manual": True}).json()
    assert next(s for s in k["steps"] if s["id"] == "a1-i0")["manual"] is True and k["counts"]["manual"] == 2
    k = c.delete(f"{MAP}/k1/steps/a1-u0").json()
    assert k["removed"] == 1 and "a1-u0" not in [s["id"] for s in k["steps"]]
    k = c.post(f"{MAP}/k1/steps", json={"lane": "Tax adviser", "text": "Reviews the figure", "manual": False}).json()
    assert k["steps"][-1]["lane"] == "Tax adviser" and k["steps"][-1]["mark"] == "stated" and "Tax adviser" in k["lanes"]
    again = c.post(f"{MAP}/draw").json()["kpis"][0]
    assert [s["id"] for s in again["steps"]] == [s["id"] for s in k["steps"]]
    assert next(s for s in again["steps"] if s["id"] == "a1-i0")["text"] == "Adjusts it by hand"
    saved = json.loads(world.plane("co-a").path("intents", "m2_baseline", PMB, "process_map.json").read_text())
    assert [s["state"] for s in saved["k1"]["steps"] if s["id"] == "a1-u0"] == ["removed"]  # kept in the file, not deleted


def test_bad_input_is_refused_in_plain_words(world):
    seed(world)
    c = login(world, "co-a")
    assert c.post(f"{MAP}/k1/steps", json={"lane": "", "text": "x"}).status_code == 400
    assert c.post(f"{MAP}/nope/steps", json={"lane": "A", "text": "x"}).status_code == 404
    assert c.post(f"{MAP}/k1/steps/zzz/validate").status_code == 404
    assert c.get(f"{BASE}/baselines/a b/process-map").status_code in (404, 400)
    r = c.put(f"{MAP}/k1/tracking", json={"status": "maybe"})
    assert r.status_code == 400 and "Tracked now" in r.json()["message"]
    assert c.put(f"{MAP}/k1/tracking", json={"status": "not_tracked", "tentative_date": "soon"}).status_code == 400


def test_tracking_status_with_a_tentative_date_and_next_step_shows_on_the_kpi_and_on_each_step(world):
    seed(world)
    c = login(world, "co-a", name="Pat Owner")
    c.post(f"{MAP}/draw")
    k = c.put(f"{MAP}/k1/tracking", json={"status": "not_tracked", "tentative_date": "2027-03-31",
                                          "next_step": "Ask the bank for a daily feed"}).json()
    t = k["tracking"]
    assert (t["status"]["value"], t["status"]["mark"], t["status"]["by"]) == ("not_tracked", "stated", "Test Pat Owner")
    assert t["tentative_date"]["value"] == "2027-03-31" and t["next_step"]["value"] == "Ask the bank for a daily feed"
    assert {s["tracking"] for s in k["steps"]} == {"not_tracked"}
    k = c.put(f"{MAP}/k1/tracking", json={"status": "tracked_now", "step_id": "a1-i1"}).json()
    assert [s["tracking"] for s in k["steps"]][2] == "tracked_now" and k["steps"][0]["tracking"] == "not_tracked"
    assert c.put(f"{MAP}/k1/tracking", json={"status": "partly", "step_id": "nope"}).status_code == 404
    k = c.put(f"{MAP}/k1/tracking", json={"status": "partly", "tentative_date": ""}).json()
    assert k["tracking"]["tentative_date"]["mark"] == "unknown" and k["tracking"]["next_step"]["value"]  # a date is optional


def test_the_kpis_own_tracking_value_from_the_work_list_is_the_default(world):
    seed(world, kpis=({**KPI, "tracking": prov("partly", "stated", "Arjun Rao", "meeting")},))
    k = kpi_view(login(world, "co-a"))
    assert k["tracking"]["status"]["value"] == "partly"


def test_the_pack_default_seeds_guessed_steps_when_there_are_no_answers(world):
    put_pack_default(world)
    seed(world, answers=())
    k = login(world, "co-a").post(f"{MAP}/draw").json()["kpis"][0]
    assert [(s["lane"], s["mark"]) for s in k["steps"]] == [("Operations", "guessed"), ("Committee", "guessed")]
    assert k["counts"]["to_confirm"] == 2 and k["steps"][0]["owner"] is None


def test_drawing_with_a_model_rewords_through_it_and_without_one_still_draws(world):
    seed(world)
    c = login(world, "co-a")
    world.app.state.lens_model_factory = lambda plane: Echo()
    assert [s["text"] for s in c.post(f"{MAP}/draw").json()["kpis"][0]["steps"]][0] == "Sends statement, daily (tidied)"
    del world.app.state.lens_model_factory
    k = c.post(f"{MAP}/draw").json()["kpis"][0]  # model_env is {}: no key, no model
    assert k["steps"][0]["text"] == "Sends statement, daily" and len(k["steps"]) == 5


@pytest.mark.parametrize("company", ["co-a", "co-b", "co-none", "co-solo"])
def test_every_industry_an_empty_company_and_one_person_alone(world, company):
    c = login(world, company)
    assert c.get(MAP).json()["kpis"] == []  # nothing yet: an empty list, not a failure
    seed(world, company)
    assert len(c.post(f"{MAP}/draw").json()["kpis"][0]["steps"]) == 5


def test_another_companys_map_and_a_missing_module_are_unreachable(world):
    seed(world, "co-a")
    assert login(world, "co-b", name="B Person").get(MAP).json()["kpis"] == []
    assert login(world, "co-off", name="Off Person").get(MAP).status_code in (403, 404)
    assert login(world, "co-a", name="Other Person", roles=("participant",)).get(MAP).status_code == 403


def test_a_damaged_file_is_refused_and_never_overwritten(world):
    folder = seed(world)
    (folder / "process_map.json").write_text("{not json")
    c = login(world, "co-a")
    assert c.post(f"{MAP}/draw").status_code == 500
    assert (folder / "process_map.json").read_text() == "{not json"


def test_fresh_steps_from_a_redraw_are_numbered_after_a_persons_added_step():
    m = D.draw([ANSWER], None, "pack", None)
    D.add_step(m, "Tax adviser", "Reviews the figure", False, "Pat")  # order 6
    more = {**ANSWER, "downstream": S([{"who": S("Committee"), "what": S("Reads the monthly pack")}, {"who": S("Board"), "what": S("Signs off")}])}
    again = D.draw([more], None, "pack", m)["steps"]
    assert len({s["order"] for s in again}) == len(again)
    assert next(s for s in again if s["id"] == "a1-d1")["order"] > next(s for s in again if s["id"] == "added-1")["order"]


def test_editing_a_removed_step_is_refused_until_it_is_restored(world):
    seed(world)
    c = login(world, "co-a")
    c.post(f"{MAP}/draw")
    c.delete(f"{MAP}/k1/steps/a1-u0")
    for r in (c.put(f"{MAP}/k1/steps/a1-u0", json={"text": "x"}), c.post(f"{MAP}/k1/steps/a1-u0/validate")):
        assert r.status_code == 409 and "Restore the step first" in r.json()["message"]
    assert kpi_view(c)["removed"] == 1


ROUTES = [("get", ""), ("post", "/draw"), ("post", "/k1/steps"), ("post", "/k1/steps/a1-u0/validate"), ("put", "/k1/steps/a1-u0"),
          ("delete", "/k1/steps/a1-u0"), ("put", "/k1/tracking")]


@pytest.mark.parametrize("verb,tail", ROUTES)
def test_a_role_without_access_is_refused_on_every_process_map_route(world, verb, tail):
    seed(world)
    c = login(world, "co-a", name="Other Person", roles=("participant",))
    assert getattr(c, verb)(MAP + tail, **({} if verb in ("get", "delete") else {"json": {"lane": "A", "text": "b", "status": "partly"}})).status_code == 403
    assert c.get(MAP + "/not-declared/extra/route").status_code in (403, 404)


# ---- a restricted measure is not in the map for anyone not named (defect 2)

def test_the_map_leaves_out_a_restricted_measure_its_steps_definition_and_owner_names(world):
    secret = {"id": "k2", "name": "Bonus pool", "definition": prov("Pay plus the HR top-up", "stated", "Lina Ho"),
              "owners": {"data": prov("Lina Ho", "stated", "Lina Ho")},
              "governance": {"personal": "yes", "sensitive": True, "may_see": ["Test Ann Analyst"]}}
    answer = {**ANSWER, "id": "a2", "kpi_id": "k2", "owner_name": "Lina Ho",
              "in_between": S([{"who": S("Payroll"), "step": S("Adds the HR top-up"), "manual": S(True)}], by="Lina Ho")}
    seed(world, kpis=(KPI, secret), answers=(ANSWER, answer))
    admin = login(world, "co-a")
    full = admin.get(MAP).json()
    assert [k["id"] for k in full["kpis"]] == ["k1", "k2"]
    nick = login(world, "co-a", "Nick Nobody", ("analyst",))
    out = json.dumps(nick.get(MAP).json())
    assert "Bonus pool" not in out and "HR top-up" not in out and "Lina Ho" not in out and "k2" not in out
    assert [k["id"] for k in nick.get(MAP).json()["kpis"]] == ["k1"]
    for call in (lambda: nick.post(f"{MAP}/k2/steps", json={"lane": "Payroll", "text": "x"}),
                 lambda: nick.put(f"{MAP}/k2/tracking", json={"status": "tracked_now"}),
                 lambda: nick.delete(f"{MAP}/k2/steps/anything")):
        assert call().status_code == 403  # P3: hidden but real is refused plainly, not "not found"
    drawn = nick.post(f"{MAP}/draw").json()                                         # a redraw by someone who cannot see it skips it
    assert [k["id"] for k in drawn["kpis"]] == ["k1"]
    assert not admin.get(MAP).json()["kpis"][1]["drawn"]
    ann = login(world, "co-a", "Ann Analyst", ("analyst",))                         # named in governance: sees it
    assert [k["id"] for k in ann.get(MAP).json()["kpis"]] == ["k1", "k2"]
