"""Entitlement test kit. Companies are plain ids; industries are arbitrary strings (never real wording).

The kit app is the real install_auth + install_modulegate with fixture module routes of every kind
(plain, router, WebSocket, mount, catch-all) under /api/modules/<id>/, for ids that are owned, switched
off, never owned and not in the catalogue.
"""
import asyncio

import yaml
from fastapi import APIRouter, FastAPI, WebSocket
from fastapi.testclient import TestClient

from sh_platform.auth import install_auth
from sh_platform.auth.permissions import DEFAULT_PATH
from sh_platform.auth.test_accounts import make_test_account
from sh_platform.entitlements import EntitlementStore
from sh_platform.modulegate import install_modulegate
from sh_platform.settings import Settings

SECRET = "fake-test-secret-not-real"
MODS = ["m1_intent", "m2_baseline", "m4_build", "m6_ops", "ghost"]  # ghost is not in the catalogue
REFUSED = {"error": "module_not_available", "message": "This module is not part of your plan."}


class Kit:
    def __init__(self, tmp_path):
        self.settings = Settings(mode="dev", data_root=str(tmp_path / "data"), session_secret=SECRET)
        data = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
        for m in MODS:
            p = f"/api/modules/{m}"
            data["routes"].update({
                f"GET {p}/ping": {"authenticated": True},
                f"POST {p}/write": {"authenticated": True},
                f"GET {p}/analyst-only": {"roles": ["analyst"]},
                f"WEBSOCKET {p}/ws": {"authenticated": True},
                f"GET {p}/items/{{n}}": {"authenticated": True},
                f"GET {p}/files/{{path}}": {"authenticated": True},
                f"MOUNT {p}/static/{{path}}": {"authenticated": True},
            })  # note: {p}/undeclared is deliberately NOT declared
        perms = tmp_path / "perms.yaml"
        perms.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.app = FastAPI()
        install_auth(self.app, self.settings, route_permissions=perms)
        install_modulegate(self.app, self.settings)
        for m in MODS:
            self._add_routes(m)
        self.store: EntitlementStore = self.app.state.entitlements
        self.accounts = self.app.state.account_store

    def _add_routes(self, m: str):
        p = f"/api/modules/{m}"
        app = self.app
        app.get(f"{p}/ping")(lambda: {"served": "ping"})
        app.post(f"{p}/write")(lambda: {"served": "write"})
        app.get(f"{p}/analyst-only")(lambda: {"served": "analyst"})
        app.get(f"{p}/undeclared")(lambda: {"served": "undeclared"})
        app.get(f"{p}/files/{{path:path}}")(lambda path: {"served": "files", "path": path})

        @app.websocket(f"{p}/ws")
        async def ws(sock: WebSocket):
            await sock.accept()
            await sock.send_text("served")
            await sock.close()

        r = APIRouter(prefix=p)
        r.add_api_route("/items/{n}", lambda n: {"served": "item", "n": n}, methods=["GET"])
        app.include_router(r)
        sub = FastAPI()
        sub.get("/{rest:path}")(lambda rest: {"served": "mount", "rest": rest})
        app.mount(f"{p}/static", sub)

    def login(self, name, company_id, roles=("participant",)):
        acct, pw = make_test_account(self.accounts, name, company_id, list(roles))
        c = TestClient(self.app)
        r = c.post("/api/auth/login", json={"email": acct["email"], "password": pw})
        assert r.status_code == 200, r.text
        c.headers["x-csrf-token"] = c.cookies["sh_csrf"]
        return c

    def raw_get(self, client: TestClient, path: str):
        """GET sent straight to the ASGI app so the path is NOT normalised by an HTTP client."""
        out = {}

        async def run():
            sent = []
            scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
                     "query_string": b"", "root_path": "", "scheme": "http", "http_version": "1.1",
                     "headers": [(b"cookie", f"sh_session={client.cookies['sh_session']}".encode())],
                     "server": ("t", 80), "client": ("c", 1)}

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(msg):
                sent.append(msg)

            await self.app(scope, receive, send)
            out["status"] = sent[0]["status"]
            out["body"] = b"".join(m.get("body", b"") for m in sent[1:])

        asyncio.run(run())
        return out
