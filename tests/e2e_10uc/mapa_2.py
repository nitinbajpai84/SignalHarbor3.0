"""Charter 2. Map: Process maps, Definitions and Health tabs; "Open in the map" from a trail panel (head of data, Anita Rao).
Run: python mapa_2.py --base URL --creds PATH --out DIR
Playwright sync, Chromium, 1440x900. Synthetic data only. The password is read from the creds file and never printed or saved. Exit 1 on a failed step."""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
BAD = re.compile(r"undefined|\bNaN\b|\bnull\b|traceback|exception|\berror\b|\b(?:table|source|files|dash|person):\S|\b(?:bronze|silver|gold)_\w+|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", re.I)
MONTH = re.compile(r"\b\d{1,2} [A-Z][a-z]{2} \d{4}\b")
PR = U["process"]
TITLE = U["project"]["title"]


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
    page.get_by_label("Email").wait_for(state="detached", timeout=20000)
    page.wait_for_load_state("networkidle")
    return page.url


def loaded(page):
    """A tab fetches after it mounts: wait until its 'Loading...' line is gone (cycle 1 read the tab while it still said Loading)."""
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)  # the tab's fetch starts after it mounts
    page.wait_for_function("() => !/Loading/.test(document.body.innerText)", timeout=20000)


def open_map(page, base, q=""):
    page.goto(f"{base}/centre/map{q}", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Map", exact=True).first.wait_for()
    loaded(page)


def tab(page, name):
    page.get_by_role("button", name=name, exact=True).click()
    loaded(page)


def body(page, run, a):
    base = a.base.rstrip("/")
    run.step(page, "Sign in as head of data", "login accepted", lambda: login(page, base, a.creds, "anita.rao"))

    def procs():
        open_map(page, base)
        tab(page, "Process maps")
        try:
            page.get_by_role("tablist", name="Signed processes").get_by_role("button", name=TITLE).wait_for(timeout=10000)
        except Exception:  # noqa: BLE001
            raise AssertionError("signed process chip missing")
        t = page.inner_text("body")
        need("Signed" in t and MONTH.search(t), "owner/signed line missing")
        need(page.get_by_role("group", name="Process map").is_visible(), "swim lane not drawn")
        steps = PR["steps"]
        miss = [s["name"] for s in steps if not page.get_by_role("button", name=f"Step {s['n']}: {s['name']}").count()]
        need(not miss, f"steps missing: {miss}")
        manual = sum(1 for s in steps if s["manual"])
        shown = page.get_by_text("Manual", exact=True).count()
        need(shown == manual, f"{shown} Manual flags, expected {manual} (P32)")
        return f"{len(steps)} steps, {shown} manual"
    run.step(page, "Process maps tab", "signed process, 6 steps, 4 marked Manual (P32)", procs)

    def lanes():
        t = page.get_by_role("group", name="Process map").inner_text()
        miss = [w for w in {s["who"] for s in PR["steps"]} if w not in t]
        need(not miss, f"step owners not on the lanes: {miss}")
    run.step(page, "Who does each step", "step owners visible on the swim lane", lanes, hard=False)

    def pick_step():
        s2 = PR["steps"][1]
        page.get_by_role("button", name=f"Step 2: {s2['name']}").click()
        t = page.inner_text("body")
        need(s2["control"][:30] in t or s2["exception"][:30] in t, "no control or exception shown after clicking a step (the Map passes only selected/onSelect to the swim lane)")
    run.step(page, "Click step 2", "control and exception of the step shown", pick_step, hard=False)

    def defs():
        tab(page, "Definitions")
        try:
            page.locator("section.ds-card h2").first.wait_for(timeout=10000)
        except Exception:  # noqa: BLE001 - counted below
            pass
        n = page.locator("section.ds-card h2").count()
        need(n >= 1, "no concept shown")
        t = page.inner_text("body")
        need(TITLE in t, "owning project not named")
        need("Owner" in t and "Version" in t and MONTH.search(t), "owner, version and signed date missing")
        need("No wording yet" not in t, "a definition has no wording")
        return "concepts: " + ", ".join(page.locator("section.ds-card h2").all_inner_texts())[:200]
    run.step(page, "Definitions tab", "concepts with team, project, owner, version, signed date", defs)

    def kpis():
        t = page.inner_text("body")
        miss = [k for k in ("Net worth", "Cash", "Holdings") if k not in t]
        need(not miss, f"names not found in definitions: {miss} (tiles K01-K03 of P33)")
    run.step(page, "Definitions of the three tiles", "Net worth, Cash and Holdings named (P33)", kpis, hard=False)

    def health():
        tab(page, "Health")
        try:
            page.get_by_role("columnheader").first.wait_for(timeout=10000)
        except Exception:  # noqa: BLE001 - reported below
            pass
        for h in ("Source", "Arrival", "Last received", "Files turned away", "Values older than 90 days", "Values not yet verified", "Open breaks"):
            need(page.get_by_role("columnheader", name=h).count(), f"column {h} missing")
        t = page.inner_text("table")
        miss = [n for n in ("Fund administrator", "Trading system export", "Manager statements by email", "Market data file") if n not in t]
        need(not miss, f"sources missing: {miss}")
        need("Owner Mei Chen" in t, "source owner Mei Chen missing")
        return t.replace("\n", " ")[:300]
    run.step(page, "Health tab", "7 columns, four sources, owner Mei Chen", health)

    def health_words():
        t = page.inner_text("table")
        need(re.search(r"On time|Late by|Nothing received yet|No schedule set", t), "no arrival words")
    run.step(page, "Health in words", "arrival in words (on time, late by days, nothing received)", health_words)

    def stale_counts():
        t = page.locator("tr", has_text="Manager statements by email").inner_text()
        need(re.search(r"\b2\b", t), f"expected 2 stale values (C 101 days, D 192 days, P07); row: {t!r}")
    run.step(page, "Stale values at manager statements", "2 values older than 90 days", stale_counts, hard=False)

    def trail():
        page.goto(base + "/centre/action", wait_until="domcontentloaded")
        loaded(page)
        btn = page.get_by_role("button", name="Where is this from?")
        try:  # the button is put on each card after the cards arrive
            btn.first.wait_for(timeout=10000)
        except Exception:  # noqa: BLE001 - nothing under Needs me (the head of data owns no card): try the other filter, then a case
            page.get_by_role("button", name="Worth a look", exact=True).click(); loaded(page)
            if not btn.count():
                page.goto(base + "/centre/action/cases", wait_until="domcontentloaded"); loaded(page)
                page.get_by_role("row").nth(1).get_by_role("link").first.click(); loaded(page)
        need(btn.count(), "no 'Where is this from?' button on Today (both filters) or on a case page")
        btn.first.click()
        panel = page.get_by_role("region", name="Where this is from")
        panel.wait_for()
        panel.get_by_text("Loading the trail").wait_for(state="detached", timeout=20000)
        need(panel.get_by_text("Recorded").count() or panel.get_by_text("Waiting").count(), "trail steps not shown")
        link = panel.get_by_role("link", name=re.compile("Open in the map", re.I)).or_(panel.get_by_role("button", name=re.compile("Open in the map", re.I)))
        need(link.count(), "no 'Open in the map' control in the trail panel (ui/src/v1/a5trail/TrailPanel.tsx has none)")
        link.first.click()
        page.wait_for_load_state("networkidle")
        need("/centre/map" in page.url and "focus=" in page.url, f"did not land on the map with a focus: {page.url}")
        return page.url
    run.step(page, "Open in the map from a trail panel", "trail panel offers Open in the map; map opens with the item focused", trail)

    def focus_defs():
        open_map(page, base, "?tab=definitions")
        name = page.locator("section.ds-card h2").first.inner_text()
        open_map(page, base, "?tab=definitions&focus=" + name.replace(" ", "%20"))
        out = page.locator("section.ds-card").first.evaluate("e => getComputedStyle(e).outlineStyle + ' ' + getComputedStyle(e).outlineWidth")
        need("solid" in out, f"focused concept not marked: {out}")
        return f"{name} marked ({out})"
    run.step(page, "Definitions link with a concept named", "that concept is marked", focus_defs)

    def focus_proc():
        open_map(page, base, "?tab=processes&focus=not-a-real-intent")
        need(page.get_by_role("group", name="Process map").is_visible(), "unknown focus should fall back to the first signed process")
    run.step(page, "Process link with an unknown item", "falls back to the first signed process", focus_proc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Run("mapa_2", a.out)
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
