"""Month 1, step 5: Leo gives Span a sample of each source (Samples tab), lists the PDF notice lines and marks the fields."""
import base64
import json
from uc6 import Person, dump, REPO
PID = "prj-a4d01dff"
A = f"/api/v1/build/p/{PID}/architecture"
SRC = REPO / "docs/demo/uc6/sources"
TABLES = {"src_b254846149e3": SRC / "2026-07/commitments_schedule_2026-07-31.xlsx",
          "src_9d7872539afe": SRC / "2026-07/bank_cash_EG-B_2026-07.csv",
          "src_2592a1845d1d": SRC / "2026-07/administrator_cash_2026-07.csv",
          "src_142d203b3212": SRC / "2026-07/administrator_cash_2026-07.csv",  # North's duplicate of the administrator source
          "src_2f21acda5f4a": SRC / "2026-07/notice_receipt_log.csv"}
PDF = SRC / "2026-08/2026-07-06_cedarpoint_fund-D_call.pdf"  # July has no notice; the first notice of the year serves as the sample
NOTICES = "src_2e265c52d311"
with Person("leo") as l:
    out = {}
    for sid, f in TABLES.items():
        st, r = l.post(f"{A}/samples/{sid}/table", {"name": f.name, "data": base64.b64encode(f.read_bytes()).decode()})
        out[sid] = r
        print("table", sid, f.name, st, json.dumps(r, default=str)[:300].encode("ascii", "replace").decode())
    st, r = l.post(f"{A}/samples/{NOTICES}/pdf", {"name": PDF.name, "data": base64.b64encode(PDF.read_bytes()).decode()})
    print("pdf", st, json.dumps(r, default=str)[:200])
    st, lines = l.get(f"{A}/samples/{NOTICES}/lines")
    for x in lines.get("lines", []):
        print("line", x["n"], x["text"][:110].encode("ascii", "replace").decode())
    dump("m1_samples", {"tables": out, "lines": lines})
