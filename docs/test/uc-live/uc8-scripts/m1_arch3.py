"""Leo marks the FX confirmation fields, then asks Span to draft the design pack (POST .../pack/generate, a model call)."""
from lib import *
w = W("leo"); pid = st("pid"); A = f"/api/v1/build/p/{pid}/architecture"; sid = "src_56e8835c6345"
for line, name, fmt in ((1, "confirmation_ref", "text"), (5, "trade_date", "date"), (6, "value_date", "date"), (7, "sell_currency", "text"),
                        (8, "sell_amount", "number"), (9, "buy_currency", "text"), (10, "buy_amount", "number"), (11, "contract_rate", "number")):
    s, r = w.api("POST", A + f"/samples/{sid}/mark", {"line": line, "name": name, "format": fmt}); print("mark", name, s, "" if s < 300 else r)
t = time.time(); s, r = w.api("POST", A + "/pack/generate", {}); keep("pack-v1", r); print("generate", s, round(time.time() - t), "s", json.dumps(r)[:3000])
w.go(f"/centre/build/p/{pid}/architecture/pack", 6000); w.shot("jul-05-leo-design-pack-drafted"); print(w.text()[:3000]); w.close()
