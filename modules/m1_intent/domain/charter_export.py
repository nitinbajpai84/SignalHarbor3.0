"""The signed charter as a file (printable HTML, Markdown) and as an email text for the organiser to copy. Nothing is sent.

Everything is built from `charter_view` (the dict the charter screen is drawn from), so the file and the screen cannot differ.
No author of any note appears here: the view carries none, and an anonymous note is only ever a plain label."""
import re
from html import escape

from modules.m1_intent.domain.charter import with_so_that

ANON = "(an anonymous note)"
NONE_RAISED = "None raised in this session."


def one_line(s, cap: int = 300) -> str:
    """Whitespace (a line break included) collapsed to single spaces, then cut to `cap` characters."""
    return " ".join(str(s).split())[:cap].rstrip()


_MD = re.compile(r"([\\`*_\[\]<>#])")


def md(s) -> str:
    """One line of user text for Markdown: no line break, and no character that starts markup."""
    return _MD.sub(r"\\\1", one_line(s))


def _head(view: dict, company: str, title: str, illustrative: bool) -> dict:
    f = view["footer"]
    rows = {p.get("id", i): {"title": one_line(p["title"]), "priority": one_line(p["priority_label"] or p["tie"] or "No priority yet"),
                      "so_that": one_line(with_so_that(p["so_that"])) if p["so_that"] else "",
                      "details": [one_line(f"{d['label']}: {', '.join(d['values'])}") for d in p.get("details", [])]} for i, p in enumerate(view["problems"])}
    # four lists in the screen's order: problems to solve now, pain points, what to track for the future, levers for what-if
    lists = view.get("lists") or [{"heading": "Problems", "ids": list(rows)}]
    return {"company": one_line(company), "title": one_line(title, 120), "date": one_line(f["date"]), "illustrative": illustrative,
            "rows": list(rows.values()), "sections": [(one_line(l["heading"]), [rows[i] for i in l["ids"] if i in rows]) for l in lists],
            "later": [one_line(x["title"]) for x in view["later"]] + [_alone(n) for n in view.get("alone", [])],
            "parked": [one_line(f"{x['title']}: {x['reason']} (review by {x['review_date']})") for x in view.get("parked", [])],
            "wall": _wall(view.get("wall")),
            "signers": [(one_line(s["name"]), one_line(s["at"][:10])) for s in view["signing"]["signers"]],
            "line": f"{f['participants']} people, {f['notes']} notes, {f['later']} left for later."}


LANE_NAMES = {"tracking": "Tracking today", "missing": "Missing", "watch": "To watch", "levers": "Levers"}
SEALED = "A sealed card"


def _wall(w) -> list[tuple[str, int, list[str]]] | None:
    """Page one: per lane its name, count and card lines. A sealed card is only a label; an anonymous author is only "Anonymous"."""
    if not w:
        return None
    return [(LANE_NAMES.get(l["lane"], l["lane"]), l["count"],
             [SEALED if c.get("silhouette") else one_line(c["text"]) + f" ({one_line(c['author'], 80)})" for c in l["cards"]]) for l in w["lanes"]]


def _alone(n: dict) -> str:
    """A note left on its own: its words, and the author's name only when it was posted by name."""
    if not n["text"]:
        return ANON
    return one_line(n["text"]) + (f" ({one_line(n['author_name'], 80)})" if n.get("author_name") else "")


NOT_NAMED = "Not named"


def _frozen_lines(page: dict) -> list[str]:
    """One signed page (4 to 8) as plain lines. A page that waited for its record says so in its own words."""
    key, rows = page["key"], page.get("rows") or []
    if page.get("status") in ("missing", "empty") or (key != "build" and not rows):
        return [one_line(page.get("text") or "Nothing recorded.")]
    if key == "measures":
        return [one_line(f"{r['problem']}: " + (", ".join(f"{m['name']} ({m['state']})" for m in r["measures"]) or "No measure yet")) for r in rows]
    if key == "processes":
        return [one_line(f"{r['name']}, {r['chip']}, owner {r['owner'] or NOT_NAMED}") for r in rows]
    if key == "sources":
        out = [one_line(f"{r['name']}: {r['state']}. Source owner {r['source_owner'] or NOT_NAMED}, data owner {r['data_owner'] or NOT_NAMED}, "
                        f"business owner {r['business_owner'] or NOT_NAMED}") for r in rows]
        return out + ([f"{page['restricted']} restricted {'source is' if page['restricted'] == 1 else 'sources are'} not listed."] if page.get("restricted") else [])
    if key == "roles":
        return [one_line(f"{r['label']}: {r['person'] or NOT_NAMED}") for r in rows]
    needed = {True: "Yes", False: "No"}.get(page.get("needed"), "Not answered")
    return [f"Build needed: {needed}"] + [one_line(f"{l['label']}: {'Passes' if l['ok'] else 'Does not pass yet'}") for l in page.get("lines") or []]


def _frozen(view: dict) -> list[tuple[str, list[str]]]:
    """Pages 4 to 8 and 10 as signed, for the download. Empty for a view that carries no frozen copy."""
    f = view.get("frozen") or {}
    out = [(f"{p['n']}. {p['title']}", _frozen_lines(p)) for p in f.get("pages") or []]
    if f.get("pages") is not None and "risks" in f:
        out.append(("10. Known risks", [one_line(r["text"]) + (f" Accepted by {one_line(r['accepted_by'], 80)}." if r.get("accepted_by") else "")
                                         for r in f["risks"]] or ["No known risks."]))
    return out


def to_markdown(view: dict, company: str, title: str, illustrative: bool) -> str:
    d = _head(view, company, title, illustrative)
    out = [f"# Intent charter: {md(d['company'])}" + (" (Illustrative)" if illustrative else ""), "", f"**Session:** {md(d['title'])}", f"**Date:** {md(d['date'])}"]
    if d["wall"]:
        out += ["", "## What the committee put on the wall"]
        for lane, n, cards in d["wall"]:
            out += ["", f"### {md(lane)} ({n})", ""] + [f"- {md(x)}" for x in cards]
    for heading, rows in d["sections"]:
        out += ["", f"## {md(heading)}", ""] + ([f"- {NONE_RAISED}"] if not rows else [])
        for i, r in enumerate(rows, 1):
            out += [f"{i}. **{md(r['title'])}** ({md(r['priority'])})"] + ([f"   {md(r['so_that'])}"] if r["so_that"] else [])
            out += [f"   {md(x)}" for x in r["details"]]
    if d["later"]:
        out += ["", "## Left for later", ""] + [f"- {md(x)}" for x in d["later"]]
    if d["parked"]:
        out += ["", "## 9. Parked for later", ""] + [f"- {md(x)}" for x in d["parked"]]
    for heading, lines in _frozen(view):
        out += ["", f"## {md(heading)}", ""] + [f"- {md(x)}" for x in lines]
    return "\n".join(out + ["", "## Signed by", ""] + [f"- {md(n)}, {md(at)}" for n, at in d["signers"]] + ["", d["line"], ""])


def to_html(view: dict, company: str, title: str, illustrative: bool) -> str:
    d, e = _head(view, company, title, illustrative), escape
    tag = ' <span class="tag">Illustrative</span>' if illustrative else ""
    rows = "".join(f"<h2>{e(h)}</h2>" + ("<ol>" + "".join(
        f"<li><strong>{e(r['title'])}</strong> <em>{e(r['priority'])}</em>" + (f"<br>{e(r['so_that'])}" if r["so_that"] else "")
        + "".join(f"<br>{e(x)}" for x in r["details"]) + "</li>" for r in rs) + "</ol>" if rs else f"<p>{NONE_RAISED}</p>")
        for h, rs in d["sections"])
    wall = ("<h2>What the committee put on the wall</h2>" + "".join(
        f"<h3>{e(l)} ({n})</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in cs) + "</ul>" for l, n, cs in d["wall"])) if d["wall"] else ""
    later = "<h2>Left for later</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in d["later"]) + "</ul>" if d["later"] else ""
    parked = "<h2>9. Parked for later</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in d["parked"]) + "</ul>" if d["parked"] else ""
    frozen = "".join(f"<h2>{e(h)}</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in ls) + "</ul>" for h, ls in _frozen(view))
    sig = "".join(f"<li>{e(n)}, {e(at)}</li>" for n, at in d["signers"])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Intent charter: {e(d['company'])}</title><style>body{{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#111}}"
            "em{color:#555;font-style:normal;border:1px solid #bbb;border-radius:4px;padding:0 .4rem;font-size:.85em}"
            ".tag{border:1px solid #b45309;color:#b45309;border-radius:4px;padding:0 .4rem;font-size:.6em;vertical-align:middle}"
            "li{margin:.6rem 0}@media print{body{margin:0}}</style></head><body>"
            f"<h1>Intent charter: {e(d['company'])}{tag}</h1><p>{e(d['title'])}<br>{e(d['date'])}</p>"
            f"{wall}{rows}{later}{parked}{frozen}<h2>Signed by</h2><ul>{sig}</ul><p>{e(d['line'])}</p></body></html>")


def email_text(view: dict, company: str, title: str, link_path: str) -> dict:
    """Subject and plain body for the people who took part. The link is the charter's own path (the screen adds the site)."""
    d = _head(view, company, title, False)
    lines = [f"{i}. {r['title']} ({r['priority']})" for i, r in enumerate(d["sections"][0][1], 1)]  # what was agreed to work on: the intent list; the other lists are in the download
    body = (f"Hello,\n\nThank you for taking part in the session \"{d['title']}\". The charter was signed on {d['date']}.\n\n"
            "What we agreed to work on:\n" + "\n".join(lines) + f"\n\nYou can read and download the charter here:\n{link_path}\n\nThank you.\n")
    return {"subject": f"The signed charter: {d['title']}"[:120], "body": body}


def safe_filename(company: str, date: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", f"charter-{company}-{date}").strip("-").lower()
