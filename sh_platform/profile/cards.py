"""`record_card`: the one write path for the `cards` section (A-053). Only the wall routes call it.

A card is `{id, lane, q1..q4, sealed, anonymous, author | anon_key, from_interview, room, cluster, shelf}`. `q1..q4` are text (or
`{value, mark}`); the cells are written through `store.record`. The stored `author` is a person id, or an `anon-*` key when the card is
anonymous: the card in hand carries one of `author` / `anon_key`, never both. An anonymous card's provenance names nobody.
"""
from typing import Any, Mapping

from sh_platform.plane import CompanyPlane
from sh_platform.profile import store

LANES = ("tracking", "missing", "watch", "levers")
_Q = ("q1", "q2", "q3", "q4")
ANON = "anonymous"


def _check(card: Mapping[str, Any]) -> str:
    """Raises ValueError for a bad card; returns the value to store as `author`."""
    if card.get("lane") not in LANES:
        raise ValueError("a card sits in tracking, missing, watch or levers")
    for f in ("sealed", "anonymous"):
        if not isinstance(card.get(f), bool):
            raise ValueError(f"{f} must be true or false")
    author, key = card.get("author"), card.get("anon_key")
    if author and key:
        raise ValueError("a card has an author or an anonymous key, never both")
    if card["anonymous"]:
        if not (isinstance(key, str) and key.startswith("anon-")):
            raise ValueError("an anonymous card needs an anon-* key and no author")
        return key
    if not author or str(author).startswith("anon-") or key:
        raise ValueError("a named card needs an author")
    return str(author)


def record_card(plane: CompanyPlane, card: Mapping[str, Any], by: str = "the wall", source: str = "A card on the wall") -> None:
    """Validates and writes one card. `by` is who said it (ignored for an anonymous card: it is written as "anonymous")."""
    author = _check(card)
    store._path(f"cards.{card.get('id')}.lane")  # the id must be a plain profile segment
    prov = {"mark": "stated", "by": ANON if card["anonymous"] else by, "from": source}
    base = f"cards.{card['id']}"
    for f in ("lane", "sealed", "anonymous"):
        store.record(plane, f"{base}.{f}", card[f], prov)
    store.record(plane, f"{base}.author", author, prov)
    for f in (*_Q, "from_interview", "room", "cluster", "shelf"):
        v = card.get(f)
        if v is None:
            continue
        if isinstance(v, Mapping):
            store.record(plane, f"{base}.{f}", v.get("value"), {**prov, "mark": v.get("mark", "stated")})
        else:
            store.record(plane, f"{base}.{f}", v, prov)
