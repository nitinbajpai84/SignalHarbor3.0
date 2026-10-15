"""Path K: the Office view liquidity (Consume > Office) for an as-at date, as the Office screen calls it. sh py.sh liq.py 2026-07-31 [who]"""
import json, sys
from uc6 import Person, dump
d = sys.argv[1]
with Person(sys.argv[2] if len(sys.argv) > 2 else "raj") as p:
    st, o = p.get(f"/api/v1/office/liquidity?currency=USD&as_of={d}"); dump("liq_" + d, o)
    print("status", st)
    for e in o.get("entities", []):
        b = {x["key"]: x for x in e["buckets"]}
        print(e["entity_code"], "cash", e["available_cash"], "| 30d calls", b["30"]["calls"], "after", b["30"]["cash_after_calls"], "after confirmed", b["30"]["cash_after_confirmed_calls"],
              "| 60d calls", b.get("60", {}).get("calls"), "| uncalled", e.get("uncalled") or e.get("uncalled_commitment"), "| not confirmed", len(e.get("not_confirmed") or []))
    print(json.dumps({k: v for k, v in o.items() if k != "entities"}, default=str)[:600])
