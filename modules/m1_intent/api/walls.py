"""The company's walls (IC-2t): one read-only list, a wall per topic or department. Numbers only: no card text, no names."""
from fastapi import APIRouter, Request

from modules.m1_intent.api import deps
from modules.m1_intent.store.notes import NoteStore

router = APIRouter()
guarded = deps.guarded()


@router.get("/walls")
@guarded
async def walls(request: Request):
    """Started sessions of the signed-in company: id, topic, purpose, state, how many cards, how many people contributed."""
    store = deps.store(request)

    def work():
        notes = NoteStore(store._plane)  # ponytail: SessionStore keeps its plane private; one read of the same plane
        return {"walls": [{**w, "cards_count": len(notes.board(w["id"])), "people_count": notes.contributors(w["id"])} for w in store.walls()]}

    return await deps.blocking(work)
