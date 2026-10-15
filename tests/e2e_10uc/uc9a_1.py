"""UC9 charter 1 (P32): sponsor opens the signed month-end intent in Intent and sees the signed process swim lane.
Usage: python uc9a_1.py --base URL --creds PATH --out DIR"""
import argparse, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

N = "uc9a_1"
ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
PROC, WHO = U["process"], "Daniel Foo"
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b(?:intent|proj|usr|user)[-_][0-9a-f]{6,}", re.I)


def password_for(creds, email):
    for ln in pathlib.Path(creds).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if p and not ln.startswith("#") and p[0].lower() == email.lower():
            return p[1]
    raise SystemExit("no credentials for the sponsor in the creds file")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--creds", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out) / N; out.mkdir(parents=True, exist_ok=True)
    rows, n = [], [0]
    email = next(p["email"] for p in U["people"] if p["name"] == WHO)

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        pg.set_default_timeout(20000)

        def step(name, expected, check):
            n[0] += 1
            shot = f"{n[0]:02d}-{name}.png"
            try:
                actual = check() or "as expected"; ok = True
            except Exception as e:  # noqa: BLE001
                actual = f"{type(e).__name__}: {str(e)[:300]}"; ok = False
            try:
                pg.screenshot(path=str(out / shot), full_page=True)
                body = pg.inner_text("body")
                if ok and BAD.search(body):
                    ok, actual = False, f"raw id or error text on screen: {BAD.search(body).group(0)}"
            except Exception as e:  # noqa: BLE001
                ok, actual = False, f"screenshot failed: {e}"
            rows.append((name, expected, actual, ok, shot))

        def visible(text, exact=True):
            pg.get_by_text(text, exact=exact).first.wait_for(state="visible")

        def login():
            pg.goto(a.base + "/login")
            pg.get_by_label("Email").fill(email)
            pg.get_by_label("Password").fill(password_for(a.creds, email))
            pg.evaluate("document.querySelector('form').requestSubmit()")
            pg.wait_for_url(lambda u: "/login" not in u)
            pg.wait_for_load_state("networkidle")
        step("login", "sponsor signs in and leaves the login page", lambda: login())

        def open_intent():
            pg.goto(a.base + "/centre/intent?new=1"); pg.wait_for_load_state("networkidle")  # the welcome with its recent list; without ?new=1 it jumps to the open draft
            pg.get_by_role("link", name=PROC["project_title"]).first.wait_for(timeout=15000)
            link = pg.get_by_role("link", name=PROC["project_title"])
            if link.count():
                link.first.click()
            pg.wait_for_url(re.compile(r"/centre/intent/[^/]+$"))
            pg.get_by_role("heading", name=PROC["project_title"]).first.wait_for(state="visible")
        step("intent-list", "recent intents list the signed month-end intent; opening it shows its title", open_intent)

        def signed():
            # once the signed intent has gone to Build and the project is live, the pill reads Live and North says it was signed (j-uc9a.0)
            pg.get_by_text(re.compile(r"^(Signed|Live)$")).first.wait_for(state="visible")
            pg.get_by_text(re.compile(r"Version|signed it|Signed by")).first.wait_for(state="visible")
        step("signed-state", "the intent shows a Signed pill and a version", signed)

        def lane():
            g = pg.get_by_role("group", name="Process map")
            g.wait_for(state="visible")
            for s in PROC["steps"]:
                g.get_by_role("button", name=f"Step {s['n']}: {s['name']}").wait_for(state="visible")
            for who in {s["who"] for s in PROC["steps"]}:
                g.get_by_text(who, exact=True).first.wait_for(state="visible")
            return f"{len(PROC['steps'])} steps, lanes {sorted({s['who'] for s in PROC['steps']})}"
        step("swimlane", "swim lane shows all 6 steps in order with a lane per owner (Mei Chen, Raj Patel, Daniel Foo)", lane)

        def systems():
            g = pg.get_by_role("group", name="Process map")
            for s in PROC["steps"]:
                g.get_by_text(s["system"], exact=True).first.wait_for(state="visible")
        step("systems", "each step card shows its system (File drop, Excel, Email, Report pack)", systems)

        def handovers():
            g = pg.get_by_role("group", name="Process map")
            txt = g.inner_text()
            miss = [f"To step {s['n'] + 1}" for s in PROC["steps"][:-1] if f"To step {s['n'] + 1}" not in txt]
            assert not miss, f"hand-overs missing: {miss}"
        step("handovers", "hand-overs 1-2, 2-3, 3-4, 4-5, 5-6 appear on the cards", handovers)

        def manual():
            g = pg.get_by_role("group", name="Process map")
            flagged = [s["n"] for s in PROC["steps"]
                       if g.get_by_role("button", name=f"Step {s['n']}: {s['name']}").get_by_text("Manual", exact=True).count()]
            assert flagged == PROC["manual_steps_flagged_for_automation"], f"manual flags on steps {flagged}, expected {PROC['manual_steps_flagged_for_automation']}"
            pg.get_by_text("Manual step", exact=True).first.wait_for(state="visible")  # the legend sits under the swim lane, not inside its group
            return f"manual flags on {flagged}"
        step("manual-flags", "steps 1-4 carry the Manual flag, steps 5-6 do not; legend explains it", manual)

        def sign_state():
            assert pg.get_by_role("button", name="That's right").is_disabled(), "confirm button should be disabled once signed"
        step("map-locked", "signed map cannot be re-confirmed (That's right is disabled)", sign_state)
        br.close()

    fails = [r for r in rows if not r[3]]
    md = [f"# {N}: UC9 sponsor sees the signed process swim lane (P32)", "", f"Result: {'FAIL' if fails else 'PASS'}", "",
          "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
    for i, (s, e, ac, ok, sh) in enumerate(rows, 1):
        md.append(f"| {i} | {s} | {e} | {ac.replace('|', '/')} | {'pass' if ok else 'FAIL'} | {sh} |")
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:3])); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
