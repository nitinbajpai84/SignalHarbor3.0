"""Harbor 3.0 Knowledge, the office's own records beyond its threads: figure records, pack recipes, signed rules, signals, key documents and the
ranked use cases. Called by v3_knowledge.build; every node has facts with a source and a date, every edge a plain-word reason. Nothing is invented:
a link is drawn only when a record names it or its words match. Built once per request; documents, signals and use cases are capped."""
import json
import logging
import re

from sh_platform.v1 import wh

log = logging.getLogger(__name__)
MAX_DOCS, MAX_SIGNALS, MAX_CARDS = 16, 40, 24
DOC_FIG = {"capital_call_notice": "call", "distribution_notice": "distribut", "investment_report": "nav", "manager_statement": "nav"}
SKIP = {"fund", "with", "from", "that", "this", "than", "must", "over", "each", "entit"}


def _t(v, n=300) -> str:
    return str(v or "").strip()[:n]


def _toks(s) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{4,}", str(s).lower())} - SKIP


def _day(v) -> str:
    return str(v or "")[:10]


def _figures(g, plane) -> dict[str, str]:
    """Figure records: status and versions, what each reads, the recipe it was built from, the use cases that use it. -> {recipe id: figure node id}."""
    from sh_platform.v1 import v3_figstore as FS, v3_recipes as R
    try:
        from sh_platform.v1.v3_pack_readers import KINDS as PK
    except Exception:  # noqa: BLE001 - without the readers a figure names no source
        PK = {}
    by_recipe: dict[str, str] = {}
    for rec in FS.every(plane):
        ver = FS.version(rec) or {}
        runs = [r for v in rec["versions"] for r in v.get("runs") or []]
        last = _day(max((r["at"] for r in runs), default=""))
        f = g.node("figure", g.slug(rec["name"]), rec["name"], last)
        word = {"verified": "checked and current", "held": "held back", "draft": "a draft"}.get(ver.get("status"), ver.get("status") or "new")
        g.fact(f, f"Version {rec.get('current_v')} of {len(rec['versions'])}, {word}", "Figure record", last)
        f["status"], f["versions"] = ver.get("status") or "", len(rec["versions"])
        if h := FS.hold_of(rec):
            g.fact(f, f"A newer version is held: {h['reason']}", "Figure record", last)
        if rec.get("definition"):
            g.fact(f, f"Means {rec['definition']}", "Figure record", last)
        if ver.get("tie_out"):
            g.fact(f, ("Adds up: " if ver["tie_out"].get("ok") else "Does not add up: ") + str(ver["tie_out"].get("rule")), "Figure record", _day(ver["tie_out"].get("at")))
        bf = ver.get("built_from") or {}
        if bf.get("kind") == "recipe":
            r = R.recipe(bf["id"]) or {}
            rn = g.node("recipe", bf["id"], r.get("label") or bf["id"].replace("_", " "))
            g.fact(rn, r.get("why") or r.get("formula") or "A written recipe", "Pack recipes")
            g.edge(f["id"], rn["id"], "built from", f"{rec['name']} follows the written recipe {rn['label']}")
            by_recipe[bf["id"]] = f["id"]
        for t in ver.get("reads") or []:
            for label, _skill, goes_to in PK.values():
                if t.replace("_", " ") in goes_to and f"source:{g.slug(label)}" in g.nodes:
                    g.edge(f["id"], f"source:{g.slug(label)}", "reads", f"{rec['name']} reads {label}")
        for u in rec.get("used_by") or []:
            g.edge(f["id"], f"usecase:{u.get('thread')}", "used by", f"{u.get('brief') or 'A use case'} uses {rec['name']}")
    return by_recipe


def _rules(g, plane) -> None:
    """The signed office rules in force: each signed by a person, limiting a figure it is read against or the entity of the portfolio it names."""
    with wh.connect(plane) as con:
        rows = con.execute("select r.rule_code, r.rule_type, v.definition_text, v.parameters, v.effective_from, v.approved_at, u.display_name from rule_versions v "
                           "join business_rules r on r.id = v.business_rule_id left join users u on u.id = v.approved_by "
                           "where v.approval_status = 'approved' and v.effective_to is null order by r.rule_code").fetchall()
        ports = dict(con.execute("select p.portfolio_code, e.entity_name from portfolios p join legal_entities e on e.id = p.legal_entity_id").fetchall())
    figs = [n for n in g.nodes.values() if n["kind"] == "figure"]
    for code, typ, text, params, frm, at, signer in rows:
        n = g.node("rule", code, _t(text, 70), _day(at))
        g.fact(n, text, "Signed rule", _day(at))
        g.fact(n, f"In force from {_day(frm)}", "Signed rule", _day(at))
        if p := g.person(signer):
            g.edge(n["id"], p, "signed by", f"{signer} signed this rule")
            g.fact(n, f"Signed by {signer}", "Signed rule", _day(at))
        pr = json.loads(params) if isinstance(params, str) else params or {}
        ent = ports.get(pr.get("portfolio_code") or pr.get("portfolio"))
        if ent and (k := next((k for k, x in g.nodes.items() if x["kind"] == "entity" and x["label"] == ent), None)):
            g.edge(n["id"], k, "limits", f"The rule applies to the portfolios of {ent}")
        want = _toks(" ".join([code.replace("_", " "), text, str(pr.get("dimension") or "")]))
        for f in figs:
            if want & _toks(f["label"]):
                g.edge(n["id"], f["id"], "limits", f"{f['label']} is read against this rule")
                g.edge(f["id"], n["id"], "checked by", f"{f['label']} is checked against this rule")


def _signals(g, plane, accounts, by_recipe) -> None:
    """Signals that fired, or that watch a figure this office has; each goes to a person."""
    from sh_platform.v1 import v3_signals as SG
    stats = SG.stats(plane)
    from sh_platform.v1 import v3_roles as VR
    holder = {r["id"]: r.get("person") for r in VR._roles(plane)}  # the person who holds each role of the pack
    picked = []
    for s in SG.library(plane):
        if s.get("error") or s.get("disabled"):
            continue
        watch = [by_recipe[r] for r in (i.get("recipe") or i.get("id") for i in s.get("inputs") or [] if i.get("kind") == "figure") if r in by_recipe]
        if s["id"] in stats or watch:
            picked.append((s["id"] not in stats, s["id"], s, watch))
    for _, sid, s, watch in sorted(picked, key=lambda x: x[:2])[:MAX_SIGNALS]:
        st = stats.get(sid, {})
        n = g.node("signal", sid, s["title"], _day(st.get("last_fired")))
        n["fired"] = st.get("fired", 0)
        g.fact(n, f"Fired {st['fired']} time{'s' * (st['fired'] != 1)}" if st else "Has not fired yet", "Fired signals", _day(st.get("last_fired")))
        if s.get("hold"):
            g.fact(n, "While open it holds: " + str(s["hold"]["blocks"]).replace("_", " "), "Signal definition")
        g.fact(n, _t(re.sub(r"[{}]", "", s["message"]).split(". ")[0], 200), "Signal definition")
        for f in watch:
            g.edge(n["id"], f, "watches", f"{s['title']} reads this figure")
        trig = s["trigger"]
        if trig.get("on") == "file_arrived" and trig.get("kind"):
            if fl := next((x for x in g.nodes.values() if x["kind"] == "file" and x["label"].lower().endswith("." + str(trig["kind"]))), None):
                g.edge(n["id"], fl["id"], "watches", f"{s['title']} looks at each {trig['kind']} file that arrives")
        if p := g.person(holder.get(s["route_to"])):
            g.edge(n["id"], p, "goes to", f"{s['title']} is routed to {s.get('role_title') or 'this person'}")


def _documents(g, plane) -> None:
    """Key documents: the latest notices, investment reports and fund terms, each about a fund and stating the value a figure adds up."""
    kinds = ("capital_call_notice", "distribution_notice", "investment_report", "fund_terms")
    per, seen = max(2, MAX_DOCS // len(kinds)), {}
    with wh.connect(plane) as con:
        docs = con.execute("select d.id, d.document_type, d.title, d.document_date, d.received_at, i.canonical_name from documents d left join instruments i on i.id = d.instrument_id "
                           "where d.document_type in (" + ",".join("?" * len(kinds)) + ") order by d.document_date desc nulls last", list(kinds)).fetchall()
        for did, typ, title, ddate, rec, fund in docs:
            if seen.get(typ, 0) >= per:
                continue
            seen[typ] = seen.get(typ, 0) + 1
            n = g.node("document", str(did), f"{typ.replace('_', ' ').capitalize()}: {title}", _day(ddate))
            g.fact(n, f"A {typ.replace('_', ' ')} dated {_day(ddate)}", "Documents", _day(rec or ddate))
            for fn, vt, vn, ccy, pg in con.execute("select field_name, value_text, value_numeric, currency, page_number from extracted_fields where document_id = ? "
                                                   "and (value_text is not null or value_numeric is not null) limit 4", [did]).fetchall():
                val = vt if vt is not None else f"{float(vn):,.2f}".rstrip("0").rstrip(".") + (f" {ccy}" if ccy else "")
                g.fact(n, f"{fn.replace('_', ' ').capitalize()}: {val}" + (f" (page {pg})" if pg else ""), f"Document: {title}", _day(rec or ddate))
            if fund and (k := next((k for k, x in g.nodes.items() if x["kind"] == "fund" and x["label"] == fund), None)):
                g.edge(n["id"], k, "about", f"The document is about {fund}")
            for f in (x for x in list(g.nodes.values()) if x["kind"] == "figure" and DOC_FIG.get(typ, "~") in x["label"].lower()):
                g.edge(n["id"], f["id"], "states", f"The document states a value that {f['label']} adds up")


def _cards(g, plane, by_recipe) -> None:
    """The ranked top-50 use cases of the pack that this office already has a figure or a signal for: asked by a person, answered with figures."""
    from sh_platform.v1 import v3_model as M
    pack = M.pack_of(plane)
    if pack is None:
        return
    try:
        doc = pack.section("use_cases_100")
    except KeyError:
        return
    who = {p["id"]: p["person"] for p in doc.get("people") or []}
    added = 0
    for c in sorted((c for c in doc.get("use_cases") or [] if (c.get("priority") or 99) <= 50), key=lambda c: c["priority"]):
        figs = [by_recipe[r] for r in (c.get("reuses") or {}).get("recipes") or [] if r in by_recipe]
        sigs = [k for k in g.nodes if k.startswith("signal:" + c["id"])]
        if not (figs or sigs) or added >= MAX_CARDS:
            continue
        added += 1
        n = g.node("usecase", c["id"], c["title"])
        n["stage"] = "suggested"
        g.fact(n, f"Question: {_t(c.get('question'))}", "Use case library")
        g.fact(n, f"Suggested, never enforced; the person decides ({c.get('cadence') or 'on request'})", "Use case library")
        if p := g.person(who.get(c.get("owner"))):
            g.edge(n["id"], p, "asked by", f"{g.nodes[p]['label']} is who asks this")
        for f in figs:
            g.edge(n["id"], f, "answers with", f"{c['title']} is answered with {g.nodes[f]['label']}")
        for sk in sigs:
            g.edge(sk, n["id"], "feeds", f"{g.nodes[sk]['label']} belongs to this use case")


def add(g, plane, accounts) -> None:
    by_recipe = _figures(g, plane)
    _rules(g, plane)
    _signals(g, plane, accounts, by_recipe)
    _documents(g, plane)
    _cards(g, plane, by_recipe)
