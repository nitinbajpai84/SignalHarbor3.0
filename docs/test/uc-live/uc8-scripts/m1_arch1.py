"""Month 1, architecture (Leo, data engineer, with Span): confirm the three real sources, answer Span's questions, upload the July samples.
Calls are the ones the Architecture step's buttons make (b10_routes.py)."""
from lib import *
import base64
w = W("leo"); pid = st("pid"); A = f"/api/v1/build/p/{pid}/architecture"
TRADE, ADMIN, FXPDF = "src_5072f6f91d8a", "src_b684cdbe5b1d", "src_56e8835c6345"
def call(m, p, b=None, k=None):
    s, r = w.api(m, A + p, b); print(m, p, s, json.dumps(r)[:400] if s >= 300 else ""); k and keep(k, r); return s, r
call("POST", "/systems/confirm", {"ids": [TRADE, ADMIN, FXPDF]}, "arch-confirm")
call("POST", "/questions/grain", {"value": {"label": "trade by trade, monthly by entity and portfolio", "period": "monthly", "dims": ["entity", "portfolio", "trade"]}})
call("POST", "/questions/history", {"value": []})
call("POST", "/questions/checks", {"value": [
    {"id": "chk-control-total", "kind": "control_total", "text": "The loaded administrator total equals the file's footer total (July: USD 1,408,050.00)", "tolerance": "exact"},
    {"id": "chk-key", "kind": "unique_key", "text": "external_trade_id is unique per side", "tolerance": "exact"},
    {"id": "chk-allowance", "kind": "tolerance", "text": "A break above 5,000 USD needs an owner", "tolerance": "5000 USD"}]})
call("POST", "/questions/definitions", {"value": {"K07": "Count of breaks whose absolute USD difference is above 5,000 USD; the excess is the difference minus 5,000 USD. Same figure as K05."}})
call("POST", "/questions/freshness", {"value": {"freq": "monthly", "at": "06:00", "day": "five business days after month-end", "label": "06:00, five business days after month-end"}})
call("POST", "/questions/access", {"value": {"narrower": []}})
for sid, f in ((TRADE, SRC / "2026-07/trading_export_20260706.csv"), (ADMIN, SRC / "2026-07/administrator_trade_confirmations_2026-07.xlsx")):
    call("POST", f"/samples/{sid}/table", {"name": f.name, "data": base64.b64encode(f.read_bytes()).decode()}, "arch-sample-" + sid)
s, q = call("GET", "/questions", None, "arch-questions-after")
print("still open:", [(x["id"], x["title"]) for x in q.get("open", [])])
w.close()
