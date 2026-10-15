"""Shared bits for the launch film tools: paths, the page size, the off-camera sign-in, the script parser and the narration clock."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "video" / "out"
WORK = OUT / "film"              # per-scene audio, frames, clips, cards for the launch film (v1 and v2 kept their own folders)
COST = ROOT / "docs" / "video" / "COST.md"
SCRIPT = ROOT / "docs" / "video" / "SCRIPT.md"
import os
PORT = int(os.environ.get("SH_FILM_PORT", 8695))   # the explainer records on its own server (8696)
BASE = f"http://127.0.0.1:{PORT}"
DATA = ROOT / ".sh-tmp" / "testenv" / os.environ.get("SH_FILM_ENV", "film") / "data"
W, H, FPS = 1920, 1080, 30         # the film
VW, VH, DSF = 1440, 810, 4 / 3     # the page: 1440x810 CSS px drawn at 1920x1080 device px, so text is large and crisp
LEAD = 0.3                         # silence at the start of a scene before the voice
sys.path.insert(0, str(ROOT))


def password_for(email: str) -> str:
    """The seeded password for one account. Held in memory only: never printed, logged or written."""
    for line in (DATA / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == email and not line.startswith("#"):
            return p[1]
    raise SystemExit(f"no seeded account {email}")


def sign_in_state(pw, who: str) -> dict:
    """Sign in off camera in a throwaway context and return its cookies for the recording context."""
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": VW, "height": VH})
    page = ctx.new_page()
    page.goto(BASE + "/login")
    email = f"{who}.evergreen@example.test"
    page.fill("#email", email)
    page.fill("#password", password_for(email))
    page.click("button[type=submit]")
    page.wait_for_url(lambda u: "/login" not in u, timeout=30000)
    state = ctx.storage_state()
    b.close()
    return state


def load_json(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def sentences(text: str) -> list[str]:
    return [s for s in SENT.split(text.strip()) if s]


def scenes() -> list[dict]:
    """Scenes from SCRIPT.md: n, name, chapter, lower, kind, caption (as written), spoken (as said), and both per sentence."""
    out: list[dict] = []
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"### Scene (\d+): (.+)", line)
        if m:
            out.append({"n": int(m[1]), "name": m[2].strip(), "chapter": "", "lower": "", "kind": "screen", "broll": "", "text": []})
        elif out and line.startswith("- ") and ":" in line:
            k, v = line[2:].split(":", 1)
            key = {"Chapter": "chapter", "Lower third": "lower", "Kind": "kind", "Broll": "broll"}.get(k.strip())
            if key:
                out[-1][key] = v.strip()
        elif out and line.startswith("> "):
            out[-1]["text"].append(line[2:].strip())
    for s in out:
        raw = sentences(" ".join(s.pop("text")))
        s["cap_sent"] = [re.sub(r"\{([^|}]*)\|([^}]*)\}", r"\1", x) for x in raw]
        s["say_sent"] = [re.sub(r"\{([^|}]*)\|([^}]*)\}", r"\2", x) for x in raw]
        s["caption"], s["spoken"] = " ".join(s["cap_sent"]), " ".join(s["say_sent"])
    return out


def scene(n: int) -> dict:
    return next(s for s in scenes() if s["n"] == n)


def phrase_time(n: int, phrase: str) -> float:
    """Seconds from the start of scene n's voice at which `phrase` (as written in the captions) is said. Each sentence has a
    start and an end (narration.json); inside a sentence the time is shared out by characters."""
    s = scene(n)
    spans = load_json(WORK / "narration.json")[str(n)]["spans"]
    for cap, (a, b) in zip(s["cap_sent"], spans):
        at = cap.find(phrase)
        if at >= 0:
            return a + (b - a) * at / max(len(cap), 1)
    raise KeyError(f"'{phrase}' is not in the narration of scene {n}")
