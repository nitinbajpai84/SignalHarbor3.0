"""The owner questionnaire (M2-10, M2-11) and the check of an answer. Every field comes back as a provenance value
(domain/provenance.py): stated, guessed or unknown. "I don't know" is a valid answer and keeps value null.
A list field (upstream, in_between, downstream) is one provenance value whose value is the list of hops; every hop names
a person or the word "Unknown" (M2-11: every hop has an owner or Unknown), may carry its `team` and its step `order`, and never
loses text: `what` and `step` are the same thing, and an unknown key is refused by name.
`sources` is a list of rows, one per system or file; each cell is its own provenance value."""
import copy
import hashlib
import re
from pathlib import Path

import yaml

from modules.m2_baseline.domain.provenance import MARKS, prov, unknown

CONTRACT = Path(__file__).resolve().parent.parent / "contracts" / "questionnaire.yaml"
UNKNOWN_WHO = "Unknown"
BLANK = "not answered yet"
SAMPLE = "sample_doc_id"  # set by an upload, not by a question


class AnswerError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class Questionnaire:
    def __init__(self, raw: dict):
        self.raw = raw
        self.fields: dict[str, dict] = {f["key"]: f for f in raw["fields"]}
        self.limits: dict = raw["limits"]
        self.link_hours: int = raw["link"]["hours_valid"]
        self.reminder_days: list[int] = sorted(raw["reminders"]["days"])
        self.no_reply_days: int = raw["no_reply_days"]

    def public(self) -> dict:
        """What a screen needs to draw the form (the old single-text questions are not asked any more)."""
        return {"fields": [f for f in self.raw["fields"] if not f.get("legacy")], "marks": self.raw["marks"], "limits": self.limits}


_PARSED: dict[tuple, object] = {}  # (path, content hash) -> parsed YAML; holds the last file read


def _parse(path: Path):
    """Parse the contract once per change of the file: readiness asks for it per measure and per field, and parsing the
    YAML every time made one confirm on a 16-measure baseline take seconds. A change to the file is read again."""
    data = path.read_bytes()  # a small file: the hash of its bytes is the key, so an edit inside one mtime tick is still seen
    key = (str(path), hashlib.sha1(data).hexdigest())
    raw = _PARSED.get(key)
    if raw is None:
        raw = yaml.safe_load(data.decode("utf-8"))
        _PARSED.clear()
        _PARSED[key] = raw
    return copy.deepcopy(raw)  # each caller gets its own copy; nobody can change another's


def load_questionnaire(path: Path | None = None) -> Questionnaire:
    p = Path(path).resolve() if path else CONTRACT  # CONTRACT is already resolved
    raw = _parse(p)  # a private copy of the cached parse, so one caller's change never reaches another
    if not (isinstance(raw, dict) and {"link", "reminders", "no_reply_days", "limits", "marks", "fields"} <= set(raw)):
        raise ValueError("the questionnaire contract is not valid")
    return Questionnaire(raw)


def _text(value, cap: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnswerError("Please write an answer, or mark it as one you don't know.", field)
    return value.strip()[:cap]


def _order(value, q: Questionnaire, field: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = 0
    if not 1 <= n <= q.limits["hop_order"]:
        raise AnswerError(f"A step number is a whole number from 1 to {q.limits['hop_order']}.", field)
    return n


def _hops(value, spec: dict, q: Questionnaire, field: str) -> list[dict]:
    if not isinstance(value, list) or not value or len(value) > q.limits["hops"]:
        raise AnswerError(f"List between 1 and {q.limits['hops']} steps, or mark it as one you don't know.", field)
    keys = {part["key"] for part in spec["hop"]}
    text_key = next(k for k in ("what", "step") if k in keys)  # `what` and `step` are one thing: the words of the step
    out = []
    for n, h in enumerate(value, 1):
        if not isinstance(h, dict):
            raise AnswerError("Those steps could not be read. Please try again.", field)
        h = dict(h)
        if text_key not in h and any(k in h for k in ("what", "step")):
            h[text_key] = h.get("what", h.get("step"))
        bad = [k for k in h if k not in keys and k not in ("what", "step")]
        if bad:
            raise AnswerError(f"Step {n} in the {field.replace('_', ' ')} list: “{bad[0]}” is not something this kind of step can say. It can say {', '.join(p['key'] for p in spec['hop'])}.", field)
        if any(not isinstance(h.get(k), (str, type(None))) for k in ("who", "team", "what", "step")):
            raise AnswerError("Each step's who, team and what must be plain text.", field)
        hop = {}
        for part in spec["hop"]:
            k = part["key"]
            if k == "manual":
                hop[k] = h.get(k) is True
            elif k == "who":
                hop[k] = str(h.get(k) or "").strip()[:q.limits["hop_who_chars"]] or UNKNOWN_WHO  # nobody named says so
            elif k == "order":
                if (n := _order(h.get(k), q, field)) is not None:  # a step number or a team the owner did not give is left out
                    hop[k] = n
            elif k == "team":
                if team := str(h.get(k) or "").strip()[:q.limits["hop_who_chars"]]:
                    hop[k] = team
            else:
                hop[k] = str(h.get(k) or "").strip()[:q.limits["hop_what_chars"]]
        out.append(hop)
    return out


def _list_cell(value, q: Questionnaire, field: str) -> list[str]:
    items = re.split(r"[,;\n]", value) if isinstance(value, str) else value
    if not isinstance(items, list) or any(not isinstance(i, str) for i in items):
        raise AnswerError("Please give a short list of names, one after another.", field)
    return [i.strip()[:q.limits["item_chars"]] for i in items if i.strip()][:q.limits["list_items"]]


def _rows(value, spec: dict, q: Questionnaire, field: str, mark: str, by: str, source: str) -> list[dict]:
    """One row per system or file; each cell becomes a provenance value. A cell is a plain value (it takes the field's mark) or
    {value, mark}; blank or "unknown" is an unknown cell, which is allowed."""
    if not isinstance(value, list) or not value or len(value) > q.limits["source_rows"]:
        raise AnswerError(f"List between 1 and {q.limits['source_rows']} systems or files, or mark it as one you don't know.", field)
    cols = {c["key"]: c for c in spec["row"]}
    out = []
    for r in value:
        if not isinstance(r, dict):
            raise AnswerError("Those systems or files could not be read. Please try again.", field)
        bad = [k for k in r if k not in cols]
        if bad:
            raise AnswerError(f"“{bad[0]}” is not something a system or file can say. Use {', '.join(cols)}.", field)
        row = {}
        for key, col in cols.items():
            cell, cell_mark = r.get(key), mark
            if isinstance(cell, dict):
                cell_mark, cell = cell.get("mark", mark), cell.get("value")
                if cell_mark not in MARKS:
                    raise AnswerError("Say for each answer whether you are sure, it is a best guess, or you don't know.", field)
            if cell_mark == "unknown" or cell is None or (isinstance(cell, (str, list)) and not cell):
                row[key] = unknown(by, source)
            elif col["kind"] == "choice":
                if not isinstance(cell, str) or cell not in {c["value"] for c in col["choices"]}:
                    raise AnswerError(f"Please choose one of the answers offered for “{col['label']}”.", field)
                row[key] = prov(cell, cell_mark, by, source)
            elif col["kind"] == "list":
                items = _list_cell(cell, q, field)
                row[key] = prov(items, cell_mark, by, source) if items else unknown(by, source)
            else:
                row[key] = prov(_text(cell, q.limits["text_chars"], field), cell_mark, by, source)
        if row["name"]["mark"] == "unknown":
            raise AnswerError("Please name each system or file, or take the row out.", field)
        out.append(row)
    return out


def _summary(rows: list[dict], q: Questionnaire, mark: str, by: str, source: str) -> dict[str, dict]:
    """What a reader that knows only the old single questions sees: the names, the structure and the arrival, as text."""
    labels = {c["value"]: c["label"] for r in q.fields["sources"]["row"] if r["key"] == "frequency" for c in r["choices"]}
    shapes = {r["structure"]["value"] for r in rows if r["structure"]["mark"] != "unknown"}
    arrive = [f"{r['name']['value']}: " + ", ".join(x for x in (labels.get(r["frequency"]["value"], ""), r["sla"]["value"] or "") if x)
              for r in rows if r["frequency"]["mark"] != "unknown" or r["sla"]["mark"] != "unknown"]
    out = {"source": prov("; ".join(r["name"]["value"] for r in rows), mark, by, source)}
    if shapes:
        out["data_type"] = prov(shapes.pop() if len(shapes) == 1 else "both", mark, by, source)
    if arrive:
        out["arrival"] = prov("; ".join(arrive), mark, by, source)
    return out


def clean_answers(q: Questionnaire, given, by: str, source: str) -> dict[str, dict]:
    """The answered fields of one form as provenance values. `given` is {field: {value, mark}}; a field left out is not
    touched. Raises AnswerError (plain words) for an unknown field, a missing mark or a value that does not fit."""
    if not isinstance(given, dict):
        raise AnswerError("Those answers could not be read. Please try again.")
    out = {}
    for key, item in given.items():
        spec = q.fields.get(key)
        if spec is None:
            raise AnswerError("That question is not part of this form.", str(key))
        if not isinstance(item, dict) or item.get("mark") not in MARKS:
            raise AnswerError("Say for each answer whether you are sure, it is a best guess, or you don't know.", key)
        if item["mark"] == "unknown":
            out[key] = unknown(by, source)
            continue
        value = item.get("value")
        if spec["kind"] == "choice":
            if not isinstance(value, str) or value not in {c["value"] for c in spec["choices"]}:
                raise AnswerError("Please choose one of the answers offered.", key)
        elif spec["kind"] == "text":
            value = _text(value, q.limits["text_chars"], key)
        elif spec["kind"] == "rows":
            value = _rows(value, spec, q, key, item["mark"], by, source)
        else:
            value = _hops(value, spec, q, key)
        out[key] = prov(value, item["mark"], by, source)
    rows = out.get("sources")
    if rows and rows["mark"] != "unknown":  # the old single questions follow the rows, unless the caller answered them too
        out = {**_summary(rows["value"], q, rows["mark"], by, source), **out}
    elif rows:  # "I don't know" about the systems is an answer for the old questions too, not "not answered yet"
        out = {**{k: unknown(by, source) for k in ("source", "data_type", "arrival")}, **out}
    return out


def source_rows(answer: dict) -> list[dict]:
    """The systems or files of one answer, each cell a provenance value: its `sources` rows, or for an old answer its one
    free-text `source` as one row named from the text and marked guessed (the old data type, arrival and SLA ride along)."""
    rows = answer.get("sources")
    if isinstance(rows, dict) and rows.get("mark") != "unknown" and isinstance(rows.get("value"), list):
        return [r for r in rows["value"] if isinstance(r, dict) and isinstance(r.get("name"), dict)]
    old = answer.get("source")
    text = old.get("value") if isinstance(old, dict) and old.get("mark") != "unknown" else None
    if not (isinstance(text, str) and text.strip()):
        return []
    by = str(answer.get("owner_name") or "")
    row = {k: unknown(by, "old answer") for k in ("kind", "lands", "owner", "connection", "tables", "fields", "read_out", "personal")}
    return [{**row, "name": prov(text.strip(), "guessed", old.get("by") or by, old.get("from") or "old answer", old.get("at")),
             "structure": answer.get("data_type") or unknown(by, "old answer"), "frequency": answer.get("arrival") or unknown(by, "old answer"),
             "sla": answer.get("sla") or unknown(by, "old answer")}]


def with_blanks(record: dict, q: Questionnaire) -> dict:
    """The record with every field present: an unanswered one reads as unknown from "not answered yet", never as known.
    `unanswered` lists them so a screen can tell "I don't know" from "not asked yet"."""
    blanks = [k for k in (*q.fields, SAMPLE) if k not in record]
    return {**record, **{k: unknown(record.get("owner_name", ""), BLANK) for k in blanks}, "unanswered": blanks}
