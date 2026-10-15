"""LI-OUTCOMES: the outcomes numbers of one company. Synthetic data only; the planes are written by path, as the modules write them."""
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform import outcomes as O
from sh_platform.app import create_app
from sh_platform.plane import PlaneStore
from sh_platform.profile import record, record_card
from sh_platform.profile.view import Viewer
from sh_platform.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
FAMILY, MUTUAL = "lakeside-family-office", "harbor-mutual"
ADMIN, ANYONE = Viewer("Mei Tan", frozenset({"company_admin"})), Viewer("Wei Chen", frozenset({"participant"}))
T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
SID, BID, AID, OID = "a" * 32, "b" * 32, "c" * 32, "d" * 32
LENS = {"mark": "stated", "by": "Lens", "from": "A list"}


def put(plane, rel: str, data) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def iso(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


def card(plane, cid: str, author: str, minutes: float, cluster: str | None = None, sealed: bool = False, text: str = "A thing we track") -> None:
    record_card(plane, {"id": cid, "lane": "tracking", "sealed": sealed, "anonymous": False, "author": author, "q1": text,
                        **({"cluster": cluster} if cluster else {})}, by=author)
    path = plane.path("context", "profile", "profile.json")  # the card's own time: the cells carry `at`
    doc = json.loads(path.read_text(encoding="utf-8"))
    for cell in doc["cards"][cid].values():
        cell["at"] = iso(minutes)
    path.write_text(json.dumps(doc), encoding="utf-8")


def kpi(kid: str, personal: str = "no", confirmed: bool = False, changed: bool = False) -> dict:
    src = "edited by Priya" if changed else "confirmed by the data owner (a draft)"
    parts = {p: {"value": "x", "mark": "stated", "by": "Sara", "from": src} for p in O.NEEDED}
    return {"id": kid, "governance": {"personal": personal, "sensitive": False}, "technical": parts,
            **({"technical_confirmed": {"by": "Sara", "at": iso(0)}} if confirmed else {})}


def trial(result: str, minutes: float = 600) -> dict:
    return {"result": result, "computed_at": iso(minutes)}


@pytest.fixture
def planes(tmp_path):
    return PlaneStore(tmp_path / "planes")


def demo(plane, industry_note: str = "Weekly report") -> None:
    """A company part way through: files, interviews not done, one room, cards, a baseline of four measures (one restricted), a trial."""
    record(plane, "inputs.g1.documents", [{"id": "f1", "name": "people.xlsx", "restricted": False}], {**LENS, "at": iso(0)})
    record(plane, "inputs.g2.documents", [{"id": "f2", "name": "systems.xlsx", "restricted": False}], {**LENS, "at": iso(60)})
    put(plane, f"intents/m1_intent/sessions/{SID}.json", {"id": SID, "state": "closed", "outcome_id": OID,
                                                          "inputs": {"actions": 9, "free_text": 2, "cards_new": 1}})
    put(plane, f"intents/m1_intent/stages/{SID}.json", {"started": {"private_rooms": (T0 + timedelta(days=1)).timestamp()}})
    put(plane, f"intents/m1_intent/outcomes/{OID}.json", {"signed_at": iso(24 * 60 + 90)})
    start = 24 * 60
    card(plane, "k1", "Wei Chen", start + 2, cluster="late reports", text=industry_note)
    card(plane, "k2", "Wei Chen", start + 4, cluster="late reports")
    card(plane, "k3", "Sara Lim", start + 20, cluster="data gaps")
    put(plane, f"intents/m2_baseline/outcomes/{OID}.json", {"signed_at": iso(3 * 24 * 60), "baseline_id": BID})
    put(plane, f"intents/m2_baseline/{BID}/kpis.json", [kpi("m1", confirmed=True), kpi("m2", confirmed=True, changed=True), kpi("m3"),
                                                       kpi("secret", personal="yes", confirmed=True)])
    put(plane, f"intents/m2_baseline/{BID}/governed_state.json", {"m1": {"owners": {"mark": "stated"}}, "m2": {"owners": {"mark": "guessed"}},
                                                                 "secret": {"owners": {"mark": "stated"}}})
    ad = f"intents/m3_connect/assessments/{AID}"
    put(plane, f"{ad}/assessment.json", {"id": AID, "created_at": iso(4 * 24 * 60)})
    put(plane, f"{ad}/trial.json", {"m1": trial("matches", 5 * 24 * 60), "m2": trial("gap"), "secret": trial("matches", 1)})
    put(plane, f"{ad}/rules.json", {"m1": {"auto_checked": True}, "secret": {"auto_checked": True}})
    put(plane, f"{ad}/inputs_count.json", {"actions": {"upload": 5}, "actions_total": 5, "free_text": 1})
    put(plane, f"{ad}/plan.json", {"signed_at": iso(6 * 24 * 60), "signatures": [{}]})


def test_an_empty_company_is_all_not_yet(planes):
    out = O.build(planes.create(FAMILY), ADMIN, [])
    h = out["headline"]
    assert {k: v for k, v in h.items() if k != "stage"} == {k: None for k in h if k != "stage"}
    assert h["stage"] == "Not started"
    assert all(m["actions"] is None and m["free_text"] is None and m["minutes"] is None for m in out["modules"])
    assert out["funnel"] == {"cards": 0, "clusters": 0, "measures": 0, "owned": 0, "matching": 0}


@pytest.mark.parametrize("company", [FAMILY, MUTUAL])
def test_a_company_part_way_through_two_industries(planes, company):
    plane = planes.create(company)
    demo(plane, "Weekly report" if company == FAMILY else "Claims backlog")
    out = O.build(plane, ADMIN, ["Wei Chen"])
    h = out["headline"]
    assert h["days_file_to_match"] == 5.0                      # first file at T0, first match at day 5
    assert h["days_card_to_report"] == 5.0                     # first card two minutes into day 1, plan signed on day 6
    assert h["stage"] is None                                  # the plan is signed
    assert h["definitions_unchanged"] == {"unchanged": 1, "of": 2}
    assert h["match"] == {"matches": 1, "gap": 1, "cannot": 0, "not_yet": 1, "restricted": 1}
    assert h["cards_first_five"] == 1.0                        # two of Wei's cards in five minutes, two named people
    assert h["files_read"] == 2 and h["interviews"] is None and h["drafts_accepted"] == 2
    assert out["modules"][0] == {"module": "m1_intent", "actions": 9, "free_text": 2, "minutes": 90 - 0}
    assert out["modules"][2]["actions"] == 5 and out["modules"][2]["minutes"] == 2 * 24 * 60
    assert out["funnel"] == {"cards": 3, "clusters": 2, "measures": 3, "owned": 1, "matching": 1}


def test_before_the_plan_is_signed_the_stage_is_named(planes):
    plane = planes.create(FAMILY)
    demo(plane)
    plane.path("intents", "m3_connect", "assessments", AID, "plan.json").unlink()
    plane.path("intents", "m2_baseline", "outcomes", f"{OID}.json").unlink()
    h = O.build(plane, ADMIN, [])["headline"]
    assert h["days_card_to_report"] is None and h["stage"] == "Define strategically"


def test_nothing_restricted_is_counted_or_named(planes):
    plane = planes.create(FAMILY)
    demo(plane)
    record(plane, "governance.restricted_areas.pay.area", "Pay", LENS)
    record(plane, "governance.restricted_areas.pay.may_see", ["Mei Tan"], LENS)
    card(plane, "s1", "Sara Lim", 24 * 60 + 3, text="Pay for the team is wrong", sealed=True)
    as_admin, as_other = O.build(plane, ADMIN, []), O.build(plane, ANYONE, [])
    assert as_admin["funnel"]["cards"] == 4 and as_other["funnel"]["cards"] == 3   # a sealed card is counted only for who may open it
    assert as_other["headline"]["match"] == as_admin["headline"]["match"]          # a restricted measure is counted for nobody, only as one number
    text = json.dumps([as_admin, as_other])
    for word in ("secret", "Pay", "Wei", "Sara", "Mei", "late reports", AID, BID, SID, OID):
        assert word not in text


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    root = tmp_path_factory.mktemp("oc_seeded") / "data"
    spec = importlib.util.spec_from_file_location("oc_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    result = mod.seed(root)
    pw = {}
    for line in result["path"].read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            email, password = line.split()[:2]
            pw[email] = password
    return root, pw


@pytest.fixture
def client(seeded, tmp_path):
    root, pw = seeded
    shutil.copytree(root, tmp_path / "data")
    settings = load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(tmp_path / "data"), "SH_SESSION_SECRET": "FAKE-outcomes-secret-0123456789-abcdefghij"},
                             env_file=tmp_path / "none.env")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>OC</title>", encoding="utf-8")
    app = create_app(settings, dist_dir=dist)

    def login(role: str) -> TestClient:
        email = f"{role}.{FAMILY}@example.test"
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
        return c
    return login


@pytest.mark.parametrize("role", ["company_admin", "sponsor", "analyst", "approver", "owner"])
def test_the_route_answers_these_roles(client, role):
    r = client(role).get("/api/company/outcomes")
    assert r.status_code == 200 and set(r.json()) == {"headline", "modules", "funnel"}


def test_a_participant_and_a_signed_out_visitor_are_refused(client, seeded, tmp_path):
    assert client("participant").get("/api/company/outcomes").status_code == 403
    assert TestClient(create_app(load_settings({"SH_MODE": "dev", "SH_DATA_ROOT": str(seeded[0]), "SH_SESSION_SECRET": "FAKE-outcomes-secret-0123456789-abcdefghij"},
                                               env_file=tmp_path / "none.env"), dist_dir=tmp_path)).get("/api/company/outcomes").status_code in (401, 403)
