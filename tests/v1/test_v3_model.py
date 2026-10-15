"""Harbor 3.0 industry model: two industries, an empty company, admitting a proposal, and no leak from one office to another.
Synthetic data only; the pack comes from packs/<industry>/1/model.yaml through the pack loader."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.entitlements import EntitlementStore  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_model as M  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

REQUIRED = ("name", "label", "table", "properties", "relations")


@pytest.fixture()
def root(tmp_path):
    es = EntitlementStore(tmp_path)
    for cid, industry in (("fo-a", "family_office"), ("fo-b", "family_office"), ("ins-a", "insurance"), ("none-a", "retail"), ("blank-a", "")):
        es.create_company(cid, cid, industry or "unset")
    return tmp_path


def plane(root, cid):
    return PlaneStore(root).plane_for(cid)


def mapping(pl, mid, cols, sheet="Holdings", state="approved"):
    """A 2.0 intake mapping written the way e0b_mappings stores it; columns are (source, 'table.field' or '')."""
    d = pl.path("model", "mappings")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mid}.json").write_text(json.dumps({"id": mid, "state": state, "file_pattern": "holdings_*.xlsx", "sheet": sheet, "version": 1, "layout": [c[0] for c in cols],
                                               "columns": [{"source": s, "target_table": t.partition(".")[0], "target_field": t.partition(".")[2]} for s, t in cols]}),
                                   encoding="utf-8")


def test_each_pack_model_is_well_formed_and_versioned():
    from sh_platform.packs import PackLoader
    loader = PackLoader(M._packs_root())
    for industry in ("family_office", "insurance", "asset_management"):
        doc = loader.load(industry).section("model")
        assert doc["version"] == 1 and doc["objects"]
        names = {o["name"] for o in doc["objects"]}
        for o in doc["objects"]:
            assert all(k in o for k in REQUIRED)
            assert all({"name", "label", "type", "synonyms"} <= set(p) for p in o["properties"])
            assert all(r["to"] in names for r in o["relations"]), (industry, o["name"])


def test_family_office_and_insurance_start_on_their_own_model(root):
    fo, ins = M.model(plane(root, "fo-a")), M.model(plane(root, "ins-a"))
    assert fo["pack"] == {"id": "family_office", "label": "Family office", "version": 1}
    assert {"portfolio", "position", "commitment"} <= {o["name"] for o in fo["objects"]} and all(o["from"] == "industry" for o in fo["objects"])
    assert {"policy", "claim", "premium", "reserve", "reinsurer", "broker", "product", "policyholder"} == {o["name"] for o in ins["objects"]}
    assert not ({o["name"] for o in fo["objects"]} & {"policy", "claim"}), "no insurance content in a family office"
    assert all(o["count"] is None for o in fo["objects"]), "no warehouse, no count"
    assert fo["coverage"] == {"pct": None, "unmapped": []} and fo["proposals"] == [] and fo["versions"] == []
    stale = next(p for o in fo["objects"] if o["name"] == "valuation" for p in o["properties"] if p["name"] == "is_stale")
    assert stale["derived"]


@pytest.mark.parametrize("cid", ["none-a", "blank-a"])
def test_a_company_with_no_pack_gets_an_honest_empty_state(root, cid):
    pl = plane(root, cid)
    mapping(pl, "m0001", [("Fund", "portfolios.portfolio_name")])
    m = M.model(pl)
    assert m["objects"] == [] and m["proposals"] == [] and m["coverage"]["pct"] is None and m["pack"]["label"] is None and m["message"]
    assert M.language(pl)["words"] == [] and M.packs(pl)["current"] in ("retail", "unset")


def test_counts_come_from_the_warehouse_read_only(root):
    pl = plane(root, "fo-a")
    with wh.connect(pl) as con:
        con.execute("insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values "
                    "(uuid(), uuid(), uuid(), 'P1', 'One', 'SGD'), (uuid(), uuid(), uuid(), 'P2', 'Two', 'SGD')")
    objs = {o["name"]: o["count"] for o in M.model(pl)["objects"]}
    assert objs["portfolio"] == 2 and objs["entity"] == 0
    assert M.model(plane(root, "fo-b"))["objects"][0]["count"] is None


def test_coverage_and_proposals_from_the_intake_mappings(root):
    pl = plane(root, "fo-a")
    mapping(pl, "m0001", [("Fund", "instruments.canonical_name"), ("Val Date", "position_snapshots.position_date"), ("Tax lot", "position_snapshots.tax_lot"),
                          ("Notes", ""), ("Side letter", "side_letters.clause")])
    mapping(pl, "m0002", [("Old col", "portfolios.old")], state="rejected")
    m = M.model(pl)
    assert m["coverage"] == {"pct": 40, "unmapped": ["Notes", "Side letter", "Tax lot"]}
    assert {p["property"] for p in m["proposals"]} == {"tax_lot", "clause"}, "one per mapped column with no property; the unplaced Notes column is not a proposal"
    assert any(o["from"] == "proposed" and o["table"] == "side_letters" for o in m["objects"])
    mapping(pl, "m0003", [("Memo", "")], sheet="Memo")
    flagged = json.loads((pl.path("model", "mappings") / "m0003.json").read_text(encoding="utf-8"))
    flagged["columns"][0]["new"] = True
    (pl.path("model", "mappings") / "m0003.json").write_text(json.dumps(flagged), encoding="utf-8")
    assert "memo" in {p["property"] for p in M.model(pl)["proposals"]}, "a new column flagged in intake is proposed too"


def test_admitting_a_proposal_adds_it_to_the_office_layer_with_a_version(root):
    pl = plane(root, "fo-a")
    mapping(pl, "m0001", [("Tax lot", "position_snapshots.tax_lot"), ("Fund", "instruments.canonical_name")])
    pid = M.model(pl)["proposals"][0]["id"]
    m = M.answer_proposal(pl, pid, "admit", "Anita Rao")
    pos = next(o for o in m["objects"] if o["name"] == "position")
    assert next(p for p in pos["properties"] if p["name"] == "tax_lot")["from"] == "office" and pos["from"] == "industry"
    assert m["proposals"] == [] and m["coverage"] == {"pct": 100, "unmapped": []}
    assert m["versions"] == [{"v": 1, "at": m["versions"][0]["at"], "by": "Anita Rao", "change": "Anita Rao admitted tax_lot on Position"}]
    saved = json.loads((root / "fo-a" / "v3" / "model.json").read_text(encoding="utf-8"))
    assert saved["additions"][0]["by"] == "Anita Rao"
    with pytest.raises(KeyError):
        M.answer_proposal(pl, pid, "admit", "Anita Rao")


def test_rejecting_a_proposal_hides_it_without_a_version(root):
    pl = plane(root, "fo-a")
    mapping(pl, "m0001", [("Tax lot", "position_snapshots.tax_lot")])
    m = M.answer_proposal(pl, M.model(pl)["proposals"][0]["id"], "reject", "Anita Rao")
    assert m["proposals"] == [] and m["versions"] == [] and m["coverage"]["unmapped"] == ["Tax lot"]


def test_one_offices_additions_never_show_for_another(root):
    a, b = plane(root, "fo-a"), plane(root, "fo-b")
    mapping(a, "m0001", [("Tax lot", "position_snapshots.tax_lot")])
    M.answer_proposal(a, M.model(a)["proposals"][0]["id"], "admit", "Anita Rao")
    M.add_word(a, "Dry powder", "Cash waiting for calls", "Anita Rao")
    props_b = {p["name"] for o in M.model(b)["objects"] for p in o["properties"]}
    assert "tax_lot" not in props_b and M.model(b)["versions"] == []
    assert "Dry powder" not in {w["word"] for w in M.language(b)["words"]}
    assert not (root / "fo-b" / "v3" / "model.json").exists()
    assert "tax_lot" not in json.dumps(M.model(plane(root, "ins-a")))
    assert "tax_lot" not in (ROOT / "packs" / "family_office" / "1" / "model.yaml").read_text(encoding="utf-8"), "the pack never takes an office's addition"


def test_language_seeds_from_the_pack_and_keeps_office_words(root):
    pl = plane(root, "ins-a")
    lang = M.language(pl)
    gwp = next(w for w in lang["words"] if w["word"] == "Gross written premium")
    assert gwp == {"word": "Gross written premium", "means": "GWP", "by": "from the industry", "used": 0}
    lang = M.add_word(pl, "Gross written premium", "What we book before reinsurance", "Anita Rao")
    mine = [w for w in lang["words"] if w["word"] == "Gross written premium"]
    assert len(mine) == 1 and mine[0]["by"] == "Anita Rao"
    with pytest.raises(ValueError):
        M.add_word(pl, " ", "x", "Anita Rao")
    fo_words = M.language(plane(root, "fo-a"))["words"]
    assert fo_words and "Gross written premium" not in {w["word"] for w in fo_words}


def test_corrections_and_golden_answers(root):
    pl = plane(root, "fo-a")
    cid = M.propose_correction(pl, "Cash means the administrator figure", "What is our cash?", "The administrator figure, SGD 1.2m")
    assert M.language(pl)["corrections"] == [{"id": cid, "text": "Cash means the administrator figure"}]
    lang = M.answer_correction(pl, cid, "admit", "Anita Rao")
    assert lang["corrections"] == [] and lang["golden"][0]["q"] == "What is our cash?" and lang["golden"][0]["by"] == "Anita Rao"
    with pytest.raises(KeyError):
        M.answer_correction(pl, cid, "admit", "Anita Rao")


def test_taught_lists_always_on_notes_and_books_with_their_state(root):
    pl = plane(root, "fo-a")
    idx = pl.path("knowledge", "index.json")
    idx.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": "kn_1", "agent": "lumen", "title": "House rules", "kind": "note", "always": True, "active": True, "version": 2},
            {"id": "kn_2", "agent": "span", "title": "Reconciliation handbook", "kind": "file", "active": False, "version": 1},
            {"id": "kn_3", "agent": "span", "title": "Passing remark", "kind": "note", "active": True, "version": 1}]
    idx.write_text(json.dumps(rows), encoding="utf-8")
    taught = {t["name"]: t for t in M.language(pl)["taught"]}
    assert set(taught) == {"House rules", "Reconciliation handbook"}
    assert taught["House rules"]["on"] is True and taught["House rules"]["version"] == 2 and taught["Reconciliation handbook"] == {
        "name": "Reconciliation handbook", "agent": "span", "books": 1, "always": False, "on": False, "version": 1}


def test_packs_list_counts():
    out = M.packs(type("P", (), {"root": ROOT / "data-none", "company_id": "x"})())
    by = {p["id"]: p for p in out["packs"]}
    assert {"family_office", "insurance", "asset_management"} <= set(by) and by["insurance"]["objects"] == 8 and by["family_office"]["questions"] > 0


# ---- the routes: sign-in, permissions, plain answers -----------------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {ln.split()[0]: ln.split()[1] for ln in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if ln.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    c.data = data
    return c


def test_routes_model_proposal_packs_and_language(client):
    m = client.get("/api/v3/model").json()
    assert m["pack"]["id"] == EG.INDUSTRY and m["objects"] and "coverage" in m
    pl = PlaneStore(client.data).plane_for(EG.COMPANY)
    mapping(pl, "m0001", [("Tax lot", "position_snapshots.tax_lot")])
    pid = client.get("/api/v3/model").json()["proposals"][0]["id"]
    assert client.post(f"/api/v3/model/proposals/{pid}", json={"answer": "maybe"}).status_code == 400
    assert client.post("/api/v3/model/proposals/p-nothing", json={"answer": "admit"}).status_code == 404
    done = client.post(f"/api/v3/model/proposals/{pid}", json={"answer": "admit"}).json()
    assert done["proposals"] == [] and done["versions"][0]["by"]
    assert any(p["id"] == EG.INDUSTRY for p in client.get("/api/v3/packs").json()["packs"]) and client.get("/api/v3/packs").json()["current"] == EG.INDUSTRY
    lang = client.post("/api/v3/language/words", json={"word": "Dry powder", "means": "Cash waiting for calls"}).json()
    assert [w["means"] for w in lang["words"] if w["word"] == "Dry powder"] == ["Cash waiting for calls"]
    assert client.post("/api/v3/language/words", json={"word": "", "means": ""}).status_code == 400
    assert client.post("/api/v3/language/corrections/c-nothing", json={"answer": "admit"}).status_code == 404
    assert set(client.get("/api/v3/language").json()) == {"words", "corrections", "golden", "taught"}
