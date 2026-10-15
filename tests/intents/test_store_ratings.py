"""Spec 10 rule 4: the organiser and sponsor never see an individual anonymous score (T09 leak)."""
from sh_platform.intents import lifecycle as L, store as S
from sh_platform.profile.view import Viewer


def test_lead_sees_signed_scores_only_and_everyone_keeps_their_own():
    rec = L.new_record("problem", "acme", L.person("a-org", "Janet"), S.now_iso(), title="Late sweeps", purpose="Sweeps run late")
    rec["people"]["sponsor"] = L.person("a-spon", "Daniel")
    rec["state"] = "closed"
    rec["ratings"] = [{"by": None, "anonymous": True, "score": 2, "note": "", "at": "x"},
                      {"by": "a-p1", "anonymous": False, "score": 5, "note": "Clear", "at": "x"}]
    for lead in ("a-org", "a-spon"):
        out = S.cut(rec, "content", Viewer(name="", roles=frozenset(), account_id=lead))
        assert [r["score"] for r in out["ratings"]] == [5]
    mine = S.cut(rec, "content", Viewer(name="", roles=frozenset(), account_id="a-p1"))
    assert [r["score"] for r in mine["ratings"]] == [5]
    other = S.cut(rec, "content", Viewer(name="", roles=frozenset(), account_id="a-p9"))
    assert other["ratings"] == []
