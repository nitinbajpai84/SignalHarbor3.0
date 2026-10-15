"""E5b: the CIO Brief. A report as issued beside the same report as known now, and "why did this move?".

- `brief(plane, viewer, report_version_id, currency=None)`: figures in another reporting currency only through a signed fx rate (E3d); lines {line_key, label, issued, known_now, difference, currency, status, case_id}, a banner when
  any line is draft, revised, stale or unverified (naming the open case), and the open cases. Lines the viewer may not see are left out.
- `explain(plane, viewer, report_version_id, line_key, question=None, model=None)`: the fixed format (answer, evidence, sources, caveats,
  next action, approver). Figures are copied by the program from the lines and E1a chains; the model only words the sentence with tokens
  (it sees no name and writes no digit). With the model off, a fixed sentence is used and the result says so.
Sibling cards are imported lazily: e1_reports, e1_access, e1_asof, e4_guard (these raise when missing); e4_cases, e6_trace (optional).
Line shape read from e1_reports (tolerant): key|line_key|metric_value_id|instrument_id, label|name, value|numeric_value, currency, status,
instrument_id, portfolio_id, metric_value_id, source_row_id, is_total.
"""
from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

from sh_platform.v1.scope_memo import memo
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
WORDS = {"certified": "official", "official": "official", "approved": "official", "indicative": "estimated", "estimated": "estimated",
         "manager_estimate": "estimated", "revised": "revised", "stale": "stale", "draft": "draft", "unverified": "unverified"}
NEEDS_CARE = {"draft", "revised", "stale", "unverified"}
TOKENS = {"holding", "issued", "known", "difference", "issued_date", "received_date"}
OPEN_CASE = "('resolved', 'rejected')"
NO_MODEL = "Worded by fixed rules; the model is off."


def _need(module: str):
    try:
        return __import__(f"sh_platform.v1.{module}", fromlist=["x"])
    except ImportError:
        log.warning("e5_brief needs %s, which is not installed", module)
        raise


def _s(v) -> str | None:
    return None if v is None else str(v)


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _get(d: dict, *keys):
    return next((d[k] for k in keys if d.get(k) is not None), None)


def _money(v: Decimal | None, ccy: str | None) -> str:
    return "not available" if v is None else f"{v:,.2f} {ccy or ''}".strip()


def _day(v) -> str:
    return v.strftime("%d %b %Y").lstrip("0") if isinstance(v, (date, datetime)) else str(v or "")


def _word(status) -> str:
    return WORDS.get(str(status or "").lower(), "unverified")


def _row(con, sql: str, params: list) -> dict | None:
    cur = con.execute(sql, params)
    r = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], r)) if r else None


def _rows(con, sql: str, params: list) -> list[dict]:
    cur = con.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _visible(plane, viewer, lines: list[dict]) -> tuple[list[dict], bool]:
    """Lines the viewer may see; (lines, something_hidden). A total is dropped when anything else was hidden. Fails closed."""
    allowed = _need("e1_access").visible_portfolios(plane, viewer)
    allowed = {str(a) for a in allowed}
    keep = [ln for ln in lines if (str(ln["portfolio_id"]) in allowed if ln.get("portfolio_id") else bool(allowed))]
    hidden = len(keep) < len(lines)
    return ([ln for ln in keep if not ln.get("is_total")] if hidden else keep), hidden


def _lines(plane, viewer, rvid: str) -> tuple[list[dict], bool]:
    R = _need("e1_reports")
    issued = {_key(ln): ln for ln in R.as_issued(plane, rvid)}
    known = {_key(ln): ln for ln in R.as_known_now(plane, rvid)}
    out = []
    for k in list(issued) + [k for k in known if k not in issued]:
        i, n = issued.get(k), known.get(k)
        base = dict(n or i)
        iv, nv = _dec(_get(i or {}, "value", "numeric_value")), _dec(_get(n or {}, "value", "numeric_value"))
        status = _word(base.get("status"))
        if iv is not None and nv is not None and iv != nv and status in ("official", "estimated"):
            status = "revised"
        out.append({**base, "line_key": k, "label": _get(base, "label", "name") or k, "issued": iv, "known_now": nv,
                    "difference": None if iv is None or nv is None else nv - iv, "status": status,
                    "currency": base.get("currency")})
    return _visible(plane, viewer, out)


def _key(ln: dict) -> str:
    return str(_get(ln, "key", "line_key", "metric_value_id", "instrument_id", "label", "name"))


def _open_cases(plane, rvid: str) -> list[dict]:
    with wh.connect(plane, read_only=True) as con:
        rows = _rows(con, "select e.*, i.metric_value_id as impact_metric_value_id from exception_impacts i join exceptions e on e.id = i.exception_id"
                          f" where i.report_version_id = ? and e.status not in {OPEN_CASE} order by e.detected_at", [rvid])
        notes = {_s(i): n for i, n in con.execute("select exception_id, event_note from exception_events where event_type = 'opened'").fetchall()}
    return [{"id": _s(r["id"]), "number": r.get("case_number") or _number(notes.get(_s(r["id"]))), "title": r["title"], "instrument_id": _s(r.get("instrument_id")),
             "metric_value_id": _s(r["impact_metric_value_id"]), "status": r["status"]} for r in rows]


def _number(note) -> str | None:
    """E4a keeps the CASE-0001 number as the note of the case's `opened` event."""
    return note if note and re.fullmatch(r"CASE-\d+", str(note)) else None


def _case_name(c: dict) -> str:
    return f"{c['number']} ({c['title']})" if c.get("number") else f"the open case \"{c['title']}\""


def _case_for(line: dict, cases: list[dict]) -> dict | None:
    for c in cases:
        if (c["metric_value_id"] and c["metric_value_id"] == _s(line.get("metric_value_id"))) or (
                c["instrument_id"] and c["instrument_id"] == _s(line.get("instrument_id"))):
            return c
    return None


def _clean(ln: dict, case: dict | None, rate: Decimal | None = None, ccy: str | None = None) -> dict:
    def conv(v):
        return v if v is None or rate is None else (v * rate).quantize(Decimal("0.01"))
    return {"line_key": ln["line_key"], "label": ln["label"], "issued": conv(ln["issued"]), "known_now": conv(ln["known_now"]),
            "difference": conv(ln["difference"]), "currency": ccy or ln["currency"], "status": ln["status"],
            "instrument_id": _s(ln.get("instrument_id")), "case_id": case["id"] if case else None}


def _currencies(plane, rv: dict, base: str | None, wanted: str | None) -> tuple[list[str], Decimal | None, str | None, str | None]:
    """(currencies the screen may switch between, rate to apply, currency shown, plain message). Another currency is offered only
    when the signed fx rule and a rate for the report date exist; otherwise the figures stay in the report currency and say why."""
    if not base:
        return [], None, None, None
    with wh.connect(plane, read_only=True) as con:
        r = con.execute("select reporting_currencies from reports where id = ?", [rv["report_id"]]).fetchone()
    others = [c.strip().upper() for c in str(r[0] if r and r[0] else "").split(",") if c.strip() and c.strip().upper() != base]
    rates, why = {}, None
    for c in others:
        try:
            got = _need("e3_calc").fx(plane, base, c, rv["period_end"], rv["cutoff_at"])
        except ImportError:
            got = None
        if got is None:
            why = f"No signed exchange rate for {base} to {c} is available yet, so figures are shown in {base} only."
        else:
            rates[c] = got
    wanted = (wanted or "").upper()
    if wanted and wanted != base and wanted not in rates:
        return [base, *rates], None, base, why or f"{wanted} is not a reporting currency of this report, so figures are shown in {base}."
    return [base, *rates], rates.get(wanted), wanted if wanted in rates else base, why


@memo
def brief(plane, viewer, report_version_id: str, currency: str | None = None) -> dict:
    lines, hidden = _lines(plane, viewer, report_version_id)
    with wh.connect(plane, read_only=True) as con:
        rv = _row(con, "select v.*, r.report_name from report_versions v join reports r on r.id = v.report_id where v.id = ?", [report_version_id])
    if rv is None:
        raise LookupError("This report version does not exist.")
    cases = _open_cases(plane, report_version_id)
    base = next((ln["currency"] for ln in lines if ln.get("currency")), None)
    offered, rate, shown, message = _currencies(plane, rv, base, currency)
    out = [_clean(ln, _case_for(ln, cases), rate, shown) for ln in lines]
    care = [x for x in out if x["status"] in NEEDS_CARE]
    banner = None
    if care:
        named = [c for c in cases if any(x["case_id"] == c["id"] for x in care)] or cases
        banner = (f"{len(care)} line{'s' if len(care) != 1 else ''} below {'show' if len(care) != 1 else 'shows'} a manager-reported valuation that is "
                  "revised, stale or not yet confirmed, so the figures known now differ from the report as issued."
                  + (" Open case: " + "; ".join(_case_name(c) for c in named) + "." if named else ""))
    return {"report_version_id": report_version_id, "report_name": rv["report_name"], "period_end": rv["period_end"],
            "issued_at": rv.get("issued_at"), "cutoff_at": rv["cutoff_at"], "version_status": rv["status"], "lines": out,
            "currency": shown, "currencies": offered, "currency_message": message,
            "banner": banner, "open_cases": [c for c in cases if not hidden or any(x["case_id"] == c["id"] for x in out)], "partial": hidden}


# ---- explain -----------------------------------------------------------------------------------------------------------

def _evidence(plane, viewer, line: dict) -> tuple[list[dict], list[dict]]:
    """(evidence rows oldest first, sources) from the E1a chain of the line's valuation; only rows of portfolios the viewer sees."""
    A, acc = _need("e1_asof"), _need("e1_access")
    allowed = {str(a) for a in acc.visible_portfolios(plane, viewer)}
    row_id = line.get("source_row_id")
    chain = A.chain(plane, "valuation_observations", row_id) if row_id else []
    if not chain and line.get("instrument_id"):
        cur = A.latest(plane, "valuation_observations", {"instrument_id": line["instrument_id"]}, wh.now())
        chain = A.chain(plane, "valuation_observations", cur["id"]) if cur else []
    chain = [r for r in chain if (str(r["portfolio_id"]) in allowed if r.get("portfolio_id") else bool(allowed))]
    ev, src = [], []
    with wh.connect(plane, read_only=True) as con:
        for r in chain:
            doc = _row(con, "select * from documents where id = ?", [r["evidence_document_id"]]) if r.get("evidence_document_id") else None
            fld = _row(con, "select * from extracted_fields where id = ?", [r["extracted_field_id"]]) if r.get("extracted_field_id") else None
            where = None
            if doc:
                where = doc["title"] + (f", page {fld['page_number']}, line {fld['line_number']}" if fld and fld.get("page_number") else "")
                src.append({"document_id": _s(doc["id"]), "title": doc["title"], "document_status": doc["document_status"],
                            "received_at": doc["received_at"], "page": fld and fld.get("page_number"), "line": fld and fld.get("line_number"),
                            "extracted_field_id": fld and _s(fld["id"])})
            ev.append({"row_id": _s(r["id"]), "label": str(r.get("valuation_type") or "").replace("_", " "),
                       "value": _dec(r["value_amount"]), "currency": r["currency"], "as_of": r["valuation_date"], "received_at": r["received_at"],
                       "recorded_at": r["recorded_at"], "source": where, "state": "current", "approval": r.get("approval_status")})
    # the confirm step re-records the same value from the same page with its new approval: one piece of evidence, not two
    same = lambda a, b: (a["value"], a["as_of"], a["source"]) == (b["value"], b["as_of"], b["source"])  # noqa: E731
    ev = [e for e, nxt in zip(ev, ev[1:] + [None]) if nxt is None or not same(e, nxt)]
    for e, nxt in zip(ev, ev[1:]):
        e["state"] = "superseded"
    src = list({(s["document_id"], s["page"], s["line"]): s for s in src}.values())
    return ev, src


CONFIRMED = ("confirmed", "approved", "approved_official")


def _status_caveats(status: str, ev: list[dict]) -> list[str]:
    cur = ev[-1] if ev else {}
    if status == "revised" and cur.get("approval") in CONFIRMED:
        return [f"The figure is revised: the manager's amended statement replaced the value the report used, and it was confirmed on {_day(cur.get('recorded_at'))}."]
    if status in ("estimated", "revised"):
        return [f"The figure is {status}, not official, until the manager's final statement is confirmed."]
    if status in ("stale", "unverified", "draft"):
        return [f"The figure is {status}."]
    return []


def _wording(plane, model, words: dict, direction: str) -> str | None:
    """The model's sentence with tokens, or None (off, failed, a digit, or an unknown token)."""
    try:
        from sh_platform.agents.loop import run_agent
        from sh_platform.agents.registry import ToolRegistry
        from sh_platform.agents.runs import RunRegistry
        from sh_platform.build.agents.runtime import OpenGate
        from sh_platform.egress.providers import build_model_client
        from sh_platform.v1.router import route
        from sh_platform.v1.skill_loader import load_skill
        base = model if model is not None else build_model_client(plane)
        routed = route(base, "north", "summary", "", plane, want_json=True)
        if routed is None:
            return None
        system = load_skill("briefing", plane) + '\nReply with ONLY one JSON object: {"answer": "<one or two sentences using the tokens>"}.'
        res = run_agent(routed, ToolRegistry(OpenGate()), plane.company_id, "m1_intent", "Briefing", system,
                        {"facts": [f"The holding moved {direction} since the report was issued.", words["why"]]},
                        "Word the answer to the CIO's question about this move.", recorder=RunRegistry(plane))
    except Exception:  # noqa: BLE001 - any failure leaves the wording to rules
        log.warning("the briefing model call failed; fixed wording is used")
        return None
    if res.status != "done":
        return None
    a, b = res.text.find("{"), res.text.rfind("}")
    try:
        text = str(json.loads(res.text[a:b + 1])["answer"]).strip()
    except (ValueError, KeyError, TypeError):
        return None
    bad = re.search(r"\d", text) or set(re.findall(r"\{(\w+)\}", text)) - TOKENS or not text
    return None if bad else text


def _trace(plane, viewer, rvid: str):
    try:
        return _need("e6_trace").agent_run(plane, viewer, "briefing", "router", "briefing-v1", "v1")
    except ImportError:
        return contextlib.nullcontext()


def explain(plane, viewer, report_version_id: str, line_key: str, question: str | None = None, model=None) -> dict:
    if question:
        refusal = _need("e4_guard").check_request(question)
        if refusal:
            return {"refused": True, "reason": refusal.get("reason"), "review_path": refusal.get("review_path")}
    lines, _ = _lines(plane, viewer, report_version_id)
    line = next((ln for ln in lines if ln["line_key"] == line_key), None)
    if line is None:
        raise LookupError("This line is not in the report, or you may not see it.")
    cases = _open_cases(plane, report_version_id)
    if line.get("is_total"):
        return _explain_total(plane, viewer, report_version_id, line, lines, cases)
    case = _case_for(line, cases)
    ev, sources = _evidence(plane, viewer, line)
    iv, nv, ccy, diff = line["issued"], line["known_now"], line["currency"], line["difference"]
    moved = bool(diff)
    when = next((e["received_at"] for e in reversed(ev) if e["state"] == "current"), None)
    with wh.connect(plane, read_only=True) as con:
        rv = _row(con, "select * from report_versions where id = ?", [report_version_id])
    fill = {"holding": line["label"], "issued": _money(iv, ccy), "known": _money(nv, ccy), "difference": _money(diff, ccy),
            "issued_date": _day(rv.get("issued_at") or rv["cutoff_at"]), "received_date": _day(when)}
    pending = next((e for e in reversed(ev) if e.get("approval") in ("pending", "proposed")), None)
    if moved:
        fixed = ("The manager-reported valuation of {holding} changed by {difference} since the report was issued on {issued_date}: "
                 "{issued} then, {known} now. The latest statement was received on {received_date}.")
        why = "A later statement replaced the value the report used." if len(ev) > 1 else "The value known now differs from the issued one."
        with _trace(plane, viewer, report_version_id):
            text = _wording(plane, model, {"why": why}, "up" if diff > 0 else "down")
        wording = "model" if text else "rules"
        answer = (text or fixed).format(**fill)
    elif pending and pending["value"] != iv:
        wording = "rules"
        answer = ("An amended statement reports a manager-reported valuation of {holding} of {pending}, but it is not verified yet, so it is not in "
                  "the figures known now. As issued on {issued_date}: {issued}.").format(**fill, pending=_money(pending["value"], ccy))
    elif line["status"] == "unverified":
        wording = "rules"
        answer = "No verified newer manager-reported valuation of {holding} is known. As issued on {issued_date}: {issued}.".format(**fill)
    else:
        wording, answer = "rules", "The manager-reported valuation of {holding} has not changed since the report was issued on {issued_date}: {issued}.".format(**fill)
    caveats = _status_caveats(line["status"], ev)
    if not sources and moved:
        caveats.append("No source document is linked to this change yet.")
    if wording == "rules":
        caveats.append(NO_MODEL)
    action, approver = _next(plane, viewer, moved, case)
    return {"refused": False, "line_key": line_key, "answer": answer, "wording": wording,
            "evidence": [{k: v for k, v in e.items() if k != "row_id"} for e in ev] or [
                {"label": "issued", "value": iv, "currency": ccy, "state": "current"}],
            "figures": {"issued": iv, "known_now": nv, "difference": diff, "currency": ccy}, "status": line["status"],
            "sources": sources, "caveats": caveats, "next_action": action, "approver": approver,
            "case": {"id": case["id"], "number": case["number"], "title": case["title"]} if case else None}


def _next(plane, viewer, moved: bool, case: dict | None) -> tuple[str, str]:
    """(next action, approver)."""
    if not (moved or case):
        return "No action needed.", "Not needed: nothing has changed."
    approver = "The authorised approver for a corrected report (decision maker)"
    action = "Review the case and decide whether to reissue the report." if case else "Open a case so the change is reviewed."
    if case:
        try:
            got = _need("e4_cases").get(plane, case["id"], viewer)
            asked = [a["requested_from"] for a in got.get("approvals") or [] if a.get("requested_from") and not a.get("decided_by")]
            approver = asked[0] if asked else approver
        except Exception:  # noqa: BLE001 - the checker's name is a nicety; the default approver stands
            log.warning("the case could not be read for its checker")
    return action, approver


def _explain_total(plane, viewer, rvid: str, line: dict, lines: list[dict], cases: list[dict]) -> dict:
    """A total is not a manager valuation: it moved because the lines under it moved. Name them, their evidence and their case."""
    iv, nv, ccy, diff = line["issued"], line["known_now"], line["currency"], line["difference"]
    movers = [ln for ln in lines if not ln.get("is_total") and ln["difference"]]
    with wh.connect(plane, read_only=True) as con:
        rv = _row(con, "select * from report_versions where id = ?", [rvid])
    issued_on = _day(rv.get("issued_at") or rv["cutoff_at"])
    ev, sources, caveats, case, got = [], [], [], None, {}
    for m in movers:
        e, s = _evidence(plane, viewer, m)
        got[m["line_key"]] = e[-1].get("received_at") if e else None
        ev += [{**x, "label": f"{m['label']}: {x['label']}"} for x in e]
        sources += [x for x in s if x["document_id"] not in {y["document_id"] for y in sources}]
        caveats += [f"{m['label']}: {c[0].lower()}{c[1:]}" for c in _status_caveats(m["status"], e)]
        case = case or _case_for(m, cases)
    if not diff:
        answer = f"The total has not changed since the report was issued on {issued_on}: {_money(iv, ccy)}."
    else:
        parts = "; ".join(f"{m['label']} {'+' if m['difference'] > 0 else ''}{_money(m['difference'], ccy)} ({_money(m['issued'], ccy)} to {_money(m['known_now'], ccy)}"
                          + (f", statement received {_day(got[m['line_key']])})" if got.get(m["line_key"]) else ")") for m in movers)
        answer = (f"The total moved by {'+' if diff > 0 else ''}{_money(diff, ccy)} since the report was issued on {issued_on}: {_money(iv, ccy)} then, "
                  f"{_money(nv, ccy)} now. " + (f"It moved because of: {parts}." if parts else "No line below explains it."))
        rest = diff - sum((m["difference"] for m in movers), Decimal(0))
        if parts and rest:
            answer += f" {_money(rest, ccy)} is not explained by a line below."
        if case:
            answer += f" {_case_name(case)} is open for it."
    caveats.append(NO_MODEL)
    action, approver = _next(plane, viewer, bool(diff), case)
    return {"refused": False, "line_key": line["line_key"], "answer": answer, "wording": "rules",
            "evidence": [{k: v for k, v in e.items() if k != "row_id"} for e in ev] or [{"label": "issued", "value": iv, "currency": ccy, "state": "current"}],
            "figures": {"issued": iv, "known_now": nv, "difference": diff, "currency": ccy}, "status": line["status"],
            "sources": sources, "caveats": caveats, "next_action": action, "approver": approver,
            "case": {"id": case["id"], "number": case["number"], "title": case["title"]} if case else None}
