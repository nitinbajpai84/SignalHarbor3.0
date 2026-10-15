from lib import *
w = W(sys.argv[1]); s, r = w.api("GET", f"/api/v1/intents/{st('iid')}/sow"); keep("sow-" + sys.argv[1], r)
print(s, r.get("state"), r.get("version"), r.get("may"), r.get("sign_block")) if isinstance(r, dict) else print(s, r); w.close()
