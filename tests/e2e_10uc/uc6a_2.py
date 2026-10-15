"""Browser journey uc6a_2: Finance case and commitments (P22, P24)

python tests/e2e_10uc/uc6a_2.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Playwright (sync, Chromium), 1440x900. Signs in through the login page as the approver named in docs/test/10uc_universe.json, walks the
journey, screenshots every step to DIR/uc6a_2/NN-<step>.png and writes DIR/uc6a_2/result.md. Exit 1 on any failed step.
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


def called_now(c) -> Decimal:
    """Answer key P24 and its item 3: a confirmed notice counts as called once confirmed (C 4,050,000, D 4,750,000), not at 30 Sep."""
    later = sum((Decimal(m["amount"]) for m in U["cash_movements"] if m.get("fund") == c["fund"] and m.get("notice_kind") == "call"
                 and m.get("confirmation_status") == "confirmed" and str(m.get("due_date")) > U["meta"]["as_of"]), Decimal(0))
    return Decimal(c["called_to_date"]) + later


def uncalled_now(c) -> Decimal:
    return Decimal(c["commitment_amount"]) - called_now(c)


NAME, TITLE = "uc6a_2", "Finance case 'Fund the capital call', Entity B cash after the calls, commitments called and uncalled (P22, P24)"
CALL_C, CALL_E = MOVE["mv-2026-10-C-call"], MOVE["mv-2026-10-E-call"]
fname = lambda m: FUND[m["fund"]]["canonical_name"]  # noqa: E731
CASE_TITLE = "Fund the capital call"


def journey(run: Run, page: Page, base: str):
    b = LIQ["EG-B"]

    def cases_list():
        page.goto(base.rstrip("/") + "/centre/action")
        page.get_by_role("navigation", name="Action tabs").get_by_role("link", name="Cases", exact=True).click()
        page.get_by_role("heading", name="Action", exact=True, level=1).wait_for()
        settle(page)
        rows = page.get_by_role("row").filter(has_text=CASE_TITLE)  # the title may name the fund after these words (a6.11)
        assert rows.count() == 1, f"expected exactly one '{CASE_TITLE}' case, saw {rows.count()} (none would mean the Fund C call did not open it, two that Fund E did too)"
        t = norm(rows.first.inner_text())
        assert money(CALL_C["amount"]) in t, f"case size not {money(CALL_C['amount'])}: {t}"
        assert f"Due {day(CALL_C['due_date'])[:-5]}" in t, f"case due date not {day(CALL_C['due_date'])[:-5]}: {t}"
        return t
    run.step("Cases list", f"P22 Action > Cases has one Finance case '{CASE_TITLE}' for the {fname(CALL_C)} call: {money(CALL_C['amount'])}, due {day(CALL_C['due_date'])[:-5]}; "
             f"no case for the unconfirmed {fname(CALL_E)} call", cases_list)

    def case_page():
        row = page.get_by_role("row").filter(has_text=CASE_TITLE).first
        row.get_by_role("link").first.click()
        h1 = page.get_by_role("heading", level=1).filter(has_text=CASE_TITLE)
        h1.wait_for()
        settle(page)
        t = norm(h1.first.inner_text())
        assert money(CALL_C["amount"]) in t, f"case heading does not carry {money(CALL_C['amount'])}: {t}"
        assert page.get_by_role("region", name="History").is_visible(), "no History section"
        return t
    run.step("Open the case", f"Case page headed '{CASE_TITLE}, {money(CALL_C['amount'])}' with its History", case_page)

    def case_says_fund():
        t = norm(page.locator("body").inner_text())
        assert fname(CALL_C) in t, f"the case page never names the fund ({fname(CALL_C)}); the person cannot tell which call to fund"
        assert fname(CALL_E) not in t, "the case mentions the unconfirmed Fund E call"
        return f"case names {fname(CALL_C)}"
    run.step("Case names the fund", f"The case page says which fund called ({fname(CALL_C)}) and does not mention {fname(CALL_E)}", case_says_fund, full=True)

    def liquidity_b():
        open_office(page, base)
        c = card(page, "EG-B")
        c.scroll_into_view_if_needed()
        t = norm(c.inner_text())
        assert f"Available cash {money(b['available_cash_administrator_8_oct'])}" in t, f"available cash not {money(b['available_cash_administrator_8_oct'])}"
        return check_buckets(c, "EG-B")
    run.step("Entity B cash after the calls", f"P22 Entity B: available {money(b['available_cash_administrator_8_oct'])}; cash after calls within 30 days {money(b['after_all_noticed_calls_30d'])} (shortfall)", liquidity_b)

    def shortfall_word():
        t = norm(card(page, "EG-B").inner_text()).lower()
        assert "shortfall" in t or "short" in t or "not enough" in t, "a negative cash figure is shown with no word saying it is a shortfall"
        return "shortfall named"
    run.step("Shortfall is said in words", "The negative figure is explained as a shortfall, not left as a bare minus sign", shortfall_word)

    def confirmed_only():
        t = norm(card(page, "EG-B").inner_text())
        want = money(b["after_confirmed_calls_30d"])
        assert want in t, f"after the confirmed call only, cash {want} is not on screen (the 30-day row mixes in the unconfirmed call)"
        return want
    run.step("Cash after the confirmed call only", f"P22 after the confirmed call {money(b['after_confirmed_calls_30d'])} is visible beside the all-calls figure", confirmed_only)

    def uncalled():
        seen = []
        for code in ("EG-HOLD", "EG-B"):
            want = sum(uncalled_now(c) for c in U["commitments"] if c["legal_entity"] == code)
            t = norm(card(page, code).inner_text())
            assert f"Still to be called {money(want)}" in t, f"{ENT[code]}: expected 'Still to be called {money(want)}'"
            seen.append(f"{ENT[code]} {money(want)}")
        return "; ".join(seen)
    run.step("Still to be called per entity", "P24 Office view uncalled per entity = sum of the fund uncalled amounts", uncalled)

    # P24: each manager's profile, Commitments table
    by_mgr: dict[str, list] = {}
    for c in U["commitments"]:
        by_mgr.setdefault(FUND[c["fund"]]["manager"], []).append(c)
    for mid, coms in by_mgr.items():
        mname = MGR[mid]["name"]

        def profile(mid=mid, mname=mname, coms=coms):
            page.goto(base.rstrip("/") + "/centre/consume/managers")
            page.get_by_role("heading", name="Managers", level=1).wait_for()
            settle(page)
            page.get_by_role("link", name=mname, exact=True).click()
            page.get_by_role("heading", name=mname, level=1).wait_for()
            settle(page)
            sec = page.get_by_role("region", name="Commitments")
            sec.scroll_into_view_if_needed()
            seen = []
            for c in coms:
                name = FUND[c["fund"]]["canonical_name"]
                cells = [norm(x) for x in sec.get_by_role("row").filter(has_text=name).first.get_by_role("cell").all_inner_texts()]
                assert len(cells) >= 5, f"{name}: no commitment row"
                assert cells[1] == ENT[c["legal_entity"]], f"{name}: entity '{cells[1]}', expected '{ENT[c['legal_entity']]}'"
                got = [amount(x) for x in cells[2:5]]
                want = [Decimal(c["commitment_amount"]), called_now(c), uncalled_now(c)]
                assert got == want, f"{name}: committed/called/not yet called {got}, expected {want}"
                assert got[1] <= got[0], f"{name}: called exceeds committed"
                assert all(c["currency"] in x for x in cells[2:5]), f"{name}: currency missing in {cells[2:5]}"
                seen.append(f"{name} {got[0]:,}/{got[1]:,}/{got[2]:,}")
            return "; ".join(seen)
        run.step(f"Commitments, {mname}", "P24 " + "; ".join(f"{FUND[c['fund']]['canonical_name']} committed {Decimal(c['commitment_amount']):,}, called {called_now(c):,}, "
                 f"not yet called {uncalled_now(c):,}" for c in coms), profile)


if __name__ == "__main__":
    sys.exit(main(NAME, TITLE, journey))
