"""Test UI copy for game words, model names, em-dashes, and American spellings.

Checks files under:
- ui/src/pages
- ui/src/design
- ui/src/shell
- ui/src/modules/*/{wall,define,charter,truth,request,intake,voice}
- sh_platform/pulse

Does NOT check:
- ui/src/modules/*/legacy
- Code that is only reachable from /modules paths
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_SRC = ROOT / "ui" / "src"
SH_PLATFORM = ROOT / "sh_platform"

# Copy violations to check for
GAME_WORDS = {
    "quest", "quests",
    "level", "levels",
    "player", "players",
    "badge", "badges",
    "score", "scores",
    "point", "points",
    "xp", "exp",
    "mission", "missions",
    "boss", "bosses",
    "unlock", "unlocked", "unlocking"
}

MODEL_NAMES = {
    "Claude", "claude",
    "Anthropic", "anthropic",
    "GPT", "gpt",
    "OpenAI", "openai",
    "Gemini", "gemini",
    "Sonnet", "sonnet",
    "Opus", "opus",
    "Haiku", "haiku"
}

# American spellings to avoid (British preferred)
AMERICAN_SPELLINGS = {
    "organize": "organise",
    "organized": "organised",
    "organizing": "organising",
    "color": "colour",
    "colored": "coloured",
}

def get_target_files():
    """Get all files to check. Excludes test files (.test.tsx, .test.ts, test_*.py)."""
    files = []

    def should_check(f):
        """Skip test files."""
        name = f.name
        return not (name.endswith(".test.tsx") or name.endswith(".test.ts") or name.startswith("test_"))

    # ui/src/pages
    pages_dir = UI_SRC / "pages"
    if pages_dir.exists():
        for f in pages_dir.rglob("*.ts*"):
            if should_check(f):
                files.append(f)

    # ui/src/design
    design_dir = UI_SRC / "design"
    if design_dir.exists():
        for f in design_dir.rglob("*.ts*"):
            if should_check(f):
                files.append(f)

    # ui/src/shell
    shell_dir = UI_SRC / "shell"
    if shell_dir.exists():
        for f in shell_dir.rglob("*.ts*"):
            if should_check(f):
                files.append(f)

    # ui/src/modules/*/ (all subdirectories except legacy)
    modules_dir = UI_SRC / "modules"
    if modules_dir.exists():
        for module_dir in modules_dir.iterdir():
            if not module_dir.is_dir() or module_dir.name == "legacy":
                continue
            # Check all subdirectories within the module, except legacy
            for subdir in module_dir.iterdir():
                if subdir.is_dir() and subdir.name != "legacy":
                    for f in subdir.rglob("*.ts*"):
                        if should_check(f):
                            files.append(f)

    # sh_platform/pulse
    pulse_dir = SH_PLATFORM / "pulse"
    if pulse_dir.exists():
        for f in pulse_dir.rglob("*.py"):
            if should_check(f):
                files.append(f)

    return sorted(set(files))

def is_string_context(line, col_start, col_end):
    """Check if a position is inside a string literal (simple heuristic)."""
    # Look for quotes before and after the token
    before = line[:col_start]
    after = line[col_end:]

    # Count quotes in before section
    single_quotes = before.count("'") - before.count("\\'")
    double_quotes = before.count('"') - before.count('\\"')
    backticks = before.count("`") - before.count("\\`")

    # If odd number of quotes, we're in a string
    in_single = (single_quotes % 2) == 1
    in_double = (double_quotes % 2) == 1
    in_backtick = (backticks % 2) == 1

    return in_single or in_double or in_backtick

def check_file(filepath):
    """Check a file for copy violations. Returns list of (line_num, text, violation)."""
    violations = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except:
        return violations

    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith("//") or line.strip().startswith("#"):
            continue

        # Check for game words (case-insensitive in strings/copy)
        for game_word in GAME_WORDS:
            pattern = r"\b" + re.escape(game_word) + r"\b"
            for match in re.finditer(pattern, line, re.IGNORECASE):
                col_start = match.start()
                col_end = match.end()

                # Only flag if in string context (conservative check)
                if is_string_context(line, col_start, col_end):
                    violations.append({
                        "line": line_num,
                        "text": line.strip(),
                        "violation": f"game word: {game_word}",
                        "file": filepath
                    })

        # Check for model names (case-sensitive, mainly in comments/copy)
        for model_name in MODEL_NAMES:
            if model_name in line:
                # Only flag in strings or comments
                if '"' in line or "'" in line or "//" in line or "#" in line:
                    violations.append({
                        "line": line_num,
                        "text": line.strip(),
                        "violation": f"model name: {model_name}",
                        "file": filepath
                    })

        # Check for em-dashes in copy (—)
        if "—" in line:
            # Only flag if in string, and not in code that's removing dashes (.replace, re.sub, etc)
            if ('"' in line or "'" in line) and not any(op in line for op in [".replace(", "re.sub(", "gsub(", ".substitute("]):
                violations.append({
                    "line": line_num,
                    "text": line.strip(),
                    "violation": "em-dash in copy",
                    "file": filepath
                })

        # Check for American spellings (only in strings)
        for american, british in AMERICAN_SPELLINGS.items():
            pattern = r"\b" + re.escape(american) + r"\b"
            for match in re.finditer(pattern, line):
                col_start = match.start()
                col_end = match.end()

                # Only flag if in string context
                if is_string_context(line, col_start, col_end):
                    # Not if it's a CSS property or class name
                    context = line[max(0, col_start-10):col_end+10]
                    if not any(x in context for x in ["color:", "backgroundColor", "fontSize"]):
                        violations.append({
                            "line": line_num,
                            "text": line.strip(),
                            "violation": f"American spelling: {american} (use {british})",
                            "file": filepath
                        })

    return violations

def test_copy_rules():
    """Test that copy follows the rules."""
    files = get_target_files()
    all_violations = {}

    for filepath in files:
        violations = check_file(filepath)
        if violations:
            rel_path = filepath.relative_to(ROOT)
            all_violations[str(rel_path)] = violations

    if all_violations:
        # Format error message
        msg = "Copy rule violations found:\n\n"
        for filepath in sorted(all_violations.keys()):
            msg += f"{filepath}:\n"
            for v in all_violations[filepath]:
                msg += f"  line {v['line']}: {v['violation']}\n"
                msg += f"    {v['text'][:80]}\n"
            msg += "\n"

        raise AssertionError(msg)

if __name__ == "__main__":
    test_copy_rules()
    print("✓ No copy rule violations found")
