"""UC1b_2 browser journey. Run: python uc1b_2.py --base URL --creds PATH --out DIR (Playwright sync, Chromium, 1440x900)."""
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


def brow(page, label: str):
    """The Brief row whose first cell is this label (a plain has_text also matches rows that mention it in their source text)."""
    return page.locator("tbody tr").filter(has=page.locator("td:first-child, th:first-child").filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$"))).first


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


# UC1 charter 2 (P06 and the CIO Brief): the Office view, "Why did this move" on the liquid book, and the Brief from the new shell.
SPONSOR = next(p for p in U["people"] if p["platform_role"] == "sponsor")["name"]
LB = U["liquid_book_month_end"]
AUG, SEP = Decimal(LB["2026-08-31"]["total"]), Decimal(LB["2026-09-30"]["total"])
MOVE = SEP - AUG  # 1,648,000
REP = U["report_issued"]
LIQ_LINE = next(l for l in REP["lines"] if Decimal(l["value"]) == SEP)  # "Liquid book"
A_LINE = REP["lines"][0]
A_AMD = next(s for s in U["statements"] if s["fund"] == "A" and s["kind"] == "amended" and s["period_end"] == "2026-09-30")
LIQ_PORT = next(p for p in U["portfolios"] if p["portfolio_code"] == "EG-LIQUID")["portfolio_name"]
P06 = [n(AUG), n(SEP), n(MOVE)]
WHY = re.compile("Why did this move", re.I)


def main() -> int:
    a = args()
    email, password = creds_for(a.creds, SPONSOR)
    with sync_playwright() as pw:
        b, page = browser(pw, a)
        r = Run(page, Path(a.out) / "uc1b_2", "UC1 charter 2: Why did this move on the liquid book, and the CIO Brief", password)
        base = a.base.rstrip("/")
        found: list[str] = []  # where the P06 figures showed up

        def s1():
            sign_in(page, base, email, password)
            settle(page)
            page.get_by_role("link", name="Consume", exact=True).click()
            page.wait_for_url(re.compile(r"/centre/consume"))
            settle(page)
            try:  # the heading renders after the route change: wait for it rather than read it once
                page.get_by_role("heading", name="Consume").first.wait_for(timeout=15000)
            except Exception:  # noqa: BLE001
                raise AssertionError("no Consume heading")
            return "on Consume as " + SPONSOR

        def s2():
            office = page.get_by_role("link", name=re.compile("office", re.I))
            if office.count() == 0:
                go(page, base, "/centre/consume/office")
                raise AssertionError("Consume has no link or tab to the Office view (it lists projects only); opened /centre/consume/office by address")
            office.first.click()
            page.wait_for_url(re.compile(r"/consume/office"))
            return "reached Office view from Consume"

        def s3():
            if "/consume/office" not in page.url:
                go(page, base, "/centre/consume/office")
            page.get_by_role("heading", name="Office view").wait_for()
            page.get_by_text("All holdings:").wait_for()
            page.wait_for_function("!document.body.innerText.includes('Loading the')")
            hold = page.get_by_role("region", name="Holdings")
            ht = hold.inner_text()
            need(LIQ_PORT in ht, f"Holdings lacks {LIQ_PORT}")
            need(n(SEP) in ht, f"Holdings lacks the liquid total {n(SEP)}")
            iss = page.get_by_role("region", name="Issued versus known now")
            row = iss.locator("tr").filter(has_text=LIQ_LINE["label"]).first
            rt = row.inner_text()
            need(rt.count(n(SEP)) >= 2, f"Liquid book row should show {n(SEP)} as issued and known now: {rt!r}")
            need("Official" in rt, f"Liquid book row is not Official: {rt!r}")
            return " ".join(rt.split())

        def s4():
            # the Office view's "Why did this move" is a section with a Portfolio choice and a Month, not a button (OfficePage.tsx)
            sec = page.get_by_role("region", name=WHY)
            if sec.count() == 0:
                btn = page.get_by_role("button", name=WHY)
                need(btn.count() > 0, "the Office view has no 'Why did this move' for the liquid book (P06 says Consume > Office view > Why did this move)")
                btn.first.click()
            else:
                pick = sec.get_by_label("Portfolio")
                opt = next((o for o in pick.locator("option").all_inner_texts() if "liquid" in o.lower()), None)
                need(opt, f"no liquid book in the Portfolio choice: {pick.locator('option').all_inner_texts()}")
                pick.select_option(label=opt)
                sec.get_by_label("Month").fill("2026-09")
                sec.get_by_text(re.compile(re.escape(n(MOVE)))).first.wait_for(timeout=20000)
            t = r.body()
            need(all(x in t for x in P06), f"answer lacks {P06}")
            found.append("Office view")
            return "answer shows " + ", ".join(P06)

        def s5():
            if "/consume/office" not in page.url:
                go(page, base, "/centre/consume/office")
                page.get_by_text("All holdings:").wait_for()
            page.get_by_role("link", name="Open the CIO Brief").click()
            page.wait_for_url(re.compile(r"/centre/consume/brief/"))
            settle(page)
            page.locator("table tbody tr").first.wait_for()
            need(dmy(REP["issued_at"]) in r.body(), f"Brief does not say Issued {dmy(REP['issued_at'])}")
            lt = brow(page, LIQ_LINE["label"]).inner_text()
            need(n(SEP) in lt, f"Brief liquid row lacks {n(SEP)}: {lt!r}")
            at = brow(page, A_LINE["label"]).inner_text()
            need(n(A_LINE["value"]) in at and n(A_AMD["value"]) in at and "Revised" in at,
                 f"Brief Fund A row should show {n(A_LINE['value'])}, {n(A_AMD['value'])}, Revised: {at!r}")
            return "Brief open; " + " ".join(at.split())

        def s6():
            row = brow(page, A_LINE["label"])
            row.get_by_role("button", name="Why did this move?").click()
            sec = page.get_by_role("region", name="Explanation")
            sec.wait_for()
            page.wait_for_function("!document.body.innerText.includes('Working it out')")
            t = sec.inner_text()
            need(n(A_AMD["value"]) in t and n(Decimal(A_AMD["value"]) - Decimal(A_LINE["value"])) in t, f"explanation lacks the Fund A figures: {t[:300]!r}")
            return " ".join(t.split())[:300]

        def s7():
            # the Brief's button explains a line that changed since issue (BriefPage.tsx l.changed); the liquid book did not
            # change (41,200,000 issued and now), so it has none. P06 (the month's move) is the Office view's answer (s4).
            row = brow(page, LIQ_LINE["label"])
            need(row.get_by_role("button", name="Why did this move?").count() == 0,
                 "the Brief offers 'Why did this move?' on the liquid book line, which has not changed since issue")
            need(brow(page, A_LINE["label"]).get_by_role("button", name="Why did this move?").count() > 0,
                 "the Brief has no 'Why did this move?' on the Fund A line, which changed since issue")
            return "button on the changed Fund A line only; liquid book unchanged since issue"

        def s8():
            go(page, base, "/centre/consume")
            page.get_by_role("button", name=re.compile(re.escape(U["project"]["title"]))).first.click()
            sec = page.locator('section[aria-label^="Dashboards of"]')
            sec.get_by_role("link").first.click()
            page.locator("article").first.wait_for()
            seen = []
            for i in range(page.locator("article").count()):
                art = page.locator("article").nth(i)
                w = art.get_by_role("button", name=WHY)
                if w.count() == 0:
                    continue
                title = art.locator("strong").first.inner_text()
                w.click()
                page.wait_for_function("!document.body.innerText.includes('Lumen is working')")
                page.wait_for_timeout(500)
                said = re.findall(r"[^\n]*\b(?:is|are) (?:up|down|unchanged)[^\n]*", r.body())
                seen.append(f"{title}: {(said[-1] if said else 'no answer')[:200]}")
                if all(x in r.body() for x in P06):
                    found.append(f"dashboard tile {title}")
            need(seen, "no accepted tile with a 'Why did this move' button")
            need(found and found[-1].startswith("dashboard"), "no tile answer shows the liquid book move " + str(P06) + "; tiles said: " + " || ".join(seen))
            return " || ".join(seen)

        def s9():
            need(found, f"nowhere on screen does a Why-did-this-move answer give the liquid book move {P06} (Aug {n(AUG)} to Sep {n(SEP)})")
            return "P06 figures seen in: " + ", ".join(found)

        r.step("Sign in and open Consume", "Consume page for the CIO", s1)
        r.step("Reach the Office view from Consume", "A visible way to the Office view", s2)
        r.step("Office view: liquid book figures", f"{LIQ_PORT} {n(SEP)}; Liquid book issued and known now {n(SEP)}, Official", s3)
        r.step("Office view: Why did this move on the liquid book", f"Answer with {n(AUG)} to {n(SEP)}, +{n(MOVE)}", s4)
        r.step("Open the CIO Brief from the Office view", f"Brief issued {dmy(REP['issued_at'])}; liquid {n(SEP)}; Fund A {n(A_LINE['value'])} to {n(A_AMD['value'])} Revised", s5)
        r.step("Brief: Why did this move on the Fund A line", "Explanation with the 180,000 change", s6)
        r.step("Brief: Why did this move only on lines changed since issue", "Fund A has the button; the liquid book (unchanged) has none", s7)
        r.step("Consume dashboard tile: Why did this move", f"A tile answer with {P06}", s8, soft=True)
        r.step("P06 answer reachable somewhere", f"At least one route shows {n(AUG)} to {n(SEP)}, +{n(MOVE)}", s9)
        rc = r.finish()
        b.close()
        return rc


if __name__ == "__main__":
    sys.exit(main())
