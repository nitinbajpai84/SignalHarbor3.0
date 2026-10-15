"""Node and edge vocabulary of the company graph (spec section 2).

Reshaped from the earlier product's context models (node/relationship tuples, a checked constructor) and the earlier spine's edge endpoint
rules (`EDGE_TYPES: type -> (allowed from-types, allowed to-types)`). Industry-specific types are dropped; every node carries a provenance
list, an optional `restricted_to` and the room it grew in. Stdlib only.
"""
from __future__ import annotations

NODE_TYPES: tuple[str, ...] = ("Problem", "Pain", "Signal", "Lever", "Measure", "Term", "Process", "Step", "System", "Source", "Field",
                               "Person", "Team", "Rule", "Risk", "Decision", "PlanItem")
ROOMS: tuple[str, ...] = ("wall", "define", "truth", "build", "consume")
_CARD = ["Problem", "Pain", "Signal", "Lever"]
# edge type -> (allowed from-types, allowed to-types)
EDGE_TYPES: dict[str, tuple[list[str], list[str]]] = {
    "raised_by": (_CARD, ["Person"]),
    "measured_by": (["Problem"], ["Measure"]),
    "defined_as": (["Measure"], ["Term"]),
    "fed_by": (["Measure"], ["Source"]),
    "uses": (["Source"], ["Field"]),
    "produced_by": (["Source"], ["Process"]),
    "step_of": (["Step"], ["Process"]),
    "owned_by": (["Measure", "Source", "Process", "System"], ["Person"]),
    "governed_by": (["Measure", "Source"], ["Rule"]),
    "at_risk": (["Measure"], ["Risk"]),
    "decided_by": (["Risk", "Problem", "Decision"], ["Decision", "Person"]),  # Risk/Problem -> Decision -> Person
    "moves": (["Lever"], ["Measure"]),
    "watches": (["Signal"], ["Measure"]),
    "planned_in": (["Source"], ["PlanItem"]),
    "member_of": (["Person"], ["Team"]),
}
STRUCTURAL = frozenset({"measured_by", "fed_by"})  # kept, labelled restricted, when one end is a silhouette


Guard = tuple[list[str], dict]  # (names allowed, {name: [account ids]}); None on a node means open


def meet(*guards: "Guard | None") -> "Guard | None":
    """Several limits on one node: only the names on all of them (a closed list with nobody named stays closed). None when none apply."""
    gs = [g for g in guards if g is not None]
    if not gs:
        return None
    names = set(gs[0][0])
    for g in gs[1:]:
        names &= set(g[0])
    return sorted(names), {k: v for g in gs for k, v in g[1].items()}


class Graph:
    """Nodes by id and edges by (from, to, type). An edge with a missing end, or ends the rules do not allow, is refused (False).
    `gate(label)` is called for every node but a Person or Team and returns the extra limit a name like it carries (the profile's own rule)."""

    def __init__(self, gate=None) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple[str, str, str], dict] = {}
        self.gate = gate

    def guard(self, id: str) -> "Guard | None":
        n = self.nodes.get(id)
        return None if n is None or n["restricted_to"] is None else (n["restricted_to"], n["restricted_bound"] or {})

    def node(self, id: str, type: str, label: str, provenance: list[dict], room: str, guard: "Guard | None" = None) -> str:
        if type not in NODE_TYPES or room not in ROOMS:
            raise ValueError(f"unknown node type {type!r} or room {room!r}")
        if self.gate and type not in ("Person", "Team"):
            guard = meet(guard, self.gate(label))
        old = self.nodes.get(id)
        if old:  # one node per id: provenance adds up, limits add up
            old["provenance"] += [p for p in provenance if p not in old["provenance"]]
            guard = meet(self.guard(id), guard)
            old["restricted_to"], old["restricted_bound"] = (guard[0], guard[1] or None) if guard else (None, None)
            return id
        self.nodes[id] = {"id": id, "type": type, "label": label, "provenance": list(provenance), "restricted_to": guard[0] if guard else None,
                          "restricted_bound": (guard[1] or None) if guard else None, "room": room}
        return id

    def edge(self, a: str, b: str, type: str, provenance: list[dict]) -> bool:
        if type not in EDGE_TYPES:
            raise ValueError(f"unknown edge type {type!r}")
        if a not in self.nodes or b not in self.nodes:
            return False
        src, dst = EDGE_TYPES[type]
        if self.nodes[a]["type"] not in src or self.nodes[b]["type"] not in dst:
            return False
        self.edges.setdefault((a, b, type), {"from": a, "to": b, "type": type, "provenance": list(provenance)})
        return True
