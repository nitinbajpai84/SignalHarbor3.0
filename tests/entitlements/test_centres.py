"""Centres: named module groups with a company-level switch. Fails closed; an absent key means on."""
import json
from pathlib import Path

import pytest
import yaml

from sh_platform.entitlements import load_catalogue
from gate_kit import REFUSED

CAT = Path(__file__).resolve().parents[2] / "sh_platform" / "catalogue.yaml"
INTENT = ["m1_intent", "m2_baseline", "m3_connect"]


def listing(c):
    return c.get("/api/modules").json()


def test_catalogue_declares_intent_and_two_empty_centres():
    c = {x.id: x for x in load_catalogue().centres}
    assert c["intent"].modules == tuple(INTENT) and c["intent"].name and c["intent"].description
    assert c["build"].modules == () and c["consume"].modules == ()


@pytest.mark.parametrize("mutate", [
    lambda d: d["centres"][0]["modules"].append("m9_nope"),
    lambda d: d["centres"][1]["modules"].append("m1_intent"),   # one module in two centres
    lambda d: d["centres"][0].pop("description"),
])
def test_bad_centre_fails_at_load(tmp_path, mutate):
    d = yaml.safe_load(CAT.read_text(encoding="utf-8"))
    mutate(d)
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalogue(p)


def test_absent_key_means_on(world):
    s = world.store
    assert s.centre_for("m2_baseline") == "intent" and s.centre_for("m4_build") is None
    assert s.enabled_modules("co-b") == INTENT
    assert [c.id for c in s.centres_for("co-b")] == ["intent"]


def test_centre_off_hides_every_module_and_refuses_routes(world):
    s = world.store
    s.set_centre("co-b", "intent", False)
    assert s.enabled_modules("co-b") == [] and s.centres_for("co-b") == []
    c = world.login("b", "co-b", ["analyst"])
    assert listing(c) == []
    r = c.get("/api/modules/m1_intent/ping")
    assert r.status_code == 403 and r.json() == REFUSED
    s.set_centre("co-b", "intent", True)
    assert s.enabled_modules("co-b") == INTENT


def test_module_off_inside_centre_on_stays_off(world):
    s = world.store
    s.set_module("co-b", "m2_baseline", False)
    s.set_centre("co-b", "intent", True)
    assert s.enabled_modules("co-b") == ["m1_intent", "m3_connect"]


@pytest.mark.parametrize("bad", ["yes", 1, None, "true", {}])
def test_only_a_real_true_counts_when_the_key_is_present(world, tmp_path, bad):
    p = tmp_path / "data" / "_control" / "entitlements.json"
    ent = json.loads(p.read_text(encoding="utf-8"))
    ent["co-b"]["centres"] = {"intent": bad}
    p.write_text(json.dumps(ent), encoding="utf-8")
    assert world.store.enabled_modules("co-b") == []


def test_listing_carries_centre_and_description(world):
    rows = listing(world.login("b", "co-b", ["analyst"]))
    assert {r["centre"] for r in rows} == {"intent"}
    assert rows[0]["centre_name"] == "Intent centre" and rows[0]["centre_description"]
    a = {r["id"]: r for r in listing(world.login("a", "co-a", ["analyst"]))}
    assert a["m4_build"]["centre"] is None and "centre_name" not in a["m4_build"]


def test_industries_and_empty_company(world):
    world.store.set_centre("co-a", "intent", False)
    assert world.store.enabled_modules("co-a") == ["m4_build", "m5_foresight"]  # outside any centre: unaffected
    assert world.store.enabled_modules("co-n") == ["m1_intent"]  # other industry, untouched
    assert world.store.centres_for("co-empty") == [] and listing(world.login("e", "co-empty", ["company_admin"])) == []
