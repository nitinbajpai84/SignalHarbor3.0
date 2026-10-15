"""UC2 analyst, charter 2: open the Entity B break case, ask the agent to explain, add a note, send for approval; the approver sees it in Today (P08).
Run: python uc2a_1.py --base URL --creds PATH --out DIR   (synthetic data only; passwords are read, never printed or saved)."""
import argparse, json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

N = 2
ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
EB = next(r for r in U["cash_8_oct"] if r["legal_entity"] == "EG-B")
TR = next(r for r in U["cash_8_oct"] if r["legal_entity"] == "EG-TRUST")
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
TOL = next(r for r in U["rules"] if r["rule_code"] == "cash_tolerance")["parameters"]
ANALYST = next(p for p in U["people"] if p["name"] == "Mei Chen")
APPROVER = next(p for p in U["people"] if p["platform_role"] == "approver")
n = lambda s: f"{float(s):,.0f}"                      # "880400.00" -> "880,400"
DAY = "2026-10-08"
TITLE = f"Cash differs · {ENT['EG-B']} · {DAY}"       # the case title the check writes (sh_platform/v1/e3_recon.py)
BAD = [r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", r"\b[0-9a-f]{32}\b", r"\bundefined\b", r"\bNaN\b", r"\[object", r"Traceback", r"\bError:", r"\bnull\b"]


class Run:
    def __init__(s, out):
        s.dir = Path(out) / f"uc2a_{N}"; s.dir.mkdir(parents=True, exist_ok=True)
        s.rows, s.i, s.fail = [], 0, False

    def step(s, page, name, expected, check):
        s.i += 1; shot = f"{s.i:02d}-{name}.png"; actual, ok = "", True
        try:
            actual = check() or "as expected"
            body = page.inner_text("body")
            for pat in BAD:
                m = re.search(pat, body)
                if m: raise AssertionError(f"raw or error text on screen: {m.group(0)!r}")
        except Exception as e:  # keep the first line only
            ok, actual, s.fail = False, str(e).splitlines()[0][:300], True
        page.screenshot(path=str(s.dir / shot), full_page=True)
        s.rows.append((s.i, name, expected, actual, ok, shot))
        print(f"{'PASS' if ok else 'FAIL'} {shot} {actual if not ok else ''}")
        return ok

    def write(s):
        L = [f"# UC2 analyst {N}: break case, explain, send for approval", "", f"Result: **{'FAIL' if s.fail else 'PASS'}**", "",
             "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        L += [f"| {i} | {a} | {b} | {c} | {'pass' if ok else 'fail'} | {sh} |" for i, a, b, c, ok, sh in s.rows]
        (s.dir / "result.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def creds(path, email):
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] == email: return p[1]
    raise SystemExit("no sign-in details for the analyst in the creds file")


def login(page, base, email, pw):
    page.goto(base + "/login"); page.get_by_label("Email").fill(email); page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(lambda u: "/login" not in u, timeout=30000)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); base = a.base.rstrip("/"); r = Run(a.out)
    note = (f"Entity B cash on 8 Oct: administrator {n(EB['administrator'])} against trading export {n(EB['trading_export'])} USD, "
            f"{n(EB['difference'])} over the {n(TOL['abs_amount'])} tolerance. Checked and ready for approval.")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); page.set_default_timeout(20000)
        login(page, base, ANALYST["email"], creds(a.creds, ANALYST["email"]))
        page.goto(base + "/centre/action/cases")
        row = page.get_by_role("row").filter(has_text=TITLE)
        if row.count() == 0:  # the check has not been run in this copy yet: run it as the analyst would
            page.goto(base + "/centre/action/reconciliations"); page.get_by_label("Check as at").fill(DAY)
            card = page.locator("li.ds-card").filter(has=page.get_by_role("heading", name="Cash by entity"))
            card.get_by_role("button", name="Run now").click()
            expect(card.get_by_text(re.compile(r"as at\s+\d{1,2}\s+\w+\s+\d{4}"))).to_be_visible()
            page.goto(base + "/centre/action/cases")

        def s1():
            expect(page.get_by_role("columnheader").first).to_be_visible()  # Cases tab content
            expect(row).to_have_count(1); expect(row).to_contain_text(f"USD {n(EB['difference'])}")
        r.step(page, "cases-list", "The Entity B cash break is in Cases with its size", s1)

        def s2():
            row.get_by_role("link").first.click()
            expect(page.get_by_text(re.compile(r"What Tally found", re.I))).to_be_visible(timeout=60000)
            main_text = page.inner_text("main")
            assert TITLE in main_text and f"USD {n(EB['difference'])}" in main_text, "title or size not found"
            assert n(EB["administrator"]) in main_text, f"administrator amount not found"
            # "Ask Tally to write this up" is offered to the case owner only (a2.6), so it is looked for after the case is taken
        r.step(page, "open-case", "Case page: title, size, what was compared, what Tally found", s2)

        def s3():
            t = page.get_by_role("button", name="Take case")
            if t.count(): t.click()
            expect(page.get_by_text(re.compile("Assigned|Being investigated"))).to_be_visible()
            expect(page.get_by_role("button", name="Submit for check")).to_be_visible()
        r.step(page, "take-case", "Analyst takes the case; state reads Assigned and Submit for check appears", s3)

        def s4():
            page.get_by_role("button", name="Ask Tally to write this up").click()
            sec = page.get_by_label("Proposed by Tally")
            expect(sec).to_be_visible(timeout=90000)
            assert len(sec.inner_text().strip()) > len("Proposed by Tally") + 20, "the proposal has no text"
            return "proposal: " + sec.inner_text().replace(chr(10), " ")[:160]
        r.step(page, "agent-explains", "A proposal from Tally appears, labelled as proposed, with text", s4)

        def s5():
            page.get_by_role("button", name="Submit for check").click()
            f = page.get_by_label("Explanation to send for check"); expect(f).to_be_visible()
            f.fill(note); expect(f).to_have_value(note)
        r.step(page, "write-note", "Explanation box opens; the analyst's note (figures from the universe) is typed", s5)

        def s6():
            page.get_by_role("button", name="Confirm").click()
            expect(page.get_by_text("Waiting for a check")).to_be_visible()
            expect(page.get_by_role("button", name="Submit for check")).to_have_count(0)
            expect(page.get_by_label("History")).to_contain_text(n(EB["difference"]))
            expect(page.get_by_role("alert")).to_have_count(0)
        r.step(page, "sent-for-check", "State reads Waiting for a check; the note is in History; no error", s6)
        page.context.close()

        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); page.set_default_timeout(20000)
        login(page, base, APPROVER["email"], creds(a.creds, APPROVER["email"]))
        page.goto(base + "/centre/action")
        card = lambda: page.locator("li.ds-card").filter(has_text=re.compile("Cash differs.*Entity B"))

        def s7():
            expect(page.get_by_role("heading", name="Action", exact=True)).to_be_visible()  # Today is Action's first tab, no heading of its own
            sel = page.get_by_label("Viewing as")
            opts = sel.locator("option").all_inner_texts() if sel.count() else []
            for o in [None] + opts:  # the break card is addressed to a business role; look through the roles this person has
                if o: sel.select_option(label=o)
                for f in ("Needs me", "Worth a look"):  # and through both filters
                    page.get_by_role("button", name=f, exact=True).click()
                    page.wait_for_timeout(1500)
                    if card().count(): break
                if card().count(): break
            expect(card().first).to_be_visible()
            return "found under: " + (o or "default view")
        r.step(page, "approver-today", "Approver's Today lists the Entity B cash break", s7)

        def s8():
            card().first.get_by_role("link").first.click()
            expect(page.get_by_text(re.compile(r"What Tally found", re.I))).to_be_visible(timeout=60000)
            main_text = page.inner_text("main")
            assert "Cash differs" in main_text and "Entity B" in main_text, "title text not found"
            expect(page.get_by_text("Waiting for a check")).to_be_visible()
            expect(page.get_by_role("button", name="Approve")).to_be_visible()
            expect(page.get_by_role("button", name="Send back")).to_be_visible()
            assert n(EB["difference"]) in main_text, f"difference amount {n(EB['difference'])} not found in history/content"
        r.step(page, "approver-opens-case", "Approver opens it: Waiting for a check, Approve and Send back offered, the analyst's note in History", s8)
        b.close()
    r.write(); sys.exit(1 if r.fail else 0)


main()
