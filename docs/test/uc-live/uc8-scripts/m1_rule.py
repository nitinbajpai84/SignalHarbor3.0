"""Month 1, rule: the trade check before any tolerance rule (P7 evidence), then Anita proposes cash_tolerance 5,000 USD and Raj approves."""
from lib import *
l = W("leo"); s, r = l.api("POST", "/api/v1/recon/trade_vs_admin/run", {"as_of_date": "2026-07-31"}); keep("jul-recon-before-rule", r); print("check before rule", s, json.dumps(r)[:400]); l.close()
a = W("anita"); s, r = a.api("GET", "/api/v1/rules"); keep("rules-start", r)
print("rules now:", [(x.get("rule_type"), x.get("state") or x.get("status")) for x in (r if isinstance(r, list) else r.get("rules", r.get("items", [])))][:20])
body = {"definition_text": "Trades from the administrator and the trading export agree within 5,000 USD for trade checks on EG-TRUST.",
        "parameters": {"abs_amount": 5000, "currency": "USD"}, "effective_from": "2026-07-01", "rule_type": "cash_tolerance"}
s, r = a.api("POST", "/api/v1/rules/cash_tolerance", body); keep("rule-propose", r); print("propose", s, json.dumps(r)[:500]); a.close()
vid = (r.get("version") or {}).get("id") or r.get("vid") or r.get("id") if isinstance(r, dict) else None
if vid:
    st("rule_vid", vid); j = W("raj"); s, r = j.api("POST", f"/api/v1/rules/versions/{vid}/approve", {}); keep("rule-approve", r); print("approve", s, json.dumps(r)[:400])
    j.go("/centre/settings/rules", 4000); j.shot("jul-07-raj-rule-approved"); j.close()
