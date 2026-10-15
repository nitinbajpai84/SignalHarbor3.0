"""Module 2 is mounted, gated like every module, and starts from module 1's signed charters."""
import json

from m2_kit import login


def test_status_counts_signed_charters_and_needs_the_module(world):
    c = login(world, "co-a")
    r = c.get("/api/modules/m2_baseline/status")
    assert r.status_code == 200 and r.json() == {"module": "m2_baseline", "charters": 0}
    folder = world.plane("co-a").path("intents", "m1_intent", "outcomes")
    folder.mkdir(parents=True)
    (folder / ("a" * 32 + ".json")).write_text(json.dumps({}))
    assert c.get("/api/modules/m2_baseline/status").json()["charters"] == 1


def test_a_company_without_module_2_is_refused(world):
    assert login(world, "co-off").get("/api/modules/m2_baseline/status").status_code in (403, 404)
