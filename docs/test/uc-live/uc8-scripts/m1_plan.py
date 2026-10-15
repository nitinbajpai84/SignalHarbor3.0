"""Month 1: the build plan drawn from the pack must also be proposed (Leo) and approved (Anita) before the builder starts (b11_builder.pack_of
reads the newest APPROVED plan). Then Leo starts the builder on a copy (POST .../builder/start)."""
from lib import *
pid = st("pid"); P = f"/api/v1/build/p/{pid}"
l = W("leo"); s, r = l.api("POST", P + "/plan/propose", {}); keep("plan-propose", r); print("propose", s, json.dumps(r)[:300] if s >= 300 else (r.get("version"), r.get("state")))
l.close()
a = W("anita"); s, r = a.api("POST", P + "/plan/approve", {"note": "Approved with the July design pack."}); keep("plan-approve", r); print("approve", s, json.dumps(r)[:300] if s >= 300 else (r.get("version"), r.get("state"))); a.close()
l = W("leo"); t = time.time(); s, r = l.api("POST", P + "/builder/start", {}); keep("builder-start", r); print("start", s, round(time.time() - t), "s", json.dumps(r)[:2500])
l.go(f"/centre/build/p/{pid}/pipelines", 8000); l.shot("jul-09-leo-builder-on-copy"); print(l.text()[600:3500]); l.close()
