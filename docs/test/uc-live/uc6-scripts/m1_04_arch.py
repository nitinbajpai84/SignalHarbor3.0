"""Month 1, step 4: Leo on Architecture: What I already know (Confirm the systems), The few questions (Accept all). Screenshots of both."""
import json
from uc6 import Person, dump
PID = "prj-a4d01dff"
A = f"/api/v1/build/p/{PID}/architecture"
with Person("leo") as l:
    st, s = l.get(A + "/summary"); dump("m1_arch_summary", s)
    systems = s.get("systems") or []
    for x in systems:
        print("system", x.get("id"), "|", x.get("name"), "|", x.get("status"), "|", json.dumps(x.get("arrives") or x.get("how"), default=str)[:80])
    l.shot(f"/centre/build/p/{PID}/architecture", "jul-04-leo-architecture-known", 5000)
    st, c = l.post(A + "/systems/confirm", {"ids": [x["id"] for x in systems if x.get("id")]})
    print("confirm", st)
    st, q = l.get(A + "/questions"); dump("m1_arch_questions", q)
    for x in (q.get("questions") or []):
        print("Q", x.get("id"), "|", (x.get("question") or x.get("text") or "")[:150], "| default:", json.dumps(x.get("proposal") or x.get("default"), default=str)[:200])
    st, a = l.post(A + "/questions/accept-all"); print("accept-all", st, json.dumps(a, default=str)[:300])
    l.shot(f"/centre/build/p/{PID}/architecture", "jul-04-leo-architecture-questions-accepted", 4000)
