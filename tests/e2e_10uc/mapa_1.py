"""Charter 1. Map, Data flow tab: sources to dashboards, click a box for owner and last load (head of data, Anita Rao).
Run: python mapa_1.py --base URL --creds PATH --out DIR
Playwright sync, Chromium, 1440x900. Synthetic data only. The password is read from the creds file and never printed or saved. Exit 1 on a failed step."""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
BAD = re.compile(r"undefined|\bNaN\b|\bnull\b|traceback|exception|\berror\b|\b(?:table|source|files|dash|person):\S|\b(?:bronze|silver|gold)_\w+|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", re.I)
MONTH = re.compile(r"\b\d{1,2} [A-Z][a-z]{2} \d{4}\b")
P = U["project"]


def creds_for(path, who):
    """First line of the creds file whose first word mentions `who` (email  password  ...). Password stays in memory only."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and who in p[0].lower():
            return p[0], p[1]
    sys.exit(f"no login for {who} in the creds file")


class Run:
    def __init__(self, name, out):
        self.dir = Path(out) / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows, self.n, self.name = [], 0, name

    def step(self, page, title, expected, fn, hard=True):
        """Run fn (returns the actual text or raises AssertionError), screenshot, then check the screen for raw ids and error words."""
        self.n += 1
        shot = f"{self.n:02d}-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40]}.png"
        status, actual = "pass", ""
        try:
            actual = fn() or "as expected"
            bad = BAD.findall(page.inner_text("body"))
            if bad:
                status, actual = "fail", f"raw id or error text on screen: {sorted(set(map(str, bad)))[:5]}"
        except Exception as e:  # noqa: BLE001 - a failed step is a finding, not a crash
            status, actual = ("fail" if hard else "note"), f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
        try:
            page.screenshot(path=str(self.dir / shot), full_page=True)
        except Exception:  # noqa: BLE001
            shot = "(no screenshot)"
        self.rows.append((self.n, title, expected, actual, status, shot))
        print(f"{status.upper():5} {self.n:02d} {title}: {actual[:140]}")

    def finish(self):
        L = [f"# {self.name}", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        L += [f"| {n} | {t} | {e} | {a.replace('|', '/')} | {s} | {sh} |" for n, t, e, a, s, sh in self.rows]
        (self.dir / "result.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        sys.exit(1 if any(r[4] == "fail" for r in self.rows) else 0)


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def login(page, base, creds, who):
    email, pw = creds_for(creds, who)
    page.goto(base + "/", wait_until="domcontentloaded")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.get_by_label("Email").wait_for(state="detached", timeout=30000)
    try:  # Today polls while it loads, so networkidle may never come (cycle 2: login step timed out here)
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001
        pass
    return page.url


def open_map(page, base, q=""):
    page.goto(f"{base}/centre/map{q}", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Map", exact=True).first.wait_for()
    page.wait_for_load_state("networkidle")


def aside(page):
    return page.get_by_role("complementary", name="About this box")


HINT = "Choose a box to see who owns it"  # FlowTab.tsx side-panel hint (the script said "Click a box", which the Map never wrote)


def chosen(page):
    """Boxes marked chosen: only the flow boxes (inside a stage section), not the tab chips, which also carry aria-pressed."""
    return page.locator("section[aria-label] > button[aria-pressed='true']")


def panel(page, label):
    """The side panel once it shows the box just clicked (it renders after the click; reading at once read the old panel)."""
    aside(page).get_by_role("heading", name=re.compile(label, re.I)).first.wait_for()  # label may be "A|B" (feed box names changed)
    return aside(page).inner_text()


def body(page, run, a):
    base = a.base.rstrip("/")
    run.step(page, "Sign in as head of data", "login accepted, a start page opens", lambda: login(page, base, a.creds, "anita.rao"))

    def landing():
        open_map(page, base)
        need(page.get_by_text("How your data, your work and your numbers connect").is_visible(), "Map subline missing")
        want = ["Data flow", "Process maps", "Definitions", "Conversations", "Health"]  # MapPage.tsx TABS; Health is the data team's
        tabs = [t for t in want if page.get_by_role("button", name=t, exact=True).count()]
        need(tabs == want, f"tabs seen: {tabs}")
        return f"Map opens on Data flow with {len(tabs)} tabs"
    run.step(page, "Open the Map", "heading Map, four tabs, Data flow first", landing)

    def columns():
        got = [s for s in ("Sources", "Files", "Raw data", "Company model", "Ready for reports", "Dashboards", "People") if page.get_by_role("region", name=s, exact=True).count()]
        need({"Sources", "Files", "Raw data", "Ready for reports", "Dashboards", "People"} <= set(got), f"columns: {got}")
        return f"columns left to right: {got}"
    run.step(page, "Columns from sources to people", "one column per stage, Sources to People", columns)

    def sources():
        reg = page.get_by_role("region", name="Sources", exact=True)
        miss = [n for n in ("Fund administrator", "Trading system export", "Manager statements by email", "Market data file")
                if not reg.get_by_role("button", name=re.compile(n)).count()]
        need(not miss, f"source boxes missing: {miss}")
        return "4 sources in the seeded office"
    run.step(page, "The four sources", "administrator, trading export, manager email, market data", sources)

    run.step(page, "Side panel before a click", "hint to click a box",
             lambda: need(page.get_by_text(HINT).is_visible(), "no hint in the side panel"))

    def click_source():
        page.get_by_role("region", name="Sources", exact=True).get_by_role("button", name=re.compile("Fund administrator")).click()
        t = panel(page, "Fund administrator")
        need("Mei Chen" in t, "owner Mei Chen not shown")
        need("Last load" in t and "Fed by" in t and "Feeds" in t, "panel sections missing")
        need(aside(page).get_by_role("button", name=re.compile("Administrator positions|Files from Fund administrator")).count(), "feeds list lacks the administrator feed box")
        return "owner Mei Chen; feeds the administrator box (Files box absent in this seed)"
    run.step(page, "Click Fund administrator", "owner Mei Chen, Fed by, Feeds, last load line", click_source)

    def follow_to_files():
        aside(page).get_by_role("button", name=re.compile("Administrator positions|Files from Fund administrator")).first.click()
        t = panel(page, "Administrator positions|Files from Fund administrator")
        need("Mei Chen" in t, "owner missing")
        need(MONTH.search(t), f"no last-load date in the panel: {t[:160]!r}")
        return "last load " + MONTH.search(t).group(0)
    run.step(page, "Follow to the files box", "owner and a last-load date", follow_to_files)

    def one_marked():
        n = chosen(page).count()
        need(n == 1, f"{n} boxes marked chosen")
        need("focus=" in page.url, "chosen box not kept in the address")
    run.step(page, "One box marked, kept in the address", "exactly one chosen box; focus in the link", one_marked)

    def gold():
        reg = page.get_by_role("region", name="Ready for reports", exact=True)
        for g in P["gold"]:
            label = g.removeprefix("gold_").replace("_", " ")
            need(reg.get_by_role("button", name=re.compile(label, re.I)).count(), f"ready-for-reports box for '{label}' missing")
        reg.get_by_role("button", name=re.compile("investment report holdings monthly", re.I)).click()
        t = panel(page, "Investment report holdings monthly")
        need("Live" in t, "status Live not shown (the project is live)")
        need("Not named yet" not in t.split("Last load")[0], "owner not named on the ready-for-reports table")
        return t.replace("\n", " ")[:140]
    run.step(page, "Ready-for-reports table of the live project", "both gold tables as plain names; Live; owner named (P33)", gold)

    def raw():
        reg = page.get_by_role("region", name="Raw data", exact=True)
        for b_ in P["bronze"]:
            label = b_.removeprefix("bronze_").replace("_", " ")
            need(reg.get_by_role("button", name=re.compile(label, re.I)).count(), f"raw-data box for '{label}' missing")
    run.step(page, "Raw data boxes", "administrator and trading export positions (P33)", raw)

    def dash_people():
        box = page.get_by_role("region", name="Ready for reports", exact=True).get_by_role("button", name=re.compile("holdings monthly", re.I))
        if box.get_attribute("aria-pressed") != "true":  # a second click on the chosen box clears it
            box.click()
        need("Feeds" in panel(page, "holdings monthly"), "no Feeds list")
        dash = page.get_by_role("region", name="Dashboards", exact=True).get_by_role("button")
        need(dash.count() >= 1, "no dashboard box")
        name = dash.first.inner_text().splitlines()[0]
        dash.first.click()
        panel(page, name)
        ppl = page.get_by_role("region", name="People", exact=True)
        miss = [n for n in ("Daniel Foo", "Raj Patel") if not ppl.get_by_role("button", name=n).count()]
        need(not miss, f"dashboard audience missing from People: {miss}")
        t = aside(page).inner_text()
        need("Daniel Foo" in t and "Raj Patel" in t, "dashboard panel does not list its audience")
        return "dashboard feeds Daniel Foo and Raj Patel"
    run.step(page, "Dashboard and who it is shared with", "dashboard box feeds Daniel Foo and Raj Patel (P33)", dash_people)

    def unpick():
        src = page.get_by_role("region", name="Sources", exact=True).get_by_role("button", name=re.compile("Fund administrator"))
        if src.get_attribute("aria-pressed") != "true":
            src.click(); panel(page, "Fund administrator")
        src.click()
        try:
            page.get_by_text(HINT).wait_for(timeout=5000)
        except Exception:  # noqa: BLE001
            raise AssertionError("panel did not clear")
    run.step(page, "Click the chosen box again", "panel clears", unpick)

    def deep():
        open_map(page, base, "?tab=flow&focus=source%3Aadministrator")
        panel(page, "Fund administrator")
    run.step(page, "Link with a box named opens it focused", "Fund administrator panel open", deep)

    def unknown_focus():
        open_map(page, base, "?tab=flow&focus=nope")
        need(page.get_by_text(HINT).is_visible(), "unknown focus should show the hint, not break")
    run.step(page, "Link with an unknown box", "hint, no error", unknown_focus)

    run.step(page, "Read-only reminder", "subline says everything is read from records",
             lambda: need(page.get_by_text("Everything here is read from your records").is_visible(), "subline gone"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Run("mapa_1", a.out)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.set_default_timeout(15000)
        try:
            body(page, run, a)
        finally:
            b.close()
    run.finish()


if __name__ == "__main__":
    main()
