"""K7 (file k8_sop): a standard operating procedure written from a signed intent of work and its swim lane.
Pure functions over the SOW record: build() -> dict, to_markdown(), to_docx(). No model, no figures invented: what the
conversation did not capture is written "Not stated yet" and listed under Open points, so North can ask for it."""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

from sh_platform.v1.i4_sow import kind_word

NOT_STATED = "Not stated yet"
MANUAL = re.compile(r"manual|spreadsheet|excel|by hand|workbook|tracker|e-?mail|file drop|paste|re-?typ|re-?key|types? (?:in|the)", re.I)


def is_manual(s: dict) -> bool:
    """N1-SOP-01, H1-05: the step's own `manual` flag (North's draft or the person's edit) wins; only a step with no flag is judged
    from its words (hand work: a spreadsheet, a workbook or tracker, an email, a file drop, pasting or typing figures in)."""
    if isinstance(s.get("manual"), bool):
        return s["manual"]
    return bool(MANUAL.search(" ".join(str(s.get(f) or "") for f in ("name", "does", "system"))))


def _j(xs) -> str:
    return ", ".join(str(x) for x in xs or [] if str(x).strip()) or NOT_STATED


def build(sow: dict) -> dict:
    """The SOP as data: purpose, scope, roles, steps, hand-overs, controls, definitions and open points."""
    g, proc = sow.get("goal") or {}, sow.get("process") or {}
    steps_in, hand = proc.get("steps") or [], proc.get("handovers") or []
    steps, open_points = [], []
    for i, s in enumerate(steps_in, 1):
        n = s.get("n") or i
        manual = is_manual(s)
        row = {"n": n, "name": s.get("name") or "", "who": s.get("who") or NOT_STATED, "system": s.get("system") or NOT_STATED,
               "does": s.get("does") or "", "input": _j(s.get("inputs")), "output": _j(s.get("outputs")),
               "control": str(s.get("control") or "").strip() or NOT_STATED, "exception": str(s.get("exception") or "").strip() or NOT_STATED,
               "manual": manual,
               "handovers": [{"to_step": h.get("to_step"), "what": h.get("what") or ""} for h in hand if h.get("from_step") == n]}
        steps.append(row)
        for field, label in (("control", "the control"), ("exception", "what to do when it goes wrong")):
            if row[field] == NOT_STATED:
                open_points.append(f"Step {n} ({row['name']}): {label} is not stated yet.")
        if row["who"] == NOT_STATED:
            open_points.append(f"Step {n} ({row['name']}): who does it is not stated yet.")
    open_points += [f"Unclear in the intent of work: {u.get('question')}" for u in sow.get("unclear") or [] if not u.get("settled")]
    sig = sow.get("signature")
    return {
        "title": f"Standard operating procedure: {sow.get('title') or g.get('line') or 'Untitled'}",
        "version": sow.get("version") or 1,
        "signed": f"Signed by {sig.get('name')} ({sig.get('role')}) on {str(sig.get('at'))[:10]}." if sig else "Not signed yet. This is a draft.",
        "purpose": g.get("why") or g.get("line") or NOT_STATED,
        "scope": " ".join([_end(g.get('line') or NOT_STATED), _end(f"Readers: {_j(g.get('readers'))}"), _end(f"Needed by: {g.get('needed_by') or NOT_STATED}")]),
        "roles": list(dict.fromkeys(s["who"] for s in steps if s["who"] != NOT_STATED)),
        "systems": list(dict.fromkeys(s["system"] for s in steps if s["system"] != NOT_STATED)),
        "steps": steps,
        "manual_steps": [s["n"] for s in steps if s["manual"]],
        "controls": [f"{kind_word(r.get('kind'))}: {r.get('rule')}" for r in sow.get("governance") or []],  # UC9-04: 'Access: ...', not 'access: ...'
        "definitions": [f"{k.get('name')}: {k.get('definition') or 'No definition yet'}" for k in sow.get("kpis") or []],
        "open_points": open_points,
    }


def _end(x) -> str:
    """One full stop at the end of a sentence, never two (a9.6: the person's control text often ends with its own)."""
    x = str(x).rstrip()
    return x if x.endswith((".", "!", "?")) else x + "."


def _lines(sop: dict) -> list[tuple[str, list[str]]]:
    def step(s: dict) -> str:
        out = " ".join([_end(f"{s['n']}. {s['name']}{' (manual: a candidate for automation)' if s['manual'] else ''}"), _end(f"Who: {s['who']}"),
                        _end(f"System: {s['system']}"), _end(f"Input: {s['input']}"), _end(f"Output: {s['output']}"),
                        _end(f"Control: {s['control']}"), _end(f"If it goes wrong: {s['exception']}")])
        return out + "".join(" " + _end(f"Hand over to step {h['to_step']}: {h['what']}") for h in s["handovers"])
    return [("Purpose", [sop["purpose"]]), ("Scope", [sop["scope"]]),
            ("Roles", sop["roles"] or [NOT_STATED]), ("Systems", sop["systems"] or [NOT_STATED]),
            ("Steps", [step(s) for s in sop["steps"]] or ["No steps yet."]),
            ("Manual steps flagged for automation", [f"{s['n']}. {s['name']}" for s in sop["steps"] if s["manual"]] or ["None"]),  # UC9-04: named
            ("Controls", sop["controls"] or ["None stated"]), ("Definitions", sop["definitions"] or ["None stated"]),
            ("Open points", sop["open_points"] or ["None"])]


def to_markdown(sop: dict) -> str:
    out = [f"# {sop['title']}", f"Version {sop['version']}. {sop['signed']}", ""]
    for head, lines in _lines(sop):
        out += [f"## {head}", ""] + [f"- {x}" for x in lines] + [""]
    return "\n".join(out)


def docx_available() -> bool:
    try:
        import docx  # noqa: F401
    except ImportError:
        return False
    return True


def to_docx(sop: dict) -> bytes:
    """PF2: a Word file everywhere. python-docx when installed, else the same headings and bullets written as plain WordprocessingML."""
    if not docx_available():
        return _plain_docx(sop)
    import docx
    d = docx.Document()
    d.add_heading(sop["title"], 0)
    d.add_paragraph(f"Version {sop['version']}. {sop['signed']}")
    for head, lines in _lines(sop):
        d.add_heading(head, 1)
        for x in lines:
            d.add_paragraph(x, style="List Bullet")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PARTS = {
    "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
    "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
}


def _plain_docx(sop: dict) -> bytes:
    """A minimal valid .docx with the standard library: title, headings (bold, larger) and bullet lines. No styles part, so Word's defaults apply."""
    def para(text: str, size: int = 0, bold: bool = False) -> str:
        rpr = ("<w:b/>" if bold else "") + (f'<w:sz w:val="{size}"/>' if size else "")
        return f'<w:p><w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    body = [para(sop["title"], 36, True), para(f"Version {sop['version']}. {sop['signed']}")]
    for head, lines in _lines(sop):
        body += [para(head, 28, True)] + [para(f"• {x}") for x in lines]
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{_W}"><w:body>{"".join(body)}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in _PARTS.items():
            z.writestr(name, xml)
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def filename(sop: dict, ext: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", sop["title"].split(": ", 1)[-1]).strip("-")[:60] or "sop"
    return f"SOP-{stem}-v{sop['version']}.{ext}"
