"""Run 3, July step 6: Leo marks the notice fields and asks Span to draft the design pack (no hand-made model change: FIXC says Span reuses silver)."""
import json
from uc6 import Person, dump
PID = "prj-a4d01dff"
A = f"/api/v1/build/p/{PID}/architecture"
NOTICES = "src_2e265c52d311"
MARKS = [(0, "notice_kind", "text"), (2, "fund", "text"), (3, "manager_reference", "text"), (4, "investor", "text"), (5, "notice_date", "date"),
         (6, "amount", "money"), (7, "due_date", "date"), (9, "paid_in_after_call", "money")]
with Person("leo") as l:
    for n, name, fmt in MARKS:
        st, r = l.post(f"{A}/samples/{NOTICES}/mark", {"line": n, "name": name, "format": fmt})
        print("mark", n, name, st, "" if st == 200 else json.dumps(r)[:200])
    st, pk = l.post(f"{A}/pack/generate", timeout=300000)
    dump("m1_pack_v1", pk)
    print("pack", st, json.dumps(pk, default=str)[:3500].encode("ascii", "replace").decode())
    l.shot(f"/centre/build/p/{PID}/architecture/pack", "jul-06-leo-design-pack-drafted", 5000)
