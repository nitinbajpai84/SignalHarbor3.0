"""IC-3c (A-054): the governed state of a measure, six provenance cells. Pure rules; the file is store/governed.py.
Declarative like a per-field check: each field is checked on its own, a field with nothing behind it is unknown, and `complete` is a
hard rule (all six stated), never a score."""
from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from modules.m2_baseline.domain import catalogue as C
from sh_platform.profile.store import cell as _cell  # the kernel's provenance cell helper (one shape everywhere)

FIELDS = ("owners", "classification", "may_see", "resolving", "affects", "review_date")
CLASSES = ("open", "personal", "sensitive", "restricted")  # weakest to strictest
ROLES = ("business", "data", "process")
QUARTER_DAYS = 91
REFUSED = "Only the person named for this part can confirm it. Ask them, or ask the sponsor to name them."


@lru_cache(maxsize=1)
def contract() -> dict:
    return yaml.safe_load((Path(__file__).resolve().parent.parent / "contracts" / "governed_state.yaml").read_text(encoding="utf-8"))


def _key(text: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def draft_cell(value: Any, source: str) -> dict:
    """An agent's guess; no value at all is an unknown."""
    return _cell(value, {"mark": "unknown" if value is None else "guessed", "by": "Lens", "from": source, "agent": "lens"})


def person_cell(value: Any, by: str) -> dict:
    return _cell(value, {"mark": "stated", "by": by, "from": "confirmed in Define"})


def blank() -> dict:
    return {f: draft_cell(None, "not drafted yet") for f in FIELDS}


def keep_old(old: Any, new: dict) -> bool:
    """store.set_cell's two rules: a guess never replaces a stated value; an agent never replaces a person's cell."""
    if not isinstance(old, dict) or old.get("mark") in (None, "unknown"):
        return False
    return (old["mark"] == "stated" and new["mark"] == "guessed") or (old.get("agent") is None and new.get("agent") is not None)


def is_complete(entry: dict) -> bool:
    return all(isinstance(entry.get(f), dict) and entry[f].get("mark") == "stated" for f in FIELDS)


def percentages(entries: list[dict]) -> dict:
    n = len(entries)

    def pct(count: int) -> int:
        return round(100 * count / n) if n else 0

    def stated(e: dict, f: str) -> bool:
        return e[f].get("mark") == "stated"
    return {"owned": pct(sum(stated(e, "owners") for e in entries)),
            "classified": pct(sum(stated(e, "classification") for e in entries)),
            "may_see_confirmed": pct(sum(stated(e, "may_see") for e in entries)),
            "sealed": pct(sum(stated(e, "classification") and e["classification"]["value"] != "open" and stated(e, "may_see") for e in entries))}


# ---- who confirms what ---------------------------------------------------------------------------------------------------------

def _v(item: dict, key: str) -> Any:
    c = (item or {}).get(key)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _is(viewer: C.Viewer, name: Any, account: Any = None) -> bool:
    if account and viewer.account_id:
        return account == viewer.account_id
    return bool(name) and C.norm(name) == C.norm(viewer.name) and not viewer.shared_name


def named_owner(kpi: dict, viewer: C.Viewer) -> bool:
    return any(_is(viewer, C.value_of(c), c.get("account_id")) for c in (kpi.get("owners") or {}).values() if isinstance(c, dict))


def head_of_data(profile: dict, viewer: C.Viewer) -> bool:
    people = (profile or {}).get("people") or {}
    return any(_v(p, "is_head_of_data") is True and _is(viewer, _v(p, "name"), _v(p, "account_id")) for p in people.values())


def _slot_names(kpi: dict, current: dict | None, role: str) -> set[str]:
    """Who a slot already holds: the governed cell's value and the work list's nominee (an empty business slot shows the process owner)."""
    cell = (current or {}).get("value") if isinstance((current or {}).get("value"), dict) and (current or {}).get("mark") != "unknown" else {}
    work = lambda r: C.value_of(c) if (c := (kpi.get("owners") or {}).get(r)) and isinstance(c, dict) and c.get("mark") != "unknown" else None  # noqa: E731
    return {C.norm(n) for n in (cell.get(role), work(role), work("process") if role == "business" else None) if n}


def _named_for(kpi: dict, current: dict | None, role: str, viewer: C.Viewer) -> bool:
    c = (kpi.get("owners") or {}).get(role) or {}
    said = (current or {}).get("value") if (current or {}).get("mark") == "stated" and isinstance((current or {}).get("value"), dict) else {}
    return (isinstance(c, dict) and c.get("mark") != "unknown" and _is(viewer, C.value_of(c), c.get("account_id"))) or _is(viewer, said.get(role))


def check_confirm(field: str, kpi: dict, profile: dict, viewer: C.Viewer, value: Any = None, current: dict | None = None) -> None:
    """Raises CatalogueError("forbidden", one plain sentence). The company admin role passes nothing for others (A-069).
    For owners, with the submitted `value` and the `current` governed cell: each slot that changes needs the person named for it, or the head of data."""
    if field not in FIELDS:
        raise C.CatalogueError("invalid", "That part of a measure's governance does not exist.")
    head = head_of_data(profile, viewer)
    ok = {"named_owner": named_owner(kpi, viewer), "head_of_data": head, "sponsor": "sponsor" in viewer.roles,
          "governance_lead": "approver" in viewer.roles or head}
    if not any(ok[w] for w in contract()["fields"][field]["confirmed_by"]):
        raise C.CatalogueError("forbidden", REFUSED)
    if field != "owners" or head or not isinstance(value, dict):
        return
    for role in ROLES:
        if role not in value:  # a slot left out keeps its current name (the store fills it), so it is not a change
            continue
        got = C.norm(value.get(role)) if isinstance(value.get(role), str) and value.get(role).strip() else None
        before = _slot_names(kpi, current, role)
        if (got in before if got else not before) or _named_for(kpi, current, role, viewer):
            continue
        raise C.CatalogueError("forbidden", f"Only the {role} owner named for this measure, or the head of data, can change the {role} owner.")


def clean(field: str, value: Any, stated: bool = False) -> Any:
    """A checked value. `stated` (a person's confirmation) also needs the one thing that makes the field mean something."""
    bad = C.CatalogueError("invalid", "That answer is not in a form this part accepts.")

    def text(v: Any) -> str:
        if not isinstance(v, str) or not v.strip() or len(v) > 120:
            raise bad
        return v.strip()
    if field == "owners":
        if not isinstance(value, dict) or set(value) - set(ROLES):
            raise bad
        got = {r: (text(value[r]) if value.get(r) is not None else None) for r in ROLES}
        if stated and not got["business"]:
            raise C.CatalogueError("invalid", "Please name the business owner.")
        return got
    if field == "classification":
        if value not in CLASSES:
            raise bad
        return value
    if field in ("may_see", "affects"):
        if not isinstance(value, list):
            raise bad
        return [text(v) for v in value]
    if field == "resolving":
        if not isinstance(value, dict) or set(value) - {"team", "target_week"}:
            raise bad
        week = value.get("target_week")
        if week is not None and (not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= 520):
            raise bad
        team = text(value["team"]) if value.get("team") is not None else None
        if stated and not team:
            raise C.CatalogueError("invalid", "Please name the team that will resolve it.")
        return {"team": team, "target_week": week}
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise bad from None


# ---- the lens draft: no model call ---------------------------------------------------------------------------------------------

def _list(v: Any) -> list[str]:
    return [str(x).strip() for x in (v if isinstance(v, list) else re.split(r"[,;]", str(v or ""))) if str(x).strip()]


def _names_hit(item: dict, key: str, texts: set[str]) -> bool:
    """A profile area or rule names the measure when its key or label sits inside the measure's name or one of its fields' names."""
    own = {_key(k) for k in (key, _v(item, "area"), _v(item, "field")) if k and _key(k)}
    return any(o in t or t in o for o in own for t in texts if t)


def _week(text: str) -> int | None:
    m = re.search(r"\bweek\s*(\d{1,3})\b", text, re.I)
    return int(m.group(1)) if m else None


def draft(kpi: dict, field_names: list[str], profile: dict, pack_kpis: list[dict], today: date) -> dict:
    """Six draft cells for one measure from what is already stored. `field_names` are the catalogue fields that feed it."""
    g, gov = kpi.get("governance") or {}, (profile or {}).get("governance") or {}
    name = str(kpi.get("name") or kpi.get("id"))
    texts = {_key(name)} | {_key(f) for f in field_names if _key(f)}
    areas = [a for k, a in (gov.get("restricted_areas") or {}).items() if _names_hit(a, k, texts)]
    rules = [r for k, r in (gov.get("field_rules") or {}).items() if _names_hit(r, k, texts)]
    out = {}
    owners = {r: C.value_of((kpi.get("owners") or {}).get(r)) or None for r in ROLES}
    out["owners"] = draft_cell(owners if any(owners.values()) else None, "the work list's owners")
    cls = "sensitive" if g.get("sensitive") else "open" if g.get("personal") == "no" else "personal"  # not sure counts as personal (catalogue rule)
    sources = ["the measure's own answers"]
    for r in rules:
        said = "sensitive" if _v(r, "sensitive") is True else "open" if _v(r, "personal") == "no" else "personal"
        cls = max(cls, said, key=CLASSES.index)
        sources.append("the profile's field rules")
    if areas:
        cls = "restricted"
        sources.append("the profile's restricted areas")
    out["classification"] = draft_cell(cls, ", ".join(dict.fromkeys(sources)))
    names = list(dict.fromkeys(_list(g.get("may_see")) + [n for x in areas + rules for n in _list(_v(x, "may_see"))]))
    out["may_see"] = draft_cell(names if names or cls == "open" else None, "the measure, the restricted areas and the field rules")
    boss = owners["business"]
    team = next((_v(p, "team") for p in ((profile or {}).get("people") or {}).values() if boss and _key(_v(p, "name")) == _key(boss) and _v(p, "team")), None)
    best = None
    for c in ((profile or {}).get("constraints") or {}).values():
        text = str(_v(c, "text") or "")
        if str(_v(c, "kind") or "").lower() == "deadline" and _week(text) and any(w and _key(w) in _key(text) for w in (name, team)):
            best = _week(text) if best is None else min(best, _week(text))
    out["resolving"] = draft_cell({"team": team, "target_week": best} if team or best else None, "the profile's people and deadlines")
    mine = next((p for p in pack_kpis if _key(p.get("name")) == _key(name)), None)
    by_id = {p.get("id"): p.get("name") for p in pack_kpis}
    down = [by_id.get(d.get("kpi"), d.get("kpi")) for d in (mine or {}).get("drives") or [] if isinstance(d, dict)]
    out["affects"] = draft_cell(down if mine else None, "the industry pack's dependencies")
    out["review_date"] = _cell((today + timedelta(days=QUARTER_DAYS)).isoformat(), {"mark": "guessed", "by": "Lens", "from": "default", "agent": "lens"})
    return out
