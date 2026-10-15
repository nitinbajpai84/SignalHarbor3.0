"""Shared helpers for the interview tests (a uniquely named module: `conftest` clashes across test folders). Synthetic data only."""
from pathlib import Path

from sh_platform.profile import store

ROOT = Path(__file__).resolve().parents[2]
FAMILY, OTHER = "lakeside-family-office", "harbor-mutual"
PACK_LABEL = "Investment committee pack, page 4"


class StubModel:
    """Stands in for the gateway-backed model client: records every message list, replies from a queue (then 'none')."""

    def __init__(self, *replies: str):
        self.replies, self.sent = list(replies), []

    def complete(self, module_id, messages, tools=None):
        self.sent.append(messages)
        text = self.replies.pop(0) if self.replies else "TRIGGER: none"
        return type("Reply", (), {"text": text, "tool_calls": [], "outside": False})()

    @property
    def everything(self) -> str:
        return "\n".join(str(m) for call in self.sent for m in call)


def _agent(label: str, doc_id: str = "d1") -> dict:
    return {"mark": "stated", "by": "Lens", "agent": "lens", "from": label, "ref": {"kind": "document", "id": doc_id}}


def seed(plane) -> None:
    """A small profile: three people (Dan owns a system, Sue is the sponsor), two systems, one reported figure, one restricted area."""
    def put(path, value, prov):
        store.record(plane, path, value, prov)
    for pid, name, role, extra in (("aaron-lyle", "Aaron Lyle", "Head of exposure", {}), ("dan-data", "Dan Data", "Head of data", {}),
                                   ("sue-sponsor", "Sue Sponsor", "Chair", {"is_sponsor": True})):
        put(f"people.{pid}.name", name, _agent("People list", "p1"))
        put(f"people.{pid}.role", role, _agent("People list", "p1"))
        for k, v in extra.items():
            put(f"people.{pid}.{k}", v, _agent("People list", "p1"))
    put("systems.custody-feed.name", "Custody feed", _agent("Data landscape list", "s1"))
    put("systems.custody-feed.owner", "Dan Data", _agent("Data landscape list", "s1"))
    put("systems.custody-feed.lands", "as a daily file", _agent("Data landscape list", "s1"))
    put("systems.performance-workbook.name", "Performance workbook", _agent("Data landscape list", "s1"))
    f = "reported_figures.single-issuer-concentration@2026-09-30"
    for k, v in (("measure", "Single-issuer concentration"), ("figure", 13.32), ("unit", "%"), ("period_end", "2026-09-30")):
        put(f"{f}.{k}", v, _agent(PACK_LABEL))
    put("governance.restricted_areas.hr.area", "HR", _agent("Governance list", "g1"))
    put("governance.restricted_areas.hr.may_see", ["Mei Tan"], _agent("Governance list", "g1"))
    put("governance.field_rules.capital-called.field", "Capital called", _agent("Governance list", "g1"))
    put("governance.field_rules.capital-called.personal", "no", _agent("Governance list", "g1"))
