"""10-use-case campaign, journey uc1a_1: the CIO opens Consume > Office view.

Standalone Playwright script (sync API, Chromium, 1440x900). Synthetic data only.
    python uc1a_1.py --base http://127.0.0.1:8700 --creds <seed_credentials.txt> --out <dir>
Writes <out>/uc1a_1/NN-<step>.png and <out>/uc1a_1/result.md; exits 1 when any step fails.
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
    # match the first cell by its text: a holding's name is a button whose aria-label ("<name>: Where is this from?", OfficePage.tsx)
    # becomes the cell's accessible name, so a name match finds no row
    text = re.compile(rf"^\s*{re.escape(first_cell).replace('/', '.')}\s*$")  # a '/' breaks Playwright's regex selector
    return scope.get_by_role("row").filter(has=page.locator("td:first-child", has_text=text)).first


def cells(row) -> list[str]:
    return [norm(c.inner_text()) for c in row.get_by_role("cell").all()]


def holding(row) -> list[str]:
    """A Holdings row as [holding, value, status, source], whatever other columns the table has (Asset class came in after the script;
    the columns are found by their headers)."""
    heads = [norm(h) for h in row.locator("xpath=ancestor::table[1]").get_by_role("columnheader").all_inner_texts()]
    got = dict(zip(heads, cells(row)))
    return [got.get("Holding", ""), got.get("Value", ""), got.get("Status", ""), got.get("Source", "")]


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


# ---- journey 1: the CIO opens Consume > Office view (holdings, status words, USD/SGD) -----------------------------------------
# P07 status words at 30 Sep, as the screen writes them. PRC29 is a question, not a status.
WORDS = {"A": "Revised", "B": "Official", "C": "Stale", "D": "Stale", "E": "Unverified", "H1": "Estimated", "H2": "Estimated", "L1": "Official", "L2": "Official"}
SOURCE_DATE = {"C": "30 Jun 2026", "D": "31 Mar 2026"}  # the old valuation dates behind the two Stale words (P07)
PF_FUNDS = {"EG-GROWTH": ["A", "B"], "EG-B-OPS": ["C", "D", "E"], "EG-FUNDS": ["H1", "H2", "L1", "L2"]}


def fund_total(code: str) -> Decimal:
    return sum((Decimal(KNOWN[k]["known_now_value"]) for k in PF_FUNDS[code]), Decimal(0))


def portfolio_totals() -> dict[str, Decimal]:
    t = {c: fund_total(c) for c in PF_FUNDS}
    t["EG-LIQUID"] = Decimal(BRIDGE["EG-LIQUID"]["investment_view"])
    return t


def holdings_usd(page):
    sec, bad = region(page, "Holdings"), []
    for key, word in WORDS.items():
        name, want = FUND[key]["canonical_name"], usd(KNOWN[key]["known_now_value"])
        row = row_of(sec, page, name)
        if row.count() == 0 or not row.is_visible():
            bad.append(f"{key} {name}: no row")
            continue
        got = holding(row)
        if want not in got[1]:
            bad.append(f"{key} {name}: value '{got[1]}', expected {want}")
        if row.get_by_text(word, exact=True).count() != 1:
            bad.append(f"{key} {name}: status '{got[2]}', expected {word}")
        if key in SOURCE_DATE and SOURCE_DATE[key] not in got[3]:
            bad.append(f"{key} {name}: source '{got[3]}', expected the valuation date {SOURCE_DATE[key]}")
    prc = SEC["PRC29"]
    prow = row_of(sec, page, prc["canonical_name"])
    if prow.count() == 0:
        bad.append("PRC29: no row")
    else:
        want = usd(Decimal(prc["quantity_30_sep"]) * Decimal(prc["prices_month_end"]["2026-09-30"]))
        got = holding(prow)
        if want not in got[1]:
            bad.append(f"PRC29: value '{got[1]}', expected {want}")
        if "needs a class" not in " ".join(got[2:]).lower():
            bad.append(f"PRC29: status '{got[2]}', expected 'Needs a class'")
    need(not bad, "; ".join(bad))
    return "Fund rows show the universe values and status words: A Revised, B Official, C and D Stale, E Unverified, H1/H2 Estimated, L1/L2 Official; PRC29 present."


def totals_usd(page):
    sec, bad = region(page, "Holdings"), []
    for code, tot in portfolio_totals().items():
        h = sec.get_by_role("heading", name=re.compile(re.escape(PF[code]["portfolio_name"])))
        if h.count() == 0:
            bad.append(f"{code}: no heading '{PF[code]['portfolio_name']}'")
        elif usd(tot) not in norm(h.first.inner_text()):
            bad.append(f"{code}: heading '{norm(h.first.inner_text())}', expected {usd(tot)}")
    grand = sum(portfolio_totals().values(), Decimal(0))
    line = norm(sec.locator("p, div", has=page.locator("strong", has_text="All holdings:")).last.inner_text())  # the label is its own <strong>
    if usd(grand) not in line:
        bad.append(f"All holdings: '{line[:80]}', expected {usd(grand)}")
    need(not bad, "; ".join(bad))
    return f"Portfolio totals and the all-holdings line match the universe ({usd(grand)})."


def where_fund_a(page):
    sec = region(page, "Holdings")
    row = row_of(sec, page, FUND["A"]["canonical_name"])
    row.get_by_role("button", name="Where is this from?").click()
    box = sec.locator("td[colspan] p").first  # the opened box sits in its own full-width row under the holding
    box.wait_for()
    txt = norm(box.inner_text())
    need("30 Sep 2026" in txt, f"Where-from text for Fund A: '{txt}', expected the valuation date 30 Sep 2026")
    return f"Fund A says: {txt}"


def issued_as_issued(page):
    sec, bad = region(page, "Issued versus known now"), []
    for ln in ISSUED["lines"]:
        row = row_of(sec, page, ln["label"])
        if row.count() == 0:
            bad.append(f"no row '{ln['label']}'")
            continue
        got = cells(row)
        if got[1] != usd(ln["value"]):
            bad.append(f"{ln['label']} as issued '{got[1]}', expected {usd(ln['value'])}")
    txt = norm(sec.inner_text())
    if "issued 3 Oct 2026" not in txt:
        bad.append("no 'issued 3 Oct 2026'")
    need(not bad, "; ".join(bad))
    return "As-issued column: A 10,000,000, B 6,400,000, Liquid book 41,200,000, Total 57,600,000 USD; issued 3 Oct 2026."


def to_sgd(page):
    switch_currency(page, "SGD")
    hold, bad, used = region(page, "Holdings"), [], set()
    for key in ("A", "B", "E"):
        row = row_of(hold, page, FUND[key]["canonical_name"])
        got = holding(row)
        usd_v = KNOWN[key]["known_now_value"]
        hit = [r for r in (RATE_ISSUED, RATE_8OCT) if usd(conv(usd_v, r), "SGD") in got[1]]
        if not hit:
            bad.append(f"{key}: SGD value '{got[1]}', expected {usd(conv(usd_v, RATE_ISSUED), 'SGD')} (1.3412) or {usd(conv(usd_v, RATE_8OCT), 'SGD')} (1.3388)")
        used.update(hit)
        if usd(usd_v) not in got[1]:
            bad.append(f"{key}: the original {usd(usd_v)} is not shown beside the SGD figure")
    iss = region(page, "Issued versus known now")
    total = ISSUED["lines"][-1]
    got = cells(row_of(iss, page, total["label"]))
    if got[1] != usd(ISSUED["total_sgd"], "SGD"):
        bad.append(f"Issued total in SGD '{got[1]}', expected {usd(ISSUED['total_sgd'], 'SGD')} (57,600,000 at 1.3412)")
    for ln in ISSUED["lines"][:-1]:
        g = cells(row_of(iss, page, ln["label"]))[1]
        if g != usd(conv(ln["value"], RATE_ISSUED), "SGD"):
            bad.append(f"{ln['label']} issued in SGD '{g}', expected {usd(conv(ln['value'], RATE_ISSUED), 'SGD')}")
    need(not bad, "; ".join(bad))
    return f"SGD switch: holdings convert at {'/'.join(str(r) for r in sorted(used))} with the USD original beside them; issued total {usd(ISSUED['total_sgd'], 'SGD')}."


def back_to_usd(page):
    switch_currency(page, "USD")
    sec = region(page, "Holdings")
    need("SGD" not in sec.inner_text(), "SGD figures still show in Holdings after switching back to USD.")
    got = holding(row_of(sec, page, FUND["A"]["canonical_name"]))[1]
    need(usd(KNOWN["A"]["known_now_value"]) in got, f"Fund A shows '{got}' after switching back")
    return "USD restored; no SGD left in Holdings."


def journey(j: Journey, page: Page, base: str, creds: Path):
    j.step("sign-in", "The CIO signs in with the sign-in form and reaches the centre bar.", lambda: login(page, base, creds))
    j.step("consume-to-office", "Consume page offers the Office view; clicking it opens the Office view.", lambda: open_office(page, base))

    def frame():
        need(page.get_by_role("heading", name="Office view").is_visible(), "No Office view heading")
        for s in ("Holdings", "Issued versus known now", "Investment total against administrator NAV", "Liquidity"):
            need(region(page, s).is_visible(), f"Section '{s}' is missing")
        grp = page.get_by_role("group", name="Currency")
        usd_on = grp.get_by_role("button", name="USD", exact=True).get_attribute("aria-pressed")
        need(usd_on == "true" and grp.get_by_role("button", name="SGD", exact=True).is_visible(), "USD should be selected with SGD beside it")
        loaded(page)
        return "Office view with Holdings, Issued versus known now, NAV bridge and Liquidity; USD selected, SGD offered."
    j.step("office-view", "Heading Office view, four sections, USD selected, SGD available.", frame)
    j.step("holdings-status-words", "P07: each fund shows its universe value and status word (Revised, Official, Stale, Unverified, Estimated); PRC29 'Needs a class'.", lambda: holdings_usd(page))
    j.step("holdings-totals", "Portfolio totals and All holdings equal the universe sums.", lambda: totals_usd(page))
    j.step("holdings-where-from", "P02/P07: Where is this from? on Fund A names the 30 Sep 2026 valuation.", lambda: where_fund_a(page))
    j.step("issued-as-issued", "P01: as issued 10,000,000 / 6,400,000 / 41,200,000 / 57,600,000 USD, issued 3 Oct 2026.", lambda: issued_as_issued(page))
    j.step("switch-to-sgd", "P16/P01: SGD at 1.3412 (issued total 77,253,120.00 SGD); USD original shown beside holdings.", lambda: to_sgd(page))
    j.step("switch-back-to-usd", "USD restores the dollar figures.", lambda: back_to_usd(page))


if __name__ == "__main__":
    main("uc1a_1", "CIO opens the Office view: holdings, status words, USD/SGD", journey)
