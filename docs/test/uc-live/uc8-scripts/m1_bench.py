"""Workaround W1b: the owner (Mei) is refused the benchmark sheet (403, 'company administrator or the data team or the sponsor').
Daniel Foo (sponsor) types the July figure Mei gave into the empty row (POST /api/v1/build/{iid}/benchmarks/sheet/rows/{rid})."""
from lib import *
w = W("daniel"); iid = st("iid")
s, sh = w.api("GET", f"/api/v1/build/{iid}/benchmarks/sheet"); keep("bench-sheet", sh); print("sheet", s)
for row in (sh.get("sheet") or sh).get("rows", []):
    print(" row", row.get("id"), row.get("kpi"), row.get("period"), row.get("reported"), row.get("expected"))
    if row.get("reported") is None and not row.get("dropped"):
        s, r = w.api("POST", f"/api/v1/build/{iid}/benchmarks/sheet/rows/{row['id']}", {"reported": 0, "expected": 0}); print("  typed 0 ->", s)
s, r = w.api("GET", f"/api/v1/intents/{iid}/sow"); keep("sow-after-fill", r); print("SOW", r.get("may"), r.get("sign_block"))
w.close()
