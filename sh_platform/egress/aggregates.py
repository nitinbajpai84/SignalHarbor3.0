"""Under-five rule: a figure may leave only as a fact over a group of MIN_GROUP or more.

A held-back figure is caught by VALUE, not by spelling. In any outgoing text, after NFKC (so
full-width digits and superscripts count) and with zero-width characters removed, every numeric
token is read under the plausible readings (comma or dot as thousands mark or as decimal point;
spaces, thin spaces, no-break spaces, apostrophes, the right single quote, underscores and the
Arabic thousands mark as thousands marks; an exponent such as 1.234e3; hex 0x4d2, octal 0o2322
and binary 0b10011010010; each space-separated part on its own) and compared as a number,
ignoring the sign (so "down 50" matches -50, and 1234.0, 1234.00, 1 234, 1.234, 1'234 and 1.234e3
all match 1234). The fractional part of a decimal is not read as a separate number. A figure
followed by million/mn/m or thousand/k also matches a held-back value that rounds (or cuts) to it,
e.g. "1.23 million" for 1234567. Before matching, only these are removed: tokens that really exist
in the vault or this call's session (the caller passes them in, e.g. PERSON_002), and real calendar
dates written YYYY-MM-DD (month 1-12, a valid day). Time parts after a date (10:30:00.5, +02:00)
stay in the text and are matched like any other numbers.
Limits: a small held-back value such as 2 blocks any standalone 2 in the text, also the minutes in
"10:02", a version "1.2.3" read as 123, and each number of a phone number (fails closed). NOT
caught: number words ("twelve", "one thousand two hundred"), other languages' scale words,
"bn/billion", figures derived from the value (percentages, differences), Roman numerals, and
digits split by letters."""
import datetime
import math
import re
import unicodedata
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

MIN_GROUP = 5
_SHAPE = {"label", "value", "group_size"}
_SEP_CHARS = "    '’_٬"
_TOKEN = re.compile(
    r"0[xX][0-9a-fA-F]{1,40}|0[oO][0-7]{1,60}|0[bB][01]{1,200}|"
    r"\d(?:[\d.," + _SEP_CHARS + r"]{0,60}\d)?(?:[eE][-+]?\d{1,4})?(?![\d])")
_DATE = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?!\d)")
_SCALE_AFTER = re.compile(r"\s?(million|mn|m|thousand|k)\b", re.I)
_SCALES = {"million": 10**6, "mn": 10**6, "m": 10**6, "thousand": 10**3, "k": 10**3}
_SEP_SPLIT = re.compile("[" + re.escape(_SEP_CHARS) + "]+")


def is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fact_ok(f) -> bool:
    """Fail closed: wrong shape, non-number or non-finite value (NaN, inf), non-integer or small
    group all fail. A bool group_size (True) is rejected on purpose: True would count as 1."""
    return (isinstance(f, dict) and set(f) == _SHAPE and isinstance(f["label"], str)
            and is_number(f["value"]) and (isinstance(f["value"], int) or math.isfinite(f["value"]))
            and isinstance(f["group_size"], int)
            and not isinstance(f["group_size"], bool) and f["group_size"] >= MIN_GROUP)


def _dec(s: str):
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return abs(d) if d.is_finite() else None


def _readings(tok: str) -> set:
    """All plausible numbers a token can mean."""
    out = set()
    if tok[:2].lower() in ("0x", "0o", "0b") and len(tok) > 2:
        try:
            out.add(Decimal(int(tok, 0)))
        except ValueError:
            pass
        return out
    parts = [tok] + [p for p in _SEP_SPLIT.split(tok) if p]
    for p in parts:
        if len(p) > 70:
            continue
        mant, e, exp = re.match(r"([^eE]*)([eE]?)(.*)", p).groups()
        tail = (e + exp) if e else ""
        flat = _SEP_SPLIT.sub("", mant)
        cands = [
            flat.replace(",", ""),                      # 1,234.5 (comma thousands)
            flat.replace(".", "").replace(",", "."),    # 1.234,5 (dot thousands)
            re.sub(r"[.,]", "", flat),                  # every mark is a thousands mark
            flat.replace(",", "."),                     # comma is the decimal point
        ]
        for c in cands:
            if c.count(".") <= 1 and c.strip("."):
                d = _dec(c + tail)
                if d is not None:
                    out.add(d)
    return out


def _real_date(m) -> str:
    try:
        datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)  # not a calendar date: leave it to be matched as numbers
    return " "


def _clean(text: str, tokens=()) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u2212", "-")
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    if tokens:
        alt = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
        text = re.sub(r"(?<![A-Za-z0-9_])(?:" + alt + r")(?![A-Za-z0-9_])", " ", text)
    return _DATE.sub(_real_date, text)


class SuppressedFigures:
    """Values held back for one call. `appears_in(text)` is true if any is quoted in the text."""

    def __init__(self):
        self.facts: list = []
        self._values: set = set()

    def add(self, fact) -> None:
        self.facts.append(fact)
        v = fact.get("value") if isinstance(fact, dict) else None
        if is_number(v):
            try:
                d = _dec(repr(v))
            except ValueError:  # an integer too long to print
                d = None
            if d is not None:
                self._values.add(d)

    def add_figures(self, obj) -> None:
        """Hold back every number in a JSON object (not group_size or ids), at any depth."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k).lower()
                if key in ("group_size", "id") or key.endswith("_id"):
                    continue
                if is_number(v):
                    self.add({"label": str(k), "value": v})
                else:
                    self.add_figures(v)
        elif isinstance(obj, list):
            for x in obj:
                self.add_figures(x)

    def __len__(self) -> int:
        return len(self.facts)

    def appears_in(self, text: str, tokens=()) -> bool:
        if not self._values:
            return False
        text = _clean(text, tokens)
        for m in _TOKEN.finditer(text):
            readings = _readings(m.group(0))
            if readings & self._values:
                return True
            scale = _SCALE_AFTER.match(text, m.end())
            if scale and self._scaled_hit(readings, _SCALES[scale.group(1).lower()]):
                return True
        return False

    def _scaled_hit(self, readings: set, scale: int) -> bool:
        for shown in readings:
            places = Decimal(1).scaleb(min(shown.as_tuple().exponent, 0))
            for v in self._values:
                if v >= scale:
                    for mode in (ROUND_HALF_UP, ROUND_DOWN):
                        if (v / scale).quantize(places, rounding=mode) == shown:
                            return True
        return False


def filter_facts(facts) -> tuple[list, SuppressedFigures]:
    allowed, suppressed = [], SuppressedFigures()
    for f in facts:
        (allowed.append(f) if fact_ok(f) else suppressed.add(f))
    return allowed, suppressed
