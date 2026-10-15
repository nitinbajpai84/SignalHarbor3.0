"""`read(plane, viewer)`: the profile as one person may see it.

The governance rules are copied from module 2 (modules/m2_baseline/domain/catalogue.py `allows`, `ROLE_PASS`, `_kpi_guard`,
`_restricted_kpi`; domain/worklist.py `may_see`), not imported, so the kernel stays under the modules:
- a field rule that is personal, "not sure" (or nothing said) or sensitive is seen only by the people named in `may_see`, and by the company
  admin; where nobody is named yet, only the company admin sees it;
- a name bound to account ids when it was named is matched on the account, otherwise on the display name; a name another account also
  carries (`shared_name`) does not match by name alone;
- a field's own extra list (`field_may_see`) adds a limit; the company admin and the sponsor always pass it;
- account ids stay on the server.
A restricted area is seen by the same rule over its own `may_see`. What sits in a hidden area (a person of that team, a system, a figure,
a sample, a document marked restricted) is dropped, not shown as a stub: nobody learns it exists.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sh_platform.plane import CompanyPlane
from sh_platform.profile import store

ROLE_PASS = frozenset({"\0sponsor", "\0company_admin"})  # in a guard: these roles pass too (catalogue.ROLE_PASS)
ADMIN = "company_admin"


@dataclass(frozen=True)
class Viewer:
    name: str
    roles: frozenset[str]
    shared_name: bool = False  # another account of the company has the same display name
    account_id: str | None = None


def norm(text: Any) -> str:
    return " ".join(str(text).lower().split())


def allows(guard: frozenset[str], viewer: Viewer) -> bool:
    """Named people pass. Where nobody has been named yet, only the company admin passes, so someone can name them (catalogue.allows)."""
    if any(g[1:] in viewer.roles for g in guard if g.startswith("\0")):
        return True
    if not guard:
        return ADMIN in viewer.roles
    return norm(viewer.name) in guard and not viewer.shared_name


def _key(text: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _v(item: dict, key: str) -> Any:
    c = item.get(key)
    return c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None


def _names(value: Any) -> frozenset[str]:
    return frozenset(norm(n) for n in (value if isinstance(value, list) else []) if str(n).strip())


def _passes(guard: frozenset[str], bound: dict, viewer: Viewer) -> bool:
    """`allows`, plus worklist.may_see's account binding: a name bound to accounts is matched on the account id, never the display name.
    A-069: the company admin passes only while nobody is named (so the lists can be set up); once a name is on the list the admin is like anyone else.
    Role markers still pass for the roles they name."""
    if any(g[1:] in viewer.roles for g in guard if g.startswith("\0")):
        return True
    names = {g for g in guard if not g.startswith("\0")}
    if not names:
        return ADMIN in viewer.roles and not guard
    me = norm(viewer.name)
    return any(viewer.account_id in bound[k] if k in bound and viewer.account_id else k == me and k not in bound and not viewer.shared_name
               for k in names)


def _bound(item: dict) -> dict:
    b = _v(item, "may_see_accounts")
    return {norm(k): list(v) for k, v in b.items()} if isinstance(b, dict) else {}


def sees_area(item: dict, viewer: Viewer) -> bool:
    return _passes(_names(_v(item, "may_see")), _bound(item), viewer)


SHUT_SOURCE = {"restricted": True, "label": "A restricted source"}


def sees_source(item: dict, viewer: Viewer) -> bool:
    """Module 2's source rule (catalogue.guards): personal "No" is open; "Yes" is for the named people and the company admin (where nobody is
    named, the admin alone); "Not sure" is open unless a names list is given, then the named, the sponsor and the admin. A source marked
    restricted is closed like a "Yes"."""
    said = norm(_v(item, "personal_data") or "")
    names = _names(_v(item, "may_see")) if isinstance(_v(item, "may_see"), list) else _names(re.split(r"[,;]", str(_v(item, "may_see") or "")))
    if said.startswith("yes") or _v(item, "restricted") is True:
        return _passes(names, _bound(item), viewer)
    if said.startswith("not sure") and names:
        return _passes(names | ROLE_PASS, _bound(item), viewer)
    return True


def sees_rule(item: dict, viewer: Viewer) -> bool:
    """catalogue._restricted_kpi / _kpi_guard: an open field (personal "no", not sensitive) is seen by all; anything else by the named."""
    personal = _v(item, "personal") or "not_sure"
    if personal == "no" and not _v(item, "sensitive"):
        return _passes_own(item, viewer)
    return _passes(_names(_v(item, "may_see")), _bound(item), viewer) and _passes_own(item, viewer)


def _passes_own(item: dict, viewer: Viewer) -> bool:
    own = _names(_v(item, "field_may_see"))
    return not own or _passes(own | ROLE_PASS, _bound(item), viewer)


def _plain(item: dict) -> dict:
    return {k: v for k, v in item.items() if k != "may_see_accounts"}


def read(plane: CompanyPlane, viewer: Viewer) -> dict:
    """The profile for this viewer. Raises nothing for an empty profile."""
    doc = store.raw(plane)
    gov = doc["governance"]
    areas = {k: a for k, a in gov["restricted_areas"].items()}
    hidden_areas = {norm(_v(a, "area") or k) for k, a in areas.items() if not sees_area(a, viewer)}
    hidden_areas.discard("")
    admin = ADMIN in viewer.roles

    def open_item(item: dict) -> bool:
        return not ({norm(_v(item, "area") or ""), norm(_v(item, "team") or "")} & hidden_areas)

    area_names = {_key(x) for k, a in areas.items() if not sees_area(a, viewer) for x in (k, _v(a, "area") or "") if x} - {""}
    # a system named like a hidden area is shut too, even with no area or team cell
    shut = {k: s for k, s in doc["systems"].items() if open_item(s) and (not sees_source(s, viewer) or {_key(k), _key(_v(s, "name") or "")} & area_names)}
    shut_names = {_key(x) for k, s in shut.items() for x in (k, _v(s, "name") or "") if x}
    # a measure or file named like a field rule or restricted area this viewer may not see is closed to them too (same normalised names)
    shut_names |= {_key(x) for k, r in gov["field_rules"].items() if not sees_rule(r, viewer) for x in (k, _v(r, "field") or "") if x}
    shut_names |= {_key(x) for k, a in areas.items() if not sees_area(a, viewer) for x in (k, _v(a, "area") or "") if x}
    shut_names.discard("")

    def tied(item: dict) -> bool:
        return any(_key(_v(item, f) or "") in shut_names for f in ("system", "measure", "name", "area")) or _key(Path(str(_v(item, "file") or "")).stem) in shut_names

    out = {"version": doc.get("version", 1)}
    for section in ("people", "systems", "reported_figures", "samples", "interviews", "constraints"):
        out[section] = {k: _plain(i) for k, i in doc[section].items() if open_item(i) and not (section in ("reported_figures", "samples") and tied(i))}
    # an interview by a person the viewer may not see goes with the person (anonymous notes have their own key, no person behind it)
    out["interviews"] = {k: i for k, i in out["interviews"].items() if k not in doc["people"] or k in out["people"]}
    ordinal = {k: n for n, k in enumerate(sorted(shut), 1)}  # restricted-1, restricted-2 ...: no hash of the name, nothing to guess against
    out["systems"] = {(f"restricted-{ordinal[k]}" if k in shut else k): (SHUT_SOURCE if k in shut else v) for k, v in out["systems"].items()}
    out["systems"].update({f"restricted-{n}": SHUT_SOURCE for k, n in ordinal.items()})
    for k, p in out["people"].items():
        if not admin:
            p.pop("account_id", None)
            p.pop("account_suggestion", None)
    out["cards"] = _cards(doc, areas, viewer)
    out["governance"] = {"restricted_areas": {k: _plain(a) for k, a in areas.items() if sees_area(a, viewer)},
                         "field_rules": {k: _plain(r) for k, r in gov["field_rules"].items() if sees_rule(r, viewer)}}
    hidden = {d.get("id") for i in doc["inputs"].values() for d in _list(i.get("documents")) if d.get("id") and ((d.get("restricted") and not admin) or _key(Path(str(d.get("name") or "")).stem) in shut_names)}  # a file flagged restricted has no list, so only the admin passes it; one named like a closed measure or source goes too, admin or not (A-069)
    out["inputs"] = {}
    for g, item in doc["inputs"].items():
        item = dict(item)
        for key in ("documents", "results"):  # not even a restricted file's name, in the list of files or in what Lens did with them
            c = item.get(key)
            if hidden and isinstance(c, dict) and isinstance(c.get("value"), list):
                item[key] = {**c, "value": [d for d in c["value"] if d.get("id") not in hidden]}
        out["inputs"][g] = item
    return _scrub(out, hidden)


SILHOUETTE = "A sealed card"
_QS = ("q1", "q2", "q3", "q4")


def _cards(doc: dict, areas: dict, viewer: Viewer) -> dict:
    """A sealed card is whole only to a viewer who may see every restricted area its words name (and at least one); otherwise a silhouette.
    An anonymous card never carries its `author` (the `anon-*` key) for anyone, the admin included."""
    named = [(_key(x), a) for k, a in areas.items() for x in (k, _v(a, "area") or "") if _key(x)]
    out = {}
    for k, c in doc.get("cards", {}).items():
        if _v(c, "sealed") is True:
            words = f" {_key(' '.join(str(_v(c, q) or '') for q in _QS))} "
            hit = [a for n, a in named if f" {n} " in words]
            if not hit or not all(sees_area(a, viewer) for a in hit):
                out[k] = {"id": k, "lane": _v(c, "lane"), "sealed": True, "silhouette": SILHOUETTE}
                continue
        out[k] = {f: v for f, v in c.items() if not (f == "author" and _v(c, "anonymous") is True)}
    return out


def cards_summary(plane: CompanyPlane, viewer: Viewer) -> dict:
    """Cards per lane and in all, over the same per-viewer filter as `read`."""
    gov = store.raw(plane)["governance"]["restricted_areas"]
    cards = _cards(store.raw(plane), gov, viewer)
    lanes = {"tracking": 0, "missing": 0, "watch": 0, "levers": 0}
    for c in cards.values():
        lane = c["lane"] if c.get("sealed") is True and "silhouette" in c else _v(c, "lane")
        lanes[lane] = lanes.get(lane, 0) + 1
    return {"lanes": lanes, "total": len(cards)}


NOBODY = Viewer("", frozenset())  # no name, no role: every restricted area, source, measure, sample and figure is closed to it


def read_unrestricted(plane: CompanyPlane) -> dict:
    """The profile as a reader on no restricted list sees it: every restricted item is dropped. The same for everyone, so it is safe to keep."""
    return read(plane, NOBODY)


def _list(cell: Any) -> list[dict]:
    return [d for d in cell["value"] if isinstance(d, dict)] if isinstance(cell, dict) and isinstance(cell.get("value"), list) else []


HIDDEN_SOURCE = "a restricted document"


def _scrub(node: Any, hidden: set) -> Any:
    """A cell whose `ref` points at a document the viewer may not see shows "a restricted document" as `from` and loses its `ref`."""
    if isinstance(node, dict):
        if "mark" in node and isinstance(node.get("ref"), dict) and node["ref"].get("id") in hidden:
            return {**{k: v for k, v in node.items() if k != "ref"}, "from": HIDDEN_SOURCE}
        return {k: _scrub(v, hidden) for k, v in node.items()}
    return [_scrub(v, hidden) for v in node] if isinstance(node, list) else node
