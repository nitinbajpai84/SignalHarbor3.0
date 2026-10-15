"""Write skills/<id>/SKILL.md for every skill in docs/v3/SKILLS-CATALOGUE.md (run once; run again to refresh the core skills).

Front matter and body sections follow docs/v3/HARBOR-SPEC.md ("Added 15 Oct"). Steps come from the goal and output only: no invented rules.
tests.jsonl is written only where v3_skills has a check function for the skill."""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

log = logging.getLogger(__name__)
CATALOGUE = ROOT / "docs" / "v3" / "SKILLS-CATALOGUE.md"
OUT = ROOT / "skills"
CENTRE = {"intent": "intent", "data": "build", "model": "build", "map": "build", "build": "build", "run": "build", "check": "build",
          "action": "action", "consume": "consume", "knowledge": "knowledge", "harbor": "knowledge"}
TIER = {"F": "fast", "S": "strong", "T": "tools", "T+F": "tools"}  # T+F: mostly tools
ROW = re.compile(r"^\|\s*(?:([^|`]*?)\s*\|\s*)?`([a-z]+\.[a-z0-9-]+)`\s*\|(.*)\|\s*$")
TOKEN = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?:\.[a-z_]+)?|\b[a-z]\d+[a-z]*\b")
# known answers: only where a plain check can be written (see v3_skills.CHECKS)
TESTS = {
    "data.detect-duplicate": [{"input": {"a": "abc", "b": "abc"}, "expected": "yes"}, {"input": {"a": "abc", "b": "abd"}, "expected": "no"}],
    "run.load-file": [{"input": {"rows_in": 120, "rows_out": 120}, "expected": "ok"}, {"input": {"rows_in": 120, "rows_out": 119}, "expected": "fail"}],
    "intent.sign": [{"input": {"clicked": "Anita Rao", "signed": "Anita Rao"}, "expected": "ok"},
                    {"input": {"clicked": "Anita Rao", "signed": "Grace Ong"}, "expected": "fail"}],
    "consume.answer-from-cache": [{"input": {"cached_version": "run-7", "current_version": "run-7"}, "expected": "hit"},
                                  {"input": {"cached_version": "run-6", "current_version": "run-7"}, "expected": "miss"}],
}


def parse(text: str) -> list[dict]:
    """The catalogue tables -> one dict per skill (id, goal, output, check, tier, from, milestone)."""
    rows, milestone = [], ""
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        if m.group(1):
            milestone = m.group(1).strip()
        cells = [c.strip() for c in m.group(3).split("|")]
        if len(cells) != 5:
            log.warning("skipped a catalogue row with %d cells: %s", len(cells), m.group(2))
            continue
        goal, output, check, tier, src = cells
        rows.append({"id": m.group(2), "goal": goal, "output": output, "check": check, "tier": TIER[tier], "from": src, "milestone": milestone})
    return rows


def tools_of(src: str) -> list[str]:
    return list(dict.fromkeys(TOKEN.findall(src)))


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render(r: dict) -> str:
    sid = r["id"]
    prefix, _, short = sid.partition(".")
    name = short.replace("-", " ").capitalize()
    goal = r["goal"].rstrip(".")
    tools = tools_of(r["from"])
    steps = ["Read what Harbor passes in for this step.", goal[0].upper() + goal[1:] + ".", f"Produce: {r['output']}.",
             f"Check: {r['check']}. If the check fails, stop and ask a person."]
    never = ["Never invent a figure, name or rule that is not in the inputs.", "Never act outside its own output."]
    if r["tier"] == "tools":
        never.append("Never call a model.")
    inputs = f"What the milestone \"{r['milestone']}\" hands over." if r["milestone"] else "What Harbor hands over for this step."
    head = ["---", f"id: {sid}", f"name: {q(name)}", f"goal: {q(goal)}", f"when: {q('Use when: ' + goal[0].lower() + goal[1:])}",
            f"centre: {CENTRE[prefix]}", "source: core", f"tier: {r['tier']}", "version: 1", "status: in_use", f"from: {q(r['from'])}", "---", ""]
    body = [f"# {name}", "", "## Inputs", inputs, "", "## Output", r["output"], "", "## Steps", *[f"{i}. {s}" for i, s in enumerate(steps, 1)], "",
            "## Tools", *([f"- {t}" for t in tools] or ["- none (new code)"]), "", "## Checks", f"- {r['check']}", "", "## Never", *[f"- {n}" for n in never], ""]
    return "\n".join(head + body)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = parse(CATALOGUE.read_text(encoding="utf-8"))
    for r in rows:
        d = OUT / r["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(render(r), encoding="utf-8", newline="\n")
        if r["id"] in TESTS:
            (d / "tests.jsonl").write_text("\n".join(json.dumps(t) for t in TESTS[r["id"]]) + "\n", encoding="utf-8", newline="\n")
    log.info("wrote %d skills to %s", len(rows), OUT)
    return 0 if len(rows) == 63 else 1


if __name__ == "__main__":
    raise SystemExit(main())
