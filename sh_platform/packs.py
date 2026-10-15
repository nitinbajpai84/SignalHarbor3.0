"""Pack loader: industry knowledge is always read by parameter from packs/<industry>/<version>/."""
import functools
import json
import re
from pathlib import Path

import yaml

SUGGESTION_LABEL = (
    "What others in the industry usually track "
    "(a suggestion, not your company's own definition)"
)
_INDUSTRY_RE = re.compile(r"[a-z0-9_]+")
_VERSION_RE = re.compile(r"[1-9][0-9]*")
_NOT_SECTIONS = {"pack", "template", "generator"}  # metadata and old build files, not content


class Pack:
    empty = False
    suggestion_label = SUGGESTION_LABEL

    def __init__(self, industry: str, version: int, label: str, folder: Path, status: str = "proposed"):
        self.industry, self.version, self.label, self.status = industry, version, label, status
        self.folder = folder
        self._files = {
            f.stem: f
            for f in sorted(folder.iterdir())
            if f.is_file() and f.suffix in (".yaml", ".yml", ".json") and f.stem not in _NOT_SECTIONS
        }

    def sections(self) -> list[str]:
        return list(self._files)

    def section(self, name: str):
        f = self._files[name]  # unknown name raises KeyError
        return _read_section(str(f), f.stat().st_mtime_ns)

    def intents_section(self, name: str):
        """A file under the pack's intents/ folder (file 49); an unknown name raises KeyError."""
        f = self.folder / "intents" / f"{name}.yaml"
        if not f.is_file():
            raise KeyError(name)
        return _read_section(str(f), f.stat().st_mtime_ns)


_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


@functools.lru_cache(maxsize=256)
def _read_section(path: str, mtime_ns: int):
    """Parsed pack file, cached per path and modification time (packs are read on every room request)."""
    f = Path(path)
    text = f.read_text(encoding="utf-8")
    return json.loads(text) if f.suffix == ".json" else yaml.load(text, Loader=_YAML_LOADER)


class EmptyPack:
    empty = True
    suggestion_label = SUGGESTION_LABEL

    def __init__(self, industry: str):
        self.industry = industry
        self.message = (
            "No industry knowledge is available yet for this industry. "
            "You can still work from your own company's information."
        )

    def sections(self) -> list[str]:
        return []

    def intents_section(self, name: str):
        raise KeyError(name)

    def section(self, name: str):
        raise KeyError(name)


class PackLoader:
    def __init__(self, packs_root):
        self.root = Path(packs_root)

    def _versions(self, industry: str) -> list[int]:
        d = self.root / industry
        if not d.is_dir():
            return []
        return sorted(int(v.name) for v in d.iterdir() if v.is_dir() and _VERSION_RE.fullmatch(v.name))

    def industries(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            d.name for d in self.root.iterdir()
            if d.is_dir() and _INDUSTRY_RE.fullmatch(d.name) and self._versions(d.name)
        )

    def load(self, industry: str, version: "str | int | None" = None) -> "Pack | EmptyPack":
        if not _INDUSTRY_RE.fullmatch(industry):
            raise ValueError("industry must be lowercase letters, digits or underscore")
        if version is not None and not _VERSION_RE.fullmatch(str(version)):
            raise ValueError("version must be a whole number")
        versions = self._versions(industry)
        want = max(versions, default=None) if version is None else int(version)
        if want not in versions:
            return EmptyPack(industry)  # never another industry's or version's content
        folder = self.root / industry / str(want)
        meta_file = folder / "pack.yaml"
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else {}
        meta = meta or {}
        return Pack(industry, want, meta.get("label", industry), folder, meta.get("status", "proposed"))
