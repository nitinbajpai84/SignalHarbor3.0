"""E6b: evaluation harness for the v2.0 agents and calculations (working deck slide 23).
Usage: python tools/eval_v2.py <company> [--suite NAME ...] [--data-root data] [--allow-live]
The suites register documents and open cases, so by default the company is COPIED to a temp folder and the copy is evaluated;
only --allow-live runs on the company itself.
Seven suites: extraction, identity, calculation, asof, retrieval, safety, action.
Each suite imports the card it tests lazily; a missing card is reported "not built" (not a failure).
Prints pass/fail per case and a release-gate summary; exit 1 if any built suite has a failing case."""
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "v1" / "fixtures" / "e6"
E2 = ROOT / "tests" / "v1" / "fixtures" / "e2"


class NotBuilt(Exception):
    """A card this suite needs is not on disk (or the fixtures it reads are missing)."""


def mod(name: str):
    try:
        return importlib.import_module(f"sh_platform.v1.{name}")
    except ImportError as e:
        if e.name and e.name.endswith(name):
            raise NotBuilt(name) from e
        raise


def fixture(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def viewer():
    from sh_platform.profile.view import Viewer
    return Viewer("Eval Admin", frozenset({"company_admin"}), False, "acc-eval")


def _dec(x) -> Decimal:
    return Decimal(str(x))


# Each suite returns [(case, ok, detail)].
def suite_extraction(plane):
    ex, intake = mod("e2_extract"), mod("e2_intake")
    expected = sorted((E2 / "expected").glob("*.json")) if (E2 / "expected").is_dir() else []
    if not expected:
        raise NotBuilt("E2e fixtures")
    out = []
    for p in expected:
        want = json.loads(p.read_text(encoding="utf-8"))
        pdf = E2 / (want.get("filename") or p.stem + ".pdf")
        if not pdf.is_file() or not want.get("expected_fields"):
            continue
        doc = intake.register(plane, str(pdf), viewer())
        got = {}
        for fid in ex.extract(plane, doc, viewer()):
            f = _field(plane, fid)
            got[f["field_name"]] = f
        for w in want["expected_fields"]:
            f = got.get(w["field_name"]) or {}
            ok = bool(f) and _same(f.get("value_numeric") if w.get("value_numeric") is not None else f.get("value_text"),
                                   w["value_numeric"] if w.get("value_numeric") is not None else w["value_text"])
            ok = ok and (w.get("page_number") is None or f.get("page_number") == w["page_number"])
            out.append((f"{p.stem}: {w['field_name']}", ok, "" if ok else f"expected {w['value_text']!r} on page {w.get('page_number')}, got "
                        f"{f.get('value_text')!r} on page {f.get('page_number')}" if f else f"field {w['field_name']} was not read"))
    return out


def _field(plane, fid):
    wh = mod("wh")
    with wh.connect(plane) as con:
        cur = con.execute("select * from extracted_fields where id = ?", [fid])
        return dict(zip([c[0] for c in cur.description], cur.fetchone()))


def _same(a, b) -> bool:
    try:
        return abs(_dec(str(a).replace(",", "")) - _dec(str(b).replace(",", ""))) < Decimal("0.01")
    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


def _instrument_name(plane, instrument_id):
    if not instrument_id:
        return None
    wh = mod("wh")
    with wh.connect(plane) as con:
        r = con.execute("select canonical_name from instruments where id = ?", [instrument_id]).fetchone()
    return r[0] if r else None


def _source_id(plane, code="manager_email"):
    wh = mod("wh")
    with wh.connect(plane) as con:
        r = con.execute("select id from source_systems where source_code = ?", [code]).fetchone()
    if not r:
        raise NotBuilt(f"source system {code}")
    return str(r[0])


def suite_identity(plane):
    match = mod("e2_match")
    src = _source_id(plane)
    out = []
    for c in fixture("identity.json"):
        r = match.resolve(plane, c["name"], src)
        got = _instrument_name(plane, r.get("instrument_id")) or next(
            (_instrument_name(plane, x.get("instrument_id") if isinstance(x, dict) else x) for x in r.get("candidates") or []), None)
        errs = []
        if "expect_status" in c and r.get("status") != c["expect_status"]:
            errs.append(f"status {r.get('status')}")
        if "expect_status_in" in c and r.get("status") not in c["expect_status_in"]:
            errs.append(f"status {r.get('status')}")
        if "expect_instrument" in c and got != c["expect_instrument"]:
            errs.append(f"instrument {got}")
        if "expect_not_instrument" in c and r.get("instrument_id") and got == c["expect_not_instrument"] and r.get("status") == "approved":
            errs.append("auto-approved the wrong fund")
        out.append((c["case"], not errs, "; ".join(errs)))
    return out


def _portfolio_ids(plane):
    wh = mod("wh")
    with wh.connect(plane) as con:
        return [r[0] for r in con.execute("select id from portfolios").fetchall()]


def _total(plane, calc, cutoff, ccy="USD", on=None):
    on = on or date(2026, 9, 30)
    return sum(_dec(calc.portfolio_value(plane, p, on, cutoff, ccy)["total"]) for p in _portfolio_ids(plane))


CUT_3OCT = datetime(2026, 10, 3, 23, 59, tzinfo=timezone.utc)


def suite_calculation(plane):
    calc = mod("e3_calc")
    out = [("calc version is set", bool(calc.CALC_VERSION), "")]
    for label, cutoff, want in (("total as at 3 Oct is 57.60m", CUT_3OCT, "57600000"), ("total now is 57.78m", datetime.now(timezone.utc), "57780000")):
        got = _total(plane, calc, cutoff)
        out.append((label, got == _dec(want), f"got {got}"))
    return out


def suite_asof(plane):
    asof = mod("e1_asof")
    wh = mod("wh")
    with wh.connect(plane) as con:
        r = con.execute("select id from instruments where canonical_name = 'Evergreen Growth I'").fetchone()
    if not r:
        raise NotBuilt("Evergreen demo company")
    where = {"instrument_id": r[0]}
    out = []
    for label, cutoff, want in (("Fund A as at 3 Oct is 10.00m", CUT_3OCT, "10000000"), ("Fund A now is 10.18m", datetime.now(timezone.utc), "10180000")):
        row = asof.latest(plane, "valuation_observations", where, cutoff)
        got = row and next((row[k] for k in ("value_amount",) if k in row), None)
        out.append((label, got is not None and _dec(got) == _dec(want), f"got {got}"))
    return out


def suite_retrieval(plane):
    brief = mod("e5_brief")
    wh = mod("wh")
    with wh.connect(plane) as con:
        r = con.execute("select id from report_versions where issued_at is not null order by issued_at desc limit 1").fetchone() if _has(con, "report_versions") else None
    if not r:
        raise NotBuilt("an issued report")
    keys = {ln["label"]: ln["line_key"] for ln in brief.brief(plane, viewer(), r[0])["lines"]}  # the fixture names a holding; E5b keys are E1c keys
    out = []
    for c in fixture("retrieval.json"):
        try:
            text = json.dumps(brief.explain(plane, viewer(), r[0], keys.get(c["line_key"], c["line_key"]))).lower()
        except LookupError as e:  # a line that is not in the report: the answer must say so
            text = str(e).lower()
        miss = [s for s in c["expect_contains"] if s.lower() not in text]
        out.append((c["case"], not miss, f"missing {miss}" if miss else ""))
    return out


def _has(con, table):
    return bool(con.execute("select 1 from information_schema.tables where table_name = ?", [table]).fetchone())


def suite_safety(plane):
    guard = mod("e4_guard")
    cases = fixture("safety_requests.json")
    out = [(f"refuse: {t}", bool((guard.check_request(t) or {}).get("refused")), "") for t in cases["refused"]]
    out += [(f"allow: {t}", guard.check_request(t) is None, "wrongly refused") for t in cases["allowed"]]
    out.append(("agent cannot write nav_snapshots", bool(guard.check_action("update", "nav_snapshots")), ""))
    inj = E2 / "injection_attack_test.pdf"
    if inj.is_file():
        ex, intake = mod("e2_extract"), mod("e2_intake")
        before = _count(plane, "exceptions")
        ex.extract(plane, intake.register(plane, str(inj), viewer()), viewer())
        out.append(("injection document gives no action", _count(plane, "exceptions") == before, "document text changed state"))
    return out


def _count(plane, table):
    wh = mod("wh")
    with wh.connect(plane) as con:
        return con.execute(f"select count(*) from {table}").fetchone()[0]


def suite_action(plane):
    recon, cases = mod("e3_recon"), mod("e4_cases")
    day = date(2026, 10, 8)
    recon.run(plane, "cash_by_entity", day)
    first = _count(plane, "exceptions")
    recon.run(plane, "cash_by_entity", day)
    out = [("a rerun does not duplicate the break", _count(plane, "exceptions") == first, f"{first} then {_count(plane, 'exceptions')}")]
    wh = mod("wh")
    with wh.connect(plane) as con:
        r = con.execute("select id from exceptions limit 1").fetchone()
    if r:
        try:
            cases.assign(plane, r[0], viewer(), "nobody-with-no-seat")
            out.append(("assign to a user with no seat is refused", False, "accepted"))
        except Exception:
            out.append(("assign to a user with no seat is refused", True, ""))
    return out


SUITES = {"extraction": suite_extraction, "identity": suite_identity, "calculation": suite_calculation,
          "asof": suite_asof, "retrieval": suite_retrieval, "safety": suite_safety, "action": suite_action}


def run(plane, names=None, out=print) -> dict:
    """{suite: {"status": "pass"|"fail"|"not built", "cases": [...]}}"""
    res = {}
    for name in names or SUITES:
        try:
            cases = SUITES[name](plane)
            ok = all(c[1] for c in cases)
            res[name] = {"status": "pass" if ok else "fail", "cases": cases}
        except NotBuilt as e:
            res[name] = {"status": "not built", "cases": [], "needs": str(e)}
        except Exception as e:  # a crash inside a built suite is a failure, never a silent pass
            res[name] = {"status": "fail", "cases": [("suite crashed", False, f"{type(e).__name__}: {e}")]}
        out(f"\n== {name}: {res[name]['status']}" + (f" (needs {res[name]['needs']})" if res[name]["status"] == "not built" else ""))
        for case, ok, detail in res[name]["cases"]:
            out(f"  {'PASS' if ok else 'FAIL'}  {case}" + (f"  [{detail}]" if detail and not ok else ""))
    return res


def gate(res: dict, out=print) -> int:
    out("\nRelease gate")
    for n, r in res.items():
        cs = r["cases"]
        out(f"  {n:<12} {r['status']:<10} {sum(c[1] for c in cs)}/{len(cs)}")
    bad = [n for n, r in res.items() if r["status"] == "fail"]
    skipped = [n for n, r in res.items() if r["status"] == "not built"]
    out("  " + ("BLOCKED: " + ", ".join(bad) if bad else "PASS for every built suite") + (f"; not built: {', '.join(skipped)}" if skipped else ""))
    return 1 if bad else 0


def working_copy(data_root, company: str, allow_live: bool = False):
    """(plane, cleanup). The company is copied to a temp root unless allow_live; an unknown company starts empty in the temp root."""
    from sh_platform.plane import PlaneStore
    live = PlaneStore(data_root)
    if allow_live:
        return live.plane_for(company), lambda: None
    tmp = tempfile.mkdtemp(prefix="sh_eval_")
    if live.exists(company):
        src = live.plane_for(company).root
        shutil.copytree(src, Path(tmp) / company)
    else:
        PlaneStore(tmp).create(company)
    return PlaneStore(tmp).plane_for(company), lambda: shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("company")
    ap.add_argument("--suite", action="append", choices=list(SUITES))
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--allow-live", action="store_true", help="run on the company itself (it registers documents and opens cases there)")
    a = ap.parse_args(argv)
    plane, cleanup = working_copy(a.data_root, a.company, a.allow_live)
    try:
        return gate(run(plane, a.suite))
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
