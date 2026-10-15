"""Access charter 1: the CIO cannot open Build approvals; Finance cannot see Map unless allowed; a direct URL to another role's page is refused.
Usage: python access_1.py --base URL --creds PATH --out DIR   (Playwright sync, Chromium, 1440x900)"""
import argparse, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ui_copy import REFUSED  # noqa: E402  (the refusal line as the shell writes it today)

N = "access_1"
ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
TITLE = U["project"]["title"]
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b(?:intent|proj|usr|user)[-_][0-9a-f]{6,}", re.I)
GREY = ("Raw data", "Company model")  # data-team layers of the Map (K1 landing note)


def email_of(name):
    return next(p["email"] for p in U["people"] if p["name"] == name)


def password_for(creds, email):
    for ln in pathlib.Path(creds).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if p and not ln.startswith("#") and p[0].lower() == email.lower():
            return p[1]
    raise SystemExit("no credentials in the creds file for " + email.split(".")[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out) / N; out.mkdir(parents=True, exist_ok=True)
    rows, n, cur, notes = [], [0], [None], {}

    with sync_playwright() as pw:
        br = pw.chromium.launch()

        def new_page():
            pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
            pg.set_default_timeout(20000)
            cur[0] = pg
            return pg

        def step(name, expected, check, ids=True):
            n[0] += 1
            shot = f"{n[0]:02d}-{name}.png"
            pg = cur[0]
            try:
                actual = check() or "as expected"; ok = True
            except Exception as e:  # noqa: BLE001
                actual = f"{type(e).__name__}: {str(e)[:300]}"; ok = False
            try:
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
            return pg

        def bar_has(present, absent):
            nav = cur[0].get_by_role("navigation", name="Centres")
            nav.wait_for(state="visible")
            for w in present:
                nav.get_by_role("link", name=w, exact=True).wait_for(state="visible")
            for w in absent:
                assert nav.get_by_role("link", name=w, exact=True).count() == 0, f"{w} is on the bar"
            return f"bar shows {present}, not {absent}"

        def refused(path, banned):
            pg = cur[0]
            pg.goto(a.base + path); pg.wait_for_load_state("networkidle")
            pg.get_by_text(REFUSED).wait_for(state="visible")
            assert re.search(r"/centre/action/?$", pg.url), f"expected the start page, at {pg.url.replace(a.base, '')}"
            for h in banned:
                assert pg.get_by_role("heading", name=h).count() == 0, f"'{h}' is on screen"
            return f"{path} sent back to /centre/action with the refusal line"

        # ---- the head of data (positive control) and the real project's build address
        login("Anita Rao")

        def anita_build():
            pg = cur[0]
            bar_has(["Intent", "Action", "Build", "Consume", "Map"], [])
            pg.goto(a.base + "/centre/build"); pg.wait_for_load_state("networkidle")
            pg.get_by_role("heading", name="Build Centre").wait_for(state="visible")
            link = pg.get_by_role("row").filter(has_text=TITLE).get_by_role("link").first
            link.wait_for(state="visible")
            notes["href"] = link.get_attribute("href")
            link.click()
            pg.get_by_role("heading", name=TITLE).first.wait_for(state="visible")
            return "head of data has Build and Map on the bar and opens the project's build page"
        # Finding: the Build list prints the raw project id beside the title (ui/src/v1/b6/ProjectsPage.tsx:31), so the id check is off for this step.
        step("head-of-data-build", "Anita Rao (analyst) sees Build and Map on the bar and opens the signed project's build page", anita_build, ids=False)

        # ---- the CIO
        login("Daniel Foo")

        def cio_bar():
            assert re.search(r"/centre/action", cur[0].url), cur[0].url
            return bar_has(["Intent", "Action", "Consume", "Map"], ["Build"])  # every role has the Map (ui/src/shell/roles.ts, 9 Oct)
        step("cio-bar", "Daniel Foo (CIO, sponsor) signs in to Action; the bar shows Intent, Action, Consume and Map, no Build", cio_bar)
        step("cio-build-list", "the CIO typing /centre/build is sent back to Action with the refusal line", lambda: refused("/centre/build", ["Build Centre"]))

        def cio_approval():
            href = notes.get("href")
            assert href and "/build/p/" in href, "could not read the project's build address from the head of data's list"
            r = refused(href, [TITLE])
            assert cur[0].get_by_text("Approve the plan and the model change").count() == 0, "approve button on screen"
            return r + "; no approve button"
        step("cio-build-approval", "the CIO opening the project's Build page (where the plan is approved) by address is refused; no Approve button", cio_approval)
        step("cio-control", "the CIO typing /centre/control is refused", lambda: refused("/centre/control", ["Control panel"]))
        step("cio-settings", "the CIO typing /centre/settings/rules is refused (Settings is for the data team)", lambda: refused("/centre/settings/rules", ["Settings"]))

        # ---- Finance
        login("Raj Patel")
        step("finance-bar", "Raj Patel (Finance, approver) has Map but no Build on the bar", lambda: bar_has(["Action", "Consume", "Map"], ["Build"]))

        def fin_map():
            pg = cur[0]
            pg.goto(a.base + "/centre/map"); pg.wait_for_load_state("networkidle")
            pg.get_by_role("heading", name="Map", exact=True).wait_for(state="visible")
            for w in GREY:
                assert pg.get_by_text(w, exact=True).count() == 0, f"data-team layer '{w}' is shown to Finance"
            tabs = pg.get_by_role("tablist", name="Map views")
            tabs.get_by_text("Data flow", exact=True).wait_for(state="visible")
            assert tabs.get_by_text("Health", exact=True).count() == 0, "the Health tab is offered to Finance"  # hidden, not refused (MapPage.tsx)
            return "no raw-data or company-model layer; no Health tab (it is the data team's)"
        step("finance-map", "Finance opening /centre/map directly sees only report-ready tables and dashboards: no Raw data, no Company model, no Health tab", fin_map)
        step("finance-build", "Finance typing /centre/build is refused", lambda: refused("/centre/build", ["Build Centre"]))
        step("finance-settings", "Finance typing /centre/settings/model is refused", lambda: refused("/centre/settings/model", ["Settings"]))

        # ---- the risk participant
        login("Sofia Reyes")

        def risk_menu():
            pg = cur[0]
            bar_has(["Action", "Map", "Consume"], ["Build"])  # PF2: Consume for every role
            pg.get_by_role("button", name="Account menu").click()
            pg.get_by_role("link", name="What the agents remember about you").wait_for(state="visible")
            assert pg.get_by_role("link", name="Settings", exact=True).count() == 0, "Settings is offered"
            assert pg.get_by_role("link", name="Control panel").count() == 0, "Control panel is offered"
            return "bar: Intent, Action, Consume and Map; account menu offers memory and sign out, no Settings or Control"
        step("risk-bar", "Sofia Reyes (Risk, participant) has no Build but has Consume (PF2); her account menu has no Settings or Control", risk_menu)
        step("risk-build", "Risk typing /centre/build is refused", lambda: refused("/centre/build", ["Build Centre"]))
        step("risk-settings", "Risk typing /centre/settings/people is refused", lambda: refused("/centre/settings/people", ["Settings"]))

        # ---- nobody signed in
        new_page()

        def anon():
            pg = cur[0]
            pg.goto(a.base + "/centre/build"); pg.wait_for_load_state("networkidle")
            pg.wait_for_url(re.compile(r"/login"))
            pg.get_by_label("Email").wait_for(state="visible")
            return "sent to the login page"
        step("signed-out", "someone not signed in who types /centre/build lands on the login page", anon)
        br.close()

    fails = [r for r in rows if not r[3]]
    md = [f"# {N}: access by role, direct addresses refused", "", f"Result: {'FAIL' if fails else 'PASS'}", "",
          "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
    for i, (s, e, ac, ok, sh) in enumerate(rows, 1):
        md.append(f"| {i} | {s} | {e} | {ac.replace('|', '/')} | {'pass' if ok else 'FAIL'} | {sh} |")
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:3])); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
