"""UC2 black-box checker: planted fact P08 (Entity B cash break, 8 Oct 2026).

python tools/verify_10uc/uc2.py --base http://127.0.0.1:8651 --creds PATH --out DIR
Stdlib only. Figures come from docs/test/10uc_universe.json. Passwords are read from the creds file and never printed or written.
Writes DIR/uc2/<fact>.json and DIR/uc2/result.md; exit 1 if any fact fails.
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
UNIVERSE = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
DAY = "2026-10-08"


class Client:
    def __init__(self, base):
        self.base, self.jar = base.rstrip("/"), CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), None)
        if csrf:
            h["X-CSRF-Token"] = csrf
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with self.op.open(req, timeout=60) as r:
                code, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, {"raw": raw[:300].decode("utf-8", "replace")}


def creds(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if line.startswith("#") or len(p) < 2:
            continue
        out[p[0].lower()] = p[1]
    return out


def login(base, email, pw):
    c = Client(base)
    code, _ = c.call("POST", "/api/auth/login", {"email": email, "password": pw})
    return c if code == 200 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / "uc2"
    out.mkdir(parents=True, exist_ok=True)
    pw = creds(a.creds)
    email = {}
    for p in UNIVERSE["people"]:  # first person per platform role
        email.setdefault(p["platform_role"], p["email"])
    who = {r: login(a.base, email[r], pw.get(email[r].lower(), "")) for r in ("analyst", "approver", "participant")}

    cash = {r["legal_entity"]: r for r in UNIVERSE["cash_8_oct"]}
    ents = {e["entity_code"]: e["entity_name"] for e in UNIVERSE["legal_entities"]}
    b, trust, hold = cash["EG-B"], cash["EG-TRUST"], cash["EG-HOLD"]
    title = f"Cash differs · {ents['EG-B']} · {DAY}"  # e3_recon's title, middle dots
    rows = []  # (fact, expected, actual, ok, request, response)

    def rec(fact, expected, actual, ok, request, response):
        rows.append((fact, expected, actual, bool(ok), request, response))

    def cases_for(role):
        if not who[role]:
            return None, {"error": "login failed"}
        return who[role].call("GET", "/api/v1/cases?exception_type=break")

    def find(body, t):
        return [c for c in (body or {}).get("cases", []) if c.get("title") == t]

    # 1. analyst runs the cash check: 3 entities checked, 1 break (a re-run opens nothing new)
    req = f"POST /api/v1/recon/cash_by_entity/run {{as_of_date: {DAY}}} as analyst"
    if who["analyst"]:
        code, run = who["analyst"].call("POST", "/api/v1/recon/cash_by_entity/run", {"as_of_date": DAY})
        run = run if isinstance(run, dict) else {}
        n_opened = len(run.get("opened", []))
        rec("run_checked_3_breaks_1", "200; checked 3, breaks 1, opened 0 or 1",
            f"{code}; checked {run.get('checked')}, breaks {run.get('breaks')}, opened {n_opened}",
            code == 200 and run.get("checked") == 3 and run.get("breaks") == 1 and n_opened in (0, 1), req, run)
    else:
        rec("run_checked_3_breaks_1", "analyst signs in", "login failed", False, req, {})

    # 2. the break case: one, exact figures, seen by analyst and approver
    for role in ("analyst", "approver"):
        code, body = cases_for(role)
        hit = find(body, title)
        c = hit[0] if len(hit) == 1 else {}
        amt = Decimal(str(c["amount"])) if c.get("amount") is not None else None
        d = c.get("description") or ""
        adm, trd = f"{Decimal(b['administrator']):,.2f}", f"{Decimal(b['trading_export']):,.2f}"
        exp = f"{role}: 200; one break case '{title}', amount {b['difference']} USD, text has {adm} and {trd}"
        act = f"{code}; {len(hit)} case(s); amount {amt}; currency {c.get('currency')}; type {c.get('exception_type')}"
        ok = (code == 200 and len(hit) == 1 and amt == Decimal(b["difference"]) and c.get("currency") == "USD"
              and c.get("exception_type") == "break" and adm in d and trd in d)
        rec(f"break_case_{role}", exp, act, ok, f"GET /api/v1/cases?exception_type=break as {role}",
            {"matching": hit, "total_break_cases": len((body or {}).get("cases", []))})

    # 3 and 4. no case for Trust (1,800 inside tolerance) or Holdings (equal); exactly one cash case on 8 Oct
    code, body = cases_for("analyst")
    cash_cases = [c for c in (body or {}).get("cases", []) if (c.get("title") or "").startswith("Cash differs") and DAY in c["title"]]
    bad = [c["title"] for c in cash_cases if ents["EG-TRUST"] in c["title"] or ents["EG-HOLD"] in c["title"]]
    rec("no_case_trust_holdings", f"no cash case for {ents['EG-TRUST']} (diff {trust['difference']}) or {ents['EG-HOLD']} (diff {hold['difference']})",
        f"cases found: {bad or 'none'}", code == 200 and not bad, "GET /api/v1/cases?exception_type=break as analyst",
        {"cash_cases": [c["title"] for c in cash_cases]})
    rec("one_break_case_8_oct", "1 cash break case for 8 Oct", str(len(cash_cases)), len(cash_cases) == 1,
        "GET /api/v1/cases?exception_type=break as analyst", {"count": len(cash_cases)})

    # 5. roles that must not run the check get 403
    for role in ("approver", "participant"):
        if who[role]:
            code, r1 = who[role].call("POST", "/api/v1/recon/cash_by_entity/run", {"as_of_date": DAY})
            code2, r2 = who[role].call("GET", "/api/v1/recon/runs")
            rec(f"{role}_cannot_run_recon", "403 on run; 200 on runs list (open to every company role)", f"{code}, {code2}", code == 403 and code2 == 200,
                f"POST recon run and GET recon/runs as {role}", {"run": r1, "runs": r2})
        else:
            rec(f"{role}_cannot_run_recon", "403", "login failed", False, "login", {})

    # 6. participant sees the P08 case: case access follows entity grants, and the answer key puts Sofia Reyes in the Investment office
    #    group with every entity (10UC-ANSWER-KEY.md, "Everything above is visible to ..."; a2.9)
    code, body = cases_for("participant")
    hit = find(body, title)
    rec("participant_sees_case", "200 and the P08 case in the list (Investment office group, every entity)", f"{code}; {len(hit)} matching",
        code == 200 and len(hit) == 1, "GET /api/v1/cases?exception_type=break as participant", {"matching": hit})

    lines = ["# UC2 result: P08 Entity B cash break 8 Oct", "", "| fact | expected | actual | pass/fail |", "|---|---|---|---|"]
    for fact, exp, act, ok, req, resp in rows:
        lines.append(f"| {fact} | {exp} | {act} | {'pass' if ok else 'FAIL'} |".replace("\n", " "))
        excerpt = json.dumps(resp, default=str)
        (out / f"{fact}.json").write_text(json.dumps({
            "fact": fact, "request": req, "response_excerpt": json.loads(excerpt) if len(excerpt) < 6000 else excerpt[:6000],
            "expected": exp, "actual": act, "result": "pass" if ok else "fail"}, indent=1), encoding="utf-8")
    (out / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(r[3] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
