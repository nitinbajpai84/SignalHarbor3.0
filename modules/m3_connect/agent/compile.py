"""Lens compiles a signed measure definition into a rule (M3-P03). Client set-up copied from module 2's Lens (not imported).

What the model is shown: the measure's name, the definition text (the technical definition first when module 2 signed one), and the
column names and types of the matched sources, as one plain-text context. Never a row, a figure from the data, a source name or a file.
Names go through the egress vault (tokenised) and the gateway; the reply is JSON and is checked against the columns that exist: an invalid
rule is retried once with what was wrong, then it is "could not compile" with the reason. A pack hint (kpi_tree `rule`) is the fallback.
"""
import json
import logging
import re

from modules.m3_connect.domain import engine as E
from modules.m3_connect.domain import rules as R
from sh_platform.agents.loop import run_agent
from sh_platform.agents.registry import ToolRegistry
from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.names import protected_names
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.egress.vault import NameVault, VaultUnavailable
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
AGENT_NAME, MODULE_ID = "Lens", "m3_connect"
SYSTEM = """You are Lens, a business analyst. You turn the definition of a business measure into a rule a program can run over a table.
Reply with ONE JSON object and nothing else. Use only the column names you are given, spelled exactly.
A rule is {"op", "column", "filters", "period", "group_by", "pick", "having", "numerator", "denominator", "left", "right"}:
- op is one of sum, avg, count, min, max, latest, first (a column over rows), ratio (numerator and denominator are rules), difference (left minus right, both rules).
- column is one column, or "a - b + c" to add and subtract columns row by row. A count may leave it out.
- filters is a list of {"column", "op", "value"}; op is eq, ne, in (value is a list), between (value is [low, high]), not_null, or not_in_column
  (the row's value is not among the values another column holds; value is that column's name).
- period is {"column", "from", "to"} on a date column; leave it out unless the definition names a period.
- group_by is a column or a list of columns; with op sum/avg/min/max, pick says whether the largest ("max") or smallest ("min") group is wanted;
  with op count it counts the different groups, and having {"column", "older_than_business_days"} keeps groups whose newest date is that old.
- latest and first need a date column in period or order_by.
Do not write a scale, a figure, a source or a comment. If the definition cannot be written as a rule with these columns, reply {"error": "why, in plain words, without figures"}."""
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def figures(text: str) -> list[dict]:
    """The figures in the definition text shown, as facts for the number guard: they are the definition's, never the company's data."""
    return [{"id": "shown", "label": "figure in the text shown", "value": v, "group_size": 5} for v in sorted({m.group().rstrip(",") for m in _NUM.finditer(text or "")})]


def get_model(state, plane):
    """The model client for this company, or None (no key set up, or a setting is wrong). Tests plug a stub in as `lens_model_factory`."""
    factory = getattr(state, "lens_model_factory", None)
    override = getattr(state, "model_env", None)  # tests set {}: the real .env holds keys and a test must never reach a live model
    try:
        return factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env())
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def register_names(plane, company: str, people: list[str]) -> None:
    vault = NameVault(plane)
    for kind, name in protected_names(company, list(people)):
        try:
            if name:
                vault.register(kind, name)
        except (ValueError, VaultUnavailable):
            log.warning("a name could not be registered with the egress vault")  # the gateway then refuses to send


def _parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group()) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def ask(model, gate, company_id: str, plane, name: str, text: str, columns: dict[str, str], note: str = "") -> tuple[dict | None, str]:
    """(the model's rule or None, why not). One call."""
    context = {"measure": name, "definition": text, "columns": columns, "facts": figures(text)}
    res = run_agent(model, ToolRegistry(gate), company_id, MODULE_ID, AGENT_NAME, SYSTEM, context,
                    "Write the rule." + (f" Your last rule was not usable: {note}. Try again." if note else ""), recorder=RunRegistry(plane))
    if res.status in ("refused", "error"):
        return None, "Lens could not reach the model just now"
    d = _parse(res.text) if res.status == "done" and not res.numbers_replaced else None
    if d is None:
        return None, "the model's answer was not a rule"
    if "error" in d and "op" not in d:
        return None, str(d["error"])[:200]
    return d, ""


def compile_rule(model, gate, company_id: str, plane, *, name: str, text: str, columns: dict[str, dict], feeders: list[str] = (),
                 hint: dict | None = None, synonyms: dict | None = None) -> dict:
    """The rule record for one measure: {state, origin, rule, words, reason, reason_kind}. Order: the model (from `text`, which is the technical
    definition when there is one), retried once if invalid; then the pack's hint; else could not compile with the reason."""
    flat = {c: t for cols in columns.values() for c, t in cols.items()}
    why, problems = ("Lens had no model to write it with, and the pack has no rule for it" if text.strip() else "no definition was given"), []
    if model is not None and text.strip():
        note = ""
        for _ in range(2):
            d, why = ask(model, gate, company_id, plane, name, text, flat, note)
            if d is not None:
                rule, problems = R.resolve(d, columns, feeders, synonyms)
                if not problems:
                    return _record(rule, "technical" if text.startswith("Technical:") else "definition")
                why = "; ".join(problems)
            note = why
            if why.startswith("Lens could not reach"):
                break
    if hint:
        rule, problems = R.resolve(hint, columns, feeders, synonyms)
        if not problems:
            return _record(rule, "pack hint")
        why = "; ".join(problems)
    kind = "no_data" if problems and all("is not in the data" in p for p in problems) else "invalid"
    return {"state": R.COULD_NOT, "origin": None, "rule": None, "words": None, "reason": why, "reason_kind": kind}


def _record(rule: dict, origin: str) -> dict:
    return {"state": "draft", "origin": origin, "rule": rule, "words": R.words(rule), "reason": None, "reason_kind": None}


def compile_all(model, gate, company_id: str, plane, adir, measures: list[dict], columns: dict, feeders_of, pack_kpis: list, technical_of, synonyms: dict | None = None) -> dict:
    """Compiles every visible measure and merges into rules.json. A checked rule (a person's) is never replaced; one Lens checked itself is."""
    rules = R.read_rules(adir)
    for m in measures:
        if m.get("restricted") or (rules.get(m["id"], {}).get("state") == "checked" and not rules[m["id"]].get("auto_checked")):
            continue
        tech, _ = technical_of(m)
        text = ("Technical: " + tech + " ") * bool(tech) + str(m.get("definition") or "")
        rec = compile_rule(model, gate, company_id, plane, name=str(m.get("name") or ""), text=text.strip(), columns=columns,
                           feeders=feeders_of(m["id"]), hint=R.hint_for(pack_kpis, m["id"]), synonyms=synonyms)
        if rules.get(m["id"], {}).get("auto_checked") and rules[m["id"]].get("rule") == rec.get("rule"):
            continue  # the same rule again: Lens's own check on it still stands (the next trial run takes it back if it stops matching)
        rules[m["id"]] = {"measure": m["id"], "compiled_at": R.now(), "checked_by": None, "checked_at": None, **rec}
    R.write_file(adir, "rules.json", rules)
    return rules
