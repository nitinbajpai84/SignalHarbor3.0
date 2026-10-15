"""UC7 Manager diligence research: black-box checker for planted facts P25-P27 (docs/test/10uc_universe.json).

python tools/verify_10uc/uc7.py --base http://127.0.0.1:PORT --creds PATH --out DIR
Logs in as the people the facts name, calls the product's /api/v1 routes, compares with the universe, writes DIR/uc7/<fact>.json and
DIR/uc7/result.md, exits 1 if any fact fails. Passwords come from the creds file and are never printed or written. Stdlib only."""
from __future__ import annotations

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

REPO = Path(__file__).resolve().parents[2]
U = json.loads((REPO / "docs" / "test" / "10uc_universe.json").read_text(encoding="utf-8"))
JUDGING = re.compile(r"\b(good news|bad news|concern|worrying|red flag|warning|positive|negative|alarming|encouraging|troubling)\b", re.I)
EXCERPT = 1500


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def dec(v):
    return Decimal(str(v).replace(",", ""))


def bdays_after(due: date, got: date) -> int:
    return sum(1 for i in range(1, (got - due).days + 1) if (due + timedelta(days=i)).weekday() < 5)


class Client:
    def __init__(self, base, email=None, password=None, label="anonymous"):
        self.base, self.label, self.csrf = base.rstrip("/"), label, ""
        self.jar = CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.log = []
        self.signed_in = False
        if email:
            st, _ = self.call("POST", "/api/auth/login", {"email": email, "password": password}, log=False)
            self.signed_in = st == 200
            self.csrf = next((c.value for c in self.jar if c.name == "sh_csrf"), "")
            self.log.append({"request": f"POST /api/auth/login as {label}", "status": st})

    def call(self, method, path, body=None, log=True):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json"} if data is not None else {}
        if method != "GET" and self.csrf:
            h["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with self.op.open(req, timeout=60) as r:
                st, raw = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            st, raw = e.code, e.read().decode("utf-8", "replace")
        except OSError as e:
            st, raw = 0, str(e)
        try:
            js = json.loads(raw)
        except ValueError:
            js = raw
        if log:
            self.log.append({"request": f"{method} {path} as {self.label}", "status": st, "response_excerpt": raw[:EXCERPT]})
        return st, js


class Fact:
    def __init__(self, fid):
        self.p = next(x for x in U["planted"] if x["id"] == fid)
        self.id, self.checks, self.calls = fid, [], []

    def check(self, name, expected, actual, ok, who="", blame=""):
        self.checks.append({"check": name, "expected": str(expected), "actual": str(actual)[:400], "pass": bool(ok), "who": who, "if_wrong": blame})

    @property
    def passed(self):
        return bool(self.checks) and all(c["pass"] for c in self.checks)


def person(role_name):
    return next(p for p in U["people"] if p["platform_role"] == role_name)


def fund(key):
    return next(f for f in U["funds"] if f["key"] == key)


def doc(did):
    return next(d for d in U["documents"] if d["id"] == did)


def stmt(sid):
    return next(s for s in U["statements"] if s["statement_id"] == sid)


def manager(mid):
    return next(m for m in U["managers"] if m["id"] == mid)


def prev(p) -> str:
    """A document preview is text, or a table {heading, columns} (a7.0: joining the dict crashed the checker)."""
    return p if isinstance(p, str) else json.dumps(p) if p else ""


def negatives(fact, roles_named, clients, path, marker):
    """Anonymous is refused; every other office role may read manager research: the routes use the Consumer seat and the answer key
    opens manager documents to the office (a7.4). The name is kept so the three facts read the same."""
    seen = set(roles_named) | {"company_admin"}
    anon = Client(clients["__base__"])
    st, _ = anon.call("GET", path)
    fact.calls += anon.log
    fact.check("anonymous is refused", "401/403", st, st in (401, 403), "anonymous", "product")
    for p in U["people"]:
        if p["platform_role"] in seen:
            continue
        seen.add(p["platform_role"])
        c = clients.get(p["name"])
        if not c or not c.signed_in:
            fact.check(f"{p['name']} ({p['platform_role']}) signs in", "signed in", "no sign-in", False, p["name"], "seed (creds) or product")
            continue
        st, body = c.call("GET", path)
        fact.calls += c.log[-1:]
        shown = st == 200 and marker(json.dumps(body))
        fact.check(f"{p['name']} ({p['platform_role']}) may read it too", "HTTP 200 with the fact",
                   f"HTTP {st}" + (", fact present" if shown else ""), shown, p["name"], "product (office roles read manager research)")


def run(base, creds_path, out):
    creds = {}
    for line in Path(creds_path).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("#") and len(parts) >= 2:
            creds[parts[0].lower()] = parts[1]
    clients = {"__base__": base}
    for p in U["people"]:
        pw = creds.get(p["email"].lower())
        clients[p["name"]] = Client(base, p["email"], pw, p["name"]) if pw else None
    kr, cp = slug(manager("MGR-KESTREL")["name"]), slug(manager("MGR-CEDARPOINT")["name"])
    as_of = U["meta"]["as_of"]
    facts = []

    def who(fact, name):
        c = clients.get(name)
        if not c or not c.signed_in:
            fact.check(f"{name} signs in", "signed in", "failed or no credentials", False, name, "seed (creds) or product")
            return None
        return c

    # ---------------- P25 ----------------
    f = Fact("P25"); facts.append(f)
    news = doc("doc-news-01")
    fact_text = news["key_facts"][0]
    left = re.search(r"(\w+ \w+) left", fact_text).group(1)
    sole = re.search(r"(\w+ \w+) is sole portfolio manager", fact_text).group(1)
    day = re.search(r"\d{1,2} \w+ 2026", fact_text).group(0)
    since = doc("doc-note-04")["document_date"]
    path = f"/api/v1/managers/{kr}/changes?since={since}"
    roles = [r.strip() for r in f.p["role"].split(",")]
    for r in roles:
        pn = person(r)["name"]
        c = who(f, pn)
        if not c:
            continue
        st, prof = c.call("GET", f"/api/v1/managers/{kr}")
        _, ch = c.call("GET", path)
        f.calls += c.log[-2:]
        docs = prof.get("documents", []) if isinstance(prof, dict) else []
        f.check(f"{pn}: manager page opens", 200, st, st == 200, pn, "product")
        f.check(f"{pn}: newsletter is on the manager page", news["title"], [d.get("name") for d in docs],
                any(news["title"] in (d.get("name") or "") for d in docs), pn, "seed (library upload) or product")
        chips = ch.get("passages", []) if isinstance(ch, dict) else []
        hit = [x for x in chips if news["title"] in x.get("file", "") and left in x.get("text", "") and sole in x.get("text", "")]
        f.check(f"{pn}: source chip carries '{left}' and '{sole}' with file and place", "chip with file, from, to, text",
                json.dumps(hit[:1] or chips[:2])[:300], bool(hit) and all(k in hit[0] for k in ("file", "from", "to")), pn,
                "product (passage search did not return the newsletter) or seed (PDF text)")
        f.check(f"{pn}: the passage names the date {day}", day, hit[0]["text"][:200] if hit else "no chip",
                bool(hit) and day in hit[0]["text"], pn, "seed (PDF text) or universe (date wording)")
        said = (" ".join([x.get("text", "") for x in ch.get("items", [])] + [x.get("text", "") for x in chips])) if isinstance(ch, dict) else ""
        f.check(f"{pn}: no verdict words", "none", JUDGING.findall(said), not JUDGING.search(said), pn, "product")
    negatives(f, roles, clients, path, lambda t: news["title"].lower() in t.lower() or left in t)

    # ---------------- P26 ----------------
    f = Fact("P26"); facts.append(f)
    c = who(f, person("sponsor")["name"])
    h1, h2 = fund("H1"), fund("H2")
    am, fin, first = stmt("stmt-H1-2026-07-31-amended"), stmt("stmt-H2-2026-08-31-final"), stmt("stmt-H1-2026-07-31-final")
    if c:
        st, ch = c.call("GET", f"/api/v1/managers/{kr}/changes")
        f.calls += c.log[-1:]
        ch = ch if isinstance(ch, dict) else {}
        items = ch.get("items", [])
        f.check("last meeting date", since, ch.get("since", st), ch.get("since") == since, "sponsor", "seed (meeting note not loaded) or product")
        f.check("nothing dated on or before the meeting", "none", [i["date"] for i in items if i["date"] <= since],
                not any(i["date"] <= since for i in items), "sponsor", "product")
        a = [i for i in items if i["kind"] == "statement" and i["date"] == am["received_at"][:10] and "revised" in i["text"].lower()
             and h1["canonical_name"] in i["text"] and "31 Jul 2026" in i["text"]]
        f.check("July amended statement listed on its received date", f"{am['received_at'][:10]} revised statement for {h1['canonical_name']} 31 Jul 2026",
                a[0]["text"] if a else [i["text"] for i in items if "Jul 2026" in i["text"]], bool(a), "sponsor",
                "product or seed (statement not loaded as an amendment)")
        figs = [i for i in items if "7,012,500" in i["text"] and "7,050,000" in i["text"]]
        f.check("'what changed' states the amendment from 7,050,000 to 7,012,500", "both figures in the answer",
                [i["text"] for i in items if "Jul 2026" in i["text"]], bool(figs), "sponsor",
                "product (item says a revised statement arrived, gives no figures) or universe (expects figures the answer does not carry)")
        b = [i for i in items if i["kind"] == "statement" and i["date"] == fin["received_at"][:10]
             and h2["canonical_name"] in i["text"] and "31 Aug 2026" in i["text"]]
        f.check("August Equity Long/Short statement listed on 22 Sep 2026", f"{fin['received_at'][:10]} {h2['canonical_name']} 31 Aug 2026",
                b[0]["text"] if b else [i["text"] for i in items if "Aug 2026" in i["text"]], bool(b), "sponsor", "product or seed")
        c2 = [i for i in items if i["kind"] == "document" and news["title"] in i["text"] and i["date"] == news["document_date"]]
        f.check("newsletter listed on 28 Sep 2026", f"{news['document_date']} {news['title']}",
                c2[0]["text"] if c2 else [i["text"] for i in items if i["kind"] == "document"], bool(c2), "sponsor", "product or seed (library date stamp)")
        hit = [x for x in ch.get("passages", []) if left in x.get("text", "") and sole in x.get("text", "")]
        f.check("newsletter passage names the team change", f"{left} / {sole}", json.dumps(hit[:1])[:250], bool(hit), "sponsor",
                "product (search) or seed (PDF text)")
        # lateness from the inbox, taken at the end of September so August is the period
        _, ib = c.call("GET", "/api/v1/managers/inbox?as_of=2026-09-30")
        f.calls += c.log[-1:]
        row = next((x for m in (ib.get("managers", []) if isinstance(ib, dict) else []) if m["manager_id"] == kr
                    for x in m["funds"] if x["fund_name"] == h2["canonical_name"]), {})
        f.check("inbox: August statement received 22 Sep 2026, due 14 Sep 2026", f"{fin['received_at'][:10]} / {fin['due_date']}",
                f"{row.get('received_on')} / {row.get('due')}",
                row.get("received_on") == fin["received_at"][:10] and row.get("due") == fin["due_date"], "sponsor", "product or seed")
        if row.get("received_on") and row.get("due"):
            bd = bdays_after(date.fromisoformat(row["due"]), date.fromisoformat(row["received_on"]))
            f.check("business days from the product's own due and received dates", fin["late_business_days"], bd,
                    bd == fin["late_business_days"], "sponsor", "universe")
        f.check("inbox days_late equals 6 business days", fin["late_business_days"], row.get("days_late"),
                row.get("days_late") == fin["late_business_days"], "sponsor",
                "product (inbox counts calendar days, received minus due) while the signed rule and the universe count business days")
        # the figures, as known before the amendment and now
        _, fl = c.call("GET", f"/api/v1/evidence/asof?table=valuation_observations&cutoff={am['received_at'][:10]}T00:00:00Z")
        _, nowrows = c.call("GET", "/api/v1/evidence/asof?table=valuation_observations")
        f.calls += c.log[-2:]

        def july(rows):
            return [r for r in (rows.get("rows", []) if isinstance(rows, dict) else [])
                    if str(r.get("valuation_date"))[:10] == am["period_end"] and dec(r["value_amount"]) in (dec(first["value"]), dec(am["value"]))]
        before, after = july(fl), july(nowrows)
        f.check("as known before 20 Aug: July NAV", dec(first["value"]), [r["value_amount"] for r in before],
                any(dec(r["value_amount"]) == dec(first["value"]) for r in before), "sponsor", "seed or product (as-of query)")
        f.check("as known now: July NAV", dec(am["value"]), [r["value_amount"] for r in after],
                any(dec(r["value_amount"]) == dec(am["value"]) for r in after), "sponsor", "seed or product")
    negatives(f, ["sponsor"], clients, f"/api/v1/managers/{kr}/changes", lambda t: "revised statement" in t.lower())

    # ---------------- P27 ----------------
    f = Fact("P27"); facts.append(f)
    fc, fd = fund("C"), fund("D")
    cc = next(x for x in U["commitments"] if x["fund"] == "C")
    cd = next(x for x in U["commitments"] if x["fund"] == "D")
    ddq, note3 = doc("doc-ddq-02"), doc("doc-note-03")
    jun, mar = stmt("stmt-D-2026-06-30-missing"), stmt("stmt-D-2026-03-31-final")
    roles = [r.strip() for r in f.p["role"].split(",")]
    for r in roles:
        pn = person(r)["name"]
        c = who(f, pn)
        if not c:
            continue
        st, prof = c.call("GET", f"/api/v1/managers/{cp}")
        _, ib = c.call("GET", f"/api/v1/managers/inbox?as_of={as_of}")
        _, ch = c.call("GET", f"/api/v1/managers/{cp}/changes?since=2026-01-01")
        f.calls += c.log[-3:]
        P = prof if isinstance(prof, dict) else {}
        f.check(f"{pn}: profile opens", 200, st, st == 200, pn, "product")
        want = sorted([fc["canonical_name"], fd["canonical_name"]])
        names = sorted(x["fund_name"] for x in P.get("funds", []))
        f.check(f"{pn}: funds C and D", want, names, names == want, pn, "seed or product")
        by_fund = {x["fund_id"]: x["fund_name"] for x in P.get("funds", [])}
        crow = P.get("commitments", {}).get("rows", [])
        for k, uc_ in (("C", cc), ("D", cd)):
            g = next((x for x in crow if by_fund.get(x["fund_id"]) == fund(k)["canonical_name"]), {})
            # a confirmed October notice counts as called once confirmed (answer key P24 and its item 3; a7.3)
            later = sum((dec(m["amount"]) for m in U["cash_movements"] if m.get("fund") == k and m.get("notice_kind") == "call"
                         and m.get("confirmation_status") == "confirmed" and str(m.get("due_date")) > as_of), Decimal(0))
            want_f = {"commitment": dec(uc_["commitment_amount"]), "called": dec(uc_["called_to_date"]) + later,
                      "uncalled": dec(uc_["commitment_amount"]) - dec(uc_["called_to_date"]) - later}
            for field in ("commitment", "called", "uncalled"):
                f.check(f"{pn}: Fund {k} {field}", want_f[field], g.get(field), field in g and dec(g[field]) == want_f[field], pn,
                        "seed or product" if field == "commitment" else "product (calls counted differently) or seed")
        D = next((x for x in P.get("funds", []) if x["fund_name"] == fd["canonical_name"]), {})
        lv = D.get("last_value") or {}
        f.check(f"{pn}: Fund D last valuation 31 Mar 2026, 4,650,000", f"{mar['period_end']} {dec(mar['value'])}", f"{lv.get('valuation_date')} {lv.get('amount')}",
                lv.get("valuation_date") == mar["period_end"] and lv.get("amount") is not None and dec(lv["amount"]) == dec(mar["value"]), pn, "seed or product")
        ibD = next((x for m in (ib.get("managers", []) if isinstance(ib, dict) else []) if m["manager_id"] == cp
                    for x in m["funds"] if x["fund_name"] == fd["canonical_name"]), {})
        miss = [e for e in ibD.get("earlier_missing", []) if e["period_end"] == jun["period_end"]]
        f.check(f"{pn}: June statement shown as missing, due {jun['due_date']}", f"{jun['period_end']} due {jun['due_date']}",
                miss or ibD.get("earlier_missing"), bool(miss) and miss[0]["due"] == jun["due_date"], pn, "product or seed")
        blob = (json.dumps(ibD) + json.dumps(P.get("funds", []))).lower()
        f.check(f"{pn}: last value called stale in words", "the word stale on the fund", lv.get("valuation_date"), "stale" in blob, pn,
                "product (profile gives the date but never says stale) or universe (wording)")
        qs = [q for q in P.get("questions", []) if q.get("state") == "open" and "30 June 2026" in q.get("text", "") and "Cedarpoint Opportunities II" in q.get("text", "")]  # C2-UC7-04: the fund by name, not "Fund D"
        f.check(f"{pn}: open question about the June statement", "open question naming Cedarpoint Opportunities II and 30 June 2026",
                [q.get("text") for q in P.get("questions", [])], bool(qs), pn, "seed or product")
        dd = [d for d in P.get("documents", []) if ddq["title"] in (d.get("name") or "")]
        f.check(f"{pn}: DDQ listed", ddq["title"], [d.get("name") for d in P.get("documents", [])], bool(dd), pn, "seed (library) or product")
        text = " ".join([prev(d.get("preview")) for d in dd] + [x.get("text", "") for x in (ch.get("passages", []) if isinstance(ch, dict) else [])]).lower()
        f.check(f"{pn}: DDQ terms reachable: quarterly statements within 45 days", "45 days", text[:200], "45 days" in text, pn,
                "product (no route returns DDQ text for a profile; passages only search documents newer than the cut) or seed (PDF text)")
        f.check(f"{pn}: DDQ terms reachable: auditor change in Q2 2026", "auditor change, Q2 2026", text[:200],
                "auditor" in text and "q2 2026" in text, pn, "product (as above) or seed")
        meet = [n for n in P.get("notes", []) if n.get("kind") == "meeting" and n.get("on") == note3["document_date"] and "auditor change" in n.get("text", "")]
        f.check(f"{pn}: LP call note of {note3['document_date']} (auditor change) is on the profile", "meeting note",
                [n.get("on") for n in P.get("notes", [])], bool(meet), pn, "seed")
    negatives(f, roles, clients, f"/api/v1/managers/{cp}", lambda t: "6000000" in t)

    # ---------------- output ----------------
    d = Path(out) / "uc7"
    d.mkdir(parents=True, exist_ok=True)
    esc = lambda s: str(s).replace("|", "/").replace("\n", " ")[:160]  # noqa: E731
    md = ["# UC7 Manager diligence research", "", f"Base: {base}  |  as of {as_of}", "",
          "| Fact | Check | Expected | Actual | Pass |", "|---|---|---|---|---|"]
    for f in facts:
        (d / f"{f.id}.json").write_text(json.dumps({"fact": f.id, "title": f.p["fact"], "where": f.p["where"], "roles": f.p["role"],
                                                    "expected": f.p["expected"], "result": "pass" if f.passed else "fail",
                                                    "checks": f.checks, "requests": f.calls}, indent=1, default=str), encoding="utf-8")
        md += [f"| {f.id} | {esc(c['check'])} | {esc(c['expected'])} | {esc(c['actual'])} | {'pass' if c['pass'] else 'FAIL'} |" for c in f.checks]
    md += ["", "| Fact | Result |", "|---|---|"] + [f"| {f.id} {f.p['fact']} | {'pass' if f.passed else 'FAIL'} |" for f in facts]
    (d / "result.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for f in facts:
        print(f.id, "pass" if f.passed else "FAIL", f"({sum(c['pass'] for c in f.checks)}/{len(f.checks)})")
    return 0 if all(f.passed for f in facts) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit(run(a.base, a.creds, a.out))
