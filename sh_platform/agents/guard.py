"""Number-to-fact guard: every figure in an answer must equal a recorded fact, else it is replaced.

Rules (documented limits):
- A number counts if it equals a fact value in sign and size (digits, thousands commas, decimals, percent sign).
  "-1,200" does not trace to +1200. Facts must be recorded in the form they are stated: 12% does not trace to
  0.12.
- A percentage and a count are not told apart: "12%" and "12" are the same figure, so a percentage can trace to a
  count fact of 12 (and the other way round). Known limit; the fact's label is not read.
- Facts whose group_size is missing, not an integer, or under 5 are never a source.
- Ignored (never replaced): numbers that also appear in the question; ids that are whole tokens of 1-3 capitals
  or a capital plus 1-2 digits, a hyphen, then 1-4 digits (D-013, P1-02, A-001; not Sales-4500, USD4500, x99 or
  T1000, which are checked); full dates (ISO, dd/mm/yyyy, "3 March 2025", "March 3, 2025");
  Q1-Q4, H1-H2 and FY2026 labels; list ordinals, meaning digits followed by "." or ")" at the start of a line
  (so a line starting "99. items" reads as list number 99 and is ignored, a known limit).
- A plain 4-digit number from 1900 to 2100 is a year only in a date context (after in, since, until, FY, Q1-Q4
  or a month name) AND when the next word is not a count or unit: not one of units/cases/orders/customers/items/
  people/users/accounts, and not a lowercase word ending in "s" (a plural noun) unless it is a
  month, a weekday or a short function word (is, was, has, as, this, his, its, us, does, thus). Otherwise it is
  checked like any figure ("grew by 2000 units", "in 1999 cases", "March 2000 orders").
- Round 5: the value of a JSON reply's "name", "title", "label" or "code" is a label, never a stated figure ("Cash break over 5k").
- r7: the figure names a JSON reply lists under "kpis", "figures" or "unplaced" are names; in a JSON reply's "sql", 0, 1 and a digit glued
  to a word (an alias ps2) are code. Every other number in the SQL is checked.
- Brackets give no exemption: "[99]" is checked.
- AQ1: also ignored: ids made of a lowercase prefix and a hex part with a digit (prj-84d783f2), words joined by "_" that hold a digit
  (custodian_note_r1), file names (note_r1.txt), ISO date-times, column types (varchar(255)), and a day with a month but no year (9 Sep,
  Oct 9). "Sales-4500" and "sales-4500" are still checked (a 4-digit part is not an id). A clock time ("11:40") is checked: it passes
  when a record or a tool result stated it (the loop counts figures written in a tool's sentences).
- LQ-11: a number written as a word ("one trade", "three tables") is checked like digits when it counts something this run's own tools
  talked about: zero to twenty or "a single", followed by a word the tools used (a tool said "trades +0", so "one trade" is a claim about
  trades; "two options" is not checked when no tool spoke of options). "No one", "one of", "one more" are never checked. Words past twenty
  are out of scope. Derived totals count only if recorded as a fact.
- SS-1: a figure is tied to what it counts. A figure found only inside a tool's own sentences carries the words after it ("351 rows",
  "1 row returned"); when the answer's figure is followed by a word too, one of the next three words on either side must be the same
  (singular or plural), else the figure is replaced ("4 entities" when the tool said "4 tables"). A labelled fact or a tool figure with no
  word after it matches any word.
- KP-2: a JSON reply's "sow_patch" and "process_steps" are North's drafted brief lines, and the caller checks each line whole (i6_chat.ungrounded
  leaves out a line holding a figure that neither the person, the files, the context nor a tool stated). The guard leaves them alone: before
  this it blanked a number inside the sentence ("Retain the result for not available yet years", "ready by not available yet:not available yet").
"""
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sh_platform.agents.groups import group_ok

NOT_AVAILABLE = "not available yet"
_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_MONTH = (r"(?i:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
          r"|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_NUM = re.compile(r"(?:(?<![\w.])[-−])?" + _AMOUNT)
# AQ1 (ER-07, SPM-3, SS-5, LQ-4): identifiers, file names, clock times, column types and a day with its month are not figures. Before
# this the guard rewrote digits inside them: "prj-not available yetd...", "last load 2026-10-09 not available yet:...", "varchar(not
# available yet)", "custodian_note_rnot available yet.txt".
_ID_SKIP = (r"|(?<![\w-])[a-z]+(?:-[a-z]+)*-(?=[0-9a-f]*\d)[0-9a-f]{6,}(?:-[0-9a-f]+)*(?![\w-])"   # prj-84d783f2, tr-north-0a880dbf-357909fb
            r"|(?<!\w)(?=\w*_)(?=\w*\d)\w+"                                                     # cash_2026_09, custodian_note_r1
            r"|(?<![\w.])[\w-]+\.(?i:txt|csv|pdf|xlsx?|json|docx?|md|eml|msg|pptx?)\b"            # custodian_note_r1.txt
            r"|\b[a-z]+\(\d+(?:,\s*\d+)?\)"                                                    # varchar(255), decimal(18,2)
            r'|"(?:name|title|label|code)"\s*:\s*"(?:[^"\\]|\\.)*"'                            # a JSON reply's name or label is not a stated figure ("Cash break over 5k")
            r'|"(?:kpis?|figures?|unplaced)"\s*:\s*\[(?:\s*"(?:[^"\\]|\\.)*"\s*,?)*\s*\]')      # r7: figure names a design lists ("Calls due within 7 days")
# r7: in a JSON reply's "sql", 0 and 1 (coalesce(x, 0), nullif(n, 0), limit 1) and a digit glued to a name (an alias ps2) are code, not figures; any
# other number in the SQL is still checked, so a threshold the intent does not state is still blanked (and the plan check refuses that SQL)
_SQL_VALUE = re.compile(r'"sql"\s*:\s*"((?:[^"\\]|\\.)*)"')
_DRAFT_KEY = re.compile(r'"(?:sow_patch|process_steps)"\s*:\s*')


def _draft_spans(text: str) -> list[tuple[int, int]]:
    """KP-2: where a JSON reply's drafted brief lines are; a reply cut short (no whole value) gets no exemption."""
    out = []
    for m in _DRAFT_KEY.finditer(text):
        try:
            out.append((m.end(), json.JSONDecoder().raw_decode(text, m.end())[1]))
        except ValueError:
            continue
    return out


_BLANKED = re.compile(r"(?:\s+(?:for|by|of|in|at|to|over|under|within|after|before|every|about|around))?\s+" + re.escape(NOT_AVAILABLE)
                      + r"(?:\s*[:.,]\s*" + re.escape(NOT_AVAILABLE) + r")*(?:\s+(?!and\b|or\b)[a-z]+)?", re.I)


def unblank(text) -> str:
    """A line an older guard blanked mid-sentence, said without the number ("Retain the result for not available yet years" -> "Retain the result")."""
    t = str(text or "")
    return re.sub(r"\s{2,}", " ", _BLANKED.sub("", t)).strip() if NOT_AVAILABLE in t else t
_TOKEN = re.compile(
    r"(?P<skip>\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?!\d)"
    r"|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+" + _MONTH + r"\.?,?\s+\d{4}\b"
    r"|\b" + _MONTH + r"\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+" + _MONTH + r"\b"                                  # 9 Sep, 3rd March
    r"|\b" + _MONTH + r"\.?\s+\d{1,2}(?:st|nd|rd|th)?(?![\d,.]*\d)\b"                  # Oct 9
    + _ID_SKIP +
    r"|(?<![\w-])(?:[A-Z]{1,3}|[A-Z]\d{1,2})-\d{1,4}(?![\w-])|\b[QH][1-4]\b|\bFY\d{2,4}\b)"
    r"|(?P<num>(?:(?<![\w.])[-−])?" + _AMOUNT + r"%?)")
_DATE_CONTEXT = re.compile(
    r"(?:\b(?:in|since|until)\s+|\bFY\s*|\bQ[1-4]\s+|\b" + _MONTH + r"\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?)$",
    re.IGNORECASE)


_COUNT_NOUNS = {"units", "cases", "orders", "customers", "items", "people", "users", "accounts"}
_NOT_PLURAL = {"is", "was", "has", "as", "this", "his", "its", "us", "does", "thus", "mondays", "tuesdays",
               "wednesdays", "thursdays", "fridays", "saturdays", "sundays"}
_NEXT_WORD = re.compile(r"\s+([A-Za-z]+)")


def _counts_something(after: str) -> bool:
    m = _NEXT_WORD.match(after)
    if not m:
        return False
    w = m.group(1)
    if w.lower() in _COUNT_NOUNS:
        return True
    return w.islower() and w.endswith("s") and w not in _NOT_PLURAL


@dataclass
class GuardResult:
    text: str
    replaced: int = 0
    missing: list[str] = field(default_factory=list)
    kinds: list[dict] = field(default_factory=list)  # SS-5: per replaced figure its kind and the word it counted, never the value

    @property
    def ok(self) -> bool:
        return self.replaced == 0


_MONEY_BEFORE = re.compile(r"(?:\$|£|€|\bUSD|\bSGD|\bEUR|\bGBP)\s*$")
_MONEY_AFTER = re.compile(r"^\s*(?:USD|SGD|EUR|GBP|million|billion|bn\b|[km]\b)", re.IGNORECASE)
_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+\S", re.MULTILINE)


# earlier talk (the model's own past replies included) and memory are never a source: a figure the model made up once must not pass the next time
_NOT_SOURCES = frozenset({"earlier_in_this_chat", "memory", "remembered", "recall", "warning", "turns"})


def context_facts(context) -> list[dict]:
    """The figures the agent was given in its context (a count of tables, a limit): sources like a fact, with the words after each.
    Money and percentages in the context are not: a company money figure must come from a tool."""
    out: list[dict] = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k not in _NOT_SOURCES:
                    walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            for m in _TOKEN.finditer(v):
                tok = m.group("num")
                if tok is None or tok.endswith("%") or _MONEY_BEFORE.search(v[:m.start()]) or _MONEY_AFTER.match(v[m.end():]):
                    continue
                if (val := _value(tok)) is not None:
                    out.append({"label": "text", "noun": " ".join(_WORDS.findall(v[m.end():m.end() + 40])[:3]), "value": str(val),
                                "group_size": 5})

    walk(context)
    return out


def _value(raw) -> Decimal | None:
    m = _NUM.search(str(raw))
    try:
        return Decimal(m.group().replace(",", "").replace("−", "-")) if m else None
    except InvalidOperation:
        return None


def _sources(facts: list[dict]) -> dict[Decimal, set]:
    """value -> the words each source said it counts ("" for a labelled fact or a figure with no word after it: any word fits)."""
    out: dict[Decimal, set] = {}
    for f in facts:
        if group_ok(f.get("group_size")):
            v = _value(f.get("value"))
            if v is not None:
                out.setdefault(v, set()).add(str(f.get("noun") or "") if f.get("label") == "text" else "")
    return out


_WORDS = re.compile(r"[A-Za-z]+")
_GLUE = frozenset("the a an of in on at to for and or by per with from this that these those our your their its new more".split())


def _stem(w: str) -> str:
    w = w.lower()
    return w[:-3] + "y" if w.endswith("ies") else w[:-2] if w.endswith(("ses", "xes")) else w[:-1] if w.endswith("s") and not w.endswith("ss") else w


SENTENCE_END = r"[.:]\s|[;!?\n]|\.$"
_SENTENCE_END = re.compile(SENTENCE_END)


def _nouns(text: str) -> list[str]:
    """The words right after a figure, up to three and never past the end of its sentence ("+0. There ..." counts nothing)."""
    text = _SENTENCE_END.split(text, maxsplit=1)[0]
    return [_stem(w) for w in _WORDS.findall(text)[:3] if w.lower() not in _GLUE]


def _fits(after: str, nouns: set) -> bool:
    """SS-1: the answer's figure means what a source's figure meant (one of the next words matches), or a source did not say."""
    mine = _nouns(after)
    if not mine or "" in nouns:
        return True
    return any(set(mine) & set(_nouns(n)) for n in nouns)


_NUMBER_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                             "sixteen seventeen eighteen nineteen twenty".split())}
_WORD_NUM = re.compile(r"(?<![\w-])(a single|" + "|".join(_NUMBER_WORDS) + r")\s+(?:(?:new|more|other|further|separate|additional|single)\s+)?([a-z]+)\b",
                       re.IGNORECASE)
_NOT_COUNT = re.compile(r"(?:\bno|\bany|\bsome|\bevery|\beach|\bthe)\s*$", re.IGNORECASE)
_IDIOM = frozenset("of another more or and way time point day thing moment by".split())


def check_numbers(answer_text: str, facts: list[dict], question: str = "", words: set | None = None) -> GuardResult:
    """`words`: the words this run's own tools used (LQ-11: "one trade" is checked when a tool talked about trades)."""
    sources = _sources(facts)
    asked = {_value(m.group()) for m in _NUM.finditer(question or "")}
    asked |= {Decimal(1 if w.lower() == "a single" else _NUMBER_WORDS[w.lower()]) for w, _ in _WORD_NUM.findall(question or "")}
    result = GuardResult(answer_text)
    listed = len(_LIST_LINE.findall(answer_text))
    sql_spans = [m.span(1) for m in _SQL_VALUE.finditer(answer_text)]  # a count of the items the reply lists itself ("four tables:" and four lines) is not an outside figure
    drafts = _draft_spans(answer_text) if "_patch" in answer_text or "process_steps" in answer_text else []

    def drafted(m: re.Match) -> bool:
        return any(a <= m.start() < b for a, b in drafts)

    def fix(m: re.Match) -> str:
        tok = m.group("num")
        if tok is None or drafted(m):
            return m.group()
        text = m.string
        line_start = text.rfind("\n", 0, m.start()) + 1
        ordinal = (not text[line_start:m.start()].strip() and tok.isdigit()
                   and text[m.end():m.end() + 1] in (".", ")"))
        year = (tok.isdigit() and len(tok) == 4 and 1900 <= int(tok) <= 2100
                and bool(_DATE_CONTEXT.search(text[:m.start()]))
                and not _counts_something(text[m.end():]))
        v = _value(tok)
        operand = text[:m.start()].rstrip()[-1:] in ("×", "*", "/", "÷")  # "share = a / b × 100": a formula's constant, not a company figure
        counts_items = bool(listed) and v == listed and not _MONEY_BEFORE.search(text[:m.start()])
        code = any(a <= m.start() < b for a, b in sql_spans) and (v in (0, 1) or (text[m.start() - 1:m.start()] or " ").isalnum())
        if v in asked or ordinal or year or operand or code or counts_items or (v in sources and _fits(text[m.end():m.end() + 40], sources[v])):
            return tok
        result.replaced += 1
        if tok not in result.missing:
            result.missing.append(tok)
        result.kinds.append({"kind": "percent" if tok.endswith("%") else "number", "counts": (_nouns(text[m.end():m.end() + 40]) or [""])[0][:24]})
        return NOT_AVAILABLE

    def fix_word(m: re.Match) -> str:
        word, noun = m.group(1), m.group(2).lower()
        n = 1 if word.lower() == "a single" else _NUMBER_WORDS[word.lower()]
        before = m.string[max(0, m.start() - 6):m.start()]
        tooled = bool(words) and (_stem(noun) in {_stem(w) for w in words})
        if noun in _IDIOM or _NOT_COUNT.search(before) or not tooled or drafted(m):
            return m.group()
        v = Decimal(n)
        if v in asked or (listed and v == listed) or (v in sources and _fits(m.group(2), sources[v])):
            return m.group()
        result.replaced += 1
        if word not in result.missing:
            result.missing.append(word)
        result.kinds.append({"kind": "number_in_words", "counts": _stem(noun)[:24]})
        return NOT_AVAILABLE + m.group()[len(word):]

    text = _TOKEN.sub(fix, answer_text)
    if drafts:  # the first pass changed lengths before the drafts (the "reply" comes first): find them again
        drafts[:] = _draft_spans(text)
    result.text = _WORD_NUM.sub(fix_word, text)
    return result
