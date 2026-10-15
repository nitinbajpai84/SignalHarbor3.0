"""Areas (departments and operations areas) kept in the profile: `areas.<id>.{name, kind, status, from}` as provenance cells, and
`people.<pid>.areas` (list of area ids) as a person's tag. Pack areas are suggestions and are never stored until the admin accepts them.
`store.DEPTH` has no "areas" entry yet, so areas are written here with `store.cell` inside `store.mutate` (the same lock and write);
a person's tag goes through `store.set_cell`, so an agent's guess never replaces an admin's tag."""
import re
from typing import Any

from sh_platform.profile import store, view

KINDS = ("department", "operations_area")
ACCEPTED = "Accepted from suggestions"
SETTINGS = "_settings"  # the company's own switch (titles_private) sits beside the areas, never listed as one
_SLUG = re.compile(r"[^a-z0-9]+")


class AreaRefusal(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _v(item: dict, key: str) -> Any:
    c = item.get(key)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _same(a: str, b: str) -> bool:
    return re.sub(r"\s+", "", a.lower()) == re.sub(r"\s+", "", b.lower())


def _items(doc: dict) -> dict:
    return {k: a for k, a in (doc.get("areas") or {}).items() if k != SETTINGS}


def listing(doc: dict) -> list[dict]:
    return [{"id": k, "name": _v(a, "name"), "kind": _v(a, "kind"), "status": _v(a, "status") or "active", "from": _v(a, "from") or ""}
            for k, a in _items(doc).items()]


def titles_private(doc: dict) -> bool:
    return _v((doc.get("areas") or {}).get(SETTINGS, {}), "titles_private") is True


def _prov(by: str, src: str) -> dict:
    return {"mark": "stated", "by": by, "from": src}


def _put(doc: dict, aid: str, field: str, value: Any, by: str, src: str) -> None:
    doc.setdefault("areas", {}).setdefault(aid, {})[field] = store.cell(value, _prov(by, src))


def _clean(name: Any, kind: Any) -> tuple[str, str]:
    name = _name(name)
    if kind not in KINDS:
        raise AreaRefusal("Pick Department or Operations area.")
    return name, kind


def _name(name: Any) -> str:
    name = " ".join(str(name or "").split())
    if not name or len(name) > 60:
        raise AreaRefusal("Give the area a name of up to 60 characters.")
    return name


def _free_name(doc: dict, name: str, besides: str | None = None) -> None:
    if any(k != besides and _same(name, str(_v(a, "name") or "")) for k, a in _items(doc).items()):
        raise AreaRefusal("There is already an area with that name.")


def _add(doc: dict, aid: str, name: str, kind: str, by: str, src: str) -> None:
    _free_name(doc, name)
    for f, val in (("name", name), ("kind", kind), ("status", "active"), ("from", src)):
        _put(doc, aid, f, val, by, src)


def add(plane, name: Any, kind: Any, by: str) -> str:
    name, kind = _clean(name, kind)

    def change(doc: dict) -> str:
        base = _SLUG.sub("-", name.lower()).strip("-") or "area"
        aid, n = base, 2
        while aid in (doc.get("areas") or {}):
            aid, n = f"{base}-{n}", n + 1
        _add(doc, aid, name, kind, by, "Added by the company admin")
        return aid
    return store.mutate(plane, change)


def _existing(doc: dict, aid: str) -> dict:
    a = _items(doc).get(aid)
    if a is None:
        raise AreaRefusal("We could not find that.", 404)
    return a


def rename(plane, aid: str, name: Any, by: str) -> None:
    name = _name(name)

    def change(doc: dict) -> None:
        _existing(doc, aid)
        _free_name(doc, name, besides=aid)
        _put(doc, aid, "name", name, by, "Renamed by the company admin")  # the id stays, so past intents keep matching
    store.mutate(plane, change)


def set_status(plane, aid: str, status: str, by: str) -> None:
    def change(doc: dict) -> None:
        _existing(doc, aid)
        _put(doc, aid, "status", status, by, "Retired by the company admin" if status == "retired" else "Brought back by the company admin")
    store.mutate(plane, change)


def suggestions(pack, doc: dict) -> list[dict]:
    """Pack areas not yet taken by the company. An industry with no pack, or a pack with no areas file, gives none."""
    try:
        rows = pack.section("areas")["areas"]
    except (KeyError, TypeError):
        return []
    have = _items(doc)
    return [{"id": r["id"], "name": r["name"], "kind": r["kind"], "note": r.get("note", "")} for r in rows
            if r.get("id") not in have and not any(_same(r["name"], str(_v(a, "name") or "")) for a in have.values())]


def accept(plane, pack, ids: Any, by: str) -> list[str]:
    if not isinstance(ids, list) or not ids:
        raise AreaRefusal("Tick at least one suggestion.")

    def change(doc: dict) -> list[str]:
        offered = {r["id"]: r for r in suggestions(pack, doc)}
        if any(i not in offered for i in ids):
            raise AreaRefusal("That suggestion is not available.")
        for i in dict.fromkeys(ids):
            _add(doc, i, offered[i]["name"], offered[i]["kind"], by, ACCEPTED)
        return list(dict.fromkeys(ids))
    return store.mutate(plane, change)


def add_teams(plane, teams: Any, by: str) -> list[str]:
    """Lens's line "Add them?": each team value becomes an active department. A name already taken is skipped."""
    if not isinstance(teams, list) or not teams:
        raise AreaRefusal("Pick at least one team.")
    return [add(plane, t, "department", by) for t in teams if t in lens_lines(store.load(plane))["teams"]]


def set_titles_private(plane, on: bool, by: str) -> None:
    store.mutate(plane, lambda doc: _put(doc, SETTINGS, "titles_private", bool(on), by, "Set by the company admin"))


def people_areas(person: dict) -> list[str]:
    v = _v(person, "areas")
    return [str(i) for i in v] if isinstance(v, list) else []


def tag(plane, pid: str, area_ids: Any, by: str) -> None:
    """The admin's tag: `people.<pid>.areas`, stated. Only active areas, and only ones that exist."""
    if not isinstance(area_ids, list) or not all(isinstance(i, str) for i in area_ids):
        raise AreaRefusal("Pick areas from the list.")

    def change(doc: dict) -> None:
        if pid not in doc["people"]:
            raise AreaRefusal("We could not find that.", 404)
        active = {r["id"] for r in listing(doc) if r["status"] == "active"}
        mine = set(people_areas(doc["people"][pid]))
        if any(i not in active and i not in mine for i in area_ids):  # a retired tag already held may stay
            raise AreaRefusal("Pick areas from the list.")
        store.set_cell(doc, f"people.{pid}.areas", list(dict.fromkeys(area_ids)), _prov(by, "Tagged by the company admin"))
    store.mutate(plane, change)


def reach(doc: dict, picked: list[str]) -> dict:
    """How many sign-in accounts a pick reaches: linked people whose tags meet it. No people in the file: not known."""
    if not doc["people"]:
        return {"count": None, "missing": "No people file read yet"}
    pick = set(picked)
    n = sum(1 for p in doc["people"].values() if isinstance(_v(p, "account_id"), str) and pick & set(people_areas(p)))
    return {"count": n, "missing": None}


def lens_lines(doc: dict) -> dict:
    """What Lens may offer, from each person's team: team values no area is named after, and tags for people whose team is an active area.
    Drafts only; the admin accepts. A person who already has a tag is never offered one."""
    areas = listing(doc)
    teams: dict[str, str] = {}
    tags = []
    for pid, p in doc["people"].items():
        team = str(_v(p, "team") or _v(p, "department") or "").strip()
        if not team:
            continue
        hit = next((a for a in areas if _same(a["name"] or "", team)), None)
        if hit is None:
            teams.setdefault(view.norm(team), team)
        elif hit["status"] == "active" and not people_areas(p):
            tags.append({"pid": pid, "name": _v(p, "name") or pid, "area_id": hit["id"], "area_name": hit["name"]})
    return {"teams": list(teams.values()), "tags": tags}


def areas_of_account(doc: dict, account_id: str | None) -> frozenset[str]:
    """A viewer's areas: the tags of the person linked to the account (`people.<pid>.account_id`)."""
    if not account_id:
        return frozenset()
    return frozenset(a for p in doc["people"].values() if _v(p, "account_id") == account_id for a in people_areas(p))
