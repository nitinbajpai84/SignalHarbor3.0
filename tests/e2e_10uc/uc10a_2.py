"""UC10 charter 2: the head of data (Anita Rao) in Build approves Span's plan, runs the pipeline, sets the schedule and exports the Airflow file.

Usage: python tests/e2e_10uc/uc10a_2.py --base http://127.0.0.1:8711 --creds <seed_credentials.txt> --out <dir>
Picks the project uc10a_1 sent to Build (<out>/uc10a_1/handoff.json), else the project titled as in the universe. A plan nobody has sent to the head of data yet is
proposed first by the data engineer (Leo Park), because the proposer cannot approve their own plan. Writes <out>/uc10a_2/NN-<step>.png and result.md; exit 1 on a failed check.
Synthetic data only; every name comes from docs/test/10uc_universe.json. Passwords are read from the creds file and never printed or saved.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
N, ROWS = 2, []
BAD = re.compile(r"undefined|\bNaN\b|\bnull\b|\[object|Traceback|Internal Server Error|Something went wrong|Unexpected token|\bHTTP [45]\d\d\b")
# case numbers, trade and forward ids are business references people use (CASE-0001, T-20261006-005, FXF-2026-002), not raw ids
RAW_ID = re.compile(r"\b(?!CASE-\d{4}\b|T-\d{8}\b|FXF-\d{4}\b)[A-Z]{1,5}-\d{3,}\b|\b(?:intent|int|prj|proj|plan|run|dash)-[0-9a-f]{6,}\b|\b[0-9a-f]{12,}\b")


def creds_for(path: str, prefix: str) -> tuple[str, str]:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].lower().startswith(prefix) and p[0].lower().endswith("example.test") and "evergreen" in p[0]:
            return p[0], p[1]
    sys.exit(f"no credentials for {prefix}")


class Run:
    def __init__(self, out: Path):
        self.dir = out / f"uc10a_{N}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.failed = False

    def shot(self, page, step: str) -> str:
        self.n += 1
        name = f"{self.n:02d}-{step}.png"
        page.screenshot(path=str(self.dir / name), full_page=False)
        return name

    def step(self, page, step: str, expected: str, ok: bool, actual: str):
        shot = self.shot(page, step)
        ROWS.append((step, expected, actual.replace("\n", " ")[:300], "pass" if ok else "FAIL", shot))
        print(("PASS " if ok else "FAIL ") + step, flush=True)
        self.failed |= not ok

    def clean(self, page, step: str):
        """No raw id, error text or 'undefined' on the visible screen."""
        text = page.locator("body").inner_text()
        bad = sorted(set(BAD.findall(text)))
        ids = sorted(set(RAW_ID.findall(text)))
        ok = not bad and not ids
        ROWS.append((step + ": clean screen", "no raw id, error text or 'undefined'", "clean" if ok else f"error words {bad}; raw ids {ids}", "pass" if ok else "FAIL", "-"))
        print(("PASS " if ok else "FAIL ") + step + " clean", flush=True)
        self.failed |= not ok

    def write(self, title: str):
        md = [f"# UC10 head of data, Build: {'FAIL' if self.failed else 'PASS'}", "", f"Project: {title}", "",
              "| Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|"]
        md += [f"| {a} | {b} | {c.replace('|', '/')} | {d} | {e} |" for a, b, c, d, e in ROWS]
        (self.dir / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def press(loc, timeout=8000):
    """Plain clicks have timed out on this box: try one, then fall back to a DOM click."""
    try:
        loc.click(timeout=timeout)
    except Exception:
        loc.evaluate("e => e.click()")


def login(page, base: str, email: str, password: str):
    page.goto(base + "/login", wait_until="domcontentloaded")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(lambda u: "/login" not in u, timeout=30000)
    page.wait_for_load_state("domcontentloaded")


def open_doc(page, title: str):
    """Bring one document of the workbench to the front (a thin strip button when another is enlarged)."""
    thin = page.get_by_role("button", name=f"Open {title}")
    if thin.count():
        press(thin.first)
        page.wait_for_timeout(500)


def h1(page) -> str:
    return page.get_by_role("heading", level=1).first.inner_text().strip()


def open_project(page, base: str, title: str):
    page.goto(base + "/centre/build", wait_until="domcontentloaded")
    row = page.get_by_role("row").filter(has_text=title)
    row.first.wait_for(timeout=30000)
    press(row.first.get_by_role("link").first)  # the row may hold more than one link
    page.get_by_text("Opening the project").wait_for(state="detached", timeout=30000)
    page.get_by_role("heading", level=1).filter(has_text=title).first.wait_for(timeout=30000)


def idle(page, timeout=240000):
    page.get_by_text("Span is working").wait_for(state="detached", timeout=timeout)
    page.wait_for_timeout(800)


def propose_as_engineer(browser, base: str, creds: str, title: str) -> str:
    """Leo Park (data engineer) gets the plan to 'Waiting for the head of data' when nobody has sent it yet."""
    email, pw = creds_for(creds, "leo.park")
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.set_default_timeout(30000)
    login(page, base, email, pw)
    open_project(page, base, title)
    ask = page.get_by_role("button", name="Ask Span to propose a plan")
    if ask.count() and ask.is_enabled():
        press(ask)
        page.get_by_text("Span has not proposed a plan yet").wait_for(state="detached", timeout=240000)
        idle(page)
    open_doc(page, "5 Approval")
    send = page.get_by_role("button", name="Send to the head of data")
    if send.count() and send.is_enabled():
        press(send)
        page.get_by_text("Waiting for the head of data").first.wait_for(timeout=120000)
    state = "Waiting for the head of data" if page.get_by_text("Waiting for the head of data").count() else "not waiting"
    page.context.close()
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Run(Path(a.out))
    hand = Path(a.out) / "uc10a_1" / "handoff.json"
    chained = hand.is_file()
    title = json.loads(hand.read_text(encoding="utf-8"))["title"] if chained else U["project"]["title"]
    gold, bronze = U["project"]["gold"], U["project"]["bronze"]
    email, pw = creds_for(a.creds, "anita.rao")
    with sync_playwright() as pw_:
        br = pw_.chromium.launch()
        page = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.set_default_timeout(30000)
        try:
            login(page, a.base, email, pw)
            run.step(page, "signed-in", "Anita Rao lands in Action with Build in the bar",
                     page.get_by_role("link", name=re.compile("^BUILD", re.I)).count() > 0, page.url)

            # Before she opens the plan, make sure someone else proposed it (Leo Park).
            lp = propose_as_engineer(br, a.base, a.creds, title)
            ROWS.append(("setup: data engineer proposes", "Leo Park sends the plan to the head of data", lp, "pass" if lp.startswith("Waiting") or not chained else "FAIL", "-"))
            run.failed |= chained and not lp.startswith("Waiting")

            page.goto(a.base + "/centre/action", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            card = page.get_by_text(f"{title} is ready for Build")
            run.step(page, "action-card", "A card in Action says the project is ready for Build" + ("" if chained else " (only when uc10a_1 sent it)"),
                     card.count() > 0 or not chained, f"card found: {card.count() > 0}")
            if card.count():
                press(page.get_by_role("link", name="Open in Build").first)
                page.wait_for_url(re.compile(r"/centre/build/p/"), timeout=30000)
                page.get_by_role("heading", level=1).filter(has_text=title).first.wait_for()
            else:
                open_project(page, a.base, title)
            run.step(page, "build-page", "The Build page header is the project title (not an id) with Span's six documents",
                     h1(page) == title and not RAW_ID.search(h1(page)) and page.get_by_text("Span, the build agent").count() == 1, f"header: {h1(page)}")
            run.clean(page, "build-page")

            page.goto(a.base + "/centre/build", wait_until="domcontentloaded")
            row = page.get_by_role("row").filter(has_text=title).first
            row.wait_for()
            rt = row.inner_text()
            run.step(page, "project-list", "Build Centre lists the project by title with its stage and build state, owner named",
                     "Waiting for the head of data" in rt or "Approved" in rt or "Live" in rt, rt)
            open_project(page, a.base, title)

            open_doc(page, "1 Sources")
            body = page.locator(".wb-docs").inner_text()
            run.step(page, "sources", "Sources lists the administrator and trading exports with owners",
                     "Owner:" in body and ("administrator" in body.lower() or "trading" in body.lower()), body[:300])

            open_doc(page, "3 Tables")
            tables = page.locator(".wb-docs").inner_text().lower()
            has_layers = page.get_by_role("region", name="bronze").count() > 0 and page.get_by_role("region", name="gold").count() > 0
            seeded = [t for t in bronze + gold if t not in tables]
            run.step(page, "tables", f"Bronze and gold tables are listed; for the universe project: {', '.join(bronze + gold)}",
                     has_layers and (chained or not seeded), f"bronze+gold sections: {has_layers}; universe tables not shown: {seeded}")

            open_doc(page, "5 Approval")
            ap_text = page.locator(".wb-docs").inner_text()
            approve = page.get_by_role("button", name="Approve the plan and the model change")
            waiting = "Waiting for the head of data" in ap_text
            run.step(page, "approval-view", "Approval shows who proposed the plan and that it waits for the head of data (or is already approved)",
                     ("Proposed by: " in ap_text) and (waiting or "Approved by" in ap_text), ap_text[:300])
            if approve.count() and approve.is_enabled():
                press(approve)
                page.get_by_text(re.compile("Approved by Anita Rao")).first.wait_for(timeout=120000)
            ap_text = page.locator(".wb-docs").inner_text()
            run.step(page, "approved", "Approved by Anita Rao, which also approves the model change", "Approved by Anita Rao" in ap_text or "Live" in ap_text, ap_text[:300])
            run.clean(page, "approved")

            open_doc(page, "6 Pipeline")
            sandbox = page.get_by_role("button", name="Try it on a copy")
            press(sandbox)
            page.get_by_text(re.compile(r"Sandbox run, plan version \d+: ")).first.wait_for(timeout=240000)
            summ = page.get_by_text(re.compile(r"Sandbox run, plan version \d+: ")).first
            press(summ)
            runs_text = page.locator(".wb-docs").inner_text()
            sandbox_ok = not re.search(r"Sandbox run, plan version \d+: (failed|error)", runs_text, re.I)
            run.step(page, "sandbox-run", "The sandbox run finishes without a failed step; each table shows rows and a status",
                     sandbox_ok and "Rows" in runs_text, summ.inner_text())
            golive = page.get_by_role("button", name="Go live")
            if golive.count() and golive.is_enabled():
                press(golive)
                page.get_by_text(re.compile(r"Live run, plan version \d+: ")).first.wait_for(timeout=240000)
            live_txt = page.locator(".wb-docs").inner_text()
            run.step(page, "go-live", "A live run is recorded (or the project is already live)", bool(re.search(r"Live run, plan version \d+: (?!failed|error)", live_txt, re.I)), live_txt[-300:])
            run.clean(page, "go-live")

            sel = page.get_by_label("Repeat")
            sel.select_option(label="Every month")
            page.locator("input[type=time]").first.fill("07:00")
            press(page.get_by_role("button", name="Save the schedule"))
            page.wait_for_timeout(1500)
            page.reload(wait_until="domcontentloaded")
            page.get_by_role("heading", level=1).filter(has_text=title).first.wait_for()
            open_doc(page, "6 Pipeline")
            run.step(page, "schedule", "The schedule 'Every month' at 07:00 is saved and is still there after a reload (needed by " + U["process"]["needed_by"] + ")",
                     page.get_by_label("Repeat").input_value() == "monthly" and page.locator("input[type=time]").first.input_value() == "07:00",
                     f"repeat={page.get_by_label('Repeat').input_value()} at={page.locator('input[type=time]').first.input_value()}")

            page.get_by_text("For engineers").first.click()  # the Airflow link sits in this details block
            with page.expect_download(timeout=60000) as dl:
                press(page.get_by_role("link", name="Download the Airflow file"))
            f = dl.value
            dest = run.dir / f.suggested_filename
            f.save_as(str(dest))
            code = dest.read_text(encoding="utf-8", errors="replace")
            names_ok = [t for t in gold if t in code] if not chained else [t for t in re.findall(r"gold_[a-z0-9_]+", code)]
            run.step(page, "airflow-export", "The Airflow file downloads as a Python DAG that names the gold tables",
                     dest.stat().st_size > 0 and f.suggested_filename.endswith(".py") and "DAG" in code and bool(names_ok), f"{f.suggested_filename}, {dest.stat().st_size} bytes, gold tables named: {sorted(set(names_ok))}")

            page.goto(a.base + "/centre/build", wait_until="domcontentloaded")
            row = page.get_by_role("row").filter(has_text=title).first
            row.wait_for()
            run.step(page, "list-after", "Build Centre now shows the project as Live", "Live" in row.inner_text(), row.inner_text())
            run.clean(page, "list-after")
        except Exception as e:  # a missing screen is a failed step, not a crash
            run.step(page, "stopped", "the journey completes", False, f"{type(e).__name__}: {str(e)[:250]}")
        finally:
            run.write(title)
            br.close()
    sys.exit(1 if run.failed else 0)


if __name__ == "__main__":
    main()
