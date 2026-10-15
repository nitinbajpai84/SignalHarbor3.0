"""Post module-1-demo.mp4 into one session's briefing video slot (local only; no code change needed).

Usage:  python docs/guides/m1/post-video.py <32-character session id> [email]
The password is read from data/_control/seed_credentials.txt and is never printed.
Works while the session is a draft, in the lobby or in the briefing (before the rooms open).
"""
import http.cookiejar
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8200"
sid = sys.argv[1]
email = sys.argv[2] if len(sys.argv) > 2 else "company_admin.lakeside-family-office@example.test"
pw = next(l.split()[1] for l in (ROOT / "data/_control/seed_credentials.txt").read_text().splitlines() if l.startswith(email))
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    try:
        with op.open(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


code, _ = call("POST", "/api/auth/login", json.dumps({"email": email, "password": pw}).encode(), {"Content-Type": "application/json"})
assert code == 200, f"sign-in failed ({code})"
csrf = next((c.value for c in jar if c.name == "sh_csrf"), "")
video = (pathlib.Path(__file__).parent / "module-1-demo.mp4").read_bytes()
print(call("PUT", f"/api/modules/m1_intent/sessions/{sid}/briefing/video", video,
           {"Content-Type": "video/mp4", "X-CSRF-Token": csrf}))
