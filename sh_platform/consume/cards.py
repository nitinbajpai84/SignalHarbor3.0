"""Context cards for gold tables (spec 60, rulings C40 to C45). One card per gold table: what it means, which measures it serves, where it
comes from, who owns it, its quality rules, its last change and why, and the Initiative that made or changed it.

The Architect drafts the technical lines from records (blueprint lineage and rules, the knowledge map's versions); Lens drafts "What it means"
from the signed definition. Every drafted line carries `from`, the record it was read from; a line with no record reads "Not available yet" and says
what is missing. The data owner of the table's first measure (C42) confirms, corrects or disputes; nobody else, an agent included.
Record: `consume/cards/<table>.json`. States: draft, confirmed, changed (derived: a newer map version than `confirmed_at`), disputed.

Routes: GET /api/company/consume/cards/{table}, POST .../confirm, .../edit, .../dispute. `redraft(plane, table)` is the Architect's answer to a
dispute; the build chain calls `draft_for_blueprint(plane)` after a signature.
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from modules.m2_baseline.domain import technical as T
from modules.m2_baseline.store import baseline as B
from modules.m2_baseline.store import governed as GS
from modules.m2_baseline.store.kpis import read_kpis
from sh_platform.consume import feeds
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import view
from sh_platform.profile.api import _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()

LINES = ("meaning", "lineage", "owner", "rules", "last_change")
TITLES = {"meaning": "What it means", "lineage": "Where it comes from", "owner": "Owner", "rules": "Quality rules", "last_change": "Last change and why"}
NO_CARD = "No context card yet. The Architect drafts one when the blueprint that builds this table is signed."
NOT_OWNER = "Only the data owner of this table can do that."
SAFE = re.compile(r"[a-z0-9_]{1,40}")
INTENT_REF = re.compile(r"(?:intent:)?((?:ini|prb|dec|bra|pul)-[0-9a-f]{8,40})")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def table_of(raw: str) -> str | None:
    t = str(raw).lower().removeprefix("gold.")
    return t if SAFE.fullmatch(t) else None


def _path(plane, table: str):
    return plane.path("consume", "cards", f"{table}.json")


def read_card(plane, table: str) -> dict | None:
    try:
        c = read_json_strict(_path(plane, table), dict)
    except (OSError, ValueError):
        return None
    return c if isinstance(c, dict) and c.get("table") == f"gold.{table}" else None


def _write(plane, table: str, card: dict) -> None:
    write_json_atomic(_path(plane, table), card)


def _line(text: str | None, ref: str | None, missing: str) -> dict:
    return {"text": text, "mark": "guessed", "from": ref} if text else {"text": f"Not available yet: {missing}", "mark": "guessed", "from": None}


# ---- the records a card is read from ---------------------------------------------------------------------------------------------

def _blueprint(plane) -> dict:
    try:
        return read_json_strict(plane.path("build", "blueprint.json"), dict) or {}
    except (OSError, ValueError):
        return {}


def _mart_table(mart: str) -> str:
    return str(mart).lower().removeprefix("gold.").split(".")[0]


def _base(plane):
    found = B.baselines(plane)
    return next((b for b in found if b.get("state") == "signed"), found[0] if found else None)


def _versions(plane, table: str) -> list[dict]:
    """The mart node's versions, oldest first. Node ids look like `mart:gold-k01-<slug>`."""
    try:
        doc = read_json_strict(plane.path("graph", "versions.json"), dict) or {}
    except (OSError, ValueError):
        return []
    rows = []
    for node, vs in doc.items():
        if str(node).startswith(f"mart:gold-{table}-") or node == f"mart:gold-{table}":
            rows += [dict(v, node=node) for v in vs if isinstance(v, dict)]
    return sorted(rows, key=lambda v: str(v.get("at")))


def _node_id(plane, table: str) -> str:
    """The map node of the mart (`mart:gold-k12-<slug>`); the plain `mart:<table>` when the map does not hold it yet."""
    try:
        nodes = (read_json_strict(plane.path("graph", "company.json"), dict) or {}).get("nodes") or []
    except (OSError, ValueError):
        nodes = []
    return next((n["id"] for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith(f"mart:gold-{table}-")), f"mart:{table}")


def _intent_of(plane, ref: str | None) -> str | None:
    """The intent a version's ref points at: directly, or through the update row with that id (55's updates.json)."""
    if not ref:
        return None
    m = INTENT_REF.fullmatch(str(ref))
    if m:
        return m.group(1)
    try:
        ups = read_json_strict(plane.path("graph", "updates.json"), list) or []
    except (OSError, ValueError):
        return None
    row = next((u for u in ups if isinstance(u, dict) and u.get("id") == ref), None)
    m = INTENT_REF.fullmatch(str(row.get("ref"))) if row else None
    return m.group(1) if m else None


def _has(card: dict, n: str) -> bool:
    """A line a person can stand behind: read from a record, or written by the owner."""
    c = card.get(n)
    return isinstance(c, dict) and bool(c.get("from") or c.get("edited_by"))


def draft(plane, table: str, code: str, only: tuple = LINES) -> dict:
    """The Architect's and Lens's draft lines from the records. Never writes."""
    bp, base = _blueprint(plane), _base(plane)
    lin = [e for e in bp.get("lineage") or [] if isinstance(e, dict) and _mart_table(e.get("mart", "")) == table]
    measures = list(dict.fromkeys([str(e["measure"]).upper() for e in lin if e.get("measure")] or [code]))
    kpis = {k.get("id"): k for k in (read_kpis(plane, base["id"]) if base else []) if isinstance(k, dict)}
    k = kpis.get(code) or {}
    defn = T.text_of(k.get("definition")) if isinstance(k.get("definition"), dict) and k["definition"].get("mark") != "unknown" else ""
    gov = GS._read(plane, base["id"]) if base else {}
    oc = (gov.get(code) or {}).get("owners")
    owners = oc.get("value") if isinstance(oc, dict) and oc.get("mark") != "unknown" else None
    data_owner = owners.get("data") if isinstance(owners, dict) else None
    rules = [r for r in bp.get("rules") or [] if isinstance(r, dict) and str(r.get("measure")).upper() in measures]
    vs = _versions(plane, table)
    lines = {
        "meaning": _line(defn or None, f"signed definition of {code}" if defn else None, "no signed definition"),
        "lineage": _line("; ".join(f"{e.get('source')} ({', '.join(e.get('fields') or [])})" for e in lin) or None, "build/blueprint.json lineage" if lin else None,
                         "the map holds no lineage for this table"),
        "owner": _line(data_owner, f"owners of {code} in the baseline" if data_owner else None, "no data owner named"),
        "rules": _line("; ".join(f"{r.get('rule')} ({r.get('severity')}, from {r.get('from')})" for r in rules) or None, "build/blueprint.json rules" if rules else None,
                       "no quality rule set yet"),
        "last_change": _line(f"{vs[-1].get('what')}, by {vs[-1].get('by')}, {str(vs[-1].get('at'))[:10]}" if vs else None, f"graph/versions.json {vs[-1].get('node')} v{vs[-1].get('v')}" if vs else None,
                             "no change recorded since it was built"),
    }
    made = {"intent_id": i, "how": "created" if vs[-1].get("v") == 1 else "changed"} if vs and (i := _intent_of(plane, vs[-1].get("ref"))) else None
    return {"lines": {k2: v for k2, v in lines.items() if k2 in only}, "measures": measures, "made_by": made}


def _new(plane, table: str, code: str) -> dict:
    d = draft(plane, table, code)
    now = _now()
    return {"table": f"gold.{table}", "measures": d["measures"], **d["lines"], "made_by": d["made_by"], "state": "draft", "drafted_by": ["architect", "lens"], "drafted_at": now,
            "confirmed_by": None, "confirmed_at": None, "stale_since": None, "stale_ref": None, "dispute": None,
            "history": [{"at": now, "by": "architect and lens", "action": "drafted", "line": None, "old": None, "new": None, "why": None}]}


def draftable(plane, table: str, code: str) -> bool:
    d = draft(plane, table, code)
    return any(l["from"] for l in d["lines"].values())


def draft_for_blueprint(plane) -> list[str]:
    """After a blueprint signature (59): a draft card for every table its lineage names that has none. Returns the tables drafted."""
    done = []
    for t in dict.fromkeys(_mart_table(e.get("mart", "")) for e in _blueprint(plane).get("lineage") or [] if isinstance(e, dict)):
        if SAFE.fullmatch(t) and read_card(plane, t) is None:
            with lock_for(_path(plane, t)):
                if read_card(plane, t) is None:
                    _write(plane, t, _new(plane, t, t.upper()))
                    done.append(t)
    return done


def redraft(plane, table: str) -> dict | None:
    """The Architect's answer to a dispute: every line a person has not edited is read again from the records; the old text stays in the history."""
    with lock_for(_path(plane, table)):
        card = read_card(plane, table)
        if card is None:
            return None
        d = draft(plane, table, card["measures"][0] if card["measures"] else table.upper())
        for name, new in d["lines"].items():
            old = card.get(name) or {}
            if old.get("edited_by"):
                continue
            if old.get("text") != new["text"]:
                card["history"].append({"at": _now(), "by": "architect", "action": "redrafted", "line": name, "old": old.get("text"), "new": new["text"], "why": None})
            card[name] = new
        card["measures"], card["made_by"], card["state"], card["dispute"] = d["measures"], d["made_by"], "draft", None
        card["confirmed_by"] = card["confirmed_at"] = None
        _write(plane, table, card)
        return card


# ---- who acts, and the state a viewer is shown -----------------------------------------------------------------------------------

def data_owner(plane, code: str) -> str | None:
    base = _base(plane)
    c = ((GS._read(plane, base["id"]) if base else {}).get(code) or {}).get("owners")
    v = c.get("value") if isinstance(c, dict) and c.get("mark") != "unknown" else None
    return v.get("data") if isinstance(v, dict) else None


def is_owner(plane, viewer: view.Viewer, code: str) -> bool:
    o = data_owner(plane, code)
    return bool(o) and view.norm(o) == view.norm(viewer.name) and not viewer.shared_name


def _state(plane, table: str, card: dict) -> tuple[str, str | None]:
    """(state, stale_since): a confirmed card turns `changed` when the table's map node has a version newer than the confirmation."""
    if card["state"] == "confirmed":
        newer = [v for v in _versions(plane, table) if str(v.get("at")) > str(card.get("confirmed_at"))]
        if newer:
            return "changed", newer[0].get("at")
    return card["state"], card.get("stale_since")


def _fresh(plane, table: str, card: dict) -> dict:
    """A changed card shown, or confirmed again, with the map's newest last change and made-by read again (a line a person edited is kept)."""
    d = draft(plane, table, card["measures"][0] if card["measures"] else table.upper(), ("last_change",))
    lc = card["last_change"] if card["last_change"].get("edited_by") else d["lines"]["last_change"]
    return {**card, "last_change": lc, "made_by": d["made_by"]}


def shape(plane, viewer: view.Viewer, feed: list[dict], card: dict, rows: list[dict] | None = None, areas=None) -> dict:
    from sh_platform.intents import store
    table = card["table"].removeprefix("gold.")
    by = {m["code"]: m for m in feed}
    state, stale = _state(plane, table, card)
    if state == "changed":
        card = _fresh(plane, table, card)
    mk = card.get("made_by")
    made = None
    if mk:
        row = next((r for r in rows or [] if r["id"] == mk["intent_id"]), None)
        tier = store.tier_of(row, viewer, areas if areas is not None else frozenset()) if row else None
        made = {"how": mk["how"], "title": row["title"] if tier and tier != "exists" else None, "href": f"/centre/intent/{mk['intent_id']}" if tier else None,
                "text": None if tier else "An Initiative you cannot open"}
    code = card["measures"][0] if card["measures"] else table.upper()
    owner = is_owner(plane, viewer, code)
    lines = {n: {**card[n], "title": TITLES[n]} for n in LINES if isinstance(card.get(n), dict)}
    return {"table": card["table"], "state": state, "stale_since": stale, "lines": lines,
            "measures": [{"code": c, "name": by[c]["name"] if c in by and by[c]["may_see"] else None, "restricted": c not in by or not by[c]["may_see"]} for c in card["measures"]],
            "made_by": made, "lineage_href": f"/centre/intent/graph?view=lineage&focus={_node_id(plane, table)}", "suggest_href": f"/centre/intent/map/{_node_id(plane, table)}",
            "drafted_line": f"Drafted by the Architect and Lens on {str(card['drafted_at'])[:10]}." + (f" Confirmed by {card['confirmed_by']} on {str(card['confirmed_at'])[:10]}." if card.get("confirmed_by") else ""),
            "dispute": card.get("dispute") and {"by": card["dispute"].get("by"), "reason": card["dispute"].get("reason")},
            "can": {"confirm": owner, "edit": owner, "dispute": owner}, "history": card.get("history", [])[-20:]}


def get_card(plane, viewer: view.Viewer, feed: list[dict], raw: str, rows=None, areas=None) -> tuple[int, dict]:
    table = table_of(raw)
    m = next((x for x in feed if table and x["code"] == table.upper()), None)
    if m is None:
        return 404, {"detail": "We could not find that."}
    if not m["may_see"]:  # a restricted measure: the table name and the owner only
        return 200, {"table": f"gold.{table}", "state": None, "restricted": f"Restricted: ask {m.get('owner') or 'the owner'}", "owner": data_owner(plane, m["code"])}
    card = read_card(plane, table)
    if card is None and draftable(plane, table, m["code"]):
        with lock_for(_path(plane, table)):
            card = read_card(plane, table) or _new(plane, table, m["code"])
            _write(plane, table, card)
    if card is None:
        return 200, {"table": f"gold.{table}", "state": None, "empty": NO_CARD}
    return 200, shape(plane, viewer, feed, card, rows, areas)


# ---- the three owner acts ------------------------------------------------------------------------------------------------------

def _act(plane, viewer, feed, raw: str, change) -> tuple[int, dict]:
    table = table_of(raw)
    m = next((x for x in feed if table and x["code"] == table.upper() and x["may_see"]), None)
    if m is None:
        return 404, {"detail": "We could not find that."}
    if not is_owner(plane, viewer, m["code"]):
        return 403, {"detail": NOT_OWNER}
    with lock_for(_path(plane, table)):
        card = read_card(plane, table)
        if card is None:
            return 404, {"detail": NO_CARD}
        err = change(card)
        if err:
            return 422, {"detail": err}
        _write(plane, table, card)
    return 200, shape(plane, viewer, feed, card)


def confirm(plane, viewer, feed, raw: str) -> tuple[int, dict]:
    def change(card):
        if card["state"] == "disputed":
            return "This card is disputed. Wait for the Architect's new draft."
        now = _now()
        if _state(plane, table_of(raw), card)[0] == "changed":
            card.update(_fresh(plane, table_of(raw), card))
            card["history"].append({"at": now, "by": viewer.name, "action": "read the change again", "line": "last_change", "old": None, "new": card["last_change"]["text"], "why": None})
        for n in LINES:
            if _has(card, n):
                card[n]["mark"] = "stated"
        card.update(state="confirmed", confirmed_by=viewer.name, confirmed_at=now, stale_since=None, stale_ref=None)
        card["history"].append({"at": now, "by": viewer.name, "action": "confirmed", "line": None, "old": None, "new": None, "why": None})
    return _act(plane, viewer, feed, raw, change)


def edit(plane, viewer, feed, raw: str, line, text, why) -> tuple[int, dict]:
    def change(card):
        if line not in LINES:
            return "Pick which line to correct."
        if not (isinstance(text, str) and text.strip() and len(text) <= 600) or not (isinstance(why, str) and why.strip() and len(why) <= 300):
            return "Send the new text and why you changed it."
        old, now = card[line].get("text"), _now()
        card[line] = {"text": text.strip(), "mark": "guessed", "from": f"edited by {viewer.name}", "edited_by": viewer.name, "why": why.strip()}
        card.update(state="draft", confirmed_by=None, confirmed_at=None)
        card["history"].append({"at": now, "by": viewer.name, "action": "edited", "line": line, "old": old, "new": text.strip(), "why": why.strip()})
    return _act(plane, viewer, feed, raw, change)


def dispute(plane, viewer, feed, raw: str, reason) -> tuple[int, dict]:
    def change(card):
        if not (isinstance(reason, str) and reason.strip() and len(reason) <= 600):
            return "Say what is wrong."
        now = _now()
        card["dispute"] = {"by": viewer.name, "at": now, "reason": reason.strip()}
        card["state"] = "disputed"
        card["history"].append({"at": now, "by": viewer.name, "action": "disputed", "line": None, "old": None, "new": None, "why": reason.strip()})
        card["history"].append({"at": now, "by": "north", "action": "asked the Architect to redraft", "line": None, "old": None, "new": None, "why": None})
    return _act(plane, viewer, feed, raw, change)


# ---- Pulse (Nira, kind decision, to the data owner only) and Ask Lens ------------------------------------------------------------

def pulse_lines(plane, viewer: view.Viewer, feed: list[dict]) -> list[dict]:
    from sh_platform.pulse.lines import line
    out = []
    for m in feed:
        t = m["code"].lower()
        card = read_card(plane, t)
        if card is None or not is_owner(plane, viewer, m["code"]):
            continue
        state, _ = _state(plane, t, card)
        href = f"/centre/consume/feeds/{m['code']}?card=confirm"
        if state == "draft":
            out.append(line(f"card:{t}:confirm", "decision", f"A context card for gold.{t} waits for you.", "Confirm it or correct a line.", href, "Open it", f"consume/cards/{t}.json", card["drafted_at"]))
        elif state == "changed":
            out.append(line(f"card:{t}:changed", "decision", f"gold.{t} changed since you confirmed its card. Check it.", "", href, "Open it", f"consume/cards/{t}.json", card.get("confirmed_at")))
    return out


def facts_for(plane, code: str) -> list[str]:
    """Lines for Ask Lens (C44): a confirmed card is quoted as fact; a draft is quoted as 'draft, not yet confirmed by <owner>'. A restricted
    measure is the caller's check (it must pass feeds may_see before asking)."""
    t = str(code).lower()
    card = read_card(plane, t) if SAFE.fullmatch(t) else None
    if card is None:
        return []
    state, _ = _state(plane, t, card)
    prefix = "" if state == "confirmed" else f"(draft, not yet confirmed by {data_owner(plane, str(code).upper()) or 'its data owner'}) "
    return [f"{prefix}{TITLES[n]}: {card[n]['text']}" for n in LINES if _has(card, n)]


# ---- routes ---------------------------------------------------------------------------------------------------------------------

def _ctx(request: Request):
    from sh_platform.intents import store
    plane, viewer = _plane(request), _viewer(request)
    return plane, viewer, feeds.build(plane, viewer, feeds._pack_names(request))["measures"], store.read_index(plane), store.areas_of(plane, viewer)


async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        return {}
    return b if isinstance(b, dict) else {}


@router.get("/api/company/consume/cards/{table}")
def get_card_route(request: Request, table: str):
    plane, viewer, feed, rows, areas = _ctx(request)
    s, out = get_card(plane, viewer, feed, table, rows, areas)
    return JSONResponse(out, status_code=s)


@router.post("/api/company/consume/cards/{table}/confirm")
def post_confirm(request: Request, table: str):
    plane, viewer, feed, *_ = _ctx(request)
    s, out = confirm(plane, viewer, feed, table)
    return JSONResponse(out, status_code=s)


@router.post("/api/company/consume/cards/{table}/edit")
async def post_edit(request: Request, table: str):
    b = await _body(request)
    plane, viewer, feed, *_ = _ctx(request)
    s, out = edit(plane, viewer, feed, table, b.get("line"), b.get("text"), b.get("why"))
    return JSONResponse(out, status_code=s)


@router.post("/api/company/consume/cards/{table}/dispute")
async def post_dispute(request: Request, table: str):
    b = await _body(request)
    plane, viewer, feed, *_ = _ctx(request)
    s, out = dispute(plane, viewer, feed, table, b.get("reason"))
    return JSONResponse(out, status_code=s)
