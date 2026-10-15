"""Helpers for the M2-P05 tests (no tests here). Fixtures of baseline.json, kpis.json, answers.json, process_map.json and
catalogue.json in the SHARED.md shapes, written where the stand-in read functions look until M2-P01 to M2-P04 land.
Family-office wording only as example text. Every person is a throwaway test account."""
import json

from m2_kit import BASE, login
from modules.m2_baseline.domain import glossary as G
from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.domain.provenance import prov, unknown

BID = "c" * 32  # a real baseline id is 32 hex characters (store.baseline.is_id)
PEOPLE = {"bea": "Business Bea", "dan": "Data Dan", "pia": "Process Pia", "sam": "Sponsor Sam", "hana": "Head Hana"}


def me(key: str) -> str:
    """The name the account store shows for this person (make_test_account adds "Test ")."""
    return f"Test {PEOPLE[key]}"


class Team:
    """One account per person: three owners, a sponsor, the head of data, an analyst."""

    def __init__(self, world, company="co-a"):
        self.world, self.company = world, company
        roles = {"bea": ("owner",), "dan": ("owner",), "pia": ("owner",), "sam": ("sponsor",), "hana": ("company_admin",)}
        self.c = {k: login(world, company, PEOPLE[k], roles[k]) for k in PEOPLE}
        self.analyst = login(world, company, "Analyst Al", ("analyst",))

    def url(self, tail="", bid=BID) -> str:
        return f"{BASE}/baselines/{bid}{tail}"


def stated(value, by="Test Business Bea", source="meeting"):
    return prov(value, "stated", by, source)


def kpi(id_, name, owners=("bea", "dan", "pia"), tracking="tracked_now", tracking_mark="stated", definition=True, ready=True):
    """`ready`: the technical definition is complete and confirmed by the data owner, so the measure is ready to build (M2-E4); the rest of a ready
    baseline is the glossary reviewed (seed), governance decided (CATALOGUE) and no open question."""
    o = {}
    for role, key in zip(("business", "data", "process"), owners):
        o[role] = unknown("Lens") if key is None else (prov("A Name Lens Guessed", "guessed", "Lens") if key == "guess" else stated(me(key)))
    k = {"id": id_, "name": name, "problem_ids": ["c1"], "priority": "must",
         "definition": stated(f"{name}, as the office defines it") if definition else unknown("Lens"),
         "owners": o, "governance": {"personal": "no", "sensitive": False, "may_see": []},
         "tracking": prov(tracking, tracking_mark, "Test Data Dan", "meeting") if tracking_mark != "unknown" else unknown("Lens")}
    if ready:
        for part, v in (("sources", ["S01"]), ("fields", ["F001"]), ("calculation", "1. Take F001.")):
            k = T.set_part(k, part, v, "stated", "Test Data Dan")
        k = T.confirm(k, "Test Data Dan")
    return k


def answer(kpi_id, source="Custodian portal export", tracked="yes", dtype="structured", arrival="Daily by noon", by="Test Data Dan"):
    def f(v):
        return unknown(by) if v is None else prov(v, "stated", by, "meeting")
    return {"id": f"a-{kpi_id}", "meeting": "kickoff", "owner_name": by, "kpi_id": kpi_id, "tracked_today": f(tracked),
            "could_track": f("yes"), "source": f(source), "data_type": f(dtype), "arrival": f(arrival), "sla": f(None),
            "dependencies": f(None), "sample_doc_id": None, "upstream": [], "in_between": [], "downstream": []}


def standard_kpis():
    return [kpi("K1", "Capital call timeliness"),
            kpi("K2", "Exposure concentration", tracking="not_tracked"),
            kpi("K3", "Manager fee reconciliation", owners=(None, "dan", "pia"))]


def standard_answers(everyone=False):
    """Dan's answers. `everyone`: Bea and Pia answered the same (a part is confirmed only by an owner who answered, N-D)."""
    one = [answer("K1"), answer("K2", source=None, tracked="no", arrival=None)]  # K3 is blocked: no owner, no answers asked
    twins = [{**a, "id": f"{a['id']}-{key}", "owner_name": me(key)} for key in ("bea", "pia") for a in one] if everyone else []
    return one + twins


CATALOGUE = {
    "sources": [{"Source ID": prov("S01", "stated", "Test Data Dan"), "Source name": prov("Custodian portal", "stated", "Test Data Dan"),
                 "Availability": unknown("Lens"), "Contains personal data?": prov("No", "stated", "Test Data Dan")}],
    "tables": [{"Item ID": prov("T01", "stated", "Test Data Dan"), "Name of table, file or document type": prov("", "guessed", "Lens"),
                "Related KPIs": prov("K1", "stated", "Test Data Dan")}],
    "fields": [], "extractions": [], "kpis": [],
}
PROCESS_MAP = {"K1": {"lanes": ["Operations", "Finance"], "steps": [
    {"id": "s1", "lane": "Operations", "text": "Capital call notice received", "order": 1, "manual": True, "confirmed": True,
     "from": "answer a-K1", "state": "validated", "by": "Test Process Pia"}]}}


def reviewed_glossary(kpis: list[dict]) -> dict:
    """glossary.json with every measure's entry reviewed (the glossary half of the ready-to-build gate)."""
    entries, _ = G.build_entries(kpis, [], {}, "", [], "2026-10-03T10:00:00+00:00")
    return {"baseline_version": 1, "provided": None, "matches": {}, "unmatched_terms": [], "rejected": [], "documents": [], "restricted_kept": 0,
            "entries": [G.reviewed(e, "Test Pat Owner", "2026-10-03T10:00:00+00:00") for e in entries]}


def seed(world, company="co-a", bid=BID, kpis=None, answers=None, catalogue=None, process_map=None, baseline=True, silent=False, glossary=True):
    """Writes the fixture files for one baseline into the company's plane. By default every owner has answered; `silent`:
    only Dan has."""
    answers = standard_answers(everyone=not silent) if answers is None else answers
    folder = world.plane(company).path("intents", "m2_baseline", bid)
    folder.mkdir(parents=True, exist_ok=True)
    files = {"kpis.json": standard_kpis() if kpis is None else kpis, "answers.json": answers,
             "catalogue.json": CATALOGUE if catalogue is None else catalogue,
             "process_map.json": PROCESS_MAP if process_map is None else process_map}
    if glossary:
        files["glossary.json"] = reviewed_glossary(files["kpis.json"])
    if baseline:
        files["baseline.json"] = {"id": bid, "charter_outcome_id": "c" * 32, "state": "review", "created_at": "2026-10-03T10:00:00+00:00"}
    for name, data in files.items():
        (folder / name).write_text(json.dumps(data))


def everyone_answers(team, kpi_ids, bid=BID):
    """A part can be confirmed only by an owner who answered (N-D): add an answer for each owner who has none yet."""
    path = team.world.plane(team.company).path("intents", "m2_baseline", bid, "answers.json")
    rows = json.loads(path.read_text())
    for k in kpi_ids:
        for key in ("bea", "dan", "pia"):
            if not any(r["kpi_id"] == k and r["owner_name"] == me(key) for r in rows):
                twin = next((r for r in rows if r["kpi_id"] == k), answer(k))  # same answers as the first, under this owner's name
                rows.append({**twin, "id": f"a-{k}-{key}", "owner_name": me(key)})
    path.write_text(json.dumps(rows))


def confirm_all(team, kpi_ids=("K1", "K2")):
    everyone_answers(team, kpi_ids)
    for k in kpi_ids:
        for who, part in (("bea", "definition"), ("dan", "source"), ("pia", "process")):
            r = team.c[who].post(team.url("/confirm"), json={"kpi_id": k, "part": part})
            assert r.status_code == 200 or r.json()["error"] == "already_confirmed", r.text


def sign_both(team):
    a = team.c["sam"].post(team.url("/countersign"))
    b = team.c["hana"].post(team.url("/countersign"))
    return a, b
