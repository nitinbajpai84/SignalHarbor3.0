"""E0b2 data agent tools: read a spreadsheet's shape, propose a mapping onto the data model, find similar approved mappings, propose a model change.

- `profile_sheet(path, sheet=None)` -> {file_name, sheet, header_row, first_data_row, last_data_row, columns, column_info, units, totals, exclude_rows,
  status, purpose, row_count, merged_bands}. Rows are 1-based. Reads the file on this machine only; the profile holds figures (control totals), so it
  stays local: only column names and digit-free samples ever go into a model prompt.
- `propose_mapping(plane, profile, viewer=None, model=None)` -> {columns: {source: "table.field" | "ignore" | {target, transform}}, status, totals_match,
  rejected, source, note, mapping}. Rules first (names and synonyms), then the model for what is left; every target is checked with
  `e0a_catalogue.has_field`, an invented one is dropped to "ignore" and named in `rejected`. `mapping` is the record `e0b_mappings.save_proposal` takes.
- `similar_approved_mappings(plane, profile, k=3)`, `propose_model_change(plane, viewer, reason, dbml)`; `registry(...)` registers the tools for the agent.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

from sh_platform.v1.e0b_mappings import col_key

log = logging.getLogger(__name__)
MONEY = {"source_market_value", "value_amount", "amount", "debit", "credit", "nav_amount", "commitment_amount"}
DATE_FIELDS = {"position_date", "valuation_date", "effective_date", "nav_period_end", "observed_at", "weight_effective_from", "committed_on"}
IGNORE = "ignore"
DEBIT_CREDIT = {"cash_movements.debit", "cash_movements.credit"}
_UNIT_WORDS = {"usd", "eur", "gbp", "sgd", "000", "thousand", "thousands", "k"}
_STATUS_WORDS = ("in progress", "draft", "not for use")


def _d(*pairs: tuple[str, str]) -> dict:
    return {k: v for keys, v in pairs for k in keys.split("|")}


# domain -> (purpose label, {normalised header -> "table.field" | "ignore"}); the first line of each map is the distinctive headers
DOMAINS: dict[str, dict] = {
    "positions": _d(("position date|as at|as at date|as of date|as of|holding date|valuation date|value date", "position_snapshots.position_date"),
                    ("fund name|fund|security|security name|instrument|holding", "instruments.canonical_name"),
                    ("fund id|fund code|isin|identifier|security id|instrument id|code", "instrument_identifiers.identifier_value"),
                    ("portfolio|account|portfolio code|entity", "portfolios.portfolio_code"),
                    ("units|quantity|shares|holding units", "position_snapshots.quantity"),
                    ("market value|mkt value|mv|value|valuation amount|book value|closing cash|administrator closing cash|closing balance|cash balance", "position_snapshots.source_market_value"),
                    ("currency|ccy", "position_snapshots.currency"),
                    ("entity code|legal entity", "legal_entities.entity_code")),
    "valuations": _d(("valuation date|value date|nav date", "valuation_observations.valuation_date"),
                     ("fund|fund name|instrument|security", "instruments.canonical_name"),
                     ("estimated value|valuation|value|nav|estimate|reported value", "valuation_observations.value_amount"),
                     ("ccy|currency", "valuation_observations.currency"),
                     ("type|valuation type|source type|basis", "valuation_observations.valuation_type")),
    "cash": _d(("date|value date|transaction date|movement date|as of date", "cash_movements.effective_date"),
               ("fund|fund name|instrument", "instruments.canonical_name"),
               ("portfolio|account|entity", "portfolios.portfolio_code"),
               ("type|movement type|transaction type", "cash_movements.movement_type"),
               ("amount|cash amount|net movement|movement", "cash_movements.amount"),
               ("debit|debits|withdrawal|withdrawals|money out", "cash_movements.debit"),
               ("credit|credits|deposit|deposits|money in", "cash_movements.credit"),
               ("currency|ccy", "cash_movements.currency"),
               ("portfolio code", "portfolios.portfolio_code"),
               ("entity code|legal entity", "legal_entities.entity_code")),
    # uncalled is worked out; called to date is kept on the commitment by e0c_load (UC6 G), so neither is mapped as a column here (deliberate ignore)
    "commitments": _d(("fund name|fund|instrument", "instruments.canonical_name"),
                      ("administrator code|fund code", "instrument_identifiers.identifier_value"),
                      ("legal entity|entity|entity code", "legal_entities.entity_code"),
                      ("commitment|commitment amount|committed", "commitments.commitment_amount"),
                      ("committed on|commitment date", "commitments.committed_on"),
                      ("currency|ccy", "commitments.currency"),
                      ("called to date|uncalled|notices outstanding", IGNORE)),
    "capital_calls": _d(("notice date|call date|date of notice", "cash_movements.effective_date"),
                        ("fund|fund name|instrument", "instruments.canonical_name"),
                        ("call amount|amount called|capital call", "cash_movements.amount"),
                        ("ccy|currency", "cash_movements.currency"),
                        ("due|due date|payment due|pay by", IGNORE)),
    "nav": _d(("period end|nav date|period|as at", "nav_snapshots.nav_period_end"),
              ("portfolio|account|entity|portfolio code", "portfolios.portfolio_code"),
              ("nav|net asset value|nav amount", "nav_snapshots.nav_amount"),
              ("currency|ccy", "nav_snapshots.currency"),
              ("status|nav status", "nav_snapshots.nav_status")),
    "market_data": _d(("obs date|observation date|date|observed at", "market_observations.observed_at"),
                      ("series|series key|index|ticker", "market_observations.series_key"),
                      ("level|value|price|close", "market_observations.value"),
                      ("kind|observation type|type", "market_observations.observation_type"),
                      ("base ccy|base currency|currency|ccy", "market_observations.base_currency"),
                      # an FX fixing file (Date, Pair, Rate): the model keeps FX as market observations of type fx (e0c_load sets it from the pair)
                      ("pair|currency pair|fx pair", "market_observations.series_key"),
                      ("rate|fx rate|exchange rate|fixing rate|spot rate|mid rate", "market_observations.value"),
                      ("fixing|fixing time|source|rate source", IGNORE)),
    "benchmark": _d(("index|series|component|benchmark", "benchmark_components.market_series_key"),
                    ("weight|weight pct|target weight", "benchmark_components.component_weight"),
                    ("spread|spread bps", "benchmark_components.spread_bps"),
                    ("effective from|effective date|from", "benchmark_components.weight_effective_from"),
                    ("effective to|to", "benchmark_components.weight_effective_to")),
}
SHEET_HINTS = {"positions": "position", "valuations": "valuation", "cash": "cash", "capital_calls": "call", "nav": "nav", "commitments": "commitment",
               "market_data": "level", "benchmark": "benchmark"}


def norm_header(name) -> str:
    """Header text without units: 'Market Value (USD 000)' -> 'market value'; 'Weight %' -> 'weight'; 'Spread (bps)' -> 'spread'."""
    text = re.sub(r"\([^)]*\)", " ", str(name).lower()).replace("%", " pct ")
    words = [w for w in col_key(text).split() if w not in _UNIT_WORDS and w != "bps"]
    return " ".join(words).replace(" pct", "").strip()


# ---- profile -----------------------------------------------------------------------------------------------------------------------

def _plane(plane):
    if not isinstance(plane, str):
        return plane
    from sh_platform.plane import PlaneStore
    return PlaneStore(os.environ.get("SH_DATA_ROOT") or "./data").plane_for(plane).ensure()  # the eval runner passes a company slug


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def _date_format(values: list) -> str | None:
    """'%d/%m/%Y' or '%m/%d/%Y' for text dates (the first part above 12 decides; none above 12 -> day first, noted by the caller); None for real dates."""
    first = second = 0
    seen = False
    if values and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", _text(v)) for v in values if _text(v)) and any(_text(v) for v in values):
        return "%Y-%m-%d"  # ISO: year first, so the day and month cannot be swapped
    for v in values:
        m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", _text(v))
        if m:
            seen = True
            first += int(m[1]) > 12
            second += int(m[2]) > 12
    if not seen:
        return None
    return "%m/%d/%Y" if second > first else "%d/%m/%Y"


def _kind(values: list) -> str:
    vals = [v for v in values if v not in (None, "")]
    if vals and all(isinstance(v, (datetime, date)) for v in vals):
        return "date"
    if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "number"
    if vals and all(re.fullmatch(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}", _text(v)) for v in vals):
        return "text_date"
    return "text"


def _pick_sheet(wb, sheet):
    if sheet:
        if sheet not in wb.sheetnames:
            raise ValueError(f"There is no sheet called {sheet}.")
        return wb[sheet]
    visible = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    return (visible or wb.worksheets)[0]


def _coerce(c: str):
    """A CSV cell is text; plain numbers become numbers (an id with a leading zero stays text), everything else stays text."""
    t = c.strip()
    if re.fullmatch(r"-?\d+", t) and not (len(t.lstrip("-")) > 1 and t.lstrip("-").startswith("0")):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    return t if t else None


def read_grid(path, sheet: str | None = None) -> tuple[str, list[list]]:
    """(sheet title, rows as lists of values) for an Excel sheet or a CSV file (one sheet, named after the file). Local only."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        import csv
        import io
        text = path.read_bytes().decode("utf-8-sig", errors="replace")
        return re.sub(r"^[0-9a-f]{64}__", "", path.stem), [[_coerce(c) for c in r] for r in csv.reader(io.StringIO(text))]
    from openpyxl import load_workbook
    ws = _pick_sheet(load_workbook(path, data_only=True), sheet)
    return ws.title, [list(r) for r in ws.iter_rows(values_only=True)]


def profile_sheet(path, sheet: str | None = None) -> dict:
    """The shape of one sheet: header row (merged bands skipped), data range, columns, units, date formats, a totals row, a purpose guess."""
    path = Path(path)
    title, rows = read_grid(path, sheet)
    strings = [sum(isinstance(c, str) and c.strip() != "" for c in r) for r in rows[:20]]
    hdr = max(range(len(strings)), key=lambda i: (strings[i], -i)) if strings else 0  # most text cells; a merged band has few
    head = rows[hdr] if rows else []
    idx = [i for i, c in enumerate(head) if _text(c)]
    names = [_text(head[i]) for i in idx]
    blank = next((i for i in range(hdr + 1, len(rows)) if not any(c not in (None, "") for c in rows[i])), len(rows))
    last_row = blank - 1  # the table ends at the first blank row; notes below it are not data
    totals = next((i for i in range(hdr + 1, last_row + 1) if _text(rows[i][idx[0]]).lower().startswith("total")), None) if idx else None
    end = (totals if totals is not None else last_row + 1)
    body = [r for r in rows[hdr + 1:end] if any(c not in (None, "") for c in r)]
    info = []
    for n, i in zip(names, idx):
        vals = [r[i] if i < len(r) else None for r in body]
        k = _kind(vals)
        info.append({"name": n, "index": i, "kind": k, "date_format": _date_format(vals) if k == "text_date" else None})
    text = " ".join([title] + [_text(c) for r in rows[:hdr] for c in r if isinstance(c, str)]).lower()
    units = "thousands" if re.search(r"thousand|\b000\b", text + " " + " ".join(names).lower()) else None
    status = "in_progress" if any(w in text for w in _STATUS_WORDS) else "final"
    stated = sums = None
    match = None
    if totals is not None:
        stated, sums = {}, {}
        for n, i in zip(names, idx):
            v = rows[totals][i] if i < len(rows[totals]) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                stated[n] = v
                sums[n] = sum(r[i] for r in body if i < len(r) and isinstance(r[i], (int, float)))
        match = all(abs(stated[n] - sums[n]) < 0.5 for n in stated) if stated else None
    bands = [_text(c) for c in rows[hdr - 1] if _text(c)] if hdr and sum(isinstance(c, str) for c in rows[hdr - 1]) < len(idx) else []  # a merged band just above
    prof = {"file_name": path.name, "sheet": title, "header_row": hdr + 1, "first_data_row": hdr + 2,
            "last_data_row": 0, "columns": names, "column_info": info, "units": units,
            "totals": None if totals is None else {"row": totals + 1, "stated": stated, "sums": sums, "matches": match},
            "totals_match": match, "exclude_rows": [] if totals is None else [totals + 1], "status": status, "row_count": len(body),
            "merged_bands": bands}
    prof["last_data_row"] = max((i + 1 for i in range(hdr + 1, end) if any(c not in (None, "") for c in rows[i])), default=hdr + 1)
    prof["purpose"] = guess_purpose(prof, title)
    return prof


def guess_purpose(profile: dict, sheet_name: str = "") -> str:
    heads = {norm_header(c) for c in profile["columns"]}
    sheet_name = (sheet_name or profile.get("sheet") or "").lower()
    score = {d: sum(h in {norm_header(k) for k in m} for h in heads) + (1 if SHEET_HINTS[d] in sheet_name else 0) for d, m in DOMAINS.items()}
    return max(score, key=lambda d: (score[d], d == "positions"))


# ---- mapping -----------------------------------------------------------------------------------------------------------------------

def _transform(profile: dict, info: dict, target: str) -> dict | None:
    field, name = target.split(".", 1)[1], info["name"]
    tr = {}
    if field in MONEY and profile.get("units") == "thousands":
        tr["multiply"] = 1000
    if field == "component_weight" and "%" in name:
        tr["multiply"] = 0.01
    if field in DATE_FIELDS and info.get("date_format"):
        tr["date_format"] = info["date_format"]
    return tr or None


def _rules(profile: dict) -> dict:
    synonyms = {norm_header(k): v for k, v in DOMAINS[profile.get("purpose") or guess_purpose(profile)].items()}
    return {i["name"]: synonyms.get(norm_header(i["name"])) for i in profile["column_info"]}


def _split(target: str) -> tuple[str, str]:
    t, _, f = str(target).partition(".")
    return t, f


def _valid(plane, target) -> bool:
    from sh_platform.v1 import e0a_catalogue
    t, f = _split(target)
    if target in DEBIT_CREDIT:  # read columns the loader folds into the one signed amount (e0c_load); the model has no such fields
        return True
    return bool(t and f and e0a_catalogue.has_field(plane, t, f))


def _model_targets(plane, model, profile: dict, left: list[str], examples: list[dict]) -> dict:
    """Ask the model where the left-over columns belong. Column names and digit-free shapes only; a failed call returns {}."""
    from sh_platform.agents.loop import run_agent
    from sh_platform.agents.registry import ToolRegistry
    from sh_platform.agents.runs import RunRegistry
    from sh_platform.build.agents.runtime import OpenGate
    from sh_platform.v1 import e0a_catalogue
    from sh_platform.v1.egress_fit import fit
    from sh_platform.v1.router import route
    table = {"commitments": "commitments", "positions": "position_snapshots", "valuations": "valuation_observations", "cash": "cash_movements", "capital_calls": "cash_movements",
             "nav": "nav_snapshots", "market_data": "market_observations", "benchmark": "benchmark_components"}.get(profile.get("purpose"), "")
    fields = {n: cols for n in (table, "instruments", "instrument_identifiers", "portfolios")
              if n and (cols := e0a_catalogue.columns_of(plane, n))}  # tables() lists names only; columns_of has the fields
    shape = {i["name"]: i["kind"] for i in profile["column_info"] if i["name"] in left}
    ctx = fit({"sheet_purpose": profile.get("purpose"), "model_fields": fields, "columns_to_place": shape,
               "similar_approved": [{"columns": m.get("layout"), "targets": [f"{c['target_table']}.{c['target_field']}" for c in m["columns"]]}
                                    for m in examples][:3]})
    system = ("You are the data agent. Place each spreadsheet column on one field of the data model, or null if it fits none. Use ONLY field names "
              "listed in model_fields as 'table.field'; never invent one. Never write a digit. Reply with ONLY one JSON object {column: 'table.field' or null}.")
    try:
        res = run_agent(route(model, "data", "mapping", "", plane, want_json=True), ToolRegistry(OpenGate()), plane.company_id, "m3_connect", "Data",
                        system, ctx, "Place the columns.", recorder=RunRegistry(plane))
    except Exception:  # noqa: BLE001 - a failed call leaves the columns to a person
        log.warning("the mapping model call failed; rules only")
        return {}
    a, b = res.text.find("{"), res.text.rfind("}")
    try:
        got = json.loads(res.text[a:b + 1]) if res.status == "done" and 0 <= a < b else {}
    except ValueError:
        return {}
    return got if isinstance(got, dict) else {}


def propose_mapping(plane, profile: dict, viewer=None, model=None) -> dict:
    plane = _plane(plane)
    purpose = profile.get("purpose") or guess_purpose(profile)
    profile = {**profile, "purpose": purpose}
    info = {i["name"]: i for i in profile.get("column_info") or [{"name": c, "kind": "text", "date_format": None} for c in profile["columns"]]}
    profile.setdefault("column_info", list(info.values()))
    got, rejected = _rules(profile), []
    left = [c for c, t in got.items() if t is None]
    source = "rules"
    if left and model is not None and os.environ.get("SH_MODEL_PROVIDER", "").lower() != "off":
        asked = _model_targets(plane, model, profile, left, similar_approved_mappings(plane, profile))
        for c in left:
            t = asked.get(c)
            taken = {x for x in got.values() if x and x != IGNORE}
            if t and (_split(t)[1] == "id" or _split(t)[1].endswith("_id") or t in taken):  # keys are the loader's; a field already filled
                rejected.append({"column": c, "target": t})                                  # by a named column is not filled twice (UC5)
                continue
            if t:
                got[c], source = t, "rules and model"
    cols, records = {}, []
    for c, t in got.items():
        if t and t != IGNORE and not _valid(plane, t):
            rejected.append({"column": c, "target": t})  # invented or not in the current model: named, never used
            t = IGNORE
        t = t or IGNORE
        tr = _transform(profile, info[c], t) if t != IGNORE else None
        cols[c] = {"target": t, "transform": tr} if tr else t
        tt, tf = _split(t) if t != IGNORE else ("", "")
        records.append({"source": c, "target_table": tt, "target_field": tf, "transform": tr})
    note = ("Mapped by rules only (no model was used)." if source == "rules" else "Mapped by rules, then the model for the rest.")
    if rejected:
        note += " Not in the data model, left unmapped: " + ", ".join(f"{r['column']} ({r['target']})" for r in rejected) + "."
    if profile.get("status") == "in_progress":
        note += " The sheet says it is in progress, so nothing should load from it yet."
    if profile.get("totals_match") is False:
        note += " The totals row in the sheet does not add up to its rows."
    return {"columns": cols, "status": profile.get("status", "final"), "totals_match": profile.get("totals_match"), "rejected": rejected, "source": source,
            "note": note, "mapping": {"file_name": profile.get("file_name", ""), "sheet": profile["sheet"], "header_row": profile.get("header_row"),
                                      "purpose": purpose, "columns": records, "proposed_by": {"kind": "agent", "name": "Data agent", "account_id": None}}}


def similar_approved_mappings(plane, profile: dict, k: int = 3) -> list:
    """The closest approved mappings: shared column names (Jaccard) plus a bonus for the same sheet purpose."""
    from sh_platform.v1 import e0b_mappings
    mine = {norm_header(c) for c in profile["columns"]}
    scored = []
    for m in e0b_mappings.listing(_plane(plane), "approved"):
        theirs = {norm_header(c) for c in m["layout"]}
        j = len(mine & theirs) / max(1, len(mine | theirs))
        if j >= 0.5 or m.get("purpose") == profile.get("purpose"):  # a few shared words such as currency do not make two sheets alike
            scored.append((j + (0.25 if m.get("purpose") == profile.get("purpose") else 0), m))
    return [{**m, "score": round(s, 3)} for s, m in sorted(scored, key=lambda x: (-x[0], x[1]["id"]))[:k] if s > 0]


def propose_model_change(plane, viewer, reason: str, dbml: str) -> str:
    """Open an E0a change proposal for the head of data to decide. Returns the proposal number as text."""
    from sh_platform.v1 import e0a_catalogue
    return str(e0a_catalogue.propose(_plane(plane), viewer, dbml=dbml, note=reason)["version"])


# ---- the tools the data agent is given ------------------------------------------------------------------------------------------

def registry(gate, module_id: str, plane, viewer, model=None):
    """Tool registry for the data agent. Results are strings and name lists (no figures, no rows); proposals are collected, never written here."""
    from sh_platform.agents.registry import ToolRefused, ToolRegistry
    from sh_platform.v1 import e0a_catalogue
    reg = ToolRegistry(gate)

    def _file(name) -> Path:
        n = Path(str(name)).name  # a bare file name from the landing folders only, never a path
        for part in (("landing", "inbox"), ("landing", "originals")):
            hit = next(iter(sorted(plane.path(*part).glob(f"*{n}"))), None) if plane.path(*part).is_dir() else None
            if hit and hit.name.endswith(n):
                return hit
        raise ToolRefused("That file is not in the landing folder.")

    def list_tables() -> dict:
        return {"tables": [t["name"] for t in e0a_catalogue.tables(plane)]}

    def describe_table(table) -> dict:
        d = e0a_catalogue.describe(plane, str(table))
        if d is None:
            raise ToolRefused("There is no such table. Call list_tables.")
        return {"table": d["name"], "columns": [f"{c['name']} ({c['type']})" for c in d["columns"]]}

    def profile_tool(file, sheet) -> dict:
        p = profile_sheet(_file(file), str(sheet) or None)
        return {"sheet": p["sheet"], "header_row": f"row {p['header_row']}", "columns": p["columns"], "units": p["units"] or "none stated",
                "status": p["status"], "purpose": p["purpose"], "totals": "a totals row" if p["totals"] else "no totals row"}

    def similar_tool(file, sheet) -> dict:
        p = profile_sheet(_file(file), str(sheet) or None)
        return {"similar": [f"{m['file_pattern']} / {m['sheet']} v{m['version']}" for m in similar_approved_mappings(plane, p)]}

    def propose_tool(file, sheet) -> dict:
        r = propose_mapping(plane, profile_sheet(_file(file), str(sheet) or None), viewer, model)
        return {"file": str(file), "sheet": r["mapping"]["sheet"], "mapping": r["mapping"]["columns"], "note": r["note"]}

    def change_tool(reason, dbml) -> dict:
        if not str(reason).strip() or not str(dbml).strip():
            raise ToolRefused("Give a reason and the DBML script.")
        return {"reason": str(reason)[:500], "dbml": str(dbml)[:20000]}

    ro = dict(read_only=True)
    reg.register(module_id, "list_tables", lambda: list_tables(), parameters={}, description="List the tables of the data model.", **ro)
    reg.register(module_id, "describe_table", describe_table, parameters={"table": "string"},
                 description="Columns of one table. Always call this before naming a field; never invent a table or column.", **ro)
    reg.register(module_id, "profile_sheet", profile_tool, parameters={"file": "string", "sheet": "string"},
                 description="Shape of a landed spreadsheet: header row, columns, units, status. Pass sheet as an empty string for the first sheet.", **ro)
    reg.register(module_id, "similar_approved_mappings", similar_tool, parameters={"file": "string", "sheet": "string"},
                 description="Approved mappings closest to this sheet, to use as examples.", **ro)
    reg.register(module_id, "propose_mapping", propose_tool, parameters={"file": "string", "sheet": "string"}, read_only=False, proposes=True,
                 description="Propose a column-by-column mapping for a landed sheet. A person approves it before anything loads.")
    reg.register(module_id, "propose_model_change", change_tool, parameters={"reason": "string", "dbml": "string"}, read_only=False, proposes=True,
                 description="Propose a change to the data model (DBML). The head of data decides.")
    return reg
