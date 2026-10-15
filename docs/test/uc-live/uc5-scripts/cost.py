"""Model spend so far in the UC5 run-2 env (reads the product's own cost log)."""
import json
from pathlib import Path
from uc5lib import ROOT
rows = [json.loads(l) for l in (ROOT / ".sh-tmp/testenv/uc5-run2/data/evergreen/context/model_costs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
print("calls", len(rows), "usd", round(sum(r.get("cost_usd") or 0 for r in rows), 5), "modes", sorted({r.get("mode") for r in rows}), "models", sorted({r.get("model") for r in rows}))
