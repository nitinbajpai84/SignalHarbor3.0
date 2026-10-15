"""Month 1, step 3 (workaround): the hand-over to Leo. Mei (owner) lacks the seat, Daniel (sponsor) is not the project owner; Grace (admin) tries."""
import json
from uc6 import Person
PID = "prj-f6002931"
with Person("grace") as g:
    st, out = g.post(f"/api/v1/projects/{PID}/handover", {"to": "Leo Park", "due": "2026-10-23",  # 7 Aug refused as passed: hand-over checks the real clock, not the company clock
                     "message": "Leo, July first. The Excel and CSVs come by upload; the notices are PDFs. Check against Mei's July figures."})
    print("handover by Grace", st, json.dumps(out, default=str)[:400])
with Person("leo") as l:
    l.shot("/centre/action", "jul-03-leo-action-handover")
    st, s = l.get(f"/api/v1/build/p/{PID}/architecture/summary")
    print("leo summary", st, json.dumps(s, default=str)[:1500].encode("ascii", "replace").decode())
