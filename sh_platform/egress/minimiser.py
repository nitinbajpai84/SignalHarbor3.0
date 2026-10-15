"""Guard 2: build the smallest payload. Question, allowed facts, optional short summary; nothing else."""
from sh_platform.egress.aggregates import SuppressedFigures, filter_facts
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.rows import json_findings

MAX_SUMMARY_CHARS = 1200


def minimise(question: str, facts, allowed_fields, summary: str | None = None):
    """Return (payload, suppressed). A fact is kept only if its label is in `allowed_fields` and
    its group is big enough; the rest are remembered in `suppressed` so the gateway can block
    their values being quoted in text. Raw rows or a table in the question are refused; a
    summary over MAX_SUMMARY_CHARS is refused, never cut."""
    code = json_findings(question)[0]
    if code:
        raise EgressBlocked(code)
    if summary is not None and len(summary) > MAX_SUMMARY_CHARS:
        raise EgressBlocked("summary_too_long")
    code = json_findings(summary)[0] if summary is not None else None
    if code:
        raise EgressBlocked(code)
    kept = []
    dropped = SuppressedFigures()
    for f in facts:
        if not isinstance(f, dict):
            raise EgressBlocked("bad_fact")
        if "label" not in f:
            raise EgressBlocked("raw_rows")  # a record, not a fact
        if f["label"] in allowed_fields:
            kept.append(f)
        else:
            dropped.add(f)
    allowed, suppressed = filter_facts(kept)
    for f in dropped.facts:
        suppressed.add(f)
    payload: dict = {"question": question, "facts": allowed}
    if summary is not None:
        payload["summary"] = summary
    return payload, suppressed
