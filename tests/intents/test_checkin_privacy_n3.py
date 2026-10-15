"""N3: before the week closes a reporter reads only their own items on the record; the reviewer reads all; closed, all read all."""
import pytest

from sh_platform.intents import checkin as C
from sh_platform.profile import view

ORG = view.Viewer("Org", frozenset({"participant"}), account_id="a-org")
IRFAN = view.Viewer("Irfan", frozenset({"participant"}), account_id="a-irfan")
SHARON = view.Viewer("Sharon", frozenset({"participant"}), account_id="a-sharon")
REC = {"id": "i1", "people": {"organiser": {"account_id": "a-org"}}, "series": {}}


def week(state):
    items = [C._new_item("broke", f"{n} line", v) for n, v in (("irfan", IRFAN), ("sharon", SHARON))]
    return {"week_key": "2026-W41", "opens": "2026-10-05", "answers_close": "2026-10-06", "closes": "2026-10-08", "state": state, "items": items,
            "submissions": [{"state": "submitted", "minutes": 2}], "people": [{}, {}]}


@pytest.mark.parametrize("who,state,seen", [(IRFAN, "review", ["irfan line"]), (SHARON, "collect", ["sharon line"]), (ORG, "review", ["irfan line", "sharon line"]),
                                           (IRFAN, "closed", ["irfan line", "sharon line"])])
def test_record_reach(monkeypatch, who, state, seen):
    monkeypatch.setattr(C, "_load_entry", lambda *a: (None, who, REC, week(state)))
    monkeypatch.setattr(C, "_pointers", lambda *a: [])
    out = C.get_intents_by_intent_id_pulse_record("i1", None)
    assert [i["text"] for i in out["items"]] == seen
