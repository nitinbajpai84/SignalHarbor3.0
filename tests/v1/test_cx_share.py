"""C3: a card per audience member with access, none without access, once per refresh; group members count."""
import json
from datetime import datetime, timezone

import pytest

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import cx_share as S
from sh_platform.v1 import e5_pulse as P
from sh_platform.v1 import wh
from sh_platform.v1.e1_write import org_id

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
U = {k: wh.new_id() for k in ("cio", "fin", "out")}
ENT, GRP = wh.new_id(), wh.new_id()


def ins(con, table, **row):
    con.execute(f"insert into {table} ({', '.join(row)}) values ({', '.join('?' * len(row))})", list(row.values()))


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    pl = PlaneStore(tmp_path / "data").create("acme")
    org = org_id(pl)
    with wh.connect(pl) as con:
        for k, name, role in (("cio", "Priya Nair", "CIO"), ("fin", "Fiona Lee", "Finance"), ("out", "Oscar Out", "Finance")):
            ins(con, "users", id=U[k], organization_id=org, external_identity_id="acc-" + k, display_name=name,
                email=k + "@x.test", business_role=role, is_active=True, created_at=NOW)
        ins(con, "legal_entities", id=ENT, organization_id=org, entity_code="EH", entity_name="Evergreen Holdings", base_currency="USD")
        ins(con, "access_groups", id=GRP, organization_id=org, group_name="Finance team")
        ins(con, "access_group_scopes", id=wh.new_id(), organization_id=org, access_group_id=GRP, scope_type="legal_entity",
            scope_value=ENT, access_level="read")
        for k in ("cio", "fin"):
            ins(con, "access_group_memberships", id=wh.new_id(), organization_id=org, access_group_id=GRP, user_id=U[k], granted_at=NOW)
    d = pl.root / "consume" / "EV-0001" / "dashboards"
    d.mkdir(parents=True)
    (d / "d1.json").write_text(json.dumps({"id": "d1", "title": "September dashboard", "project_id": "EV-0001", "tiles": [{"id": "t1"}, {"id": "t2"}],
                                           "audience": [U["cio"], GRP, U["out"]], "refresh": "same", "created_by": "Mei Tan",
                                           "updated_at": "2026-10-09T08:00:00Z"}), encoding="utf-8")
    return pl


def test_card_per_member_with_access_only(plane):
    r = S.notify(plane, "EV-0001", "d1", "refreshed", tiles_changed=2)
    assert sorted(r["made"]) == ["Fiona Lee", "Priya Nair"] and r["skipped_no_access"] == ["Oscar Out"]
    cio = P.items(plane, Viewer("Priya Nair", frozenset(), False, "acc-cio"))
    assert [c["headline"] for c in cio if c["kind"] == "dashboard"] == ["September dashboard refreshed · 2 tiles changed"]
    assert P.items(plane, Viewer("Oscar Out", frozenset(), False, "acc-out")) == []


def test_once_per_refresh(plane):
    S.notify(plane, "EV-0001", "d1", "refreshed", token="r1")
    again = S.notify(plane, "EV-0001", "d1", "refreshed", token="r1")
    assert again["made"] == [] and len(again["already"]) == 2
    assert len(S.notify(plane, "EV-0001", "d1", "refreshed", token="r2")["made"]) == 2
