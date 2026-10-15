"""The glossary as an Excel file and as a printable page (M2-E2). Both are drawn from `glossary.flat` rows, the same words as the screen.

Reuse (D-031): the workbook is written with domain/xlsx_export.py's own cell, sheet and style helpers (inline strings, the template's styles,
text that starts like a formula kept as text); only the zip packaging is repeated here, because `build_xlsx` is tied to the catalogue's tabs.
The printable page follows modules/m1_intent/domain/charter_export.py (every value escaped, a print style, a safe file name); `one_line`
and `safe_filename` are copied from it, because a module never imports another module.
"""
import io
import re
import zipfile
from html import escape

from modules.m2_baseline.domain import xlsx_export as X

MAIN = ("Term", "Also called", "Business definition", "How sure", "Owner", "How often reported", "Who may see it", "Personal data",
        "Change", "Source document", "Reviewed", "Where the number comes from")
MAIN_KEYS = ("term", "aliases", "definition", "how_sure", "owner", "frequency", "who", "personal", "change", "source", "reviewed", "data_source")
CHANGES = ("Term", "Change", "Previous (your glossary)", "New (this baseline)", "Assumption", "Decided by")
ONLY_YOURS = "In your glossary only"
NOT_YET = "Not available yet"


def one_line(s, cap: int = 300) -> str:
    return " ".join(str(s).split())[:cap].rstrip()


def safe_filename(company: str, kind: str = "business-glossary") -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", f"{kind}-{company}").strip("-").lower()


def change_rows(rows: list[dict], unmatched: list[dict]) -> list[list[str]]:
    """What changed or is new, then what is only in the provided glossary. Unchanged entries are not listed."""
    out = [[r["term"], r["change"], r["previous"], r["definition"], r["assumption"], r["decided_by"]] for r in rows if r["change"] != "Unchanged"]
    return out + [[t["term"], ONLY_YOURS, t["definition"] or NOT_YET, "", "", ""] for t in unmatched]


def _grid(title: str, blurb: str, head: tuple, body: list[list[str]], widths: list[float]) -> str:
    cell = lambda ref, t: X._s(ref, t, X.BODY_TEXT if t[:1] in ("=", "+", "-", "@") else X.BODY)  # noqa: E731
    rows = [f'<row r="1">{X._s("A1", title, X.TITLE)}</row>', f'<row r="2">{X._s("A2", blurb, X.BLURB)}</row>',
            '<row r="4" ht="30" customHeight="1">' + "".join(X._s(f"{X._col(i)}4", h, X.HEAD) for i, h in enumerate(head)) + "</row>"]
    rows += [f'<row r="{n}">' + "".join(cell(f"{X._col(i)}{n}", str(v)) if str(v) else f'<c r="{X._col(i)}{n}" s="{X.BODY}"/>' for i, v in enumerate(r)) + "</row>"
             for n, r in enumerate(body, 5)]
    view = '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A5" sqref="A5"/>'
    return X._sheet(X._widths(widths), "".join(rows), view=view, dim=f"A1:{X._col(len(head) - 1)}{max(4, 4 + len(body))}")


def build_xlsx(company: str, rows: list[dict], unmatched: list[dict], illustrative: bool = False, stamp: str = "") -> bytes:
    """`stamp` (M2-E4): "Draft, not signed", or who signed and when, written in the title so the document says what it is."""
    tag = (" (Illustrative)" if illustrative else "") + (f" ({stamp})" if stamp else "")
    sheets = [("Business glossary", _grid(f"Business glossary: {company}{tag}", "One row per measure. Every wording is stated by a named person or marked as a guess.",
                                          MAIN, [[r[k] for k in MAIN_KEYS] for r in rows], [26, 24, 60, 22, 22, 18, 26, 14, 12, 26, 24, 30])),
              ("Changes", _grid("What changed against your glossary", "Previous is the wording you provided; new is this baseline's wording.",
                                CHANGES, change_rows(rows, unmatched), [26, 20, 50, 50, 50, 30]))]
    ns, rel, media = X.NS, X.REL, X.MEDIA
    wb = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns} xmlns:r="{rel}"><sheets>'
          + "".join(f'<sheet name="{X._text(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1))
          + '</sheets><calcPr calcId="124519" fullCalcOnLoad="1"/></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="{rel}/styles" Target="styles.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
             f'<Override PartName="/xl/workbook.xml" ContentType="{media}.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="{media}.styles+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{media}.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + "</Types>")
    root = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in (("[Content_Types].xml", types), ("_rels/.rels", root), ("xl/workbook.xml", wb), ("xl/_rels/workbook.xml.rels", rels), ("xl/styles.xml", X.STYLES)):
            z.writestr(name, data)
        for i, (_, xml) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return out.getvalue()


def to_html(company: str, rows: list[dict], unmatched: list[dict], illustrative: bool = False, stamp: str = "") -> str:
    e = escape
    tag = (' <span class="tag">Illustrative</span>' if illustrative else "") + (f' <span class="tag">{e(one_line(stamp, 120))}</span>' if stamp else "")
    table = lambda head, body: ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>"  # noqa: E731
                                + "".join("<tr>" + "".join(f"<td>{e(one_line(c, 2000))}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
    changes = change_rows(rows, unmatched)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Business glossary: {e(one_line(company, 120))}</title><style>body{{font:15px/1.45 system-ui,sans-serif;margin:2rem;color:#111}}"
            "table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #bbb;padding:.35rem .5rem;text-align:left;vertical-align:top}"
            "th{background:#eef1f4}.tag{border:1px solid #b45309;color:#b45309;border-radius:4px;padding:0 .4rem;font-size:.6em;vertical-align:middle}"
            "@media print{body{margin:0}}</style></head><body>"
            f"<h1>Business glossary: {e(one_line(company, 120))}{tag}</h1>" + table(MAIN, [[r[k] for k in MAIN_KEYS] for r in rows])
            + "<h2>What changed against your glossary</h2>" + (table(CHANGES, changes) if changes else "<p>Nothing differs from your glossary.</p>") + "</body></html>")
