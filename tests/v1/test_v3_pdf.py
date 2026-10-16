"""Harbor 3.0 PDFs (v3_pdf): a PDF is read by layout, a new layout costs one question, the answer is remembered, every value keeps its page and
quote, a value that fails the layout's checks is never loaded, a layout marked twice becomes an office skill. The 2.0 calls are stubbed; the
files are the synthetic 10uc statements and confirmations."""
import csv
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_pdf as V  # noqa: E402
from sh_platform.v1 import v3_skills as S  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402

FIX = ROOT / "tests" / "v1" / "fixtures" / "10uc"
BLUE = ["bluewater_B_2026-06-30_final.pdf", "bluewater_B_2026-07-31_final.pdf", "bluewater_B_2026-08-31_final.pdf"]
KEY = "Net asset value of your interest"


def pdf(name: str) -> bytes:
    return next(FIX.glob(f"*/{name}")).read_bytes()


class Fake:
    """Stands in for the 2.0 routes Harbor calls: records them, answers like the real ones."""
    def __init__(self):
        self.calls, self.rows = [], {}

    def __call__(self, ctx, who, method, path, body=None, files=None, data=None, soft=False):
        self.calls.append((method, path))
        if path == "/api/v1/evidence/documents":
            return {"id": "doc-" + str(len(self.calls))}
        if path == "/api/v1/intake/upload":
            name, blob = files["file"]
            self.rows[name] = blob.decode("utf-8")
            return {"file_id": "f-" + name}
        if path.endswith("/load"):
            return {"state": "loaded"}
        if path.startswith("/api/v1/model/mappings") and method == "GET":
            return []
        return {}


@pytest.fixture()
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    fake = Fake()
    monkeypatch.setattr(H.Ctx, "api", lambda ctx, *a, **k: fake(ctx, *a, **k))
    monkeypatch.setattr(V, "_prematch", lambda x, pairs, also="": [])
    monkeypatch.setattr(V, "_spec_type", lambda x, layout: {"id": "xt_aaaaaaaaaaaa", "version": 1})
    from sh_platform.v1 import e2_intake
    monkeypatch.setattr(e2_intake, "listing", lambda plane, instrument_id=None: [])
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    plane = PlaneStore(str(data)).plane_for("evergreen")
    return app, plane, fake


def thread(plane, tid: str, files: dict[str, bytes]) -> dict:
    th = {"id": tid, "title": "Statements", "created": H.now() + tid, "stage": "working", "events": [], "steps": [], "asked": 0,
          "started_by": "Helen Foo", "iid": "ini-test", "intake": {}}
    H.save(plane, th)
    fs = H.read_files(plane)
    for name, data in files.items():
        H.drop(plane, name, data)
        fs.append({"name": name, "arrived_at": H.now(), "status": "recognised", "source": "Manager statements", "thread": tid})
    H._fp(plane).write_text(json.dumps(fs), encoding="utf-8")
    return th


def test_layout_pairs_and_candidates():
    pages = V.pages_of(BLUE[0], pdf(BLUE[0]))
    pairs = V.pairs_of(pages)
    got = {p["label"]: p for p in pairs}
    assert got[KEY]["value"] == "USD 5,953,418.00" and got[KEY]["page"] == 2 and got[KEY]["quote"] == f"{KEY}\nUSD 5,953,418.00"
    assert got["Fund"]["value"] == "Fund B - Evergreen Income II"
    assert "units set out on page 2" not in " ".join(p["value"] for p in pairs)  # prose is not a value
    fields = V.propose(pairs)
    assert [c["label"] for c in V.candidates(pairs, fields)] == [KEY]
    sig, name = V.layout_of(pages)
    assert name == "Bluewater Capital - Partner Valuation Statement"
    other = V.layout_of(V.pages_of("k.pdf", pdf("kestrel_H1_2026-09-30_estimate.pdf")))[0]
    assert other != sig  # another manager is another layout
    same = V.layout_of(V.pages_of(BLUE[1], pdf(BLUE[1])))[0]
    assert same == sig  # another month of the same manager is the same layout


def test_fx_confirmation_candidates_skip_references():
    name = "FXF-2026-001_confirmation_2026-09-15.pdf"
    pairs = V.pairs_of(V.pages_of(name, pdf(name)))
    fields = V.propose(pairs)
    assert {f["name"]: f["format"] for f in fields}["trade date"] == "date"
    assert "our ref (client)" not in {f["name"] for f in fields if f["format"] == "number"}  # a reference is text, not a number
    assert [c["value"] for c in V.candidates(pairs, fields)] == ["USD 2,000,000.00", "SGD 2,680,000.00"]


def test_text_is_kept_as_printed_and_every_value_has_page_and_quote(tmp_path):
    name = "cedarpoint_C_2026-06-30_final.pdf"
    pairs = V.pairs_of(V.pages_of(name, pdf(name)))
    fields = V.propose(pairs)
    key = "limited partner capital balance"
    lay = {"name": "x", "fields": [{**f, "required": f["name"] == key or f["required"]} for f in fields], "key": key}

    class P:  # run_checks only reads the plane for a ties_to check
        pass
    values, checks, status = V.read_values(P(), lay, pairs)
    assert status == "ok" and values["fund"]["value"] == "Cedarpoint Ventures III, L.P."  # x5's text parser would cut the final full stop
    assert all(v["page"] and v["quote"] and v["raw"] in v["quote"] for v in values.values() if v["raw"])


def run_a(office, tid, names):
    app, plane, fake = office
    th = thread(plane, tid, {n: pdf(n) for n in names})
    x = H.Ctx(app, plane, th, None)
    V.intake(x)
    return x, fake


def test_new_layout_asks_once_then_the_same_layout_loads_without_asking(office):
    app, plane, fake = office
    x, _ = run_a(office, "t-1", BLUE)
    qs = V.questions(x)
    assert len(qs) == 1 and qs[0]["options"] == [f"{KEY}: USD 5,953,418.00", V.LEAVE] and qs[0]["assumed"] == qs[0]["options"][0]
    assert "3 files" in qs[0]["text"]
    assert {f["status"] for f in x.th["pdf"]["files"].values()} == {"asked"}
    V.answer(x, qs[0]["id"].split(":", 1)[1], qs[0]["assumed"])
    got, aside = V.load(x)
    assert (got, aside) == (3, []) and V.memory(plane)["bluewater capital partner valuation statement"]["key"] == KEY.lower()
    (csv_name, text), = fake.rows.items()
    assert csv_name.endswith("_valuation_rows.csv")
    head, *rows = text.strip().splitlines()
    assert head.startswith("file,layout,fund,valuation date,value,currency") and len(rows) == 3
    assert "2026-06-30,5953418.00,USD" in rows[0] and f"{KEY} / USD 5,953,418.00" in rows[0] and ",2," in rows[0]  # page 2 and the quote
    rec = json.loads(next((plane.path("extractions")).glob("*.json")).read_text(encoding="utf-8"))
    assert rec["status"] == "ok" and rec["confirmed_by"] == "Harbor, for Helen Foo"
    # next month, another thread: same layout, no question, loaded
    x2, fake2 = run_a(office, "t-2", ["bluewater_B_2026-09-30_final.pdf"])
    assert V.questions(x2) == [] and x2.th["pdf"]["files"]["bluewater_B_2026-09-30_final.pdf"]["status"] == "read"
    assert V.load(x2)[0] == 1


def test_left_out_layout_is_not_loaded(office):
    x, fake = run_a(office, "t-1", BLUE[:1])
    q = V.questions(x)[0]
    V.answer(x, q["id"].split(":", 1)[1], V.LEAVE)
    assert V.load(x) == (0, []) and not fake.rows and V.memory(x.plane) == {}


def test_a_value_that_fails_a_check_is_never_loaded(office, monkeypatch):
    x, fake = run_a(office, "t-1", BLUE[:1])
    V.answer(x, V.questions(x)[0]["id"].split(":", 1)[1], f"{KEY}: USD 5,953,418.00")
    real = V.pages_of

    def broken(name, data):  # the period end is no longer a date on the page
        return [(pg, [(k, "not given" if t == "30 June 2026" else t) for k, t in ls]) for pg, ls in real(name, data)]
    monkeypatch.setattr(V, "pages_of", broken)
    got, aside = V.load(x)
    assert got == 0 and not fake.rows and "period end" in aside[0]["text"] and "review queue" in aside[0]["text"]
    rec = json.loads(next((x.plane.path("extractions")).glob("*.json")).read_text(encoding="utf-8"))
    assert rec["status"] == "review" and "confirmed_by" not in rec


def test_an_fx_confirmation_goes_to_the_fx_rows_file_with_both_legs_and_its_page(office):
    name = "FXF-2026-002_confirmation_2026-10-05.pdf"
    x, fake = run_a(office, "t-1", [name])
    q = V.questions(x)[0]
    assert q["options"][:2] == ["Client sells (USD): USD 3,000,000.00", "Client buys (SGD): SGD 4,035,600.00"]
    V.answer(x, q["id"].split(":", 1)[1], q["options"][1])
    got, aside = V.load(x)
    assert got == 1 and not aside
    (text,) = fake.rows.values()  # one row per confirmation, both legs, the document and the page of the reference
    row = next(csv.DictReader(io.StringIO(text)))
    assert [row[k] for k in ("trade reference", "trade date", "value date", "currency bought", "amount bought", "currency sold", "amount sold", "rate", "counterparty", "source page")] == [
        "FXF-2026-002", "2026-10-05", "2027-01-05", "SGD", "4035600.00", "USD", "3000000.00", "1.3452", "Harbour Bank (synthetic)", "1"]
    assert json.loads(row["pdf reading"])["trade date"]["page"] == 1 and "Trade date" in json.loads(row["pdf reading"])["trade date"]["quote"]


def test_a_layout_marked_twice_becomes_an_office_skill(office, monkeypatch):
    app, plane, fake = office
    x, _ = run_a(office, "t-1", BLUE[:1])
    V.answer(x, V.questions(x)[0]["id"].split(":", 1)[1], f"{KEY}: USD 5,953,418.00")
    assert S.listing(plane, "waiting") == []
    real = V.pages_of

    def renamed(name, data):  # the manager renamed the line that holds the amount
        return [(pg, [(k, t.replace(KEY, "Value of your holding")) for k, t in ls]) for pg, ls in real(name, data)]
    monkeypatch.setattr(V, "pages_of", renamed)
    x2, _ = run_a(office, "t-2", BLUE[1:2])
    q = V.questions(x2)[0]
    assert "looks different now" in q["text"] and q["assumed"].startswith("Value of your holding")
    V.answer(x2, q["id"].split(":", 1)[1], q["assumed"])
    lay = V.memory(plane)["bluewater capital partner valuation statement"]
    assert lay["marks"] == 2 and next(f for f in lay["fields"] if f["name"] == KEY.lower())["where_usually"] == f"{KEY} | Value of your holding"
    waiting = S.listing(plane, "waiting")
    assert len(waiting) == 1 and waiting[0]["id"].startswith("office.") and waiting[0]["status"] == "waiting"
    assert V.load(x2)[0] == 1  # the changed layout still reads the old files' label too


def test_harbor_hooks_send_pdfs_down_the_document_path(office):
    app, plane, fake = office
    th = thread(plane, "t-1", {BLUE[0]: pdf(BLUE[0])})
    th["pid"] = "p1"
    x = H.Ctx(app, plane, th, None)
    msg = H.a_intake(x)
    assert th["intake"][BLUE[0]].startswith("pdf:doc-") and ("POST", "/api/v1/intake/upload") not in fake.calls and msg.startswith("1 files read")
    d = H.d2(x)
    assert [q["id"] for q in d["questions"] if q["id"].startswith("pdf:")] and d["files"][0]["read_as"].startswith("Bluewater Capital")
    th["answers"] = {q["id"]: q["assumed"] for q in d["questions"]}
    H.b_answers(x)
    assert H.b_load(x).startswith("1 files loaded") and re.search(r"_valuation_rows\.csv$", next(iter(fake.rows)))
    assert H.read_files(plane)[0]["status"] == "loaded"


def test_a_value_read_from_a_picture_waits_for_a_person_then_loads_when_accepted(office, monkeypatch):
    monkeypatch.setattr(V, "is_picture", lambda data: True)
    x, fake = run_a(office, "t-1", BLUE[:1])
    V.answer(x, V.questions(x)[0]["id"].split(":", 1)[1], f"{KEY}: USD 5,953,418.00")
    got, aside = V.load(x)
    assert got == 0 and not fake.rows and "picture" in aside[0]["text"]
    path = next(x.plane.path("extractions").glob("*.json"))
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["status"] == "review" and "confirmed_by" not in rec
    rec.update(status="ok", accepted_by="Helen Foo", checks=[])  # what x5_extract.accept leaves after a person confirms
    rec["values"][KEY.lower()] = {"value": "5953418.00", "raw": "USD 5,953,418.00", "line": 12, "by": "person"}  # a corrected value has no page or quote
    path.write_text(json.dumps(rec), encoding="utf-8")
    assert V.load(x) == (1, []) and "2026-06-30,5953418.00,USD" in next(iter(fake.rows.values()))
