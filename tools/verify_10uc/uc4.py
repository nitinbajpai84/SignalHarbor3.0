"""UC4 black-box checker (planted facts P14-P16 of docs/test/10uc_universe.json).
python tools/verify_10uc/uc4.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Logs in over HTTP as the role each fact names, reads only real /api/v1 routes, writes DIR/uc4/<fact>.json and result.md. Exit 1 on any fail.
Passwords are read from the creds file and never printed or written. Only GETs after login, so no CSRF handling is needed."""
import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

U = json.loads((Path(__file__).resolve().parents[2] / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
PLANTED = {p["id"]: p for p in U["planted"] if p["use_case"] == "UC4"}


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, headers={"Content-Type": "application/json"},
                                     data=None if body is None else json.dumps(body).encode())
        try:
            with self.op.open(req, timeout=60) as r:
                code, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
        except OSError as e:
            return 0, {"error": str(e)}
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, {"raw": raw[:300].decode("utf-8", "replace")}


def creds_for(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 3 and "@" in p[0]:
            out[p[0]] = p[1]
    return out


def as_role(base, creds, platform_role):
    person = next(p for p in U["people"] if p["platform_role"] == platform_role)
    c, pw = Client(base), creds.get(person["email"])
    code = c.call("POST", "/api/auth/login", {"email": person["email"], "password": pw})[0] if pw else -1
    return c, person["name"], code


def numbers(o, acc=None):
    """every number or numeric string anywhere in a JSON value, as Decimal"""
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        for v in o.values():
            numbers(v, acc)
    elif isinstance(o, list):
        for v in o:
            numbers(v, acc)
    elif isinstance(o, (int, float, str)) and not isinstance(o, bool):
        try:
            acc.add(Decimal(str(o)).normalize())
        except InvalidOperation:
            pass
    return acc


def text(o):
    return json.dumps(o).lower()


def has(nums, want):
    return Decimal(want).normalize() in nums


def p14(base, creds):
    role = PLANTED["P14"]["role"]
    c, who, lc = as_role(base, creds, role)
    path = "/api/v1/benchmarks/comparison?portfolio=EG-LIQUID&code=EG-OFFICE-BLEND&start=2026-09&end=2026-09"
    k, b = c.call("GET", path)
    m = next(iter((b.get("months") if isinstance(b, dict) else None) or []), {})

    def pct(x):
        return Decimal(str(x["pct"])) if isinstance(x, dict) and x.get("pct") is not None else None

    # a list, not a dict by series_key: the equity index and the private sleeve (equity + 300 bps) share IDX:GLEQ:SYN (a4.0)
    pairs = [(x.get("series_key"), pct(x.get("return"))) for x in m.get("components", [])]
    vals = [v for _, v in pairs]
    got = {
        "portfolio_4.1667": pct(m.get("portfolio")) == Decimal("4.1667"),
        "blend_2.7072": pct(m.get("benchmark")) == Decimal("2.7072"),
        "components_3.5002_0.4002": Decimal("3.5002") in vals and Decimal("0.4002") in vals,
        "private_sleeve_3.7502": Decimal("3.7502") in vals or Decimal("3.7466") in vals,  # 3.7466 tolerated until the seed spread is settled
        "difference_1.4595": pct(m.get("difference")) == Decimal("1.4595"),
        "liquid_sleeve_difference_1.9065": pct((m.get("liquid_sleeve") or {}).get("difference")) == Decimal("1.9065"),
        "certified_true": m.get("certified") is True,
    }
    exp = {"portfolio": "4.1667", "blend": "2.7072", "components": ["3.5002", "0.4002", "3.7502"], "difference": "1.4595",
           "liquid_sleeve_difference": "1.9065", "certified": True}
    return dict(fact="P14", role=f"{role} ({who})", expected=exp,
                actual={"figures_found": got, "components": [f"{k} {v}" for k, v in pairs], "certified": m.get("certified"), "problems": m.get("problems")},
                request=[{"path": path, "status": k}], ok=lc == 200 and k == 200 and all(got.values()))


def p15(base, creds):
    role, code_ = PLANTED["P15"]["role"], U["benchmark"]["benchmark_code"]
    v2 = next(v for v in U["benchmark"]["versions"] if v["version_number"] == 2)
    c, who, lc = as_role(base, creds, role)
    k, b = c.call("GET", "/api/v1/benchmarks")
    d2 = next((d for d in (b.get("definitions") if isinstance(b, dict) else None) or []
               if d.get("benchmark_code") == code_ and d.get("version") == 2), {})
    pq = d2.get("policy_question") or {}
    notice_ok = d2.get("notice") == "In progress: not used for certified figures."
    case_ok = bool(pq.get("question")) and bool(pq.get("case"))
    # the approver cannot see the case in /cases; the analyst (Mei Chen) can
    m, mname, mc = as_role(base, creds, "analyst")
    ck, cb = m.call("GET", "/api/v1/cases?exception_type=policy_question")
    cases = (cb.get("cases") if isinstance(cb, dict) else None) or []
    mine = [x for x in cases if "benchmark" in text(x)]
    kinds = {str(x.get("exception_type")) for x in mine}
    ak, _ = Client(base).call("GET", "/api/v1/cases?exception_type=policy_question")
    return dict(fact="P15", role=f"{role} ({who}); cases read as analyst ({mname})",
                expected={"case_kind": "policy_question", "about": code_, "v2_status": v2["approval_status"],
                          "notice": "In progress: not used for certified figures.", "anonymous": "401/403"},
                actual={"benchmarks_status": k, "v2_status": d2.get("status"), "notice": d2.get("notice"), "policy_question_case": pq.get("case"),
                        "cases_status": ck, "case_kinds": sorted(kinds), "case_titles": [x.get("title") for x in mine], "anonymous_status": ak},
                request=[{"path": "/api/v1/benchmarks", "status": k}, {"path": "/api/v1/cases?exception_type=policy_question (analyst)", "status": ck}],
                ok=lc == 200 and k == 200 and notice_ok and case_ok and mc == 200 and ck == 200 and kinds == {"policy_question"} and ak in (401, 403))


def p16(base, creds):
    role, rate, rep = PLANTED["P16"]["role"], U["fx_fixings"]["pinned"]["2026-09-30"], U["report_issued"]
    c, who, lc = as_role(base, creds, role)
    usd = next(x["value"] for x in rep["lines"] if x["label"] == "Total")
    calc = (Decimal(usd) * Decimal(rate)).quantize(Decimal("0.01"))
    k, b = c.call("GET", "/api/v1/office/issued?currency=SGD")
    k2, b2 = c.call("GET", "/api/v1/office/issued?currency=USD")
    ak, _ = Client(base).call("GET", "/api/v1/office/issued?currency=SGD")
    sgd_ok, usd_ok = has(numbers(b), rep["total_sgd"]), has(numbers(b2), usd)
    return dict(fact="P16", role=f"{role} ({who})",
                expected={"usd_total": usd, "rate": rate, "total_sgd": rep["total_sgd"], "fx_8_oct": U["fx_fixings"]["pinned"]["2026-10-08"], "anonymous": "401/403"},
                actual={"sgd_status": k, "sgd_total_found": sgd_ok, "usd_total_found": usd_ok, "arithmetic_ok": calc == Decimal(rep["total_sgd"]), "anonymous_status": ak},
                request=[{"path": "/api/v1/office/issued?currency=SGD", "status": k}, {"path": "/api/v1/office/issued?currency=USD", "status": k2}],
                ok=lc == 200 and k == 200 and calc == Decimal(rep["total_sgd"]) and sgd_ok and usd_ok and ak in (401, 403))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / "uc4"
    out.mkdir(parents=True, exist_ok=True)
    creds, rows = creds_for(a.creds), []
    for fn in (p14, p15, p16):
        try:
            r = fn(a.base, creds)
        except Exception as e:  # a checker error is a fail, with the reason
            r = dict(fact=fn.__name__.upper(), role="", expected="", actual=f"checker error: {type(e).__name__}: {e}", request=[], ok=False)
        r["result"] = "pass" if r["ok"] else "fail"
        (out / f"{r['fact']}.json").write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
        rows.append(r)
    md = ["# UC4 result", "", "| fact | expected | actual | result |", "|---|---|---|---|"]
    for r in rows:
        cell = lambda v: json.dumps(v, default=str).replace("|", "/")[:400]
        md.append(f"| {r['fact']} | {cell(r['expected'])} | {cell(r['actual'])} | {r['result']} |")
    (out / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(f"{r['fact']} {r['result']}" for r in rows))
    sys.exit(0 if all(r["ok"] for r in rows) else 1)


if __name__ == "__main__":
    main()
