import json
from uc6 import Person
with Person("leo") as l:
    st, r = l.put("/api/v1/model/mappings/map-9bd5fea6ddcd", {"columns": [], "fixed": {"portfolios.portfolio_code": "EG-B-OPS"}}); print("fixed", st, json.dumps(r)[:200])
    st, ld = l.post("/api/v1/intake/files/014ce670-f3f3-47a4-bbcd-b7df16813295/load", {}, timeout=300000)
    print(st, json.dumps(ld.get("last_load"), default=str)[:700])
