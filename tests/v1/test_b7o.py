"""STUDIO2 card C: three presentations of one tile, one of them Lumen's pick, from the words used and the table's columns; no model call."""
import pytest

from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import b7o_options as O
from sh_platform.v1 import b7o_routes
from sh_platform.v1.p1_project import Refused
from tests.v1.test_b7_studio import HEAD, api, draft  # noqa: F401 - api is a fixture
from tests.v1.test_cx import ADMIN, env  # noqa: F401 - env is a fixture


def tid_of(plane, pid, d):
    return S.view(plane, ADMIN, pid, d["id"])["layout"]["items"][0]["tile"]


def test_three_different_options_one_pick_tied_to_the_words(env):
    plane, pid = env
    d = draft(plane, pid)
    t = tid_of(plane, pid, d)
    out = O.options(plane, ADMIN, pid, d["id"], t, "show net worth per day")["options"]
    assert len(out) == 3 and sum(o["pick"] for o in out) == 1
    assert len({o["label"] for o in out}) == 3 and len({repr(o["patch"]) for o in out}) == 3
    pick = next(o for o in out if o["pick"])
    assert pick["patch"]["kind"] == "line" and '"per day"' in pick["why"] and out[0] is pick
    assert all(o["patch"]["measure"] == "net_worth" for o in out)


def test_other_words_pick_other_options_and_latest_is_the_newest_period(env):
    plane, pid = env
    d = draft(plane, pid)
    t = tid_of(plane, pid, d)
    cmp = next(o for o in O.options(plane, ADMIN, pid, d["id"], t, "which fund is the biggest")["options"] if o["pick"])
    assert cmp["patch"]["kind"] == "bar" and cmp["patch"]["split"] == "entity" and cmp["patch"]["only"] == {"column": "month", "values": ["2026-09-30"]}
    tab = next(o for o in O.options(plane, ADMIN, pid, d["id"], t, "what is the change")["options"] if o["pick"])
    assert tab["patch"]["kind"] == "table"
    none = O.options(plane, ADMIN, pid, d["id"], t, "hello")["options"]
    assert sum(o["pick"] for o in none) == 1 and "Nothing in your words" in next(o for o in none if o["pick"])["why"]


def test_route_is_maker_only_and_a_bad_tile_is_refused(api):
    plane, pid, c, cur = api
    c.app.include_router(b7o_routes.router)
    d = draft(plane, pid)
    t = tid_of(plane, pid, d)
    url = f"/api/v1/build/p/{pid}/studio/{d['id']}/tiles/{t}/options"
    r = c.post(url, json={"text": "per day"})
    assert r.status_code == 200 and len(r.json()["options"]) == 3
    assert c.post(url.replace(t, "t-nope00"), json={}).status_code == 404
    from sh_platform.profile.view import Viewer
    cur["v"] = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")
    assert c.post(url, json={}).status_code in (403, 404)


def test_permissions_declared():
    import yaml
    from pathlib import Path
    declared = yaml.safe_load(Path(O.__file__).with_name("b7o.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    assert {f"{m} {r.path}" for r in b7o_routes.router.routes for m in r.methods} == set(declared)
