import json, sys
from uc6 import Person, dump
PID = "prj-a4d01dff"; B = f"/api/v1/build/p/{PID}/builder"
who = sys.argv[1]; path = sys.argv[2]; body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
with Person(who) as p:
    st, r = (p.get(B + path) if path == "" else p.post(B + path, body or {}, timeout=600000))
    dump("builder" + path.replace("/", "_"), r)
    print(st, json.dumps(r, default=str)[:3500].encode("ascii", "replace").decode())
