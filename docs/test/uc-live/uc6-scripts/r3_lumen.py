import json
from uc6 import Person, dump
PID = "prj-a4d01dff"; S = f"/api/v1/build/p/{PID}/studio"
with Person("leo") as m:
    st, r = m.post(S + "/starter", {}, timeout=300000); print("starter", st, json.dumps(r, default=str)[:1200].encode("ascii","replace").decode())
    dump("lumen_starter", r)
