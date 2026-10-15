"""Words and bars the journeys expect, read from the UI source so a copy or role-table change never leaves a journey waiting for old
text (cycle 1: the refusal line changed, and the Map went on every role's bar, and the journeys still expected the old ones). Stdlib only."""
import json
import re
from pathlib import Path

UI = Path(__file__).resolve().parents[2] / "ui" / "src"


def shell_copy(key: str) -> str:
    """One string of ui/src/shell/copy.ts, e.g. shell_copy("refused")."""
    m = re.search(rf'^\s*{re.escape(key)}:\s*"([^"]*)"', (UI / "shell" / "copy.ts").read_text(encoding="utf-8"), re.M)
    if not m:
        raise LookupError(f"no '{key}' in ui/src/shell/copy.ts")
    return m.group(1)


REFUSED = shell_copy("refused")  # what the shell says when a typed address is not open to the person
_LABEL = {"intent": "Intent", "pulse": "Action", "build": "Build", "consume": "Consume", "map": "Map"}


def bar_for(role: str) -> list[str]:
    """The bar labels for one role, in order: ROLE_TABLE of ui/src/shell/roles.ts put through barFor's order."""
    src = (UI / "shell" / "roles.ts").read_text(encoding="utf-8")
    table = json.loads(src.split("/* role table */", 1)[1].split("/* end role table */", 1)[0].strip())
    mine = set(table.get(role, {}).get("centres", []))
    return [_LABEL[c] for c in ("intent", "pulse", "build", "consume", "map") if c in mine]


if __name__ == "__main__":
    assert REFUSED and "not" in REFUSED, REFUSED
    assert bar_for("analyst")[:2] == ["Intent", "Action"] and "Build" in bar_for("analyst") and "Build" not in bar_for("sponsor")
    assert bar_for("nobody") == []
    print(REFUSED, bar_for("participant"))
