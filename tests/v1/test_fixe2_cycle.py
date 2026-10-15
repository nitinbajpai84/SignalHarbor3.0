"""FIXE2: the company's cycle date. One function (wh.today) answers for the company; intake, runs, recon, Consume and the hand-over due date read it;
two companies with different cycle dates never leak into each other."""
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b9_verify, cy_routes, e2_intake, e3_recon, k4_office, p2_assign, wh

JUL31 = date(2026, 7, 31)
ADMIN = Viewer(name="Nitin", roles=frozenset({"company_admin"}), account_id="acc-admin")


@pytest.fixture()
def planes(tmp_path):
    wh.reset_cache()
    store = PlaneStore(tmp_path / "data")
    return store.create("acme"), store.create("globex")


def test_the_default_is_the_real_day_and_the_setting_pins_it(planes):
    a, _ = planes
    wh.use(a)
    assert wh.today(a) == datetime.now(timezone.utc).date()
    wh.set_demo_today(a, JUL31)
    assert wh.today(a) == wh.today() == JUL31 and wh.demo_today(a) == JUL31
    wh.set_demo_today(a, None)
    assert wh.today() == datetime.now(timezone.utc).date()


def test_intake_run_recon_and_consume_default_to_the_cycle_date(planes):
    a, _ = planes
    wh.set_demo_today(a, JUL31)
    wh.connect(a).close()                                                      # a request resolves its company
    assert e3_recon._day(None) == JUL31                                        # recon as_of
    assert k4_office._day(None) == JUL31                                       # Consume (Office) as_of
    assert b9_verify._latest_month(a, "no-such-project") == "2026-06"         # a run's month: the month before the cycle date
    doc = e2_intake.register(a, "x.txt", ADMIN, data=b"Fund A statement 31 July 2026", filename="fund-a.txt")
    with wh.connect(a) as con:
        got = con.execute("select received_at from documents where id = ?", [doc]).fetchone()[0]
    assert got.astimezone(timezone.utc).date() == JUL31                                                 # intake as-of


def test_due_date_is_judged_on_the_cycle_date(planes):
    a, _ = planes
    wh.set_demo_today(a, JUL31)
    p2_assign._check(a, ["pipelines"], "x", "", "2026-08-07")                     # accepted at cycle 31 Jul (the real clock says 12 Oct or later)
    with pytest.raises(p2_assign.Refused):
        p2_assign._check(a, ["pipelines"], "x", "", "2026-07-30")
    p2_assign._check(a, ["pipelines"], "x", "", "2026-07-31")


def test_two_companies_with_different_cycle_dates_do_not_leak(planes):
    a, b = planes
    wh.set_demo_today(a, JUL31)
    wh.set_demo_today(b, date(2026, 9, 30))
    wh.use(a)
    assert wh.today() == JUL31 and wh.today(b) == date(2026, 9, 30)
    wh.use(b)
    assert wh.today() == date(2026, 9, 30) and wh.today(a) == JUL31
    seen = {}
    import threading
    def work(name, plane):
        wh.connect(plane).close()
        seen[name] = wh.today()
    ts = [threading.Thread(target=work, args=(n, p)) for n, p in (("a", a), ("b", b))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert seen == {"a": JUL31, "b": date(2026, 9, 30)}


def test_the_route_sets_and_clears_the_cycle_date(planes, monkeypatch):
    a, _ = planes
    monkeypatch.setattr(cy_routes, "_plane", lambda r: a)
    monkeypatch.setattr(cy_routes, "viewer_of", lambda r: Viewer(name="Pat", roles=frozenset({"head_of_data", "analyst"}), account_id="x"))
    c = TestClient(_app())
    assert c.put("/api/v1/cycle-date", json={"cycle_date": "2026-07-31"}).json()["today"] == "2026-07-31"
    assert c.get("/api/v1/cycle-date").json()["pinned"] is True
    assert c.put("/api/v1/cycle-date", json={"cycle_date": "31/07"}).status_code == 400
    assert c.put("/api/v1/cycle-date", json={"cycle_date": None}).json()["pinned"] is False
    monkeypatch.setattr(cy_routes, "viewer_of", lambda r: Viewer(name="Mei", roles=frozenset({"analyst"}), account_id="y"))
    assert c.put("/api/v1/cycle-date", json={"cycle_date": "2026-07-31"}).status_code == 403
    assert c.get("/api/v1/cycle-date").json()["can_set"] is False


def _app():
    app = FastAPI()
    app.include_router(cy_routes.router)
    return app
