"""Auth test kit. No industry is involved anywhere in these tests; companies are plain ids."""
import yaml
import pytest
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient

from sh_platform.auth import install_auth
from sh_platform.auth.accounts import AccountStore
from sh_platform.auth.permissions import DEFAULT_PATH
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class Kit:
    def __init__(self, tmp_path, **kw):
        self.clock = Clock()
        self.settings = Settings(mode=kw.pop("mode", "dev"), data_root=str(tmp_path / "data"),
                                 session_secret=kw.pop("secret", SECRET))
        data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
        data["routes"].update({
            "GET /api/t/echo": {"authenticated": True},
            "POST /api/t/write": {"authenticated": True},
            "GET /api/t/approve": {"roles": ["approver"]},
            "GET /page": {"authenticated": True},
            "GET /api/t/public-state": {"public": True},
            "GET /api/t/loop-thread": {"public": True},
            "PUT /api/t/write": {"authenticated": True},
            "PATCH /api/t/write": {"authenticated": True},
            "DELETE /api/t/write": {"authenticated": True},
            "WEBSOCKET /ws/ok": {"authenticated": True},
            "WEBSOCKET /ws/approvers": {"roles": ["approver"]},
        })
        data["routes"].update(kw.pop("extra_routes", {}))
        perms = tmp_path / "perms.yaml"
        perms.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.app = FastAPI()
        install_auth(self.app, self.settings, clock=self.clock, route_permissions=perms, **kw)

        @self.app.get("/api/t/echo")
        def echo(request: Request, company_id: str | None = None):
            return {"company_id": request.state.company_id, "roles": request.state.roles}

        @self.app.post("/api/t/write")
        def write():
            return {"ok": True}

        @self.app.get("/api/t/approve")
        def approve():
            return {"ok": True}

        @self.app.get("/page")
        def page():
            return {"ok": True}

        @self.app.get("/api/t/public-state")
        def public_state(request: Request):
            return {"company_id": getattr(request.state, "company_id", None),
                    "roles": getattr(request.state, "roles", None)}

        @self.app.get("/api/t/loop-thread")
        async def loop_thread():
            import threading
            return {"ident": threading.get_ident()}

        @self.app.put("/api/t/write")
        @self.app.patch("/api/t/write")
        @self.app.delete("/api/t/write")
        def write_other():
            return {"ok": True}

        @self.app.websocket("/ws/ok")
        async def ws_ok(ws: WebSocket):
            await ws.accept()
            await ws.send_text("hi")
            await ws.close()

        @self.app.websocket("/ws/approvers")
        async def ws_approvers(ws: WebSocket):
            await ws.accept()
            await ws.close()

        @self.app.websocket("/ws/undeclared")
        async def ws_undeclared(ws: WebSocket):
            await ws.accept()
            await ws.close()

        @self.app.get("/api/t/undeclared")
        def undeclared():
            return {"ok": True}

        self.store: AccountStore = self.app.state.account_store

    def account(self, name, company_id, roles):
        return make_test_account(self.store, name, company_id, roles)

    def client(self) -> TestClient:
        return TestClient(self.app)

    def login(self, name, company_id="co-a", roles=("participant",)):
        acct, pw = self.account(name, company_id, list(roles))
        c = self.client()
        r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
        assert r.status_code == 200, r.text
        return c, acct, pw


@pytest.fixture
def kit(tmp_path):
    return Kit(tmp_path)


@pytest.fixture
def make_kit(tmp_path):
    return lambda **kw: Kit(tmp_path, **kw)
