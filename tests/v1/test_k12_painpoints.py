"""W2 pain-point demo: the sample file is valid and honest, a local file wins, bad files are refused, the route reads only."""
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.v1 import k12_painpoints as P

ITEM = {"id": "X1", "cluster": "C", "title": "t", "severity": "low", "does": "d", "coverage": "strong", "use_case": "u", "link": "/centre/consume"}


def put(root, name, items):
    d = root / "local" / "painpoints"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(yaml.safe_dump({"painpoints": items}), encoding="utf-8")


def test_sample_is_valid_and_honest():
    r = P.load()
    assert r["source"] == "sample" and r["total"] == sum(r["counts"].values()) >= 6
    assert all(v for v in r["counts"].values())  # strong, partial and not in scope all appear
    for g in r["clusters"]:
        for i in g["items"]:
            assert i["coverage"] != "not_in_scope" or (i["reason"] and not i["link"])
            assert i["coverage"] == "not_in_scope" or i["link"].startswith("/centre/")
    assert "portfolio data management system" in str(r)


def test_sample_has_no_vendor_or_client_names():
    text = P.SAMPLE.read_text(encoding="utf-8").lower()
    assert not any(w in text for w in ("bloomberg", "addepar", "clearwater", "advent", "evergreen"))


def test_local_wins_and_groups_in_order(tmp_path):
    put(tmp_path, "acme", [ITEM, {**ITEM, "id": "X2", "cluster": "D"}, {**ITEM, "id": "X3"}])
    r = P.load("acme", tmp_path)
    assert r["source"] == "local" and [g["cluster"] for g in r["clusters"]] == ["C", "D"] and len(r["clusters"][0]["items"]) == 2


def test_missing_name_falls_back_to_sample(tmp_path):
    (tmp_path / "packs/family_office/1").mkdir(parents=True)
    (tmp_path / "packs/family_office/1/painpoints_sample.yaml").write_text(P.SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    assert P.load("nobody", tmp_path)["source"] == "sample"


@pytest.mark.parametrize("bad", [
    {"coverage": "great"}, {"severity": "huge"}, {"coverage": "not_in_scope"}, {"link": "https://elsewhere.example/x"}, {"link": "//elsewhere.example"}, {"title": ""},
])
def test_bad_item_refused(tmp_path, bad):
    put(tmp_path, "b", [{**ITEM, **bad}])
    with pytest.raises(ValueError):
        P.load("b", tmp_path)


def test_duplicate_ids_and_traversal_refused(tmp_path):
    put(tmp_path, "d", [ITEM, ITEM])
    with pytest.raises(ValueError):
        P.load("d", tmp_path)
    with pytest.raises(ValueError):
        P.load("../x", tmp_path)


def test_route(monkeypatch):
    monkeypatch.setattr(P, "viewer_of", lambda request: object())
    app = FastAPI()
    app.include_router(P.router)
    c = TestClient(app)
    assert c.get("/api/v1/demo/painpoints").json()["source"] == "sample"
    assert c.get("/api/v1/demo/painpoints?name=../x").status_code == 400
    assert c.post("/api/v1/demo/painpoints").status_code == 405


def test_permissions_file_declares_the_route():
    y = yaml.safe_load((P.Path(P.__file__).parent / "k12.permissions.yaml").read_text(encoding="utf-8"))
    assert list(y["routes"]) == ["GET /api/v1/demo/painpoints"]
