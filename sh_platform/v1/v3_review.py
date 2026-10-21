"""Confidence on every field read from a document, and the review queue (docs/v3/PROGRAM-GAPS.md W4 and W10 method 1; ASSUMPTIONS A60).
high   = a known layout read deterministically, or both models agree and every rule check passes.
medium = agreement (or a plain read) but no rule check ran.
low    = disagreement, a failed check, or a poor scan.
A field below the signed rule `review_confidence_min` (default high) is stored with review_status 'held': the figures' SQL leaves 'held' out, like
'rejected', until a person confirms or corrects it. A correction is also saved as a regression case in <plane>/v3/corrections.jsonl."""
import json
import threading

from sh_platform.v1 import wh

RANK = {"low": 0, "medium": 1, "high": 2}
RULE = "review_confidence_min"
LOCK = threading.Lock()


def score(known: bool = False, agree: bool | None = None, checks_ok: bool | None = None, picture: bool = False) -> str:
    """known: read by rules from a known layout. agree: the second model agreed (None = not asked). checks_ok: the rule checks (None = none ran)."""
    if picture or agree is False or checks_ok is False:
        return "low"
    return "high" if known or (agree and checks_ok) else "medium"


def minimum(plane) -> str:
    """The signed rule's threshold; high when no version is signed."""
    try:
        with wh.connect(plane, read_only=True) as con:
            r = con.execute("select v.parameters from rule_versions v join business_rules b on b.id = v.business_rule_id where b.rule_code = ? "
                            "and v.approval_status = 'approved' order by v.version_number desc limit 1", [RULE]).fetchone()
        got = json.loads(r[0]).get("min") if r and r[0] else None
    except Exception:  # noqa: BLE001 - no rule table or no rule yet: the default
        got = None
    return got if got in RANK else "high"


def status_for(plane, confidence: str) -> str:
    return "confirmed" if RANK.get(confidence, 0) >= RANK[minimum(plane)] else "held"


def _fp_path(plane):
    return plane.path("v3", "review_layouts.json")


def remember_layout(plane, ids: list[str], fingerprint: str) -> None:
    with LOCK:
        p = _fp_path(plane)
        m = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        m.update({i: fingerprint for i in ids})
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(m), encoding="utf-8")


def queue(plane) -> list[dict]:
    """The held fields, oldest first: what Harbor read, where on the page and the quoted line."""
    with wh.connect(plane, read_only=True) as con:
        cur = con.execute("select f.id, f.field_name, f.value_text, f.currency, f.page_number, f.line_number, f.confidence, d.title "
                          "from extracted_fields f left join documents d on d.id = f.document_id where f.review_status = 'held' order by f.id")
        rows = cur.fetchall()
    quotes = _quotes(plane)
    return [{"id": str(i), "field": n, "reading": t or "", "currency": c, "page": p, "line": ln, "confidence": cf, "document": d or "", "quote": quotes.get(str(i), "")}
            for i, n, t, c, p, ln, cf, d in rows]


def _quotes(plane) -> dict:
    p = plane.path("v3", "review_quotes.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def remember_quotes(plane, quotes: dict) -> None:
    with LOCK:
        p = plane.path("v3", "review_quotes.json")
        m = _quotes(plane)
        m.update(quotes)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(m), encoding="utf-8")


def _num(text):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(text).replace(",", "").strip())
    except InvalidOperation:
        return None


def resolve(plane, field_id: str, person: str, value: str | None = None) -> dict:
    """Confirm (value None) or correct a held field: the person's name and time are kept and the field is released. Raises KeyError when it is not held."""
    with wh.connect(plane) as con:
        r = con.execute("select field_name, value_text, document_id from extracted_fields where id = ? and review_status = 'held'", [field_id]).fetchone()
        if not r:
            raise KeyError(field_id)
        name, was, doc = r
        u = con.execute("select id from users where display_name = ? limit 1", [person]).fetchone()  # reviewed_by is the person's user id
        who = str(u[0]) if u else None
        if value is None:
            con.execute("update extracted_fields set review_status = 'confirmed', reviewed_by = ?, reviewed_at = ? where id = ?", [who, wh.now(), field_id])
        else:
            n = _num(value)
            con.execute("update extracted_fields set review_status = 'corrected', reviewed_by = ?, reviewed_at = ?, corrected_value_text = ?, value_text = ?, "
                        "value_numeric = coalesce(?, value_numeric) where id = ?", [who, wh.now(), value, value[:255], n, field_id])
    _log(plane, {"field_id": field_id, "field": name, "status": "confirmed" if value is None else "corrected", "by": person, "at": wh.now().isoformat()})
    out = {"id": field_id, "field": name, "status": "confirmed" if value is None else "corrected", "by": person}
    if value is not None and value != was:
        save_correction(plane, field_id, name, was, value, person, doc)
    return out


def _log(plane, row: dict) -> None:
    """Who checked which field and when (the name, as the users table may not hold the person)."""
    with LOCK:
        p = plane.path("v3", "review_log.jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")


def save_correction(plane, field_id, name, wrong, right, person, doc) -> None:
    """A regression case for later tests to replay: the field, the wrong value, the right value and the layout it came from."""
    fp = (json.loads(_fp_path(plane).read_text(encoding="utf-8")) if _fp_path(plane).is_file() else {}).get(field_id, "")
    row = {"field": name, "wrong": wrong, "right": right, "layout": fp, "document": str(doc), "field_id": field_id, "by": person, "at": wh.now().isoformat()}
    with LOCK:
        p = plane.path("v3", "corrections.jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
