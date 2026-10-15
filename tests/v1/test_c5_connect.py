"""C5 connectors: spec rules, egress gate, IMAP / SFTP / Graph with stub clients (no network), idempotent landing, health, routes."""
import importlib.util
import json
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.egress.policy import EgressPolicy
from sh_platform.plane import PlaneStore
from sh_platform.v1 import c5_routes as R
from sh_platform.v1 import e0c_landing as L
from sh_platform.v1 import wh
from sh_platform.v1.c5_connect import ops
from sh_platform.v1.c5_connect import spec as S

SECRET = "s3cret-value-xyz"
CSV1, CSV2 = b"fund,nav\nA,10\n", b"fund,nav\nB,20\n"


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    for k in ("CONN_MAIL_USER", "CONN_MAIL_PASS", "CONN_SFTP_USER", "CONN_SFTP_PASS", "CONN_MS_TENANT", "CONN_MS_ID", "CONN_MS_SECRET"):
        monkeypatch.setenv(k, SECRET)
    return p


def allow(plane, *hosts):
    pol = EgressPolicy(plane)
    pol.set_internet("c5_connect", True)
    pol.set_internet_hosts(hosts)


def log_lines(plane):
    return [json.loads(x) for x in (plane.area("context") / "egress_log.jsonl").read_text().splitlines()] if (plane.area("context") / "egress_log.jsonl").exists() else []


IMAP_SPEC = {"kind": "imap", "host": "mail.example.test", "schedule": "daily", "source_code": "custodian",
             "credentials": {"user": "CONN_MAIL_USER", "password": "CONN_MAIL_PASS"}}


def mail(*atts, body="hello"):
    m = EmailMessage()
    m["From"], m["Subject"] = "ops@example.test", "Statement"
    m.set_content(body)
    for name, data in atts:
        m.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return m.as_bytes()


class FakeImap:
    instances: list = []

    def __init__(self, msgs):
        self.msgs, self.readonly, self.logged_in, self.out = msgs, None, None, False
        FakeImap.instances.append(self)

    def login(self, u, p):
        self.logged_in = (u, p)
        if p != SECRET:
            raise RuntimeError("AUTH failed " + p)

    def select(self, box, readonly=False):
        self.readonly = readonly
        return "OK", [b"1"]

    def uid(self, cmd, *a):
        if cmd == "SEARCH":
            n = int(a[1].split()[1].split(":")[0])
            ids = [u for u in self.msgs if u >= n] or [max(self.msgs)]  # a real server returns the last message for n:*
            return "OK", [b" ".join(str(i).encode() for i in ids)]
        return "OK", [(b"x", self.msgs[int(a[0])]), b")"]

    def logout(self):
        self.out = True


def imap_factory(msgs):
    return lambda host, port: (_ for _ in ()).throw(AssertionError(port)) if port != 993 else FakeImap(msgs)


def test_spec_holds_names_not_secrets(plane):
    with pytest.raises(L.Refused):
        S.save(plane, "m1", {**IMAP_SPEC, "credentials": {"user": "me@x.com", "password": "hunter2!"}})
    with pytest.raises(L.Refused):
        S.save(plane, "m1", {**IMAP_SPEC, "credentials": {"user": "CONN_MAIL_USER"}})
    with pytest.raises(L.Refused):
        S.save(plane, "m1", {**IMAP_SPEC, "host": "http://evil.test/x"})
    s = S.save(plane, "m1", IMAP_SPEC)
    assert s["params"]["mailbox"] == "INBOX" and s["credentials"]["password"] == "CONN_MAIL_PASS"
    assert S.get(plane, "m1")["kind"] == "imap"
    assert SECRET not in (plane.path("connectors", "specs.json")).read_text()


def test_egress_default_deny_and_log(plane):
    spec = S.save(plane, "m1", IMAP_SPEC)
    F = {"imap": imap_factory({1: mail(("a.csv", CSV1))})}
    r = ops.test(plane, spec, F)
    assert not r["ok"] and r["code"] == "internet_off"
    EgressPolicy(plane).set_internet("c5_connect", True)
    assert ops.test(plane, spec, F)["code"] == "destination_not_allowed"
    assert [x["decision"] for x in log_lines(plane)] == ["blocked", "blocked"] and L._all(plane) == []
    allow(plane, "mail.example.test")
    assert ops.test(plane, spec, F)["ok"]
    last = log_lines(plane)[-1]
    assert last["module"] == "c5_connect" and last["kind"] == "imap" and last["host"] == "mail.example.test" and last["decision"] == "sent"
    assert SECRET not in json.dumps(log_lines(plane))


def test_imap_attachments_only_read_only_and_idempotent(plane):
    allow(plane, "mail.example.test")
    spec = S.save(plane, "m1", IMAP_SPEC)
    msgs = {1: mail(("a.csv", CSV1), ("notes.txt", b"x")), 2: mail(body="no attachment")}
    F = {"imap": imap_factory(msgs)}
    dry = ops.dry_run(plane, spec, F)
    assert [i["name"] for i in dry["would_arrive"]] == ["a.csv"] and L._all(plane) == []  # nothing lands in a dry run
    assert FakeImap.instances[-1].readonly is True and FakeImap.instances[-1].out is True
    res = ops.fetch(plane, spec, F)
    assert res["status"] == "ok" and res["landed"] == 1
    rec = L._all(plane)[0]
    assert rec["source_code"] == "custodian" and rec["state"] == "new" and rec["sender"] == "connector:m1"
    assert L.original_path(plane, rec).read_bytes() == CSV1
    again = ops.fetch(plane, spec, F)
    assert again["landed"] == 0 and again["seen"] == 0  # checkpoint moved on
    msgs[3] = mail(("copy_of_a.csv", CSV1), ("b.csv", CSV2))  # same bytes under another name, plus a new file
    third = ops.fetch(plane, spec, F)
    assert third["landed"] == 1 and third["duplicates"] == 1 and len(L._all(plane)) == 2


def test_failures_are_reported_without_secrets(plane, monkeypatch):
    allow(plane, "mail.example.test")
    spec = S.save(plane, "m1", IMAP_SPEC)
    monkeypatch.setenv("CONN_MAIL_PASS", "wrong-password-999")
    r = ops.fetch(plane, spec, {"imap": imap_factory({1: mail(("a.csv", CSV1))})})
    assert r["status"] == "failed" and r["error"]["code"] == "login_failed" and "wrong-password-999" not in json.dumps(r)
    monkeypatch.delenv("CONN_MAIL_USER")
    r = ops.test(plane, spec, {"imap": imap_factory({})})
    assert r["code"] == "missing_credential" and "CONN_MAIL_USER" in r["message"]
    h = ops.health(plane)[0]
    assert h["failed"] and h["status"] == "failed" and h["last_ok"] is None


class Attr(SimpleNamespace):
    pass


class FakeSftp:
    def __init__(self, files):
        self.files, self.closed = files, False

    def listdir_attr(self, p):
        assert p == "/out"
        return [Attr(filename=n, st_size=len(d), st_mtime=100, st_mode=0o100644) for n, d in self.files.items()] + \
               [Attr(filename="sub", st_size=0, st_mtime=1, st_mode=0o040755)]

    def read(self, p):
        return self.files[p.rsplit("/", 1)[1]]

    def close(self):
        self.closed = True


SFTP_SPEC = {"kind": "sftp", "host": "sftp.example.test", "schedule": "hourly", "source_code": "admin",
             "credentials": {"user": "CONN_SFTP_USER", "password": "CONN_SFTP_PASS"}, "params": {"remote_path": "/out/"}}


def test_sftp_pull_idempotent(plane):
    allow(plane, "sftp.example.test")
    spec = S.save(plane, "s1", SFTP_SPEC)
    files = {"nav.csv": CSV1, "readme.pdf": b"%PDF"}
    seen_args = []
    F = {"sftp": lambda h, port, u, p, k: seen_args.append((h, port, k)) or FakeSftp(files)}
    assert ops.fetch(plane, spec, F)["landed"] == 1
    assert seen_args == [("sftp.example.test", 22, None)]
    assert ops.fetch(plane, spec, F)["landed"] == 0
    files["nav.csv"] = CSV2  # same name, new bytes: lands as a second file
    assert ops.fetch(plane, spec, {"sftp": lambda *a: FakeSftp({"nav.csv": CSV2})})["landed"] == 0  # same size and time: not seen as changed
    files2 = {"nav2.csv": CSV2}
    assert ops.fetch(plane, spec, {"sftp": lambda *a: FakeSftp(files2)})["landed"] == 1
    assert len(L._all(plane)) == 2


@pytest.mark.skipif(importlib.util.find_spec("paramiko") is not None, reason="paramiko installed")
def test_sftp_without_paramiko_reports(plane):
    allow(plane, "sftp.example.test")
    r = ops.test(plane, S.save(plane, "s1", SFTP_SPEC))
    assert not r["ok"] and r["code"] == "unavailable" and "paramiko" in r["message"]


GRAPH_SPEC = {"kind": "graph", "schedule": "daily", "source_code": "sharepoint", "credentials":
              {"tenant": "CONN_MS_TENANT", "client_id": "CONN_MS_ID", "client_secret": "CONN_MS_SECRET"}, "params": {"drive_id": "d1", "folder": "Statements"}}


def graph_http(calls):
    def http(method, url, headers, data=None):
        calls.append((method, url, headers.get("Authorization")))
        if "oauth2" in url:
            assert SECRET in data.decode()  # the secret goes to Microsoft only, in the body
            return 200, json.dumps({"access_token": "tok"}).encode()
        if "download.example.test" in url:
            assert "Authorization" not in headers
            return 200, CSV1
        assert headers["Authorization"] == "Bearer tok"
        return 200, json.dumps({"value": [
            {"id": "i1", "eTag": "e1", "name": "jan.csv", "size": 3, "file": {}, "@microsoft.graph.downloadUrl": "https://download.example.test/x?sig=1"},
            {"id": "i2", "name": "folder", "folder": {}}, {"id": "i3", "eTag": "e", "name": "x.zip", "file": {}}]}).encode()
    return http


def test_graph_download_host_must_be_allowed_too(plane):
    spec = S.save(plane, "g1", GRAPH_SPEC)
    calls = []
    F = {"http": graph_http(calls)}
    allow(plane, "graph.microsoft.com", "login.microsoftonline.com")
    r = ops.fetch(plane, spec, F)
    assert r["status"] == "failed" and r["error"]["code"] == "destination_not_allowed" and L._all(plane) == []
    allow(plane, "graph.microsoft.com", "login.microsoftonline.com", "download.example.test")
    assert ops.test(plane, spec, F)["ok"]
    assert ops.fetch(plane, spec, F)["landed"] == 1
    assert ops.fetch(plane, spec, F)["landed"] == 0
    assert L._all(plane)[0]["name"] == "jan.csv" and L._all(plane)[0]["source_code"] == "sharepoint"
    assert {x["host"] for x in log_lines(plane) if x["decision"] == "sent"} == {"graph.microsoft.com", "login.microsoftonline.com", "download.example.test"}
    assert SECRET not in json.dumps(log_lines(plane)) and "sig=1" not in json.dumps(log_lines(plane))


def test_health_late_failed_and_map_feed(plane):
    allow(plane, "mail.example.test")
    spec = S.save(plane, "m1", IMAP_SPEC)
    S.save(plane, "man", {**IMAP_SPEC, "schedule": "manual", "source_code": "other"})
    assert ops.fetch(plane, spec, {"imap": imap_factory({1: mail(("a.csv", CSV1))})})["status"] == "ok"
    h = {x["id"]: x for x in ops.health(plane)}
    assert h["m1"]["files_landed"] == 1 and not h["m1"]["late"] and h["m1"]["last_ok"] and h["man"]["status"] == "never"
    later = wh.now() + timedelta(days=2)
    h = {x["id"]: x for x in ops.health(plane, later)}
    assert h["m1"]["late"] and not h["man"]["late"]  # manual is never late
    assert ops.map_feed(plane)["custodian"]["connector"] == "m1" and "other" in ops.map_feed(plane)
    assert ops.run_due(plane, {"imap": imap_factory({1: mail(("a.csv", CSV1))})}) == []  # just ran: not due


@pytest.fixture()
def api(plane, monkeypatch):
    allow(plane, "mail.example.test")
    app = FastAPI()
    app.include_router(R.router)
    role = {"v": "analyst"}

    def seat(request, s):
        if role["v"] == "consumer":
            from fastapi import HTTPException
            raise HTTPException(403, {"error": "not_allowed", "message": "no"})
    monkeypatch.setattr(R, "require_seat", seat)
    monkeypatch.setattr(R, "_plane", lambda request: plane)
    R.CLIENTS.clear()
    R.CLIENTS["imap"] = imap_factory({1: mail(("a.csv", CSV1))})
    yield TestClient(app), role
    R.CLIENTS.clear()


def test_routes_and_permissions(api, plane):
    c, role = api
    assert c.put("/api/v1/connectors/m1", json={**IMAP_SPEC, "credentials": {"user": "x@y.z", "password": "CONN_MAIL_PASS"}}).status_code == 400
    assert c.put("/api/v1/connectors/m1", json=IMAP_SPEC).status_code == 200
    assert c.post("/api/v1/connectors/m1/test").json()["ok"] is True
    assert c.post("/api/v1/connectors/m1/dry-run").json()["would_arrive"][0]["name"] == "a.csv"
    assert c.post("/api/v1/connectors/m1/fetch").json()["landed"] == 1
    got = c.get("/api/v1/connectors").json()
    assert got["connectors"][0]["health"]["files_landed"] == 1 and "CONN_MAIL_PASS" in json.dumps(got) and SECRET not in json.dumps(got)
    assert c.post("/api/v1/connectors/nope/fetch").status_code == 404
    role["v"] = "consumer"
    assert c.get("/api/v1/connectors").status_code == 403 and c.delete("/api/v1/connectors/m1").status_code == 403
    role["v"] = "analyst"
    assert c.delete("/api/v1/connectors/m1").json() == {"deleted": "m1"}


def test_every_route_is_declared_default_deny():
    decl = yaml.safe_load((Path(R.__file__).parent / "c5.permissions.yaml").read_text())["routes"]
    mine = {f"{m} {r.path}" for r in R.router.routes for m in r.methods}
    assert mine == set(decl)
    assert all(set(v["roles"]) == {"company_admin", "analyst"} for v in decl.values())


def test_platform_secrets_and_control_chars_refused(plane):
    for bad in ({"user": "SH_JEV_API_KEY", "password": "CONN_MAIL_PASS"}, {"user": "CONN_MAIL_USER", "password": "SH_MCP_TOKEN"}):
        with pytest.raises(L.Refused):
            S.save(plane, "m1", {**IMAP_SPEC, "credentials": bad})
    with pytest.raises(L.Refused):
        S.save(plane, "m1", {**IMAP_SPEC, "params": {"mailbox": "INBOX\r\nA1 DELETE INBOX"}})
