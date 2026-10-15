"""Workaround W1: North said it noted the result, success test and the July figure for 'Breaks above 5,000 USD allowance' but wrote none of
them. Mei fills them with the document's own edit controls (PUT /api/v1/intents/{iid}/sow, the 'edit' button) and the benchmark sheet
cell (POST /api/v1/build/{iid}/benchmarks/sheet/rows/{rid}, typing a figure in a row)."""
from lib import *
w = W("mei"); iid = st("iid")
for f, v in (("result", "One page: the five figures at the top (trades compared, matched, breaks, net break in USD, breaks above the 5,000 USD allowance), then a table of breaks with trade id, security, break type, USD difference, amount over the allowance and owner."),
             ("success", "The July 2026 figures come out as compared 4, matched 4, breaks 0, net break 0.00 USD, and every later break has an owner within five business days of month-end.")):
    s, r = w.api("PUT", f"/api/v1/intents/{iid}/sow", {"section": "template_fields", "field": f, "value": v}); print("edit", f, s, r.get("sign_block") if isinstance(r, dict) else r)
s, r = w.api("PUT", f"/api/v1/intents/{iid}/sow", {"section": "goal", "field": "why", "value": "A wrong or missing booking at the administrator flows into the trust's NAV; Raj must approve corrections before the administrator closes the month."}); print("why", s)
s, sh = w.api("GET", f"/api/v1/build/{iid}/benchmarks/sheet"); keep("bench-sheet", sh)
for row in sh.get("rows", []):
    if row.get("reported") is None:
        s, r = w.api("POST", f"/api/v1/build/{iid}/benchmarks/sheet/rows/{row['id']}", {"reported": 0, "expected": 0}); print("bench row", row["id"], row.get("kpi"), s)
s, r = w.api("GET", f"/api/v1/intents/{iid}/sow"); keep("sow-after-fill", r); print("SOW", r.get("may"), r.get("sign_block"))
w.pg.goto(st("intent_url")); w.pg.wait_for_timeout(5000); w.shot("jul-01-mei-intent-drafted-filled"); w.close()
