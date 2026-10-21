"""Harbor 3.0 Knowledge, the use case story: each use case from the person who asked down to the files, the office's domains, the data model in plain
words (logical and physical) and one list of decisions and rules. Built only from records the office already keeps: threads (v3_harbor), figure records
(v3_figstore), the pack's recipes (v3_recipes), signals (v3_signals), the model (v3_model) and the warehouse row counts. Nothing is invented: a link is drawn
only when a record names it. Company only, like v3_knowledge; ordering is fixed; the whole read is kept for a few seconds per company and data stamp."""
from __future__ import annotations

import logging
import re
import threading
import time
from functools import lru_cache

import yaml

from sh_platform.v1 import v3_figstore as FS
from sh_platform.v1 import v3_harbor as H
from sh_platform.v1 import v3_recipes as R
from sh_platform.v1 import wh

log = logging.getLogger(__name__)
# domain id (the recipe file's name) -> plain name; the order is the tie-break for a thread that is equally in two
DOMAINS = {"cash": "Capital calls and cash", "invest": "Investments and returns", "hold": "Holdings and risk", "report": "Reporting",
           "operate": "Operations and data", "family": "Family", "office": "Office"}
OTHER = "other"
STAGE = {"drafting": "Being drafted", "decision1": "Waiting for the brief to be confirmed", "working": "Being built", "decision2": "Waiting for the files to be confirmed",
         "decision3": "Waiting to go live", "live": "Live", "question": "Waiting for an answer"}
GATES = {"decision1": "Brief confirmed", "decision2": "Files confirmed", "decision3": "Went live"}
WHY = {"person": "You said", "loader": "How the data is read", "ASSUMPTIONS A5": "How the data is read", "ASSUMPTIONS A1": "How the data is read",
       "ASSUMPTIONS A2": "How the data is read", "ASSUMPTIONS A7": "The written recipe", "ASSUMPTIONS A8": "The written recipe"}
DOMAIN_CAP = 12  # boxes a domain row draws
TTL = 20  # seconds a read is kept; a changed file moves the stamp earlier
_LOCK = threading.RLock()
_KEPT: dict[str, tuple] = {}


def plain(name) -> str:
    return re.sub(r"\s+", " ", str(name or "").replace("_", " ")).strip()


def words(text) -> str:
    """A sentence with table names in the office's words: cash_movements -> cash movements."""
    return re.sub(r"\b[a-z]+(?:_[a-z]+)+\b", lambda m: m.group(0).replace("_", " "), str(text or ""))


def _day(v) -> str:
    return str(v or "")[:10]


def _short(v) -> str:
    """2026-10-21 -> 21 Oct."""
    try:
        return f"{int(str(v)[8:10])} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(str(v)[5:7]) - 1]}"
    except (ValueError, IndexError):
        return str(v or "")


def _slug(s) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:60]


def recipe_domains() -> dict[str, str]:
    """recipe id -> the domain it is written in (the recipes folder has one file per domain)."""
    return {r["id"]: r["domain"] for r in R._file()["recipes"] if r.get("domain") in DOMAINS}


@lru_cache(maxsize=None)
def rule_codes(rid: str) -> tuple[tuple[str, bool], ...]:
    """The signed rule codes a recipe reads: ((code, prefix)), from the literal codes in its SQL and tie-out."""
    r = R.recipe(rid) or {}
    sql = f"{r.get('sql') or ''} {(r.get('tie_out') or {}).get('sql') or ''}"
    out = []
    for m in re.finditer(r"rule_code\s*(=|like|in)\s*(\([^)]*\)|'[^']*')", sql, re.I):
        for c in re.findall(r"'([^']+)'", m.group(2)):
            out.append((c.rstrip("%"), m.group(1).lower() == "like" or c.endswith(("%", "_"))))
    return tuple(sorted(set(out)))


def _stamp(plane) -> tuple:
    parts = []
    for rel in (("v3", "threads"), ("v3", "figures"), ("v3", "signals"), ("warehouse",)):
        d = plane.path(*rel)
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.is_file():
                    s = p.stat()
                    parts.append((p.name, s.st_mtime_ns, s.st_size))
    p = plane.path("v3", "files.json")
    parts.append(p.stat().st_mtime_ns if p.is_file() else 0)
    return (tuple(parts), int(time.time() // TTL))


# ---- the read ---------------------------------------------------------------------------------------------------------------------------

def _rules_in_force(plane) -> list[dict]:
    try:
        with wh.connect(plane, read_only=True) as con:
            rows = con.execute("select r.rule_code, r.rule_type, v.definition_text, v.version_number, v.effective_from, v.approved_at, u.display_name from rule_versions v "
                               "join business_rules r on r.id = v.business_rule_id left join users u on u.id = v.approved_by "
                               "where v.approval_status = 'approved' and v.effective_to is null order by r.rule_code").fetchall()
    except Exception:  # noqa: BLE001 - a warehouse that cannot be read just now leaves the signed rules out; the rest of the story stands
        log.info("knowledge story: rules not read", exc_info=True)
        return []
    return [{"code": c, "type": t, "text": str(x or ""), "version": v, "from": _day(f), "at": _day(a), "signer": s or ""} for c, t, x, v, f, a, s in rows]


def _counts(plane) -> dict[str, int]:
    from sh_platform.v1.v3_figures import table_rows
    try:
        return table_rows(plane)
    except Exception:  # noqa: BLE001 - counts we cannot give are left off, never guessed
        log.info("knowledge story: row counts not read", exc_info=True)
        return {}


def _roles_of(plane, accounts) -> dict[str, dict]:
    """display name -> {email, role}: the job the office gave the person (the pack's role title) or else their account role."""
    from sh_platform.v1 import v3_ops as O, v3_roles as VR
    titles = {r["id"]: str(r.get("title") or r["id"]) for r in VR._roles(plane)}
    jobs = VR._jobs(plane) if hasattr(VR, "_jobs") else {}
    out = {}
    for a in accounts:
        email = str(a.get("email") or "").strip().casefold()
        role = titles.get(jobs.get(email)) or ", ".join(r.replace("_", " ") for r in a.get("roles") or [])
        out[str(a.get("display_name") or "")] = {"email": email, "role": role}
    return out


_SIG: dict[str, tuple] = {}


def _signals(plane) -> list[dict]:
    """The usable signals; the library is parsed from many files, so it is kept until one of them changes."""
    from sh_platform.v1 import v3_model as M
    folder = getattr(M.pack_of(plane), "folder", None)
    st = tuple((p.name, p.stat().st_mtime_ns) for d in (folder and folder / "signals", plane.path("v3", "signals", "office")) if d and d.is_dir() for p in sorted(d.glob("*.yaml")))
    with _LOCK:
        got = _SIG.get(plane.company_id)
    if got and got[0] == st:
        return got[1]
    out = _signals_read(plane)
    with _LOCK:
        _SIG[plane.company_id] = (st, out)
    return out


def _signals_read(plane) -> list[dict]:
    from sh_platform.v1 import v3_roles as VR, v3_signals as SG
    holder = {r["id"]: r.get("person") for r in VR._roles(plane)}
    out = []
    for s in SG.library(plane):
        if s.get("error") or s.get("disabled"):
            continue
        refs = {str((s.get("trigger") or {}).get("figure") or "")} | {str(i.get("recipe") or i.get("id") or "") for i in s.get("inputs") or [] if i.get("kind") == "figure"}
        out.append({"id": s["id"], "title": s.get("title") or s["id"], "refs": refs - {""}, "to": holder.get(s.get("route_to")) or s.get("role_title") or "",
                    "message": re.sub(r"[{}]", "", str(s.get("message") or "")).split(". ")[0]})
    return sorted(out, key=lambda s: s["id"])


def _domain_of(recipes: list[str]) -> str:
    seen = [recipe_domains().get(r) for r in recipes]
    seen = [d for d in seen if d in DOMAINS]
    return max(DOMAINS, key=lambda d: (seen.count(d), -list(DOMAINS).index(d))) if seen else OTHER


def _item(kind, key, label, sub="", detail=(), **more) -> dict:
    """One box of the story; `detail` is the right panel: (heading, text) pairs, the empty ones left out."""
    return {"id": f"{kind}:{key}", "kind": kind, "label": label, "sub": sub, "detail": [{"k": k, "v": v} for k, v in detail if v], "shared": [], **more}


def _kinds(names) -> str:
    return ", ".join(sorted({n.rsplit(".", 1)[-1].lower() for n in names if "." in n}))


def _thread_story(plane, th, ctx) -> dict:
    """One thread's story with every item; `ctx` carries the shared reads (figure records, counts, rules, signals, files, people)."""
    tid, rec, sow = th["id"], th.get("record") or {}, ctx["sows"].get(th.get("iid") or "") or {}
    figs = []
    gold_of = {f["kpi"]: f for f in th.get("figures") or [] if isinstance(f, dict)}
    for name, link in sorted((th.get("figs") or {}).items()):
        fr = ctx["figures"].get(link.get("id"))
        if not fr:
            continue
        ver = FS.version(fr, link.get("v")) or FS.version(fr) or {}
        bf = ver.get("built_from") or {}
        rid = bf.get("id") if bf.get("kind") == "recipe" else None
        r = R.recipe(rid) if rid else None
        reads = list(ver.get("reads") or (r or {}).get("may_read") or [])
        g = gold_of.get(name) or ctx["gold_by_fig"].get(fr["id"]) or {}
        figs.append({"rec": fr, "ver": ver, "name": fr["name"], "recipe": r, "rid": rid, "reads": sorted(set(reads)), "table": g.get("table"), "words": g.get("words"),
                     "status": ver.get("status") or "draft", "v": ver.get("v")})
    domain = _domain_of([f["rid"] for f in figs if f["rid"]])
    # rules: the signed rules the recipes read (by the codes in their SQL), and the rules the signed brief itself states
    rules: dict[str, tuple] = {}
    for f in figs:
        for code, prefix in rule_codes(f["rid"]) if f["rid"] else ():
            for ru in ctx["rules"]:
                if ru["code"].startswith(code) if prefix else ru["code"] == code:
                    rules.setdefault(ru["code"], (ru, set()))[1].add(f["name"])
    items: dict[str, list] = {k: [] for k in ("decisions", "kpis", "gold", "silver", "bronze", "used_by")}
    edges: list[list[str]] = []
    signer = rec.get("signed_by") or th.get("started_by") or ""
    if rec or sow.get("state") == "signed":
        items["decisions"].append(_item("brief", tid, "Brief signed", f"{signer} · version {rec.get('version') or 1}",
                                        detail=[("Signed by", f"{signer}" + (f" ({ctx['people'].get(signer, {}).get('role')})" if ctx["people"].get(signer, {}).get("role") else "")),
                                                ("Signed on", _day(rec.get("signed_at"))), ("Question in the brief", str((th.get("brief") or {}).get("question") or (sow.get("goal") or {}).get("line") or ""))]))
    gates = [e for e in th.get("events") or [] if e.get("kind") == "decision_done"]
    for i, e in enumerate(gates[:3]):
        if i:  # the first gate is the brief itself
            by = e.get("by") if e.get("by") not in (None, "Harbor", "You") else th.get("started_by") or ""
            items["decisions"].append(_item("gate", f"{tid}:{i}", list(GATES.values())[i], f"{by} · {_short(e.get('at'))}", detail=[("When", _day(e.get("at"))), ("By", by), ("What was said", str(e.get("text") or ""))]))
    for ru, users in rules.values():
        items["decisions"].append(_item("rule", ru["code"], plain(ru["code"]).capitalize(), f"Rule · version {ru['version']} · {ru['signer']}",
                                        detail=[("What it says", ru["text"]), ("Version", str(ru["version"])), ("Signed by", ru["signer"]), ("Signed on", ru["at"]), ("Read by", ", ".join(sorted(set(users))))]))
    for text in th.get("rules") or []:
        items["decisions"].append(_item("brule", _slug(text), str(text)[:90], f"Rule in the brief · {signer}", detail=[("What it says", str(text)), ("Stated in", "the signed brief"), ("Signed by", signer)]))
    # assumptions: "What I assumed" of the figure versions this use case uses, the ones a person or Harbor gave first
    said = {}
    for f in figs:
        for a in f["ver"].get("assumptions") or []:
            t = str(a.get("text") or "").strip()
            if t:
                said.setdefault(t, {"source": a.get("source") or "", "figs": []})["figs"].append(f["name"])
    for t, a in sorted(said.items(), key=lambda kv: (kv[1]["source"] in WHY, kv[0])):
        key, shown = _slug(t)[:50], words(t)
        items["decisions"].append(_item("assumption", key, shown if len(shown) <= 80 else shown[:77] + "...", "Assumed · " + WHY.get(a["source"], a["source"] or "Harbor"),
                                        detail=[("What I assumed", shown), ("Where it is recorded", WHY.get(a["source"], a["source"] or "Harbor")), ("Used by", ", ".join(sorted(set(a["figs"]))))]))
        edges += [[f"assumption:{key}", f"kpi:{f['rec']['id']}"] for f in figs if f["name"] in a["figs"]]
    # KPIs, gold, silver
    silver_seen: dict[str, list] = {}
    for f in figs:
        fr, kid = f["rec"], f"kpi:{f['rec']['id']}"
        owner = f["ver"].get("approved_by") or ""
        used = [u for u in fr.get("used_by") or [] if u.get("thread") != tid]
        built = f"recipe {f['recipe']['label']}" if f["recipe"] else "a design made for this use case"
        items["kpis"].append(_item("kpi", fr["id"], f["name"], f"{f['status']} · {'recipe' if f['recipe'] else 'design'}", status=f["status"], tables=f["reads"],
                                   links=[{"label": "Open the figure page", "to": f"/v3/knowledge/figures/{fr['id']}"}],
                                   detail=[("Means", str(fr.get("definition") or "")), ("Status", f"{f['status']}, version {f['v']}"), ("Built from", built),
                                           ("Reads", ", ".join(plain(t) for t in f["reads"]) or "nothing recorded yet"),
                                           ("Never reads", ", ".join(plain(t) for t in (f["recipe"] or {}).get("never_read") or []) or ""),
                                           ("Also used by", ", ".join(sorted({str(u.get("brief") or "") for u in used if u.get("brief")}))),
                                           ("Owner", f"{owner} · version {f['v']} · {f['status']} {_short(_day((f['ver'].get('runs') or [{}])[-1].get('at')))}" if owner else "")]))
        edges.append(["brief:" + tid, kid]) if items["decisions"] and items["decisions"][0]["kind"] == "brief" else None
        edges += [[f"rule:{ru['code']}", kid] for ru, users in rules.values() if f["name"] in users]
        if f["table"]:
            tid_g = f"gold:{f['table']}"
            if not any(i["id"] == tid_g for i in items["gold"]):
                n = ctx["counts"].get(f["table"])
                items["gold"].append(_item("gold", f["table"], f["words"] or plain(f["table"].removeprefix("gold_")), f"{n:,} rows" if n is not None else "",
                                           detail=[("Rows", f"{n:,}" if n is not None else "not counted"), ("Holds", f["name"]), ("Table", plain(f["table"]))]))
            edges.append([tid_g, kid])  # edges run the way the data moves: bronze, silver, gold, KPI, use
            edges += [[f"silver:{t}", tid_g] for t in f["reads"]]
        for t in f["reads"]:
            silver_seen.setdefault(t, []).append(f["name"])
    for t in sorted(silver_seen):
        n = ctx["counts"].get(t)
        items["silver"].append(_item("silver", t, plain(t), f"{n:,} rows" if n is not None else "",
                                     detail=[("Rows", f"{n:,}" if n is not None else "not counted"), ("Read by", ", ".join(sorted(set(silver_seen[t])))),
                                             ("What it is", "one table of the office's clean model, shared by every use case")]))
    # bronze: files recognised for this use case by the source they were read as, the brief's sources, documents and reference files
    by_src: dict[str, list] = {}
    for fl in ctx["files"]:
        if fl.get("thread") == tid and fl.get("status") in ("recognised", "loaded"):
            by_src.setdefault(fl.get("source") or "Files", []).append(fl)
    sources = {str(s.get("name")): s for s in sow.get("sources") or [] if isinstance(s, dict) and s.get("name")} | {s: {} for s in th.get("sources") or []}
    for name in sorted(set(by_src) | set(sources), key=str.lower):
        fs = by_src.get(name, [])
        kinds = _kinds(f["name"] for f in fs)
        held = (sources.get(name) or {}).get("holds")
        items["bronze"].append(_item("bronze", _slug(name), name, (f"{len(fs)} files" + (f" · {kinds}" if kinds else "")) if fs else "named in the brief",
                                     detail=[("Files read", str(len(fs))), ("File types", kinds), ("Holds", str(held or "")), ("Newest", max((_day(f.get("arrived_at")) for f in fs), default=""))]))
    for key, label, names in (("documents", "Documents read", list((th.get("docs") or {}).keys())), ("reference", "Reference files", list((th.get("pack") or {}).keys()))):
        if names:
            items["bronze"].append(_item("bronze", f"{tid}-{key}", label, f"{len(names)} · {_kinds(names)}", detail=[("Files", str(len(names))), ("File types", _kinds(names))]))
    for b in items["bronze"]:
        edges += [[b["id"], s["id"]] for s in items["silver"]]
    # used by: the board, the morning note, the signals that watch its recipes
    rids = {f["rid"] for f in figs if f["rid"]} | {f["rec"]["id"] for f in figs}
    if th.get("stage") == "live" and th.get("pid") and th.get("mode") != "process":
        items["used_by"].append(_item("board", tid, "Board", th["title"], detail=[("What it is", "The live board of this use case"), ("Shows", ", ".join(f["name"] for f in figs))]))
    if (th.get("note") or {}).get("figures"):
        items["used_by"].append(_item("note", tid, "Morning note", "read by " + str((th.get("brief") or {}).get("read_by") or (sow.get("goal") or {}).get("readers") or "the team"),
                                      detail=[("What it is", "The note Harbor writes after each run"), ("Figures in it", str(len(th["note"]["figures"])))]))
    for s in ctx["signals"]:
        hit = [f for f in figs if f["rid"] in s["refs"] or f["rec"]["id"] in s["refs"]]
        if hit:
            items["used_by"].append(_item("signal", s["id"], "Signal", f"{s['title']}" + (f" → {s['to']}" if s["to"] else ""),
                                          detail=[("Watches", ", ".join(f["name"] for f in hit)), ("Says", s["message"]), ("Goes to", s["to"])]))
    for u in items["used_by"]:
        if u["kind"] == "signal":
            edges += [[f"kpi:{f['rec']['id']}", u["id"]] for f in figs if f["rid"] in next(s for s in ctx["signals"] if s["id"] == u["id"].split(":", 1)[1])["refs"]
                      or f["rec"]["id"] in next(s for s in ctx["signals"] if s["id"] == u["id"].split(":", 1)[1])["refs"]]
        else:
            edges += [[f"kpi:{f['rec']['id']}", u["id"]] for f in figs]
    ids = {i["id"] for g in items.values() for i in g}
    asker = th.get("started_by") or rec.get("started_by") or ""
    first = next((str(e.get("text") or "") for e in th.get("events") or [] if e.get("kind") == "person"), "")
    return {"id": tid, "title": th["title"], "stage": th["stage"], "stage_label": STAGE.get(th["stage"], th["stage"]), "live": th["stage"] == "live", "domain": domain,
            "who": {"name": asker, "role": ctx["people"].get(asker, {}).get("role", ""), "at": _day(th.get("created"))}, "asked": first,
            **items, "edges": sorted({(a, b) for a, b in edges if a in ids and b in ids}), "recipes": sorted(rids)}


def _read(plane, accounts) -> dict:
    from sh_platform.v1 import i5_graph
    ctx = {"figures": {r["id"]: r for r in FS.every(plane)}, "counts": _counts(plane), "rules": _rules_in_force(plane), "signals": _signals(plane),
           "files": H.read_files(plane), "people": _roles_of(plane, accounts), "sows": dict(i5_graph._sows(plane))}
    ths = H.all_threads(plane)
    ctx["gold_by_fig"] = {}
    for th in ths:  # a reused figure answers from the table of the thread that made it
        for name, link in (th.get("figs") or {}).items():
            g = next((f for f in th.get("figures") or [] if f.get("kpi") == name and f.get("table")), None)
            if g and not link.get("reused"):
                ctx["gold_by_fig"].setdefault(link["id"], g)
    stories = sorted((_thread_story(plane, th, ctx) for th in ths), key=lambda s: (s["title"].lower(), s["id"]))
    users: dict[str, set] = {}
    for s in stories:  # which use cases share an item
        for k in ("decisions", "kpis", "gold", "silver", "bronze"):
            for i in s[k]:
                users.setdefault(i["id"], set()).add(s["id"])
    titles = {s["id"]: s["title"] for s in stories}
    for s in stories:
        for k in ("decisions", "kpis", "gold", "silver", "bronze"):
            for i in s[k]:
                if i["kind"] != "gate" and i["kind"] != "brief":
                    i["shared"] = [{"id": t, "title": titles[t]} for t in sorted(users[i["id"]] - {s["id"]}, key=lambda t: (titles[t].lower(), t))]
    return {"stories": stories, "ctx": ctx, "titles": titles}


def base(plane, accounts) -> dict:
    key = plane.company_id
    st = _stamp(plane)
    with _LOCK:
        got = _KEPT.get(key)
        if got and got[0] == st:
            return got[1]
    b = _read(plane, accounts)
    with _LOCK:
        _KEPT[key] = (st, b)
    return b


# ---- the answers ------------------------------------------------------------------------------------------------------------------------

def _row(s) -> dict:
    return {"id": s["id"], "title": s["title"], "stage": s["stage"], "stage_label": s["stage_label"], "live": s["live"], "asked_by": s["who"]["name"],
            "role": s["who"]["role"], "figures": len(s["kpis"]),
            "find": " ".join([s["title"], s["who"]["name"], s["who"]["role"], *(i["label"] for k in ("kpis", "gold", "silver", "bronze") for i in s[k])]).lower()}


def domain_list(stories) -> list[dict]:
    names = {**DOMAINS, OTHER: "Other"}
    return [{"id": d, "name": n, "count": sum(s["domain"] == d for s in stories)} for d, n in names.items()]


def usecases(plane, accounts) -> dict:
    ss = base(plane, accounts)["stories"]
    groups = [{"domain": d["id"], "name": d["name"], "count": d["count"], "items": [_row(s) for s in ss if s["domain"] == d["id"]]} for d in domain_list(ss) if d["count"]]
    return {"groups": groups, "domains": domain_list(ss), "total": len(ss)}


def usecase(plane, accounts, tid) -> dict | None:
    b = base(plane, accounts)
    s = next((s for s in b["stories"] if s["id"] == tid), None)
    if s is None:
        return None
    return {**{k: v for k, v in s.items() if k != "recipes"}, "domain": {"id": s["domain"], "name": {**DOMAINS, OTHER: "Other"}[s["domain"]]}, "conversation": f"/v3/thread/{tid}"}


def domain(plane, accounts, did) -> dict | None:
    b = base(plane, accounts)
    names = {**DOMAINS, OTHER: "Other"}
    if did not in names:
        return None
    cols = [s for s in b["stories"] if s["domain"] == did]
    rows = {}
    for key, label in (("decisions", "Decisions"), ("kpis", "KPIs"), ("gold", "Gold"), ("silver", "Silver"), ("bronze", "Bronze")):
        seen: dict[str, dict] = {}
        for c, s in enumerate(cols):
            for i in s[key]:
                if key == "decisions" and i["kind"] in ("assumption", "gate"):
                    continue  # the assumptions are on each story; here the rules and the signed briefs
                e = seen.setdefault(i["id"], {"id": i["id"], "label": i["label"], "sub": i["sub"], "kind": i["kind"], "cols": [], "shared_outside": bool(i.get("shared")) and not all(
                    o["id"] in {x["id"] for x in cols} for o in i["shared"])})
                e["cols"].append(c)
        items = sorted(seen.values(), key=lambda e: (e["cols"][0], e["label"].lower(), e["id"]))
        hidden = 0
        if key in ("silver", "bronze", "gold") and len(items) > DOMAIN_CAP:  # the most shared first; the rest are counted, never drawn
            keep = {e["id"] for e in sorted(items, key=lambda e: (-len(e["cols"]), e["label"].lower(), e["id"]))[:DOMAIN_CAP]}
            hidden, items = len(items) - DOMAIN_CAP, [e for e in items if e["id"] in keep]
        rows[key] = {"label": label, "items": items, "hidden": hidden}
    return {"id": did, "name": names[did], "usecases": [{"id": s["id"], "title": s["title"], "who": s["who"]["name"], "role": s["who"]["role"]} for s in cols],
            "people": len({s["who"]["name"] for s in cols if s["who"]["name"]}), "rows": rows, "others": [d for d in domain_list(b["stories"]) if d["id"] != did]}


def decisions(plane, accounts) -> dict:
    b = base(plane, accounts)
    out: dict[str, dict] = {}
    for s in b["stories"]:
        for i in s["decisions"]:
            e = out.setdefault(i["id"], {"id": i["id"], "kind": {"brief": "decision", "gate": "decision", "rule": "rule", "brule": "rule", "assumption": "assumption"}[i["kind"]],
                                   "label": i["label"], "sub": i["sub"], "detail": i["detail"], "usecases": []})
            e["usecases"].append({"id": s["id"], "title": s["title"]})
    in_force = {r["code"] for r in b["ctx"]["rules"]}
    for r in b["ctx"]["rules"]:  # every signed rule in force, whether or not a use case reads it yet
        e = out.setdefault(f"rule:{r['code']}", {"id": f"rule:{r['code']}", "kind": "rule", "label": plain(r["code"]).capitalize(), "sub": f"Rule · version {r['version']} · {r['signer']}",
                                                 "detail": [{"k": k, "v": v} for k, v in (("What it says", r["text"]), ("Version", str(r["version"])), ("Signed by", r["signer"]), ("Signed on", r["at"])) if v], "usecases": []})
    order = {"rule": 0, "decision": 1, "assumption": 2}
    items = sorted(out.values(), key=lambda e: (order[e["kind"]], -len(e["usecases"]), e["label"].lower(), e["id"]))
    for e in items:
        e["usecases"].sort(key=lambda u: (u["title"].lower(), u["id"]))
    return {"items": items, "counts": {k: sum(e["kind"] == k for e in items) for k in order}, "in_force": len(in_force)}


# ---- the data model ---------------------------------------------------------------------------------------------------------------------

def logical(plane, accounts) -> dict:
    from sh_platform.v1 import v3_model as M
    b = base(plane, accounts)
    pack, _lay, mobjs, _cols, _props = M._model_state(plane)
    model = {"pack": {"id": pack.industry, "label": pack.label, "version": pack.version} if pack is not None else None,
             "objects": [{**o, "count": b["ctx"]["counts"].get(o["table"])} for o in mobjs]}
    reads: dict[str, list] = {}  # table -> the figures that read it
    for s in b["stories"]:
        for k in s["kpis"]:
            for t in k["tables"]:
                reads.setdefault(t, []).append({"id": k["id"].split(":", 1)[1], "name": k["label"], "usecase": {"id": s["id"], "title": s["title"]}})
    objs = []
    byname = {o["name"]: o for o in model["objects"]}
    for o in model["objects"]:
        rel = [{"to": r["to"], "to_label": byname[r["to"]]["label"], "label": r["label"]} for r in o.get("relations") or [] if r.get("to") in byname]
        kp = {}
        for k in reads.get(o["table"], []):
            kp.setdefault(k["id"], {"id": k["id"], "name": k["name"], "usecases": []})["usecases"].append(k["usecase"])
        objs.append({"id": o["name"], "label": o["label"], "about": o.get("about") or "", "count": o.get("count"), "table": plain(o["table"]),
                     "properties": [{"label": p.get("label") or p["name"], "derived": p.get("derived")} for p in o.get("properties") or []],
                     "relations": rel, "kpis": sorted(kp.values(), key=lambda k: (k["name"].lower(), k["id"]))})
    return {"objects": objs, "pack": model.get("pack")}


def physical(plane, accounts, kpi: str | None = None) -> dict:
    b = base(plane, accounts)
    counts = b["ctx"]["counts"]
    gold = {}
    for s in b["stories"]:
        for g in s["gold"]:
            gold.setdefault(g["id"].split(":", 1)[1], {"id": g["id"], "label": g["label"], "rows": counts.get(g["id"].split(":", 1)[1]), "usecase": s["title"]})
    silver = [{"id": f"silver:{t}", "label": plain(t), "rows": n} for t, n in counts.items() if not t.startswith(("gold_", "bronze_"))]
    silver.sort(key=lambda r: (-(r["rows"] or 0), r["label"]))
    src: dict[str, list] = {}
    for fl in b["ctx"]["files"]:
        if fl.get("status") in ("recognised", "loaded"):
            src.setdefault(fl.get("source") or "Files", []).append(fl["name"])
    bronze = [{"id": f"bronze:{_slug(n)}", "label": n, "rows": len(v), "kinds": _kinds(v)} for n, v in sorted(src.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))]
    kpis: dict[str, dict] = {}
    for s in b["stories"]:
        by_id = {k["id"]: k for k in s["kpis"]}
        for kid, k in sorted(by_id.items()):
            fid = kid.split(":", 1)[1]
            e = kpis.setdefault(fid, {"id": fid, "name": k["label"], "status": k["status"], "usecases": [], "gold": set(), "silver": set(), "bronze": set(), "used_by": []})
            e["usecases"].append({"id": s["id"], "title": s["title"], "who": s["who"]["name"]})
            for g, c in s["edges"]:
                if c == kid and g.startswith("gold:"):
                    e["gold"].add(g)
                    e["silver"] |= {z for z, x in s["edges"] if x == g and z.startswith("silver:")}
            e["bronze"] |= {i["id"] for i in s["bronze"]}
            e["used_by"] += [{"kind": u["kind"], "label": u["label"], "sub": u["sub"]} for u in s["used_by"] if (kid, u["id"]) in set(map(tuple, s["edges"]))]
    rows = []
    for e in sorted(kpis.values(), key=lambda e: (e["name"].lower(), e["id"])):
        rows.append({**{k: e[k] for k in ("id", "name", "status", "usecases", "used_by")}, "gold": sorted(e["gold"]), "silver": sorted(e["silver"]), "bronze": sorted(e["bronze"])})
    pick = next((r for r in rows if r["id"] == kpi), None)
    return {"bronze": {"items": bronze, "total": sum(x["rows"] for x in bronze)}, "silver": {"items": silver, "total": len(silver)},
            "gold": {"items": sorted(gold.values(), key=lambda g: (-(g["rows"] or 0), g["label"])), "total": len(gold)}, "kpis": {"items": rows, "total": len(rows)},
            "picked": pick, "path": {"gold": pick["gold"], "silver": pick["silver"], "bronze": pick["bronze"]} if pick else None}
