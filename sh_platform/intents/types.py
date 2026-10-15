"""IC v2 (02, 03): the intent types catalogue and North's one-line proposal for the chooser."""
import re
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
CATALOGUE = Path(__file__).resolve().parents[2] / "modules" / "m1_intent" / "contracts" / "intent_types.yaml"

# ponytail: keyword rules, first match wins in this order; swap for the model call through the gateway if misses matter.
RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("decision", "It asks for one choice to be made.", re.compile(r"\b(decide|decision|choose which|which one|whether to|pick between|approve)\b", re.I)),
    ("pulse", "It describes a regular round of reports.", re.compile(r"\b(weekly|every week|each week|check-?in|round of|what ran)\b", re.I)),
    ("problem", "It names something that is wrong today.", re.compile(r"\b(broke|broken|wrong|fails?|failing|failed|error|late|missing|stuck|keeps? happening|not working|issue|problem)\b", re.I)),
    ("initiative", "It asks for something new to be added or changed, which is a project, not a repair (ruling 31).", re.compile(r"\b(wants?|would like|need) (a|an|one|another|to add|to have|new)\b|\bnew (column|field|report|screen|feature|option|filter|button)\b|\badd(ed)? (a|an|one|another)\b|\b(improvements?|enhancements?|nice to have|feature request)\b", re.I)),
    ("brainstorm", "It asks people to think of ideas together.", re.compile(r"\b(brainstorm|ideas?|think (through|about|together)|explore|options for|how might we)\b", re.I)),
    ("initiative", "It describes a project with a goal.", re.compile(r"\b(project|initiative|build|launch|set up|introduce|improve|create|implement|plan|roll ?out)\b", re.I)),
]
LIKELY = 2


@lru_cache(maxsize=1)
def load_catalogue() -> dict:
    return yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))


def classify_text(text: str) -> dict:
    """North's proposal: {type, reason, confidence, title}. type is None when it cannot tell; the person always confirms."""
    line = " ".join(text.split())
    title = line[:80].rstrip(" .,;:")
    hits = [(t, why, len(rx.findall(line))) for t, why, rx in RULES if rx.search(line)]
    if not hits:
        return {"type": None, "reason": "Do you want people to think with you, or is something already broken?", "confidence": None, "title": title}
    t, why, n = max(hits, key=lambda h: h[2])  # max keeps the first of equals, so rule order breaks ties
    return {"type": t, "reason": why, "confidence": "Likely" if n >= LIKELY or len(hits) == 1 else "Possible", "title": title}


class Classify(BaseModel):
    text: str


@router.get("/api/intents/types")
def get_intents_types(request: Request):
    return load_catalogue()


@router.post("/api/intents/classify")
def post_intents_classify(body: Classify, request: Request):
    if not body.text.strip() or len(body.text) > 600:
        return JSONResponse({"message": "Say what you want to do in one to six hundred characters."}, status_code=422)
    return classify_text(body.text)
