"""Requests to owners and the answer link's files (M2-06, M2-07, M2-29).

intents/m2_baseline/<baseline id>/requests.json   the shape in contracts/SHARED.md, plus the additive keys in questionnaire.yaml
<data root>/_control/m2_answer_index.json         request id -> company and baseline, so a link with no account finds its
                                                   company (the same idea as module 1's join index). No token, no hash.

The link token is "ow-<request id>-<secret>". Only its SHA-256 hash is stored here. Locks are the baseline folder's, shared
with the answers file, so a submit and an answer save happen together (one process).
"""
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.m2_baseline.domain import requests as R
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
UNREADABLE = "Module 2's saved files could not be read. Please ask your administrator."


class StoreError(Exception):
    """A saved file is unreadable: never overwritten, the screen says so."""


class LinkError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class WrongState(Exception):
    """The action does not fit where this request is; the message says why in plain words."""


def read_list(path: Path) -> list:
    try:
        return read_json_strict(path, list) or []
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None


def baseline_folder(plane, baseline_id: str) -> Path:
    return plane.path("intents", "m2_baseline", baseline_id)


class OwnerIndex:
    def __init__(self, data_root):
        self._path = Path(data_root).resolve() / "_control" / "m2_answer_index.json"

    def _read(self) -> dict:
        try:
            data = read_json_strict(self._path, dict) or {}
        except (OSError, ValueError):
            raise StoreError(UNREADABLE) from None
        return data

    def add(self, request_id: str, company_id: str, baseline_id: str) -> None:
        with lock_for(self._path):
            data = self._read()
            data[request_id] = {"company_id": company_id, "baseline_id": baseline_id}
            write_json_atomic(self._path, data)

    def lookup(self, request_id: str) -> dict | None:
        with lock_for(self._path):
            found = self._read().get(request_id)
        return found if isinstance(found, dict) and set(found) == {"company_id", "baseline_id"} else None


class RequestStore:
    def __init__(self, plane, baseline_id: str, clock=time.time):
        self._plane, self.baseline_id, self._clock = plane, baseline_id, clock
        self._dir = baseline_folder(plane, baseline_id)
        self._file = self._dir / "requests.json"

    # ---- files
    def lock(self):
        return lock_for(self._dir)

    def now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), timezone.utc)

    def kpis(self) -> list:
        """The baseline's KPIs, through M2-P01's store read function (integration, A-043)."""
        from modules.m2_baseline.store.kpis import read_kpis
        return read_kpis(self._plane, self.baseline_id)

    def kpi_names(self) -> dict[str, str]:
        return {k["id"]: str(k.get("name") or "A measure") for k in self.kpis()}

    def all(self) -> list[dict]:
        return read_list(self._file)

    def get(self, request_id: str) -> dict:
        found = next((r for r in self.all() if r["id"] == request_id), None)
        if found is None:
            raise LookupError("no request")
        return found

    def _change(self, request_id: str, change) -> dict:
        with self.lock():
            rows, out = self.all(), None
            for i, r in enumerate(rows):
                if r["id"] == request_id:
                    out = rows[i] = change(dict(r))
            if out is None:
                raise LookupError("no request")
            write_json_atomic(self._file, rows)
            return out

    # ---- sending (M2-06)
    def send(self, index: OwnerIndex, q, only: set[str] | None = None, sender: str = "") -> list[tuple[dict, str | None]]:
        """`only` = the measures the sender may see: an owner of any other measure is skipped (no request, no link, no change).
        `sender` is the person sending: they get no request of their own (no one asks the asker) when they appear only as a guessed or default
        owner. A measure they were named for in a person's own words (stated), or a request they already have, is asked as anyone is.
        One request per nominated owner. A person who already has one keeps it (their KPI list is brought up to date,
        no new link); a new one gets a new token, returned once and never stored. Returns [(request, token or None)]."""
        with self.lock():
            kpis = self.kpis()
            if not kpis:
                raise LookupError("no kpis")
            rows, out, now = self.all(), [], self.now()
            for o in R.owners_to_ask(kpis):
                if only is not None and set(o["kpi_ids"]) - only:
                    continue
                have = next((r for r in rows if r["owner_name"] == o["name"]), None)
                if have is None and sender and R.plain_name(o["name"]).casefold() == R.plain_name(sender).casefold() and not any(
                        (k["owners"].get(r) or {}).get("mark") == "stated" and str((k["owners"].get(r) or {}).get("value") or "").strip() == o["name"]
                        for k in kpis for r in k["owners"]):
                    continue  # named only by a guess or a default: the sender added herself to nothing
                if have is not None:
                    if have["kpi_ids"] != o["kpi_ids"] or have["role"] != o["role"]:
                        if have["state"] == "answered" and set(o["kpi_ids"]) - set(have["kpi_ids"]):
                            have.update(state="opened", answered_at=None)  # a new measure: they owe an answer for it again
                        have.update(kpi_ids=o["kpi_ids"], role=o["role"])
                    out.append((have, None))
                    continue
                row, token = self._new(index, q, o["name"], o["role"], o["kpi_ids"], now)
                rows.append(row)
                out.append((row, token))
            write_json_atomic(self._file, rows)
            return out

    def _new(self, index: OwnerIndex, q, name: str, role: str, kpi_ids: list[str], now) -> tuple[dict, str]:
        rid = R.new_request_id()
        token = R.new_token(rid)
        row = {"id": rid, "owner_name": name, "role": role, "kpi_ids": kpi_ids,
               "token_hash": R.digest(token), "state": "sent", "sent_at": now.isoformat(), "reminders": [],
               "expires_at": (now + timedelta(hours=q.link_hours)).isoformat(), "opened_at": None,
               "answered_at": None, "revoked_at": None, "meeting": None, "samples": 0}
        index.add(rid, self._plane.company_id, self.baseline_id)
        return row, token

    def ask(self, index: OwnerIndex, q, owner_name: str, role: str, kpi_id: str, question: dict, account_id: str | None = None) -> tuple[dict, str | None]:
        """M2-E1 "Ask the owner": an open question joins this owner's request (`questions`: [{ambiguity_id, kpi_id, text}]). The owner is matched by
        account id when they have one (two people with one name are two owners), else by name. A person with no request yet gets one; one whose
        link was withdrawn or has expired gets a NEW link (the old one stays dead), so the question is never added to a request nobody can open.
        A new link is returned once (as in `send`). One who already answered owes an answer again."""
        with self.lock():
            rows, now = self.all(), self.now()
            same = [r for r in rows if r["owner_name"] == owner_name]
            have = next((r for r in same if account_id and r.get("account_id") == account_id), None) or \
                next((r for r in same if not r.get("account_id") or not account_id), None)
            token = None
            if have is None:
                have, token = self._new(index, q, owner_name, f"{role} owner", [kpi_id], now)
                rows.append(have)
            elif R.link_state(have, now) != "open" or have["state"] == "in_meeting":
                token = R.new_token(have["id"])
                have.update(token_hash=R.digest(token), state="sent", sent_at=now.isoformat(), reminders=[], answered_at=None, opened_at=None, revoked_at=None,
                            meeting=None, expires_at=(now + timedelta(hours=q.link_hours)).isoformat())
                index.add(have["id"], self._plane.company_id, self.baseline_id)
            if account_id:
                have["account_id"] = account_id
            have["questions"] = [*(x for x in have.get("questions") or [] if x["ambiguity_id"] != question["ambiguity_id"]), question]
            if kpi_id not in have["kpi_ids"]:
                have["kpi_ids"] = [*have["kpi_ids"], kpi_id]
            if have["state"] == "answered":
                have.update(state="opened", answered_at=None)
            write_json_atomic(self._file, rows)
            return have, token

    def relink(self, request_id: str, index: OwnerIndex, q) -> tuple[dict, str]:
        """A new link for someone who lost theirs or was moved to a meeting: the old one stops working, the clock restarts."""
        token = R.new_token(request_id)
        now = self.now()

        def change(r: dict) -> dict:
            if r["state"] == "answered":
                raise WrongState("This person has already answered, so there is nothing to send again.")
            return {**r, "token_hash": R.digest(token), "state": "sent", "sent_at": now.isoformat(), "reminders": [],
                    "expires_at": (now + timedelta(hours=q.link_hours)).isoformat(), "revoked_at": None, "meeting": None}
        row = self._change(request_id, change)
        index.add(request_id, self._plane.company_id, self.baseline_id)
        return row, token

    def reopen(self, request_id: str, index: OwnerIndex, q) -> tuple[dict, str]:
        """The organiser lets an answered person change their answers: a new link, the old one stops working. Their
        answers stay as they are (the answers file is not touched)."""
        token = R.new_token(request_id)
        now = self.now()

        def change(r: dict) -> dict:
            if r["state"] != "answered":
                raise WrongState("This person has not sent their answers in yet, so there is nothing to reopen.")
            return {**r, "token_hash": R.digest(token), "state": "sent", "sent_at": now.isoformat(), "reminders": [],
                    "expires_at": (now + timedelta(hours=q.link_hours)).isoformat(), "opened_at": None, "answered_at": None,
                    "revoked_at": None, "samples": 0, "reopened_at": now.isoformat()}
        row = self._change(request_id, change)
        index.add(request_id, self._plane.company_id, self.baseline_id)
        return row, token

    def revoke(self, request_id: str) -> dict:
        return self._change(request_id, lambda r: {**r, "revoked_at": r["revoked_at"] or self.now().isoformat()})

    def remind(self, request_id: str) -> dict:
        """Marks a reminder as sent (nothing is emailed: Nira has no email service). Recorded with its date."""
        def change(r: dict) -> dict:
            if r["state"] not in R.OPEN_STATES:
                raise WrongState("This person does not owe an answer, so there is nothing to remind them about.")
            return {**r, "reminders": [*r["reminders"], self.now().isoformat()]}
        return self._change(request_id, change)

    def to_meeting(self, request_id: str, organiser: str) -> dict:
        """"Answer in a meeting instead": the link is withdrawn and the organiser fills the form on the person's behalf."""
        def change(r: dict) -> dict:
            if r["state"] == "answered":
                raise WrongState("This person has already answered.")
            now = self.now().isoformat()
            return {**r, "state": "in_meeting", "meeting": {"by": organiser, "at": now}, "revoked_at": r["revoked_at"] or now}
        return self._change(request_id, change)

    def meeting_started(self, owner_name: str, organiser: str) -> None:
        """Answers were entered for this person in a meeting: their request, if any, now reads "in a meeting"."""
        with self.lock():
            r = next((x for x in self.all() if x["owner_name"] == owner_name), None)
            if r is not None and r["state"] != "answered" and r["state"] != "in_meeting":
                self.to_meeting(r["id"], organiser)

    # ---- the answer link (M2-07)
    def ground(self, request_id: str, token: str) -> dict:
        """The request for a token that is good right now. `link_invalid` when nothing matches; `link_gone` (with the
        reason in words) when it matched but was withdrawn or has expired. Only a holder of the real secret sees which."""
        found = next((r for r in self.all() if r["id"] == request_id), None)
        match = found is not None and hmac.compare_digest(found["token_hash"], R.digest(token))
        if not match:
            raise LinkError("link_invalid", "This link is not working. Please ask for a new one.")
        gone = R.link_state(found, self.now())
        if gone != "open":
            raise LinkError("link_gone", R.LINK_GONE[gone])
        return found

    def opened(self, request_id: str) -> dict:
        def change(r: dict) -> dict:
            return {**r, "state": "opened", "opened_at": self.now().isoformat()} if r["state"] == "sent" else r
        return self._change(request_id, change)

    def count_sample(self, request_id: str, cap: int) -> None:
        """Counts one more sample on this link, or refuses when the cap is reached."""
        def change(r: dict) -> dict:
            if r.get("samples", 0) >= cap:
                raise WrongState(f"You can attach up to {cap} files. Please tell the organiser if you need to send more.")
            return {**r, "samples": r.get("samples", 0) + 1}
        self._change(request_id, change)

    def answered(self, request_id: str) -> dict:
        return self._change(request_id, lambda r: {**r, "state": "answered", "answered_at": self.now().isoformat()})
