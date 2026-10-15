"""UC8 black-box checker: planted facts P28-P31 (trade and FX forward breaks, matched trades).

    python tools/verify_10uc/uc8.py --base http://127.0.0.1:8657 --creds PATH --out DIR

Logs in over HTTP as the roles the facts name, runs the real recon route, reads the cases, compares figures as Decimal against
docs/test/10uc_universe.json. Writes DIR/uc8/<fact>.json and DIR/uc8/result.md. Exit 1 if any fact fails. Passwords are never printed or written.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
RUN_DAY = "2026-10-09"
D = Decimal


class Client:
    def __init__(self, base):
        self.base, self.jar = base.rstrip("/"), CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None):
        h = {"Content-Type": "application/json"}
        csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), None)
        if csrf:
            h["X-CSRF-Token"] = csrf
        req = urllib.request.Request(self.base + path, method=method, headers=h, data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.op.open(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"raw": raw[:200].decode("utf-8", "replace")}


def creds(path):
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if len(p) >= 4 and "@" in p[0] and not ln.startswith("#"):
            out[p[0]] = p[1]
    return out


def login(base, cr, person):
    key = ".".join(person.lower().split()) + "."
    em = next((e for e in cr if e.startswith(key)), None)
    if not em:
        return None, f"no credentials for {person}"
    c = Client(base)
    st, _ = c.call("POST", "/api/auth/login", {"email": em, "password": cr[em]})
    return (c, None) if st == 200 else (None, f"login failed for {person}: HTTP {st}")


PERSON = {"analyst": "Mei Chen"}  # role word in the planted list -> person in tools/seed_evergreen.py


def amt(case):
    v = case.get("candidate_impact_amount", case.get("amount"))
    return None if v is None else D(str(v).replace(",", ""))


def brief(c):
    return {k: c.get(k) for k in ("number", "title", "exception_type", "status", "candidate_impact_amount", "impact_currency", "description")} if c else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / "uc8"
    out.mkdir(parents=True, exist_ok=True)
    cr = creds(a.creds)
    P = {p["id"]: p for p in U["planted"] if p["use_case"] == "UC8"}
    trades = {t["id"]: t for t in U["trades_oct"]}
    fx = {f["id"]: f for f in U["fx_forwards"]}
    results = {}

    def rec(fid, expected, actual, ok, request=None, response=None, notes=""):
        results[fid] = {"fact": fid, "title": P[fid]["fact"], "request": request, "response_excerpt": response, "expected": expected,
                        "actual": actual, "pass": bool(ok), "notes": notes}

    cli, err = login(a.base, cr, PERSON[P["P28"]["role"]])
    if err:
        for fid in P:
            rec(fid, "login as " + P[fid]["role"], err, False)
    else:
        req = {"method": "POST", "path": "/api/v1/recon/trade_vs_admin/run", "body": {"as_of_date": RUN_DAY}}
        st, run = cli.call("POST", req["path"], req["body"])
        st2, cl = cli.call("GET", "/api/v1/cases?exception_type=break")
        cases = cl.get("cases", []) if st2 == 200 and isinstance(cl, dict) else []
        trade_cases = [c for c in cases if str(c.get("title", "")).startswith("Trade ")]
        run = run if isinstance(run, dict) else {}
        ex = {"run_status": st, "checked": run.get("checked"), "breaks": run.get("breaks"), "cases_status": st2,
              "trade_case_titles": [c.get("title") for c in trade_cases]}

        def find(tid):
            return [c for c in cases if tid in str(c.get("title", ""))]

        # P28 quantity mismatch
        t = trades["T-20261002-003"]
        want = (D(t["quantity"]) - D(t["administrator_quantity"])) * D(t["price"])
        assert want == D(t["difference_usd"]), "universe is inconsistent for P28"
        cs = find(t["id"])
        c = cs[0] if cs else {}
        ok = len(cs) == 1 and c.get("exception_type") == "break" and amt(c) == want and str(c.get("title", "")).startswith("Trade differs")
        rec("P28", f"one break case 'Trade differs' for {t['id']}, impact {want} USD (over tolerance 5000)", brief(c) or "no case", ok, req, ex | {"case": brief(c)})
        # P29 missing at administrator
        t = trades["T-20261006-005"]
        want = D(t["amount"])
        cs = find(t["id"])
        c = cs[0] if cs else {}
        ok = len(cs) == 1 and c.get("exception_type") == "break" and amt(c) == want and str(c.get("title", "")).startswith("Trade not matched")
        rec("P29", f"one break case 'Trade not matched' for {t['id']}, impact {want} USD", brief(c) or "no case", ok, req, ex | {"case": brief(c)})
        # P30 FX confirmation mismatch
        f2, f1 = fx["FXF-2026-002"], fx["FXF-2026-001"]
        sgd = D(f2["confirmation_buy_amount"]) - D(f2["buy_amount"])
        usd = D(f2["difference_usd_at_8_oct"])
        assert sgd == D(f2["difference_sgd"])
        cs, cs1 = find(f2["id"]), find(f1["id"])
        c = cs[0] if cs else {}
        got, ccy = (amt(c), c.get("impact_currency")) if c else (None, None)
        ok = len(cs) == 1 and not cs1 and c.get("exception_type") == "break" and ((got == sgd and ccy == "SGD") or (got == usd and ccy == "USD"))
        rec("P30", f"one break case for {f2['id']}, difference SGD {sgd} (or USD {usd}); none for {f1['id']}",
            {"case": brief(c) or "no case", "cases_for_FXF-2026-001": len(cs1)}, ok, req, ex | {"case": brief(c)})
        # P31 matched trades: no case
        ids = [t["id"] for t in U["trades_oct"] if t["result"] == "matched"]
        hits = {i: len(find(i)) for i in ids}
        planted = {"T-20261002-003", "T-20261006-005", "FXF-2026-002"}
        other = [c.get("title") for c in trade_cases if not any(p in c.get("title", "") for p in planted)]
        ok = all(v == 0 for v in hits.values()) and ids == ["T-20261001-001", "T-20261002-002", "T-20261007-006"]
        rec("P31", f"no case for {ids}", {"cases_per_trade": hits, "other_trade_cases": other}, ok, req, ex, "other_trade_cases is information, not a failure")
        # who may not run: POST run allows company_admin and analyst only; GET runs is open to every company role (e3b.permissions.yaml)
        for person, role in (("Raj Patel", "approver"), ("Sofia Reyes", "participant"), ("Daniel Foo", "sponsor")):
            c2, e2 = login(a.base, cr, person)
            for fid in results:
                if e2:
                    results[fid].setdefault("access", []).append({"role": role, "result": e2, "pass": False})
                    results[fid]["pass"] = False
                    continue
            if e2:
                continue
            s, _ = c2.call("POST", "/api/v1/recon/trade_vs_admin/run", {"as_of_date": RUN_DAY})
            s2, _ = c2.call("GET", "/api/v1/recon/runs")
            good = s == 403 and s2 == 200
            for fid in results:
                results[fid].setdefault("access", []).append({"role": role, "run": s, "runs": s2, "expected": "403/200", "pass": good})
                results[fid]["pass"] = results[fid]["pass"] and good
        s, _ = Client(a.base).call("GET", "/api/v1/cases")
        for fid in results:
            results[fid].setdefault("access", []).append({"role": "no sign-in", "cases": s, "expected": "401/403", "pass": s in (401, 403)})
            results[fid]["pass"] = results[fid]["pass"] and s in (401, 403)

    rows = ["| fact | expected | actual | result |", "|---|---|---|---|"]
    for fid, r in results.items():
        (out / f"{fid}.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        cell = json.dumps(r["expected"], default=str)[:200].replace("|", "/"), json.dumps(r["actual"], default=str)[:300].replace("|", "/")
        rows.append(f"| {fid} {r['title']} | {cell[0]} | {cell[1]} | {'pass' if r['pass'] else 'FAIL'} |")
    (out / "result.md").write_text("# UC8 result\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    sys.exit(0 if results and all(r["pass"] for r in results.values()) else 1)


if __name__ == "__main__":
    main()
