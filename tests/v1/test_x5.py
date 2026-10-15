"""X5 document extraction. A stubbed model confirms a spec in North's conversation and points at lines by letter alias (the program
copies the values); a document in a changed layout goes to review; a second one makes North draft a revised spec, which on yes bumps
the version and clears the queue. With the model off: rules propose a spec, a correction becomes a worked example and drives the
revision; the analyst may not confirm a spec."""
import base64
import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.agents.protocols import ModelReply
from sh_platform.app import create_app
from sh_platform.egress.rows import json_findings
from sh_platform.settings import Settings
from tests.v1.team import on_team
from sh_platform.v1 import x5_extract as X
from sh_platform.v1.skill_loader import load_skill, skill_label

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "data" / "_control" / "seed_credentials.txt"
ARJUN, LEELA = "arjun.mehta.neera@example.test", "leela.raman.neera@example.test"
pytestmark = pytest.mark.skipif(not CREDS.is_file(), reason="no seeded demo data")

A = """# Custodian statement, July 2026
Statement date: 31 July 2026. Prepared for Meredith Shaw.

| Item | Amount |
|---|---|
| Securities | SGD 1,200,000 |
| Cash | SGD 300,000 |
| Total valuation | SGD 1,500,000 |
"""


def layout_b(month: str, day: int, sec: str, cash: str, total: str) -> str:
    return (f"# Custodian statement, {month} 2026\nStatement date: {day} {month} 2026. Prepared for Meredith Shaw.\n\n"
            f"| Item | Amount |\n|---|---|\n| Securities | SGD {sec} |\n| Cash | SGD {cash} |\n| Portfolio value | SGD {total} |\n")


B1 = layout_b("August", 31, "1,250,000", "310,000", "1,560,000")
B2 = layout_b("September", 30, "1,270,000", "290,000", "1,560,000")
LABELS = {"statement date": "Statement date", "securities": "Securities", "cash": "Cash", "total": "Total valuation"}
FIELDS = [{"name": "statement date", "format": "date", "where_usually": "Statement date", "required": True},
          {"name": "securities", "format": "number", "where_usually": "Securities"},
          {"name": "cash", "format": "number", "where_usually": "Cash"},
          {"name": "total", "meaning": "closing value", "format": "number", "where_usually": "Total valuation", "required": True}]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("x5") / "data"
    shutil.copytree(ROOT / "data", data)
    a = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    a.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    yield a
    mp.undo()


def client(app, email):
    pw = {l.split()[0]: l.split()[1] for l in CREDS.read_text().splitlines() if l.strip() and not l.startswith("#")}
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def doc(name: str, text: str) -> dict:
    return {"name": name, "data": base64.b64encode(text.encode()).decode(), "kind": "document"}


class Stub:
    """North's chat answers with a confirmed spec; extraction calls get line aliases found in the quoted passage."""

    def __init__(self, chat: dict):
        self.chat, self.x5_seen = chat, []

    def complete(self, module_id, messages, tools=None):
        body = json.loads(messages[-1]["content"])
        if not messages[0]["content"].startswith(X.SYSTEM):
            return ModelReply(text=json.dumps(self.chat))
        self.x5_seen.append(messages)
        lines = dict(re.findall(r"^([A-Z]{1,3})\) (.*)$", body["context"]["document"], re.M))
        find = lambda label: next((a for a, t in lines.items() if label.lower() in t.lower()), None)  # noqa: E731
        if "sit now" in body["question"]:
            return ModelReply(text=json.dumps({"line": find("Portfolio value"), "label": "Portfolio value"}))
        return ModelReply(text=json.dumps({f: {"line": find(lb), "label": lb} if find(lb) else None for f, lb in LABELS.items()}))


def test_skill_loader():
    s = load_skill("north")
    assert s.startswith("# North, the intent agent") and len(s) <= 6000 and "Traps" in s
    assert skill_label("north") == "North, the intent agent" and load_skill("../etc") == "" and load_skill("nobody") == ""


def test_spec_from_chat_review_and_layout_change(app):
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    stub = Stub({"reply": "These statements look alike: statement date, securities, cash and the total. I will take those out.",
                 "sow_patch": {}, "process_steps": None, "covered": ["goal", "documents", "extraction"], "ready": False,
                 "extraction": {"types": [{"name": "Custodian statement", "files": ["x5-stmt-2026-07.md", "x5-stmt-2026-08.md"],
                                           "fields": FIELDS, "checks": [{"kind": "ties_to", "field": "total", "detail": "sum of: securities, cash"}],
                                           "confirmed": True}]}})
    app.state.build_model_factory = lambda plane: stub
    try:
        t = arjun.post("/api/v1/intents/chat", json={"text": "Monthly statements into a valuation table",
                                                       "files": [doc("x5-stmt-2026-07.md", A), doc("x5-stmt-2026-08.md", B1)]})
        assert t.status_code == 200, t.text
        iid = t.json()["id"]
        assert "extraction" in t.json()["needs_done"]
        ov = arjun.get(f"/api/v1/intents/{iid}/extract").json()
        st = ov["types"][0]
        assert st["state"] == "confirmed" and st["version"] == 1 and len(st["sample_files"]) == 2
        by_file = {d["file"]: d for d in ov["documents"]}
        assert by_file["documents/x5-stmt-2026-07.md"]["status"] == "ok"
        assert by_file["documents/x5-stmt-2026-08.md"]["status"] == "review"  # the total sits under a new label: never guessed
        on_team(app, iid, "Leela Raman", "data engineer")  # G1: the document is its project's; Internal is the team's alone
        ok = leela.get(f"/api/v1/extract/{by_file['documents/x5-stmt-2026-07.md']['doc_id']}").json()
        assert ok["values"]["total"]["value"] == "1500000" and ok["values"]["total"]["by"] == "model"  # copied by the program
        assert ok["values"]["statement date"]["value"] == "2026-07-31"
        bad = leela.get(f"/api/v1/extract/{by_file['documents/x5-stmt-2026-08.md']['doc_id']}").json()
        assert bad["values"]["total"]["value"] == "" and {"total:present", "total:ties_to"} <= set(bad["failed_first"])
        assert bad["lines"] and st["revision"] is None
        import sh_platform.v1.c4_library as CL
        with pytest.MonkeyPatch.context() as m:  # K1: project read is not the right to the file
            m.setattr(CL, "readable", lambda item, viewer: False)
            m.setattr(CL, "_index", lambda plane: [{"id": "lib_x", "name": "stmt", "path": "documents/x5-stmt-2026-08.md", "visibility": "company"}])
            lk = leela.get(f"/api/v1/extract/{by_file['documents/x5-stmt-2026-08.md']['doc_id']}").json()
            assert lk["lines"] == [] and lk["locked"] and "Portfolio" not in str(lk)
        q = leela.get("/api/v1/extract/queue").json()
        assert any(i["intent_id"] == iid for i in q["items"]) and q["line"] == X.queue_line(q["count"])

        # a second document in the new layout: North drafts a revised spec, before and after on both
        t2 = arjun.post(f"/api/v1/intents/{iid}/chat", json={"text": "September's statement.", "files": [doc("x5-stmt-2026-09.md", B2)]})
        assert t2.status_code == 200, t2.text
        rev = arjun.get(f"/api/v1/intents/{iid}/extract").json()["types"][0]["revision"]
        assert rev and rev["field"] == "total" and "Portfolio value" in next(f for f in rev["fields"] if f["name"] == "total")["where_usually"]
        assert [(x["before"], x["after"]) for x in rev["before_after"]] == [("", "1560000"), ("", "1560000")]
        assert leela.post(f"/api/v1/intents/{iid}/extract/types/{st['id']}/revision", json={"accept": True}).status_code == 403
        st2 = arjun.post(f"/api/v1/intents/{iid}/extract/types/{st['id']}/revision", json={"accept": True}).json()
    finally:
        del app.state.build_model_factory
    assert st2["version"] == 2 and st2["previous"][0]["version"] == 1 and st2["revision"] is None
    docs = arjun.get(f"/api/v1/intents/{iid}/extract").json()["documents"]
    assert all(d["status"] == "ok" for d in docs) and {d["version"] for d in docs} == {1, 2}  # the old version kept for the older one

    assert stub.x5_seen
    for messages in stub.x5_seen:  # passages only, names masked, no record lists, no over-long strings
        for m in messages:
            assert json_findings(m["content"]) == (None, []), m["content"][:300]
            assert "Meredith Shaw" not in m["content"]
        body = json.loads(messages[-1]["content"])
        assert "BEGIN QUOTED DOCUMENT TEXT" in body["context"]["document"]


def test_rules_spec_correction_and_refusal(app):
    arjun, leela = client(app, ARJUN), client(app, LEELA)
    iid = arjun.post("/api/v1/intents/chat", json={"text": "Statement values by rules",
                                                    "files": [doc("x5r-stmt-2026-07.md", A)]}).json()["id"]
    on_team(app, iid, "Leela Raman")  # G1: Internal is the team's alone
    t = arjun.post(f"/api/v1/intents/{iid}/extract/propose", json={"file": "x5r-stmt-2026-07.md"}).json()
    assert t["state"] == "proposed" and {"statement date", "securities", "cash", "total valuation"} <= {f["name"] for f in t["fields"]}
    put = {"confirm": True, "checks": [{"kind": "ties_to", "field": "total valuation", "detail": "sum of: securities, cash"}]}
    assert leela.put(f"/api/v1/intents/{iid}/extract/types/{t['id']}", json=put).status_code == 403  # the analyst may not confirm
    ov = arjun.put(f"/api/v1/intents/{iid}/extract/types/{t['id']}", json=put).json()
    assert [d["status"] for d in ov["documents"]] == ["ok"]

    for name, text in (("x5r-stmt-2026-08.md", B1), ("x5r-stmt-2026-09.md", B2)):
        arjun.post(f"/api/v1/intents/{iid}/chat/files", json=doc(name, text))
    r1 = leela.post(f"/api/v1/intents/{iid}/extract/run", json={"files": ["x5r-stmt-2026-08.md"]}).json()["extractions"][0]
    assert r1["status"] == "review"
    assert leela.post(f"/api/v1/extract/{r1['doc_id']}/accept", json={"values": {"total valuation": "SGD x"}}).status_code == 422
    got = leela.post(f"/api/v1/extract/{r1['doc_id']}/accept", json={"values": {"total valuation": "1,560,000"}}).json()
    assert got["extraction"]["status"] == "ok" and got["extraction"]["values"]["total valuation"]["by"] == "person"
    assert got["revision"] is None  # one document is not a layout change yet
    r2 = leela.post(f"/api/v1/intents/{iid}/extract/run", json={"files": ["x5r-stmt-2026-09.md"]}).json()["extractions"][0]
    assert r2["status"] == "review"
    assert leela.post(f"/api/v1/extract/{r2['doc_id']}/accept", json={}).json()["extraction"]["status"] == "review"  # still failing: stays queued
    spec = arjun.get(f"/api/v1/intents/{iid}/extract").json()["types"][0]
    assert spec["examples"] == [{"file": "documents/x5r-stmt-2026-08.md", "field": "total valuation", "value": "1560000"}]
    assert "Portfolio value" in spec["revision"]["why"]  # found from the person's correction
    arjun.post(f"/api/v1/intents/{iid}/extract/types/{t['id']}/revision", json={"accept": True})
    docs = arjun.get(f"/api/v1/intents/{iid}/extract").json()
    assert docs["queue"] == {"count": 0, "line": "Nothing needs a look"}
