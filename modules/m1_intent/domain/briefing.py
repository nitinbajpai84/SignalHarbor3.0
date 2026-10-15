"""The briefing stage (M1-05, M1-06) and the stage clock's stored facts (M1-14).

Rules text is built from the prepared session; only the fixed plain-words labels come from
contracts/briefing.yaml. People are seat ids (the organiser's seat is the organiser's account id; guests get theirs
from M1-P02). Stored per session in the company plane (`intents/m1_intent/stages/<id>.json`); the video file lives
in the plane's `context` area. Nothing here knows about requests.
"""
import re
from dataclasses import dataclass, replace
from pathlib import Path

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.timer import iso
from modules.m1_intent.store.files import UNREADABLE, StoreError, lock_for, read_json, write_json

_HEX = re.compile(r"[0-9a-f]{32}")
_SEAT = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_FILE_KEYS = {"started", "extensions", "seats", "video_type"}
ANSWERS = ("clear",)  # a person confirms "clear"; asking Nira is a separate act (see mark_asked)


@dataclass(frozen=True)
class BriefingSettings:
    video_types: dict[str, str]
    max_video_bytes: int
    extension_minutes: tuple[int, ...]
    question_max: int
    reply_max: int
    labels: dict[str, str]
    time_text: str
    notes_text: str
    notes_text_by_names: dict[str, str]  # the notes sentence for each names rule: named, choice, anonymous
    kinds_text: str
    read_aloud_unavailable: str
    default_video: tuple[Path, str] | None = None   # (file, content type) when the module ships one


def load_settings(folder=None) -> BriefingSettings:
    name = "briefing.yaml"
    d = C._read(folder, name)
    try:
        video, nira, rules = d["video"], d["nira"], d["rules"]
        types = video["allowed_types"]
        if not (isinstance(types, dict) and types and all(isinstance(k, str) and isinstance(v, str) for k, v in types.items())):
            raise ValueError("video types must be a list of content types with a file ending")
        s = BriefingSettings(
            video_types=dict(types), max_video_bytes=C._int(video["max_megabytes"], "video size") * 1024 * 1024,
            extension_minutes=tuple(C._int(m, "an extension") for m in d["extension_minutes"]),
            question_max=C._int(nira["question_max_chars"], "question length"),
            reply_max=C._int(nira["reply_max_chars"], "reply length"),
            labels={k: str(rules["labels"][k]) for k in ("purpose", "outcome", "time", "notes", "kinds")},
            time_text=str(rules["time_text"]), notes_text=str(rules["notes_text"]), kinds_text=str(rules["kinds_text"]),
            notes_text_by_names={"named": str(rules["notes_text_named"]), "choice": str(rules["notes_text"]),
                                 "anonymous": str(rules["notes_text_anonymous"])},
            read_aloud_unavailable=str(d["read_aloud_unavailable"]))
        dv = d.get("briefing_default_video")
        if dv:
            path = Path(__file__).resolve().parents[1] / str(dv["file"])
            if str(dv["content_type"]) not in s.video_types:
                raise ValueError("the default video must be of an allowed type")
            s = replace(s, default_video=(path, str(dv["content_type"])) if path.is_file() else None)
        if not s.extension_minutes:
            raise ValueError("there must be at least one extension on offer")
        s.time_text.format(length=1, briefing=1, individual=1, together=1)
    except (KeyError, ValueError, TypeError, IndexError, AttributeError) as e:
        raise C.ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None
    return s


def _span(minutes: int) -> str:
    """A length in the unit a person reads: minutes under two hours, hours under two days, else days."""
    n = int(minutes)
    if n >= 2880:
        return f"{round(n / 1440)} days"
    if n >= 120:
        return f"{round(n / 60)} hours"
    return f"{n} minute" + ("" if n == 1 else "s")


def build_rules(prep: dict, s: BriefingSettings) -> list[dict]:
    """What the briefing says, in order: purpose, outcome (when given), time, what to write about (the four kinds of note), how notes are shown."""
    split = prep["split"]
    rows = [("purpose", prep["purpose"]), ("outcome", prep["outcome"]),
            ("time", s.time_text.format(length=_span(max(int(prep["length_minutes"]), sum(int(v) for v in split.values()))), **{k: _span(v) for k, v in split.items()})), ("kinds", s.kinds_text),
            ("notes", s.notes_text_by_names.get(prep.get("names"), s.notes_text))]  # the organiser's names rule, true for this session
    return [{"id": k, "label": s.labels[k], "text": t} for k, t in rows if t]


def title_of(prep: dict) -> str:
    return " ".join(prep["purpose"].split())[:120]


def seat_ok(seat) -> bool:
    return isinstance(seat, str) and _SEAT.fullmatch(seat) is not None


class StageStore:
    """Confirmations, stage start times, extensions and the video file of the sessions of one company plane."""

    def __init__(self, plane):
        self._plane = plane

    def _path(self, session_id: str) -> Path:
        if not _HEX.fullmatch(session_id):
            raise StoreError(UNREADABLE)
        return self._plane.path("intents", "m1_intent", "stages", f"{session_id}.json")

    def _video_path(self, session_id: str) -> Path:
        self._path(session_id)  # checks the id
        return self._plane.path("context", "m1_intent", "briefing_video", f"{session_id}.bin")

    def get(self, session_id: str) -> dict:
        data = read_json(self._path(session_id))
        if data is None:
            return {"started": {}, "extensions": {}, "seats": {}, "video_type": None}
        if not (isinstance(data, dict) and set(data) == _FILE_KEYS and isinstance(data["started"], dict)
                and isinstance(data["extensions"], dict) and isinstance(data["seats"], dict)):
            raise StoreError(UNREADABLE)
        return data

    def _update(self, session_id: str, change) -> dict:
        path = self._path(session_id)
        with lock_for(path):
            data = self.get(session_id)
            out = change(data)
            write_json(path, data)
            return out if out is not None else data

    # ---- the stage clock
    def started(self, session_id: str, stage: str, default: float) -> float:
        """When the stage began. A stage nobody has timed yet began at `default` (the session's last change)."""
        have = self.get(session_id)["started"].get(stage)
        if have is not None:
            return float(have)
        self._update(session_id, lambda d: d["started"].setdefault(stage, default))
        return float(self.get(session_id)["started"][stage])

    def start(self, session_id: str, stage: str, now: float) -> None:
        self._update(session_id, lambda d: d["started"].__setitem__(stage, now))

    def extensions(self, session_id: str, stage: str) -> list[dict]:
        return list(self.get(session_id)["extensions"].get(stage, []))

    def extend(self, session_id: str, stage: str, minutes: int, now: float) -> None:
        self._update(session_id, lambda d: d["extensions"].setdefault(stage, []).append({"at": iso(now), "minutes": minutes}))

    # ---- confirmations
    def status(self, session_id: str, seat: str) -> str:
        return self.get(session_id)["seats"].get(seat, "waiting")

    def confirm(self, session_id: str, seat: str) -> None:
        self._update(session_id, lambda d: d["seats"].__setitem__(seat, "clear"))

    def set_rooms_done(self, session_id: str, seat: str, is_done: bool) -> None:
        """The private rooms' "I'm done" (kept beside the briefing's "clear" under its own key, so neither undoes the other)."""
        def change(d):
            d["seats"].pop(f"done:{seat}", None)
            if is_done:
                d["seats"][f"done:{seat}"] = "done"
        self._update(session_id, change)

    def rooms_done(self, session_id: str, seat: str) -> bool:
        return self.get(session_id)["seats"].get(f"done:{seat}") == "done"

    def mark_asked(self, session_id: str, seat: str) -> None:
        """Asking Nira never undoes "clear"."""
        self._update(session_id, lambda d: d["seats"].setdefault(seat, "asked"))

    def confirmed(self, session_id: str) -> int:
        return sum(1 for v in self.get(session_id)["seats"].values() if v == "clear")

    # ---- the video
    def video_type(self, session_id: str) -> str | None:
        return self.get(session_id)["video_type"]

    def save_video(self, session_id: str, data: bytes, content_type: str) -> None:
        path = self._video_path(session_id)
        with lock_for(path):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(path)
            except OSError:
                raise StoreError("That could not be saved. Please try again.") from None
            self._update(session_id, lambda d: d.__setitem__("video_type", content_type))

    def video_file(self, session_id: str) -> Path | None:
        if self.video_type(session_id) is None:
            return None
        path = self._video_path(session_id)
        return path if path.is_file() else None
