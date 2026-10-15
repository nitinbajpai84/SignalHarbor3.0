"""modules/<id>/manifest.yaml loader. Strict: anything unexpected is an error with a plain message."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from sh_platform.auth.permissions import Permissions, load_permissions
from sh_platform.plane import valid_module_id

_SEGMENT = re.compile(r"[A-Za-z0-9_-]+|\{[a-z_][a-z0-9_]*\}")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"}
_KEYS = {"id", "name", "agent", "routes", "tools", "pack_sections", "inputs", "output"}
_ROUTE_KEYS = {"method", "path", "roles"}


class ManifestError(ValueError):
    """The manifest is not valid; the message says what to fix."""


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    id: str
    name: str
    agent: str
    routes: list[Route]
    tools: list[str]
    pack_sections: list[str]
    inputs: list[str]
    output: str


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{what} must be text")
    return value.strip()


def _list(value, what: str) -> list:
    if not isinstance(value, list):
        raise ManifestError(f"{what} must be a list")
    return value


def _route(raw, module_id: str, roles: set[str]) -> Route:
    if not isinstance(raw, dict) or set(raw) != _ROUTE_KEYS:
        raise ManifestError(f"every route needs exactly {sorted(_ROUTE_KEYS)}")
    method, path = raw["method"], raw["path"]
    if method not in _METHODS:
        raise ManifestError(f"route method must be one of {sorted(_METHODS)}")
    prefix = f"/api/modules/{module_id}/"
    if not isinstance(path, str) or not path.startswith(prefix) or not path[len(prefix):] \
            or not all(_SEGMENT.fullmatch(s) for s in path[len(prefix):].split("/")):
        raise ManifestError(f"route path must be a plain path under {prefix}")
    rs = _list(raw["roles"], "route roles")
    if not rs or not all(isinstance(r, str) and r in roles for r in rs):
        raise ManifestError("route roles must be a non-empty list of known roles")
    return Route(method, path, tuple(rs))


def load_manifest(path: Path | str, known_roles=None) -> Manifest:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise ManifestError(f"{path.name}: cannot be read as YAML") from None
    try:
        if not isinstance(data, dict):
            raise ManifestError("must be a mapping of keys")
        if set(data) - _KEYS:
            raise ManifestError(f"unknown key {sorted(map(str, set(data) - _KEYS))[0]!r}")
        if _KEYS - set(data):
            raise ManifestError(f"missing key {sorted(_KEYS - set(data))[0]!r}")
        mid = data["id"]
        if not valid_module_id(mid):
            raise ManifestError("id must be lowercase letters, digits and underscores")
        roles = set(known_roles if known_roles is not None else load_permissions().roles)
        routes, seen = [], set()
        for raw in _list(data["routes"], "routes"):
            r = _route(raw, mid, roles)
            key = (r.method, re.sub(r"\{[^}]*\}", "{}", r.path))
            if key in seen:
                raise ManifestError(f"route {r.method} {r.path} is listed twice")
            seen.add(key)
            routes.append(r)
        tools = _list(data["tools"], "tools")
        if not all(valid_module_id(t) for t in tools) or len(set(tools)) != len(tools):
            raise ManifestError("tool names must be unique and use lowercase letters, digits and underscores")
        return Manifest(
            id=mid, name=_text(data["name"], "name"), agent=_text(data["agent"], "agent"), routes=routes,
            tools=list(tools),
            pack_sections=[_text(s, "pack section") for s in _list(data["pack_sections"], "pack_sections")],
            inputs=[_text(s, "input") for s in _list(data["inputs"], "inputs")],
            output=_text(data["output"], "output"))
    except ManifestError as e:
        raise ManifestError(f"{path.name}: {e}") from None


def manifest_route_gaps(manifest: Manifest, perms: Permissions) -> list[str]:
    """Manifest routes that route_permissions.yaml does not declare with exactly the same roles.

    A module route must be declared there (default deny) AND is gated by the module gate (path prefix).
    """
    gaps = []
    for r in manifest.routes:
        rule = perms.routes.get(f"{r.method} {r.path}")
        if rule is None or rule.public or rule.authenticated or rule.roles != set(r.roles):
            gaps.append(f"{r.method} {r.path}")
    return gaps
