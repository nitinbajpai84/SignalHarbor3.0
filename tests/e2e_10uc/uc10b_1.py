"""UC10 Consume, browser journey 1 (planted fact P33): Lumen proposes a tile in Build > Dashboard studio, the head of data publishes it, it is shared with Daniel and Raj, they see it on Today.

python tests/e2e_10uc/uc10b_1.py --base URL --creds PATH --out DIR
Writes DIR/uc10b_1/NN-<step>.png and DIR/uc10b_1/result.md; exit 1 on any failed step. Passwords are read, never printed or saved.
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
TILES = [t.split(" ", 1)[1].rsplit(" (", 1)[0] for t in PRJ["tiles"]]  # planted tile titles
MAKER, APPROVER, VIEWERS = "Leo Park", U["process"]["head_of_data"], ["Daniel Foo", "Raj Patel"]
ASK = "Show net worth USD by entity per month as a line chart"  # words only; USD, entity and month are columns of the gold tables
NEW_TILE = re.compile(r"net worth (usd )?by entity,? per month", re.I)  # rules title: "Net worth by entity, per month (USD)"
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
        self.dir, self.rows, self.i = Path(out) / "uc10b_1", [], 0
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
        md = ["# UC10 browser journey 1 (P33): Lumen builds a tile, shares it, Daniel and Raj see it on Today", "",
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


def reveal(page, doc, probe):
    """On a narrow layout a document is a tab; on desktop it is already open."""
    try:
        probe.first.wait_for(timeout=8000)  # the page may still be loading its documents; is_visible() does not wait
    except Exception:  # noqa: BLE001 - not there: it is a tab on a narrow layout
        page.get_by_role("button", name=f"Show {doc}").click()


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
        em = PEOPLE[MAKER]["email"].lower()
        ctx, page = login(browser, base, em, creds[em])
        run.step(page, "leo-signed-in", f"{MAKER} (analyst) is signed in and leaves the login page", lambda: clean(page) or page.url.replace(base, ""))

        def pick():
            page.goto(base + "/centre/consume")
            expect(page.get_by_role("heading", name="Consume", exact=True)).to_be_visible()
            page.get_by_role("button", name=re.compile(re.escape(title))).click()
            expect(page.get_by_text(re.compile(r"\b([3-9]|\d\d) (accepted )?tiles")).first).to_be_visible()  # 3 planted; a rerun adds the tile it published
            clean(page)
            return f"project '{title}' lists its dashboard with its 3 tiles"
        run.step(page, "consume-pick-project", f"Consume lists '{title}'; its dashboard shows its 3 tiles", pick)

        def open_board():
            page.get_by_role("link", name=re.compile(re.escape(title))).first.click()
            expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()
            for t in TILES:
                art = page.locator("article", has_text=t).first
                expect(art).to_be_visible()  # Consume draws the published grid, with no Accepted/Proposed word (OP1)
            expect(page.get_by_text(USED).nth(len(TILES) - 1)).to_be_visible()  # each tile loads its data on its own: wait for the third
            assert page.get_by_text(USED).count() >= len(TILES), "a planted tile shows no 'Data used'"
            assert page.get_by_text("could not be loaded").count() == 0, "a tile could not load its numbers"
            clean(page)
            return f"tiles {', '.join(TILES)} are on the published dashboard with their numbers"
        run.step(page, "dashboard-three-tiles", f"The dashboard shows {', '.join(TILES)} on the published grid, with numbers", open_board)

        def gold():
            reveal(page, "Figures available", page.get_by_text(PRJ["gold"][0]))
            for g in PRJ["gold"]:
                expect(page.get_by_text(g, exact=True).first).to_be_visible()
            return "both gold tables are listed in the tables drawer"
        run.step(page, "gold-tables", f"The tables drawer lists {', '.join(PRJ['gold'])}", gold)

        # OP1 (10 Oct): Consume shows published dashboards only; Lumen proposes tiles in Build > Dashboard studio, the maker
        # accepts and submits, and the head of data approves before Consume shows it (UC10B-003).
        GRID = '[aria-label="Dashboard grid"] article'

        def studio(page=page):
            page.goto(base + "/centre/build")
            page.get_by_role("heading", name="Build Centre").wait_for()
            page.get_by_role("row").filter(has_text=title).get_by_role("link").first.click()
            page.get_by_role("link", name="Dashboard studio").first.click()
            page.get_by_role("link", name="Open", exact=True).first.click()
            page.wait_for_url(re.compile(r"/studio\?d="))
            expect(page.locator(GRID).first).to_be_visible()

        def proposed():
            # a rerun may leave an earlier proposal in the thread: pick the newest one still waiting
            return page.get_by_role("region", name="Talk to Lumen").locator("article", has_text=NEW_TILE).last

        def ask():
            studio()
            chat = page.get_by_role("region", name="Talk to Lumen")
            before = chat.locator("article", has_text=NEW_TILE).count()
            chat.get_by_role("textbox").fill(ASK)
            chat.get_by_role("button", name="Send", exact=True).click()
            expect(chat.locator("article", has_text=NEW_TILE)).to_have_count(before + 1, timeout=60000)
            expect(proposed().get_by_role("button", name="Accept")).to_be_visible()
            clean(page)
            return "Lumen proposed one tile in the studio, waiting for Accept or Not this"
        run.step(page, "lumen-proposes-tile", f"In Build > Dashboard studio, asking Lumen '{ASK}' proposes one tile with Accept and Not this", ask)

        def accept():
            placed = page.locator(GRID, has_text=NEW_TILE)
            before = placed.count()
            proposed().get_by_role("button", name="Accept").click()
            expect(placed).to_have_count(before + 1)
            expect(placed.last.get_by_text(USED)).to_be_visible()
            page.get_by_role("button", name="Submit for approval").click()
            expect(page.get_by_text("waiting for the head of data or the sponsor")).to_be_visible()
            clean(page)
            return "the tile is on the grid with its numbers; the new version is sent for approval"
        run.step(page, "accept-new-tile", "Accept places the tile on the grid; Submit for approval sends the new version", accept)

        def approve():
            em2 = PEOPLE[APPROVER]["email"].lower()
            c2, p2 = login(browser, base, em2, creds[em2])
            try:
                studio(p2)
                box = p2.get_by_role("region", name="Waiting for your approval")
                expect(box).to_be_visible()
                box.get_by_role("button", name="Approve and publish").click()
                expect(p2.get_by_text(re.compile(rf"Approved by {APPROVER}"))).to_be_visible()
                p2.screenshot(path=str(run.dir / f"{run.i + 1:02d}-approved-by-{APPROVER.split()[0].lower()}.png"), full_page=True)
                return f"{APPROVER} approved and published the new version"
            finally:
                c2.close()
        run.step(page, "head-of-data-approves", f"{APPROVER} (head of data) sees 'Waiting for your approval' and publishes it", approve)

        def to_consume():
            page.goto(base + "/centre/consume")
            page.get_by_role("button", name=re.compile(re.escape(title))).click()
            page.get_by_role("link", name=re.compile(re.escape(title))).first.click()
            expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()

        def share():
            to_consume()
            reveal(page, "Share", page.get_by_role("button", name="Share with these people"))
            expect(page.get_by_text(re.compile(r"Shared with:"))).to_be_visible()
            for v in VIEWERS:
                expect(page.get_by_text(re.compile(rf"Shared with:.*{v}"))).to_be_visible()
                assert page.get_by_label(v).is_checked(), f"{v} should be ticked"
            page.get_by_role("button", name="Share with these people").click()
            expect(page.get_by_text(re.compile(r"Shared with:.*Daniel Foo")).first).to_be_visible()
            expect(page.get_by_text("did not go through")).to_have_count(0)
            clean(page)
            return "audience is Daniel Foo and Raj Patel; shared again with no error"
        run.step(page, "share-with-daniel-raj", "The share panel reads 'Shared with: Daniel Foo, Raj Patel'; sharing again raises no error", share)
        ctx.close()

        for who in VIEWERS:
            em = PEOPLE[who]["email"].lower()
            ctx, page = login(browser, base, em, creds[em])
            slug = who.split()[0].lower()

            def today(who=who, page=page):
                page.goto(base + "/centre/action")  # Today is the first tab of Action; it has no heading of its own
                expect(page.get_by_role("heading", name="Action", exact=True)).to_be_visible()
                page.get_by_role("button", name="Worth a look", exact=True).click()
                page.wait_for_load_state("networkidle")
                card = page.locator("li", has_text="shared with you").first
                expect(card.get_by_role("heading", name=re.compile(rf"{re.escape(title)}.*shared with you"))).to_be_visible()
                expect(card.get_by_text(re.compile(r"^(Shared|Refreshed)$"))).to_be_visible()  # a share of a dashboard already shared reads Refreshed (e5 statusWord)
                expect(card.get_by_role("link", name="Open dashboard")).to_be_visible()
                clean(page)
                return f"{who} has a 'shared with you' card for the dashboard on Today (Worth a look)"
            run.step(page, f"{slug}-today-card", f"{who} sees '{title} shared with you' on Today with an Open dashboard link", today)

            def open_dash(who=who, page=page):
                page.locator("li", has_text="shared with you").first.get_by_role("link", name="Open dashboard").click()
                expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()
                for t in TILES:
                    expect(page.locator("article", has_text=t).first).to_be_visible()
                expect(page.locator("article", has_text=NEW_TILE).first).to_be_visible()
                expect(page.get_by_role("button", name="Accept")).to_have_count(0)
                expect(page.get_by_role("button", name="Accept")).to_have_count(0)  # read only: no Accept (the "Read only" label is gone; the subline says "The accepted tiles")
                expect(page.get_by_text(USED).nth(len(TILES))).to_be_visible()  # each tile loads on its own: wait for the 4th (a rerun publishes more)
                clean(page)
                return f"{who} sees the 3 planted tiles and the new one, read only, with numbers"
            run.step(page, f"{slug}-opens-dashboard", f"{who} opens it: {', '.join(TILES)} and the new tile, read only, no Accept button", open_dash)
            ctx.close()
        browser.close()
    sys.exit(0 if run.finish() else 1)


if __name__ == "__main__":
    main()
