"""Harbor 3.0: which statement the office expects from each fund each period (assumption A2, table `expected_statements`).

After a load, `fill(x)` takes every fund (an instrument whose type says fund) the office has a commitment or a holding in and decides how often it sends statements:
  1. a person already confirmed a schedule for it: kept, never overridden;
  2. the fund's terms state it: a confirmed extracted field `reporting_frequency` (monthly, quarterly, semi-annual, annual) on a document of the fund;
  3. the cadence of statements already received: two or more past statements (a manager valuation, or a document with a valuation date)
     that are one, three, six or twelve months apart, most of the time;
  4. otherwise nothing is written and Decision 2 asks one question, "How often does <fund> send statements?" (monthly / quarterly).
Every row says how it was decided in `source`. Due date = period end + the days the fund terms state (confirmed extracted field
`statement_due_days`), else empty with the reason "no terms on file": a due date is never invented.
Periods run from the first statement received (at most 36 months back; else the commitment, at most 13 months back) to the first period end after today.
ponytail: a change of frequency adds the new periods; the old schedule's later periods stay (no cancelled status in the table yet)."""
import calendar
import logging
import re
from collections import Counter
from datetime import date

log = logging.getLogger(__name__)
SKILL = "action.detect-exception"
FREQ_N = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}
WORDS = (("semi", "semi_annual"), ("half", "semi_annual"), ("month", "monthly"), ("quarter", "quarterly"), ("annual", "annual"), ("year", "annual"))
ASK = {"Monthly": "monthly", "Quarterly": "quarterly"}
NO_TERMS = "no terms on file"
MAX_PERIODS = 40


def freq_of(text) -> str | None:
    t = str(text or "").lower()
    return next((f for w, f in WORDS if w in t), None)


def month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def add_months(d: date, k: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + k, 12)
    return month_end(y, m + 1)


def cadence(days: list[date]) -> str | None:
    """monthly / quarterly / semi_annual / annual when more than half of the gaps between the dates agree; else None (two dates make one gap)."""
    ds = sorted(set(days))
    gaps = [round((b - a).days / 30.44) for a, b in zip(ds, ds[1:])]
    if not gaps:
        return None
    gap, n = Counter(gaps).most_common(1)[0]
    return next((f for f, k in FREQ_N.items() if k == gap), None) if n * 2 > len(gaps) else None


def periods(freq: str, today: date, received: list[date], committed: date | None) -> list[date]:
    n = FREQ_N[freq]
    floor = add_months(today, -36 if received else -13)  # a schedule with no statement yet does not count back past a year
    start = max(min(received) if received else (committed or add_months(today, -13)), floor)
    phase = max(received).month % n if received else 0  # follow the manager's own month ends; with none, calendar ones (March, June, September, December)
    out, d = [], month_end(start.year, start.month)
    while len(out) < MAX_PERIODS:
        if (d.month - phase) % n == 0 and d >= start:
            out.append(d)
            if d > today:
                break
        d = add_months(d, 1)
    return out


# ---- reading the warehouse ----------------------------------------------------------------------------------------------------------

def _funds(con, org) -> list[tuple]:
    return con.execute(
        "select i.id, i.canonical_name from instruments i where i.organization_id = ? and i.instrument_type ilike '%fund%' "
        "and (exists (select 1 from commitments c where c.instrument_id = i.id) or exists (select 1 from position_snapshots p where p.instrument_id = i.id)) "
        "order by i.canonical_name", [org]).fetchall()


def _terms(con, iid) -> tuple[str | None, int | None, str]:
    """(frequency, due days, where it was read) from the fund's documents: only fields a person confirmed or corrected."""
    rows = con.execute(
        "select d.title, e.field_name, coalesce(e.corrected_value_text, e.value_text), e.value_numeric, e.page_number from extracted_fields e "
        "join documents d on d.id = e.document_id where d.instrument_id = ? and e.review_status in ('confirmed', 'corrected') "
        "and e.field_name in ('reporting_frequency', 'statement_due_days') order by d.document_date desc nulls last, e.id", [iid]).fetchall()
    freq = next(((freq_of(t), f"{d}" + (f", page {p}" if p else "")) for d, f, t, n, p in rows if f == "reporting_frequency" and freq_of(t)), None)
    days = next((int(n if n is not None else re.search(r"\d+", str(t)).group()) for d, f, t, n, p in rows
                 if f == "statement_due_days" and (n is not None or re.search(r"\d+", str(t or "")))), None)
    return (freq[0], days, freq[1]) if freq else (None, days, "")


def _received(con, iid) -> list[date]:
    return [r[0] for r in con.execute(
        "select valuation_date from valuation_observations where instrument_id = ? and valuation_type in ('manager_estimate', 'manager_final') "
        "union select valuation_date from documents where instrument_id = ? and valuation_date is not null", [iid, iid]).fetchall() if r[0]]


def _current(con, iid) -> dict:
    return {r[0]: r[1:] for r in con.execute(
        "select period_end, id, frequency, due_date, source from expected_statements e where instrument_id = ? "
        "and not exists (select 1 from expected_statements s where s.supersedes_expected_statement_id = e.id)", [iid]).fetchall()}


def _write(plane, con, org, iid, freq: str, source: str, days: int | None, today: date, received: list[date]) -> int:
    from sh_platform.v1.e1_write import record_many
    committed = con.execute("select min(committed_on) from commitments where instrument_id = ?", [iid]).fetchone()[0]
    have, rows, sups = _current(con, iid), [], []
    for pe in periods(freq, today, received, committed):
        due = date.fromordinal(pe.toordinal() + days) if days is not None else None
        old = have.get(pe)
        if old and (old[1], old[2]) == (freq, due) and old[3].split()[0] == source.split()[0]:
            continue
        rows.append({"instrument_id": iid, "period_end": pe, "due_date": due, "frequency": freq, "source": source, "due_reason": None if due else NO_TERMS})
        sups.append(old[0] if old else None)
    if rows:
        record_many(plane, "expected_statements", rows, sups)
    return len(rows)


# ---- the three public calls -----------------------------------------------------------------------------------------------------------

def fill(x) -> dict:
    """After a load: write the schedule of every fund that can be decided. {written, funds, open: [{id, name}]}; never stops the load."""
    from sh_platform.v1 import v3_harbor as H
    from sh_platform.v1 import v3_skills as S
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    out = {"written": 0, "funds": 0, "open": []}
    try:
        with S.record(x.plane, x.th.get("id"), SKILL) as rec, wh.connect(x.plane) as con:
            org, today = org_id(x.plane), wh.today(x.plane)
            for iid, name in _funds(con, org):
                have = _current(con, iid)
                if any(str(v[3]).startswith("confirmed by") for v in have.values()):
                    continue
                freq, days, where = _terms(con, iid)
                got = _received(con, iid)
                if freq:
                    source = f"fund terms: {where}"
                elif (freq := cadence(got)):
                    source = f"cadence of {len(set(got))} statements received ({min(got)} to {max(got)})"
                else:
                    if not have:
                        out["open"].append({"id": str(iid), "name": name})
                    continue
                n = _write(x.plane, con, org, iid, freq, source, days, today, got)
                out["written"] += n
                out["funds"] += bool(n)
            rec["detail"] = f"{out['written']} expected statements for {out['funds']} funds, {len(out['open'])} funds to ask about"
    except Exception:  # noqa: BLE001 - the schedule is a help; the load is already done
        log.warning("expected statements could not be filled", exc_info=True)
        return out
    ex = x.th.setdefault("exceptions", [])
    for o in out["open"]:  # said once on the Desk; Decision 2 of the next thread asks it
        t = f"How often does {o['name']} send statements?"
        if not any(e.get("title") == t for e in ex):
            ex.append({"title": t, "text": "Nothing on file says, and fewer than two statements have arrived. I will ask at the next Decision 2; until then I do not count it missing."})
    return out


def questions(x) -> list[dict]:
    """Decision 2: one question for each fund with a commitment or a holding whose frequency nothing on file can tell (and no schedule yet)."""
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    qs = []
    try:
        with wh.connect(x.plane, read_only=True) as con:
            for iid, name in _funds(con, org_id(x.plane)):
                if _current(con, iid) or _terms(con, iid)[0] or cadence(_received(con, iid)):
                    continue
                qs.append({"id": f"pdf:freq-{iid}", "text": f"How often does {name} send statements?", "options": list(ASK), "assumed": None})
    except Exception:  # noqa: BLE001 - no warehouse yet: nothing to ask
        log.info("expected statements: no questions", exc_info=True)
    return qs


def answer(x, iid: str, val: str) -> str:
    """b_answers: the person's pick is the schedule for that fund, with them named as the source."""
    from sh_platform.v1 import wh
    from sh_platform.v1.e1_write import org_id
    freq = ASK.get(val)
    if not freq:
        return ""
    who = x.th.get("started_by") or "the person"
    with wh.connect(x.plane) as con:
        name = (con.execute("select canonical_name from instruments where id = ?", [iid]).fetchone() or [""])[0]
        n = _write(x.plane, con, org_id(x.plane), iid, freq, f"confirmed by {who}", _terms(con, iid)[1], wh.today(x.plane), _received(con, iid))
    x.th["exceptions"] = [e for e in x.th.get("exceptions") or [] if e.get("title") != f"How often does {name} send statements?"]
    return f"{name}: {freq}, {n} periods"
