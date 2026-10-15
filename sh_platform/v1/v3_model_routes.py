"""Harbor 3.0 industry model, packs and language routes (logic in v3_model). Every failure answers a plain message."""
from fastapi import APIRouter, HTTPException, Request

from sh_platform.profile.api import _name, _plane
from sh_platform.v1 import v3_model as M

router = APIRouter()


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


def _who(request: Request) -> str:
    return _name(request) or "A team member"


def _answer(body: dict) -> str:
    if body.get("answer") not in ("admit", "reject"):
        raise HTTPException(400, "Answer admit or reject.")
    return body["answer"]


@router.get("/api/v3/model")
def get_model(request: Request):
    return M.model(_plane(request))


@router.post("/api/v3/model/proposals/{pid}")
async def answer_proposal(pid: str, request: Request):
    plane, answer = _plane(request), _answer(await _json(request))
    try:
        return M.answer_proposal(plane, pid, answer, _who(request))
    except KeyError:
        raise HTTPException(404, M.NOT_FOUND) from None


@router.get("/api/v3/packs")
def get_packs(request: Request):
    return M.packs(_plane(request))


@router.get("/api/v3/language")
def get_language(request: Request):
    return M.language(_plane(request))


@router.post("/api/v3/language/words")
async def post_word(request: Request):
    plane, b = _plane(request), await _json(request)
    try:
        return M.add_word(plane, str(b.get("word") or ""), str(b.get("means") or ""), _who(request))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/api/v3/language/corrections/{cid}")
async def answer_correction(cid: str, request: Request):
    plane, answer = _plane(request), _answer(await _json(request))
    try:
        return M.answer_correction(plane, cid, answer, _who(request))
    except KeyError:
        raise HTTPException(404, M.NOT_FOUND) from None
