"""The shapes of docs/plan/SHAPES.md as small schema dicts, and one checker.

Spec grammar: "str" "int" "num" "bool" "date" "iso" "any"; ("?", spec) = null or spec; ("in", [values]);
[spec] = list of spec; {key: spec} = object with at least those keys (extra keys are allowed).
"""
import re

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def check(spec, v, path="$") -> list[str]:
    """Return one 'path: expected X, got Y' line per mismatch."""
    def bad(exp):
        return [f"{path}: expected {exp}, got {type(v).__name__} {str(v)[:40]!r}"]
    if isinstance(spec, tuple) and spec[0] == "?":
        return [] if v is None else check(spec[1], v, path)
    if isinstance(spec, tuple) and spec[0] == "in":
        return [] if v in spec[1] else bad("one of " + "|".join(map(str, spec[1])))
    if isinstance(spec, dict):
        if not isinstance(v, dict):
            return bad("object")
        return [e for k, s in spec.items() for e in (check(s, v[k], f"{path}.{k}") if k in v else [f"{path}.{k}: missing"])]
    if isinstance(spec, list):
        if not isinstance(v, list):
            return bad("list")
        return [e for i, x in enumerate(v) for e in check(spec[0], x, f"{path}[{i}]")]
    ok = {"str": isinstance(v, str), "bool": isinstance(v, bool), "any": True,
          "int": isinstance(v, int) and not isinstance(v, bool),
          "num": isinstance(v, (int, float)) and not isinstance(v, bool),
          "date": isinstance(v, str) and bool(_DATE.match(v)),
          "iso": isinstance(v, str) and bool(_ISO.match(v))}[spec]
    return [] if ok else bad(spec)


def figures(v, allow=(), path="$") -> list[str]:
    """Paths of every number in v (names-and-links-only shapes must return none); keys in allow are skipped."""
    if isinstance(v, bool):
        return []
    if isinstance(v, (int, float)):
        return [path]
    if isinstance(v, dict):
        return [p for k, x in v.items() if k not in allow for p in figures(x, allow, f"{path}.{k}")]
    if isinstance(v, list):
        return [p for i, x in enumerate(v) for p in figures(x, allow, f"{path}[{i}]")]
    return []


NAME = ("?", "str")
LINE = {"id": "str", "kind": ("in", ["invite", "decision", "request", "measure", "brief", "ops", "signature"]),
        "title": "str", "detail": "str", "href": "str", "action": "str", "due": ("?", "date"),
        "source": {"record": "str", "at": "iso"}}
PULSE = {"date": "date", "person": {"name": "str", "roles": ["str"]}, "minutes": "int",
         "strips": [{"key": ("in", ["invited", "decide", "give", "watch"]), "lines": [LINE]}],
         "map": {"new_this_week": ["str"], "owned_changes": "int"}}
MARK = {"mark": ("in", ["guessed", "stated"]), "from": "str"}
BLUEPRINT = {"version": "int", "state": ("in", ["draft", "signed"]),
             "signed_by": [{"name": "str", "role": "str", "at": "iso"}], "band": ("in", ["now", "next", "later"]),
             "model": {"facts": [{"name": "str", "grain": "str", "keys": ["str"], "measures": ["str"]}],
                       "dimensions": [{"name": "str", "keys": ["str"], "attributes": ["str"], "scd": ("in", [1, 2])}]},
             "lineage": [{"measure": "str", "source": "str", "fields": ["str"], "transform": "str", "mart": "str"}],
             "rules": [{"measure": "str", "rule": "str", "severity": ("in", ["block", "warn", "inform"]),
                        "from": ("in", ["scan", "trial"])}],
             "access": [{"mart": "str", "may_see": ("?", ["str"])}],
             "schedule": [{"source": "str", "expected": "str", "sla": "str", "depends_on": ["str"]}],
             "infra": {"warehouse": "str", "runner": "str"}, "provenance": "any"}
PIPELINE = {"source": "str", "title": "str", "lands_at": "str", "pattern": "str", "expected": "str", "sla": "str",
            "schema": [{"field": "str", "type": "str"}], "rules": ["str"], "depends_on": ["str"],
            "owner": "str", "marts": ["str"]}
RUN = {"id": "str", "source": "str", "started": "iso", "ended": "iso", "on_time": "bool", "rows": "int",
       "schema_ok": "bool", "rules": [{"rule": "str", "passed": "bool", "count": "int"}],
       "marts_ready": ("?", "iso"), "sla_met": ("?", "bool"), "owner": "str",
       "status": ("in", ["ok", "late", "failed"])}
RUNS = {"runs": [RUN]}
PROVE = {"band": "str",
         "measures": [{"code": "str",
                       "periods": [{"period": "str", "ours": ("?", "num"), "reported": ("?", "num"),
                                    "result": ("in", ["match", "gap", "not_yet"]), "reason": NAME, "accepted_by": NAME}],
                       "uat": {"state": ("in", ["pending", "signed", "sent_back"]), "by": NAME, "at": ("?", "iso"), "note": NAME},
                       "release_ready": "bool"}],
         "release": {"state": ("in", ["draft", "signed"]), "by": NAME, "at": ("?", "iso")}}
FEEDS = {"measures": [{"code": "str", "name": "str", "owner": "str",
                       "latest": ("?", {"period": "str", "value": "num"}), "trend": [{"period": "str", "value": "num"}],
                       "range_break": "bool", "may_see": "bool"}]}
MARKET = {"briefs": [{"id": "str", "title": "str", "summary": "str", "measures": ["str"], "source": "str",
                      "outside": ("in", [True])}]}
WHATIF = {"driver": "str", "moved": [{"code": "str", "path": ["str"], "change_pct": "num"}], "basis": "str"}
MEMORY = {"entries": [{"id": "str", "kind": ("in", ["fact", "preference", "decision", "open"]), "text": "str",
                       "from": [{"conversation": "str", "at": "iso"}], "updated_at": "iso",
                       "by": ("in", ["agent", "person"])}], "budget": "int"}
NODE = {"id": "str", "type": "str", "label": "str", "owner": "str", "steward": "str",
        "trail": [{"step": ("in", ["asked", "defined", "supplied", "built", "released"]), "label": "str", "ref": "str",
                   "by": "str", "at": "iso"}],
        "definition": "any", "versions": [{"v": "int", "what": "str", "by": "str", "at": "iso", "ref": "str"}],
        "commits": [{"id": "str", "when": "str", "what": "str", "by": "str"}], "may_see_figure": "bool"}
VERSION = {"v": "int", "what": "str", "by": "str", "at": "iso", "ref": "str"}
COMMENT = {"id": "str", "kind": ("in", ["comment", "suggestion", "ambiguity"]), "text": "str", "by": "str", "at": "iso",
           "state": ("in", ["open", "accepted", "declined", "answered"]), "decided_by": NAME,
           "decided_at": ("?", "iso"), "answer": NAME}
SIGN = ("?", {"by": "str", "at": "iso"})
REGISTER = {"rows": [{"code": "str", "name": "str", "kind": ("in", ["measure", "definition"]), "owner": "str",
                      "pipeline": NAME,
                      "signed": {k: SIGN for k in ("charter", "baseline", "blueprint", "uat", "release")},
                      "version": "int", "href": "str"}]}
ROLES = {"architect": NAME, "developer": NAME, "tester": NAME, "sponsor": "str", "ops": NAME, "informed": ["str"]}
