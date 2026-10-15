"""10-use-case campaign, journey uc1a_2: the CIO reads issued vs known now and the NAV bridge.

Standalone Playwright script (sync API, Chromium, 1440x900). Synthetic data only.
    python uc1a_2.py --base http://127.0.0.1:8700 --creds <seed_credentials.txt> --out <dir>
Writes <out>/uc1a_2/NN-<step>.png and <out>/uc1a_2/result.md; exits 1 when any step fails.
Figures come from docs/test/10uc_universe.json; nothing is copied here. Passwords are read from the creds file and never printed or saved.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
CIO_EMAIL = next(p["email"] for p in U["people"] if p["name"] == "Daniel Foo")
FUND = {f["key"]: f for f in U["funds"]}
PF = {p["portfolio_code"]: p for p in U["portfolios"]}
SEC = {s["key"]: s for s in U["securities"]}
ISSUED = U["report_issued"]
RATE_ISSUED = Decimal(ISSUED["fx_rate_used"])
RATE_8OCT = Decimal(U["fx_fixings"]["pinned"]["2026-10-08"])
KNOWN = {v["fund"]: v for v in U["valuations_monthly"] if v["month_end"] == "2026-09-30"}  # value known now per fund at 30 Sep
BRIDGE = {b["portfolio"]: b for b in U["nav_bridge_30_sep"]}

BAD = [  # things that must never reach a business user's screen
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "a raw id"),
    (re.compile(r"\bstmt-[A-Za-z0-9-]+"), "a statement id"),
    (re.compile(r"\b(undefined|\bNaN\b|null)\b"), "undefined, NaN or null"),
    (re.compile(r"\[object|Traceback|Internal Server Error|TypeError|\bHTTP \d{3}\b"), "error text"),
    (re.compile(r"did not go through|could not be loaded|could not sign you in"), "an error message"),
]


def usd(v, ccy="USD") -> str:
    """Money the way the screen writes it: 'USD 10,180,000', 'SGD 1,234.5' (en-US, up to two decimals)."""
    s = f"{Decimal(str(v)).quantize(Decimal('0.01'), ROUND_HALF_UP):,.2f}"
    return f"{ccy} {s.rstrip('0').rstrip('.') if '.' in s else s}"


def conv(v, rate) -> Decimal:
    return Decimal(str(v)) * Decimal(str(rate))


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace(" ", " ")).strip()


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


class Journey:
    def __init__(self, page: Page, outdir: Path, name: str):
        self.page, self.name, self.rows, self.n = page, name, [], 0
        self.dir = outdir / name
        self.dir.mkdir(parents=True, exist_ok=True)

    def step(self, slug: str, expected: str, fn, clean: bool = True) -> bool:
        """Run one step: screenshot it whatever happens, add the clean-screen check, record pass or fail."""
        self.n += 1
        actual, ok = "", True
        try:
            actual = fn() or "As expected."
            if clean:
                self.clean()
        except Exception as e:  # noqa: BLE001 - a failed step is a result, the journey carries on
            ok = False
            first = str(e).splitlines()[0] if str(e) else ""
            actual = str(e) if isinstance(e, AssertionError) else f"{type(e).__name__}: {first}"
            if not isinstance(e, AssertionError):
                print(traceback.format_exc(limit=2), file=sys.stderr)
        shot = f"{self.n:02d}-{slug}.png"
        try:
            self.page.screenshot(path=str(self.dir / shot), full_page=True)
        except Exception:  # noqa: BLE001
            shot += " (screenshot failed)"
        self.rows.append((self.n, slug, expected, actual, ok, shot))
        print(f"{'PASS' if ok else 'FAIL'} {self.n:02d} {slug}: {actual[:200]}")
        return ok

    def clean(self):
        text = self.page.locator("body").inner_text()
        found = [what for rx, what in BAD if rx.search(text)]
        # a business warning (ds-warn, e.g. the Entity B shortfall, a6.7) is content; only an error alert fails the clean-screen check
        alerts = [norm(a.inner_text()) for a in self.page.get_by_role("alert").all() if a.is_visible() and "ds-warn" not in (a.get_attribute("class") or "")]
        need(not found and not alerts, f"The screen shows {', '.join(found) or 'an alert'}{': ' + ' / '.join(alerts) if alerts else ''}.")

    def write(self, title: str) -> int:
        failed = [r for r in self.rows if not r[4]]
        md = [f"# {self.name}: {title}", "", f"Result: {'FAIL' if failed else 'PASS'} ({len(self.rows) - len(failed)} of {len(self.rows)} steps passed)", "",
              "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        for n, slug, exp, act, ok, shot in self.rows:
            md.append("| " + " | ".join([str(n), slug, *(s.replace("|", "/").replace("\n", " ") for s in (exp, act)), "pass" if ok else "FAIL", shot]) + " |")
        (self.dir / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return 1 if failed else 0


def password_for(creds: Path, email: str) -> str:
    for line in creds.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not line.startswith("#") and parts[0].lower() == email.lower():
            return parts[1]
    raise SystemExit(f"No sign-in line for {email} in the creds file.")


def loaded(page: Page, timeout=30000):
    page.wait_for_function("!document.body.innerText.includes('Loading the')", timeout=timeout)


def login(page: Page, base: str, creds: Path) -> str:
    pw = password_for(creds, CIO_EMAIL)
    page.goto(base, wait_until="domcontentloaded")
    page.get_by_label("Email").fill(CIO_EMAIL)
    page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")  # plain clicks have timed out on this box
    page.get_by_role("navigation", name="Centres").wait_for(timeout=30000)
    need(page.get_by_label("Password").count() == 0, "Still on the sign-in page after submitting.")
    return f"Signed in as the CIO (Daniel Foo); landed on {page.url.replace(base, '') or '/'}."


def open_office(page: Page, base: str) -> str:
    """Consume centre, then the Office view the way a CIO would: by a link on the Consume page. Falls back to the address so later steps still run."""
    page.get_by_role("navigation", name="Centres").get_by_role("link", name=re.compile("consume", re.I)).first.click()
    page.wait_for_url(re.compile(r"/centre/consume"), timeout=15000)
    page.wait_for_timeout(1500)
    link = page.get_by_role("link", name=re.compile(r"office view", re.I))
    if link.count() == 0:
        page.goto(f"{base}/centre/consume/office", wait_until="domcontentloaded")
        page.get_by_role("heading", name="Office view").wait_for(timeout=20000)
        raise AssertionError("The Consume page has no link to the Office view (ui/src/v1/p3/ConsumeEntry.tsx); reached it by address instead.")
    link.first.click()
    page.get_by_role("heading", name="Office view").wait_for(timeout=20000)
    return "The Consume page links to the Office view; it opened."


def region(page: Page, name: str):
    return page.get_by_role("region", name=name, exact=True)


def row_of(scope, page: Page, first_cell: str):
    return scope.get_by_role("row").filter(has=page.get_by_role("cell", name=first_cell, exact=True)).first


def cells(row) -> list[str]:
    return [norm(c.inner_text()) for c in row.get_by_role("cell").all()]


def switch_currency(page: Page, ccy: str):
    page.get_by_role("group", name="Currency").get_by_role("button", name=ccy, exact=True).click()
    page.wait_for_function("(c) => [...document.querySelectorAll('[aria-label=Currency] button')].some(b => b.textContent.trim() === c && b.getAttribute('aria-pressed') === 'true')", arg=ccy)
    page.wait_for_timeout(500)
    loaded(page)


def main(name: str, title: str, journey):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.set_default_timeout(15000)
        j = Journey(page, a.out, name)
        try:
            journey(j, page, base, a.creds)
        finally:
            code = j.write(title)
            browser.close()
    sys.exit(code)


# ---- journey 2: the CIO reads issued vs known now and the NAV bridge, then asks where the Fund A revision is from ---------------
BRIDGE_TITLE = "Investment total against administrator NAV"
PARTS = [("Revisions", "revisions"), ("Timing (valuation date)", "timing"), ("Exchange rates", "fx"), ("Unexplained", "unexplained")]
STATUS_KNOWN = {"Evergreen Growth I": "Revised", "Evergreen Income II": "Official", "Liquid book": "Official"}  # P02 / P07 for the lines


def issued_vs_known(page):
    sec, bad = region(page, "Issued versus known now"), []
    known_total = Decimal(ISSUED["lines"][-1]["value"]) + (Decimal(KNOWN["A"]["known_now_value"]) - Decimal(ISSUED["lines"][0]["value"]))
    for ln in ISSUED["lines"]:
        got = cells(row_of(sec, page, ln["label"]))
        known = known_total if ln["label"] == "Total" else Decimal(KNOWN["A"]["known_now_value"]) if ln is ISSUED["lines"][0] else Decimal(ln["value"])
        if got[1] != usd(ln["value"]):
            bad.append(f"{ln['label']} as issued '{got[1]}', expected {usd(ln['value'])}")
        if got[2] != usd(known):
            bad.append(f"{ln['label']} known now '{got[2]}', expected {usd(known)}")
        want = STATUS_KNOWN.get(ln["label"])
        if want and want not in got[3]:
            bad.append(f"{ln['label']} status '{got[3]}', expected {want}")
    need(not bad, "; ".join(bad))
    return f"Fund A as issued 10,000,000 vs known now 10,180,000 (Revised); B and Liquid book unchanged; total 57,600,000 vs {usd(known_total)}."


def issued_where(page):
    sec = region(page, "Issued versus known now")
    sec.get_by_role("button", name="Where is this from?").click()
    box = sec.get_by_text(re.compile(r"compared with what the company knows now")).first
    box.wait_for()
    txt = norm(box.inner_text())
    need("3 Oct 2026" in txt or "03 Oct 2026" in txt, f"Where-from text '{txt}' does not name the issue date 3 Oct 2026")
    return f"Says: {txt}"


def card(page, code):
    name = PF[code]["portfolio_name"]
    return region(page, BRIDGE_TITLE).locator("div").filter(has=page.get_by_role("heading", name=re.compile(re.escape(name)))).first


def bridge_card(page, code):
    b, c, bad = BRIDGE[code], card(page, code), []
    need(c.count() and c.is_visible(), f"{code}: no bridge card for '{PF[code]['portfolio_name']}'")
    head = norm(c.locator("p").first.inner_text())
    for label, v in (("Investment view", b["investment_view"]), ("Administrator NAV", b["administrator_nav"])):
        if f"{label}" not in head or usd(v) not in head:
            bad.append(f"header lacks {label} {usd(v)}: '{head}'")
    diff = Decimal(b["investment_view"]) - Decimal(b["administrator_nav"])
    if f"Difference {usd(diff)}" not in head:
        bad.append(f"header lacks 'Difference {usd(diff)}': '{head}'")
    for label, key in PARTS:
        row = c.get_by_role("row").filter(has=page.get_by_role("cell", name=re.compile("^" + re.escape(label)))).first
        if row.count() == 0:
            bad.append(f"no '{label}' row")
            continue
        got = cells(row)[1]
        if got != usd(b[key]):
            bad.append(f"{label} '{got}', expected {usd(b[key])}")
    need(not bad, f"{code}: " + "; ".join(bad))
    return f"{code}: view {usd(b['investment_view'])} vs NAV {usd(b['administrator_nav'])}, difference {usd(diff)}"


def bridge_all(page):
    loaded(page)
    return "; ".join(bridge_card(page, c) for c in ("EG-GROWTH", "EG-LIQUID", "EG-B-OPS", "EG-FUNDS"))


def part_where(page, code, label, funds, phrase, date_text=None):
    c = card(page, code)
    row = c.get_by_role("row").filter(has=page.get_by_role("cell", name=re.compile("^" + re.escape(label)))).first
    row.get_by_role("button", name="Where is this from?").click()
    items = c.locator("li")
    items.first.wait_for()
    texts = [norm(t.inner_text()) for t in items.all()]
    bad = []
    for f in funds:
        hit = [t for t in texts if FUND[f]["canonical_name"] in t and phrase in t]
        if not hit:
            bad.append(f"no line naming {FUND[f]['canonical_name']} ({phrase}); got {texts}")
        elif date_text and date_text not in hit[0]:
            bad.append(f"{FUND[f]['canonical_name']} line lacks '{date_text}': '{hit[0]}'")
    need(not bad, "; ".join(bad))
    return " | ".join(texts)


# the bridge row a part sits in and the words its trail uses; the row comes from the universe's part kind, not from this script
# (a1.13: E, H1 and H2 were 'timing' in the universe and 'Revisions' on screen; the universe now says revision)
KIND_ROW = {"revision": ("Revisions", "revised since the NAV was struck"), "timing": ("Timing (valuation date)", "dated after the NAV date")}


def bridge_where(page, code):
    parts = BRIDGE[code]["parts"]
    kinds = {p["kind"] for p in parts}
    need(len(kinds) == 1, f"{code}: parts of more than one kind in the universe: {kinds}")
    label, phrase = KIND_ROW[kinds.pop()]
    return part_where(page, code, label, [p["fund"] for p in parts], phrase)


def brief(page):
    region(page, "Issued versus known now").get_by_role("link", name="Open the CIO Brief").click()
    page.wait_for_url(re.compile(r"/centre/consume/brief/"))
    page.get_by_role("heading", level=1).wait_for()
    # the brief shows "Loading the brief." until its data arrives; wait for that to clear, not a fixed pause
    page.get_by_text("Loading the brief.").wait_for(state="detached", timeout=20000)
    txt = norm(page.locator("body").inner_text())
    bad = [s for s in (FUND["A"]["canonical_name"], "10,000,000", "10,180,000", "Revised") if s not in txt]
    need(not bad, f"The CIO Brief does not show {bad}")
    need(page.get_by_role("button", name="Why did this move?").count() >= 1, "No 'Why did this move?' on the changed line")
    return "CIO Brief shows Fund A 10,000,000 to 10,180,000, Revised, with 'Why did this move?'."


def journey(j: Journey, page: Page, base: str, creds: Path):
    j.step("sign-in", "The CIO signs in with the sign-in form and reaches the centre bar.", lambda: login(page, base, creds))
    j.step("consume-to-office", "Consume page offers the Office view; clicking it opens the Office view.", lambda: open_office(page, base))
    j.step("issued-vs-known-now", "P01/P02: Fund A 10,000,000 as issued vs 10,180,000 known now (Revised); total 57,600,000 vs 57,780,000.", lambda: (loaded(page), issued_vs_known(page))[1])
    j.step("issued-where-from", "Where is this from? under the issued table names the report and its issue date.", lambda: issued_where(page))
    j.step("nav-bridge", "P03-P05: Growth 16,580,000 vs 16,400,000 (revisions 180,000); Entity B 22,875,000 vs 22,525,000 (timing 350,000); Funds 22,750,000 vs 22,550,000 (timing 200,000); Liquid equal.", lambda: bridge_all(page))
    j.step("fund-a-revision-where-from", "P03: Where is this from? on Revisions (Growth) names Evergreen Growth I as revised since the NAV was struck, valuation of 30 Sep 2026.",
           lambda: part_where(page, "EG-GROWTH", "Revisions", ["A"], "revised since the NAV was struck", "30 Sep 2026"))
    j.step("fund-e-where-from", "P04: Where is this from? on the Entity B bridge row (the universe's part kind) names Saltmarsh Infrastructure Fund II.",
           lambda: bridge_where(page, "EG-B-OPS"))
    j.step("funds-where-from", "P05: Where is this from? on the Funds bridge row (the universe's part kind) names both Kestrel Ridge funds (H1, H2).",
           lambda: bridge_where(page, "EG-FUNDS"))
    j.step("cio-brief", "Open the CIO Brief from the issued table: Fund A moved 10,000,000 to 10,180,000, Revised.", lambda: brief(page))


if __name__ == "__main__":
    main("uc1a_2", "CIO reads issued vs known now and the NAV bridge, asks where the Fund A revision is from", journey)
