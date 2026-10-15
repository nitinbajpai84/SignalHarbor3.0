"""BC-1: the Build centre's environment check. `GET /api/company/build/environment` gives the questions, each a provenance cell
(stated by a person, guessed from the company profile, or unknown); `PUT` confirms answers as stated by the signed-in person. Stored in the
company plane at warehouse/environment.json. A guess is computed on read and never stored, so it can never replace a stated answer."""
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.jsonfile import lock_for, read_json_strict, write_json_atomic
from sh_platform.profile import store
from sh_platform.profile.api import _name, _plane

log = logging.getLogger(__name__)
router = APIRouter()
QUESTIONS = {
    "warehouse_location": "Where may the warehouse live?",
    "warehouse_today": "Is there a warehouse or lake today?",
    "scheduler": "Is there a scheduler today?",
    "arrival": "Where do files arrive?",
    "alerts": "Where should alerts go?",
    "warehouse_target": "Which warehouse should the SQL be written for?",  # a stated answer only (SF07)
}
SYSTEM_WORDS = {"warehouse_today": ("warehouse", "lake", "snowflake", "bigquery", "redshift", "databricks", "synapse"),
                "scheduler": ("scheduler", "airflow", "cron", "dagster", "prefect")}
ALERT_WORDS = ("slack", "teams", "webhook", "email")
MAX_ANSWER = 300
DEFAULT = "Inside this company's plane, on this machine"  # A-064


def _file(plane):
    return plane.path("warehouse", "environment.json")


def _txt(c: Any) -> str:
    v = c.get("value") if isinstance(c, dict) else None
    return str(v).strip() if v is not None else ""


def _guess(value: str, source: str) -> dict:
    return store.cell(value, {"mark": "guessed", "by": "Build centre", "from": source})


def prefill(profile: dict) -> dict:
    """One cell per question, from the profile's systems and constraints. Nothing found reads unknown."""
    systems = [(sid, {k: _txt(c) for k, c in s.items() if isinstance(c, dict)}) for sid, s in sorted((profile.get("systems") or {}).items())]
    notes = [(cid, _txt(c.get("kind")) + " " + _txt(c.get("text"))) for cid, c in sorted((profile.get("constraints") or {}).items())]
    out = {"warehouse_location": _guess(DEFAULT, "Default rule: the warehouse lives in the plane")}
    for key, words in SYSTEM_WORDS.items():
        hit = next(((s.get("name") or sid, s) for sid, s in systems if any(w in (s.get("kind", "") + " " + s.get("name", "")).lower() for w in words)), None)
        out[key] = _guess(hit[0], f"Systems in the company profile: {hit[0]}") if hit else store.cell(None, {"mark": "unknown", "by": "Build centre", "from": "Nothing in the profile says"})
    lands = [(s.get("name") or sid, s["lands"]) for sid, s in systems if s.get("lands")]
    out["arrival"] = (_guess("; ".join(f"{n}: {v}" for n, v in lands), "How data lands, in the company profile") if lands
                      else store.cell(None, {"mark": "unknown", "by": "Build centre", "from": "Nothing in the profile says"}))
    out["warehouse_target"] = store.cell(None, {"mark": "unknown", "by": "Build centre", "from": "Only a person can say this"})
    alert = next((t.strip() for _, t in notes if any(w in t.lower() for w in ALERT_WORDS)), None)
    out["alerts"] = (_guess(alert, "Constraints in the company profile") if alert
                     else store.cell(None, {"mark": "unknown", "by": "Build centre", "from": "Nothing in the profile says"}))
    return out


def read(plane, profile: dict) -> dict:
    """Stated answers win; otherwise the profile's guess. Never writes."""
    saved = read_json_strict(_file(plane), dict) or {}
    guess = prefill(profile)
    answers = {}
    for key in QUESTIONS:
        c = (saved.get("answers") or {}).get(key)
        answers[key] = c if isinstance(c, dict) and c.get("mark") == "stated" else guess[key]
    return {"questions": [{"key": k, "question": q, "answer": answers[k]} for k, q in QUESTIONS.items()],
            "has_warehouse": bool(_txt(answers["warehouse_today"])) and _txt(answers["warehouse_today"]).lower() not in ("none", "no")}


def confirm(plane, key: str, value: str, who: str) -> dict:
    cell = store.cell(value, {"mark": "stated", "by": who, "from": "Confirmed in the environment check"})
    path = _file(plane)
    with lock_for(path):
        doc = read_json_strict(path, dict) or {"version": 1, "answers": {}}
        doc.setdefault("answers", {})[key] = cell
        write_json_atomic(path, doc)
    return cell


def _bad(msg: str) -> JSONResponse:
    return JSONResponse({"error": "invalid", "message": msg}, status_code=422)


@router.get("/api/company/build/environment")
def get_environment(request: Request):
    plane = _plane(request)
    return read(plane, store.raw(plane))


@router.put("/api/company/build/environment")
async def put_environment(request: Request):
    try:
        body = await request.json()
    except ValueError:
        return _bad("Send the answers as JSON.")
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict) or not answers or any(k not in QUESTIONS for k in answers):
        return _bad("Answer one or more of the questions.")
    if any(not isinstance(v, str) or not v.strip() or len(v) > MAX_ANSWER for v in answers.values()):
        return _bad(f"Each answer is a line of text, up to {MAX_ANSWER} characters.")
    plane, who = _plane(request), _name(request) or "A team member"
    for k, v in answers.items():
        confirm(plane, k, v.strip(), who)
    return read(plane, store.raw(plane))
