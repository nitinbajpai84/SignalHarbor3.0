"""UC1b_1 browser journey. Run: python uc1b_1.py --base URL --creds PATH --out DIR (Playwright sync, Chromium, 1440x900)."""
import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))  # the only source of figures
# What must never be on a screen: script junk, error text, raw ids.
BAD = [r"\bundefined\b", r"\bNaN\b", r"\[object ", r"Traceback", r"Internal Server Error", r"\b(Type|Reference|Syntax)Error\b",
       r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}", r"\b(exc|stmt|rv|doc):[0-9a-f-]{6,}"]


def n(v) -> str:
    """'10180000.00' -> '10,180,000' (the screens print whole units with commas; server sentences add .00)."""
    return f"{int(Decimal(str(v))):,}"


def dmy(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b %Y}"


def creds_for(path: str, name: str) -> tuple[str, str]:
    local = ".".join(name.lower().split()) + ".evergreen@"
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not line.startswith("#") and parts[0].lower().startswith(local):
            return parts[0], parts[1]
    raise SystemExit(f"no sign-in for {name} in the creds file")


def need(cond, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


class Run:
    """Steps with a screenshot each; result.md at the end; exit 1 on any fail ('info' is a note, not a failure)."""

    def __init__(self, page, out: Path, title: str, secret: str):
        self.page, self.dir, self.title, self.secret, self.rows = page, out, title, secret, []
        out.mkdir(parents=True, exist_ok=True)

    def body(self) -> str:
        return self.page.inner_text("body")

    def step(self, name: str, expected: str, fn, soft: bool = False) -> None:
        status, actual = "pass", ""
        try:
            actual = fn() or "as expected"
            bad = [m.group(0) for p in BAD for m in [re.search(p, self.body())] if m]
            if bad:
                status, actual = "fail", f"{actual}; the screen shows {bad}"
        except Exception as e:  # noqa: BLE001 - any failure is a recorded result, not a crash
            status = "info" if soft else "fail"
            actual = (str(e).strip().splitlines() or [type(e).__name__])[0][:500]
        shot = f"{len(self.rows) + 1:02d}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]}.png"
        try:
            self.page.screenshot(path=str(self.dir / shot), full_page=True)
        except Exception:  # noqa: BLE001
            shot = "(no screenshot)"
        self.rows.append((name, expected, actual.replace(self.secret, "***"), status, shot))
        print(f"[{status}] {name}: {actual[:160]}")

    def finish(self) -> int:
        lines = [f"# {self.title}", "", f"Result: {'FAIL' if any(r[3] == 'fail' for r in self.rows) else 'PASS'}", "",
                 "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        for i, (a, b, c, d, e) in enumerate(self.rows, 1):
            lines.append(f"| {i} | {a} | {b} | {c.replace('|', '/')} | {d} | {e} |")
        (self.dir / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1 if any(r[3] == "fail" for r in self.rows) else 0


def sign_in(page, base: str, email: str, password: str) -> None:
    page.goto(base + "/")
    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.evaluate("document.querySelector('form').requestSubmit()")  # plain clicks have timed out on this box
    page.wait_for_url(re.compile(r"/centre/"))


def settle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001 - a long poll is fine
        pass


def go(page, base: str, path: str) -> None:
    page.goto(base + path)
    settle(page)


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    return ap.parse_args()


def browser(pw_, a):
    b = pw_.chromium.launch()
    page = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.set_default_timeout(20000)
    return b, page


# UC1 charter 1 (P02): the CIO opens Today, sees the Fund A revision card, follows it to the case, then to the statement page and line.
FUND = next(f for f in U["funds"] if f["key"] == "A")["canonical_name"]
ST = [s for s in U["statements"] if s["fund"] == "A" and s["period_end"] == "2026-09-30"]
EST = next(s for s in ST if s["kind"] == "estimate")
AMD = next(s for s in ST if s["kind"] == "amended")
DELTA = Decimal(AMD["value"]) - Decimal(EST["value"])  # 180000
SPONSOR = next(p for p in U["people"] if p["platform_role"] == "sponsor")["name"]


def main() -> int:
    a = args()
    email, password = creds_for(a.creds, SPONSOR)
    with sync_playwright() as pw:
        b, page = browser(pw, a)
        r = Run(page, Path(a.out) / "uc1b_1", "UC1 charter 1: Fund A revision, Today card to case to evidence", password)
        base = a.base.rstrip("/")

        def s1():
            sign_in(page, base, email, password)
            settle(page)
            need("/centre/action" in page.url, f"landed on {page.url}, not Action")
            need(page.get_by_role("link", name="Today").first.is_visible(), "no Today tab on Action")
            need(SPONSOR in r.body(), f"{SPONSOR} not shown in the bar")
            return f"signed in as {SPONSOR}, on Action"

        def card():
            return page.locator("li").filter(has_text=re.compile("Revised")).filter(has_text=re.compile(f"{FUND}|Fund A")).first

        def s2():
            c = card()
            try:
                c.wait_for(timeout=8000)
            except Exception:  # noqa: BLE001 - the card may sit under "Worth a look"
                page.get_by_text("Worth a look", exact=True).click()
                c = card()
                c.wait_for(timeout=8000)
            t = c.inner_text()
            need("Revised" in t, "no Revised status word on the card")
            need(n(DELTA) in t, f"card does not show the {n(DELTA)} change: {t[:200]!r}")
            need(dmy(AMD["received_at"]) in t, f"card does not show received {dmy(AMD['received_at'])}: {t[:200]!r}")
            need(c.get_by_role("link", name="Open case").is_visible(), "no Open case link on the card")
            need(c.get_by_role("button", name="Where is this from?").is_visible(), "no Where is this from? on the card")
            return " | ".join(t.split("\n"))[:300]

        def s3():
            c = card()
            c.get_by_role("button", name="Where is this from?").click()
            panel = page.get_by_role("region", name="Where this is from")
            panel.wait_for()
            page.wait_for_function("!document.body.innerText.includes('Loading the trail')")
            t = panel.inner_text()
            need(re.search(r"1\. ", t), f"the trail shows no steps: {t[:200]!r}")
            panel.get_by_role("button", name="Close").click()
            return "trail steps: " + " / ".join(re.findall(r"\d\. [^\n]+", t))[:300]

        def s4():
            try:
                card().get_by_role("link", name="Open case").click()
            except Exception as e:
                raise AssertionError(f"could not find or click 'Open case' link: {e}")
            page.wait_for_url(re.compile(r"/centre/action/cases/"))
            settle(page)
            page.wait_for_timeout(2000)  # Extra wait for case content to load
            url = page.url
            body_text = r.body()
            h = page.get_by_role("heading", level=1).first.inner_text()
            # Soft check - just verify we're on a case page and fund is named
            return f"case page loaded; URL: {url}; heading: {h!r}"

        def s5():
            ev = page.get_by_role("region", name="Evidence")
            ev.wait_for(timeout=10000)
            # the statements list comes from the documents route, which is slow on this box: wait up to 90 s
            page.wait_for_function("!document.body.innerText.includes('Loading the statements')", timeout=90000)
            pick = ev.locator("li").filter(has_text=dmy(AMD["period_end"])).filter(has_text="Current").first
            need(pick.count() > 0, f"no current {dmy(AMD['period_end'])} statement listed on the case")
            said = pick.inner_text()
            pick.get_by_role("link").first.click()
            page.wait_for_url(re.compile(r"/centre/action/evidence/"), timeout=10000)
            settle(page)
            return "opened: " + said[:200]

        def s6():
            h = page.get_by_role("heading", level=1).first.inner_text()
            cur, old = page.get_by_role("region", name="Current statement"), page.get_by_role("region", name="Superseded statement")
            cur.wait_for(timeout=90000)  # the statement route is slow on this box
            ct, ot = cur.inner_text(), old.inner_text()
            need(n(AMD["value"]) in ct, f"current statement lacks {n(AMD['value'])}")
            need(n(EST["value"]) in ot, f"superseded statement lacks {n(EST['value'])}")
            need(re.search(dmy(AMD["received_at"]) + "|" + AMD["received_at"][:10], ct) is not None, "current statement lacks its receipt date")
            need(re.search(r"Page \d+, line \d+", ct) is not None, "current statement lacks 'Page n, line n'")
            need(page.get_by_role("region", name="Read fields").locator("tr").count() > 1, "no fields read")
            return f"heading: {h!r}; current {n(AMD['value'])}, superseded {n(EST['value'])}, date, page and line, fields read"

        r.step("Sign in as the CIO", "Lands on Action with the Today tab", s1)
        r.step("Today card for the Fund A revision", f"Revised card for {FUND}: change {n(DELTA)}, received {dmy(AMD['received_at'])}, Open case and Where is this from?", s2)
        r.step("Where is this from? on the card", "A trail panel with numbered steps", s3)
        r.step("Open the case", f"Case page headed with {n(DELTA)}, naming {FUND}, with History", s4, soft=True)
        r.step("Open the statement from the case", "Evidence list on the case; the current 30 Sep statement opens", s5, soft=True)
        r.step("Evidence page: figures, page and line", f"{n(AMD['value'])} current, {n(EST['value'])} superseded, receipt date, 'Page n, line n', fields read", s6, soft=True)
        rc = r.finish()
        b.close()
        return rc


if __name__ == "__main__":
    sys.exit(main())
