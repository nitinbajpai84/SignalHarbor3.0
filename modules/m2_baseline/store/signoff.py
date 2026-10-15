"""Sign-off files in the company plane (M2-23 to M2-28, X-08).

intents/m2_baseline/<baseline id>/signoff.json      versions (confirmations, named owners, review, countersignatures) + the audit trail
intents/m2_baseline/outcomes/<outcome id>.json      the baseline outcome record module 3 reads (written once per signed version)

The module-2 process (D-026) is a process record from sh_platform/process_record.py, opened with the first version
and completed when the baseline is signed; the outcome record carries both ids. The audit trail is append-only and
hash-chained: a changed or removed entry is reported as not intact. Locks cover threads in one process (A-015).
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone

from modules.m2_baseline.domain import handoff as H
from modules.m2_baseline.domain import readiness as R
from modules.m2_baseline.domain import signoff as S
from modules.m2_baseline.domain import worklist as W
from modules.m2_baseline.store import documents as DOC
from modules.m2_baseline.store import gate as GATE
from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.process_record import ProcessRecordError, ProcessRecords

log = logging.getLogger(__name__)
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_HEX = re.compile(r"[0-9a-f]{16,64}")
UNREADABLE = "The sign-off records could not be read, so nothing was changed. Please ask your administrator."
NOT_SAVED = "That could not be saved. Please try again."


class StoreError(Exception):
    """A plain-words failure; never contains a path or an id."""


# ---- reading the other packages' files -------------------------------------------------------------------------------
# The other packages' files are read through their own store read functions (integration, A-043). The process map has
# no module-level reader, so its file is read here directly, in the SHARED.md shape.
from modules.m2_baseline.store.answers import read_answers  # noqa: E402,F401
from modules.m2_baseline.store.baseline import read_baseline, set_state  # noqa: E402,F401
from modules.m2_baseline.store.catalogue import read_catalogue  # noqa: E402,F401
from modules.m2_baseline.store.kpis import read_kpis  # noqa: E402,F401
from modules.m2_baseline.store.glossary import read as read_glossary  # noqa: E402
# Each reads the file at the shape SHARED.md fixes. When the owning package lands, replace the body with an import of
# its store read function of the same name (nothing else here changes).
def _shared(plane, baseline_id, name):
    if not (isinstance(baseline_id, str) and _ID.fullmatch(baseline_id)):
        return None
    try:
        return read_json_strict(plane.path("intents", "m2_baseline", baseline_id, name))
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None








def read_tracking(plane, baseline_id) -> dict:
    """What people set with the process map's tracking route: {kpi_id: {status, ...}} (store/process_map.py)."""
    d = _shared(plane, baseline_id, "process_map_tracking.json")
    return d if isinstance(d, dict) else {}


def read_process_map(plane, baseline_id) -> dict:
    d = _shared(plane, baseline_id, "process_map.json")
    return d if isinstance(d, dict) else {}




def read_baseline_outcome(plane, outcome_id) -> dict | None:
    """What module 3 calls: the outcome record of a signed baseline, or None."""
    if not (isinstance(outcome_id, str) and _HEX.fullmatch(outcome_id)):
        return None
    try:
        d = read_json_strict(plane.path("intents", "m2_baseline", "outcomes", f"{outcome_id}.json"), dict)
    except (OSError, ValueError):
        raise StoreError(UNREADABLE) from None
    return d


def latest_baseline_outcome(plane, baseline_id) -> dict | None:
    """The outcome record of the newest signed version of this baseline, or None."""
    doc = SignoffStore(plane).read(baseline_id)
    signed = [v for v in (doc or {"versions": []})["versions"] if v["status"] == "signed"]
    return read_baseline_outcome(plane, signed[-1]["record"]["outcome_id"]) if signed else None


# ---- audit (X-08) ----------------------------------------------------------------------------------------------------
def _digest(prev: str, entry: dict) -> str:
    return hashlib.sha256((prev + json.dumps(entry, sort_keys=True)).encode("utf-8")).hexdigest()


def audit_intact(entries: list[dict]) -> bool:
    prev = ""
    for n, e in enumerate(entries, 1):
        body = {k: v for k, v in e.items() if k != "hash"}
        if e.get("n") != n or e.get("hash") != _digest(prev, body):
            return False
        prev = e["hash"]
    return True


class SignoffStore:
    def __init__(self, plane, clock=time.time, contracts_dir=None, sponsors=()):
        """`sponsors`: (display name, account id) of the company's sponsor accounts, to tell which measures none of them can see."""
        self._plane, self._clock, self._contracts_dir, self._sponsors = plane, clock, contracts_dir, tuple(sponsors)
        self.contract = R.load_contract("signoff.yaml", contracts_dir)

    # ---- files
    def _path(self, baseline_id):
        if not (isinstance(baseline_id, str) and _ID.fullmatch(baseline_id)):
            raise LookupError("no baseline")
        return self._plane.path("intents", "m2_baseline", baseline_id, "signoff.json")

    def _now(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def read(self, baseline_id) -> dict | None:
        try:
            doc = read_json_strict(self._path(baseline_id), dict)
        except (OSError, ValueError):
            raise StoreError(UNREADABLE) from None
        if doc is None:
            return None
        vs, audit = doc.get("versions"), doc.get("audit")
        if not (set(doc) == {"baseline_id", "versions", "audit"} and doc["baseline_id"] == baseline_id
                and isinstance(vs, list) and vs and isinstance(audit, list)
                and all(isinstance(v, dict) and v.get("version") == i and v.get("status") in ("open", "signed")
                        for i, v in enumerate(vs, 1))):
            raise StoreError(UNREADABLE)
        return doc

    def _save(self, doc: dict) -> None:
        try:
            write_json_atomic(self._path(doc["baseline_id"]), doc)
        except OSError:
            raise StoreError(NOT_SAVED) from None

    def _lock(self, baseline_id):
        return lock_for(self._path(baseline_id))

    # ---- the module 2 process record (D-026)
    def _open_record(self, baseline_id: str, number: int) -> dict:
        try:
            rec = ProcessRecords(self._plane, self._clock).start("m2_baseline", "baseline", f"{baseline_id}:v{number}")
        except ProcessRecordError as e:
            raise StoreError(str(e)) from None
        return {"session_id": rec.session_id, "outcome_id": rec.outcome_id}

    def _version(self, baseline_id: str, number: int, review: dict | None = None) -> dict:
        return {"version": number, "status": "open", "record": self._open_record(baseline_id, number), "parts": {},
                "named": {}, "review": review or {}, "settled": {}, "left_out": {}, "documents": None, "countersign": [], "signed_at": None}

    def _ensure(self, baseline_id: str) -> dict:
        if read_baseline(self._plane, baseline_id) is None:
            raise LookupError("no baseline")
        doc = self.read(baseline_id)
        if doc is None:
            doc = {"baseline_id": baseline_id, "versions": [self._version(baseline_id, 1)], "audit": []}
            self._save(doc)
        return doc

    # ---- audit trail
    def _append(self, doc: dict, by: str, action: str, **detail) -> dict:
        if action not in self.contract["audit_actions"]:
            raise ValueError("unknown audit action")
        prev = doc["audit"][-1]["hash"] if doc["audit"] else ""
        entry = {"n": len(doc["audit"]) + 1, "at": self._now(), "by": by, "action": action,
                 "version": doc["versions"][-1]["version"], **{k: v for k, v in detail.items() if v is not None}}
        return {**doc, "audit": [*doc["audit"], {**entry, "hash": _digest(prev, entry)}]}

    def record(self, baseline_id: str, by: str, action: str, **detail) -> None:
        """For the other M2 packages: an audit entry (for example `settle`, written by whoever settles a conflict)."""
        with self._lock(baseline_id):
            self._save(self._append(self._ensure(baseline_id), by, action, **detail))

    def audit(self, baseline_id, only: set[str] | None = None) -> dict:
        """`only`: entries about a measure outside it are left out (the chain check still runs on the whole trail)."""
        doc = self.read(baseline_id)
        entries = doc["audit"] if doc else []
        shown = [e for e in entries if only is None or e.get("kpi_id") is None or e["kpi_id"] in only]
        return {"entries": shown, "intact": audit_intact(entries)}

    # ---- the view (M2-23, M2-26)
    def _names(self, kpis) -> dict:
        return {k["id"]: k.get("name") or k["id"] for k in kpis if isinstance(k, dict) and k.get("id")}

    def _blind(self, kpis) -> frozenset:
        """The measures no sponsor account may see (A-044). With no sponsor account known, none: acceptance is then still asked."""
        return frozenset(k["id"] for k in kpis if self._sponsors and isinstance(k, dict) and k.get("id") and isinstance(k.get("governance"), dict)
                         and not any(W.may_see(k, name, acct, False) for name, acct in self._sponsors))

    def view(self, baseline_id: str, only: set[str] | None = None) -> dict:
        """`only` = the measures the asker may see: readiness, names and lock reasons are worked out from those alone, and
        when some measure is hidden the baseline never shows as ready to that person."""
        baseline = read_baseline(self._plane, baseline_id)
        if baseline is None:
            raise LookupError("no baseline")
        doc = self.read(baseline_id)
        version = doc["versions"][-1] if doc else {"version": 1, "status": "open", "record": None, "parts": {}, "named": {},
                                                  "review": {}, "left_out": {}, "documents": None, "countersign": [], "signed_at": None}
        left = version.get("left_out") or {}
        kpis = [k for k in read_kpis(self._plane, baseline_id) if not (isinstance(k, dict) and k.get("id") in left)]  # M2-E4: a measure left out is not in this baseline
        every = only is None or {k["id"] for k in kpis if isinstance(k, dict) and k.get("id")} <= only
        answers, whole, full_version, hidden = read_answers(self._plane, baseline_id), kpis, version, 0
        if only is not None:
            kpis = [k for k in kpis if isinstance(k, dict) and k.get("id") in only]
            hidden = len([k for k in whole if isinstance(k, dict) and k.get("id")]) - len(kpis)
            version = {**version, "parts": {k: p for k, p in version["parts"].items() if k in only}}
        mapped = read_tracking(self._plane, baseline_id)
        blind = self._blind(whole)
        v = R.compute(kpis, answers, version, self.contract, mapped, blind)
        if not every:  # A-044: readiness is the whole baseline's, as booleans only; nothing about a hidden measure is shown
            f = R.compute(whole, answers, full_version, self.contract, mapped, blind)
            v = {**v, "ready": f["ready"], "can_countersign": f["can_countersign"]}
        label = {s["slot"]: s["label"] for s in self.contract["countersign"]}
        return {"baseline_id": baseline_id, "version": version["version"], "versions": len(doc["versions"]) if doc else 1,
                "status": version["status"], "locked": S.locked_reason(version, self.contract, names=self._names(kpis)),
                "all_visible": every, "restricted_count": hidden,
                "signatures": [{"slot": s["slot"], "name": s["name"], "at": s["at"], "label": label.get(s["slot"], s["slot"]),
                                "restricted_covered": s.get("restricted_covered", 0), "note": s.get("note")}
                               for s in version["countersign"]],
                "record_pending": self._record_pending(version),
                "waiting_for": [s["label"] for s in self.contract["countersign"] if s["slot"] not in {x["slot"] for x in version["countersign"]}],
                "signed_at": version["signed_at"], "documents": version.get("documents"),
                "outcome_id": version["record"]["outcome_id"] if version["status"] == "signed" and version["record"] else None,
                **v}

    def _record_pending(self, version: dict) -> bool:
        """Signed, but the module 2 process record is not closed yet (the last step of a countersign failed)."""
        if version["status"] != "signed" or not version["record"]:
            return False
        rec = ProcessRecords(self._plane, self._clock).get_by_outcome(version["record"]["outcome_id"])
        return rec is not None and rec.outcome_state != "completed"

    def _complete_record(self, version: dict) -> None:
        """Closes the process side of the record (D-026). A failure leaves the baseline signed with `record_pending` set;
        calling countersign again retries this step."""
        try:
            ProcessRecords(self._plane, self._clock).complete_outcome(version["record"]["outcome_id"])
        except ProcessRecordError:
            log.exception("the module 2 process record could not be completed; it stays pending")

    # ---- changes: each takes the lock, applies one domain function, records one audit entry
    def _change(self, baseline_id, by, action, apply, **detail):
        """`apply(version, kpis)` returns (new version, extra audit detail)."""
        with self._lock(baseline_id):
            doc = self._ensure(baseline_id)
            version = doc["versions"][-1]
            kpis = R.with_tracking(read_kpis(self._plane, baseline_id), read_answers(self._plane, baseline_id), version, self.contract,
                                   read_tracking(self._plane, baseline_id))  # N-A: "tracked today" is read in one place
            result, extra = apply(version, kpis)
            doc = {**doc, "versions": [*doc["versions"][:-1], result]}
            self._save(self._append(doc, by, action, **{**detail, **extra}))
        return self.view(baseline_id)

    def confirm(self, baseline_id, who, kpi_id, part_id, acct_id, people):
        now = self._now()
        return self._change(baseline_id, who, "confirm",
                            lambda v, k: (S.confirm(v, self.contract, k, kpi_id, part_id, who, acct_id, people, now, read_answers(self._plane, baseline_id)), {}),
                            kpi_id=kpi_id, part=part_id)

    def name_owner(self, baseline_id, who, kpi_id, part_id, name, is_sponsor, people=()):
        now = self._now()
        return self._change(baseline_id, who, "name_owner",
                            lambda v, k: (S.name_owner(v, self.contract, k, kpi_id, part_id, name, who, is_sponsor, now, people), {}),
                            kpi_id=kpi_id, part=part_id, detail=f"named {str(name).strip()[:120]}")

    def set_review(self, baseline_id, who, kpi_id, fields):
        now = self._now()

        def apply(v, k):
            nv, withdrawn = S.set_review(v, self.contract, k, kpi_id, fields, who, now)
            return nv, ({"detail": "the acceptance was withdrawn because the plan changed"} if withdrawn else {})
        return self._change(baseline_id, who, "update_review", apply, kpi_id=kpi_id)

    def accept(self, baseline_id, who, kpi_id, is_sponsor):
        now = self._now()
        return self._change(baseline_id, who, "accept", lambda v, k: (S.accept(v, k, kpi_id, who, is_sponsor, now), {}),
                            kpi_id=kpi_id, detail="accepted as unknown for now")

    def settle(self, baseline_id, who, kpi_id, field, value, role_ok):
        now = self._now()
        return self._change(baseline_id, who, "settle",
                            lambda v, k: S.settle(v, self.contract, read_answers(self._plane, baseline_id), kpi_id, field, value, who, role_ok, now),
                            kpi_id=kpi_id)

    def leave_out(self, baseline_id, who, kpi_id, reason, roles):
        """M2-E4: the organiser or a sponsor leaves a measure out of this baseline, with a reason."""
        now = self._now()
        return self._change(baseline_id, who, "leave_out", lambda v, k: (S.leave_out(v, self.contract, k, kpi_id, reason, who, set(roles), now), {}),
                            kpi_id=kpi_id, detail="left out of this baseline")

    def forget_left_out(self, baseline_id, who, kpi_id) -> None:
        """A measure taken out or added again starts clean: its old "left out" status (kept by id on the open version) is dropped, so a re-added
        measure is never left out because an earlier one with the same id was."""
        doc = self.read(baseline_id)
        if not doc or doc["versions"][-1]["status"] == "signed" or kpi_id not in (doc["versions"][-1].get("left_out") or {}):
            return
        self._change(baseline_id, who, "bring_back", lambda v, k: ({**v, "left_out": {i: x for i, x in v["left_out"].items() if i != kpi_id}}, {}),
                     kpi_id=kpi_id, detail="the measure was added again")

    def bring_back(self, baseline_id, who, kpi_id, roles):
        return self._change(baseline_id, who, "bring_back", lambda v, k: (S.bring_back(v, self.contract, kpi_id, set(roles)), {}),
                            kpi_id=kpi_id, detail="brought back into this baseline")

    def confirm_by_link(self, baseline_id, name, kpi_id, part_id):
        now = self._now()
        return self._change(baseline_id, name, "confirm",
                            lambda v, k: (S.confirm_by_link(v, self.contract, k, kpi_id, part_id, name, now, read_answers(self._plane, baseline_id)), {}),
                            kpi_id=kpi_id, part=part_id, detail="through the answer link")

    def my_parts(self, baseline_id, name, kpi_ids, with_account=False) -> list[dict]:
        """The parts a nominee with no account may confirm through their link: {kpi_id, part, label, confirmed}. N4: an owner with an
        account confirms signed in; `with_account=True` lists only those parts (the link page tells them to sign in)."""
        doc, kpis = self.read(baseline_id), read_kpis(self._plane, baseline_id)
        version = doc["versions"][-1] if doc else {"named": {}, "parts": {}}
        out = []
        for k in kpis:
            if k["id"] not in kpi_ids:
                continue
            for p in self.contract["parts"]:
                status, owner = R.owner_of(k, version["named"], p["owner"])
                if status == "named" and S._norm(owner) == S._norm(name) and bool(R.owner_account(k, version["named"], p["owner"])) == with_account:
                    out.append({"kpi_id": k["id"], "part": p["id"], "label": p["label"],
                                "confirmed": bool((version["parts"].get(k["id"]) or {}).get(p["id"]))})
        return out

    def my_parts_signed_in(self, baseline_id, acct_id, people, seen) -> dict:
        """A signed-in owner's own parts and nothing else (any role): only measures in `seen`, only parts where this account is the
        named owner. {status, parts: [{kpi_id, kpi_name, part, label, confirmed}]}."""
        doc, kpis = self.read(baseline_id), read_kpis(self._plane, baseline_id)
        version = doc["versions"][-1] if doc else {"named": {}, "parts": {}, "status": "open"}
        out = []
        for k in kpis:
            if not (isinstance(k, dict) and k.get("id") in seen):
                continue
            for p in self.contract["parts"]:
                status, owner = R.owner_of(k, version["named"], p["owner"])
                try:
                    mine = status == "named" and S._is_owner(owner, R.owner_account(k, version["named"], p["owner"]), acct_id, list(people))
                except S.SignoffError:
                    mine = False  # two people share the name: nothing is shown
                if mine:
                    out.append({"kpi_id": k["id"], "kpi_name": k.get("name") or "A measure", "part": p["id"], "label": p["label"],
                                "confirmed": bool((version["parts"].get(k["id"]) or {}).get(p["id"]))})
        return {"status": version["status"], "parts": out}

    def new_version(self, baseline_id, who):
        """A change after signing: version n+1, with the review notes carried over and every confirmation and signature blank."""
        with self._lock(baseline_id):
            doc = self._ensure(baseline_id)
            last = doc["versions"][-1]
            if last["status"] != "signed":
                raise S.SignoffError("not_signed", "The current version is not signed yet, so it can still be changed.")
            nxt = self._version(baseline_id, last["version"] + 1, last["review"])
            nxt["named"] = last["named"]
            nxt["left_out"] = last.get("left_out") or {}
            self._save(self._append({**doc, "versions": [*doc["versions"], nxt]}, who, "new_version",
                                    detail=f"version {nxt['version']} started"))
            set_state(self._plane, baseline_id, "review")  # the working copy can be changed again
        return self.view(baseline_id)

    def countersign(self, baseline_id, who, acct_id, roles, restricted=0, viewer=None, sees=None):
        """The sponsor, then the head of data. The second signature signs the baseline and writes the hand-off. On a baseline
        that is signed but whose outcome record is still pending, the same call retries the closing step."""
        with self._lock(baseline_id):
            doc = self._ensure(baseline_id)
            before = doc["versions"][-1]
            if self._record_pending(before):
                self._complete_record(before)
                return self.view(baseline_id)
            view = self.view(baseline_id)
            now = self._now()
            left = before.get("left_out") or {}
            full = GATE.compute(self._plane, baseline_id, left)  # over every measure and row, never one person's view
            shown = GATE.for_viewer(self._plane, baseline_id, left, viewer, sees, full) if viewer is not None else full  # the sentence is the asker's own
            version = S.countersign(before, self.contract, view, who, acct_id, set(roles), now, restricted, {"ok": full["ok"], "refusal": shown["refusal"]},
                                    DOC.fingerprints(self._plane, baseline_id, left, now))
            slot = version["countersign"][-1]["slot"]
            if version["status"] == "signed":
                self._hand_off(baseline_id, version, view)
            doc = {**doc, "versions": [*doc["versions"][:-1], version]}
            self._save(self._append(doc, who, "sign", detail=slot, part=slot))
            if version["status"] == "signed":
                set_state(self._plane, baseline_id, "signed")  # N-E: from here every write route on the working copy answers 409
                self._complete_record(version)  # last, as module 1 does (D-026)
        return self.view(baseline_id)

    def _hand_off(self, baseline_id: str, version: dict, view: dict) -> None:
        """M2-28: the outcome record module 3 reads. Written before the sign-off is saved, so a signed baseline always has one."""
        baseline = read_baseline(self._plane, baseline_id)
        kpis = read_kpis(self._plane, baseline_id)
        record = H.build_outcome(H.load_outcome_contract(self._contracts_dir), outcome_id=version["record"]["outcome_id"],
                                 session_id=version["record"]["session_id"], baseline=baseline, version=version, view=view,
                                 process_map=read_process_map(self._plane, baseline_id), catalogue=read_catalogue(self._plane, baseline_id),
                                 governance={k["id"]: k.get("governance") or {} for k in kpis if isinstance(k, dict) and k.get("id")},
                                 glossary=read_glossary(self._plane, baseline_id)["entries"], kpis=kpis)
        try:
            write_json_atomic(self._plane.path("intents", "m2_baseline", "outcomes", f"{record['outcome_id']}.json"), record)
        except OSError:
            raise StoreError(NOT_SAVED) from None

    def locked_reason(self, baseline_id, kpi_id=None, part=None) -> str | None:
        """For the packages that re-draft (M2-27): who signed or confirmed the thing about to be rewritten, or None."""
        doc = self.read(baseline_id)
        if doc is None:
            return None
        return S.locked_reason(doc["versions"][-1], self.contract, kpi_id, part, self._names(read_kpis(self._plane, baseline_id)))

    def refuse_if_locked(self, baseline_id, kpi_id=None, part=None) -> None:
        """Raises BaselineLocked (the route answers 409) when a re-draft would rewrite signed or confirmed content."""
        doc = self.read(baseline_id)
        if doc is not None:
            S.refuse_if_locked(doc["versions"][-1], self.contract, kpi_id, part, self._names(read_kpis(self._plane, baseline_id)))

