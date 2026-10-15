import re
from pathlib import Path

import pytest
import yaml

from sh_platform.auth.permissions import Permissions, Rule, load_permissions
from sh_platform.entitlements import Catalogue, load_catalogue
from sh_platform.manifest import ManifestError, load_manifest, manifest_route_gaps

IDS = ["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight", "m6_ops"]


def test_catalogue_has_six_modules_in_order_and_three_packages():
    c = load_catalogue()
    assert [m.id for m in c.modules] == IDS
    assert [m.number for m in c.modules] == [1, 2, 3, 4, 5, 6]
    assert [m.agent for m in c.modules][:3] == ["North", "Lens", "Lens"]
    assert all(m.name and m.description and m.agent for m in c.modules)
    assert c.packages["discover"] == IDS[:3]
    assert c.packages["build"] == IDS[:5]
    assert c.packages["run"] == IDS
    assert set(c.packages) == {"discover", "build", "run"}


def test_catalogue_text_names_no_industry():
    text = (Path(__file__).resolve().parents[2] / "sh_platform" / "catalogue.yaml").read_text(encoding="utf-8")
    assert not re.search(r"insur|asset|policyholder|reinsur|bank|fund", text, re.I)


@pytest.mark.parametrize("mutate", [
    lambda d: d["packages"]["run"]["modules"].append("m9_nope"),           # package names an unknown module
    lambda d: d["modules"].append(dict(d["modules"][0])),                  # duplicate module id
    lambda d: d["modules"][0].pop("agent"),                                # missing key
    lambda d: d["modules"][0].update(bogus=1),                             # unknown key
    lambda d: d["packages"]["discover"].update(modules=[]),                # empty package
    lambda d: d["modules"][0].update(id="Bad Id"),                         # bad id
])
def test_bad_catalogue_is_refused(tmp_path, mutate):
    data = yaml.safe_load((Path(__file__).resolve().parents[2] / "sh_platform" / "catalogue.yaml")
                          .read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalogue(p)


# ---- manifest

GOOD = {
    "id": "m1_intent", "name": "Intent", "agent": "North",
    "routes": [{"method": "GET", "path": "/api/modules/m1_intent/rooms", "roles": ["analyst"]},
               {"method": "POST", "path": "/api/modules/m1_intent/rooms/{room_id}/notes",
                "roles": ["participant", "analyst"]},
               {"method": "WEBSOCKET", "path": "/api/modules/m1_intent/live", "roles": ["analyst"]}],
    "tools": ["list_rooms", "summarise_notes"],
    "pack_sections": ["problems", "glossary"],
    "inputs": ["company brief"],
    "output": "charter",
}


def write(tmp_path, data, name="manifest.yaml"):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def mutated(**changes):
    d = {**GOOD, "routes": [dict(r) for r in GOOD["routes"]]}
    d.update(changes)
    return d


def test_good_manifest_loads(tmp_path):
    m = load_manifest(write(tmp_path, GOOD))
    assert m.id == "m1_intent" and m.agent == "North"
    assert [(r.method, r.path) for r in m.routes][0] == ("GET", "/api/modules/m1_intent/rooms")
    assert m.tools == ["list_rooms", "summarise_notes"]
    assert m.output == "charter"


BAD = {
    "unknown top key": mutated(extra="x"),
    "missing id": {k: v for k, v in GOOD.items() if k != "id"},
    "missing output": {k: v for k, v in GOOD.items() if k != "output"},
    "missing routes": {k: v for k, v in GOOD.items() if k != "routes"},
    "missing tools": {k: v for k, v in GOOD.items() if k != "tools"},
    "bad id": mutated(id="M1 Intent"),
    "empty name": mutated(name=""),
    "name not text": mutated(name=5),
    "duplicate route": mutated(routes=GOOD["routes"] + [dict(GOOD["routes"][0])]),
    "duplicate route different param name": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent/a/{x}", "roles": ["analyst"]},
        {"method": "GET", "path": "/api/modules/m1_intent/a/{y}", "roles": ["analyst"]}]),
    "route outside module": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m2_baseline/rooms", "roles": ["analyst"]}]),
    "route outside api": mutated(routes=[{"method": "GET", "path": "/api/health", "roles": ["analyst"]}]),
    "route is the module root": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent", "roles": ["analyst"]}]),
    "route prefix lookalike": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intentX/rooms", "roles": ["analyst"]}]),
    "route dot dot": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent/../m2_baseline/x", "roles": ["analyst"]}]),
    "route double slash": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent//x", "roles": ["analyst"]}]),
    "route with query": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent/x?a=1", "roles": ["analyst"]}]),
    "route bad method": mutated(routes=[
        {"method": "TRACE", "path": "/api/modules/m1_intent/x", "roles": ["analyst"]}]),
    "route unknown key": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent/x", "roles": ["analyst"], "extra": 1}]),
    "route missing roles": mutated(routes=[{"method": "GET", "path": "/api/modules/m1_intent/x"}]),
    "route empty roles": mutated(routes=[{"method": "GET", "path": "/api/modules/m1_intent/x", "roles": []}]),
    "route unknown role": mutated(routes=[
        {"method": "GET", "path": "/api/modules/m1_intent/x", "roles": ["wizard"]}]),
    "routes not a list": mutated(routes={"a": 1}),
    "tool uppercase": mutated(tools=["List_rooms"]),
    "tool leading digit": mutated(tools=["1tool"]),
    "tool with dash": mutated(tools=["list-rooms"]),
    "tool with newline": mutated(tools=["list_rooms\n"]),
    "tool duplicate": mutated(tools=["a", "a"]),
    "tools not a list": mutated(tools="list_rooms"),
    "pack sections not text": mutated(pack_sections=[1]),
    "inputs not a list": mutated(inputs="brief"),
    "output not text": mutated(output=["charter"]),
}


@pytest.mark.parametrize("name", list(BAD))
def test_bad_manifest_is_a_plain_error(tmp_path, name):
    with pytest.raises(ManifestError) as e:
        load_manifest(write(tmp_path, BAD[name]))
    msg = str(e.value)
    assert msg and "Traceback" not in msg and str(tmp_path) not in msg  # plain, no folder path


def test_unreadable_manifests_are_errors(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "missing.yaml")
    p = tmp_path / "bad.yaml"
    p.write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(p)
    p.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(p)


def test_manifest_routes_must_be_declared_with_the_same_roles(tmp_path):
    m = load_manifest(write(tmp_path, GOOD))
    perms = load_permissions()
    assert len(manifest_route_gaps(m, perms)) == 3  # nothing declared yet
    full = Permissions(roles=perms.roles, routes={
        "GET /api/modules/m1_intent/rooms": Rule(roles=frozenset({"analyst"})),
        "POST /api/modules/m1_intent/rooms/{room_id}/notes": Rule(roles=frozenset({"participant", "analyst"})),
        "WEBSOCKET /api/modules/m1_intent/live": Rule(roles=frozenset({"analyst"}))})
    assert manifest_route_gaps(m, full) == []
    wider = Permissions(roles=perms.roles, routes={**full.routes,
                        "GET /api/modules/m1_intent/rooms": Rule(authenticated=True)})
    assert len(manifest_route_gaps(m, wider)) == 1  # yaml is looser than the manifest
    renamed = Permissions(roles=perms.roles, routes={**full.routes,
                          "POST /api/modules/m1_intent/rooms/{rid}/notes": full.routes[
                              "POST /api/modules/m1_intent/rooms/{room_id}/notes"]})
    renamed.routes.pop("POST /api/modules/m1_intent/rooms/{room_id}/notes")
    assert len(manifest_route_gaps(m, renamed)) == 1  # path format must match exactly
