"""UC5 run 2 browser helper: one headless Chromium per person, signed in through the real /login page.
W("leo").api(method, path, body) calls the same HTTP API the UI calls, with the person's session cookie and CSRF header.
Every call is appended to D:/Temp/uc5r2/calls.jsonl. Passwords are read from <env>/_control/seed_credentials.txt (or SH_DEMO_PASSWORD), never written."""
import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
BASE = os.environ.get("UC5_BASE", "http://127.0.0.1:8822")
CREDS = ROOT / ".sh-tmp/testenv/uc5-run2/data/_control/seed_credentials.txt"
OUT = ROOT / "docs/test/uc-live/uc5-run2-shots"; OUT.mkdir(parents=True, exist_ok=True)
LOG = Path("D:/Temp/uc5r2/calls.jsonl"); LOG.parent.mkdir(parents=True, exist_ok=True)
EMAIL = {k: f"{v}.evergreen@example.test" for k, v in dict(daniel="daniel.foo", mei="mei.chen", raj="raj.patel", sofia="sofia.reyes",
         anita="anita.rao", leo="leo.park", grace="grace.ong").items()}


def _pw(email):
    if os.environ.get("SH_DEMO_PASSWORD"):
        return os.environ["SH_DEMO_PASSWORD"]
    for l in CREDS.read_text(encoding="utf-8").splitlines():
        p = l.split()
        if p and p[0] == email:
            return p[1]
    raise KeyError(email)


_PW = None


class W:
    def __init__(s, who, dark=False):
        global _PW
        s.who = who
        _PW = _PW or sync_playwright().start()
        s.b = _PW.chromium.launch()
        s.ctx = s.b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark" if dark else "light")
        s.pg = s.ctx.new_page()
        s.pg.goto(BASE + "/login"); s.pg.fill("#email", EMAIL[who]); s.pg.fill("#password", _pw(EMAIL[who]))
        s.pg.keyboard.press("Enter"); s.pg.wait_for_timeout(2500)

    def go(s, path, wait=3000):
        s.pg.goto(BASE + path); s.pg.wait_for_timeout(wait); return s

    def shot(s, name):
        p = OUT / f"{name}.png"; s.pg.screenshot(path=str(p), full_page=True); return str(p)

    def text(s):
        return s.pg.inner_text("body")

    def api(s, method, path, body=None, files=None, timeout=300000):
        hdr = {"X-CSRF-Token": next((c["value"] for c in s.ctx.cookies() if c["name"] == "sh_csrf"), "")}
        if files is not None:
            r = s.ctx.request.fetch(BASE + path, method=method, multipart=files, timeout=timeout, headers=hdr)
        else:
            hdr["content-type"] = "application/json"
            r = s.ctx.request.fetch(BASE + path, method=method, data=json.dumps(body) if body is not None else None, timeout=timeout, headers=hdr)
        try: out = r.json()
        except Exception: out = r.text()[:2000]
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"who": s.who, "m": method, "p": path, "status": r.status, "body": body if files is None else "<multipart>",
                                "resp": out}, ensure_ascii=False, default=str) + "\n")
        return r.status, out

    def upload(s, path, source_code):
        p = Path(path)
        return s.api("POST", "/api/v1/intake/upload", files={
            "data": {"name": p.name, "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "buffer": p.read_bytes()},
            "filename": p.name, "source_code": source_code, "sensitivity": "internal"})

    def close(s):
        s.b.close()


def j(x, n=3000):
    s = json.dumps(x, ensure_ascii=True, default=str, indent=1)
    return s if len(s) <= n else s[:n] + " ...<cut>"
