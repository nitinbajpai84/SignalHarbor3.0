"""Figure recipes (assumptions A7 and A8): a common figure is built from a written recipe, not designed again by the model on every build.

A recipe (packs/family_office/1/recipes.yaml) names the tables its figure MAY read and the ones it must NEVER read, the formula in words, the SQL over the
company model, and a tie-out. This module matches a brief's figure to a recipe, renders its SQL for one table name, checks that any design of such a figure reads
only the allowed tables, runs the tie-out on the trial-run copy (a line of Decision 3), and keeps a model design that worked as an office skill so the next
build of that figure in that office reuses it word for word. The pack's recipes are suggestions: an office edits or replaces them.

Hooks: `place` in b10_design.design (recipe or saved design first, the model for the rest), `allowed` in the same function (a design that reads a table the
recipe forbids is dropped), `install` in v3_figures.install (Decision 3 gets the tie-out lines and a figure that does not tie out is held).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

log = logging.getLogger(__name__)
FILE = Path(__file__).resolve().parents[2] / "packs" / "family_office" / "1" / "recipes.yaml"
DESIGN = "model.design-ready-table"
MARK, SAVED = "Recipe ", "Saved design "
COUNTLIKE = re.compile(r"\b(?:number of|count of|how many|counts?)\b", re.I)  # a count of breaks is not the break ("Matched trades count", c7)
# "Breaks over 5,000": the break; its threshold is the signed tolerance, applied when the figure is answered (v3_rule_checks)
THRESHOLD = re.compile(r"\s*\b(?:over|above|exceed\w*|more than|at least|greater than)\s+[$\d][\d,.]*\s*[km]?\b.*$", re.I)
TOL = 0.01


# ---- the recipes ---------------------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _file() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def recipes() -> list[dict]:
    return _file()["recipes"]


def recipe(rid: str) -> dict | None:
    return next((r for r in recipes() if r["id"] == rid), None)


def _words(text) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip() + " "


SPLIT = re.compile(r"\b(?:(?:by|per|for each|each)\s+[a-z]+|in\s+[a-z]{3})\b", re.I)  # "cash by entity", "net worth in usd": a split or a unit, not another figure


def match(kpi: dict, strict: bool = True) -> dict | None:
    """The recipe a brief's figure is, by the names it answers to and by words: the longest name in the figure's own name wins, a word set scores
    above a short name. A count is not the recipe's figure; a threshold ("breaks over 5,000") is cut off the name. A name that matches nothing
    ("Variance over 5,000") is matched by the word sets of its name and definition together. A one-word name ("cash", "break") is the figure only
    when it is the whole name, less its split: "Distributions incoming cash" and "Net break in USD" are other figures (c6 fixc). `strict=False`
    (a question's words) lets a one-word name match anywhere."""
    name = THRESHOLD.sub("", str(kpi.get("name") or ""))
    if not name.strip() or COUNTLIKE.search(name):
        return None
    text, have = _words(name), set(_words(name).split())
    core = _words(SPLIT.sub(" ", name)).strip()
    best, score = None, 0
    for r in recipes():
        got = max([10 + len(n) for n in r.get("names") or [] if _words(n) in text and (not strict or " " in n.strip() or _words(n).strip() == core)] or [0])
        if r.get("words_all") and all(have & set(g) for g in r["words_all"]):
            got = max(got, 25)
        if got > score:
            best, score = r, got
    if best is None and kpi.get("definition"):
        full = set(_words(f"{name} {kpi['definition']}").split())
        best = next((r for r in recipes() if r.get("words_all") and all(full & set(g) for g in r["words_all"])), None)
    return best


# ---- Decision 1: each figure of the brief is bound to a recipe by what it means, once ----------------------------------------------------
# The binding sits on the brief's figure (built_from: a recipe id, "" for none; built_from_why; built_from_by: who suggested it; built_from_confirmed:
# who confirmed it) and on the thread (th["bindings"]). Every later step reads it through `bound`: the design, the answer, the monthly runs.

BIND = "intent.define-figure"  # the binding is part of the figure's card
RULES, SPAN = "the rules", "Span"
BIND_TASK = "extraction"  # the router's fast tier: a small model for one typed question
BIND_SYSTEM = (
    "You bind the figures of a brief to the pack's written recipes. For each figure answer one question: which of these recipes computes this figure, "
    "or none? Evidence standard: bind only when the recipe computes that very quantity, the same thing measured from the kind of records the brief names. "
    "Decide by the figure's definition, its formula, the sources and the brief's question (`brief_question`); the figure's name is only a hint. "
    "A count of items (number of breaks, matches count) is not the recipe's amount, so it is none. A threshold or tolerance in the name ('over 5,000') "
    "does not change the figure: it is applied when the figure is answered. The drafted formula can be loose or only restate the threshold; decide by "
    "what the figure measures. A total, a split or a subset of the recipe's quantity (summed, by entity, only the unmatched ones, only those over a "
    "threshold) is that recipe's figure: the answer reads the recipe's table. A figure that only uses the recipe's result (its share, its count) is none. "
    "When the evidence is not clear, answer none. Never invent a recipe id. `brief_question` is North's summary; `said` is the person's own words. "
    'Reply with JSON only: {"bindings": [{"figure": <figure id>, "recipe": <recipe id or "none">, "why": <one plain sentence>}]}.')


def described() -> dict[str, str]:
    """The recipes in plain words for the judge's options, and the option that none computes the figure."""
    return {**{r["id"]: f"{r['label']}: {r['formula']}" for r in recipes()}, "none": "No recipe here computes this figure; Span designs a table for it."}


def bound(k: dict) -> dict | None:
    """The recipe the figure is built and answered from: its binding when it has one ("" is none), never a new match by name. A figure with no
    binding at all (a brief from before Decision 1 bound its figures) falls back to the name match."""
    if "built_from" in k:
        return recipe(k["built_from"]) if k["built_from"] else None
    return match(k)


def _sig(k: dict) -> str:
    return hashlib.sha256(json.dumps([k.get(f) for f in ("name", "definition", "formula")], default=str).encode("utf-8")).hexdigest()[:12]


def _ask(plane, model, ctx: dict) -> dict | None:
    """The typed question, a small model at temperature 0; the reply is kept by a hash of its input, so the same brief binds the same way. None when
    there is no model or the call fails twice (the rules' binding stands)."""
    if model is None or os.environ.get("SH_MODEL_PROVIDER", "").lower() == "off":
        return None
    from sh_platform.agents import loop
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.agents.runs import RunRegistry
    from sh_platform.build.agents.runtime import OpenGate
    from sh_platform.egress.providers import TEMPERATURE
    from sh_platform.v1.egress_fit import fit
    from sh_platform.v1.router import route
    ctx, ask = fit(ctx), "For each figure: which of these recipes computes this figure, or none?"  # records as one-line strings: the row guard lets them out
    kept = plane.path("v3", "bind_cache", hashlib.sha256(json.dumps([BIND_SYSTEM, BIND_TASK, ctx, ask], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:32] + ".json")
    try:
        if kept.is_file():
            return json.loads(kept.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("a kept binding reply could not be read", exc_info=True)
    for attempt in (1, 2):
        token = TEMPERATURE.set(0)
        try:
            res = loop.run_agent(route(model, "span", BIND_TASK, "", plane, want_json=True), ToolRegistry(OpenGate()), plane.company_id, "m3_connect", "Span",
                                 BIND_SYSTEM, ctx, ask, recorder=RunRegistry(plane))
            a, b = res.text.find("{"), res.text.rfind("}")
            got = json.loads(res.text[a:b + 1]) if res.status == "done" and 0 <= a < b else None
        except Exception:  # noqa: BLE001 - asked again once; then the rules' binding stands
            log.warning("the binding call %s failed", attempt, exc_info=True)
            got = None
        finally:
            TEMPERATURE.reset(token)
        if isinstance(got, dict) and isinstance(got.get("bindings"), list):
            try:
                kept.parent.mkdir(parents=True, exist_ok=True)
                kept.write_text(json.dumps(got, sort_keys=True), encoding="utf-8")
            except OSError:
                log.warning("a binding reply could not be kept", exc_info=True)
            return got
    return None


def bind(plane, model, kpis: list[dict], question: str = "", sources: list[dict] | None = None, said: str = "") -> bool:
    """Bind each figure that has no binding yet (or whose words changed since a machine bound it) to a recipe by its meaning. The rules are the first
    pass (the name, then the words of the name and definition together); the figures they leave go to one typed model question. A binding a person
    chose or confirmed is kept. A recipe the question's words name that no figure is bound to is added as a suggested figure, bound to it (the person
    removes it at Decision 1). Writes onto the figures in place (`kpis` is the brief's own list);
    True when any binding changed."""
    todo = [k for k in kpis if isinstance(k, dict) and k.get("name") and not k.get("built_from_confirmed")
            and ("built_from" not in k or (k.get("built_from_by") in (RULES, SPAN) and k.get("built_from_sig") != _sig(k)))]
    if not todo:
        return False
    for k in todo:
        r = match(k)
        k.update(built_from=r["id"] if r else "", built_from_by=RULES, built_from_sig=_sig(k),
                 built_from_why=f"Its name or definition names the {r['label'].lower()} recipe." if r else "No recipe of the pack computes it; Span designs it.")
    left = [k for k in todo if not k["built_from"]]
    if left:  # by meaning: the figures the rules could not bind
        ctx = {"brief_question": question, **({"said": said} if said else {}),
               "sources": [{"name": s.get("name"), "holds": s.get("holds")} for s in sources or [] if isinstance(s, dict)],
               "figures": [{"id": i, **{f: k.get(f) for f in ("name", "definition", "formula", "unit")}} for i, k in enumerate(left)],
               "recipes": [{"id": r["id"], "label": r["label"], "also_called": r.get("names") or [], "formula": r["formula"], "reads": r["may_read"],
                            "why": r.get("why", "")} for r in recipes()]}
        got = _ask(plane, model, ctx) or {}
        if model is not None:  # two models of different families bind each figure; a figure they agree on is bound, the rest keep the single model's binding
            from sh_platform.v1 import v3_judge as J
            ids_ = [r["id"] for r in recipes()]
            for i, k in enumerate(left):
                from sh_platform.v1.egress_fit import fit
                one = fit({**ctx, "figures": [ctx["figures"][i]]})  # records as one-line strings: the row guard lets them out
                said = J.judged(plane, "recipe", J.question("recipe", figure=k.get("name"), definition=k.get("definition") or "not given", formula=k.get("formula") or "not given"),
                                [*ids_, "none"], one, J.standard("recipe"), person=False, describe=described())
                if said:
                    got.setdefault("bindings", [])[:] = [b for b in got.get("bindings") or [] if str(b.get("figure")) != str(i)] + [
                        {"figure": i, "recipe": said, "why": "Two models of different families agreed."}]
        ids = {**{str(i): k for i, k in enumerate(left)}, **{k["name"]: k for k in left}}  # a reply may name the figure instead of its id
        for b in got.get("bindings") or []:
            if isinstance(b, dict) and str(b.get("figure")) in ids and recipe(str(b.get("recipe"))):
                ids[str(b["figure"])].update(built_from=b["recipe"], built_from_why=str(b.get("why") or "")[:300], built_from_by=SPAN)
    have = {k.get("built_from") for k in kpis if isinstance(k, dict)}
    first = todo[0]
    for r in recipes():  # ponytail: the question's own words name the recipe and no figure is bound to it: added as a suggestion the person can drop.
        if r["id"] not in have and (asks(question, r) or asks(said, r)):  # A small model's yes/no varied from run to run here (c7); words do not.
            k = {"code": f"K{len(kpis) + 1:02d}", "name": r["label"], "definition": r["formula"], "formula": r["formula"], "period": first.get("period"),
                 "owner": first.get("owner"), "status": "defined", "pack_suggested": True, "sources_by": "Span"}
            k.update(built_from=r["id"], built_from_why=f"Your question asks for the {r['label'].lower()} and no figure of the brief is built from it.",
                     built_from_by=RULES, built_from_sig=_sig(k))
            kpis.append(k)
    return True


def asks(question: str, r: dict) -> bool:
    """The question's own words name the recipe: one of its phrases, or a word from each of its word groups."""
    text = _words(question)
    return any(" " in n.strip() and _words(n) in text for n in r.get("names") or []) or bool(
        r.get("words_all") and all(set(text.split()) & set(g) for g in r["words_all"]))


def shown(k: dict) -> str:
    """The brief's "Built from" line: "Cash break recipe (suggested)", or who confirmed it."""
    r = bound(k)
    what = f"{r['label']} recipe" if r else "No recipe: Span designs it"
    return what + (f" (confirmed by {k['built_from_confirmed']})" if k.get("built_from_confirmed") else " (suggested)")


def bindings(kpis: list[dict]) -> list[dict]:
    """The thread's copy of the bindings: figure, recipe, why, who suggested it, who confirmed it."""
    return [{"figure": k["name"], "recipe": k.get("built_from") or None, "why": k.get("built_from_why") or "", "by": k.get("built_from_by") or "",
             "confirmed_by": k.get("built_from_confirmed")} for k in kpis if isinstance(k, dict) and k.get("name") and "built_from" in k]


def _sow_write(plane, iid: str, change) -> dict | None:
    """Apply `change(kpis)` to the brief's figures under its lock (never a signed brief). -> the brief, or None when nothing changed."""
    from sh_platform.jsonfile import lock_for, write_json_atomic
    from sh_platform.v1 import i4_sow as S4
    path = S4.path_of(plane, iid)
    with lock_for(path):
        sow = S4.read(plane, iid)
        if sow.get("state") == "signed" or not change(sow.setdefault("kpis", [])):
            return None
        write_json_atomic(path, sow)
        return sow


def bind_brief(x, sow: dict) -> dict:
    """Decision 1 hook (v3_harbor._north): bind the drafted brief's figures; returns the brief with its bindings."""
    from sh_platform.build.agents.runtime import get_model
    from sh_platform.v1 import v3_skills as SK
    iid = x.th.get("iid")
    if not iid or not sow.get("kpis"):
        return sow
    try:
        model = get_model(x.app.state, x.plane)
        with SK.record(x.plane, x.th.get("id"), BIND) as rec:
            said = " ".join(str(e.get("text") or "") for e in x.th.get("events") or [] if e.get("kind") == "person")[:2000]  # the person's own words
            got = _sow_write(x.plane, iid, lambda ks: bind(x.plane, model, ks, str((sow.get("goal") or {}).get("line") or ""), sow.get("sources"), said))
            rec["detail"] = "bound: " + "; ".join(f"{b['figure']} -> {b['recipe'] or 'none'} ({b['by']})" for b in bindings((got or sow).get("kpis") or []))[:280]
        sow = got or sow
    except Exception:  # noqa: BLE001 - a binding that fails leaves the figure unbound; Decision 1 still shows the brief
        log.warning("the brief's figures could not be bound", exc_info=True)
    x.th["bindings"] = bindings(sow.get("kpis") or [])
    return sow


def choose(plane, iid: str, index: int, value: str, who: str) -> None:
    """The person changes a figure's "Built from" at Decision 1: a recipe id or label, or "none"."""
    v = re.sub(r"\s*\((?:suggested|confirmed by [^)]*)\)$", "", str(value or "").strip().lower()).removesuffix(" recipe")
    r = next((r for r in recipes() if v in (r["id"], r["label"].lower())), None)
    if r is None and v not in ("", "none", "no recipe"):
        raise ValueError(f"No recipe is called {value!r}. One of: {', '.join(r['label'] for r in recipes())}, or none.")

    def change(ks):
        if not 0 <= index < len(ks) or not isinstance(ks[index], dict):
            return False
        ks[index].update(built_from=r["id"] if r else "", built_from_why=f"Chosen by {who}.", built_from_by=who, built_from_sig=_sig(ks[index]))
        return True
    _sow_write(plane, iid, change)


def confirm(plane, th: dict, who: str) -> None:
    """Decision 1 confirmed: each binding becomes the person's, and the thread keeps the copy."""
    iid = th.get("iid")
    if not iid:
        return

    def change(ks):
        mine = [k for k in ks if isinstance(k, dict) and "built_from" in k]
        for k in mine:
            k["built_from_confirmed"] = who or "the person who confirmed the brief"
        return bool(mine)
    try:
        sow = _sow_write(plane, iid, change)
        from sh_platform.v1 import i4_sow as S4
        th["bindings"] = bindings((sow or S4.read(plane, iid)).get("kpis") or [])
    except Exception:  # noqa: BLE001 - never blocks the confirm
        log.warning("the bindings could not be confirmed", exc_info=True)


def stale(kpi: dict, covering: list[dict]) -> bool:
    """A figure with a recipe whose covering tables were not built from that recipe (the rules' tables, a model's): it is built from the recipe too."""
    r = bound(kpi)
    return bool(r) and not any(str(g.get("purpose") or "").startswith(f"{MARK}{r['id']}:") for g in covering)


def dims_for(r: dict, kpi: dict) -> list[str]:
    """The dimensions of the recipe the figure asks for ("by entity"), else the recipe's default."""
    if not r.get("dims"):
        return []
    if r.get("always_dims"):
        return list(r["default_dims"])
    from sh_platform.v1 import b10_design as D
    ask = [D._stem(d) for d in D._dims(kpi, [])]
    return [d for d in r["dims"] if d in ask] or list(r.get("default_dims") or list(r["dims"])[:1])


def render(r: dict, name: str, dims: list[str] | None = None) -> str:
    """The recipe's SQL for the ready table `name` (one line)."""
    f = _file()
    cols = "".join(f"{r['dims'][d][0]} as {r['dims'][d][1]}, " for d in dims or [])
    sql = r["sql"].replace("{dims}", cols).replace("{name}", name).replace("{positions}", f["snippets"]["positions"])
    return " ".join(sql.split())


def table_name(slug: str, r: dict, dims: list[str]) -> str:
    return (f"gold_{slug}_{r['id']}" + (f"_by_{'_'.join(dims)}" if dims else ""))[:63].rstrip("_")


# ---- A8: which tables a design may read ------------------------------------------------------------------------------------------------

def tables_read(sql: str) -> set[str]:
    """The tables a select reads (the common table expressions it defines are not tables)."""
    import sqlglot
    from sqlglot import exp
    q = sqlglot.parse_one(sql, read="duckdb")
    ctes = {c.alias_or_name for c in q.find_all(exp.CTE)}
    made = q.this.name if isinstance(q, exp.Create) and isinstance(q.this, exp.Table) else None  # the table the statement creates is not one it reads
    return {t.name for t in q.find_all(exp.Table) if t.name and t.name not in ctes and t.name != made}


def refusal(r: dict, sql: str) -> str | None:
    """Why a design of this recipe's figure may not stand: it reads a table the recipe does not allow. The reason names the tables it may read."""
    try:
        read = tables_read(sql)
    except Exception:  # noqa: BLE001 - the plan check says what is wrong with SQL that cannot be read
        log.info("the design's SQL could not be read for the tables check", exc_info=True)
        return None
    bad = sorted(read - set(r["may_read"]))
    if not bad:
        return None
    never = sorted(set(bad) & set(r.get("never_read") or []))
    return (f"{r['label']} reads only {', '.join(r['may_read'])}; this design reads {', '.join(bad)}"
            + (f", which it must never read ({r.get('why', '')})" if never else "") + ".")


def allowed(gold: list[dict], notes: list[str], kpis: list[dict] = ()) -> list[dict]:
    """The designed tables that do not break their figure's recipe's tables rule (the recipe the figure is bound to); the others are named in `notes`
    with the reason (b10_design hook)."""
    by_name = {k["name"]: k for k in kpis if isinstance(k, dict) and k.get("name")}
    out = []
    for g in gold:
        why = next((m for k in g.get("kpis") or [] if (r := bound(by_name.get(k) or {"name": k})) and (m := refusal(r, g.get("sql") or ""))), None)
        if why:
            notes.append(f"Span dropped {g.get('name') or 'a table'}: {why}")
        else:
            out.append(g)
    return out


# ---- building from a recipe, or from a design that worked ------------------------------------------------------------------------------------

def _table(slug: str, r: dict, k: dict) -> dict:
    dims = dims_for(r, k)
    name = table_name(slug, r, dims)
    sql = render(r, name, dims)
    keys = [*(r["dims"][d][1] for d in dims), *re.findall(r"\bas (position_date|day|month|valuation_date)\b", sql)[:1]]
    cols = {c: d for c, d in (r.get("columns") or {}).items()}
    return {"name": name, "layer": "gold", "columns": [], "sql": sql, "depends_on": sorted(tables_read(sql)), "grain": r["grain"], "keys": keys, "col_defs": cols,
            "kpis": [str(k["name"])], "purpose": f"{MARK}{r['id']}: {r['label']} from the pack's recipe, a suggestion you can edit. {r['formula']}"}


def saved(plane, figure: str) -> dict | None:
    """The design this office saved for the figure, or None."""
    from sh_platform.v1 import v3_skills as SK
    try:
        return (SK._meta(plane, skill_id(figure)) or {}).get("design")
    except Exception:  # noqa: BLE001 - a skill that cannot be read is not reused
        log.warning("a saved design could not be read", exc_info=True)
        return None


def skill_id(figure: str) -> str:
    from sh_platform.v1 import v3_skills as SK
    return "office.design-" + (SK._slug(figure) or "figure")


def _from_saved(slug: str, k: dict, d: dict) -> dict:
    name = f"gold_{slug}_{d['suffix']}"[:63].rstrip("_")
    return {"name": name, "layer": "gold", "columns": [], "sql": d["sql"].replace("{name}", name), "depends_on": d["depends_on"], "grain": d.get("grain", ""),
            "keys": d.get("keys") or [], "col_defs": d.get("col_defs") or {}, "kpis": [str(k["name"])],
            "purpose": f"{SAVED}{k['name']}: the design this office kept the last time it gave rows. {d.get('purpose', '')}"[:300]}


def place(plane, viewer, pid: str, kpis: list[dict], slug: str, grain: dict, plan: dict, notes: list[str]) -> list[dict]:
    """b10_design hook. Each figure that has a recipe, else a design this office saved, is placed from it and passes the plan check like any other design.
    Returns the figures still to design (the model is asked only for those); the placed ones lose their "could not place" note."""
    from sh_platform.v1 import b6_span as S
    made: dict[str, dict] = {}
    left: list[dict] = []
    for k in kpis:
        r = bound(k)
        d = None if r else saved(plane, k["name"])
        try:
            t = _table(slug, r, k) if r else _from_saved(slug, k, d) if d else None
        except Exception:  # noqa: BLE001 - a recipe or a saved design that cannot be rendered leaves the figure to the model
            log.warning("a recipe could not be built for %s", k.get("name"), exc_info=True)
            t = None
        if t is None:
            left.append(k)
        elif t["name"] in made:
            made[t["name"]]["kpis"].append(t["kpis"][0])
        else:
            made[t["name"]] = t
    ok = S.keep_valid(plane, plan, list(made.values()), notes) if made else []
    placed = {n for t in ok for n in t["kpis"]}
    left += [k for k in kpis if k["name"] in {n for t in made.values() for n in t["kpis"]} and k["name"] not in placed]
    plan["tables"] = plan["tables"] + ok
    plan["built_by"] = "recipes" if ok and not left else plan.get("built_by", "rules")
    notes[:] = [n for n in notes if not ((m := re.search(r"could not place the KPI '([^']+)'", n)) and m.group(1) in placed)]
    return [k for k in kpis if k["name"] not in placed]


# ---- remember what worked ---------------------------------------------------------------------------------------------------------------------

def remember(plane, figure: str, g: dict, slug_prefix: str) -> bool:
    """Keep a model design that passed the checks and gave rows as an office skill (office.design-<figure>, in use), the SQL word for word with the table
    name left as {name}. A figure already saved with the same SQL is left alone. ponytail: a skill the person edits or retires in Skills stays theirs; a
    new, different design replaces only a skill Harbor saved."""
    from sh_platform.v1 import v3_skills as SK
    name = str(g["name"])
    if not name.startswith(slug_prefix) or not g.get("sql"):
        return False
    design = {"suffix": name[len(slug_prefix):], "sql": " ".join(str(g["sql"]).split()).replace(name, "{name}"), "depends_on": list(g.get("depends_on") or []),
              "grain": g.get("grain") or "", "keys": list(g.get("keys") or []), "col_defs": dict(g.get("definitions") or g.get("col_defs") or {}), "purpose": g.get("purpose") or ""}
    sid = skill_id(figure)
    with SK.LOCK:
        have = SK._meta(plane, sid)
        if have and (have.get("design") == design or have.get("from") != "v3_recipes.remember"):
            return False
        meta = {"id": sid, "name": f"Design for {figure}", "goal": f"Build the ready table for {figure} the way it worked before.",
                "when": f"Use when {figure} is built again in this office.", "centre": "build", "source": "office", "tier": "fast",
                "version": int((have or {}).get("version") or 0) + 1, "status": "in_use", "from": "v3_recipes.remember", "design": design,
                "why": "A design from the model passed the checks and gave rows on the trial-run copy, so it is reused word for word.",
                "inputs": "The figure of the brief.", "output": "The ready table's SQL, unchanged.",
                "steps": ["Use the saved SQL for this figure with the new table name.", "Run the same checks as for any design."], "tools": [],
                "checks": ["The ready table has rows and a value for the figure."], "never": ["Never change the saved SQL without a person editing this skill."]}
        SK._hist(meta, "Harbor", "Saved a design that worked", meta["version"])
        SK._save(plane, meta)
    return True


# ---- Decision 3: the tie-out ------------------------------------------------------------------------------------------------------------------

def tie_out(con, r: dict, name: str) -> dict | None:
    """Run the recipe's tie-out on the copy. -> {ok, label, a, b} or None when the recipe has none or the table is not in the copy."""
    t = r.get("tie_out")
    if not t:
        return None
    snip = _file()["snippets"]
    sql = t["sql"].replace("{name}", name).replace("{positions_check}", snip["positions_check"])
    try:
        a, b = con.execute(sql).fetchone()
    except Exception:  # noqa: BLE001 - the table was not built on the copy: the figure's own line says so
        log.info("the tie-out of %s could not run", name, exc_info=True)
        return None
    a, b = float(a or 0), float(b or 0)
    return {"ok": abs(a - b) <= TOL, "label": t["label"], "a": a, "b": b}


def _num(v: float) -> str:
    return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"


def recompute(con, r: dict, kpi: dict, name: str) -> dict | None:
    """The figure's table against its own recipe worked out again on the copy: -> {ok, a, b} (the table's total of the recipe's measure, the
    recipe's), or None when it cannot be run. A table the recipe built agrees with itself, so only another table is checked."""
    sql = re.sub(r"^create table \S+ as ", "", render(r, "recheck", dims_for(r, kpi)))
    try:
        a = con.execute(f'select coalesce(sum("{r["measure"]}"), 0) from "{name}"').fetchone()[0]
        b = con.execute(f'select coalesce(sum("{r["measure"]}"), 0) from ({sql}) as q').fetchone()[0]
    except Exception:  # noqa: BLE001 - the table has no such column, or a table is missing: it does not agree
        log.info("the recipe recomputation of %s could not run", name, exc_info=True)
        return {"ok": False, "a": None, "b": None}
    a, b = float(a or 0), float(b or 0)
    return {"ok": abs(a - b) <= TOL, "a": a, "b": b}


def needs(con, r: dict) -> str | None:
    """The first input the recipe needs that has no rows on the copy, as the reason the figure would be wrong, else None."""
    for n in r.get("needs") or []:
        try:
            got = con.execute(n["sql"]).fetchone()[0]
        except Exception:  # noqa: BLE001 - a table that is not there holds nothing
            log.info("the needs check of %s could not run", r["id"], exc_info=True)
            got = 0
        if not got:
            return n["why"]
    return None


def guard(con, r: dict, kpi: dict, g: dict) -> tuple[list[dict], str | None]:
    """Decision 3's checks of a figure bound to recipe `r` with ready table `g`: the tie-out, the recomputation (a table the recipe did not build), the
    inputs the recipe needs. -> (lines, why it is held or None). A held figure is never stated as fact."""
    k, lines, why = kpi["name"], [], None
    if not str(g.get("purpose") or "").startswith(f"{MARK}{r['id']}:"):
        c = recompute(con, r, kpi, g["name"])
        lines.append({"label": f"{k}: against its recipe", "value": "Agrees" if c["ok"] else "Does not agree", "ok": c["ok"],
                      "note": f"{r['label']} worked out again from its recipe" + (f" gives {_num(c['b'])}; the ready table has {_num(c['a'])}." if c["a"] is not None and not c["ok"] else ".")})
        if not c["ok"]:
            why = f"it does not agree with the {r['label'].lower()} recipe worked out again on the same data" + (f" ({_num(c['a'])} against {_num(c['b'])})." if c["a"] is not None else ".")
    t = tie_out(con, r, g["name"])
    if t is not None:
        lines.append({"label": f"{k}: tie-out", "value": "Ties out" if t["ok"] else "Does not tie out", "ok": t["ok"],
                      "note": t["label"] + (f" ({_num(t['a'])}, and the other side {_num(t['b'])})." if not t["ok"] else ".")})
        if not t["ok"] and why is None:
            why = f"{t['label']}: the ready table has {_num(t['a'])} and the other side {_num(t['b'])}."
    if why is None and (n := needs(con, r)):
        lines.append({"label": f"{k}: inputs", "value": "Missing", "ok": False, "note": n})
        why = n
    return lines, why


def held(th: dict | None, name: str) -> dict | None:
    """The figure as Decision 3 held it, or None. The answer path reads a held figure only as "Not available yet: <reason>"."""
    return next((f for f in (th or {}).get("figures") or [] if f.get("kpi") == name and f.get("held")), None)


def finish(x, d: dict) -> dict:
    """Decision 3 (the v3_figures.install hook): each figure bound to a recipe gets its checks on the trial-run copy (`guard`); one that fails is held
    with the reason. Each model design that passed and gave rows is saved for the next build of the figure."""
    from sh_platform.v1 import b9_verify as V, v3_skills as SK
    from sh_platform.v1.v3_figures import _not_loaded, kpis_of
    th, plane = x.th, x.plane
    try:
        pk = x.api("leo", "GET", f"/api/v1/build/p/{th['pid']}/architecture/pack", soft=True).get("pack") or {}
        gold = pk.get("target", {}).get("gold") or []
        figs = {f["kpi"]: f for f in th.get("figures") or [] if "ok" in f}
        kp = {k["name"]: k for k in kpis_of(plane, th.get("iid"))}
        mine = [(k, f, next((g for g in gold if g["name"] == f.get("table")), None)) for k, f in figs.items() if f.get("ok")]
        mine = [(k, f, g) for k, f, g in mine if g]
    except Exception:  # noqa: BLE001 - no pack to read: Decision 3 stays as it was
        log.warning("recipes: the pack could not be read for Decision 3", exc_info=True)
        return d
    lines, hold = [], []
    con = None
    try:
        for k, f, g in mine:
            purpose = str(g.get("purpose") or "")
            kpi = kp.get(k) or {"name": k}
            r = bound(kpi) if k in kp else (recipe(purpose[len(MARK):].split(":", 1)[0]) if purpose.startswith(MARK) else None)
            if r:
                con = con or V._copy(plane)
                got, why = guard(con, r, kpi, g)
                lines += got
                if why:
                    hold.append(k)
                    f.update(ok=False, held=True, reason=why + _not_loaded(th))
                if not any(r_.get("detail") == f"source: recipe {r['id']} for {k}" for r_ in SK.runs(plane, th["id"]) if r_.get("skill") == DESIGN):
                    SK._log_run(plane, th["id"], DESIGN, 0, True, f"source: recipe {r['id']} for {k}")
            elif (th.get("model_tables") or {}).get(g["name"]) and g.get("sql"):
                remember(plane, k, g, f"gold_{_slug_of(plane, th['pid'])}_")
    except Exception:  # noqa: BLE001 - the checks never break Decision 3
        log.warning("recipes: tie-out or save failed", exc_info=True)
    finally:
        if con is not None:
            con.close()
    if lines:
        d["checks"] = [*(d.get("checks") or []), *lines]
    if hold:
        for c in d.get("checks") or []:
            if c.get("label") in hold:
                c.update(ok=False, value="Held: not stated as a figure", note=figs[c["label"]]["reason"])
        d["title"] = "Some figures have no numbers yet. Go live?"
        d["summary"] = (d.get("summary") or "") + f" {len(hold)} figure(s) held because their checks failed: {', '.join(hold)}."
    return d


def _slug_of(plane, pid: str) -> str:
    """The project's slug as the plan names its tables (gold_<slug>_...), the same way b6_span.draft_plan works it out."""
    from sh_platform.v1 import e0a_catalogue as E, p1_project as P1
    from sh_platform.v1.b6_span import slug
    return E.slug_of(P1.read(plane, pid).get("title") or pid) or slug(pid)


def install(H) -> None:
    d3 = H.DECISIONS["decision3"]

    def decision3(x):
        return finish(x, d3(x))
    H.DECISIONS["decision3"] = decision3
