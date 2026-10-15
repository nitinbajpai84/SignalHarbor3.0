"""UC3 charter 2 (P13): the same fund under two names shows one row; Settings > identifiers.
Usage: python uc3b_2.py --base URL --creds PATH --out DIR   (synthetic data; analyst Mei Chen)."""
import argparse, datetime, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

N = "uc3b_2"
ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
FUND = {f["key"]: f for f in U["funds"]}
MGR = {m["id"]: m for m in U["managers"]}
REV = {s["fund"]: s for s in U["statements"] if s["kind"] == "amended" and s["fund"] in ("A", "C", "H1")}
# the value each amended statement replaced: estimate for A, the earlier final for C and H1
OLD = {}
for k in REV:
    prev = [s for s in U["statements"] if s["fund"] == k and s["period_end"] == REV[k]["period_end"] and s["kind"] in ("estimate", "final") and s["value"]]
    OLD[k] = prev[-1]["value"]
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def money(v):
    return f"{int(float(v)):,}"


def when(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b %Y')}"


class Run:
    def __init__(self, page, out):
        self.page, self.out, self.rows, self.n = page, Path(out) / N, [], 0
        self.out.mkdir(parents=True, exist_ok=True)

    def step(self, name, expected, fn):
        self.n += 1
        shot = f"{self.n:02d}-{name}.png"
        try:
            actual, ok = fn() or "as expected", True
        except Exception as e:  # keep walking so one failure does not hide the rest
            actual, ok = str(e).splitlines()[0][:300], False
        try:
            self.page.screenshot(path=str(self.out / shot), full_page=True)
        except Exception as e:  # screenshot may fail in headless; record but continue
            print(f"WARNING: screenshot failed for {name}: {str(e)[:100]}")
            shot = f"{self.n:02d}-{name}-no-screenshot.txt"
            (self.out / shot).write_text(f"Screenshot failed: {str(e)[:300]}", encoding="utf-8")
        bad = BAD.search(self.page.inner_text("body"))
        if ok and bad:
            ok, actual = False, f"raw id, error text or 'undefined' on screen: {bad.group(0)}"
        self.rows.append((name, expected, actual, ok, shot))
        print(("PASS " if ok else "FAIL ") + name, "" if ok else actual)

    def text(self, *needles):
        body = re.sub(r"\s+", " ", self.page.inner_text("body"))
        miss = [x for x in needles if x not in body]
        assert not miss, f"not on screen: {miss}"

    def write(self):
        L = [f"# {N}: same fund under two names (P13)", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        for i, (n, e, a, ok, s) in enumerate(self.rows, 1):
            L.append(f"| {i} | {n} | {e} | {a} | {'pass' if ok else 'FAIL'} | {s} |")
        (self.out / "result.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        return all(r[3] for r in self.rows)


def login(page, base, creds):
    page.goto(f"{base}/login")
    for line in Path(creds).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if p and not line.startswith("#") and p[0].startswith("mei.chen.evergreen@"):
            page.locator("#email").fill(p[0])
            page.locator("#password").fill(p[1])
            break
    else:
        raise SystemExit("no Mei Chen account in the creds file")
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(lambda u: "/login" not in u, timeout=20000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    h1, b = FUND["H1"], FUND["B"]
    kr = MGR["MGR-KESTREL"]["name"]
    alias = [x for x in h1["identifiers"]["manager_email"]["manager_fund_name"] if x != h1["canonical_name"]][0]   # KR Macro Fund Ltd - Class B USD
    code = h1["identifiers"]["administrator"]["administrator_code"]
    b_alias = [x for x in b["identifiers"]["manager_email"]["manager_fund_name"] if x.startswith("Fund B - ") and x != f"Fund B - {b['canonical_name']}"][0]
    jul = REV["H1"]
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB").new_page()
        page.set_default_timeout(15000)
        r = Run(page, a.out)
        login(page, base, a.creds)
        r.step("signed-in", "Signed in as the analyst; the shell opens, not the login page", lambda: page.wait_for_selector("nav"))

        def inbox():
            page.goto(f"{base}/centre/action/managers")
            page.get_by_role("link", name=kr).wait_for()
            body = re.sub(r"\s+", " ", page.inner_text("body"))
            assert alias not in body, f"'{alias}' shows as its own row in the inbox"
            assert b_alias not in body and "Fund B - " not in body, f"'{b_alias}' shows in the inbox"
        r.step("inbox-no-alias-rows", f"Action > Managers shows neither '{alias}' nor '{b_alias}'", inbox)

        def one_row(mgr_name, fund_name):
            card = page.locator("li.ds-card", has=page.get_by_role("link", name=mgr_name)).first
            n = card.locator("li").filter(has=page.get_by_text(fund_name, exact=True)).count()
            assert n == 1, f"{mgr_name}: {n} rows for {fund_name}, expected exactly 1"
            return f"{mgr_name}: one row for {fund_name}"
        r.step("kestrel-one-row", f"{kr} card: exactly one row named {h1['canonical_name']} (and one for {FUND['H2']['canonical_name']})",
               lambda: (one_row(kr, h1["canonical_name"]), one_row(kr, FUND["H2"]["canonical_name"]))[0])
        r.step("bluewater-one-row", f"{MGR['MGR-BLUEWATER']['name']} card: exactly one row named {b['canonical_name']}", lambda: one_row(MGR["MGR-BLUEWATER"]["name"], b["canonical_name"]))

        def profile():
            page.get_by_role("link", name=kr).click()
            page.get_by_role("heading", name=kr).wait_for()
            page.get_by_text("Loading the manager.").wait_for(state="detached", timeout=30000)  # the profile loads after the heading
            funds = page.get_by_role("region", name="Funds")
            funds.get_by_text(h1["canonical_name"], exact=True).first.wait_for(timeout=20000)
            assert funds.locator("li").filter(has=page.get_by_text(h1["canonical_name"], exact=True)).count() == 1, "Funds list does not have exactly one Kestrel Ridge Macro Fund"
            r.text(h1["canonical_name"], FUND["H2"]["canonical_name"])
            assert alias not in re.sub(r"\s+", " ", page.get_by_role("region", name="Funds").inner_text()), "alias shown as a fund"
        r.step("kestrel-profile", f"Consume > Managers > {kr}: Funds lists {h1['canonical_name']} once, never the alias", profile)

        def timeline():
            sec = page.get_by_role("region", name="Statements")
            link = sec.get_by_role("link", name=re.compile(rf"^{re.escape(h1['canonical_name'])}, valued {re.escape(when(jul['period_end']))}"))
            assert link.count() >= 1, f"July amended statement is not filed under {h1['canonical_name']}"
            assert alias not in re.sub(r"\s+", " ", sec.inner_text()), "timeline names the fund by its alias"
        r.step("july-under-one-name", f"Statements timeline files the July amended statement under {h1['canonical_name']}, not '{alias}'", timeline)

        def evidence():
            page.get_by_role("region", name="Statements").get_by_role("link", name=re.compile(rf"^{re.escape(h1['canonical_name'])}, valued {re.escape(when(jul['period_end']))}")).first.click()
            page.get_by_role("heading", name=re.compile("valued")).wait_for()
            body = re.sub(r"\s+", " ", page.inner_text("body"))
            assert "is not matched to any fund yet" not in body, "the amended statement's name is not matched to a fund"
            assert f'"{alias}" to {h1["canonical_name"]}' in body, f"no match line from '{alias}' to {h1['canonical_name']}"
            return "match line shown: " + re.search(r'(Matched|Proposed match, not yet approved)[^.]*\.', body).group(0)
        r.step("evidence-match", f"July amended statement page says '{alias}' is matched to {h1['canonical_name']}", evidence)

        def settings():
            page.goto(f"{base}/centre/settings")
            nav = page.get_by_role("navigation", name="Settings")
            nav.wait_for()
            labels = [t.strip() for t in nav.locator("a").all_inner_texts()]
            link = nav.get_by_role("link", name=re.compile("identifier", re.I))
            assert link.count() >= 1, f"Settings has no identifiers section (sections: {', '.join(labels)})"
            link.first.click()
            page.get_by_role("table", name="Identifiers").wait_for(timeout=20000)  # it loads after the click ("Loading the identifiers.")
            r.text(h1["canonical_name"], alias, code)
            return f"identifiers shows {h1['canonical_name']}, {alias}, code {code}"
        r.step("settings-identifiers", f"Settings > identifiers lists {h1['canonical_name']} with its other name '{alias}' and administrator code {code}", settings)

        ok = r.write()
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
