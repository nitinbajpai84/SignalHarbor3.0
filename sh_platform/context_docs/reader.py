"""Reading an uploaded file into text, once, on this machine (D-032).

Copied from the earlier product: `emitters/documents.py` (`_xml_text`, `_office_text`, the type lists) and
`sh_platform/context/agent_docs.py` (`_guard_office_zip`, `_pdf_segments`, `_chunk`, `_safe_name`, the limits from
`contracts/settings/agent_docs.yaml`). Changed for this product: no model reads a file (no Gemini for pictures or PDFs),
pictures and scanned PDFs are read by a local picture reader if one is installed, a PDF is read with PyMuPDF, and Excel is read with the standard
library because openpyxl is not a dependency here.
"""
import html
import io
import itertools
import pathlib
import re
import zipfile
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

MAX_UPLOAD_BYTES = 15 * 1024 * 1024        # agent_docs.yaml max_upload_bytes (Confirmed)
MAX_TEXT_CHARS = 2_000_000                 # agent_docs.yaml max_text_chars (Proposal pending Nitin)
DOCX_MAX_ENTRIES = 1000                    # agent_docs.yaml docx_max_entries (Confirmed)
DOCX_MAX_UNCOMPRESSED = 100 * 1024 * 1024  # agent_docs.yaml docx_max_uncompressed_bytes (Confirmed)
MAX_PDF_PAGES = 2000                       # agent_docs.yaml max_pdf_pages (Confirmed)
MAX_PART_BYTES = 20 * 1024 * 1024         # most bytes read from one zip part (the guard checks only the claimed size)
MAX_HTML_BYTES = 2_000_000                 # a web page larger than this is refused before parsing
MAX_EML_BYTES = 250_000                   # the email parser reads this far (~0.5 ms per mail part; 25 000 tiny parts
                                           # took 14 s); ponytail: a text part after a big attachment is lost
MAX_EML_PARTS = 200                        # mail parts looked at
XLSX_ROWS_PER_SHEET = 40                  # documents.py: every sheet's header and first rows
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150

TEXT_TYPES = {"txt", "md", "csv", "tsv", "json", "yaml", "yml", "sql"}
MARKUP_TYPES = {"html", "htm", "eml"}  # read by the standard library's parsers, never by a regular expression
OFFICE_TYPES = {"docx", "pptx", "xlsx"}
PICTURE_TYPES = {"png", "jpg", "jpeg", "webp", "gif"}
NO_READER_MSG = "To read text from pictures this machine needs a picture reader; your company admin can switch it on."


class Refusal(ValueError):
    """A file that cannot be taken in. The message is plain words for the screen."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def pdf_reader_available() -> bool:
    for mod in ("fitz", "pypdf"):  # PyMuPDF first
        try:
            __import__(mod)
            return True
        except ImportError:
            continue
    return False


def allowed_extensions() -> list[str]:
    return sorted(TEXT_TYPES | MARKUP_TYPES | OFFICE_TYPES | ({"pdf"} if pdf_reader_available() else set()))


def ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def safe_name(filename: str) -> str:
    name = pathlib.PurePath(filename or "file").name
    name = re.sub(r"[^\w.\- ]+", "_", name).strip(" .") or "file"
    if len(name) <= 120:
        return name
    stem, dot, ext = name.rpartition(".")
    return f"{stem[:119 - len(ext)].rstrip(' .')}.{ext}" if dot and stem and len(ext) <= 10 else name[:120]  # a long name keeps its type


def _guard_office_zip(data: bytes, label: str) -> None:
    """Zip-bomb guard from the zip's own directory (the size it CLAIMS), before anything is decompressed."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > DOCX_MAX_ENTRIES:
                raise Refusal(f"This {label} file has too many parts to read safely.")
            if sum(i.file_size for i in infos) > DOCX_MAX_UNCOMPRESSED:
                raise Refusal(f"This {label} file would expand too far to read safely.")
    except zipfile.BadZipFile:
        raise Refusal(f"This {label} file is damaged or password-protected, so it cannot be read.") from None


def _part(z: zipfile.ZipFile, name: str) -> bytes:
    with z.open(name) as f:
        data = f.read(MAX_PART_BYTES + 1)
    if len(data) > MAX_PART_BYTES:
        raise Refusal("This file has a part too large to read safely.")
    return data


def _xml_text(xml: bytes, tag: str) -> str:
    """Text runs from Office XML (w:t in Word, a:t in PowerPoint), paragraph breaks kept."""
    s = xml.decode("utf-8", "ignore")
    out = []
    for m in re.finditer(rf"<{tag}(?:\s[^<>]*)?>([^<]*)</{tag}>|</[wa]:p>", s):
        out.append("\n" if m.group(1) is None else html.unescape(m.group(1)))
    return re.sub(r"\n{3,}", "\n\n", "".join(out))


def _xlsx_cells(row: str):
    """(attributes, body) per cell. Split on the closing tag and match only `[^<>]` runs, so an unclosed tag costs
    nothing and the work stays linear however a hostile file is built."""
    for part in row.split("</c>"):
        found = list(re.finditer(r"<c\b([^<>]*?)(/>|>)", part))
        for i, m in enumerate(found):
            yield m.group(1), (part[m.end():] if m.group(2) == ">" and i == len(found) - 1 else "")


def _xlsx_text(z: zipfile.ZipFile, max_rows: int = XLSX_ROWS_PER_SHEET) -> str:
    # ponytail: sheets are matched to names by order and cells are read with regular expressions; formulas show
    # their last saved value only. Swap in openpyxl if it ever becomes a dependency.
    names = re.findall(r'<sheet\b[^<>]*?\bname="([^"]*)"', _part(z, "xl/workbook.xml").decode("utf-8", "ignore"))
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in _part(z, "xl/sharedStrings.xml").decode("utf-8", "ignore").split("</si>")[:-1]:
            shared.append(html.unescape("".join(re.findall(r"<t\b[^<>]*>([^<]*)</t>", si.split("<si>")[-1]))))
    sheets = sorted((n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                    key=lambda n: int(re.findall(r"\d+", n)[-1]))
    out = []
    for i, part in enumerate(sheets):
        out.append(f"## Sheet: {html.unescape(names[i]) if i < len(names) else i + 1}")
        rows = []
        for seg in _part(z, part).decode("utf-8", "ignore").split("</row>")[:-1]:
            m = re.search(r"<row\b[^<>]*(?<!/)>", seg)
            if m:
                rows.append(seg[m.end():])
        for n, row in enumerate(rows):
            if n >= max_rows:
                out.append("... (more rows)")
                break
            cells = []
            for attrs, body in _xlsx_cells(row):
                v = re.search(r"<v>([^<]*)</v>", body)
                if 't="s"' in attrs and v and v.group(1).isdigit() and int(v.group(1)) < len(shared):
                    cells.append(shared[int(v.group(1))])
                elif 't="inlineStr"' in attrs:
                    cells.append(html.unescape("".join(re.findall(r"<t\b[^<>]*>([^<]*)</t>", body))))
                else:
                    cells.append(html.unescape(v.group(1)) if v else "")
            if any(cells):
                out.append(" | ".join(cells))
    return "\n".join(out)


def _office_segments(ext: str, data: bytes, xlsx_rows: int | None = None) -> list[tuple[str | None, str]]:
    _guard_office_zip(data, f".{ext}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if ext == "docx":
                return [(None, _xml_text(_part(z, "word/document.xml"), "w:t"))]
            if ext == "xlsx":
                return [(None, _xlsx_text(z, xlsx_rows or XLSX_ROWS_PER_SHEET))]
            slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                            key=lambda n: int(re.findall(r"\d+", n)[-1]))
            return [(f"slide {i}", _xml_text(_part(z, n), "a:t").strip()) for i, n in enumerate(slides, 1)]
    except (KeyError, zipfile.BadZipFile):
        raise Refusal(f"This .{ext} file could not be opened. Is it damaged or password-protected?") from None


OCR_PAGES = 20  # pages of a scanned PDF sent to the local picture reader


def _pdf_segments(data: bytes, ocr_pages: int = OCR_PAGES, ocr_seconds: float | None = None,
                  partial: list | None = None) -> list[tuple[str | None, str]]:
    """Text per page with PyMuPDF (pypdf if that is missing). A PDF with no text layer is read like a picture, locally."""
    try:
        import fitz
    except ImportError:
        fitz = None
    try:
        if fitz is None:
            import pypdf
            pages = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages[:MAX_PDF_PAGES]]
            doc = None
        else:
            doc = fitz.open(stream=data, filetype="pdf")
            if doc.needs_pass:
                raise ValueError("locked")
            pages = []
            for i, page in enumerate(doc):
                if i >= MAX_PDF_PAGES or sum(map(len, pages)) >= MAX_TEXT_CHARS:
                    break
                pages.append(page.get_text())
        if not any(t.strip() for t in pages) and doc is not None:
            from sh_platform.v1 import ocr_local
            if ocr_local.available():  # image-only PDF: each page as a picture, read on this machine, never sent anywhere
                import time
                end = None if ocr_seconds is None else time.monotonic() + ocr_seconds
                pages = []
                for pg in list(doc)[:ocr_pages]:
                    if end is not None and time.monotonic() > end:
                        break
                    pages.append(ocr_local.ocr(pg.get_pixmap(dpi=200).tobytes("png")) or "")
                if partial is not None and len(pages) < min(doc.page_count, MAX_PDF_PAGES):
                    partial.append(True)  # pages left unread: the caller keeps the file Restricted until they are
        if doc is not None:
            doc.close()
        if not any(t.strip() for t in pages):
            raise Refusal("This PDF has no text to read. " + NO_READER_MSG)
        return [(f"p. {i}", t) for i, t in enumerate(pages, 1)]
    except Refusal:
        raise
    except Exception:  # noqa: BLE001 - the libraries raise many kinds for a damaged or locked file; said plainly below
        raise Refusal("This PDF could not be read. Is it damaged or password-protected?") from None


class _TagStripper(HTMLParser):
    """Visible text of a web page: tags dropped, script and style left out, block ends kept as line breaks, and
    collection stops at MAX_TEXT_CHARS so a hostile page cannot grow the result."""

    _SKIP = {"script", "style", "head"}
    _BREAK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.size = 0
        self._skipping = 0

    def _add(self, text: str) -> None:
        text = text[:MAX_TEXT_CHARS - self.size]
        if text:
            self.parts.append(text)
            self.size += len(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skipping += 1
        elif tag in self._BREAK:
            self._add("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skipping = max(0, self._skipping - 1)
        elif tag in self._BREAK:
            self._add("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._add(data)


def _tags_cannot_overlap(s: str) -> str:
    """html.parser takes cubic time on a hostile page such as '<a <a <a ...' (12 KB took 5 s). A '<' is kept as a tag
    start only when the next '>' comes before the next '<'; any other '<' becomes the text '&lt;'. One pass, linear.
    ponytail: a comment or script that itself contains '<' shows as text; fine for context, swap the parser if not."""
    out, pos, gt, lt, end = [], 0, -1, s.find("<"), len(s)
    while lt != -1:
        if gt < lt:
            gt = s.find(">", lt)  # remembered, so a page with no '>' at all is searched once
            gt = end if gt == -1 else gt
        nxt = s.find("<", lt + 1)
        out.append(s[pos:lt])
        # '<!' and '<?' (comments, CDATA, declarations) are also text: html.parser re-scans for '-->' / ']]>' each time
        keep = gt < end and (nxt == -1 or gt < nxt) and s[lt + 1:lt + 2] not in ("!", "?")
        out.append("<" if keep else "&lt;")
        pos, lt = lt + 1, nxt
    out.append(s[pos:])
    return "".join(out)


def _html_text(data: bytes) -> str:
    if len(data) > MAX_HTML_BYTES:
        raise Refusal("This page is too large to read; save it as text and upload that instead.")
    p = _TagStripper()
    text = _tags_cannot_overlap(data.decode("utf-8", "replace"))
    for i in range(0, len(text), 65536):  # stop parsing once the text is full: 300,000 nested tags need not all be read
        p.feed(text[i:i + 65536])
        if p.size >= MAX_TEXT_CHARS:
            break
    p.close()
    return re.sub(r"\n\s*\n+", "\n\n", "".join(p.parts)).strip()


def _eml_text(data: bytes) -> str:
    """Headers (from, to, date, subject) and every text/plain part that is not an attachment. Other parts are ignored."""
    try:
        msg = BytesParser(policy=policy.default).parsebytes(data[:MAX_EML_BYTES])
    except (ValueError, LookupError):
        raise Refusal("This email file could not be read.") from None
    lines = [f"{h}: {' '.join(str(msg[h]).split())}" for h in ("From", "To", "Date", "Subject") if msg[h]]
    for part in itertools.islice(msg.walk(), MAX_EML_PARTS):
        if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
            try:
                lines += ["", part.get_content()[:MAX_TEXT_CHARS]]
            except (LookupError, ValueError):
                continue  # an unknown character set: skip the part, never guess
    return "\n".join(lines).strip()


def read_segments(name: str, data: bytes, xlsx_rows: int | None = None, ocr_pages: int = OCR_PAGES,
                  ocr_seconds: float | None = None, partial: list | None = None) -> list[tuple[str | None, str]]:
    """(location, text) per page, slide or whole file. Raises Refusal for anything that cannot be taken in."""
    ext = ext_of(name)
    if ext in PICTURE_TYPES:  # read locally if a picture reader is installed; otherwise the caller stores it unread
        from sh_platform.v1 import ocr_local
        text = ocr_local.ocr(data)
        if text is None:
            raise Refusal(NO_READER_MSG)
        return [(None, text)]
    if ext == "pdf" and not pdf_reader_available():
        raise Refusal("PDF files cannot be read on this machine yet. Save the document as Word or text and upload that.")
    if ext not in allowed_extensions():
        raise Refusal(f"Cannot accept .{ext or '(no extension)'} files here. Allowed: {', '.join(allowed_extensions())}.")
    if ext == "pdf":
        return _pdf_segments(data, ocr_pages, ocr_seconds, partial)
    if ext in OFFICE_TYPES:
        return _office_segments(ext, data, xlsx_rows)
    if ext in MARKUP_TYPES:
        return [(None, _eml_text(data) if ext == "eml" else _html_text(data))]
    return [(None, data.decode("utf-8", "replace"))]


def chunk(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks
