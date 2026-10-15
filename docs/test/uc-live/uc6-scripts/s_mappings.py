import json
from uc6 import Person, dump
with Person("anita") as a:
    st, o = a.get("/api/v1/model/mappings"); dump("mappings", o)
    rows = o.get("mappings", o) if isinstance(o, dict) else o
    print(st, type(rows).__name__, len(rows) if hasattr(rows, "__len__") else "")
    for m in (rows if isinstance(rows, list) else [])[:20]:
        print(json.dumps({k: m.get(k) for k in ("id", "status", "state", "file_name", "source_code", "sheet", "proposed_by", "file_id")}, default=str)[:300])
