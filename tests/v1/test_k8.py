"""Card K7: the SOP from a signed intent of work: steps with who, system, input, output, control and exception; manual steps flagged;
missing control or exception listed as open points (never invented); a draft has no SOP; download is Word when python-docx is
installed, else Markdown."""
import copy
import secrets
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sh_platform.app import create_app
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import PlaneStore
from sh_platform.settings import Settings
from sh_platform.v1 import k8_sop as K
from tests.v1.team import on_team

ROOT = Path(__file__).resolve().parents[2]
IID = "k8test01"
SOW = {
    "id": "sow-k8test01", "intent_id": IID, "title": "Month-end reporting", "state": "signed", "version": 2,
    "goal": {"line": "Issue the monthly report", "why": "The family reads it on the fifth working day", "readers": ["Family"], "decisions": [], "needed_by": "5th working day"},
    "process": {"steps": [
        {"n": 1, "name": "Pull administrator file", "who": "Operations", "does": "Downloads the NAV file", "inputs": ["Administrator portal"], "outputs": ["NAV file"],
         "system": "Administrator portal", "control": "Row count checked against the portal", "exception": "Ask the administrator to resend"},
        {"n": 2, "name": "Reconcile cash in a spreadsheet", "who": "Finance", "does": "Matches cash by hand", "inputs": ["NAV file"], "outputs": ["Cash sheet"], "system": "Excel"},
        {"n": 3, "name": "Review and issue", "who": "", "does": "Signs off", "inputs": [], "outputs": [], "system": ""},
    ], "handovers": [{"from_step": 1, "to_step": 2, "what": "NAV file"}]},
    "kpis": [{"code": "NAV", "name": "Net asset value", "definition": "Assets less liabilities"}],
    "sources": [], "catalogue": [], "governance": [{"rule": "The CIO approves the report", "kind": "approval", "applies_to": []}],
    "unclear": [{"id": "u1", "question": "Who covers when Finance is away?", "settled": False}],
    "signature": {"name": "Arjun Mehta", "role": "sponsor", "at": "2026-10-08T09:00:00+00:00"},
}


def test_build_fills_what_is_known_and_lists_what_is_not():
    sop = K.build(SOW)
    s1, s2, s3 = sop["steps"]
    assert (s1["who"], s1["system"], s1["control"], s1["exception"]) == ("Operations", "Administrator portal", "Row count checked against the portal", "Ask the administrator to resend")
    assert s1["handovers"] == [{"to_step": 2, "what": "NAV file"}]
    assert s2["manual"] and not s1["manual"] and sop["manual_steps"] == [2]
    assert s2["control"] == K.NOT_STATED and s3["who"] == K.NOT_STATED  # nothing invented
    assert sop["roles"] == ["Operations", "Finance"]
    assert "Step 2 (Reconcile cash in a spreadsheet): the control is not stated yet." in sop["open_points"]
    assert "Step 3 (Review and issue): who does it is not stated yet." in sop["open_points"]
    assert any("Who covers when Finance is away?" in p for p in sop["open_points"])
    assert sop["definitions"] == ["Net asset value: Assets less liabilities"] and sop["controls"] == ["Approval: The CIO approves the report"]
    md = K.to_markdown(sop)
    assert "## Steps" in md and "(manual: a candidate for automation)" in md and "Hand over to step 2: NAV file." in md
    assert K.filename(sop, "md") == "SOP-Month-end-reporting-v2.md"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SH_MODEL_PROVIDER", "off")
    data = tmp_path_factory.mktemp("k8") / "data"
    shutil.copytree(ROOT / "data" / "_control", data / "_control")
    (data / "neera").mkdir()
    app = create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real"))
    app.state.model_env = {"SH_MODEL_PROVIDER": "off"}
    from sh_platform.auth.accounts import AccountStore
    pw = {}
    for who in ("arjun.mehta", "leela.raman"):
        email = f"{who}.neera@example.test"
        pw[email] = secrets.token_urlsafe(16)
        AccountStore(data).set_password(email, pw[email])
    yield app, data, pw
    mp.undo()


def client(world, who):
    app, _, pw = world
    c = TestClient(app)
    email = f"{who}.neera@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf", "")
    return c


def test_routes_preview_and_download(world):
    leela = client(world, "leela.raman")
    me = leela.get("/api/auth/me").json()
    plane = PlaneStore(world[1]).plane_for(me.get("company_id") or me["company"]["id"]).ensure()
    draft = copy.deepcopy(SOW) | {"state": "draft", "signature": None}
    write_json_atomic(plane.path("intents", IID, "sow.json"), draft)
    on_team(world[0], IID, "Leela Raman")
    url = f"/api/v1/intents/{IID}/sop"

    r = leela.get(url)
    assert r.status_code == 409 and "signed" in r.json()["detail"]["message"]  # a draft has no SOP

    write_json_atomic(plane.path("intents", IID, "sow.json"), SOW)
    got = leela.get(url)
    assert got.status_code == 200 and got.json()["manual_steps"] == [2] and len(got.json()["steps"]) == 3

    md = leela.get(url + "/download?format=md")
    assert md.status_code == 200 and "## Open points" in md.text and ".md" in md.headers["content-disposition"]
    word = leela.get(url + "/download")  # PF2: always Word, with or without python-docx
    assert word.status_code == 200 and ".docx" in word.headers["content-disposition"] and word.content[:2] == b"PK"
    assert leela.get(url + "/download?format=pdf").status_code == 400
    assert leela.get("/api/v1/intents/nosuchone/sop").status_code == 404


def test_docx_without_python_docx_is_a_valid_word_file(monkeypatch):
    """PF2: the Intent panel and the project page both give .docx; with no python-docx the stdlib writer still makes a real Word file."""
    import io
    import zipfile
    monkeypatch.setattr(K, "docx_available", lambda: False)
    data = K.to_docx(K.build(SOW))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= set(z.namelist())
        doc = z.read("word/document.xml").decode("utf-8")
    assert "Open points" in doc and "<w:document" in doc
    from xml.dom.minidom import parseString
    parseString(doc)  # well-formed, names with & or < escaped


def test_manual_steps_are_named_and_controls_read_as_words():
    """UC9-04: 'Manual steps flagged' names each step; a control starts with its kind in words, not the raw key."""
    md = K.to_markdown(K.build(SOW))
    assert "- 2. Reconcile cash in a spreadsheet" in md and "- Step 2\n" not in md
    assert "- Approval: The CIO approves the report" in md and "approval:" not in md


def test_intent_document_names_sources_and_kpis_with_one_full_stop():
    """UC9-03: the intent document (and the project page, which reads the same lines) has no KPI code, no source id and no '..'."""
    from sh_platform.v1 import i4_sow as I
    sow = copy.deepcopy(SOW)
    sow["kpis"] = [{"code": "K01", "name": "Net worth", "definition": "Holdings at month end.", "formula": "sum", "source_ids": ["administrator"], "status": "defined"}]
    sow["sources"] = [{"id": "administrator", "name": "Fund administrator export", "kind": "file"}]
    sow["catalogue"] = [{"table": "administrator_positions", "layer": "landing", "source_id": "administrator", "feeds_kpis": ["K01"], "meaning": "Positions."}]
    sow["governance"] = [{"rule": "Only the office sees entity figures.", "kind": "access", "applies_to": ["all"], "stated_by": "Daniel"}]
    md = I.to_markdown(sow)
    assert ".." not in md and "K01" not in md and "Sources: Fund administrator export." in md
    assert "From Fund administrator export; feeds Net worth." in md and "Access: Only the office sees entity figures. Applies to all." in md
