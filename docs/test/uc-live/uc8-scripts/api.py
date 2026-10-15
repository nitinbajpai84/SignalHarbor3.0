"""Ad-hoc API call as one person: python api.py <who> <METHOD> <path> [json-body] [keep-name]"""
from lib import *
w = W(sys.argv[1]); body = json.loads(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
s, r = w.api(sys.argv[2], sys.argv[3], body)
if len(sys.argv) > 5: keep(sys.argv[5], {"req": sys.argv[2:5], "status": s, "resp": r})
print(s, json.dumps(r, default=str)[:int(os.environ.get("N", "3000"))]); w.close()
