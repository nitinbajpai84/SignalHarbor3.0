"""Adversarial probes for GET /api/company/graph (CG-2)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the route test's fixtures live beside this file
from test_graph_route import login, FAMILY, MUTUAL, n, e  # noqa: E402,F401

from sh_platform.plane import PlaneStore
from sh_platform.profile.store import record
from sh_platform.profile import view
from sh_platform.graph.build import rebuild

PROV = {"mark": "stated", "by": "Mei Tan", "from": "Interview"}


def _plane(c):
    root = Path(c.app.state.settings.data_root)
    return PlaneStore(root).plane_for(FAMILY)


def _write(c, doc):
    _plane(c).path("graph", "company.json").write_text(json.dumps(doc), encoding="utf-8")


def test_focus_cannot_probe_existence(login):
    c = login("sponsor")
    hidden = c.get("/api/company/graph?view=trace&focus=m3")
    absent = c.get("/api/company/graph?view=trace&focus=zzz")
    assert hidden.status_code == absent.status_code == 404 and hidden.json() == absent.json()
    empty = c.get("/api/company/graph?view=trace")
    assert empty.status_code == 404


def test_trace_from_silhouette_shows_no_label(login):
    c = login("sponsor")
    m = c.get("/api/company/graph").json()
    sil = next(x["id"] for x in m["nodes"] if x.get("restricted"))
    t = c.get(f"/api/company/graph?view=trace&focus={sil}").json()
    blob = json.dumps(t)
    assert "Secret measure" not in blob and "m3" not in blob and "priya" not in blob.lower()
    print("TRACE FROM SILHOUETTE:", blob)


def test_admin_is_silhouetted_when_someone_is_named(login):
    blob = json.dumps(login("company_admin").get("/api/company/graph").json())
    assert "Secret measure" not in blob and "priya" not in blob.lower()


def test_other_company_cannot_reach_silhouette(login):
    o = login("company_admin", MUTUAL)
    assert o.get("/api/company/graph?view=trace&focus=restricted-1").status_code == 404


def test_holes_hide_restricted_measure_name(login):
    c = login("sponsor")
    doc = {"version": 1, "built_at": "x", "nodes": [n("m9", "Measure", "Hidden loose", restricted_to=["priya nair"]), n("m2", "Measure", "Loose")], "edges": []}
    _write(c, doc)
    r = c.get("/api/company/graph?view=holes").json()
    assert "Hidden loose" not in json.dumps(r), r
    print("HOLES:", r)


def test_owner_of_restricted_measure_not_revealed_via_edges(login):
    c = login("sponsor")
    doc = {"version": 1, "built_at": "x",
           "nodes": [n("measure:secret", "Measure", "Secret", restricted_to=["priya nair"]), n("person:olga", "Person", "Olga Owner",
                     provenance=[{"mark": "stated", "by": "the record", "from": "Reported figures"}])],
           "edges": [e("measure:secret", "person:olga", "owned_by")]}
    _write(c, doc)
    r = c.get("/api/company/graph").json()
    assert all(x["type"] != "owned_by" for x in r["edges"])
    print("ORPHAN OWNER MAP:", r)


def test_real_build_owner_of_restricted_figure_appears_as_person(login):
    """A reported figure inside a restricted area, owned by someone not in the people list: the profile hides the row for the
    sponsor; does the graph still show the owner's name?"""
    c = login("sponsor")
    pl = _plane(c)
    record(pl, "governance.restricted_areas.trust.area", "Family Trust", PROV)
    record(pl, "governance.restricted_areas.trust.may_see", ["Priya Nair"], PROV)
    record(pl, "reported_figures.f1.measure", "Trust NAV", PROV)
    record(pl, "reported_figures.f1.area", "Family Trust", PROV)
    record(pl, "reported_figures.f1.owner", "Olga Trustee", PROV)
    rebuild(pl)
    prof = view.read(pl, view.Viewer("Arjun Rao", frozenset({"sponsor"})))
    assert "Olga Trustee" not in json.dumps(prof)
    blob = json.dumps(c.get("/api/company/graph").json())
    assert "Trust NAV" not in blob
    assert "Olga Trustee" not in blob, "owner of a restricted figure leaks as a Person node: " + blob


def test_graph_is_rebuilt_when_profile_tightens(login):
    """A-069: admin sees an unnamed area; once someone is named the admin must lose it (the profile does at once)."""
    c = login("company_admin")
    pl = _plane(c)
    record(pl, "governance.restricted_areas.trust.area", "Family Trust", PROV)
    record(pl, "reported_figures.f1.measure", "Trust NAV", PROV)
    record(pl, "reported_figures.f1.area", "Family Trust", PROV)
    rebuild(pl)
    assert "Trust NAV" in json.dumps(c.get("/api/company/graph").json())
    record(pl, "governance.restricted_areas.trust.may_see", ["Priya Nair"], PROV)  # marks the graph dirty
    prof = view.read(pl, view.Viewer("Mei Tan", frozenset({"company_admin"}), account_id=None))
    assert "Trust NAV" not in json.dumps(prof), "profile control"
    assert "Trust NAV" not in json.dumps(c.get("/api/company/graph").json()), "graph route serves a stale, more open graph"


def test_bad_focus_inputs(login):
    c = login("sponsor")
    for f in ["../../etc/passwd", "%00", "a" * 5000, "restricted-0", "restricted--1"]:
        assert c.get("/api/company/graph", params={"view": "trace", "focus": f}).status_code == 404
