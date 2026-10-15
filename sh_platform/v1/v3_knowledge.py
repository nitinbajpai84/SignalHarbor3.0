"""Harbor 3.0 Knowledge: what THIS company knows about itself, built only from its own records (spec: docs/v3/HARBOR-SPEC.md, 15 Oct).
Nodes: people (accounts), entities and funds (warehouse, read only), sources and figures (signed briefs), recognised files, use cases (live threads),
decisions (each brief's decisions and open cases). Edges are plain words: decides, reads, feeds, commits to, uses, waits on. Nothing is invented:
a figure's value comes from the live note, a link is drawn only when a record names it. No industry view, no data model, no table names."""
import logging
import re
from datetime import date

from sh_platform.v1 import i5_graph, wh
from sh_platform.v1 import v3_harbor as H

log = logging.getLogger(__name__)
KINDS = [("person", "People"), ("entity", "Entities"), ("fund", "Funds"), ("source", "Sources"), ("file", "Files"),
         ("figure", "Figures"), ("usecase", "Use cases"), ("decision", "Decisions")]
STAGE = {"drafting": "Being drafted", "decision1": "Waiting for the brief to be confirmed", "working": "Being built", "decision2": "Waiting for the files to be confirmed",
         "decision3": "Waiting to go live", "live": "Live", "question": "Waiting for an answer"}


def _slug(s) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:60]


def _t(v, n=300) -> str:
    return (", ".join(map(str, v)) if isinstance(v, list) else str(v or "")).strip()[:n]


class _G:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}

    def node(self, kind, key, label, since="") -> dict:
        n = self.nodes.setdefault(f"{kind}:{key}", {"id": f"{kind}:{key}", "kind": kind, "label": _t(label, 120), "facts": [], "since": since or ""})
        n["since"] = min(filter(None, [n["since"], since or ""]), default="")
        return n

    def fact(self, n, text, source, at="") -> None:
        text = _t(text)
        if text and not any(f["text"] == text for f in n["facts"]):
            n["facts"].append({"text": text, "source": source, "at": (at or "")[:10]})

    def edge(self, a, b, label) -> None:
        if a in self.nodes and b in self.nodes and a != b:
            self.edges[(a, b, label)] = {"from": a, "to": b, "label": label}


def _warehouse(g: _G, plane) -> None:
    if not wh.path(plane).is_file():
        return
    try:
        with wh.connect(plane) as con:
            ents = con.execute("select id, entity_code, entity_name, base_currency, active_from from legal_entities order by entity_name").fetchall()
            funds = con.execute("select id, canonical_name, instrument_type, manager_name, currency, created_at from instruments").fetchall()
            com = con.execute("select legal_entity_id, instrument_id, commitment_amount, currency, committed_on, called_to_date, called_as_at from commitments "
                              "where id not in (select supersedes_commitment_id from commitments where supersedes_commitment_id is not null)").fetchall()
    except Exception:  # noqa: BLE001 - a warehouse that cannot be read just now leaves entities and funds out; the rest of the map stands
        log.info("knowledge: warehouse not read", exc_info=True)
        return
    used = {c[1] for c in com}
    for eid, code, name, cur, frm in ents:
        n = g.node("entity", eid, name, str(frm or ""))
        g.fact(n, f"Code {code}, reports in {cur}", "Warehouse: legal entities", str(frm or ""))
    for iid, name, typ, mgr, cur, cat in funds:
        if iid not in used:
            continue
        n = g.node("fund", iid, name, str(cat or ""))
        g.fact(n, f"A {typ}" + (f" run by {mgr}" if mgr else "") + (f", in {cur}" if cur else ""), "Warehouse: instruments", str(cat or ""))
    for eid, iid, amt, cur, on, called, called_as in com:
        if f"entity:{eid}" not in g.nodes or f"fund:{iid}" not in g.nodes:
            continue
        g.edge(f"entity:{eid}", f"fund:{iid}", "commits to")
        line = f"committed {amt:,.0f} {cur} on {on}" + (f"; called {called:,.0f} as at {called_as}" if called is not None and called_as else "")
        g.fact(g.nodes[f"entity:{eid}"], f"{line[0].upper() + line[1:]} to {g.nodes[f'fund:{iid}']['label']}", "Warehouse: commitments", str(on))
        g.fact(g.nodes[f"fund:{iid}"], f"{g.nodes[f'entity:{eid}']['label']} {line}", "Warehouse: commitments", str(on))


def _people(g: _G, accounts: list[dict]) -> None:
    for a in accounts:
        if a.get("disabled"):
            continue
        n = g.node("person", a["account_id"], a["display_name"])
        g.fact(n, "Role: " + ", ".join(r.replace("_", " ") for r in a.get("roles") or []), "Accounts")


def _person(g: _G, name) -> str | None:
    name = str(name or "").strip().lower()
    return next((k for k, n in g.nodes.items() if n["kind"] == "person" and name and n["label"].lower() == name), None)


def _threads(g: _G, plane, processes: list[dict]) -> None:
    sows = dict(i5_graph._sows(plane))
    names = {k: n["label"] for k, n in g.nodes.items() if n["kind"] == "entity"}
    for th in H.all_threads(plane):  # discarded threads are left out
        sow, rec, src = sows.get(th.get("iid") or "") or {}, th.get("record") or {}, f"Thread: {th['title']}"
        uc = g.node("usecase", th["id"], th["title"], th["created"])
        uc["stage"] = th["stage"]
        g.fact(uc, STAGE.get(th["stage"], th["stage"]), src, th["created"])
        if th.get("started_by"):
            g.fact(uc, f"Started by {th['started_by']}", src, th["created"])
        signed = bool(rec) or sow.get("state") == "signed"
        goal = (sow.get("goal") or {}) if signed else {}
        at = rec.get("signed_at") or th["created"]
        bsrc = f"Signed brief: {th['title']}"
        if goal.get("line"):
            g.fact(uc, f"Question: {_t(goal['line'])}", bsrc, at)
        if goal.get("readers"):
            g.fact(uc, "Read by " + _t(goal["readers"]), bsrc, at)
            for r in goal["readers"] if isinstance(goal["readers"], list) else [goal["readers"]]:
                if p := _person(g, r):
                    g.edge(p, uc["id"], "reads")
        signer = _person(g, rec.get("signed_by"))
        if rec.get("signed_by"):
            g.fact(uc, f"Signed by {rec['signed_by']}" + (f" ({rec['role']})" if rec.get("role") else ""), bsrc, at)
        if signer:
            g.edge(signer, uc["id"], "decides")
        if signed:
            _brief(g, th, sow, uc, bsrc, at, processes, signer)
        for i, ex in enumerate(th.get("exceptions") or []):  # an open case waits on a person; it waits on an entity only when its words name one
            text = f"{ex.get('title', 'Check')}: {ex.get('text', '')}".strip(": ")
            d = g.node("decision", f"{th['id']}:case{i}", ex.get("title") or "Open case", th["created"])
            d["waiting"] = True
            g.fact(d, text, f"Open case on {th['title']}", th["created"])
            if signer:
                g.edge(signer, d["id"], "decides")
            for k, nm in names.items():
                if nm.lower() in text.lower():
                    g.edge(d["id"], k, "waits on")


def _brief(g, th, sow, uc, bsrc, at, processes, signer) -> None:
    goal = sow.get("goal") or {}
    decs = goal.get("decisions")
    for i, text in enumerate(decs if isinstance(decs, list) else [decs] if decs else []):
        d = g.node("decision", f"{th['id']}:{i}", text, th["created"])
        g.fact(d, f"Decided for {th['title']}", bsrc, at)
        if signer:
            g.edge(signer, d["id"], "decides")
    srcs = []
    for s in (x for x in sow.get("sources") or [] if isinstance(x, dict) and x.get("name")):
        n = g.node("source", _slug(s["name"]), s["name"], th["created"])
        held = s.get("holds") or s.get("owner")
        g.fact(n, f"Holds {_t(held)}" if held else "Named in a signed brief", bsrc, at)
        srcs.append((n, H._toks(" ".join([s["name"], _t(s.get("holds"))]))))
    for k in (x for x in sow.get("kpis") or [] if isinstance(x, dict) and x.get("name")):
        f = g.node("figure", _slug(k["name"]), k["name"], th["created"])
        for key, lab in (("definition", "Means"), ("formula", "Worked out as"), ("period", "Updated"), ("owner", "Owned by")):
            if k.get(key):
                g.fact(f, f"{lab} {_t(k[key])}", bsrc, at)
        g.edge(uc["id"], f["id"], "uses")
        want = H._toks(" ".join([k["name"], _t(k.get("definition"))]))
        for n, _ in [(n, t) for n, t in srcs if want & t] or srcs[:1] * (len(srcs) == 1):
            g.edge(n["id"], f["id"], "feeds")
        for nf in (th.get("note") or {}).get("figures") or []:  # the one place a value comes from: the live note
            if _slug(nf.get("label")) == _slug(k["name"]) and nf.get("value"):
                when = (th.get("events") or [{}])[-1].get("at", "")
                g.fact(f, f"Latest {nf['value']}" + (f" ({nf['change']})" if nf.get("change") else ""), f"Note of {th['title']}", when)
    steps = [s for s in (sow.get("process") or {}).get("steps") or [] if isinstance(s, dict)]
    if steps:
        lanes: list[str] = []
        out = []
        for s in steps:
            lane = _t(s.get("who") or "The team", 60)
            lanes += [lane] * (lane not in lanes)
            out.append({"lane": lane, "text": _t(s.get("does") or s.get("name"), 200)})
        processes.append({"title": th["title"], "lanes": lanes, "steps": out})


def _files(g: _G, plane) -> None:
    for f in H.read_files(plane):
        if f.get("status") not in ("recognised", "loaded"):
            continue
        n = g.node("file", _slug(f["name"]), f["name"], f.get("arrived_at", ""))
        g.fact(n, f"Arrived and read as {f.get('source') or 'a source'}", "Files", f.get("arrived_at", ""))
        if f.get("source") and f["source"] != "benchmark":
            s = g.node("source", _slug(f["source"]), f["source"], f.get("arrived_at", ""))
            g.fact(s, "Recognised from a file that arrived", "Files", f.get("arrived_at", ""))
            g.edge(n["id"], s["id"], "feeds")


def build(plane, accounts: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    g, processes = _G(), []
    _people(g, accounts)
    _warehouse(g, plane)
    _threads(g, plane, processes)
    _files(g, plane)
    ym = today.isoformat()[:7]
    things = [{"name": label, "count": sum(n["kind"] == k for n in g.nodes.values()),
               "new": any(n["kind"] == k and n["since"].startswith(ym) for n in g.nodes.values())} for k, label in KINDS]
    nodes = [{k: v for k, v in n.items() if k != "since"} for n in g.nodes.values()]
    return {"nodes": nodes, "edges": list(g.edges.values()), "processes": processes, "things": [t for t in things if t["count"]],
            "empty": not any(n["kind"] != "person" for n in nodes)}
