import json, sys
from uc6 import Person
PID = "prj-a4d01dff"; S = f"/api/v1/build/p/{PID}/studio"; DID = sys.argv[1]
for who, act in (("leo", "submit"), ("anita", "approve")):
    with Person(who) as p:
        st, r = p.post(f"{S}/{DID}/{act}", {}, timeout=200000); print(who, act, st, "" if st == 200 else json.dumps(r)[:300])
