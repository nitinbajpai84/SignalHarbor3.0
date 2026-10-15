"""E1d access to structured data: a member sees only scoped entities, a non-member none, expiry is ignored, the admin sees all,
a portfolio scope reaches its portfolio only, failure closes, admin changes are logged."""
from datetime import datetime, timedelta, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e1_access as A
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

ADMIN = Viewer("Arjun", frozenset({"company_admin"}), False, "acc-a")
MEI = Viewer("Mei", frozenset({"analyst"}), False, "acc-m")
RAJ = Viewer("Raj", frozenset({"analyst"}), False, "acc-r")
STRANGER = Viewer("Nobody", frozenset({"participant"}), False, "acc-x")
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_MODEL_PROVIDER", "off")
    wh.reset_cache()
    plane = PlaneStore(tmp_path).create("evergreen")
    org = org_id(plane)
    ids = {k: wh.new_id() for k in ("holdings", "trust", "p1", "p2", "p3", "mei", "raj", "adm")}
    with wh.connect(plane) as con:
        con.execute("insert into organizations values (?,?,?)", [org, "Evergreen", NOW])
        for k, acc, name in (("mei", "acc-m", "Mei"), ("raj", "acc-r", "Raj"), ("adm", "acc-a", "Arjun")):
            con.execute("insert into users values (?,?,?,?,?,?,?,?)", [ids[k], org, acc, name, f"{k}@x.test", None, True, NOW])
        for k, code in (("holdings", "H"), ("trust", "T")):
            con.execute("insert into legal_entities values (?,?,?,?,?,?,?)", [ids[k], org, code, code, "USD", None, None])
        for k, ent in (("p1", "holdings"), ("p2", "holdings"), ("p3", "trust")):
            con.execute("insert into portfolios values (?,?,?,?,?,?,?,?)", [ids[k], org, ids[ent], k, k, "USD", None, None])
    return plane, ids


def test_member_sees_only_scoped_entities(world):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    A.add_member(plane, ADMIN, g, ids["mei"])
    A.add_scope(plane, ADMIN, g, "legal_entity", ids["holdings"], "read")
    assert A.visible_entities(plane, MEI) == {ids["holdings"]}
    assert A.visible_portfolios(plane, MEI) == {ids["p1"], ids["p2"]}
    assert A.level(plane, MEI, entity_id=ids["holdings"]) == "read"
    assert A.level(plane, MEI, portfolio_id=ids["p1"]) == "read"
    assert A.level(plane, MEI, entity_id=ids["trust"]) == "none"
    assert A.level(plane, MEI, portfolio_id=ids["p3"]) == "none"
    assert A.level(plane, MEI) == "none"  # nothing named: closed
    assert A.visible_entities(plane, RAJ) == set()  # a user with no group


def test_portfolio_scope_and_best_level_wins(world):
    plane, ids = world
    g1, g2 = A.add_group(plane, ADMIN, "A"), A.add_group(plane, ADMIN, "B")
    for g in (g1, g2):
        A.add_member(plane, ADMIN, g, ids["raj"])
    A.add_scope(plane, ADMIN, g1, "portfolio", ids["p3"], "read")
    A.add_scope(plane, ADMIN, g2, "portfolio", ids["p3"], "full")
    A.add_scope(plane, ADMIN, g2, "portfolio", ids["p1"], "preview")  # preview never opens rows
    assert A.visible_portfolios(plane, RAJ) == {ids["p3"]}
    assert A.visible_entities(plane, RAJ) == {ids["trust"]}
    assert A.level(plane, RAJ, portfolio_id=ids["p3"]) == "full"
    assert A.level(plane, RAJ, portfolio_id=ids["p1"]) == "none"


def test_non_member_and_unknown_viewer_see_nothing(world):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    A.add_scope(plane, ADMIN, g, "legal_entity", ids["holdings"], "full")
    assert A.visible_entities(plane, STRANGER) == set()
    assert A.level(plane, STRANGER, entity_id=ids["holdings"]) == "none"


def test_expired_membership_is_ignored_and_removal_works(world):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    A.add_scope(plane, ADMIN, g, "legal_entity", ids["holdings"], "full")
    A.add_member(plane, ADMIN, g, ids["mei"], expires_at=NOW - timedelta(days=1))
    assert A.visible_entities(plane, MEI) == set()
    A.add_member(plane, ADMIN, g, ids["mei"], expires_at=NOW + timedelta(days=1))  # renewing replaces the old row
    assert A.visible_entities(plane, MEI) == {ids["holdings"]}
    assert A.remove_member(plane, ADMIN, g, ids["mei"]) is True
    assert A.visible_entities(plane, MEI) == set()
    assert A.remove_member(plane, ADMIN, g, ids["mei"]) is False


def test_admin_sees_all(world):
    plane, ids = world
    assert A.visible_entities(plane, ADMIN) == {ids["holdings"], ids["trust"]}
    assert A.visible_portfolios(plane, ADMIN) == {ids["p1"], ids["p2"], ids["p3"]}
    assert A.level(plane, ADMIN, entity_id=ids["trust"]) == "full"


def test_failure_closes(world, monkeypatch):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    A.add_member(plane, ADMIN, g, ids["mei"])
    A.add_scope(plane, ADMIN, g, "legal_entity", ids["holdings"], "full")
    monkeypatch.setattr(wh, "connect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert A.visible_entities(plane, MEI) == set()
    assert A.level(plane, MEI, entity_id=ids["holdings"]) == "none"


def test_admin_changes_are_validated_and_logged(world):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    with pytest.raises(ValueError):
        A.add_scope(plane, ADMIN, g, "country", "x", "full")
    with pytest.raises(ValueError):
        A.add_scope(plane, ADMIN, g, "portfolio", ids["p1"], "write")
    with pytest.raises(LookupError):
        A.add_member(plane, ADMIN, g, "no-such-user")
    A.add_member(plane, ADMIN, g, ids["mei"])
    groups = A.list_groups(plane)
    assert groups[0]["members"][0]["name"] == "Mei"
    log = plane.path("warehouse", "access_admin_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2 and '"add_member"' in log[1] and "Arjun" in log[1]


def test_account_id_that_matches_no_user_does_not_fall_back_to_the_name(world):
    plane, ids = world
    g = A.add_group(plane, ADMIN, "Ops")
    A.add_member(plane, ADMIN, g, ids["mei"])
    A.add_scope(plane, ADMIN, g, "legal_entity", ids["holdings"], "read")
    assert A.visible_entities(plane, Viewer("Mei", frozenset({"analyst"}), False, "acc-other")) == set()
    assert A.visible_entities(plane, Viewer("Mei", frozenset({"analyst"}), False, "")) == {ids["holdings"]}  # no account id: the name is used
