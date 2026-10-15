import json, sys
from uc6 import Person
with Person("leo") as l:
    st, r = l.get("/api/v1/ops/runs")
    for x in r["runs"][:int(sys.argv[1]) if len(sys.argv) > 1 else 40]:
        print(x["run_id"], x["kind"], x["mode"], x["status"], x["who"], x["started"][:19], "pack", x.get("pack_version"))
