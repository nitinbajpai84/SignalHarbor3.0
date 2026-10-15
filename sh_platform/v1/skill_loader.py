"""Skill loader (X5): an agent's skill is a folder of plain files under skills/<name>/.

load_skill(name) joins playbook, questions, traps, examples (then any other .md,
alphabetically) into one block for the agent's static prompt, trimmed to 6,000
characters. A missing folder gives "" so a card never breaks without its skill.
T1: `load_skill(name, plane)` also reads the company's `skills/<name>/*.md` (plane), whose files replace the repo's of the same name.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
ORDER = ("playbook.md", "questions.md", "traps.md", "examples.md")
LIMIT = 6000
LABELS = {"north": "North, the intent agent", "span": "Span, the build agent", "lumen": "Lumen, the consume agent",
          "tally": "Tally, the data analyst"}
# G1: three agents. The retired skill names still load (and resolve to the merged skill), so no caller breaks.
ALIASES = {"data": "span", "flow": "span", "intake": "span", "investigation": "span",
           "briefing": "lumen", "consumer": "lumen"}


def _folder(name: str) -> Path | None:
    name = ALIASES.get(name, name)
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        return None  # no path tricks in a skill name
    d = SKILLS_DIR / name
    return d if d.is_dir() else None


def agents() -> list[str]:
    """The agents that have a skill in the repo (a company can edit these): north, span, lumen."""
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and p.name not in ALIASES and "." not in p.name and not p.name.startswith("_"))


def _company_dirs(name: str, plane) -> list[Path]:
    """T1: the company's copies of an agent's skill, `skills/<folder>/` in its plane. Each file wins over the repo's file of the same name.
    A copy saved under the retired name (before the rename) is read first, so the alias target's own copy wins over it."""
    if plane is None or not name or not name.replace("_", "").replace("-", "").isalnum():
        return []
    target = ALIASES.get(name, name)
    olds = [n for n, t in ALIASES.items() if t == target]  # every retired name that folds into this agent
    dirs = [plane.path("skills", n) for n in dict.fromkeys((*olds, target))]
    return [d for d in dirs if d.is_dir()]


def is_company(path: Path, plane) -> bool:
    return plane is not None and SKILLS_DIR not in path.parents


def skill_files(name: str, plane=None) -> dict[str, Path]:
    """file name -> path, in reading order, the company's file in place of the repo's file of the same name."""
    found: dict[str, Path] = {}
    for d in (_folder(name), *_company_dirs(name, plane)):  # the company's folders last, so they replace
        if d is not None:
            found.update({p.name: p for p in d.glob("*.md")})
    first = [n for n in ORDER if n in found]
    return {n: found[n] for n in first + sorted(n for n in found if n not in ORDER)}


def load_skill(name: str, plane=None) -> str:
    """The skill block; pass the company's plane and its edited files win over the repo's defaults."""
    text = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in skill_files(name, plane).values()).strip()
    return text[:LIMIT]


def skill_label(name: str, plane=None) -> str:
    """The skill's name for the Context box: the playbook's first heading, else a fixed label."""
    play = skill_files(name, plane).get("playbook.md")
    if play is not None:
        for line in play.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
    return LABELS.get(name, name.replace("_", " ").title())
