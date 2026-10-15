"""Access charter 2: at phone width (390px) Today, the case page and the Office view are usable with no sideways scroll.
Usage: python access_2.py --base URL --creds PATH --out DIR   (Playwright sync, Chromium, 390x844)"""
import argparse, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

N = "access_2"
ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b(?:intent|proj|usr|user)[-_][0-9a-f]{6,}", re.I)
W = 390


def email_of(name):
    return next(p["email"] for p in U["people"] if p["name"] == name)


def password_for(creds, email):
    for ln in pathlib.Path(creds).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if p and not ln.startswith("#") and p[0].lower() == email.lower():
            return p[1]
    raise SystemExit("no credentials in the creds file for " + email.split(".")[0])


def flat(s):
    return s.replace(",", "")


def fig(x):  # a universe figure as digits only, e.g. 10180000
    return str(int(round(float(str(x).replace(",", "")))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out) / N; out.mkdir(parents=True, exist_ok=True)
    rows, n, cur = [], [0], [None]

    # figures come from the universe file, never typed here
    stm = {(s["fund"], s["period_end"], s["kind"]): s for s in U["statements"]}
    amended_a = stm[("A", "2026-09-30", "amended")]["value"]
    estimate_a = stm[("A", "2026-09-30", "estimate")]["value"]
    sgd_total = None
    for p in U["planted"]:
        if p["id"] == "P16":
            m = re.search(r"= ([\d,]+\.\d\d) SGD", p["expected"])
            sgd_total = m.group(1) if m else None
        if p["id"] == "P08":
            m = re.search(r"over the ([\d,]+) tolerance", p["expected"]); tol = m.group(1) if m else None
            m = re.search(r"([\d,]+) USD over", p["expected"]); break_amt = m.group(1) if m else None

    with sync_playwright() as pw:
        br = pw.chromium.launch()

        def new_page():
            pg = br.new_context(viewport={"width": W, "height": 844}).new_page()
            pg.set_default_timeout(20000)
            cur[0] = pg
            return pg

        def overflow():
            """(document wider than the phone?, wide things inside it)"""
            return cur[0].evaluate("""(w) => {
              const de = document.documentElement;
              const wide = [];
              for (const el of document.body.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.width && r.right > w + 1 && getComputedStyle(el).position !== 'fixed') {
                  const t = (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30);
                  wide.push(el.tagName.toLowerCase() + ' "' + t + '" right=' + Math.round(r.right));
                }
              }
              return [Math.max(de.scrollWidth, document.body.scrollWidth) > w + 1, wide.slice(0, 4)];
            }""", W)

        def step(name, expected, check, scroll=True, ids=True):
            n[0] += 1
            shot = f"{n[0]:02d}-{name}.png"
            pg = cur[0]
            try:
                actual = check() or "as expected"; ok = True
            except Exception as e:  # noqa: BLE001
                actual = f"{type(e).__name__}: {str(e)[:300]}"; ok = False
            pg = cur[0]  # the login step makes the page inside check()
            try:
                wide_doc, wide = overflow()
                if wide_doc and scroll and ok:
                    ok, actual = False, "the page scrolls sideways at 390px; too wide: " + "; ".join(wide)
                elif wide_doc and not scroll:
                    actual += " (note: sideways scroll here, not part of this charter)"
                pg.screenshot(path=str(out / shot), full_page=True)
                body = pg.inner_text("body")
                m = BAD.search(body)
                if ok and m and ids:
                    ok, actual = False, f"raw id or error text on screen: {m.group(0)}"
            except Exception as e:  # noqa: BLE001
                ok, actual = False, f"screenshot failed: {e}"
            rows.append((name, expected, actual, ok, shot))

        def login(name):
            pg = new_page(); email = email_of(name)
            pg.goto(a.base + "/login")
            pg.get_by_label("Email").fill(email)
            pg.get_by_label("Password").fill(password_for(a.creds, email))
            pg.evaluate("document.querySelector('form').requestSubmit()")
            pg.wait_for_url(lambda u: "/login" not in u)
            pg.wait_for_load_state("networkidle")

        def settle():
            cur[0].wait_for_load_state("networkidle")
            cur[0].wait_for_timeout(500)

        # ---- the CIO on the phone: Today and the Office view
        step_login = lambda: login("Daniel Foo")
        step("login", "the CIO signs in on a 390px screen and reaches the start page", step_login)

        def today():
            pg = cur[0]
            pg.goto(a.base + "/centre/action"); settle()
            pg.get_by_role("heading", name="Action", exact=True).first.wait_for(state="visible")  # Today is a tab of Action, not a heading
            pg.locator("a[aria-current='page']", has_text="Today").wait_for(state="visible")
            pg.get_by_role("button", name="Needs me").wait_for(state="visible")
            pg.get_by_role("button", name="Worth a look").wait_for(state="visible")
            return "Action heading, the Today tab, Needs me and Worth a look filters fit the screen"
        step("today", "Today shows its heading and both filters inside 390px", today)

        def today_cards():
            pg = cur[0]
            seen = []
            for f in ("Needs me", "Worth a look"):
                pg.get_by_role("button", name=f).click(); settle()
                seen.append(pg.get_by_role("listitem").count())
            pg.get_by_role("button", name="Needs me").click(); settle()
            cards = pg.locator("li.ds-card")
            if cards.count():
                cards.first.get_by_role("button", name="Not for me").wait_for(state="visible")
            body = pg.inner_text("body")
            assert re.search(r"Revised|Nothing needs you|Official|Stale|Unverified|Estimated", body, re.I), "no card and no empty line on Today"
            return f"cards per filter: {seen}; first card's Not for me button is on screen"
        step("today-cards", "the Today cards (status word, headline, buttons) stay inside 390px in both filters", today_cards)

        def revised():
            pg = cur[0]
            for f in ("Needs me", "Worth a look"):
                pg.get_by_role("button", name=f).click(); settle()
                if pg.get_by_text(re.compile(r"^Revised", re.I)).count():
                    return f"a Revised card (Fund A amended, P02) is under '{f}'"
            raise AssertionError("no card with the status word Revised (P02: Fund A amended statement, +180,000)")
        step("today-revised", "a card with the status word Revised is on Today (P02)", revised)

        def burger():
            pg = cur[0]
            pg.get_by_role("button", name="Centres").click()
            menu = pg.locator(".cs-menu")
            for w in ("Action", "Consume"):
                menu.get_by_role("link", name=w, exact=True).wait_for(state="visible")
            menu.get_by_role("link", name="Consume", exact=True).click(); settle()
            assert "/centre/consume" in pg.url, pg.url
            return "the Centres menu opens, Consume opens from it"
        step("menu-to-consume", "the Centres menu (burger) opens on the phone and leads to Consume", burger)

        def office():
            pg = cur[0]
            pg.goto(a.base + "/centre/consume/office"); settle()
            pg.get_by_role("heading", name="Office view").wait_for(state="visible")
            for t in ("Holdings", "Issued versus known now", "Investment total against administrator NAV", "Liquidity"):
                pg.get_by_role("region", name=t).wait_for(state="visible")
            pg.get_by_role("group", name="Currency").get_by_role("button", name="SGD").wait_for(state="visible")
            return "Office view heading, USD/SGD switch and its four sections are on screen"
        step("office", "Office view shows Holdings, Issued versus known now, NAV bridge and Liquidity inside 390px", office)

        def issued():
            pg = cur[0]
            sec = pg.get_by_role("region", name="Issued versus known now")
            sec.scroll_into_view_if_needed()
            txt = flat(sec.inner_text())
            for label, v in (("issued Fund A estimate", estimate_a), ("known now Fund A amended", amended_a)):
                assert fig(v) in txt, f"{label} {fig(v)} is not in the section"
            assert re.search("Revised", txt, re.I), "status word Revised missing from the Issued section"
            return f"{fig(estimate_a)} and {fig(amended_a)} (P01/P02) are readable; the word Revised is shown"
        step("office-issued", "Issued versus known now carries Fund A's 10,000,000 issued and 10,180,000 known now, status Revised (P01, P02)", issued)

        def sgd():
            pg = cur[0]
            pg.get_by_role("group", name="Currency").get_by_role("button", name="SGD").click(); settle()
            sec = pg.get_by_role("region", name="Issued versus known now")
            want = flat(sgd_total).split(".")[0]
            try:  # the section re-renders after the switch: wait for the figure rather than read it once
                sec.get_by_text(re.compile(",?".join(want))).first.wait_for(state="visible", timeout=10000)
            except Exception:  # noqa: BLE001
                raise AssertionError(f"SGD total {sgd_total} (P16) is not in the section: {flat(sec.inner_text())[:200]}")
            return f"SGD total {sgd_total} is shown after the switch"
        step("office-sgd", "switching to SGD shows the SGD total (P16)", sgd)

        # ---- an analyst on the phone: a case
        login("Mei Chen")

        def find_case():
            pg = cur[0]
            pg.goto(a.base + "/centre/action/cases"); settle()
            pg.get_by_role("columnheader").first.wait_for(state="visible")  # Cases tab content
            row = pg.get_by_role("row").filter(has_text=re.compile(rf"(?<![\d,.]){break_amt.replace(',', ',?')}(?![\d,])")).first if break_amt else pg.get_by_role("row").nth(1)
            row.wait_for(state="visible")
            return f"the cash break case ({break_amt} USD over the {tol} tolerance, P08) is in the list"
        step("cases-list", "the Cases list shows the Entity B cash break of 12,400 (P08)", find_case, scroll=False)

        def case_page():
            pg = cur[0]
            row = pg.get_by_role("row").filter(has_text=re.compile(rf"(?<![\d,.]){break_amt.replace(',', ',?')}(?![\d,])")).first
            row.get_by_role("link").first.click(); settle()
            h1 = pg.get_by_role("heading", level=1).filter(has_text=re.compile(r"CASE-\d+")).first  # the Action frame's h1 comes first
            h1.wait_for(state="visible")
            assert fig(break_amt) in flat(h1.inner_text()), f"case heading does not carry {break_amt}: {h1.inner_text()[:80]}"
            pg.get_by_role("region", name="History").wait_for(state="visible")
            pg.get_by_role("region", name="What was compared").wait_for(state="visible")
            return "case heading with the amount, the history and what was compared all fit the screen"
        step("case-page", "the case page shows its heading with 12,400, the History and 'What was compared' inside 390px", case_page)

        def case_buttons():
            pg = cur[0]
            btns = pg.get_by_role("main").get_by_role("button")
            n_btn = btns.count()
            assert n_btn > 0, "no action button on the case page"
            for i in range(n_btn):
                b = btns.nth(i).bounding_box()
                if b and btns.nth(i).is_visible():
                    assert b["x"] >= -1 and b["x"] + b["width"] <= W + 1, f"button '{btns.nth(i).inner_text()[:20]}' leaves the screen"
            return f"{n_btn} buttons, all inside the screen width"
        step("case-buttons", "every button on the case page is reachable without sideways scroll", case_buttons)
        br.close()

    fails = [r for r in rows if not r[3]]
    md = [f"# {N}: phone width 390px, Today, case page, Office view", "", f"Result: {'FAIL' if fails else 'PASS'}", "",
          "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
    for i, (s, e, ac, ok, sh) in enumerate(rows, 1):
        md.append(f"| {i} | {s} | {e} | {ac.replace('|', '/')} | {'pass' if ok else 'FAIL'} | {sh} |")
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:3])); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
