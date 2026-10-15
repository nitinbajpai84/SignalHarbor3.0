"""The catalogue as the template's Excel workbook (M2-18): the same tabs, header rows, columns, dropdown lists and formulas.

Reuse (D-031): harness/build_etl_mapping_workbook.py (378 lines) and emitters/intake_template_builder.py (311 lines) both write with openpyxl,
which this repo does not have and must not gain. What is copied is their shape (one sheet per section, a header row, widths, a hidden-style
Lists sheet, list validations) and what is new is the writer: zipfile and xml escaping from the stdlib, laid out like the template's own file
(inline strings, the template's styles, the same freeze panes, validations and formulas, formulas calculated again when Excel opens it).
ponytail: no theme part, no shared strings, no cell comments. Add them if a customer's Excel version refuses the file.

Not written: the template's two example rows (the file has only this baseline's rows), and rows a person may not see (M2-05; the caller
passes rows already filtered). It describes data and never contains it.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

from modules.m2_baseline.domain import catalogue as C

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml"
TITLE, BLURB, GUIDE, HEAD, BODY = 5, 6, 7, 8, 10  # the template's style numbers
BODY_TEXT = 12  # BODY with quotePrefix: text that starts like a formula stays text after a re-save
FIRST_ROW = 5
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# The template's styles, without its theme (the font names are explicit, so no theme part is needed).
STYLES = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet {NS}><numFmts count="0"/><fonts count="9">'
    '<font><name val="Calibri"/><family val="2"/><sz val="11"/></font>'
    '<font><b val="1"/><color rgb="00052A52"/><sz val="18"/></font><font><b val="1"/><color rgb="00052A52"/></font><font><b val="1"/></font>'
    '<font><b val="1"/><color rgb="00052A52"/><sz val="16"/></font><font><color rgb="006A7179"/></font>'
    '<font><b val="1"/><color rgb="00FFFFFF"/></font><font><i val="1"/><color rgb="006A7179"/><sz val="9"/></font>'
    '<font><i val="1"/><color rgb="006A7179"/></font></fonts>'
    '<fills count="4"><fill><patternFill/></fill><fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="00052A52"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="00EEF1F4"/></patternFill></fill></fills>'
    '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border>'
    + "".join(f'<{s} style="thin"><color rgb="00D5DBE1"/></{s}>' for s in ("left", "right", "top", "bottom")) +
    '</border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="13">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" applyAlignment="1" xfId="0"><alignment vertical="top"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" applyAlignment="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="7" fillId="0" borderId="0" applyAlignment="1" xfId="0"><alignment vertical="bottom" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="6" fillId="2" borderId="1" applyAlignment="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="8" fillId="3" borderId="1" applyAlignment="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyAlignment="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" quotePrefix="1" applyAlignment="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles><dxfs count="2">'
    '<dxf><fill><patternFill patternType="solid"><fgColor rgb="00CFEDEF"/><bgColor rgb="00CFEDEF"/></patternFill></fill></dxf>'
    '<dxf><fill><patternFill patternType="solid"><fgColor rgb="00F6E7D8"/><bgColor rgb="00F6E7D8"/></patternFill></fill></dxf></dxfs>'
    '<tableStyles count="0" defaultTableStyle="TableStyleMedium9" defaultPivotStyle="PivotStyleLight16"/></styleSheet>'
)


def _text(s: object) -> str:
    return escape(_ILLEGAL.sub("", str(s)))


def _s(ref: str, text: object, style: int | None = None) -> str:
    st = f' s="{style}"' if style is not None else ""
    return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{_text(text)}</t></is></c>'


def _f(ref: str, formula: str, cached: object, style: int = BODY) -> str:
    if isinstance(cached, (int, float)) and not isinstance(cached, bool):
        return f'<c r="{ref}" s="{style}"><f>{_text(formula)}</f><v>{cached}</v></c>'
    return f'<c r="{ref}" s="{style}" t="str"><f>{_text(formula)}</f><v>{_text(cached)}</v></c>'


def _col(i: int) -> str:
    return chr(ord("A") + i)


def _sheet(cols: str, rows: str, extra: str = "", view: str = "", color: str = "", dim: str = "") -> str:
    tab = f'<sheetPr><tabColor rgb="{color}"/></sheetPr>' if color else ""
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet {NS}>{tab}<dimension ref="{dim}"/>'
            f'<sheetViews><sheetView workbookViewId="0">{view}</sheetView></sheetViews><sheetFormatPr baseColWidth="8" defaultRowHeight="15"/>'
            f'<cols>{cols}</cols><sheetData>{rows}</sheetData>{extra}'
            '<pageMargins left="0.75" right="0.75" top="1" bottom="1" header="0.5" footer="0.5"/></worksheet>')


def _widths(ws: list[float]) -> str:
    return "".join(f'<col width="{w:g}" customWidth="1" min="{i}" max="{i}"/>' for i, w in enumerate(ws, 1))


def _read_me(c: dict, stamp: str = "") -> str:
    rm, rows = c["read_me"], []
    for r in rm["rows"]:
        n, cells = r["row"], []
        if r.get("a"):
            cells.append(_s(f"A{n}", f"{r['a']} ({stamp})" if stamp and n == 1 else r["a"], 1 if n == 1 else 4 if r["a"] == "Version" else 2))
        if r.get("b"):
            cells.append(_s(f"B{n}", r["b"], None if r["a"] == "Version" else 3))
        rows.append(f'<row r="{n}">{"".join(cells)}</row>')
    last = max(r["row"] for r in rm["rows"])
    return _sheet(_widths(rm["widths"]), "".join(rows), color=rm["tab_color"], dim=f"A1:B{last}")


def _lists(c: dict) -> str:
    cols = c["lists"]["columns"]
    depth = max(len(v) for v in cols.values())
    rows = ['<row r="1">' + "".join(_s(f"{_col(i)}1", name, 11) for i, name in enumerate(cols)) + "</row>"]
    for r in range(depth):
        cells = "".join(_s(f"{_col(i)}{r + 2}", v[r]) for i, v in enumerate(cols.values()) if r < len(v))
        rows.append(f'<row r="{r + 2}">{cells}</row>')
    return _sheet(_widths([c["lists"]["width"]] * len(cols)), "".join(rows), color=c["lists"]["tab_color"], dim=f"A1:{_col(len(cols) - 1)}{depth + 1}")


def _cell_text(tab: str, header: str, cell: object) -> str:
    """What goes in the cell. An unknown stays blank, except where the template says to write "Unknown" and a named person said so."""
    if (tab, header) == ("tables", "Related KPIs") and C.said_unknown(cell):
        return "Unknown"
    if (tab, header) == ("fields", "Business meaning") and cell is not None and C.is_blank(cell):
        return C.NOT_YET  # a missing meaning says so, in the words the screens use
    return C.text_of(cell)


def _tab(c: dict, tab: str, rows: list[dict]) -> str:
    spec, last = c["tabs"][tab], max(c["export"]["last_row"], FIRST_ROW + len(rows) - 1)
    cols = spec["columns"]
    head = [f'<row r="1">{_s("A1", spec["title"], TITLE)}</row>', f'<row r="2">{_s("A2", spec["blurb"], BLURB)}</row>',
            '<row r="3" ht="36" customHeight="1">' + "".join(_s(f"{k['letter']}3", k["guidance"] or "", GUIDE) for k in cols) + "</row>",
            '<row r="4" ht="44" customHeight="1">' + "".join(_s(f"{k['letter']}4", k["header"], HEAD) for k in cols) + "</row>"]
    body = []
    for n in range(FIRST_ROW, last + 1):
        row = rows[n - FIRST_ROW] if n - FIRST_ROW < len(rows) else None
        cells = []
        for k in cols:
            ref, h = f"{k['letter']}{n}", k["header"]
            if C.is_computed(k):
                cached = C.text_of(row.get(h)) if row else ""
                cells.append(_f(ref, k["formula"].replace("{r}", str(n)), int(cached) if cached.isdigit() else cached))
            else:
                t = _cell_text(tab, h, row.get(h)) if row else ""
                cells.append(_s(ref, t, BODY_TEXT if t[0] in "=+-@" else BODY) if t else f'<c r="{ref}" s="{BODY}"/>')
        body.append(f'<row r="{n}">{"".join(cells)}</row>')
    sc = spec["conditional_column"]
    good, bad = ("Ready", "Not ready") if tab == "kpis" else ("Complete", "Missing")
    second = f'{sc}{FIRST_ROW}="{bad}"' if tab == "kpis" else f'LEFT({sc}{FIRST_ROW},7)="{bad}"'
    cf = (f'<conditionalFormatting sqref="{sc}{FIRST_ROW}:{sc}{last}"><cfRule type="expression" priority="1" dxfId="0">'
          f'<formula>{sc}{FIRST_ROW}="{good}"</formula></cfRule><cfRule type="expression" priority="2" dxfId="1"><formula>{escape(second)}</formula>'
          '</cfRule></conditionalFormatting>')
    dvs = [k for k in cols if k.get("validation")]
    dv = f'<dataValidations count="{len(dvs)}">' + "".join(
        f'<dataValidation type="list" errorStyle="warning" allowBlank="1" showErrorMessage="1" errorTitle="Not in the list" '
        f'error="That value is not in the list. Keep it only if you need it." sqref="{k["letter"]}{FIRST_ROW}:{k["letter"]}{last}">'
        f'<formula1>{escape(k["validation"].replace("204", str(last)) if "$204" in k["validation"] else k["validation"])}</formula1></dataValidation>'
        for k in dvs) + "</dataValidations>"
    x, y = spec["freeze"]["x"], spec["freeze"]["y"]
    view = (f'<pane xSplit="{x}" ySplit="{y}" topLeftCell="{_col(x)}{y + 1}" activePane="bottomRight" state="frozen"/>'
            '<selection pane="topRight"/><selection pane="bottomLeft"/><selection pane="bottomRight" activeCell="A1" sqref="A1"/>')
    return _sheet(_widths([k["width"] for k in cols]), "".join(head + body), cf + dv, view, spec["tab_color"], f"A1:{cols[-1]['letter']}{last}")


GOVERNANCE_SHEET = "Governance"
GOVERNANCE_HEADS = ("Level", "Name", "Belongs to", "Holds personal data", "Sensitive to the business", "Who may see it", "Decided by", "Decided on", "Still undecided")
GOVERNANCE_WIDTHS = (12, 34, 30, 20, 16, 40, 20, 12, 44)


TECHNICAL_SHEET = "Technical definitions"
TECHNICAL_HEADS = ("Measure ID", "Measure", "Calculation", "Sources", "Tables", "Fields", "Filters", "Grain", "Period", "Currency basis", "Notes", "Confirmed by the data owner")
TECHNICAL_WIDTHS = (12, 28, 60, 28, 28, 36, 30, 20, 20, 24, 36, 26)


def _governance(rows: list[list[str]]) -> str:
    """M2-E3: the governance view as a sheet: the rows the person may see, one per measure, source and field."""
    return _list_sheet("Governance", "Who may see each measure, source and field, and whether it holds personal data. Only what you may see is listed.",
                       GOVERNANCE_HEADS, GOVERNANCE_WIDTHS, rows, "FF2E7D6B")


def _technical(rows: list[list[str]]) -> str:
    """M2-E1: the technical definition of each measure the person may see: where the data comes from, the fields and the calculation steps."""
    return _list_sheet(TECHNICAL_SHEET, "For each measure: the sources, tables and fields it uses (as named in tabs 1 to 4) and how it is calculated. Only what you may see is listed.",
                       TECHNICAL_HEADS, TECHNICAL_WIDTHS, rows, "FF7A5BA6")


def _list_sheet(title: str, blurb: str, heads: tuple, widths: tuple, rows: list[list[str]], color: str) -> str:
    head = [f'<row r="1">{_s("A1", title, TITLE)}</row>',
            f'<row r="2">{_s("A2", blurb, BLURB)}</row>',
            '<row r="4" ht="32" customHeight="1">' + "".join(_s(f"{_col(i)}4", h, HEAD) for i, h in enumerate(heads)) + "</row>"]
    cell = lambda n, i, t: (_s(f"{_col(i)}{n}", t, BODY_TEXT if t[0] in "=+-@" else BODY) if t else f'<c r="{_col(i)}{n}" s="{BODY}"/>')  # noqa: E731
    body = [f'<row r="{n}">' + "".join(cell(n, i, t) for i, t in enumerate(r)) + "</row>" for n, r in enumerate(rows, FIRST_ROW)]
    last = FIRST_ROW + max(len(rows), 1) - 1
    view = '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A5" sqref="A5"/>'
    return _sheet(_widths(list(widths)), "".join(head + body), "", view, color, f"A1:{_col(len(heads) - 1)}{last}")


def build_xlsx(shown: dict, governance: list[list[str]] | None = None, technical: list[list[str]] | None = None, stamp: str = "") -> bytes:
    """The workbook as bytes. `shown` is C.with_derived(...) of the rows the person may see (hidden rows already left out).
    `governance` (the view's rows, already filtered for the person) adds the Governance sheet."""
    c = C.contract()
    sheets = [("Read me", _read_me(c, stamp))] + [(c["tabs"][t]["sheet"], _tab(c, t, shown[t])) for t in C.TABS]
    if governance is not None:
        sheets.append((GOVERNANCE_SHEET, _governance(governance)))
    if technical is not None:
        sheets.append((TECHNICAL_SHEET, _technical(technical)))
    sheets.append(("Lists", _lists(c)))
    wb = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {NS} xmlns:r="{REL}"><bookViews><workbookView activeTab="0"/></bookViews><sheets>'
          + "".join(f'<sheet name="{_text(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1))
          + '</sheets><calcPr calcId="124519" fullCalcOnLoad="1"/></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="{REL}/styles" Target="styles.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             f'<Override PartName="/xl/workbook.xml" ContentType="{MEDIA}.sheet.main+xml"/>'
             f'<Override PartName="/xl/styles.xml" ContentType="{MEDIA}.styles+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{MEDIA}.worksheet+xml"/>' for i in range(1, len(sheets) + 1))
             + "</Types>")
    root = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", root)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return out.getvalue()
