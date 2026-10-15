"""A long-lived stream asks whether a session is still alive without keeping it alive (M1-P02 fix round 1)."""
from sh_platform.auth.sessions import SessionManager

ACCOUNT = {"account_id": "a1", "company_id": "co-a", "roles": ["analyst"]}


class Clock:
    now = 1_000.0

    def __call__(self):
        return self.now


def test_is_live_is_true_for_a_live_session_and_false_after_destroy_idle_or_absolute_and_for_junk():
    clock = Clock()
    m = SessionManager("fake-test-secret-not-real", idle=60, absolute=600, clock=clock)
    cookie, _ = m.create(ACCOUNT)
    sid = m.resolve(cookie)["sid"]
    assert m.is_live(sid) is True
    for junk in (None, "", "nope", 5):
        assert m.is_live(junk) is False
    clock.now += 61
    assert m.is_live(sid) is False  # idle
    other, _ = m.create(ACCOUNT)
    sid2 = m.resolve(other)["sid"]
    m.destroy(sid2)
    assert m.is_live(sid2) is False
    third, _ = m.create(ACCOUNT)
    sid3 = m.resolve(third)["sid"]
    for _ in range(12):  # touched all the time, so never idle, but the absolute limit still ends it
        clock.now += 59
        m.resolve(third)
    assert m.is_live(sid3) is False


def test_is_live_never_refreshes_the_idle_timer():
    clock = Clock()
    m = SessionManager("fake-test-secret-not-real", idle=60, absolute=6000, clock=clock)
    cookie, _ = m.create(ACCOUNT)
    sid = m.resolve(cookie)["sid"]
    for _ in range(10):  # ten checks, 10 s apart: a stream's ticks
        clock.now += 10
        m.is_live(sid)
    assert m.is_live(sid) is False  # 100 s idle in total: the checks did not keep it alive
