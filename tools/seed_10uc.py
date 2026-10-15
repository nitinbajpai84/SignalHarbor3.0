"""Seed the ten-use-case universe on Evergreen Office (card D): 13 months of coherent, synthetic history for the ten use cases.

Usage: python tools/seed_10uc.py [--data-root PATH] [--reset] [--hold-amended-a]
Order: tools/seed_evergreen.py (company, people, 30 Sep story) -> this file (history and the planted facts) -> tools/seed_v3_demo.py
(the four-centre project, gold tables and dashboard, built last so the gold tables see all of it). Idempotent: a second run changes
nothing. `--data-root` points at a temporary root for tests. `--hold-amended-a` leaves Fund A's 7 Oct amended statement out so a demo can
drop it in live. Synthetic only; every entity, fund, identifier and figure comes from docs/test/10uc_universe.json (no second set).

How the data gets in (the answer key, docs/test/10UC-ANSWER-KEY.md, lists every planted fact):
- History (Oct 2025 to 3 Oct 2026) is back-dated with explicit `recorded_at`, like tools/seed_evergreen.py, because e1_write stamps "now".
  Statements and notices are registered as documents (the fixture PDFs under tests/v1/fixtures/10uc/), each value linked to its document,
  page and line.
- What arrives after the 3 Oct report went out goes through the product's own writers, stamped now: Fund A's amended statement
  (e2_extract.confirm), Fund E's Q3 statement (read, not confirmed), the October capital call and distribution notices (e2_extract.confirm ->
  k6_liquidity.record_notice), commitments (k6_liquidity), trades (e1_write), the checks (e3_recon) and the benchmark question (k7_benchmark).
- The fixture PDFs put a label and its value on separate lines, which the rule-based reader in e2_extract cannot pair, so the reading step
  (extracted_fields) is written here from the universe and located in the PDF text; everything after it is the product's code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sh_platform.jsonfile import read_json_strict, write_json_atomic  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.profile.view import Viewer  # noqa: E402
from sh_platform.settings import load_settings  # noqa: E402
from sh_platform.v1 import e1_write, wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402
from tools import seed_v3_demo as V3  # noqa: E402

UNIVERSE = ROOT / "docs" / "test" / "10uc_universe.json"
FIX = ROOT / "tests" / "v1" / "fixtures" / "10uc"
U = json.loads(UNIVERSE.read_text(encoding="utf-8"))
MARKER = "Cedarpoint Ventures III"          # the first fund this seed adds: present = the extension is done
ROLE = {n: r for n, _, r in EG.PEOPLE}
ROLES = {n: frozenset({r, *EG.EXTRA_ROLES.get(n, [])}) for n, r in ROLE.items()}  # Anita Rao also holds head_of_data
ROLES["Mei Chen"] = frozenset({"analyst"})  # ROLE1: the history is written as the ops analyst she was in the story; her account is now the business owner
MGR_SLUG = {"MGR-NORTHGATE": "northgate", "MGR-BLUEWATER": "bluewater", "MGR-CEDARPOINT": "cedarpoint", "MGR-SALTMARSH": "saltmarsh",
            "MGR-KESTREL": "kestrel"}
IDX_EQ, IDX_BD = "IDX:GLEQ:SYN", "IDX:GLBD:SYN"
CASH_PF = {"EG-HOLD": "EG-GROWTH", "EG-TRUST": "EG-LIQUID", "EG-B": "EG-B-OPS"}


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def dd(s: str) -> date:
    return date.fromisoformat(s[:10])


def money(x) -> Decimal:
    return Decimal(str(x))


def at(d: date, h: int = 9, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)


def bd_after(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


def viewers(ids: dict[str, str]) -> dict[str, Viewer]:
    return {n: Viewer(n, ROLES[n], False, ids[n]) for n in ROLE}


# ---------- phase 1: entities, instruments, identifiers, rules, benchmark ----------

def _static(plane, ids: dict[str, str]) -> dict:
    with wh.connect(plane) as con:
        org = e1_write.org_id(plane)
        if con.execute("select 1 from instruments where canonical_name = ?", [MARKER]).fetchone():
            return {"static": "kept"}
        if con.execute("select 1 from source_batches where batch_reference = 'manager statements 2026-08-31'").fetchone():
            raise RuntimeError("This company already holds the one-month demo data of tools/seed_v3_demo.py (its made-up 31 Aug rows). "
                               "Run with --reset on it, or use a new data root, so the 31 Aug figures are not counted twice.")
        con.execute("begin")
        uid = {r[0]: r[1] for r in con.execute("select display_name, id from users").fetchall()}
        ent = {r[0]: r[1] for r in con.execute("select entity_code, id from legal_entities").fetchall()}
        pf = {r[0]: r[1] for r in con.execute("select portfolio_code, id from portfolios").fetchall()}
        for p in U["portfolios"]:
            if p["portfolio_code"] not in pf:
                pf[p["portfolio_code"]] = EG.put(con, "portfolios", dict(
                    organization_id=org, legal_entity_id=ent[p["legal_entity"]], portfolio_code=p["portfolio_code"],
                    portfolio_name=p["portfolio_name"], base_currency=p["base_currency"], active_from=dd(p["active_from"])))
        sysid = {r[0]: r[1] for r in con.execute("select source_code, id from source_systems").fetchall()}
        if "security_master" not in sysid:
            sysid["security_master"] = EG.put(con, "source_systems", dict(
                organization_id=org, source_code="security_master", source_name="Security master", source_type="reference",
                connection_method="file drop", owner_user_id=uid["Mei Chen"], permitted_use="may_index", expected_cadence="monthly", is_active=True))
        mgr = {m["id"]: m["name"] for m in U["managers"]}
        have = {r[0]: r[1] for r in con.execute("select canonical_name, id from instruments").fetchall()}
        ins: dict[str, str] = {}
        for f in U["funds"]:
            if f["canonical_name"] in have:
                ins[f["key"]] = have[f["canonical_name"]]
            else:
                ins[f["key"]] = EG.put(con, "instruments", dict(
                    organization_id=org, canonical_name=f["canonical_name"], instrument_type=f["instrument_type"], asset_class=f["asset_class"],
                    manager_name=mgr.get(f["manager"]), currency=f["currency"], created_at=EG.utc(2026, 1, 1)))
        for s in U["securities"]:
            ins[s["key"]] = EG.put(con, "instruments", dict(
                organization_id=org, canonical_name=s["canonical_name"], instrument_type=s["instrument_type"], asset_class=s["asset_class"],
                manager_name=None, currency=s["currency"], created_at=EG.utc(2026, 1, 1)))
        for fx in U["fx_forwards"]:
            ins[fx["id"]] = EG.put(con, "instruments", dict(
                organization_id=org, canonical_name=fx["id"], instrument_type="fx_forward", asset_class=fx["asset_class"], manager_name=None,
                currency="USD", created_at=EG.utc(2026, 1, 1)))
        # identifiers: the universe's names and codes, approved by Mei (those the base seed made are kept)
        mei = uid["Mei Chen"]
        known = {(str(r[0]), r[1], r[2]) for r in con.execute("select instrument_id, identifier_type, identifier_value from instrument_identifiers").fetchall()}

        def ident(key: str, system: str, typ: str, value: str):
            if (str(ins[key]), typ, value) not in known:
                EG.put(con, "instrument_identifiers", dict(
                    organization_id=org, instrument_id=ins[key], source_system_id=sysid[system], identifier_type=typ, identifier_value=value,
                    valid_from=date(2026, 1, 1), mapping_status="approved", approved_by=mei, approved_at=EG.utc(2026, 2, 1)))
        for f in U["funds"]:
            for system, kinds in f["identifiers"].items():
                for typ, vals in kinds.items():
                    for v in vals if isinstance(vals, list) else [vals]:
                        ident(f["key"], system, typ, v)
        for s in U["securities"]:
            for system, kinds in s["identifiers"].items():
                for typ, v in kinds.items():
                    ident(s["key"], {"internal": "security_master"}.get(system, system), typ, v)
        # the manager's contact person, one row on the manager's first fund (the follow-up draft names this person)
        if "manager_contacts" not in sysid:
            sysid["manager_contacts"] = EG.put(con, "source_systems", dict(
                organization_id=org, source_code="manager_contacts", source_name="Manager contacts", source_type="internal",
                connection_method="manual", owner_user_id=mei, permitted_use="may_index", expected_cadence="ad hoc", is_active=True))
        for m in U["managers"]:
            first = next((f for f in U["funds"] if f["manager"] == m["id"]), None)
            if first and m.get("contact_name"):
                ident(first["key"], "manager_contacts", "manager_contact", m["contact_name"])
        # signed rules not in the base seed: the alert window and the four limits (owner proposes, the CIO signs)
        done = {r[0] for r in con.execute("select rule_code from business_rules").fetchall()}
        for r in U["rules"]:
            if r["rule_code"] in done:
                continue
            rid = EG.put(con, "business_rules", dict(organization_id=org, rule_code=r["rule_code"], rule_type=r["rule_type"], owner_user_id=uid[r["owner"]]))
            EG.put(con, "rule_versions", dict(organization_id=org, business_rule_id=rid, version_number=1, definition_text=r["definition_text"],
                                              parameters=json.dumps(r["parameters"]), effective_from=dd(r["effective_from"]), approval_status="approved",
                                              approved_by=uid[r["approved_by"]], approved_at=EG.utc(2026, 1, 5)))
        # the benchmark: v1 approved, v2 still in progress (never certified)
        b = U["benchmark"]
        for v in b["versions"]:
            did = EG.put(con, "benchmark_definitions", dict(
                organization_id=org, benchmark_code=b["benchmark_code"], benchmark_name=b["benchmark_name"], version_number=v["version_number"],
                reporting_currency=b["reporting_currency"], effective_from=dd(v["effective_from"]), calculation_method=v["calculation_method"],
                approval_status=v["approval_status"], approved_by=uid[v["approved_by"]] if v["approved_by"] else None))
            for c in v["components"]:
                EG.put(con, "benchmark_components", dict(
                    organization_id=org, benchmark_definition_id=did, market_series_key=c["market_series_key"], component_weight=money(c["component_weight"]),
                    spread_bps=money(c["spread_bps"]) if c["spread_bps"] else None, weight_effective_from=dd(v["effective_from"]), treatment_note=c["treatment_note"]))
        con.execute("commit")
    return {"static": "made"}


def _maps(plane) -> dict:
    with wh.connect(plane, read_only=True) as con:
        pf = {r[0]: str(r[1]) for r in con.execute("select portfolio_code, id from portfolios").fetchall()}
        ent = {r[0]: str(r[1]) for r in con.execute("select entity_code, id from legal_entities").fetchall()}
        ins = {r[0]: str(r[1]) for r in con.execute("select canonical_name, id from instruments").fetchall()}
        sysid = {r[0]: str(r[1]) for r in con.execute("select source_code, id from source_systems").fetchall()}
        uid = {r[0]: str(r[1]) for r in con.execute("select display_name, id from users").fetchall()}
    key = {f["key"]: ins[f["canonical_name"]] for f in U["funds"]}
    key.update({s["key"]: ins[s["canonical_name"]] for s in U["securities"]})
    key.update({x["id"]: ins[x["id"]] for x in U["fx_forwards"]})
    key["CASH"] = ins["Cash"]
    return {"org": e1_write.org_id(plane), "pf": pf, "ent": ent, "ins": key, "sys": sysid, "uid": uid}


# ---------- documents ----------

def _find_line(pages, needle: str) -> tuple[int, int]:
    for page, lines in pages:
        for k, text in lines:
            if needle in text:
                return page, k
    return 1, 1


def _doc(plane, con, m: dict, path: Path, *, title: str, instrument: str | None, dtype: str, vdate: date | None, received: datetime, status: str,
         supersedes: str | None, source_record: str | None, name: str | None = None) -> tuple[str, str]:
    """The documents row `e2_intake.register` writes, with the fund and date given (the fixture PDFs cannot be matched by heading)."""
    from sh_platform.v1 import doc_index, e2_intake
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    name = name or path.name
    rel = e2_intake._stored(plane, name, data, sha)
    did = wh.new_id()
    con.execute("insert into documents (id, organization_id, source_system_id, source_record_id, access_group_id, instrument_id, external_document_id,"
                " document_type, title, original_filename, original_uri, content_hash, document_date, valuation_date, received_at, recorded_at,"
                " document_status, supersedes_document_id, processing_status, contains_personal_data) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [did, m["org"], e2_intake._source(con, m["org"], "manager_email"), source_record, e2_intake._group(con, m["org"]), instrument, None, dtype,
                 title[:300], name, rel, sha, None, vdate, received, received + timedelta(minutes=5), status, supersedes, "registered", False])
    doc_index.ensure(plane, rel)
    return did, rel


def _fields(plane, con, m: dict, did: str, rel: str, rows: list[tuple], reviewer: str | None, when: datetime, run_id: str | None = None) -> dict[str, str]:
    """extracted_fields as the reader writes them: (name, text, numeric, currency, locate-this-text, review_status)."""
    from sh_platform.v1 import e2_extract
    pages = e2_extract._segments(plane, rel)
    out = {}
    for name, text, num, ccy, needle, status in rows:
        page, line = _find_line(pages, needle) if needle else (1, 1)
        out[name] = EG.put(con, "extracted_fields", dict(
            organization_id=m["org"], document_id=did, field_name=name, value_text=text, value_numeric=num, currency=ccy, page_number=page, line_number=line,
            confidence="high", extracted_by_agent_run_id=run_id, review_status=status, reviewed_by=reviewer if status != "pending" else None,
            reviewed_at=when if status != "pending" else None))
    return out


def _statement_file(s: dict, tmp: Path) -> Path:
    f = next(x for x in U["funds"] if x["key"] == s["fund"])
    if f["manager"] in MGR_SLUG:
        return FIX / "manager_statements" / f"{MGR_SLUG[f['manager']]}_{s['fund']}_{s['period_end']}_{s['kind']}.pdf"
    # Meridian's index funds: no PDF in the fixtures, so a small one with the label and value on one line (the reader can read it)
    from tools.make_e2_statements import _write_plain
    p = tmp / f"meridian_{s['fund']}_{s['period_end']}_{s['kind']}.pdf"
    name = f["identifiers"]["manager_email"]["manager_fund_name"][0]
    d = dd(s["period_end"])
    _write_plain(p, name, [f"Statement date: {d.day} {d:%B %Y}", f"Administrator reference: {f['identifiers']['administrator']['administrator_code']}",
                           f"Net asset value: USD {money(s['value']):,.2f}", "Currency: USD", f"Units: {s.get('units', '')}", "Status: Final"])
    return p


def _title(f: dict, s: dict) -> str:
    """The canonical title, or the manager's own when it names the fund another way (P13: 'KR Macro Fund Ltd - Class B USD'), unless that
    other way is the name of another holding (Bluewater prints Fund B as 'Evergreen Liquid Book', the office's own liquid book)."""
    others = [x["canonical_name"] for x in U["funds"] if x is not f]
    if s.get("title") and f["canonical_name"] not in s["title"] and not any(o in s["title"] for o in others):
        return s["title"]
    d = dd(s["period_end"])
    return f"{f['canonical_name']} statement {d.day} {d:%b %Y} ({'amended' if s['kind'] == 'amended' else s['kind']})"


# ---------- phase 2: commitments (the product's writer) ----------

def _commitments(plane, m: dict) -> list[dict]:
    from sh_platform.v1 import k6_liquidity as K6
    if K6.commitments(plane):
        return K6.commitments(plane)
    with wh.connect(plane) as con:
        recs = EG._batch(con, m["org"], m["sys"]["manager_email"], "commitments register 2026-10-09", EG.utc(2026, 10, 9, 5), date(2026, 10, 9),
                         [{"type": "commitment", "fund": c["fund"], "amount": c["commitment_amount"]} for c in U["commitments"]], "total commitment")
    for c, rec in zip(U["commitments"], recs):
        K6.record_commitment(plane, {"legal_entity_id": m["ent"][c["legal_entity"]], "instrument_id": m["ins"][c["fund"]], "source_record_id": rec,
                                     "commitment_amount": money(c["commitment_amount"]), "currency": c["currency"], "committed_on": dd(c["committed_on"])})
    return K6.commitments(plane)


# ---------- phase 3: the history ----------

def _history(plane, m: dict, tmp: Path) -> dict:
    com = {c["instrument_id"]: c for c in _commitments(plane, m)}
    org, ins, pf, sysid, uid = m["org"], m["ins"], m["pf"], m["sys"], m["uid"]
    fund_pf = {f["key"]: pf[f["portfolio"]] for f in U["funds"]}
    funds = {f["key"]: f for f in U["funds"]}
    with wh.connect(plane) as con:
        if con.execute("select 1 from valuation_observations where valuation_date = ?", [date(2025, 10, 31)]).fetchone():
            return {"history": "kept"}
        con.execute("begin")
        mei = uid["Mei Chen"]
        # -- manager statements: document, reading, valuation (amended ones supersede the statement they replace)
        doc_of, val_of = {}, {}
        n_docs = n_vals = 0
        base_rows = {("A", "2026-09-30"): "estimate", ("B", "2026-09-30"): "final"}
        for s in sorted((x for x in U["statements"] if x["kind"] != "missing"), key=lambda x: (x["received_at"], x["fund"])):
            f = funds[s["fund"]]
            key = (s["fund"], s["period_end"])
            if (s["kind"], key) == ("amended", ("A", "2026-09-30")) or key == ("E", "2026-09-30"):
                continue                                    # arrive 7 and 8 Oct: the product's own path (phase 4)
            received = ts(s["received_at"])
            path = _statement_file(s, tmp)
            first = s["kind"] != "amended"
            prior = doc_of.get(key) if not first else None
            base = None
            if base_rows.get(key) == s["kind"]:             # the base seed wrote the 30 Sep A estimate and B final already: link them
                base = con.execute("select id, source_record_id from valuation_observations where instrument_id = ? and valuation_date = ?"
                                   " and evidence_document_id is null", [ins[s["fund"]], dd(s["period_end"])]).fetchone()
            if base:
                rec = str(base[1])
            else:
                rec, = EG._batch(con, org, sysid["manager_email"], s["statement_id"], received, dd(s["period_end"]),
                                 [{"type": "statement", "amount": s["value"], "label": s["kind"]}], "total value")
            did, rel = _doc(plane, con, m, path, title=_title(f, s), instrument=ins[s["fund"]], dtype="manager_statement", vdate=dd(s["period_end"]),
                            received=received, status="estimate" if s["kind"] == "estimate" else "final", supersedes=prior, source_record=rec)
            n_docs += 1
            doc_of[key] = did
            ff = _fields(plane, con, m, did, rel, [
                ("nav", f"{int(money(s['value'])):,}", money(s["value"]), "USD", f"{int(money(s['value'])):,}", "confirmed"),
                ("valuation_date", s["period_end"], None, None, None, "confirmed"),
                ("currency", "USD", None, "USD", None, "confirmed")], mei, received + timedelta(days=1))
            if base:
                con.execute("update valuation_observations set evidence_document_id = ?, extracted_field_id = ? where id = ?", [did, ff["nav"], str(base[0])])
                val_of[key] = str(base[0])
                continue
            val_of[key] = EG.put(con, "valuation_observations", dict(
                organization_id=org, instrument_id=ins[s["fund"]], portfolio_id=fund_pf[s["fund"]], source_record_id=rec, evidence_document_id=did,
                extracted_field_id=ff["nav"], valuation_date=dd(s["period_end"]), received_at=received, recorded_at=received + timedelta(minutes=10),
                value_amount=money(s["value"]), currency="USD", valuation_type="manager_estimate" if s["kind"] == "estimate" else "manager_final",
                approval_status="estimated" if s["kind"] == "estimate" else "approved",
                supersedes_valuation_id=val_of.get(key) if s["kind"] == "amended" else None))
            n_vals += 1
        # the base seed's two 30 Sep values were written as "official"; the product reads "approved" (anything else shows as unverified)
        con.execute("update valuation_observations set approval_status = 'approved' where approval_status = 'official' and valuation_type = 'manager_final'"
                    " and valuation_date = ?", [date(2026, 9, 30)])
        # -- the liquid book: 20 securities a month, quantity times price equals value; the roll-up instrument carries nothing of its own
        navs = {(n["portfolio"], n["nav_period_end"]): n for n in U["administrator_nav_monthly"]}
        for month, book in sorted(U["liquid_book_month_end"].items()):
            nav_at = ts(navs[("EG-LIQUID", month)]["received_at"])
            received = nav_at - timedelta(hours=1)
            payloads = [{"type": "position", "security": p["security"], "quantity": p["quantity"], "price": p["price"], "amount": p["value"]} for p in book["positions"]]
            roll = month == "2026-09-30"
            if roll:
                payloads.append({"type": "rollup", "security": "LIQ", "amount": "0.00", "note": "carried by the 20 security lines"})
            recs = EG._batch(con, org, sysid["administrator"], f"administrator positions {month}", received, dd(month), payloads, "total market value")
            for p, rec in zip(book["positions"], recs):
                assert money(p["quantity"]) * money(p["price"]) == money(p["value"]), (month, p)
                EG.put(con, "valuation_observations", dict(
                    organization_id=org, instrument_id=ins[p["security"]], portfolio_id=pf["EG-LIQUID"], source_record_id=rec, valuation_date=dd(month),
                    received_at=received, recorded_at=received + timedelta(minutes=5), value_amount=money(p["value"]), currency="USD",
                    valuation_type="administrator", approval_status="approved"))
            if roll:
                EG.put(con, "valuation_observations", dict(
                    organization_id=org, instrument_id=ins["LIQ"], portfolio_id=pf["EG-LIQUID"], source_record_id=recs[-1], valuation_date=dd(month),
                    received_at=received, recorded_at=received + timedelta(minutes=5), value_amount=Decimal(0), currency="USD",
                    valuation_type="internal", approval_status="approved"))
        # -- administrator NAV per portfolio per month (30 Sep EG-GROWTH came with the base seed)
        for month in sorted({n["nav_period_end"] for n in U["administrator_nav_monthly"]}):
            rows = [n for n in U["administrator_nav_monthly"] if n["nav_period_end"] == month and not (n["portfolio"] == "EG-GROWTH" and month == "2026-09-30")]
            received = ts(rows[0]["received_at"])
            recs = EG._batch(con, org, sysid["administrator"], f"nav {month} all portfolios", received, dd(month),
                             [{"type": "nav", "portfolio": n["portfolio"], "amount": n["nav_amount"]} for n in rows], "total nav")
            for n, rec in zip(rows, recs):
                EG.put(con, "nav_snapshots", dict(
                    organization_id=org, portfolio_id=pf[n["portfolio"]], source_record_id=rec, nav_period_end=dd(month), received_at=received,
                    recorded_at=received + timedelta(minutes=5), nav_amount=money(n["nav_amount"]), currency=n["currency"], nav_status=n["nav_status"],
                    approved_at=received + timedelta(hours=1)))
        # -- cash per entity per day, administrator (accounting) and trading export (operational); 8 Oct came with the base seed
        for day in sorted({c["date"] for c in U["cash_daily"]}):
            if day == "2026-10-08":
                continue
            rows = [c for c in U["cash_daily"] if c["date"] == day]
            for view, system, col, status in (("accounting", "administrator", "administrator", "official"), ("operational", "trading_export", "trading_export", "indicative")):
                if view == "operational" and day < "2026-10-01":
                    continue  # e3_calc.portfolio_value counts trading-export cash as a holding; before 1 Oct it would sit inside every NAV bridge
                received = at(dd(day), 22)
                recs = EG._batch(con, org, sysid[system], f"cash {day} {system}", received, dd(day),
                                 [{"type": "cash", "entity": c["entity"], "amount": c[col]} for c in rows], "total cash")
                for c, rec in zip(rows, recs):
                    EG.put(con, "position_snapshots", dict(
                        organization_id=org, source_record_id=rec, portfolio_id=pf[CASH_PF[c["entity"]]], instrument_id=ins["CASH"], position_date=dd(day),
                        as_of_at=at(dd(day), 16), received_at=received, recorded_at=received + timedelta(minutes=5), quantity=money(c[col]),
                        source_market_value=money(c[col]), currency="USD", view_type=view, data_status=status))
        # -- market data: month-end index levels and USD/SGD fixings, plus the daily fixings of Sep and Oct
        have_fx = {r[0].date() for r in con.execute("select observed_at from market_observations where series_key = ?", [EG.FX_SERIES]).fetchall()}
        idx = U["index_levels"]["month_end_anchors"]
        fxm = U["fx_fixings"]["month_end"]
        for day in sorted(fxm):
            received = at(dd(day) + timedelta(days=1), 1)
            rows = [(IDX_EQ, "index_level", idx[IDX_EQ][day], "USD", None), (IDX_BD, "index_level", idx[IDX_BD][day], "USD", None)]
            if dd(day) not in have_fx:
                rows.append((EG.FX_SERIES, "fx", fxm[day], "USD", "SGD"))
            recs = EG._batch(con, org, sysid["market_data"], f"market data {day}", received, dd(day),
                             [{"type": r[1], "series": r[0], "amount": r[2]} for r in rows])
            for (series, typ, val, base, quote), rec in zip(rows, recs):
                EG.put(con, "market_observations", dict(
                    organization_id=org, source_record_id=rec, series_key=series, observation_type=typ,
                    observed_at=at(dd(day), 8 if typ == "fx" else 16), received_at=received, recorded_at=received + timedelta(minutes=5),
                    value=money(val), base_currency=base, quote_currency=quote, quality_status="clean"))
        daily = {d: v for d, v in U["fx_fixings"]["daily_2026_09_01_to_10_09"].items() if d != "2026-10-09" and dd(d) not in have_fx}  # 9 Oct carries 8 Oct
        recs = EG._batch(con, org, sysid["market_data"], "usdsgd wmr4pm daily 2026-09-01_to_2026-10-08", at(date(2026, 10, 8), 22), date(2026, 10, 8),
                         [{"type": "fx", "date": d, "amount": v} for d, v in daily.items()])
        for (d, v), rec in zip(daily.items(), recs):
            EG.put(con, "market_observations", dict(
                organization_id=org, source_record_id=rec, series_key=EG.FX_SERIES, observation_type="fx", observed_at=at(dd(d), 8),
                received_at=at(dd(d) + timedelta(days=1), 1), recorded_at=at(dd(d) + timedelta(days=1), 1, 5), value=money(v), base_currency="USD",
                quote_currency="SGD", quality_status="clean"))
        # -- calls and distributions to 1 Oct (the opening balance and the notices already in the office); newer notices come in phase 4
        for c in U["commitments"]:
            cm = com[ins[c["fund"]]]
            rec, = EG._batch(con, org, sysid["manager_email"], f"opening calls {c['fund']}", at(date(2025, 7, 31)), date(2025, 7, 31),
                             [{"type": "opening_balance", "fund": c["fund"], "amount": c["called_before_2025_08"]}], "total called")
            EG.put(con, "cash_movements", dict(
                organization_id=org, source_record_id=rec, portfolio_id=pf[funds[c["fund"]]["portfolio"]], instrument_id=ins[c["fund"]], movement_type="call",
                effective_date=date(2025, 7, 31), received_at=at(date(2025, 7, 31)), recorded_at=at(date(2025, 7, 31)), amount=money(c["called_before_2025_08"]),
                currency="USD", confirmation_status="paid", due_date=date(2025, 7, 31), notice_kind="call", commitment_id=cm["id"]))
        old_notices = [x for x in U["cash_movements"] if x["notice_date"] < "2026-10-01"]
        for x in old_notices:
            f = funds[x["fund"]]
            path = _notice_file(x)
            received = at(dd(x["notice_date"]), 8)
            did, rel = _doc(plane, con, m, path, title=f"{f['canonical_name']} {'capital call' if x['notice_kind'] == 'call' else 'distribution'} notice {dd(x['notice_date']).day} {dd(x['notice_date']):%b %Y}",
                            instrument=ins[x["fund"]], dtype="capital_call_notice", vdate=None, received=received, status="final", supersedes=None, source_record=None)
            batch = EG.put(con, "source_batches", dict(organization_id=org, source_system_id=sysid["manager_email"], batch_reference=f"notice:{did}", received_at=received,
                                                       loaded_at=received, validation_status="loaded"))
            rec = EG.put(con, "source_records", dict(organization_id=org, source_batch_id=batch, external_record_id=did, record_type="manager_notice", received_at=received,
                                                     recorded_at=received, raw_payload_uri=rel, content_hash=hashlib.sha256(did.encode()).hexdigest(), quality_status="loaded"))
            con.execute("update documents set source_record_id = ? where id = ?", [rec, did])
            EG.put(con, "cash_movements", dict(
                organization_id=org, source_record_id=rec, portfolio_id=pf[f["portfolio"]], instrument_id=ins[x["fund"]],
                movement_type="call" if x["notice_kind"] == "call" else "distribution", effective_date=dd(x["due_date"]), received_at=received,
                recorded_at=received + timedelta(minutes=5), amount=money(x["amount"]), currency=x["currency"],
                confirmation_status="paid" if x["notice_kind"] == "call" else "confirmed",  # funded long before 1 Oct: never overdue
                due_date=dd(x["due_date"]), notice_kind=x["notice_kind"], commitment_id=com[ins[x["fund"]]]["id"]))
        con.execute("commit")
    return {"history": "made", "statements": n_docs, "valuations": n_vals, "notices": len(old_notices)}


def _cash_activity(plane, m: dict) -> int:
    """P08b: the daily cash items behind the cash balances, on each side with its own system of record (universe `cash_activity`), so Tally can
    rank the Entity B wire. Back-dated with explicit recorded_at like the cash positions above (e1_write stamps now); the bank reference goes in
    the source record's external_record_id. Its own guard, so a data root seeded before this card gets them on the next run."""
    from sh_platform.v1 import e2_intake
    org, pf, sysid = m["org"], m["pf"], m["sys"]
    # the trading desk's file (description and counterparty per movement) lands as it came; each record points at its row (a2.1: Tally can say what a wire was)
    csv_path = FIX / "trading_export" / "cash_movements_trading_export_2026-09-09_to_2026-10-08.csv"
    data = csv_path.read_bytes()
    landed = e2_intake._stored(plane, csv_path.name, data, hashlib.sha256(data).hexdigest())
    csv_row = {r.split(",", 2)[1]: k for k, r in enumerate(data.decode("utf-8").splitlines(), 1) if k > 1}
    with wh.connect(plane) as con:
        if con.execute("select 1 from source_records where record_type = 'cash_movement' limit 1").fetchone():
            return 0
        con.execute("begin")
        n = 0
        for side, system in (("administrator", "administrator"), ("trading_export", "trading_export")):
            for day in sorted({i[f"{side}_date"] for i in U["cash_activity"] if i[f"{side}_date"]}):
                rows = sorted((i for i in U["cash_activity"] if i[f"{side}_date"] == day), key=lambda i: (i["entity"], i["reference"]))
                received = at(dd(day), 6) if day > "2026-10-08" else at(dd(day), 22)   # 9 Oct: the administrator's morning file, before the 18:00 cutoff
                recs = EG._batch(con, org, sysid[system], f"cash movements {day} {system.replace('_', ' ')}", received, dd(day),
                                 [{"type": "cash_movement", "entity": i["entity"], "reference": i["reference"], "amount": i["amount"]} for i in rows], "total movement")
                for i, rec in zip(rows, recs):
                    con.execute("update source_records set external_record_id = ? where id = ?", [i["reference"], rec])
                    if side == "trading_export":
                        con.execute("update source_records set sheet_name = ?, row_number = ?, cell_range = ?, raw_payload_uri = ? where id = ?",
                                    [csv_path.name, csv_row[i["reference"]], f"A{csv_row[i['reference']]}:J{csv_row[i['reference']]}", landed, rec])
                        con.execute("update source_batches set storage_uri = ? where id = (select source_batch_id from source_records where id = ?)", [landed, rec])
                    EG.put(con, "cash_movements", dict(
                        organization_id=org, source_record_id=rec, portfolio_id=pf[CASH_PF[i["entity"]]], instrument_id=m["ins"]["CASH"], movement_type=i["movement_type"],
                        effective_date=dd(day), received_at=received, recorded_at=received + timedelta(minutes=5), amount=money(i["amount"]), currency=i["currency"],
                        confirmation_status="confirmed"))
                    n += 1
        con.execute("commit")
    return n


def _notice_file(x: dict) -> Path:
    f = next(f for f in U["funds"] if f["key"] == x["fund"])
    return FIX / "notices" / f"{x['notice_date']}_{MGR_SLUG[f['manager']]}_fund-{x['fund']}_{x['notice_kind']}.pdf"


# ---------- phase 4: what arrives after the 3 Oct report, through the product's own writers ----------

def _agent_run(plane, who):
    from sh_platform.v1 import e2_extract
    try:
        from sh_platform.v1.e6_trace import agent_run
        return agent_run(plane, who, "intake", "rules-only", e2_extract.PROMPT_VERSION, e2_extract.TOOL_POLICY)
    except ImportError:
        import contextlib
        return contextlib.nullcontext()


def _live_statement(plane, m: dict, who: Viewer, s: dict, confirm: bool) -> dict:
    """A statement read after the report went out: document, reading (the value waits for a person), pending valuation, revision check; then
    the person's confirmation through e2_extract.confirm when `confirm`."""
    from sh_platform.v1 import e2_extract, e3_impact
    f = next(x for x in U["funds"] if x["key"] == s["fund"])
    assert f["manager"] in MGR_SLUG, "live statements use fixture PDFs only"
    received = ts(s["received_at"])
    with wh.connect(plane) as con:
        if con.execute("select 1 from documents where original_filename = ?", [_statement_file(s, Path('.')).name]).fetchone():
            return {"kept": True}
        prior = con.execute("select id from documents d where instrument_id = ? and valuation_date = ? and not exists (select 1 from documents n where n.supersedes_document_id = d.id)"
                            " order by received_at desc limit 1", [m["ins"][s["fund"]], dd(s["period_end"])]).fetchone()
        con.execute("begin")
        did, rel = _doc(plane, con, m, _statement_file(s, Path('.')), title=_title(f, s), instrument=m["ins"][s["fund"]], dtype="manager_statement",
                        vdate=dd(s["period_end"]), received=received, status="final", supersedes=str(prior[0]) if prior else None, source_record=None)
        con.execute("commit")
    with _agent_run(plane, who) as run:
        run_id = run if isinstance(run, str) else getattr(run, "id", None)
        with wh.connect(plane) as con:
            con.execute("begin")
            ff = _fields(plane, con, m, did, rel, [
                ("nav", f"{int(money(s['value'])):,}", money(s["value"]), "USD", f"{int(money(s['value'])):,}", "pending"),
                ("valuation_date", s["period_end"], None, None, None, "confirmed"), ("currency", "USD", None, "USD", None, "confirmed"),
                ("status_label", "amended" if s["kind"] == "amended" else "final", None, None, None, "confirmed")], None, wh.now(), run_id)
            con.execute("update extracted_fields set reviewed_at = ? where document_id = ? and review_status = 'confirmed'", [wh.now(), did])
            con.execute("commit")
    with wh.connect(plane, read_only=True) as con:
        doc = e2_extract._doc(con, did)
    with wh.connect(plane, read_only=True) as con:
        prev = con.execute("select 1 from valuation_observations where instrument_id = ? and valuation_date = ?", [m["ins"][s["fund"]], dd(s["period_end"])]).fetchone()
    if prev:
        vid = e2_extract._record_valuation(plane, doc, {"id": ff["nav"], "document_id": did}, money(s["value"]), "USD", dd(s["period_end"]), "pending")
    else:  # a first value for the date: _record_valuation would leave the portfolio empty, so the row names it
        vid = e1_write.record(plane, "valuation_observations", {
            "instrument_id": doc["instrument_id"], "portfolio_id": next(pf for code, pf in m["pf"].items() if code == f["portfolio"]),
            "evidence_document_id": did, "extracted_field_id": ff["nav"], "valuation_date": dd(s["period_end"]), "received_at": doc["received_at"],
            "value_amount": money(s["value"]), "currency": "USD", "approval_status": "pending", "valuation_type": "manager_final"})
    case = e3_impact.on_new_valuation(plane, vid)
    out = {"document_id": did, "pending_valuation_id": vid, "case_id": case}
    if confirm:
        out.update(e2_extract.confirm(plane, ff["nav"], who))
    return out


def _live_notice(plane, m: dict, who: Viewer, x: dict, confirm: bool) -> dict:
    """A notice: document, reading, a `noticed` cash movement per commitment (k6_liquidity.record_notice); confirmed ones go through e2_extract.confirm."""
    from sh_platform.v1 import e2_extract, k6_liquidity
    f = next(f for f in U["funds"] if f["key"] == x["fund"])
    path = _notice_file(x)
    received = at(dd(x["notice_date"]), 8)
    with wh.connect(plane) as con:
        if con.execute("select 1 from documents where original_filename = ?", [path.name]).fetchone():
            return {"kept": True}
        con.execute("begin")
        did, rel = _doc(plane, con, m, path, title=f"{f['canonical_name']} {'capital call' if x['notice_kind'] == 'call' else 'distribution'} notice {dd(x['notice_date']).day} {dd(x['notice_date']):%b %Y}",
                        instrument=m["ins"][x["fund"]], dtype="capital_call_notice", vdate=None, received=received, status="final", supersedes=None, source_record=None)
        amount_name = "call_amount" if x["notice_kind"] == "call" else "distribution_amount"
        n = f"{int(money(x['amount'])):,}"
        with _agent_run(plane, who) as run:
            run_id = run if isinstance(run, str) else getattr(run, "id", None)
            ff = _fields(plane, con, m, did, rel, [
                (amount_name, n, money(x["amount"]), x["currency"], n, "pending"), ("notice_kind", x["notice_kind"], None, None, None, "confirmed"),
                ("due_date", x["due_date"], None, None, "Payment due date" if x["notice_kind"] == "call" else None, "confirmed"),
                ("fund", f["canonical_name"], None, None, f["canonical_name"], "confirmed"), ("currency", x["currency"], None, x["currency"], None, "confirmed")],
                None, wh.now(), run_id)
        con.execute("commit")
    with wh.connect(plane) as con:
        _read_on_arrival(con, did, received)
    k6_liquidity.record_notice(plane, did, m["ins"][x["fund"]], x["notice_kind"], money(x["amount"]), x["currency"], x["due_date"], "noticed")
    out = {"document_id": did}
    if confirm:
        out.update(e2_extract.confirm(plane, ff[amount_name], who))
    return out


def _recorded_on_arrival(plane, did: str, received: datetime) -> None:
    """The product's writers stamp now; a statement read on its day of arrival is recorded that day (pending 30 minutes after it arrived,
    Mei's confirmation an hour later), so an as-known-on view between arrival and the seed run sees it."""
    with wh.connect(plane) as con:
        con.execute("begin")
        con.execute("update valuation_observations set recorded_at = ? where evidence_document_id = ? and approval_status = 'pending'",
                    [received + timedelta(minutes=30), did])
        con.execute("update valuation_observations set recorded_at = ? where evidence_document_id = ? and approval_status <> 'pending'",
                    [received + timedelta(minutes=90), did])
        con.execute("update extracted_fields set reviewed_at = ? where document_id = ? and reviewed_at is not null", [received + timedelta(minutes=90), did])
        _read_on_arrival(con, did, received)
        con.execute("commit")


def _read_on_arrival(con, did: str, received: datetime) -> None:
    """The intake agent's run that read a document is dated ten minutes after it arrived, not when the seed ran."""
    con.execute("update agent_runs set started_at = ?, finished_at = ? where id in (select extracted_by_agent_run_id from extracted_fields where document_id = ?)",
                [received + timedelta(minutes=10), received + timedelta(minutes=11), did])


def _live(plane, m: dict, V: dict[str, Viewer], hold_a: bool) -> dict:
    out = {}
    mei = V["Mei Chen"]
    for s in sorted((x for x in U["statements"] if (x["fund"], x["period_end"], x["kind"]) in (("A", "2026-09-30", "amended"), ("E", "2026-09-30", "final"))),
                    key=lambda x: x["received_at"]):
        if s["fund"] == "A" and hold_a:
            continue
        out[f"statement_{s['fund']}"] = got = _live_statement(plane, m, mei, s, confirm=s["fund"] == "A")
        if "document_id" in got:
            _recorded_on_arrival(plane, got["document_id"], ts(s["received_at"]))
    for x in sorted((x for x in U["cash_movements"] if x["notice_date"] >= "2026-10-01"), key=lambda x: x["notice_date"]):
        out[x["id"]] = _live_notice(plane, m, mei, x, confirm=x["confirmation_status"] == "confirmed")
    return out


# ---------- phase 5: trades, the checks, the benchmark question ----------

def _trades(plane, m: dict) -> int:
    with wh.connect(plane) as con:
        if con.execute("select 1 from transactions limit 1").fetchone():
            return 0
        org, ins, pf, sysid = m["org"], m["ins"], m["pf"], m["sys"]
        by_day: dict[tuple, list] = {}
        rows = []
        # (trade id, date, settle, instrument key, side, quantity, price, cash, currency, administrator quantity or None, administrator cash)
        for t in U["trades_oct"]:
            fx = t["security"].startswith("FXF")
            qty, price, cash = money(t["quantity"]), money(t["price"]), money(t["amount"])
            if t["administrator"] == "present":
                aq = money(t["administrator_quantity"])
                acash = cash if aq == qty and not fx else (aq * price if not fx else money(U["fx_forwards"][1]["confirmation_buy_amount"]))
            else:
                aq = acash = None
            rows.append((t["id"], t["trade_date"], t["settlement_date"], t["security"], "fx_forward" if fx else t["side"], qty, price, cash, t["currency"], aq, acash))
        f1 = U["fx_forwards"][0]
        rows.append(("FXF-2026-001", f1["trade_date"], f1["value_date"], f1["id"], "fx_forward", money(f1["sell_amount"]), money(f1["contract_rate"]),
                     money(f1["buy_amount"]), "SGD", money(f1["sell_amount"]), money(f1["buy_amount"])))
        for r in rows:
            by_day.setdefault((r[1], "trading_export"), []).append(r)
            if r[9] is not None:
                by_day.setdefault((r[1], "administrator"), []).append(r)
        con.execute("begin")
        recs: dict[tuple, str] = {}
        for (day, system), rs in sorted(by_day.items()):
            ref = f"trading_export_{day.replace('-', '')}.csv" if system == "trading_export" else f"administrator_trades_{day.replace('-', '')}.xlsx"
            got = EG._batch(con, org, sysid[system], ref, at(dd(day), 22), dd(day), [{"type": "trade", "id": r[0], "amount": str(r[7])} for r in rs], "total trade amount")
            for r, rec in zip(rs, got):
                recs[(r[0], system)] = rec
        con.execute("commit")
    for system in ("trading_export", "administrator"):
        batch = []
        for r in rows:
            tid, day, settle, key, side, qty, price, cash, ccy, aq, acash = r
            if system == "administrator" and aq is None:
                continue
            q, c = (qty, cash) if system == "trading_export" else (aq, acash)
            sign = 1 if side == "buy" else -1
            batch.append(dict(source_record_id=recs[(tid, system)], portfolio_id=pf["EG-LIQUID"], instrument_id=ins[key], external_trade_id=tid,
                              transaction_type=side, trade_date=dd(day), effective_date=dd(day), settlement_date=dd(settle),
                              quantity_delta=sign * q if side in ("buy", "sell") else -q,
                              cash_amount=-sign * c if side in ("buy", "sell") else c, currency=ccy, status="booked"))
        e1_write.record_many(plane, "transactions", batch)
    return len(rows)


def _checks(plane) -> dict:
    """Run the product's own checks once, so the cases the answer key names exist: cash on 8 Oct, trades and limits on 9 Oct, and the benchmark
    question (a certified return asked of version 2, still in progress, is refused and raises one policy question)."""
    from sh_platform.v1 import e3_recon, k7_benchmark
    from sh_platform.v1.i2_north import Refused
    out = {}
    for code, day in (("cash_by_entity", "2026-10-08"), ("trade_vs_admin", "2026-10-09"), ("limits", "2026-10-09")):
        r = e3_recon.run_detail(plane, code, dd(day))
        out[code] = {"checked": r["checked"], "breaks": r["breaks"], "opened": len(r["opened"])}
    try:
        k7_benchmark.certified_return(plane, U["benchmark"]["benchmark_code"], date(2026, 10, 1), date(2026, 10, 8))
    except Refused as e:
        out["benchmark"] = {"refused": e.message}
    return out


# ---------- phase 6: library, manager notes, the month-end process ----------

DOC_FILES = {  # universe document id -> fixture file
    "doc-note-01": "notes/01_northgate_annual_meeting_2026-02-11.md", "doc-note-02": "notes/02_bluewater_quarterly_call_2026-04-22.md",
    "doc-note-03": "notes/03_cedarpoint_update_call_2026-05-19.md", "doc-note-04": "notes/04_kestrel_ridge_onsite_2026-06-12.md",
    "doc-note-05": "notes/05_saltmarsh_q2_call_2026-07-30.md", "doc-note-06": "notes/06_meridian_service_review_2026-08-26.md",
    "doc-ddq-01": "research_docs/kestrel_ridge_ddq_2026.pdf", "doc-ddq-02": "research_docs/cedarpoint_ventures_ddq_2026.pdf",
    "doc-news-01": "research_docs/kestrel_ridge_q3_2026_newsletter.pdf", "doc-news-02": "research_docs/northgate_mid_year_letter_2026.pdf",
    "doc-ic-01": "notes/07_investment_committee_note_2026-09-17.md"}
EXTRA_DOCS = [("Investment committee note, October 2026", "notes/08_investment_committee_note_2026-10-08.md", "2026-10-08")]


def _library(plane, V: dict[str, Viewer]) -> dict:
    from sh_platform.v1 import c4_library
    mei = V["Mei Chen"]
    have = {i["name"] for i in c4_library._index(plane)}
    items = [(d["title"], DOC_FILES[d["id"]], d["document_date"]) for d in U["documents"]] + EXTRA_DOCS
    made, stamped = 0, {}
    for title, rel, day in items:
        path = FIX / rel
        name = f"{title}{path.suffix}"
        if name in have:
            continue
        # manager documents are open to the office; the investment committee notes are Internal (a person who is not Mei asks for access)
        r = c4_library.upload(plane, mei, name, path.read_bytes(), kind="document", note=f"{title}, dated {day}", share=True,
                              sensitivity="internal" if "committee" in title.lower() else "open", reviewed=True)
        if "item" in r:
            made += 1
            stamped[r["item"]["id"]] = day
    if stamped:  # the library stamps an upload with today; these documents carry their own date, which "what changed" compares with
        idx = c4_library._index_path(plane)
        rows = c4_library._index(plane)
        for i in rows:
            if i["id"] in stamped:
                i["at"] = f"{stamped[i['id']]}T09:00:00+00:00"
        write_json_atomic(idx, rows)
    return {"library": made}


def _manager_notes(plane, V: dict[str, Viewer]) -> int:
    from sh_platform.v1 import k5_managers as K5
    mei, n = V["Mei Chen"], 0  # the notes say "Prepared by Mei Chen"
    mgr = {m["id"]: m for m in U["managers"]}
    for d in U["documents"]:
        if d["document_type"] != "meeting_note":
            continue
        mid = K5.slug(mgr[d["manager"]]["name"])
        if any(x["on"] == d["document_date"] and x["kind"] == "meeting" for x in K5.notes(plane, mid)):
            continue
        K5.add_note(plane, mei, mid, f"{d['title']}: " + " ".join(d["key_facts"]), "meeting", d["document_date"])
        n += 1
    cp = K5.slug("Cedarpoint Ventures")
    q = "Cedarpoint Opportunities II's 30 June 2026 statement was due on 14 July 2026 and has not arrived. Ask Cedarpoint when to expect it."
    if not any(x["text"] == q for x in K5.notes(plane, cp)):
        K5.add_note(plane, mei, cp, q, "question", "2026-10-09")
        n += 1
    return n


def _process(plane) -> dict:
    """Give the signed month-end intent the controls and exception paths the universe states, so the SOP has them (and flag the manual steps)."""
    p = next((p for p in V3.p1_project.all_projects(plane) if p.get("title") == V3.TITLE), None)
    if not p:
        return {"process": "no project"}
    path = plane.path("intents", p["intent_id"], "sow.json")
    sow = read_json_strict(path)
    if not sow:
        return {"process": "no intent"}
    if all(s.get("control") for s in sow["process"]["steps"]):
        return {"process": "kept"}
    by_n = {s["n"]: s for s in U["process"]["steps"]}
    for s in sow["process"]["steps"]:
        u = by_n[s["n"]]
        s["control"], s["exception"], s["manual"] = u["control"], u["exception"], u["manual"]
        if u["manual"] and not any(w in s["does"].lower() for w in ("by hand", "manual")):
            s["does"] = s["does"].rstrip(".") + ", by hand."
    write_json_atomic(path, sow)
    return {"process": "made"}



# ---------- the owner seat ----------

# The family principal: the sixth platform role, so A1 (every role talks to every agent) can be tested. Not in the universe's people list
# because she does no step of the month-end process; tests/evals/scorers.py EXTRA_NAMES keeps her name out of the egress log too.
OWNER = ("Helen Foo", "Family principal", "owner")


def _owner(data_root: Path, plane) -> dict:
    """The owner account (password only in seed_credentials.txt, never printed) and her row in the company's people table. Idempotent."""
    from sh_platform.auth.accounts import AccountStore
    from sh_platform.jsonfile import lock_for
    from tools.seed import _new_password
    name, business, role = OWNER
    store, email = AccountStore(data_root), EG.email_of(name)
    made = store.get_by_email(email) is None
    if made:
        pw = _new_password()
        store.create(email, pw, name, EG.COMPANY, [role])
        creds = data_root / "_control" / "seed_credentials.txt"
        with lock_for(creds):
            old = creds.read_text(encoding="utf-8") if creds.is_file() else ""
            creds.write_text(old.rstrip("\n") + f"\n{email}  {pw}  {role}  {EG.COMPANY}\n", encoding="utf-8")
    with wh.connect(plane) as con:
        org = e1_write.org_id(plane)
        if not con.execute("select 1 from users where email = ?", [email]).fetchone():
            EG.put(con, "users", dict(organization_id=org, external_identity_id=store.get_by_email(email)["account_id"],
                                      display_name=name, email=email, business_role=business, is_active=True, created_at=EG.utc(2026, 1, 1)))
        _principal_reads_all(con, org, con.execute("select id from users where email = ?", [email]).fetchone()[0])
    return {"owner": "made" if made else "kept"}


PRINCIPAL_GROUP = "Family principal"


def _principal_reads_all(con, org, uid) -> None:
    """EVT-T10 (product decision, AGENT-TRIAGE): the family principal reads every entity. Her own access group with read on every legal entity
    (and the manager statements), so e1_access.level is read and she may open every case, ask Tally and read every figure; never full,
    she acts on nothing. Idempotent: an entity added later gets its scope on the next seed run."""
    row = con.execute("select id from access_groups where group_name = ?", [PRINCIPAL_GROUP]).fetchone()
    gid = row[0] if row else EG.put(con, "access_groups", dict(organization_id=org, group_name=PRINCIPAL_GROUP,
                                                               description="The family principal reads every entity"))
    have = {(r[0], str(r[1])) for r in con.execute("select scope_type, scope_value from access_group_scopes where access_group_id = ?", [gid]).fetchall()}
    want = [("legal_entity", str(e[0])) for e in con.execute("select id from legal_entities").fetchall()] + [("document_type", "manager_statement")]
    for typ, val in want:
        if (typ, val) not in have:
            EG.put(con, "access_group_scopes", dict(organization_id=org, access_group_id=gid, scope_type=typ, scope_value=val, access_level="read"))
    if not con.execute("select 1 from access_group_memberships where access_group_id = ? and user_id = ?", [gid, uid]).fetchone():
        EG.put(con, "access_group_memberships", dict(organization_id=org, access_group_id=gid, user_id=uid, granted_at=EG.utc(2026, 1, 1),
                                                     granted_by=con.execute("select id from users where display_name = 'Grace Ong'").fetchone()[0]))


# ---------- main ----------

def seed(data_root: Path, reset: bool = False, hold_amended_a: bool = False) -> dict:
    data_root = Path(data_root)
    base = EG.seed(data_root, reset)
    plane = PlaneStore(data_root).plane_for(EG.COMPANY).ensure()
    wh.set_demo_today(plane, V3.DEMO_TODAY)  # the story is set on 9 Oct 2026 whatever day the demo is shown
    if reset:  # the rebuilt warehouse has no gold tables: let the demo project run its plan again
        for p in V3.p1_project.all_projects(plane):
            if p.get("title") == V3.TITLE:
                plane.path("build", p["id"], "runs.jsonl").unlink(missing_ok=True)
    ids, _ = EG.accounts(data_root)
    V = viewers(ids)
    out = {**base}
    out.update(_static(plane, ids))
    m = _maps(plane)
    with tempfile.TemporaryDirectory(prefix="sh10uc_") as t:
        out.update(_history(plane, m, Path(t)))
    out["cash_activity"] = _cash_activity(plane, m)
    fresh = out["history"] == "made"
    if fresh:
        out["live"] = _live(plane, m, V, hold_amended_a)
        out["trades"] = _trades(plane, m)
        out["checks"] = _checks(plane)
    out.update(_library(plane, V))
    out["manager_notes"] = _manager_notes(plane, V)
    v3 = V3.seed(data_root)
    out["project_id"], out["dashboard"] = v3["project_id"], v3["dashboard"]
    out.update(_process(plane))
    out.update(_owner(data_root, plane))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", help="default: SH_DATA_ROOT from settings")
    ap.add_argument("--reset", action="store_true", help="clear and rebuild the evergreen warehouse (use a root with no earlier demo project)")
    ap.add_argument("--hold-amended-a", action="store_true", help="leave Fund A's amended statement of 7 Oct out, to drop it in live")
    a = ap.parse_args(argv)
    raw = a.data_root or load_settings(env_file=ROOT / ".env").data_root
    root = Path(raw) if Path(raw).is_absolute() else ROOT / raw
    r = seed(root, a.reset, a.hold_amended_a)
    print(f"{EG.NAME}: base {r['warehouse']}, ten-use-case history {r['history']}, project {r['project_id']}, dashboard {r['dashboard']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
