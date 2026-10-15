"""SF06: the design document (step 1). Template in agents/design_template.yaml, store in the company plane, plain standalone HTML render.

build/design/design.json         the current draft or signed version: {version, state, sections: {id: [line]}, specs, signed_by, drafted}
build/design/design.v<n>.json    a signed version, kept read-only; an edit after signing opens v<n+1> beside it, stated lines carried over (rule 7)
A line is {text, mark, from, by, at}, as the change note lines are. Code writes the `records` sections (also the fallback when the model
call fails); Span's sections are handed in by span_design.py and stay "Not available yet" until then. Routes are SF13's."""
import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
TEMPLATE = Path(__file__).parent / "agents" / "design_template.yaml"
EMPTY = "No design document yet. Span drafts it when a change note is filed."
SPAN_SENTENCE = "Span could not reach the model. Sections below are filled from the records only."
MAX_TEXT = 2000
NOT_YET = "Not available yet"
ME = "Design document"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rd(path, empty=None) -> Any:
    try:
        d = read_json_strict(path)
    except (OSError, ValueError):
        log.warning("a record needed for the design document could not be read")
        return empty
    return empty if d is None else d


def template() -> list[dict]:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))["sections"]


def _file(plane, name: str = "design.json"):
    return plane.path("build", "design", name)


def _ln(text: Any, src: str, by: str = "Span", mark: str = "guessed") -> dict:
    return {"text": str(text)[:MAX_TEXT], "mark": mark, "from": src, "by": by, "at": _now()}


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _notes(plane) -> list[dict]:
    from sh_platform.build import chain
    return chain.all_notes(plane)


def _note_lines(notes: list[dict], section: str, hidden: frozenset = frozenset()) -> list[dict]:
    return [dict(ln) for n in notes for ln in _list((n.get("sections") or {}).get(section)) if isinstance(ln, dict) and ln.get("text")
            and str(ln.get("measure") or "").lower() not in hidden and str(ln.get("component") or "") not in hidden]


def has_records(plane) -> bool:
    """The design starts once a change note exists (it opens when the gap report is signed)."""
    return bool(_notes(plane))


def fill_from_records(plane) -> dict[str, list[dict]]:
    """Every `fill: records` section from the records, and for each Span section the "Not available yet" line naming what is missing.
    SF14: one document is read by every role, so it is filled as nobody-in-particular sees the records: a restricted component reads
    "Restricted", and restricted measures, sources and source-map rows are left out (the screens' own masking rules)."""
    from sh_platform.build import architecture as A, blueprint as B, chain, contracts, runner
    from sh_platform.profile import view
    nobody = view.Viewer("", frozenset())
    bp = _rd(plane.path("build", "blueprint.json"), {})
    bp = bp if isinstance(bp, dict) else {}
    hidden = frozenset(B._hidden({"access": _list(bp.get("access"))}, nobody))
    hidden_src = runner._hidden_sources(plane, nobody)
    notes, rec = _notes(plane), A.read(plane)
    pipes = [(p, {**d, "marts": [m for m in d.get("marts") or [] if str(m).split(".", 1)[-1].lower() not in hidden]})
             for p, d in A.contracts(plane) if d["source"] not in hidden_src]
    shown = lambda code: str(code or "").lower() not in hidden  # noqa: E731
    secret = hidden | {c["id"] for c in rec["components"] if isinstance(c, dict) and not A.may_see(c, nobody)}  # note lines name either
    out: dict[str, list[dict]] = {}
    for s in template():
        out[s["id"]] = [] if s["fill"] == "records" else [_ln(f"{NOT_YET}: needs {s['missing']}.", "design template", ME)]
    out["context"] = [_ln(f"{n.get('id')}: {n.get('title')}", f"build/changes/{n.get('id')}.json", ME) for n in notes] + _note_lines(notes, "why", secret)
    comps = A.masked([c for c in rec["components"] if isinstance(c, dict) and c.get("state") != "proposed"], nobody)[0]
    out["current"] = [_ln(f"{c.get('label')} ({c.get('kind')}, {c.get('view')})", "build/architecture/record.json", ME) for c in comps] \
        or [_ln(f"{NOT_YET}: the architecture record has no components yet.", "build/architecture/record.json", ME)]
    out["delta"] = _note_lines(notes, "what_changes", secret)
    m = bp.get("model") if isinstance(bp.get("model"), dict) else {}
    out["layers"] = [_ln(f"{d.get('title') or d['source']}: loads {', '.join(d.get('marts') or []) or 'no mart yet'}", p, ME) for p, d in pipes]
    out["layers"] += [_ln(f"Fact {f.get('name')}: {f.get('grain')}", "build/blueprint.json model", ME) for f in _list(m.get("facts"))
                      if isinstance(f, dict) and all(shown(x) for x in _list(f.get("measures")))]
    out["layers"] += [_ln(f"Dimension {d.get('name')}: slowly changing type {d.get('scd')}", "build/blueprint.json model", ME)
                      for d in _list(m.get("dimensions")) if isinstance(d, dict)]
    out["sources"] = [_ln(d.get("title") or d["source"], p, ME) for p, d in pipes]
    for n in notes:
        smap = (chain._intent(plane, n.get("intent_id")).get("build_handoff") or {}).get("source_map")
        out["sources"] += [_ln(f"{s['name']}: {s.get('quadrant') or NOT_YET}" + (", strategic" if s.get("strategic") else ""),
                               f"intents/{n['intent_id']}/intent.json build_handoff", ME) for s in _list(smap)
                           if isinstance(s, dict) and s.get("name") and not s.get("restricted")]
    out["flows"] = [_ln(f"{d.get('title') or d['source']} depends on {', '.join(map(str, d['depends_on']))}" if d.get("depends_on")
                        else f"{d.get('title') or d['source']} has no upstream dependency", p, ME) for p, d in pipes]
    out["security"] = [_ln("A restricted mart: restricted to named people" if isinstance(a.get("may_see"), list) else f"{a.get('mart')}: open to everyone with Build access",
                           "build/blueprint.json access", ME) for a in _list(bp.get("access")) if isinstance(a, dict)]
    out["quality"] = [_ln(f"{r.get('measure')}: {r.get('rule')} ({r.get('severity')})", "build/blueprint.json rules", ME)
                      for r in _list(bp.get("rules")) if isinstance(r, dict) and shown(r.get("measure"))] + _note_lines(notes, "tests", secret)
    out["operations"] = [_ln(f"{s.get('source')}: expected {s.get('expected')}, service level {s.get('sla')}", "build/blueprint.json schedule", ME)
                         for s in _list(bp.get("schedule")) if isinstance(s, dict) and contracts.slug(s.get("source") or "") not in hidden_src]         + _note_lines(notes, "run_book", secret)
    out["risks"] = _note_lines(notes, "risks", secret) or out["risks"]
    out["decisions"] = _note_lines(notes, "decisions", secret) or out["decisions"]
    folder = plane.path("build", "proposals")
    props = [_rd(f, {}) for f in sorted(folder.glob("P-*.json"))] if folder.is_dir() else []
    out["suggestions"] = [_ln(f"{p['id']}: {p.get('title')}", f"build/proposals/{p['id']}.json", ME) for p in props
                          if isinstance(p, dict) and p.get("state") == "proposed" and p.get("id") and shown(p.get("measure"))] or [_ln("Span has no suggestions right now.", "build/proposals", ME)]
    return out


def read(plane) -> dict | None:
    d = _rd(_file(plane), None)
    return d if isinstance(d, dict) and isinstance(d.get("sections"), dict) else None


def _keep_stated(old: dict, new: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Stated lines stay where they are; the new draft's lines replace the guessed ones (S6, rule 7)."""
    out = {}
    for sid, lines in new.items():
        stated = [ln for ln in _list((old.get("sections") or {}).get(sid)) if isinstance(ln, dict) and ln.get("mark") == "stated"]
        out[sid] = stated + [ln for ln in lines if ln["text"] not in {s["text"] for s in stated}]
    return out


def draft(plane, span_sections: dict[str, list[dict]] | None = None, specs: dict | None = None, fallback: bool = False) -> dict | None:
    """Fill the draft from the records, with Span's sections where given. After a signature this opens the next version. None when there is
    nothing to draft from yet."""
    if not has_records(plane):
        return None
    with lock_for(_file(plane)):
        old = read(plane) or {"version": 0, "state": "draft", "sections": {}}
        new = fill_from_records(plane)
        for sid, lines in (span_sections or {}).items():
            if sid in new and lines:
                new[sid] = lines
        ver = old["version"] + 1 if old["state"] == "signed" or not old["version"] else old["version"]
        doc = {"version": ver, "state": "draft", "sections": _keep_stated(old, new), "specs": specs or old.get("specs") or {}, "signed_by": [],
               "drafted": {"by": "Span", "at": _now(), "fallback": fallback}}
        write_json_atomic(_file(plane), doc)
    return doc


def edit_line(plane, section: str, index: int, text: str, by: str) -> dict | None:
    """A person edits a line; it becomes stated. On a signed version this first opens v<n+1> (the signed one stays beside it)."""
    with lock_for(_file(plane)):
        doc = read(plane)
        if doc is None or section not in doc["sections"] or not 0 <= index < len(doc["sections"][section]):
            return None
        if doc["state"] == "signed":
            doc = {**doc, "version": doc["version"] + 1, "state": "draft", "signed_by": []}
        doc["sections"] = {k: [dict(ln) for ln in v] for k, v in doc["sections"].items()}
        doc["sections"][section][index] = {**doc["sections"][section][index], "text": str(text)[:MAX_TEXT], "mark": "stated", "by": by, "at": _now()}
        write_json_atomic(_file(plane), doc)
    return doc


def sign(plane, by: str, role: str) -> dict | None:
    """Signed read-only, kept as design.v<n>.json. None when there is no draft or it is already signed."""
    with lock_for(_file(plane)):
        doc = read(plane)
        if doc is None or doc["state"] == "signed":
            return None
        doc = {**doc, "state": "signed", "signed_by": [{"name": by, "role": role, "at": _now()}]}
        write_json_atomic(_file(plane, f"design.v{doc['version']}.json"), doc)
        write_json_atomic(_file(plane), doc)
    return doc


CSS = ("body{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:0 auto;padding:1rem;color:#1b1f24;background:#fff}"
       "h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:2rem;border-bottom:1px solid #d0d7de}.banner{padding:.5rem .75rem;border:1px solid #d0d7de;"
       "border-radius:6px;background:#f6f8fa}.tag{font-size:.75rem;color:#57606a;border:1px solid #d0d7de;border-radius:1em;padding:0 .5em;margin-left:.5em}"
       "li{margin:.25rem 0}svg{max-width:100%;height:auto}")


def _clean_svg(svg: str) -> str:
    """Diagrams come in as strings: drop scripts and any absolute web address (an svg namespace is not needed inline)."""
    svg = re.sub(r"<script\b.*?</script\s*>", "", svg, flags=re.S | re.I)
    return re.sub(r"""\s(?:xmlns(?::\w+)?|(?:xlink:)?href)\s*=\s*["']https?://[^"']*["']""", "", svg, flags=re.I)


def render_plain(doc: dict | None, diagrams: dict[str, str] | None = None) -> str:
    """One standalone page: inline CSS, no script, no external asset. Sections follow the template order; no document gives the empty state."""
    diagrams, e = diagrams or {}, html.escape
    if doc is None:
        body = f"<h1>Design document</h1><p>{e(EMPTY)}</p>"
    else:
        sig = (doc.get("signed_by") or [{}])[0]
        banner = f"Signed by {e(str(sig.get('name')))} on {e(str(sig.get('at'))[:10])}" if doc.get("state") == "signed" else "Draft"
        fb = f"<p>{e(SPAN_SENTENCE)}</p>" if (doc.get("drafted") or {}).get("fallback") else ""
        parts = [f"<h1>Design document, version {int(doc['version'])}</h1><p class=\"banner\">{banner}</p>{fb}"]
        for s in template():
            parts.append(f"<h2>{e(s['title'])}</h2>")
            if s.get("diagram") and diagrams.get(s["diagram"]):
                parts.append(f"<figure>{_clean_svg(diagrams[s['diagram']])}</figure>")
            items = "".join(f"<li>{e(ln['text'])}" + ("<span class=\"tag\">Span's suggestion</span>" if ln.get("mark") == "guessed" and ln.get("by") == "Span" else "")
                            + "</li>" for ln in _list(doc["sections"].get(s["id"])))
            parts.append(f"<ul>{items}</ul>" if items else f"<p>{NOT_YET}.</p>")
        body = "".join(parts)
    return f"<!doctype html><html lang=\"en-GB\"><head><meta charset=\"utf-8\"><title>Design document</title><style>{CSS}</style></head><body>{body}</body></html>"
