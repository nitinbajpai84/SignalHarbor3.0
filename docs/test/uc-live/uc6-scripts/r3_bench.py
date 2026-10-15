import json, sys
from uc6 import Person
PID = "prj-a4d01dff"
with Person("leo") as l:
    st, r = l.post(f"/api/v1/build/p/{PID}/builder/benchmark", {"name": sys.argv[1], "text": open(sys.argv[2], encoding="utf-8").read()}, timeout=300000)
    print("benchmark", st, json.dumps(r, default=str)[:3000].encode("ascii", "replace").decode())
