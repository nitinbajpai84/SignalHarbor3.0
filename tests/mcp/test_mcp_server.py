"""W2 MCP: tool listing, access refused, no raw rows, token revoke (and the draft, name and log rules)."""
import json

import pytest

from sh_platform.agents.registry import ToolRegistry
from sh_platform.auth.accounts import AccountStore
from sh_platform.mcp import server, tokens
from sh_platform.plane import PlaneStore

READ_ONLY = {"name": "x"}


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    plane = PlaneStore(root).create("acme").ensure()
    store = AccountStore(root)
    admin = store.create("admin@example.test", "pw-test-1", "Ada Admin", "acme", ["company_admin"])
    part = store.create("part@example.test", "pw-test-2", "Pat Part", "acme", ["participant"])
    return root, plane, admin, part


def rpc(root, token, method, params=None, mid=1):
    status, out = server.handle(root, token, {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
    return status, out


def call(root, token, name, args=None):
    status, out = rpc(root, token, "tools/call", {"name": name, "arguments": args or {}})
    assert status == 200
    return out["result"]


def issue(plane, account, scopes=("read",)):
    return tokens.issue(plane, account["account_id"], "test assistant", scopes)["token"]


def test_tool_listing_follows_scope(world):
    root, plane, admin, _ = world
    status, out = rpc(root, issue(plane, admin), "initialize", {"protocolVersion": "2025-06-18"})
    assert status == 200 and out["result"]["capabilities"] == {"tools": {"listChanged": False}}
    names = {t["name"] for t in rpc(root, issue(plane, admin), "tools/list")[1]["result"]["tools"]}
    assert {"search_documents", "describe_table", "list_intents", "query_figure", "get_lineage"} <= names
    assert not names & {"open_case", "propose_tile", "export_sop_docx"}  # a read token sees no write or export tool
    full = rpc(root, issue(plane, admin, tokens.SCOPES), "tools/list")[1]["result"]["tools"]
    kinds = {t["description"].split("]")[0][1:] for t in full}
    assert kinds == {"read", "propose", "export"}
    assert {"open_case", "open_ticket", "propose_tile", "propose_pipeline_change", "export_sop_docx", "export_report_pdf", "export_diagram"} <= {t["name"] for t in full}
    assert rpc(root, issue(plane, admin), "tools/nope")[1]["error"]["code"] == -32601


def test_access_refused(world):
    root, plane, admin, part = world
    assert server.handle(root, None, {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401
    assert server.handle(root, "shmcp.acme.abc.def", {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401
    good = issue(plane, admin)
    assert server.handle(root, good[:-2] + "xx", {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401
    assert server.handle(root, good.replace("acme", "other"), {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401
    # out of scope and unknown look the same
    a, b = call(root, good, "open_case", {"title": "t", "exception_type": "x"}), call(root, good, "no_such_tool")
    assert a["isError"] and a["content"] == b["content"] == [{"type": "text", "text": server.NOT_AVAILABLE}]
    # a project the person cannot see; a wrong argument
    r = call(root, good, "query_figure", {"project": "nope", "table": "t"})
    assert r["isError"] and "project" in r["content"][0]["text"]
    assert call(root, good, "get_intent", {"bogus": 1})["isError"]
    # the person's own role and a disabled account decide, not the token
    full = issue(plane, part, tokens.SCOPES)
    assert call(root, full, "propose_pipeline_change", {"project": "p", "name": "gold_x"})["isError"]
    store = AccountStore(root)
    store._write([{**a, "disabled": True} if a["account_id"] == part["account_id"] else a for a in store._read()])
    assert server.handle(root, full, {"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401


def test_no_raw_rows_and_small_groups(world, monkeypatch):
    root, plane, admin, _ = world
    reg = ToolRegistry(__import__("sh_platform.build.agents.runtime", fromlist=["OpenGate"]).OpenGate())
    answers = iter([{"rows": [{"a": 1}, {"a": 2}]}, {"total": 1200, "group_size": 3}, {"total": 1200, "group_size": 6}, [3, 4, 5]])
    reg.register("m1_intent", "get_intent", lambda intent_id: next(answers), read_only=True, description="d", parameters={"intent_id": "string"})
    monkeypatch.setattr(server, "_reg", lambda c, key, args: (reg, "m1_intent"))
    t = issue(plane, admin)
    r = call(root, t, "get_intent")
    assert r["isError"] and "1" not in r["content"][0]["text"].replace("raw rows", "")
    assert json.loads(call(root, t, "get_intent")["content"][0]["text"]) == {"available": False}   # group of three
    assert json.loads(call(root, t, "get_intent")["content"][0]["text"]) == {"total": 1200, "group_size": 6}
    assert json.loads(call(root, t, "get_intent")["content"][0]["text"]) == {"available": False}   # a bare list of numbers


def test_token_revoke_expiry_and_storage(world):
    root, plane, admin, part = world
    rec = tokens.issue(plane, admin["account_id"], "Claude desktop", ["read"])
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert server.handle(root, rec["token"], ping)[0] == 200
    secret = rec["token"].rsplit(".", 1)[1]
    assert secret not in (plane.area("context") / "mcp_tokens.json").read_text()   # stored hashed
    assert "token" not in tokens.listing(plane, admin["account_id"])[0]
    assert not tokens.revoke(plane, rec["id"], part["account_id"])                  # not someone else's
    assert server.handle(root, rec["token"], ping)[0] == 200
    assert tokens.revoke(plane, rec["id"], admin["account_id"])
    assert server.handle(root, rec["token"], ping)[0] == 401
    short = tokens.issue(plane, admin["account_id"], "short", ["read"], 1)
    rows = json.loads((plane.area("context") / "mcp_tokens.json").read_text())
    next(r for r in rows if r["id"] == short["id"])["expires"] = "2020-01-01T00:00:00+00:00"
    (plane.area("context") / "mcp_tokens.json").write_text(json.dumps(rows))
    assert server.handle(root, short["token"], ping)[0] == 401
    with pytest.raises(tokens.TokenError):
        tokens.issue(plane, admin["account_id"], "x", ["delete"])
    assert tokens.revoke(plane, short["id"], part["account_id"], admin=True) is True  # a company admin may revoke any


def test_proposals_are_drafts_names_are_tokens_and_the_call_is_logged(world):
    root, plane, admin, _ = world
    from sh_platform.egress.vault import NameVault
    NameVault(plane).register("person", "Mei Lindqvist")
    t = issue(plane, admin, ("read", "propose"))
    r = call(root, t, "open_case", {"title": "Check the cash break for Mei Lindqvist", "exception_type": "cash_break", "description": "x"})
    assert not r["isError"], r
    body = json.loads(r["content"][0]["text"])
    assert body["status"] == "draft" and "Mei Lindqvist" not in r["content"][0]["text"]
    drafts = json.loads((plane.area("context") / "mcp_drafts.json").read_text())
    assert [d["status"] for d in drafts] == ["draft"] and drafts[0]["account_id"] == admin["account_id"]
    assert call(root, t, "open_ticket", {"title": "t", "stage": "nowhere"})["isError"]
    log = [json.loads(x) for x in (plane.area("context") / "run_registry.jsonl").read_text().splitlines()]
    assert [(x["agent"], x["status"], x["tools_called"]) for x in log] == [("mcp", "done", ["open_case"]), ("mcp", "refused", ["open_ticket"])]
    assert "Lindqvist" not in json.dumps(log) and "cash break" not in json.dumps(log)


def test_http_routes_default_deny_and_bearer(tmp_path):
    import yaml
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sh_platform.auth import install_auth
    from sh_platform.auth.permissions import DEFAULT_PATH
    from sh_platform.mcp.routes import router
    from sh_platform.settings import Settings

    data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    data["routes"].update(yaml.safe_load((__import__("pathlib").Path(server.__file__).parent / "mcp.permissions.yaml").read_text())["routes"])
    perms = tmp_path / "perms.yaml"
    perms.write_text(yaml.safe_dump(data), encoding="utf-8")
    s = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret="fake-test-secret-not-real")
    PlaneStore(s.data_root).create("acme").ensure()
    AccountStore(s.data_root).create("a@example.test", "pw-test-1", "Ada", "acme", ["company_admin"])
    app = FastAPI()
    install_auth(app, s, route_permissions=perms)
    app.include_router(router)
    c = TestClient(app)
    assert c.get("/api/v1/mcp/tokens").status_code == 401                       # signed-out: refused
    assert c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 401
    assert c.get("/mcp").status_code == 405
    assert c.post("/api/auth/login", json={"email": "a@example.test", "password": "pw-test-1"}).status_code == 200
    csrf = {"x-csrf-token": c.cookies.get("sh_csrf")}
    assert c.post("/api/v1/mcp/tokens", json={"label": "x"}).status_code == 403  # no csrf
    made = c.post("/api/v1/mcp/tokens", json={"label": "Claude", "scopes": ["read"]}, headers=csrf).json()
    bearer = {"authorization": "Bearer " + made["token"]}
    anon = TestClient(app)                                                       # no cookie: the token alone
    r = anon.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=bearer)
    assert r.status_code == 200 and any(t["name"] == "describe_table" for t in r.json()["result"]["tools"])
    assert anon.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=bearer).status_code == 202
    assert c.delete(f"/api/v1/mcp/tokens/{made['id']}", headers=csrf).status_code == 200
    assert anon.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers=bearer).status_code == 401
