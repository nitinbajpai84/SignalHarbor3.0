"""UC8 browser journey UC8 FX forward confirmation mismatch and matched trades (P30, P31).

    python tests/e2e_10uc/uc8a_2.py --base URL --creds PATH --out DIR

Signs in as the analyst (Mei Chen), walks Action > Reconciliations and Cases, screenshots every step to DIR/uc8a_2/NN-<step>.png and
writes DIR/uc8a_2/result.md. Figures come from docs/test/10uc_universe.json. Passwords are never printed or saved. Exit 1 on a failure.
"""
import argparse
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
TRADES = {t["id"]: t for t in U["trades_oct"]}
FX = {f["id"]: f for f in U["fx_forwards"]}
PORT = {p["portfolio_code"]: p["portfolio_name"] for p in U["portfolios"]}
SEC = {s["key"]: s["canonical_name"] for s in U["securities"]}
RUN_DAY = "2026-10-09"
RUN_DAY_TEXT = "9 Oct 2026"
BREAKS = r"\d+ (?:breaks open|differences? to look at)"  # the card's words (ReconPage.tsx): "N differences to look at"
BAD = [r"\bundefined\b", r"\[object", r"Traceback", r"\bNaN\b", r"\bnull\b", r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
       r"did not go through", r"could not be loaded", r"Internal Server Error"]
money = lambda v: f"{D(v):,.2f}"  # noqa: E731


def analyst_login(path):
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if len(p) >= 4 and p[0].startswith("mei.chen.") and "@" in p[0]:
            return p[0], p[1]
    sys.exit("no credentials for Mei Chen in the creds file")


class Journey:
    def __init__(self, page, out):
        self.page, self.out, self.rows, self.n = page, out, [], 0

    def step(self, name, expected, fn):
        """Run fn (returns the actual text, raises on a failure), screenshot, record."""
        self.n += 1
        try:
            actual, ok = fn() or "as expected", True
        except Exception as e:  # noqa: BLE001 - any failure is a failed step, the walk goes on
            actual, ok = f"{type(e).__name__}: {str(e)[:300]}", False
        shot = f"{self.n:02d}-{name}.png"
        try:
            self.page.screenshot(path=str(self.out / shot), full_page=True)
        except Exception:  # noqa: BLE001
            shot += " (no screenshot)"
        if ok:  # nothing raw on screen
            text = self.page.inner_text("body")
            hit = next((b for b in BAD if re.search(b, text)), None)
            if hit:
                actual, ok = f"raw or error text on screen, matched {hit}", False
        self.rows.append((self.n, name, expected, actual.replace("\n", " "), ok, shot))
        print(f"{'PASS' if ok else 'FAIL'} {self.n:02d} {name}")

    def finish(self, title):
        lines = [f"# {title}", "", "| # | step | expected | actual | result | screenshot |", "|---|---|---|---|---|---|"]
        for n, name, e, a, ok, s in self.rows:
            lines.append(f"| {n} | {name} | {e.replace('|', '/')} | {a.replace('|', '/')} | {'pass' if ok else 'FAIL'} | {s} |")
        (self.out / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        sys.exit(0 if all(r[4] for r in self.rows) else 1)


def sign_in(j, base, email, password):
    page = j.page

    def landing():
        page.goto(base.rstrip("/") + "/", wait_until="domcontentloaded")
        page.get_by_label("Email").wait_for(timeout=20000)
        page.get_by_role("button", name="Sign in").wait_for(timeout=5000)
        return "the sign-in page shows Email, Password and Sign in"

    def go():
        page.get_by_label("Email").fill(email)
        page.get_by_label("Password").fill(password)
        page.evaluate("document.querySelector('form').requestSubmit()")
        page.get_by_label("Email").wait_for(state="detached", timeout=20000)
        return "signed in as the analyst"
    j.step("sign-in-page", "sign-in page with Email, Password and Sign in", landing)
    j.step("signed-in", "the form is accepted and the sign-in page goes away", go)


def open_recon(j, base):
    page = j.page

    def action():
        page.goto(base.rstrip("/") + "/centre/action", wait_until="domcontentloaded")
        page.get_by_role("heading", name="Action", exact=True).first.wait_for(timeout=20000)
        tabs = page.get_by_role("navigation", name="Action tabs")
        for t in ("Today", "Cases", "Reconciliations", "Managers"):
            tabs.get_by_role("link", name=t, exact=True).wait_for(timeout=5000)
        return "Action centre open with its four tabs"

    def tab():
        page.get_by_role("navigation", name="Action tabs").get_by_role("link", name="Reconciliations").click()
        page.get_by_role("heading", name="Trades against the administrator").wait_for(timeout=15000)
        return "Reconciliations tab lists the check Trades against the administrator"
    j.step("action-centre", "Action centre with the tabs Today, Cases, Reconciliations, Managers", action)
    j.step("reconciliations", "Reconciliations tab with the check Trades against the administrator", tab)


def run_trades(j):
    page = j.page
    card = page.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Trades against the administrator"))

    def run():
        page.get_by_label("Check as at").fill(RUN_DAY)
        card.get_by_role("button", name="Run now").click()
        card.get_by_text(re.compile(BREAKS)).wait_for(timeout=60000)
        txt = card.inner_text()
        assert "as at " + RUN_DAY_TEXT in txt, "last run is not as at " + RUN_DAY_TEXT  # dates read D MMM YYYY (house format)
        assert "must match by trade id" in txt, "rule words missing"
        assert "5,000 USD" in txt, "tolerance 5,000 USD not stated"
        return "run done: " + re.search(BREAKS, txt).group(0) + "; the signed tolerance is stated in words"
    j.step("run-trades-check", f"Run now as at {RUN_DAY}: breaks open, last run line, tolerance 5,000 USD in words", run)


def open_cases(j):
    page = j.page

    def go():
        page.get_by_role("navigation", name="Action tabs").get_by_role("link", name="Cases").click()
        page.get_by_role("table").wait_for(timeout=20000)
        return f"{page.get_by_role('row').count() - 1} cases listed"
    j.step("cases", "Cases tab with a table of open cases", go)


def row_for(j, ident):
    return j.page.get_by_role("row").filter(has_text=ident)


def main_for(n, title, body):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / f"uc8a_{n}"
    out.mkdir(parents=True, exist_ok=True)
    email, pw = analyst_login(a.creds)
    with sync_playwright() as pw_:
        br = pw_.chromium.launch()
        page = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.set_default_timeout(20000)
        j = Journey(page, out)
        try:
            sign_in(j, a.base, email, pw)
            open_recon(j, a.base)
            run_trades(j)
            open_cases(j)
            body(j)
        finally:
            br.close()
    j.finish(title)


def body(j):
    page = j.page
    f2, f1 = FX["FXF-2026-002"], FX["FXF-2026-001"]
    sgd = D(f2["confirmation_buy_amount"]) - D(f2["buy_amount"])  # P30
    usd = D(f2["difference_usd_at_8_oct"])
    assert sgd == D(f2["difference_sgd"])

    def fx_row():
        r = row_for(j, f2["id"])
        r.first.wait_for(timeout=15000)
        assert r.count() == 1, "more than one case for the forward"
        txt = r.inner_text()
        assert "Trade differs" in txt, f"row is not a Trade differs case: {txt[:200]}"
        assert f"SGD {sgd:,.0f}" in txt or f"{usd:,}" in txt, f"size is neither SGD {sgd} nor USD {usd}: {txt[:200]}"
        return "one case for the forward, size " + re.search(r"(SGD|USD) [\d,.]+", txt).group(0)

    def fx_case():
        row_for(j, f2["id"]).get_by_role("link").first.click()
        page.get_by_role("heading", name=re.compile("Trade differs")).first.wait_for(timeout=20000)
        page.get_by_role("region", name="What was compared").wait_for(timeout=15000)
        txt = page.inner_text("body")
        assert money(sgd) in txt or f"{usd:,}" in txt, f"case page shows neither {money(sgd)} nor {usd}"
        return "case page shows the difference " + (money(sgd) if money(sgd) in txt else f"{usd:,}")

    def none_for_matched():
        page.get_by_role("table").wait_for(timeout=15000)
        ids = [f1["id"]] + [t["id"] for t in U["trades_oct"] if t["result"] == "matched"]
        assert ids[1:] == ["T-20261001-001", "T-20261002-002", "T-20261007-006"], "universe matched list changed"
        bad = {i: row_for(j, i).count() for i in ids if row_for(j, i).count()}
        assert not bad, f"cases opened for matched items: {bad}"
        return "no case for " + ", ".join(ids)
    j.step("p30-case-listed", f"one case for {f2['id']} (sell USD 3,000,000 at 1.3425, confirmed 1.3452): difference SGD {sgd:,.0f} or USD {usd:,}", fx_row)
    j.step("p30-case-open", "case page: what was compared shows both amounts and the difference over the tolerance", fx_case)
    page.get_by_role("link", name="All cases").click()
    j.step("p31-matched-no-case", "no case for FXF-2026-001 or the matched trades T-20261001-001, T-20261002-002, T-20261007-006", none_for_matched)


if __name__ == "__main__":
    main_for(2, "UC8 FX forward confirmation mismatch and matched trades (P30, P31)", body)
