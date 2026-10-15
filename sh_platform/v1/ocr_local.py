"""Local picture reader. `ocr(path_or_bytes) -> str | None`: text read from a picture on this machine, or None when no engine is
installed (or the picture holds no text). Engines tried in order: rapidocr_onnxruntime, then pytesseract with a tesseract binary on PATH.
Egress rule: the picture and its bytes never go to a model or an outside service; only the text this returns may travel on."""
from __future__ import annotations

import functools
import io
import logging
import pathlib
import shutil
import threading

log = logging.getLogger(__name__)


MAX_SIDE = 1600  # longest side, in pixels, handed to the engine; phone pictures are 4000+ px and read no better
_lock = threading.Lock()


def _shrink(data: bytes) -> bytes:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if max(im.size) <= MAX_SIDE:
            return data
        im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        im.save(out, "PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 - not a picture PIL knows: the engine gets the bytes as they are
        return data


def _rapid():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()

    def run(data: bytes) -> str:
        result, _ = engine(data, use_cls=False)  # no upside-down check: phone pictures and scans are upright; saves a stage
        return "\n".join(str(r[1]) for r in result or [])
    return run


def _tesseract():
    import pytesseract
    from PIL import Image
    if not (shutil.which("tesseract") or getattr(pytesseract.pytesseract, "tesseract_cmd", "") != "tesseract"):
        raise RuntimeError("no tesseract binary")

    def run(data: bytes) -> str:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)))
    return run


_made: list = []  # [engine or None] once chosen: built once per process, under a lock


def _engine():
    with _lock:
        if not _made:
            _made.append(None)
            for make in (_rapid, _tesseract):
                try:
                    _made[0] = make()
                    break
                except Exception:  # noqa: BLE001 - not installed or not usable: try the next one
                    continue
        return _made[0]


def available() -> bool:
    return _engine() is not None


@functools.lru_cache(maxsize=4)  # the same picture is read for the scan, the preview and the catalogue; read it once
def _read(data: bytes) -> str | None:
    run = _engine()
    if run is None:
        return None
    try:
        return run(_shrink(data)).strip() or None
    except Exception:  # noqa: BLE001 - a picture the engine cannot read is stored unread
        log.warning("a picture could not be read")
        return None


def ocr(path_or_bytes) -> str | None:
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else pathlib.Path(path_or_bytes).read_bytes()
    return _read(bytes(data))
