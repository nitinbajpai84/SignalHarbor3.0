"""Film 9 ("A day at Evergreen Office"): start builds as their people and wait out the drafting, off camera.

    python tools/video/film9_stage.py start ops_clerk          # start that role's first suggested build via the API, as that person
    python tools/video/film9_stage.py wait cio hr_admin ...    # poll until each role's build has left drafting (run as a background shell)
    python tools/video/film9_stage.py show                     # one line per role: thread and stage

Drafting takes 2 to 5 minutes, so the film records the finished brief afterwards and the narration says Harbor drafted it.
A build is found the way the Desk finds it (GET /api/v3/me/role, "started"); `start` never starts a second one.
Office: the film office behind http://127.0.0.1:8640 (SH_FILM9_BASE, SH_FILM9_OFFICE). Passwords are read from the office's
seed_credentials.txt, held in memory only, never printed. Writes docs/video/out/film9/stage.json.
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ.get("SH_FILM9_BASE", "http://127.0.0.1:8640")
OFFICE = Path(os.environ.get("SH_FILM9_OFFICE", "D:/Temp/sh3-film"))
ROLES = {r["id"]: r for r in yaml.safe_load((ROOT / "packs/family_office/1/role_builds.yaml").read_text(encoding="utf-8"))["roles"]}
STATE = ROOT / "docs/video/out/film9/stage.json"
LIMIT = 30 * 60


def email_of(role: str) -> str:
    return ROLES[role]["person"].lower().replace(" ", ".") + ".evergreen@example.test"


def password(email: str) -> str:
    for line in (OFFICE / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == email and not line.startswith("#"):
            return p[1]
    raise SystemExit(f"no seeded account {email}")


class Person:
    """A signed-in API session (cookies in memory)."""

    def __init__(self, role: str):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        em = email_of(role)
        self.call("POST", "/api/auth/login", {"email": em, "password": password(em)})

    def call(self, method: str, path: str, body=None):
        csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), "")
        req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "X-CSRF-Token": csrf})
        with self.op.open(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")


def thread_of(p: Person) -> str | None:
    builds = p.call("GET", "/api/v3/me/role").get("builds") or []
    return builds[0].get("started") if builds else None


def save(role: str, **kv) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    s = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    s.setdefault(role, {}).update(kv)
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def start(role: str) -> None:
    p = Person(role)
    tid = thread_of(p)
    if not tid:
        tid = p.call("POST", "/api/v3/threads", {"text": ROLES[role]["builds"][0]["say"]})["id"]
        print(role, "started", tid, flush=True)
    else:
        print(role, "already started", tid, flush=True)
    save(role, thread=tid)


def wait(roles: list[str]) -> None:
    ps = {r: Person(r) for r in roles}
    t0, left = time.time(), set(roles)
    while left and time.time() - t0 < LIMIT:
        for r in sorted(left):
            try:
                tid = thread_of(ps[r])
                stage = ps[r].call("GET", f"/api/v3/threads/{tid}")["stage"] if tid else "not started"
            except (urllib.error.URLError, OSError, KeyError) as e:
                print(time.strftime("%H:%M:%S"), r, "poll failed:", str(e)[:80], flush=True)
                continue
            save(r, thread=tid, stage=stage)
            if stage not in ("drafting", "not started"):
                print(time.strftime("%H:%M:%S"), r, "drafted:", stage, flush=True)
                left.discard(r)
        if left:
            time.sleep(10)
    print("DONE" if not left else f"TIMEOUT {sorted(left)}", flush=True)


def show() -> None:
    for r in ROLES:
        p = Person(r)
        tid = thread_of(p)
        print(r, tid, p.call("GET", f"/api/v3/threads/{tid}")["stage"] if tid else "-")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["show"]
    {"start": lambda: [start(r) for r in args], "wait": lambda: wait(args), "show": show}[cmd]()
