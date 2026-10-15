"""SF06: the design document template, store, versions and plain renderer. Synthetic data only, tmp planes, no model call."""
import json
import re

import pytest
import yaml

from sh_platform.build import design_doc as D
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore

PROBLEMS = {"family office": ("Valuation chase", "fund", "ORG_03 statements"), "asset management": ("Fee reconciliation", "mandate", "ORG_07 trades")}


def make_plane(tmp_path, company):
    return PlaneStore(tmp_path).create(company)


def seed(plane, title, entity, source):
    ln = lambda t: {"text": t, "mark": "guessed", "from": "test", "by": "Architect", "at": "2026-10-01T00:00:00+00:00"}
    write_json_atomic(plane.path("build", "changes", "C-0001.json"), {
        "id": "C-0001", "title": title, "intent_id": None, "state": "with_architect",
        "sections": {"why": [ln(f"Handed to Build on 2026-10-01 for {title}")], "what_changes": [ln(f"Adds the {entity} mart")], "decisions": [], "tests": [ln("Baseline 0.42 reproduces")],
                     "run_book": [], "risks": [ln("One source arrives late")], "build_steps": []}})
    write_json_atomic(plane.path("build", "blueprint.json"), {
        "version": 2, "state": "draft", "model": {"facts": [{"name": f"fact_{entity}", "grain": f"One row per {entity} per month", "keys": [], "measures": ["K1"]}],
                                                  "dimensions": [{"name": f"dim_{entity}", "keys": [], "attributes": [], "scd": 2}]},
        "access": [{"mart": "gold.k1", "may_see": None}, {"mart": "gold.k2", "may_see": ["Someone"]}],
        "rules": [{"measure": "K1", "rule": "Value is filled", "severity": "warn"}], "schedule": [{"source": source, "expected": "D+2 09:00", "sla": "WD3"}]})
    write_json_atomic(plane.path("build", "pipelines", "p1.json"), {"source": source, "title": source, "marts": ["gold.k1"], "depends_on": []})


@pytest.fixture(params=sorted(PROBLEMS))
def plane(request, tmp_path):
    p = make_plane(tmp_path, request.param.replace(" ", "-"))
    seed(p, *PROBLEMS[request.param])
    return p


def test_empty_company(tmp_path):
    p = make_plane(tmp_path, "empty-co")
    assert D.draft(p) is None and D.read(p) is None
    assert D.EMPTY == "No design document yet. Span drafts it when a change note is filed." and D.EMPTY in D.render_plain(None)


def test_sections_in_template_order_and_reorder_without_code(plane, tmp_path, monkeypatch):
    doc = D.draft(plane, fallback=True)
    titles = [s["title"] for s in D.template()]
    html = D.render_plain(doc)
    assert [html.index(f"<h2>{t}") for t in titles] == sorted(html.index(f"<h2>{t}") for t in titles)
    assert D.SPAN_SENTENCE in html
    assert "Not available yet: needs Span's target architecture draft." in "".join(ln["text"] for ln in doc["sections"]["target"])
    flipped = tmp_path / "t.yaml"
    flipped.write_text(yaml.safe_dump({"sections": list(reversed(D.template()))}), encoding="utf-8")
    monkeypatch.setattr(D, "TEMPLATE", flipped)
    html2 = D.render_plain(doc)
    assert html2.index("<h2>Suggestions for the data team") < html2.index("<h2>Purpose and scope")


def test_signed_is_read_only_and_edit_opens_next_version_keeping_stated(plane):
    D.draft(plane)
    D.edit_line(plane, "context", 0, "Janet's own wording", "Aaron Lyle")
    signed = D.sign(plane, "Grace Ward", "Head of department")
    assert signed["state"] == "signed" and D.sign(plane, "Grace Ward", "Head of department") is None
    assert "Signed by Grace Ward" in D.render_plain(signed)
    nxt = D.edit_line(plane, "delta", 0, "Edited after signature", "Aaron Lyle")
    assert nxt["version"] == 2 and nxt["state"] == "draft"
    assert D.read(plane)["version"] == 2
    v1 = json.loads(D._file(plane, "design.v1.json").read_text(encoding="utf-8"))
    assert v1["state"] == "signed" and v1["sections"]["delta"][0]["text"] != "Edited after signature"
    redraft = D.draft(plane)
    assert redraft["version"] == 2
    assert redraft["sections"]["context"][0] == {**v1["sections"]["context"][0]}
    assert redraft["sections"]["delta"][0]["text"] == "Edited after signature" and redraft["sections"]["delta"][0]["mark"] == "stated"


def test_draft_after_signature_opens_next_version(plane):
    D.draft(plane)
    D.sign(plane, "Grace Ward", "Head of department")
    assert D.draft(plane)["version"] == 2


def test_span_sections_replace_guesses_but_not_stated(plane):
    D.draft(plane)
    D.edit_line(plane, "target", 0, "Architect kept this", "Aaron Lyle")
    new = D.draft(plane, span_sections={"target": [D._ln("Span target line", "span")], "purpose": [D._ln("Span purpose", "span")]})
    assert [ln["text"] for ln in new["sections"]["target"]] == ["Architect kept this", "Span target line"]
    assert new["sections"]["purpose"][0]["text"] == "Span purpose"


def test_every_figure_traces_to_a_record(plane):
    doc = D.draft(plane)
    records = " ".join(f.read_text(encoding="utf-8") for f in plane.path("build").rglob("*.json") if "design" not in f.parts[-2:])
    for sid, lines in doc["sections"].items():
        for ln in lines:
            for num in re.findall(r"\d+(?:\.\d+)?", ln["text"]):
                assert num in records, f"{num} in {sid} is not in any record"


def test_html_has_no_script_and_no_http_even_with_hostile_diagram(plane):
    doc = D.draft(plane)
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><a href="https://x.test/a"><rect/></a></svg>'
    html = D.render_plain(doc, {"current": svg, "target": svg, "delta": svg})
    assert "<script" not in html.lower() and "http" not in html and html.count("<svg") == 3


def test_lines_are_escaped(plane):
    D.draft(plane)
    D.edit_line(plane, "context", 0, "<b>bold</b> & more", "Aaron Lyle")
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; more" in D.render_plain(D.read(plane))


def test_no_industry_word_in_code():
    src = (D.Path(D.__file__).read_text(encoding="utf-8") + D.TEMPLATE.read_text(encoding="utf-8")).lower()
    for word in ("family office", "insurance", "asset management", "fund"):
        assert word not in src
