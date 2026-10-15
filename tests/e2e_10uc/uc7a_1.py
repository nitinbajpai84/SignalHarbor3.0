"""UC7 charter 1 (P25): Consume > Managers > Kestrel Ridge Advisors, the newsletter team change with its source chip and no verdict.
Usage: python uc7a_1.py --base URL --creds PATH --out DIR   (sponsor, 1440x900)"""
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
NAME, TITLE = "uc7a_1", "UC7 P25: Kestrel Ridge newsletter team change"
KR = "Kestrel Ridge Advisors"


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
    page.get_by_role("heading", name="Managers", exact=True).wait_for(timeout=15000)
    page.get_by_role("link", name=name).wait_for(timeout=15000)
    t = run.text()
    run.step("managers-list", f"Managers list names {name}", [("heading Managers", "Managers" in t), (f"{name} listed", name in t)])
    page.get_by_role("link", name=name).click()
    page.get_by_role("heading", name=name, exact=True).wait_for(timeout=15000)
    page.wait_for_load_state("networkidle")


def show_changes(page, since=None):
    if since:
        page.get_by_label("Since").fill(since)
    page.get_by_role("button", name="Show what changed").click()
    page.get_by_role("status").filter(has_text="dated item").first.wait_for(timeout=20000)
    return norm(page.get_by_label("What changed", exact=True).inner_text())


P = PLANTED["P25"]["expected"]
D1, D2 = dates_in(P)[:2]                                            # 28 Sep 2026 (newsletter), 30 Sep 2026 (left)
LEFT = re.search(r"(\w+ \w+) left on", P).group(1)                  # Thomas Lindqvist
SOLE = re.search(r"(\w+ \w+) sole portfolio manager", P).group(1)   # Priya Nair


def journey(page, base, run):
    open_manager(page, base, run, KR)
    t = run.text()
    run.step("manager-page", "Kestrel Ridge page with funds, statements, notes, documents and the What changed section",
             [(f"title {KR}", KR in t), ("Kestrel Ridge Macro Fund listed", "Kestrel Ridge Macro Fund" in t),
              ("section What changed since the last meeting?", "What changed since the last meeting?" in t),
              ("one Show what changed button", page.get_by_role("button", name="Show what changed").count() == 1)],
             soft=[("newsletter named under Diligence documents", "newsletter" in t.lower())])
    sec = show_changes(page)                                        # no date: since the last meeting on record
    chip_text = norm(" | ".join(page.get_by_label("What changed", exact=True).locator(".ds-chip").all_inner_texts()))
    page.get_by_label("What changed", exact=True).scroll_into_view_if_needed()
    run.step("what-changed", "Team change listed with its date and a source chip",
             [(f"{LEFT} named", LEFT in sec), (f"{SOLE} named", SOLE in sec), (f"newsletter date {D1} shown", D1 in sec),
              ("a source chip names the newsletter", "newsletter" in chip_text.lower()),
              ("chip cites lines of the file", bool(re.search(r"lines \d+ to \d+", chip_text))),
              ("passages heading 'From the documents'", "From the documents" in sec)],
             soft=[(f"{D2} (left) in the quoted passage", D2 in sec or "30 September 2026" in sec), ("1 Oct in the passage", "1 Oct" in sec)])
    fact = re.sub(r"[^.]*does not say[^.]*\.", "", sec)             # the standing disclaimer may talk about 'well or badly'
    v = VERDICT.search(fact)
    run.step("no-verdict", "The product never says whether the change is good or bad",
             [(f"no verdict wording (saw {v.group(0)!r})" if v else "no verdict wording", not v)],
             soft=[("standing note that nothing here says whether a manager is doing well or badly", "does not say whether" in sec)])


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
