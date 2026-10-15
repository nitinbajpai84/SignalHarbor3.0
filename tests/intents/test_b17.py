"""B17: the catalogue and the governed state from an Initiative. Synthetic records in a temporary company plane (module 2's own files)."""
import json

import pytest

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import governed as G
from modules.m2_baseline.store import governed as GS
from sh_platform.intents import catalogue as X
from sh_platform.plane import PlaneStore

BID = "e" * 32
AT = "2026-10-03T10:00:00+00:00"
ADMIN = C.Viewer("Janet Shaw", frozenset({"company_admin"}), account_id="a-janet")
OWNER = C.Viewer("Harvey Rowley", frozenset({"owner"}), account_id="a-harvey")
APPROVER = C.Viewer("Grace Ward", frozenset({"approver"}), account_id="a-grace")
SPONSOR = C.Viewer("Daniel Kerr", frozenset({"sponsor"}), account_id="a-daniel")
OUTSIDER = C.Viewer("Aaron Lyle", frozenset({"participant"}), account_id="a-aaron")


def cell(v):
    return {"value": v, "mark": "stated", "by": "Janet Shaw", "from": "nominated", "at": AT}


def kpi(code, name, priority="must", data="Harvey Rowley", personal="no", may_see=()):
    return {"id": code, "name": name, "problem_ids": [], "priority": priority,
            "definition": cell(f"{name} definition"),
            "owners": {"business": cell("Harvey Rowley"), "data": cell(data), "process": {"value": None, "mark": "unknown"}},
            "governance": {"personal": personal, "sensitive": False, "may_see": list(may_see)}}


@pytest.fixture
def plane(tmp_path):
    p = PlaneStore(tmp_path / "planes").create("ardmore")
    folder = p.path("intents", "m2_baseline", BID)
    folder.mkdir(parents=True)
    (folder / "baseline.json").write_text(json.dumps({"id": BID, "state": "mapping", "created_at": "2026-10-03"}))
    (folder / "kpis.json").write_text(json.dumps([kpi("K01", "Total AUM"), kpi("K02", "Fee income", "should"),
                                                   kpi("K03", "Pay review", "must", personal="yes", may_see=["Janet Shaw"])]))
    (folder / "catalogue.json").write_text(json.dumps({}))
    return p


def test_one_node_per_code_and_name_is_a_label(plane):
    assert X.node_ids(plane, BID) == ["measure:K01", "measure:K02", "measure:K03"]
    with pytest.raises(X.Refused) as e:  # the same name in other words is refused with the code it matches
        X.mint(plane, BID, "total  aums", "Janet Shaw")
    assert e.value.status == 409 and "K01" in e.value.message
    row = X.mint(plane, BID, "Assets held", "Janet Shaw")
    assert row["code"] == "M-1"
    X.set_label(plane, BID, "K01", "Assets under management", "Janet Shaw")  # a rename keeps the code, the old label becomes an alias
    reg = {r["code"]: r for r in X.register(plane, BID)}
    assert reg["K01"]["label"] == "Assets under management" and "Total AUM" in reg["K01"]["aliases"]
    assert X.duplicate_of(X.register(plane, BID), "TOTAL AUM")["code"] == "K01"  # an alias finds the one code
    assert sorted(X.node_ids(plane, BID)) == ["measure:K01", "measure:K02", "measure:K03", "measure:M-1"]
    assert all(i.split(":")[1] in reg for i in X.node_ids(plane, BID))  # an id is never a name


def test_merge_leaves_one_live_node(plane):
    X.mint(plane, BID, "Assets held", "Janet Shaw")
    X.merge(plane, BID, "K01", "M-1", "Janet Shaw")
    reg = {r["code"]: r for r in X.register(plane, BID)}
    assert reg["M-1"]["merged_into"] == "K01" and "M-1" in reg["K01"]["aliases"] and "Assets held" in reg["K01"]["aliases"]
    assert "measure:M-1" not in X.node_ids(plane, BID)
    assert X.blockers(plane, BID) == []
    assert X.entry_view(plane, BID, "M-1", ADMIN)["code"] == "K01"  # the retired code redirects to the survivor


def test_merge_retires_the_later_code_whichever_way_asked(plane):
    X.mint(plane, BID, "Assets held", "Janet Shaw")
    X.mint(plane, BID, "Assets kept", "Janet Shaw")
    X.merge(plane, BID, "M-2", "M-1", "Janet Shaw")
    reg = {r["code"]: r for r in X.register(plane, BID)}
    assert reg["M-2"]["merged_into"] == "M-1" and reg["M-1"]["merged_into"] is None


def test_my_measures_shows_no_restricted_rows(plane):
    rows = X.catalogue_view(plane, BID, OUTSIDER, owner_me=True)["measures"]
    assert rows == []


def test_graph_guard_blocks_a_name_minted_node_and_a_shared_name():
    nodes = {"measure:K01": {"type": "Measure", "label": "Total AUM"}, "measure:total-aum": {"type": "Measure", "label": "total aum"}}
    out = X.graph_blockers(nodes, {"K01"})
    assert any("no code" in b for b in out) and any("share the name" in b for b in out)
    assert X.graph_blockers({"measure:K01": nodes["measure:K01"]}, {"K01"}) == []


def test_six_fields_confirmed_only_by_the_named_role(plane):
    want = {"owners": OWNER, "classification": APPROVER, "may_see": APPROVER, "resolving": SPONSOR, "affects": OWNER, "review_date": OWNER}
    values = {"owners": {"business": "Harvey Rowley", "data": "Harvey Rowley", "process": None}, "classification": "open", "may_see": [],
              "resolving": {"team": "Finance", "target_week": 4}, "affects": ["Fee income"], "review_date": "2027-01-04"}
    for field, who in want.items():
        for other in (ADMIN, OUTSIDER):  # the organiser confirms nothing for others
            with pytest.raises(C.CatalogueError) as e:
                GS.confirm_field(plane, BID, "K01", field, values[field], other)
            assert e.value.message == G.REFUSED
        entry = GS.confirm_field(plane, BID, "K01", field, values[field], who)
        assert entry[field]["mark"] == "stated" and entry[field]["by"] == who.name
    view = X.governed_view(plane, BID, OWNER)
    assert view["measures"][0]["can_confirm"]["owners"] is True and view["measures"][0]["can_confirm"]["classification"] is False


def test_percentages_traced_and_must_needs_all_six(plane):
    v = X.governed_view(plane, BID, ADMIN)
    assert v["strip"]["owned"] == {"n": 0, "of": 3, "pct": 0}
    assert v["must"] == {"n": 0, "of": 2} and {m["id"] for m in v["not_governed"]} == {"K01", "K03"}
    GS.confirm_field(plane, BID, "K01", "owners", {"business": "Harvey Rowley", "data": None, "process": None}, OWNER)
    GS.confirm_field(plane, BID, "K01", "classification", "open", APPROVER)
    v = X.governed_view(plane, BID, ADMIN)
    assert v["strip"]["owned"] == {"n": 1, "of": 3, "pct": 33} and v["strip"]["classified"]["n"] == 1 and v["strip"]["team_assigned"]["n"] == 0
    assert v["must"]["n"] == 0  # two of six stated is not governed
    row = next(m for m in v["measures"] if m["id"] == "K01")
    assert row["n"] == 2 and row["needs"] == ["who may see", "resolving team", "affected downstream", "review date"]
    GS.confirm_field(plane, BID, "K01", "may_see", [], APPROVER)
    GS.confirm_field(plane, BID, "K01", "resolving", {"team": "Finance", "target_week": 3}, SPONSOR)
    GS.confirm_field(plane, BID, "K01", "affects", [], OWNER)
    GS.confirm_field(plane, BID, "K01", "review_date", "2027-01-04", OWNER)
    v = X.governed_view(plane, BID, ADMIN)
    assert v["must"] == {"n": 1, "of": 2} and [m["id"] for m in v["not_governed"]] == ["K03"]


def test_no_measures_is_not_available_yet(tmp_path):
    p = PlaneStore(tmp_path / "planes").create("ardmore")
    folder = p.path("intents", "m2_baseline", BID)
    folder.mkdir(parents=True)
    (folder / "baseline.json").write_text(json.dumps({"id": BID, "state": "mapping"}))
    (folder / "kpis.json").write_text("[]")
    v = X.governed_view(p, BID, ADMIN)
    assert v["strip"] is None and "Not available yet" in v["empty"]
    c = X.catalogue_view(p, BID, ADMIN)
    assert c["counts"] is None and c["empty"].startswith("No measures yet")


def test_owners_have_one_source(plane):
    GS.confirm_field(plane, BID, "K01", "owners", {"business": "Grace Ward", "data": "Katie", "process": None}, OWNER)
    lst = next(m for m in X.catalogue_view(plane, BID, ADMIN)["measures"] if m.get("code") == "K01")
    ent = X.entry_view(plane, BID, "K01", ADMIN)
    chart = next(m for m in X.charter_view(plane, BID, ADMIN)["measures"] if m["code"] == "K01")
    comp = X.company_owner_map(plane)["k01"]
    assert lst["owner"] == ent["owners"]["data"] == chart["owners"]["data"] == comp["data"] == "Katie"
    assert ent["owners"]["business"] == chart["owners"]["business"] == comp["business"] == "Grace Ward"
    assert GS.governed_for(plane, BID, ADMIN) and X.governed_view(plane, BID, ADMIN)["measures"][0]["owners"]["data"] == "Katie"


def test_confirming_owners_updates_the_measures_own_owners(plane):
    from modules.m2_baseline.store import kpis as K
    GS.confirm_field(plane, BID, "K01", "owners", {"business": "Harvey Rowley", "data": "Katie Rao"}, OWNER)  # process left out keeps its name
    k = next(x for x in K.read_kpis(plane, BID) if x["id"] == "K01")
    assert k["owners"]["data"]["value"] == "Katie Rao" and k["owners"]["business"]["value"] == "Harvey Rowley"
    with pytest.raises(C.CatalogueError):  # Harvey no longer holds the data slot: the check reads the updated owners
        GS.confirm_field(plane, BID, "K01", "owners", {"business": "Harvey Rowley", "data": "Harvey Rowley"}, OWNER)


def test_applying_an_owners_proposal_updates_the_measures_owners_and_keeps_left_out_slots(plane):
    from modules.m2_baseline.store import kpis as K
    GS.confirm_field(plane, BID, "K01", "owners", {"business": "Harvey Rowley", "data": "Harvey Rowley"}, OWNER)
    X.propose(plane, BID, "K01", "owners", {"business": "Harvey Rowley", "data": "Katie Rao"}, "new data owner", ADMIN, "i1")
    entry = X.decide(plane, BID, "K01", "owners", "apply", None, OWNER)
    k = next(x for x in K.read_kpis(plane, BID) if x["id"] == "K01")
    assert entry["owners"]["value"]["data"] == k["owners"]["data"]["value"] == "Katie Rao" and k["owners"]["business"]["value"] == "Harvey Rowley"


def test_a_restricted_measure_is_hidden_from_others(plane):
    rows = X.catalogue_view(plane, BID, OUTSIDER)["measures"]
    assert {"restricted": True, "label": X.RESTRICTED} in rows
    assert "K03" not in json.dumps(rows) and "Pay review" not in json.dumps(rows)
    assert X.catalogue_view(plane, BID, OUTSIDER)["counts"]["not_drafted"] == 2
    with pytest.raises(X.Refused) as e:
        X.entry_view(plane, BID, "K03", OUTSIDER)
    assert e.value.status == 404
    assert "K03" not in json.dumps(X.charter_view(plane, BID, OUTSIDER)) and "K03" not in json.dumps(X.governed_view(plane, BID, OUTSIDER))
    assert X.entry_view(plane, BID, "K03", ADMIN)["label"] == "Pay review"


def test_entry_state_and_trail(plane):
    assert X.entry_view(plane, BID, "K01", ADMIN)["state"] == "not_drafted"
    from modules.m2_baseline.store import technical as ST
    sees = ST.sees_for(OWNER)
    for part, val in (("calculation", "month end holdings"), ("sources", []), ("fields", [])):
        ST.edit(plane, BID, "K01", part, val, "stated", "Katie", ADMIN, ST.sees_for(ADMIN))
    assert X.entry_view(plane, BID, "K01", ADMIN)["state"] == "draft"
    e = X.entry_view(plane, BID, "K01", ADMIN)
    assert e["missing"] and not e["can_confirm"]  # Sources and Fields are still empty: confirm stays disabled


def test_proposal_waits_until_the_named_person_applies_it(plane):
    GS.confirm_field(plane, BID, "K01", "classification", "open", APPROVER)
    with pytest.raises(X.Refused):  # a part nobody has confirmed cannot be proposed
        X.propose(plane, BID, "K01", "may_see", [], "why", ADMIN)
    X.propose(plane, BID, "K01", "classification", "personal", "It holds names", ADMIN, "i1")
    assert GS._read(plane, BID)["K01"]["classification"]["value"] == "open"
    assert X.governed_view(plane, BID, APPROVER)["measures"][0]["proposals"]["classification"]["by"] == "Janet Shaw"
    with pytest.raises(X.Refused) as e:
        X.decide(plane, BID, "K01", "classification", "apply", None, ADMIN)
    assert e.value.status == 403
    entry = X.decide(plane, BID, "K01", "classification", "apply", None, APPROVER)
    assert entry["classification"]["value"] == "personal" and entry["history"]["classification"][0]["cell"]["value"] == "open" and "classification" not in entry["proposals"]


ACCOUNTS = [{"account_id": "a-katie", "display_name": "Katie Rao", "roles": ["analyst"], "disabled": False},
            {"account_id": "a-harvey", "display_name": "Harvey Rowley", "roles": ["owner"], "disabled": False}]
KATIE = C.Viewer("Katie Rao", frozenset({"analyst"}), account_id="a-katie")


def test_a_minted_measure_is_seen_by_the_analyst_and_named_owners(plane):
    X.mint(plane, BID, "Assets held", "Janet Shaw")
    assert X.entry_view(plane, BID, "M-1", ADMIN) and not any(r.get("code") == "M-1" for r in X.catalogue_view(plane, BID, OWNER)["measures"])
    X.share(plane, BID, ACCOUNTS)
    assert any(r.get("code") == "M-1" for r in X.catalogue_view(plane, BID, KATIE)["measures"])
    assert not any(r.get("code") == "M-1" for r in X.catalogue_view(plane, BID, OWNER)["measures"])  # nobody named yet
    from modules.m2_baseline.store import kpis as K
    K.change(plane, BID, "M-1", lambda k: {**k, "owners": {**k["owners"], "data": {"value": "Harvey Rowley", "mark": "stated", "by": "Janet Shaw", "from": "x", "at": AT, "account_id": "a-harvey"}}})
    X.share(plane, BID, ACCOUNTS)
    assert any(r.get("code") == "M-1" for r in X.catalogue_view(plane, BID, OWNER)["measures"])
    assert next(k for k in K.read_kpis(plane, BID) if k["id"] == "K03")["governance"]["may_see"] == ["Janet Shaw"]  # a seeded measure is left alone


def test_owners_confirmed_in_the_governed_state_become_named_owners_one_slot_each(plane):
    X.mint(plane, BID, "Assets held", "Janet Shaw")
    from modules.m2_baseline.store import kpis as K
    K.change(plane, BID, "M-1", lambda k: {**k, "owners": {**k["owners"], "data": {"value": "Katie Rao", "mark": "stated", "by": "Janet Shaw", "from": "x", "at": AT, "account_id": "a-katie"}}})
    X.share(plane, BID, ACCOUNTS)
    k = next(x for x in K.read_kpis(plane, BID) if x["id"] == "M-1")
    state = {"owners": {"value": None, "mark": "unknown"}}
    prof = {}
    assert X.owner_slots(k, state, prof, KATIE) == {"business": False, "data": True, "source": False}  # the data owner may not confirm the business slot
    assert X.owner_slots(k, state, prof, ADMIN) == {"business": False, "data": False, "source": False}  # the organiser confirms for nobody
    doc = GS._read(plane, BID)
    doc["M-1"] = {**G.blank(), "owners": G.person_cell({"business": "Harvey Rowley", "data": "Katie Rao", "process": None}, "Katie Rao")}
    GS.B.write_file(GS._file(plane, BID), doc)
    X.adopt_owners(plane, BID, ACCOUNTS)
    k = next(x for x in K.read_kpis(plane, BID) if x["id"] == "M-1")
    assert k["owners"]["business"]["value"] == "Harvey Rowley" and k["owners"]["business"]["account_id"] == "a-harvey"
    assert k["owners"]["data"]["by"] == "Janet Shaw"  # a person the organiser named is not replaced
    assert G.named_owner(k, OWNER) and X.owner_slots(k, doc["M-1"], prof, OWNER)["business"] is True


def test_the_trail_leaves_out_lines_of_other_baselines_with_the_same_code(plane):
    from sh_platform.graph.versions import append_version
    append_version(plane, "measure:K01", "Renamed in another baseline", "Someone", "f" * 32)
    append_version(plane, "measure:K01", "Linked in a build", "The record", "build-7")
    append_version(plane, "measure:K01", "Alias added here", "Janet Shaw", BID)
    text = " ".join(t["text"] for t in X.entry_view(plane, BID, "K01", ADMIN)["trail"])
    assert "another baseline" not in text and "Alias added here" in text and "Linked in a build" in text


def test_the_data_owner_confirms_only_their_slot_in_the_m2_check(plane):
    X.mint(plane, BID, "Assets held", "Janet Shaw")
    from modules.m2_baseline.store import kpis as K
    K.change(plane, BID, "M-1", lambda k: {**k, "owners": {**k["owners"], "data": {"value": "Katie Rao", "mark": "stated", "by": "Janet Shaw", "from": "x", "at": AT, "account_id": "a-katie"}}})
    k = next(x for x in K.read_kpis(plane, BID) if x["id"] == "M-1")
    G.check_confirm("owners", k, {}, KATIE, {"business": None, "data": "Katie Rao", "process": None}, {"value": None, "mark": "unknown"})
    with pytest.raises(C.CatalogueError):
        G.check_confirm("owners", k, {}, KATIE, {"business": "Harvey Rowley", "data": "Katie Rao", "process": None}, {"value": None, "mark": "unknown"})
