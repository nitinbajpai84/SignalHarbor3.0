"""Run 3, July step 7: Leo settles the open pack rows and submits, Anita approves (FIXC: one approval also approves the model change and the build plan)."""
import json
from uc6 import Person, dump
PID = "prj-a4d01dff"; A = f"/api/v1/build/p/{PID}/architecture"
NOTE = {"check": "Mapped at intake from the uploaded file and approved by the head of data.",
        "derived": "Computed from silver: administrator closing cash and the commitments table, with the 30/60 day windows from the intent."}
with Person("leo") as l:
    st, pk = l.get(f"{A}/pack")
    rows = [m for m in pk["pack"]["mapping"] if m.get("needs_person") and not m.get("resolved")]
    print("open rows", len(rows))
    for m in rows:
        st, r = l.call("PUT", f"{A}/pack/edit", {"section": "mapping", "key": m["id"], "changes": {"resolve": NOTE[m["kind"]]}, "note": "Leo settles this row."})
        print("resolve", m["id"][:50], st, "" if st == 200 else json.dumps(r)[:200])
    st, r = l.post(f"{A}/pack/submit", {}); print("submit", st, json.dumps(r, default=str)[:500].encode("ascii","replace").decode())
    l.shot(f"/centre/build/p/{PID}/architecture/pack", "jul-07-leo-pack-submitted", 5000)
with Person("anita") as a:
    st, r = a.post(f"{A}/pack/approve", {"version": 1, "note": "Approved for UC6 run 3."}); print("approve", st, json.dumps(r, default=str)[:1500].encode("ascii","replace").decode())
    a.shot(f"/centre/build/p/{PID}/architecture/pack", "jul-07-anita-pack-approved", 5000)
    st, p = a.get(f"{A}/pack"); print("can", p.get("can"), "plan_version", p.get("plan_version"), "versions", [(v["version"], v["state"], v.get("plan_version")) for v in p["versions"]])
