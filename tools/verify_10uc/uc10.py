"""UC10 black-box checker (planted fact P33: pipeline and dashboard). Stdlib only; passwords are read, never printed or written.

python tools/verify_10uc/uc10.py --base http://127.0.0.1:8659 --creds PATH --out DIR
Writes DIR/uc10/<fact>.json and DIR/uc10/result.md; exit 1 if any fact fails. Every expected value comes from docs/test/10uc_universe.json.
"""
import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

U = json.loads((Path(__file__).resolve().parents[2] / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
P33 = next(p for p in U["planted"] if p["id"] == "P33")
PRJ = U["project"]
PEOPLE = {p["name"]: p for p in U["people"]}


class Client:
    def __init__(self, base, email, password):
        self.base = base.rstrip("/")
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ""
        st, _ = self.call("POST", "/api/auth/login", {"email": email, "password": password})
        if st != 200:
            raise SystemExit(f"login failed for {email}: HTTP {st}")

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "X-CSRF-Token": self.csrf})
        try:
            with self.op.open(req, timeout=60) as r:
                st, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            st, raw = e.code, e.read()
        try:
            return st, json.loads(raw or b"null")
        except ValueError:
            return st, {"raw": raw[:200].decode("utf-8", "replace")}


def load_creds(path):
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.startswith("#"):
            parts = ln.split()
            out[parts[0].lower()] = parts[1]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    creds, out = load_creds(a.creds), Path(a.out) / "uc10"
    out.mkdir(parents=True, exist_ok=True)
    clients = {}

    def who(name):
        if name not in clients:
            e = PEOPLE[name]["email"].lower()
            clients[name] = Client(a.base, e, creds[e])
        return clients[name]

    maker = next(n for n, p in PEOPLE.items() if p["platform_role"] == "analyst" and n == "Leo Park")  # the data engineer seat made the dashboard
    shared = re.search(r"shared with (.+?)\.?$", P33["expected"]).group(1).split(" and ")
    others = [n for n in PEOPLE if n not in shared and n != maker and PEOPLE[n]["platform_role"] not in ("company_admin",)]
    results = []

    def fact(name, expected, request, resp, actual, ok):
        results.append((name, expected, actual, ok))
        (out / f"{name}.json").write_text(json.dumps({"fact": name, "request": request, "response_excerpt": str(resp)[:1500], "expected": expected,
                                                      "actual": actual, "result": "pass" if ok else "fail"}, indent=1, default=str), encoding="utf-8")

    me = who(maker)
    st, js = me.call("GET", "/api/v1/build/projects")
    prj = next((p for p in (js or {}).get("projects", []) if p.get("title") == PRJ["title"]), None)
    fact("P33_project_live", {"title": PRJ["title"], "stage": PRJ["stage"]}, "GET /api/v1/build/projects", js,
         {"found": bool(prj), "stage": prj and prj["stage"]}, bool(prj) and prj["stage"] == PRJ["stage"])
    if not prj:
        for n in ("bronze_gold", "dashboard", "audience", "tile_data", "access"):
            fact(f"P33_{n}", "project must exist", "-", "-", "project not found", False)
    else:
        pid = prj["id"]
        st, js = me.call("GET", f"/api/v1/model/projects/{pid}/tables")
        got = {k: sorted((js or {}).get(k, [])) for k in ("bronze", "gold")}
        # the project's gold tables plus any the planted facts place in the Build plan (P14: the benchmark table, a4.3)
        planned = {t for p in U["planted"] for t in re.findall(r"gold_[a-z0-9_]+", str(p.get("where", ""))) if "Build plan" in str(p.get("where", ""))}
        want = {"bronze": sorted(PRJ["bronze"]), "gold": sorted(set(PRJ["gold"]) | planned)}
        fact("P33_bronze_gold", want, f"GET /api/v1/model/projects/{pid}/tables", js, got, got == want)

        base = f"/api/v1/consume/p/{pid}/dashboards/{PRJ['dashboard_id']}"
        st, js = me.call("GET", base)
        tiles = [t for t in (js or {}).get("tiles", []) if isinstance(t, dict)]
        want_t = sorted((t.split()[0], t.split(" ", 1)[1].rsplit(" (", 1)[0], t.rsplit("(", 1)[1].rstrip(")")) for t in PRJ["tiles"])
        got_t = sorted((t["id"], t["title"], t.get("kpi")) for t in tiles if t.get("state") == "accepted")
        fact("P33_dashboard", {"id": PRJ["dashboard_id"], "accepted_tiles (id, title, kpi)": want_t}, f"GET {base}", js,
             {"http": st, "accepted_tiles": got_t, "all_tiles": len(tiles)}, st == 200 and got_t == want_t and len(tiles) == len(want_t))

        aud = sorted(p["name"] for p in (js or {}).get("audience_people", []))
        fact("P33_audience", sorted(shared), f"GET {base} (audience_people)", (js or {}).get("audience_people"), aud, aud == sorted(shared))

        rows = {}
        for t in want_t:
            s, d = me.call("GET", f"{base}/tiles/{t[0]}/data")
            rows[t[0]] = {"http": s, "rows": len((d or {}).get("rows", [])), "error": (d or {}).get("message")}
        fact("P33_tile_data", {"each tile": "HTTP 200 with at least 1 row"}, f"GET {base}/tiles/<id>/data", rows, rows,
             all(r["http"] == 200 and r["rows"] > 0 for r in rows.values()))

        acc = {}
        for n in shared + [maker, "Grace Ong"]:
            acc[n] = who(n).call("GET", base)[0]
        for n in others:
            acc[n] = who(n).call("GET", base)[0]
        for n in others:  # a blocked role also gets no tile rows
            acc[n + " (tile data)"] = who(n).call("GET", f"{base}/tiles/{want_t[0][0]}/data")[0]
        okacc = all(acc[n] == 200 for n in shared + [maker, "Grace Ong"]) and all(v in (403, 404) for k, v in acc.items() if k.split(" (")[0] in others)
        fact("P33_access", {"200": shared + [maker, "Grace Ong (admin)"], "403": others}, f"GET {base} as each person", acc, acc, okacc)

    md = ["# UC10 result (P33)", "", "| fact | expected | actual | pass/fail |", "|---|---|---|---|"]
    for n, e, ac, ok in results:
        md.append(f"| {n} | {json.dumps(e, default=str)} | {json.dumps(ac, default=str)} | {'pass' if ok else 'FAIL'} |".replace("\n", " "))
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(f"{'pass' if ok else 'FAIL'}  {n}" for n, _, _, ok in results))
    sys.exit(0 if all(r[3] for r in results) else 1)


if __name__ == "__main__":
    main()
