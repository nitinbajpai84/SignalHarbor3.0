"""Deterministic file writers (pdf, xlsx, eml, csv) for the Evergreen Office 6-month generator.
The PDF writer is the hand-written one from tools/gen_10uc/notices.py (no timestamps); xlsx zips get a fixed date."""
import base64
import csv
import io
import re
import zipfile
import datetime as dt
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

FIXED = dt.datetime(2026, 1, 1)


class Registry:
    """Every written file: path (relative to OUT), kind, month, description, tags (mess ids)."""
    def __init__(self, out):
        self.out, self.rows = Path(out), []

    def path(self, month, kind, name):
        p = self.out / month / kind / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def add(self, p, kind, month, desc, mess=()):
        self.rows.append(dict(path=Path(p).relative_to(self.out).as_posix(), kind=kind, month=month, desc=desc, mess=list(mess)))


BS = chr(92)


def esc(t):
    return str(t).replace(BS, BS * 2).replace("(", BS + "(").replace(")", BS + ")").encode("latin-1", "replace").decode("latin-1")


def pdf_bytes(title, lines):
    """lines: (text, bold, size) or text or '---' for a rule. One A4 page, top-down flow."""
    ops, y = [], 800
    for ln in lines:
        if ln == "---":
            ops.append(f"50 {y + 4} m 545 {y + 4} l S"); y -= 8; continue
        t, b, z = (ln, 0, 10) if isinstance(ln, str) else (ln[0], ln[1], ln[2] if len(ln) > 2 else 10)
        ops.append(f"BT /{'F2' if b else 'F1'} {z} Tf 50 {y} Td ({esc(t)}) Tj ET")
        y -= z + 5
        assert y > 40, f"pdf overflow: {title}"
    stream = "\n".join(ops).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            f"<< /Title ({esc(title)}) /Producer (Evergreen Office synthetic generator) >>".encode()]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for of in offs:
        out += f"{of:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 7 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return bytes(out)


def write_pdf(p, title, lines):
    Path(p).write_bytes(pdf_bytes(title, lines))


def write_xlsx(p, sheets, money_cols=()):
    """sheets: {name: [header, *rows]} (a leading list of 'title' rows is allowed via ('__title__', [...]) not needed)."""
    wb = Workbook(); wb.remove(wb.active)
    wb.properties.creator = "Evergreen Office synthetic generator"; wb.properties.created = wb.properties.modified = FIXED
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
        for i in range(1, ws.max_column + 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = 18
    buf = io.BytesIO(); wb.save(buf)
    zin = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in sorted(zin.namelist()):
            zi = zipfile.ZipInfo(n, (2026, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
            data = zin.read(n)
            if n == "docProps/core.xml":  # openpyxl stamps the save time into this part
                data = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", rb"\g<1>2026-01-01T00:00:00Z", data)
            zout.writestr(zi, data)


def write_csv(p, header, rows):
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(rows)


def write_eml(p, frm, to, subject, when, body, mid, attach=None, extra=()):
    """when: datetime. attach: (filename, bytes) or None. Fixed boundary so output is byte-stable."""
    d = when.strftime("%a, %d %b %Y %H:%M:%S +0000")
    h = [f"From: {frm}", f"To: {to}", f"Subject: {subject}", f"Date: {d}", f"Message-ID: <{mid}@office6m.example.test>", "MIME-Version: 1.0", *extra]
    if attach:
        b = "=====office6m-boundary====="
        h.append(f'Content-Type: multipart/mixed; boundary="{b}"')
        b64 = base64.encodebytes(attach[1]).decode()
        txt = "\n".join(h) + f'\n\n--{b}\nContent-Type: text/plain; charset="utf-8"\n\n{body}\n\n--{b}\nContent-Type: application/pdf; name="{attach[0]}"\nContent-Transfer-Encoding: base64\nContent-Disposition: attachment; filename="{attach[0]}"\n\n{b64}\n--{b}--\n'
    else:
        txt = "\n".join(h + ['Content-Type: text/plain; charset="utf-8"']) + f"\n\n{body}\n"
    Path(p).write_bytes(txt.replace("\r\n", "\n").encode("utf-8"))
