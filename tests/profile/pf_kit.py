"""Shared test helpers for the profile tests (a uniquely named module: `conftest` clashes across test folders)."""
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILY, OTHER = "lakeside-family-office", "harbor-mutual"
PEOPLE = (b"Name,Role,Team,Email,Manager,Key role\n"
          b"Mei Tan,Head of finance,Finance,mei@example.test,,organiser\n"
          b"Sue Sponsor,Chair,Board,sue@example.test,,sponsor\n"
          b"Dan Data,Head of data,Data,dan@example.test,Mei Tan,head of data\n")
SYSTEMS = b"System,Kind,Owner,How it arrives,Frequency,Licence\nCustody feed,feed,Dan Data,daily file,daily,none\nPerformance workbook,spreadsheet,Mei Tan,email,monthly,\n"
GOV = b"Area,Field,Personal,Sensitive,Who may see\n,Pay,yes,yes,Mei Tan\nHR,,,,\n,Capital called,no,no,\n"
PACK = b"Measure,Figure,Unit,Period end,Where it came from\nSingle-issuer concentration,13.32,%,2026-09-30,\"Investment committee pack, page 4\"\n"
CONSTRAINTS = b"Kind,Detail\nlicence,Market data may not be stored outside the office\ninternet,Off\n"
SAMPLE = b"Val Date,Acct,Mkt Value\n2026-09-01,A1,100\n2026-09-02,A2,250\n"


class StubModel:
    """Stands in for the gateway-backed model client. Records every message list it is given."""

    def __init__(self, text: str = "none"):
        self.text, self.sent = text, []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        return type("Reply", (), {"text": self.text, "tool_calls": [], "outside": False})()

    @property
    def everything(self) -> str:
        return "\n".join(str(m) for call in self.sent for m in call)


def xlsx(rows: list[list]) -> bytes:
    """A one-sheet workbook with inline strings, enough for the stdlib reader."""
    def c(r, i, v):
        ref = f"{chr(65 + i)}{r + 1}"
        return f'<c r="{ref}"><v>{v}</v></c>' if isinstance(v, (int, float)) else f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    body = "".join(f'<row r="{r + 1}">{"".join(c(r, i, v) for i, v in enumerate(row))}</row>' for r, row in enumerate(rows))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet><sheetData>{body}</sheetData></worksheet>')
    return out.getvalue()
