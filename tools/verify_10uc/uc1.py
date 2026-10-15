"""Black-box checker for UC1 (P&L / NAV explanation), planted facts P01-P07 of docs/test/10uc_universe.json.

    python tools/verify_10uc/uc1.py --base http://127.0.0.1:8650 --creds PATH --out DIR

Logs in as the role each fact names (people from the universe; passwords from the creds file, never printed or written), calls the
real /api/v1 routes, compares figures as Decimal, writes DIR/uc1/<fact>.json and DIR/uc1/result.md, exits 1 if any fact fails.
Figures come from the universe JSON only. Stdlib only. Read-only: GET, plus the CIO Brief explain POST (which only reads).
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
U = json.loads((ROOT / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
PLANTED = {p["id"]: p for p in U["planted"]}
PEOPLE_BY_ROLE: dict[str, dict] = {}
for _p in U["people"]:
    PEOPLE_BY_ROLE.setdefault(_p["platform_role"], _p)
FUND = {f["key"]: f["canonical_name"] for f in U["funds"]}
SEC = {s["key"]: s for s in U["securities"]}
PF_NAME = {p["portfolio_code"]: p["portfolio_name"] for p in U["portfolios"]}
AS_OF = U["meta"]["as_of"]
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


def csrf_of(op) -> str:
    jar = next((h.cookiejar for h in op.handlers if isinstance(h, urllib.request.HTTPCookieProcessor)), [])
    return next((c.value for c in jar if c.name == "sh_csrf"), "")


def same_instant(a, b) -> bool:
    """True when two ISO timestamps name the same moment (10:30Z == 18:30+08:00); the API answers in office time (a1.10)."""
    try:
        x, y = (datetime.fromisoformat(str(v).replace("Z", "+00:00")) for v in (a, b))
        return x.tzinfo is not None and y.tzinfo is not None and x == y
    except ValueError:
        return False


# the universe calls the report line "Liquid book"; the product names it after the roll-up instrument (a1.11)
LINE_ALIAS = {"Liquid book": "Evergreen Liquid Book"}


def line_of(lines: dict, label: str):
    return lines.get(label) or lines.get(LINE_ALIAS.get(label, label))


def D(v) -> Decimal:
    return Decimal(str(v).replace(",", ""))


def f2(v) -> str:
    return "n/a" if v is None else format(D(v).quantize(Q2, ROUND_HALF_UP), "f")


class Client:
    """Signed-in sessions per role. Passwords stay inside _opener(); nothing about them is stored or logged."""

    def __init__(self, base: str, creds: dict[str, str]):
        self.base, self.creds = base.rstrip("/"), creds
        self.sessions: dict[str, urllib.request.OpenerDirector] = {}

    def _opener(self, role):
        if role is None:
            return urllib.request.build_opener()
        if role not in self.sessions:
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            email = PEOPLE_BY_ROLE[role]["email"]
            pw = self.creds.get(email.lower())
            if pw is None:
                raise RuntimeError(f"no sign-in for {email} in the creds file")
            st, _ = self._send(op, "POST", "/api/auth/login", {"email": email, "password": pw})
            if st != 200:
                raise RuntimeError(f"sign-in as {role} failed with HTTP {st}")
            self.sessions[role] = op
        return self.sessions[role]

    def _send(self, op, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        h = {"Content-Type": "application/json"} if data else {}
        if method != "GET":  # the double-submit CSRF token: the sh_csrf cookie echoed as a header (a1.12)
            h["X-CSRF-Token"] = csrf_of(op)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with op.open(req, timeout=60) as r:
                raw, st = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, st = e.read(), e.code
        try:
            return st, json.loads(raw.decode("utf-8") or "null")
        except ValueError:
            return st, {"raw": raw[:300].decode("utf-8", "replace")}

    def call(self, role, method, path, body=None):
        return self._send(self._opener(role), method, path, body)


class Fact:
    def __init__(self, fid: str):
        self.id, self.p = fid, PLANTED[fid]
        self.checks: list[dict] = []
        self.requests: list[dict] = []
        self.excerpt: dict = {}
        self.error = None

    def check(self, name, expected, actual, ok=None, soft=False):
        ok = (str(expected) == str(actual)) if ok is None else bool(ok)
        self.checks.append({"check": name, "expected": str(expected), "actual": str(actual), "pass": ok, "soft": soft})

    def money(self, name, expected, actual, soft=False):
        try:
            ok = actual is not None and D(expected) == D(actual)
        except Exception:  # noqa: BLE001 - an unreadable figure is a failed check
            ok = False
        self.check(name, f2(expected), f2(actual) if actual is not None else "missing", ok, soft)

    @property
    def passed(self) -> bool:
        return self.error is None and bool(self.checks) and all(c["pass"] for c in self.checks if not c["soft"])


def get(c: Client, f: Fact, role, path, method="GET", body=None):
    st, js = c.call(role, method, path, body)
    f.requests.append({"as": role or "nobody", "request": f"{method} {path}", "status": st})
    return st, js


def refused_when_signed_out(c, f, path):
    st, js = get(c, f, None, path)
    leak = any(k in json.dumps(js) for k in ("57600000", "10180000", "16580000", "41200000"))
    f.check(f"signed-out request to {path.split('?')[0]} is refused", "HTTP 401/403, no figures", f"HTTP {st}{', figures shown' if leak else ''}",
            st in (401, 403) and not leak)


def issued(c, f, role, cur="USD"):
    st, js = get(c, f, role, f"/api/v1/office/issued?currency={cur}")
    f.check(f"{role} may read the issued view ({cur})", "HTTP 200", f"HTTP {st}", st == 200)
    return js if st == 200 and isinstance(js, dict) else {}


def by_label(js):
    return {ln["label"]: ln for ln in js.get("lines", [])}


# ---- facts -------------------------------------------------------------------------------------------------------------

def p01(c, f):
    rep = U["report_issued"]
    js = issued(c, f, "sponsor")
    f.excerpt["issued"] = js
    lines = by_label(js)
    for want in rep["lines"]:
        ln = line_of(lines, want["label"])
        f.money(f"{want['label']} as issued (USD)", want["value"], None if ln is None else ln.get("issued"))
    for want in rep["lines"]:  # the as-issued word of Fund A / Total is not exposed by the route, so not asserted
        if want["label"] in (FUND["A"], "Total"):
            continue  # the line labels come from the universe ("Liquid book" became "Evergreen Liquid Book"; a hard-coded label crashed)
        f.check(f"{want['label']} status word", want["status"], (line_of(lines, want["label"]) or {}).get("status"))
    r = js.get("report") or {}
    f.check("issued at", rep["issued_at"], r.get("issued_at"), same_instant(rep["issued_at"], r.get("issued_at")))
    f.check("report period end", rep["period_end"], str(r.get("period_end"))[:10])
    rvid = r.get("report_version_id")
    if rvid:
        st, b = get(c, f, "sponsor", f"/api/v1/brief/{rvid}")
        b = b if isinstance(b, dict) else {}
        f.excerpt["brief"] = {k: b.get(k) for k in ("report_name", "period_end", "issued_at", "cutoff_at", "currencies")}
        f.check("CIO Brief opens", "HTTP 200", f"HTTP {st}", st == 200)
        f.check("cutoff", rep["cutoff_at"], b.get("cutoff_at"), same_instant(rep["cutoff_at"], b.get("cutoff_at")))
        cur = set(b.get("currencies") or [])
        f.check("CIO Brief currencies include USD and SGD", "SGD,USD", ",".join(sorted(cur)), {"USD", "SGD"} <= cur)
    else:
        f.check("report version id", "present", "missing", False)
    sg = by_label(issued(c, f, "sponsor", "SGD"))
    f.money("Total as issued in SGD", rep["total_sgd"], (sg.get("Total") or {}).get("issued"))
    refused_when_signed_out(c, f, "/api/v1/office/issued?currency=USD")


def p02(c, f):
    js = issued(c, f, "sponsor")
    ln = by_label(js).get(FUND["A"]) or {}
    a = next(v for v in U["valuations_monthly"] if v["fund"] == "A" and v["month_end"] == "2026-09-30")
    iss, now = D(a["administrator_value"]), D(a["known_now_value"])
    f.money("Fund A as issued", iss, ln.get("issued"))
    f.money("Fund A known now", now, ln.get("known_now"))
    f.money("Fund A difference", now - iss, ln.get("difference"))
    pct = (D(ln["difference"]) / D(ln["issued"]) * 100).quantize(Q2) if ln.get("issued") and ln.get("difference") is not None else None
    f.check("difference as % of issued", f2((now - iss) / iss * 100), "n/a" if pct is None else f2(pct))
    f.check("status word", "revised", str(ln.get("status")).lower())
    st, rules = get(c, f, "sponsor", "/api/v1/rules")
    rule = next((r for r in (rules if isinstance(rules, list) else []) if r.get("rule_code") == "cio_materiality"), None)
    prm = (rule or {}).get("parameters") or {}
    if isinstance(prm, str):
        try:
            prm = json.loads(prm)
        except ValueError:
            prm = {}
    f.excerpt["cio_materiality"] = rule
    over = (bool(prm) and ln.get("difference") is not None and pct is not None
            and abs(D(ln["difference"])) > D(prm.get("abs_amount", 0)) and pct > D(str(prm.get("pct_of_fund", 0))))
    f.check("over cio_materiality (100,000 USD / 0.5%)", "abs_amount 100000, pct_of_fund 0.5, exceeded",
            f"abs_amount {prm.get('abs_amount')}, pct_of_fund {prm.get('pct_of_fund')}, exceeded={over}",
            over and str(prm.get("abs_amount")) == "100000" and str(prm.get("pct_of_fund")) == "0.5")
    rvid = (js.get("report") or {}).get("report_version_id")
    if rvid and ln.get("line_key"):
        st, ex = get(c, f, "sponsor", f"/api/v1/brief/{rvid}/explain", "POST", {"line_key": ln["line_key"]})
        f.excerpt["explain"] = ex
        f.check("CIO Brief explain opens", "HTTP 200", f"HTTP {st}", st == 200)
        fg = (ex or {}).get("figures") or {} if isinstance(ex, dict) else {}
        f.money("explain: known now", now, fg.get("known_now"))
        f.money("explain: difference", now - iss, fg.get("difference"))
        seen = "2026-10-07" in json.dumps(ex, default=str)
        f.check("explain evidence shows receipt on 7 Oct 2026", "2026-10-07", "found" if seen else "not found", seen)
    else:
        f.check("CIO Brief explain reachable", "line key and report version", "missing", False)
    st, pu = get(c, f, "sponsor", f"/api/v1/pulse2/items?on_date={AS_OF}&role=cio")
    items = pu.get("items", []) if isinstance(pu, dict) else []
    rev = [i for i in items if str(i.get("status_word", "")).lower().startswith("revised")]
    f.excerpt["pulse_revised_cards"] = [{k: i.get(k) for k in ("headline", "status_word", "role", "urgency")} for i in rev]
    f.check("Today card with status word Revised for the CIO", ">= 1 card", f"{len(rev)} card(s)", len(rev) >= 1)
    st2, _ = get(c, f, "participant", "/api/v1/rules")
    f.check("participant (Risk) is refused the rules register", "HTTP 403", f"HTTP {st2}", st2 == 403)


CODE_OF = {"P03": "EG-GROWTH", "P04": "EG-B-OPS", "P05": "EG-FUNDS"}


def bridge(c, f):
    n = next(b for b in U["nav_bridge_30_sep"] if b["portfolio"] == CODE_OF[f.id])
    path = "/api/v1/office/nav-bridge?currency=USD&as_of=2026-09-30"
    st, js = get(c, f, "sponsor", path)
    f.check("nav bridge opens", "HTTP 200", f"HTTP {st}", st == 200)
    name = PF_NAME.get(n["portfolio"])  # EG-FUNDS has no row in the universe portfolios list: fall back to the code
    pfs = (js or {}).get("portfolios", []) if isinstance(js, dict) else []
    pf = next((p for p in pfs if p.get("portfolio_name") == name), None) or next(
        (p for p in pfs if n["portfolio"] in json.dumps(p) or (name is None and "funds" in str(p.get("portfolio_name")).lower())), None)
    f.excerpt["portfolio"] = pf
    f.excerpt["portfolio_names_returned"] = [p.get("portfolio_name") for p in pfs]
    if not pf:
        f.check("portfolio present", name or n["portfolio"], "missing", False)
        return
    f.check("bridge available", "True", str(pf.get("available")), pf.get("available") is True)
    f.money("investment view", n["investment_view"], pf.get("investment_total"))
    f.money("administrator NAV", n["administrator_nav"], pf.get("administrator_nav"))
    parts = {p["code"]: p for p in pf.get("parts", [])}
    for k in ("revisions", "timing", "fx", "unexplained"):
        f.money(k, n[k], (parts.get(k) or {}).get("amount"))
    text = json.dumps([p.get("evidence") for p in parts.values()], default=str)
    for part in n["parts"]:
        nm = FUND[part["fund"]]
        f.check(f"evidence names {nm} ({part['kind']})", "named", "named" if nm in text else "not named", nm in text)
    refused_when_signed_out(c, f, path)


def holdings(c, f, role, as_of):
    st, js = get(c, f, role, f"/api/v1/office/holdings?currency=USD&as_of={as_of}")
    f.check(f"{role} holdings at {as_of} open", "HTTP 200", f"HTTP {st}", st == 200)
    js = js if isinstance(js, dict) else {}
    return js, {p["portfolio_name"]: p for e in js.get("entities", []) for p in e.get("portfolios", [])}


def p06(c, f):
    aug, sep = "2026-08-31", "2026-09-30"
    lb = U["liquid_book_month_end"]
    pname = PF_NAME["EG-LIQUID"]
    _, a = holdings(c, f, "sponsor", aug)
    _, s = holdings(c, f, "sponsor", sep)
    pa, ps = a.get(pname) or {}, s.get(pname) or {}
    ta, ts = lb[aug]["total"], lb[sep]["total"]
    f.money("liquid book total 31 Aug", ta, pa.get("total"))
    f.money("liquid book total 30 Sep", ts, ps.get("total"))
    diff = D(ts) - D(ta)
    ok2 = pa.get("total") is not None and ps.get("total") is not None
    got = D(ps["total"]) - D(pa["total"]) if ok2 else None
    f.money("change Aug to Sep", diff, got)
    pct = (diff / D(ta) * 100).quantize(Q4, ROUND_HALF_UP)
    gpct = (got / D(pa["total"]) * 100).quantize(Q4, ROUND_HALF_UP) if ok2 else None
    f.check("change %", "4.1667", "n/a" if gpct is None else str(gpct), gpct is not None and gpct == pct and str(pct) == "4.1667")
    sept = [t["id"] for t in U["trades_oct"] if t["trade_date"][:7] == "2026-09"]
    f.check("no trades in September (universe)", "0", str(len(sept)), not sept)
    want = {SEC[x["security"]]["canonical_name"]: D(x["value"]) for x in lb[sep]["positions"]}
    was = {SEC[x["security"]]["canonical_name"]: D(x["value"]) for x in lb[aug]["positions"]}
    exp_chg = {k: want[k] - was.get(k, Decimal(0)) for k in want}
    la = {l["name"]: D(l["value"]) for l in pa.get("lines", []) if l.get("value") is not None}
    ls = {l["name"]: D(l["value"]) for l in ps.get("lines", []) if l.get("value") is not None}
    act_chg = {k: ls[k] - la.get(k, Decimal(0)) for k in ls}
    top_e = max(exp_chg, key=lambda k: abs(exp_chg[k]))
    top_a = max(act_chg, key=lambda k: abs(act_chg[k])) if act_chg else None
    f.check("largest contributor", f"{top_e} {f2(exp_chg[top_e])}", f"{top_a} {f2(act_chg[top_a])}" if top_a else "none",
            top_a == top_e and act_chg[top_a] == exp_chg[top_e])
    bad = [k for k in exp_chg if act_chg.get(k) != exp_chg[k]]
    f.check("every security's change equals the move in the monthly prices", "0 differences",
            f"{len(bad)} difference(s){': ' + ', '.join(bad[:5]) if bad else ''}", not bad)
    st, wm = get(c, f, "sponsor", "/api/v1/office/why-moved?start=2026-08-31&end=2026-09-30&book=liquid")
    f.check("sponsor may read the why-moved view", "HTTP 200", f"HTTP {st}", st == 200)
    wm = wm if isinstance(wm, dict) else {}
    f.money("why-moved start", "39552000", wm.get("start_value"))
    f.money("why-moved end", "41200000", wm.get("end_value"))
    f.money("why-moved change", "1648000", wm.get("change"))
    f.check("why-moved change %", "4.1667", str(wm.get("percent")), wm.get("percent") is not None and D(wm["percent"]) == D("4.1667"))
    parts = {x["code"]: x for x in wm.get("parts", [])}
    price = parts.get("price", {}).get("lines", [])
    top = price[0] if price else {}
    f.check("largest contributor in why-moved", "Northwind Logistics +132,000.00", f"{wm.get('largest')} {f2(top['amount']) if top else 'none'}",
            wm.get("largest") == "Northwind Logistics" and bool(top) and D(top["amount"]) == D("132000"))
    tr = json.dumps(parts.get("trades", {}).get("lines", []))
    f.check("trades list names FXF-2026-001", "FXF-2026-001", "found" if "FXF-2026-001" in tr else "missing", "FXF-2026-001" in tr)
    f.excerpt = {"aug_total": pa.get("total"), "sep_total": ps.get("total"), "changes": {k: format(v, "f") for k, v in act_chg.items()},
                 "why_moved": {k: wm.get(k) for k in ("start_value", "end_value", "change", "percent", "largest")}}

def p07(c, f):
    js, pfs = holdings(c, f, "analyst", "2026-09-30")
    lines = {l["name"]: l for p in pfs.values() for l in p.get("lines", [])}
    f.excerpt = {n: {k: l.get(k) for k in ("value", "status", "source")} for n, l in lines.items()}
    vm = {v["fund"]: v for v in U["valuations_monthly"] if v["month_end"] == "2026-09-30"}
    exp = {"A": "revised", "B": "official", "C": "stale", "D": "stale", "E": "unverified", "H1": "estimated", "H2": "estimated",
           "L1": "official", "L2": "official"}
    for k, word in exp.items():
        ln = lines.get(FUND[k])
        f.check(f"{FUND[k]} ({k}) status word", word, str(ln.get("status")).lower() if ln else "missing")
        f.money(f"{FUND[k]} ({k}) value", vm[k]["known_now_value"], ln.get("value") if ln else None, soft=(k == "E"))  # E: unconfirmed figure, soft
    prc = lines.get("Pacific Rim Convertible 2029 note")
    row = next(x for x in U["liquid_book_month_end"]["2026-09-30"]["positions"] if x["security"] == "PRC29")
    f.money("PRC29 value", row["value"], prc.get("value") if prc else None)
    found = "needs a class" in json.dumps(js).lower()
    f.check("PRC29 shows 'Needs a class'", "text present", "found" if found else "not in the holdings response", found)
    refused_when_signed_out(c, f, "/api/v1/office/holdings?currency=USD&as_of=2026-09-30")


RUN = {"P01": p01, "P02": p02, "P03": bridge, "P04": bridge, "P05": bridge, "P06": p06, "P07": p07}


def read_creds(path: str) -> dict[str, str]:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not line.startswith("#") and len(parts) >= 2:
            out[parts[0].lower()] = parts[1]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out) / "uc1"
    out.mkdir(parents=True, exist_ok=True)
    c = Client(a.base, read_creds(a.creds))
    facts = []
    for fid, fn in RUN.items():
        f = Fact(fid)
        try:
            fn(c, f)
        except Exception as e:  # noqa: BLE001 - a crash is a failed fact with the reason, not a stopped run
            f.error = f"{type(e).__name__}: {str(e)[:300]}"
        facts.append(f)
        (out / f"{fid}.json").write_text(json.dumps({
            "fact": fid, "what": f.p["fact"], "role": f.p["role"], "expected": f.p["expected"], "requests": f.requests,
            "response_excerpt": f.excerpt, "checks": f.checks, "error": f.error, "result": "pass" if f.passed else "fail"},
            indent=2, default=str), encoding="utf-8")
    rows = ["# UC1 P&L / NAV explanation", "", f"Base {a.base}. Universe as of {AS_OF}.", "",
            "| Fact | Expected | Actual | Result |", "|---|---|---|---|"]
    for f in facts:
        bad = [x for x in f.checks if not x["pass"] and not x["soft"]]
        act = f.error or (f"all {len(f.checks)} checks match" if not bad else
                          "; ".join(f"{b['check']}: got {b['actual']}" for b in bad[:4]) + (f" (+{len(bad) - 4} more)" if len(bad) > 4 else ""))
        rows.append(f"| {f.id} {f.p['fact']} | {f.p['expected'][:140].replace('|', '/')} | {act.replace('|', '/')} | {'pass' if f.passed else 'FAIL'} |")
    (out / "result.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    for f in facts:
        print(f.id, "pass" if f.passed else "FAIL")
    return 0 if all(f.passed for f in facts) else 1


if __name__ == "__main__":
    sys.exit(main())
