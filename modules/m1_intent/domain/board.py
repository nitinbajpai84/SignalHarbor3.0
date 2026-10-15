"""The brainstorm board (M1-17 to M1-19). Pure Python: no web, no storage, no model.

A cluster is {id, name, note_ids, source, pack_problem_id, reasoning}; `source` is "north" or "person". A note is in at
most one cluster; one in none is "on its own". The board never holds a note's words or author: only public note ids
(the rest is read through NoteStore.board, the one read for boards). Nothing is ever deleted: a note moved out of a
cluster is on its own or in another, and a cluster left empty simply goes.
"""
import re
import secrets
from dataclasses import dataclass

from modules.m1_intent.domain import contracts as C
from modules.m1_intent.domain.notes import NOTE_KINDS, kind_of

EDIT_STAGES = ("board", "together")
_AFTER_ROOMS = ("board", "together", "signing", "closed")
NOT_YET = "The board appears when the private rooms close."
NO_CLUSTERS = "Group the notes first, or make a cluster by hand."
FALLBACK_NOTE = "Grouped without North; please check."
_WORD = re.compile(r"[a-z]{4,}")
_STOP = frozenset("""about above after again also another because been before being between both could does doing done each
else even every from have having here into just like made make many more most much must need only other over really same
should since some such than that their them then there these they this those through very want what when where which while
will with would your know think whether""".split())


class BoardError(Exception):
    """A plain-words refusal."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class WrongStage(BoardError):
    """The session is not in a stage that allows this: the API answers 409."""


def readable(state: str, paused_from, stages=_AFTER_ROOMS) -> bool:
    """A session paused on a stage can be read as that stage."""
    return state in stages or (state == "paused" and paused_from in stages)


def check_board_readable(state: str, paused_from) -> None:
    if not readable(state, paused_from):
        raise WrongStage(NOT_YET)


def check_editable(state: str) -> None:
    if state not in EDIT_STAGES:
        raise WrongStage("The board can be changed only before the room signs the charter." if state in ("signing", "closed")
                         else NOT_YET if state != "paused" else "The room is held. You can change the board when you carry on.")


@dataclass(frozen=True)
class BoardSettings:
    options: tuple[dict, ...]
    name_chars: int
    comment_chars: int
    comments_per_cluster: int
    min_notes: int
    note_chars_sent: int
    notes_chars_sent: int
    split_suffix: str
    default_name: str
    auto_priorities: tuple[str, ...] = ("must", "should")  # contracts/board.yaml auto_tick
    auto_min_votes: int = 1

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(o["id"] for o in self.options)


def load_settings(folder=None) -> BoardSettings:
    name = "board.yaml"
    d = C._read(folder, name)
    try:
        rows, lim, words = d["vote_options"], d["limits"], d["wording"]
        opts = tuple({"id": r["id"], "label": r["label"]} for r in rows)
        if not opts or len({o["id"] for o in opts}) != len(opts) or not all(
                isinstance(o["id"], str) and o["id"] and isinstance(o["label"], str) for o in opts):
            raise ValueError("the vote options need unique ids and labels")
        return BoardSettings(opts, C._int(lim["cluster_name_chars"], "cluster name limit"),
                             C._int(lim["comment_chars"], "comment limit"),
                             C._int(lim["comments_per_cluster"], "comments limit"),
                             C._int(lim["min_cluster_notes"], "smallest group", 2),
                             C._int(lim["note_chars_sent"], "note size"), C._int(lim["notes_chars_sent"], "notes size"),
                             str(words["split_suffix"]), str(words["default_cluster_name"]),
                             tuple(str(x) for x in d["auto_tick"]["priorities"]), C._int(d["auto_tick"]["min_votes"], "smallest backing", 1))
    except (KeyError, ValueError, TypeError) as e:
        raise C.ContractError(f"{name} is not valid: {e if isinstance(e, ValueError) else 'a setting is missing'}.") from None


def clean_name(s: BoardSettings, v) -> str:
    if not isinstance(v, str) or not " ".join(v.split()):
        raise BoardError("Please give the group a name.")
    v = " ".join(v.split())
    if len(v) > s.name_chars:
        raise BoardError(f"That name is too long. Please keep it under {s.name_chars} characters.")
    if any(ord(c) < 32 or ord(c) == 127 for c in v):
        raise BoardError("That name has a character that cannot be saved.")
    return v


def new_cluster(name: str, note_ids: list[str], source: str, pack_problem_id=None, reasoning: str = "") -> dict:
    return {"id": secrets.token_hex(8), "name": name, "note_ids": list(note_ids), "source": source,
            "pack_problem_id": pack_problem_id, "reasoning": reasoning}


def apply_grouping(s: BoardSettings, note_ids: list[str], groups: list[dict], problem_ids: set[str]) -> list[dict]:
    """North's groups made safe: only known notes, each in one group at most, a group of fewer than the smallest size
    is dissolved (its notes stay on their own), a pack problem id North was not given is dropped. No note is lost:
    whatever is in no group is on its own by definition."""
    known, taken, out = set(note_ids), set(), []
    for g in groups:
        ids = [n for n in dict.fromkeys(g.get("note_ids") or []) if n in known and n not in taken]
        if len(ids) < s.min_notes:
            continue
        taken.update(ids)
        try:
            name = clean_name(s, g.get("name"))
        except BoardError:
            name = s.default_name
        pid = g.get("pack_problem_id")
        reason = " ".join(str(g.get("reasoning") or "").split())[:300]
        out.append(new_cluster(name, ids, "north", pid if pid in problem_ids else None, reason))
    return out


SEALED = "A sealed card"  # the profile's silhouette wording for a card the viewer may not see
SEALED_CLUSTER = "A sealed cluster"
SEALED_GROUP = "Sealed"  # the stored name of the one cluster that holds every sealed note; no word of any note is in it


def mask_sealed(plane, notes: list[dict], viewer=None) -> list[dict]:
    """The one mask for every reader of the board's notes (board, together, summary, charter, export, hand-off). A sealed note is whole only
    where the profile shows its card whole to `viewer` (the wall's own filter, same card id); otherwise its words, details and name are gone.
    No viewer (a document, which is read by many) is the viewer on no list. A card that is missing is treated as closed."""
    if not any(n.get("restricted") for n in notes):
        return notes
    from sh_platform.profile import read
    from sh_platform.profile.view import NOBODY
    cards = read(plane, viewer or NOBODY)["cards"]
    return [{**{k: v for k, v in n.items() if k != "author_name"}, "text": SEALED, "anonymous": True, "sealed": True, "fields": {}}
            if n.get("restricted") and "silhouette" in cards.get(n["id"], {"silhouette": 1}) else n for n in notes]


def cluster_name(name: str, notes: list[dict]) -> str:
    """A cluster whose notes are all sealed for this viewer is named "A sealed cluster": North named it from words the viewer may not read.
    Where only some are sealed the name stays: it is North's summary of the group, and the open notes are the viewer's to read."""
    return SEALED_CLUSTER if notes and all(n.get("sealed") for n in notes) else name


def shown(note: dict) -> dict:
    """The board's note: the public record's words, whether it is anonymous, the name only when posted by name, and
    `mine` for the viewer's own. Never a field that could lead to an author."""
    out = {"id": note["id"], "text": note["text"], "kind": kind_of(note), "anonymous": note["anonymous"] is True,
           "mine": note.get("mine") is True}
    if note.get("sealed"):
        out["sealed"] = True
    if not out["anonymous"] and note.get("author_name"):
        out["author_name"] = note["author_name"]
    return out


def view(clusters: list[dict], notes: list[dict]) -> dict:
    """Clusters and the lone notes, each note once. `notes` are the public records (NoteStore.board). A note id in a
    cluster that is no longer a note is ignored; a note in no cluster is on its own."""
    by_id = {n["id"]: n for n in notes}
    out, inside = [], set()
    for c in clusters:
        ids = [n for n in c["note_ids"] if n in by_id and n not in inside]
        inside.update(ids)
        kinds = {kind_of(by_id[n]) for n in ids}  # one kind, "mixed" only when the organiser put kinds together by hand
        cluster_view = {"id": c["id"], "name": cluster_name(c["name"], [by_id[n] for n in ids]), "source": c["source"], "reasoning": c.get("reasoning", ""),
                        "kind": next(iter(kinds)) if len(kinds) == 1 else "mixed" if kinds else None,
                        "note_ids": ids, "notes": [shown(by_id[n]) for n in ids]}
        if "colour" in c:
            cluster_view["colour"] = c["colour"]
        out.append(cluster_view)
    return {"clusters": out, "on_its_own": [shown(n) for n in notes if n["id"] not in inside]}


def assign_colours(clusters: list[dict], preserve_ids: set[str] = None, previous_colours: dict[str, int] = None) -> list[dict]:
    """Assign stable colour indices 0-7 to clusters. When preserve_ids is given, those clusters keep their previous
    colours (used on restore). New clusters get the lowest unused index. When all 8 colours are used, the 9th cluster
    reuses the lowest freed index (lowest colour that was previously used but is now free)."""
    preserve_ids = preserve_ids or set()
    previous_colours = previous_colours or {}

    # Build a map of cluster ID to desired colour
    colour_map = {}
    used_colours = set()

    # First pass: preserve colours for restored clusters
    for c in clusters:
        if c["id"] in preserve_ids and c["id"] in previous_colours:
            colour = previous_colours[c["id"]]
            colour_map[c["id"]] = colour
            used_colours.add(colour)

    # Find freed colours (were used before but not now)
    previously_used = set(previous_colours.values())
    freed_colours = sorted(previously_used - used_colours)

    # Second pass: assign lowest unused colours to new clusters
    # Prefer freed colours first, then lowest unused from 0-7
    for c in clusters:
        if c["id"] not in colour_map:
            # Try freed colours first
            if freed_colours:
                colour = freed_colours.pop(0)
            else:
                # Find lowest unused colour 0-7
                for colour in range(8):
                    if colour not in used_colours:
                        break
            colour_map[c["id"]] = colour
            used_colours.add(colour)

    # Apply colours to clusters
    return [{**c, "colour": colour_map[c["id"]]} for c in clusters]


def by_kind(notes: list[dict]) -> dict[str, list[dict]]:
    """The public records split by kind, in the order of NOTE_KINDS; a kind with no notes is left out."""
    return {k: [n for n in notes if kind_of(n) == k] for k in NOTE_KINDS if any(kind_of(n) == k for n in notes)}


def edited(clusters: list[dict], snapshot) -> bool:
    """True when the groups differ from the way North made them (a restore makes them the same again)."""
    flat = lambda rows: [(c["id"], c["name"], sorted(c["note_ids"])) for c in rows]  # noqa: E731
    return snapshot is not None and flat(clusters) != flat(snapshot)


def _find(clusters: list[dict], cluster_id) -> dict:
    c = next((x for x in clusters if x["id"] == cluster_id), None)
    if c is None:
        raise BoardError("We could not find that group.")
    return c


def move_note(clusters: list[dict], note_ids: list[str], note_id: str, target) -> list[dict]:
    """The note goes to the target cluster, or on its own when `target` is None. An emptied cluster goes."""
    if note_id not in note_ids:
        raise BoardError("We could not find that note.")
    if target is not None:
        _find(clusters, target)
    moved = [{**c, "note_ids": [n for n in c["note_ids"] if n != note_id]} for c in clusters]
    if target is not None:
        _find(moved, target)["note_ids"].append(note_id)
    return [c for c, old in zip(moved, clusters) if c["note_ids"] or not old["note_ids"]]  # one the move emptied goes; a cluster made by hand stays


def rename(s: BoardSettings, clusters: list[dict], cluster_id: str, name) -> list[dict]:
    _find(clusters, cluster_id)
    clean = clean_name(s, name)
    return [{**c, "name": clean} if c["id"] == cluster_id else c for c in clusters]


def split(s: BoardSettings, clusters: list[dict], cluster_id: str, note_ids, name=None) -> list[dict]:
    """The chosen notes leave a cluster for a new one beside it. At least one note must stay."""
    c = _find(clusters, cluster_id)
    if not isinstance(note_ids, list) or not note_ids or not all(isinstance(n, str) for n in note_ids):
        raise BoardError("Please choose the notes to split off.")
    chosen = list(dict.fromkeys(note_ids))
    if not set(chosen) <= set(c["note_ids"]):
        raise BoardError("We could not find those notes in that group.")
    if len(chosen) >= len(c["note_ids"]):
        raise BoardError("At least one note has to stay in the group. Choose fewer notes to split off.")
    room = s.name_chars - len(s.split_suffix) - 1
    new_name = clean_name(s, name) if name is not None else f"{c['name'][:room]} {s.split_suffix}"
    kept = [{**x, "note_ids": [n for n in x["note_ids"] if n not in chosen]} if x["id"] == cluster_id else x for x in clusters]
    at = next(i for i, x in enumerate(kept) if x["id"] == cluster_id) + 1
    return [*kept[:at], new_cluster(new_name, chosen, "person"), *kept[at:]]


def add_cluster(s: BoardSettings, clusters: list[dict], note_ids: list[str], name, chosen=()) -> list[dict]:
    """A cluster made by hand, by the organiser, optionally with some notes taken from where they are."""
    clean = clean_name(s, name)
    if not isinstance(chosen, (list, tuple)) or not all(isinstance(n, str) and n in note_ids for n in chosen):
        raise BoardError("We could not find those notes.")
    chosen = list(dict.fromkeys(chosen))
    kept = [{**c, "note_ids": [n for n in c["note_ids"] if n not in chosen]} for c in clusters]
    return [c for c, old in zip(kept, clusters) if c["note_ids"] or not old["note_ids"]] + [new_cluster(clean, chosen, "person")]


def keyword_groups(s: BoardSettings, notes: list[dict]) -> list[dict]:
    """The fallback when North cannot answer: notes that share a keyword (a word of 4+ letters, not a common one) go
    together, most shared word first. Words come from the notes themselves; no model, nothing invented.
    ponytail: crude plural-stripping, one word per group; a real stemmer or phrase match if people find the groups too loose."""
    words = {n["id"]: {w.rstrip("s") for w in _WORD.findall(n["text"].lower()) if w not in _STOP} for n in notes}
    df: dict[str, int] = {}
    for ws in words.values():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    too_common = len(notes) * 0.6 if len(notes) >= 5 else len(notes) + 1  # a word in most notes tells nothing
    out, taken = [], set()
    for w in sorted((w for w, c in df.items() if s.min_notes <= c <= too_common), key=lambda w: (-df[w], w)):
        ids = [n["id"] for n in notes if w in words[n["id"]] and n["id"] not in taken]
        if len(ids) >= s.min_notes:
            taken.update(ids)
            out.append(new_cluster(clean_name(s, w.capitalize()), ids, "keywords", None, FALLBACK_NOTE))
    return out
