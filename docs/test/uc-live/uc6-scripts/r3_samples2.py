"""Run 3 workaround (two attempts): the figure-named 'sources' North drafted need a landed sample before the builder runs.
Attempt 1 (same files) answered duplicate. Attempt 2: Leo uploads a small extract of the real file to each, and the notice PDF on Evidence."""
import base64, json
from uc6 import Person, REPO, TMP
S = REPO / "docs/demo/uc6/sources/2026-07"
adm = (S / "administrator_cash_2026-07.csv").read_text(encoding="utf-8").splitlines()
rec = (S / "notice_receipt_log.csv").read_text(encoding="utf-8")
MAP = {"available_cash_by_entity": ("sample_available_cash.csv", "\n".join(adm[:6]) + "\n"),
       "calls_due_next_30_days": ("sample_calls_due_30.csv", rec + "\n"), "calls_due_31_60_days": ("sample_calls_due_31_60.csv", rec + "\n#\n"),
       "uncalled_commitment_by_f": ("sample_uncalled.csv", "fund,commitment,called\nA,15000000,11250000\n"), "administrator_closing_ca": ("sample_admin_closing.csv", "\n".join(adm[:5]) + "\n")}
with Person("leo") as l:
    for code, (fn, text) in MAP.items():
        body = {"file": {"name": fn, "mimeType": "text/csv", "buffer": text.encode()}, "source_code": code, "sensitivity": "internal"}
        st, r = l.call("POST", "/api/v1/intake/upload", files=body)
        print(code, st, json.dumps({k: r.get(k) for k in ("file_id", "duplicate", "source_code", "state")} if isinstance(r, dict) else r)[:300])
    pdf = REPO / "docs/demo/uc6/sources/2026-08/2026-07-06_cedarpoint_fund-D_call.pdf"
    st, r = l.post("/api/v1/evidence/documents", {"filename": pdf.name, "data": base64.b64encode(pdf.read_bytes()).decode()}, timeout=300000)
    print("pdf", st, json.dumps(r, default=str)[:400])
