"""UC10 charter 1: the analyst (Mei Chen) talks to North, the intent and swim lane are drafted, she signs and sends it to Build.

Usage: python tests/e2e_10uc/uc10a_1.py --base http://127.0.0.1:8711 --creds <seed_credentials.txt> --out <dir>
Writes <out>/uc10a_1/NN-<step>.png, result.md and handoff.json (the project title, read by uc10a_2). Exit 1 on any failed check.
Synthetic data only; every figure and name comes from docs/test/10uc_universe.json. Passwords are read from the creds file and never printed or saved.
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
N, ROWS = 1, []
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
        """No raw id, error text or 'undefined' anywhere on the visible screen."""
        text = page.locator("body").inner_text()
        bad = sorted(set(BAD.findall(text)))
        ids = sorted(set(RAW_ID.findall(text)))
        ok = not bad and not ids
        ROWS.append((step + ": clean screen", "no raw id, error text or 'undefined'", "clean" if ok else f"error words {bad}; raw ids {ids}", "pass" if ok else "FAIL", "-"))
        print(("PASS " if ok else "FAIL ") + step + " clean", flush=True)
        self.failed |= not ok

    def write(self, title: str):
        md = [f"# UC10 analyst, intent conversation: {'FAIL' if self.failed else 'PASS'}", "", f"Journey: {title}", "",
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


def thinking_done(page, wait_s=240):
    try:
        page.get_by_text("North is thinking").wait_for(timeout=8000)
    except Exception:
        pass
    page.get_by_text("North is thinking").wait_for(state="detached", timeout=wait_s * 1000)
    page.wait_for_timeout(800)


def accept_all(page):
    """North proposes its changes and waits (9 Oct): the person accepts each one ("Accept" beside "Not this"), as she would on screen."""
    for _ in range(12):
        acc = page.get_by_role("button", name="Accept", exact=True)
        if not acc.count():
            break
        press(acc.first)
        page.wait_for_timeout(700)
    for _ in range(12):  # each section North just filled carries "Looks right: <section>" (DocumentLayout.tsx)
        ok = page.get_by_role("button", name=re.compile(r"^Looks right"))
        if not ok.count():
            return
        press(ok.first)
        page.wait_for_timeout(300)


def say(page, text: str):
    """Send one message to North, wait until North has finished thinking, then accept what North proposed."""
    page.get_by_label("Your message").fill(text)
    page.evaluate("document.querySelector('form[aria-label=\"Message North\"]').requestSubmit()")
    thinking_done(page)
    accept_all(page)


def open_doc(page, title: str):
    """Bring one document of the workbench to the front (it is a thin strip button when another is enlarged)."""
    thin = page.get_by_role("button", name=f"Open {title}")
    if thin.count():
        press(thin.first)
        page.wait_for_timeout(500)


def h1(page) -> str:
    return page.get_by_role("heading", level=1).first.inner_text().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Run(Path(a.out))
    proc = U["process"]
    title, steps = proc["project_title"], proc["steps"]
    email, pw = creds_for(a.creds, "mei.chen")
    with sync_playwright() as pw_:
        br = pw_.chromium.launch()
        page = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.set_default_timeout(30000)
        try:
            login(page, a.base, email, pw)
            run.step(page, "signed-in", "Mei Chen lands on her start page with the Intent centre in the bar",
                     page.get_by_role("link", name=re.compile("^INTENT", re.I)).count() > 0, page.url)
            run.clean(page, "signed-in")

            page.goto(a.base + "/centre/intent?new=1", wait_until="domcontentloaded")  # a new intent, never an open draft left by another run
            box = page.get_by_label("What you would like to build")
            try:
                box.wait_for(timeout=15000)
                fresh = True
            except Exception:
                fresh = False  # she has an open conversation: carry on in it
            opening = f"I want to build the {title}. {proc['sponsor']} needs it by the {proc['needed_by']}."
            run.step(page, "intent-centre", "The Intent Centre welcomes her and asks what she plans to build",
                     fresh or "/centre/intent/" in page.url, page.url + (" (welcome)" if fresh else " (open conversation)"))
            if fresh:
                box.fill(opening)
                page.evaluate("document.querySelector('form').requestSubmit()")
                page.wait_for_url(re.compile(r"/centre/intent/[^/]+$"), timeout=60000)
                thinking_done(page)
                accept_all(page)
            else:
                say(page, opening)
            run.step(page, "north-answers", "North answers in the conversation and starts the intent of work",
                     page.get_by_role("heading", name="Documents").count() > 0 and page.get_by_text("Intent of work").count() > 0,
                     page.locator(".wb-log").inner_text()[-300:])
            run.clean(page, "north-answers")

            say(page, "Today it works like this. " + " ".join(f"Step {s['n']}: {s['name']}, done by {s['who']} in {s['system']}." for s in steps))
            open_doc(page, "Process map")
            swim = page.get_by_role("group", name="Process map")
            try:
                swim.wait_for(timeout=20000)
            except Exception:
                pass
            nstep = page.get_by_role("button", name=re.compile(r"^Step \d+:")).count()
            words = [max(re.findall(r"[A-Za-z]+", s["name"]), key=len).lower() for s in steps]
            seen = (swim.inner_text() if swim.count() else "").lower()
            missing = [w for w in words if w not in seen]
            # North words the steps itself: one key word may be phrased differently (as with the systems below)
            run.step(page, "swim-lane", f"The process map shows a swim lane with the {len(steps)} steps (key words {', '.join(words)}) and who does each",
                     nstep >= 4 and len(missing) <= 1, f"{nstep} step buttons; missing key words {missing}")
            sysmiss = [s["system"] for s in steps if s["system"].lower() not in seen]
            run.step(page, "swim-systems", "Each step names its system: " + ", ".join(sorted({s["system"] for s in steps})),
                     len(sysmiss) <= 2, f"systems not shown: {sysmiss}")
            run.clean(page, "swim-lane")

            tiles = [re.sub(r"^t-\d+ | \(K\d+\)$", "", t) for t in U["project"]["tiles"]]
            say(page, "The sources are the administrator positions export and the trading system export, both dropped as files each month. "
                      f"I want to see {', '.join(tiles)}.")
            open_doc(page, "Intent of work")
            body = page.locator(".wb-docs").inner_text().lower()
            run.step(page, "intent-drafted", "The intent of work has a goal, the sources and the dashboard figures",
                     "goal" in body and "source" in body and any(t.lower().split()[0] in body for t in tiles), body[:300])

            ok = page.get_by_role("button", name="That's right")  # the process map's confirm button (was "Looks right"; j-uc10a.3)
            if ok.count():
                press(ok.first)
            accept_all(page)
            for _ in range(6):
                thinking_done(page)
                if page.get_by_role("link", name="Sign the intent of work").count():
                    break
                rep = U["report_issued"]  # North asks for last month's figures: give the issued September report's lines
                say(page, "Last month's issued report (30 Sep 2026, USD): " + "; ".join(f"{x['label']} {int(float(x['value'])):,}" for x in rep["lines"])
                    + ". That is everything I have. Please finish the intent of work so I can sign it.")
            hand = page.get_by_role("link", name="Sign the intent of work")
            name = h1(page)
            run.step(page, "ready-to-sign", "North says the intent is ready; the header shows the project title, not an id or 'Talk to North'",
                     hand.count() > 0 and name != "Talk to North" and not RAW_ID.search(name) and "investment" in name.lower(), f"header: {name}")

            press(hand.first)
            page.wait_for_url(re.compile(r"/sow$"), timeout=30000)
            page.get_by_role("heading", name=re.compile(r"^1\. Goal")).wait_for()
            run.step(page, "sow-page", "The intent of work page shows eight sections and the same title in the header",
                     h1(page) == name and page.get_by_role("heading", name=re.compile(r"^8\. Signature")).count() == 1, f"header: {h1(page)}")
            for q in page.get_by_role("textbox", name=re.compile(r"^Answer:")).all():
                q.fill("Confirmed by the sponsor; use the issued report as the benchmark.")
                press(page.get_by_role("button", name="Settle").first)
                page.wait_for_timeout(600)
            sign = page.get_by_role("button", name="Sign", exact=True)
            run.step(page, "sow-ready", "Nothing blocks the signature", sign.count() == 1 and sign.is_enabled(),
                     f"sign buttons {sign.count()}; notices {page.get_by_role('status').all_inner_texts()}")
            press(sign)
            dlg = page.get_by_role("dialog", name="Sign the intent of work")
            dlg.wait_for()
            run.step(page, "sign-confirm", "A confirm sentence names the version and title before signing", "I sign version" in dlg.inner_text(), dlg.inner_text()[:200])
            press(dlg.get_by_role("button", name="Yes, I sign"))
            page.get_by_text(re.compile(r"Signed by Mei Chen")).first.wait_for(timeout=60000)
            run.step(page, "signed", "Signed by Mei Chen; the page is read-only and Span has been asked to draft the design",
                     page.get_by_text("Span has been asked to draft the design").count() > 0, page.locator("body").inner_text()[:200])
            run.clean(page, "signed")

            press(page.get_by_role("link", name="North's thread"))
            page.get_by_role("button", name="Send to Build").wait_for(timeout=30000)
            run.step(page, "back-to-north", "Back in the conversation the Send to Build button waits",
                     page.get_by_role("button", name="Send to Build").is_enabled(), h1(page))
            press(page.get_by_role("button", name="Send to Build"))
            page.get_by_text("Sent to Build").first.wait_for(timeout=30000)
            txt = page.get_by_role("status").filter(has_text="Sent to Build").inner_text()
            run.step(page, "sent-to-build", "Sent to Build; the head of data has a card in Action; header still the title; no id on screen",
                     "head of data has a card in Action" in txt and not RAW_ID.search(txt) and h1(page) == name, f"{txt} | header: {h1(page)}")
            run.clean(page, "sent-to-build")
            (run.dir / "handoff.json").write_text(json.dumps({"title": name}), encoding="utf-8")
        except Exception as e:  # a missing screen is a failed step, not a crash
            run.step(page, "stopped", "the journey completes", False, f"{type(e).__name__}: {str(e)[:250]}")
        finally:
            run.write(title)
            br.close()
    sys.exit(1 if run.failed else 0)


if __name__ == "__main__":
    main()
