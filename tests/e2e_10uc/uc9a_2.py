"""UC9 charter 2 (P32): sponsor previews and downloads the SOP of the signed month-end intent; manual steps flagged.
Usage: python uc9a_2.py --base URL --creds PATH --out DIR"""
import argparse, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

N = "uc9a_2"
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

        def preview():
            pg.get_by_role("link", name="Download the procedure").first.wait_for(state="visible")
            pg.get_by_role("button", name="Read the procedure here").click()
            pg.get_by_label("Procedure preview").wait_for(state="visible")
            pg.get_by_role("heading", name=re.compile(re.escape(PROC["project_title"]), re.I)).first.wait_for(state="visible")
        step("preview", "Read the procedure here opens a panel titled for the monthly investment report", preview)

        def roles():
            p = pg.get_by_label("Procedure preview"); t = p.inner_text()
            for who in {s["who"] for s in PROC["steps"]}:
                assert who in t, f"role {who} missing from the Roles line"
            assert "Purpose." in t and "Roles." in t
        step("roles", "Purpose and Roles lines name Mei Chen, Raj Patel and Daniel Foo", roles)

        def steps():
            items = pg.get_by_label("Procedure preview").get_by_role("listitem")
            names = [pg.get_by_label("Procedure preview").locator("ol > li").nth(i).locator("strong").first.inner_text() for i in range(6)]
            assert names == [s["name"] for s in PROC["steps"]], f"step names {names}"
            for i, s in enumerate(PROC["steps"]):
                t = pg.get_by_label("Procedure preview").locator("ol > li").nth(i).inner_text()
                for k, label in (("who", "Who"), ("system", "System")):
                    assert label in t and s[k] in t, f"step {s['n']}: '{label}: {s[k]}' missing"
                assert s["control"].rstrip(".") in t, f"step {s['n']}: control missing"
                assert s["exception"].rstrip(".") in t, f"step {s['n']}: exception missing"
                for part in ("Input", "Output"):  # a <dt>/<dd> pair: "Input" then the value on its own cell, no colon (SopPanel.tsx)
                    assert re.search(part + r":?\s+(?!Output|Control)\S", t), f"step {s['n']}: {part} empty"  # an empty <dd> runs into the next <dt>
            return "6 steps with owner, system, input, output, control and exception"
        step("six-steps", "6 steps in order, each with who, system, input, output, control and exception", steps)

        def manual():
            li = pg.get_by_label("Procedure preview").locator("ol > li")
            flagged = [i + 1 for i in range(6) if li.nth(i).get_by_text("Manual: could be automated").count()]
            assert flagged == PROC["manual_steps_flagged_for_automation"], f"manual flags on {flagged}"
            return f"manual flags on {flagged}"
        step("manual-flags", "steps 1-4 flagged 'Manual: could be automated'; 5 and 6 not", manual)

        def handovers():
            t = pg.get_by_label("Procedure preview").inner_text()
            miss = [f"Hand over to step {s['n'] + 1}" for s in PROC["steps"][:-1] if f"Hand over to step {s['n'] + 1}" not in t]
            assert not miss, f"missing {miss}"
        step("handovers", "hand-overs 1-2, 2-3, 3-4, 4-5, 5-6 listed", handovers)

        def download():
            with pg.expect_download() as d:
                pg.get_by_role("link", name="Download the procedure").first.click()
            dl = d.value
            name = dl.suggested_filename
            assert name.lower().endswith((".docx", ".md")), f"unexpected file name {name}"
            dest = out / name; dl.save_as(str(dest))
            data = dest.read_bytes(); assert len(data) > 1000, f"file only {len(data)} bytes"
            if name.lower().endswith(".docx"):
                assert data[:2] == b"PK", "not a .docx container"
                import zipfile
                xml = zipfile.ZipFile(dest).read("word/document.xml").decode("utf-8", "ignore")
                text = re.sub(r"<[^>]+>", " ", xml)
            else:
                text = data.decode("utf-8", "ignore")
            for s in PROC["steps"]:
                assert s["name"] in text, f"step '{s['name']}' missing from the file"
            assert not re.search(r"undefined|\[object", text), "undefined in the file"
            return f"{name}, {len(data)} bytes, all 6 step names present"
        step("download", "Download the procedure saves a .docx or .md that carries the six steps", download)

        def hide():
            pg.get_by_role("button", name="Hide the procedure").click()
            pg.get_by_label("Procedure preview").wait_for(state="detached")
        step("hide", "Hide the SOP closes the preview", hide)
        br.close()

    fails = [r for r in rows if not r[3]]
    md = [f"# {N}: UC9 Download the procedure (P32)", "", f"Result: {'FAIL' if fails else 'PASS'}", "",
          "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
    for i, (s, e, ac, ok, sh) in enumerate(rows, 1):
        md.append(f"| {i} | {s} | {e} | {ac.replace('|', '/')} | {'pass' if ok else 'FAIL'} | {sh} |")
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:3])); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
