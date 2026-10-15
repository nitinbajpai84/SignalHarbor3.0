import json, sys
from uc6 import Person
PID = "prj-a4d01dff"; S = f"/api/v1/build/p/{PID}/studio"; DID = sys.argv[1]
with Person("leo") as l:
    st, r = l.post(f"{S}/{DID}/ask", {"text": sys.argv[2]}, timeout=300000)
    print(st, json.dumps({k: v for k, v in r.items() if k != "dashboard"}, default=str)[:300])
    for p in r.get("proposals", []):
        t = p.get("tile") or p
        st, a = l.post(f"{S}/{DID}/tiles/{t['id']}/accept", {}); print("accept", st)
        st, d = l.get(f"{S}/{DID}/tiles/{t['id']}/data"); print(json.dumps({k: d.get(k) for k in ("columns", "rows")}, default=str)[:900])
