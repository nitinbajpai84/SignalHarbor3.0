"""Module loader (M1-P01): discovers modules/<id>/manifest.yaml, mounts the module router under
/api/modules/<id>/, merges its route declarations into the permission table, refuses a mismatch at startup,
and never lets one broken module take the app down. Temporary module folders only."""
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"
MID = "m3_connect"  # in the catalogue, has no real module yet: free for a fixture module


def manifest(roles="[analyst]", mid=MID, extra="") -> str:
    return textwrap.dedent(f"""\
        id: {mid}
        name: Fixture
        agent: Flow
        routes:
          - {{method: GET, path: /api/modules/{mid}/ping, roles: {roles}}}
        {extra}
        tools: []
        pack_sections: []
        inputs: []
        output: demo
        """)


ROUTER = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/ping")
def ping():
    return {"pong": True}
"""


def make_module(root: Path, name=MID, manifest_text=None, api=ROUTER) -> Path:
    d = root / name
    (d / "api").mkdir(parents=True)
    if manifest_text is not None:
        (d / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    if api is not None:
        (d / "api" / "__init__.py").write_text(api, encoding="utf-8")
    return d


def build(tmp_path, modules_root):
    s = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret=SECRET)
    return create_app(s, modules_root=modules_root)


def login(app, company="co-a", roles=("analyst",)):
    acct, pw = make_test_account(app.state.account_store, f"loader-{roles[0]}", company, list(roles))
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
    return c


def own(app, *modules):
    app.state.entitlements.create_company("co-a", "Company A", "industry_a", modules=list(modules))


def test_the_real_app_loads_module_1_with_its_permissions(tmp_path):
    app = build(tmp_path, None)  # the default modules folder of the repo
    own(app, "m1_intent")
    c = login(app, roles=("company_admin",))
    assert c.get("/api/modules/m1_intent/sessions").json() == []
    perms = next(mw.kwargs["perms"] for mw in app.user_middleware if mw.kwargs.get("perms"))
    assert "GET /api/modules/m1_intent/sessions" in perms.routes


def test_a_manifest_route_missing_from_the_table_is_merged_and_enforced(tmp_path):
    root = tmp_path / "mods"
    make_module(root, manifest_text=manifest())
    app = build(tmp_path, root)
    own(app, MID)
    assert login(app, roles=("analyst",)).get(f"/api/modules/{MID}/ping").json() == {"pong": True}
    assert login(app, roles=("participant",)).get(f"/api/modules/{MID}/ping").status_code == 403  # roles enforced


def test_startup_refuses_a_manifest_that_disagrees_with_the_table(tmp_path):
    root = tmp_path / "mods"
    real = (Path(__file__).resolve().parent.parent / "modules" / "m1_intent" / "manifest.yaml").read_text(encoding="utf-8")
    bad = real.replace('{method: GET, path: "/api/modules/m1_intent/lists", roles: [company_admin, sponsor, analyst]}',
                       '{method: GET, path: "/api/modules/m1_intent/lists", roles: [company_admin]}')
    assert bad != real
    make_module(root, "m1_intent", manifest_text=bad, api="from fastapi import APIRouter\nrouter = APIRouter()\n")
    with pytest.raises(RuntimeError) as e:
        build(tmp_path, root)
    msg = str(e.value)
    assert "m1_intent" in msg and "GET /api/modules/m1_intent/lists" in msg and "permission" in msg.lower()


def test_startup_refuses_a_router_route_the_manifest_does_not_declare(tmp_path):
    root = tmp_path / "mods"
    make_module(root, manifest_text=manifest(), api=ROUTER + '\n@router.get("/secret")\ndef secret():\n    return {}\n')
    with pytest.raises(RuntimeError) as e:
        build(tmp_path, root)
    assert MID in str(e.value) and "/secret" in str(e.value)


@pytest.mark.parametrize("text", ["not: [valid", "id: m3_connect\n", "- just\n- a list\n", ""])
def test_a_broken_manifest_skips_only_that_module(tmp_path, text, caplog):
    root = tmp_path / "mods"
    make_module(root, MID, manifest_text=text)
    make_module(root, "m4_build", manifest_text=manifest(mid="m4_build"), api=ROUTER)
    app = build(tmp_path, root)  # does not raise
    app.state.entitlements.create_company("co-a", "Company A", "industry_a", modules=[MID, "m4_build"])
    c = login(app)
    assert c.get(f"/api/modules/{MID}/ping").status_code == 404  # no routes: 404 behind the gate
    assert c.get("/api/modules/m4_build/ping").json() == {"pong": True}  # the neighbour still works
    assert any(MID in r.getMessage() for r in caplog.records)


def test_no_manifest_a_wrong_id_and_an_import_error_each_skip_that_module_only(tmp_path):
    root = tmp_path / "mods"
    make_module(root, "m3_connect", manifest_text=None)                                  # no manifest
    make_module(root, "m4_build", manifest_text=manifest(mid="m5_foresight"), api=ROUTER)  # id differs from folder
    make_module(root, "m5_foresight", manifest_text=manifest(mid="m5_foresight"), api="raise RuntimeError('boom')\n")
    make_module(root, "m6_ops", manifest_text=manifest(mid="m6_ops"), api=ROUTER)
    app = build(tmp_path, root)
    app.state.entitlements.create_company("co-a", "Company A", "industry_a",
                                          modules=["m3_connect", "m4_build", "m5_foresight", "m6_ops"])
    c = login(app)
    for m in ("m3_connect", "m4_build", "m5_foresight"):
        assert c.get(f"/api/modules/{m}/ping").status_code == 404, m
    assert c.get("/api/modules/m6_ops/ping").json() == {"pong": True}


def test_a_missing_modules_folder_is_fine(tmp_path):
    app = build(tmp_path, tmp_path / "does-not-exist")
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}


def test_a_module_not_owned_by_the_company_is_refused_even_though_it_loaded(tmp_path):
    root = tmp_path / "mods"
    make_module(root, manifest_text=manifest())
    app = build(tmp_path, root)
    own(app, "m1_intent")  # owns something else
    r = login(app).get(f"/api/modules/{MID}/ping")
    assert (r.status_code, r.json()["error"]) == (403, "module_not_available")
