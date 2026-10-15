"""E1c: reports and issued versions.

An issued report version never changes. `as_issued` returns it as it went out; `as_known_now` re-reads every source row
through E1a with cutoff = now and marks each line official / estimated / revised / unverified. A re-issue is a new version
that supersedes the old one. Each line's source rows are recorded in `metric_evidence`: `note` = "<table>:<row id>" is the one
observation pointer; the real pointer columns carry at most one of extracted_field_id / source_record_id (never two).

Vocabulary: a valuation's approval_status is proposed, confirmed (or approved) or rejected. A superseding row that is confirmed/approved
shows its line as revised; any other shows it as unverified. A line's status word (official, estimated, revised) is stored in
metric_values.value_status. `issue` refuses lines that are unverified/draft and sources recorded after the cutoff.

A line is a dict: {metric_code (holding_value | portfolio_total), portfolio_id?, instrument_id?, value, currency, status,
sources?: [{table, row_id}]}. A portfolio_total line with no sources is recomputed as the sum of the holding lines in scope.
"""
from __future__ import annotations

import logging
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
FALLBACK_CALC_VERSION = "e1c-1"
SYSTEM_USER = "00000000-0000-5000-8000-000000000e1c"  # owner of the built-in metric definitions (no person owns them)
METRICS = {
    "holding_value": ("Holding value", "The value of one holding in the report currency, from the latest known valuation."),
    "portfolio_total": ("Portfolio total", "The sum of the holding values in the report or portfolio."),
}
# subject columns, value column and currency column per observation table (same subjects as E1a/E1b)
SUBJECT = {
    "valuation_observations": (("instrument_id", "portfolio_id", "valuation_date"), "value_amount", "currency"),
    "position_snapshots": (("portfolio_id", "instrument_id", "position_date", "view_type"), "source_market_value", "currency"),
    "nav_snapshots": (("portfolio_id", "nav_period_end"), "nav_amount", "currency"),
}


def _calc_version() -> str:
    try:
        from sh_platform.v1 import e3_calc
        return str(e3_calc.CALC_VERSION)
    except (ImportError, AttributeError):
        log.warning("E3d calc version not available; recording %s", FALLBACK_CALC_VERSION)
        return FALLBACK_CALC_VERSION


def _latest(plane, table: str, where: dict, cutoff) -> dict | None:
    try:
        from sh_platform.v1 import e1_asof
    except ImportError:
        log.warning("E1a (e1_asof) is not available; cannot read evidence as known now")
        raise
    return e1_asof.latest(plane, table, where, cutoff)


def _org(plane) -> str:
    """organization_id as E1b writes it (one warehouse file per company, so reads need no organization filter)."""
    from sh_platform.v1 import e1_write
    return e1_write.org_id(plane)


def _s(v):
    return None if v is None else str(v)  # UUID columns come back as UUID objects


def _key(metric_code, portfolio_id, instrument_id) -> str:
    return f"{metric_code}|{portfolio_id or ''}|{instrument_id or ''}"


def _ensure_metric(plane, con, metric_code: str) -> str:
    row = con.execute("select id from metric_definitions where metric_code=? order by version_number desc limit 1",
                      [metric_code]).fetchone()
    if row:
        return row[0]
    name, text = METRICS[metric_code]
    mid = wh.new_id()
    con.execute("insert into metric_definitions (id, organization_id, decision_intent_id, metric_code, metric_name, version_number,"
                " definition_text, implementation_ref, owner_user_id, approval_status) values (?,?,?,?,?,?,?,?,?,?)",
                [mid, _org(plane), None, metric_code, name, 1, text, "sh_platform.v1.e1_reports", SYSTEM_USER, "approved"])
    return mid


def ensure_report(plane, report_code: str, name: str, audience: str, currencies) -> str:
    ccy = currencies if isinstance(currencies, str) else ",".join(currencies)
    with wh.connect(plane) as con:
        row = con.execute("select id from reports where report_code=?", [report_code]).fetchone()
        if row:
            return row[0]
        rid = wh.new_id()
        con.execute("insert into reports (id, organization_id, decision_intent_id, report_code, report_name, audience, reporting_currencies)"
                    " values (?,?,?,?,?,?,?)", [rid, _org(plane), None, report_code, name, audience, ccy])
        return rid


def _pointer(con, table: str, row_id: str) -> tuple[str | None, str | None, object]:
    """(source_record_id, extracted_field_id, recorded_at) of the evidence row; exactly one pointer: the extracted field if the
    row has one, else the source record, else neither (the note still names the row)."""
    if table not in SUBJECT:
        raise ValueError(f"{table} is not an evidence table")
    cols = {r[0] for r in con.execute("select column_name from information_schema.columns where table_name=?", [table]).fetchall()}
    sel = ", ".join(c if c in cols else "null" for c in ("source_record_id", "extracted_field_id", "recorded_at"))
    r = con.execute(f"select {sel} from {table} where id=?", [row_id]).fetchone()  # table is whitelisted
    if r is None:
        raise ValueError(f"{table} row {row_id} does not exist")
    return (None, r[1], r[2]) if r[1] else (r[0], None, r[2])


def _end(cutoff) -> datetime:
    if isinstance(cutoff, datetime):
        return cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
    if isinstance(cutoff, date):
        return datetime.combine(cutoff, time.max, tzinfo=timezone.utc)
    return _end(date.fromisoformat(str(cutoff)[:10]))


def issue(plane, report_code: str, period_end, cutoff, approved_by: str, lines: list[dict], rule_versions: list[str] | None = None, issued_at: datetime | None = None) -> str:
    """Create the run, the metric values with their evidence and the issued report version; the previous issue for the
    same period becomes superseded. Returns the report_version id. Refuses unverified/draft lines and sources recorded
    after the cutoff. `rule_versions`: the signed rule version ids the figures used (kept on the run).
    `issued_at`: when it was issued (also the run's start and finish); default now, a seed may back-date it."""
    if not lines:
        raise ValueError("A report needs at least one line.")
    for ln in lines:
        if ln.get("status", "unverified") in ("unverified", "draft"):
            raise ValueError("An issued report cannot contain an unverified or draft line.")
    now, cut = issued_at or wh.now(), _end(cutoff)
    with wh.connect(plane) as con:
        rep = con.execute("select id from reports where report_code=?", [report_code]).fetchone()
        if not rep:
            raise ValueError(f"Unknown report {report_code}; call ensure_report first.")
        con.begin()
        try:
            run = wh.new_id()
            con.execute("insert into calculation_runs (id, organization_id, decision_intent_id, started_at, finished_at, knowledge_cutoff_at,"
                        " reporting_date, code_version, rule_versions_used, input_manifest_uri, run_status, validation_status)"
                        " values (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [run, _org(plane), None, now, now, cutoff, period_end, _calc_version(), json.dumps(list(rule_versions or [])),
                         f"warehouse://{wh.path(plane).name}", "finished", "passed"])
            for ln in lines:
                mv = wh.new_id()
                con.execute("insert into metric_values (id, organization_id, calculation_run_id, metric_definition_id, portfolio_id, instrument_id,"
                            " reporting_date, numeric_value, currency, value_status, published_at) values (?,?,?,?,?,?,?,?,?,?,?)",
                            [mv, _org(plane), run, _ensure_metric(plane, con, ln.get("metric_code", "holding_value")), ln.get("portfolio_id"),
                             ln.get("instrument_id"), period_end, Decimal(str(ln["value"])), ln.get("currency"), ln["status"], now])
                for s in ln.get("sources", []):
                    src, field, rec = _pointer(con, s["table"], s["row_id"])
                    if rec > cut:
                        raise ValueError(f"A source of this report was recorded after the cutoff ({s['table']} {s['row_id']}).")
                    con.execute("insert into metric_evidence (id, organization_id, metric_value_id, source_record_id, document_passage_id,"
                                " extracted_field_id, evidence_role, note) values (?,?,?,?,?,?,?,?)",
                                [wh.new_id(), _org(plane), mv, src, None, field, "input", f"{s['table']}:{s['row_id']}"])
            prev = con.execute("select id from report_versions where report_id=? and period_end=? and status='issued' order by issued_at desc limit 1",
                               [rep[0], period_end]).fetchone()
            vid = wh.new_id()
            con.execute("insert into report_versions (id, organization_id, report_id, calculation_run_id, period_end, cutoff_at, status,"
                        " approved_by, issued_at, supersedes_report_version_id) values (?,?,?,?,?,?,?,?,?,?)",
                        [vid, _org(plane), rep[0], run, period_end, cutoff, "issued", approved_by, now, prev[0] if prev else None])
            con.execute("insert into approvals (id, organization_id, report_version_id, approval_type, requested_from_user_id,"
                        " decision_by_user_id, status, requested_at, decided_at) values (?,?,?,?,?,?,?,?,?)",
                        [wh.new_id(), _org(plane), vid, "report_issue", approved_by, approved_by, "approved", now, now])
            if prev:  # workflow state only; the new row's supersedes link is the record of why
                con.execute("update report_versions set status='superseded' where id=?", [prev[0]])
            con.commit()
        except Exception:
            con.rollback()
            raise
    return vid


def as_issued(plane, report_version_id: str) -> list[dict]:
    """The lines exactly as issued, with their sources."""
    with wh.connect(plane, read_only=True) as con:
        run = con.execute("select calculation_run_id from report_versions where id=?",
                          [report_version_id]).fetchone()
        if not run:
            raise LookupError("We could not find that report version.")
        rows = con.execute(
            "select v.id, d.metric_code, v.portfolio_id, v.instrument_id, v.numeric_value, v.currency, v.value_status, i.canonical_name "
            "from metric_values v join metric_definitions d on d.id=v.metric_definition_id "
            "left join instruments i on i.id=v.instrument_id where v.calculation_run_id=? order by d.metric_code desc, i.canonical_name",
            [run[0]]).fetchall()
        out = []
        for mv, code, pf, ins, val, ccy, st, name in rows:
            src = [dict(zip(("table", "row_id"), r[0].split(":", 1))) for r in
                   con.execute("select note from metric_evidence where metric_value_id=? order by id", [mv]).fetchall()]
            pf, ins = _s(pf), _s(ins)
            out.append({"key": _key(code, pf, ins), "metric_code": code, "portfolio_id": pf, "instrument_id": ins, "label": name or "Total", "is_total": code == "portfolio_total" and pf is None,
                        "value": val, "currency": ccy, "status": st, "sources": src})
        return out


def _row(plane, table: str, row_id: str) -> dict | None:
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute(f"select * from {table} where id=?", [row_id])  # table comes from the SUBJECT whitelist
        r = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], r)) if r else None


@memo
def as_known_now(plane, report_version_id: str) -> list[dict]:
    """Every line recomputed from what the company knows now. A line whose source row has been superseded shows the new
    value with status revised; a line with nothing to check against is unverified; totals are re-added from the holdings."""
    now = wh.now()
    lines = as_issued(plane, report_version_id)
    for ln in lines:
        ln["issued_value"] = ln["value"]
        if ln["metric_code"] == "portfolio_total" and not ln["sources"]:
            continue  # re-added below
        if not ln["sources"]:
            ln["status"] = "unverified"
        for s in ln["sources"]:
            spec = SUBJECT.get(s["table"])
            used = _row(plane, s["table"], s["row_id"]) if spec else None
            cur = _latest(plane, s["table"], {k: used[k] for k in spec[0]}, now) if used else None
            if cur is None or cur[spec[2]] != ln["currency"]:  # ponytail: no FX here; E3d converts once wired
                ln["status"] = "unverified"
            elif str(cur["id"]) != s["row_id"]:
                ok = cur.get("approval_status", "confirmed") in ("confirmed", "approved", "approved_official")
                ln["value"], ln["status"], ln["source_now"] = cur[spec[1]], "revised" if ok else "unverified", {"table": s["table"], "row_id": str(cur["id"])}
    holdings = [x for x in lines if x["metric_code"] == "holding_value"]
    for t in (x for x in lines if x["metric_code"] == "portfolio_total" and not x["sources"]):
        scope = [h for h in holdings if not t["portfolio_id"] or h["portfolio_id"] == t["portfolio_id"]]
        t["value"] = sum((Decimal(str(h["value"])) for h in scope), Decimal(0))
        if any(h["status"] == "unverified" for h in scope):
            t["status"] = "unverified"
        elif any(h["status"] == "revised" for h in scope):
            t["status"] = "revised"
    return lines


def versions_using(plane, table: str, row_id: str) -> list[str]:
    """Issued report versions whose figures used that row."""
    with wh.connect(plane, read_only=True) as con:
        return [str(r[0]) for r in con.execute(
            "select distinct rv.id from metric_evidence e join metric_values v on v.id=e.metric_value_id "
            "join report_versions rv on rv.calculation_run_id=v.calculation_run_id "
            "where e.note=? and rv.status='issued'", [f"{table}:{row_id}"]).fetchall()]


@memo
def listing(plane) -> list[dict]:
    with wh.connect(plane, read_only=True) as con:
        reps = con.execute("select id, report_code, report_name, audience, reporting_currencies from reports order by report_name",
                           []).fetchall()
        return [{"id": str(r[0]), "report_code": r[1], "name": r[2], "audience": r[3], "currencies": r[4], "versions": [
            dict(zip(("id", "period_end", "cutoff_at", "status", "issued_at", "approved_by", "supersedes"), (_s(v[0]), *v[1:5], _s(v[5]), _s(v[6])))) for v in con.execute(
                "select id, period_end, cutoff_at, status, issued_at, approved_by, supersedes_report_version_id from report_versions "
                "where report_id=? order by issued_at desc", [r[0]]).fetchall()]} for r in reps]
