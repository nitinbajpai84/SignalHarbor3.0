"""K7 benchmark factory: certified portfolio-vs-benchmark returns. A benchmark definition still in progress (or draft) is refused for
certified output and is raised once as a policy question (a case), because someone must decide what the benchmark is before anyone reports against it.
All arithmetic is in e3_calc (Decimal, never a model)."""
from __future__ import annotations

from sh_platform.v1 import e3_calc, wh
from sh_platform.v1.i2_north import Refused

POLICY_TYPE = "policy_question"
_STATUS_WORDS = {"in_progress": "still being defined", "draft": "still a draft"}


def _title(code: str) -> str:
    return f"Agree the definition of benchmark {code}"


def flag_policy_question(plane, code: str, name: str = "", status: str = "in_progress") -> str:
    """Open the policy-question case for this benchmark unless one is already open; return its id."""
    from sh_platform.v1 import e4_cases
    title = _title(code)
    with wh.connect(plane, read_only=True) as con:
        row = con.execute("select id from exceptions where exception_type = ? and title = ? and status not in ('resolved', 'rejected') limit 1",
                          [POLICY_TYPE, title]).fetchone()
    if row:
        return str(row[0])
    word = _STATUS_WORDS.get(status, status)
    return e4_cases.open(plane, {"exception_type": POLICY_TYPE, "title": title, "materiality_status": "unknown",
                                 "description": f"The benchmark {name or code} is {word}. It cannot be used in a certified report until it is approved. "
                                                "Who decides what it contains, and from when?"})


def _not_approved(plane, d: dict) -> str:
    word = _STATUS_WORDS.get(d["approval_status"], d["approval_status"])
    with wh.connect(plane, read_only=True) as con:
        open_q = con.execute("select 1 from exceptions where exception_type = ? and title = ? and status not in ('resolved', 'rejected') limit 1",
                             [POLICY_TYPE, _title(d["benchmark_code"])]).fetchone()
    tail = f' It waits on the open question "{_title(d["benchmark_code"])}".' if open_q else ""
    return f"The benchmark {d['benchmark_name']} (version {d['version_number']}) is {word}, so it cannot be used in a certified report.{tail}"


def certified_return(plane, code: str, period_start, period_end, cutoff=None, currency: str | None = None) -> dict:
    """The benchmark return for a certified report. Refused (409, plain words) unless the definition in force is approved."""
    res = e3_calc.benchmark_return(plane, code, period_start, period_end, cutoff, currency)
    d = res["definition"]
    if d is None:
        raise Refused(404, res["problems"][0])
    if d["approval_status"] != "approved":
        flag_policy_question(plane, code, d["benchmark_name"], d["approval_status"])
        raise Refused(409, f"The benchmark {d['benchmark_name']} is {_STATUS_WORDS.get(d['approval_status'], d['approval_status'])}, so it cannot be used in a "
                           "certified report. A question has been raised for the people who set policy.")
    return res


def comparison(plane, portfolio_id: str, code: str, period_start, period_end, cutoff=None, currency: str | None = None) -> dict:
    """{portfolio, benchmark, difference, problems, certified}: the Consume tile 'portfolio vs benchmark'. difference is None unless both returns are.
    currency defaults to the definition's reporting currency. `certified` is true only when the benchmark definition is approved and every closing value is official or revised."""
    b = e3_calc.benchmark_return(plane, code, period_start, period_end, cutoff, currency)
    if b["definition"] and b["definition"]["approval_status"] != "approved":  # refused, never worked out against an unagreed definition (a4.2)
        b = {**b, "value": None, "components": [], "problems": [_not_approved(plane, b["definition"])]}
    p = e3_calc.portfolio_return(plane, portfolio_id, period_start, period_end, cutoff, currency or (b["definition"] or {}).get("reporting_currency") or "USD")
    d = b["definition"] or {}
    diff = None if b["value"] is None or p["value"] is None else p["value"] - b["value"]
    sure = d.get("approval_status") == "approved" and set(p["statuses"]) <= {"official", "revised"}
    return {"portfolio": p, "benchmark": b, "difference": diff, "problems": p["problems"] + b["problems"], "certified": bool(sure and diff is not None)}
