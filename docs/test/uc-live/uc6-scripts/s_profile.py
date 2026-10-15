import json, sys
from uc6 import Person, dump
FID = sys.argv[1]
with Person("leo") as l:
    st, o = l.post(f"/api/v1/intake/files/{FID}/profile", {}); dump("profile_" + FID[:8], o)
    print(st, json.dumps(o, default=str)[:1200].encode("ascii", "replace").decode())
    st, o = l.get("/api/v1/model/mappings"); print("mappings", st, json.dumps(o, default=str)[:600])
