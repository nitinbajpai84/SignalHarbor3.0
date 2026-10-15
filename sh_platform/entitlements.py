"""Module catalogue, company directory and per-company module switches.

Control-area files (no company data): <data_root>/_control/companies.json and entitlements.json.
Every read goes back to the file (no cache), so a switch takes effect on the next request. Anything
unreadable, unknown or not a real JSON true means "not owned" (fail closed).
"""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.plane import PlaneStore, valid_company_id, valid_module_id

CATALOGUE_PATH = Path(__file__).resolve().parent / "catalogue.yaml"
_MODULE_KEYS = {"id", "number", "name", "description", "agent"}
LOGO_NAME = re.compile(r"logo\.(png|svg)")  # the only file names a company's logo may have, in its plane's brand/ folder
_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


def clean_brand(brand) -> dict:
    """{logo?, primary_colour?} with a fixed logo file name and a hex colour; anything else is refused."""
    if not isinstance(brand, dict) or set(brand) - {"logo", "primary_colour"}:
        raise ValueError("brand must be {logo, primary_colour}")
    out = {k: v for k, v in brand.items() if v}
    if "logo" in out and not (isinstance(out["logo"], str) and LOGO_NAME.fullmatch(out["logo"])):
        raise ValueError("brand logo must be logo.png or logo.svg")
    if "primary_colour" in out and not (isinstance(out["primary_colour"], str) and _COLOUR.fullmatch(out["primary_colour"])):
        raise ValueError("brand primary_colour must be like #1a2b3c")
    return out


@dataclass(frozen=True)
class Module:
    id: str
    number: int
    name: str
    description: str
    agent: str

    def public(self) -> dict:
        return {"id": self.id, "number": self.number, "name": self.name,
                "description": self.description, "agent": self.agent}


@dataclass(frozen=True)
class Centre:
    id: str
    name: str
    description: str
    modules: tuple[str, ...]  # module ids, catalogue order; may be empty (declared, nothing in it yet)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}


@dataclass(frozen=True)
class Catalogue:
    modules: tuple[Module, ...]
    packages: dict[str, list[str]]  # package id -> module ids, catalogue order
    centres: tuple[Centre, ...] = ()

    @property
    def ids(self) -> list[str]:
        return [m.id for m in self.modules]


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"catalogue: {what} must be text")
    return value.strip()


def load_catalogue(path: Path | str | None = None) -> Catalogue:
    try:
        data = yaml.safe_load(Path(path or CATALOGUE_PATH).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"catalogue could not be read: {type(e).__name__}") from None
    if not isinstance(data, dict) or set(data) - {"centres"} != {"modules", "packages"}:
        raise ValueError("catalogue: needs 'modules' and 'packages' (and optionally 'centres')")
    modules = []
    for raw in data["modules"] if isinstance(data["modules"], list) else []:
        if not isinstance(raw, dict) or set(raw) != _MODULE_KEYS:
            raise ValueError(f"catalogue: every module needs exactly {sorted(_MODULE_KEYS)}")
        mid = raw["id"]
        if not valid_module_id(mid):
            raise ValueError("catalogue: bad module id")
        if not isinstance(raw["number"], int) or isinstance(raw["number"], bool):
            raise ValueError("catalogue: module number must be a whole number")
        modules.append(Module(mid, raw["number"], *(_text(raw[k], f"module {k}")
                                                    for k in ("name", "description", "agent"))))
    ids = [m.id for m in modules]
    if not modules or len(set(ids)) != len(ids) or len({m.number for m in modules}) != len(modules):
        raise ValueError("catalogue: modules are missing or repeated")
    packages: dict[str, list[str]] = {}
    for pid, spec in (data["packages"] if isinstance(data["packages"], dict) else {}).items():
        if not valid_module_id(pid) or not isinstance(spec, dict) \
                or set(spec) != {"name", "modules"}:
            raise ValueError("catalogue: every package needs exactly 'name' and 'modules'")
        _text(spec["name"], "package name")
        members = spec["modules"]
        if not isinstance(members, list) or not members or not all(isinstance(m, str) for m in members) \
                or len(set(members)) != len(members) or not set(members) <= set(ids):
            raise ValueError(f"catalogue: package {pid} must list known modules once each")
        packages[pid] = [i for i in ids if i in members]
    if not packages:
        raise ValueError("catalogue: no packages")
    centres: list[Centre] = []
    for raw in data.get("centres") or []:
        if not isinstance(raw, dict) or set(raw) != {"id", "name", "description", "modules"}                 or not valid_module_id(raw["id"]) or not isinstance(raw["modules"], list):
            raise ValueError("catalogue: every centre needs exactly id, name, description, modules")
        members = raw["modules"]
        if not all(isinstance(m, str) for m in members) or len(set(members)) != len(members)                 or not set(members) <= set(ids):
            raise ValueError(f"catalogue: centre {raw['id']} must list known modules once each")
        centres.append(Centre(raw["id"], _text(raw["name"], "centre name"),
                              _text(raw["description"], "centre description"), tuple(i for i in ids if i in members)))
    cids = [c.id for c in centres]
    all_members = [m for c in centres for m in c.modules]
    if len(set(cids)) != len(cids) or len(set(all_members)) != len(all_members):
        raise ValueError("catalogue: a centre or a module is repeated across centres")
    return Catalogue(tuple(modules), packages, tuple(centres))


def _clean(value, what: str, limit: int, *, forbid_paths: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit \
            or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{what} must be short plain text")
    value = value.strip()
    if forbid_paths and (".." in value or "/" in value or "\\" in value):
        raise ValueError(f"{what} must not look like a path")
    return value


class EntitlementStore:
    def __init__(self, data_root, catalogue: Catalogue | None = None):
        self.catalogue = catalogue or load_catalogue()
        self._planes = PlaneStore(data_root)
        control = self._planes.root / "_control"  # company ids cannot start with "_": no clash
        self._companies_path, self._ent_path = control / "companies.json", control / "entitlements.json"
        self._lock = lock_for(self._companies_path)  # one lock for both files

    # -- files
    @staticmethod
    def _load(path: Path, kind: type):
        data = read_json_strict(path, kind)
        return kind() if data is None else data

    @staticmethod
    def _write(path: Path, data) -> None:
        write_json_atomic(path, data)

    def _row(self, company_id) -> dict:
        """The company's switches, or {} for anything unknown or unreadable."""
        try:
            valid_company_id(company_id)
            if self.company(company_id) is None:  # fail closed: no directory entry, nothing owned
                return {}
            with self._lock:
                row = self._load(self._ent_path, dict).get(company_id)
        except (OSError, ValueError, TypeError, RecursionError):
            return {}
        return row if isinstance(row, dict) else {}

    # -- queries
    def company(self, company_id) -> dict | None:
        try:
            valid_company_id(company_id)
            with self._lock:
                rows = self._load(self._companies_path, list)
        except (OSError, ValueError, TypeError, RecursionError):
            return None
        return next((dict(r) for r in rows if isinstance(r, dict) and r.get("company_id") == company_id), None)

    def enabled_modules(self, company_id) -> list[str]:
        return [m for m in self.catalogue.ids if self.is_enabled(company_id, m)]

    def centre_for(self, module_id) -> str | None:
        return next((c.id for c in self.catalogue.centres if module_id in c.modules), None)

    @staticmethod
    def _centre_on(row: dict, centre_id) -> bool:
        """Absent key means on (existing companies keep working); anything present must be a real true."""
        switches = row.get("centres", {})
        return isinstance(switches, dict) and (centre_id not in switches or switches[centre_id] is True)

    def centres_for(self, company_id) -> list[Centre]:
        """Centres switched on for the company that hold at least one module it owns."""
        row = self._row(company_id)
        owned = {m for m in self.catalogue.ids if row.get(m) is True}
        return [c for c in self.catalogue.centres if owned & set(c.modules) and self._centre_on(row, c.id)]

    def list_companies(self) -> list[dict]:
        """The directory rows (a copy), unreadable file means none."""
        try:
            with self._lock:
                rows = self._load(self._companies_path, list)
        except (OSError, ValueError, TypeError, RecursionError):
            return []
        return [dict(r) for r in rows if isinstance(r, dict) and isinstance(r.get("company_id"), str)]

    def switches(self, company_id) -> dict:
        """{"modules": {id: bool}, "centres": {id: bool}} as set, for the control panel; real true only."""
        row = self._row(company_id)
        return {"modules": {m: row.get(m) is True for m in self.catalogue.ids},
                "centres": {c.id: self._centre_on(row, c.id) for c in self.catalogue.centres}}

    def is_enabled(self, company_id, module_id) -> bool:
        """Never raises. Only a real JSON true for a catalogue module of a known company counts, and
        its centre must not be switched off."""
        if not isinstance(module_id, str) or module_id not in self.catalogue.ids:
            return False
        row = self._row(company_id)
        return row.get(module_id) is True and self._centre_on(row, self.centre_for(module_id))

    # -- changes
    def create_company(self, company_id, name, industry, package=None, modules=None, brand=None) -> dict:
        valid_company_id(company_id)
        rec = {"company_id": company_id, "name": _clean(name, "name", 200),
               "industry": _clean(industry, "industry", 64, forbid_paths=True)}  # a pack folder name: any text
        if package is not None and modules is not None:
            raise ValueError("give a package or a list of modules, not both")
        if package is not None:
            key = package.strip().casefold() if isinstance(package, str) else None
            if key not in self.catalogue.packages:
                raise ValueError("unknown package")
            owned = set(self.catalogue.packages[key])
            rec["package"] = key
        else:
            if modules is not None and (not isinstance(modules, (list, tuple, set, frozenset))
                                        or not all(isinstance(m, str) and m in self.catalogue.ids for m in modules)):
                raise ValueError("unknown module")
            owned = set(modules or ())
            rec["package"] = None
        if brand:
            rec["brand"] = clean_brand(brand)
        with self._lock:
            companies, ent = self._load(self._companies_path, list), self._load(self._ent_path, dict)
            if any(isinstance(r, dict) and r.get("company_id") == company_id for r in companies):
                raise FileExistsError("company already exists")
            self._planes.create(company_id)  # empty plane; FileExistsError if the folder is there
            self._write(self._companies_path, [*companies, rec])  # companies first: a crash then owns nothing
            self._write(self._ent_path, {**ent, company_id: {m: m in owned for m in self.catalogue.ids}})
        return dict(rec)

    def set_module(self, company_id, module_id, enabled) -> None:
        valid_company_id(company_id)
        if not isinstance(module_id, str) or module_id not in self.catalogue.ids:
            raise ValueError("unknown module")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        with self._lock:
            if self.company(company_id) is None:
                raise LookupError("unknown company")
            ent = self._load(self._ent_path, dict)
            row = ent.get(company_id) if isinstance(ent.get(company_id), dict) else {}
            self._write(self._ent_path, {**ent, company_id: {**row, module_id: enabled}})

    def set_centre(self, company_id, centre_id, enabled) -> None:
        valid_company_id(company_id)
        if centre_id not in {c.id for c in self.catalogue.centres}:
            raise ValueError("unknown centre")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        with self._lock:
            if self.company(company_id) is None:
                raise LookupError("unknown company")
            ent = self._load(self._ent_path, dict)
            row = ent.get(company_id) if isinstance(ent.get(company_id), dict) else {}
            self._write(self._ent_path, {**ent, company_id: {**row, "centres": {**(row.get("centres") if isinstance(row.get("centres"), dict) else {}), centre_id: enabled}}})

    def set_brand(self, company_id, brand) -> None:
        """Replaces the company's brand record (used by the seed to bring an existing company up to date)."""
        valid_company_id(company_id)
        brand = clean_brand(brand)
        with self._lock:
            rows = self._load(self._companies_path, list)
            if not any(isinstance(r, dict) and r.get("company_id") == company_id for r in rows):
                raise LookupError("unknown company")
            self._write(self._companies_path, [{**r, "brand": brand} if isinstance(r, dict) and r.get("company_id") == company_id else r
                                               for r in rows])
