"""Route permission table: loaded from route_permissions.yaml, default deny."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "route_permissions.yaml"
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class Rule:
    public: bool = False
    authenticated: bool = False
    roles: frozenset[str] = frozenset()
    guest: bool = False  # a person with only an X-Session-Token may use it (module routes, see auth/guest.py)
    entry: bool = False  # guest routes only: also reachable with NO session and NO token; the handler decides


@dataclass(frozen=True)
class Permissions:
    roles: dict[str, str]
    routes: dict[str, Rule]

    def rule_for(self, method: str, path_format: str) -> Rule | None:
        return self.routes.get(f"{method.upper()} {path_format}")


def is_unsafe(method: str) -> bool:
    return method.upper() in _UNSAFE


def load_permissions(path: Path | str | None = None) -> Permissions:
    data = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8")) or {}
    roles = {str(k): str(v) for k, v in (data.get("roles") or {}).items()}
    merged = dict(data.get("routes") or {})
    if path is None:  # 1.0: each card declares its own routes beside its code; the kernel file wins on a clash
        from sh_platform.v1 import extra_permission_files
        for f in extra_permission_files():
            for k, v in ((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("routes") or {}).items():
                merged.setdefault(" ".join(str(k).split()), v)
    routes: dict[str, Rule] = {}
    for key, spec in merged.items():
        spec = spec or {}
        rule = Rule(
            public=bool(spec.get("public")),
            authenticated=bool(spec.get("authenticated")),
            roles=frozenset(spec.get("roles") or ()),
            guest=spec.get("guest", False),
            entry=spec.get("entry", False),
        )
        if rule.public and (rule.authenticated or rule.roles) or not (
                rule.public or rule.authenticated or rule.roles):
            raise ValueError(f"route {key!r} needs public, or authenticated and/or roles")
        if not rule.roles <= roles.keys():
            raise ValueError(f"route {key!r} names an unknown role")
        _check_guest(key, rule)
        routes[" ".join(str(key).split())] = rule
    return Permissions(roles=roles, routes=routes)


def _check_guest(key: str, rule: Rule) -> None:
    """A guest rule is the widest door in the table, so it is kept narrow: a plain HTTP module route, roles that
    include participant, never public or authenticated-only. `entry` needs guest and POST. Only GET and POST may be
    guest (nothing a token holder does is a PUT, PATCH or DELETE), and never a catch-all `{x:path}` segment, which
    would open a whole subtree to a token by one line."""
    if rule.guest is not True and rule.guest is not False or rule.entry is not True and rule.entry is not False:
        raise ValueError(f"route {key!r}: guest and entry must be true or false")
    if rule.entry and not rule.guest:
        raise ValueError(f"route {key!r}: entry needs guest")
    if not rule.guest:
        return
    method, _, path = " ".join(str(key).split()).partition(" ")
    plain_module_route = re.fullmatch(r"/api/modules/[a-z][a-z0-9_]*/\S+", path) is not None
    if (method not in ("GET", "POST") or not plain_module_route or ":path}" in path or rule.public
            or rule.authenticated
            or "participant" not in rule.roles or rule.entry and method != "POST"):
        raise ValueError(f"route {key!r}: a guest route must be a plain HTTP route under /api/modules/<module>/ "
                         f"with the participant role and nothing public")
