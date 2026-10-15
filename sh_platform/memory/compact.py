"""Compaction: older entries fold into one digest when a memory passes its budget. Deterministic, no model, never invents."""
import logging

log = logging.getLogger(__name__)
KEEP = 5
LINE = 160  # ponytail: plain truncation of each folded line; a model summary is MEM-2's, and may replace this


def size(entries: list[dict]) -> int:
    return sum(len(e["text"]) for e in entries)


def fold(entries: list[dict], budget: int) -> list[dict]:
    """Keep the newest KEEP agent entries and every person edit; fold the older agent entries (and any old digest) into one `digest`."""
    if size(entries) <= budget:
        return entries
    agent = sorted((e for e in entries if e.get("by") != "person"), key=lambda e: e["updated_at"], reverse=True)
    older = agent[KEEP:]
    if not older:
        return entries
    mine = [e for e in entries if e.get("by") == "person" or e in agent[:KEEP]]
    room = max(budget - size(mine), 0)
    text = " | ".join(e["text"][:LINE] if e["kind"] == "digest" else f"[{e['kind']}] {e['text'][:LINE]}" for e in reversed(older))
    prov = [p for e in older for p in e.get("from", [])]
    digest = {"id": "digest", "kind": "digest", "text": text[:room] or text[:LINE], "from": prov,
              "updated_at": max(e["updated_at"] for e in older), "by": "agent"}
    log.info("memory compacted: %d entries into one digest", len(older))
    return [*mine, digest]
