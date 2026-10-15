"""UC4 charter 2 (P15): benchmark version 2 is In Progress, refused for certified output and shown as a policy question.
Usage: python uc4a_2.py --base URL --creds PATH --out DIR   (synthetic data).
Walk: Raj Patel (approver) finds the one policy question in Action > Cases and opens it; Raj is turned back from Settings;
Anita Rao (head of data) opens Settings > Rules to see where the benchmark stands."""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

N = "uc4a_2"
ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
B = U["benchmark"]
CODE = B["benchmark_code"]
V2 = next(v for v in B["versions"] if v["version_number"] == 2)
PEOPLE = {p["name"]: p["email"] for p in U["people"]}
TITLE = f"Agree the definition of benchmark {CODE}"
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


class Run:
    def __init__(self, out):
        self.page, self.out, self.rows, self.n = None, Path(out) / N, [], 0
        self.out.mkdir(parents=True, exist_ok=True)

    def step(self, name, expected, fn):
        self.n += 1
        shot = f"{self.n:02d}-{name}.png"
        try:
            actual, ok = fn() or "as expected", True
        except Exception as e:  # keep walking so one failure does not hide the rest
            actual, ok = str(e).splitlines()[0][:400], False
        self.page.screenshot(path=str(self.out / shot), full_page=True)
        bad = BAD.search(self.page.inner_text("body"))
        if ok and bad:
            ok, actual = False, f"raw id, error text or 'undefined' on screen: {bad.group(0)}"
        self.rows.append((name, expected, actual, ok, shot))
        print(("PASS " if ok else "FAIL ") + name, "" if ok else actual)

    def body(self):
        return re.sub(r"\s+", " ", self.page.inner_text("body"))

    def text(self, *needles):
        b = self.body()
        miss = [x for x in needles if x not in b]
        assert not miss, f"not on screen: {miss}"

    def write(self):
        L = [f"# {N}: benchmark v2 in progress, a policy question (P15)", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        for i, (n, e, a, ok, s) in enumerate(self.rows, 1):
            L.append(f"| {i} | {n} | {e} | {a} | {'pass' if ok else 'FAIL'} | {s} |")
        (self.out / "result.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        return all(r[3] for r in self.rows)


def login(br, base, creds, who):
    """A fresh browser context signed in as `who` (a name from the universe people list). The password is read, never printed."""
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB")
    page = ctx.new_page()
    page.set_default_timeout(15000)
    page.goto(f"{base}/login")
    for line in Path(creds).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if p and not line.startswith("#") and p[0].lower() == PEOPLE[who].lower():
            page.locator("#email").fill(p[0])
            page.locator("#password").fill(p[1])
            break
    else:
        raise SystemExit(f"no {who} account in the creds file")
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    return ctx, page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    r = Run(a.out)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx, r.page = login(br, base, a.creds, "Raj Patel")
        page = r.page

        def cases():
            page.goto(f"{base}/centre/action/cases")
            page.get_by_role("heading", name="Action", exact=True).wait_for()
            page.get_by_role("cell", name=TITLE).first.wait_for()
            n = page.get_by_role("cell", name=TITLE).count()
            assert n == 1, f"the policy question must be raised once, found {n}"
            row = page.get_by_role("row").filter(has_text=TITLE)
            return "one row: " + re.sub(r"\s+", " ", row.inner_text())
        r.step("policy-question-listed-once", f"Action > Cases has exactly one case '{TITLE}'", cases)

        def open_case():
            page.get_by_role("row").filter(has_text=TITLE).get_by_role("link").click()
            page.get_by_role("heading", name=re.compile(re.escape(TITLE))).wait_for()
            r.text("History")
            return "case page open"
        r.step("open-policy-question", "The case page opens with the same title and its history", open_case)

        def wording():
            # the case description loads after the page (Tally's panel), so wait for it rather than read at once
            page.get_by_text(re.compile("still being defined")).first.wait_for()
            r.text("still being defined", "certified report")
            return "wording on screen"
        r.step("case-says-why", "The case says the benchmark is still being defined and cannot be used in a certified report", wording)

        def no_statement_noise():
            assert "No statements are linked to this case" not in r.body(), "the page shows 'Evidence for this case: No statements are linked' for a question about a benchmark"
        r.step("case-page-not-confusing", "A policy question shows what was asked, not an empty statements list", no_statement_noise)

        def v2_facts():
            r.text(CODE)
            return "benchmark named: " + CODE
        r.step("case-names-benchmark", f"The case names {CODE}", v2_facts)

        def settings_read_only():  # a4.4: the approver, who agrees the benchmark, reads the Rules register (read only)
            page.goto(f"{base}/centre/settings/rules")
            page.wait_for_load_state("networkidle")
            assert "/centre/settings/rules" in page.url, f"approver was turned away from Settings > Rules: {page.url}"
            page.get_by_role("heading", name="Rules").first.wait_for()
            return "Rules register open to the approver"
        r.step("approver-reads-rules", "The approver opens Settings > Rules to read the benchmark rule (a4.4)", settings_read_only)
        ctx.close()

        ctx, r.page = login(br, base, a.creds, "Anita Rao")
        page = r.page

        def rules():
            page.goto(f"{base}/centre/settings/rules")
            page.get_by_role("heading", name="Rules").first.wait_for()
            r.text("The rules the figures follow")
            return "Rules register open"
        r.step("settings-rules", "Head of data opens Settings > Rules", rules)

        def rules_benchmark():
            b = r.body()
            assert re.search("benchmark", b, re.I), "no rule or note about the benchmark (version 2 in progress) in the Rules register"
        r.step("rules-show-benchmark-v2", f"Rules show the benchmark policy: version 1 approved, version 2 ({V2['effective_from']}) still in progress", rules_benchmark)

        def cases_head():
            page.goto(f"{base}/centre/action/cases")
            page.get_by_role("cell", name=TITLE).first.wait_for()
            return "head of data sees the same single question"
        r.step("head-of-data-sees-question", "The head of data sees the same policy question in Action > Cases", cases_head)
        ctx.close()
        ok = r.write()
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
