"""UC4 charter 1 (P14): the benchmark gold table proposed by Span for an intent mentioning a benchmark, approved, run.
Usage: python uc4a_1.py --base URL --creds PATH --out DIR   (synthetic data).
Walk: Raj Patel (approver) tries Build and is turned back; Leo Park (data engineer) finds the plan with the benchmark gold table;
Anita Rao (head of data) approves it; Leo runs it in the sandbox; Raj looks for the September figures in Consume."""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

N = "uc4a_1"
ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
SEP = U["benchmark"]["september_2026"]
PEOPLE = {p["name"]: p["email"] for p in U["people"]}
BAD = re.compile(r"undefined|\[object|Traceback|Internal Server Error|\bNaN\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
TABLE = re.compile(r"gold_\w+_benchmark_monthly")


def shown(v):
    """A return in percent may be shown in full or to 2 dp."""
    return [v, f"{float(v):.2f}"]


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
        L = [f"# {N}: benchmark gold table, approve, run (P14)", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
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
    st = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch()

        # 1. Raj Patel, approver: the Build centre is not his; he is sent back to Action
        ctx, r.page = login(br, base, a.creds, "Raj Patel")
        page = r.page

        def raj_build():
            page.goto(f"{base}/centre/build")
            page.wait_for_load_state("networkidle")
            assert "/centre/build" not in page.url, f"approver was let into Build: {page.url}"
            assert page.get_by_role("link", name=re.compile("^build", re.I)).count() == 0, "Build is on the approver's bar"
            return f"turned back to {page.url.replace(base, '')}"
        r.step("approver-turned-back-from-build", "The approver (role table: Pulse, Intent, Consume) cannot open Build; lands on Action", raj_build)
        ctx.close()

        # 2. Leo Park, data engineer: find the plan with the benchmark gold table
        ctx, r.page = login(br, base, a.creds, "Leo Park")
        page = r.page

        def projects():
            page.goto(f"{base}/centre/build")
            page.get_by_role("heading", name="Build Centre").wait_for()
            page.locator("table a").first.wait_for()
            st["links"] = [l.get_attribute("href") for l in page.locator("table a").all()]
            assert st["links"], "no projects in Build"
            return f"{len(st['links'])} project(s)"
        r.step("build-projects", "Build Centre lists the office's projects", projects)

        def find_plan():
            for href in st["links"]:
                page.goto(base + href)
                page.wait_for_load_state("networkidle")
                m = TABLE.search(page.inner_text("body"))
                if m:
                    st["href"], st["table"] = href, m.group(0)
                    return f"{href} has {m.group(0)}"
            raise AssertionError("no project plan holds a gold_<project>_benchmark_monthly table: Span adds it only when the signed intent has a KPI mentioning a benchmark "
                                 "(the Evergreen intent has K01-K03 only) and a live plan cannot be proposed again from the screen")
        r.step("plan-has-benchmark-gold-table", "Span's plan holds gold_investment_report_benchmark_monthly (portfolio return, benchmark return, difference by month)", find_plan)

        def table_cols():
            assert st.get("href"), "not reached: no plan with a benchmark table"
            page.get_by_text(st["table"]).first.click()
            r.text("benchmark_code", "portfolio_return", "benchmark_return", "difference")
            return "columns benchmark_code, month, portfolio_return, benchmark_return, difference"
        r.step("benchmark-table-columns", "Opening the table shows its five columns and its SQL", table_cols)

        def state_waiting():
            # The seed (answer key P33) already has this plan Live, approved by Anita Rao; the 'Waiting' state is not in the seed.
            assert st.get("href"), "not reached"
            r.text("State: Live", "Approved by Anita Rao")
            return "plan is Live, approved by Anita Rao (seeded)"
        r.step("plan-state-approved", "Plan state reads 'Live' and 'Approved by Anita Rao' (seeded)", state_waiting)
        ctx.close()

        # 3. Anita Rao, head of data, approves (she is not the proposer). The seed has it approved already: no button, nothing to click.
        ctx, r.page = login(br, base, a.creds, "Anita Rao")
        page = r.page

        def approve():
            assert st.get("href"), "not reached"
            page.goto(base + st["href"])
            page.get_by_text(re.compile("Approved by Anita Rao")).first.wait_for()
            btn = page.get_by_role("button", name="Approve the plan")
            if btn.count() and btn.is_enabled():
                btn.click()
                page.get_by_text(re.compile("Approved by Anita Rao")).first.wait_for()
                return "Approved by Anita Rao (clicked)"
            return "Approved by Anita Rao (seeded; no approve button offered)"
        r.step("head-of-data-approves", "Anita Rao approves; the plan reads 'Approved by Anita Rao'", approve)
        ctx.close()

        # 4. Leo Park runs it in the sandbox
        ctx, r.page = login(br, base, a.creds, "Leo Park")
        page = r.page

        def run():
            assert st.get("href"), "not reached"
            page.goto(base + st["href"])
            page.get_by_role("button", name="Try it on a copy").click()
            line = page.get_by_text(re.compile(r"Sandbox run, plan version \d+")).first
            line.wait_for()
            line.click()
            r.text(st["table"])
            b = r.body()
            assert not re.search(r"Sandbox run, plan version \d+: (failed|error)", b, re.I), "the sandbox run failed"
            return re.search(r"Sandbox run, plan version \d+: \w+", b).group(0)
        r.step("sandbox-run", "Try it on a copy lists a run whose steps include the benchmark table, not failed", run)
        ctx.close()

        # 5. Raj Patel looks for the September figures in Consume
        ctx, r.page = login(br, base, a.creds, "Raj Patel")
        page = r.page

        def figures():
            page.goto(f"{base}/centre/consume")
            page.get_by_role("link", name=re.compile("^Benchmark$")).click()
            page.get_by_text("Portfolio against benchmark").first.wait_for()
            # the portfolio list is empty for this reader, so the code is typed (EG-LIQUID = Evergreen Liquid portfolio)
            page.locator("form input").first.fill("EG-LIQUID")
            page.get_by_role("button", name="Show").click()
            page.get_by_text(re.compile(r"2\.7072")).first.wait_for()  # the figures load after 'Working out the returns.'
            seen = r.body()
            want = ["blend_v1_return_pct", "sixty_forty_return_pct", "eg_liquid_portfolio_return_pct", "eg_liquid_minus_sixty_forty_pct"]
            miss = [SEP[k] for k in want if not any(x in seen for x in shown(SEP[k]))]
            assert not miss, f"figures not on screen: {miss}"
            return "benchmark figures shown"
        r.step("consume-benchmark-figures", "Consume shows 'portfolio vs benchmark': blend 2.7072, 60/40 2.2602, EG-LIQUID 4.1667, difference 1.9065", figures)
        ctx.close()
        ok = r.write()
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
