"""Browser journey uc6a_1: Office view Liquidity (P21, P23)

python tests/e2e_10uc/uc6a_1.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Playwright (sync, Chromium), 1440x900. Signs in through the login page as the approver named in docs/test/10uc_universe.json, walks the
journey, screenshots every step to DIR/uc6a_1/NN-<step>.png and writes DIR/uc6a_1/result.md. Exit 1 on any failed step.
Figures come from docs/test/10uc_universe.json; nothing is hard-coded twice. Passwords are read from the creds file and never printed or saved.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
PLANTED = {p["id"]: p for p in U["planted"]}
FUND = {f["key"]: f for f in U["funds"]}
MOVE = {m["id"]: m for m in U["cash_movements"]}
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
LIQ = {r["legal_entity"]: r for r in U["liquidity_9_oct"]}
MGR = {m["id"]: m for m in U["managers"]}
APPROVER = next(p for p in U["people"] if p["platform_role"] == "approver")
ccy = "USD"

BAD = [(r"\bundefined\b", "the word undefined"), (r"\bNaN\b", "NaN"), (r"\[object ", "[object ...]"), (r"Traceback|Internal Server Error|stack trace", "error text"),
       (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "a raw uuid"), (r"\bmv-\d{4}-", "a raw movement id"),
       (r"\bEG-[A-Z]+\b(?!-)", "a raw entity code"), (r"\bMGR-[A-Z]+\b", "a raw manager code"), (r"\bHTTP [45]\d\d\b", "an HTTP status")]


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("−", "-").replace(" ", " ").replace(" ", " ")).strip()


def money(v, c=ccy) -> str:
    """The way the Office view writes a figure: 'USD 880,400', 'USD -169,600', 'USD 0'."""
    s = f"{Decimal(str(v)):,.2f}"
    s = s[:-3] if s.endswith(".00") else s
    return f"{c} {s}"


def day(iso: str) -> str:
    y, m, d = (int(x) for x in iso[:10].split("-"))
    return f"{d} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} {y}"


def amount(cell: str):
    m = re.search(r"-?[\d,]+(?:\.\d+)?", norm(cell))
    return Decimal(m.group(0).replace(",", "")) if m else None


def creds_for(path: str, email: str) -> str:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not line.startswith("#") and parts[0].lower() == email.lower():
            return parts[1]
    raise SystemExit(f"no sign-in for {email} in the creds file")


class Run:
    def __init__(self, name: str, title: str, out: str, page: Page):
        self.name, self.title, self.page, self.rows, self.n = name, title, page, [], 0
        self.dir = Path(out) / name
        self.dir.mkdir(parents=True, exist_ok=True)

    def shot(self, step: str, full: bool = False) -> str:
        self.n += 1
        f = f"{self.n:02d}-{re.sub(r'[^a-z0-9]+', '-', step.lower()).strip('-')}.png"
        try:
            self.page.screenshot(path=str(self.dir / f), full_page=full)
        except Exception:  # a screenshot that cannot be taken must not hide the step result
            f = "(screenshot failed)"
        return f

    def step(self, name: str, expected: str, fn, full: bool = False):
        """Runs fn() -> actual text; any assertion or timeout is a fail. Always screenshots and also checks the screen for raw ids and errors."""
        try:
            actual, ok = fn() or "as expected", True
        except (AssertionError, PWTimeout) as e:
            actual, ok = f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}", False
        except Exception as e:  # noqa: BLE001  (a broken page is a result, not a crash)
            actual, ok = f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}", False
        bad = self.dirty()
        if bad:
            actual, ok = f"{actual}; screen shows {bad}", False
        self.rows.append((name, expected, actual, ok, self.shot(name, full)))
        print(("PASS " if ok else "FAIL ") + name)

    def note(self, name: str, text: str):
        """A thing seen that is not a failure of a planted fact (missing link, confusing wording)."""
        self.rows.append((name, "(observation)", text, True, ""))

    def dirty(self) -> str:
        found = []
        text = norm(self.page.locator("body").inner_text())
        for rx, what in BAD:
            if re.search(rx, text):
                found.append(what)
        for a in self.page.get_by_role("alert").all():
            # a business warning (ds-warn: the Entity B shortfall, a6.7) is content; only an error alert counts
            if a.is_visible() and a.inner_text().strip() and "ds-warn" not in (a.get_attribute("class") or ""):
                found.append(f"an alert: {norm(a.inner_text())[:80]}")
        return ", ".join(found)

    def finish(self) -> int:
        ok = all(r[3] for r in self.rows)
        lines = [f"# {self.name}: {self.title}", "", f"Result: {'PASS' if ok else 'FAIL'}", "",
                 "| # | Step | Expected | Actual | Pass | Screenshot |", "|---|---|---|---|---|---|"]
        for i, (s, e, a, p, f) in enumerate(self.rows, 1):
            cell = lambda t: t.replace("|", "/").replace("\n", " ")  # noqa: E731
            lines.append(f"| {i} | {cell(s)} | {cell(e)} | {cell(a)} | {'pass' if p else 'FAIL'} | {f} |")
        (self.dir / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{self.name}: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1


def settle(page: Page):
    """Wait until no 'Loading the ...' line is left."""
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => !/Loading the/.test(document.body.innerText)", timeout=30000)


def sign_in(page: Page, base: str, email: str, password: str):
    page.goto(base.rstrip("/") + "/")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.get_by_label("Email").wait_for(state="detached", timeout=30000)
    page.wait_for_load_state("networkidle")


def open_office(page: Page, base: str) -> str:
    """Goes to the Office view. The Consume landing (ProjectList) has no link to it, so a link is tried first and the address is the fallback."""
    link = page.get_by_role("link", name=re.compile("Office view", re.I))
    if link.count():
        link.first.click()
        how = "link"
    else:
        page.goto(base.rstrip("/") + "/centre/consume/office")
        how = "address only (no link to the Office view on screen)"
    page.get_by_role("heading", name="Office view", level=1).wait_for(timeout=30000)
    settle(page)
    return how


def card(page: Page, entity_code: str):
    """The Liquidity card of one legal entity, found by its heading."""
    sec = page.get_by_role("region", name="Liquidity")
    return sec.locator("div").filter(has=page.get_by_role("heading", name=ENT[entity_code], exact=True)).first


def bucket_cells(c, label: str) -> list[str]:
    row = c.get_by_role("row").filter(has_text=label).first
    return [norm(x) for x in row.get_by_role("cell").all_inner_texts()]


def check_buckets(c, code: str) -> str:
    """Every bucket row of the entity: calls, distributions and cash after the calls, against the universe."""
    row, running, seen = LIQ[code], Decimal(LIQ[code]["available_cash_administrator_8_oct"]), []
    for key, label in (("30", "Within 30 days"), ("60", "31 to 60 days"), ("90", "61 to 90 days")):
        calls, dist = Decimal(row["calls_due"][key]), Decimal(row["distributions_expected"][key])
        running -= calls
        cells = bucket_cells(c, label)
        cells[3:4] = [re.sub(r"\s*\(shortfall\)$", "", x) for x in cells[3:4]]  # a negative figure now carries the word shortfall (a6.7)
        want = [label, money(calls), money(dist), money(running)]
        assert cells[:4] == want, f"{ENT[code]} row '{label}': expected {want}, saw {cells[:4]}"
        seen.append(f"{label}: {cells[1]} / {cells[2]} / {cells[3]}")
    return "; ".join(seen)


def main(name: str, title: str, journey) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pw_secret = creds_for(a.creds, APPROVER["email"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(20000)
        run = Run(name, title, a.out, page)
        try:
            run.step("Sign in as the approver", f"Sign in page accepts {APPROVER['name']} ({APPROVER['business_role']}) and lands in the centre",
                     lambda: (sign_in(page, a.base, APPROVER["email"], pw_secret), f"signed in, now at {page.url.replace(a.base.rstrip('/'), '')}")[1])
            journey(run, page, a.base)
        finally:
            code = run.finish()
            browser.close()
    return code


NAME, TITLE = "uc6a_1", "Office view, Liquidity: calls due in 30/60/90 days, Fund E unconfirmed flagged (P21, P23)"
CALL_C, CALL_E, CALL_D, DIST_A = (MOVE[k] for k in ("mv-2026-10-C-call", "mv-2026-10-E-call", "mv-2026-12-D-call", "mv-2026-11-A-dist"))
fname = lambda m: FUND[m["fund"]]["canonical_name"]  # noqa: E731
due = lambda m: day(m["due_date"])  # noqa: E731


def journey(run: Run, page: Page, base: str):
    how = {}

    def office():
        how["v"] = open_office(page, base)
        assert page.get_by_role("heading", name="Office view", level=1).is_visible()
        return f"Office view open, reached by {how['v']}"
    run.step("Open the Office view", "Office view page opens under Consume with its currency switch (USD/SGD)", office)
    if not how.get("v", "link").startswith("link"):
        run.note("Navigation", "The Consume landing shows no way into the Office view; the test had to type the address (ui/src/v1/cxui/ProjectList.tsx, ui/src/pages/ConsumeCentre.tsx).")

    def liquidity():
        sec = page.get_by_role("region", name="Liquidity")
        sec.scroll_into_view_if_needed()
        assert sec.get_by_role("heading", name="Liquidity", level=2).is_visible()
        for code in ("EG-HOLD", "EG-TRUST", "EG-B"):
            assert card(page, code).is_visible(), f"no Liquidity card for {ENT[code]}"
        return "Liquidity section shows a card for each of the three entities"
    run.step("Liquidity section", f"Liquidity lists {', '.join(ENT.values())}", liquidity)

    b = LIQ["EG-B"]

    def entity_b():
        c = card(page, "EG-B")
        c.scroll_into_view_if_needed()
        t = norm(c.inner_text())
        assert f"Available cash {money(b['available_cash_administrator_8_oct'])}" in t, f"available cash not {money(b['available_cash_administrator_8_oct'])}: {t[:160]}"
        return check_buckets(c, "EG-B")
    run.step("Entity B calls 30/60/90 days", f"P21/P23 Entity B: calls {money(b['calls_due']['30'])} within 30 days, {money(b['calls_due']['60'])} in 31 to 60, "
             f"{money(b['calls_due']['90'])} in 61 to 90; available cash {money(b['available_cash_administrator_8_oct'])}", entity_b)

    def unconfirmed():
        c = card(page, "EG-B")
        # the label is its own <strong>: read the whole status line around it (j-uc6a.0)
        line = norm(c.get_by_role("status").filter(has=page.locator("strong", has_text=re.compile(r"^Not confirmed yet:"))).first.inner_text())
        want = f"{fname(CALL_E)} {money(CALL_E['amount'])} due {due(CALL_E)}"
        assert want in line, f"expected '{want}' in '{line}'"
        assert fname(CALL_C) not in line, "the confirmed Fund C call is flagged as unconfirmed"
        return line
    run.step("Fund E flagged not confirmed", f"P21 'Not confirmed yet' names {fname(CALL_E)} {money(CALL_E['amount'])} due {due(CALL_E)} and not the confirmed {fname(CALL_C)} call", unconfirmed)

    def where_b():
        c = card(page, "EG-B")
        c.get_by_role("button", name="Where is this from?").click()
        t = norm(c.inner_text())
        for m, status in ((CALL_C, "confirmed"), (CALL_E, "waiting to be confirmed"), (CALL_D, "confirmed")):
            want = f"{fname(m)}: capital call {money(m['amount'])} due {due(m)}, {status}"
            assert want in t, f"expected '{want}'"
        assert "as at 8 Oct 2026" in t, "cash source date is not 8 Oct 2026"
        return "source list shows Fund C call confirmed, Fund E call waiting to be confirmed, Fund D call confirmed, cash as at 8 Oct 2026"
    run.step("Where is this from, Entity B", f"P21/P23 sources: {fname(CALL_C)} {money(CALL_C['amount'])} due {due(CALL_C)} confirmed; {fname(CALL_E)} {money(CALL_E['amount'])} due {due(CALL_E)} waiting; "
             f"{fname(CALL_D)} {money(CALL_D['amount'])} due {due(CALL_D)} confirmed; cash as at 8 Oct 2026", where_b)

    h = LIQ["EG-HOLD"]

    def holdings_card():
        c = card(page, "EG-HOLD")
        c.scroll_into_view_if_needed()
        c.get_by_role("button", name="Where is this from?").click()
        s = check_buckets(c, "EG-HOLD")
        t = norm(c.inner_text())
        want = f"{fname(DIST_A)}: distribution {money(DIST_A['amount'])} due {due(DIST_A)}, waiting to be confirmed"
        assert want in t, f"expected '{want}'"
        assert "Not confirmed yet" not in t, "a distribution is flagged as an unconfirmed call"
        return s
    run.step("Evergreen Holdings distribution", f"P23 {ENT['EG-HOLD']}: distribution {money(DIST_A['amount'])} expected {due(DIST_A)} in the 31 to 60 day row; no calls", holdings_card)

    def trust():
        c = card(page, "EG-TRUST")
        c.scroll_into_view_if_needed()
        assert f"Available cash {money(LIQ['EG-TRUST']['available_cash_administrator_8_oct'])}" in norm(c.inner_text())
        s = check_buckets(c, "EG-TRUST")
        assert "Not confirmed yet" not in norm(c.inner_text())
        return s
    run.step("Evergreen Family Trust has no calls", f"{ENT['EG-TRUST']} shows {money(LIQ['EG-TRUST']['available_cash_administrator_8_oct'])} and no calls or flags", trust)

    def wording():
        t = norm(page.get_by_role("region", name="Liquidity").inner_text())
        assert "Not available yet" not in t, "a figure is missing in Liquidity"
        return "no missing figure in Liquidity"
    run.step("No missing figure", "Liquidity shows no 'Not available yet' on the planted entities", wording, full=True)


if __name__ == "__main__":
    sys.exit(main(NAME, TITLE, journey))
