"""`GET /api/company/graph/node/{id}`: one node of the viewer's gated map with its trail, owner, steward, versions and commits (SHAPES 10, A-072).

Versions live in `graph/versions.json` `{node id: [{v, what, by, at, ref}]}`. `append_version` adds one; `record_versions_from_build(plane, old_doc, new_doc)`
diffs the graph before and after a rebuild. Nothing here shows a figure: names, links and dates only.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from modules.m2_baseline.store import governed as GS
from sh_platform.graph.build import _HEX, _newest_baseline, _t
from sh_platform.graph.hooks import rebuild_if_dirty
from sh_platform.graph.read import _sees, graph_for
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import CompanyPlane
from sh_platform.profile import store
from sh_platform.profile.api import _plane, _viewer
from sh_platform.profile.view import _names, _v

log = logging.getLogger(__name__)
router = APIRouter()
THE_RECORD = "Signal Harbor"
OLD_RECORD = "the record"  # what older rows carry as their author


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(plane: CompanyPlane, name: str, kind: type) -> object:
    try:
        d = read_json_strict(plane.path("graph", name), kind)
    except (OSError, ValueError):
        log.warning("a graph record could not be read")
        return kind()
    return d if d is not None else kind()


def append_version(plane: CompanyPlane, node_id: str, what: str, by: str, ref: str) -> dict:
    path = plane.path("graph", "versions.json")
    with lock_for(path):
        doc = _read(plane, "versions.json", dict)
        rows = doc.setdefault(node_id, [])
        row = {"v": len(rows) + 1, "what": what, "by": by, "at": _now(), "ref": ref}
        rows.append(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, doc)
    return row


def _and_more(names: list[str]) -> str:
    """"A", "A and B", "A, B and 3 more": up to two named, then a count."""
    names = list(dict.fromkeys(names))
    if len(names) <= 2:
        return " and ".join(names)
    return f"{names[0]}, {names[1]} and {len(names) - 2} more"


def _sentences(node_id: str, old_label: str, new_label: str, was: set, now: set, labels: dict[str, str], restricted: bool) -> str:
    """The plain sentence for one change: rename, owner, definition, what it is linked to or no longer linked to, who may see it."""
    out = []
    if old_label != new_label:
        out.append(f"Renamed from {old_label} to {new_label}")
    other = lambda e: e[1] if e[0] == node_id else e[0]  # noqa: E731
    gained, lost = sorted(now - was), sorted(was - now)
    for e in gained:
        if e[2] == "owned_by" and e[0] == node_id:
            out.append(f"Owner set to {labels.get(e[1], 'someone')}")
        elif e[2] == "defined_as" and e[0] == node_id:
            out.append("Defined in the baseline")
    rest = [e for e in gained if e[2] not in ("owned_by", "defined_as") or e[0] != node_id]
    if rest:
        out.append("Linked to " + _and_more([labels.get(other(e), "another item") for e in rest]))
    if lost:
        out.append("No longer linked to " + _and_more([labels.get(other(e), "another item") for e in lost]))
    if restricted:
        out.append("Who may see it changed")
    return "; ".join(out)


def record_versions_from_build(plane: CompanyPlane, old_doc: dict | None, new_doc: dict) -> int:
    """A version per node whose label, edge set or restriction changed between two graph documents; by Signal Harbor, ref the record that changed.
    Nothing is recorded without an old graph (the first build is not a change). Returns how many were appended."""
    if not old_doc or not old_doc.get("nodes"):
        return 0
    old = {n["id"]: n for n in old_doc["nodes"]}

    def edges(doc: dict) -> dict[str, set]:
        out: dict[str, set] = {}
        for e in doc.get("edges", []):
            for me in (e["from"], e["to"]):
                out.setdefault(me, set()).add((e["from"], e["to"], e["type"]))
        return out
    oe, ne, count = edges(old_doc), edges(new_doc), 0
    for n in new_doc["nodes"]:
        o = old.get(n["id"])
        if o is None:
            continue
        ref = next((p.get("from") for p in reversed(n.get("provenance") or []) if p.get("from")), THE_RECORD)
        labels = {x["id"]: x["label"] for x in (*old_doc["nodes"], *new_doc["nodes"])}
        what = _sentences(n["id"], o["label"], n["label"], oe.get(n["id"], set()), ne.get(n["id"], set()), labels,
                          o.get("restricted_to") != n.get("restricted_to"))
        if what:
            append_version(plane, n["id"], what, THE_RECORD, ref)
            count += 1
    return count


def plain_versions(rows: list, neighbours: list[str]) -> list[dict]:
    """The rows as a reader sees them: older bare texts ("Links changed", "Name changed") become sentences, "the record" becomes Signal
    Harbor, and consecutive rows with the same text on the same day fold into one."""
    link = "Linked to " + _and_more(neighbours) if neighbours else "Links updated"
    bare = {"Links changed": link, "Name changed": "Renamed", "Who may see it changed": "Who may see it changed"}
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        what = "; ".join(bare.get(w.strip(), w.strip()) for w in str(r.get("what") or "").split(";") if w.strip())
        what = what.replace(OLD_RECORD, "the baseline") or "Updated"
        by = THE_RECORD if r.get("by") in (OLD_RECORD, None, "") else r["by"]
        if out and out[-1]["what"] == what and _day(out[-1]["at"]) == _day(r.get("at")):
            continue
        out.append({**r, "what": what, "by": by})
    return [{**r, "v": i + 1} for i, r in enumerate(out)]


def steward(plane: CompanyPlane, accounts: list[dict]) -> str:
    """graph/steward.json name, else the profile person who is head of data, else the company admin's name."""
    named = _read(plane, "steward.json", dict).get("name")
    if named:
        return str(named)
    for p in store.raw(plane).get("people", {}).values():
        if _v(p, "is_head_of_data") is True and _t(p.get("name")):
            return _t(p["name"])
    return next((a["display_name"] for a in accounts if "company_admin" in a["roles"] and not a.get("disabled")), "")


def _day(at: object) -> str:
    """"22 Sep" from an iso time; "" when there is none."""
    try:
        d = datetime.fromisoformat(str(at))
    except ValueError:
        return ""
    return f"{d.day} {d:%b}"


def _read_rec(plane: CompanyPlane, folder: tuple[str, ...], rid: str) -> dict:
    """One module record by id (a hex name only, so an id never walks the plane)."""
    if not _HEX.fullmatch(rid):
        return {}
    try:
        d = read_json_strict(plane.path(*folder, f"{rid}.json"), dict)
    except (OSError, ValueError):
        log.warning("a module record could not be read for the node page")
        return {}
    return d or {}


def wall_name(plane: CompanyPlane, session: dict, charter_signed: bool, account_id: str | None, text: str) -> str:
    """A wall's topic or purpose is shown only to its organiser, a seat holder, or anyone once its charter is signed; otherwise "A wall"."""
    sid = str(session.get("id") or "")
    if charter_signed or (account_id and session.get("organiser_account_id") == account_id):
        return text
    seats = _read_rec(plane, ("intents", "m1_intent", "rooms"), sid).get("seats") if _HEX.fullmatch(sid) else None
    mine = account_id and any(isinstance(x, dict) and x.get("state") == "taken" and x.get("account_id") == account_id for x in seats or [])
    return text if mine else "A wall"


def _named_count(plane: CompanyPlane, baseline_id: str, mid: str) -> int | None:
    """How many people are on the measure's governed access list (the list Feeds uses); None when there is no governed record."""
    if not _HEX.fullmatch(baseline_id):
        return None
    cell = (GS._read(plane, baseline_id).get(mid) or {}).get("may_see")
    if not isinstance(cell, dict) or cell.get("mark") == "unknown":
        return None
    return len(_names(cell.get("value")))


def _draft_release(plane: CompanyPlane, subj: str) -> list[dict]:
    """The Released step when the release record carries the measure but is not signed: "Not yet" with the reason, from build/prove.json."""
    if not subj.startswith("measure:"):
        return []
    try:
        pv = read_json_strict(plane.path("build", "prove.json"), dict) or {}
    except (OSError, ValueError):
        return []
    rel = pv.get("release") if isinstance(pv.get("release"), dict) else {}
    code = subj.split(":", 1)[1].lower()
    if rel.get("state") == "signed" or not any(isinstance(m, dict) and str(m.get("code")).lower() == code for m in pv.get("measures") or []):
        return []
    return [{"step": "released", "label": "Not yet: the release is drafted, not signed", "detail": "", "ref": None, "by": "the release record", "at": None}]


@router.get("/api/company/graph/node/{node_id}")
def get_api_company_graph_node_node_id(request: Request, node_id: str) -> dict:
    try:
        plane, viewer = _plane(request), _viewer(request)
    except PermissionError:
        raise HTTPException(403, "Your company space could not be opened. Please ask your administrator.") from None
    rebuild_if_dirty(plane)
    from sh_platform.graph.knowledge_map import try_backfill
    try_backfill(plane)  # the seeded signed records predate the map: their moments and versions, once
    g = graph_for(plane, viewer)
    seen = {n["id"]: n for n in g["nodes"]}
    if node_id not in seen or seen[node_id].get("restricted"):
        raise HTTPException(404, "No such node")  # a silhouette id and an unknown id answer alike
    doc = read_json_strict(plane.path("graph", "company.json"), dict) or {}
    raw = {n["id"]: n for n in doc.get("nodes", []) if n["id"] in seen and not seen[n["id"]].get("restricted")}
    me = raw[node_id]
    out = [e for e in doc["edges"] if e["from"] == node_id and e["to"] in raw]
    inc = [e for e in doc["edges"] if e["to"] == node_id and e["from"] in raw]
    base = _newest_baseline(plane)

    def at(n: dict) -> tuple[str, str | None]:
        p = (n.get("provenance") or [{}])[-1]
        return str(p.get("by") or THE_RECORD), p.get("at")

    trail: list[dict] = []
    charter = _read_rec(plane, ("intents", "m1_intent", "outcomes"), str(base.get("charter_outcome_id") or ""))
    wsess = _read_rec(plane, ("intents", "m1_intent", "sessions"), str(charter.get("session_id") or ""))
    wall = str((wsess.get("preparation") or {}).get("purpose") or "")
    wall = wall_name(plane, wsess, bool(charter.get("signed_at")), request.state.account_id, wall) if wall else ""
    asked = {f"problem:{p['id']}": p for p in charter.get("problems") or [] if isinstance(p, dict) and p.get("id")}
    # a mart reads its measure's signed baseline: asked, defined and supplied are the measure's own steps (the seeded marts predate the map)
    subj = next((e["from"] for e in inc if e["type"] == "fed_by" and raw[e["from"]]["type"] == "Measure"), node_id) if me["type"] == "Mart" else node_id
    s_out = [e for e in doc["edges"] if e["from"] == subj and e["to"] in raw] if subj != node_id else out
    s_inc = [e for e in doc["edges"] if e["to"] == subj and e["from"] in raw] if subj != node_id else inc
    for e in s_inc:
        if e["type"] == "measured_by":
            by, when = at(raw[e["from"]])
            cards = (asked.get(e["from"]) or {}).get("note_count")
            sub = f"Problem: {raw[e['from']]['label']}" + (f" · {cards} card{'' if cards == 1 else 's'}" if cards else "")
            trail.append({"step": "asked", "label": wall or raw[e["from"]]["label"], "detail": sub, "ref": e["from"], "by": by, "at": when})
    terms = [e["to"] for e in s_out if e["type"] == "defined_as"]
    signers = [s["name"] for s in base.get("signatures") or [] if isinstance(s, dict) and s.get("name")]
    for t in terms:
        when = base.get("signed_at")
        sub = " · ".join(x for x in (f"Signed by {', '.join(signers)}" if signers else "", _day(when)) if x)
        trail.append({"step": "defined", "label": f"Baseline, version {base.get('baseline_version') or 1}", "detail": sub, "ref": t,
                      "by": ", ".join(signers) or THE_RECORD, "at": when})
    for e in s_out:
        if e["type"] == "fed_by" and e["to"] != node_id and not (subj != node_id and raw[e["to"]]["type"] == "Mart"):
            fields = [raw[x["to"]]["label"] for x in doc["edges"] if x["from"] == e["to"] and x["type"] == "uses" and x["to"] in raw]
            by, when = at(raw[e["to"]])
            trail.append({"step": "supplied", "label": raw[e["to"]]["label"], "detail": f"Fields: {', '.join(fields)}" if fields else "", "ref": e["to"],
                          "by": by, "at": when})
    pipes = [raw[e["to"]] for e in out if e["type"] == "built_by"]

    def named(src: str, typ: str) -> list[str]:
        return [raw[x["to"]]["label"] for x in doc["edges"] if x["from"] == src and x["type"] == typ and x["to"] in raw]
    designers = [n for e in s_out if e["type"] == "designed_in" for n in named(e["to"], "designed_by")]
    for p in pipes:
        by, when = at(p)
        n = len(p.get("commits") or [])
        sub = " · ".join(x for x in (f"Design signed by {', '.join(designers)}" if designers else "", f"{n} commit{'' if n == 1 else 's'}" if n else "") if x)
        trail.append({"step": "built", "label": f"Pipeline {p['label']}", "detail": sub, "ref": p["id"], "by": by, "at": when})
    rels = [e["to"] for e in s_out if e["type"] == "released_in"]
    for p in pipes:  # the older link: a release tied to the pipeline
        rels += [x["to"] if x["from"] == p["id"] else x["from"] for x in doc["edges"] if x["type"] == "released_by" and p["id"] in (x["from"], x["to"])]
    for rel in dict.fromkeys(r for r in rels if r in raw and raw[r]["type"] == "Release"):
        by, when = at(raw[rel])
        sub = " · ".join(x for x in (f"UAT: {', '.join(named(rel, 'tested_by'))}" if named(rel, "tested_by") else "",
                                     f"release: {', '.join(named(rel, 'released_by'))}" if named(rel, "released_by") else "") if x)
        trail.append({"step": "released", "label": raw[rel]["label"], "detail": sub, "ref": rel, "by": by, "at": when})
    if not any(s["step"] == "released" for s in trail):  # a release drafted but not signed carries the measure: say so, never "released"
        trail += _draft_release(plane, subj)
    owner = next((raw[e["to"]]["label"] for e in out if e["type"] == "owned_by"), None)
    mid = subj.split(":", 1)[1] if subj.startswith("term:") or (raw[subj]["type"] == "Measure" and terms) else ""
    gloss = next((d for d in base.get("glossary") or [] if isinstance(d, dict) and str(d.get("kpi_id")) == mid), None) if mid else None
    definition = None
    if gloss is not None:
        tech = (base.get("technical") or {}).get(mid) or {}
        steps = sorted((s for s in ((base.get("process_map") or {}).get(mid) or {}).get("steps") or [] if isinstance(s, dict) and s.get("state") != "removed"),
                       key=lambda s: s.get("order") or 0)
        definition = {"term": _t(gloss.get("term")), "business": _t(gloss.get("business_definition") or gloss.get("definition")),
                      "technical": _t(tech.get("calculation")) if isinstance(tech, dict) else "", "process": " · ".join(str(s.get("text") or "") for s in steps)}
    accounts = request.app.state.account_store.in_company(request.state.company_id)
    return {"id": node_id, "type": me["type"], "label": me["label"], "owner": owner, "steward": steward(plane, accounts) or None, "trail": trail,
            "definition": definition, "versions": plain_versions(_read(plane, "versions.json", dict).get(node_id, []),
                                       [raw[x]["label"] for x in dict.fromkeys(e["to"] for e in out if e["type"] in ("fed_by", "built_by")) if x in raw]),
            "commits": [c for p in pipes for c in p.get("commits") or []], "baseline_id": base.get("baseline_id"),
            "may_see_named": _named_count(plane, str(base.get("baseline_id") or ""), mid or node_id.split(":", 1)[-1]) if me["type"] == "Measure" else None,
            "may_see_figure": me["type"] == "Measure" and _sees(me, viewer)}
