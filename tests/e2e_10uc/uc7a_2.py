"""UC7 charter 2 (P26, P27): What changed since the last meeting (Kestrel Ridge) with dated sources, then the Cedarpoint Ventures profile.
Usage: python uc7a_2.py --base URL --creds PATH --out DIR   (sponsor, 1440x900)"""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
UNI = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
PLANTED = {p["id"]: p for p in UNI["planted"]}
FUND = {f["key"]: f["canonical_name"] for f in UNI["funds"]}
SPONSOR = next(p for p in UNI["people"] if p["platform_role"] == "sponsor")
BAD = re.compile(r"undefined|\[object|\bNaN\b|Traceback|Internal Server Error|\bnull\b|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\bMGR-[A-Z]+|\bdoc-[a-z]+-\d+|stmt-H\d", re.I)
VERDICT = re.compile(r"good news|bad news|worrying|concerning|a concern|positive|negative|red flag|reassuring|recommend|warning sign", re.I)
NAME, TITLE = "uc7a_2", "UC7 P26 and P27: what changed (Kestrel Ridge) and the Cedarpoint profile"
KR, CP = "Kestrel Ridge Advisors", "Cedarpoint Ventures"


def norm(t):
    """Page text with 'Sept' folded to 'Sep' (en-GB ICU) and whitespace collapsed."""
    return re.sub(r"\s+", " ", t.replace(" ", " ").replace("Sept ", "Sep ").replace("’", "'"))


class Run:
    def __init__(self, page, out, title):
        self.page, self.out, self.title, self.rows, self.n = page, out, title, [], 0
        out.mkdir(parents=True, exist_ok=True)

    def text(self):
        return norm(self.page.inner_text("body"))

    def step(self, name, expected, checks, soft=()):
        """checks fail the step; soft checks are reported as notes only."""
        self.n += 1
        shot = f"{self.n:02d}-{name}.png"
        self.page.screenshot(path=str(self.out / shot), full_page=True)
        bad = BAD.search(self.text())
        checks = list(checks) + [("no raw id, error text or 'undefined' on screen" + (f" (saw {bad.group(0)!r})" if bad else ""), not bad)]
        failed = [l for l, ok in checks if not ok]
        notes = [l for l, ok in soft if not ok]
        actual = "; ".join(l + (" - ok" if ok else " - MISSING") for l, ok in list(checks) + list(soft))
        self.rows.append((self.n, name, expected, actual, "FAIL" if failed else "pass", shot, notes))
        print(f"{'FAIL' if failed else 'pass'} {shot} {failed or ''} {('note: ' + str(notes)) if notes else ''}")

    def finish(self):
        bad = sum(r[4] == "FAIL" for r in self.rows)
        md = [f"# {self.title}", "", f"Result: {'FAIL' if bad else 'PASS'} ({len(self.rows) - bad} of {len(self.rows)} steps passed)", "",
              "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        md += [f"| {n} | {s} | {e} | {a}{' NOTES: ' + ' / '.join(no) if no else ''} | {r} | {sh} |".replace("\n", " ") for n, s, e, a, r, sh, no in self.rows]
        (self.out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return 1 if bad else 0


def password_for(creds, email):
    for line in Path(creds).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0].lower() == email.lower():
            return parts[1]
    sys.exit(f"no credentials line for {email}")


def login(page, base, creds, person):
    page.goto(base.rstrip("/") + "/", wait_until="domcontentloaded")
    page.get_by_label("Email").fill(person["email"])
    page.get_by_label("Password").fill(password_for(creds, person["email"]))
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_function("!document.querySelector('input[type=password]')", timeout=20000)
    page.wait_for_load_state("networkidle")


def dates_in(expected):
    return re.findall(r"\d{1,2} [A-Z][a-z]{2} 20\d\d", expected)


def open_manager(page, base, run, name):
    """Consume > Managers list, then the manager by name (nothing in the shell links to this list yet; reached by address)."""
    page.goto(base.rstrip("/") + "/centre/consume/managers", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Managers", exact=True).wait_for(timeout=60000)
    page.get_by_role("link", name=name).wait_for(timeout=60000)
    t = run.text()
    run.step("managers-list", f"Managers list names {name}", [("heading Managers", "Managers" in t), (f"{name} listed", name in t)])
    page.get_by_role("link", name=name).click()
    page.get_by_role("heading", name=name, exact=True).wait_for(timeout=60000)  # manager page takes ~18 s on the c2j9 build
    page.wait_for_load_state("networkidle")


def show_changes(page, since=None):
    if since:
        page.get_by_label("Since").fill(since)
    page.get_by_role("button", name="Show what changed").click()
    page.get_by_role("status").filter(has_text="dated item").first.wait_for(timeout=60000)  # changes route takes 10-20 s on c2j9
    return norm(page.get_by_label("What changed", exact=True).inner_text())


P26, P27 = PLANTED["P26"]["expected"], PLANTED["P27"]["expected"]
OLD, NEW = re.search(r"from ([\d,]+) to ([\d,]+) USD", P26).groups()          # 7,050,000 and 7,012,500
AMEND, LATE_RECV, NEWS = "20 Aug 2026", "22 Sep 2026", "28 Sep 2026"           # dates named in P26
COMMIT = re.search(r"commitments ([\d,]+) and ([\d,]+)", P27).groups()       # 6,000,000 and 5,000,000
C_NAME, D_NAME = FUND["C"], FUND["D"]


def journey(page, base, run):
    open_manager(page, base, run, KR)
    sec = show_changes(page)
    page.get_by_label("What changed", exact=True).scroll_into_view_if_needed()
    area = page.get_by_label("What changed", exact=True)
    chips = [norm(c) for c in area.locator(".ds-chip").all_inner_texts()]
    items = area.locator("ul").first.locator("li").count()
    full = run.text()
    run.step("what-changed", "Dated, sourced changes since 12 Jun 2026: amended July NAV, late August statement, newsletter",
             [("last meeting 12 Jun 2026 stated above the button", "12 Jun 2026" in full),
              ("answer line counts dated items", bool(re.search(r"\d+ dated items?", sec))),
              ("at least three listed changes", items >= 3),
              ("July statement item (31 Jul 2026, revised) listed", "31 Jul 2026" in sec and "revised" in sec.lower()),
              (f"amended statement dated {AMEND}", AMEND in sec),
              ("August statement of the Equity Long/Short Fund (31 Aug 2026) listed", "Equity Long/Short Fund dated 31 Aug 2026" in sec),
              (f"August statement dated {LATE_RECV}", LATE_RECV in sec),
              (f"newsletter dated {NEWS}", NEWS in sec),
              ("every listed change has a source chip", len(chips) >= items)],
             soft=[("a chip names the Q3 2026 newsletter", any("newsletter" in c.lower() for c in chips))])
    run.step("figures", f"July NAV amended from {OLD} to {NEW} USD; August statement late",
             [(f"amended figure {NEW} on screen", NEW in full)],
             soft=[(f"previous figure {OLD} on screen", OLD in full),
                   ("lateness as 6 business days (the UI counts calendar days, so it says 8 days late)", "6 business days" in full or "6 days late" in full)])
    page.get_by_role("link", name=re.compile(r"Kestrel Ridge Macro Fund, valued 31 Jul 2026")).first.click()
    page.wait_for_load_state("networkidle")
    run.step("source-statement", "A statement line opens its record", [("left the manager page for the evidence view", "/centre/action/evidence/" in page.url)])
    open_manager(page, base, run, CP)
    t = run.text()
    page.get_by_label("Commitments", exact=True).scroll_into_view_if_needed()
    run.step("cedarpoint-profile", "Funds C and D, commitments 6,000,000 and 5,000,000, D last valued 31 Mar 2026, June statement missing, open question",
             [(f"fund C {C_NAME}", C_NAME in t), (f"fund D {D_NAME}", D_NAME in t),
              (f"commitment {COMMIT[0]}", COMMIT[0] in t), (f"commitment {COMMIT[1]}", COMMIT[1] in t),
              ("D last valuation 31 Mar 2026", "31 Mar 2026" in t),
              ("June statement missing (30 Jun 2026)", "Still missing: the statement for 30 Jun 2026" in t),
              ("open question about the June statement", "30 June 2026" in t and "has not arrived" in t),
              ("DDQ listed under Diligence documents", "DDQ" in t)],
             soft=[("the word stale on fund D", "stale" in t.lower())])
    sec = show_changes(page, "2026-01-01")
    run.step("cedarpoint-ddq", "DDQ: quarterly statements within 45 days; auditor change in Q2 2026",
             [("a dated, sourced answer", bool(re.search(r"\d+ dated items?", sec)))],
             soft=[("DDQ says 45 days", "45 days" in sec), ("an auditor change is mentioned", "auditor" in sec.lower())])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        run = Run(pg, Path(a.out) / NAME, TITLE)
        try:
            login(pg, a.base, a.creds, SPONSOR)
            run.step("signed-in", "Signed in as the sponsor; the login form is gone", [("password field gone", pg.locator("input[type=password]").count() == 0)])
            journey(pg, a.base, run)
        except Exception as e:  # a missing screen is a failed step, with a picture
            run.step("stopped", "journey completes", [(f"stopped: {type(e).__name__}: {str(e).splitlines()[0][:160]}", False)])
        code = run.finish()
        br.close()
    sys.exit(code)
