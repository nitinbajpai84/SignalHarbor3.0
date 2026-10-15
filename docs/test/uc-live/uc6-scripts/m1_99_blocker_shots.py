"""Blocker evidence for July: the intake file pages (held back / quarantined), Operations > Runs, Consume > Office at 31 Jul, Map > Data model, the pack."""
from uc6 import Person
PID = "prj-f6002931"
with Person("leo") as l:
    l.shot("/centre/data/intake/80ff0576-969e-44c0-9960-84802cb495bf", "jul-90-leo-blocker-bank-file-quarantined", 4000)
    l.shot("/centre/data/intake/30e47809-813c-460a-9e85-6edb0402eab2", "jul-91-leo-blocker-admin-cash-0-rows", 4000)
    l.shot("/centre/data/intake/60af990b-8cdf-4533-b0d5-ec186ec2b65b", "jul-92-leo-blocker-commitments-held-back", 4000)
    l.shot("/centre/operations", "jul-93-leo-operations-runs-none", 4000)
    l.shot(f"/centre/build/p/{PID}/architecture/pack", "jul-94-leo-design-pack-11-open-rows", 4000)
with Person("raj") as r:
    r.shot("/centre/consume/office", "jul-95-raj-office-liquidity-cash-zero", 5000)
with Person("anita") as a:
    a.shot("/centre/map/data-model", "jul-96-anita-map-data-model-no-call-table", 5000)
