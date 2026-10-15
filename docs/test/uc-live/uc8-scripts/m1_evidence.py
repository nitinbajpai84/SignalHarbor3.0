"""Month 1 evidence at the stop point: silver transactions row count (Map > Data model API), the July trade check (Grace, the only
person allowed to run it), Operations runs, Action items, the Map page."""
from lib import *
g = W("grace")
s, r = g.api("GET", "/api/v1/centre-map/model"); keep("map-model", r)
txt = json.dumps(r); i = txt.find('"transactions"'); print("map model", s, txt[max(0, i - 200): i + 400] if i >= 0 else txt[:600])
s, r = g.api("POST", "/api/v1/recon/trade_vs_admin/run", {"as_of_date": "2026-07-31"}); keep("jul-recon-after-load", r); print("trade check 31 Jul", s, json.dumps(r)[:700])
s, r = g.api("GET", "/api/v1/ops/runs"); keep("ops-runs", r); print("ops runs", s, json.dumps(r)[:900])
g.go("/centre/action/reconciliations", 6000); g.shot("jul-10-grace-trade-check-empty"); print(g.text()[300:1500])
g.go("/centre/map", 6000); g.shot("jul-11-grace-map"); g.go("/centre/operations", 6000); g.shot("jul-12-grace-operations-runs"); print(g.text()[300:1500]); g.close()
l = W("leo"); l.go("/centre/action", 6000); l.shot("jul-13-leo-action-items"); print(l.text()[300:1800]); l.close()
