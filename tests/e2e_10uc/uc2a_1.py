"""UC2 analyst, charter 1: Action > Reconciliations. Cash check shows the Entity B break of 12,400 and the tolerance in words (P08).
Run: python uc2a_1.py --base URL --creds PATH --out DIR   (synthetic data only; passwords are read, never printed or saved)."""
import argparse, json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

N = 1
ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
EB = next(r for r in U["cash_8_oct"] if r["legal_entity"] == "EG-B")
TR = next(r for r in U["cash_8_oct"] if r["legal_entity"] == "EG-TRUST")
ENT = {e["entity_code"]: e["entity_name"] for e in U["legal_entities"]}
TOL = next(r for r in U["rules"] if r["rule_code"] == "cash_tolerance")["parameters"]
ANALYST = next(p for p in U["people"] if p["platform_role"] == "analyst" and p["name"] == "Mei Chen")
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
        L = [f"# UC2 analyst {N}: cash check shows the Entity B break", "", f"Result: **{'FAIL' if s.fail else 'PASS'}**", "",
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
    with sync_playwright() as pw:
        b = pw.chromium.launch(); page = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); page.set_default_timeout(20000)
        login(page, base, ANALYST["email"], creds(a.creds, ANALYST["email"]))
        page.goto(base + "/centre/action/reconciliations")
        card = lambda: page.locator("li.ds-card").filter(has=page.get_by_role("heading", name="Cash by entity"))

        def s1():
            expect(page.get_by_role("heading", name="Action", exact=True).first).to_be_visible()
            expect(page.get_by_role("link", name="Reconciliations")).to_be_visible()
            expect(card()).to_be_visible()
            expect(card().get_by_role("button", name="Run now")).to_be_visible()
        r.step(page, "reconciliations-page", "Action > Reconciliations lists Cash by entity with a Run now button for the analyst", s1)

        def s2():
            page.get_by_label("Check as at").fill(DAY)
            expect(page.get_by_label("Check as at")).to_have_value(DAY)
        r.step(page, "set-date", f"Check as at {DAY}", s2)

        def s3():
            card().get_by_role("button", name="Run now").click()
            expect(card()).to_contain_text(re.compile(r"as at\s+\d{1,2}\s+\w+\s+\d{4}"))
            expect(page.get_by_role("alert")).to_have_count(0)
            return card().inner_text().replace("\n", " ")[:200]
        r.step(page, "run-cash-check", "Run now finishes; the card says the run is as at 2026-10-08, no error", s3)

        def s4():
            expect(card().get_by_text(re.compile(r"\b1\s+\w+.*to look at"))).to_be_visible()
            expect(card()).to_contain_text(f"{len(U['cash_8_oct'])} compared")
        r.step(page, "one-break", "One break open, three entities compared (Holdings, Trust, Entity B)", s4)

        def s5():
            words = f"{n(TOL['abs_amount'])} {TOL['currency']}"
            expect(card()).to_contain_text(re.compile(rf"up to {re.escape(words)}", re.I))
            expect(card().get_by_text(re.compile(r"signed rule \S+"))).to_have_count(0)  # words, not a rule id
        r.step(page, "tolerance-in-words", f"Tolerance written in words: differences up to {n(TOL['abs_amount'])} {TOL['currency']} are accepted", s5)

        def s6():
            # the card now lists every entity compared (a2.2); an entity inside the tolerance must not be called over the allowance
            lines = [ln for ln in card().inner_text().splitlines() if ENT["EG-HOLD"] in ln or ENT["EG-TRUST"] in ln]
            assert lines and not [ln for ln in lines if re.search(r"over the allowance|open the case", ln, re.I)], f"a break is shown for an entity inside tolerance: {lines}"
            wis = card().get_by_role("button", name="Where is this from?")
            if wis.count() == 0: return "Where is this from? button not found (expected to be visible)"
        r.step(page, "only-entity-b", "No break line for Holdings or the Trust (inside the tolerance); a Where is this from? button for the case", s6)

        def s7():
            page.goto(base + "/centre/action/cases")
            row = page.get_by_role("row").filter(has_text=TITLE)
            expect(row).to_have_count(1)
            expect(row).to_contain_text(f"USD {n(EB['difference'])}")
            assert page.get_by_role("row").filter(has_text=ENT["EG-TRUST"]).filter(has_text="Cash differs").count() == 0, "a case exists for the Trust"
        r.step(page, "case-in-cases", f"Cases lists exactly one 'Cash differs' case for Entity B, size USD {n(EB['difference'])}; none for the Trust", s7)

        def s8():
            page.get_by_role("row").filter(has_text=TITLE).get_by_role("link").first.click()
            expect(page.get_by_text(re.compile(r"What Tally found", re.I))).to_be_visible(timeout=60000)  # wait for agent to finish
            main_text = page.inner_text("main")
            assert n(EB["administrator"]) in main_text, f"administrator amount {n(EB['administrator'])} not found"
            assert n(EB["trading_export"]) in main_text, f"trading export amount {n(EB['trading_export'])} not found"
            assert n(EB["difference"]) in main_text, f"difference amount {n(EB['difference'])} not found"
            assert f"USD {n(EB['difference'])}" in main_text, f"USD {n(EB['difference'])} not found in page"
        r.step(page, "case-figures", f"Case shows administrator {n(EB['administrator'])}, trading export {n(EB['trading_export'])}, difference {n(EB['difference'])} USD", s8)
        b.close()
    r.write(); sys.exit(1 if r.fail else 0)


main()
