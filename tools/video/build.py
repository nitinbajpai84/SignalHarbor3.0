"""One command for the Signal Harbor launch film: voice, cards, recordings, the cut, sound, captions and every output.

    python tools/video/build.py --film             # re-render everything from the recordings in docs/video/out/film
                                                   # (films only what is missing; an agent take is never paid twice)
    python tools/video/build.py --film --record    # film every screen scene again on fresh data, then cut
    python tools/video/build.py --film --only 7 8      # re-record screen scenes 7 and 8 on fresh data, then cut
    python tools/video/build.py --film --assemble-only # only the cut and the outputs from what is in docs/video/out/film
    python tools/video/build.py --explainer            # the 90-second Build explainer (tools/video/explainer.py)

Outputs in docs/video/out/ (git-ignored):
  signal-harbor-launch-hero.mp4 (1920x1080), -60s.mp4, -15s.mp4, -60s-vertical.mp4 and -15s-vertical.mp4 (1080x1920),
  signal-harbor-launch-hero-share.mp4 (under 30 MB), an .srt for each cut, signal-harbor-launch-poster.png,
  and stills/ (a frame every 3 s of the hero and every 2 s of each vertical cut, for the review).
The recording server (port 8695 only) runs on a fresh copy of the demo data and is stopped at the end. Never touches data/
or ports 8400, 8501, 8502.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import cards  # noqa: E402
import narrate  # noqa: E402
import record  # noqa: E402
import sound  # noqa: E402
from common import BASE, DATA, FPS, LEAD, OUT, ROOT, WORK, phrase_time, scenes  # noqa: E402

PORT = 8695
NAME = "signal-harbor-launch"
HERO = OUT / f"{NAME}-hero.mp4"
STILLS = OUT / "stills"
BROLL = ROOT / "docs" / "video" / "broll"
NAVY = "0x0F1B2D"
V = ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS)]
DIP = 0.22
LT_IN, LT_ON = 1.2, 2.5

# Where the product text being discussed sits in the 1920x1080 frame, per screen scene: [(until scene second, (x0, y0, x1, y1))].
# A caption goes in the band (top: y 170 to 300, bottom: y 890 to 1030) and a lower third in the corner (top: y 24 to 134, bottom:
# y 740 to 860) that cover less of it. Read from the stills of the cut.
FOCUS = {
    4: [(99, (60, 330, 1860, 1050))],
    5: [(99, (0, 330, 1920, 1060))],
    6: [(99, (0, 100, 1920, 800))],
    7: [(99, (60, 300, 1920, 880))],
    8: [(99, (0, 300, 1920, 1060))],
    9: [(99, (0, 330, 1100, 480))],
    11: [(6, (0, 200, 1920, 1050)), (99, (1100, 0, 1920, 420))],
    12: [(7, (0, 170, 1920, 800)), (99, (0, 420, 1100, 1080))],
    13: [(99, (0, 330, 1920, 1060))],
    14: [(99, (0, 330, 1920, 1060))],
    15: [(99, (0, 60, 1920, 700))],
    16: [(99, (0, 300, 1920, 1050))],
    18: [(4, (0, 60, 1920, 780)), (99, (0, 500, 1920, 1060))],
}
CAP_BOX = {"top": (380, 170, 1540, 300), "bottom": (380, 890, 1540, 1030)}
LT_BOX = {"top": (48, 24, 620, 134), "bottom": (48, 740, 620, 860)}


def focus_at(n: int, t: float):
    for until, box in FOCUS.get(n, []):
        if t <= until:
            return box
    return None


def overlap(a, b) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def band(boxes: dict, focus, tie: str) -> str:
    """The band that covers less of the subject; `tie` when they cover the same (nothing, usually)."""
    if focus is None:
        return tie
    o = {k: overlap(v, focus) for k, v in boxes.items()}
    return tie if o["top"] == o["bottom"] else min(o, key=o.get)


BREATH = {15: 0.8, 17: 0.8}   # seconds of picture and music with no voice before the North and Trust chapters (added to the scene before)


# ---- the server ----------------------------------------------------------------------------------------------------------------

def up() -> bool:
    try:
        return urllib.request.urlopen(BASE + "/", timeout=3).status == 200
    except OSError:
        return False


def stop_server() -> None:
    """Stop whatever listens on port 8695, and nothing else."""
    ps = (f"Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(1.5)


def fresh_server() -> subprocess.Popen:
    stop_server()
    subprocess.run([sys.executable, str(ROOT / "tools/make_test_env.py"), "film", "--seed"], check=True, cwd=ROOT)
    proc = subprocess.Popen([sys.executable, str(ROOT / "tools/serve_test.py"), "--port", str(PORT), "--data-root", str(DATA)],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        if up():
            return proc
        time.sleep(1)
    raise SystemExit("the recording server did not start")


# ---- ffmpeg --------------------------------------------------------------------------------------------------------------------

def ff(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed: " + r.stderr[-2000:])
    return r.stderr


def length(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def smooth(u: str) -> str:
    return f"(({u})*({u})*(3-2*({u})))"


def camera(zooms: list[dict], d: float, push: float = 0.045) -> tuple[str, str, str]:
    """zoompan expressions: a slow push over the whole shot, plus each marked push-in onto a figure (eased in, held, out)."""
    T = "(on/30)"
    base = f"(1+{push}*{smooth(f'clip({T}/{d:.3f},0,1)')})"
    zs, xs, ys = [], [], []
    for z in zooms:
        t0, rin, rout = z["t"], z["in"], z["out"]
        b = t0 + rin + z["hold"]
        e = "(" + smooth(f"clip(({T}-{t0:.3f})/{rin},0,1)") + "-" + smooth(f"clip(({T}-{b:.3f})/{rout},0,1)") + ")"
        zs.append(f"{z['z'] - 1:.3f}*{e}")
        xs.append(f"{z['cx'] - 960:.1f}*{e}")
        ys.append(f"{z['cy'] - 540:.1f}*{e}")
    zoom = base + (f"*(1+{'+'.join(zs)})" if zs else "")
    cx = "960" + "".join(f"+{x}" for x in xs)
    cy = "540" + "".join(f"+{y}" for y in ys)
    return zoom, f"max(0,min(iw-iw/zoom,2*({cx})-iw/zoom/2))", f"max(0,min(ih-ih/zoom,2*({cy})-ih/zoom/2))"


def dips(vf: str, d: float, fin: bool, fout: bool) -> str:
    if fin:
        vf += f",fade=t=in:st=0:d={DIP}:color={NAVY}"
    if fout:
        vf += f",fade=t=out:st={d - DIP:.3f}:d={DIP}:color={NAVY}"
    return vf


def lower_overlay(lower: Path | None, d: float) -> tuple[list[str], str]:
    """The lower third: 2.5 s on screen (in at 1.2 s, out at 3.7 s)."""
    if not lower:
        return [], ""
    return (["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(lower)],
            f";[1:v]format=rgba,fade=t=in:st={LT_IN}:d=0.3:alpha=1,fade=t=out:st={LT_IN + LT_ON - 0.3:.2f}:d=0.3:alpha=1[lt];[v0][lt]overlay=0:0:eof_action=pass[v1]")


def pace(rec: dict, planned: float) -> float:
    """A take that ran long (an action came late) is played a little faster so the shot ends with its words; never over 1.3x.
    Only the picture's pace changes: every frame and every reply is shown as recorded."""
    over = float(rec["seconds"]) / planned
    return round(min(over, 1.3), 3) if float(rec["seconds"]) - planned > 1.0 else 1.0


def screen_segment(rec: dict, d: float, lower: Path | None, fin: bool, fout: bool, dest: Path, speed: float = 1.0) -> None:
    src = WORK / rec["clip"]
    zooms = [{**z, "t": z["t"] / speed, "in": z["in"] / speed, "hold": z["hold"] / speed, "out": z["out"] / speed} for z in rec.get("zooms", [])]
    z, x, y = camera(zooms, d)
    vf = (f"[0:v]setpts=PTS/{speed},tpad=stop_mode=clone:stop_duration=2,trim=duration={d:.3f},setpts=PTS-STARTPTS,scale=3840:2160:flags=lanczos,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s=1920x1080:fps={FPS},setsar=1")
    vf = dips(vf, d, fin, fout) + "[v0]"
    extra, ov = lower_overlay(lower, d)
    ff("-i", str(src), *extra, "-filter_complex", vf + ov, "-map", "[v1]" if ov else "[v0]", *V, "-t", f"{d:.3f}", "-an", str(dest))


def card_segment(src: Path, d: float, lower: Path | None, fin: bool, fout: bool, dest: Path) -> None:
    vf = dips(f"[0:v]tpad=stop_mode=clone:stop_duration=3,trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={FPS},setsar=1", d, fin, fout) + "[v0]"
    extra, ov = lower_overlay(lower, d)
    ff("-i", str(src), *extra, "-filter_complex", vf + ov, "-map", "[v1]" if ov else "[v0]", *V, "-t", f"{d:.3f}", "-an", str(dest))


def broll_segment(clip: Path, d: float, fin: bool, fout: bool, dest: Path) -> None:
    """Nitin's clip: filled to 1920x1080, graded towards the navy palette, a little grain; only here, never over the product."""
    vf = ("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,"
          "eq=saturation=0.85:contrast=1.04:brightness=-0.02,colorbalance=bs=0.06:ms=0.03:hs=-0.02,noise=alls=6:allf=t,setsar=1")
    ff("-i", str(clip), "-filter_complex", dips(vf, d, fin, fout) + "[v0]", "-map", "[v0]", *V, "-t", f"{d:.3f}", "-an", str(dest))


# ---- captions ------------------------------------------------------------------------------------------------------------------

def cues(text: str, limit: int = 78) -> list[str]:
    """A sentence in caption-sized pieces (two lines at most), cut at the comma or space nearest the middle."""
    if len(text) <= limit:
        return [text]
    mid = len(text) // 2
    cands = [m.end() for m in re.finditer(r"[,;:] ", text)] or [m.end() for m in re.finditer(" ", text)]
    cut = min(cands, key=lambda i: abs(i - mid))
    return cues(text[:cut].strip(), limit) + cues(text[cut:].strip(), limit)


def two_lines(text: str, width: int = 44) -> str:
    if len(text) <= width:
        return text
    sp = [m.start() for m in re.finditer(" ", text)]
    cut = min(sp, key=lambda i: abs(i - len(text) / 2))
    return text[:cut] + "\n" + text[cut + 1:]


def stamp(t: float, ass: bool = False) -> str:
    ms = int(round(max(t, 0) * 1000))
    if ass:
        return f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def sentence_cues(sentence: str, a: float, b: float, limit: int = 78) -> list[tuple[float, float, str]]:
    parts = cues(sentence, limit)
    tot = sum(len(p) for p in parts) or 1
    out, t = [], a
    for p in parts:
        e = t + (b - a) * len(p) / tot
        out.append((t, e, p))
        t = e
    return out


def write_captions(items: list[tuple], srt: Path, ass: Path, vertical: bool = False, top: list[str] | None = None) -> None:
    """items: (start, end, text[, place]). place "top" lifts the burned caption above a subject low in the frame; "hide" leaves it
    out of the picture (the card already shows those words) but keeps it in the .srt."""
    items = [(*x, "")[:4] for x in items]
    srt.write_text("".join(f"{i + 1}\n{stamp(a)} --> {stamp(b - 0.03)}\n{two_lines(t)}\n\n" for i, (a, b, t, _) in enumerate(items)), encoding="utf-8")
    w, h = (1080, 1920) if vertical else (1920, 1080)
    size, margin, width = (52, 190, 26) if vertical else (46, 54, 44)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,Arial,{size},&H00F6F4EE,&H00F6F4EE,&H262D1B0F,&H262D1B0F,1,0,0,0,100,100,0,0,3,14,0,2,80,80,{margin},1\n"
            f"Style: Top,Arial,64,&H00F6F4EE,&H00F6F4EE,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,0,0,8,60,60,45,1\n"
            f"Style: Sub,Arial,40,&H00C2C25F,&H00C2C25F,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,60,60,125,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = [f"Dialogue: 0,{stamp(a, True)},{stamp(b - 0.03, True)},Cap,,0,0,{170 if pl == 'top' and not vertical else 0},,{'{' + chr(92) + 'an8}' if pl == 'top' else ''}"
          f"{two_lines(t, width).replace(chr(10), chr(92) + 'N')}" for a, b, t, pl in items if pl != "hide"]
    if top:
        end = stamp(items[-1][1] + 5, True)
        ev += [f"Dialogue: 0,0:00:00.00,{end},Top,,0,0,0,,{top[0]}", f"Dialogue: 0,0:00:00.00,{end},Sub,,0,0,0,,{top[1]}"]
    ass.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


# ---- the hero ------------------------------------------------------------------------------------------------------------------

def timeline() -> list[dict]:
    narr = json.loads((WORK / "narration.json").read_text(encoding="utf-8"))
    recs = json.loads((WORK / "recordings.json").read_text(encoding="utf-8")) if (WORK / "recordings.json").exists() else {}
    items, t = [], 0.0
    for s in scenes():
        n = s["n"]
        if n in BREATH and items:
            items[-1]["d"] = round(items[-1]["d"] + BREATH[n], 3)
            t += BREATH[n]
        if s["chapter"]:
            items.append({"kind": "chapter", "n": n, "d": cards.CHAPTER, "start": t})
            t += cards.CHAPTER
        d = cards.length(n)
        kind = s["kind"]
        if kind in ("screen", "agent"):
            if str(n) not in recs or not (WORK / recs[str(n)]["clip"]).exists():
                raise SystemExit(f"scene {n} has no recording; run without --assemble-only")
            rec = recs[str(n)]
            speed = rec.get("speed") or pace(rec, d)
            # the take's resting tail after the last word is cut to half a second; a take with a fixed speed or the editor's voice
            # placement keeps its length
            secs = float(rec["seconds"]) if rec.get("voice_at") or rec.get("speed") else min(float(rec["seconds"]), d + 0.3)
            d = max(d, secs / speed)
        else:
            rec, speed = None, 1.0
        spans, parts = narr[str(n)]["spans"], None
        if rec and rec.get("voice_at"):
            # the editor's placement for a take whose actions came late: each sentence starts on its moment in the picture
            parts = [narrate.say(x, f"scene {n}") for x in s["say_sent"]]
            spans = []
            for at, wav in zip(rec["voice_at"], parts):
                a = at / speed - LEAD
                spans.append([round(a, 3), round(a + narrate.seconds(wav), 3)])
            d = max(d, LEAD + spans[-1][1] + 0.3)
        items.append({"kind": kind, "n": n, "d": round(d, 3), "start": t, "voice": WORK / f"voice{n}.wav", "speed": speed, "parts": parts,
                      "rec": rec, "broll": s["broll"], "spans": spans, "cap": s["cap_sent"]})
        t += round(d, 3)
    return items


def cut_hero(items: list[dict], clean: bool = False) -> Path:
    """The hero's picture. clean: no lower thirds (the cuts are built from it)."""
    segs = []
    for i, it in enumerate(items):
        prev = items[i - 1] if i else None
        nxt = items[i + 1] if i + 1 < len(items) else None
        screenish = it["kind"] in ("screen", "agent")
        fin = prev is None or not (screenish and prev["kind"] in ("screen", "agent"))
        fout = nxt is None or not (screenish and nxt["kind"] in ("screen", "agent"))
        dest = WORK / f"seg-{i:02d}.mp4"
        pos = band(LT_BOX, focus_at(it["n"], LT_IN + LT_ON / 2), "bottom")
        lower = cards.CARDS / f"lower-{it['n']}{'-top' if pos == 'top' else ''}.png"
        lower = lower if lower.exists() and it["kind"] != "chapter" and not clean else None
        if clean and not (cards.CARDS / f"lower-{it['n']}.png").exists() or clean and it["kind"] == "chapter":
            segs.append(dest)           # nothing to take off: the segment is the same
            continue
        if clean:
            dest = WORK / f"seg-{i:02d}-clean.mp4"
        if it["kind"] == "chapter":
            card_segment(cards.CARDS / f"chapter-{it['n']}.mp4", it["d"], None, True, True, dest)
        elif screenish:
            screen_segment(it["rec"], it["d"], lower, fin, fout, dest, it["speed"])
        elif it["kind"] == "broll" and (BROLL / f"{it['broll'].lower()}.mp4").exists():
            broll_segment(BROLL / f"{it['broll'].lower()}.mp4", it["d"], fin, fout, dest)
        else:
            card_segment(cards.CARDS / f"scene-{it['n']}.mp4", it["d"], lower, fin, fout, dest)
        segs.append(dest)
        print(f"  {it['kind']:7} {it['n']:>2}: {it['d']:.2f} s at {it['start']:.2f}", flush=True)
    lst = WORK / ("segments-clean.txt" if clean else "segments.txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    out = WORK / ("hero-clean.mp4" if clean else "hero-picture.mp4")
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out))
    return out


def hero_audio(items: list[dict], total: float) -> Path:
    n = int(total * sound.SR) + sound.SR
    voice = np.zeros(n)
    fx = np.zeros(n)
    for it in items:
        if it["kind"] == "chapter":
            continue
        if it["parts"]:
            for wav, (a, _) in zip(it["parts"], it["spans"]):
                sound.place(voice, sound.read_wav(wav), it["start"] + LEAD + a)
        else:
            sound.place(voice, sound.read_wav(it["voice"]), it["start"] + LEAD)
        for kind, at in (it["rec"] or {}).get("marks", []):
            sound.place(fx, sound.cue(kind), it["start"] + at / it["speed"])
        if it["n"] == 1:
            sound.place(fx, sound.cue("strike"), it["start"] + LEAD + phrase_time(1, "The number changed"))
        if it["n"] == 3:
            sound.place(fx, sound.cue("swell"), it["start"] + LEAD + phrase_time(3, "This is") - 2.4)
        if it["n"] == 20:
            sound.place(fx, sound.cue("swell") * 0.6, it["start"] - 1.6)
    st = {it["n"]: it["start"] for it in items if it["kind"] != "chapter"}
    sec = {"cold": st[2], "reveal": st[3] + LEAD + phrase_time(3, "This is"), "pulse": (st[4] - 1.6, st[16] + 12),
           "padonly": (st[17] - 1.6, st[19]), "close": st[20]}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), voice)
    mix = WORK / "hero-mix.wav"
    sound.write_wav(mix, voice + music + fx)
    return mix


def loudnorm(src: Path, dest: Path) -> None:
    """Two-pass loudness normalisation to -16 LUFS, true peak -1 dB."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    af = (f"loudnorm=I=-16:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
    ff("-i", str(src), "-af", af, "-ar", "48000", str(dest))


def finish(picture: Path, audio: Path, ass: Path, dest: Path) -> None:
    ff("-i", picture.name, "-i", audio.name, "-vf", f"ass={ass.name}", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18",
       "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
       str(dest), cwd=picture.parent)


def plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", html.unescape(text).lower())


def on_card(n: int) -> str:
    """The words a card shows, letters and digits only, so the burned caption does not repeat them."""
    f = cards.CARDS / f"scene-{n}.html"
    if not f.exists():
        return ""
    body = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", f.read_text(encoding="utf-8"), flags=re.S)
    return plain(re.sub(r"<[^>]+>", " ", body))


def make_hero() -> tuple[list[dict], float]:
    items = timeline()
    picture = cut_hero(items)
    cut_hero(items, clean=True)
    total = length(picture)
    caps = []
    for it in items:
        if it["kind"] == "chapter":
            continue
        clip = BROLL / f"{it['broll'].lower()}.mp4"
        card = on_card(it["n"]) if it["kind"] == "card" or (it["kind"] == "broll" and not clip.exists()) else ""
        place = "" if it["n"] in FOCUS else (it["rec"] or {}).get("captions", "")
        for sent, (a, b) in zip(it["cap"], it["spans"]):
            for c in sentence_cues(sent, it["start"] + LEAD + a, it["start"] + LEAD + b):
                pl = place
                if it["n"] in FOCUS:
                    pl = band(CAP_BOX, focus_at(it["n"], (c[0] + c[1]) / 2 - it["start"]), "bottom")
                caps.append((*c, "hide" if card and plain(sent) in card else pl))
    write_captions(caps, OUT / f"{NAME}-hero.srt", WORK / "hero.ass")
    raw = hero_audio(items, total)
    mix = WORK / "hero-audio.wav"
    loudnorm(raw, mix)
    finish(picture, mix, WORK / "hero.ass", HERO)
    (WORK / "timeline.json").write_text(json.dumps([{k: (str(v) if isinstance(v, Path) else v) for k, v in it.items() if k not in ("rec", "parts")}
                                                    for it in items], indent=1), encoding="utf-8")
    return items, length(HERO)


# ---- the social cut and the teaser ---------------------------------------------------------------------------------------------

SHOTS = {"S01": (1, None), "S02": (1, "USD 57.6"), "S05": (3, None), "S09": (5, None), "S11": (5, "One wire"), "S14": (7, "The report issued"),
         "S26": (13, None), "S30": (14, None), "S32": (15, None), "S38": (17, "Your data stays"), "S43": (20, None)}


SPOKEN = {"fifty seven point six million dollars": "USD 57.6 million", "twelve thousand four hundred dollars": "USD 12,400"}


def written(text: str) -> str:
    """A cut's line as the captions show it: figures as figures."""
    for said, shown in SPOKEN.items():
        text = text.replace(said, shown)
    return text


# Vertical cuts (1080x1920): the product is not letterboxed; each shot is a crop of the 1920x1080 picture centred on what the voice
# is naming (the figure, the answer or the control), shown 1080x1360 between a name band on top (200 px) and the caption band
# underneath (360 px), so a caption never covers the product. (scene, phrase) -> (crop width, [(second in the shot, centre x, centre y)]);
# the crop is 1080:1360 (width x 1.259 high), at most 857 wide, and glides between the points. Centres read from the stills.
VCARDS = {1, 3, 17, 20}      # cards, laid out again for vertical (cards.py, v-scene-N)
CROPS = {
    (5, None): (857, [(0, 380, 470), (3.3, 560, 300), (6.5, 560, 560), (9.5, 480, 790)]),        # the case, then Tally's chips and wire lines
    (5, "One wire"): (857, [(0, 560, 560), (4.5, 480, 790)]),
    (7, "The report issued"): (640, [(0, 860, 540), (5, 860, 540)]),                              # Known now against the issued report
    (13, None): (857, [(0, 520, 640), (7, 520, 740)]),                                            # the chat box, the typed words
    (14, None): (700, [(0, 400, 640), (4.5, 420, 560)]),                                          # Waiting for your approval, then the button
    (15, None): (760, [(0, 420, 480), (5, 420, 420)]),                                            # North's question and the typed words
}
VBAND, VFG_H, VNAME = 200, 1360, 150


def crop_filter(spec: tuple, d: float) -> str:
    cw, pts = spec
    ch = round(cw * VFG_H / 1080)

    def lerp(k: int) -> str:
        e = "if(lt(t,{b}),{y0}+({y1}-{y0})*(t-{a})/({b}-{a}),{rest})"
        out = f"{pts[-1][k]}"
        for (a, *p0), (b, *p1) in reversed(list(zip(pts, pts[1:]))):
            out = e.format(a=a, b=b, y0=p0[k - 1], y1=p1[k - 1], rest=out)
        return out
    x, y = lerp(1), lerp(2)
    return (f"crop=w={cw}:h={ch}:x='max(0,min(1920-{cw},({x})-{cw / 2}))':y='max(0,min(1080-{ch},({y})-{ch / 2}))',"
            f"scale=1080:{VFG_H}:flags=lanczos,pad=1080:1920:0:{VBAND}:color={NAVY}")


def make_cut(name: str, items: list[dict]) -> Path:
    rows = json.loads((WORK / f"cut-{name}.json").read_text(encoding="utf-8"))
    start = {it["n"]: it["start"] for it in items if it["kind"] != "chapter"}
    picture = WORK / "hero-clean.mp4"
    segs, vsegs, caps, capsv, voice_at, t = [], [], [], [], [], 0.0
    pre = 0.35
    for i, r in enumerate(rows):
        ids = re.findall(r"S\d\d", r["picture"])
        sid = ids[-1] if "then" in r["picture"] else ids[0]
        n, phrase = SHOTS[sid]
        src = start[n] + (LEAD + phrase_time(n, phrase) - 0.3 if phrase else 0.0)
        d = round(pre + r["seconds"] + (0.9 if i == len(rows) - 1 else 0.45), 3)
        dest = WORK / f"{name}-seg{i}.mp4"
        vf = f"fade=t=in:st=0:d=0.2:color={NAVY},fade=t=out:st={d - 0.2:.3f}:d=0.2:color={NAVY}"
        ff("-ss", f"{src:.3f}", "-i", str(picture), "-t", f"{d:.3f}", "-vf", vf, *V, "-an", str(dest))
        segs.append(dest)
        vdest = WORK / f"{name}-vseg{i}.mp4"
        if n in VCARDS:
            ff("-ss", f"{src - start[n]:.3f}", "-i", str(cards.CARDS / f"v-scene-{n}.mp4"), "-t", f"{d:.3f}", "-vf", vf, *V, "-an", str(vdest))
        else:
            ff("-ss", f"{src:.3f}", "-i", str(picture), "-t", f"{d:.3f}", "-vf", crop_filter(CROPS[(n, phrase)], d) + "," + vf, *V, "-an", str(vdest))
        vsegs.append(vdest)
        sents = [x for x in re.split(r"(?<=[.!?])\s+", r["text"]) if x]
        a = t + pre
        for x in sents:
            dd = narrate.seconds(narrate.say(x, f"{name} cut"))
            caps += sentence_cues(written(x), a, a + dd)
            capsv += sentence_cues(written(x), a, a + dd, 52)
            a += dd + 0.28
        voice_at.append((WORK / r["wav"], t + pre))
        t += d
    pics = []
    for tag, parts in (("", segs), ("-v", vsegs)):
        lst = WORK / f"{name}{tag}-segments.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        pics.append(WORK / f"{name}{tag}-picture.mp4")
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(pics[-1]))
    pic = pics[0]
    total = length(pic)
    n = int(total * sound.SR) + sound.SR
    voice = np.zeros(n)
    for wav, at in voice_at:
        sound.place(voice, sound.read_wav(wav), at)
    reveal = sum(length(s) for s in segs[:1]) if name == "social" else 0.6
    sec = {"cold": 0.5, "reveal": reveal, "pulse": (reveal + 2, total - 8), "padonly": (total - 8, total - 4), "close": total - 4}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), voice)
    raw = WORK / f"{name}-mix.wav"
    sound.write_wav(raw, voice + music)
    mix = WORK / f"{name}-audio.wav"
    loudnorm(raw, mix)
    label = "60s" if name == "social" else "15s"
    write_captions(caps, OUT / f"{NAME}-{label}.srt", WORK / f"{name}.ass")
    dest = OUT / f"{NAME}-{label}.mp4"
    finish(pic, mix, WORK / f"{name}.ass", dest)
    write_captions(capsv, WORK / f"{name}-v.srt", WORK / f"{name}-v.ass", vertical=True, top=["SIGNAL HARBOR", "Every figure, explained."])
    finish(pics[1], mix, WORK / f"{name}-v.ass", OUT / f"{NAME}-{label}-vertical.mp4")
    return dest


# ---- share copy, poster, stills ------------------------------------------------------------------------------------------------

def share_copy(total: float) -> Path:
    dest = OUT / f"{NAME}-hero-share.mp4"
    kbps = int(27.5 * 8 * 1024 / total) - 96
    log = WORK / "share2pass"
    common = ["-i", str(HERO), "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", str(log)]
    ff(*common, "-pass", "1", "-an", "-f", "mp4", "NUL")
    ff(*common, "-pass", "2", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dest))
    return dest


def poster(items: list[dict]) -> None:
    it = next(i for i in items if i["n"] == 20 and i["kind"] != "chapter")
    at = it["start"] + it["d"] - 1.3   # everything has landed, before the fade to navy
    ff("-ss", f"{at:.2f}", "-i", str(WORK / "hero-picture.mp4"), "-frames:v", "1", str(OUT / f"{NAME}-poster.png"))


def stills(total: float) -> None:
    """For the review: a frame every 3 s of the hero and every 2 s of each vertical cut."""
    STILLS.mkdir(parents=True, exist_ok=True)
    for old in STILLS.glob("*.png"):
        old.unlink()
    ff("-i", str(HERO), "-vf", "fps=1/3,scale=1280:-2", str(STILLS / "hero-%03d.png"))
    for label in ("60s", "15s"):
        ff("-i", str(OUT / f"{NAME}-{label}-vertical.mp4"), "-vf", "fps=1/2,scale=540:-2", str(STILLS / f"vertical-{label}-%03d.png"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", action="store_true", help="the launch film (the only film this script makes now)")
    ap.add_argument("--skip-record", action="store_true")
    ap.add_argument("--record", action="store_true", help="film the screen scenes again on fresh data (agent takes are kept)")
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--only", type=int, nargs="*", default=[])
    ap.add_argument("--keep-server", action="store_true")
    ap.add_argument("--explainer", action="store_true", help="the 90-second Build explainer instead (tools/video/explainer.py, port 8696)")
    a = ap.parse_args()
    if a.explainer:     # its own process: the explainer sets its data folder and port before the shared modules load
        flags = [f for f in ("--assemble-only", "--keep-server") if getattr(a, f[2:].replace("-", "_"))]
        subprocess.run([sys.executable, str(Path(__file__).with_name("explainer.py")), *flags], check=True)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    proc = None
    try:
        if not a.assemble_only:
            narrate.main()
            cards.render()
            recs = json.loads((WORK / "recordings.json").read_text(encoding="utf-8")) if (WORK / "recordings.json").exists() else {}
            missing = [s["n"] for s in scenes() if s["kind"] in ("screen", "agent") and str(s["n"]) not in recs]
            if not (a.record or a.only or missing):
                print("every scene has its recording; re-rendering from them (pass --record to film the screen scenes again)", flush=True)
            elif not a.skip_record:
                proc = fresh_server()
                record.main(a.only, agents=True)
        if proc is not None and not a.keep_server:
            stop_server()
            proc = None
        items, total = make_hero()
        print(f"hero: {total:.1f} s", flush=True)
        for name in ("social", "teaser"):
            print(f"{name}: {length(make_cut(name, items)):.1f} s", flush=True)
        share = share_copy(total)
        print(f"share copy: {share.stat().st_size / 1e6:.1f} MB", flush=True)
        poster(items)
        stills(total)
    finally:
        if proc is not None and not a.keep_server:
            stop_server()


if __name__ == "__main__":
    main()
