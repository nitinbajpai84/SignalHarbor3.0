"""Adapter for the agent runtime (P1-07): complete(module_id, messages, tools) through the gateway.

The envelope is the gateway's own JSON ({"messages": [...], "tools": [...]}); real provider
adapters (a given provider's message format) live in sh_platform/egress/providers/ (A-017) and sit behind the gateway. Provider, model and URL are chosen by
the caller or settings when the gateway is built, never here."""
import json
import re
from dataclasses import dataclass, field

from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import EgressGateway


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    id: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    tool_calls: list = field(default_factory=list)
    outside: bool = False
    usage: dict | None = None  # {tokens_in, tokens_out} when the provider reported them (R1 cost log)


def parse_reply(text: str) -> tuple[str, list[ToolCall]]:
    """JSON with a "text" string and optional "tool_calls" -> both; anything else is plain text.
    A malformed tool call (no name, arguments not an object) is dropped, never run."""
    try:
        data = json.loads(text)
    except ValueError:
        return text, []
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return text, []
    calls = []
    raw = data.get("tool_calls")
    for i, c in enumerate(raw if isinstance(raw, list) else []):
        if isinstance(c, dict) and isinstance(c.get("name"), str) and isinstance(c.get("arguments"), dict):
            cid = c["id"] if isinstance(c.get("id"), str) else f"call_{i}"
            calls.append(ToolCall(c["name"], c["arguments"], cid))
    return data["text"], calls


# A tool-call turn and a tool result cross the gateway as plain text inside the allowed {role, content} keys
# (A-011, A-017). The header lines hold no bracket or brace, so the JSON after them is still scanned by the
# gateway's structural checks. Provider adapters read them back with decode_turn.
_CALLS_HEAD = "tool_calls"  # then one line: {"<id>": {"name": ..., "arguments": {...}}, ...}
_RESULT_HEAD = re.compile(r"tool_result id=(\S{1,64}) name=(\S{1,64})\n")
_TOKEN_OK = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def _word(v, fallback: str) -> str:
    return v if isinstance(v, str) and _TOKEN_OK.fullmatch(v) else fallback


# str.splitlines() (which the gateway's row scan uses) also breaks lines at these; the adapters split on a plain
# newline only. Escaped (not ensure_ascii, which would hide accented names from the vault) so a line stays one line.
_LINE_BREAKS = {c: "\\u%04x" % c for c in (0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029)}


def _one_line(s: str) -> str:
    return s.translate(str.maketrans(_LINE_BREAKS))


def encode_turn(m: dict) -> dict:
    """One loop message -> the gateway's {role, content}. A plain message is unchanged."""
    role, content = m["role"], m["content"]
    if role == "assistant" and isinstance(content, str):
        content = _one_line(content)  # assistant text can never carry a line the gateway's scan would split
    calls = m.get("tool_calls") if role == "assistant" else None
    if isinstance(calls, list) and calls:
        # SF14c: a step's calls go as ONE JSON object keyed by call id, on one line. One JSON line per call read as a
        # list of records to the gateway's rows check, so every step with two calls was refused. A keyed object is
        # never rows, and each call's arguments are still walked by every structural check.
        keyed = {}
        for i, c in enumerate(calls):
            cid = _word(c.get("id"), f"call_{i}")
            keyed[f"call_{i}" if cid in keyed else cid] = {"name": _word(c.get("name"), "tool"),
                                                           "arguments": c.get("arguments") or {}}
        lines = [content] if content else []
        lines += [_CALLS_HEAD, _one_line(json.dumps(keyed, ensure_ascii=False))]
        return {"role": role, "content": "\n".join(lines)}
    if role == "tool" and (m.get("name") or m.get("tool_call_id")):
        head = f"tool_result id={_word(m.get('tool_call_id'), 'call_0')} name={_word(m.get('name'), 'tool')}"
        return {"role": role, "content": f"{head}\n{content}"}
    return {"role": role, "content": content}


def decode_turn(m: dict) -> dict:
    """The inverse, for provider adapters: {"role": "assistant", "text", "calls": [ToolCall]},
    {"role": "tool", "id", "name", "content"} (id and name empty when the header is missing), or a plain
    {"role", "content"}."""
    role, content = m["role"], m["content"]
    if role == "tool":
        h = _RESULT_HEAD.match(content)
        return ({"role": "tool", "id": h[1], "name": h[2], "content": content[h.end():]} if h
                else {"role": "tool", "id": "", "name": "", "content": content})
    if role != "assistant":
        return {"role": role, "content": content}
    text, calls, lines, i = [], [], content.splitlines(), 0
    while i < len(lines):
        if lines[i] == _CALLS_HEAD and i + 1 < len(lines):
            try:
                keyed = json.loads(lines[i + 1])
            except ValueError:
                keyed = None
            if isinstance(keyed, dict) and keyed:
                calls += [ToolCall(_word(c.get("name"), "tool"), c["arguments"], _word(k, f"call_{n}"))
                          for n, (k, c) in enumerate(keyed.items())
                          if isinstance(c, dict) and isinstance(c.get("arguments"), dict)]
                i += 2
                continue
        text.append(lines[i])
        i += 1
    return {"role": role, "text": "\n".join(text), "calls": calls} if calls else {"role": role, "content": content}


JSON_TYPES = ("object", "array", "integer", "number", "boolean")  # "string" is the default and goes as the bare name


def _type_of(v) -> str:
    v = v.get("type") if isinstance(v, dict) else v
    return v if v in JSON_TYPES else "string"  # a description (North's style) or anything unknown is text


def _param_names(p) -> list[str]:
    """Parameter names for the gateway. A non-text JSON type rides along as `name:type`: a type word, never a value."""
    if isinstance(p, dict):
        p = p["properties"] if isinstance(p.get("properties"), dict) else p
        return [str(k) if _type_of(v) == "string" else f"{k}:{_type_of(v)}" for k, v in p.items()]
    return [x for x in p if isinstance(x, str)] if isinstance(p, list) else []


def param_schema(params) -> dict:
    """What a provider adapter declares, {name: {"type": ...}}, from the gateway's `name` / `name:type` list."""
    out = {}
    for p in params or []:
        name, _, typ = str(p).rpartition(":")
        if typ not in JSON_TYPES:
            name, typ = str(p), "string"
        out[name] = {"type": typ, "items": {}} if typ == "array" else {"type": typ}
    return out


def _back(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_back(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _back(v, fn) for k, v in obj.items()}
    return obj


class EgressModelClient:
    def __init__(self, gateway: EgressGateway):
        self.gateway = gateway

    def complete(self, module_id: str, messages: list[dict], tools=None,
                 suppressed: SuppressedFigures | None = None) -> ModelReply:
        """All messages and tool descriptions travel in ONE guarded call. A tool goes as its name,
        description and parameter NAMES (field names may leave, values never). `suppressed` is the
        per-call SuppressedFigures from the minimiser for this question."""
        payload = {"messages": [encode_turn(m) for m in messages]}
        if tools:
            payload["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                                 "parameters": _param_names(t.get("parameters"))} for t in tools]
        raw = self.gateway.send_model_prompt(module_id, payload, suppressed=suppressed, detokenise=False)
        text, calls = parse_reply(raw.text)
        def back(s):
            return self.gateway.detokenise(s, raw.tokens)  # only the names this call sent
        calls = [ToolCall(c.name, _back(c.arguments, back), c.id) for c in calls]
        try:
            used = json.loads(raw.text).get("usage")
        except (ValueError, AttributeError):
            used = None
        return ModelReply(back(text), calls, outside=False, usage=used if isinstance(used, dict) else None)
