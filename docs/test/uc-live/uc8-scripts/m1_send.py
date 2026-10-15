"""Mei presses the North page's 'Send to Build' control after Daniel signed (POST /api/v1/intents/{iid}/send-to-build)."""
from lib import *
import re
w = W("mei"); iid = st("iid"); w.pg.goto(st("intent_url")); w.pg.wait_for_timeout(6000)
b = w.pg.get_by_role("button", name=re.compile("to Build", re.I))
print("buttons with Build:", [x for x in w.buttons() if "uild" in x])
if b.count():
    b.first.click(); w.pg.wait_for_timeout(6000); w.shot("jul-03-mei-sent-to-build")
else:
    s, r = w.api("POST", f"/api/v1/intents/{iid}/send-to-build", {}); keep("send-to-build", r); print("API", s, str(r)[:600])
    w.pg.reload(); w.pg.wait_for_timeout(5000); w.shot("jul-03-mei-sent-to-build")
s, r = w.api("GET", f"/api/v1/intents/{iid}/project"); print("project", r.get("id"), r.get("stage"), r.get("people")); st("pid", r.get("id")); w.close()
