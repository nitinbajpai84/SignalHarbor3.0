import pytest


class StubGate:
    """Stub EntitlementGate: a set of (company, module) pairs that are switched on."""

    def __init__(self, *pairs):
        self.on = set(pairs)

    def is_enabled(self, company_id, module_id):
        return (company_id, module_id) in self.on


class StubModel:
    """Stub ModelClient: plays back replies in order (the last one repeats)."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, module_id, messages, tools=None):
        self.calls.append({"module_id": module_id, "messages": list(messages), "tools": tools})
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


@pytest.fixture
def gate():
    return StubGate(("acme", "m1"), ("beta", "m1"))
