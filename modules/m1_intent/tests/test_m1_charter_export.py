"""Download of the signed charter (HTML and Markdown) and the ready email for the people who took part. Built from the
charter screen's own view; nothing is sent. Family-office example text only."""
import pytest

from m1_kit import BASE
from modules.m1_intent.domain import charter_export as X
from test_m1_charter_kit import charter, draft, ready, second_signer, stand_in_result  # noqa: F401  (the autouse fixture)
from test_m1_room_kit import guest, hdr, seat_in

SECRET = "Private room thought nobody may see"


def signed(world, seats=3, guest_seat=None):
    org, sid, code = ready(world, seats=seats)
    token = seat_in(world, guest(world), code, guest_seat, name="Sara Guest")[0] if guest_seat else None
    draft(org, sid)
    assert org.post(f"{BASE}/sessions/{sid}/charter/sign").status_code == 200
    two = second_signer(world, "co-a", code)
    assert two.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]["status"] == "signed"
    return org, sid, code, two, token


def files(c, sid, **kw):
    r = c.get(f"{BASE}/sessions/{sid}/charter/download", **kw)
    assert r.status_code == 200, r.text
    return {f["format"]: f for f in r.json()["files"]}


def test_the_download_holds_exactly_what_the_charter_screen_shows(world):
    org, sid, _, _, _ = signed(world)
    view = charter(org, sid)["charter"]
    f = files(org, sid)
    assert f["html"]["filename"].endswith(".html") and f["markdown"]["filename"].endswith(".md")
    for p in view["problems"]:
        for text in (p["title"], p["priority_label"] or ""):
            assert text in f["html"]["content"] and text in f["markdown"]["content"]
        if p["so_that"]:
            assert X.with_so_that(p["so_that"]) in f["html"]["content"]
    for s in view["signing"]["signers"]:
        assert s["name"] in f["html"]["content"] and s["at"][:10] in f["markdown"]["content"]
    assert view["footer"]["date"] in f["html"]["content"]
    assert "Illustrative" not in f["html"]["content"]  # the test company is not a demo one
    assert "<!doctype html>" in f["html"]["content"]


def test_a_demo_company_is_tagged_illustrative_and_text_is_escaped():
    view = {"footer": {"date": "2026-10-04", "participants": 3, "notes": 2, "later": 0}, "later": [], "alone": [{"text": None}, {"text": "<b>x</b>"}],
            "problems": [{"title": "A <i>problem</i>", "priority_label": "Must", "tie": None, "so_that": "we plan"}],
            "signing": {"signers": [{"name": "Pat Lee", "at": "2026-10-04T09:00:00+00:00"}]}}
    html = X.to_html(view, "Illustrative Lakeside Family Office", "Session", True)
    assert 'class="tag">Illustrative' in html and "<i>problem" not in html and "&lt;b&gt;x&lt;/b&gt;" in html and X.ANON in html
    assert "(Illustrative)" in X.to_markdown(view, "Illustrative Lakeside Family Office", "Session", True)


def test_a_seated_guest_downloads_and_a_stranger_does_not(world):
    org, sid, code = ready(world, seats=3)
    token, _ = seat_in(world, guest(world), code, 1, name="Sara Guest")
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    second_signer(world, "co-a", code).post(f"{BASE}/sessions/{sid}/charter/sign")
    g = guest(world)
    assert files(g, sid, headers=hdr(token))["html"]["content"] == files(org, sid)["html"]["content"]
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter/download").status_code == 401
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter/download", headers=hdr("garbage")).status_code == 401
    other = world.login("other-co", "co-b", ["company_admin"])
    assert other.get(f"{BASE}/sessions/{sid}/charter/download").status_code in (403, 404)


def test_before_signing_the_download_is_a_plain_409(world):
    org, sid, _ = ready(world)
    assert org.get(f"{BASE}/sessions/{sid}/charter/download").status_code == 409  # no charter yet
    draft(org, sid)
    r = org.get(f"{BASE}/sessions/{sid}/charter/download")
    assert r.status_code == 409 and r.json()["error"] == "wrong_state" and "signed" in r.json()["message"]
    assert org.get(f"{BASE}/sessions/{sid}/charter/email").status_code == 409


def test_the_email_is_for_the_organiser_only_and_holds_no_private_text(world):
    org, sid, code, two, token = signed(world, guest_seat=3)
    r = org.get(f"{BASE}/sessions/{sid}/charter/email")
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["subject"] and "Capital calls arrive too late" in e["body"] and e["link_path"] in e["body"]
    assert SECRET not in r.text
    by_name = {p["name"]: p["email"] for p in e["people"]}
    assert by_name["Second Signer"] and "@" in by_name["Second Signer"] and by_name["Sara Guest"] is None
    # a signer who did not organise, and a guest, are refused
    assert two.get(f"{BASE}/sessions/{sid}/charter/email").status_code in (403, 404)
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter/email", headers=hdr(token)).status_code == 403
    assert guest(world).get(f"{BASE}/sessions/{sid}/charter/email").status_code in (401, 403)


# ---- hardening: hostile text, expired token, other company, anonymous notes
NASTY = [{"id": "c1", "title": "Late calls <script>alert(1)</script> \"x\"\n# Signed by\n- Fake Person", "priority": "must", "note_count": 1, "agree_count": 1,
          "ticked": True, "so_that": "we see <script>1</script> \"q\" *bold*", "library_problem_id": None}]


def nasty_signed(world, monkeypatch):
    from test_m1_charter_kit import put_result
    monkeypatch.setattr("modules.m1_intent.api.charter.notes_on_their_own", lambda plane, sid: [{"text": None}, {"text": "Plain <b>note</b>"}])
    org, sid, code = ready(world, seats=3, purpose="Plan <script>\nBcc: evil@example.test\n# Heading")
    put_result(world, "co-a", sid, NASTY)
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    two = second_signer(world, "co-a", code)
    assert two.post(f"{BASE}/sessions/{sid}/charter/sign").json()["charter"]["status"] == "signed"
    return org, sid


def test_hostile_text_is_escaped_in_html_and_cannot_fake_markdown_structure(world, monkeypatch):
    org, sid = nasty_signed(world, monkeypatch)
    f = files(org, sid)
    assert "<script>" not in f["html"]["content"] and "&lt;script&gt;" in f["html"]["content"]
    md = f["markdown"]["content"]
    assert "<script>" not in md and "\n# Signed by" not in md and "\n- Fake Person" not in md
    assert md.count("## Signed by") == 1 and "\n# Heading" not in md
    assert X.ANON in f["html"]["content"] and X.ANON in md and "Plain &lt;b&gt;note&lt;/b&gt;" in f["html"]["content"]


def test_the_email_subject_and_body_are_one_line_safe_and_capped(world, monkeypatch):
    org, sid = nasty_signed(world, monkeypatch)
    e = org.get(f"{BASE}/sessions/{sid}/charter/email").json()
    assert "\n" not in e["subject"] and "\r" not in e["subject"] and len(e["subject"]) <= 120
    assert "\r" not in e["body"] and "\n# Signed by" not in e["body"] and "\nBcc:" not in e["body"]
    assert len(X.one_line("a " * 500, 80)) <= 80


def test_an_expired_guest_token_gets_no_download(world):
    import time
    org, sid, code = ready(world, seats=3)
    token, _ = seat_in(world, guest(world), code, 1, name="Sara Guest")
    draft(org, sid)
    org.post(f"{BASE}/sessions/{sid}/charter/sign")
    now = [time.time()]
    world.app.state.m1_clock = lambda: now[0]
    second_signer(world, "co-a", code).post(f"{BASE}/sessions/{sid}/charter/sign")
    g = guest(world)
    assert g.get(f"{BASE}/sessions/{sid}/charter/download", headers=hdr(token)).status_code == 200
    now[0] += 31 * 86400
    assert g.get(f"{BASE}/sessions/{sid}/charter/download", headers=hdr(token)).status_code == 401


def test_another_companys_admin_gets_no_email(world):
    org, sid, _, _, _ = signed(world)
    other = world.login("other-admin", "co-b", ["company_admin"])
    assert other.get(f"{BASE}/sessions/{sid}/charter/email").status_code in (403, 404)
