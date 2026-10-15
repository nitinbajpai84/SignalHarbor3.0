"""UC6 black-box checker: planted facts P21-P24 (private-asset liquidity and commitments).

python tools/verify_10uc/uc6.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Logs in as the role each fact names, calls the real /api/v1 routes, compares figures as Decimal, writes DIR/uc6/<fact>.json and
DIR/uc6/result.md, exits 1 if any fact fails. Stdlib only. Passwords are read from the creds file and never printed or written.
Figures come from docs/test/10uc_universe.json; nothing is hard-coded twice.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs/test/10uc_universe.json").read_text(encoding="utf-8"))
AS_OF = U["meta"]["as_of"]
PLANTED = {p["id"]: p for p in U["planted"]}
FUND = {f["key"]: f for f in U["funds"]}
MOVE = {m["id"]: m for m in U["cash_movements"]}
LIQ = {r["legal_entity"]: r for r in U["liquidity_9_oct"]}
PERSON = {}
for _p in U["people"]:
    PERSON.setdefault(_p["platform_role"], _p)   # first person per role (approver = Raj Patel, company_admin = Grace Ong)
LIQ_PATH = f"/api/v1/office/liquidity?currency=USD&as_of={AS_OF}"
CASE_PATH = "/api/v1/cases?status=active&exception_type=capital_call"


def D(x):
    try:
        return Decimal(str(x).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.op.open(req, timeout=60) as r:
                code, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
        except OSError as e:
            return 0, {"error": str(e)}
        try:
            return code, json.loads(raw or b"{}")
        except ValueError:
            return code, {"raw": raw[:200].decode("utf-8", "replace")}

    def get(self, path):
        return self.call("GET", path)


def creds_by_email(path: str) -> dict:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if line.strip() and not line.startswith("#") and len(parts) >= 2 and "@" in parts[0]:
            out[parts[0].lower()] = parts[1]
    return out


def login(base: str, creds: dict, who: dict):
    c, pw = Client(base), creds.get(who["email"].lower())
    if pw is None:
        return None, f"no credentials for {who['name']} in the creds file"
    code, _ = c.call("POST", "/api/auth/login", {"email": who["email"], "password": pw})
    return (c, "") if code == 200 else (None, f"login of {who['name']} failed: HTTP {code}")


class Fact:
    def __init__(self, fid: str):
        self.id, self.rows, self.calls = fid, [], []

    def req(self, who, path, code, excerpt):
        self.calls.append({"as": who, "request": f"GET {path}", "http": code, "response_excerpt": excerpt})

    def check(self, label, expected, actual, ok=None):
        ok = (expected == actual) if ok is None else ok
        self.rows.append({"check": label, "expected": str(expected), "actual": str(actual), "pass": bool(ok)})

    def money(self, label, expected, actual):
        e, a = D(expected), D(actual)
        self.check(label, expected, actual, e is not None and a is not None and e == a)

    @property
    def passed(self):
        return bool(self.rows) and all(r["pass"] for r in self.rows)


def entity(fc: dict, code: str) -> dict:
    return next((e for e in (fc.get("entities") or []) if e.get("entity_code") == code), {})


def bucket(ent: dict, key: str) -> dict:
    return next((b for b in ent.get("buckets", []) if b.get("key") == key), {})


def item(ent: dict, mid: str) -> dict:
    """The forecast item for a planted movement: same fund, kind and due date."""
    m = MOVE[mid]
    name = FUND[m["fund"]]["canonical_name"]
    for b in ent.get("buckets", []):
        for i in b.get("items", []):
            if i.get("fund") == name and i.get("due_date") == m["due_date"] and i.get("kind") == m["notice_kind"]:
                return i
    return {}


def has_items(body: dict) -> bool:
    return any(bk.get("items") for e in body.get("entities", []) for bk in e.get("buckets", []))


def admin_sees(f: Fact, base, creds, who: dict, path: str, probe):
    """The company admin sees everything (answer key, people table: Grace Ong 'everything, Settings'; a6.0)."""
    label = f"{who['name']} ({who['platform_role']}) sees it too"
    c, err = login(base, creds, who)
    if c is None:
        f.check(label, "refused or empty", err, False)
        return
    code, body = c.get(path)
    f.req(f"{who['name']} ({who['platform_role']})", path, code, body if code != 200 else {"seen": bool(probe(body))})
    f.check(label, "HTTP 200 with the figures", f"HTTP {code}" + (", shown" if code == 200 and probe(body) else ", nothing shown"),
            code == 200 and bool(probe(body)))


def confirmed_after(fund: str) -> Decimal:
    """October-on call notices already confirmed: the product counts them as called once confirmed (answer key P24, item 3; a6.1)."""
    return sum((D(m["amount"]) for m in U["cash_movements"] if m.get("fund") == fund and m.get("notice_kind") == "call"
                and m.get("confirmation_status") == "confirmed" and str(m.get("due_date")) > AS_OF), Decimal(0))


def called_now(c: dict) -> Decimal:
    return D(c["called_to_date"]) + confirmed_after(c["fund"])


def is_call_case(x: dict) -> bool:  # the title may name the fund after 'Fund the capital call' (a6.11)
    return str(x.get("title") or "").startswith("Fund the capital call")


def cases_of(c: Client, who: str, f: Fact) -> list:
    code, cs = c.get(CASE_PATH)
    got = [x for x in (cs.get("cases", []) if isinstance(cs, dict) else []) if x.get("exception_type") == "capital_call"]
    f.req(who, CASE_PATH, code, [{k: x.get(k) for k in ("exception_type", "title", "status", "instrument_id", "description")} for x in got])
    return got


def p21(base, creds, appr):
    f = Fact("P21")
    code, fc = appr.get(LIQ_PATH)
    ent = entity(fc, "EG-B")
    f.req("approver", LIQ_PATH, code, {"entity": ent.get("entity_code"), "bucket_30": bucket(ent, "30"), "unconfirmed": ent.get("unconfirmed")})
    f.check("liquidity route answers", 200, code)
    c_id, e_id = "mv-2026-10-C-call", "mv-2026-10-E-call"
    for mid in (c_id, e_id):
        m, i = MOVE[mid], item(ent, mid)
        name = FUND[m["fund"]]["canonical_name"]
        f.money(f"{name} call amount", m["amount"], i.get("amount"))
        f.check(f"{name} due date", m["due_date"], i.get("due_date"))
        f.check(f"{name} status word", m["confirmation_status"], i.get("status"))
        f.check(f"{name} confirmed flag", m["confirmation_status"] == "confirmed", i.get("confirmed"))
        f.check(f"{name} in the 30-day bucket of Entity B", True, bool(i) and i in bucket(ent, "30").get("items", []))
    f.check("Fund E call flagged as not confirmed", True, any(i.get("due_date") == MOVE[e_id]["due_date"] for i in ent.get("unconfirmed", [])))
    f.check("Fund C call not flagged", False, any(i.get("due_date") == MOVE[c_id]["due_date"] for i in ent.get("unconfirmed", [])))
    f.money("30-day calls total, Entity B", LIQ["EG-B"]["calls_due"]["30"], bucket(ent, "30").get("calls"))
    f.check("Finance case 'Fund the capital call' visible to the approver", True, any(is_call_case(x) for x in cases_of(appr, "approver", f)))
    admin_sees(f, base, creds, PERSON["company_admin"], LIQ_PATH, has_items)   # no access group, so E1d shows no entity
    return f


def p22(base, creds, appr):
    f = Fact("P22")
    code, fc = appr.get(LIQ_PATH)
    ent, row = entity(fc, "EG-B"), LIQ["EG-B"]
    f.req("approver", LIQ_PATH, code, {"entity": ent.get("entity_code"), "available_cash": ent.get("available_cash"), "bucket_30": bucket(ent, "30")})
    f.money("available cash (administrator, 8 Oct)", row["available_cash_administrator_8_oct"], ent.get("available_cash"))
    calls = [i for i in bucket(ent, "30").get("items", []) if i.get("kind") == "call"]
    conf = sum((D(i["amount"]) for i in calls if i.get("confirmed")), Decimal(0))
    allc = sum((D(i["amount"]) for i in calls), Decimal(0))
    avail = D(ent.get("available_cash")) or Decimal(0)
    f.money("after the confirmed call", row["after_confirmed_calls_30d"], avail - conf)
    f.money("after both noticed calls (shortfall)", row["after_all_noticed_calls_30d"], avail - allc)
    f.money("30-day bucket cash_after_calls", row["after_all_noticed_calls_30d"], bucket(ent, "30").get("cash_after_calls"))
    f.check("shortfall is negative", True, (D(bucket(ent, "30").get("cash_after_calls")) or Decimal(0)) < 0)
    cases = cases_of(appr, "approver", f)
    ci, ei = item(ent, "mv-2026-10-C-call"), item(ent, "mv-2026-10-E-call")
    f.check("exactly one capital_call case", 1, len(cases))
    f.check("case title", "Fund the capital call", cases[0].get("title") if cases else None, bool(cases) and is_call_case(cases[0]))
    f.check("case is for the Fund C call", ci.get("instrument_id"), cases[0].get("instrument_id") if cases else None,
            bool(ci) and bool(cases) and str(cases[0].get("instrument_id")) == str(ci.get("instrument_id")))
    f.check("no case for the unconfirmed Fund E call", False, any(str(x.get("instrument_id")) == str(ei.get("instrument_id")) for x in cases))
    admin_sees(f, base, creds, PERSON["company_admin"], CASE_PATH, lambda b: any(x.get("exception_type") == "capital_call" for x in b.get("cases", [])))
    return f


def p23(base, creds, appr):
    f = Fact("P23")
    code, fc = appr.get(LIQ_PATH)
    b, h = entity(fc, "EG-B"), entity(fc, "EG-HOLD")
    f.req("approver", LIQ_PATH, code, {"EG-B bucket 60": bucket(b, "60"), "EG-HOLD bucket 60": bucket(h, "60")})
    d, a = MOVE["mv-2026-12-D-call"], MOVE["mv-2026-11-A-dist"]
    di, ai = item(b, "mv-2026-12-D-call"), item(h, "mv-2026-11-A-dist")
    f.money("Fund D call amount", d["amount"], di.get("amount"))
    f.check("Fund D call due", d["due_date"], di.get("due_date"))
    f.check("Fund D call status", d["confirmation_status"], di.get("status"))
    f.check("Fund D call in the 60-day bucket of Entity B", True, bool(di) and di in bucket(b, "60").get("items", []))
    f.money("60-day calls, Entity B", LIQ["EG-B"]["calls_due"]["60"], bucket(b, "60").get("calls"))
    f.money("Fund A distribution amount", a["amount"], ai.get("amount"))
    f.check("Fund A distribution due", a["due_date"], ai.get("due_date"))
    f.check("Fund A distribution status", a["confirmation_status"], ai.get("status"))
    f.check("Fund A distribution kind", "distribution", ai.get("kind"))
    f.check("Fund A distribution in the 60-day bucket of Evergreen Holdings", True, bool(ai) and ai in bucket(h, "60").get("items", []))
    f.money("60-day distributions, Evergreen Holdings", LIQ["EG-HOLD"]["distributions_expected"]["60"], bucket(h, "60").get("distributions"))
    admin_sees(f, base, creds, PERSON["company_admin"], LIQ_PATH, has_items)
    return f


def p24(base, creds, appr):
    f = Fact("P24")
    inbox_path = f"/api/v1/managers/inbox?as_of={AS_OF}"
    code, inbox = appr.get(inbox_path)
    f.req("approver", inbox_path, code, [m.get("manager_id") for m in inbox.get("managers", [])])
    mgr = {m["name"]: m["manager_id"] for m in inbox.get("managers", [])}
    slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")  # noqa: E731  (same rule as k5_managers.slug)
    by_fund, seen = {}, []
    for m in U["managers"]:
        mid = mgr.get(m["name"]) or slug(m["name"])
        code, prof = appr.get(f"/api/v1/managers/{mid}")
        rows = (prof.get("commitments") or {}).get("rows", []) if code == 200 else []
        seen.append({"manager": m["name"], "http": code, "rows": rows})
        f.check(f"{m['name']} profile answers", 200, code)
        name_of = {x["fund_id"]: x["fund_name"] for x in prof.get("funds", [])} if code == 200 else {}
        for r in rows:
            t = by_fund.setdefault(name_of.get(r["fund_id"]), {"c": Decimal(0), "k": Decimal(0), "u": Decimal(0)})
            t["c"] += D(r["commitment"]) or 0
            t["k"] += D(r["called"]) or 0
            t["u"] += D(r["uncalled"]) or 0
    f.req("approver", "/api/v1/managers/{id} for each manager", 200, seen)
    for c in U["commitments"]:
        name = FUND[c["fund"]]["canonical_name"]
        t = by_fund.get(name, {})
        f.money(f"{name} committed", c["commitment_amount"], t.get("c"))
        f.money(f"{name} called", called_now(c), t.get("k"))
        f.money(f"{name} uncalled", D(c["commitment_amount"]) - called_now(c), t.get("u"))
        f.check(f"{name} called does not exceed commitment", True, t.get("k") is not None and t["k"] <= t["c"])
    code, fc = appr.get(LIQ_PATH)
    f.req("approver", LIQ_PATH, code, {e["entity_code"]: e.get("uncalled") for e in fc.get("entities", [])})
    for ent in sorted({c["legal_entity"] for c in U["commitments"]}):
        f.money(f"uncalled commitment on the Office view, {ent}",
                sum(D(c["commitment_amount"]) - called_now(c) for c in U["commitments"] if c["legal_entity"] == ent),
                entity(fc, ent).get("uncalled"))
    ga = PERSON["company_admin"]
    c, err = login(base, creds, ga)
    label = "company_admin sees the commitments"
    if c is None:
        f.check(label, "refused or empty", err, False)
    else:
        mid = mgr.get("Cedarpoint Ventures", "cedarpoint-ventures")
        code, prof = c.get(f"/api/v1/managers/{mid}")
        rows = (prof.get("commitments") or {}).get("rows", []) if code == 200 else []
        f.req(f"{ga['name']} (company_admin)", f"/api/v1/managers/{mid}", code, {"commitment_rows": len(rows)})
        f.check(label, "HTTP 200 with rows", f"HTTP {code}, {len(rows)} rows", code == 200 and bool(rows))
    return f


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out) / "uc6"
    out.mkdir(parents=True, exist_ok=True)
    creds = creds_by_email(a.creds)
    appr, err = login(a.base, creds, PERSON["approver"])
    facts = []
    for fn in (p21, p22, p23, p24):
        fid = fn.__name__.upper()
        if appr is None:
            f = Fact(fid)
            f.check("approver signs in", "signed in", err, False)
        else:
            try:
                f = fn(a.base, creds, appr)
            except Exception as e:  # a missing key in an answer is a failure to report, not a crash
                f = Fact(fid)
                f.check("checker ran", "no error", f"{type(e).__name__}: {e}", False)
        facts.append(f)
        p = PLANTED[fid]
        (out / f"{fid}.json").write_text(json.dumps({
            "fact": fid, "title": p["fact"], "role": p["role"], "expected": p["expected"], "requests": f.calls, "checks": f.rows,
            "actual": [r["actual"] for r in f.rows if not r["pass"]] or "all checks match", "result": "pass" if f.passed else "fail"},
            indent=2, default=str), encoding="utf-8")
    lines = ["# UC6 result", "", f"Base {a.base}, as of {AS_OF}.", "", "| Fact | Expected | Actual | Pass |", "|---|---|---|---|"]
    for f in facts:
        for r in f.rows:
            lines.append(f"| {f.id} {r['check']} | {r['expected']} | {r['actual']} | {'pass' if r['pass'] else 'FAIL'} |")
    lines += ["", *[f"{f.id}: {'pass' if f.passed else 'FAIL'}" for f in facts]]
    (out / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(f"{f.id}: {'pass' if f.passed else 'FAIL'}" for f in facts))
    return 0 if all(f.passed for f in facts) else 1


if __name__ == "__main__":
    sys.exit(main())
