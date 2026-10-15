"""N2 comments: add, reply, edit and delete keep history; @mention reaches Today only for a person who may see the thing; raise as a case or ticket
links both ways; a person without access sees nothing and can change nothing. Routes are declared."""
import re
from datetime import date
from pathlib import Path

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e4_cases, e5_pulse, wh
from sh_platform.v1 import n2_comments as N
from sh_platform.v1.e1_write import org_id

P1 = "00000000-0000-4000-8000-000000000001"
MEI = Viewer("Mei Tan", frozenset({"analyst"}), False, "a-mei")
RAJ = Viewer("Raj Iyer", frozenset({"approver"}), False, "a-raj")
RINA = Viewer("Rina Rao", frozenset({"participant"}), False, "a-rina")
ADMIN = Viewer("Arjun Mehta", frozenset({"company_admin"}), False, "a-arjun")
LINE = f"{P1}/fund-a"
TODAY = date(2026, 10, 10)


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    wh.reset_cache()
    from sh_platform.v1 import a5_trail, cx_dash, e1_access

    def seen(v):
        return v.name in ("Mei Tan", "Raj Iyer")

    monkeypatch.setattr(e1_access, "level", lambda plane, viewer, entity_id=None, portfolio_id=None: "full" if e1_access.is_admin(viewer) else "read" if seen(viewer) and portfolio_id == P1 else "none")
    monkeypatch.setattr(e1_access, "visible_portfolios", lambda plane, viewer: {P1} if seen(viewer) else set())
    rec = {"id": "dash-1", "created_by": "a-mei", "audience": [], "lifecycle": {}, "tiles": [{"id": "t1"}]}
    monkeypatch.setattr(cx_dash, "find_pid", lambda plane, did: "p1")
    monkeypatch.setattr(cx_dash, "_load", lambda plane, pid, did: rec)
    monkeypatch.setattr(cx_dash, "may_view", lambda plane, viewer, r: seen(viewer) or e1_access.is_admin(viewer))
    monkeypatch.setattr(cx_dash, "_has_data", lambda plane, viewer: False)

    def trail(plane, viewer, kind, item_id):
        if not (seen(viewer) or e1_access.is_admin(viewer)):
            raise PermissionError
        return {}
    monkeypatch.setattr(a5_trail, "trail", trail)
    plane = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(plane) as con:
        for v in (MEI, RAJ, RINA, ADMIN):
            con.execute("insert into users (id, organization_id, external_identity_id, display_name, email, is_active, created_at) values (?,?,?,?,?,?,?)",
                        [wh.new_id(), org_id(plane), v.account_id, v.name, v.account_id + "@example.test", True, wh.now()])
    return plane


def texts(plane, viewer, kind="office_line", item=LINE):
    return [c["text"] for c in N.thread(plane, viewer, kind, item)["comments"]]


def on_today(plane, viewer):
    return [i for i in e5_pulse.items(plane, viewer, TODAY) if i["kind"] == "comment"]


def test_comment_and_reply(plane):
    c = N.add(plane, MEI, "office_line", LINE, "Why did this move?")["id"]
    N.add(plane, RAJ, "office_line", LINE, "Revised estimate.", parent_id=c)
    t = N.thread(plane, RAJ, "office_line", LINE)
    assert [x["parent_id"] for x in t["comments"]] == [None, c] and t["count"] == 2
    assert t["comments"][0]["may"]["edit"] is False
    assert N.thread(plane, MEI, "office_line", LINE)["comments"][0]["may"]["edit"] is True


def test_edit_keeps_history_and_only_author_edits(plane):
    c = N.add(plane, MEI, "office_line", LINE, "First wording")["id"]
    with pytest.raises(N.Refused) as e:
        N.edit(plane, RAJ, c, "Hijack")
    assert e.value.status == 403
    row = N.edit(plane, MEI, c, "Second wording")["thread"]["comments"][0]
    assert row["text"] == "Second wording" and row["edited"] and [h["text"] for h in row["history"]] == ["First wording"]
    assert N.edit(plane, MEI, c, "Third")["thread"]["comments"][0]["history"][1]["text"] == "Second wording"
    assert sum(1 for e in N.events(plane) if e["event"] in ("add", "edit")) == 3  # append-only: nothing was rewritten


def test_delete_shows_who_and_hides_words_but_keeps_them(plane):
    c = N.add(plane, MEI, "office_line", LINE, "Secret figure 123")["id"]
    with pytest.raises(N.Refused) as e:
        N.delete(plane, RAJ, c)  # not the author, not an admin
    assert e.value.status == 403
    row = N.delete(plane, ADMIN, c)["thread"]["comments"][0]
    assert row["deleted"] and row["deleted_by"] == "Arjun Mehta" and row["text"] is None and row["history"] == []
    assert N.thread(plane, MEI, "office_line", LINE)["count"] == 0
    assert any(e["event"] == "add" and e["text"] == "Secret figure 123" for e in N.events(plane))
    with pytest.raises(N.Refused) as e:
        N.edit(plane, MEI, c, "again")
    assert e.value.status == 409
    c2 = N.add(plane, MEI, "office_line", LINE, "mine")["id"]
    assert N.delete(plane, MEI, c2)["thread"]["comments"][1]["deleted_by"] == "Mei Tan"


@pytest.mark.parametrize("kind,item", [("office_line", LINE), ("brief_line", LINE), ("dashboard", "dash-1"), ("widget", "dash-1/t1"),
                                       ("valuation", "v1"), ("metric", "m1"), ("tile", "t1")])
def test_person_without_access_sees_and_does_nothing(plane, kind, item):
    c = N.add(plane, MEI, kind, item, "Private note")["id"]
    for call in (lambda: N.thread(plane, RINA, kind, item), lambda: N.add(plane, RINA, kind, item, "hi"),
                 lambda: N.edit(plane, RINA, c, "x"), lambda: N.delete(plane, RINA, c), lambda: N.raise_as(plane, RINA, c)):
        with pytest.raises(N.Refused) as e:
            call()
        assert e.value.status == 403 and "Private" not in e.value.message
    assert texts(plane, MEI, kind, item) == ["Private note"]


def test_company_line_needs_every_portfolio(plane):
    assert N.add(plane, ADMIN, "brief_line", "company/total", "Total looks high")
    with pytest.raises(N.Refused):
        N.thread(plane, RAJ, "brief_line", "company/total")  # a partial view of the company is not enough


def test_bad_kind_and_empty_text(plane):
    with pytest.raises(N.Refused) as e:
        N.thread(plane, MEI, "invoice", "1")
    assert e.value.status == 400
    with pytest.raises(N.Refused):
        N.add(plane, MEI, "office_line", LINE, "   ")
    with pytest.raises(N.Refused):
        N.add(plane, MEI, "office_line", "not-a-line", "x")


def test_case_thread_follows_case_access(plane):
    cid = e4_cases.open(plane, {"exception_type": "revision", "title": "Fund A", "portfolio_id": P1, "actor": ADMIN})
    N.add(plane, MEI, "case", "CASE-0001", "On it")  # reached by number, stored by id
    assert texts(plane, RAJ, "case", cid) == ["On it"]
    with pytest.raises(N.Refused) as e:
        N.thread(plane, RINA, "case", cid)
    assert e.value.status == 403


def test_mention_reaches_today_only_with_access(plane):
    r = N.add(plane, MEI, "office_line", LINE, "@Raj Iyer please check, @Rina Rao fyi")
    assert r["not_told"] == ["Rina Rao"] and r["thread"]["comments"][0]["mentions"] == ["Raj Iyer", "Rina Rao"]
    e5_pulse.generate(plane, TODAY)
    raj = on_today(plane, RAJ)
    assert len(raj) == 1 and "Mei Tan" in raj[0]["headline"] and "check" not in raj[0]["text"]  # the words stay in the thread
    assert on_today(plane, RINA) == [] and on_today(plane, MEI) == []
    N.add(plane, MEI, "office_line", LINE, "Self mention: @Mei Tan is me")  # nobody is told
    e5_pulse.generate(plane, TODAY)
    assert len(on_today(plane, RAJ)) == 1 and on_today(plane, MEI) == []


def test_edit_tells_only_new_mentions_and_delete_withdraws(plane):
    c = N.add(plane, MEI, "office_line", LINE, "@Raj Iyer look")["id"]
    N.edit(plane, MEI, c, "@Raj Iyer look again @Arjun Mehta")
    e5_pulse.generate(plane, TODAY)
    assert len(on_today(plane, RAJ)) == 1  # not told twice
    assert on_today(plane, ADMIN) == [] or len(on_today(plane, ADMIN)) == 1  # Arjun is an admin and sees all: told once at most
    N.delete(plane, MEI, c)
    assert N.pulse_cards(plane, None, TODAY) == []


def test_raise_as_case_links_both_ways(plane):
    c = N.add(plane, MEI, "office_line", LINE, "This value looks wrong")["id"]
    out = N.raise_as(plane, MEI, c, "case")
    ref, row = out["case"], out["thread"]["comments"][0]
    assert row["case"]["number"] == "CASE-0001" and row["case"]["link"] == f"/centre/desk/{ref['id']}" and row["may"]["raise"] is False
    hist = e4_cases.get(plane, ref["id"], RAJ)["history"]  # Raj sees the portfolio, so the case
    assert any(h["event_type"] == "comment" and "This value looks wrong" in h["text"] for h in hist)
    with pytest.raises(e4_cases.Refused):
        e4_cases.get(plane, ref["id"], RINA)
    with pytest.raises(N.Refused) as e:
        N.raise_as(plane, MEI, c, "case")
    assert e.value.status == 409
    assert N.thread(plane, RAJ, "office_line", LINE)["comments"][0]["case"]["id"] == ref["id"]


def test_raise_as_ticket(plane):
    c = N.add(plane, MEI, "dashboard", "dash-1", "The title is misspelt")["id"]
    out = N.raise_as(plane, MEI, c, "ticket")
    assert out["ticket"]["number"].startswith("TCK-") and out["thread"]["comments"][0]["ticket"]["id"] == out["ticket"]["id"]
    d = N.add(plane, MEI, "dashboard", "dash-1", "gone")["id"]
    N.delete(plane, MEI, d)
    with pytest.raises(N.Refused) as e:
        N.raise_as(plane, MEI, d)
    assert e.value.status == 409
    with pytest.raises(N.Refused) as e:
        N.raise_as(plane, MEI, c, "wish")
    assert e.value.status == 400


def test_routes_are_declared():
    from sh_platform.v1 import n2_routes
    declared = Path(n2_routes.__file__).with_name("n2.permissions.yaml").read_text(encoding="utf-8")
    for r in n2_routes.router.routes:
        for m in r.methods - {"HEAD", "OPTIONS"}:
            assert re.search(rf"^\s+{m} {re.escape(r.path)}:", declared, re.M), (m, r.path)


def test_ticket_never_goes_to_a_person_who_cannot_see(plane):
    from sh_platform.v1 import t2_tickets
    c = N.add(plane, MEI, "office_line", LINE, "@Rina Rao and @Raj Iyer please look")["id"]
    tid = N.raise_as(plane, MEI, c, "ticket")["ticket"]["id"]
    t = next(t for t in t2_tickets.all_tickets(plane) if t["id"] == tid)
    assert t["assigned_to"] == "Raj Iyer"  # Rina is named first but cannot see the line, so the words never go to her


def test_mention_card_reads_plainly(plane):
    N.add(plane, MEI, "office_line", LINE, "@Raj Iyer see this")
    body = on_today(plane, RAJ)[0]
    assert " a office" not in str(body)
