"""Print the last turns, pending proposals and stage of an intent (as Mei). Usage: chat_state.py IID"""
import sys, json
from uc5lib import W
w = W(sys.argv[2] if len(sys.argv) > 2 else "mei"); s, b = w.api("GET", f"/api/v1/intents/{sys.argv[1]}/chat")
for t in b["turns"][-4:]: print(t["by"], "|", t["text"][:900].encode("ascii", "replace").decode())
print("keys", sorted(b.keys()))
print("stage", b.get("stage"), "needs_done", b.get("needs_done"), "asked", b.get("asked"))
print("pending", [p.get("id") for p in (b.get("proposals") or {}).get("pending", [])])
print("sow", json.dumps(b.get("sow"), ensure_ascii=True)[:1500])
