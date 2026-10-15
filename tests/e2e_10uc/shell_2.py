"""Charter 2, Settings: agent runs and cost; Today card wording per kind (Revised, Break, Limit, Late, Shared).

Run: python tests/e2e_10uc/shell_2.py --base http://127.0.0.1:8714 --creds PATH --out DIR
Exit 1 on any failed assertion. Passwords are read from the creds file and never printed or saved.
"""
import argparse, json, re, sys, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui_copy import REFUSED  # noqa: E402  (the refusal line as the shell writes it today)

ROOT = Path(__file__).resolve().parents[2]
BAD = [r"\bundefined\b", r"\bNaN\b", r"\[object Object\]", r"Traceback", r"Internal Server Error",
       r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", r"\b(super_admin|company_admin)\b"]
RAW_KINDS = {"exception", "statement", "approval", "build", "share", "dashboard", "refresh", "load", "mapping", "document", "pipeline"}
AGENT_WORDS = ("North, the industry expert", "Span, the data engineer", "Lumen, the analyst", "Tally, the data analyst")


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


def login(page, base, name, cred):
    email, pw = cred[".".join(name.lower().split())]
    page.goto(base + "/login"); page.get_by_label("Email").fill(email); page.get_by_label("Password").fill(pw)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_url(re.compile(r"/centre/"), timeout=30000)
    page.get_by_role("navigation", name="Centres").wait_for(timeout=15000); page.wait_for_load_state("networkidle")


def cards(page):
    """Every Today card in both filters: (filter, status word, headline, rest of the card text)."""
    out = []
    for f in ("Needs me", "Worth a look"):
        page.get_by_role("button", name=f, exact=True).click(); page.wait_for_timeout(500)
        for li in page.get_by_role("listitem").filter(has=page.get_by_role("heading", level=2)).all():
            lines = [x.strip() for x in li.inner_text().splitlines() if x.strip()]
            if len(lines) >= 2: out.append((f, lines[0], lines[1], " ".join(lines[2:])))
    return out


def today(rec, page, who, uni, want):
    """want: list of (status word, regex the card text must match, figure from the universe or None)."""
    page.get_by_role("link", name="Today", exact=True).click(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
    on = page.get_by_role("heading", name="Action", exact=True).first.is_visible() and page.locator("a[aria-current='page']", has_text="Today").count() > 0
    rec.check(page, f"{who} opens Action > Today", "Action heading with the Today tab current (Today is a tab, not a heading)", on, page.url)
    cs = cards(page)
    rec.check(page, f"{who} Today cards (both filters)", "at least one card", len(cs) > 0, [f"{w}: {h}" for _, w, h, _ in cs])
    rec.check(page, f"{who} card words are plain", "no card shows an internal kind as its word", not [w for _, w, _, _ in cs if w.lower() in RAW_KINDS], sorted({w for _, w, _, _ in cs}))
    for word, rx, fig in want:
        hit = [c for c in cs if c[1].startswith(word) and re.search(rx, c[2] + " " + c[3], re.I) and (fig is None or fig in c[3] + c[2])]
        rec.check(page, f"{who} sees a '{word}' card" + (f" with {fig}" if fig else ""), f"word {word}, text /{rx}/", bool(hit),
                  hit[0][1:] if hit else [c[1:3] for c in cs if c[1].startswith(word)] or "none")
    # kind to word rules from ui/src/v1/e5/api.ts statusWord, checked on whatever cards exist
    for f, w, h, rest in cs:
        if re.match(r"limit breached", h, re.I): rec.check(page, f"{who} '{h}' reads Limit", "Limit", w == "Limit", w)
        if re.match(r"statement missing", h, re.I): rec.check(page, f"{who} '{h}' reads Late", "Late", w == "Late", w)
        if "Open dashboard" in rest or "dashboard" in h.lower() and "shared" in rest.lower(): rec.check(page, f"{who} dashboard card reads Shared or Refreshed", "Shared / Refreshed", w in ("Shared", "Refreshed"), w)
    rec.clean(page, f"{who} Today")
    return cs


def run(base, cred, out):
    rec = Rec(out, "shell_2")
    uni = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
    P = {p["id"]: p["expected"] for p in uni["planted"]}
    rev = re.search(r"\+([\d,]+)", P["P02"]).group(1)           # 180,000
    brk = re.search(r"([\d,]+) USD over", P["P08"]).group(1)    # 12,400
    with sync_playwright() as pw:
        br = pw.chromium.launch()

        def session(name):
            ctx = br.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); page.set_default_timeout(20000)
            login(page, base, name, cred); return ctx, page

        # ---- Today card wording, per person ----
        journeys = [("Daniel Foo", [("Revised", r"manager-reported valuation", rev)]),   # CIO: P02
                    ("Mei Chen", [("Break", r"a difference of", brk), ("Revised", r"manager-reported valuation", rev)]),  # Operations: P08, P02
                    ("Raj Patel", [("Break", r"a difference of", None)]),               # Finance
                    ("Sofia Reyes", [("Limit", r"above the signed limit|limit", None)])]  # Risk: P17
        for name, want in journeys:
            try:
                ctx, page = session(name)
                cs = today(rec, page, name, uni, want)
                if name == "Mei Chen":
                    page.get_by_role("link", name="Managers", exact=True).click(); page.wait_for_load_state("networkidle")
                    try:  # the inbox answers in about a second; read it once it is there
                        page.get_by_text("Kestrel Ridge").first.wait_for(timeout=15000)
                    except Exception:  # noqa: BLE001 - the check below reports it
                        pass
                    t = page.inner_text("body")
                    rec.check(page, "Mei Chen Managers shows lateness in plain days", r"'N day(s) late' or 'Received N days late'", bool(re.search(r"\d+ (?:business )?days? late", t)), re.findall(r"[^.\n]*\d+ (?:business )?days? late", t)[:3])
                    rec.check(page, "Mei Chen Managers names Kestrel Ridge", "Kestrel Ridge", "Kestrel Ridge" in t, "Kestrel Ridge" in t)
                    rec.clean(page, "Mei Chen Managers")
                if name == "Daniel Foo":
                    shared = [c for c in cs if c[1] in ("Shared", "Refreshed")]
                    rec.check(page, "Daniel Foo has a Shared card for the dashboard (P33)", "Shared card, dashboard shared with Daniel Foo", bool(shared),
                              shared[0][1:3] if shared else "not on screen: appears only after the dashboard is shared in the run", soft=True)
                ctx.close()
            except Exception:
                rec.check(page, f"{name} Today journey", "completes", False, " ".join(traceback.format_exc().split())[-300:]); ctx.close()

        # ---- Settings > Agent runs and cost ----
        for name, mode in (("Grace Ong", "admin"), ("Mei Chen", "analyst"), ("Daniel Foo", "refused")):
            try:
                ctx, page = session(name)
                page.get_by_role("button", name="Account menu").click()
                if mode == "refused":
                    rec.check(page, f"{name} account menu has no Settings", "no Settings link", page.get_by_role("link", name="Settings", exact=True).count() == 0, "absent")
                    page.goto(base + "/centre/settings/runs"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
                    t = page.inner_text("body")
                    rec.check(page, f"{name} typed Settings address is refused", "back on Action with a plain sentence", page.url.rstrip("/").endswith("/centre/action") and REFUSED in t, page.url)
                    rec.clean(page, f"{name} refused Settings"); ctx.close(); continue
                page.get_by_role("link", name="Settings", exact=True).click(); page.wait_for_load_state("networkidle")
                page.get_by_role("navigation", name="Settings").get_by_role("link", name="Agent runs and cost").click(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
                sec = page.get_by_role("region", name="Agent runs and cost")
                rec.check(page, f"{name} opens Agent runs and cost", "section with its explanation", sec.get_by_text("what it cost").is_visible(), page.url)
                if mode == "analyst":  # the server decides: either the data or one plain sentence, never a raw error
                    alert = sec.get_by_role("alert")
                    txt = alert.inner_text() if alert.count() else "runs shown"
                    rec.check(page, f"{name} gets runs or one plain sentence", "runs, or a sentence without codes", not re.search(r"\b(403|500|forbidden|exception)\b", txt, re.I), txt)
                    rec.clean(page, f"{name} Agent runs"); ctx.close(); continue
                table = sec.get_by_role("table", name="Runs by agent and day")
                if table.count():
                    heads = [h.strip() for h in table.get_by_role("columnheader").all_inner_texts()]
                    rec.check(page, "Grace Ong runs table columns", "Agent, Day, Runs, Failed, Tool calls, Cost", heads == ["Agent", "Day", "Runs", "Failed", "Tool calls", "Cost"], heads)
                    rows = [[c.strip() for c in r.get_by_role("cell").all_inner_texts()] for r in table.get_by_role("row").all()[1:]]
                    rec.check(page, "Grace Ong agents named with their role", "North / Span / Lumen with role words", all(r[0] in AGENT_WORDS for r in rows), [r[0] for r in rows])
                    rec.check(page, "Grace Ong cost is a figure or 'Not available yet', never zero", "USD 0.1234 or Not available yet", all(re.fullmatch(r"USD \d+\.\d{4}|Not available yet", r[5]) and r[5] != "USD 0.0000" for r in rows), [r[5] for r in rows])
                    rec.check(page, "Grace Ong counts are whole numbers", "runs, failed, tool calls are digits", all(r[2].isdigit() and r[3].isdigit() and r[4].isdigit() for r in rows), [r[2:5] for r in rows])
                    rec.check(page, "Grace Ong failed runs list present", "Failed runs heading", sec.get_by_role("heading", name="Failed runs").is_visible(), "visible")
                else:
                    rec.check(page, "Grace Ong sees an honest empty state", "No agent runs yet.", sec.get_by_text("No agent runs yet.").is_visible(), "empty state", soft=True)
                rec.clean(page, "Grace Ong Agent runs")
                day = sec.get_by_label("Day").first  # a day with nothing in it
                day.fill("2020-01-01")
                try:  # the runs load after the day changes; wait for the empty-day line rather than a fixed pause
                    sec.get_by_text("No agent runs on that day.").wait_for(timeout=10000)
                except Exception:
                    pass
                rec.check(page, "Grace Ong filters to a quiet day", "No agent runs on that day.", sec.get_by_text("No agent runs on that day.").is_visible(), sec.inner_text()[-120:])
                day.fill(""); page.wait_for_timeout(800)
                for sect in ("People and access", "Rules", "Templates and skills", "Signed register", "Testing or Real use", "What the agents remember about you"):
                    page.get_by_role("navigation", name="Settings").get_by_role("link", name=sect).click(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(500)
                    rec.check(page, f"Grace Ong Settings > {sect}", "section opens", page.get_by_role("region", name=sect).is_visible(), page.url)
                    rec.clean(page, f"Grace Ong {sect}")
                ctx.close()
            except Exception:
                rec.check(page, f"{name} Settings journey", "completes", False, " ".join(traceback.format_exc().split())[-300:]); ctx.close()
        br.close()
    rec.write(["Charter 2: Settings agent runs and cost; Today card wording per kind (Revised, Break, Limit, Late, Shared).",
               f"Figures read from docs/test/10uc_universe.json: P02 change {rev}, P08 break {brk}. 'note' rows are findings and do not fail the run."])
    return rec.failed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for f in ("--base", "--creds", "--out"): ap.add_argument(f, required=True)
    a = ap.parse_args()
    sys.exit(1 if run(a.base.rstrip("/"), creds(a.creds), a.out) else 0)
