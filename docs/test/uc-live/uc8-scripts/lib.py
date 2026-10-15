"""UC8 run 2 helper: headless Chromium signed in as one person through the real /login, plus the same-session API caller.
Passwords are read from the env's _control/seed_credentials.txt (or SH_DEMO_PASSWORD) at run time; never written anywhere."""
import json, os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="ascii", errors="replace")
ROOT = Path(__file__).resolve().parents[4]
BASE = os.environ.get("UC8_BASE", "http://127.0.0.1:8813")
ENV = ROOT / ".sh-tmp/testenv/uc8-run2"
SRC = ROOT / "docs/demo/uc8/sources"
OUT = ROOT / "docs/test/uc-live/uc8-run2-shots"
LOG = ENV / "api"; LOG.mkdir(parents=True, exist_ok=True)
def _cred():
    out = {}
    for l in (ENV / "data/_control/seed_credentials.txt").read_text().splitlines():
        if l and not l.startswith("#"):
            p = l.split(); out[p[0].split(".")[0]] = (p[0], os.environ.get("SH_DEMO_PASSWORD") or p[1])
    return out
CRED = _cred()
def st(k, v=None):
    p = ENV / "state.json"; d = json.loads(p.read_text()) if p.exists() else {}
    if v is None: return d.get(k)
    d[k] = v; p.write_text(json.dumps(d, indent=1)); return v
def rec(**kw):
    with open(ENV / "run-log.jsonl", "a", encoding="utf-8") as f: f.write(json.dumps(kw, ensure_ascii=False, default=str) + "\n")
def keep(name, obj):
    (LOG / f"{name}.json").write_text(json.dumps(obj, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
class W:
    def __init__(s, who):
        s.who = who; s.t0 = time.time()
        s.pw = sync_playwright().start(); s.b = s.pw.chromium.launch()
        s.ctx = s.b.new_context(viewport={"width": 1440, "height": 900})
        s.pg = s.ctx.new_page(); e, p = CRED[who]
        s.pg.goto(BASE + "/login"); s.pg.fill("#email", e); s.pg.fill("#password", p); s.pg.keyboard.press("Enter"); s.pg.wait_for_timeout(2500)
    def go(s, path, wait=2500): s.pg.goto(BASE + path); s.pg.wait_for_timeout(wait)
    def shot(s, name, full=True):
        s.pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full); print("shot", name); return f"uc8-run2-shots/{name}.png"
    def api(s, method, path, body=None, files=None):
        h = {"X-CSRF-Token": next((c["value"] for c in s.ctx.cookies() if c["name"] == "sh_csrf"), "")}
        if files:
            r = s.ctx.request.fetch(BASE + path, method=method, multipart=files, headers=h, timeout=300000)
        else:
            h["content-type"] = "application/json"
            r = s.ctx.request.fetch(BASE + path, method=method, data=json.dumps(body) if body is not None else None, timeout=300000, headers=h)
        try: return r.status, r.json()
        except Exception: return r.status, r.text()[:600]
    def upload(s, path, field, f, extra=None):
        f = Path(f); mime = "text/csv" if f.suffix == ".csv" else ("application/pdf" if f.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        parts = {field: {"name": f.name, "mimeType": mime, "buffer": f.read_bytes()}}; parts.update(extra or {})
        return s.api("POST", path, files=parts)
    def text(s): return s.pg.inner_text("body")
    def buttons(s): return [x.inner_text().strip() for x in s.pg.locator("button").all() if x.is_visible() and x.inner_text().strip()]
    def secs(s): return round(time.time() - s.t0)
    def close(s): s.b.close(); s.pw.stop()
