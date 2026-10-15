"""Span's modelling knowledge (plan 3.5, requirement A): the technique pack, `pick` for a question, and the company's own decisions.

The pack (modelling_pack.yaml) is suggestion material, never company policy. Decisions live in company memory
(context/memory/span/company.json) as kind `decision`: depersonalised, figures dropped, never written back once a company
admin deleted the line (tombstone), and a person's edit is never overwritten (memory._merge).
"""
import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from sh_platform import memory
from sh_platform.jsonfile import lock_for
from sh_platform.memory import filters
from sh_platform.memory.api import tomb_hash
from sh_platform.memory.compact import fold
from sh_platform.plane import CompanyPlane
from sh_platform.profile import view

log = logging.getLogger(__name__)
PACK = Path(__file__).with_name("modelling_pack.yaml")
REQUIRED = ("id", "name", "what", "fits_when", "avoid_when", "keys", "effort", "signals")
MAX_PASSAGES = 3
AGENT = "span"
_COND = re.compile(r"^(not )?([a-z_]+)(?: (>=|<=|==|>|<) (-?\d+(?:\.\d+)?))?$")
_OPS = {">": float.__gt__, "<": float.__lt__, ">=": float.__ge__, "<=": float.__le__, "==": float.__eq__}
_FIGURE = re.compile(r"(?<!type )(?<![A-Za-z0-9])[$€£]?\d[\d,.]*")  # "type 2" names a technique; any other figure is dropped
_WORD = re.compile(r"[a-z0-9]{4,}")


@lru_cache(maxsize=1)
def load_pack() -> tuple[dict, ...]:
    entries = (yaml.safe_load(PACK.read_text(encoding="utf-8")) or {}).get("entries") or []
    for e in entries:
        missing = [k for k in REQUIRED if k not in e]
        if missing:
            raise ValueError(f"modelling pack entry {e.get('id')} lacks {missing}")
        for s in e["signals"]:
            if not _COND.match(s):
                raise ValueError(f"modelling pack entry {e['id']} has an unreadable signal: {s}")
    return tuple(entries)


def _facts(facts: dict | list | None) -> dict:
    """Facts as {name: value}; a list of {name|label, value} read-tool facts is accepted too."""
    if isinstance(facts, dict):
        return facts
    return {str(f.get("name") or f.get("label")): f.get("value") for f in facts or [] if isinstance(f, dict)}


def holds(signal: str, facts: dict) -> bool:
    neg, name, op, num = _COND.match(signal).groups()
    v = facts.get(name)
    if op is None:
        ok = bool(v)
    else:
        try:
            ok = v is not None and _OPS[op](float(v), float(num))
        except (TypeError, ValueError):
            ok = False
    return ok != bool(neg)


def passage(e: dict) -> dict:
    text = (f"{e['name']}: {e['what']} Fits when: {'; '.join(e['fits_when'])}. Avoid when: {'; '.join(e['avoid_when'])}. "
            f"Keys: {e['keys']} Effort: {e['effort']}." + (f" {e['notes']}" if e.get("notes") else ""))
    return {"id": e["id"], "name": e["name"], "text": text}


def pick(question: str, facts: dict | list | None = None) -> list[dict]:
    """At most three passages: entries whose every signal holds come first (more signals, more specific), then word overlap."""
    f, words = _facts(facts), set(_WORD.findall(view.norm(question or "")))
    scored = []
    for i, e in enumerate(load_pack()):
        score = 10 * len(e["signals"]) if e["signals"] and all(holds(s, f) for s in e["signals"]) else 0
        score += len(words & set(_WORD.findall(view.norm(f"{e['id']} {e['name']} {e['what']}"))))
        if score:
            scored.append((-score, i, e))
    return [passage(e) for _, _, e in sorted(scored)[:MAX_PASSAGES]]


def decision_line(accepted: bool, technique: str, subject: str, reason: str) -> str:
    return f"Chose {technique} for {subject} because {reason}" if accepted else f"Declined {technique} for {subject}: {reason}"


def remember_decision(plane: CompanyPlane, text: str) -> bool:
    """Write one company decision for Span. False when it was not written (a quote, restricted or contact content, or tombstoned)."""
    text = filters.depersonalise(" ".join(_FIGURE.sub("", str(text or "")).split()), filters.person_names(plane))
    if not text or not filters.allowed(re.sub(r"\btype \d\b", "type", text), filters.restricted_terms(plane)):
        log.info("a span decision was not written: it failed the memory filters")
        return False
    path = memory._path(plane, AGENT, None)
    with lock_for(path):
        doc = memory.load(plane, AGENT)
        if tomb_hash(text) in {t.get("hash") for t in doc.get("deleted", [])}:
            log.info("a span decision was not written: a company admin deleted it before")
            return False
        memory._merge(doc["entries"], {"kind": "decision", "text": text, "conversation": "span decision"}, memory._now())
        doc["entries"] = fold(doc["entries"], doc.get("budget", memory.BUDGET))
        memory.save(plane, AGENT, None, doc)
    return True


def decisions(plane: CompanyPlane, topic: str = "") -> list[dict]:
    """Company decisions on this topic as [{text, at}], newest first, never people's names."""
    words, names = set(_WORD.findall(view.norm(topic or ""))), filters.person_names(plane)
    out = []
    for e in sorted(memory.load(plane, AGENT)["entries"], key=lambda e: str(e.get("updated_at")), reverse=True):
        text = filters.depersonalise(str(e.get("text") or ""), names)
        if text and (not words or words & set(_WORD.findall(view.norm(text)))):
            out.append({"text": text, "at": e.get("updated_at")})
    return out[:20]
