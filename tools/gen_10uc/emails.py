"""Deterministic generator: synthetic manager and internal emails (.eml, plain text) from docs/test/10uc_universe.json.
Run: python tools/gen_10uc/emails.py   (no randomness; same output every run)"""
import json, re, datetime as dt
from pathlib import Path
from email.message import EmailMessage
from email.utils import format_datetime
from email import policy, message_from_binary_file

ROOT = Path(__file__).resolve().parents[2]
U = json.load(open(ROOT / "docs/test/10uc_universe.json", encoding="utf-8"))
OUT = ROOT / "tests/v1/fixtures/10uc/emails"
OUT.mkdir(parents=True, exist_ok=True)

MG = {m["id"]: m for m in U["managers"]}
FUND = {f["key"]: f for f in U["funds"]}
ST = {s["statement_id"]: s for s in U["statements"]}
OFFICE = "Evergreen Office"
DOM = "example.test"


PEOPLE = {p["name"]: p["email"] for p in U["people"]}


def addr(name):  # office address, as the universe holds it
    return PEOPLE[name]


def maddr(m):  # manager address, as the universe holds it
    return MG[m]["contact_email"]


def money(v):
    return f"{float(v):,.0f}"


def pdate(s):
    return dt.date.fromisoformat(s[:10])


def long(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def bd_between(a, b):  # weekdays after a up to and including b
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        n += d.weekday() < 5
    return n


def utc(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def me(n):
    return f"{n} <{addr(n)}>"


FOOT_OFF = f"{OFFICE} | Operations | Synthetic test data, not a real communication."
manifest = []


def write(fname, sender, to, subject, when, body, cc=(), what="", facts="", in_reply_to=None, refs=None, draft=False, att=None):
    n = len(manifest) + 1
    m = EmailMessage(policy=policy.SMTP)
    m["From"], m["To"] = sender, ", ".join(to)
    if cc:
        m["Cc"] = ", ".join(cc)
    m["Subject"] = subject
    m["Date"] = format_datetime(when)
    mid = f"<10uc-{n:03d}@{DOM}>"
    m["Message-ID"] = mid
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
    if refs:
        m["References"] = " ".join(refs)
    if draft:
        m["X-Unsent"] = "1"
    if att:
        m["X-Attachments-Listed"] = att
    m.set_content(body.strip("\n") + "\n", cte="7bit")
    (OUT / fname).write_bytes(m.as_bytes())
    manifest.append((fname, what, facts, mid))
    return mid


def mgr_sig(mid):
    m = MG[mid]
    return (f"Kind regards,\n{m['contact_name']}\n{m['name']}\n{maddr(mid)}\n\n"
            "This email and any attachment are confidential and intended for the addressee only. Synthetic test data.")


# ---------- 1. statement deliveries ----------
def delivery(sid, fname, name_idx=0, extra="", what="", facts="", subject_tag=""):
    s = ST[sid]
    f = FUND[s["fund"]]
    m = MG[f["manager"]]
    names = f["identifiers"]["manager_email"]["manager_fund_name"]
    fn = names[name_idx]
    pe = pdate(s["period_end"])
    label = {"final": "Statement", "estimate": "Estimated statement", "amended": "Amended statement"}[s["kind"]]
    body = f"""Dear {OFFICE} team,

Please find attached the {label.lower()} for {fn} as at {long(pe)}.

  Fund:              {fn}
  Administrator ref: {f['identifiers']['administrator']['administrator_code']}
  Statement date:    {long(pe)}
  Status:            {s['kind']}
  Net asset value:   USD {money(s['value'])}
{extra}
Please let us know if you have any questions.

{mgr_sig(f['manager'])}
"""
    write(fname, f"{m['contact_name']} <{maddr(f['manager'])}>", [me("Mei Chen")],
          f"{fn} - {label} {pe.strftime('%d %b %Y')}{subject_tag}", utc(s["received_at"]), body,
          att=f"{f['key']}_{s['period_end']}_{s['kind']}.pdf", what=what, facts=facts)


SEP = [("A", "estimate", 0, "Figure is an estimate; the final statement follows once the administrator closes the period.\n"),
       ("B", "final", 2, ""), ("E", "final", 0, ""),
       ("H1", "estimate", 0, "Figure is an estimate pending the administrator close.\n"),
       ("H2", "estimate", 0, "Figure is an estimate pending the administrator close.\n"),
       ("L1", "final", 0, ""), ("L2", "final", 0, "")]
plant_sep = {"A": "P01, P09", "B": "P01, P09", "E": "P04, P07, P09", "H1": "P05, P09", "H2": "P05, P09", "L1": "P09", "L2": "P09"}
for k, kind, idx, extra in SEP:
    sid = f"stmt-{k}-2026-09-30-{kind}"
    delivery(sid, f"01_delivery_{k}_2026-09-30_{kind}.eml", idx, extra,
             what=f"Manager delivers the 30 Sep 2026 {kind} statement for fund {k}",
             facts=f"{plant_sep[k]}: USD {money(ST[sid]['value'])} received {ST[sid]['received_at'][:10]}")

delivery("stmt-D-2026-03-31-final", "02_delivery_D_2026-03-31_final_late.eml", 1,
         "Apologies for the short delay in issuing this statement.\n",
         what="Fund D March 2026 statement, 5 business days late",
         facts="P10: due 2026-04-14, received 2026-04-21, 5 bd late; USD 4,650,000")
delivery("stmt-E-2026-06-30-final", "02_delivery_E_2026-06-30_final_late.eml", 0, "",
         what="Fund E June 2026 statement, 8 business days late",
         facts="P10: due 2026-07-14, received 2026-07-24, 8 bd late; USD 9,600,000")
delivery("stmt-H2-2026-08-31-final", "02_delivery_H2_2026-08-31_final_late.eml", 0,
         "Please see our separate note regarding the timing of this statement.\n",
         what="Fund H2 August 2026 statement, 6 business days late (apology same day, file 03)",
         facts="P10, P26: due 2026-09-14, received 2026-09-22, 6 bd late; USD 5,090,000")

# ---------- 2. late-statement apology (H2 August) ----------
h2 = ST["stmt-H2-2026-08-31-final"]
assert h2["late_business_days"] == 6
write("03_apology_H2_august_late.eml", f"{MG['MGR-KESTREL']['contact_name']} <{maddr('MGR-KESTREL')}>", [me("Mei Chen")],
      "Apology: late August 2026 statement, Kestrel Ridge Equity L/S", utc(h2["received_at"]) + dt.timedelta(minutes=5),
      f"""Dear Mei,

I am sorry that the August 2026 statement for Kestrel Ridge Equity L/S was delivered on 22 September 2026, {h2['late_business_days']} business days after the 14 September due date.
The delay came from the administrator's month-end valuation review, which ran longer than planned. The August net asset value is USD {money(h2['value'])}.

We have added a second reviewer so that the September statement is not delayed. The estimate for 30 September was sent on 7 October.

{mgr_sig('MGR-KESTREL')}
""", what="Manager apology for the late H2 August statement",
      facts="P10: 6 bd late, due 2026-09-14, received 2026-09-22; USD 5,090,000")

# ---------- 3. revision notice with amended statement (Fund A, 30 Sep) ----------
a = ST["stmt-A-2026-09-30-amended"]
ae = ST["stmt-A-2026-09-30-estimate"]
diff = float(a["value"]) - float(ae["value"])
assert diff == 180000
write("04_revision_notice_A_2026-09-30_amended.eml", f"{MG['MGR-NORTHGATE']['contact_name']} <{maddr('MGR-NORTHGATE')}>", [me("Mei Chen")],
      "Revision notice: Evergreen Growth I, 30 Sep 2026 (amended statement attached)", utc(a["received_at"]),
      f"""Dear {OFFICE} team,

This notice accompanies the amended statement for Evergreen Growth I as at 30 September 2026. It replaces the estimated statement sent on 2 October 2026.

  Previous (estimate): USD {money(ae['value'])}
  Amended:             USD {money(a['value'])}
  Change:              +USD {money(diff)} (+{diff / float(ae['value']) * 100:.2f}%)
  Reason:              final portfolio company valuations arrived after the estimate was prepared.

Please treat the amended statement as the official figure for the period and discard the estimate.

{mgr_sig('MGR-NORTHGATE')}
""", att="A_2026-09-30_amended.pdf", what="Revision notice sent with the Fund A amended statement",
      facts="P02, P03, P12: 10,000,000 -> 10,180,000 (+180,000, +1.80%), received 2026-10-07")

c = ST["stmt-C-2026-06-30-amended"]
assert float(c["value"]) - 8420000 == -145000
delivery("stmt-C-2026-06-30-amended", "05_delivery_C_2026-06-30_amended.eml", 0,
         f"This replaces the statement issued on {long(pdate(ST['stmt-C-2026-06-30-final']['received_at']))} (USD 8,420,000). The change of USD -145,000 reflects a write-down of one portfolio company.\n",
         what="Fund C amended June statement, revision stated in the body",
         facts="P12: 8,420,000 -> 8,275,000 (-145,000), received 2026-08-18", subject_tag=" (amended)")
delivery("stmt-H1-2026-07-31-amended", "05_delivery_H1_2026-07-31_amended.eml", 1,
         "This replaces the statement issued on 7 August 2026 (USD 7,050,000). The change of USD -37,500 is a fee accrual correction.\n",
         what="Fund H1 amended July statement under the second name 'KR Macro Fund Ltd - Class B USD'",
         facts="P12, P13: 7,050,000 -> 7,012,500 (-37,500), received 2026-08-20; same fund as 'Kestrel Ridge Macro Fund' (code 4481)",
         subject_tag=" (amended)")

# ---------- 4. internal follow-up chain ----------
mei, raj, dan = "Mei Chen", "Raj Patel", "Daniel Foo"
issued = U["report_issued"]
assert issued["lines"][0]["value"] == "10000000.00"
tot_sgd = issued["total_sgd"]
t0 = utc(a["received_at"]) + dt.timedelta(hours=4)
m1 = write("06_internal_1_mei_to_raj_daniel.eml", me(mei), [me(raj)],
           "Fund A amended statement over materiality - September report", t0,
           f"""Raj, Daniel,

Northgate sent an amended September statement for Evergreen Growth I this morning: USD {money(a['value'])} against the USD {money(ae['value'])} estimate used in the September investment report we issued on 3 October (cutoff 10:00 UTC, total USD 57,600,000 / SGD {float(tot_sgd):,.2f} at {issued['fx_rate_used']}).

The change is +USD {money(diff)} (+1.80%), above the CIO materiality of USD 100,000 / 0.5%. The EG-GROWTH investment view becomes 16,580,000 against the administrator NAV of 16,400,000; the whole difference is this revision.

I have not changed the issued report. Do you want the review reopened?

Mei
""", cc=[me(dan)], what="Internal: Mei flags the Fund A revision",
           facts="P01, P02, P03: 10,000,000 -> 10,180,000, +180,000, SGD 77,253,120.00 at 1.3412")
m2 = write("06_internal_2_raj_reply.eml", me(raj), [me(mei)],
           "Re: Fund A amended statement over materiality - September report", t0 + dt.timedelta(hours=1),
           """Mei,

Yes, reopen the review. The revision is over materiality, so we should show the issued figure and the known-now figure side by side rather than overwrite the issued one. Please also check whether the Fund E and H1/H2 timing differences are still the same after the NAV of 2 October.

Raj
""", cc=[me(dan)], in_reply_to=m1, refs=[m1], what="Internal: Raj asks to reopen the review", facts="P02, P04, P05")
m3 = write("06_internal_3_daniel_question.eml", me(dan), [me(mei), me(raj)],
           "Re: Fund A amended statement over materiality - September report", t0 + dt.timedelta(hours=3),
           """Mei, Raj,

Thanks. Two things before the investment committee: can Mei confirm with Northgate that the amended figure is final, and what is still outstanding from other managers? I know Cedarpoint's June statement is still missing.

Daniel
""", in_reply_to=m2, refs=[m1, m2], what="Internal: CIO asks what is outstanding", facts="P11")
dm = ST["stmt-D-2026-06-30-missing"]
overdue = bd_between(pdate(dm["due_date"]), dt.date(2026, 10, 9))
assert overdue == 63
cp = MG["MGR-CEDARPOINT"]
write("06_internal_4_mei_status.eml", me(mei), [me(dan), me(raj)],
      "Re: Fund A amended statement over materiality - September report", utc("2026-10-08T07:30:00Z"),
      f"""Daniel, Raj,

Northgate confirmed by phone that the amended USD {money(a['value'])} is final.

Outstanding statements as of today:
- Cedarpoint Opportunities Fund II (Fund D), 30 June 2026: due 14 July 2026, never received.
- Cedarpoint Ventures III (Fund C) and Fund D, 30 September 2026: due 14 October 2026, not yet late.
- Fund E September statement arrived today; I have not yet confirmed the extracted USD 9,950,000.

I have drafted a follow-up to {cp['contact_name']} at Cedarpoint for the June statement. It is saved as a draft and has not been sent; tell me if you want it changed first.

Mei
""", in_reply_to=m3, refs=[m1, m2, m3], what="Internal: Mei reports outstanding statements and the unsent draft",
      facts="P09, P11: D June due 2026-07-14, never received; E 9,950,000 unverified")

write("07_followup_draft_D_missing_June.eml", me(mei), [f"{cp['contact_name']} <{maddr('MGR-CEDARPOINT')}>"],
      "Missing statement: Cedarpoint Opportunities Fund II, 30 June 2026", utc("2026-10-08T07:45:00Z"),
      f"""Dear {cp['contact_name'].split()[0]},

We have not received the 30 June 2026 statement for Cedarpoint Opportunities Fund II (administrator ref {FUND['D']['identifiers']['administrator']['administrator_code']}). It was due on 14 July 2026 and is now {overdue} business days overdue.

The latest statement we hold for this fund is 31 March 2026 (USD 4,650,000). Could you send the June statement, or tell us when to expect it? We understood from our May call that the auditor change may have delayed reporting.

Best regards,
Mei Chen
Operations, {OFFICE}
{FOOT_OFF}
""", draft=True, what="Unsent follow-up draft to Hana Sato for Fund D June (X-Unsent header)",
      facts="P11: Hana Sato, fund D, 30 Jun 2026, due 2026-07-14, 63 bd overdue at 9 Oct; D last value 4,650,000")

# ---------- manifest ----------
lines = ["# Emails fixture manifest (synthetic)", "",
         "Generated by `tools/gen_10uc/emails.py` from `docs/test/10uc_universe.json`. Plain-text `.eml`; all addresses are the universe's own (`*.example`, `example.com`), Message-IDs on `example.test`; no real people or firms. Attachments are named in an `X-Attachments-Listed` header only (the PDFs come from the statements generator). `X-Unsent: 1` marks the draft.", "",
         "| File | Holds | Planted facts / figures |", "|---|---|---|"]
lines += [f"| {f} | {w} | {p} |" for f, w, p, _ in manifest]
(OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- verify ----------
def verify():
    got = {}
    for p in sorted(OUT.glob("*.eml")):
        msg = message_from_binary_file(open(p, "rb"), policy=policy.default)
        for x in re.findall(r"[\w.]+@[\w.]+", str(msg["From"]) + str(msg["To"]) + str(msg["Cc"] or "")):
            assert x in PEOPLE.values() or x in {m["contact_email"] for m in MG.values()}, (p, x)
        got[p.name] = msg.get_content()
    for k, kind, *_ in SEP:
        assert f"USD {money(ST[f'stmt-{k}-2026-09-30-{kind}']['value'])}" in got[f"01_delivery_{k}_2026-09-30_{kind}.eml"], k
    assert "+USD 180,000 (+1.80%)" in got["04_revision_notice_A_2026-09-30_amended.eml"]
    assert "USD 10,180,000" in got["04_revision_notice_A_2026-09-30_amended.eml"]
    assert "6 business days" in got["03_apology_H2_august_late.eml"]
    assert "63 business days" in got["07_followup_draft_D_missing_June.eml"]
    assert f"{float(tot_sgd):,.2f}" in got["06_internal_1_mei_to_raj_daniel.eml"]
    assert "USD 8,275,000" in got["05_delivery_C_2026-06-30_amended.eml"]
    assert "USD 7,012,500" in got["05_delivery_H1_2026-07-31_amended.eml"]
    assert len(got) == len(manifest)
    return len(got)


if __name__ == "__main__":
    print("emails written and verified:", verify())
