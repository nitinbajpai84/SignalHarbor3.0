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
    sent = []
    page.on("request", lambda q: sent.append((q.method, q.url)) if q.method != "GET" or re.search(r"send|mail|smtp", q.url, re.I) else None)
    late = [s for s in STM if s["late_business_days"] and s["kind"] != "missing"]  # H2 Aug, E Jun, D Mar (P10)
    missing = next(s for s in U["statements"] if s["kind"] == "missing")  # D Jun (P11)
    d = FUNDS[missing["fund"]]
    mgr = MGRS[d["manager"]]
    r.step("Open Action > Managers", "inbox with the managers", lambda: (open_managers(page, base), (True, "inbox shown"))[1])

    for s in late:
        f = FUNDS[s["fund"]]; m = MGRS[f["manager"]]; n = s["late_business_days"]

        def check(s=s, f=f, m=m, n=n):
            click(page.get_by_role("link", name=m["name"], exact=True).first)
            page.get_by_role("heading", name="Statements and revisions").wait_for(timeout=30000)
            line = page.evaluate(LI, [f["canonical_name"], rf"valued {rx(s['period_end'])}"]) or ""
            ok_recv = has(line, rf"received {rx(s['received_at'])}")
            ok_late = has(line, rf"\b{n}\b[^.]{{0,25}}late|late[^.]{{0,25}}\b{n}\b")
            return ok_recv and ok_late, f"received date shown={ok_recv}; '{n} late' wording shown={ok_late}; line: {line[:160]}"
        r.step(f"Late statement: {f['canonical_name']} {s['period_end']} on the {m['name']} page",
               f"received {s['received_at'][:10]}, due {s['due_date']}, {n} business days late (P10)", check)
        page.goto(base + "/centre/action/managers"); page.wait_for_selector("li.ds-card", timeout=30000)

    def inbox_late():
        card = page.evaluate(CARD, mgr["name"]) or ""
        block = re.search(rf"Still missing: the statement for {rx(missing['period_end'])}, due {rx(missing['due_date'])}[^\n]*", card, re.I)
        txt = block.group(0) if block else card[:200]
        return bool(block) and has(txt, r"\b63\b"), f"found={bool(block)}; text: {txt}"
    r.step("Missing statement on the Cedarpoint card", f"Still missing: {d['canonical_name']} 30 Jun 2026, due 14 Jul 2026, 63 business days overdue (P11)", inbox_late)

    box = page.locator("li.ds-card").filter(has=page.get_by_role("heading", name=mgr["name"], exact=True))
    def draft():
        click(box.get_by_role("button", name="Draft a follow-up"))
        ta = box.get_by_label(re.compile("Draft email", re.I)); ta.wait_for(timeout=15000)
        t = ta.input_value()
        miss = [w for w in (mgr["contact_name"], d["canonical_name"], rx(missing["period_end"]), rx(missing["due_date"])) if not has(t, w)]
        extra = [FUNDS[k]["canonical_name"] for k in FUNDS if k != "D" and FUNDS[k]["canonical_name"] in t]
        return not miss and not extra, f"missing from draft: {miss}; other funds named: {extra}; first lines: {t[:200]!r}"
    r.step("Draft a follow-up", "email draft addressed to Hana Sato, naming Cedarpoint Opportunities II and 30 Jun 2026, no other fund (P11)", draft)

    r.step("Labelled not sent", "'Draft email (not sent)' label and the note that it has not been sent; a Copy the draft button",
           lambda: (has(box.inner_text(), r"has not been sent") and box.get_by_role("button", name="Copy the draft").is_visible() and has(box.inner_text(), r"not sent"), box.inner_text()[-160:]))

    def copy():
        click(box.get_by_role("button", name="Copy the draft"))
        box.get_by_text("Copied.").wait_for(timeout=8000)
        clip = page.evaluate("navigator.clipboard.readText()")
        return has(clip, "Cedarpoint Opportunities II"), f"Copied shown; clipboard {len(clip)} characters"
    r.step("Copy the draft", "Copied. appears and the draft is on the clipboard", copy)

    r.step("Nothing was sent", "the only non-GET request is the follow-up draft; no send or mail request",
           lambda: (all(re.search(r"/managers/[^/]+/followup", u) for _, u in sent) and not any(re.search(r"send|mail|smtp", u, re.I) for _, u in sent), f"{len(sent)} request(s): " + ", ".join(f"{m} {u.split('/api')[-1]}" for m, u in sent)))
    r.hygiene()


if __name__ == "__main__":
    session(args(), 2, "UC3 late and missing statements, follow-up for Fund D (P10, P11)", body)
