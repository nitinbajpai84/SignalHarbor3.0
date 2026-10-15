"""The upload proposal is quick: a 3-page text PDF and a 1200x900 picture each come back inside 5 s, and the model is not asked
when the rules already know the topic. A scan not fully read stays Restricted."""
import io
import time

import fitz
import pytest
from PIL import Image, ImageDraw

from sh_platform.v1 import k1_classify as C
from sh_platform.v1 import ocr_local


class Stub:
    calls = 0

    def complete(self, *a, **k):
        Stub.calls += 1
        raise AssertionError("the model must not be asked here")


def text_pdf(pages=3) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Statement summary page {i}. Holdings and valuation for the month.")
    return doc.tobytes()


def picture(w=1200, h=900) -> bytes:
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    for i in range(10):
        d.text((40, 40 + i * 60), f"Invoice line {i} total {i * 137} Orchard Growth Partners", fill="black")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def timed(name, data):
    start = time.perf_counter()
    got = C.propose(name, data, "", Stub())
    return got, time.perf_counter() - start


def test_text_pdf_proposal_is_quick():
    got, secs = timed("statement-summary.pdf", text_pdf())
    assert secs < 5 and got["topics"] and Stub.calls == 0


@pytest.fixture()
def asked(monkeypatch):
    """Counts the calls that would reach the model for a topic (Jev)."""
    got = []
    monkeypatch.setattr(C, "ask_topic", lambda *a, **k: (got.append(a[2]), None)[1])
    return got


def test_the_model_is_reachable_when_the_rules_do_not_know(asked):
    """The control for the picture test: an unclear name does reach the model, so "not asked" there means something."""
    C.propose("qwerty.txt", b"nothing helpful in here", "", Stub())
    assert asked == ["qwerty.txt"]


@pytest.mark.skipif(not ocr_local.available(), reason="no picture reader installed")
def test_picture_proposal_is_quick(asked):
    got, secs = timed("IMG_0042.png", picture())  # a name the rules cannot read: only the extension says "picture"
    assert secs < 5 and got["topics"] == ["Pictures"] and asked == []


def test_pages_left_unread_keep_the_file_restricted(monkeypatch):
    monkeypatch.setattr(ocr_local, "_engine", lambda: (lambda data: "Plain words about the month."))
    ocr_local._read.cache_clear()
    doc = fitz.open()
    for _ in range(C.PROPOSAL_OCR_PAGES + 1):
        doc.new_page().insert_image(fitz.Rect(72, 72, 172, 172), stream=picture(200, 100))
    got = C.propose("scan.pdf", doc.tobytes(), "", None)
    assert got["sensitivity"] == "restricted"


def test_a_fully_read_scan_is_not_kept_restricted(monkeypatch):
    monkeypatch.setattr(ocr_local, "_engine", lambda: (lambda data: "Plain words about the month."))
    ocr_local._read.cache_clear()
    doc = fitz.open()
    for _ in range(C.PROPOSAL_OCR_PAGES):
        doc.new_page().insert_image(fitz.Rect(72, 72, 172, 172), stream=picture(200, 100))
    got = C.propose("scan.pdf", doc.tobytes(), "", None)
    assert got["sensitivity"] != "restricted" and not got["pii"]["found"]


def test_unread_text_respects_ocr_pages_limit(monkeypatch):
    # unread_text must use ocr_pages=1, ocr_seconds=2.0 and not re-read with defaults
    from sh_platform.v1 import c4_library as lib
    monkeypatch.setattr(ocr_local, "_engine", lambda: (lambda data: "Text from OCR"))
    ocr_local._read.cache_clear()
    doc = fitz.open()
    for _ in range(10):
        doc.new_page().insert_image(fitz.Rect(72, 72, 172, 172), stream=picture(200, 100))
    assert lib.unread_text("scan.pdf", doc.tobytes()) is False
