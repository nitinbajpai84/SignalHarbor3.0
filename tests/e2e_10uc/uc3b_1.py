"""UC3 charter 1 (P12): revised statements count and timeline for A, C, H1.
Usage: python uc3b_1.py --base URL --creds PATH --out DIR   (synthetic data; analyst Mei Chen)."""
import argparse, datetime, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

N = "uc3b_1"
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
        L = [f"# {N}: revised statements, count and timeline (P12)", "", "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
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
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB").new_page()
        page.set_default_timeout(15000)
        r = Run(page, a.out)
        login(page, base, a.creds)
        r.step("signed-in", "Signed in as the analyst; the shell opens, not the login page", lambda: page.wait_for_selector("nav"))

        # Action > Managers: counts and the A revision
        def inbox():
            page.goto(f"{base}/centre/action/managers")
            page.get_by_role("link", name=MGR["MGR-NORTHGATE"]["name"]).wait_for()
            r.text(*[m["name"] for m in MGR.values()], "revised")
        r.step("action-managers", "Managers tab lists every manager, each with 'N expected · N received · N late · N revised'", inbox)

        a_name = FUND["A"]["canonical_name"]

        def a_row():
            li = page.locator("li", has=page.get_by_text(a_name, exact=True)).last
            t = re.sub(r"\s+", " ", li.inner_text())
            assert "Revised once" in t, f"A row has no 'Revised once': {t[:200]}"
            assert f"USD {money(REV['A']['value'])}" in t, f"A last value is not the amended {money(REV['A']['value'])}: {t[:240]}"
            return f"A shows 'Revised once' and last value {money(REV['A']['value'])}"
        r.step("fund-a-revised", f"{a_name}: Revised once; last value USD {money(REV['A']['value'])} (amended, not the {money(OLD['A'])} estimate)", a_row)

        def northgate_count():
            card = page.locator("li.ds-card", has=page.get_by_role("link", name=MGR["MGR-NORTHGATE"]["name"])).first
            t = re.sub(r"\s+", " ", card.inner_text())
            assert re.search(r"\b1 revised", t), f"Northgate count is not '1 revised': {t[:200]}"
        r.step("northgate-count", "Northgate Partners card says 1 revised", northgate_count)

        # Consume > Managers statements timeline for each revised fund, then the evidence page
        for key in ("A", "C", "H1"):
            s, f = REV[key], FUND[key]
            mname = MGR[f["manager"]]["name"]
            label = re.compile(rf"^{re.escape(f['canonical_name'])}, valued {re.escape(when(s['period_end']))}")

            def timeline(s=s, f=f, mname=mname, label=label):
                page.goto(f"{base}/centre/consume/managers")
                page.get_by_role("link", name=mname).click()
                page.get_by_role("heading", name=mname).wait_for()
                li = page.get_by_role("region", name="Statements").locator("li", has=page.get_by_role("link", name=label)).filter(has_text="replaces an earlier statement")
                assert li.count() >= 1, f"no 'replaces an earlier statement' line for {f['canonical_name']} valued {when(s['period_end'])}"
                t = re.sub(r"\s+", " ", li.first.inner_text())
                assert f"received {when(s['received_at'])}" in t, f"want received {when(s['received_at'])} in: {t}"
                assert "final" in t and "replaced by a later one" not in t, t
                return t
            r.step(f"timeline-{key}", f"{mname} > Statements: {f['canonical_name']} valued {when(s['period_end'])}, received {when(s['received_at'])}, final, replaces an earlier statement", timeline)

            def evidence(s=s, key=key, label=label):
                page.get_by_role("region", name="Statements").get_by_role("link", name=label).first.click()
                page.get_by_role("heading", name=re.compile("valued")).wait_for()
                r.text(money(s["value"]), money(OLD[key]))
                return f"evidence page shows amended {money(s['value'])} and original {money(OLD[key])}"
            r.step(f"evidence-{key}", f"Statement link opens the original/amended view: {money(OLD[key])} and {money(s['value'])}", evidence)

        ok = r.write()
        br.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
