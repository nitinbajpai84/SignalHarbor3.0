"""One isolated data plane per company under the data root. Fails closed."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from sh_platform import jsonfile

AREAS = ("landing", "warehouse", "intents", "baseline", "context", "graph")
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_MODULE_ID = re.compile(r"[a-z][a-z0-9_]*")
_DEVICE = re.compile(r"(con|prn|aux|nul|conin\$|conout\$|clock\$|com[0-9¹²³]|lpt[0-9¹²³])",
                     re.I)  # Windows device names
_DRIVE = re.compile(r"[A-Za-z]:")  # "C:" opens a Windows drive path
_NAME_MAX = 255  # longest file name most file systems accept
_NOT_READY = "plane could not be prepared"


class CrossCompanyError(PermissionError):
    """A request reached outside the signed-in company's plane."""


class InvalidCompanyId(ValueError):
    """The company id is not an allowed name."""


def valid_company_id(value) -> str:
    # fullmatch + explicit ASCII class: no unicode lookalikes, no trailing newline
    if not isinstance(value, str) or not _ID.fullmatch(value) or _DEVICE.fullmatch(value):
        raise InvalidCompanyId("invalid company id")
    return value


def valid_module_id(value) -> bool:
    """True for a module (or tool, or package) id: lowercase letters, digits, underscores, starting with a letter."""
    return isinstance(value, str) and _MODULE_ID.fullmatch(value) is not None


def _is_device_part(part: str) -> bool:
    # "con", "NUL.txt", "aux.", "dir/com1": any component whose stem is a device name
    return any(_DEVICE.fullmatch(c.split(".")[0].split(":")[0].strip())
               for c in re.split(r"[\\/]", part))


def _is_bad_part(part) -> bool:
    """Refused on every OS alike: Windows refuses these itself, Linux would take "..\\beta" or "C:\\x" as one plain name."""
    if not isinstance(part, str) or "\x00" in part or _is_device_part(part):
        return True
    return any(_DRIVE.match(c) or len(c) > _NAME_MAX for c in re.split(r"[\\/]", part))


def _plain(p: Path) -> Path:
    """Windows: resolve() can hand back the extended form \\\\?\\D:\\... when another thread creates a folder of the path while it resolves
    (Python 3.11 ntpath.realpath), and that form is never "under" the plain root. The same path without the prefix is checked instead."""
    s = str(p)
    if not s.startswith("\\\\?\\"):
        return p
    return Path("\\\\" + s[8:] if s[4:8].upper() == "UNC\\" else s[4:])


def _state_path():
    from sh_platform.state.routing import StatePath
    return StatePath


def _wrap(folder: Path) -> Path:
    """Production mode: the folder is a StatePath, so every path under it sends its .json documents to the state store."""
    return _state_path()(folder) if jsonfile.ROUTE is not None else folder


@dataclass(frozen=True)
class CompanyPlane:
    company_id: str
    root: Path = field(repr=False)

    def __post_init__(self):
        valid_company_id(self.company_id)
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise ValueError("plane root must be an absolute path")

    def path(self, *parts) -> Path:
        # Resolved (symlink/junction-free) result must stay under root.
        if any(_is_bad_part(p) for p in parts):
            raise CrossCompanyError("path outside company plane")
        try:  # a backslash is a separator on every OS, so "..\\beta" is judged as "../beta"
            p = self.root.joinpath(*(p.replace("\\", "/") for p in parts)).resolve()
        except (OSError, RuntimeError, ValueError):  # RuntimeError: link loop
            raise CrossCompanyError("path outside company plane") from None
        p = _plain(p)
        if jsonfile.ROUTE is not None:
            p = _state_path()(p)
        if not p.is_relative_to(self.root):
            raise CrossCompanyError("path outside company plane")
        if not p.exists() and parts and str(parts[0]) in ("library", "projects"):  # L3: a library file that moved into its folder
            from sh_platform.v1 import l3_library
            new = l3_library.alias(self.root, "/".join(str(x).replace("\\", "/") for x in parts))
            if new:
                return self.path(*new.split("/"))
        return p

    def area(self, name: str) -> Path:
        if name not in AREAS:
            raise ValueError("unknown area")
        return self.path(name)

    def ensure(self) -> "CompanyPlane":
        try:
            for a in AREAS:
                self.area(a).mkdir(parents=True, exist_ok=True)
        except CrossCompanyError:
            raise
        except OSError:
            raise RuntimeError(_NOT_READY) from None
        return self


class PlaneStore:
    def __init__(self, data_root):
        self.root = Path(data_root).resolve()

    def _plane(self, company_id: str) -> CompanyPlane:
        """Validate the id; refuse a link (symlink/junction, even dangling) in its place."""
        valid_company_id(company_id)
        folder = self.root / company_id
        try:
            plain = not folder.is_symlink() and os.path.normcase(folder.resolve()) == os.path.normcase(folder)
        except (OSError, RuntimeError, ValueError):  # RuntimeError: link loop
            plain = False
        if not plain:
            raise CrossCompanyError("plane is not a plain folder in the data root")
        return CompanyPlane(company_id, _wrap(folder))

    def exists(self, company_id: str) -> bool:
        return self._plane(company_id).root.is_dir()

    def plane_for(self, company_id: str) -> CompanyPlane:
        plane = self._plane(company_id)
        if not plane.root.is_dir():
            raise LookupError("unknown company")
        return plane

    def create(self, company_id: str) -> CompanyPlane:
        plane = self._plane(company_id)
        try:
            plane.root.mkdir(parents=True)  # atomic: no exists()-then-mkdir race
        except OSError:
            raise (FileExistsError("company already exists") if plane.root.is_dir()
                   else RuntimeError(_NOT_READY)) from None
        return plane.ensure()

    def list_company_ids(self) -> list[str]:
        try:
            names = sorted(d.name for d in self.root.iterdir() if d.is_dir())
        except OSError:
            return []
        ids = []
        for n in names:
            try:
                self._plane(n)
            except (InvalidCompanyId, CrossCompanyError):
                continue
            ids.append(n)
        return ids


def require_same_company(session_company_id, requested_company_id) -> None:
    try:
        ok = valid_company_id(session_company_id) == valid_company_id(requested_company_id)
    except InvalidCompanyId:
        ok = False
    if not ok:
        raise CrossCompanyError("request is for a different company")
