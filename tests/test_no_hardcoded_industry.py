"""Fails if industry wording appears in kernel, module or UI source (rule: industry is a parameter)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNED = re.compile(r"insurance|insurer|asset[_ \-]?management|policyholder|reinsur", re.I)
SKIP_TOP = {"packs", "tests", "tools", "docs"}  # only at the top of a scanned root
SKIP_ANYWHERE = {"node_modules", "__pycache__", ".git", "dist"}


def find_hardcoded(*roots: Path) -> list[str]:
    hits = []
    for root in roots:
        for f in Path(root).rglob("*"):
            parts = f.relative_to(root).parts
            if not f.is_file() or parts[0] in SKIP_TOP or SKIP_ANYWHERE & set(parts):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary file
            for n, line in enumerate(text.splitlines(), 1):
                if BANNED.search(line):
                    hits.append(f"{f}:{n}")
    return hits


def test_tree_has_no_hardcoded_industry():
    roots = [ROOT / d for d in ("sh_platform", "modules", "ui/src") if (ROOT / d).is_dir()]
    assert find_hardcoded(*roots) == []


def test_walker_catches_planted_word(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n# Policyholder list\n")
    assert len(find_hardcoded(tmp_path)) == 1


def test_walker_skips_excluded_dirs(tmp_path):
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "a.yaml").write_text("insurance\n")
    assert find_hardcoded(tmp_path) == []


def test_nested_and_hyphen_words_are_caught(tmp_path):
    (tmp_path / "m" / "tools").mkdir(parents=True)
    (tmp_path / "m" / "tools" / "x.py").write_text("insurance\n")
    (tmp_path / "a.ts").write_text("const assetManagement = 1; // asset-management\n")
    assert len(find_hardcoded(tmp_path)) == 2
