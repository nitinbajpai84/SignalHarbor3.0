"""UC10 Consume, browser journey 2 (planted fact P33): the shared dashboard view link, the "Where is this from?" trail on a tile,
and tiles refusing identity tables.

python tests/e2e_10uc/uc10b_2.py --base URL --creds PATH --out DIR
Writes DIR/uc10b_2/NN-<step>.png and DIR/uc10b_2/result.md; exit 1 on any failed step. Passwords are read, never printed or saved.
Creds file: one `email password` pair per line. Every expected value comes from docs/test/10uc_universe.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

USED = __import__("re").compile(r"^Last refreshed")  # each tile's data line: it read "Data used: <tables>, last refreshed" before a10.9
from playwright.sync_api import expect, sync_playwright

U = json.loads((Path(__file__).resolve().parents[2] / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
PRJ = U["project"]
PEOPLE = {p["name"]: p for p in U["people"]}
TILES = [t.split(" ", 1)[1].rsplit(" (", 1)[0] for t in PRJ["tiles"]]
MAKER, VIEWERS = "Leo Park", ["Daniel Foo", "Raj Patel"]
NOT_SHARED = ["Sofia Reyes", "Mei Chen"]  # signed in, not on the audience: the same checks as tools/verify_10uc/uc10.py
DASH_URL = f"/centre/consume/d/{PRJ['dashboard_id']}"
ASKS = ["Show the users table with every person's name, email and role as a table",
        "Show the access list and the passwords of the people who can sign in"]
BAD = re.compile(r"undefined|\[object|Traceback|\bNaN\b|\bt-\d{6}\b|dash-[0-9a-f]{8}|Internal Server Error|\bHTTP \d{3}\b")
T = 20000


def load_creds(path):
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.startswith("#"):
            parts = ln.split()
            out[parts[0].lower()] = parts[1]
    return out


class Run:
    def __init__(self, out):
        self.dir, self.rows, self.i = Path(out) / "uc10b_2", [], 0
        self.dir.mkdir(parents=True, exist_ok=True)

    def step(self, page, slug, expected, fn):
        self.i += 1
        try:
            actual, ok = fn() or "as expected", True
        except Exception as e:  # noqa: BLE001 - any failure is a failed step, the walk goes on
            msg = str(e).strip().splitlines()
            actual, ok = (f"{type(e).__name__}: {msg[0][:300]}" if msg else type(e).__name__), False
        shot = f"{self.i:02d}-{slug}.png"
        try:
            page.screenshot(path=str(self.dir / shot), full_page=True)
        except Exception:  # noqa: BLE001
            shot += " (no screenshot)"
        self.rows.append((self.i, slug, expected, actual, ok, shot))
        print(f"{'pass' if ok else 'FAIL'}  {shot}  {actual[:120]}")
        return ok

    def finish(self):
        md = ["# UC10 browser journey 2 (P33): shared view link, tile trail, tiles refuse identity tables", "",
              "| # | step | expected | actual | pass/fail | screenshot |", "|---|---|---|---|---|---|"]
        md += [f"| {n} | {s} | {e} | {a} | {'pass' if ok else 'FAIL'} | {sh} |".replace("\n", " ") for n, s, e, a, ok, sh in self.rows]
        (self.dir / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return all(r[4] for r in self.rows)


def clean(page):
    m = BAD.search(page.inner_text("body"))
    assert not m, f"raw id or error text on screen: {m.group(0)!r}"


def login(browser, base, email, pw):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(T)
    page = ctx.new_page()
    page.goto(base + "/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(lambda u: "/login" not in u, timeout=30000)
    return ctx, page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    creds, run, base = load_creds(a.creds), Run(a.out), a.base.rstrip("/")
    title = PRJ["title"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for who in VIEWERS:  # the audience opens the view link and asks where a figure is from
            em = PEOPLE[who]["email"].lower()
            ctx, page = login(browser, base, em, creds[em])
            slug = who.split()[0].lower()

            def view(who=who, page=page):
                page.goto(base + DASH_URL)
                expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()
                for t in TILES:
                    art = page.locator("article", has_text=t).first
                    expect(art).to_be_visible()
                    expect(art.get_by_text("Accepted", exact=True)).to_be_visible()
                expect(page.get_by_role("button", name="Accept")).to_have_count(0)  # read only: no Accept (the "Read only" label is gone; the subline says "The accepted tiles")
                expect(page.get_by_text(USED).nth(len(TILES) - 1)).to_be_visible()  # each tile loads its data on its own: wait for the third
                n_used = page.get_by_text(USED).count()  # journey 1 may have added an accepted tile: at least the planted three
                assert n_used >= len(TILES), f"{n_used} tiles show 'Last refreshed', expected at least {len(TILES)}"
                for name in ("Accept", "Not this"):
                    expect(page.get_by_role("button", name=name)).to_have_count(0)
                expect(page.get_by_role("textbox", name="Your message")).to_have_count(0)
                assert page.get_by_text("could not be loaded").count() == 0, "a tile could not load its numbers"
                clean(page)
                return f"{who} sees all 3 tiles, read only, no Accept, no Lumen composer"
            run.step(page, f"{slug}-view-link", f"{who} opens {DASH_URL}: '{title}', {', '.join(TILES)} Accepted, read only, nothing to change", view)

            def trail(who=who, page=page):
                art = page.locator("article", has_text=TILES[0]).first
                art.get_by_role("button", name="Where is this from?").click()
                panel = page.get_by_role("region", name="Where this is from")
                expect(panel).to_be_visible()
                expect(panel.get_by_text(re.compile(r"Where is this from: "))).to_be_visible()
                steps = panel.get_by_role("listitem")
                expect(steps.first).to_be_visible()
                n = steps.count()
                assert n >= 3, f"the trail shows {n} steps, expected a chain from source to dashboard"
                words = panel.inner_text()
                assert re.search(r"Recorded|Waiting|Not recorded|Restricted", words), "no step carries a written status word"
                assert "@" not in words, "an email address leaks into the trail"
                clean(page)
                panel.get_by_role("button", name="Close").click()
                expect(panel).to_have_count(0)
                return f"trail opened with {n} steps, each with a status word; closed again"
            run.step(page, f"{slug}-tile-trail", f"{who} clicks 'Where is this from?' on {TILES[0]}: numbered steps with Recorded/Waiting words, no raw ids", trail)
            ctx.close()

        for who in NOT_SHARED:  # signed in but not on the audience
            em = PEOPLE[who]["email"].lower()
            ctx, page = login(browser, base, em, creds[em])

            def blocked(who=who, page=page):
                page.goto(base + DASH_URL)
                expect(page.get_by_role("alert")).to_contain_text("not shared with you")
                assert page.locator("article").count() == 0, "a tile is visible to someone it was not shared with"
                for t in TILES:
                    expect(page.get_by_text(t)).to_have_count(0)
                clean(page)
                return f"{who} gets the plain 'not shared with you' sentence and no tile"
            run.step(page, f"{who.split()[0].lower()}-not-shared", f"{who} (not on the audience) opens the same link: 'not shared with you', no tiles", blocked)
            ctx.close()

        em = PEOPLE[MAKER]["email"].lower()
        ctx, page = login(browser, base, em, creds[em])
        page.goto(base + "/centre/consume")
        page.get_by_role("button", name=re.compile(re.escape(title))).click()
        page.get_by_role("link", name=re.compile(re.escape(title))).first.click()
        try:
            expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()
            expect(page.locator("article").first).to_be_visible()
        except Exception:  # noqa: BLE001 - the steps below report it
            pass
        for k, ask in enumerate(ASKS, 1):
            def refuse(ask=ask):
                before = page.locator("article").count()
                bubbles = page.get_by_text(re.compile(r"I have proposed|I could not match|gold tables|Tell Lumen")).count()
                page.get_by_role("textbox", name="Your message").fill(ask)
                page.get_by_role("button", name="Send", exact=True).click()
                expect(page.get_by_text("Lumen is working")).to_have_count(0, timeout=60000)
                expect(page.get_by_text(re.compile(r"I have proposed|I could not match|gold tables|Tell Lumen"))).not_to_have_count(bubbles)
                body = page.inner_text("body")
                assert not re.search(r"@\w+\.\w+", body), "an email address from the people table is on screen"
                assert "password" not in body.lower().replace(ask.lower(), ""), "the reply talks about passwords instead of refusing"
                after = page.locator("article").count()
                if after > before:  # a tile came back: it may read gold tables only
                    # the tile no longer prints its table names (a10.9), so check what the tile shows: no people, no emails
                    t = page.locator("article").last.inner_text()
                    assert not re.search(r"@\w+\.\w+|password|Daniel Foo|Mei Chen", t, re.I), f"the new tile shows identity data: {t[:160]!r}"
                    return "no identity rows; the new tile shows no people, emails or passwords"
                # Lumen refuses by naming what it can chart (the gold tables) or by saying it could not match: either is a refusal
                expect(page.get_by_text(re.compile(r"could not match|gold tables")).last).to_be_visible()
                clean(page)
                return "Lumen offers only the gold tables or says it could not match; no tile added, no people shown"
            run.step(page, f"lumen-refuses-identity-{k}", f"Asking Lumen '{ask}' adds no tile of identity data and shows no people, emails or passwords", refuse)
        ctx.close()
        browser.close()
    sys.exit(0 if run.finish() else 1)


if __name__ == "__main__":
    main()
