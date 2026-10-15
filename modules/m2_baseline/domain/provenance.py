"""Stated, guessed or unknown, with who said it and where it came from (M2-12). Every module 2 value is one of these."""
from datetime import datetime, timezone

MARKS = ("stated", "guessed", "unknown")


def prov(value, mark: str, by: str, source: str = "", at: str | None = None) -> dict:
    if mark not in MARKS:
        raise ValueError("mark must be stated, guessed or unknown")
    if mark == "unknown":
        value = None  # an unknown is never shown with a value that looks complete
    return {"value": value, "mark": mark, "by": by, "from": source,
            "at": at or datetime.now(timezone.utc).isoformat()}


def unknown(by: str = "Lens", source: str = "") -> dict:
    return prov(None, "unknown", by, source)
