"""M4 build nodes: Blueprint, Pipeline, Release from synthetic build files on a temp plane."""
import json

from sh_platform.graph.build_nodes import add_build_nodes, record_commit
from sh_platform.graph.models import Graph
from sh_platform.plane import PlaneStore

PROV = [{"mark": "stated", "by": "t", "at": None, "from": "t"}]


def put(plane, parts, data):
    p = plane.path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def setup(tmp_path, files=True):
    pl = PlaneStore(tmp_path / "planes").create("lakeside-family-office")
    if files:
        put(pl, ["build", "blueprint.json"], {"version": 2, "state": "signed", "signed_by": [{"name": "Ana Ng", "role": "architect", "at": "2026-10-01"}],
            "lineage": [{"measure": "K1", "source": "custody", "mart": "gold.k1"}, {"measure": "K2", "source": "custody", "mart": "gold.k2"}],
            "access": [{"mart": "gold.k1", "may_see": ["Ana Ng"]}, {"mart": "gold.k2", "may_see": None}]})
        put(pl, ["build", "pipelines", "custody.json"], {"source": "Custody feed", "marts": ["gold.k1"], "owner": "Dan Data"})
        put(pl, ["build", "prove.json"], {"band": "now", "release": {"state": "signed", "by": "Sam Sponsor", "at": "2026-10-05"},
            "measures": [{"code": "K1", "uat": {"state": "signed", "by": "Tia Test", "at": "2026-10-04"}, "release_ready": True}]})
    g = Graph()
    for k in ("K1", "K2"):
        g.node(f"measure:{k}", "Measure", k, PROV, "define", (["Ana Ng"], {}) if k == "K1" else None)
    return g, {}, pl


def test_nodes_and_edges_appear(tmp_path):
    g, people, pl = setup(tmp_path)
    add_build_nodes(g, pl, people)
    assert {"blueprint:v2", "pipeline:custody-feed", "release:now-2026-10"} <= set(g.nodes)
    assert g.nodes["blueprint:v2"]["label"] == "Blueprint v2" and g.nodes["release:now-2026-10"]["label"] == "Release now 2026-10"
    assert {"designed_by", "designed_in", "built_by", "owned_by", "released_by", "tested_by", "released_in"} <= {e["type"] for e in g.edges.values()}
    assert all(e["provenance"][0]["from"].startswith("build/") for e in g.edges.values())


def test_restriction_inherited(tmp_path):
    g, people, pl = setup(tmp_path)
    add_build_nodes(g, pl, people)
    for n in ("blueprint:v2", "pipeline:custody-feed"):
        assert g.nodes[n]["restricted_to"] == ["Ana Ng"]
    assert not g.nodes["release:now-2026-10"].get("restricted_to")  # a release is a name and a date; each measure's own edge keeps its guard


def test_commits_read_and_recorded(tmp_path):
    g, people, pl = setup(tmp_path)
    record_commit(pl, "custody", "Added a null check", "Dan Data")
    add_build_nodes(g, pl, people)
    c = g.nodes["pipeline:custody-feed"]["commits"]
    assert len(c) == 1 and c[0]["what"] == "Added a null check" and c[0]["by"] == "Dan Data" and {"id", "when"} <= set(c[0])


def test_missing_files_add_nothing(tmp_path):
    g, people, pl = setup(tmp_path, files=False)
    add_build_nodes(g, pl, people)
    assert set(g.nodes) == {"measure:K1", "measure:K2"} and not g.edges


def test_built_by_for_a_suffixed_mart_and_released_from_the_list(tmp_path):
    g, people, pl = setup(tmp_path)
    put(pl, ["build", "blueprint.json"], {"version": 2, "state": "signed", "lineage": [{"measure": "K1", "source": "Custody feed", "mart": "gold.k1.coverage"}, {"measure": "K2", "source": "Custody feed", "mart": "gold.k2.other"}]})
    put(pl, ["build", "prove.json"], {"band": "now", "release": {"state": "signed", "by": "Sam", "at": "2026-10-05", "released": ["K2"]}, "measures": [{"code": "K1", "release_ready": True}, {"code": "K2"}]})
    add_build_nodes(g, pl, people)
    edges = set(g.edges)
    assert ("measure:K1", "pipeline:custody-feed", "built_by") in edges and ("measure:K2", "pipeline:custody-feed", "built_by") in edges
    assert ("measure:K2", "release:now-2026-10", "released_in") in edges and ("measure:K1", "release:now-2026-10", "released_in") not in edges
