"""Daniel Foo signs the intent of work on the real signing page (/centre/intent/{iid}/sign): ticks 'I have read all N sections',
presses 'Sign intent'. Then 'Send to Build' if the screen offers it (else POST /api/v1/intents/{iid}/send-to-build, the same call)."""
from lib import *
import re
w = W("daniel"); iid = st("iid")
w.go(f"/centre/intent/{iid}/sow", 5000); w.shot("jul-02-daniel-intent-before-sign")
w.go(f"/centre/intent/{iid}/sign", 5000)
w.pg.get_by_role("checkbox").first.check(); w.pg.wait_for_timeout(500)
w.pg.get_by_role("button", name="Sign intent").click(); w.pg.wait_for_timeout(5000)
w.shot("jul-02-daniel-intent-signed"); print(w.text()[:1500]); print("BUTTONS", w.buttons())
s, r = w.api("GET", f"/api/v1/intents/{iid}/sow"); keep("sow-signed", r); print("state", r.get("state"), r.get("signature"))
b = w.pg.get_by_role("button", name=re.compile("Build", re.I))
if b.count():
    print("clicking", b.first.inner_text()); b.first.click(); w.pg.wait_for_timeout(5000); w.shot("jul-02-daniel-sent-to-build"); print(w.text()[:800])
else:
    s, r = w.api("POST", f"/api/v1/intents/{iid}/send-to-build", {}); keep("send-to-build", r); print("send-to-build API", s, str(r)[:800])
w.close()
