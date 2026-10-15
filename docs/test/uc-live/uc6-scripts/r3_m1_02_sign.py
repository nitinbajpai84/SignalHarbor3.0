"""Run 3, July step 2: Mei accepts North's last drafts, Daniel signs (sign page, confirm box + Sign), Mei sends to Build."""
import json, sys
from uc6 import Person, dump
IID = "ini-097ec18a7f77bc6be9cdf63cf23c8aeb"
with Person("mei") as m:
    st, props = m.get(f"/api/v1/intents/{IID}/proposals")
    for pr in props.get("pending", []):
        print("accept proposal", pr["id"], m.post(f"/api/v1/intents/{IID}/proposals/{pr['id']}/accept")[0])
    st, sow = m.get(f"/api/v1/intents/{IID}/sow")
    print("steps", len(sow["process"]["steps"]), "handovers", len(sow["process"]["handovers"]))
    print("kpis", [(k["name"], k["unit"]) for k in sow["kpis"]])
    print("sign_block", sow.get("sign_block"), "may", sow.get("may"))
    dump("r3_sow_before_sign", sow)
    m.shot(f"/centre/intent/{IID}/sow", "jul-01-mei-intent-ready", 4000)
if "--sign" in sys.argv:
    with Person("daniel") as d:
        d.shot("/centre/action", "jul-02-daniel-action-intent-to-sign")
        d.shot(f"/centre/intent/{IID}/sign", "jul-02-daniel-sign-page", 4000)
        st, sow = d.get(f"/api/v1/intents/{IID}/sow")
        st, out = d.post(f"/api/v1/intents/{IID}/sow/sign", {"confirm": True, "version": sow["version"]})
        print("sign", st, json.dumps(out, default=str)[:500])
        d.shot(f"/centre/intent/{IID}/sow", "jul-02-daniel-intent-signed", 4000)
