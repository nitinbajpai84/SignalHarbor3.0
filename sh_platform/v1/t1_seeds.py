"""T1b seed templates as document skeletons (V1-BUILD Round 10, card T1b): two per output kind (benchmarks keeps one).

A template is an ordered list of sections: `{key, heading, instruction, example, required, type, columns?, choices?, view?, labels?,
ask?, learn?, parse?, default?}`. `fields` are derived from the sections (`fields_from`) so North's goals and the sign check read the
same keys as before; a record written before sections existed gets them back from its fields (`sections_from_fields`), enriched with
the instruction and example the seed holds for that key. Nothing here calls a model or touches a plane.
"""
from __future__ import annotations

FREE = {"label": "Anything else", "required": False}
FREE_KEY = "comments"
EXTRA = ("columns", "choices", "view", "labels", "ask", "learn", "parse", "default")


def sec(key, heading, instruction="", example="", required=True, type_="long_text", **more) -> dict:
    return {"key": key, "heading": heading, "instruction": instruction, "example": example, "required": required, "type": type_, **more}


def field_of(s: dict) -> dict:
    """The flat field a section stands for (the shape T1 and North's goals read)."""
    f = {"key": s["key"], "label": s["heading"], "help": s.get("instruction", ""), "required": bool(s.get("required")), "type": s.get("type", "text")}
    f.update({k: s[k] for k in ("columns", "choices", "ask", "learn", "parse", "default") if s.get(k)})
    return f


def fields_from(sections: list[dict]) -> list[dict]:
    return [field_of(s) for s in sections]


def sections_from_fields(fields: list[dict], kind: str | None = None, prior: list[dict] | None = None) -> list[dict]:
    """Sections for a flat field list. A key the seed (or the `prior` sections) already knows keeps its instruction, example and view."""
    known = {s["key"]: s for s in SEEDS_BY_KIND.get(kind, [{}])[0].get("sections", [])} if kind else {}
    known.update({s["key"]: s for s in prior or []})
    out = []
    for f in fields:
        old = known.get(f["key"], {})
        s = {**{k: old[k] for k in ("example", "view", "labels") if old.get(k)},
             "key": f["key"], "heading": f.get("label") or f["key"], "instruction": f.get("help") or old.get("instruction", ""),
             "example": old.get("example", ""), "required": bool(f.get("required")), "type": f.get("type", "text")}
        s.update({k: f[k] for k in ("columns", "choices", "ask", "learn", "parse", "default") if f.get(k)})
        out.append(s)
    return out


# ---- the intent of work -----------------------------------------------------------------------------------------------------------

# key, heading, required, type, instruction, example (headings and keys as docs/product/SOW-DONE-CHECKLIST.md and i6_chat's GOALS)
_REPORTING = [
    ("goal", "What you want to build, and why it matters now", True, "long_text", "A line or two: what is wanted and why now.",
     "A monthly wealth report for the family council, so they stop waiting for spreadsheets."),
    ("readers", "Who reads the result and what they decide from it", True, "long_text", "Who reads this and what they decide.",
     "The family council; they decide whether to rebalance and how much to draw."),
    ("frequency", "When it is needed and how often", True, "text", "The date it is needed by, and how often after that.",
     "By the eighth working day each month."),
    ("process", "How it is done today, step by step", True, "list", "Each step, who does it and with which file or system.",
     "1. Custodian sends positions. 2. Analyst copies them into the workbook. 3. Partner reviews and sends."),
    ("result", "What the result looks like", True, "long_text", "The sections of the report and the figures on each.",
     "One page per portfolio: net worth, allocation, performance against benchmark and fees."),
    ("kpis", "The figures, and how you work each one out today", True, "table", "One row per figure, in business words.",
     "Net worth | market value of all positions plus cash | monthly"),
    ("inputs", "Where the data comes from and who owns it", True, "table", "One row per file or system and who looks after it.",
     "Custodian positions file | file | month-end positions | Operations"),
    ("strategic", "Which sources you could not do without", False, "text", "The sources that matter most or are hard to replace.", "The custodian file."),
    ("documents", "Documents or emails it depends on", False, "text", "Policies, statements, notices or emails that feed the result.", "The investment policy statement."),
    ("manual", "What you change by hand before a figure is right", False, "long_text", "Adjustments, reclassifications, overrides and corrections.",
     "Reclassify two accounts the custodian codes wrongly."),
    ("rules", "Who may see what, how long to keep it, who approves a change", True, "long_text", "Access, retention and approval, in plain words.",
     "Family members see their own portfolios; history kept ten years; the partner approves changes."),
    ("disputes", "Limits or definitions that could be disputed", False, "long_text", "Anything two people might read differently, and which document wins.",
     "Whether performance fees count in total cost."),
    ("success", "How you will know it worked", True, "long_text", "What good looks like, in a sentence.",
     "The pack goes out by the eighth working day with no manual copying."),
    ("unclear", "What is still unclear, and who can settle it", True, "list", "Open points, each with the person who can settle it.",
     "Which benchmark applies to the growth portfolio (the partner can settle)."),
    ("extraction", "What to take out of each kind of document", False, "long_text", "For each kind of document, the values to read out of it.",
     "From a monthly statement: account, date, closing value, fees."),
    ("benchmarks", "For each figure, what you reported last period and what it should read after the load", False, "table",  # optional: no prior report, or the usual practice, must never re-open Decision 1 after a confirm
     "One row per figure: last period's figure and what the load should give.", "Net worth | September | 41.2 million | within 0.1 percent"),
]
_COLS = {"kpis": ["name", "definition", "formula", "unit", "period", "owner"], "inputs": ["name", "kind", "holds", "owner"],
         "benchmarks": ["kpi", "period", "reported", "expected"]}
_LABELS = {"name": "Name", "kind": "Kind", "holds": "What it holds", "definition": "Plain meaning", "kpi": "Figure"}


def reporting_sections(hint=lambda key: {}, access: dict | None = None) -> list[dict]:
    out = []
    for key, head, req, typ, ins, ex in _REPORTING:
        more = dict(hint(key))
        if typ == "table":
            more.update(columns=_COLS[key], labels={c: _LABELS[c] for c in _COLS[key] if c in _LABELS})
        out.append(sec(key, head, ins, ex, req, typ, **more))
    if access:  # G1: who may see the work, asked second
        out.insert(1, sec("access", access["label"], access.get("help", ""), "Only the people you name", False, "choice",
                          **{k: access[k] for k in ("choices", "learn", "ask", "parse", "default") if access.get(k)}))
    return out


def quick_sections(hint=lambda key: {}, access: dict | None = None) -> list[dict]:
    out = [sec("goal", "What is needed and why", "One line: what you need and why it matters now.", "The September custody fee totals for the committee.", True, "long_text", **hint("goal")),
           sec("frequency", "By when", "The date you need it by, and whether it repeats.", "Friday the 17th, once.", True, "text", **hint("frequency")),
           sec("kpis", "The figures wanted", "Each figure, in your words.", "Custody fees by manager", True, "list", **hint("kpis")),
           sec("inputs", "Where the data is", "Where each figure can be found, and who has it.", "Finance invoices folder; Sam in Finance", True, "list", **hint("inputs")),
           sec("rules", "Who may see it", "Who may see the result and whether it is kept.", "Committee members only", True, "long_text", **hint("rules"))]
    if access:
        out.insert(1, sec("access", access["label"], access.get("help", ""), "Only the people you name", False, "choice",
                          **{k: access[k] for k in ("choices", "learn", "ask", "parse", "default") if access.get(k)}))
    return out


# ---- process maps and definitions --------------------------------------------------------------------------------------------------

_STEP_COLS = ["name", "who", "does", "inputs", "outputs", "system"]
_STEP_LABELS = {"name": "Step", "who": "Who", "does": "What they do", "inputs": "In", "outputs": "Out", "system": "System"}
_HAND = ["from_step", "to_step", "what"]
_HAND_LABELS = {"from_step": "From step", "to_step": "To step", "what": "What is passed"}
_KPI_COLS = ["name", "definition", "formula", "unit", "period", "owner", "source"]
_KPI_LABELS = {"name": "KPI", "definition": "Plain meaning", "formula": "Formula", "unit": "Unit", "period": "Period", "owner": "Owner", "source": "Source"}

SWIM = [sec("steps", "Lanes and steps", "One column per step, in order; a lane for each team. Manual steps are flagged.", "1 | Pull custodian file | Operations | Custodian portal",
            True, "table", columns=_STEP_COLS, labels=_STEP_LABELS, view="swimlane"),
        sec("handovers", "Hand-overs", "Who passes what to whom.", "Step 1 to step 2: positions file", False, "table", columns=_HAND, labels=_HAND_LABELS),
        sec("manual_steps", "Manual steps and time taken", "Every step done by hand and how long it takes.", "Reconcile cash in a spreadsheet, two hours", False, "list")]
STEPS = [sec("steps", "Steps", "Numbered, each with who does it, the system and the hand-over.", "1. Pull custodian file (Operations, Custodian portal), then hand to Finance",
             False, "table", columns=_STEP_COLS, labels=_STEP_LABELS, view="steps"),
         sec("manual_steps", "Manual steps and time taken", "Every step done by hand and how long it takes.", "Reconcile cash in a spreadsheet, two hours", False, "list")]
GLOSSARY = [sec("kpis", "KPI glossary", "One row per figure.", "Net worth | market value of all positions plus cash", True, "table",
                columns=_KPI_COLS, labels=_KPI_LABELS, view="table"),
            sec("terms", "Other terms", "Words the figures use that need a plain meaning.", "Position: what we hold in one security", False, "list"),
            sec("open_points", "Open points", "Definitions still to be settled.", "Net or gross of fees?", False, "list")]
CARDS = [sec("kpis", "KPI cards", "One card per figure with the same fields, plus what good looks like.", "Net worth: market value of all positions plus cash",
             True, "table", columns=_KPI_COLS, labels=_KPI_LABELS, view="cards"),
         sec("terms", "Other terms", "Words the figures use that need a plain meaning.", "Position: what we hold in one security", False, "list"),
         sec("open_points", "Open points", "Definitions still to be settled.", "Net or gross of fees?", False, "list")]


def _small(*rows) -> list[dict]:
    """(key, heading, required, type, instruction, example[, columns]) as sections."""
    return [sec(k, h, i, e, r, t, **({"columns": c[0]} if c else {})) for k, h, r, t, i, e, *c in rows]


BENCH = _small(("rows", "Benchmarks", True, "table", "Figure, period, reported, expected, tolerance, source.", "Net worth | September | 41.2 million | 41.2 million | 0.1%",
                ["kpi", "period", "reported", "expected", "tolerance", "source"]))
OTHERS = {  # kind: (first name, first description, first sections, second name, second description, second sections)
    "system_design": ("Layered system design", "The three layers and how the figures are built.", _small(
        ("layers", "The three layers", True, "long_text", "Landing, silver and gold in plain words.", "Landing keeps files as received; gold holds the figures people read."),
        ("tables", "Tables", True, "table", "Each table, its layer and what it feeds.", "gold_net_worth | gold | Net worth by month", ["table", "layer", "meaning", "feeds"]),
        ("checks", "Checks and tolerances", False, "list", "What is checked and how close is close enough.", "Totals agree with the custodian within 0.1 percent"),
        ("approver", "Approved by", True, "person", "Who approves the design.", "Head of data")),
        "One-page system design", "Layers and tables on one page.", _small(
            ("layers", "The three layers", True, "long_text", "Landing, silver and gold in plain words.", "Landing keeps files as received."),
            ("tables", "Tables", True, "table", "Each table and its layer.", "gold_net_worth | gold", ["table", "layer", "meaning"]))),
    "data_model": ("Full data model", "Tables, grain, keys and relationships.", _small(
        ("tables", "Tables", True, "table", "Each table, its layer, grain and keys.", "gold_net_worth | gold | one row per portfolio per month | portfolio, month",
         ["table", "layer", "grain", "keys", "meaning"]),
        ("relationships", "Relationships", False, "list", "How tables join.", "positions to securities on security id")),
        "One-page data model", "Tables and keys on one page.", _small(
            ("tables", "Tables", True, "table", "Each table with its grain.", "gold_net_worth | one row per portfolio per month", ["table", "grain", "keys"]))),
    "build_pack": ("Full build pack", "Loads, mappings, checks and the benchmark result.", _small(
        ("loads", "Loads", True, "table", "Each load, its table and schedule.", "Custodian positions | silver_positions | monthly", ["source", "table", "schedule", "status"]),
        ("mappings", "Mappings", False, "table", "How source fields map to targets.", "mv | market_value | as is", ["source_field", "target_field", "rule"]),
        ("benchmark_result", "Benchmark result", True, "table", "Each figure against its benchmark.", "Net worth | 41.2 million | 41.2 million | yes",
         ["kpi", "expected", "loaded", "within"])),
        "Short build pack", "Loads and the benchmark result.", _small(
            ("loads", "Loads", True, "table", "Each load and its schedule.", "Custodian positions | monthly", ["source", "table", "schedule"]),
            ("benchmark_result", "Benchmark result", True, "table", "Each figure against its benchmark.", "Net worth | yes", ["kpi", "expected", "loaded", "within"]))),
    "run_book": ("Full run book", "How the feed runs every period and what to do when it does not.", _small(
        ("schedule", "Schedule and service level", True, "text", "When it runs and by when it must be done.", "Monthly, done by the fifth working day"),
        ("owners", "Who looks after it", True, "list", "Named people.", "Leela Raman (engineer)"),
        ("alerts", "Alerts and what to do", True, "list", "Each alert and the first thing to do.", "File late: ask Operations to resend"),
        ("recovery", "Recovery steps", False, "long_text", "How to rerun after a failure.", "Rerun the load for the month, then the checks")),
        "One-page run book", "Schedule, owners and alerts.", _small(
            ("schedule", "Schedule and service level", True, "text", "When it runs.", "Monthly"),
            ("owners", "Who looks after it", True, "list", "Named people.", "Leela Raman"),
            ("alerts", "Alerts and what to do", True, "list", "Each alert and what to do.", "File late: ask Operations to resend"))),
    "consumption_brief": ("Full consumption brief", "What the readers see and how they use it.", _small(
        ("audience", "Readers", True, "list", "Who reads it.", "The family council"),
        ("views", "Views and figures shown", True, "list", "Each view and the figures on it.", "Monthly page: net worth, performance"),
        ("access", "Who may see what", True, "long_text", "Access in plain words.", "Council members see all portfolios"),
        ("refresh", "How often it refreshes", False, "text", "Refresh cadence.", "Monthly")),
        "One-page consumption brief", "Readers and views on one page.", _small(
            ("audience", "Readers", True, "list", "Who reads it.", "The family council"),
            ("views", "Views and figures shown", True, "list", "Each view and its figures.", "Monthly page: net worth"))),
}

# (id, kind, name, description, companions) for the three with companions; the rest are built from OTHERS
STANDARD_IDS = {"intent_of_work": "standard-intent-of-work", "process_map": "standard-process-map", "definitions": "standard-definitions"}
OLD_NAMES = {"standard-intent-of-work": "Standard intent of work", "standard-process-map": "Standard process map",
             "standard-definitions": "Standard business definitions"}


def seeds(hint=lambda key: {}, access: dict | None = None) -> list[dict]:
    """Every seed template: {id, kind, name, description, sections, companions?}. The first of each kind is the company's standard."""
    out = [
        {"id": "standard-intent-of-work", "kind": "intent_of_work", "name": "Reporting automation",
         "description": "A recurring report to automate: goal, readers, cadence, today's process, the report's sections, figures, sources, rules, benchmarks and success.",
         "sections": reporting_sections(hint, access), "companions": {"process_map": "standard-process-map", "definitions": "standard-definitions"}},
        {"id": "quick-data-request", "kind": "intent_of_work", "name": "Quick data request",
         "description": "One page: what is needed and why, by when, the figures wanted, where the data is and who may see it.",
         "sections": quick_sections(hint, access), "companions": {"process_map": "step-list", "definitions": "kpi-cards"}},
        {"id": "standard-process-map", "kind": "process_map", "name": "Swim lane", "description": "Lanes by team; manual steps are flagged.", "sections": SWIM},
        {"id": "step-list", "kind": "process_map", "name": "Step list", "description": "Numbered steps with who, system and hand-over.", "sections": STEPS},
        {"id": "standard-definitions", "kind": "definitions", "name": "KPI glossary", "description": "A table: KPI, plain meaning, formula, unit, period, owner, source.", "sections": GLOSSARY},
        {"id": "kpi-cards", "kind": "definitions", "name": "KPI cards", "description": "One card per KPI with the same fields and what good looks like.", "sections": CARDS},
        {"id": "standard-benchmarks", "kind": "benchmarks", "name": "Standard benchmark sheet",
         "description": "For each figure: what was reported, what it should read, within how much.", "sections": BENCH},
    ]
    for kind, (n1, d1, s1, n2, d2, s2) in OTHERS.items():
        out += [{"id": f"standard-{kind.replace('_', '-')}", "kind": kind, "name": n1, "description": d1, "sections": s1},
                {"id": f"short-{kind.replace('_', '-')}", "kind": kind, "name": n2, "description": d2, "sections": s2}]
    return out


SEEDS_BY_KIND: dict[str, list[dict]] = {}
for _s in seeds():
    SEEDS_BY_KIND.setdefault(_s["kind"], []).append(_s)
