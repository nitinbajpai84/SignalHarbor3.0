"""Mei presses Accept on every pending North change (POST /api/v1/intents/{iid}/proposals/{pid}/accept, the Accept button)."""
from lib import *
w = W("mei"); iid = st("iid"); s, r = w.api("GET", f"/api/v1/intents/{iid}/proposals"); keep("proposals", r)
items = r.get("pending") or []; print("recent", [(p["id"], p["status"], p["summary"]) for p in r.get("recent") or []])
for p in items:
    if p.get("state", p.get("status")) in ("pending", "open", None):
        print("accept", p.get("id"), p.get("summary") or p.get("title"), w.api("POST", f"/api/v1/intents/{iid}/proposals/{p['id']}/accept", {})[0])
    else: print("skip", p.get("id"), p.get("state", p.get("status")))
w.close()
