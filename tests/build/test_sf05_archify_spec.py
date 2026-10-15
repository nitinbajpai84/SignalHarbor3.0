"""SF05: Archify specs (current, target, delta), the fixed boundaries, validation with no network, masking. Synthetic data, a tmp plane."""
import json
import socket
import urllib.request
from pathlib import Path

import pytest

from sh_platform.build import architecture as A, archify_spec as S
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

ROOT = Path(__file__).resolve().parents[2]
INTENT = "ini-" + "sf05" * 8
JANET = Viewer("Janet Shaw", frozenset({"company_admin"}))
DANIEL = Viewer("Daniel Kerr", frozenset({"sponsor"}))
AARON = Viewer("Aaron Lyle", frozenset({"participant"}))


def _w(plane, rel: str, doc) -> None:
    p = plane.path(*rel.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def plane(tmp_path, monkeypatch):
    pl = PlaneStore(tmp_path).create("sf05-co")
    _w(pl, "build/blueprint.json", {
        "version": 1, "state": "signed", "infra": {"warehouse": "plane", "runner": "builtin"},
        "lineage": [{"measure": "K12", "source": "Custodian file", "mart": "gold.k12.stale_share", "transform": "Stale over all"},
                    {"measure": "K06", "source": "Payroll file", "mart": "gold.k06.pay", "transform": "Pay"}],
        "access": [{"mart": "gold.k12", "may_see": None}, {"mart": "gold.k06", "may_see": ["Daniel Kerr"]}]})
    _w(pl, "build/pipelines/custodian_file.json", {"source": "custodian_file", "title": "Custodian file", "marts": ["gold.k12"], "expected": "Daily"})
    _w(pl, "build/pipelines/payroll_file.json", {"source": "payroll_file", "title": "Payroll file", "marts": ["gold.k06"], "expected": "Monthly"})
    intent = {"id": INTENT, "type": "initiative", "build_handoff": {"processes": [], "source_map": [
        {"id": "s1", "name": "Custodian file", "zone": "p1", "strategic": True, "restricted": False},
        {"id": "s2", "name": "Payroll file", "zone": "identify", "strategic": True, "restricted": True}]}}
    from sh_platform.intents import store as istore
    from sh_platform.profile import store as pstore
    monkeypatch.setattr(istore, "read_index", lambda p: [{"id": INTENT, "type": "initiative"}])
    monkeypatch.setattr(istore, "read_intent", lambda p, i: intent if i == INTENT else None)
    monkeypatch.setattr(pstore, "raw", lambda p: {"people": {}, "systems": {}, "areas": {}})
    A.regenerate(pl, "blueprint_signed", "build/blueprint.json", "Grace Ward", [])
    return pl


DRAFT = {"placements": [{"id": "gold:k20", "kind": "gold", "label": "gold.k20", "interfaces": []},
                        {"id": "silver:custodian_file", "kind": "silver", "label": "Clash with a record id"}]}


def test_fixture_validates():
    sp = json.loads((ROOT / "docs/architecture/sh-m4-build.json").read_text(encoding="utf-8"))
    assert S.validate(sp) == []


def test_unknown_type_and_dangling_connection_fail_plainly():
    sp = json.loads((ROOT / "docs/architecture/sh-m4-build.json").read_text(encoding="utf-8"))
    sp["components"].append({"id": "odd", "type": "gizmo", "label": "Odd"})
    errs = S.validate(sp)
    assert errs[0] == 'component odd type: "gizmo" is not an allowed value.'
    sp["components"].pop()
    sp["connections"].append({"from": "inputs", "to": "nowhere"})
    assert S.validate(sp) == ["The connection from inputs to nowhere points at a component that is not in the diagram."]


def test_specs_are_valid_and_carry_both_boundaries(plane):
    for sp in (S.current(plane, JANET), S.target(plane, JANET, DRAFT), S.delta(plane, JANET, DRAFT), S.current(plane, JANET, "infrastructure")):
        known = S.known_ids(plane, JANET, DRAFT, sp["meta"]["output"].split("/")[-1].split("-")[0])
        assert S.validate(sp, known) == [], sp["meta"]["title"]
        labels = [b["label"] for b in sp["boundaries"]]
        assert labels == [S.PLANE_LABEL, S.EGRESS_LABEL]
        assert S.EGRESS not in sp["boundaries"][0]["wraps"]


def test_egress_node_sits_on_the_plane_boundary(plane, tmp_path):
    empty = PlaneStore(tmp_path / "e").create("empty-co")
    for sp in (S.current(plane, JANET), S.target(plane, DANIEL, DRAFT), S.delta(plane, AARON, DRAFT), S.current(empty, JANET)):
        rect = S.boundary_rects(sp)[0]
        eg = next(c for c in sp["components"] if c["id"] == S.EGRESS)
        assert eg["pos"][0] + eg["size"][0] / 2 == rect["x"] + rect["w"]
        assert rect["y"] <= eg["pos"][1] and eg["pos"][1] + eg["size"][1] <= rect["y"] + rect["h"]
        assert S.validate(sp) == []
        svg = S.svg_with_boundaries(sp)
        assert svg.count('stroke-dasharray="6 4"') == 2 and S.PLANE_LABEL in svg and S.EGRESS_LABEL in svg


def test_component_tracing_to_nothing_is_refused(plane):
    sp = S.target(plane, JANET, DRAFT)
    known = S.known_ids(plane, JANET, DRAFT)
    assert S.validate(sp, known) == []
    sp["components"].append({"id": "made-up", "type": "database", "label": "Invented", "pos": [900, 40], "size": [160, 64]})
    assert S.validate(sp, known) == ["The component made-up traces to no record and is not one of Span's suggestions."]
    assert S.validate(sp, S.known_ids(plane, JANET, None)) != []  # without the draft, Span's placement no longer traces


def test_span_placements_are_tagged_and_in_the_delta_focus(plane):
    t = S.target(plane, JANET, DRAFT)
    span = [c for c in t["components"] if c.get("tag") == S.SPAN_TAG]
    assert [c["id"] for c in span] == ["gold-k20"]  # the clash with a record id is ignored: the record wins
    d = S.delta(plane, JANET, DRAFT)
    assert d["meta"]["views"] == [{"id": "this-change", "label": "This change", "focus": ["gold-k20"]}]
    assert "views" not in S.current(plane, JANET)["meta"]


def test_restricted_components_are_masked(plane):
    for viewer in (AARON, DANIEL, JANET):
        sp = S.current(plane, viewer)
        text = json.dumps(sp)
        hidden = viewer is AARON
        assert ("gold.k06" in text) is not hidden and ("Payroll file" in text) is not hidden
        if hidden:
            assert sum(c["label"] == "Restricted" for c in sp["components"]) >= 4
            assert not any("restricted" in k["from"] or "restricted" in k["to"] for k in sp["connections"])
        assert S.validate(sp, S.known_ids(plane, viewer)) == []


def test_strategic_flag_and_quadrant_on_sources(plane):
    sp = S.current(plane, AARON)
    src = next(c for c in sp["components"] if c["label"] == "Custodian file")
    assert src["sublabel"] == "strategic"
    items = sp["cards"][0]["items"]
    assert items == ["Custodian file: Ready to scan, priority 1, strategic"]  # the restricted source's row is not used
    janet = S.current(plane, JANET)["cards"][0]["items"]
    assert "Payroll file: To be identified, strategic" in janet


def test_validation_makes_no_network_call(plane, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    S._validator.cache_clear()
    assert S.validate(S.target(plane, JANET, DRAFT)) == []
    with pytest.raises(Exception):  # any reference outside the two schemas on disk is refused, not fetched
        S._refuse("https://example.test/other.schema.json")


def test_not_an_object():
    assert S.validate([1]) == ["The diagram is not a JSON object."]
