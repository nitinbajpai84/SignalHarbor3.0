import json, sys
from uc6 import Person
PID = "prj-a4d01dff"; A = f"/api/v1/build/p/{PID}/architecture"; V = int(sys.argv[1])
with Person("leo") as l:
    st, r = l.post(f"{A}/pack/submit", {}); print("submit", st, "" if st == 200 else json.dumps(r)[:300])
with Person("anita") as a:
    st, r = a.post(f"{A}/pack/approve", {"version": V, "note": "Approved after Leo's rewrite of the gold select."}); print("approve", st, "" if st == 200 else json.dumps(r)[:300])
    a.shot(f"/centre/build/p/{PID}/architecture/pack", f"{sys.argv[2]}-07-anita-pack-v{V}-approved", 5000)
with Person("leo") as l:
    st, b = l.get(f"/api/v1/build/p/{PID}/builder"); print("builder newer", b.get("newer"), "can", b.get("can"))
    st, r = l.post(f"/api/v1/build/p/{PID}/builder/pack", {}, timeout=600000); print("issue pack", st, "" if st == 200 else json.dumps(r)[:300])
    st, r = l.post(f"/api/v1/build/p/{PID}/builder/start", {}, timeout=600000); print("start", st, "" if st == 200 else json.dumps(r)[:300])
    st, b = l.get(f"/api/v1/build/p/{PID}/builder")
    rd = b.get("round") or {}
    print(json.dumps({k: v for k, v in rd.items() if k != "connections"}, default=str)[:2500].encode("ascii", "replace").decode()); print("can", b.get("can"), "needs", b.get("needs"))
