"""V5 D1: Delivery. Stub transports only: nothing is sent. Channels, approval by another person, figures from records, egress, outbox, scheduler."""
import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.egress import gateway as G
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.policy import EgressPolicy
from sh_platform.profile.view import Viewer
from sh_platform.v1 import b7_studio as S
from sh_platform.v1 import cx_dash as D
from sh_platform.v1 import d1_delivery as X
from sh_platform.v1 import d1_routes, wh
from sh_platform.v1.p1_project import Refused
from tests.v1.test_cx import ADMIN, GOLD, env  # noqa: F401 - env is a fixture

HEAD = Viewer(name="Head of data", roles=frozenset({"analyst"}), account_id="acc-head")
SPONSOR = Viewer(name="Daniel", roles=frozenset({"sponsor"}), account_id="acc-sp")
APPROVER = Viewer(name="Raj", roles=frozenset({"approver"}), account_id="acc-raj")
MAKER = Viewer(name="Mei", roles=frozenset({"analyst"}), account_id="acc-mei")
READER = Viewer(name="Chia", roles=frozenset({"participant"}), account_id="acc-c")
HOOK = "SH_TEST_SLACK_HOOK"
URL = "https://hooks.example-chat.test/services/AAA/BBB/ccc"
HOST = "hooks.example-chat.test"


@pytest.fixture()
def sent(monkeypatch):
    monkeypatch.delenv("SH_SMTP_URL", raising=False)
    monkeypatch.delenv(HOOK, raising=False)
    return {"hooks": [], "mail": []}


def senders(sent):
    return {"webhook": lambda plane, url, body: sent["hooks"].append((url, body)) or "ok",
            "email": lambda plane, to, subj, body: sent["mail"].append((to, subj, body)) or "sent"}


AUDIENCE = {"acc-head", "acc-sp", "acc-raj", "acc-mei"}  # READER (and OUTSIDER) are not in the dashboard's audience
OUTSIDER = Viewer(name="Ola", roles=frozenset({"analyst", "sponsor"}), account_id="acc-out")


@pytest.fixture()
def pub(env, monkeypatch):  # a published dashboard with a figure tile
    plane, pid = env
    monkeypatch.setattr(D, "_in_audience", lambda plane, viewer, rec: viewer.account_id in AUDIENCE)
    d = S.create(plane, ADMIN, pid, "Board pack")
    S.add_widget(plane, ADMIN, pid, d["id"], {"kind": "figure", "table": GOLD, "row": 0, "col": 0, "size": "wide"})
    D.submit(plane, ADMIN, pid, d["id"])
    D.decide_version(plane, HEAD, pid, d["id"], True)
    return plane, pid, d["id"]


def live(plane, pid, did, body, maker=MAKER, approver=SPONSOR):
    ch = X.create_channel(plane, maker, pid, {"dashboard_id": did} | body)
    X.submit_channel(plane, maker, pid, ch["id"])
    X.decide_channel(plane, approver, pid, ch["id"], True)
    X.go_live(plane, maker, pid)
    return X._channel(X._load(plane, pid), ch["id"])


def test_channel_needs_an_approved_dashboard(env):
    plane, pid = env
    d = S.create(plane, ADMIN, pid, "Draft only")
    with pytest.raises(Refused) as e:
        X.create_channel(plane, MAKER, pid, {"kind": "slack", "dashboard_id": d["id"]})
    assert e.value.status == 409


def test_maker_cannot_approve_and_go_live_sends_nothing(pub, sent):
    plane, pid, did = pub
    ch = X.create_channel(plane, MAKER, pid, {"kind": "slack", "dashboard_id": did})
    with pytest.raises(Refused):  # not submitted yet
        X.decide_channel(plane, SPONSOR, pid, ch["id"], True)
    X.submit_channel(plane, MAKER, pid, ch["id"])
    for who in (MAKER, READER):
        with pytest.raises(Refused) as e:
            X.decide_channel(plane, who, pid, ch["id"], True)
        assert e.value.status == 403
    with pytest.raises(Refused):
        X.go_live(plane, MAKER, pid)  # nothing approved yet
    X.decide_channel(plane, APPROVER, pid, ch["id"], True)
    with pytest.raises(Refused):  # approved but not live: no send
        X.deliver(plane, pid, X._channel(X._load(plane, pid), ch["id"]), "manual", senders=senders(sent))
    assert X.go_live(plane, MAKER, pid)["sent_now"] == 0 and not sent["hooks"] and X.outbox(plane, pid) == []


def test_send_back_needs_a_reason(pub):
    plane, pid, did = pub
    ch = X.create_channel(plane, MAKER, pid, {"kind": "email", "dashboard_id": did, "addresses": "a@acme.test"})
    X.submit_channel(plane, MAKER, pid, ch["id"])
    with pytest.raises(Refused) as e:
        X.decide_channel(plane, SPONSOR, pid, ch["id"], False, "")
    assert e.value.status == 400
    assert X.decide_channel(plane, SPONSOR, pid, ch["id"], False, "Wrong people")["sent_back"]["reason"] == "Wrong people"


def test_message_figures_come_from_the_rows_and_the_secret_stays_hidden(pub, sent, monkeypatch):
    plane, pid, did = pub
    monkeypatch.setenv(HOOK, URL)
    X.set_config(plane, ADMIN, "slack", HOOK, HOST)
    ch = live(plane, pid, did, {"kind": "slack"})
    row = X.deliver(plane, pid, ch, "manual", senders=senders(sent))
    assert row["status"] == "sent" and sent["hooks"][0][0] == URL
    view = D.published_view(D._load(plane, pid, did))
    got = D.tile_rows(plane, pid, view, view["tiles"][0]["id"])
    for v in got["rows"][0].values():
        assert X._fmt(v) in sent["hooks"][0][1]["text"]  # printed as the record holds it
    assert URL not in json.dumps(X.outbox(plane, pid)) and URL not in json.dumps(D.jsonable(X.view(plane, ADMIN, pid)))


def test_not_configured_channel_is_held_in_the_outbox_with_preview(pub, sent):
    plane, pid, did = pub
    ch = live(plane, pid, did, {"kind": "teams"})
    row = X.deliver(plane, pid, ch, "daily", senders=senders(sent))
    assert row["status"] == "held" and "not set up" in row["reason"] and row["preview"] and not sent["hooks"]
    mail = live(plane, pid, did, {"kind": "email", "addresses": ["a@acme.test"]})
    assert X.deliver(plane, pid, mail, "daily")["status"] == "held"  # no SMTP, no stub: kept, never sent
    assert [r["status"] for r in X.outbox(plane, pid)] == ["held", "held"]


def test_retry_after_setup_sends(pub, sent, monkeypatch):
    plane, pid, did = pub
    ch = live(plane, pid, did, {"kind": "slack"})
    held = X.deliver(plane, pid, ch, "daily", senders=senders(sent))
    monkeypatch.setenv(HOOK, URL)
    X.set_config(plane, ADMIN, "slack", HOOK, HOST)
    assert X.retry(plane, MAKER, pid, held["id"], senders=senders(sent))["status"] == "sent"


def test_blocked_by_egress_is_visible(pub, sent, monkeypatch):
    plane, pid, did = pub
    monkeypatch.setenv(HOOK, URL)
    X.set_config(plane, ADMIN, "slack", HOOK, HOST)
    ch = live(plane, pid, did, {"kind": "slack"})

    def refuse(*a):
        raise EgressBlocked("destination_not_allowed")
    row = X.deliver(plane, pid, ch, "daily", senders={"webhook": refuse})
    assert row["status"] == "blocked" and "list" in row["reason"]


def test_real_webhook_exit_allowlist_and_log(pub):
    plane, pid, did = pub
    seen = []
    tr = lambda url, body: seen.append((url, body)) or "ok"  # noqa: E731 - stub transport, nothing leaves
    with pytest.raises(EgressBlocked) as e:  # no host listed
        G.send_webhook(plane, URL, {"text": "hi"}, transport=tr)
    assert e.value.reason_code == "destination_not_allowed" and not seen
    X.set_config(plane, ADMIN, "slack", HOOK, HOST)
    assert G.send_webhook(plane, URL, {"text": "Board pack: 100"}, transport=tr) == "ok" and len(seen) == 1
    with pytest.raises(EgressBlocked):
        G.send_webhook(plane, f"http://{HOST}/x", {"text": "x"}, transport=tr)  # not https
    lines = [json.loads(x) for x in (plane.area("context") / "egress_log.jsonl").read_text().splitlines()]
    assert [l["decision"] for l in lines] == ["blocked", "sent", "blocked"]
    assert all("services" not in json.dumps(l) and "Board pack" not in json.dumps(l) for l in lines)  # host only, never content


def test_only_admin_sets_up_and_names_must_be_secret_names(env):
    plane, pid = env
    with pytest.raises(Refused):
        X.set_config(plane, MAKER, "slack", HOOK, "hooks.slack.com")
    with pytest.raises(Refused):
        X.set_config(plane, ADMIN, "slack", "https://hooks.slack.com/services/T/B/x", "hooks.slack.com")  # a URL is not a name
    with pytest.raises(Refused):
        X.set_config(plane, ADMIN, "slack", HOOK, "https://hooks.slack.com/x")
    view = X.set_config(plane, ADMIN, "slack", HOOK, "hooks.slack.com")
    assert view["channels"][0] == {"kind": "slack", "label": "Slack channel", "secret": HOOK, "host": "hooks.slack.com", "configured": False}
    assert EgressPolicy(plane).webhook_hosts() == ["hooks.slack.com"]
    X.set_config(plane, ADMIN, "slack", "", "")
    assert EgressPolicy(plane).webhook_hosts() == []


def test_scheduler_daily_0700_once_per_slot(pub, sent):
    plane, pid, did = pub
    s = senders(sent)
    live(plane, pid, did, {"kind": "email", "addresses": ["a@acme.test"], "when": "daily", "at": "07:00"})
    assert X.tick(plane, datetime(2026, 10, 13, 6, 59), senders=s)[0]["status"] == "sent"  # yesterday's slot, not yet sent
    assert X.tick(plane, datetime(2026, 10, 13, 6, 59), senders=s) == []  # once per slot
    assert len(X.tick(plane, datetime(2026, 10, 13, 7, 1), senders=s)) == 1  # the new 07:00 slot
    assert len(sent["mail"]) == 2


def test_on_change_sends_only_when_figures_change(pub, sent):
    plane, pid, did = pub
    s = senders(sent)
    live(plane, pid, did, {"kind": "email", "addresses": ["a@acme.test"], "when": "on_change"})
    assert len(X.tick(plane, senders=s)) == 1 and X.tick(plane, senders=s) == []
    with wh.connect(plane) as con:
        con.execute(f"insert into {GOLD} values ('2026-10-31','Fund A',999)")
    assert len(X.tick(plane, senders=s)) == 1


def test_threshold_alert_fires_once_per_change(pub, sent):
    plane, pid, did = pub
    tid = D.published_view(D._load(plane, pid, did))["tiles"][0]["id"]
    s = senders(sent)
    X.create_channel(plane, MAKER, pid, {"kind": "alert", "dashboard_id": did, "addresses": ["a@acme.test"], "alert": {"tile": tid, "op": "gt", "limit": "1000000"}})
    ch = live(plane, pid, did, {"kind": "alert", "addresses": ["a@acme.test"], "alert": {"tile": tid, "op": "lt", "limit": "1000000"}})
    out = X.tick(plane, senders=s)  # the first stays a draft; only the approved, live one is judged
    assert len(out) == 1 and "falls below" in out[0]["preview"] and X.tick(plane, senders=s) == []
    assert ch["id"] == out[0]["channel_id"]


def test_morning_note_lines_and_summary(pub):
    plane, pid, did = pub
    live(plane, pid, did, {"kind": "morning_note"})
    live(plane, pid, did, {"kind": "slack"}, approver=APPROVER)
    lines = X.morning_note_lines(plane, ADMIN)
    assert lines and lines[0]["title"] == "Board pack" and lines[0]["lines"]
    sm = X.summary(plane, ADMIN, pid)
    assert sm["complete"] and len(sm["delivered_to"]) == 2 and any("delivery channels approved" in v["text"] for v in sm["verified"])
    assert [x["n"] for x in sm["steps"]] == [1, 2, 3, 4] and sm["steps"][3]["state"] == "Approved and delivered to 2 channels"   # D5: the four-step row
    assert sm["steps"][2]["state"] is None and sm["figures"] is None                                                         # nothing verified, no review: nothing invented
    assert any(g["group"] == "Dashboards" and "Board pack" in g["items"][0]["text"] for g in sm["knowledge"])                # what entered the company map
    v = X.view(plane, ADMIN, pid)
    assert v["figures"] is None and all(c["preview"] is None or "tile" in c["preview"] for c in v["channels"])


def test_complete_page_reads_the_plan_approval_and_going_live_completes_the_project(pub):
    """V6 (walk gaps 12 and 13): the Architecture card names who approved the plan, and the project reads as live on the company map."""
    from sh_platform.jsonfile import write_json_atomic
    from sh_platform.v1 import b6_plan as B, p1_project as P1
    plane, pid, did = pub
    assert X.summary(plane, ADMIN, pid)["steps"][1]["state"] is None
    f = B.folder(plane, pid)
    f.mkdir(parents=True, exist_ok=True)
    write_json_atomic(f / "plan-v1.json", {"state": "approved", "approved_by": "Anita Rao", "version": 1})
    live(plane, pid, did, {"kind": "morning_note"})
    sm = X.summary(plane, ADMIN, pid)
    assert sm["steps"][1]["state"] == "Approved by Anita Rao" and {"text": "The architecture was approved", "by": "Anita Rao"} in sm["verified"]
    assert P1.read(plane, pid)["stage"] == "live"


def test_routes_declared_default_deny_and_end_to_end(pub, monkeypatch):
    plane, pid, did = pub
    declared = yaml.safe_load(Path(X.__file__).with_name("d1.permissions.yaml").read_text(encoding="utf-8"))["routes"]
    real = {f"{m} {r.path}" for r in d1_routes.router.routes for m in r.methods}
    assert real == set(declared)
    assert all("participant" not in v["roles"] for k, v in declared.items() if "delivery-lines" not in k)
    assert declared["PUT /api/v1/settings/delivery"]["roles"] == ["company_admin"]
    cur = {"v": MAKER}
    monkeypatch.setattr(d1_routes, "viewer_of", lambda request: cur["v"])
    monkeypatch.setattr(d1_routes, "_plane", lambda request: plane)
    app = FastAPI()
    app.include_router(d1_routes.router)
    c, base = TestClient(app), f"/api/v1/build/p/{pid}/delivery"
    cid = c.post(base + "/channels", json={"kind": "email", "dashboard_id": did, "addresses": "a@acme.test"}).json()["id"]
    assert c.post(f"{base}/channels/{cid}/submit").status_code == 200
    assert c.post(f"{base}/channels/{cid}/approve").status_code == 403  # the maker
    cur["v"] = SPONSOR
    assert c.post(f"{base}/channels/{cid}/approve").status_code == 200
    cur["v"] = MAKER
    assert c.post(base + "/go-live").json()["sent_now"] == 0
    v = c.get(base).json()
    assert v["channels"][0]["status"] == "approved" and v["channels"][0]["preview"]["text"] and v["can"]["settings"] is False
    assert c.put("/api/v1/settings/delivery", json={"kind": "slack", "secret": HOOK, "host": "hooks.slack.com"}).status_code == 403
    cur["v"] = ADMIN
    assert c.put("/api/v1/settings/delivery", json={"kind": "slack", "secret": HOOK, "host": "hooks.slack.com"}).status_code == 200
    cur["v"] = READER
    assert c.post(base + "/go-live").status_code == 403


def test_review_dashboard_access_secret_names_and_hosts(pub, sent):
    plane, pid, did = pub
    with pytest.raises(Refused) as e:  # a maker who may not open the dashboard cannot send its figures anywhere
        X.create_channel(plane, OUTSIDER, pid, {"kind": "email", "dashboard_id": did, "addresses": "a@acme.test"})
    assert e.value.status == 403
    ch = X.create_channel(plane, MAKER, pid, {"kind": "email", "dashboard_id": did, "addresses": "a@acme.test"})
    X.submit_channel(plane, MAKER, pid, ch["id"])
    with pytest.raises(Refused) as e:  # nor approve it blind
        X.decide_channel(plane, OUTSIDER, pid, ch["id"], True)
    assert e.value.status == 403
    v = X.view(plane, OUTSIDER, pid)
    assert v["channels"][0]["preview"] is None and v["channels"][0]["can"]["approve"] is False
    for name in ("ANTHROPIC_API_KEY", "SH_SECRET_KEY", "SH_SMTP_URL"):  # only SH_..._WEBHOOK / _HOOK names
        with pytest.raises(Refused):
            X.set_config(plane, ADMIN, "slack", name, "hooks.slack.com")
    for host in ("169.254.169.254", "127.0.0.1"):
        with pytest.raises(Refused):
            X.set_config(plane, ADMIN, "webhook", "SH_OUT_WEBHOOK", host)


def test_the_preview_line_uses_the_reporting_month_not_the_first_row():
    """V6 (walk gap 11): October's row came first and stood in for September's report."""
    rows = [{"month": "2026-10-31", "ret": 1}, {"month": "2026-09-30", "ret": 2}]
    assert X._row_for(rows, ["month", "ret"], "2026-09")["ret"] == 2
    assert X._row_for(rows, ["month", "ret"], None)["ret"] == 1 and X._row_for(rows, ["month", "ret"], "2025-01")["ret"] == 1
    assert X._row_for(rows, ["name", "ret"], "2026-09")["ret"] == 1   # no month column: the first row, as before
