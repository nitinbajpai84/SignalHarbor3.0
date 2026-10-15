import argparse, datetime, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
FUNDS = {f["key"]: f for f in U["funds"]}
MGRS = {m["id"]: m for m in U["managers"]}
STM = [s for s in U["statements"] if not (s.get("note") or "").startswith("Not loaded")]  # what the seed really holds
BAD = [r"undefined", r"\bNaN\b", r"\[object", r"Traceback", r"Internal Server Error", r"That did not go through",
       r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", r"\bnull\b", r"\bError\b", r"Exception"]


def rx(iso):
    """'2026-09-30' -> regex for '30 Sep 2026' (en-GB may print 'Sept')."""
    d = datetime.date.fromisoformat(iso[:10])
    return rf"{d.day}\s+{d.strftime('%b')}[a-z]*\.?\s+{d.year}"


def has(text, pattern):
    return re.search(pattern, text or "", re.I) is not None


def bad_text(text):
    return [p for p in BAD if re.search(p, text)]


class Run:
    def __init__(self, n, title, out):
        self.title, self.dir, self.rows, self.i, self.page = title, pathlib.Path(out) / f"uc3a_{n}", [], 0, None
        self.dir.mkdir(parents=True, exist_ok=True)

    def step(self, name, expected, fn=None):
        """fn() -> (ok, actual). A screenshot is taken first, so a failure still leaves a picture."""
        self.i += 1
        shot = f"{self.i:02d}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]}.png"
        try:
            self.page.screenshot(path=str(self.dir / shot), full_page=True)
            ok, actual = fn() if fn else (True, "done")
        except Exception as e:  # noqa: BLE001
            ok, actual = False, f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
        self.rows.append((name, expected, str(actual).replace("\n", " ")[:600], ok, shot))
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else " -> " + str(actual)[:200]))
        return ok

    def hygiene(self, name="No raw ids, errors or 'undefined' on screen"):
        return self.step(name, "no uuid, 'undefined', 'null', NaN or error text in the visible page",
                         lambda: (lambda b: (not b, f"found {b}" if b else "clean"))(bad_text(self.page.inner_text("body"))))

    def finish(self):
        fails = [r for r in self.rows if not r[3]]
        md = [f"# {self.title}", "", f"Result: {'FAIL' if fails else 'PASS'} ({len(self.rows) - len(fails)}/{len(self.rows)} steps passed)", "",
              "| # | Step | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|"]
        for i, (n, e, a, ok, s) in enumerate(self.rows, 1):
            md.append("| %d | %s | %s | %s | %s | %s |" % (i, n, e.replace("|", "/"), a.replace("|", "/"), "pass" if ok else "FAIL", s))
        (self.dir / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return 1 if fails else 0


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True); p.add_argument("--creds", required=True); p.add_argument("--out", required=True)
    return p.parse_args()


def credentials(path, who="mei.chen."):
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not line.startswith("#") and parts[0].startswith(who):
            return parts[0], parts[1]
    raise SystemExit("no sign-in for " + who + " in the creds file")


def login(page, base, email, password):
    page.goto(base)
    page.get_by_label(re.compile("email", re.I)).fill(email)
    page.get_by_label(re.compile("password", re.I)).fill(password)
    page.evaluate("document.querySelector('form').requestSubmit()")
    page.wait_for_selector("#email", state="detached", timeout=30000)


def click(loc):
    try:
        loc.click(timeout=8000)
    except Exception:  # noqa: BLE001  plain clicks have timed out on this box
        loc.evaluate("e => e.click()")


def open_managers(page, base):
    """Through the Action centre tab when the nav is there, else by address."""
    try:
        click(page.get_by_role("link", name="Action", exact=True).first)
        click(page.get_by_role("link", name="Managers", exact=True).first)
        page.wait_for_url("**/action/managers", timeout=8000)
    except Exception:  # noqa: BLE001
        page.goto(base + "/centre/action/managers")
    page.wait_for_selector("li.ds-card", timeout=30000)


LI = """([name, pat]) => { const re = new RegExp(pat, 'i');
  const l = [...document.querySelectorAll('li')].filter(e => e.innerText.includes(name) && re.test(e.innerText));
  l.sort((a, b) => a.innerText.length - b.innerText.length); return l[0] ? l[0].innerText : null; }"""
CARD = "(name) => { const c = [...document.querySelectorAll('li.ds-card')].find(e => e.querySelector('h2') && e.querySelector('h2').innerText === name); return c ? c.innerText : null; }"


def session(a, n, title, body, phone=False):
    r = Run(n, title, a.out)
    email, pw = credentials(a.creds)
    base = a.base.rstrip("/")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
        r.page = page = ctx.new_page()
        try:
            def open_login():
                page.goto(base)
                page.wait_for_selector("#email", timeout=30000)
                return page.get_by_label(re.compile("email", re.I)).is_visible() and page.get_by_label(re.compile("password", re.I)).is_visible(), "sign-in form shown"
            r.step("Open the sign-in page", "email and password fields are visible", open_login)
            r.step("Sign in as Mei Chen (operations analyst)", "the sign-in form goes away and the app opens",
                   lambda: (login(page, base, email, pw), (True, "signed in"))[1])
            body(r, page, base)
        finally:
            code = r.finish()
            b.close()
    sys.exit(code)


def body(r, page, base):
    sep = r"\s*·\s*"
    sept = {f: [s for s in STM if s["fund"] == f and s["period_end"] == "2026-09-30"] for f in FUNDS if f != "LIQ"}
    due = "2026-10-14"
    asof = U["meta"]["as_of"]

    r.step("Open Action, then the Managers tab", "Action page with a Managers tab, six managers listed",
           lambda: (open_managers(page, base), (all(has(page.inner_text("body"), m["name"]) for m in MGRS.values()), "managers: " + ", ".join(m["name"] for m in MGRS.values() if has(page.inner_text("body"), m["name"]))))[1])
    r.step("Heading and tab", "page titled Action, tab link Managers marked as current",
           lambda: (page.get_by_role("heading", name="Action").first.is_visible() and page.get_by_role("link", name="Managers", exact=True).first.get_attribute("aria-current") == "page", "heading and current tab found"))

    def counts():
        miss = []
        for m in MGRS.values():
            ks = [k for k in m["funds"] if k in sept]
            exp, rec = len(ks), sum(1 for k in ks if sept[k])
            card = page.evaluate(CARD, m["name"]) or ""
            if not has(card, rf"{exp} expected{sep}{rec} received{sep}0 late"):
                miss.append(f"{m['name']}: want {exp} expected / {rec} received / 0 late, card says: {card.splitlines()[1:2]}")
        return not miss, "; ".join(miss) or "all six counts match the universe"
    r.step("Counts per manager", "each manager card reads N expected, M received, 0 late for September (P09)", counts)

    def received():
        miss = []
        for k, rows in sept.items():
            f = FUNDS[k]
            line = page.evaluate(LI, [f["canonical_name"], "Statement for"]) or ""
            if not rows:
                if not (has(line, "Not due yet") and has(line, rf"due {rx(due)}")):
                    miss.append(f"{k} {f['canonical_name']}: want Not due yet, due 14 Oct 2026; got: {line[:160]}")
                continue
            first = min(r_["received_at"] for r_ in rows)
            if not (has(line, r"Received") and has(line, rf"due {rx(due)}") and has(line, rf"received {rx(first)}") and has(line, rx("2026-09-30"))):
                miss.append(f"{k} {f['canonical_name']}: want Received {first[:10]}, due 14 Oct 2026; got: {line[:160]}")
        return not miss, "; ".join(miss) or "every fund shows period 30 Sep 2026, due 14 Oct 2026 and its received date"
    r.step("Expected vs received per fund", "A 2 Oct, B 1 Oct, E 8 Oct, H1 6 Oct, H2 7 Oct, L1 and L2 1 Oct received; due 14 Oct 2026 (P09)", received)

    def waiting():
        out = []
        for k in ("C", "D"):
            line = page.evaluate(LI, [FUNDS[k]["canonical_name"], "Statement for"]) or ""
            if not (has(line, "Not due yet") and not has(line, r", received \d") and not has(line, r"Late \d")):
                out.append(f"{k}: {line[:150]}")
        return not out, "; ".join(out) or "C and D read Not due yet, not late"
    r.step("C and D are waiting, not late", "Cedarpoint Ventures III and Opportunities II show Not due yet", waiting)

    def unverified():
        l = page.evaluate(LI, [FUNDS["E"]["canonical_name"], "Statement for"]) or ""
        # P07: Fund A's last value is the confirmed amended statement, so it reads Revised; H1 and H2 are still estimates
        want = {"A": "revised", "H1": "estimate", "H2": "estimate"}
        w = [k for k, word in want.items() if not has(page.evaluate(LI, [FUNDS[k]["canonical_name"], "Statement for"]) or "", word)]
        return has(l, "unverified") and not w, f"E: {l[-80:]}; wrong status wording for {w}"
    r.step("Status words on the last value", "E shows unverified; A shows Revised (P07); H1, H2 show the estimate status", unverified)

    def nothing_late():
        wrong = []
        for m in MGRS.values():
            card = page.evaluate(CARD, m["name"]) or ""
            enabled = page.locator("li.ds-card").filter(has=page.get_by_role("heading", name=m["name"])).get_by_role("button", name="Draft a follow-up").count() == 1  # hidden when nothing is late
            chased = m["id"] == "MGR-CEDARPOINT"  # fund D June is the only missing statement in the universe
            if chased != enabled or (not chased and not has(card, "Nothing is late")):
                wrong.append(f"{m['name']}: button shown={enabled}")
        return not wrong, "; ".join(wrong) or "only Cedarpoint can draft a follow-up; the others say Nothing is late"
    r.step("Follow-up button state", "button on only where something is overdue (Cedarpoint, D June); others say Nothing is late", nothing_late)

    r.step("Dates and as-of", f"statement period is September 2026 (as of {asof}); no figure shown as zero where missing",
           lambda: (has(page.inner_text("body"), rx("2026-09-30")) and not has(page.inner_text("body"), r"USD 0(\.00)?\b"), "30 Sep 2026 shown, no USD 0"))
    r.hygiene()


if __name__ == "__main__":
    session(args(), 1, "UC3 analyst: Action > Managers, September expected vs received (P09)", body)
