"""Agent memory at intent closure (spec 46). Entries are built by code from named closure fields, never from cards or a model summary.

`write_closure_memory(plane, intent)` runs after `closed` and returns the `memory` block for the intent record
(`{written_at, by_agent, filtered, state}`: counts and ids, never text). `opening_line(plane, pid, type_)` is North's first line.
Each line goes through `filters.clean` (digits, emails, restricted areas, anonymous), then a second check against sealed and
anonymous card text and other people's names. A person's edit is never overwritten; a deleted line (tombstone) is not written back.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

from sh_platform import memory
from sh_platform.intents import store as istore
from sh_platform.jsonfile import lock_for
from sh_platform.memory import filters
from sh_platform.memory.api import person_id
from sh_platform.memory.compact import fold
from sh_platform.memory.api import tomb_hash as tombstone_hash
from sh_platform.profile import store as pstore
from sh_platform.profile import view

log = logging.getLogger(__name__)
_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
          "eighteen nineteen twenty").split()
_TYPES = ("initiative", "brainstorm", "decision", "problem")  # pulse: no pass (46 open question 12)
_FOLLOW = ("initiative", "problem", "decision", "backlog")


tomb_hash = tombstone_hash  # one key for the memory routes and this pass


def in_words(n: int) -> str:
    return _WORDS[n] if 0 <= n < len(_WORDS) else "more than twenty"  # a digit would be dropped by the number guard


def _sealed_texts(plane) -> list[str]:
    """Normalised text of sealed and anonymous cards: used only to refuse an entry that echoes them, never as input."""
    out = []
    for c in (pstore.load(plane).get("cards") or {}).values():
        if view._v(c, "sealed") is True or view._v(c, "anonymous") is True:
            out += [view.norm(str(view._v(c, f))) for f in ("q1", "q2", "q3", "q4") if view._v(c, f)]
    return [t for t in out if len(t) >= 4]


def _echoes(text: str, sealed: list[str]) -> bool:
    n = view.norm(text)
    return any(s in n or n in s or memory._sim(n, s) >= memory.CLOSE for s in sealed)


def _names_other(text: str, names: set[str], own: set[str]) -> bool:
    low = view.norm(text)
    own = {view.norm(n) for n in own}
    return any(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", low)
               for n in {view.norm(x) for x in names} - own if len(n) >= 2)


def _title(chosen) -> str:
    if isinstance(chosen, dict):
        chosen = chosen.get("title") or chosen.get("text")
    return " ".join(chosen.split()) if isinstance(chosen, str) else ""


def _inside_box(intent: dict) -> bool:
    try:
        end = datetime.fromisoformat(str(intent["time_box"]["ends"]).replace("Z", "+00:00"))
        done = datetime.fromisoformat(str(intent["closure"]["closed_at"]).replace("Z", "+00:00"))
        return done.replace(tzinfo=done.tzinfo or timezone.utc) <= end.replace(tzinfo=end.tzinfo or timezone.utc)
    except (KeyError, TypeError, ValueError):
        return False


def north_lines(intent: dict, *, closer_signed: bool) -> list[dict]:
    """Candidate lines from type, participants, time box, chosen title and the closure `next` rows."""
    t = intent.get("type")
    if t not in _TYPES:
        return []
    n = len((intent.get("people") or {}).get("participants") or [])
    fact = f"Ran {'an' if t[0] in 'aeiou' else 'a'} {t}" + (f" with {in_words(n)} {'person' if n == 1 else 'people'}." if n else ".")
    rows = [{"kind": "fact", "text": fact}]
    if _inside_box(intent):
        rows.append({"kind": "preference", "text": f"Prefers to finish {'an' if t[0] in 'aeiou' else 'a'} {t} inside the time box."})
    title = _title((intent.get("outcome") or {}).get("chosen"))
    if title and closer_signed:
        rows.append({"kind": "decision", "text": f"Chose {title}."})
    for nxt in (intent.get("closure") or {}).get("next") or []:
        if isinstance(nxt, dict) and nxt.get("kind") in _FOLLOW and str(nxt.get("reason") or "").strip():
            rows.append({"kind": "open", "text": f"Wants to follow up: {' '.join(str(nxt['reason']).split())}"})
            break
    return [{**r, "conversation": f"intent:{intent.get('id')}", "topic": f"intent:{t}"} for r in rows]


def _keep(plane, rows: list[dict], pid: str, sealed: list[str], names: set[str], own: set[str]) -> list[dict]:
    """Filters, sealed echo, other names, tombstones, and a line close to one the person edited."""
    doc = memory.load(plane, "north", pid)
    tombs = {d.get("hash") for d in doc.get("deleted") or []}
    edited = [e for e in doc["entries"] if e.get("by") == "person"]
    mine = [e["text"] for e in edited]
    said = {e.get("topic") for e in edited if e["kind"] == "preference"}  # one preference per topic: the person's word stands
    return [r for r in filters.clean(plane, rows)
            if not _echoes(r["text"], sealed) and not _names_other(r["text"], names, own)
            and tomb_hash(r["text"]) not in tombs and all(memory._sim(r["text"], m) < memory.CLOSE for m in mine)
            and not (r["kind"] == "preference" and r.get("topic") in said)]


def _pid(plane, person) -> str | None:
    acct = person.get("account_id") if isinstance(person, dict) else person
    return person_id(plane, acct) if isinstance(acct, str) and acct else None


def write_closure_memory(plane, intent: dict) -> dict:
    """Run the pass once for a `closed` intent. Never raises: a failure is logged and reported as `state: failed`."""
    block = {"written_at": None, "by_agent": {"north": [], "lens": [], "nira": []}, "filtered": 0, "state": "skipped"}
    old = intent.get("memory")
    if isinstance(old, dict) and old.get("written_at"):
        return old  # idempotent
    if intent.get("state") != "closed" or intent.get("type") not in _TYPES:
        return block  # cancelled intents and check-in weeks teach nothing
    try:
        people, closure = intent.get("people") or {}, intent.get("closure") or {}
        closer = _pid(plane, closure.get("closed_by"))
        targets = list(dict.fromkeys(p for p in (closer, _pid(plane, people.get("organiser"))) if p))
        if not targets:
            return block  # no profile link, no person memory
        sealed, names = _sealed_texts(plane), filters.person_names(plane)
        rows = north_lines(intent, closer_signed=bool(closure.get("signed")))
        profile = pstore.load(plane).get("people") or {}
        for pid in targets:
            own = {n for n in (pid.replace("-", " ").title(), view._v(profile.get(pid) or {}, "name")) if n}
            mine = [dict(r) for r in rows if r["kind"] != "decision" or pid == closer]  # a decision is the closer's own
            kept = _keep(plane, mine, pid, sealed, names, own)
            block["filtered"] += len(mine) - len(kept)
            if not kept:
                continue
            with lock_for(memory._path(plane, "north", pid)):
                doc = memory.load(plane, "north", pid)
                now, have = memory._now(), {view.norm(e["text"]): e for e in doc["entries"]}
                for k in kept:  # a line is written once; a different line stays as it is (never turned into an "open question")
                    e = have.get(view.norm(k["text"]))
                    if e is None:
                        e = {"id": hashlib.sha1(f"{k['kind']}|{k['text']}".encode()).hexdigest()[:12], "kind": k["kind"], "text": k["text"],
                             "from": [{"conversation": k["conversation"], "at": now}], "updated_at": now, "by": "agent"}
                        doc["entries"].append(e)
                    e["topic"] = e.get("topic") or k["topic"]  # topic is an optional entry field (46 open question 3)
                    if e["id"] not in block["by_agent"]["north"]:
                        block["by_agent"]["north"].append(e["id"])
                doc["entries"] = fold(doc["entries"], doc.get("budget", memory.BUDGET))
                memory.save(plane, "north", pid, doc)
        block.update(written_at=istore.now_iso(), state="written" if block["by_agent"]["north"] else "skipped")
    except Exception:  # noqa: BLE001 ponytail: closure must never fail on memory; the reason is in the log
        log.warning("closure memory pass failed for an intent", exc_info=True)
        block["state"] = "failed"
        return block
    if "memory" in istore.KEYS:  # the counts block rides on the record once store.KEYS lists `memory`
        try:
            istore.update_intent(plane, intent["id"], intent["version"], lambda r: r.__setitem__("memory", block))
        except (LookupError, istore.VersionConflict):  # an unstored or newer record keeps its own block; memory never fails closure
            log.info("closure memory block not written on the record")
    return block


def opening_line(plane, pid: str | None, type_: str | None = None) -> dict | None:
    """North's first line from this person's entries, or None (then the plain line shows and memory is not mentioned)."""
    if not pid:
        return None
    doc = memory.load(plane, "north", pid)
    tombs = {d.get("hash") for d in doc.get("deleted") or []}
    live = [e for e in doc["entries"] if not e.get("retired_at") and str(e.get("topic", "")).startswith("intent:")
            and tomb_hash(e["text"]) not in tombs]

    def pick(kind: str):
        rows = [e for e in live if e["kind"] == kind and (not type_ or e["topic"] == f"intent:{type_}")]
        return max(rows, key=lambda e: e["updated_at"], default=None)

    fact, pref = pick("fact"), pick("preference")
    if not fact:
        return None
    low = fact["text"].rstrip(".")
    out = {"line": f"Last time you {low[:1].lower()}{low[1:]}, from what North remembers about you.",
           "type": fact["topic"].split(":", 1)[1], "entry_ids": [fact["id"]], "preference": None}
    if pref:
        t = pref["text"].rstrip(".")
        out["preference"] = ("You prefer " + t[len("Prefers "):] if t.startswith("Prefers ") else t) + "."
        out["entry_ids"].append(pref["id"])
    return out
