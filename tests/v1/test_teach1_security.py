"""TEACH1 security review (TSEC): the middleware hands a big body on whole, a scope never crosses requests, and company / agent / path isolation of the
knowledge routes. No model; synthetic text only."""
import asyncio
import base64
import json

from fastapi.testclient import TestClient
from starlette.concurrency import run_in_threadpool

from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import teach as T


def _chunks(body: bytes, n: int = 65536):
    parts = [body[i:i + n] for i in range(0, len(body), n)]
    return [{"type": "http.request", "body": c, "more_body": i < len(parts) - 1} for i, c in enumerate(parts)]


def test_a_chat_body_over_the_scan_limit_reaches_the_route_whole():
    got = {}

    async def down(scope, receive, send):
        raw, more = b"", True
        while more:
            m = await receive()
            raw += m.get("body", b"")
            more = m.get("more_body", False)
        got["raw"] = raw
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    body = json.dumps({"text": "hi", "files": "x" * 700_000}).encode()
    queue = _chunks(body)

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(_m):
        pass
    asyncio.run(T.TeachMiddleware(down)({"type": "http", "method": "POST", "path": "/api/v1/consume/chat", "headers": []}, receive, send))
    assert got["raw"] == body and json.loads(got["raw"])["text"] == "hi"


def test_two_requests_at_once_each_see_only_their_own_scope():
    seen = {}

    def mw(agent, question, delay):
        async def down(scope, receive, send):
            await receive()
            await asyncio.sleep(delay)
            s = await run_in_threadpool(T._scope.get)  # what run_agent (in a worker thread) would see
            seen[question] = (s.agent, s.question)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})
        return T.TeachMiddleware(down)

    async def one(path, question, delay):
        body = json.dumps({"text": question}).encode()
        q = _chunks(body)

        async def receive():
            return q.pop(0) if q else {"type": "http.disconnect"}

        async def send(_m):
            pass
        await mw(None, question, delay)({"type": "http", "method": "POST", "path": path, "headers": []}, receive, send)

    async def both():
        await asyncio.gather(one("/api/v1/consume/chat", "alpha", 0.05), one("/api/v1/cases/c1/ask", "beta", 0.01))
    asyncio.run(both())
    assert seen == {"alpha": ("lumen", "alpha"), "beta": ("tally", "beta")} and T._scope.get() is None


def test_company_agent_and_path_isolation_of_the_routes(tmp_path):
    from sh_platform.app import create_app
    from sh_platform.auth.accounts import AccountStore
    data = tmp_path / "rdata"
    ps = PlaneStore(data)
    ps.create("acme")
    ps.create("other")
    store = AccountStore(data)
    pw = "Test-pass-1234567890"  # a throwaway password for a throwaway account in a temp folder
    store.create("leo@example.test", pw, "Leo", "acme", ["analyst"])
    store.create("ivy@example.test", pw, "Ivy", "other", ["analyst", "company_admin"])
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}

    def client(n):
        c = TestClient(app)
        assert c.post("/api/auth/login", json={"email": f"{n}@example.test", "password": pw}).status_code == 200
        c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
        return c
    leo, ivy = client("leo"), client("ivy")
    evil = base64.b64encode(b"Month end checks are matched to the ledger every day.").decode()
    made = leo.post("/api/v1/knowledge/span", json={"title": "Checks", "name": "../../../evil.txt", "data": evil})
    assert made.status_code == 200 and made.json()["name"] == "evil.txt"
    item = made.json()["id"]
    files = [p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file() and "evil" in p.name]
    assert len(files) == 1 and files[0].startswith(f"acme/knowledge/span/{item}__")  # stayed in its own folder
    assert ivy.get("/api/v1/knowledge/span").json()["items"] == []  # another company sees nothing
    assert ivy.post(f"/api/v1/knowledge/span/{item}/active", json={"active": False}).status_code == 404
    assert ivy.put(f"/api/v1/knowledge/span/{item}", json={"text": "x"}).status_code == 404
    assert leo.get("/api/v1/knowledge/..%2f..%2fx").status_code in (403, 404)
    assert leo.get("/api/v1/knowledge/tally").status_code == 403  # not Leo's agent, whatever the id
    assert leo.put(f"/api/v1/knowledge/north/{item}", json={"text": "x"}).status_code == 403
    assert leo.put(f"/api/v1/knowledge/span/..%2f..%2fx", json={"text": "x"}).status_code in (404, 405)
