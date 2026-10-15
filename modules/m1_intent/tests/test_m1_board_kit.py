"""Shared set-up for the M1-P07 tests (no tests here). A session with an organiser and guests with tokens, notes in the
private rooms (family-office wording, synthetic), a stub North that groups by words, and small helpers for the board and
the together stage. No live model call: the model is always a stub.
"""
import json

from m1_kit import BASE
from sh_platform.agents.protocols import ModelReply
from test_m1_seat_wiring_kit import flow, new_world

NOTES = [  # (text, anonymous): a family office; two groups of notes, one note on its own
    ("Capital calls reach us too late to plan the cash", False),
    ("We learn of capital calls by email days after the due date", True),
    ("No single exposure view across the family holdings", False),
    ("Exposure by name takes a week to put together", False),
    ("Private funds are not in our exposure report", True),
    ("Fee reports differ by manager and cannot be compared", False),
]
GROUPS = {"capital call": "Calls arrive too late", "exposure": "No single exposure view"}


class GatherStub:
    """A stand-in for North's model. Grouping call (it sees "Notes to group"): groups the labelled notes by the words in
    `groups` (word -> name) and replies with one fenced json block. Any other turn: one question."""

    def __init__(self, groups=None, reply=None, fail=False):
        self.groups, self.reply, self.fail, self.calls = GROUPS if groups is None else groups, reply, fail, []

    def complete(self, module_id, messages, tools=None):
        self.calls.append(messages)
        content = messages[1]["content"]
        if "Notes to group" not in content:
            return ModelReply("Who is affected?")
        if self.fail:
            raise RuntimeError("the provider is down")
        if self.reply is not None:
            return ModelReply(self.reply)
        lines = [ln[2:] for ln in json.loads(content)["question"].splitlines() if ln.startswith("- n")]
        found = {}
        for ln in lines:
            label, text = ln.split(": ", 1)
            for word, name in self.groups.items():
                if word in text.lower():
                    found.setdefault(name, []).append(label)
        out = {"groups": [{"name": n, "pack_problem_id": None, "reasoning": "Same problem", "note_ids": ids}
                          for n, ids in found.items()]}
        return ModelReply("```json\n" + json.dumps(out) + "\n```")


class Board:
    """The organiser and guests of one session, the notes written, and calls to the board and together routes."""

    def __init__(self, tmp_path, model=None, company="co-a", seats=3, names=("Ada Guest", "Ben Guest"), notes=NOTES, prep=None):
        self.w = new_world(tmp_path, model if model is not None else GatherStub())
        self.org, self.sid, self.guests = flow(self.w, company, seats=seats, names=names, prep=prep)
        self.company, self.note_ids = company, []
        for i, (text, anonymous) in enumerate(notes):
            who = self.guests[i % len(self.guests)] if self.guests else None
            nid = who.write(text)
            if anonymous:
                assert who.save(nid, anonymous=True).status_code == 200
            assert who.submit(nid).status_code == 200
            self.note_ids.append(nid)

    def url(self, path: str) -> str:
        return f"{BASE}/sessions/{self.sid}{path}"

    def org_call(self, method: str, path: str, **kw):
        return self.org.request(method, self.url(path), **kw)

    def close_rooms(self):
        r = self.org_call("POST", "/rooms/close")
        assert r.status_code == 200, r.text
        return r

    def group(self):
        r = self.org_call("POST", "/board/group")
        assert r.status_code == 200, r.text
        return r.json()

    def board(self, who=None):
        return self.org_call("GET", "/board") if who is None else who.call("GET", "/board")

    def to_together(self):
        r = self.org_call("POST", "/together")
        assert r.status_code == 200, r.text

    def cluster(self, name: str) -> dict:
        v = self.org_call("GET", "/board").json()
        return next(c for c in v["clusters"] if c["name"] == name)


def at_board(tmp_path, **kw) -> Board:
    b = Board(tmp_path, **kw)
    b.close_rooms()
    return b


def grouped(tmp_path, **kw) -> Board:
    b = at_board(tmp_path, **kw)
    b.group()
    return b


def together(tmp_path, **kw) -> Board:
    b = grouped(tmp_path, **kw)
    b.to_together()
    return b
