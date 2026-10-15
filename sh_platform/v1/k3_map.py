"""K3 (card K1 of the v4 round) The Map centre: data flow, process maps, definitions and health, all generated from records.

Nothing is drawn by hand. Data flow is read from the catalogue layers (`e0a_catalogue`), the build plans (`build/<pid>/plan-v*.json`),
their run logs, the landing records of loaded files, the dashboards (`consume/<pid>/dashboards/*.json`) and the warehouse's source
systems. Process maps are the signed intents' swim lanes. Definitions are `k2_map.concepts`. Health counts, per source, what is late,
stale, rejected, unverified or open as a break.

Read-only. The data team (analyst, company admin) sees every layer; anyone else sees only what belongs to a project or dashboard they may
open (G1 / cx_dash) and no source, file or table detail. Counts that depend on warehouse rows are limited to the portfolios the person
may see (E1d); where that is nothing, a count is None ("Not available yet"), never 0.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sh_platform.jsonfile import read_json_strict
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import wh

log = logging.getLogger(__name__)

TEAM = {"analyst", "company_admin"}
STAGES = ("source", "file", "bronze", "silver", "gold", "dashboard", "person")
STAGE_WORDS = {"source": "Sources", "file": "Files", "bronze": "Raw data", "silver": "Company model",
               "gold": "Ready for reports", "dashboard": "Dashboards", "person": "People"}
CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 31, "quarterly": 92}
STALE_DAYS = 90  # the signed limit check treats a value older than this as stale
BAD_LOAD = ("rejected_totals", "quarantined")
BAD_BATCH = ("quarantined", "rejected", "rejected_totals", "failed")
VERIFIED = ("confirmed", "approved", "approved_official", "rejected")  # anything else is not yet verified
_GOLD = re.compile(r"\bgold_\w+")


def _team(viewer) -> bool:
    return bool(set(getattr(viewer, "roles", ()) or ()) & TEAM)


def _words(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).replace("_", " ")).strip().capitalize()


def _when(v) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(v) -> str | None:
    d = _when(v)
    return d.isoformat(timespec="seconds") if d else None


def _read(path, kind=dict):
    try:
        return read_json_strict(path, kind)
    except (OSError, ValueError):
        return None


# ---- the warehouse side ---------------------------------------------------------------------------------------------------------

def _systems(plane) -> dict[str, dict]:
    """source_code -> {name, owner, cadence}. A warehouse that cannot be read gives no systems (the map shows what the files say)."""
    try:
        with wh.connect(plane, read_only=True) as con:
            users = {str(r[0]): str(r[1]) for r in con.execute("select id, display_name from users").fetchall()}
            rows = con.execute("select id, source_code, source_name, owner_user_id, expected_cadence from source_systems where is_active").fetchall()
            batches = {str(r[0]): r[1:] for r in con.execute(
                "select source_system_id, count(*), max(coalesce(loaded_at, received_at)), count(*) filter (where validation_status in "
                f"({','.join(['?'] * len(BAD_BATCH))})) from source_batches group by source_system_id", list(BAD_BATCH)).fetchall()}
    except Exception:  # noqa: BLE001 - a map must open even when the warehouse is not there yet
        log.warning("the map could not read the source systems", exc_info=True)
        return {}
    return {str(r[1]): {"id": str(r[0]), "name": str(r[2]), "owner": users.get(str(r[3])), "cadence": r[4], "batches": batches.get(str(r[0]))}
            for r in rows}


def _landing(plane) -> dict[str, list[dict]]:
    from sh_platform.v1 import e0c_landing as L
    out: dict[str, list[dict]] = {}
    for r in L._all(plane):
        out.setdefault(str(r.get("source_code") or "upload"), []).append(r)
    return out


def _canon(code: str, known) -> str:
    """A plan's source code ('administrator_export') is the same source as a system's ('administrator'): longest known code on a word boundary."""
    hits = [k for k in known if code == k or code.startswith(k + "_") or k.startswith(code + "_")]
    return max(hits, key=len) if hits else code


# ---- data flow ------------------------------------------------------------------------------------------------------------------

def _plans(plane) -> list[dict]:
    """The newest plan of every project that has one, with its last good run time."""
    from sh_platform.v1 import b6_run as R
    root = plane.path("build")
    out = []
    for d in sorted(root.iterdir() if root.is_dir() else []):
        if not d.is_dir():
            continue
        try:
            plan = R.latest_plan(plane, d.name)
            runs = R.runs(plane, d.name, 50) if plan else []
        except Exception:  # noqa: BLE001 - one unreadable project does not blank the map
            log.warning("a build plan could not be read for the map")
            continue
        if plan:
            ok = next((r.get("finished") for r in runs if r.get("status") in ("ok", "succeeded", "success", "done", "finished") and r.get("finished")), None)
            out.append({**plan, "_last_run": ok})
    return out


def _dashboards(plane, viewer, team: bool = False) -> list[dict]:
    """Dashboards as Consume shows them (the published version). The data team sees every published one (K1: every layer); anyone else
    those they may open (cx_dash.may_view). A draft or a personal dashboard shows only to whom may_view allows (its maker)."""
    from sh_platform.v1 import cx_dash
    root = plane.path("consume")
    out = []
    for f in sorted(root.glob("*/dashboards/*.json") if root.is_dir() else []):
        rec = _read(f)
        if not rec or not rec.get("id") or not rec.get("created_by"):
            continue
        try:
            view = cx_dash.published_view({**rec, "audience": rec.get("audience") or []})
            if view is not None and not rec.get("personal") and team:
                out.append(view)
            elif cx_dash.may_view(plane, viewer, {**rec, "audience": rec.get("audience") or []}):
                out.append(view or rec)
        except Exception:  # noqa: BLE001 - fail closed
            log.warning("a dashboard could not be checked for the map", exc_info=True)
    return out


def _audience_names(plane) -> dict[str, str]:
    try:
        with wh.connect(plane, read_only=True) as con:
            names = {str(r[0]): str(r[1]) for r in con.execute("select id, display_name from users").fetchall()}
            names.update({str(r[0]): str(r[1]) for r in con.execute("select id, group_name from access_groups").fetchall()})
            names.update({str(r[0]): str(r[1]) for r in con.execute(  # a dashboard's maker is a sign-in account id
                "select external_identity_id, display_name from users where external_identity_id is not null").fetchall()})
        return names
    except Exception:  # noqa: BLE001
        return {}


def flow(plane, viewer) -> dict:
    """{stages, nodes, edges}. A node: id, stage, label, owner, last_load, note, project_id, table, fed_by, feeds. Ids are readable and stable:
    source:<code>, files:<code>, table:<name>, dash:<id>, person:<name>."""
    team = _team(viewer)
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str]] = set()
    pstate: dict[str, str] = {}  # project id -> what the viewer may see of it

    def can(pid) -> bool:
        if not pid:
            return team
        if pid not in pstate:
            pstate[pid] = G1.may_see_project(plane, viewer, pid)
        return pstate[pid] in ("full", "read")

    def add(nid: str, stage: str, label: str, **kw) -> dict:
        n = nodes.setdefault(nid, {"id": nid, "stage": stage, "label": label, "owner": None, "last_load": None, "note": "", "project_id": None,
                                   "table": None})
        n.update({k: v for k, v in kw.items() if v not in (None, "")})
        return n

    plans = _plans(plane)
    if team:
        from sh_platform.v1 import e0a_catalogue as E
        systems, landing = _systems(plane), _landing(plane)
        layers = E.layers_view(plane)
        known = set(systems) | set(landing) | {r["source"] for r in layers["bronze"] if r.get("source")}
        for pl in plans:
            known |= {_canon(str(s.get("code")), known) for s in pl.get("sources") or [] if s.get("code")}

        def source(code: str, owner=None) -> str:
            code = _canon(code, known)
            sy = systems.get(code) or {}
            add(f"source:{code}", "source", sy.get("name") or _words(code), owner=sy.get("owner") or owner,
                note=f"Arrives {sy['cadence']}" if sy.get("cadence") else "")
            recs = landing.get(code) or []
            if recs:
                loaded = [_when(r.get("last_load_at")) for r in recs if r.get("state") == "loaded" and r.get("last_load_at")]
                n, last, bad = len(recs), max((d for d in loaded if d), default=None), sum(r.get("state") in BAD_LOAD for r in recs)
            elif sy.get("batches"):  # files loaded straight into the warehouse (seeded, or by a pipeline) leave a batch, not a landing record
                n, last, bad = sy["batches"]
            else:
                return f"source:{code}"
            add(f"files:{code}", "file", f"Files from {sy.get('name') or _words(code)}", owner=sy.get("owner") or owner, last_load=_iso(last),
                note=f"{n} file{'s' if n != 1 else ''}" + (f", {bad} not accepted" if bad else ""))
            edges.add((f"source:{code}", f"files:{code}"))
            return f"files:{code}"

        for code in sorted(known):
            source(code)
        last_by_source = {c: nodes[f"files:{c}"]["last_load"] for c in known if f"files:{c}" in nodes}
        for r in layers["bronze"]:
            front = source(r["source"]) if r.get("source") else None
            add(f"table:{r['name']}", "bronze", _words(f"{r['source']} {r['layout']}"), table=r["name"],
                owner=(systems.get(r["source"]) or {}).get("owner"), last_load=last_by_source.get(r["source"]), note=f"{r['columns']} columns known" if r["columns"] else "")
            if front:
                edges.add((front, f"table:{r['name']}"))
        for r in layers["gold"]:
            add(f"table:{r['name']}", "gold", _words(r["name"].removeprefix("gold_")), table=r["name"], project_id=(r["project_ids"] or [None])[0])

    for pl in plans:
        pid = pl["project_id"]
        if not can(pid):
            continue
        if team:
            for s in pl.get("sources") or []:
                if s.get("code"):
                    source(str(s["code"]), s.get("owner"))
        tbl = {t["name"]: t for t in pl.get("tables") or []}
        for name, t in tbl.items():
            layer = t.get("layer")
            if layer not in ("bronze", "silver", "gold") or (layer != "gold" and not team):
                continue
            add(f"table:{name}", layer, _words(name.removeprefix(f"{layer}_")), table=name, note=t.get("purpose") or "",
                project_id=pid if layer == "gold" else None, owner=pl.get("proposed_by") if layer == "gold" else None,
                last_load=_iso(pl.get("_last_run")) if layer == "gold" else None,
                state=pl.get("state") if layer == "gold" else None)
            if layer == "bronze":
                for s in pl.get("sources") or []:
                    code = _canon(str(s.get("code")), known) if team else ""
                    if code and name.startswith(f"bronze_{s['code']}_"):
                        front = f"files:{code}" if f"files:{code}" in nodes else f"source:{code}"
                        edges.add((front, f"table:{name}"))
                        nodes[f"table:{name}"]["last_load"] = nodes[f"table:{name}"]["last_load"] or nodes[front]["last_load"]
        # Lineage runs through warehouse tables the map does not draw (bronze -> position_snapshots -> gold): join each drawn table to the
        # nearest drawn tables upstream, so a gold table names the raw tables it is built from (P33) and agrees with the trail.
        ups: dict[str, set[str]] = {}
        for e in list(pl.get("lineage") or []) + [{"from": d, "to": n} for n, t in tbl.items() for d in t.get("depends_on") or []]:
            ups.setdefault(str(e.get("to")), set()).add(str(e.get("from")))

        def drawn_above(name: str, seen: set[str]) -> set[str]:
            out: set[str] = set()
            for u in ups.get(name, ()):
                if u not in seen:
                    seen.add(u)
                    out |= {u} if f"table:{u}" in nodes else drawn_above(u, seen)
            return out
        for b in ups:
            if f"table:{b}" in nodes:
                edges.update((f"table:{a}", f"table:{b}") for a in drawn_above(b, {b}))

    names = _audience_names(plane)
    from sh_platform.v1 import b7_studio
    sched = {pl["project_id"]: pl.get("schedule") or {} for pl in plans}

    def _name(who) -> str | None:  # a name for an account, user or group id; never the id itself
        return names.get(str(who)) or (str(who) if who and not re.fullmatch(r"[0-9a-f-]{32,36}", str(who)) else None)
    for d in _dashboards(plane, viewer, team):
        did = f"dash:{d['id']}"
        add(did, "dashboard", d.get("title") or "Dashboard", owner=_name(d.get("created_by")), last_load=_iso(d.get("published_at") or d.get("updated_at")),
            project_id=d.get("project_id"), note=b7_studio.schedule_words(sched[d["project_id"]]) if d.get("project_id") in sched else "")  # as the dashboard header says it
        for g in dict.fromkeys(m for t in d.get("tiles") or [] for m in _GOLD.findall(str(t.get("sql") or ""))):
            if f"table:{g}" in nodes:
                edges.add((f"table:{g}", did))
        for who in d.get("audience") or []:
            if label := _name(who):
                add(f"person:{label}", "person", label)
                edges.add((did, f"person:{label}"))
    for a, b in edges:
        nodes[a].setdefault("feeds", []).append(b)
        nodes[b].setdefault("fed_by", []).append(a)
    for n in nodes.values():
        n.setdefault("feeds", []), n.setdefault("fed_by", [])
        n["feeds"].sort(), n["fed_by"].sort()
    order = {s: i for i, s in enumerate(STAGES)}
    return {"stages": [{"id": s, "label": STAGE_WORDS[s]} for s in STAGES],
            "nodes": sorted(nodes.values(), key=lambda n: (order[n["stage"]], n["label"].lower())),
            "edges": [{"from": a, "to": b} for a, b in sorted(edges)]}


# ---- process maps ---------------------------------------------------------------------------------------------------------------

def processes(plane, viewer) -> list[dict]:
    """Every signed intent's swim lane the viewer may open. A project the viewer may only preview shows its title and no steps."""
    from sh_platform.v1 import i5_graph
    out = []
    for iid, sow in i5_graph._sows(plane):
        if sow.get("state") != "signed":
            continue
        prj = P.project_of(plane, iid) or {}
        lvl = G1.may_see_project(plane, viewer, prj["id"]) if prj.get("id") else "full"
        if lvl == "none":
            continue
        proc = sow.get("process") or {}
        steps = [s for s in proc.get("steps") or [] if isinstance(s, dict)]
        if not steps:
            continue
        sigs = [s for s in sow.get("signatures") or [] if isinstance(s, dict)]
        out.append({"iid": iid, "project_id": prj.get("id"), "title": prj.get("title") or sow.get("title") or (sow.get("goal") or {}).get("line") or iid,
                    "owner": (prj.get("people") or {}).get("raiser") or prj.get("started_by"), "signed_on": _iso((sigs[-1] if sigs else sow.get("signature") or {}).get("at")),
                    "locked": lvl == "preview", "process": {"steps": [], "handovers": []} if lvl == "preview" else
                    {"steps": steps, "handovers": [h for h in proc.get("handovers") or [] if isinstance(h, dict)]}})
    return sorted(out, key=lambda p: str(p["title"]).lower())


# ---- definitions ----------------------------------------------------------------------------------------------------------------

def definitions(plane, viewer) -> list[dict]:
    from sh_platform.v1 import k2_map
    return k2_map.concepts(plane, viewer)


# ---- health ---------------------------------------------------------------------------------------------------------------------

def health(plane, viewer, now: datetime | None = None) -> dict:
    """Per source: late, stale, rejected loads, values not yet verified, open breaks. The data team only; warehouse counts follow E1d."""
    if not _team(viewer):
        return {"sources": [], "totals": {}, "allowed": False}
    from sh_platform.v1 import e1_access as A
    now = now or wh.now()
    systems, landing = _systems(plane), _landing(plane)
    codes = sorted(set(systems) | set(landing))
    admin = A.is_admin(viewer)
    ports = None if admin else sorted(A.visible_portfolios(plane, viewer))
    seen = admin or bool(ports)  # None below means "not available yet": nothing of the warehouse is the viewer's to count
    scope = "" if admin else f" and portfolio_id in ({','.join(['?'] * len(ports))})" if ports else " and false"
    args = [] if admin else list(ports or [])
    stats: dict[str, dict] = {c: {"stale": 0, "unverified": 0, "breaks": 0, "bad_refs": set(), "last_batch": None} for c in codes}
    total_breaks = 0
    try:
        with wh.connect(plane, read_only=True) as con:
            sysid = {v["id"]: c for c, v in systems.items()}
            for sid, last in con.execute("select source_system_id, max(received_at) from source_batches group by source_system_id").fetchall():
                if (c := sysid.get(str(sid))) is not None:
                    stats[c]["last_batch"] = _when(last)
            for sid, ref, bid in con.execute("select source_system_id, batch_reference, id from source_batches where validation_status in ('quarantined','rejected','rejected_totals','failed')").fetchall():
                if (c := sysid.get(str(sid))) is not None:
                    stats[c]["bad_refs"].add(str(ref or bid))
            if seen:
                rows = con.execute(
                    "with live as (select v.*, coalesce(b.source_system_id, d.source_system_id) src from valuation_observations v "
                    " left join source_records r on r.id = v.source_record_id left join source_batches b on b.id = r.source_batch_id "
                    " left join documents d on d.id = v.evidence_document_id "
                    " where not exists (select 1 from valuation_observations s where s.supersedes_valuation_id = v.id)" + scope.replace("portfolio_id", "v.portfolio_id") + ")"
                    " select src, instrument_id, valuation_date, approval_status, row_number() over (partition by instrument_id, coalesce(portfolio_id, '') "
                    " order by valuation_date desc, recorded_at desc) from live", args).fetchall()
                owner_of: dict[str, str] = {}
                for src, inst, vdate, status, rn in rows:
                    c = sysid.get(str(src))
                    if c is None:
                        continue
                    if status not in VERIFIED:
                        stats[c]["unverified"] += 1
                    if rn == 1:
                        owner_of[str(inst)] = c
                        if _when(str(vdate)) < now - timedelta(days=STALE_DAYS):
                            stats[c]["stale"] += 1
                for inst, in con.execute("select instrument_id from exceptions where exception_type = 'break' and status not in ('resolved','rejected')" + scope, args).fetchall():
                    total_breaks += 1
                    if inst is not None and str(inst) in owner_of:
                        stats[owner_of[str(inst)]]["breaks"] += 1
    except Exception:  # noqa: BLE001 - health must open; the warehouse counts then read "Not available yet"
        log.warning("the map could not read warehouse health", exc_info=True)
        seen = False
    out = []
    for c in codes:
        sy, recs, st = systems.get(c) or {}, landing.get(c) or [], stats[c]
        stamps = [_when(r.get("received_at")) for r in recs] + [st["last_batch"]]
        last = max((s for s in stamps if s), default=None)
        days = CADENCE_DAYS.get(str(sy.get("cadence")))
        late = None if days is None or last is None else max(0, (now - last).days - days)
        out.append({"code": c, "name": sy.get("name") or _words(c), "owner": sy.get("owner"), "cadence": sy.get("cadence"),
                    "last_received": _iso(last), "never_received": last is None, "days_late": late or None, "is_late": bool(late),
                    "rejected": sum(r.get("state") in BAD_LOAD for r in recs) + len(st["bad_refs"] - {str(r.get(k)) for r in recs for k in ("sha256", "file_id")}),  # a file in both lists counts once
                    "stale": st["stale"] if seen else None, "unverified": st["unverified"] if seen else None, "open_breaks": st["breaks"] if seen else None})
    try:  # W2-connectors mount line 4: a late or failed connector marks its source late
        from sh_platform.v1.c5_connect import ops as C5
        feed = C5.map_feed(plane)
        for s in out:
            if (f := feed.get(s["code"])) and f["is_late"]:
                s["is_late"], s["connector_failed"] = True, f["failed"]
    except Exception:  # noqa: BLE001 - health must open without the connector feed
        log.warning("the map could not read connector health", exc_info=True)
    return {"allowed": True, "sources": out, "totals": {"late": sum(s["is_late"] for s in out), "rejected": sum(s["rejected"] for s in out),
                                                         "open_breaks": total_breaks if seen else None}}
