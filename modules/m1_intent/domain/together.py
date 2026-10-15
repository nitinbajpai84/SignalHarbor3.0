"""Back in the room (M1-20 to M1-23, D-020). The rules of voting, agreeing, commenting and ticking; the stored shape is
{votes: {cluster: {seat: option}}, agrees: {cluster: [seat]}, comments: {cluster: [comment]}, ticked: [cluster],
paused_at}. Votes and agree marks are kept by seat so each person has one; the screens only ever get counts and the
viewer's own choice. A comment by name carries the name; an anonymous one carries nothing about its author.

`read_together_result` is what M1-P09 (the charter) reads: the ticked clusters with their vote tally, note count and
agree count. Its shape is described in contracts/board.yaml.
"""
from modules.m1_intent.domain.board import BoardError, BoardSettings, WrongStage, cluster_name, load_settings, mask_sealed, readable
import calendar
import json
import re
from datetime import datetime, timezone

from modules.m1_intent.domain.charter import build_graph
from modules.m1_intent.store.board import BoardStore, TogetherStore
from modules.m1_intent.store.together_shelves import ShelfStore
from modules.m1_intent.store.notes import NoteStore
from modules.m1_intent.store.sessions import SessionStore

VOTING = "together"
CLOSED_VOTING = {"paused": "The room is held. You can vote again when the organiser carries on.",
                 "signing": "The room has moved on to signing, so voting is closed."}
SHELVES = ("must", "should", "good_to_have", "future")  # A-058
ALIAS = {"could": "good_to_have"}  # the old name reads as the new one; stored files and votes are not migrated
CONTRACT_ID = {"good_to_have": "could"}  # the id contracts/charter.yaml and board.yaml still list; see the alias note there
NOT_TOGETHER = "The room is not back together yet."


def check_voting(state: str) -> None:
    if state != VOTING:
        raise WrongStage(CLOSED_VOTING.get(state, NOT_TOGETHER))


def check_readable(state: str, paused_from) -> None:
    if not readable(state, paused_from, ("together", "signing", "closed")):
        raise WrongStage(NOT_TOGETHER)


def vote(s: BoardSettings, data: dict, cluster: str, seat: str, option) -> dict:
    """The seat's one vote on the cluster, replacing its earlier one; None takes it back."""
    if option is not None and option not in s.option_ids:
        raise BoardError("Please choose one of the options shown.")
    mine = {k: v for k, v in data["votes"].get(cluster, {}).items() if k != seat}
    if option is not None:
        mine[seat] = option
    return {**data, "votes": {**data["votes"], cluster: mine}}


def agree(data: dict, cluster: str, seat: str, agreed) -> dict:
    if not isinstance(agreed, bool):
        raise BoardError("Please choose agree or not.")
    marks = [x for x in data["agrees"].get(cluster, []) if x != seat]
    return {**data, "agrees": {**data["agrees"], cluster: [*marks, seat] if agreed else marks}}


def done(data: dict, seat: str, is_done) -> dict:
    """This seat's "I'm done" signal: readiness only, it ends nothing (the organiser decides)."""
    if not isinstance(is_done, bool):
        raise BoardError("Please choose done or not.")
    rest = [x for x in data.get("done", []) if x != seat]
    return {**data, "done": [*rest, seat] if is_done else rest}


def comment(s: BoardSettings, data: dict, cluster: str, text, anonymous, author_name: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise BoardError("Please write something first.")
    text = " ".join(text.split())
    if len(text) > s.comment_chars:
        raise BoardError(f"That is too long. Please keep it under {s.comment_chars} characters.")
    if anonymous not in (True, False, None):
        raise BoardError("Please choose By name or Anonymous.")
    have = data["comments"].get(cluster, [])
    if len(have) >= s.comments_per_cluster:
        raise BoardError("This group has as many comments as it can hold.")
    row = {"text": text, "anonymous": anonymous is True}
    if anonymous is not True and author_name:
        row["author_name"] = author_name
    return {**data, "comments": {**data["comments"], cluster: [*have, row]}}


def tick(data: dict, clusters: list[dict], cluster: str, ticked) -> dict:
    if not isinstance(ticked, bool) or cluster not in {c["id"] for c in clusters}:
        raise BoardError("We could not find that group.")
    rest = [x for x in data["ticked"] if x != cluster]
    return {**data, "ticked": [*rest, cluster] if ticked else rest, "touched": sorted({*data.get("touched", []), cluster})}


def tally(s: BoardSettings, data: dict, cluster: str) -> dict:
    counts = {o: 0 for o in s.option_ids}
    for option in data["votes"].get(cluster, {}).values():
        if option in counts:
            counts[option] += 1
    return counts


def priority(s: BoardSettings, votes: dict) -> str | None:
    """The tally is the priority (D-020): the one option with more votes than any other; none on a tie or no votes."""
    top = max(votes.values(), default=0)
    leaders = [o for o in s.option_ids if votes[o] == top]
    return leaders[0] if top > 0 and len(leaders) == 1 else None


def auto_decision(s: BoardSettings, votes: dict) -> str:
    """The vote rule (contracts/board.yaml `auto_tick`): "tick" when the backing votes (Must and Should) are more than all the
    others together, "tie" when they are level, else "none" (nobody backed it, or too few)."""
    back = sum(votes[o] for o in s.auto_priorities)
    rest = sum(n for o, n in votes.items() if o not in s.auto_priorities)
    return "none" if back < s.auto_min_votes or back < rest else "tick" if back > rest else "tie"


def apply_auto_ticks(s: BoardSettings, data: dict, clusters: list[dict]) -> dict:
    """Ticks follow the vote for every group the organiser has not decided on (`touched`); the organiser's own tick or
    removal stays. Run after each vote and when the stage closes."""
    mine = [c for c in data["ticked"] if c in data.get("touched", [])]
    auto = [c["id"] for c in clusters if c["id"] not in data.get("touched", []) and auto_decision(s, tally(s, data, c["id"])) == "tick"]
    return {**data, "ticked": [c["id"] for c in clusters if c["id"] in {*mine, *auto}]}  # board order


def cluster_view(s: BoardSettings, data: dict, cluster: dict, seat: str | None, shelf_row: dict | None = None) -> dict:
    """One cluster as the room sees it: counts, the tally, the viewer's own vote and mark, the thread."""
    cid, votes = cluster["id"], tally(s, data, cluster["id"])
    agrees = data["agrees"].get(cid, [])
    thread = data["comments"].get(cid, [])
    return {"id": cid, "name": cluster["name"], "note_ids": cluster["note_ids"], "note_count": len(cluster["note_ids"]),
            "agree_count": len(agrees), "comment_count": len(thread), "votes": votes, "vote_total": sum(votes.values()),
            "priority": priority(s, votes), "ticked": cid in data["ticked"],
            "auto_ticked": cid in data["ticked"] and cid not in data.get("touched", []), "tie": auto_decision(s, votes) == "tie",
            "my_vote": data["votes"].get(cid, {}).get(seat) if seat else None, "my_agree": bool(seat and seat in agrees),
            "shelf": shelf_row["shelf"] if shelf_row else shelf_id(priority(s, votes)),  # the organiser's shelf, else the tally
            "shelf_reason": shelf_row["reason"] if shelf_row else None, "review_date": shelf_row["review_date"] if shelf_row else None,
            "comments": [{k: v for k, v in c.items()} for c in thread]}


def result(s: BoardSettings, data: dict, clusters: list[dict], stage: str, session_id: str, alone: int,
           shelves: dict | None = None) -> dict:
    """What the charter reads (see contracts/board.yaml). No seat, no author, no comment text. A cluster on a shelf
    carries that shelf as its priority; one on Future is in neither list (so not in the charter's problems, its
    "left for later" or the hand-off) and is listed under `parked` with its reason and review date."""
    shelves = shelves or {}
    away = {c: r for c, r in shelves.items() if r["shelf"] == "future"}

    def row(c: dict) -> dict:
        v = cluster_view(s, data, c, None)
        out = {k: v[k] for k in ("id", "name", "note_ids", "note_count", "agree_count", "comment_count", "votes",
                                 "vote_total", "priority")}
        shelf = shelves.get(c["id"], {}).get("shelf")
        return {**out, "priority": CONTRACT_ID.get(shelf, shelf)} if shelf else out
    here = [c for c in clusters if c["id"] not in away]
    ticked = [row(c) for c in here if c["id"] in data["ticked"]]
    carried = [{"id": c["id"], "name": c["name"], "note_count": len(c["note_ids"])} for c in here
               if c["id"] not in data["ticked"]]
    parked = [{"id": c["id"], "name": c["name"], "note_count": len(c["note_ids"]), "reason": away[c["id"]]["reason"],
               "review_date": away[c["id"]]["review_date"]} for c in clusters if c["id"] in away]
    out = {"session_id": session_id, "stage": stage, "ticked": ticked, "carried": carried, "on_its_own_count": alone}
    return {**out, "parked": parked} if parked else out  # `parked` appears only when something is parked: earlier readers see the old shape


def read_together_result(plane, session_id: str) -> dict:
    """The together stage's result for M1-P09: the ticked clusters (name, notes, vote tally, agree count), the clusters
    carried to a later session, and how many notes are on their own. Reads the stored board only; nothing is changed
    and no person is named. Raises StoreError for a damaged or missing-id file."""
    s = load_settings()
    board, together = BoardStore(plane).get(session_id), TogetherStore(plane).get(session_id)
    session = SessionStore(plane).get(session_id)
    notes = mask_sealed(plane, NoteStore(plane).board(session_id))  # a result is read by many: sealed notes are closed in it
    shown = {n["id"]: n for n in notes}
    clusters = [{**c, "name": cluster_name(c["name"], [shown[n] for n in c["note_ids"] if n in shown]),
                 "note_ids": [n for n in c["note_ids"] if n in shown]} for c in board["clusters"]]
    inside = {n for c in clusters for n in c["note_ids"]}
    return result(s, together, clusters, session["state"] if session else "", session_id,
                  len([n for n in shown if n not in inside]), ShelfStore(plane).get(session_id)["shelves"])


# ---- shelves (A-058): the organiser's shelf for a cluster; the tally is what it is read as until one is set
def shelf_id(x):
    """`could` reads as `good_to_have` everywhere."""
    return ALIAS.get(x, x)


GOVERNED_FIELDS = ("owners", "classification", "may_see", "resolving", "affects", "review_date")  # module 2's six (contracts/governed_state.yaml)
FIELD_WORDS = {"owners": "an owner", "classification": "a classification", "may_see": "who may see", "resolving": "who resolves it",
               "affects": "what it affects", "review_date": "a review date"}
NO_MEASURES = "Define the measures first."


def may_shelve(cluster: dict, shelf: str) -> tuple[bool, str]:
    """Must or Should only when the cluster is governed (A-054). `cluster` carries the served `governed` and `missing`
    (absent when there is no baseline or no measure behind it)."""
    if shelf not in ("must", "should"):
        return True, ""
    if "governed" not in cluster:
        return False, NO_MEASURES
    if cluster["governed"]:
        return True, ""
    words = [FIELD_WORDS.get(f, f) for f in cluster.get("missing", [])]
    what = words[0] if len(words) < 2 else ", ".join(words[:-1]) + " and " + words[-1]
    return False, f"Needs {what} before it can sit on {shelf.capitalize()}."


def default_review_date(now: float) -> str:
    """Today plus one quarter (three calendar months, the day kept or cut to the month's end), from the injected clock."""
    d = datetime.fromtimestamp(now, timezone.utc).date()
    y, m = divmod(d.month + 2, 12)
    y, m = d.year + y, m + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def move_to_shelf(store: dict, cluster: dict, shelf, reason, by: str, now: float, reason_chars: int, by_account: str | None = None) -> dict:
    """The shelf store after the organiser puts `cluster` on `shelf`; Future needs a reason and gets a review date."""
    shelf = shelf_id(shelf)
    if shelf not in SHELVES:
        raise BoardError("Please choose one of the shelves shown.")
    text = " ".join(reason.split()) if isinstance(reason, str) else ""
    if shelf == "future" and not text:
        raise BoardError("Please say why this is parked for later.")
    if len(text) > reason_chars:
        raise BoardError(f"That is too long. Please keep it under {reason_chars} characters.")
    ok, why = may_shelve(cluster, shelf)
    if not ok:
        raise BoardError(why)
    was = store["shelves"].get(cluster["id"], {}).get("shelf")
    row = {"shelf": shelf, "reason": text if shelf == "future" else None,
           "review_date": default_review_date(now) if shelf == "future" else None}
    move = {"by": by, "by_account": by_account, "at": datetime.fromtimestamp(now, timezone.utc).isoformat(), "cluster": cluster["id"], "from": was, "to": shelf}
    return {**store, "shelves": {**store["shelves"], cluster["id"]: row}, "moves": [*store["moves"], move]}



# ---- IC-3t: fields the Define screen reads on each cluster
def measure_codes(pack_problem_id, pack_problems: list[dict], pack_kpis: list[dict]) -> list[str]:
    """The pack measure ids a cluster's pack problem lists (the charter's own link, build_graph); [] with no link."""
    g = build_graph([{"id": "c", "title": "", "library_problem_id": pack_problem_id}], pack_problems, pack_kpis, "") if pack_problem_id else None
    return [k["id"] for k in g["kpis"]] if g else []


def governed_of(plane, baseline_id: str | None, codes: list[str]) -> dict:
    """{governed, missing} for a cluster from module 2's governed state, read by path (no module import): governed when every
    measure in `codes` has all six fields stated; `missing` is the union of the others. {} with no baseline or no measures."""
    if not (baseline_id and codes):
        return {}
    try:
        doc = json.loads(plane.path("intents", "m2_baseline", baseline_id, "governed_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    doc = doc if isinstance(doc, dict) else {}
    stated = lambda m, f: isinstance(doc.get(m), dict) and isinstance(doc[m].get(f), dict) and doc[m][f].get("mark") == "stated"  # noqa: E731
    missing = [f for f in GOVERNED_FIELDS if not all(stated(m, f) for m in codes)]
    return {"governed": not missing, "missing": missing}


def latest_signed_baseline_id(plane) -> str | None:
    """Id of the baseline of the newest signed module 2 outcome (the outcome's own `baseline_id`, else its file name), read by path (same rule as module 3's latest_signed_baseline;
    a module may not import another). None when there is none or a file cannot be read."""
    folder = plane.path("intents", "m2_baseline", "outcomes")
    best = None
    for f in (folder.glob("*.json") if folder.is_dir() else []):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(d, dict) and d.get("kind") == "baseline" and re.fullmatch(r"[0-9a-f]{32}", f.stem)
                and str(d.get("signed_at") or "").strip() and d.get("signatures")):
            own = d.get("baseline_id") if re.fullmatch(r"[0-9a-f]{32}", str(d.get("baseline_id"))) else f.stem
            best = max(best or (str(d["signed_at"]), own), (str(d["signed_at"]), own))
    return best[1] if best else None
