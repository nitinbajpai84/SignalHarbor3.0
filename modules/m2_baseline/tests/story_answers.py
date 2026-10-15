"""The family-office demo story's owner answers (packs/family_office/1/demo_story/12_owner_answers_example.md) written as the
row-shaped answers the questionnaire now takes: one row per system or file, hops with a team and a step number. Synthetic and
illustrative. Built through clean_answers, so the fixture is also a check that the form's own shape is accepted."""
from modules.m2_baseline.domain.questionnaire import clean_answers, load_questionnaire, with_blanks

Q = load_questionnaire()
STATED = "stated"


def row(name, kind, structure, lands, owner, connection, frequency, sla, tables, fields="", read_out="", personal="no"):
    return {"name": name, "kind": kind, "structure": structure, "lands": lands, "owner": owner, "connection": connection,
            "frequency": frequency, "sla": sla, "tables": tables, "fields": fields, "read_out": read_out, "personal": personal}


NORTHGATE = "Northgate custodian daily file"
BLUEWATER = "Bluewater administrator NAV portal"
MAILBOX = "Managers' statements mailbox"
WORKBOOK = "Performance workbook"
VENDOR = "Market data vendor API"
INDEX = "Index provider API"
PAY = "Pay workbook"


def answer(i, owner, kpi, **given):
    got = clean_answers(Q, {k: {"value": v, "mark": STATED} if not isinstance(v, tuple) else {"value": v[0], "mark": v[1]} for k, v in given.items()},
                        owner, "the answer link")
    return with_blanks({"id": i, "request_id": "r1", "meeting": None, "owner_name": owner, "kpi_id": kpi, **got}, Q)


def hop(who, team, what, order, **more):
    return {"who": who, "team": team, "what": what, "order": order, **more}


def answers():
    return [
        answer("a1", "Arjun Rao", "K01", tracked_today="partly", sources=[
            row(NORTHGATE, "file_drop", "structured", "Finance share", "Arjun Rao", "file_drop", "daily", "by 12:00 on working days",
                "NGC_Statement CSV", "cash_balance, transaction_date", personal="not_sure")]),
        answer("a2", "Arjun Rao", "K12", tracked_today="partly", sources=[
            row(BLUEWATER, "portal", "structured", "Bluewater client file share", "Arjun Rao", "download", "monthly", "working day 8 after month-end",
                "NAV report", "valuation_date, valuation_basis")]),
        answer("a3", "Sara Lim", "K04", tracked_today="tracked_now", sources=[
            row(MAILBOX, "email", "unstructured", "capital-calls mailbox", "Sara Lim", "email_forward", "ad_hoc", "no fixed time",
                "Capital call notices", read_out="Capital call notices: due date, Capital call notices: amount, Capital call notices: fund"),
            row("northgate  custodian DAILY file", "file_drop", "structured", "", "", "file_drop", "daily", "around 16:00", "")]),
        answer("a4", "Tom Ng", "K15", tracked_today="partly", sources=[
            row(WORKBOOK, "excel", "structured", "Investments share", "Tom Ng", "manual_entry", "quarterly", "",
                "Fund returns, Benchmark levels", "period_return, benchmark_return, Benchmark levels: index_level"),
            row(VENDOR, "api", "structured", "", "", "download", "daily", {"value": None, "mark": "unknown"}, "Index levels", "index_level, price_date"),
            row(INDEX, "api", "structured", "", "", "download", "daily", "", "S&P 500 levels, MSCI World levels"),
            row(MAILBOX, "email", "unstructured", "", "Sara Lim", "email_forward", "", "",
                "Manager statements", read_out="Manager statements: period return, Manager statements: net asset value")],
               upstream=[hop("Market data vendor", "Market data vendor API", "Publishes index levels and prices after market close", 1),
                         hop("Northgate Custody", "Custodian", "Sends the positions file", 2)],
               in_between=[hop("Tom Ng", "Investments", "Pastes levels into Performance_Workbook.xlsx and works out period return", 4, manual=True),
                           {"who": "Tom Ng", "team": "investments team", "what": "Subtracts the benchmark, picked from memory", "order": 5, "manual": True}],
               downstream=[hop("Mei Tan", "Investments", "Reads the committee note", 7)]),
        answer("a5", "Mei Tan", "K15", upstream=[hop("Sara Lim", "Operations", "Files the managers' statements", 3)],
               in_between=[hop("Wei", "Risk", "Works out exposure by issuer and currency", 6)],
               downstream=[hop("Lina Ho", "HR", "Takes the figure for the bonus round", 8)]),
        answer("a6", "Lina Ho", "K18", tracked_today="not_tracked", sources=[
            row(PAY, "excel", "structured", "HR share", "Lina Ho", "email_forward", "quarterly", "four to six weeks after quarter-end",
                "Pay review", "salary_band, bonus_amount", personal="yes")]),
    ]


def kpis():
    def p(v, who="the charter"):
        return {"value": v, "mark": "stated", "by": who, "from": "kpis.json", "at": "2026-10-01T00:00:00+00:00"}
    ok = {"personal": "no", "sensitive": False, "may_see": []}
    names = {"K01": "Minimum six-month funding headroom", "K04": "Known obligations due", "K12": "Stale-valuation share",
             "K15": "Manager performance versus benchmark", "K18": "Compensation inputs reconciled"}
    return [{"id": k, "name": n, "problem_ids": [], "priority": "Must", "definition": p("a definition"),
             "owners": {"business": p("Mei Tan"), "data": p("Wei Chen" if k == "K15" else "Arjun Rao"), "process": p("Sara Lim")},
             "governance": {"personal": "yes", "sensitive": True, "may_see": ["Lina Ho", "Mei Tan"]} if k == "K18" else ok,
             "tracking": p("partly")} for k, n in names.items()]
