"""A19: market briefs from the industry pack. Synthetic packs in a temporary folder."""
import yaml

from sh_platform.consume.market import briefs_for
from sh_platform.packs import PackLoader


def pack(root, brief: str | None):
    d = root / "demo_co" / "1"
    (d / "market_briefs").mkdir(parents=True)
    (d / "pack.yaml").write_text("label: Demo\n", encoding="utf-8")
    (d / "kpi_tree.yaml").write_text(yaml.safe_dump({"kpis": [{"id": "K01", "name": "Funding headroom"}, {"id": "K02", "name": "Retention"}]}), encoding="utf-8")
    if brief:
        (d / "market_briefs" / "sg.md").write_text(brief, encoding="utf-8")
    return PackLoader(root)


def test_briefs_come_from_the_pack(tmp_path):
    loader = pack(tmp_path, "<!-- note -->\n# Singapore brief\n\nDated: 2026-10-02.\n\nRates moved.\nSecond line.\n\nMore.\n")
    (b,) = briefs_for(loader, "demo_co")
    assert (b["id"], b["title"], b["summary"], b["outside"]) == ("sg", "Singapore brief", "Rates moved. Second line.", True)
    assert "Demo" in b["source"]


def test_measures_are_matched_by_code_name_or_front_matter(tmp_path):
    loader = pack(tmp_path, "---\nmeasures: [K02]\n---\n# T\n\nFunding headroom is tight; see K01x.\n")
    assert briefs_for(loader, "demo_co")[0]["measures"] == ["K01", "K02"]
    loader = pack(tmp_path / "b", "# T\n\nSee K01 only.\n")
    assert briefs_for(loader, "demo_co")[0]["measures"] == ["K01"]


def test_no_pack_or_no_briefs_gives_empty(tmp_path):
    assert briefs_for(PackLoader(tmp_path), "nothing") == [] and briefs_for(PackLoader(tmp_path), None) == []
    assert briefs_for(pack(tmp_path / "c", None), "demo_co") == []


# -- second pass: internet, hand-added briefs, measures that moved
import json
from datetime import datetime, timezone

from sh_platform.consume import market_store
from sh_platform.consume.market import add_brief, market_doc
from sh_platform.egress.gateway import Reply
from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer

ADMIN = Viewer("Ann Admin", frozenset({"company_admin"}))
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)


class Gate:
    def __init__(self):
        self.calls = []

    def internet_query(self, module_id, destination, query_text, suppressed=None):
        self.calls.append((destination, query_text))
        return Reply("Rates are steady.", outside=True)


def with_sources(root):
    loader = pack(root, "# T\n\nSee K01.\n")
    (root / "demo_co" / "1" / "market_sources.yaml").write_text(
        yaml.safe_dump({"sources": [{"name": "Rates desk", "covers": "policy rates", "url": "https://rates.example.test/brief"}]}), encoding="utf-8")
    return PackLoader(root)


def test_internet_off_gives_pack_only_with_the_line(tmp_path):
    plane = PlaneStore(tmp_path / "d").create("lakeside-family-office")
    doc = market_doc(plane, ADMIN, with_sources(tmp_path / "p"), "demo_co", internet=False, gateway=Gate(), now=NOW)
    assert [b["id"] for b in doc["briefs"]] == ["sg"] and "off for this company" in doc["internet_line"] and "fetched_at" not in doc


def test_admin_added_brief_is_stored_labelled_and_listed(tmp_path):
    plane = PlaneStore(tmp_path / "d").create("lakeside-family-office")
    add_brief(plane, "Our view", "Funding is tight.", ["K01"], "Ann Admin")
    assert json.loads(plane.path("market", "briefs.json").read_text(encoding="utf-8"))["added"][0]["title"] == "Our view"
    doc = market_doc(plane, ADMIN, with_sources(tmp_path / "p"), "demo_co", internet=False, now=NOW)
    b = doc["briefs"][-1]
    assert (b["source"], b["measures"], b["outside"]) == ("added by Ann Admin", ["K01"], True)


def test_fetched_brief_is_labelled_and_cached_for_a_day(tmp_path):
    plane, gate, loader = PlaneStore(tmp_path / "d").create("lakeside-family-office"), Gate(), with_sources(tmp_path / "p")
    doc = market_doc(plane, ADMIN, loader, "demo_co", internet=True, gateway=gate, now=NOW)
    web = doc["briefs"][-1]
    assert (web["fetched"], web["outside"], web["summary"], doc["fetched_at"][:10]) == (True, True, "Rates are steady.", "2026-10-06")
    assert "Funding" not in gate.calls[0][1] and "internet_line" not in doc
    market_doc(plane, ADMIN, loader, "demo_co", internet=True, gateway=gate, now=NOW.replace(hour=20))
    assert len(gate.calls) == 1 and market_store.cached_fetch(plane, NOW) is not None
    market_doc(plane, ADMIN, loader, "demo_co", internet=True, gateway=gate, now=NOW.replace(day=8))
    assert len(gate.calls) == 2


def test_brief_text_is_plain_and_moved_falls_back_to_latest_month(tmp_path, monkeypatch):
    from sh_platform.consume import market as m
    loader = pack(tmp_path / "p", "# A -- B\n\nDated: 2026-10-02.\n\n- **Rates** -- steady.\n- **FX** -- calm.\n")
    plane = PlaneStore(tmp_path / "d").create("lakeside-family-office")
    monkeypatch.setattr(m, "_moved", lambda *a: [{"code": "K02", "name": "Retention", "month": "2026-09"}])
    b = market_doc(plane, ADMIN, loader, "demo_co", internet=False, now=NOW)["briefs"][0]
    assert (b["title"], b["summary"]) == ("A: B", "Rates: steady. FX: calm.")
    assert b["moved"] == [{"code": "K02", "name": "Retention"}] and b["moved_month"] == "2026-09"


def test_each_named_measure_carries_its_latest_move_or_none(tmp_path, monkeypatch):
    from sh_platform.consume import feeds
    loader = pack(tmp_path / "p", "# T\n\nSee K01 and K02.\n")
    plane = PlaneStore(tmp_path / "d").create("lakeside-family-office")
    trend = [{"period": "2026-08", "value": 200.0}, {"period": "2026-09", "value": 210.0}]
    monkeypatch.setattr(feeds, "build", lambda *a, **k: {"measures": [{"code": "K01", "name": "Funding headroom", "trend": trend, "latest": trend[-1], "range_break": False}]})
    b = market_doc(plane, ADMIN, loader, "demo_co", internet=False, now=NOW)["briefs"][0]
    assert b["measure_moves"] == [{"code": "K01", "name": "Funding headroom", "latest_move": {"period": "2026-09", "from": 200.0, "to": 210.0, "change_pct": 5.0}},
                                  {"code": "K02", "name": "Retention", "latest_move": None}]
