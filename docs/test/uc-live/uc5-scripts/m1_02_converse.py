"""M1-05 cont.: Mei answers North turn by turn (POST /api/v1/intents/{iid}/chat {text}, the call the chat box's Send makes) and accepts
each set of drafted changes (POST /api/v1/intents/{iid}/proposals/{pid}/accept, the Accept button). Answers are fixed sentences chosen
by the topic North asks about (`asked`) or by keywords in North's question. Usage: m1_02_converse.py IID [max_turns]"""
import sys
from uc5lib import W
IID, N = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10
A = [
    (("why", "matters"), "Because a breach found late costs us: in September a single holding went over the new 5% cap and we only saw it two weeks later."),
    (("access", "open to", "restricted", "see this"), "Only the people we name: Sofia Reyes, Mei Chen, Daniel Foo, and the data team Anita Rao and Leo Park."),
    (("kpi", "formula", "calculate", "work out", "figure"), "Exposure = value of the item, or the sum of the bucket, divided by the portfolio's investment holdings in USD (cash excluded), times 100, in percent. Funds use the latest known manager statement value; securities the administrator month-end value. Headroom = maximum minus exposure, in percentage points (not basis points). Cause: stale data if any input is older than 90 days at the month end or not yet verified, otherwise real breach."),
    (("manual", "by hand", "adjust", "change by hand"), "Nothing is changed by hand. Instruments with no asset class are not forced into a bucket; they are listed as questions."),
    (("process", "today", "step by step", "how is it done"), "Today Mei copies the administrator workbook into a spreadsheet, Sofia checks each limit by hand against the signed limits sheet and emails Daniel the breaches. It takes two days."),
    (("document", "email"), "No documents or emails: only the two workbooks."),
    (("input", "source", "where the data", "owner", "who owns"), "The administrator positions workbook comes from the fund administrator; Leo Park uploads it. The signed limits workbook is owned by Sofia Reyes and signed by Daniel Foo. Both arrive monthly and are uploaded by hand."),
    (("look like", "output", "result", "layout"), "One table per month: limit, portfolio, item, value, denominator, exposure %, maximum %, headroom in points, result, stale input, cause; plus a list of unclassified instruments."),
    (("reader", "decide"), "Sofia Reyes decides whether each breach is real or stale; Raj Patel approves any trade that cures a breach; Daniel Foo signs the limits."),
    (("frequency", "when", "often"), "Monthly, ready by the 5th business day after month end."),
    (("retain", "keep", "approves a change", "governance"), "Keep seven years. Daniel Foo approves any change to a limit."),
    (("success", "worked", "know it"), "It worked when the July figures match our manual July check: Harborview 5.73%, listed equity 80.04%, Cedarpoint 57.38% stale breach, hedge funds 54.49%."),
    (("benchmark", "last period", "reported"), "Last period (July 2026 manual check): Harborview 5.73% inside 6%; listed equity 80.04%; Cedarpoint 57.38% breach, stale; hedge funds 54.49%."),
    (("industry", "usually"), "Yes, as the industry usually defines it, with our basis: cash excluded, latest known fund values."),
    (("unclear", "settle", "open point"), "Open: which single-name cap applies before September (6% in the signed v1 workbook vs 5% in the register). Daniel Foo settles it."),
]
w = W("mei")


def accept_all(b):
    for p in (b.get("proposals") or {}).get("pending", []):
        s, _ = w.api("POST", f"/api/v1/intents/{IID}/proposals/{p['id']}/accept", {}); print("  accept", p["id"], s)


s, b = w.api("GET", f"/api/v1/intents/{IID}/chat")
for k in range(N):
    accept_all(b)
    north = [t for t in b["turns"] if t["by"] == "north"][-1]["text"]
    q = f"{b.get('asked') or ''} | {north}".lower()
    print(f"--- NORTH {k} (asked={b.get('asked')}, done={b.get('needs_done')}):", north[:500].encode("ascii", "replace").decode())
    if b.get("stage") not in (None, "talking"):
        print("stage", b.get("stage")); break
    ans = next((a for keys, a in A if any(x in q for x in keys)), "Yes, that is right. Please finish the intent so Daniel Foo can sign it.")
    print("MEI:", ans)
    s, b = w.api("POST", f"/api/v1/intents/{IID}/chat", {"text": ans})
    if s != 200: print("ERR", s, str(b)[:500]); break
accept_all(b)
s, b = w.api("GET", f"/api/v1/intents/{IID}/chat")
print("END stage", b.get("stage"), "state", b.get("state"), "done", b.get("needs_done"), "asked", b.get("asked"))
print("LAST NORTH:", [t for t in b["turns"] if t["by"] == "north"][-1]["text"][:800].encode("ascii", "replace").decode())
