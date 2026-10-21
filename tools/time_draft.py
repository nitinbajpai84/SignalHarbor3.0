"""Time the Decision 1 draft on a test server: post a message to a new thread, then say when each event, brief part and question
appeared, and which model calls ran (from the office's context/model_costs.jsonl and v3/skill_runs.jsonl).

    python tools/time_draft.py --port 8795 --data-root D:/Temp/sh3-draft-env [--mode testing|real] [--who grace]
                               [--text "..."] [--follow "a second message" --follow-at 8]

Signs in with the test office's seed credentials (never printed). Sets the office's model mode before the run. Prints one JSON report.
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEXT = "I want a performance report for the Indian funds against the NSE market index."
EMAIL = {"grace": "grace.ong", "anita": "anita.rao", "mei": "mei.chen", "daniel": "daniel.foo"}


class Http:
    def __init__(self, base: str):
        self.base, self.jar = base, CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method: str, path: str, body=None, timeout=600):
        csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), "")
        req = urllib.request.Request(self.base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"content-type": "application/json", "X-CSRF-Token": csrf})
        with self.op.open(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")


def _password(root: Path, email: str) -> str:
    for line in (root / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == email:
            return p[1]
    raise SystemExit(f"{email} is not in the seed credentials")


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _jsonl(p: Path, since: float) -> list[dict]:
    out = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("at") and _ts(r["at"]) >= since - 1:
                    out.append(r)
            except ValueError:
                pass
    return out


def run(a) -> dict:
    root = Path(a.data_root).resolve()
    plane_root = root / "evergreen"
    from sh_platform.plane import PlaneStore
    from sh_platform.v1 import router as R
    R.set_mode(PlaneStore(root).plane_for("evergreen").ensure(), a.mode, "time_draft")
    h = Http(f"http://127.0.0.1:{a.port}")
    email = f"{EMAIL[a.who]}.evergreen@example.test"
    h.call("POST", "/api/auth/login", {"email": email, "password": _password(root, email)})
    t0 = time.time()
    th = h.call("POST", "/api/v3/threads", {"text": a.text})
    tid, rel = th["id"], (lambda: round(time.time() - t0, 1))
    seen, marks, followed, quiet = set(), [], not a.follow, None
    marks.append({"t": rel(), "what": "thread created (POST returned)"})
    while time.time() - t0 < a.timeout:
        if not followed and time.time() - t0 >= a.follow_at:
            h.call("POST", f"/api/v3/threads/{tid}/say", {"text": a.follow})
            followed = True
            marks.append({"t": rel(), "what": f"follow-up sent: {a.follow[:60]}"})
        v = h.call("GET", f"/api/v3/threads/{tid}")
        for i, e in enumerate(v.get("events") or []):
            if ("e", i) not in seen:
                seen.add(("e", i))
                marks.append({"t": rel(), "what": f"event {e['kind']} ({e.get('by')}): {str(e.get('text') or e.get('chips'))[:90]}"})
        d = v.get("decision") or {}
        for g in ((d.get("brief") or {}).get("doc") or []):
            for ln in g.get("lines") or []:
                k = ("l", g.get("title"), ln.get("label"))
                if ln.get("value") and k not in seen:
                    seen.add(k)
                    marks.append({"t": rel(), "what": f"part {g.get('title')} / {ln.get('label')}" + (" (suggested)" if ln.get("suggested") else "")})
        for q in (d.get("gaps") or []) + [q.get("text") for q in d.get("questions") or [] if isinstance(q, dict)]:
            if ("q", q) not in seen:
                seen.add(("q", q))
                marks.append({"t": rel(), "what": f"open question: {str(q)[:90]}"})
        now = (v.get("now") or {}).get("name") if isinstance(v.get("now"), dict) else None
        if ("n", now) not in seen and now:
            seen.add(("n", now))
            marks.append({"t": rel(), "what": f"working: {now}"})
        busy = v.get("drafting") or now or v.get("stage") in ("drafting", "working")
        if busy or not followed:
            quiet = None
        else:
            quiet = quiet or time.time()
            if time.time() - quiet > a.settle:
                break
        time.sleep(0.5)
    end = rel()
    calls = [{"t": round(_ts(r["at"]) - t0, 1), "ms": r.get("latency_ms"), "agent": r.get("agent"), "task": r.get("task"),
              "model": r.get("model"), "tokens_out": r.get("tokens_out"), "usd": r.get("cost_usd")}
             for r in _jsonl(plane_root / "context" / "model_costs.jsonl", t0) if r.get("model")]
    skills = [{"t": round(_ts(r["at"]) - t0, 1), "skill": r["skill"], "ms": r.get("ms")}
              for r in _jsonl(plane_root / "v3" / "skill_runs.jsonl", t0) if r.get("thread") in (tid, None)]
    first_part = next((m["t"] for m in marks if m["what"].startswith("part ")), None)
    first_q = next((m["t"] for m in marks if m["what"].startswith("open question")), None)
    return {"thread": tid, "mode": a.mode, "first_part_s": first_part, "first_question_s": first_q, "done_s": round(end - a.settle, 1),
            "model_calls": len(calls), "usd": round(sum(c["usd"] or 0 for c in calls), 4), "stage": v.get("stage"),
            "marks": marks, "calls": sorted(calls, key=lambda c: c["t"]), "skills": skills}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--data-root", default="D:/Temp/sh3-draft-env")
    ap.add_argument("--mode", default="testing", choices=("testing", "real"))
    ap.add_argument("--who", default="grace", choices=sorted(EMAIL))
    ap.add_argument("--text", default=TEXT)
    ap.add_argument("--follow", help="a second message, sent while the first pass runs")
    ap.add_argument("--follow-at", type=float, default=8.0)
    ap.add_argument("--settle", type=float, default=6.0, help="seconds with nothing running before the run counts as done")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out", help="also write the report here")
    out = run(ap.parse_args())
    s = json.dumps(out, indent=1, default=str)
    if (o := ap.parse_args().out):
        Path(o).write_text(s, encoding="utf-8")
    print(s)


if __name__ == "__main__":
    main()
