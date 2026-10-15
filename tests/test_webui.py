"""The built UI is served by the backend through a declared public mount."""
import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.auth import all_routes, route_keys
from sh_platform.auth.permissions import load_permissions
from sh_platform.settings import load_settings

INDEX = "<!doctype html><title>fake ui</title>"


def make_app(tmp_path, with_dist=True):
    dist = tmp_path / "dist"
    if with_dist:
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text(INDEX, encoding="utf-8")
        (dist / "assets" / "a.js").write_text("console.log(1)", encoding="utf-8")
    settings = load_settings({"SH_DATA_ROOT": str(tmp_path / "data")}, env_file=tmp_path / "none.env")
    return create_app(settings, dist_dir=dist)


def test_spa_pages_served_signed_out(tmp_path):
    c = TestClient(make_app(tmp_path))
    for path in ("/", "/login", "/modules/m1_intent"):
        r = c.get(path)
        assert r.status_code == 200 and r.text == INDEX, path
    assert c.get("/assets/a.js").text == "console.log(1)"


def test_api_routes_still_win_and_unknown_api_is_not_index(tmp_path):
    c = TestClient(make_app(tmp_path))
    assert c.get("/api/health").json() == {"status": "ok"}
    me = c.get("/api/auth/me")
    assert me.status_code == 401 and me.json()["error"] == "session_expired"
    nope = c.get("/api/nope")
    assert nope.status_code == 404 and INDEX not in nope.text


def test_unknown_addresses_get_the_page_but_api_and_docs_stay_404(tmp_path):
    c = TestClient(make_app(tmp_path))
    for path in ("/some/unknown/page", "/Login", "/modules/x/y"):
        assert c.get(path).text == INDEX, path
    for path in ("/api/nope", "/API/nope", "/docs", "/redoc", "/openapi.json", "/favicon.ico", "/assets/missing.js"):
        r = c.get(path)
        assert r.status_code == 404 and INDEX not in r.text, path


def test_paths_cannot_escape_the_mount(tmp_path):
    (tmp_path / "secret.txt").write_text("TOPSECRET", encoding="utf-8")
    (tmp_path / "secret").write_text("TOPSECRET", encoding="utf-8")
    c = TestClient(make_app(tmp_path))
    for path in ("/..%2fsecret.txt", "/..%5csecret.txt", "/%2e%2e/secret.txt", "/..%2fsecret",
                 "/assets/..%2f..%2fsecret.txt", "/assets/..%5c..%5csecret", "/../secret.txt"):
        assert "TOPSECRET" not in c.get(path).text, path


def test_symlink_inside_dist_cannot_reach_outside(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("TOPSECRET", encoding="utf-8")
    app = make_app(tmp_path)
    try:
        (tmp_path / "dist" / "assets" / "link.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("this OS refuses symlinks")
    assert "TOPSECRET" not in TestClient(app).get("/assets/link.txt").text


def test_missing_dist_installs_nothing(tmp_path):
    app = make_app(tmp_path, with_dist=False)
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    assert c.get("/login").status_code == 404
    assert "MOUNT /{path}" not in [k for r in all_routes(app) for k in route_keys(r)]


def test_mount_is_declared_public():
    rule = load_permissions().rule_for("MOUNT", "/{path}")
    assert rule is not None and rule.public


def test_every_route_is_declared(tmp_path):
    app = make_app(tmp_path)
    declared = load_permissions().routes
    missing = [k for r in all_routes(app) for k in route_keys(r) if k not in declared]
    assert missing == []
