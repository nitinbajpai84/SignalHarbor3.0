"""UC9 black-box checker: planted fact P32 (SOP from the signed process map).
python tools/verify_10uc/uc9.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Writes DIR/uc9/P32.json and DIR/uc9/result.md; exit 1 if any check fails. Passwords are read from the creds file and never written."""
import argparse, http.cookiejar, json, re, sys, urllib.error, urllib.request
from decimal import Decimal  # noqa: F401  (no money in P32; kept for the shared pattern)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
FACT = next(p for p in U["planted"] if p["id"] == "P32")
NOT_STATED = "Not stated yet"


class Client:
    def __init__(self, base):
        self.base, self.jar = base.rstrip("/"), http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            with self.op.open(req, timeout=30) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def json(self, method, path, body=None):
        s, raw, _ = self.call(method, path, body)
        try:
            return s, json.loads(raw)
        except ValueError:
            return s, None


def creds(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            p = line.split()
            out[p[0].lower()] = p[1]
    return out


def login(base, pw_by_email, person):
    c = Client(base)
    s, _ = c.json("POST", "/api/auth/login", {"email": person["email"], "password": pw_by_email[person["email"].lower()]})
    return c if s == 200 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True), ap.add_argument("--creds", required=True), ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / "uc9"
    out.mkdir(parents=True, exist_ok=True)
    pw, people = creds(a.creds), {p["name"]: p for p in U["people"]}
    proc, rows, ev = U["process"], [], {}

    def check(name, expected, actual, ok=None):
        ok = (expected == actual) if ok is None else ok
        rows.append({"check": name, "expected": expected, "actual": actual, "pass": bool(ok)})

    sponsor = login(a.base, pw, people[proc["sponsor"]])
    if not sponsor:
        check("sponsor signs in", "200", "login failed")
        return finish(out, rows, ev)
    s, pj = sponsor.json("GET", "/api/v1/projects")
    proj = next((p for p in (pj or {}).get("projects", []) if p.get("title") == proc["project_title"]), None)
    check("signed intent found by title", proc["project_title"], proj and proj.get("title"))
    if not proj or not proj.get("intent_id"):
        return finish(out, rows, ev)
    iid = proj["intent_id"]
    path = f"/api/v1/intents/{iid}/sop"
    s, sop = sponsor.json("GET", path)
    ev["request"], ev["status"] = f"GET {path} as {proc['sponsor']} (sponsor)", s
    ev["response_excerpt"] = sop and {k: sop[k] for k in ("title", "signed", "manual_steps", "open_points") if k in sop}
    check("sponsor reads the SOP", 200, s)
    if s != 200 or not sop:
        return finish(out, rows, ev)
    steps = sop["steps"]
    check("step count", len(proc["steps"]), len(steps))
    for u, g in zip(proc["steps"], steps):
        n = u["n"]
        for f_u, f_g in (("name", "name"), ("who", "who"), ("system", "system"), ("control", "control"), ("exception", "exception")):
            check(f"step {n} {f_u}", u[f_u], g.get(f_g))
        for f in ("input", "output"):
            check(f"step {n} {f} stated", "not '%s'" % NOT_STATED, g.get(f), g.get(f) not in (None, "", NOT_STATED))
    check("manual steps flagged", proc["manual_steps_flagged_for_automation"], sop["manual_steps"])
    check("manual flag per step", [u["manual"] for u in proc["steps"]], [g["manual"] for g in steps])
    want = [(i, i + 1) for i in range(1, len(proc["steps"]))]
    got = sorted((g["n"], h["to_step"]) for g in steps for h in g["handovers"])
    check("hand-overs", want, got)

    # downloads: .md always; docx when the server has python-docx, else the server sends Markdown
    s, raw, hd = sponsor.call("GET", path + "/download?format=md")
    text = raw.decode("utf-8", "replace")
    check("download .md status", 200, s)
    check("download .md disposition", "attachment; filename=*.md", hd.get("Content-Disposition"),
          s == 200 and bool(re.search(r'filename="[^"]+\.md"', hd.get("Content-Disposition") or "")))
    for u in proc["steps"]:
        check(f"md has step {u['n']} '{u['name']}'", True, u["name"] in text)
    check("md flags 4 manual steps", 4, text.count("manual: a candidate for automation"))
    s, raw, hd = sponsor.call("GET", path + "/download?format=docx")
    cd = hd.get("Content-Disposition") or ""
    check("download docx request", "200 with .docx (Word) or .md fallback", f"{s} {cd}",
          s == 200 and (raw[:2] == b"PK" and ".docx" in cd or ".md" in cd))
    ev["docx_served_as"] = "docx" if raw[:2] == b"PK" else "md fallback"

    # who sees it: every named company role reads it; nobody signed out does
    for name, p in people.items():
        c = login(a.base, pw, p)
        st = c.call("GET", path)[0] if c else "login failed"
        check(f"{name} ({p['platform_role']}) reads", 200, st)
    st = Client(a.base).call("GET", path)[0]
    check("signed-out caller refused", "401 or 403", st, st in (401, 403))
    st = Client(a.base).call("GET", path + "/download?format=md")[0]
    check("signed-out download refused", "401 or 403", st, st in (401, 403))
    st = sponsor.call("GET", "/api/v1/intents/no-such-intent/sop")[0]
    check("unknown intent has no SOP", "404 (or 403)", st, st in (403, 404))
    return finish(out, rows, ev)


def finish(out, rows, ev):
    ok = all(r["pass"] for r in rows)
    (out / "P32.json").write_text(json.dumps({"fact": "P32", "expected": FACT["expected"], **ev, "checks": rows,
                                              "pass": ok}, indent=2, default=str), encoding="utf-8")
    md = ["# UC9 result", "", "| fact | check | expected | actual | pass |", "|---|---|---|---|---|"]
    for r in rows:
        cell = lambda x: str(x).replace("|", "/").replace("\n", " ")[:120]
        md.append(f"| P32 | {cell(r['check'])} | {cell(r['expected'])} | {cell(r['actual'])} | {'pass' if r['pass'] else 'FAIL'} |")
    md += ["", f"P32: {'pass' if ok else 'FAIL'}"]
    (out / "result.md").write_text("\n".join(md), encoding="utf-8")
    print(f"P32 {'pass' if ok else 'FAIL'} ({sum(r['pass'] for r in rows)}/{len(rows)})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
