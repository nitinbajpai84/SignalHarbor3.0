"""Cycle 2 (UC1-C2-01, UC6-01/02): the demo clock stays inside demo_today at any real time of day, moves forward, and is the same on every thread."""
import threading
from datetime import date, datetime, timedelta, timezone

from sh_platform.plane import PlaneStore
from sh_platform.v1 import wh


def test_demo_clock_stays_on_the_demo_day_late_in_the_day_and_moves_forward(tmp_path, monkeypatch):
    plane = PlaneStore(tmp_path / "data").create("acme")
    wh.set_demo_today(plane, date(2026, 10, 9))
    day_end = datetime(2026, 10, 9, 23, 59, 59, 999999, tzinfo=timezone.utc)
    seen = []
    for real in (datetime(2026, 10, 9, 22, 35, tzinfo=timezone.utc), datetime(2026, 10, 10, 0, 5, tzinfo=timezone.utc),
                 datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc), datetime(2026, 11, 30, tzinfo=timezone.utc)):
        monkeypatch.setattr(wh, "datetime", type("D", (datetime,), {"now": classmethod(lambda cls, tz=None, r=real: r)}))
        n = wh.now(plane)
        assert n.date() == date(2026, 10, 9) and datetime(2026, 10, 9, 23, tzinfo=timezone.utc) <= n <= day_end
        seen.append(n)
    assert seen == sorted(seen) and seen[0] < seen[1]          # after real midnight the clock does not jump back (the cycle 2 bug)
    assert seen[0] + timedelta(seconds=60) > seen[2]             # a real day moves it about 86 seconds


def test_plane_less_now_follows_the_company_the_thread_works_for(tmp_path):
    """FIXE2: no process-wide day. A thread that connects to the company sees its day; it never inherits another company's."""
    plane = PlaneStore(tmp_path / "data").create("acme")
    wh.set_demo_today(plane, date(2026, 10, 9))
    got = []
    def work():
        wh.connect(plane).close()
        got.append(wh.now().date())
    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert got == [date(2026, 10, 9)] and wh.now().date() == date(2026, 10, 9)
    wh.set_demo_today(plane, None)
    assert wh.now().date() == datetime.now(timezone.utc).date()
