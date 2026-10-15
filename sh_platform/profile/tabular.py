"""Reading an uploaded Excel, CSV or JSON file into a header and rows, on this machine, stdlib only (M3-P02).

Ported from the earlier product: `emitters/landing.py` `read_tabular` (CSV and the first Excel sheet to header + rows); the column
profile of `profiler.py` is in profile.py. The Excel part extends the stdlib cell reading of `sh_platform/context_docs/reader.py`
(`_xlsx_text`, which returns text) so it returns rows: cell positions are kept, so an empty cell stays an empty cell. It uses that file's
zip guard and part reader as they are (imported, not copied). If a second module needs rows, move `xlsx_rows` into sh_platform then.

Nothing is executed: a formula shows its last saved value, a macro workbook (.xlsm, or a vbaProject inside) is refused, and the caps
below stop a hostile file. A banner row ("Illustrative, synthetic ...") and any title line above the header are skipped.
`read_table(filename, data)` -> (header: list[str], rows: list[list[str | int | float | None]]).
"""
import csv
import html
import io
import json
import re
import zipfile

from sh_platform.context_docs.reader import Refusal, _guard_office_zip, _part, _xlsx_cells, ext_of

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLUMNS = 200
MAX_CELLS = 2_000_000   # rows x columns, counted while reading
MAX_JSON_DEPTH = 32
TOO_BIG = "That file has more data than can be read here. Please send a smaller one."
KINDS = ("xlsx", "csv", "json")
NOT_READ = "That file could not be read as a table. Please check it opens in Excel and try again."


def _width(row) -> int:
    return sum(1 for c in row if c not in (None, ""))


def _col_index(ref: str) -> int:
    n = 0
    for ch in ref.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _number(text: str):
    try:
        f = float(text)
    except ValueError:
        return text
    return int(f) if f.is_integer() and not re.search(r"[.eE]", text) else f


def xlsx_rows(data: bytes) -> list[list]:
    """The first sheet as rows of cell values (text, int or float, None for an empty cell)."""
    _guard_office_zip(data, ".xlsx")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            raise Refusal("That workbook contains macros, which are never run here. Please save it without macros.")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for si in _part(z, "xl/sharedStrings.xml").decode("utf-8", "ignore").split("</si>")[:-1]:
                shared.append(html.unescape("".join(re.findall(r"<t\b[^<>]*>([^<]*)</t>", si.split("<si>")[-1]))))
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
        if not sheets:
            raise Refusal(NOT_READ)
        out: list[list] = []
        total = 0
        for seg in _part(z, sheets[0]).decode("utf-8", "ignore").split("</row>")[:-1]:
            m = re.search(r"<row\b[^<>]*(?<!/)>", seg)
            if not m:
                continue
            cells: dict[int, object] = {}
            for pos, (attrs, body) in enumerate(_xlsx_cells(seg[m.end():])):
                ref = re.search(r'\br="([A-Za-z]+)\d+"', attrs)
                at = _col_index(ref.group(1)) if ref else pos
                v = re.search(r"<v>([^<]*)</v>", body)
                if 't="s"' in attrs:
                    val = shared[int(v.group(1))] if v and v.group(1).isdigit() and int(v.group(1)) < len(shared) else None
                elif 't="inlineStr"' in attrs:
                    val = html.unescape("".join(re.findall(r"<t\b[^<>]*>([^<]*)</t>", body)))
                elif v is None:
                    val = None
                elif 't="str"' in attrs or 't="e"' in attrs:
                    val = html.unescape(v.group(1))
                elif 't="b"' in attrs:
                    val = v.group(1) == "1"
                else:
                    val = _number(v.group(1))  # ponytail: a date stored as a serial number stays a number; read style ids if that bites
                if val not in (None, "") and at < MAX_COLUMNS:
                    cells[at] = val
            if cells:
                out.append([cells.get(i) for i in range(max(cells) + 1)])
                total += len(out[-1])
            if len(out) > MAX_ROWS + 10 or total > MAX_CELLS:
                raise Refusal(TOO_BIG)
    return out


def _text(data: bytes) -> str:
    if b"\0" in data[:4096]:
        raise Refusal(NOT_READ)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Refusal(NOT_READ)


def csv_rows(data: bytes) -> list[list]:
    text = _text(data)
    try:
        delim = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    out, cells = [], 0
    try:
        for r in csv.reader(io.StringIO(text, newline=""), delimiter=delim):
            cells += len(r)
            if cells > MAX_CELLS or len(out) > MAX_ROWS + 10:
                raise Refusal(TOO_BIG)
            if any(c.strip() for c in r):
                out.append([c.strip() for c in r])
    except csv.Error:
        raise Refusal(NOT_READ) from None
    return out


def _too_deep(text: str) -> bool:
    """True when brackets nest deeper than MAX_JSON_DEPTH (strings skipped). Checked before parsing, so a hostile file costs one pass."""
    depth, in_str, esc = 0, False, False
    for ch in text:
        if in_str:
            in_str, esc = (not (ch == '"' and not esc)), (ch == "\\" and not esc)
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def json_rows(data: bytes) -> tuple[list[str], list[list]]:
    """A list of objects, or `{"rows": [...]}`, or an object holding exactly one list of objects."""
    if _too_deep(_text(data)):
        raise Refusal("That JSON file is nested too deeply to read. It should hold a flat list of records.")
    try:
        doc = json.loads(_text(data))
    except (ValueError, RecursionError):
        raise Refusal(NOT_READ) from None
    if isinstance(doc, dict):
        pool = [doc["rows"]] if isinstance(doc.get("rows"), list) else list(doc.values())
        lists = [v for v in pool if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
        doc = lists[0] if len(lists) == 1 else None
    if not isinstance(doc, list) or not doc or not all(isinstance(x, dict) for x in doc):
        raise Refusal("That JSON file should hold a list of records, one object per row.")
    header = list(dict.fromkeys(k for r in doc for k in r))[:MAX_COLUMNS]
    if len(doc) * len(header) > MAX_CELLS:
        raise Refusal(TOO_BIG)
    flat = lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v  # noqa: E731
    return header, [[flat(r.get(k)) for k in header] for r in doc]


def _banner(row) -> bool:
    return _width(row) < 2 or str(row[0] or "").strip().lower().startswith("illustrative")


def read_table(filename: str, data: bytes) -> tuple[list[str], list[list]]:
    kind = ext_of(filename)
    if kind not in KINDS:
        raise Refusal("Please send an Excel (.xlsx), CSV or JSON file.")
    if len(data) > MAX_FILE_BYTES:
        raise Refusal(f"That file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB. Please send a smaller one.")
    if not data:
        raise Refusal("That file is empty.")
    if kind == "json":
        header, rows = json_rows(data)
    else:
        if kind == "xlsx" and not data.startswith(b"PK"):
            raise Refusal("That file is not an Excel workbook, whatever its name says.")
        raw = xlsx_rows(data) if kind == "xlsx" else csv_rows(data)
        while len(raw) > 1 and _banner(raw[0]):
            raw.pop(0)  # the banner, and any title line above the header
        if len(raw) < 2:
            raise Refusal("That file has a header but no rows.")
        header, rows = [str(h or "").strip() for h in raw[0]][:MAX_COLUMNS], raw[1:]
    if not any(header) or "" in header or len(set(header)) != len(header):
        raise Refusal("The first row should name every column once. Please check the header row.")
    if len(rows) > MAX_ROWS:
        raise Refusal("That file has more rows than can be read here.")
    return header, [(r + [None] * len(header))[:len(header)] for r in rows]
