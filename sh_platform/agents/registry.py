"""Tool registry: read-only tools, gate checked on listing and on every call, results are summaries.

What a result may hold (anything else is refused or hidden):
- An AGGREGATE is any dict that holds a figure: a number (not a bool) under a label, or a list of numbers,
  other than ids (`id`, `*_id`) and `group_size` itself. Every aggregate must carry its own integer
  `group_size` of MIN_GROUP or more; otherwise it becomes {"available": False}. Children are judged on their
  own: a breakdown inside a group needs its own `group_size`, the parent's does not cover it.
- A bare number as the whole result is an aggregate with no group, so it is unavailable.
- A number inside a LIST, at any depth, is unavailable: the whole list becomes {"available": False}. The one
  exception is a list item that is a dict, which is judged as an aggregate with its own `group_size`. Lists of
  non-numeric names stay allowed.
- Numeric strings ("2", "3.5", "1,200") count as numbers everywhere above.
- Raw rows are refused: any key named rows/records (any case, also "data rows", "dataRows"), or any list
  longer than MAX_LIST holding dicts, lists or strings.
- Only strict JSON is returned: NaN and infinity are refused.

A PROPOSE tool (`proposes=True`, never read-only, never outside) is the one exception to read-only: its function only checks the
arguments and returns the cleaned item (or raises ToolRefused). The loop collects that item; nothing is written during the run.
"""
import json
import re
from typing import Callable

from sh_platform.agents.groups import MIN_GROUP, group_ok, is_figure
from sh_platform.agents.protocols import EntitlementGate

__all__ = ["MIN_GROUP", "ToolRefused", "ToolRegistry"]
MAX_LIST = 50
_RAW_WORDS = {"rows", "records"}
_REFUSAL = "That tool is not available."
_UNAVAILABLE = {"available": False}


class ToolRefused(Exception):
    """A tool call was refused. The message is safe to show."""


class ToolRegistry:
    def __init__(self, gate: EntitlementGate):
        self._gate = gate
        self._tools: dict[tuple[str, str], dict] = {}

    def register(self, module_id: str, name: str, func: Callable, *, read_only: bool,
                 description: str, parameters: dict[str, str], outside: bool = False, proposes: bool = False) -> None:
        if proposes is True:
            if read_only is not False or outside:
                raise ToolRefused("a propose tool is neither read-only nor outside")
        elif read_only is not True:  # the loop is read-only, apart from propose tools that only collect
            raise ToolRefused("only read-only tools can be registered")
        if (module_id, name) in self._tools:
            raise ValueError("tool already registered")
        self._tools[(module_id, name)] = {"func": func, "description": description,
                                          "parameters": dict(parameters), "outside": outside,
                                          "proposes": proposes is True}

    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return bool(self._gate.is_enabled(company_id, module_id))

    def is_outside(self, module_id: str, name: str) -> bool:
        t = self._tools.get((module_id, name))
        return bool(t and t["outside"])

    def is_proposal(self, module_id: str, name: str) -> bool:
        t = self._tools.get((module_id, name))
        return bool(t and t["proposes"])

    def tools_for(self, company_id: str, module_id: str) -> list[dict]:
        if not self.is_enabled(company_id, module_id):
            return []
        return [{"name": n, "description": t["description"], "parameters": t["parameters"]}
                for (m, n), t in self._tools.items() if m == module_id]

    def call(self, company_id: str, module_id: str, name: str, arguments: dict):
        tool = self._tools.get((module_id, name))
        if tool is None or not self.is_enabled(company_id, module_id):
            raise ToolRefused(_REFUSAL)  # unknown, not owned and switched off look the same
        if not isinstance(arguments, dict) or set(arguments) != set(tool["parameters"]):
            raise ToolRefused("The tool was called with the wrong arguments.")
        arguments = {k: _from_json(v, tool["parameters"][k]) for k, v in arguments.items()}
        if tool["proposes"]:
            item = tool["func"](**arguments)  # the argument check: the cleaned item, or ToolRefused
            if not isinstance(item, dict):
                raise ToolRefused("The proposal could not be checked.")
            return item
        return _summary_only(tool["func"](**arguments))


def _from_json(value, declared):
    """Safety net: a provider that sent an object or list as JSON text gets it read back. The tool's own checks still run on it."""
    want = {"object": dict, "array": list}.get(declared)
    if want and isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            return value
        return parsed if isinstance(parsed, want) else value
    return value


def _summary_only(value):
    try:
        value = json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError):
        raise ToolRefused("The tool returned data that cannot be shown.") from None
    if is_figure("value", value):
        return dict(_UNAVAILABLE)  # a bare number has no group
    return _walk(value)


def _is_raw_key(key: str) -> bool:
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(key)).lower()
    return bool(_RAW_WORDS & set(re.split(r"[^a-z0-9]+", words)))


def _bare_number(node) -> bool:
    """A number, or a list holding one at any depth. A dict is judged by its own group_size instead."""
    if isinstance(node, list):
        return any(_bare_number(x) for x in node)
    return is_figure("value", node)


def _walk(node):
    if isinstance(node, list):
        if len(node) > MAX_LIST and any(isinstance(x, (dict, list, str)) for x in node):
            raise ToolRefused("raw rows")
        if any(_bare_number(x) for x in node):
            return dict(_UNAVAILABLE)
        return [_walk(x) for x in node]
    if isinstance(node, dict):
        if any(_is_raw_key(k) for k in node):
            raise ToolRefused("raw rows")
        holds_figure = any(is_figure(k, v) or (isinstance(v, list) and any(is_figure(k, x) for x in v))
                           for k, v in node.items())
        if "group_size" in node or holds_figure:
            if not group_ok(node.get("group_size")):
                return dict(_UNAVAILABLE)
        return {k: _walk(v) for k, v in node.items()}
    return node
