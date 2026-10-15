"""Gemini wire format (generateContent). Maps the gateway's already-guarded envelope; adds no content of its own.

The key goes in the `x-goog-api-key` header (never in the URL, which would be logged by proxies)."""
import json
from dataclasses import dataclass

from sh_platform.egress.model import ToolCall, decode_turn, param_schema

MAX_OUTPUT_TOKENS = 8192  # Gemini 2.5 spends much of this on its own thinking: at 2048 grouping replies were cut off after ~500 characters (FIX-G, 4 Oct)
# AQF10-03: the output cap counts Gemini 2.5's own thinking, and on a long context it thought the whole cap away and answered empty (north_figure:
# 22,388 tokens in, empty twice). A thinking budget of a quarter of the cap leaves at least 6,000 tokens for the answer. 2.5 models only: they
# take thinkingBudget (2.5 Pro needs 128 or more); later models keep their default (ponytail: set thinkingLevel there if they also end empty).
THINKING_BUDGET = 2048


def _tool_declaration(t: dict) -> dict:
    d = {"name": t["name"], "description": t["description"]}
    if t["parameters"]:  # names with their JSON type (param_schema); never values
        props = param_schema(t["parameters"])
        schema = {"type": "object", "required": list(props), "properties": props}
        # the OpenAPI-style `parameters` refuses an object or array with no inner schema; full JSON Schema takes it
        d["parametersJsonSchema" if any(v["type"] in ("object", "array") for v in props.values()) else "parameters"] = schema
    return d


def _push(contents: list[dict], role: str, parts: list[dict]) -> None:
    if contents and contents[-1]["role"] == role:
        contents[-1]["parts"].extend(parts)  # the API wants alternating turns
    else:
        contents.append({"role": role, "parts": parts})


@dataclass(frozen=True)
class GeminiAdapter:
    name: str = "gemini"
    host: str = "generativelanguage.googleapis.com"
    key_env: str = "GOOGLE_API_KEY"
    header: str = "x-goog-api-key"
    scheme: str = ""
    model_id: str = r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}"  # goes into the URL path: no ":" or "/"
    default_models: tuple = (("manager", "gemini-3.1-pro-preview"), ("specialist", "gemini-2.5-flash"),
                             ("fast", "gemini-2.5-flash"))
    thinking_budget: int | None = None  # generationConfig.thinkingConfig.thinkingBudget; None keeps Gemini's default (short structured tasks set a small one)

    def format_request(self, model: str, messages: list[dict], tools: list[dict] | None) -> tuple[str, dict]:
        system, contents = [], []
        for m in map(decode_turn, messages):
            role = m["role"]
            if role == "system":
                system.append(m["content"])
            elif role == "assistant" and "calls" in m:
                parts = ([{"text": m["text"]}] if m["text"] else []) + [
                    {"functionCall": {"name": c.name, "args": c.arguments}} for c in m["calls"]]
                _push(contents, "model", parts)
            elif role == "assistant":
                _push(contents, "model", [{"text": m["content"] or " "}])
            elif role == "tool" and m["name"]:
                _push(contents, "user", [{"functionResponse": {"name": m["name"],
                                                               "response": {"result": m["content"]}}}])
            else:
                _push(contents, "user", [{"text": m["content"] or " "}])
        body: dict = {"contents": contents, "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS}}
        budget = self.thinking_budget if self.thinking_budget is not None else THINKING_BUDGET if model.startswith("gemini-2.5") else None
        if budget is not None:
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": budget}
        if system:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [_tool_declaration(t) for t in tools]}]
        return f"/v1beta/models/{model}:generateContent", body

    def parse_reply(self, raw: str) -> tuple[str, list[ToolCall]]:
        """(text, tool calls). Anything unreadable is empty text and no calls; a malformed call is dropped."""
        try:
            parts = json.loads(raw)["candidates"][0]["content"]["parts"]
        except (ValueError, KeyError, IndexError, TypeError):
            return "", []
        text, calls = [], []
        for p in parts if isinstance(parts, list) else []:
            if not isinstance(p, dict) or p.get("thought") is True:
                continue  # the model's own thinking is never shown
            fc = p.get("functionCall")
            if isinstance(fc, dict) and isinstance(fc.get("name"), str) and isinstance(fc.get("args", {}), dict):
                calls.append(ToolCall(fc["name"], fc.get("args") or {},
                                      fc["id"] if isinstance(fc.get("id"), str) and fc["id"] else f"call_{len(calls)}"))
            elif isinstance(p.get("text"), str):
                text.append(p["text"])
        return "".join(text), calls
