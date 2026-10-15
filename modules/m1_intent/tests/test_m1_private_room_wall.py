"""The wall while the rooms are open: North drafts a card once it has heard enough, and every seat sees how the lanes fill (counts and
the names of named writers only, never another person's words or an anonymous author)."""
from m1_kit import BASE
from test_m1_briefing_kit import make_world, seated, session_at
from sh_platform.agents.protocols import ModelReply
from test_m1_seat_wiring_kit import StubNorth

CARD = {"kind": "lever", "what": "The committee picks each benchmark", "where": "Investments, every quarter", "track": "", "define": ""}


def say(c, sid, text):
    r = c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": text, "kind": "answer"})
    assert r.status_code == 200, r.text
    return r.json()


def test_north_drafts_a_card_after_two_answers_and_says_so(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: StubNorth(CARD)
    sid = session_at(w, w.login("org", "co-a", ["sponsor"]), "co-a", "private_rooms", seats=2)
    c = seated(w, "co-a", "Mei Tan")
    assert say(c, sid, "The committee should pick each benchmark")["notes"] == []  # one answer is not enough
    room = say(c, sid, "It bites the investments team every quarter")
    (n,) = room["notes"]
    assert (n["kind"], n["confirmed"], n["state"], n["text"]) == ("lever", False, "draft", CARD["what"])
    assert n["quarters"]["q2"]["text"] == CARD["where"] and n["quarters"]["q3"]["mark"] == "unknown"
    assert "drafted a card for the Levers lane" in room["turns"][-1]["text"]
    assert len(say(c, sid, "And another thing")["notes"]) == 1  # the count starts again after a card
    again = say(c, sid, "One more")  # the same words again: no second card, and North does not claim one
    assert len(again["notes"]) == 1 and "drafted" not in again["turns"][-1]["text"]


def test_every_seat_sees_counts_and_named_writers_but_no_words(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: StubNorth()
    sid = session_at(w, w.login("org", "co-a", ["sponsor"]), "co-a", "private_rooms", seats=3)
    mei, ravi, kim = (seated(w, "co-a", n) for n in ("Mei Tan", "Ravi Shah", "Kim Lee"))

    def put(c, text, kind, anonymous=False):
        n = c.post(f"{BASE}/sessions/{sid}/room/messages", json={"text": text, "kind": "note", "note_kind": kind}).json()["notes"][-1]
        if anonymous:
            assert c.post(f"{BASE}/sessions/{sid}/room/notes/{n['id']}", json={"anonymous": True}).status_code == 200
        assert c.post(f"{BASE}/sessions/{sid}/room/notes/{n['id']}/submit").status_code == 200

    put(mei, "Fees differ by manager", "pain_point")
    put(ravi, "Secret worry about pay", "lever", anonymous=True)
    seen = kim.get(f"{BASE}/sessions/{sid}/room").json()
    assert seen["wall"]["others"] == {"intent": 0, "pain_point": 1, "future_signal": 0, "lever": 1}
    assert seen["wall"]["writers"] == ["Mei Tan"]  # the anonymous author is never named
    assert seen["notes"] == [] and "Fees differ" not in str(seen) and "Secret worry" not in str(seen)
    assert mei.get(f"{BASE}/sessions/{sid}/room").json()["wall"]["others"]["pain_point"] == 0  # her own card is not someone else's


ASKS = ("Who feels it most, and how often?", "How do you track it today?")


class Parrot(StubNorth):
    """A model that parrots the person back and opens every reply the same way."""

    def complete(self, module_id, messages, tools=None):
        if "ONLY one JSON object" in messages[0]["content"]:
            return super().complete(module_id, messages, tools)
        self.calls.append(messages)
        return ModelReply(f"You're emphasizing what you just said. {ASKS[len(self.calls) % 2]}")


def test_north_moves_on_instead_of_parroting_and_then_says_it_has_drafted(tmp_path):
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: Parrot({"kind": None})
    sid = session_at(w, w.login("org", "co-a", ["sponsor"]), "co-a", "private_rooms", seats=2)
    c = seated(w, "co-a", "Mei Tan")
    replies = [say(c, sid, x)["turns"][-1]["text"] for x in ("Benchmarks are picked by managers", "The committee, every quarter")]
    assert set(replies) == set(ASKS)  # the echo clause is gone; the question stays
    w.app.state.north_model_factory = lambda plane: Parrot(CARD)
    last = say(c, sid, "It costs us a quarter")["turns"][-1]["text"]
    assert last.startswith("Thank you") and "Levers lane" in last and "?" not in last  # a draft, not another question


class RefusesDocuments(StubNorth):
    """A model call that fails whenever company document passages are in it (as the egress check does for a false name match)."""

    def complete(self, module_id, messages, tools=None):
        if "company_documents" in messages[1]["content"]:
            raise RuntimeError("blocked")
        return ModelReply("How do you track it today?")


def test_a_refused_document_passage_never_costs_north_its_reply(tmp_path, monkeypatch):
    from modules.m1_intent.api import private_room as P
    monkeypatch.setattr(P, "context_passages", lambda plane, agent, text: "A passage from a shared document.")
    w = make_world(tmp_path)
    w.app.state.north_model_factory = lambda plane: RefusesDocuments()
    sid = session_at(w, w.login("org", "co-a", ["sponsor"]), "co-a", "private_rooms", seats=2)
    turn = say(seated(w, "co-a", "Mei Tan"), sid, "Managers pick their own benchmark")["turns"][-1]
    assert (turn["text"], turn["answered"]) == ("How do you track it today?", True)
