"""Triage per KPI (M2-02): the four things the business may not know, each a provenance value, and the owners (M2-04).
Pure functions over a KPI record in the shape of contracts/SHARED.md."""
from modules.m2_baseline.domain.provenance import unknown

ROLES = ("business", "data", "process")
FOUR = ("definition", "owner", "producer", "gathered")


def owner_summary(kpi: dict) -> dict:
    """The one "owner" of the triage row: the first known of the business, data and process owner, else unknown."""
    for role in ROLES:
        o = kpi["owners"][role]
        if o["mark"] != "unknown":
            return o
    return unknown("Lens", "no owner nominated yet")


def triage(kpi: dict) -> dict:
    """{definition, owner, producer, gathered} (each a provenance value) and `unknown`, the names of those still
    unknown: unknown is a valid answer and is listed, never shown as known."""
    four = {"definition": kpi["definition"], "owner": owner_summary(kpi),
            "producer": kpi["producer"], "gathered": kpi["gathered"]}
    return {**four, "unknown": [k for k in FOUR if four[k]["mark"] == "unknown"]}


def missing_owners(kpi: dict) -> list[str]:
    """The roles with no named person. A KPI with a missing owner shows "no owner" and cannot be signed (M2-04)."""
    return [r for r in ROLES if kpi["owners"][r]["mark"] == "unknown"]


GROUPS = (("problems", "Problems to solve now"), ("pain_points", "Pain points"), ("future_signals", "What to track in future"),
          ("levers", "Levers for what-if"))


def charter_groups(charter: dict | None) -> list[dict]:
    """The signed charter's four lists, each {key, heading, items: [{id, title, priority, kind}]}. `problems` (read_charter) holds the
    intents and the pain points, told apart by `kind`; future signals and levers are context, never baselined as problems."""
    c = charter or {}
    kind = lambda p: p.get("kind") or "problem"  # noqa: E731
    rows = {"problems": [p for p in c.get("problems", []) if kind(p) == "problem"], "pain_points": [p for p in c.get("problems", []) if kind(p) == "pain_point"],
            "future_signals": c.get("future_signals") or [], "levers": c.get("levers") or []}
    return [{"key": k, "heading": h, "items": [{"id": p["id"], "title": p["title"], "priority": p.get("priority"), "kind": kind(p)} for p in rows[k]]}
            for k, h in GROUPS]


def charter_facts(charter: dict | None) -> list[str]:
    """What the charter says to watch in future and which levers it changes, as plain sentences Lens may rely on."""
    return [f"{label}: {p['title']}." for key, label in (("future_signals", "Charter: to track in future"), ("levers", "Charter lever for what-if"))
            for p in (charter or {}).get(key, [])]
