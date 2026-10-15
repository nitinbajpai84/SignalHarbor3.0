"""OpenRouter wire format (OpenAI-compatible chat completions). Maps the gateway's already-guarded envelope."""
import json
from dataclasses import dataclass

from sh_platform.egress.model import ToolCall, decode_turn, param_schema

MAX_TOKENS = 4096  # an agent reply holds a spoken answer plus a patch of the document; 1,024 cut it off mid-JSON and forced a retry


def _tool_declaration(t: dict) -> dict:
    return {"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": {"type": "object", "required": list(param_schema(t["parameters"])),
                       "properties": param_schema(t["parameters"])}}}


@dataclass(frozen=True)
class OpenRouterAdapter:
    name: str = "openrouter"
    host: str = "openrouter.ai"
    key_env: str = "OPENROUTER_API_KEY"
    header: str = "authorization"
    scheme: str = "Bearer"
    # vendor/model, up to three segments, an optional ":variant" at the end; never "." or ".." as a segment
    model_id: str = r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,60}){0,2}(?::[A-Za-z0-9._-]{1,30})?"
    default_models: tuple = (("manager", "anthropic/claude-sonnet-5"), ("specialist", "anthropic/claude-sonnet-5"),
                             ("fast", "anthropic/claude-haiku-4.5"))

    def format_request(self, model: str, messages: list[dict], tools: list[dict] | None) -> tuple[str, dict]:
        out = []
        for m in map(decode_turn, messages):
            if m["role"] == "assistant" and "calls" in m:
                out.append({"role": "assistant", "content": m["text"] or None, "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
                    for c in m["calls"]]})
            elif m["role"] == "tool" and m["id"]:
                out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
            elif m["role"] == "tool":
                out.append({"role": "user", "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        body: dict = {"model": model, "messages": out, "max_tokens": MAX_TOKENS}
        if tools:
            body["tools"] = [_tool_declaration(t) for t in tools]
        return "/api/v1/chat/completions", body

    def parse_reply(self, raw: str) -> tuple[str, list[ToolCall]]:
        """(text, tool calls). Anything unreadable is empty text and no calls; a malformed call is dropped."""
        try:
            msg = json.loads(raw)["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            return "", []
        if not isinstance(msg, dict):
            return "", []
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function") if isinstance(c, dict) else None
            if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                continue
            if isinstance(args, dict):
                calls.append(ToolCall(fn["name"], args, c["id"] if isinstance(c.get("id"), str) and c["id"] else f"call_{i}"))
        text = msg.get("content")
        return (text if isinstance(text, str) else ""), calls
