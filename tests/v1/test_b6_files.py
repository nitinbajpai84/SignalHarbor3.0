"""W04: files in the Span chat. A file is stored and ticked for the project's intent (as North's), Span answers from it, a stranger cannot read
it, and the chat route takes the file and the turn."""
import base64

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from sh_platform.v1 import b6_span as S
from sh_platform.v1 import doc_index
from sh_platform.v1 import c4_library as C4
import pytest

from tests.v1 import test_b6 as W
from tests.v1.test_b6 import ENG, READER, world as _world  # noqa: F401 - the same small world, with an intent id of the real shape

IID = "ini-" + "a1" * 16



@pytest.fixture()
def world(monkeypatch, request):
    monkeypatch.setattr(W, "IID", IID)  # test_b6's fixture reads this at call time
    return request.getfixturevalue("_world")


NOTE = b"The administrator sends valuations on the third working day. Late files break the monthly report.\n"


def test_attached_file_is_ticked_and_span_answers_from_it(world):  
    plane, pid = world
    got = S.attach(plane, READER, pid, "arrival_notes.txt", NOTE)
    assert got["name"] == "arrival_notes.txt" and got["kind"] == "document"
    assert [i["name"] for i in C4.selected(plane, IID, READER)] == ["arrival_notes.txt"]
    doc_index.ensure(plane, got["path"])
    out = S.chat(plane, READER, pid, "when does the administrator send valuations?", None, ["arrival_notes.txt"])
    reply = out["turns"][-1]["text"]
    assert "I have read arrival_notes.txt" in reply and "third working day" in reply
    assert "attached: arrival_notes.txt" in out["turns"][-2]["text"]


def test_nobody_else_reads_a_private_upload(world):  
    plane, pid = world
    got = S.attach(plane, READER, pid, "arrival_notes.txt", NOTE)
    doc_index.ensure(plane, got["path"])
    assert S.chat(plane, READER, pid, "what is the weather on Mars?", None, ["arrival_notes.txt"])["turns"][-1]["text"].removeprefix("Rules-only reply: ").startswith("I have read")
    assert C4.selected(plane, IID, ENG) == []  # a private upload stays the uploader's


def test_an_empty_turn_without_files_is_refused(world):  
    plane, pid = world
    try:
        S.chat(plane, ENG, pid, "  ", None, [])
    except S.Refused as e:
        assert e.status == 400
    else:
        raise AssertionError("an empty turn must be refused")


def test_route_takes_the_file(world, monkeypatch):  
    from sh_platform.v1 import b6_routes as R
    plane, pid = world

    async def fake_run(request, fn):
        try:
            return fn(plane, READER)  # the project's owner
        except S.Refused as e:
            return JSONResponse({"message": e.message}, status_code=e.status)
    monkeypatch.setattr(R, "_run", fake_run)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(R.router)
    r = TestClient(app).post(f"/api/v1/build/p/{pid}/chat/files", json={"name": "arrival_notes.txt", "data": base64.b64encode(NOTE).decode()})
    assert r.status_code == 200 and r.json()["name"] == "arrival_notes.txt"
    bad = TestClient(app).post(f"/api/v1/build/p/{pid}/chat/files", json={"name": "x.txt", "data": "***"})
    assert bad.status_code == 400
