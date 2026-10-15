import os
import logging

import pytest
import yaml

from sh_platform.app import create_app
from sh_platform.auth import all_routes, iter_routes, route_keys
from sh_platform.auth.accounts import check_password, hash_password
from sh_platform.auth.permissions import load_permissions
from sh_platform.settings import Settings, load_settings

EXPIRED = {"error": "session_expired", "message": "Your session has ended. Please sign in again.",
           "login_url": "/login"}


def csrf(c):
    return {"X-CSRF-Token": c.cookies["sh_csrf"]}


# ---- login
def test_login_ok_and_me(kit):
    c, acct, _ = kit.login("agent-one", "co-a", ["approver"])
    assert "sh_session" in c.cookies and "sh_csrf" in c.cookies
    me = c.get("/api/auth/me").json()
    assert me == {"display_name": acct["display_name"], "company_id": "co-a", "roles": ["approver"], "account_id": acct["account_id"], "time_zone": "Asia/Singapore"}  # PF2: the company zone, default Singapore
    assert "hash" not in str(me)


def test_all_login_failures_look_identical(kit):
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    c = kit.client()
    bad = c.post("/api/auth/login", json={"email": acct["email"], "password": "wrong"})
    unknown = c.post("/api/auth/login", json={"email": "nobody@test.invalid", "password": "x"})
    junk = c.post("/api/auth/login", content=b"not json", headers={"content-type": "application/json"})
    assert (bad.status_code, bad.json()) == (unknown.status_code, unknown.json()) == (401, bad.json())
    assert junk.status_code == 401 and junk.json() == bad.json()


def test_login_requires_json_content_type(kit):
    import json
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    body = json.dumps({"email": acct["email"], "password": pw})
    c = kit.client()
    for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        r = c.post("/api/auth/login", content=body, headers={"content-type": ctype})
        assert r.status_code == 415 and r.json()["error"] == "login_failed"
    assert "sh_session" not in c.cookies
    ok = c.post("/api/auth/login", content=body, headers={"content-type": "application/json; charset=utf-8"})
    assert ok.status_code == 200


def test_login_destroys_the_session_whose_cookie_was_sent(kit):
    c, acct, pw = kit.login("agent-one")
    old = c.cookies["sh_session"]
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    assert c.cookies["sh_session"] != old
    c.cookies.set("sh_session", old)
    assert c.get("/api/t/echo").json() == EXPIRED


def test_lockout_key_is_normalised(kit):
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    c = kit.client()
    variants = [acct["email"].upper(), " " + acct["email"], acct["email"] + " ", acct["email"].title(),
                acct["email"]]
    for v in variants:
        c.post("/api/auth/login", json={"email": v, "password": "x"})
    r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
    assert r.status_code == 401 and "sh_session" not in c.cookies


def test_unknown_email_still_runs_the_hash_check(kit, monkeypatch):
    from sh_platform.auth import accounts
    calls = []
    real = accounts.check_password
    monkeypatch.setattr(accounts, "check_password", lambda *a: calls.append(a) or real(*a))
    assert kit.store.verify("nobody@test.invalid", "x") is None
    assert len(calls) == 1


def test_roles_validated_against_yaml_on_create(kit):
    for roles in (["organiser"], ["participant", "wizard"], []):
        with pytest.raises(ValueError):
            kit.store.create("r@test.invalid", "pw", "R", "co-a", roles)


def test_add_roles_backfills_known_roles_only(kit):
    kit.store.create("h@test.invalid", "pw", "H", "co-a", ["analyst"])
    kit.store.add_roles("h@test.invalid", ["head_of_data", "analyst"])
    assert kit.store.get_by_email("h@test.invalid")["roles"] == ["analyst", "head_of_data"]
    for roles in (["wizard"], ["super_admin"]):
        with pytest.raises(ValueError):
            kit.store.add_roles("h@test.invalid", roles)


@pytest.mark.parametrize("bad", ["", "no-at", "a@b@c", "a b@test.invalid", "a\x7f@test.invalid",
                                 "a\x00@test.invalid", "x" * 250 + "@t.io"])
def test_email_sanity(kit, bad):
    with pytest.raises(ValueError):
        kit.store.create(bad, "pw", "E", "co-a", ["participant"])


def test_two_store_instances_do_not_lose_writes(kit):
    import threading
    from sh_platform.auth.accounts import AccountStore
    stores = [kit.store, AccountStore(kit.settings.data_root)]
    errors = []

    def go(i):
        try:
            stores[i % 2].create(f"t{i}@test.invalid", "pw", "T", "co-a", ["participant"])
        except Exception as e:  # noqa: BLE001 - collected and asserted below
            errors.append(e)
    threads = [threading.Thread(target=go, args=(i,)) for i in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == [] and all(kit.store.get_by_email(f"t{i}@test.invalid") for i in range(16))


@pytest.mark.parametrize("spec", [
    {"public": True, "authenticated": True}, {"public": True, "roles": ["approver"]}, {}])
def test_loader_refuses_contradictory_rules(tmp_path, spec):
    f = tmp_path / "p.yaml"
    f.write_text(yaml.safe_dump({"roles": {"approver": "x"}, "routes": {"GET /a": spec}}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_permissions(f)


def test_loader_refuses_unknown_role(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text(yaml.safe_dump({"roles": {"approver": "x"}, "routes": {"GET /a": {"roles": ["ghost"]}}}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="unknown role"):
        load_permissions(f)


def test_login_content_type_exact_media_type(kit):
    import json
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    body = json.dumps({"email": acct["email"], "password": pw})
    c = kit.client()
    r = c.post("/api/auth/login", content=body, headers={"content-type": "text/plain; x=application/json"})
    assert r.status_code == 415
    r = c.post("/api/auth/login", content=body, headers={"content-type": "APPLICATION/JSON ; charset=x"})
    assert r.status_code == 200


def test_lockout_pruning_keeps_live_locks(kit):
    from sh_platform.auth.sessions import MAX_TRACKED
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    c = kit.client()
    for _ in range(5):
        c.post("/api/auth/login", json={"email": acct["email"], "password": "x"})
    t = kit.app.state.login_throttle
    for i in range(MAX_TRACKED + 500):
        t.failed(f"flood{i}@test.invalid")
    assert len(t._state) <= MAX_TRACKED
    r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
    assert r.status_code == 401 and "sh_session" not in c.cookies  # still locked


def test_disabled_account_session_stays_dead_after_reenable(kit):
    c, acct, _ = kit.login("agent-one")
    _edit_account(kit, acct["account_id"], disabled=True)
    assert c.get("/api/t/echo").status_code == 401
    _edit_account(kit, acct["account_id"], disabled=False)
    assert c.get("/api/t/echo").status_code == 401


def test_password_check_runs_off_the_event_loop_thread(kit, monkeypatch):
    import threading
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    seen = []
    real = kit.store.verify
    monkeypatch.setattr(kit.store, "verify", lambda *a: seen.append(threading.get_ident()) or real(*a))
    with kit.client() as c:  # `with` keeps ONE event-loop thread for every request
        loop_ident = c.get("/api/t/loop-thread").json()["ident"]
        assert c.get("/api/t/loop-thread").json()["ident"] == loop_ident  # the loop thread is stable
        assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200
    assert seen and seen[0] != loop_ident


def test_failed_write_leaves_accounts_file_unchanged(kit, monkeypatch):
    kit.store.create("first@test.invalid", "pw", "F", "co-a", ["participant"])
    before = kit.store._path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full (test)")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        kit.store.create("second@test.invalid", "pw", "S", "co-a", ["participant"])
    monkeypatch.undo()
    assert kit.store._path.read_bytes() == before
    assert not list(kit.store._path.parent.glob("*.tmp"))


def _forge(kit, cookie, **changes):
    import base64
    import json
    body = cookie.rsplit(".", 1)[0]
    payload = json.loads(base64.urlsafe_b64decode(body))
    payload.update(changes)
    new = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{new}.{kit.app.state.sessions._sig(new)}"


def test_absolute_timeout_comes_from_server_record_not_cookie(kit):
    c, _, _ = kit.login("agent-one")
    # Stay active (a request every 29 min, so the idle timer never fires) with a cookie whose own exp is
    # far in the future. Only the server-side absolute limit (8 h) can end it.
    statuses = []
    for _ in range(18):  # 18 x 29 min = 522 min, past 480
        forged = _forge(kit, c.cookies["sh_session"], exp=kit.clock.now + 10**9)
        c.cookies.delete("sh_session")
        c.cookies.set("sh_session", forged)
        statuses.append(c.get("/api/t/echo").status_code)
        kit.clock.now += 29 * 60
    assert statuses[:16] == [200] * 16  # up to 464 min
    assert statuses[-1] == 401
    forged = _forge(kit, c.cookies["sh_session"], exp=kit.clock.now + 10**9)
    c.cookies.delete("sh_session")
    c.cookies.set("sh_session", forged)
    assert c.get("/api/t/echo").json() == EXPIRED


def test_cookie_with_another_accounts_sid_is_refused(kit):
    a, acct_a, _ = kit.login("agent-a")
    b, acct_b, _ = kit.login("agent-b")
    a.cookies.set("sh_session", _forge(kit, a.cookies["sh_session"], account_id=acct_b["account_id"]))
    assert a.get("/api/t/echo").json() == EXPIRED


def test_request_state_is_reset_per_request(kit):
    c, _, _ = kit.login("agent-one", "co-a", ["approver"])
    assert c.get("/api/t/echo").json()["company_id"] == "co-a"
    assert c.get("/api/t/public-state").json() == {"company_id": None, "roles": []}


def test_websocket_origin_must_match_host(kit):
    c, _, _ = kit.login("agent-one")
    with c.websocket_connect("/ws/ok", headers={"origin": "http://testserver"}) as ws:
        assert ws.receive_text() == "hi"
    assert _ws_code_with(c, "/ws/ok", {"origin": "http://evil.example"}) == 1008
    assert _ws_code_with(c, "/ws/ok", {"origin": "http://testserver:9999"}) == 1008
    for odd in ("null", "", "http://eviltestserver"):  # Host is testserver
        assert _ws_code_with(c, "/ws/ok", {"origin": odd}) == 1008, odd
    with c.websocket_connect("/ws/ok") as ws:  # no Origin header (non-browser client): allowed
        assert ws.receive_text() == "hi"


def _ws_code_with(client, path, headers):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(path, headers=headers) as ws:
            ws.receive_text()
    return e.value.code


def test_scrypt_cost_is_n_2_15():
    assert hash_password("x").split("$")[1:4] == ["32768", "8", "1"]


def test_device_name_company_rejected(kit):
    with pytest.raises(ValueError):
        kit.store.create("dev@test.invalid", "pw", "D", "con", ["participant"])


def test_lockout_after_five_failures_then_clears(kit):
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    c = kit.client()
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": acct["email"], "password": "x"}).status_code == 401
    # locked: even the right password is refused, with the same answer
    r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
    assert r.status_code == 401 and r.json()["error"] == "login_failed"
    kit.clock.now += 61
    assert c.post("/api/auth/login", json={"email": acct["email"], "password": pw}).status_code == 200


def test_disabled_account_cannot_log_in(kit):
    acct = kit.store.create("off@test.invalid", "pw-fake", "Off", "co-a", ["participant"], disabled=True)
    r = kit.client().post("/api/auth/login", json={"email": acct["email"], "password": "pw-fake"})
    assert r.status_code == 401 and r.json()["error"] == "login_failed"


def test_super_admin_has_no_company(kit):
    c, _, _ = kit.login("root-agent", None, ["super_admin"])
    assert c.get("/api/t/echo").status_code == 403  # `authenticated` alone never admits a companyless account
    me = c.get("/api/auth/me")  # its rule lists super_admin explicitly
    assert me.status_code == 200 and me.json()["company_id"] is None
    assert c.post("/api/auth/logout", headers=csrf(c)).status_code == 200
    with pytest.raises(ValueError):
        kit.store.create("x@test.invalid", "pw", "X", "co-a", ["super_admin"])
    with pytest.raises(ValueError):
        kit.store.create("y@test.invalid", "pw", "Y", None, ["participant"])


@pytest.mark.parametrize("bad", ["_x", "Co", "a b", "", "-a", "a" * 65, "co-a\n"])
def test_company_id_rules(kit, bad):
    with pytest.raises(ValueError):
        kit.store.create("z@test.invalid", "pw", "Z", bad, ["participant"])


# ---- sessions
def test_unauthenticated_api_is_401_and_browser_is_302(kit):
    c = kit.client()
    r = c.get("/api/t/echo")
    assert r.status_code == 401 and r.json() == EXPIRED
    r = c.get("/page", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/login"
    r = c.get("/api/t/echo", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 401  # under /api/ stays JSON


def test_tampered_cookie_and_wrong_secret(kit, make_kit):
    c, _, _ = kit.login("agent-one")
    good = c.cookies["sh_session"]
    body, sig = good.rsplit(".", 1)
    c.cookies.set("sh_session", body + "." + ("0" * len(sig)))
    assert c.get("/api/t/echo").json() == EXPIRED
    c.cookies.set("sh_session", "garbage")
    assert c.get("/api/t/echo").json() == EXPIRED
    other = make_kit(secret="a-different-fake-secret")
    oc = other.client()
    oc.cookies.set("sh_session", good)
    assert oc.get("/api/t/echo").status_code == 401


def test_idle_timeout(kit):
    c, _, _ = kit.login("agent-one")
    kit.clock.now += 29 * 60
    assert c.get("/api/t/echo").status_code == 200  # activity resets idle
    kit.clock.now += 29 * 60
    assert c.get("/api/t/echo").status_code == 200
    kit.clock.now += 31 * 60
    r = c.get("/api/t/echo")
    assert r.status_code == 401 and r.json() == EXPIRED


def test_absolute_timeout(kit):
    c, _, _ = kit.login("agent-one")
    for _ in range(17):  # active every 29 min (493 min in total), still ends at 8 h (480 min)
        kit.clock.now += 29 * 60
        c.get("/api/t/echo")
    assert c.get("/api/t/echo").json() == EXPIRED


def test_timeouts_overridable(make_kit):
    k = make_kit(idle_seconds=10, absolute_seconds=100)
    c, _, _ = k.login("agent-one")
    k.clock.now += 11
    assert c.get("/api/t/echo").status_code == 401


def test_logout_then_reuse(kit):
    c, _, _ = kit.login("agent-one")
    old = c.cookies["sh_session"]
    assert c.post("/api/auth/logout", headers=csrf(c)).status_code == 200
    c.cookies.set("sh_session", old)
    assert c.get("/api/t/echo").json() == EXPIRED


def test_cookie_flags(kit, make_kit):
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    h = kit.client().post("/api/auth/login", json={"email": acct["email"], "password": pw}).headers
    sess = [v for v in h.get_list("set-cookie") if v.startswith("sh_session=")][0].lower()
    tok = [v for v in h.get_list("set-cookie") if v.startswith("sh_csrf=")][0].lower()
    assert "httponly" in sess and "samesite=lax" in sess and "secure" not in sess
    assert "httponly" not in tok
    prod = make_kit(mode="prod", secret="fake-long-test-secret-" + "x" * 16)
    acct, pw = prod.account("agent-prod", "co-a", ["participant"])
    h = prod.client().post("/api/auth/login", json={"email": acct["email"], "password": pw}).headers
    assert "secure" in h.get_list("set-cookie")[0].lower()


def test_secret_required_outside_dev(make_kit):
    with pytest.raises(RuntimeError, match="SH_SESSION_SECRET"):
        make_kit(mode="prod", secret="")
    with pytest.raises(RuntimeError, match="32"):
        make_kit(mode="prod", secret="too-short-fake")
    make_kit(mode="prod", secret="fake-abcdefghij-0123456789-secret")
    for weak in (" " * 32, "f" * 32, "abcdefg" * 6, " " * 10 + "abc" + " " * 30,
                 " " * 24 + "abcdefgh"):  # last: 32 chars, but only 8 once stripped  # blanks, <8 distinct chars
        with pytest.raises(RuntimeError):
            make_kit(mode="prod", secret=weak)
    make_kit(mode="dev", secret="")  # dev generates a per-process secret
    make_kit(mode="dev", secret="short")  # dev does not insist on length


# ---- CSRF
def test_csrf(kit):
    c, _, _ = kit.login("agent-one")
    assert c.post("/api/t/write").status_code == 403
    assert c.post("/api/t/write", headers={"X-CSRF-Token": "nope"}).status_code == 403
    assert c.post("/api/t/write?csrf=" + c.cookies["sh_csrf"]).status_code == 403  # never from query
    assert c.post("/api/t/write", headers=csrf(c)).status_code == 200
    assert c.get("/api/t/echo").status_code == 200  # GET unaffected
    for method in ("put", "patch", "delete"):
        assert getattr(c, method)("/api/t/write").status_code == 403
        assert getattr(c, method)("/api/t/write", headers=csrf(c)).status_code == 200
    # another session's token in BOTH header and cookie is still refused
    other, _, _ = kit.login("agent-other")
    stolen = other.cookies["sh_csrf"]
    c.cookies.set("sh_csrf", stolen)
    assert c.post("/api/t/write", headers={"X-CSRF-Token": stolen}).status_code == 403
    c2, _, _ = kit.login("agent-two")  # another session's token does not work
    assert c.post("/api/t/write", headers=csrf(c2)).status_code == 403


# ---- default deny and roles
def test_undeclared_route_is_403_but_unknown_is_404(kit):
    c, _, _ = kit.login("agent-one")
    assert c.get("/api/t/undeclared").status_code == 403
    assert kit.client().get("/api/t/undeclared").status_code == 403
    assert c.get("/api/nothing-here").status_code == 404


def test_every_real_route_is_declared(tmp_path):
    app = create_app(load_settings({}, env_file=tmp_path / "none.env"))
    declared = load_permissions().routes
    keys = [k for r in all_routes(app) for k in route_keys(r)]
    assert len(keys) >= 4  # health + three auth routes: the walk really saw them
    assert [k for k in keys if k not in declared] == []


def test_included_router_routes_are_checked_too(kit):
    from fastapi import APIRouter
    r = APIRouter(prefix="/api/inc")
    r.add_api_route("/thing/{n}", lambda n: {"n": n}, methods=["GET"])
    kit.app.include_router(r)
    c, _, _ = kit.login("agent-one")
    assert c.get("/api/inc/thing/1").status_code == 403  # present but undeclared
    assert [x.path_format for x in iter_routes(kit.app.routes)].count("/api/inc/thing/{n}") == 1


def _ws_code(client, path):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(path) as ws:
            ws.receive_text()
    return e.value.code


def test_websocket_undeclared_or_signed_out_is_closed_1008(kit):
    assert _ws_code(kit.client(), "/ws/ok") == 1008  # declared, no session
    c, _, _ = kit.login("agent-one", "co-a", ["participant"])
    assert _ws_code(c, "/ws/undeclared") == 1008  # signed in, undeclared
    assert _ws_code(c, "/ws/approvers") == 1008  # wrong role
    with c.websocket_connect("/ws/ok") as ws:  # declared and signed in
        assert ws.receive_text() == "hi"


def test_undeclared_frontend_is_refused(kit, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<p>secret</p>", encoding="utf-8")
    kit.app.frontend("/site", directory=dist)
    assert kit.client().get("/site/").status_code == 403
    c, _, _ = kit.login("agent-one")
    r = c.get("/site/")
    assert r.status_code == 403 and "secret" not in r.text


def test_mount_refused_unless_declared(make_kit, tmp_path):
    from fastapi.staticfiles import StaticFiles
    files = tmp_path / "files"
    files.mkdir()
    (files / "a.txt").write_text("hello", encoding="utf-8")
    k = make_kit()
    k.app.mount("/files", StaticFiles(directory=files))
    assert k.client().get("/files/a.txt").status_code == 403
    k2 = make_kit(extra_routes={"MOUNT /files/{path}": {"authenticated": True}})
    k2.app.mount("/files", StaticFiles(directory=files))
    assert k2.client().get("/files/a.txt").status_code == 401  # declared: needs a session
    c, _, _ = k2.login("agent-mount")
    assert c.get("/files/a.txt").text == "hello"


def test_enumeration_fails_on_what_it_cannot_classify(kit, tmp_path):
    from fastapi.staticfiles import StaticFiles
    kit.app.mount("/m", StaticFiles(directory=tmp_path))
    keys = [k for r in all_routes(kit.app) for k in route_keys(r)]
    assert "WEBSOCKET /ws/ok" in keys and "MOUNT /m/{path}" in keys and "GET /api/t/echo" in keys
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")
    kit.app.frontend("/site", directory=dist)
    with pytest.raises(ValueError, match="cannot classify"):
        [route_keys(r) for r in all_routes(kit.app)]


def test_declared_secret_is_401_signed_out_undeclared_is_403(kit):
    c = kit.client()
    assert c.get("/api/t/echo").status_code == 401
    assert c.get("/api/t/undeclared").status_code == 403


def test_non_ascii_csrf_header_is_403(kit):
    c, _, _ = kit.login("agent-one")
    r = c.post("/api/t/write", headers={"X-CSRF-Token": b"\xc3\xa9\xff"})
    assert r.status_code == 403


def _edit_account(kit, account_id, **fields):
    import json
    path = kit.store._path
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if row["account_id"] == account_id:
            row.update(fields)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_live_session_ends_when_account_disabled(kit):
    c, acct, _ = kit.login("agent-one")
    assert c.get("/api/t/echo").status_code == 200
    _edit_account(kit, acct["account_id"], disabled=True)
    assert c.get("/api/t/echo").json() == EXPIRED


def test_roles_and_company_come_from_the_account_on_every_request(kit):
    c, acct, _ = kit.login("agent-one", "co-a", ["approver"])
    assert c.get("/api/t/approve").status_code == 200
    _edit_account(kit, acct["account_id"], roles=["participant"])  # role removed
    assert c.get("/api/t/approve").status_code == 403
    _edit_account(kit, acct["account_id"], company_id="co-b")
    assert c.get("/api/t/echo").json() == {"company_id": "co-b", "roles": ["participant"]}


def test_lockout_table_is_bounded(kit):
    from sh_platform.auth.sessions import MAX_TRACKED
    t = kit.app.state.login_throttle
    for i in range(MAX_TRACKED + 500):
        t.failed(f"user{i}@test.invalid")
    assert len(t._state) <= MAX_TRACKED
    kit.clock.now += 3600
    t.failed("one-more@test.invalid")
    assert len(t._state) == 1  # stale entries dropped


def test_fastapi_version_is_the_tested_one():
    import fastapi
    major_minor = tuple(int(x) for x in fastapi.__version__.split(".")[:2])
    assert major_minor == (0, 142), (
        f"FastAPI {fastapi.__version__} is not the version sh_platform/auth was tested with (0.142.x). "
        "Re-check iter_routes / all_routes in sh_platform/auth/__init__.py (they read FastAPI internals "
        "for include_router and app.frontend routes), then update this test."
    )


def test_roles_list_and_approver_present():
    roles = load_permissions().roles
    assert set(roles) == {"super_admin", "company_admin", "sponsor", "analyst", "head_of_data", "approver",
                          "participant", "owner"}
    assert "organiser" not in roles and all(roles.values())


def test_role_check(kit):
    p, _, _ = kit.login("agent-p", "co-a", ["participant"])
    a, _, _ = kit.login("agent-a", "co-a", ["approver"])
    assert p.get("/api/t/approve").status_code == 403
    assert a.get("/api/t/approve").status_code == 200


# ---- company comes from the session
def test_company_from_session_only(kit):
    c, _, _ = kit.login("agent-one", "co-a")
    r = c.get("/api/t/echo?company_id=co-b", headers={"X-Company-Id": "co-b", "X-Company": "co-b"})
    assert r.json()["company_id"] == "co-a"
    r = c.post("/api/t/write", json={"company_id": "co-b"}, headers=csrf(c))
    assert r.status_code == 200


def test_two_companies_same_test(kit):
    a, _, _ = kit.login("agent-a", "co-a", ["analyst"])
    b, _, _ = kit.login("agent-b", "co-b", ["analyst"])
    assert a.get("/api/t/echo").json()["company_id"] == "co-a"
    assert b.get("/api/t/echo").json()["company_id"] == "co-b"


# ---- secrets and hashing
def test_hash_is_salted_scrypt():
    h1, h2 = hash_password("same-fake-pw"), hash_password("same-fake-pw")
    assert h1 != h2 and h1.startswith("scrypt$")
    assert check_password("same-fake-pw", h1) and not check_password("other", h1)
    assert not check_password("x", "garbage")


def test_store_keeps_hash_not_password(kit):
    acct, pw = kit.account("agent-one", "co-a", ["participant"])
    raw = (kit.store._path).read_text(encoding="utf-8")
    assert pw not in raw and acct["password_hash"].startswith("scrypt$")
    assert kit.store.verify(acct["email"], pw) and kit.store.verify(acct["email"], "no") is None


def test_logs_hold_no_secret_password_or_cookie(make_kit, caplog):
    caplog.set_level(logging.DEBUG)
    k = make_kit(secret="")  # dev: generated secret logged only as a fact
    acct, pw = k.account("agent-one", "co-a", ["participant"])
    c = k.client()
    c.post("/api/auth/login", json={"email": acct["email"], "password": "wrong-fake"})
    c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
    cookie = c.cookies["sh_session"]
    c.get("/api/t/echo")
    text = caplog.text
    for secret in (pw, "wrong-fake", cookie, acct["password_hash"], k.app.state.sessions._key.decode()):
        assert secret not in text
    assert "generated a per-process secret" in text


def test_health_public_and_unchanged(tmp_path):
    from fastapi.testclient import TestClient
    r = TestClient(create_app(Settings(data_root=str(tmp_path)))).get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_in_company_lists_only_that_company_and_never_secrets(kit):
    a = kit.store.create("ic1@test.invalid", "pw", "Ann", "co-a", ["participant"])
    kit.store.create("ic2@test.invalid", "pw", "Bob", "co-b", ["participant"], disabled=True)
    assert kit.store.in_company("co-a")[-1] == {"account_id": a["account_id"], "display_name": "Ann",
                                                "roles": ["participant"], "disabled": False}
    assert all(set(x) == {"account_id", "display_name", "roles", "disabled"} for x in kit.store.in_company("co-b"))
    assert [x["display_name"] for x in kit.store.in_company("co-b")][-1] == "Bob"
    assert kit.store.in_company("co-none") == []
