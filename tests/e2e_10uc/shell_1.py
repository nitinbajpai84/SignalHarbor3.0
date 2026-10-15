"""Charter 1, Shell: each role sees the right centres in the bar; a role without access gets a plain refusal.

Run: python tests/e2e_10uc/shell_1.py --base http://127.0.0.1:8714 --creds PATH --out DIR
Exit 1 on any failed assertion. Passwords are read from the creds file and never printed or saved.
"""
import argparse, json, re, sys, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui_copy import REFUSED, bar_for  # noqa: E402  (the refusal line and the bars as the UI source has them today)

ROOT = Path(__file__).resolve().parents[2]
BAD = [r"\bundefined\b", r"\bNaN\b", r"\[object Object\]", r"Traceback", r"Internal Server Error",
       r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", r"\b(super_admin|company_admin)\b"]
FORM = "document.querySelector('form').requestSubmit()"
# Bar per platform role, read from ui/src/shell/roles.ts (9 Oct: every role has the Map)
BARS = {r: bar_for(r) for r in ("sponsor", "approver", "participant", "analyst", "company_admin")}
PATHS = {"Build": "/centre/build", "Consume": "/centre/consume", "Map": "/centre/map"}
REFUSAL = re.compile(re.escape(REFUSED) + r"|You do not have access to this")


class Rec:
    def __init__(self, out, name):
        self.dir = Path(out) / name; self.dir.mkdir(parents=True, exist_ok=True)
        self.name, self.rows, self.n, self.failed = name, [], 0, False

    def check(self, page, step, expected, ok, actual, soft=False):
        self.n += 1
        f = f"{self.n:02d}-{re.sub(r'[^a-z0-9]+', '-', step.lower()).strip('-')[:60]}.png"
        try:  # a page already closed by a failed journey must not stop the run
            page.screenshot(path=str(self.dir / f))
        except Exception:  # noqa: BLE001
            pass
        res = "pass" if ok else ("note" if soft else "FAIL")
        self.failed |= res == "FAIL"
        self.rows.append((step, str(expected), str(actual).replace("\n", " ")[:300], res, f)); print(f"[{res}] {step}: {actual}"[:220])

    def clean(self, page, step):
        text = page.inner_text("body")
        hits = [p for p in BAD if re.search(p, text)]
        self.check(page, step + " has no raw id or error text", "no raw ids, error text or 'undefined'", not hits, hits or "clean")

    def write(self, intro):
        md = [f"# {self.name}", "", *intro, "", "| Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|"]
        md += [f"| {s} | {e.replace('|', '/')} | {a.replace('|', '/')} | {r} | {f} |" for s, e, a, r, f in self.rows]
        md += ["", "Overall: " + ("FAIL" if self.failed else "PASS")]
        (self.dir / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def creds(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 4 and not line.startswith("#") and p[3] == "evergreen":
            out[p[0].split(".evergreen@")[0]] = (p[0], p[1])
    return out


def login(page, base, email, pw):
    page.goto(base + "/login"); page.get_by_label("Email").fill(email); page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(re.compile(r"/centre/"), timeout=30000)
    page.get_by_role("navigation", name="Centres").wait_for(timeout=15000); page.wait_for_load_state("networkidle")


def bar(page):
    return [t.strip() for t in page.get_by_role("navigation", name="Centres").get_by_role("link").all_inner_texts() if t.strip()]


def run(base, cred, out):
    rec = Rec(out, "shell_1")
    uni = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
    who = [(p["name"], p["platform_role"]) for p in uni["people"] if p["platform_role"] in BARS]
    # one person per role is enough, plus Mei (analyst with Operations work)
    seen, picks = set(), []
    for n, r in who:
        if n == "Mei Chen" or (r not in seen and n not in ("Anita Rao", "Leo Park")):
            picks.append((n, r)); seen.add(r)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for name, role in picks:
            want, key = BARS[role], ".".join(name.lower().split())
            ctx = br.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); page.set_default_timeout(20000)
            try:
                if key not in cred:
                    rec.check(page, f"{name} has an account", "in creds file", False, "missing"); continue
                login(page, base, *cred[key])
                rec.check(page, f"{name} ({role}) lands on Action", "/centre/action", page.url.rstrip("/").endswith("/centre/action"), page.url)
                got = bar(page)
                rec.check(page, f"{name} bar shows {', '.join(want)}", want, got == want, got)
                rec.check(page, f"{name} sees own name in the bar", name, page.get_by_text(name, exact=True).first.is_visible(), "visible")
                rec.clean(page, f"{name} landing")
                for c in want:  # every centre in the bar opens, none refuses
                    page.get_by_role("navigation", name="Centres").get_by_role("link", name=c, exact=True).click()
                    page.wait_for_load_state("networkidle"); page.wait_for_timeout(500)
                    rec.check(page, f"{name} opens {c}", "opens without a refusal", not REFUSAL.search(page.inner_text("body")), page.url)
                    rec.clean(page, f"{name} in {c}")
                for c in [x for x in PATHS if x not in want]:  # typed address of a centre the role does not hold
                    page.goto(base + PATHS[c]); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
                    t = page.inner_text("body"); m = REFUSAL.search(t)
                    rec.check(page, f"{name} typed address for {c}", "refused in plain words, centre not shown", bool(m) or not page.url.rstrip("/").endswith(PATHS[c]), f"{page.url} | {m.group(0) if m else 'no refusal text'}")
                    rec.clean(page, f"{name} refused {c}")
                    rec.check(page, f"{name} bar unchanged after refusal for {c}", want, bar(page) == want, bar(page))
                page.get_by_role("button", name="Account menu").click()
                admin = role in ("analyst", "company_admin")
                has = page.get_by_role("link", name="Settings", exact=True).count() > 0
                rec.check(page, f"{name} account menu Settings", "Settings" if admin else "no Settings", has == admin, has)
                rec.check(page, f"{name} account menu has Sign out", "Sign out", page.get_by_role("button", name="Sign out").is_visible(), "visible")
            except Exception:
                rec.check(page, f"{name} journey", "completes", False, traceback.format_exc().splitlines()[-1])
            ctx.close()
        br.close()
    rec.write(["Charter 1: each role sees the right centres in the bar; a role without access gets a plain refusal.",
               "Expected bars follow ui/src/shell/roles.ts (barFor). 'note' rows are findings and do not fail the run."])
    return rec.failed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for f in ("--base", "--creds", "--out"): ap.add_argument(f, required=True)
    a = ap.parse_args()
    sys.exit(1 if run(a.base.rstrip("/"), creds(a.creds), a.out) else 0)
