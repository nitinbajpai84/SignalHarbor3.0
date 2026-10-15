"""Step 0: starting state of the clean env (Grace and Mei): who am I, mode, cases, projects, liquidity at 31 Jul. Screenshots of Action and Office."""
import json
from uc6 import Person, dump
with Person("grace") as g:
    for p in ("/api/auth/me", "/api/v1/router/mode", "/api/v1/cases", "/api/v1/build/projects", "/api/v1/ops/runs",
              "/api/v1/office/liquidity?currency=USD&as_of=2026-07-31"):
        st, o = g.get(p); dump("s0" + p.replace("/", "_").replace("?", "_"), o)
        print(p, st, json.dumps(o, default=str)[:600])
with Person("mei") as m:
    m.shot("/centre/action", "jul-00-mei-action-empty")
    m.shot("/centre/consume/office", "jul-00-mei-office-start")
    print(m.text()[:1200])
