"""E2c: exact approved match, cleaned-name rule match proposes, ambiguous and unknown names propose nothing, a model pick is a proposal
with its agent run, approval needs the right seat and is never automatic, a second approval of the same name is refused, routes."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sh_platform.plane import PlaneStore
from sh_platform.profile.view import Viewer
from sh_platform.v1 import e2_match as M, wh
from sh_platform.v1.e1_write import org_id

U = lambda n: f"00000000-0000-0000-0000-{n:012d}"  # noqa: E731
S1, FA, FB, FC, FD, A1, P2 = U(1), U(11), U(12), U(13), U(14), U(21), U(22)

OPS = Viewer("Mei", frozenset({"analyst"}), False, "acc-mei")
CIO = Viewer("Priya", frozenset({"sponsor"}), False, "acc-priya")


@pytest.fixture()
def plane(tmp_path):
    wh.reset_cache()
    p = PlaneStore(tmp_path / "data").create("acme")
    with wh.connect(p) as con:
        con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type) values (?, ?, 'manager_email','Manager email','manager')", [S1, org_id(p)])
        for i, n in ((FA, "Evergreen Growth Fund I, L.P."), (FB, "Evergreen Income Fund II"), (FC, "Harbor Income Fund III"), (FD, "Harbor Income Fund IV")):
            con.execute("insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?, ?, ?, 'fund', now())", [i, org_id(p), n])
        con.execute("insert into instrument_identifiers values (?,?,?,?,'name','EG Growth Fund I',null,null,'approved',null,?,now())", [A1, org_id(p), FA, S1, U(99)])
    return p


def status(plane, ident):
    with wh.connect(plane) as con:
        return con.execute("select mapping_status, approved_by from instrument_identifiers where id = ?", [ident]).fetchone()


def count(plane):
    with wh.connect(plane) as con:
        return con.execute("select count(*) from instrument_identifiers").fetchone()[0]


def test_exact_approved_ignores_case_and_spacing(plane):
    r = M.resolve(plane, "  eg  GROWTH fund i ", S1)
    assert (r["instrument_id"], r["status"]) == (FA, "approved") and count(plane) == 1


def test_cleaned_name_rule_proposes_once(plane):
    r = M.resolve(plane, "Evergreen Income, Fund 2 (Class I)", S1)
    assert (r["instrument_id"], r["status"]) == (FB, "proposed") and status(plane, r["identifier_id"]) == ("proposed", None)
    assert M.resolve(plane, "Evergreen Income, Fund 2 (Class I)", S1)["identifier_id"] == r["identifier_id"] and count(plane) == 2


def test_ambiguous_and_unknown_propose_nothing(plane):
    assert M.normalise("Harbor Income Fund III") != M.normalise("Harbor Income Fund IV")
    r = M.resolve(plane, "Harbor Income Fund", S1)  # spelling is close to two instruments
    assert r["status"] == "unknown" and r["instrument_id"] is None and len(r["candidates"]) >= 2
    assert M.resolve(plane, "Zzz Quux", S1)["status"] == "unknown" and count(plane) == 1


def test_model_pick_is_a_proposal_with_its_run(plane, monkeypatch):
    monkeypatch.setattr(M, "_ask_model", lambda model, p, value, cands: (FC, U(77)))
    r = M.resolve(plane, "Harbor Income Fund", S1, model=object())
    assert (r["instrument_id"], r["status"]) == (FC, "proposed")
    with wh.connect(plane) as con:
        assert str(con.execute("select proposed_by_agent_run_id from instrument_identifiers where id = ?", [r["identifier_id"]]).fetchone()[0]) == U(77)


def test_prompt_text_has_no_digit():
    assert not any(c.isdigit() for c in M._digit_free("Fund 2 of 10"))


def test_approval_needs_seat_and_is_refused_twice(plane):
    r = M.resolve(plane, "Evergreen Income Fund 2", S1)
    with pytest.raises(M.MatchRefused) as e:
        M.approve_alias(plane, r["identifier_id"], CIO)
    assert e.value.status == 403 and status(plane, r["identifier_id"])[0] == "proposed"
    assert M.approve_alias(plane, r["identifier_id"], OPS)["mapping_status"] == "approved"
    assert [str(x) if x else x for x in status(plane, r["identifier_id"])] == ["approved", M._user_id(OPS)]
    assert M.resolve(plane, "Evergreen Income Fund 2", S1)["status"] == "approved"
    with pytest.raises(M.MatchRefused) as e:
        M.approve_alias(plane, r["identifier_id"], OPS)
    assert e.value.status == 409


def test_one_approved_mapping_per_name(plane):
    with wh.connect(plane) as con:  # a second proposal for a name already approved (e.g. another instrument)
        con.execute("insert into instrument_identifiers values (?,?,?,?,'name','eg growth fund i',null,null,'proposed',null,null,null)", [P2, org_id(plane), FB, S1])
    with pytest.raises(M.MatchRefused) as e:
        M.approve_alias(plane, P2, OPS)
    assert e.value.status == 409 and "already approved" in e.value.message


def test_reject_blocks_the_same_proposal(plane):
    r = M.resolve(plane, "Evergreen Income Fund 2", S1)
    M.reject_alias(plane, r["identifier_id"], OPS, "wrong fund")
    again = M.resolve(plane, "Evergreen Income Fund 2", S1)
    assert again["status"] == "unknown" and count(plane) == 2


def test_routes(plane, monkeypatch):
    from sh_platform.v1 import e2c_routes as R
    r = M.resolve(plane, "Evergreen Income Fund 2", S1)
    app = FastAPI()
    app.include_router(R.router)
    monkeypatch.setattr(R, "_plane", lambda req: plane)
    viewer = {"v": OPS}
    monkeypatch.setattr(R, "viewer_of", lambda req: viewer["v"])
    c = TestClient(app)
    assert [p["instrument_name"] for p in c.get("/api/v1/evidence/aliases").json()] == ["Evergreen Income Fund II"]
    viewer["v"] = CIO
    assert c.post(f"/api/v1/evidence/aliases/{r['identifier_id']}/approve").status_code == 403
    viewer["v"] = OPS
    assert c.post(f"/api/v1/evidence/aliases/{r['identifier_id']}/approve").json()["status"] == "approved"
    assert c.get("/api/v1/evidence/aliases").json() == []


def test_one_click_approves_only_exact_names(plane):
    """UC5: 27 names identical to the register each needed a click; a person approves them at once, near matches stay for review."""
    exact = M.resolve(plane, "Evergreen Income Fund II", S1)               # the instrument's own name: proposed for the new source
    near = M.resolve(plane, "Evergreen Income, Fund 2 (Class I)", S1)       # a cleaned-name match: still one by one
    assert exact["status"] == near["status"] == "proposed"
    out = M.approve_exact(plane, OPS)
    assert out == {"approved": ["Evergreen Income Fund II"], "left": 1}
    assert status(plane, exact["identifier_id"])[0] == "approved" and status(plane, near["identifier_id"])[0] == "proposed"
