"""P4: Nira's drafted messages. A tiny app carries the router with a stand-in for the sign-in layer; nothing touches the network."""
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.pulse import messages, templates

ACCOUNTS = {"a-org": {"account_id": "a-org", "display_name": "Mei Tan", "email": "mei@example.test"},
            "a-pt": {"account_id": "a-pt", "display_name": "Wei Chen", "email": "wei@example.test"}}


class Store:
    def get(self, i): return ACCOUNTS.get(i)
    def in_company(self, c): return list(ACCOUNTS.values())


@pytest.fixture
def setup(tmp_path):
    plane = PlaneStore(tmp_path).create("acme").ensure()
    app = FastAPI()
    app.state.settings = type("S", (), {"data_root": tmp_path})()
    app.state.account_store, app.state.sent = Store(), []
    app.state.email_sender = lambda p, to, s, b: app.state.sent.append((to, s, b))

    @app.middleware("http")
    async def who(request, call_next):
        request.state.company_id, request.state.account_id = "acme", request.headers["x-acct"]
        request.state.roles = request.headers.get("x-roles", "").split(",")
        return await call_next(request)
    app.include_router(messages.router)
    return plane, TestClient(app), app


REC = {"purpose": "Reporting pain points", "organiser": "Mei Tan", "closes": "on Friday", "link": "https://x.test/join", "from_record": "sessions/s1",
       "to": [{"name": "Wei Chen", "account_id": "a-pt"}], "organiser_account_id": "a-org", "sponsor": "Dan", "ask": "Get the file chased",
       "source": "Custody feed", "owner": "Wei Chen",
       "runs": [{"source": "Custody feed", "status": "late", "rows": 4812}, {"source": "Fees", "status": "ok", "rows": 300}]}


def test_each_kind_is_written_from_records_without_figures():
    for kind in templates.KINDS:
        text = templates.WRITERS[kind](REC)
        assert text["subject"] and text["body"]
        assert not re.search(r"4812|300|\d+%", text["body"]), kind
    assert "https://x.test/join" in templates.invite(REC)["body"] and "Custody feed" in templates.ops_report(REC)["body"]


def test_draft_is_idempotent(setup):
    plane, _, _ = setup
    a, b = messages.draft(plane, "invite", REC), messages.draft(plane, "invite", REC)
    messages.draft(plane, "reminder", REC)
    assert a["id"] == b["id"] and len(messages._all(plane)) == 2


def test_send_records_who_and_when_and_refuses_a_second(setup):
    plane, c, app = setup
    mid = messages.draft(plane, "invite", REC)["id"]
    h = {"x-acct": "a-org", "x-roles": "sponsor"}
    assert [m["id"] for m in c.get("/api/pulse/messages", headers=h).json()["messages"]] == [mid]
    r = c.post(f"/api/pulse/messages/{mid}/send", headers=h)
    assert r.status_code == 200 and r.json()["sent_by"] == "Mei Tan"
    saved = messages._all(plane)[0]
    assert saved["state"] == "sent" and saved["sent_by"] == "Mei Tan" and saved["sent_at"]
    assert c.post(f"/api/pulse/messages/{mid}/send", headers=h).status_code == 409
    assert len(app.state.sent) == 1 and app.state.sent[0][0] == ["wei@example.test"]


def test_a_participant_cannot_send(setup):
    plane, c, app = setup
    mid = messages.draft(plane, "invite", REC)["id"]
    h = {"x-acct": "a-pt", "x-roles": "participant"}
    assert c.post(f"/api/pulse/messages/{mid}/send", headers=h).status_code == 403
    assert c.get("/api/pulse/messages", headers=h).json() == {"messages": []}
    assert app.state.sent == [] and messages._all(plane)[0]["state"] == "draft"
