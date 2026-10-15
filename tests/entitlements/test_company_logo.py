"""A company's logo: served from its own plane only, never another company's; a missing logo is a plain 404."""
import pytest
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"></svg>'


def put_logo(kit, company, name, data):
    plane = kit.store._planes.plane_for(company)
    (plane.root / "brand").mkdir(exist_ok=True)
    (plane.root / "brand" / name).write_bytes(data)


@pytest.fixture
def two(kit):
    kit.store.create_company("co-x", "Illustrative Harbour Office", "industry_a", package="discover",
                             brand={"logo": "logo.svg", "primary_colour": "#123456"})
    kit.store.create_company("co-y", "Other Office", "industry_a", package="discover")
    put_logo(kit, "co-x", "logo.svg", SVG)
    return kit


def test_own_logo_is_served_with_safe_headers(two):
    r = two.login("x", "co-x", ["analyst"]).get("/api/company/logo")
    assert r.status_code == 200 and r.content == SVG and r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["x-content-type-options"] == "nosniff" and "default-src 'none'" in r.headers["content-security-policy"]


def test_company_route_carries_brand_only_when_set(two):
    assert two.login("x", "co-x", ["analyst"]).get("/api/company").json()["brand"] == {
        "logo": "logo.svg", "primary_colour": "#123456"}
    assert "brand" not in two.login("y", "co-y", ["analyst"]).get("/api/company").json()


def test_another_company_cannot_fetch_it_and_the_request_cannot_choose_a_company_or_path(two):
    y = two.login("y", "co-y", ["analyst"])
    for kw in ({}, {"params": {"company_id": "co-x", "path": "../co-x/brand/logo.svg"}}, {"headers": {"x-company-id": "co-x"}}):
        assert y.get("/api/company/logo", **kw).status_code == 404


def test_no_logo_file_or_record_is_a_404_and_signed_out_is_refused(two):
    assert two.login("y2", "co-y", ["participant"]).get("/api/company/logo").status_code == 404
    two.store.set_brand("co-y", {"logo": "logo.png"})  # recorded but no file
    assert two.login("y3", "co-y", ["analyst"]).get("/api/company/logo").status_code == 404
    assert TestClient(two.app).get("/api/company/logo").status_code == 401


def test_oversize_or_wrong_content_is_not_served(two):
    put_logo(two, "co-x", "logo.svg", SVG + b" " * (512 * 1024))
    x = two.login("x", "co-x", ["analyst"])
    assert x.get("/api/company/logo").status_code == 404
    two.store.set_brand("co-x", {"logo": "logo.png"})
    put_logo(two, "co-x", "logo.png", b"<html>not a png</html>")
    assert x.get("/api/company/logo").status_code == 404
    put_logo(two, "co-x", "logo.png", PNG)
    r = x.get("/api/company/logo")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


@pytest.mark.parametrize("brand", [{"logo": "../x.png"}, {"logo": "logo.exe"}, {"primary_colour": "red"}, {"other": 1}, "x"])
def test_bad_brand_is_refused(kit, brand):
    with pytest.raises(ValueError):
        kit.store.create_company("co-z", "Z", "industry_a", brand=brand)
