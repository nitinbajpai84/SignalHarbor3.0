"""Capital call / distribution notice PDFs from docs/test/10uc_universe.json.

Deterministic, no randomness. Hand-written PDF (reportlab and fpdf2 are not installed).
"""
import json
import datetime as dt
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
OUT = ROOT / "tests/v1/fixtures/10uc/notices"
FUND = {f["key"]: f for f in U["funds"]}
MGR = {m["id"]: m for m in U["managers"]}
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
COM = {c["fund"]: c for c in U["commitments"]}
PLANT = {"mv-2026-10-C-call": "P21", "mv-2026-10-E-call": "P21, P22 (noticed, not confirmed)",
         "mv-2026-11-A-dist": "P23", "mv-2026-12-D-call": "P23"}


def money(x):
    return f"{D(x):,.2f}"


def dlong(s):
    return dt.date.fromisoformat(s).strftime("%d %B %Y")


def esc(t):
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(ops, title):
    """ops: ('t', x, y, size, bold, text) or ('l', x1, y1, x2, y2). One A4 page."""
    c = []
    for o in ops:
        if o[0] == "t":
            c.append(f"BT /{'F2' if o[4] else 'F1'} {o[3]} Tf {o[1]} {o[2]} Td ({esc(o[5])}) Tj ET")
        else:
            c.append(f"{o[1]} {o[2]} m {o[3]} {o[4]} l S")
    stream = "\n".join(c).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            f"<< /Title ({esc(title)}) /Producer (Synthetic notice generator) >>".encode()]
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for of in offs:
        out += f"{of:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 7 0 R >>\n"
            f"startxref\n{x}\n%%EOF\n").encode()
    return bytes(out)


# running cumulative called per fund, in notice order
rows = []
cum = {k: D(c["called_before_2025_08"]) for k, c in COM.items()}
for m in sorted(U["cash_movements"], key=lambda m: (m["notice_date"], m["id"])):
    amt = D(m["amount"])
    if m["notice_kind"] == "call":
        cum[m["fund"]] += amt
        assert cum[m["fund"]] <= D(COM[m["fund"]]["commitment_amount"]), m["id"]
    rows.append(dict(m, amt=amt, cum=cum[m["fund"]]))


def notice(r, seq):
    f = FUND[r["fund"]]
    mg = MGR[f["manager"]]
    com = D(COM[r["fund"]]["commitment_amount"])
    call = r["notice_kind"] == "call"
    lp = ENT[r["legal_entity"]]
    code = f["identifiers"]["administrator"]["administrator_code"]
    ref = f"{mg['id'][4:8]}/{r['notice_date'][:4]}/{seq:03d}"
    kind = "CAPITAL CALL NOTICE" if call else "DISTRIBUTION NOTICE"
    ops = []

    def t(x, y, s, b=0, z=10):
        ops.append(("t", x, y, z, b, s))

    t(50, 790, mg["name"].upper(), 1, 16)
    t(50, 775, f"Investor Relations  |  {mg['contact_email']}", 0, 9)
    t(50, 762, f"Contact: {mg['contact_name']}", 0, 9)
    ops.append(("l", 50, 752, 545, 752))
    t(50, 730, kind, 1, 14)
    t(400, 730, f"Notice ref: {ref}", 0, 9)
    t(50, 705, f"Date of notice: {dlong(r['notice_date'])}")
    t(50, 690, f"Payment {'due' if call else 'value'} date: {dlong(r['due_date'])}", 1)
    t(50, 668, "To:", 1)
    t(90, 668, lp)
    t(90, 654, "Limited partner (investor)")
    t(50, 636, "Fund:", 1)
    t(90, 636, f["canonical_name"])
    t(90, 622, f"Administrator investor code: {code}")
    ops.append(("l", 50, 606, 545, 606))
    t(50, 588, "Amount " + ("to be paid by the investor" if call else "to be paid to the investor"), 1)
    t(380, 588, f"{r['currency']} {money(r['amt'])}", 1, 12)
    ops.append(("l", 50, 574, 545, 574))
    t(50, 556, "Commitment summary (after this notice)", 1)
    y = 538
    for a, b in (("Total commitment", com), ("Cumulative contributions called", r["cum"]),
                 ("Remaining uncalled commitment", com - r["cum"])):
        t(60, y, a)
        t(380, y, f"{r['currency']} {money(b)}")
        y -= 16
    if not call:
        t(60, y, "Note: a distribution does not reduce cumulative contributions called.")
        y -= 16
    y -= 8
    t(50, y, "Payment instructions", 1)
    y -= 16
    if call:
        lines = [f"Beneficiary: {f['canonical_name']} Fund Account", "Bank: Harbour Trust Bank (synthetic)",
                 f"Account: SYN-0000-{code}", f"Reference: {ref} / {lp}"]
    else:
        lines = [f"Funds will be remitted to the account on file for {lp}.", f"Reference: {ref}"]
    for s in lines:
        t(60, y, s)
        y -= 14
    y -= 10
    t(50, y, "This notice is issued under the limited partnership agreement. Late payment may incur default interest."
      if call else "This distribution is made under the distribution waterfall of the limited partnership agreement.", 0, 8)
    ops.append(("l", 50, 60, 545, 60))
    t(50, 46, f"{mg['name']} - synthetic document for test purposes only", 0, 8)
    t(480, 46, "Page 1 of 1", 0, 8)
    return make_pdf(ops, f"{kind.title()} {ref}")


def filename(r):
    return f"{r['notice_date']}_{FUND[r['fund']]['manager'][4:].lower()}_fund-{r['fund']}_{r['notice_kind']}.pdf"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.pdf"):
        p.unlink()
    man = ["# Notices fixtures (synthetic)", "",
           "Capital call and distribution notices for the Evergreen Office, generated by "
           "`tools/gen_10uc/notices.py` from `docs/test/10uc_universe.json` (one PDF per `cash_movements` row: "
           "14 months of notices from 4 Aug 2025 to 1 Sep 2026, plus 3 October 2026 notices still open). "
           "Managers, funds and investing entities are fictional.", "",
           "Cumulative called = commitments register `called_before_2025_08` plus calls noticed so far, in notice order. "
           "After the last call noticed on or before 30 Sep 2026 it equals `called_to_date` for every fund. "
           "Confirmation status (confirmed / noticed) is internal to the office and is not printed on the PDFs.", "",
           "| File | Movement id | Fund | Entity | Kind | Amount | Notice | Due | Cumulative called | Commitment | Planted facts |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    seqs = {}
    for r in rows:
        mid = FUND[r["fund"]]["manager"]
        seqs[mid] = seqs.get(mid, 0) + 1
        fn = filename(r)
        (OUT / fn).write_bytes(notice(r, seqs[mid]))
        man.append(f"| {fn} | {r['id']} | {r['fund']} | {r['legal_entity']} | {r['notice_kind']} | "
                   f"{r['currency']} {money(r['amt'])} | {r['notice_date']} | {r['due_date']} | {money(r['cum'])} | "
                   f"{money(COM[r['fund']]['commitment_amount'])} | {PLANT.get(r['id'], '')} |")
    man += ["", "Planted facts carried: P21 (Fund C 450,000 due 20 Oct; Fund E 600,000 due 30 Oct, noticed not "
            "confirmed), P22 (the Entity B calls behind the after-call cash), P23 (Fund D 250,000 due 4 Dec; Fund A "
            "distribution 320,000 expected 16 Nov), P24 (cumulative called vs commitment per fund).", ""]
    (OUT / "MANIFEST.md").write_text("\n".join(man), encoding="utf-8")


def verify():
    from pypdf import PdfReader
    for r in rows:
        tx = " ".join(PdfReader(OUT / filename(r)).pages[0].extract_text().split())
        for s in (money(r["amt"]), money(r["cum"]), money(COM[r["fund"]]["commitment_amount"]),
                  dlong(r["notice_date"]), dlong(r["due_date"]), ENT[r["legal_entity"]],
                  FUND[r["fund"]]["canonical_name"]):
            assert s in tx, (r["id"], s)
    for k, c in COM.items():
        calls = [r for r in rows if r["fund"] == k and r["notice_kind"] == "call" and r["notice_date"] <= "2026-09-30"]
        assert calls[-1]["cum"] == D(c["called_to_date"]), k
    print("verified", len(rows), "notices")


if __name__ == "__main__":
    main()
    verify()
