import json
from uc6 import Person
with Person("leo") as a:
    st, maps = a.get("/api/v1/model/mappings")
    for m in maps:
        st, full = a.get(f"/api/v1/model/mappings/{m['id']}")
        print("==", m["id"], m.get("state"), full.get("example_file"), "fixed", full.get("fixed"), "keys", [k for k in full if k not in ("columns",)][:14])
        for c in full.get("columns", []):
            print("   ", c.get("source"), "->", (c.get("target_table") or "ignore") + "." + (c.get("target_field") or ""), c.get("transform") or "")
