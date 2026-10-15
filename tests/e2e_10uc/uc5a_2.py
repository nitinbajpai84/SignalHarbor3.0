"""UC5 Cedarpoint stale-data breach, PRC29 classification question, within-limit rows with no case (P18-P20). Synthetic data only.
Usage: python uc5a_2.py --base URL --creds PATH --out DIR
"""
import argparse, json, re, sys, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

NAME, TITLE = "uc5a_2", "Cedarpoint stale-data breach, PRC29 classification question, within-limit rows with no case (P18-P20)"
ROOT = Path(__file__).resolve().parents[2]
U = json.load(open(ROOT / "docs/test/10uc_universe.json", encoding="utf-8"))
LIM = {x["rule"]: x for x in U["limits_check_30_sep"]}
ASOF = U["meta"]["as_of"]
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
A = ap.parse_args()
OUT = Path(A.out) / NAME; OUT.mkdir(parents=True, exist_ok=True)
BAD = re.compile(r"undefined|\bnull\b|\bNaN\b|\[object|Traceback|Internal Server|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}|\b[0-9a-f]{32}\b|Error:", re.I)
rows, n = [], [0]


def sign_in_of(prefix):  # the password is used to fill the form only; never printed or saved
    for line in open(A.creds, encoding="utf-8"):
        p = line.split()
        if len(p) > 1 and p[0].lower().startswith(prefix):
            return p[0], p[1]
    raise SystemExit(f"no sign-in for {prefix} in the creds file")


def check(page, step, expected, ok, actual="", scope=None):
    n[0] += 1; f = f"{n[0]:02d}-{step}.png"; page.screenshot(path=str(OUT / f), full_page=True)
    bad = BAD.search((scope if scope is not None else page.locator("body")).inner_text())
    ok = bool(ok) and not bad
    rows.append((step, expected, (str(actual) + (f" | raw/error text on screen: {bad.group(0)}" if bad else "")).strip(), ok, f))
    print(("PASS " if ok else "FAIL ") + step)


def login(ctx, prefix):
    page = ctx.new_page(); page.set_default_timeout(20000)
    email, pw = sign_in_of(prefix)
    page.goto(A.base + "/"); page.get_by_label("Email").fill(email); page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_selector("form", state="detached")
    return page


def press(loc):
    try: loc.click(timeout=8000)
    except Exception: loc.dispatch_event("click")


def pct_ok(text, exp):  # the product may show 1 or 2 decimals, rounded or cut
    x = float(exp); c = {f"{x:.2f}", f"{x:.1f}", f"{int(x * 10) / 10:.1f}", f"{x:.0f}"}
    return any(re.search(rf"(?<![\d.]){re.escape(v)}%", text) for v in c)


def limits_card(page):
    return page.locator("li.ds-card").filter(has=page.get_by_role("heading", name="Limits", exact=True))


def run_limits(page):
    page.goto(A.base + "/centre/action/reconciliations")
    page.get_by_role("heading", name="Limits", exact=True).wait_for()
    page.get_by_label("Check as at").fill(ASOF)
    card = limits_card(page)
    press(card.get_by_role("button", name="Run now"))
    card.get_by_text("limits breached").wait_for()
    return card


def open_case(page, title_re):
    page.goto(A.base + "/centre/action/cases")
    row = page.locator("tr").filter(has_text=re.compile(title_re, re.I)).first
    row.wait_for(); press(row.get_by_role("link").first)
    page.get_by_role("heading", name="The limit and the figures checked against it").wait_for()
    return page.locator("section[aria-label='What was compared']")


def journey(ctx):
    cp, le, hf = LIM["limit_manager_entity_b"], LIM["limit_listed_equity_liquid"], LIM["limit_hedge_funds"]
    page = login(ctx, "mei.chen.evergreen@")
    card = run_limits(page); txt = card.inner_text()
    check(page, "limits-run", "Limits card: Cedarpoint Ventures listed with cause 'stale data'",
          re.search(r"Cedarpoint Ventures.*stale data", txt, re.S | re.I), txt[-300:], card)
    c = open_case(page, r"Limit breached.*Cedarpoint Ventures"); t = c.inner_text()
    check(page, "case-figures", f"Case says {cp['exposure_pct']}% against {cp['max_pct']}%, cause stale data, inputs older than 90 days",
          pct_ok(t, cp["exposure_pct"]) and "Cause: stale data" in t and re.search(r"\d+ input value\(s\) are older than 90 days", t), t[:500], c)
    # P20 and P19: only the two breaches become cases; PRC29 and the within-limit rows open nothing
    page.goto(A.base + "/centre/action/cases")
    page.locator("tr").filter(has_text="Limit breached").first.wait_for()  # Wait for table to load
    titles = [r.inner_text() for r in page.locator("tr").filter(has_text="Limit breached").all()]
    ok = len(titles) == 2 and not any(re.search("Pacific Rim|PRC29|Evergreen Funds|hedge|listed", x, re.I) for x in titles)
    check(page, "cases-only-two", "Exactly two limit cases (Harborview, Cedarpoint); none for PRC29, listed equity or hedge funds", ok, f"{len(titles)} limit case(s)")
    page.goto(A.base + "/centre/action/reconciliations"); card = limits_card(page); card.wait_for(); txt = card.inner_text()
    check(page, "prc29-question", "A classification question 'Needs a class' for Pacific Rim Convertible 2029 note (1,122,000 USD, 2.72%) is on screen",
          "Needs a class" in txt and "Pacific Rim Convertible 2029" in txt and pct_ok(txt, "2.72"), txt[:300], card)
    check(page, "within-limit-rows", f"Within-limit figures shown: listed equity {le['exposure_pct']}% (60-90), hedge fund {hf['exposure_pct']}% (20-60)",
          pct_ok(txt, le["exposure_pct"]) and pct_ok(txt, hf["exposure_pct"]), txt[:300], card)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1440, "height": 900})
        try:
            journey(ctx)
        except Exception:
            rows.append(("journey stopped", "the journey runs to the end", traceback.format_exc(limit=2).replace("\n", " ")[-500:], False, "99-stopped.png"))
            for pg in ctx.pages[-1:]: pg.screenshot(path=str(OUT / "99-stopped.png"))
        ok = all(r[3] for r in rows)
        md = [f"# {NAME}: {TITLE}", f"Result: {'PASS' if ok else 'FAIL'}", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        md += [f"| {i} | {s} | {e} | {(a or 'as expected').replace('|', '/')} | {'pass' if k else 'FAIL'} | {f} |" for i, (s, e, a, k, f) in enumerate(rows, 1)]
        (OUT / "result.md").write_text("\n".join(md), encoding="utf-8"); b.close()
    sys.exit(0 if ok else 1)


main()
