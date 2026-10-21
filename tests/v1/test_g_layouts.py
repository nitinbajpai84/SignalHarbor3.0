"""W2 (v3_doc_extract): private-fund documents read in layouts never seen. The model is a deterministic fake that reads the page text (it looks
for the answer-key value in the rows and quotes the row); what is tested is the pipeline: the pack's schemas, classify, the quote proof, layout
memory (a confirmed layout is read with no model call) and the OCR path. How well a REAL model reads is tools/score_layouts.py, not this file."""
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.v1 import v3_doc_extract as DE  # noqa: E402
from tools import gen_layouts as GEN  # noqa: E402

SCHEMAS = ROOT / "packs" / "family_office" / "1" / "doc_schemas"
FIX = ROOT / "tests" / "v1" / "fixtures" / "layouts"
KEYS = yaml.safe_load((FIX / "keys.yaml").read_text(encoding="utf-8"))
TYPES = GEN.TYPES


class Plane:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, *parts):
        return self.root.joinpath(*parts)


class Fake:
    """Reads the page text it is sent: the row that holds an answer-key value is the quote (with the row above when the row holds no label)."""

    def __init__(self, expected: dict, doc_type: str, liar: dict | None = None):
        self.expected, self.doc_type, self.liar, self.calls = expected, doc_type, liar or {}, 0

    def complete(self, module_id, messages):
        self.calls += 1
        user = messages[1]["content"]
        req = {"fields": [{"name": n, "type": ty} for n, ty in re.findall(r"^- (\w+) \((\w+)\): ", user, re.M)],
               "pages": [{"page": int(n), "text": body} for n, body in re.findall(r"=== page (\d+) ===\n(.*?)(?=\n=== page |\n</document>)", user, re.S)]}
        assert "<document>" in user and "</document>" in user  # the page text travels as quoted content, in plain text
        if messages[0]["content"] == DE.CLASSIFY:
            return type("R", (), {"text": json.dumps({"doc_type": self.doc_type}), "usage": None})()
        out = {}
        for f in req["fields"]:
            name, want = f["name"], self.expected.get(f["name"])
            if want is None:
                continue
            for pg in req["pages"]:
                rows = pg["text"].splitlines()
                hit = next((i for i, r in enumerate(rows) if self.has(f["type"], r, want)), None)
                if hit is not None:
                    quote = rows[hit] if self.labelled(rows[hit]) or hit == 0 else rows[hit - 1] + "\n" + rows[hit]
                    out[name] = {"value": want, "page": pg["page"], "quote": quote}
                    break
        for name, how in self.liar.items():
            if name in out:
                out[name] = {**out[name], **how}
        return type("R", (), {"text": json.dumps({"fields": out}), "usage": None})()

    @staticmethod
    def labelled(row: str) -> bool:
        return any(len([w for w in c.split() if w.isalpha()]) and any(ch.isalpha() for ch in c) and not DE.nums(c) for c in row.split(" | ")) or ":" in row

    @staticmethod
    def has(vtype, row, want):
        if vtype in ("money", "number", "integer"):
            return any(d == Decimal(want) for _, d in DE.nums(DE.DATE.sub("", row)))  # a date's day is not the figure
        if vtype == "date":
            return any(d.isoformat() == want for _, d in DE.dates(row))
        if vtype == "currency":
            return want in DE.CCY.findall(row)
        return DE.squash(want) in DE.squash(row)


def read(plane, name, data, fake, monkeypatch):
    monkeypatch.setattr(DE, "CLIENT", lambda p: fake)
    return DE.read(plane, name, data, folder=SCHEMAS)


def file_of(name):
    return (FIX / name).read_bytes(), KEYS[name]


def test_the_pack_holds_five_schemas_that_agree_with_themselves():
    s = DE.schemas(folder=SCHEMAS)
    assert sorted(s) == sorted(TYPES)
    for t, sc in s.items():
        names = {f["name"] for f in sc["fields"]}
        assert sc["markers"] and all(f["type"] in ("text", "integer", "money", "number", "date", "currency") and f["description"] for f in sc["fields"])
        for c in sc["checks"]:
            used = {c.get(k) for k in ("total", "field", "after")} | set(c.get("parts", [])) | set(c.get("factors", [])) | set(c.get("add", [])) | set(c.get("subtract", []))
            assert used - {None} <= names, (t, c)
    assert DE.schemas(folder=ROOT / "no_such_pack") == {}  # no pack: nothing is read, nothing is made up


def test_the_hundred_layouts_exist_and_vary():
    assert len(KEYS) == 100 and sum(k["scanned"] for k in KEYS.values()) == 5
    assert len({k["style"] for k in KEYS.values()}) == 5 and {k["pages"] for k in KEYS.values()} == {1, 2}
    for t in TYPES:  # layouts differ: no two files of a type print the same text
        texts = {DE.pages_of(file_of(f"{t}_{i:02d}.pdf")[0])[0][0]["text"].splitlines()[0:3].__str__() for i in range(0, 18)}
        assert len(texts) > 1


@pytest.mark.parametrize("doc_type", TYPES)
def test_every_digital_layout_is_read_with_page_and_quote(doc_type, tmp_path, monkeypatch):
    bad = []
    for i in range(19):
        name = f"{doc_type}_{i:02d}.pdf"
        data, key = file_of(name)
        got = read(Plane(tmp_path), name, data, Fake(key["fields"], doc_type), monkeypatch)
        assert got and got["doc_type"] == doc_type and got["via"] == "model" and not got["scanned"], name
        pages = {p["n"]: DE.squash(p["text"]) for p in DE.pages_of(data)[0]}
        for f, want in key["fields"].items():
            r = got["fields"].get(f)
            if not r or r["value"] != want:
                bad.append((name, f, want, r and r["value"]))
                continue
            assert all(DE.squash(ln) in pages[r["page"]] for ln in r["quote"].splitlines())  # the receipt is real
        assert not set(got["fields"]) - set(key["fields"]), (name, "a field the document does not state was filled")
    assert not bad, bad


def test_a_quote_that_is_not_on_the_page_drops_the_field(tmp_path, monkeypatch):
    data, key = file_of("capital_call_00.pdf")
    liar = {"amount_due": {"quote": "Please pay | EUR 999,999.00"},  # a quote the page does not hold
            "due_date": {"value": "1 January 2030"},  # a real quote, but the value is not in it
            "fund": {"page": 7}}  # a page that does not exist
    got = read(Plane(tmp_path), "c.pdf", data, Fake(key["fields"], "capital_call", liar), monkeypatch)
    assert {d["field"] for d in got["dropped"]} == {"amount_due", "due_date", "fund"}
    assert not {"amount_due", "due_date", "fund"} & set(got["fields"])
    assert got["status"] == "review"  # a required field is missing, so a person looks


def test_field_rules_and_checks_send_a_read_to_a_person(tmp_path, monkeypatch):
    data, key = file_of("capital_call_00.pdf")
    wrong = dict(key["fields"], investment_amount=key["fields"]["fee_amount"])  # parts no longer add up to the amount due
    got = read(Plane(tmp_path), "c.pdf", data, Fake(wrong, "capital_call"), monkeypatch)
    assert got["status"] == "review" and "sum" in {f["kind"] for f in got["flags"]}
    f = DE.schemas(folder=SCHEMAS)["capital_call"]
    fields = {n: {"parsed": Decimal(v)} for n, v in {"amount_due": "100", "investment_amount": "60", "fee_amount": "30"}.items()}
    kinds = {x["kind"] for x in DE.judge(f, fields)}
    assert "sum" in kinds and "missing" in kinds  # 60 + 30 is not 100; fund, currency and due date are required and absent


def test_classification_uses_markers_and_asks_the_model_only_without_one(tmp_path, monkeypatch):
    data, key = file_of("capital_call_00.pdf")  # "Drawdown Notice": a marker
    fake = Fake(key["fields"], "capital_call")
    read(Plane(tmp_path), "c.pdf", data, fake, monkeypatch)
    assert fake.calls == 1  # extraction only
    data, key = file_of("capital_call_05.pdf")
    title = next(t for t in GEN.TITLES["capital_call"] if DE.squash(t) == DE.squash(DE.pages_of(data)[0][0]["text"].splitlines()[1]))
    fake = Fake(key["fields"], "capital_call")
    read(Plane(tmp_path), "c.pdf", data, fake, monkeypatch)
    assert fake.calls == (1 if any(DE.squash(m) in DE.squash(title) for m in DE.schemas(folder=SCHEMAS)["capital_call"]["markers"]) else 2)


def test_a_document_the_pack_has_no_schema_for_is_left_alone(tmp_path, monkeypatch):
    import fitz
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "Dear investor, thank you for your letter of 3 March.")
    got = read(Plane(tmp_path), "l.pdf", doc.tobytes(), Fake({}, "none"), monkeypatch)
    assert got is None  # the caller asks a person, as before
    assert DE.read(Plane(tmp_path), "l.pdf", b"not a pdf", folder=SCHEMAS) is None


@pytest.mark.parametrize("doc_type", TYPES)
def test_a_confirmed_layout_is_read_without_the_model(doc_type, tmp_path, monkeypatch):
    plane, deterministic = Plane(tmp_path), 0
    for i in range(0, 19, 2):  # layouts of every style, one and two pages
        name = f"{doc_type}_{i:02d}.pdf"
        data, key = file_of(name)
        first = read(plane, name, data, Fake(key["fields"], doc_type), monkeypatch)
        again = read(plane, name, data, Fake(key["fields"], doc_type), monkeypatch)
        assert again["via"] == "model"  # a read nobody confirmed is not remembered
        DE.confirm(plane, first, "Helen Foo")
        twin, tkey, _ = GEN.make(doc_type, i, seed=1)  # the next document of the same layout: other fund, other figures
        fake = Fake(tkey, doc_type)
        got = read(plane, f"twin{i}.pdf", twin, fake, monkeypatch)
        assert got["fields"].keys() >= {f for f in key["fields"] if f in first["anchors"]} - {"x"}
        if got["via"] == "layout":
            deterministic += 1
            assert fake.calls == 0 and got["layout_id"]
            assert {f: v["value"] for f, v in got["fields"].items() if f in first["anchors"]} == {f: tkey[f] for f in first["anchors"]}, name
        else:  # an anchor could not be followed (prose around a value): the model reads it, and nothing wrong is passed
            assert all(v["value"] == tkey[f] for f, v in got["fields"].items()), name
    assert deterministic >= 8, deterministic  # most layouts of a type repeat exactly


def test_a_different_layout_of_the_same_type_is_not_taken_for_a_known_one(tmp_path, monkeypatch):
    plane = Plane(tmp_path)
    data, key = file_of("nav_statement_00.pdf")
    DE.confirm(plane, read(plane, "a.pdf", data, Fake(key["fields"], "nav_statement"), monkeypatch), "Helen Foo")
    other, okey = file_of("nav_statement_03.pdf")
    fake = Fake(okey["fields"], "nav_statement")
    assert read(plane, "b.pdf", other, fake, monkeypatch)["via"] == "model" and fake.calls >= 1


@pytest.mark.parametrize("doc_type", TYPES)
def test_a_scan_is_read_by_ocr_on_this_machine_and_a_person_confirms_it(doc_type, tmp_path, monkeypatch):
    name = f"{doc_type}_19.pdf"
    data, key = file_of(name)
    pages, scanned = DE.pages_of(data)
    assert scanned and pages[0]["cells"]  # no text layer, but OCR found cells
    got = read(Plane(tmp_path), name, data, Fake(key["fields"], doc_type), monkeypatch)
    assert got["scanned"] and got["status"] == "review" and any(f["kind"] == "picture" for f in got["flags"])
    right = [f for f, r in got["fields"].items() if r["value"] == key["fields"][f]]
    assert len(right) >= len(key["fields"]) // 2, (len(right), len(key["fields"]), got["dropped"])  # OCR is imperfect; the quote proof drops what it cannot show


def test_the_hook_in_v3_pdf_reads_instead_of_asking(tmp_path, monkeypatch):
    from sh_platform.v1 import v3_pdf as V
    data, key = file_of("capital_call_00.pdf")
    monkeypatch.setattr(DE, "schemas", lambda plane=None, folder=None, _s=DE.schemas: _s(folder=SCHEMAS))
    monkeypatch.setattr(DE, "CLIENT", lambda p: Fake(key["fields"], "capital_call"))
    x = type("X", (), {"plane": Plane(tmp_path), "th": {"pdf": {"files": {}, "ask": {}}}})()
    rec = {"status": "read"}
    assert V._doc_read(x, "c.pdf", data, rec) is True
    assert rec["status"] == "extracted" and rec["doc_read"]["fields"]["amount_due"]["page"] == 1
    assert x.th["pdf"]["reads"]["c.pdf"]["anchors"]
    monkeypatch.setattr(DE, "CLIENT", lambda p: None)  # no model and no known layout: the old question is asked
    assert V._doc_read(x, "c.pdf", data, {"status": "read"}) is False
