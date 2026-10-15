"""Harbor 3.0 documents (v3_docs): an email or a note dropped into a data build goes to the 2.0 document intake, never table intake. A value it
states loads only after the person confirms the quoted line (e2_extract.confirm: the valuation that supersedes the earlier one); a document
with no value, or one the person keeps as context, is "read as context". A letter PDF is context, not a new statement layout.
Real 2.0 routes on a seeded synthetic office (tools/seed_evergreen); the files are the synthetic 10uc fixtures."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_docs as D  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_pdf as V  # noqa: E402
from sh_platform.v1 import wh  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

FIX = ROOT / "tests" / "v1" / "fixtures" / "10uc"
EML = "04_revision_notice_A_2026-09-30_amended.eml"
NOTE = "04_kestrel_ridge_onsite_2026-06-12.md"
LETTERS = ["kestrel_ridge_q3_2026_newsletter.pdf", "northgate_mid_year_letter_2026.pdf"]


def blob(name: str) -> bytes:
    return next(FIX.glob(f"*/{name}")).read_bytes()


@pytest.fixture()
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    monkeypatch.setattr("sh_platform.v1.doc_index._slow", lambda path: False)
    wh.reset_cache()
    data = tmp_path / "data"
    data.mkdir()
    EG.seed(data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    plane = PlaneStore(str(data)).plane_for("evergreen")
    acct = app.state.account_store.get_by_email(f"anita.rao.{plane.company_id}@example.test")
    return app, plane, acct


def ctx(office, files: list[str]):
    app, plane, acct = office
    th = {"id": "t-docs", "title": "Docs", "created": H.now(), "stage": "working", "events": [], "steps": [], "asked": 0,
          "started_by": "Raj Patel", "iid": "ini-test", "intake": {}}
    H.save(plane, th)
    fs = H.read_files(plane)
    for n in files:
        H.drop(plane, n, blob(n))
        fs.append({"name": n, "arrived_at": H.now(), "status": "recognised", "source": "Manager statements", "thread": th["id"]})
    H._fp(plane).write_text(json.dumps(fs), encoding="utf-8")
    return H.Ctx(app, plane, th, acct["account_id"])


def fund_a(plane) -> list[tuple]:
    with wh.connect(plane, read_only=True) as con:
        return con.execute("select v.id, v.value_amount, v.approval_status, v.supersedes_valuation_id from valuation_observations v join instruments i"
                           " on i.id = v.instrument_id where i.canonical_name = 'Evergreen Growth I' and v.valuation_date = '2026-09-30'"
                           " order by v.recorded_at").fetchall()


def test_figure_lines_keep_paragraph_line_and_quote():
    figs = D.figures_of(EML, blob(EML))
    assert [(f["label"], f["value"]) for f in figs] == [("Previous (estimate)", "USD 10,000,000"), ("Amended", "USD 10,180,000"), ("Change", "USD 180,000")]
    am = figs[1]
    assert am["quote"] == "Amended: USD 10,180,000" and am["amount"] == "10180000" and am["currency"] == "USD" and am["where"].startswith("paragraph ")
    assert D.figures_of(NOTE, blob(NOTE)) == []  # prose figures are not offered; the note is context
    assert D.is_doc(EML) and D.is_doc(NOTE) and D.is_doc("x.docx") and not D.is_doc("x.csv")


def test_email_value_loads_only_after_the_person_confirms_the_quoted_line(office):
    x = ctx(office, [EML])
    x.client("anita")  # the seats exist
    before = fund_a(x.plane)
    D.intake(x)
    d = x.th["docs"][EML]
    assert x.th["intake"][EML].startswith("doc:") and d["status"] == "asked" and d["fund"] == "Evergreen Growth I"
    assert fund_a(x.plane) == before  # read, not loaded: nothing reaches the warehouse before a person confirms
    q = D.questions(x)[0]
    assert q["id"] == f"doc:{EML}" and "Evergreen Growth I" in q["text"]
    assert q["assumed"].startswith('"Amended: USD 10,180,000" (paragraph') and q["options"][-1] == D.CONTEXT
    D.answer(x, EML, q["assumed"])
    n, aside = D.load(x)
    assert (n, aside) == (1, []), aside
    assert D.load(x) == (0, [])  # a retry of the load does not confirm it twice
    rows = fund_a(x.plane)
    new = rows[-1]
    assert float(new[1]) == 10180000 and new[2] == "confirmed" and new[3] is not None  # supersedes the earlier valuation
    with wh.connect(x.plane, read_only=True) as con:
        st = dict(con.execute("select value_text, review_status from extracted_fields where document_id = ?", [d["doc_id"]]).fetchall())
    assert st == {"10180000": "confirmed"}  # one 2.0 value field per document: the line the person picked


def test_kept_as_context_loads_nothing_and_is_not_set_aside(office):
    x = ctx(office, [EML, NOTE])
    before = fund_a(x.plane)
    D.intake(x)
    assert x.th["docs"][NOTE]["status"] == "context" and x.th["intake"][NOTE].startswith("doc:")
    D.answer(x, EML, D.CONTEXT)
    assert D.load(x) == (0, [])
    assert fund_a(x.plane) == before
    rows = {r["name"]: r["read_as"] for r in D.d2_files(x)}
    assert rows == {EML: "read as context", NOTE: "read as context"}


def test_harbor_never_sends_documents_to_table_intake(office, monkeypatch):
    x = ctx(office, [NOTE])
    seen = []
    real = H.Ctx.api

    def spy(self, who, method, path, *a, **k):
        seen.append(path)
        return real(self, who, method, path, *a, **k)
    monkeypatch.setattr(H.Ctx, "api", spy)
    monkeypatch.setattr("sh_platform.v1.v3_loads.intake", lambda x: None)
    monkeypatch.setattr("sh_platform.v1.v3_loads.skip", lambda x, n: False)
    monkeypatch.setattr(H, "my_files", lambda x, kind=None: [f for f in H.read_files(x.plane) if f.get("thread") == x.th["id"]])
    H.a_intake(x)
    assert "/api/v1/intake/upload" not in seen and "/api/v1/evidence/documents" in seen
    assert x.th["docs"][NOTE]["status"] == "context"


def test_a_letter_is_context_not_a_new_layout(office):
    x = ctx(office, LETTERS)
    x.th["docs"] = {}
    V.intake(x)
    assert {n: f["status"] for n, f in x.th["pdf"]["files"].items()} == {n: "context" for n in LETTERS}
    assert V.questions(x) == [] and V.load(x) == (0, [])
    assert {r["name"]: r["read_as"] for r in V.d2_files(x)} == {n: "read as context" for n in LETTERS}


def test_monthly_email_waits_in_evidence_and_loads_nothing(office):
    x = ctx(office, [EML])
    before = fund_a(x.plane)
    aside = D.monthly(x, [EML])
    assert [a["title"] for a in aside] == [f"{EML} needs a look"] and "Confirm the line in Evidence" in aside[0]["text"]
    assert fund_a(x.plane) == before
    with wh.connect(x.plane, read_only=True) as con:
        assert con.execute("select value_text, review_status from extracted_fields where document_id = ?", [x.th["docs"][EML]["doc_id"]]).fetchall() == [("10180000", "pending")]
