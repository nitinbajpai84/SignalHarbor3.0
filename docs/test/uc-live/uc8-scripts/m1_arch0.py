"""Month 1, architecture: Leo opens the project's Architecture step; read Span's summary and questions."""
from lib import *
who = sys.argv[1] if len(sys.argv) > 1 else "leo"
w = W(who); pid = st("pid")
w.go(f"/centre/build/p/{pid}/architecture", 8000); w.shot(f"jul-04-{who}-architecture-open"); print(w.text()[:2500]); print("BUTTONS", w.buttons()[:40])
for p in ("summary", "questions", "pack"):
    s, r = w.api("GET", f"/api/v1/build/p/{pid}/architecture/{p}"); keep("arch-" + p, r); print(p, s, json.dumps(r)[:1800])
w.close()
