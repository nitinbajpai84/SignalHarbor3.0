"""Run 3, July step 3: Mei sends the signed intent to Build and hands the project to Leo (FIXE1: owner may; FIXE2: due date checked on the cycle date)."""
import json
from uc6 import Person, dump
IID = "ini-097ec18a7f77bc6be9cdf63cf23c8aeb"
with Person("mei") as m:
    st, out = m.post(f"/api/v1/intents/{IID}/send-to-build"); print("send-to-build", st, json.dumps(out)[:300])
    st, pr = m.get(f"/api/v1/intents/{IID}/project")
    pid = (pr.get("project") or pr).get("id"); print("project", st, pid)
    dump("m1_project", {"pid": pid, "iid": IID})
    st, out = m.post(f"/api/v1/projects/{pid}/handover", {"to": "Leo Park", "due": "2026-08-07",
        "message": "Leo, July first. The Excel and CSVs come by upload; the notices are PDFs. Check against my July figures."})
    print("handover by Mei", st, json.dumps(out, default=str)[:400])
if st != 200:
    with Person("daniel") as d:
        st, out = d.post(f"/api/v1/projects/{pid}/handover", {"to": "Leo Park", "due": "2026-08-07", "message": "Leo, July first."})
        print("handover by Daniel", st, json.dumps(out, default=str)[:400])
with Person("leo") as l:
    l.shot("/centre/action", "jul-03-leo-action-handover")
    st, s = l.get(f"/api/v1/build/p/{pid}/architecture/summary"); dump("m1_arch_summary", s)
    print("leo summary", st, json.dumps(s, default=str)[:1200].encode("ascii", "replace").decode())
