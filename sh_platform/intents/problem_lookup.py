"""Problem (41): what the start questions and the triage note look up. Read only, per viewer.

Measures and processes come from the viewer's gated graph, people from the viewer's profile, owners from the profile ("owns" lines),
the graph (`owned_by`) and the pipeline contracts (`build/pipelines/*.json`), alerts and range breaks from Ops (`build/ops.py`).
"""
import logging
import re
from datetime import datetime, timezone

from sh_platform.build import alerts as store_alerts, ops
from sh_platform.graph.read import graph_for
from sh_platform.jsonfile import read_json_strict
from sh_platform.profile import areas as areas_store, store as profile_store, view as profile_view

log = logging.getLogger(__name__)
KIND_WORDS = {"missing": "the file has not arrived", "late": "the file arrived late", "failed": "the run failed its checks",
              "outside_range": "the value is outside its usual range"}
SOURCE_LABELS = {"business_owner": "Business owner, from the process map", "source_owner": "Source owner, from the pipeline contract",
                 "data_owner": "Data owner, from the map", "reporter": "Picked by the reporter", "admin": "The company admin"}
STOP = set("the and for that with this from have been was were are not but its our their they them what when where which while".split())


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def people(plane, viewer) -> list[dict]:
    """[{id, name, team}] for the people this viewer may see in the company profile."""
    out = []
    for key, p in profile_view.read(plane, viewer)["people"].items():
        name = profile_view._v(p, "name")
        if name:
            out.append({"id": key, "name": str(name), "team": profile_view._v(p, "team")})
    return sorted(out, key=lambda x: x["name"])


def accounts(request) -> dict[str, str]:
    """display name (lower case) -> account id, for the signed-in company."""
    st = request.app.state
    return {str(a["display_name"]).strip().lower(): a["account_id"] for a in st.account_store.in_company(request.state.company_id) if not a.get("disabled")}


def areas(plane, viewer) -> list[str]:
    """The company's active areas from the areas record (file 05); the teams in the profile only while that record is empty."""
    named = sorted({a["name"] for a in areas_store.listing(profile_store.load(plane)) if a["name"] and a["status"] == "active"})
    return named or sorted({t for p in people(plane, viewer) if (t := p["team"])})


def catalogue(plane, viewer) -> list[dict]:
    """Measures and processes the viewer may see: [{id, name, group}]."""
    out = []
    for n in graph_for(plane, viewer)["nodes"]:
        group = {"Measure": "Measures", "Process": "Processes"}.get(n.get("type"))
        if group and not str(n.get("id", "")).startswith("restricted"):
            out.append({"id": n["id"], "name": n.get("label") or n["id"], "group": group})
    return sorted(out, key=lambda x: (x["group"], x["name"]))


def _code(node_id: str) -> str:
    return node_id.split(":", 1)[-1]


def _contracts(plane) -> list[dict]:
    out = []
    for f in sorted(plane.path("build", "pipelines").glob("*.json")):
        try:
            d = read_json_strict(f, dict)
        except (OSError, ValueError):
            continue
        if d and d.get("source"):
            out.append(d)
    return out


def sources_for(plane, about_id: str) -> list[dict]:
    """The pipeline contracts whose marts feed this measure."""
    code = _norm(_code(about_id))
    return [c for c in _contracts(plane) if any(_norm(str(m).removeprefix("gold.")) == code for m in c.get("marts") or [])]


def owner_chips(plane, viewer, about_id: str | None) -> list[dict]:
    """The three proposals for the picked measure or process: [{source, name, label}], in the order of preference of spec 41."""
    if not about_id:
        return []
    code, graph, profile = _code(about_id), graph_for(plane, viewer), profile_view.read(plane, viewer)["people"]
    by_slug = {k: str(profile_view._v(p, "name") or "") for k, p in profile.items()}
    business = None
    for k, p in profile.items():
        for line in profile_view._v(p, "owns") or []:
            if str(line).lower().startswith(code.lower() + " ") and "business owner" in str(line).lower():
                business = by_slug[k]
    data = [by_slug.get(e["to"].removeprefix("person:")) for e in graph["edges"] if e["type"] == "owned_by" and e["from"] == about_id]
    data = [d for d in data if d and d != business]
    source = next((c.get("owner") for c in sources_for(plane, about_id) if c.get("owner")), None)
    chips = [("business_owner", business), ("source_owner", source), ("data_owner", data[0] if data else None)]
    return [{"source": s, "name": n, "label": SOURCE_LABELS[s]} for s, n in chips if n]


def ops_today(plane, viewer) -> dict:
    try:
        return ops.build(plane, viewer, datetime.now(timezone.utc).date())
    except (OSError, ValueError, KeyError, ImportError) as e:  # Ops could not be read: the panel says so, the screen still works
        log.warning("ops unreadable for the triage note: %s", type(e).__name__)
        return {"alerts": [], "range_breaks": [], "unreadable": True}


def matches_about(plane, about_id: str | None, alert_id: str | None, today: dict) -> tuple[list[dict], list[dict]]:
    """Alerts and range breaks for the picked measure or its sources, plus the alert the problem came from."""
    if not about_id and not alert_id:
        return [], []
    code = _norm(_code(about_id)) if about_id else None
    srcs = {c["source"] for c in sources_for(plane, about_id)} if about_id else set()
    al = [a for a in today.get("alerts") or [] if a["id"] == alert_id or (code and _norm(a.get("measure") or "") == code) or a.get("source") in srcs]
    rb = [b for b in today.get("range_breaks") or [] if (code and _norm(str(b["mart"]).removeprefix("gold.")) == code) or b.get("source") in srcs]
    return al, rb


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


def triage_refs(plane, viewer, rec: dict, others: list[dict]) -> dict:
    """The stored note: ids and reasons only (the other records are read again when it is shown). Plain matches: no wording is drafted."""
    out = rec["outcome"]
    about_id, alert_id = (out.get("about") or {}).get("id"), (rec.get("links") or {}).get("alert")
    mine, mine_words = set(rec.get("areas") or []), words(f"{out.get('what', '')} {out.get('saw', '')}")
    similar, related = [], []
    for o in others:
        if o["id"] == rec["id"] or o.get("state") == "draft":
            continue
        same_about = bool(about_id) and (o.get("outcome") or {}).get("about", {}).get("id") == about_id
        same_area = bool(mine & set(o.get("areas") or []))
        shared = len(mine_words & words(f"{(o.get('outcome') or {}).get('what', '')} {o.get('title', '')}"))
        if o.get("type") == "problem" and o.get("state") == "closed":
            if same_about:
                similar.append((0, {"intent": o["id"], "why": "Same process or measure"}))
            elif same_area and shared >= 2:
                similar.append((1, {"intent": o["id"], "why": "Same area and similar wording"}))
        elif o.get("state") in ("open", "in_session", "closing") and (same_about or same_area):
            related.append({"intent": o["id"], "why": "Same process or measure" if same_about else "Same area"})
    today = ops_today(plane, viewer)
    al, rb = matches_about(plane, about_id, alert_id, today)
    return {"drafted_at": datetime.now(timezone.utc).isoformat(), "similar": [s for _, s in sorted(similar, key=lambda x: x[0])][:5], "related": related[:5],
            "alerts": [{"alert_id": a["id"], "kind": a["kind"], "state": a["state"]} for a in al],
            "range_breaks": [{"mart": b["mart"], "basis": b.get("basis")} for b in rb], "terms": [], "drafted_plainly": True}


def alert_state(plane, alert_id: str) -> str | None:
    return next((a.get("state") for a in store_alerts._read(plane) if a.get("id") == alert_id), None)
