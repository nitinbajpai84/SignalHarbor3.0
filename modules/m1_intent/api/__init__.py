"""Module 1's router. One file per package area, so later packages add theirs without touching each other:
session.py (M1-P01); later room.py, briefing.py, private_room.py, notes.py, voice.py, board.py, together.py,
charter.py, handoff.py. Every route here must also be declared in manifest.yaml."""
from fastapi import APIRouter, Depends

from modules.m1_intent.api import briefing, session, voice  # M1-P03: briefing; M1-P06: voice

router = APIRouter(dependencies=[Depends(voice.wire_speech)])  # M1-P06: gives Nira's read-aloud its provider
router.include_router(session.router)
router.include_router(briefing.router)  # M1-P03

from modules.m1_intent.api import private_room  # noqa: E402  M1-P04

router.include_router(private_room.router)  # M1-P04
from modules.m1_intent.api import room  # M1-P02

router.include_router(room.router)  # M1-P02
router.include_router(voice.router)  # M1-P06

from modules.m1_intent.api import notes  # noqa: E402  M1-P05

router.include_router(notes.router)  # M1-P05

from modules.m1_intent.api import approver, charter  # noqa: E402  M1-P09

router.include_router(charter.router)  # M1-P09
router.include_router(approver.router)  # M1-P09

from modules.m1_intent.api import board, summary, together  # noqa: E402  M1-P07

router.include_router(board.router)  # M1-P07
router.include_router(together.router)  # M1-P07
router.include_router(summary.router)  # the summary page

from modules.m1_intent.api import walls  # noqa: E402  IC-2t

router.include_router(walls.router)  # IC-2t

from modules.m1_intent.api import roles  # noqa: E402  R1

router.include_router(roles.router)  # R1
