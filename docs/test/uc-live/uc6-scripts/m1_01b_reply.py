"""Month 1, step 1b: Mei answers North's open questions in the same chat box, then reads the draft intent (sow) and its sign gaps.
    sh py.sh m1_01b_reply.py "<message>" ["<message>" ...]"""
import json
import sys
from uc6 import Person, dump, BASE
with Person("mei") as p:
    pg = p.page
    st, o = p.get("/api/v1/intents/open")
    iid = o.get("id") or (o.get("recent") or [{}])[0].get("id")
    print("IID", iid)
    for m in sys.argv[1:]:
        st, c = p.get(f"/api/v1/intents/{iid}/chat")
        before = sum(1 for t in c.get("turns", []) if t.get("by") == "person")
        pg.goto(f"{BASE}/centre/intent/{iid}")
        pg.wait_for_timeout(3000)
        box = pg.locator("textarea").last
        box.fill(m)
        box.press("Enter")
        for _ in range(150):
            pg.wait_for_timeout(2000)
            st, c = p.get(f"/api/v1/intents/{iid}/chat")
            t = c.get("turns", [])
            if t and t[-1].get("by") != "person" and sum(1 for x in t if x.get("by") == "person") > before:
                break
        print("NORTH:", t[-1].get("text", "")[:700].encode("ascii", "replace").decode(), flush=True)
    st, sow = p.get(f"/api/v1/intents/{iid}/sow")
    dump("m1_sow_draft", sow)
    print("SOW", st, json.dumps({k: sow.get(k) for k in ("state", "version", "unclear", "sign_gaps", "missing", "can")}, default=str)[:1500].encode("ascii", "replace").decode())
