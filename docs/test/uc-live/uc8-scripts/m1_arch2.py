"""Leo uploads a Harbour Bank FX confirmation as the PDF sample (July has none; the Sep FXF-2026-001 confirmation is the bank's layout) and lists its lines."""
from lib import *
import base64
w = W("leo"); pid = st("pid"); A = f"/api/v1/build/p/{pid}/architecture"; sid = "src_56e8835c6345"
f = SRC / "2026-09/otc_confirms/FXF-2026-001_confirmation_2026-09-15.pdf"
s, r = w.api("POST", A + f"/samples/{sid}/pdf", {"name": f.name, "data": base64.b64encode(f.read_bytes()).decode()}); print("pdf", s, json.dumps(r)[:300])
s, r = w.api("GET", A + f"/samples/{sid}/lines"); keep("arch-pdf-lines", r)
for i, l in enumerate(r.get("lines", [])[:60]): print(i, json.dumps(l)[:160])
w.close()
