"""The interview routes: who may use them, the invite link, and a guest who can answer one person's interview and nothing else."""
from datetime import datetime, timedelta, timezone

from iv_kit import FAMILY, OTHER
from sh_platform.interview import links
from sh_platform.profile import store

H = "X-Session-Token"


def token_of(link: str) -> str:
    return link.rsplit("/", 1)[1].split("?")[0]


NOTE = "The weekly report is always late and Dan never says so."


def _to_q14(c):
    c.post("/api/interview/wei-chen/start")
    for _ in range(6):
        c.post("/api/interview/wei-chen/answer", json={"text": "Weekly, about once a week."})


def _organiser_views(env):
    """Everything the three organiser roles get back about Wei's interview, from the state route and the start route."""
    return [r.text for role in ("company_admin", "sponsor", "analyst")
            for r in (lambda cl: (cl.get("/api/interview/wei-chen"), cl.post("/api/interview/wei-chen/start")))(env.login(role))]


def test_a_q14_note_is_not_shown_to_the_organiser_before_or_after_the_choice(env):
    me = env.login("participant")
    _to_q14(me)
    me.post("/api/interview/wei-chen/answer", json={"text": NOTE})  # held: no choice made yet
    assert all("always late" not in t for t in _organiser_views(env))
    assert "always late" in me.get("/api/interview/wei-chen").text  # the person still sees their own words
    me.post("/api/interview/wei-chen/answer", json={"text": "private"})
    assert all("always late" not in t for t in _organiser_views(env))
    assert "always late" in me.get("/api/interview/wei-chen").text


def test_an_anonymous_note_never_sits_next_to_the_persons_name(env):
    me = env.login("participant")
    _to_q14(me)
    me.post("/api/interview/wei-chen/answer", json={"text": NOTE})
    me.post("/api/interview/wei-chen/answer", json={"text": "anonymous, it is about Dan"})
    seen = env.login("company_admin").get("/api/interview/wei-chen").json()
    assert "always late" not in str(seen) and "about Dan" not in str(seen) and "An anonymous note" not in str(seen["log"]) and "May we share this note" not in str(seen["log"])
    assert "always late" in me.get("/api/interview/wei-chen").text
    filed = store.load(env.plane())["interviews"]
    assert "always late" in str(filed) and "wei" not in str({k: v for k, v in filed.items() if k.startswith("anon-")}).lower()


def test_a_named_note_is_shown_to_the_organiser(env):
    me = env.login("participant")
    _to_q14(me)
    me.post("/api/interview/wei-chen/answer", json={"text": NOTE})
    me.post("/api/interview/wei-chen/answer", json={"text": "named"})
    assert "always late" in env.login("company_admin").get("/api/interview/wei-chen").text


def test_the_invite_link_carries_the_first_name_for_the_signed_in_message(env):
    assert env.login("company_admin").post("/api/interview/aaron-lyle/link").json()["link"].endswith("?for=Aaron")


def test_the_organiser_lists_everyone_with_status_and_a_person_sees_only_themselves(env):
    rows = {p["id"]: p for p in env.login("company_admin").get("/api/interview").json()["people"]}
    assert {"aaron-lyle", "dan-data", "sue-sponsor", "wei-chen"} <= set(rows) and rows["aaron-lyle"]["status"] == "not_started" and rows["dan-data"]["kind"] == "owner"
    mine = env.login("participant").get("/api/interview").json()
    assert [p["id"] for p in mine["people"]] == ["wei-chen"] and mine["organiser"] is False


def test_a_person_runs_their_own_interview_and_nobody_elses(env):
    c = env.login("participant")  # Wei Chen
    assert c.post("/api/interview/wei-chen/start").json()["card"]["qid"] == "Q1"
    r = c.post("/api/interview/wei-chen/answer", json={"text": "Which fund to trim, every month."}).json()
    assert r["card"]["qid"] == "Q2" and r["progress"]["answered"] == 1
    assert c.post("/api/interview/aaron-lyle/start").status_code == 403
    assert c.post("/api/interview/aaron-lyle/answer", json={"text": "x"}).status_code == 403
    assert c.post("/api/interview/wei-chen/link").status_code == 403
    admin = env.login("company_admin")
    assert admin.post("/api/interview/aaron-lyle/start").status_code == 200  # the organiser may start anyone's
    assert admin.post("/api/interview/aaron-lyle/answer", json={"text": "x"}).status_code == 403  # but answers are the person's own
    assert admin.post("/api/interview/nobody/start").status_code == 404
    assert store.load(env.plane())["interviews"]["wei-chen"]["q1"]["from"] == "Interview with Wei Chen"


def test_an_unsigned_caller_reaches_none_of_the_signed_in_routes(env):
    g = env.guest()
    assert g.get("/api/interview").status_code == 401
    assert g.post("/api/interview/aaron-lyle/start").status_code in (401, 403)
    assert g.post("/api/interview/aaron-lyle/link").status_code in (401, 403)


def test_the_answer_goes_through_the_model_stub_with_no_figure(env):
    env.stub.replies = ["TRIGGER: vague\nFOLLOWUP: Can you give one recent example?"]
    c = env.login("participant")
    c.post("/api/interview/wei-chen/start")
    r = c.post("/api/interview/wei-chen/answer", json={"text": "Slow, about 40 hours a month."}).json()
    assert r["card"]["mode"] == "followup" and r["card"]["agent"] == "north"
    assert env.stub.sent and not any(ch.isdigit() for ch in env.stub.everything)


def test_the_invite_link_lets_a_guest_answer_only_that_persons_interview(env):
    link = env.login("company_admin").post("/api/interview/aaron-lyle/link").json()["link"]
    assert link.startswith("/interview/iv.")
    g = env.guest()
    h = {H: token_of(link)}
    assert g.post("/api/modules/interview/guest/start", headers=h).json()["person"]["id"] == "aaron-lyle"
    r = g.post("/api/modules/interview/guest/answer", headers=h, json={"text": "Whether a name is over the limit.", "person": "dan-data", "person_id": "dan-data"})
    assert r.status_code == 200 and r.json()["person"]["id"] == "aaron-lyle"
    interviews = store.load(env.plane())["interviews"]
    assert "q1" in interviews["aaron-lyle"] and "dan-data" not in interviews  # the body cannot name someone else
    assert g.post("/api/modules/interview/guest/finish", headers=h).json()["status"] == "done"
    assert g.post("/api/modules/interview/guest/answer", headers=h, json={"text": "more"}).status_code == 409


def test_a_guest_link_does_not_open_the_signed_in_routes(env):
    link = env.login("company_admin").post("/api/interview/aaron-lyle/link").json()["link"]
    g = env.guest()
    g.headers[H] = token_of(link)
    assert g.get("/api/interview").status_code == 401
    assert g.get("/api/profile").status_code == 401
    assert g.get("/api/interview/dan-data").status_code == 401


def test_another_company_is_unreachable_through_a_link(env):
    token = token_of(env.login("company_admin").post("/api/interview/aaron-lyle/link").json()["link"])
    g = env.guest()
    other = token.replace(f"iv.{FAMILY}.", f"iv.{OTHER}.")
    assert g.post("/api/modules/interview/guest/start", headers={H: other}).status_code == 404
    assert g.post("/api/modules/interview/guest/start", headers={H: "iv.no-such-company." + token.split(".", 2)[2]}).status_code == 404
    assert g.post("/api/modules/interview/guest/start", headers={H: "junk"}).status_code == 404
    assert g.post("/api/modules/interview/guest/start").status_code == 404
    assert not env.plane(OTHER).path("context", "interview").exists()  # nothing written in the other company's space


def test_a_link_is_for_one_person_hashed_and_expiring(env):
    plane = env.plane()
    t1 = links.mint(plane, FAMILY, "aaron-lyle")
    t2 = links.mint(plane, FAMILY, "dan-data")
    assert links.check(plane, t1) == "aaron-lyle" and links.check(plane, t2) == "dan-data"
    assert t1 not in plane.path("context", "interview", "links.json").read_text(encoding="utf-8")  # only the hash is kept
    assert links.check(plane, t1, datetime.now(timezone.utc) + timedelta(days=15)) is None  # 336 hours
    t3 = links.mint(plane, FAMILY, "aaron-lyle")  # a new link replaces the old one
    assert links.check(plane, t1) is None and links.check(plane, t3) == "aaron-lyle"
    assert links.check(plane, t1[:-1] + ("A" if t1[-1] != "A" else "B")) is None
