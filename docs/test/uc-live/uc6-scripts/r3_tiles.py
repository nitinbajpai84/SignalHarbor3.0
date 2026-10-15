import json, sys
from uc6 import Person, dump
PID = "prj-a4d01dff"; S = f"/api/v1/build/p/{PID}/studio"; DID = sys.argv[1]; tag = sys.argv[2]
with Person("leo") as l:
    st, d = l.get(f"{S}/{DID}")
    for it in d["layout"]["items"]:
        if it.get("tile"):
            st, t = l.get(f"{S}/{DID}/tiles/{it['tile']}/data")
            print(it["title"], "|", [k for k in t if k != "tile"], json.dumps(t.get("rows"), default=str)[:400])
    l.shot(f"/centre/build/p/{PID}/lumen", f"{tag}-08-leo-lumen-starter", 5000)
