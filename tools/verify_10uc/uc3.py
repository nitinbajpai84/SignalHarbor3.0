"""UC3 black-box checker: External manager information inbox, planted facts P09-P13.

    python tools/verify_10uc/uc3.py --base http://127.0.0.1:8652 --creds PATH --out DIR

Logs in as the roles the facts name (passwords come from the creds file and are never printed or written), calls the
product's real /api/v1 routes, and checks each planted fact against docs/test/10uc_universe.json (the only source of figures).
Writes DIR/uc3/<fact>.json and DIR/uc3/result.md. Exit 1 if any fact fails. Stdlib only.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
AS_OF = U["meta"]["as_of"]
PLANTED = {p["id"]: p for p in U["planted"]}
FUNDS = {f["key"]: f for f in U["funds"]}
MGRS = {m["id"]: m for m in U["managers"]}
PEOPLE = {p["name"]: p for p in U["people"]}
DUE_N = next(r["parameters"]["business_days_after_month_end"] for r in U["rules"] if r["rule_code"] == "statement_due")
ANALYST, OUTSIDER = "Mei Chen", "Sofia Reyes"   # analyst (the role the facts name) and a participant (may read, may not draft)
CREDS: dict[str, str] = {}
BASE = ""


# ---------- helpers ----------

def d(s):
    return date.fromisoformat(str(s)[:10])


def add_bdays(x: date, n: int) -> date:
    while n > 0:
        x += timedelta(days=1)
        n -= x.weekday() < 5
    return x


def bdays_between(a: date, b: date) -> int:
    """Weekdays after a, up to and including b (0 if b <= a)."""
    n = 0
    while a < b:
        a += timedelta(days=1)
        n += a.weekday() < 5
    return n


def month_end_after(x: date) -> date:
    """Last day of the month after x's month."""
    first_next = (x.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (first_next.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def dec(v):
    try:
        return Decimal(str(v))
    except Exception:
        return None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def pretty(x: date) -> list[str]:
    return [f"{x.day} {x:%b %Y}", f"{x.day} {x:%B %Y}"]


class Client:
    def __init__(self):
        self.jar = CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        h = {"Content-Type": "application/json"} if data is not None else {}
        if method != "GET":
            h["X-CSRF-Token"] = next((c.value for c in self.jar if c.name == "sh_csrf"), "")
        r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
        try:
            with self.op.open(r, timeout=60) as resp:
                code, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
        try:
            return code, json.loads(raw or b"null")
        except ValueError:
            return code, {"raw": raw[:300].decode("utf-8", "replace")}


def read_creds(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and "@" in p[0]:
            out[p[0].lower()] = p[1]
    return out


def login(name) -> Client:
    c, email = Client(), PEOPLE[name]["email"]
    code, _ = c.call("POST", "/api/auth/login", {"email": email, "password": CREDS.get(email.lower(), "")})
    if code != 200:
        raise SystemExit(f"login failed for {name} (HTTP {code}); check the creds file")
    return c


class Fact:
    def __init__(self, fid):
        self.id, self.checks, self.requests, self.excerpt = fid, [], [], {}

    def req(self, who, method, path, body, code, excerpt):
        self.requests.append({"as": who, "method": method, "path": path, "body": body, "status": code})
        self.excerpt[f"{method} {path}"] = excerpt

    def check(self, what, expected, actual, ok=None):
        ok = (expected == actual) if ok is None else bool(ok)
        self.checks.append({"check": what, "expected": expected, "actual": actual, "pass": ok})

    @property
    def passed(self):
        return bool(self.checks) and all(c["pass"] for c in self.checks)


KEEP = ("fund_name", "state", "due", "received_on", "days_late", "revised_count", "earlier_missing", "last_value")


def inbox(a, f, as_of):
    path = f"/api/v1/managers/inbox?as_of={as_of}"
    code, r = a.call("GET", path)
    ok = code == 200 and isinstance(r, dict)
    f.req(ANALYST, "GET", path, None, code,
          {"managers": [{"name": m["name"], "funds": [{k: x.get(k) for k in KEEP} for x in m["funds"]]} for m in r["managers"]]} if ok else r)
    f.check(f"inbox as_of {as_of}: HTTP status", 200, code)
    rows = {x["fund_name"]: x for m in r["managers"] for x in m["funds"]} if ok else {}
    return ok, r, rows


def amt_ok(got, want):
    return dec(got) is not None and dec(got) == dec(want)


# ---------- the facts ----------

def p09(a):
    f = Fact("P09")
    ok, r, rows = inbox(a, f, AS_OF)
    if not ok:
        return f
    sept = [s for s in U["statements"] if s["period_end"] == "2026-09-30" and s["kind"] != "missing"]
    due = add_bdays(d("2026-09-30"), DUE_N).isoformat()
    f.check("due date of the September statements", due, sorted({str(x["due"]) for x in rows.values()}), ok=sorted({str(x["due"]) for x in rows.values()}) == [due])
    first = {}
    for s in sept:
        first[s["fund"]] = min(first.get(s["fund"], s["received_at"]), s["received_at"])
    for key in sorted(first):
        row = rows.get(FUNDS[key]["canonical_name"]) or {}
        f.check(f"{key} first received on", first[key][:10], row.get("received_on"))
        f.check(f"{key} state", "received", row.get("state"))
        # what is known now: the latest statement; Fund A's amended one counts only if the product holds it
        cand = [s for s in sept if s["fund"] == key and (s["kind"] != "amended" or row.get("revised_count"))]
        last = max(cand, key=lambda s: s["received_at"])
        want = "revised" if last["kind"] == "amended" else {"estimated": "estimated", "unverified": "unverified"}.get(last["status"], "official")
        lv = row.get("last_value") or {}
        f.check(f"{key} last value", last["value"], lv.get("amount"), ok=amt_ok(lv.get("amount"), last["value"]))
        f.check(f"{key} status word", want, lv.get("status"))
    for key, fd in sorted(FUNDS.items()):
        if fd["manager"] and key not in first:
            f.check(f"{key} waiting, not yet late", "not_due", (rows.get(fd["canonical_name"]) or {}).get("state"))
    return f


def p10(a):
    f = Fact("P10")
    for key, pe in (("H2", "2026-08-31"), ("E", "2026-06-30"), ("D", "2026-03-31")):
        s = next(x for x in U["statements"] if x["fund"] == key and x["period_end"] == pe and x["kind"] == "final")
        ok, _, rows = inbox(a, f, month_end_after(d(pe)).isoformat())   # an as_of in the month after the period end
        if not ok:
            continue
        row = rows.get(FUNDS[key]["canonical_name"]) or {}
        f.check(f"{key} {pe} due", s["due_date"], row.get("due"))
        f.check(f"{key} {pe} received on", s["received_at"][:10], row.get("received_on"))
        f.check(f"{key} {pe} state", "received_late", row.get("state"))
        f.check(f"{key} {pe} business days late", s["late_business_days"], row.get("days_late"))
    return f


def p11(a):
    f = Fact("P11")
    ok, r, rows = inbox(a, f, AS_OF)
    if not ok:
        return f
    s = next(x for x in U["statements"] if x["kind"] == "missing")
    key = s["fund"]
    want_days = int(re.search(r"(\d+) business days overdue", PLANTED["P11"]["expected"]).group(1))
    f.check("universe is self-consistent (weekdays after due to 9 Oct)", want_days, bdays_between(d(s["due_date"]), d(AS_OF)))
    row = rows.get(FUNDS[key]["canonical_name"]) or {}
    em = next((e for e in row.get("earlier_missing", []) if e.get("period_end") == s["period_end"]), None)
    f.check("D 30 Jun listed as missing", "listed", "listed" if em else "not listed")
    em = em or {}
    f.check("due date", s["due_date"], em.get("due"))
    f.check("business days overdue at 9 Oct", want_days, em.get("days_late"))
    for k2 in ("C", "D"):
        f.check(f"{k2} September is waiting, not late", "not_due", (rows.get(FUNDS[k2]["canonical_name"]) or {}).get("state"))
    mgr = MGRS[FUNDS[key]["manager"]]
    path = f"/api/v1/managers/{slug(mgr['name'])}/followup"
    body = {"fund_id": row.get("fund_id"), "as_of": AS_OF}
    code, dr = a.call("POST", path, body)
    f.req(ANALYST, "POST", path, body, code, {k: dr.get(k) for k in ("manager", "subject", "body", "sent", "note")} if code == 200 else dr)
    f.check("follow-up HTTP status", 200, code)
    if code == 200:
        text = "\n".join(str(dr.get(k) or "") for k in ("subject", "body", "draft"))
        f.check("addressed to the contact", mgr["contact_name"], mgr["contact_name"] if mgr["contact_name"] in text else None)
        f.check("names the manager", mgr["name"], mgr["name"] if mgr["name"] in text else None)
        name = FUNDS[key]["canonical_name"]
        f.check("names the fund", name, name if name in text else None)
        per = pretty(d(s["period_end"]))
        f.check("names the period", per, next((p for p in per if p in text), None), ok=any(p in text for p in per))
        f.check("never sent", False, dr.get("sent"))
    code, pr = login(OUTSIDER).call("POST", path, body)
    f.req(OUTSIDER, "POST", path, body, code, pr)
    f.check("participant cannot draft a follow-up (HTTP)", 403, code)
    code, nr = Client().call("GET", "/api/v1/managers/inbox")
    f.req("(no session)", "GET", "/api/v1/managers/inbox", None, code, nr)
    f.check("no session cannot read the inbox (HTTP 401 or 403)", [401, 403], code, ok=code in (401, 403))
    return f


def values_of(a, f, fund_id, period_end):
    """Values recorded for one fund and period, oldest first: every row the as-known-then query returns, plus its chain."""
    path = f"/api/v1/evidence/asof?table=valuation_observations&instrument_id={fund_id}"
    code, r = a.call("GET", path)
    f.req(ANALYST, "GET", path, None, code, {"rows": len(r.get("rows", []))} if code == 200 else r)
    seen = {}
    for row in (r.get("rows", []) if code == 200 else []):
        if str(row.get("valuation_date"))[:10] != period_end:
            continue
        c2, ch = a.call("GET", f"/api/v1/evidence/chain?table=valuation_observations&id={row['id']}")
        for x in (ch.get("rows", []) if c2 == 200 else [row]):
            seen[x["id"]] = x
    vals = [dec(x.get("value_amount")) for x in sorted(seen.values(), key=lambda x: str(x.get("recorded_at")))]
    return distinct_steps(vals)


def distinct_steps(vals):
    """The value history as a reader sees it: a pending row and its confirmation carry the same value, so repeats collapse (a3.1)."""
    out = []
    for v in vals:
        if not out or v != out[-1]:
            out.append(v)
    return out


def p12(a):
    f = Fact("P12")
    ok, r, rows = inbox(a, f, AS_OF)
    if not ok:
        return f
    for key, pe in (("A", "2026-09-30"), ("C", "2026-06-30"), ("H1", "2026-07-31")):
        old = next(x for x in U["statements"] if x["fund"] == key and x["period_end"] == pe and x["kind"] != "amended")
        new = next(x for x in U["statements"] if x["fund"] == key and x["period_end"] == pe and x["kind"] == "amended")
        row = rows.get(FUNDS[key]["canonical_name"]) or {}
        fid = row.get("fund_id")
        vals = values_of(a, f, fid, pe) if fid else []
        want = [dec(old["value"]), dec(new["value"])]
        f.check(f"{key} {pe} value history old, new", [str(x) for x in want], [str(x) for x in vals[-2:]], ok=vals[-2:] == want)
        if len(vals) >= 2:
            f.check(f"{key} {pe} change", str(want[1] - want[0]), str(vals[-1] - vals[-2]), ok=vals[-1] - vals[-2] == want[1] - want[0])
        path = f"/api/v1/managers/{slug(MGRS[FUNDS[key]['manager']]['name'])}"
        code, pr = a.call("GET", path)
        tl = [t for t in pr.get("timeline", []) if t["fund_id"] == fid and str(t["valuation_date"])[:10] == pe] if code == 200 else []
        f.req(ANALYST, "GET", path, None, code, {"timeline": tl} if code == 200 else pr)
        f.check(f"{key} {pe} profile HTTP status", 200, code)
        am = [t for t in tl if t.get("replaces")]
        f.check(f"{key} {pe} timeline has one amended statement", 1, len(am))
        if am:
            f.check(f"{key} {pe} amended received on", new["received_at"][:10], str(am[0]["received_at"])[:10])
            f.check(f"{key} {pe} amended is current", True, am[0].get("current"))
        if key == "A":
            lv = row.get("last_value") or {}
            f.check("A inbox revised_count", 1, row.get("revised_count"))
            f.check("A inbox last value", new["value"], lv.get("amount"), ok=amt_ok(lv.get("amount"), new["value"]))
            f.check("A inbox status word", "revised", lv.get("status"))
    return f


def p13(a):
    f = Fact("P13")
    ok, r, rows = inbox(a, f, AS_OF)
    if not ok:
        return f
    managed = {k: fd for k, fd in FUNDS.items() if fd["manager"]}
    f.check("one row per fund (count)", len(managed), len(rows))
    f.check("rows are the canonical fund names", sorted(fd["canonical_name"] for fd in managed.values()), sorted(rows))
    dup = sorted(n for fd in managed.values() for n in fd["identifiers"]["manager_email"]["manager_fund_name"] if n != fd["canonical_name"] and n in rows)
    f.check("no second name shows as its own row", [], dup)
    kest = next((m["funds"] for m in r["managers"] if m["name"] == MGRS["MGR-KESTREL"]["name"]), [])
    f.check("Kestrel Ridge shows two funds", 2, len(kest))
    h1 = FUNDS["H1"]
    row = rows.get(h1["canonical_name"]) or {}
    path = f"/api/v1/managers/{slug(MGRS['MGR-KESTREL']['name'])}"
    code, pr = a.call("GET", path)
    tl = [t for t in pr.get("timeline", []) if str(t["valuation_date"])[:10] == "2026-07-31" and t["fund_id"] == row.get("fund_id")] if code == 200 else []
    f.req(ANALYST, "GET", path, None, code, {"july_h1": tl} if code == 200 else pr)
    alias = next(s["title"] for s in U["statements"] if s["statement_id"] == "stmt-H1-2026-07-31-amended").split(" - July")[0]
    f.check("H1 July final and amended both sit on the one fund row", 2, len(tl))
    f.check("the July amended title carries the second name", alias, alias if any(alias in (t.get("title") or "") for t in tl) else None)
    path = "/api/v1/instruments"  # the as-of route keeps no dated identifiers and refuses that table (a3.3); Settings > identifiers reads this
    code, ir = a.call("GET", path)
    inst = next((i for i in ir.get("instruments", []) if i.get("instrument_id") == row.get("fund_id")), {}) if code == 200 else {}
    have = [inst.get("name")] + [x.get("value") for x in inst.get("names", []) + inst.get("codes", [])]
    f.req(ANALYST, "GET", path, None, code, {"identifier_values": have} if code == 200 else ir)
    need = [h1["identifiers"]["administrator"]["administrator_code"]] + h1["identifiers"]["manager_email"]["manager_fund_name"]
    f.check("H1 identifiers: code and both names", sorted(need), sorted(x for x in need if x in have))
    f.check("Fund B shows once, under its canonical name", 1, sum(1 for n in rows if n == FUNDS["B"]["canonical_name"]))
    return f


# ---------- main ----------

def main():
    global BASE, CREDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    BASE, CREDS = a.base.rstrip("/"), read_creds(Path(a.creds))
    out = Path(a.out) / "uc3"
    out.mkdir(parents=True, exist_ok=True)
    analyst = login(ANALYST)
    results = []
    for fn in (p09, p10, p11, p12, p13):
        fid = fn.__name__.upper()
        try:
            f = fn(analyst)
        except Exception as e:   # a crash is a failed fact, with the reason
            f = Fact(fid)
            f.check("checker ran", "no error", f"{type(e).__name__}: {e}")
        p = PLANTED[fid]
        (out / f"{fid}.json").write_text(json.dumps({
            "fact": fid, "what": p["fact"], "role": p["role"], "where": p["where"], "requests": f.requests,
            "response_excerpt": f.excerpt, "expected": p["expected"], "checks": f.checks,
            "actual": [c for c in f.checks if not c["pass"]] or "all checks as expected", "pass": f.passed},
            indent=1, default=str), encoding="utf-8")
        results.append((f, p))
    cell = lambda t: str(t).replace("|", "/").replace("\n", " ")  # noqa: E731
    lines = ["# UC3 result (P09-P13)", "", "| Fact | Expected | Actual | Pass/fail |", "|---|---|---|---|"]
    for f, p in results:
        bad = [c for c in f.checks if not c["pass"]]
        actual = f"all {len(f.checks)} checks as expected" if not bad else "; ".join(f"{c['check']}: expected {c['expected']}, got {c['actual']}" for c in bad)
        lines.append(f"| {f.id} {cell(p['fact'])} | {cell(p['expected'])[:200]} | {cell(actual)[:700]} | {'PASS' if f.passed else 'FAIL'} |")
    (out / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for f, _ in results:
        print(f.id, "PASS" if f.passed else "FAIL")
    sys.exit(0 if all(f.passed for f, _ in results) else 1)


if __name__ == "__main__":
    main()
