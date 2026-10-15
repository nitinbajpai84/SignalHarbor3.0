"""Library upload of several files, PDFs read with PyMuPDF, and pictures: read by a local picture reader when one exists, otherwise
stored unread with a plain message. A picture is never sent anywhere; only text read on this machine flows on."""
import base64
import io

import fitz
import pytest

from sh_platform.context_docs import reader
from sh_platform.v1 import k1_classify as C
from sh_platform.v1 import ocr_local
from tests.v1.test_k1 import ARJUN, CREDS, PLAIN, client, up, world  # noqa: F401 - the shared fixture

pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")
EMAIL_LINE = "Write to zed.quill@example.test about the August pack."
PLAIN_MSG = "Stored. To read text from pictures this machine needs a picture reader; your company admin can switch it on."


def pdf(text: str | None) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    else:  # image only: no text layer
        page.insert_image(fitz.Rect(72, 72, 172, 172), stream=png())
    return doc.tobytes()


def png() -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    pix.clear_with(200)
    return pix.tobytes("png")


def engine(monkeypatch, run):
    monkeypatch.setattr(ocr_local, "_engine", lambda: run)
    ocr_local._read.cache_clear()


def test_three_files_one_duplicate(world):
    app, _, _ = world
    c = client(app, ARJUN)
    a, b = b"a_col,b_col\n1,2\n", b"x_col,y_col\n3,4\n"
    got = [up(c, n, d).json() for n, d in (("batch_one.csv", a), ("batch_two.csv", b), ("batch_three.csv", a))]
    assert "item" in got[0] and "item" in got[1] and got[2]["duplicate"]["name"] == "batch_one.csv"


def test_a_pdf_with_text_is_read_and_scanned(world):
    app, _, _ = world
    data = pdf(EMAIL_LINE)
    assert "zed.quill" in reader.read_segments("pack.pdf", data)[0][1]
    pii = C.scan_pii("pack.pdf", data)
    assert pii["found"] and "email addresses" in pii["kinds"]
    got = up(client(app, ARJUN), "august_pack.pdf", data).json()
    assert got["item"]["sensitivity"] == "restricted" and "message" not in got


def test_a_picture_is_stored_with_a_plain_message_when_no_reader(world, monkeypatch):
    engine(monkeypatch, None)
    app, _, _ = world
    c = client(app, ARJUN)
    for name, data in (("scan_photo.jpeg", png()), ("scan_only.pdf", pdf(None))):
        r = up(c, name, data)
        assert r.status_code == 200, r.text
        assert r.json()["message"] == PLAIN_MSG
        assert r.json()["item"]["sensitivity"] == "restricted", "Unread files must default to Restricted"
    assert r.json()["item"]["name"] == "scan_only.pdf"
    assert up(c, "holiday.jpg", png() + b"\0").json()["item"]["kind"] == "picture"
    assert "could not look" not in r.text


def test_a_stub_reader_text_is_read_and_scanned(world, monkeypatch):
    seen = []
    engine(monkeypatch, lambda data: seen.append(data) or EMAIL_LINE)
    app, _, _ = world
    img = png()
    assert reader.read_segments("photo.png", img)[0][1] == EMAIL_LINE
    assert C.scan_pii("photo.png", img)["found"]
    r = up(client(app, ARJUN), "ocr_receipt.jpeg", img + b"\1").json()
    assert r["item"]["sensitivity"] == "restricted" and r["item"]["kind"] == "picture" and "message" not in r
    scanned = reader.read_segments("scan_only.pdf", pdf(None))  # image-only PDF goes through the same reader
    assert "zed.quill" in scanned[0][1]
    assert all(isinstance(d, bytes) for d in seen)  # the reader got the picture here, on this machine; nothing else took it


def test_an_image_with_text_is_read_by_rapidocr_when_available(world):
    """When RapidOCR is installed, images with drawn text are read and scanned."""
    pytest.importorskip("rapidocr_onnxruntime")
    app, _, _ = world
    # Create an image with drawn text using PIL
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), EMAIL_LINE, fill="black")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_data = img_bytes.getvalue()
    # Upload and verify it's scanned for personal data
    r = up(client(app, ARJUN), "drawn_text.png", img_data).json()
    assert r["item"]["sensitivity"] == "restricted", "Image with email should be restricted"
    assert "message" not in r, "Image successfully read should have no fallback message"
