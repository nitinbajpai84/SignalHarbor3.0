"""UC5 black-box checker: planted facts P17-P20 (limits). Stdlib only; figures come from docs/test/10uc_universe.json.

python tools/verify_10uc/uc5.py --base http://127.0.0.1:8654 --creds PATH --out DIR [--as-of 2026-10-09]
Passwords are read from the creds file (email  password  roles  company) and are never printed or written.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from decimal import ROUND_HALF_EVEN, Decimal
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNI = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
D = Decimal


class Client:
    def __init__(self, base, email, password):
        self.base, self.jar = base.rstrip("/"), CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.login_status = self.call("POST", "/api/auth/login", {"email": email, "password": password})[0]

    def call(self, method, path, body=None):
        h = {"Accept": "application/json"}
        data = None
        if body is not None:
            data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
        csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), None)
        if csrf and method != "GET":
            h["X-CSRF-Token"] = csrf
        try:
            with self.op.open(urllib.request.Request(self.base + path, data, h, method=method), timeout=120) as r:
                code, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, {"raw": raw[:200].decode("utf-8", "replace")}


def read_creds(path):
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        p = ln.split()
        if len(p) >= 2 and not ln.startswith("#"):
            out[p[0].lower()] = p[1]
    return out


def q(x, places):
    return D(x).quantize(D(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


def clip(x, n=1500):
    s = json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + "...(cut)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--as-of", default=UNI["meta"]["as_of"])
    a = ap.parse_args()
    creds = read_creds(a.creds)
    emails = {p["name"]: p["email"].lower() for p in UNI["people"]}
    clients = {}

    def as_(name):
        if name not in clients:
            clients[name] = Client(a.base, emails[name], creds[emails[name]])
        return clients[name]

    lim = {r["item"]: r for r in UNI["limits_check_30_sep"]}
    hvs, ced, eq, hf = lim["HVS"], lim["C+D"], lim["listed_equity"], lim["H1+H2"]
    rules = {r["rule_code"]: r["parameters"] for r in UNI["rules"] if r["rule_type"] == "limit"}
    pf_name = {p["portfolio_code"]: p["portfolio_name"] for p in UNI["portfolios"]}
    liq_total = D(UNI["liquid_book_month_end"]["2026-09-30"]["total"])
    nav = {r["portfolio"]: D(r["investment_view"]) for r in UNI["nav_bridge_30_sep"]}
    sec = {s["key"]: s for s in UNI["securities"]}
    prc = next(p for p in UNI["liquid_book_month_end"]["2026-09-30"]["positions"] if p["security"] == "PRC29")
    facts = {}

    def new(fid):
        facts[fid] = {"fact": fid, "request": [], "expected": {}, "actual": {}, "checks": []}
        return facts[fid]

    def chk(f, name, ok, exp=None, act=None):
        f["checks"].append({"check": name, "pass": bool(ok), "expected": exp, "actual": act})

    # one run of the Limits check as the operations analyst (the route allows company_admin and analyst only)
    mei = as_("Mei Chen")
    code, run = mei.call("POST", "/api/v1/recon/limits/run", {"as_of_date": a.as_of})
    run = run if isinstance(run, dict) else {"raw": run}
    runreq = f"POST /api/v1/recon/limits/run as Mei Chen (analyst) {{as_of_date: {a.as_of}}}"
    causes = run.get("causes", [])
    cases = {n: ((as_(n).call("GET", "/api/v1/cases?exception_type=limit_breach")[1] or {}).get("cases") or [])
             for n in ("Mei Chen", "Sofia Reyes")}

    def cause_of(word, pname):
        return next((c["cause"] for c in causes if word in c["title"] and pname in c["title"]), None)

    def case_of(who, word, pname):
        return next((c for c in cases[who] if word in c["title"] and pname in c["title"]), None)

    def breach_checks(f, item, key, total, cause_expect, portfolio, name_word):
        pname, p = pf_name[portfolio], rules[key]
        edge = D(str(p["max_pct"]))
        exact = D(item["item_value"]) / total * 100
        impact = D(item["item_value"]) - edge * total / 100
        f["request"] += [runreq, "GET /api/v1/cases?exception_type=limit_breach as Mei Chen and Sofia Reyes",
                         "POST /api/v1/recon/limits/run as Raj Patel and Daniel Foo (must be 403)"]
        f["expected"] = {"universe_share_2dp": item["exposure_pct"], "share_2dp_in_case": str(q(exact, 2)), "item_value": item["item_value"],
                         "portfolio_total": str(total), "case": "limit_breach", "cause": cause_expect, "impact": str(impact)}
        chk(f, "run answered 200", code == 200, 200, code)
        chk(f, "universe share is item_value/total to 2dp", q(exact, 2) == D(item["exposure_pct"]), item["exposure_pct"], str(q(exact, 2)))
        got = cause_of(name_word, pname)
        f["actual"]["run_cause"] = got
        chk(f, f"run cause for {name_word}", got == cause_expect, cause_expect, got)
        for who in ("Mei Chen", "Sofia Reyes"):
            c = case_of(who, name_word, pname)
            f["actual"][who] = {k: c.get(k) for k in ("number", "exception_type", "title", "description", "candidate_impact_amount", "impact_currency")} if c else None
            chk(f, f"{who} sees a limit_breach case", c is not None and c.get("exception_type") == "limit_breach", "limit_breach", c and c.get("exception_type"))
            if c:
                d = c.get("description") or ""
                chk(f, f"{who} case says 'It is {q(exact, 2):,}%'", f"It is {q(exact, 2):,}%" in d, f"It is {q(exact, 2):,}%", d[:200])  # 2 decimals, as the answer key (a5.0)
                chk(f, f"{who} case says 'Cause: {cause_expect}'", f"Cause: {cause_expect}." in d, f"Cause: {cause_expect}.", d[:200])
                chk(f, f"{who} impact amount", D(str(c.get("candidate_impact_amount"))) == impact, str(impact), c.get("candidate_impact_amount"))
        # who must not run it: approver and sponsor are not in the route's roles
        for who in ("Raj Patel", "Daniel Foo"):
            st = as_(who).call("POST", "/api/v1/recon/limits/run", {"as_of_date": a.as_of})[0]
            chk(f, f"{who} refused on the run route", st == 403, 403, st)

    f = new("P17")
    breach_checks(f, hvs, "limit_single_name_liquid", liq_total, "real breach", "EG-LIQUID", "Harborview Semiconductor")
    f = new("P18")
    breach_checks(f, ced, "limit_manager_entity_b", nav["EG-B-OPS"], "stale data", "EG-B-OPS", "Cedarpoint")

    # P19: PRC29 has no class; 'Needs a class' in the office holdings; counted in no bucket; no breach
    f = new("P19")
    val = D(prc["quantity"]) * D(prc["price"])
    f["request"] += ["GET /api/v1/office/holdings?currency=USD&as_of=2026-09-30 as Sofia Reyes and Mei Chen", runreq,
                     "POST /api/v1/recon/limits/run as Sofia Reyes"]
    f["expected"] = {"value": "1122000.00", "share_of_EG-LIQUID_2dp": "2.72", "status": "Needs a class", "breach_case": None,
                     "asset_class_in_universe": sec["PRC29"]["asset_class"]}
    chk(f, "universe PRC29 has no asset_class", sec["PRC29"]["asset_class"] is None, None, sec["PRC29"]["asset_class"])
    chk(f, "universe PRC29 value 1,122,000", val == D("1122000"), "1122000", str(val))
    chk(f, "universe share 2.72", q(val / liq_total * 100, 2) == D("2.72"), "2.72", str(q(val / liq_total * 100, 2)))
    for who in ("Sofia Reyes", "Mei Chen"):
        st, h = as_(who).call("GET", "/api/v1/office/holdings?currency=USD&as_of=2026-09-30")
        line = next((ln for e in (h or {}).get("entities", []) for p in e["portfolios"] if p["portfolio_name"] == pf_name["EG-LIQUID"]
                     for ln in p["lines"] if "Pacific Rim" in ln["name"]), None)
        f["actual"][who] = {"http": st, "line": line and {k: line[k] for k in ("name", "value", "status")}}
        chk(f, f"{who} holdings answered 200", st == 200, 200, st)
        chk(f, f"{who} sees PRC29 value", line is not None and D(str(line["value"])) == val, "1122000", line and line["value"])
        chk(f, f"{who} sees status 'Needs a class'", line is not None and "needs a class" in str(line["status"]).lower(), "Needs a class", line and line["status"])
    chk(f, "no breach case names Pacific Rim", all("Pacific Rim" not in c["title"] for w in cases for c in cases[w]), None, None)
    chk(f, "no 'classification' cause in the run", "classification" not in [c["cause"] for c in causes], "none", [c["cause"] for c in causes])
    # P19 reads as a question in the run record (GET runs), not as a cause
    sr, rr = as_("Sofia Reyes").call("GET", "/api/v1/recon/runs")
    lim_run = next((r for r in (rr if isinstance(rr, list) else []) if r.get("recon_code") == "limits"), {})
    qs = lim_run.get("questions") or []
    q19 = next((x for x in qs if "Pacific Rim" in str(x.get("instrument")) and x.get("portfolio") == pf_name["EG-LIQUID"]), None)
    f["actual"]["run_question"] = q19
    chk(f, "participant (Sofia Reyes) reads the runs list", sr == 200, 200, sr)
    chk(f, "run record has the P19 question 'Needs a class'", q19 is not None and q19.get("status") == "Needs a class", "Needs a class", q19 and q19.get("status"))
    chk(f, "question value 1,122,000.00 and share 2.72", q19 is not None and D(q19["value"]) == val and D(q19["exposure_pct"]) == D("2.72"), "1122000.00 / 2.72",
        q19 and [q19.get("value"), q19.get("exposure_pct")])
    chk(f, "no results line names the unclassified holding", not [x for x in lim_run.get("results", []) if "Pacific Rim" in x.get("words", "")], [], None)
    # POST stays with company_admin and analyst: the participant reads the record but cannot run Limits
    st = as_("Sofia Reyes").call("POST", "/api/v1/recon/limits/run", {"as_of_date": a.as_of})[0]
    chk(f, "participant (Sofia Reyes) refused on the Limits run route", st == 403, 403, st)

    # P20: the two in-range limits open no case
    f = new("P20")
    f["request"] += [runreq, "GET /api/v1/cases?exception_type=limit_breach as Mei Chen and Sofia Reyes"]
    f["expected"] = {"listed_equity_pct": eq["exposure_pct"], "hedge_fund_pct": hf["exposure_pct"], "cases": 0, "breaks_in_run": 2}
    for it, lo, hi, total in ((eq, 60, 90, liq_total), (hf, 20, 60, nav["EG-FUNDS"])):
        s = q(D(it["item_value"]) / total * 100, 2)
        chk(f, f"universe {it['item']} {it['exposure_pct']} = value/total and inside {lo}-{hi}", D(it["exposure_pct"]) == s and lo <= s <= hi, it["exposure_pct"], str(s))
    named = [c["title"] for w in cases for c in cases[w] if "listed_equity" in c["title"] or "hedge_fund" in c["title"]]
    chk(f, "no case for listed_equity or hedge_fund", not named, [], named)
    chk(f, "run: exactly the two planted breaks", run.get("breaks") == 2, 2, run.get("breaks"))
    chk(f, "run: causes name no asset-class bucket", not [c for c in causes if "listed_equity" in c["title"] or "hedge_fund" in c["title"]], [], causes)
    sr, rr = as_("Sofia Reyes").call("GET", "/api/v1/recon/runs")
    lim_run = next((r for r in (rr if isinstance(rr, list) else []) if r.get("recon_code") == "limits"), {})
    chk(f, "participant (Sofia Reyes) reads the runs list", sr == 200, 200, sr)
    for bucket, it, pname in (("listed_equity", eq, pf_name["EG-LIQUID"]), ("hedge_fund", hf, pf_name["EG-FUNDS"])):
        line = next((x for x in lim_run.get("results", []) if x.get("bucket") == bucket and x.get("portfolio") == pname), None)
        chk(f, f"run results line for {bucket} shows {it['exposure_pct']}% and no breach",
            line is not None and D(line["exposure_pct"]) == D(it["exposure_pct"]) and not line["breached"],
            f"{it['exposure_pct']} not breached", line and [line.get("exposure_pct"), line.get("breached")])
    f["actual"] = {"run": {k: run.get(k) for k in ("checked", "breaks", "skipped", "rule_words")}, "causes": causes}

    out = Path(a.out) / "uc5"
    out.mkdir(parents=True, exist_ok=True)
    rows, bad = [], 0
    for fid, f in facts.items():
        f["pass"] = all(c["pass"] for c in f["checks"])
        bad += not f["pass"]
        f["run_excerpt"] = clip(run, 800)
        (out / f"{fid}.json").write_text(json.dumps(f, indent=1, default=str), encoding="utf-8")
        fails = "; ".join(f"{c['check']} (expected {c['expected']}, got {clip(c['actual'], 120)})" for c in f["checks"] if not c["pass"])
        exp = next(x["expected"] for x in UNI["planted"] if x["id"] == fid)
        rows.append(f"| {fid} | {exp[:110]} | {fails or 'all ' + str(len(f['checks'])) + ' checks agree'} | {'PASS' if f['pass'] else 'FAIL'} |")
    (out / "result.md").write_text("| fact | expected | actual | pass/fail |\n|---|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
