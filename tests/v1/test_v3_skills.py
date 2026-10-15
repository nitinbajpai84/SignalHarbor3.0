"""Harbor skills: the 63 core skills, office overrides, the usage log, admit, write-skill after two repeats, and `now` on the thread view."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sh_platform.app import create_app  # noqa: E402
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.settings import Settings  # noqa: E402
from sh_platform.v1 import skill_loader as SL  # noqa: E402
from sh_platform.v1 import v3_harbor as H  # noqa: E402
from sh_platform.v1 import v3_skills as S  # noqa: E402
from tests.v1.test_v3_harbor import fake_api  # noqa: E402
from tools import make_skills as MK  # noqa: E402
from tools import seed_evergreen as EG  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    monkeypatch.setenv("SH_V3_SCAN", "off")
    monkeypatch.setattr(H, "SYNC", True)
    monkeypatch.setattr(H.Ctx, "api", fake_api)
    data = tmp_path / "data"
    data.mkdir()
    EG.company(data)
    EG.accounts(data)
    pw = {l.split()[0]: l.split()[1] for l in (data / "_control" / "seed_credentials.txt").read_text().splitlines() if l.strip()}
    c = TestClient(create_app(Settings(mode="dev", data_root=str(data), session_secret="fake-test-secret-not-real")))
    email = "anita.rao.evergreen@example.test"
    assert c.post("/api/auth/login", json={"email": email, "password": pw[email]}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("sh_csrf")
    c.plane = PlaneStore(str(data)).plane_for("evergreen")
    return c


def test_make_skills_wrote_all_63():
    rows = MK.parse(MK.CATALOGUE.read_text(encoding="utf-8"))
    assert len(rows) == 63 and len({r["id"] for r in rows}) == 63
    for r in rows:
        meta = S.parse((MK.OUT / r["id"] / "SKILL.md").read_text(encoding="utf-8"))
        assert meta["centre"] == MK.CENTRE[r["id"].split(".")[0]] and meta["source"] == "core" and meta["version"] == 1 and meta["status"] == "in_use"
        assert meta["steps"] and meta["checks"] and meta["never"] and meta["output"]
    assert len(list(MK.OUT.glob("*.*/SKILL.md"))) == 63
    assert not any("." in a for a in SL.agents()) and "north" in SL.agents()  # the new folders are not agents


def test_list_read_and_office_override(client):
    got = client.get("/api/v3/skills").json()["skills"]
    assert len(got) == 63
    one = next(s for s in got if s["id"] == "intent.sign")
    assert one["tier"] == "tools" and one["tested"] == {"passed": 2, "total": 2} and one["used"] == 0
    full = client.get("/api/v3/skills/intent.sign").json()
    assert full["steps"] and full["history"][0]["v"] == 1 and len(full["tests"]) == 2
    assert client.get("/api/v3/skills/nope.none").status_code == 404
    d = client.plane.path("skills", "intent.sign")
    d.mkdir(parents=True)
    meta = S.parse((SL.SKILLS_DIR / "intent.sign" / "SKILL.md").read_text(encoding="utf-8"))
    meta.update(name="Sign here", source="office")
    (d / "SKILL.md").write_text(S.dump(meta), encoding="utf-8")
    assert client.get("/api/v3/skills/intent.sign").json()["name"] == "Sign here"
    assert len(client.get("/api/v3/skills").json()["skills"]) == 63  # replaced, not added


def test_try_runs_tests_or_says_there_is_none(client):
    assert client.post("/api/v3/skills/data.detect-duplicate/try").json()["ok"] is True
    assert client.post("/api/v3/skills/intent.draft-goal/try").json()["message"] == "no automatic test"


def test_record_logs_usage(client):
    plane = client.plane
    with S.record(plane, "t-1", "run.load-file") as rec:
        rec["detail"] = "3 files"
    assert S.record(plane, "t-1", "intent.sign", lambda: "signed") == "signed"
    with pytest.raises(RuntimeError), S.record(plane, "t-2", "run.on-copy"):
        raise RuntimeError("boom")
    runs = client.get("/api/v3/skills/usage?thread=t-1").json()["runs"]
    assert [(r["skill"], r["ok"], r["detail"]) for r in runs] == [("run.load-file", True, "3 files"), ("intent.sign", True, "signed")]
    assert runs[0]["name"] == "Load file" and runs[0]["ms"] >= 0
    bad = client.get("/api/v3/skills/usage?thread=t-2").json()["runs"][0]
    assert bad["ok"] is False and bad["detail"] == "boom"
    assert next(s for s in client.get("/api/v3/skills").json()["skills"] if s["id"] == "run.load-file")["used"] == 1


def _two_threads(client):
    plane = client.plane
    ths = []
    for i in range(2):
        th = {"id": f"t-{i}", "title": "x", "created": f"2026-10-1{i}T00:00:00Z", "stage": "question", "events": [], "steps": [], "learn": []}
        H.save(plane, th)
        ths.append(th)
    return plane, ths


def test_write_skill_waits_for_the_second_repeat_then_admit_signs(client):
    plane, (a, b) = _two_threads(client)
    kind, sid = "Read the sample files", "office.read-the-sample-files"
    H._learn(plane, a, kind, "Which lines hold the fund? -> the second column")
    assert S.listing(plane, "waiting") == []
    H._learn(plane, b, kind, "Which lines hold the fund? -> the second column again")
    w = client.get("/api/v3/skills?status=waiting").json()["skills"]
    assert [s["id"] for s in w] == [sid] and w[0]["version"] == 0 and w[0]["source"] == "office"
    one = client.get(f"/api/v3/skills/{sid}").json()
    assert len(one["evidence"]) == 2 and one["why"] and one["steps"] and one["checks"]
    assert client.post(f"/api/v3/skills/{sid}/edit", json={"field": "goal", "value": "Read the fund column"}).json()["goal"] == "Read the fund column"
    assert S.write_skill(plane, a, kind, []) is None  # not drafted twice
    done = client.post(f"/api/v3/skills/{sid}/admit").json()
    assert done["version"] == 1 and done["status"] == "in_use" and done["history"][-1]["by"] == "Anita Rao" and done["history"][-1]["change"] == "Admitted"
    assert client.post(f"/api/v3/skills/{sid}/admit").status_code == 409
    assert client.post(f"/api/v3/skills/{sid}/edit", json={"field": "goal", "value": "x"}).status_code == 409


def test_reject_retires_a_waiting_skill(client):
    plane, (a, b) = _two_threads(client)
    H._learn(plane, a, "file:Cedar notice", "a")
    H._learn(plane, b, "file:Cedar notice", "b")
    got = client.post("/api/v3/skills/office.read-cedar-notice/reject", json={"reason": "not needed"}).json()
    assert got["status"] == "retired" and got["history"][-1]["change"] == "Rejected: not needed"


def test_a_model_draft_with_a_figure_is_not_used():
    assert S._clean({"name": "n", "goal": "g", "when": "w", "steps": ["a"], "checks": ["c"]}) is not None
    assert S._clean({"name": "n", "goal": "g", "when": "w", "steps": ["pay 5 percent"], "checks": ["c"]}) is None


def test_the_thread_view_carries_now_and_steps_are_logged(client, monkeypatch):
    seen = []

    def a_sign(x):
        seen.append(dict(x.th["now"]))
        return "signed"
    monkeypatch.setitem(H.CHAINS, "A", ([("North", "Signed the intent", a_sign)], "live"))
    monkeypatch.setitem(H.SKILLS_OF, "a_sign", ("intent.sign",))
    t = client.post("/api/v3/threads", json={"text": "Can we meet the capital calls?"}).json()
    assert t["now"] is None
    H.run_chain(client.app, client.plane, t["id"], "A", None)
    assert seen == [{"skill": "intent.sign", "name": "Sign", "text": "Signed the intent"}]
    assert client.get(f"/api/v3/threads/{t['id']}").json()["now"] is None
    done = [r["skill"] for r in client.get(f"/api/v3/skills/usage?thread={t['id']}").json()["runs"]]
    assert done[-1] == "intent.sign" and "intent.restate-ask" in done and "intent.find-gaps" in done
    th = H.load(client.plane, t["id"])
    th["now"] = {"skill": "x", "name": "X", "text": "t"}
    assert H.view(th)["now"]["skill"] == "x"
