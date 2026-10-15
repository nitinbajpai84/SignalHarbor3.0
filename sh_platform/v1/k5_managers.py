"""K3 Manager inbox (UC3) and manager research (UC7).

Everything here is read from records and worded by the program: dates, days late, counts and amounts are never written by a model.
A manager is the `manager_name` on its funds (instruments); the manager id in a URL is a slug of that name.
A fund is visible to a person only when one of its valuations sits in a portfolio they may see (E1d); administrators see all.
Nothing here says whether a manager is good or bad, and nothing is sent: a follow-up is a plain-text draft for a person to copy.
"""
from __future__ import annotations

import logging
import re
import secrets
from urllib.parse import quote
from datetime import date, datetime, timedelta
from decimal import Decimal

from sh_platform.v1.scope_memo import memo
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.v1 import wh
from sh_platform.v1.i2_north import Refused

log = logging.getLogger(__name__)
KINDS = {"note": "Note", "meeting": "Meeting", "question": "Open question"}
MAX_TEXT = 2000
STATUS_WORDS = {"official": "official", "estimated": "estimated", "revised": "revised", "unverified": "unverified"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def _add_business_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


def _bdays_after(a: date, b: date) -> int:
    """Weekdays in (a, b]: how statement_due counts, so 'days late' means business days."""
    return sum((a + timedelta(days=i)).weekday() < 5 for i in range(1, max((b - a).days, 0) + 1))


def _day(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _money(v) -> str:
    """A plain decimal string without trailing zeros (never 5E+6)."""
    t = f"{Decimal(str(v)):f}"
    return t.rstrip("0").rstrip(".") if "." in t else t


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _pretty(d) -> str:
    d = _day(d)
    return f"{d.day} {d:%b %Y}" if d else ""


def _may(viewer, route: str) -> bool:
    """Whether the viewer's roles pass the route's line in k5.permissions.yaml, so a screen hides what the server would refuse."""
    import yaml
    from pathlib import Path
    roles = yaml.safe_load(Path(__file__).with_name("k5.permissions.yaml").read_text(encoding="utf-8"))["routes"][route]["roles"]
    return bool(set(getattr(viewer, "roles", ()) or ()) & set(roles))


def _visible_fund(viewer, visible: set[str] | None, portfolios: set[str | None]) -> bool:
    return visible is None or bool({p for p in portfolios if p} & visible)


def _visible_set(plane, viewer) -> set[str] | None:
    """None = everything (administrator)."""
    from sh_platform.v1 import e1_access
    return None if e1_access.is_admin(viewer) else e1_access.visible_portfolios(plane, viewer)


# ---- funds and their statements -------------------------------------------------------------------------------------------------

def _funds(plane, viewer) -> list[dict]:
    """Funds that name a manager and that the viewer may see: [{fund_id, fund_name, manager, currency}]."""
    vis = _visible_set(plane, viewer)
    with wh.connect(plane, read_only=True) as con:
        funds = con.execute("select id, canonical_name, manager_name, currency from instruments "
                            "where manager_name is not null and trim(manager_name) <> '' order by manager_name, canonical_name").fetchall()
        ports: dict[str, set] = {}
        first: dict[str, date] = {}
        for iid, pid, vd in con.execute("select instrument_id, portfolio_id, valuation_date from valuation_observations").fetchall():
            ports.setdefault(str(iid), set()).add(str(pid) if pid else None)
            first[str(iid)] = min(first.get(str(iid), _day(vd)), _day(vd))
    return [{"fund_id": str(i), "fund_name": n, "manager": m.strip(), "currency": c, "first_valued": _iso(first.get(str(i)))}
            for i, n, m, c in funds if _visible_fund(viewer, vis, ports.get(str(i), set()))]


def _due_days(plane, as_of: date):
    from sh_platform.v1 import e3_rules
    params = (e3_rules.current(plane, "statement_due", as_of) or {}).get("parameters") or {}
    n = params.get("business_days_after_month_end") or params.get("business_days") or params.get("days")
    return int(n) if n else None


def _cadence(dates: list[date]) -> str:
    ds = sorted(set(dates))
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    return "quarterly" if gaps and min(gaps) >= 80 else "monthly"


def _current_values(plane) -> dict[str, list[dict]]:
    """Every current valuation, by fund: one read for the whole request (a read per fund made the pages slow, AUC3-02)."""
    from sh_platform.v1 import e1_asof
    out: dict[str, list[dict]] = {}
    for r in e1_asof.snapshot(plane, "valuation_observations", {}, None):
        out.setdefault(str(r["instrument_id"]), []).append(r)
    return out


def _last_value(rows: list[dict], vis: set[str] | None, today: date) -> dict | None:
    from sh_platform.v1.k4_office import _status   # the office view's word: Stale beats Official/Revised/Estimated after 90 days
    from sh_platform.v1.e3_calc import _val_status
    rows = [r for r in rows if vis is None or (r.get("portfolio_id") and str(r["portfolio_id"]) in vis)]
    if not rows:
        return None
    r = max(rows, key=lambda x: (x["valuation_date"], x["recorded_at"]))
    return {"amount": _money(r["value_amount"]), "currency": r["currency"],
            "valuation_date": _iso(r["valuation_date"]), "recorded_at": _iso(r["recorded_at"]), "status": (st := _status(STATUS_WORDS[_val_status(r)], r["valuation_date"], today)), "status_word": st.capitalize(), "valuation_id": str(r["id"])}


def _statements(plane) -> dict[str, list[dict]]:
    """Manager statements by fund, newest received first: one read for the whole request."""
    from sh_platform.v1 import e2_intake
    out: dict[str, list[dict]] = {}
    for d in e2_intake.listing(plane):
        if d["document_type"] == "manager_statement":
            out.setdefault(str(d["instrument_id"]), []).append(d)
    return out


def _statement_values(plane, vis: set[str] | None) -> dict[str, dict]:
    """The figure each statement carries: the last valuation of record that cites it (a pending or rejected step is not the figure)."""
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute("select evidence_document_id, value_amount, currency, approval_status, portfolio_id from valuation_observations "
                           "where evidence_document_id is not null order by recorded_at").fetchall()
    return {str(doc): {"amount": _money(amt), "currency": cur} for doc, amt, cur, appr, pid in rows
            if appr not in NOT_OF_RECORD and (vis is None or (pid and str(pid) in vis))}


def _revision(figures: dict[str, dict], doc: dict) -> dict | None:
    """Old figure to new figure for a statement that replaces an earlier one: {from, to, change, currency}; None when either is unknown."""
    new, old = figures.get(str(doc["id"])), figures.get(str(doc.get("supersedes_document_id") or ""))
    if not new or not old or new["currency"] != old["currency"]:
        return None
    change = Decimal(new["amount"]) - Decimal(old["amount"])
    return {"from": old["amount"], "to": new["amount"], "change": ("+" if change > 0 else "") + _money(change), "currency": new["currency"]}


MAX_BACK = 6   # ponytail: look back at most six month ends; raise it if a longer chase is wanted


def _earlier_missing(docs: list[dict], f: dict, cadence: str, as_of: date, due_n: int | None) -> list[dict]:
    """Month ends before the latest one whose statement never arrived and whose signed due date has passed, back to the fund's first record."""
    if not due_n:
        return []
    have = {_day(d["valuation_date"]) for d in docs if d["valuation_date"]}
    start = min(have) if have else _day(f.get("first_valued"))
    out, end = [], as_of.replace(day=1) - timedelta(days=1)
    for _ in range(MAX_BACK - 1):
        end = end.replace(day=1) - timedelta(days=1)
        if not start or end < start:
            break
        due = _add_business_days(end, due_n)
        if end not in have and (cadence == "monthly" or end.month in (3, 6, 9, 12)) and as_of > due:
            out.append({"period_end": end.isoformat(), "due": due.isoformat(), "days_late": _bdays_after(due, as_of)})
    return out


def _fund_row(f: dict, docs: list[dict], values: list[dict], figures: dict[str, dict], as_of: date, due_n: int | None, vis: set[str] | None) -> dict:
    cadence = _cadence([_day(d["valuation_date"]) for d in docs if d["valuation_date"]])
    period_end = as_of.replace(day=1) - timedelta(days=1)
    due = _add_business_days(period_end, due_n) if due_n else None
    mine = [d for d in docs if _day(d["valuation_date"]) == period_end]
    revised = sum(1 for d in mine if d["supersedes_document_id"])
    first = min((_day(d["received_at"]) for d in mine), default=None)
    expected = cadence == "monthly" or period_end.month in (3, 6, 9, 12)
    days_late = None
    if not expected:
        state, word = "not_expected", "Not expected this month"
    elif mine:
        late = _bdays_after(due, first) if due and first and first > due else 0
        state, word, days_late = ("received_late", "Received late", late) if late else ("received", "Received", 0)
    elif not due:
        state, word = "no_rule", "No due date signed"
    elif as_of > due:
        state, word, days_late = "late", "Late", _bdays_after(due, as_of)
    else:
        state, word = "not_due", "Not due yet"
    return {**f, "cadence": cadence, "period_end": period_end.isoformat(), "due": _iso(due), "state": state, "state_word": word,
            "received_on": _iso(first), "days_late": days_late, "revised_count": revised,
            "revisions_total": sum(1 for d in docs if d["supersedes_document_id"]),
            "earlier_missing": _earlier_missing(docs, f, cadence, as_of, due_n),
            "last_value": _last_value(values, vis, as_of),
            "statements": [{"id": d["id"], "title": d["title"], "valuation_date": d["valuation_date"], "received_at": d["received_at"],
                            "status": d["document_status"], "current": d["current"],
                            "revision": _revision(figures, d) if d["supersedes_document_id"] else None} for d in mine]}


@memo
def inbox(plane, viewer, as_of=None) -> dict:
    """Per manager and fund: statement expected this month, received, late (days), revised count, last value and status."""
    return _inbox(plane, viewer, as_of)[0]


def _inbox(plane, viewer, as_of=None, only: str | None = None) -> tuple[dict, dict]:
    """(the inbox, what it read: statements by fund, statement figures, due days, visible set). `only` = one manager's slug; others are skipped."""
    day = _day(as_of) if as_of else wh.now().date()
    if day is None:
        raise Refused(400, "The date is not one we can read. Use year-month-day.")
    vis, due_n = _visible_set(plane, viewer), _due_days(plane, day)
    funds = [f for f in _funds(plane, viewer) if only is None or slug(f["manager"]) == only]
    docs, values, figures = (_statements(plane), _current_values(plane), _statement_values(plane, vis)) if funds else ({}, {}, {})
    by: dict[str, dict] = {}
    for f in funds:
        m = by.setdefault(slug(f["manager"]), {"manager_id": slug(f["manager"]), "name": f["manager"], "funds": []})
        m["funds"].append(_fund_row(f, docs.get(f["fund_id"], []), values.get(f["fund_id"], []), figures, day, due_n, vis))
    managers = list(by.values())
    for m in managers:
        fs = m["funds"]
        m["counts"] = {"expected": sum(f["state"] != "not_expected" for f in fs),
                       "received": sum(f["state"] in ("received", "received_late") for f in fs),
                       "missing_earlier": sum(len(f["earlier_missing"]) for f in fs),
                       "late": sum(f["state"] in ("late", "received_late") for f in fs),
                       "revised": sum(f["revised_count"] for f in fs)}
    return {"as_of": day.isoformat(), "due_rule_signed": due_n is not None, "can_draft": _may(viewer, "POST /api/v1/managers/{manager_id}/followup"),
            "rule_note": None if due_n else "No signed rule says when statements are due, so lateness cannot be judged yet.",
            "managers": managers}, {"docs": docs, "figures": figures, "due_n": due_n, "vis": vis}


def _find(plane, viewer, manager_id: str, as_of=None, read: dict | None = None) -> dict:
    """One manager's inbox row, worked out for that manager only. Pass `read` (a dict) to get back what was read on the way."""
    box, got_read = _inbox(plane, viewer, as_of, only=str(manager_id))
    got = next(iter(box["managers"]), None)
    if not got:
        raise Refused(404, "We could not find that manager, or you do not have access to its funds.")
    if read is not None:
        read.update(got_read)
    return got


def _contact(plane, fund_ids: list[str]) -> str | None:
    """The manager's named contact: an approved instrument_identifiers row of type 'manager_contact' on one of its funds (the core model has no contacts table)."""
    if not fund_ids:
        return None
    with wh.connect(plane, read_only=True) as con:
        r = con.execute(f"select identifier_value from instrument_identifiers where identifier_type = 'manager_contact' and mapping_status = 'approved' "
                        f"and instrument_id in ({','.join('?' * len(fund_ids))}) order by identifier_value limit 1", fund_ids).fetchone()
    return (str(r[0]).strip() or None) if r else None


# ---- follow-up draft (never sent) ------------------------------------------------------------------------------------------------

def draft_followup(plane, viewer, manager_id: str, fund_id: str | None = None, as_of=None) -> dict:
    m = _find(plane, viewer, manager_id, as_of)
    if fund_id and not any(f["fund_id"] == fund_id for f in m["funds"]):
        raise Refused(404, "We could not find that fund for this manager.")
    mine = [f for f in m["funds"] if not fund_id or f["fund_id"] == fund_id]
    chase = [f for f in mine if f["state"] == "late"]
    older = [(f, e) for f in mine for e in f["earlier_missing"]]
    if not chase and not older:
        return {"manager": m["name"], "draft": None, "sent": False, "message": "Every statement due so far from this manager has arrived."}
    days = lambda n: f"{n} business day{'s' if n != 1 else ''}"  # noqa: E731
    period = _pretty(chase[0]["period_end"] if chase else older[0][1]["period_end"])
    lines = [f"- {f['fund_name']}: due {_pretty(f['due'])}, {days(f['days_late'])} overdue" for f in chase]
    lines += [f"- {f['fund_name']} (period ending {_pretty(e['period_end'])}): due {_pretty(e['due'])}, {days(e['days_late'])} overdue" for f, e in older]
    names = list(dict.fromkeys([f["fund_name"] for f in chase] + [f["fund_name"] for f, _ in older]))
    subject = f"Statement request: {period} ({', '.join(names)})"
    many = len(lines) > 1
    it = "them" if many else "it"
    what = (("the statements below, each with its period end:" if many else "the statement below:") if older
            else f"the statement{'s' if many else ''} for the period ending {period} for:")
    who = getattr(viewer, "name", "") or "The investment office"
    contact = _contact(plane, [f["fund_id"] for f in m["funds"]])
    hello = f"{contact} ({m['name']})" if contact else f"{m['name']} team"
    body = (f"Dear {hello},\n\nWe have not yet received {what}\n\n" + "\n".join(lines)
            + f"\n\nCould you please send {it}, or let us know when to expect {it}?\n\nKind regards,\n" + who)
    _add_note(plane, viewer, manager_id, "A follow-up email was drafted (not sent): " + ", ".join(names), "note", system=True)
    return {"manager": m["name"], "contact": contact, "subject": subject, "body": body, "draft": subject + "\n\n" + body, "sent": False,
            "note": "This email has not been sent. Copy it into your own email to send it."}


# ---- notes -----------------------------------------------------------------------------------------------------------------------

def _notes_path(plane, manager_id: str):
    return plane.path("managers", manager_id, "notes.json")


def notes(plane, manager_id: str) -> list[dict]:
    try:
        return read_json_strict(_notes_path(plane, manager_id), list) or []
    except (OSError, ValueError):
        return []


def _add_note(plane, viewer, manager_id: str, text: str, kind: str = "note", system: bool = False, on: str | None = None) -> dict:
    text = str(text or "").strip()
    if kind not in KINDS:
        raise Refused(400, "Choose note, meeting or open question.")
    if not text or len(text) > MAX_TEXT:
        raise Refused(400, f"Write something, up to {MAX_TEXT} characters.")
    day = _day(on) if on else wh.now().date()
    if day is None:
        raise Refused(400, "The date is not one we can read. Use year-month-day.")
    item = {"id": f"mn_{secrets.token_hex(5)}", "kind": kind, "text": text, "by": getattr(viewer, "name", ""), "on": day.isoformat(),
            "at": wh.now().isoformat(timespec="seconds"), "system": system, "state": "open"}
    p = _notes_path(plane, manager_id)
    with lock_for(p):
        got = notes(plane, manager_id)
        got.append(item)
        write_json_atomic(p, got)
    return item


def add_note(plane, viewer, manager_id: str, text: str, kind: str = "note", on: str | None = None) -> dict:
    _find(plane, viewer, manager_id)  # a person who cannot see the manager's funds cannot write to its file
    return _add_note(plane, viewer, manager_id, text, kind, on=on)


def resolve_question(plane, viewer, manager_id: str, note_id: str) -> dict:
    _find(plane, viewer, manager_id)
    p = _notes_path(plane, manager_id)
    with lock_for(p):
        got = notes(plane, manager_id)
        n = next((x for x in got if x["id"] == note_id and x["kind"] == "question"), None)
        if not n:
            raise Refused(404, "We could not find that question.")
        n["state"], n["answered_by"], n["answered_at"] = "answered", getattr(viewer, "name", ""), wh.now().isoformat(timespec="seconds")
        write_json_atomic(p, got)
    return n


# ---- profile ---------------------------------------------------------------------------------------------------------------------

def _commitments(plane, fund_ids: list[str], vis: set[str] | None) -> dict:
    """Commitment, called and uncalled per fund. Calls counted are the confirmed, non-superseded ones (k6_liquidity)."""
    with wh.connect(plane, read_only=True) as con:
        have = {r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()}
        if "commitments" not in have:
            return {"available": False, "rows": [], "message": "Not available yet. Commitments have not been loaded."}
        names = {str(i): n for i, n in con.execute("select id, entity_name from legal_entities").fetchall()}
        owned: dict[str, set] = {}
        for pid, ent in con.execute("select id, legal_entity_id from portfolios").fetchall():
            owned.setdefault(str(ent), set()).add(str(pid))
    from sh_platform.v1 import k6_liquidity   # counts confirmed, non-superseded calls only
    rows = []
    for fid in fund_ids:
        for c in k6_liquidity.commitments(plane, instrument_id=fid):
            if vis is not None and not owned.get(str(c["legal_entity_id"]), set()) & vis:
                continue
            rows.append({"commitment_id": c["id"], "fund_id": fid, "entity": names.get(str(c["legal_entity_id"])), "currency": c["currency"],
                         "committed_on": _iso(c.get("committed_on")), "commitment": _money(c["commitment_amount"]),
                         "called": _money(c["called"]), "uncalled": _money(c["uncalled"])})
    return {"available": True, "rows": rows, "message": None if rows else "No commitments are recorded for this manager's funds."}


def _library(plane, viewer, name: str) -> tuple[list[dict], list[dict]]:
    """(shown rows, readable raw items) for diligence documents that name the manager. A locked file shows its preview only."""
    from sh_platform.v1 import c4_library
    shown = c4_library.listing(plane, viewer, name)
    ids = {s["id"] for s in shown}
    raw = [i for i in c4_library._index(plane) if i["id"] in ids and c4_library.readable(i, viewer)]
    return shown, raw


TERMS = "reporting statements within days quarter auditor change team portfolio manager key person fees"


def _cut(text: str, n: int) -> str:
    """At most n characters, ended at a word, never mid-word."""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _readable(plane, hit: dict) -> str:
    """A passage as a person reads it: no running page headers or footers, no markdown marks, table rows as 'label: value'."""
    from sh_platform.v1 import doc_index
    try:
        lines = [t for _, t in doc_index.read(plane, hit["path"], hit["from"], hit["to"], max_lines=200, max_chars=20000)]
    except Exception:  # noqa: BLE001 - fall back to the passage text as indexed
        lines = []
    if not lines:
        return re.sub(r"\s+", " ", hit["text"]).strip()
    out = []
    for ln in lines:
        t = ln.strip()
        if re.fullmatch(r"Page \d+( of \d+)?|\d+(\.\d+)*\.?", t) or ("|" in t and not t.startswith("|")):
            continue   # ponytail: any line with a mid-line '|' is taken for a running header or footer; tell them apart by repetition if prose uses '|'
        if t.startswith("|"):
            cells = [c.strip() for c in t.strip("|").split("|") if c.strip()]
            if not cells or all(set(c) <= set("-: ") for c in cells):
                continue
            t = ": ".join(cells[:2]) + (" (" + ", ".join(cells[2:]) + ")" if cells[2:] else "") + "."
        elif re.match(r"#|- |\* |\d+\. ", t) and not re.search(r"[.;:?!]$", t):
            t += "."   # a heading, list item or table row is a sentence of its own
        t = re.sub(r"^(#+|- \[[ x]\]|[-*])\s*", "", t)
        if t:
            out.append(t)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def _key_sentences(text: str, n: int = 3, size: int = 420) -> str:
    """The n sentences of a passage that say the most about terms, team and reporting, in their own order."""
    words = set(TERMS.split())
    sents = [x for x in re.split(r"(?<=[^\d\s]\.)\s+|(?<=\d{4}\.)\s+", text) if x]   # "1. Fund C" is a list number, not a full stop

    def score(x: str) -> int:
        hits = sum(w.lower().strip(".,;:()'") in words for w in x.split())
        return hits + 2 * bool(hits and re.search(r"\d", x))   # a figure or date about the terms counts most
    best = sorted(sorted(range(len(sents)), key=lambda i: -score(sents[i]))[:n])
    return _cut(" ".join(sents[i] for i in best if score(sents[i]) > 0) or text, size)


KIND_WORDS = [(r"\bddq\b|questionnaire", "due diligence questionnaire"), (r"newsletter", "newsletter"), (r"\bletter\b", "letter"),
              (r"meeting|\bcall\b|review|\bnotes?\b", "meeting note")]   # ponytail: read from the file name; a library 'kind' field would be better


def _kind_word(name: str, kind: str) -> str:
    """What a diligence document is, read from its name (the library only says 'document'); the library's word when nothing matches."""
    return next((w for pat, w in KIND_WORDS if re.search(pat, name.lower())), kind)


def _documents_with_passages(plane, name: str, shown: list[dict], raw: list[dict]) -> list[dict]:
    """Diligence documents (DDQ, newsletters, notes) with date and the passage that says most about terms, team and reporting
    (never the cover page); a locked file shows its preview only, never a passage."""
    from sh_platform.v1 import doc_index
    paths = {i["id"]: i["path"] for i in raw}   # raw = the readable items only (_library)
    out = []
    for s in shown:
        row = {k: s.get(k) for k in ("id", "name", "kind", "at", "uploaded_by", "access", "preview")}
        row["kind"] = _kind_word(s.get("name") or "", s.get("kind") or "document")
        row["passage"] = None
        if s["id"] in paths:
            try:
                hits = doc_index.search(plane, [paths[s["id"]]], f"{name} {TERMS}", 3)
                row["passage"] = _key_sentences(" ".join(_readable(plane, h) for h in sorted(hits, key=lambda h: h["from"]))) if hits else None
            except Exception:  # an unreadable file costs the passage, not the list
                log.warning("manager document passage could not be searched", exc_info=True)
        out.append(row)
    return out


def profile(plane, viewer, manager_id: str, as_of=None) -> dict:
    return _profile(plane, viewer, manager_id, as_of)[0]


def _profile(plane, viewer, manager_id: str, as_of=None, full: bool = True) -> tuple[dict, list[dict]]:
    """(the profile, the readable library items that name the manager). `full=False` skips commitments and the document passages,
    which 'what changed' does not show."""
    read: dict = {}
    m = _find(plane, viewer, manager_id, as_of, read)
    vis, due_n, figures = read["vis"], read["due_n"], read["figures"]
    ids = [f["fund_id"] for f in m["funds"]]
    shown, raw = _library(plane, viewer, m["name"])
    timeline = []
    for f in m["funds"]:
        for d in read["docs"].get(f["fund_id"], []):
            vd, rd = _day(d["valuation_date"]), _day(d["received_at"])
            due = _add_business_days(vd, due_n) if due_n and vd else None
            late = _bdays_after(due, rd) if due and rd and rd > due and not d["supersedes_document_id"] else 0   # a revision is not a late statement
            timeline.append({"document_id": d["id"], "fund_id": f["fund_id"], "fund_name": f["fund_name"], "valuation_date": d["valuation_date"],
                             "received_at": d["received_at"], "status": d["document_status"], "current": d["current"],
                             "replaces": d["supersedes_document_id"], "title": d["title"], "days_late": late, "value": figures.get(str(d["id"])),
                             "revision": _revision(figures, d) if d["supersedes_document_id"] else None})
    timeline.sort(key=lambda t: (str(t["valuation_date"]), str(t["received_at"])), reverse=True)
    ns = notes(plane, manager_id)
    meetings = [n["on"] for n in ns if n["kind"] == "meeting"]
    return {"manager_id": manager_id, "name": m["name"], "as_of": _iso(as_of) if as_of else wh.now().date().isoformat(),
            "funds": m["funds"], "commitments": _commitments(plane, ids, vis) if full else None, "timeline": timeline,
            "notes": [n for n in reversed(ns) if n["kind"] in ("note", "meeting") and not n["system"]],
            "questions": [n for n in reversed(ns) if n["kind"] == "question"],
            "documents": _documents_with_passages(plane, m["name"], shown, raw) if full else [],
            "last_meeting": max(meetings) if meetings else None, "can_write": _may(viewer, "POST /api/v1/managers/{manager_id}/notes")}, raw


# ---- what changed since the last meeting -----------------------------------------------------------------------------------------

NOT_OF_RECORD = ("pending", "rejected")
OF_RECORD = ("approved", "approved_official", "confirmed")


def _revised_values(plane, fund_ids: list[str], names: dict[str, str], cut: date, vis: set[str] | None) -> list[dict]:
    """Valuations of record that replaced an earlier value and were recorded after `cut`: old value to new value, dated, with the source document.
    The old value is the last one of record before it: a pending or rejected step, or a confirmation of the same figure, is skipped."""
    if not fund_ids:
        return []
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute("select n.id, n.instrument_id, n.portfolio_id, n.valuation_date, n.recorded_at, n.value_amount, n.currency, n.approval_status, "
                           "n.supersedes_valuation_id, n.evidence_document_id, d.title, d.received_at "
                           "from valuation_observations n left join documents d on d.id = n.evidence_document_id "
                           f"where n.instrument_id in ({','.join('?' * len(fund_ids))})", fund_ids).fetchall()
    by = {str(r[0]): r for r in rows}
    out = []
    for vid, iid, pid, vd, rec, new, cur, appr, sup, doc, title, got in rows:
        if not sup or appr not in OF_RECORD or (vis is not None and str(pid) not in vis) or not (_day(rec) and _day(rec) > cut):
            continue
        old = by.get(str(sup))
        while old and (old[7] in NOT_OF_RECORD or Decimal(old[5]) == Decimal(new)):
            old = by.get(str(old[8])) if old[8] else None
        if not old:
            continue   # nothing of record before it, or only the same figure confirmed
        name, was, now = names[str(iid)], Decimal(_money(old[5])), Decimal(_money(new))
        sent = f", from the statement received {_pretty(got)}" if got else ""
        out.append({"date": _day(rec).isoformat(), "kind": "revised_value", "valuation_id": str(vid),
                    "text": f"{name} value for {_pretty(vd)} was revised from {was:,f} to {now:,f} {cur} ({now - was:+,f}){sent}, recorded {_pretty(rec)}.",
                    "source": {"label": title or f"Valuation of {name}", "link": f"/centre/action/evidence/{doc}" if doc else None}})
    return out


def changes(plane, viewer, manager_id: str, since: str | None = None) -> dict:
    """Dated facts after `since` (default: the last recorded meeting), each with its source. The program writes every sentence and figure."""
    from sh_platform.v1 import doc_index
    p, raw = _profile(plane, viewer, manager_id, full=False)
    ns = notes(plane, manager_id)
    meetings = sorted(n["on"] for n in ns if n["kind"] == "meeting")
    cut = _day(since) if since else (_day(meetings[-1]) if meetings else None)
    if since and cut is None:
        raise Refused(400, "The date is not one we can read. Use year-month-day.")
    if cut is None:
        return {"manager_id": manager_id, "name": p["name"], "since": None, "items": [], "worded_by": "rules",
                "answer": "No meeting is recorded for this manager yet. Add a meeting note with its date, or pick a date, and ask again."}
    items = []
    for t in p["timeline"]:
        rd = _day(t["received_at"])
        if rd and rd > cut:
            what = "A revised statement" if t["replaces"] else "A statement"
            n = t["days_late"]
            late = f", {n} business day{'s' if n != 1 else ''} late" if n else ""
            items.append({"date": rd.isoformat(), "kind": "statement",
                          "text": f"{what} for {t['fund_name']} dated {_pretty(t['valuation_date'])} arrived ({t['status'].replace('_', ' ')}){late}.",
                          "source": {"label": t["title"], "link": f"/centre/action/evidence/{t['document_id']}"}})
    revised = _revised_values(plane, [f["fund_id"] for f in p["funds"]], {f["fund_id"]: f["fund_name"] for f in p["funds"]}, cut, _visible_set(plane, viewer))
    items += revised
    for f in p["funds"]:
        for e in f["earlier_missing"] + ([{"period_end": f["period_end"], "due": f["due"], "days_late": f["days_late"]}] if f["state"] == "late" else []):
            if _day(e["due"]) > cut:   # became overdue after the meeting
                items.append({"date": e["due"], "kind": "late", "source": {"label": f"Due date for {_pretty(e['period_end'])}", "link": None},
                              "text": f"The statement for {f['fund_name']} for the period ending {_pretty(e['period_end'])} was due {_pretty(e['due'])} and is {e['days_late']} business days late."})
    seen = {r["valuation_id"] for r in revised}
    for f in p["funds"]:
        lv = f["last_value"]
        if lv and lv["valuation_id"] in seen:
            continue
        newer, recorded = (_day(lv["valuation_date"]), _day(lv["recorded_at"])) if lv else (None, None)
        if lv and ((newer and newer > cut) or (recorded and recorded > cut)):
            late_record = not (newer and newer > cut)   # a restated value for an older date, recorded after the meeting
            items.append({"date": recorded.isoformat() if late_record else lv["valuation_date"], "kind": "valuation",
                          "text": f"{f['fund_name']} last valued at {Decimal(lv['amount']):,f} {lv['currency']} on {_pretty(lv['valuation_date'])} ({lv['status']})"
                                  + (f", recorded {_pretty(recorded)}." if late_record else "."),
                          "valuation_id": lv["valuation_id"], "source": {"label": f"Valuation of {f['fund_name']}", "link": None}})
    for n in p["notes"] + p["questions"]:
        if _day(n["on"]) > cut:
            items.append({"date": n["on"], "kind": n["kind"], "text": f"{KINDS[n['kind']]} by {n['by']}: {n['text']}",
                          "source": {"label": f"{KINDS[n['kind']]}, {_pretty(n['on'])}", "link": None}})
    fresh = [i for i in raw if _day(i.get("at")) and _day(i["at"]) > cut]
    for i in fresh:
        items.append({"date": _day(i["at"]).isoformat(), "kind": "document", "text": f"Document added: {i['name']}.",
                      "source": {"label": i["name"], "link": f"/centre/library/view?file={quote(i['path'], safe='')}" if i.get("path") else None}})
    hits = []
    if fresh:
        try:
            hits = doc_index.search(plane, [i["path"] for i in fresh], f"{p['name']} change team update", 3)
        except Exception:  # an unreadable file costs the passages, not the answer
            log.warning("manager passages could not be searched", exc_info=True)
    name_of = {i["path"]: i for i in fresh}
    chips = [{"file": name_of[h["path"]]["name"], "from": h["from"], "to": h["to"], "text": _cut(_readable(plane, h), 600),
              "date": _day(name_of[h["path"]]["at"]).isoformat()} for h in hits]
    items.sort(key=lambda x: x["date"], reverse=True)
    answer = (f"Since {_pretty(cut)}: " + f"{len(items)} dated item{'s' if len(items) != 1 else ''}, newest first." if items
              else f"Nothing new is recorded for {p['name']} since {_pretty(cut)}.")
    return {"manager_id": manager_id, "name": p["name"], "since": cut.isoformat(), "items": items, "passages": chips, "answer": answer,
            "worded_by": "rules", "note": "Every line is a dated record. This does not say whether the manager is doing well or badly."}
