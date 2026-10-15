"""Narration for the launch film: one WAV per sentence (cached by text hash), joined per scene, with exact sentence times.

    python tools/video/narrate.py              # voice what changed (a sentence already voiced is never paid for again)
    python tools/video/narrate.py --audition   # one line in onyx, ash and sage (out/film/voice/audition-*.wav)

Voice: OpenAI text to speech (POST /v1/audio/speech, gpt-4o-mini-tts), key OPENAI_API_KEY from .env, never printed.
Each sentence is its own request, so a reworded sentence costs one sentence and the sentence times are exact.
Every paid call is written to docs/video/COST.md (OpenAI does not return a price; the cost is worked out from the
published rate for this model, about 0.015 USD a minute of speech, and marked as an estimate).
Writes docs/video/out/film/narration.json: per scene the seconds, the start and end of each sentence and the word count;
and cut-<name>.json for the social cut and the teaser lines.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import urllib.request
import wave
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import COST, LEAD, ROOT, SCRIPT, WORK, scenes  # noqa: E402

MODEL = "gpt-4o-mini-tts"
VOICE = "ash"    # chosen in the audition (README): 143 wpm, low and warm; onyx rushed (167 wpm), sage high and breathy
STYLE = ("Voice-over for a premium product film for family-office principals. Calm, warm, confident executive voice; "
         "quiet authority, never salesy. Unhurried pace, about 145 words a minute, with a natural pause at every full stop. "
         "Say figures clearly. Read exactly the text given, nothing added.")
RATE_PER_MIN = 0.015     # USD a minute of speech, published estimate for gpt-4o-mini-tts
BUDGET = 5.0             # the whole film, every paid call together (Nitin)
GAP = 0.2                # breath between sentences
TEMPO = 1.2              # the voice reads at about 130 words a minute; played 1.2 times faster (pitch kept) it is 155, the film's pace
INDEX = WORK / "narration.json"
CACHE = WORK / "voice"
SR = 24000


def openai_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY is not in .env")


# ---- the cost log -------------------------------------------------------------------------------------------------------------

HEAD = ("# Launch film: paid calls\n\nBudget: 5 USD for the whole film across OpenRouter (agents) and OpenAI (voice), approved by Nitin "
        "for this film. One row per paid call; free checks and decisions are noted under the table.\n\n"
        "| When | What | Provider and model | Cost (USD) |\n|---|---|---|---|\n")


def spent() -> float:
    total = 0.0
    if COST.exists():
        for line in COST.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("| 20") and cells:
                try:
                    total += float(cells[-1].split()[0])
                except (ValueError, IndexError):
                    pass
    return total


def log_cost(item: str, provider: str, cost: float) -> None:
    lines = (COST.read_text(encoding="utf-8") if COST.exists() else HEAD).splitlines()
    at = max(i for i, l in enumerate(lines) if l.startswith("|")) + 1
    lines.insert(at, f"| {datetime.now():%Y-%m-%d %H:%M} | {item} | {provider} | {cost:.4f} |")
    COST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def note_cost(text: str) -> None:
    body = COST.read_text(encoding="utf-8") if COST.exists() else HEAD
    COST.write_text(body.rstrip("\n") + f"\n\n- {datetime.now():%Y-%m-%d %H:%M} {text}\n", encoding="utf-8")


# ---- speech -------------------------------------------------------------------------------------------------------------------

def seconds(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def tts(text: str, voice: str = VOICE) -> bytes:
    body = {"model": MODEL, "voice": voice, "input": text, "instructions": STYLE, "response_format": "wav"}
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + openai_key(), "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise SystemExit(f"speech failed: HTTP {e.code} {e.read()[:300]!r}") from None


def _normal(raw: bytes, dest: Path) -> None:
    """The returned WAV (its header may carry no length) to a clean 24 kHz mono WAV with the silence at both ends trimmed."""
    tmp = dest.with_suffix(".in.wav")
    tmp.write_bytes(raw)
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-af", trim, "-ar", str(SR), "-ac", "1", str(dest)], check=True)
    tmp.unlink()


def say(text: str, what: str, voice: str = VOICE) -> Path:
    """One sentence as a WAV, from the cache when the same words were voiced before."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{MODEL}|{voice}|{STYLE}|{text}".encode()).hexdigest()[:20]
    part = CACHE / f"{key}.wav"
    if part.exists():
        return paced(part)
    if spent() >= BUDGET - 0.05:
        raise SystemExit(f"the film budget ({BUDGET} USD) is used up; stopping before another paid call")
    _normal(tts(text, voice), part)
    log_cost(f"voice, {what}, {len(text.split())} words, {seconds(part):.1f} s", f"OpenAI {MODEL} ({voice}), estimate",
             round(seconds(part) / 60 * RATE_PER_MIN, 4))
    return paced(part)


def paced(part: Path) -> Path:
    """The cached sentence at the film's pace (free: ffmpeg atempo keeps the pitch)."""
    dest = part.with_name(f"{part.stem}-t{int(TEMPO * 100)}.wav")
    if not dest.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(part), "-af", f"atempo={TEMPO}", str(dest)], check=True)
    return dest


def _silence(dest: Path, secs: float) -> Path:
    if not dest.exists():
        b = io.BytesIO()
        with wave.open(b, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(b"\0\0" * int(secs * SR))
        dest.write_bytes(b.getvalue())
    return dest


def join(parts: list[Path], dest: Path, gap: float = GAP) -> None:
    breath = _silence(CACHE / f"gap-{gap}.wav", gap)
    lst = WORK / "voice-concat.txt"
    lines = []
    for i, p in enumerate(parts):
        if i:
            lines.append(f"file '{breath.as_posix()}'")
        lines.append(f"file '{p.as_posix()}'")
    lst.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", str(SR), "-ac", "1", str(dest)], check=True)


def cut_lines(name: str) -> list[dict]:
    """The Voice column of the social cut or teaser table in SCRIPT.md: [{time, picture, text}]."""
    body = SCRIPT.read_text(encoding="utf-8")
    head = {"social": "## Social cut", "teaser": "## Teaser"}[name]
    part = body.split(head, 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in part.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and re.match(r"\d+:\d\d", cells[0]):
            rows.append({"time": cells[0], "picture": cells[1], "text": cells[2]})
    return rows


def main() -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    index = {}
    for s in scenes():
        n = str(s["n"])
        parts = [say(x, f"scene {n}") for x in s["say_sent"]]
        spans, t = [], 0.0
        for p in parts:
            d = seconds(p)
            spans.append([round(t, 3), round(t + d, 3)])
            t += d + GAP
        wav = WORK / f"voice{n}.wav"
        join(parts, wav)
        index[n] = {"seconds": round(seconds(wav), 3), "spans": spans, "words": len(s["spoken"].split())}
    INDEX.write_text(json.dumps(index, indent=1), encoding="utf-8")
    for name in ("social", "teaser"):
        rows = cut_lines(name)
        for i, r in enumerate(rows):
            sents = [x for x in re.split(r"(?<=[.!?])\s+", r["text"]) if x]
            parts = [say(x, f"{name} cut line {i + 1}") for x in sents]
            wav = WORK / f"{name}-{i}.wav"
            join(parts, wav, 0.28)
            r["wav"], r["seconds"] = wav.name, round(seconds(wav), 3)
        (WORK / f"cut-{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return index


def audition() -> None:
    line = "The September report went out on the third of October. Fifty seven point six million dollars."
    for v in ("onyx", "ash", "sage"):
        p = say(line, f"audition {v}", v)
        dest = CACHE / f"audition-{v}.wav"
        dest.write_bytes(p.read_bytes())
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "astats=metadata=0,volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        mean = re.search(r"mean_volume: (\S+)", r)
        print(v, f"{seconds(p):.2f} s", f"{len(line.split()) / seconds(p) * 60:.0f} wpm", "mean", mean[1] if mean else "?")


if __name__ == "__main__":
    if "--audition" in sys.argv:
        audition()
    else:
        idx = main()
        print("narration:", round(sum(v["seconds"] for v in idx.values()) + LEAD * len(idx), 1), "s,",
              sum(v["words"] for v in idx.values()), "words")
