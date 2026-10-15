"""UC6 run 2 helper: sign in as a person through the real login page, call the same HTTP API the screens call, take full-page screenshots.

    from uc6 import Person
    with Person("leo") as p:
        p.get("/api/v1/ops/runs")
        p.post("/api/v1/build/p/<pid>/run?mode=sandbox")
        p.shot("/centre/operations", "07-01-leo-runs")

Passwords are read from <env>/_control/seed_credentials.txt (or SH_DEMO_PASSWORD) and are never printed or written anywhere.
Every call is appended to D:/Temp/uc6r2/calls.jsonl (method, path, body, status, first 400 chars of the answer) as evidence.
"""
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("UC6_BASE", "http://127.0.0.1:8811")
REPO = Path(__file__).resolve().parents[4]
ENV = Path(os.environ.get("UC6_ENV", REPO / ".sh-tmp" / "testenv" / "uc6-run2" / "data"))
SHOTS = Path(os.environ.get("UC6_SHOTS", REPO / "docs" / "test" / "uc-live" / "uc6-run3-shots"))
SHOTS.mkdir(parents=True, exist_ok=True)
TMP = Path(os.environ.get("UC6_TMP", "D:/Temp/uc6r3"))
TMP.mkdir(parents=True, exist_ok=True)
PEOPLE = {"mei": "mei.chen", "daniel": "daniel.foo", "anita": "anita.rao", "leo": "leo.park", "sofia": "sofia.reyes", "raj": "raj.patel",
          "grace": "grace.ong"}


def _password(email: str) -> str:
    if os.environ.get("SH_DEMO_PASSWORD"):
        return os.environ["SH_DEMO_PASSWORD"]
    for line in (ENV / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0] == email:
            return parts[1]
    raise SystemExit(f"no password for {email}")


class Person:
    def __init__(self, who: str):
        self.who = who
        self.email = f"{PEOPLE[who]}.evergreen@example.test"

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        state = TMP / f"state-{self.who}.json"
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900},
                                            storage_state=str(state) if state.is_file() else None)
        self.page = self.ctx.new_page()
        if not self._signed_in():
            self.page.goto(BASE + "/login")
            self.page.fill("#email", self.email)
            self.page.fill("#password", _password(self.email))
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(2500)
            self.ctx.storage_state(path=str(state))
        return self

    def _signed_in(self) -> bool:
        r = self.ctx.request.get(BASE + "/api/auth/me") if self.ctx.cookies() else None
        return bool(r and r.status == 200)

    def __exit__(self, *a):
        self.browser.close()
        self.pw.stop()

    def call(self, method: str, path: str, body=None, timeout=300000, files=None):
        token = next((c["value"] for c in self.ctx.cookies() if c["name"] == "sh_csrf"), "")
        t0 = time.time()
        if files:
            r = self.ctx.request.fetch(BASE + path, method=method, multipart=files, headers={"X-CSRF-Token": token}, timeout=timeout)
        else:
            r = self.ctx.request.fetch(BASE + path, method=method, data=None if body is None else json.dumps(body),
                                       headers={"content-type": "application/json", "X-CSRF-Token": token}, timeout=timeout)
        try:
            out = r.json()
        except Exception:  # noqa: BLE001 - a non-JSON answer is kept as text
            out = r.text()[:2000]
        with open(TMP / "calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"who": self.who, "method": method, "path": path, "body": body if not files else "<multipart>", "status": r.status,
                                "secs": round(time.time() - t0, 1), "answer": json.dumps(out, default=str)[:400]}) + "\n")
        return r.status, out

    def get(self, path, **k):
        return self.call("GET", path, **k)

    def post(self, path, body=None, **k):
        return self.call("POST", path, body, **k)

    def put(self, path, body=None, **k):
        return self.call("PUT", path, body, **k)

    def upload(self, path, file: Path, fields: dict | None = None):
        files = {"data": {"name": file.name, "mimeType": "application/octet-stream", "buffer": file.read_bytes()}, "filename": file.name}
        files.update(fields or {})
        return self.call("POST", path, files=files)

    def shot(self, url: str, name: str, wait_ms: int = 3500) -> Path:
        if url:
            self.page.goto(BASE + url)
        self.page.wait_for_timeout(wait_ms)
        out = SHOTS / f"{name}.png"
        self.page.screenshot(path=str(out), full_page=True)
        return out

    def text(self) -> str:
        return self.page.inner_text("body")


def dump(name: str, obj) -> Path:
    p = TMP / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    return p
