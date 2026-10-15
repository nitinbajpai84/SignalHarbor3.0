"""V6 review: the old Pipelines Go live cannot skip the builder's variance gate; delivery text rounds a long computed ratio."""
from decimal import Decimal

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.v1 import b11_builder as BU
from sh_platform.v1 import b6_run as R
from sh_platform.v1.b6_routes import _builder_gate
from sh_platform.v1.d1_delivery import _fmt


def test_old_go_live_waits_for_the_builder(tmp_path):
    plane = PlaneStore(tmp_path / "data").create("evergreen")
    _builder_gate(plane, "prj-1")  # no builder record: the old controls work as before
    BU._save(plane, "prj-1", lambda r: r["rounds"].append({"state": "checked"}))
    with pytest.raises(R.Refused):
        _builder_gate(plane, "prj-1")
    BU._save(plane, "prj-1", lambda r: r["rounds"][-1].update(state="live"))
    _builder_gate(plane, "prj-1")  # after the builder's Go live, later live runs are allowed


def test_delivery_rounds_a_long_ratio_and_keeps_money():
    assert _fmt(0.006024795840697594) == "0.0060"
    assert _fmt(Decimal("1234567.891234")) == "1,234,567.89"
    assert _fmt(Decimal("12.50")) == "12.50" and _fmt(3) == "3"


def test_map_shows_one_node_per_person():
    from sh_platform.v1.k3_onto import _merge_people
    n = lambda i, t, l: {"id": i, "type": t, "label": l}  # noqa: E731
    nodes = {x["id"]: x for x in [n("person:Leo", "person", "Leo"), n("person:Leo Park", "person", "Leo Park"), n("person:lumen", "person", "lumen"),
                                  n("agent:lumen", "agent", "Lumen"), n("t:1", "table", "gold"), n("person:Anita Rao", "person", "Anita Rao")]}
    edges = {("person:Leo", "t:1", "owns"): {"from": "person:Leo", "to": "t:1", "rel": "owns"},
             ("t:1", "person:lumen", "built by"): {"from": "t:1", "to": "person:lumen", "rel": "built by"}}
    _merge_people(nodes, edges)
    assert set(nodes) == {"person:Leo Park", "agent:lumen", "t:1", "person:Anita Rao"}
    assert set(edges) == {("person:Leo Park", "t:1", "owns"), ("t:1", "agent:lumen", "built by")}
