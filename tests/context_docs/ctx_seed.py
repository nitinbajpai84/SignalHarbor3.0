"""tools/seed.py loaded once for the context tests (a uniquely named module: `conftest` clashes across folders)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_seed():
    spec = importlib.util.spec_from_file_location("ctx_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


seed = _load_seed()
