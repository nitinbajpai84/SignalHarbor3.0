"""M1-00..04: starting state as Grace (rules, cases, instruments, row counts) and the mode line."""
from uc5lib import W, j
g = W("grace")
for p in ("/api/v1/rules", "/api/v1/cases?exception_type=limit_breach", "/api/v1/centre-map/model", "/api/v1/recon/runs", "/api/v1/build/projects"):
    st, r = g.api("GET", p); print(p, st, j(r, 1500))
g.go("/centre/settings/rules"); g.shot("jul-00-grace-starting-rules")
g.go("/centre/action/cases"); g.shot("jul-00-grace-starting-cases"); print(g.text()[:800])
g.go("/centre/settings"); print(g.text()[:1500])
