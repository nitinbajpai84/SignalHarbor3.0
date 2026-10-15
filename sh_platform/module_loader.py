"""Module loader: finds modules/<id>/manifest.yaml, mounts each module's router under /api/modules/<id>/ and
merges its route declarations into the sign-in permission table.

Rules, in order of importance:
- Default deny stays: a manifest route the table does not declare is added with the manifest's roles; one the
  table declares differently stops the start with a plain message (a developer error, never silent).
- A router route the manifest does not declare also stops the start: code not in the manifest is not part of the
  module.
- A module with no manifest, a broken manifest, a wrong id or a router that will not import is logged and
  skipped; its routes then do not exist (404 behind the module gate). One module never takes the app down.
- Who may reach a module is the module gate's job (sh_platform/modulegate.py), not this file's.
"""
import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, FastAPI

from sh_platform.auth import all_routes, route_keys
from sh_platform.auth.permissions import Permissions, Rule
from sh_platform.manifest import Manifest, ManifestError, load_manifest, manifest_route_gaps

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "modules"


def _auth_permissions(app: FastAPI) -> Permissions:
    for mw in app.user_middleware:
        if mw.kwargs.get("perms") is not None:
            return mw.kwargs["perms"]
    raise RuntimeError("install_auth must run before install_modules")


def _load_router(folder: Path, module_id: str, default_root: bool) -> APIRouter:
    if default_root:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))  # modules import each other's parts as modules.<id>.<part>
        mod = importlib.import_module(f"modules.{module_id}.api")
    else:  # a module folder somewhere else (tests): load its api package from the file
        init = folder / "api" / "__init__.py"
        spec = importlib.util.spec_from_file_location(f"_sh_module_{module_id}_api", init,
                                                      submodule_search_locations=[str(init.parent)])
        if spec is None or spec.loader is None:
            raise ImportError("no api package")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    router = getattr(mod, "router", None)
    if not isinstance(router, APIRouter):
        raise TypeError("the api package has no router")
    return router


def _merge_permissions(manifest: Manifest, perms: Permissions) -> None:
    for r in manifest.routes:
        perms.routes.setdefault(f"{r.method} {r.path}", Rule(roles=frozenset(r.roles)))
    gaps = manifest_route_gaps(manifest, perms)
    if gaps:
        raise RuntimeError(
            f"Module {manifest.id} cannot start: the permissions for {', '.join(gaps)} in its manifest do not "
            f"match route_permissions.yaml. Make the two agree, then start again.")


def _check_declared(app: FastAPI, manifest: Manifest) -> None:
    prefix, declared = f"/api/modules/{manifest.id}/", {f"{r.method} {r.path}" for r in manifest.routes}
    extra = []
    for route in all_routes(app):
        if not getattr(route, "path_format", "").startswith(prefix):
            continue
        try:
            extra += [k for k in route_keys(route) if k not in declared]
        except ValueError:
            extra.append(route.path_format)  # a route type we cannot classify is not declared either
    if extra:
        raise RuntimeError(f"Module {manifest.id} cannot start: its code has routes its manifest does not "
                           f"declare ({', '.join(sorted(extra))}). Declare them in manifest.yaml.")


def install_modules(app: FastAPI, modules_root: Path | str | None = None) -> list[str]:
    """Call after install_auth and install_modulegate, before the UI mount. Returns the ids that loaded."""
    root = Path(modules_root) if modules_root is not None else DEFAULT_ROOT
    perms, loaded = _auth_permissions(app), []
    if not root.is_dir():
        log.info("No modules folder at %s; no modules loaded.", root)
        return loaded
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        if not (folder / "manifest.yaml").is_file():
            log.info("Module folder %s has no manifest yet; skipped.", folder.name)
            continue
        try:
            manifest = load_manifest(folder / "manifest.yaml", known_roles=perms.roles)
            if manifest.id != folder.name:
                raise ManifestError("the id must match the folder name")
            router = _load_router(folder, manifest.id, default_root=modules_root is None)
        except ManifestError as e:
            log.warning("Module %s skipped: %s", folder.name, e)
            continue
        except Exception as e:  # noqa: BLE001 - a broken module must not stop the others
            log.warning("Module %s skipped: it could not be loaded (%s).", folder.name, type(e).__name__)
            continue
        _merge_permissions(manifest, perms)
        app.include_router(router, prefix=f"/api/modules/{manifest.id}")
        _check_declared(app, manifest)
        loaded.append(manifest.id)
    return loaded
