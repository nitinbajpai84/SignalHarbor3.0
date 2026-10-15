"""The only seams the agent runtime depends on. Real implementations come from egress and entitlements."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)
    id: str = ""  # carried through to the tool message when the provider sets one


@dataclass(frozen=True)
class ModelReply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelClient(Protocol):
    def complete(self, module_id: str, messages: list[dict],
                 tools: list[dict] | None = None) -> ModelReply: ...


class EntitlementGate(Protocol):
    def is_enabled(self, company_id: str, module_id: str) -> bool: ...
