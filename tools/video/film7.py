"""Film v4 (docs/video/SCRIPT-V4.md, approved 12 Oct): about 3:15, five numbered steps, the 60 s cut and the 15 s teaser.

    python tools/video/film7.py --rehearse        # every scene in Testing mode (free) on a fresh copy; keeps nothing as a take
    python tools/video/film7.py --record          # the takes: scenes 4, 5 and 8 once in Real use, 6 and 9 in Testing; then the cut
    python tools/video/film7.py --record 9        # only scene 9 (Testing) on a fresh copy, then the cut
    python tools/video/film7.py                   # only the cut and the outputs, from docs/video/out/film7

Reuses the launch film's tools: narrate.say (voice, cached by text hash, cost in COST.md), record.Recorder and Scene (pointer,
rings, loading paused out), cards.render (frame-exact HTML cards), build's camera, captions, loudness and finish, sound's bed,
cues and ducking, vid6_prep's off-camera steps. Own data (.sh-tmp/testenv/vid7, restored from a snapshot before each run), own UI
build (D:/Temp/vid7/dist, from the current source), own port 8697, stopped at the end.
Outputs (docs/video/out/): signal-harbor-film-v4.mp4 and -share.mp4, -60s / -15s (each also -vertical), .srt for each, -poster.png.
"""
import os
import sys

os.environ["SH_FILM_ENV"] = "vid7"
os.environ["SH_FILM_PORT"] = "8697"

import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import cards  # noqa: E402
import common  # noqa: E402
import narrate  # noqa: E402
import record  # noqa: E402
import sound  # noqa: E402
from common import BASE, DATA, DSF, FPS, LEAD, OUT, ROOT, VH, VW, sign_in_state  # noqa: E402

PORT = 8697
WORK = OUT / "film7"
CARDS = WORK / "cards"
NAME = "signal-harbor-film-v4"
HERO = OUT / f"{NAME}.mp4"
SCRIPT = ROOT / "docs/video/SCRIPT-V4.md"
DIST = Path("D:/Temp/vid7/dist")           # the UI built from the current source (the Action page landed after ui/dist was built)
SNAP = DATA.parent / "data.snap"           # the seeded company plus the prepared project, restored before each run
NAVY = build.NAVY
TAIL = 0.45
NUM = 1.3                                  # a step's number card
STEPS = ["Ask", "Design", "Build and prove", "Read", "Act"]
STEP_OF = {4: 1, 5: 2, 6: 3, 7: 3, 8: 4, 9: 5}
AGENT_OF = {1: "North", 2: "Span, the architect", 3: "Span, the builder", 4: "Lumen", 5: "Tally"}
REAL = {4, 5}                              # one Real-use take each (live agent replies); scene 8 makes no model call, so Testing
MIN_D = {11: 6.2}                          # the close holds after its words
FRAME = (1844, 1037, 38, 43)               # the product inside the frame, under the progress bar
FONTS = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&"
         "family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap")
# the captions show figures as written; the voice says them in words
WRITTEN = [("fourteen manager statements", "14 manager statements"), ("a hundred and eighty thousand dollars", "USD 180,000"),
           ("four point one seven percent against two point seven one", "4.17% against 2.71%"),
           ("One point four six ahead", "+1.46 points ahead"), ("A twelve thousand four hundred dollar break", "A USD 12,400 break")]


def scenes() -> list[dict]:
    common.SCRIPT = SCRIPT
    return common.scenes()


def written(text: str) -> str:
    for said, shown in WRITTEN:
        text = text.replace(said, shown)
    return text


# ---- voice ----------------------------------------------------------------------------------------------------------------------

def voice() -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    index = {}
    for s in scenes():
        wavs = [narrate.say(x, f"film v4 scene {s['n']}") for x in s["say_sent"]]
        spans, t = [], 0.0
        for w in wavs:
            d = narrate.seconds(w)
            spans.append([round(t, 3), round(t + d, 3)])
            t += d + narrate.GAP
        index[str(s["n"])] = {"wavs": [str(w) for w in wavs], "spans": spans, "cap": [written(c) for c in s["cap_sent"]],
                              "said": s["cap_sent"], "seconds": spans[-1][1] if spans else 0, "words": len(s["spoken"].split())}
    (WORK / "narration.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


def narr() -> dict:
    return json.loads((WORK / "narration.json").read_text(encoding="utf-8"))


def phrase_at(nr: dict, n: int, phrase: str) -> tuple[int, float, float]:
    """(sentence, offset of the phrase inside the sentence, its time in the scene's natural voice)."""
    s = nr[str(n)]
    for i, (said, (a, b)) in enumerate(zip(s["said"], s["spans"])):
        at = said.find(phrase)
        if at >= 0:
            off = (b - a) * at / max(len(said), 1)
            return i, off, a + off
    raise KeyError(f"'{phrase}' is not in scene {n}")


# ---- cards ----------------------------------------------------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;background:var(--ds-ground);color:var(--ds-ink);font-family:'IBM Plex Sans',sans-serif;overflow:hidden}
.stage{position:relative;width:1920px;height:1080px;display:flex;flex-direction:column;justify-content:center;padding:60px 170px 0;overflow:hidden}
.glow{position:absolute;inset:-200px;background:radial-gradient(900px 640px at 74% 24%,color-mix(in srgb,var(--ds-teal) 20%,transparent),transparent 70%),
  radial-gradient(700px 520px at 10% 95%,color-mix(in srgb,var(--ds-teal) 9%,transparent),transparent 70%);animation:drift var(--D) linear both;z-index:0}
.vig{position:absolute;inset:0;background:radial-gradient(1400px 900px at 50% 50%,transparent 55%,#0007 100%);z-index:0}
.push{position:relative;z-index:1;display:flex;flex-direction:column;justify-content:center;height:100%;animation:push var(--D) cubic-bezier(.4,0,.6,1) both;transform-origin:40% 50%}
@keyframes push{from{transform:scale(1)}to{transform:scale(var(--P,1.03))}}
@keyframes drift{from{transform:translate(0,0) scale(1)}to{transform:translate(-60px,30px) scale(1.06)}}
@keyframes up{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes out{from{opacity:1}to{opacity:0}}
@keyframes wipe{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes grey{to{color:var(--ds-ink-muted)}}
@keyframes flip{from{opacity:0;transform:perspective(900px) rotateX(-80deg)}to{opacity:1;transform:none}}
@keyframes land{from{opacity:0;transform:translateY(-26px) scale(.96)}to{opacity:1;transform:none}}
.a{opacity:0;animation:up .6s cubic-bezier(.2,.7,.2,1) both}
.f{opacity:0;animation:fade .7s ease-out both}
.w{display:inline-block;opacity:0;animation:up .3s cubic-bezier(.2,.7,.2,1) both}
.serif{font-family:'Fraunces',Georgia,serif;font-optical-sizing:auto}
.mono{font-family:'IBM Plex Mono',monospace}
.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:26px;letter-spacing:.16em;text-transform:uppercase;color:var(--ds-teal-bright);font-weight:600}
h1{font-family:'Fraunces',Georgia,serif;font-size:118px;line-height:1.02;font-weight:600;letter-spacing:-.02em}
h2{font-family:'Fraunces',Georgia,serif;font-size:80px;line-height:1.08;font-weight:600;letter-spacing:-.01em}
.sub{font-size:40px;color:var(--ds-ink-soft);line-height:1.36}
.card{background:color-mix(in srgb,var(--ds-surface,#16253A) 92%,transparent);border:2px solid var(--ds-line,#2A3A50);border-radius:22px}
.teal{color:var(--ds-teal-bright)}.amber{color:var(--ds-amber)}.muted{color:var(--ds-ink-muted)}
.strike{position:relative;display:inline-block}
.strike::after{content:'';position:absolute;left:-10px;right:-10px;top:52%;height:7px;border-radius:4px;background:var(--ds-amber);transform-origin:left;
  transform:scaleX(0);animation:wipe .5s cubic-bezier(.6,0,.2,1) var(--S) both}
.mark{width:140px;height:140px}
.rule{width:150px;height:6px;border-radius:3px;background:var(--ds-teal-bright);transform-origin:left;animation:wipe .8s cubic-bezier(.6,0,.2,1) both}
.steps{display:flex;gap:26px;margin-top:70px}
.step{flex:1;border-top:4px solid var(--ds-teal-bright);padding-top:24px}
.step .k{font-family:'IBM Plex Mono',monospace;font-size:26px;color:var(--ds-teal-bright);font-weight:600}
.step .t{font-family:'Fraunces',Georgia,serif;font-size:46px;font-weight:600;margin-top:8px;line-height:1.1}
.step .g{font-size:28px;color:var(--ds-ink-soft);margin-top:10px}
"""
VCSS = """html,body{width:1080px!important;height:1920px!important}
.stage{width:1080px!important;height:1920px!important;padding:220px 70px 400px!important}
h1{font-size:96px!important}h2{font-size:64px!important}.sub{font-size:36px!important}
.steps{flex-direction:column!important;gap:22px!important;margin-top:50px!important}.step{padding-top:12px!important}
.step .t{font-size:44px!important}.row2{flex-direction:column!important;align-items:flex-start!important;gap:30px!important}
.big{font-size:104px!important}"""


def tokens() -> str:
    return cards.tokens()


def page(body: str, d: float, push: float = 1.03, extra: str = "", script: str = "") -> str:
    return (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{tokens()}{CSS}{extra}</style>"
            f"<body style='--D:{d:.2f}s;--P:{push}'><div class=stage><div class=glow></div><div class=vig></div>"
            f"<div class=push>{body}</div></div><script>{script}</script></body>")


def at(t: float, cls: str = "a") -> str:
    return f'class={cls} style="animation-delay:{max(t, 0):.2f}s"'


def words(text: str, t: float, gap: float = 0.05) -> str:
    return " ".join(f'<span class=w style="animation-delay:{t + i * gap:.2f}s">{w}</span>' for i, w in enumerate(text.split()))


def card_length(n: int, nr: dict) -> float:
    return max(round(LEAD + nr[str(n)]["seconds"] + TAIL, 3), MIN_D.get(n, 0))


def card_items(nr: dict) -> dict:
    def say(n, phrase, early=0.2):
        return LEAD + phrase_at(nr, n, phrase)[2] - early

    out: dict[str, tuple[str, float]] = {}
    mark = cards.MARK

    # 1 · Monday, 9 a.m.: the council's question, and the inputs landing round it
    d = card_length(1, nr)
    ins = [("14 manager PDFs", "fourteen manager statements", 1180, 190), ("Administrator export", "an administrator export", 1290, 380),
           ("Trading system file", "a trading file", 1180, 570), ("Benchmark workbook", "someone's spreadsheet", 1290, 760),
           ("Inbox · 23 unread", "someone's spreadsheet", 1180, 900)]
    chips = "".join(f"""<div class="card" style="position:absolute;left:{x}px;top:{y}px;padding:20px 30px;font-size:34px;font-weight:600;
        opacity:0;animation:land .55s cubic-bezier(.2,.7,.2,1) {say(1, c) + (0.6 if i == 4 else 0):.2f}s both"><span class=mono style="color:var(--ds-amber);
        font-size:24px;margin-right:16px">{['PDF', 'CSV', 'XLS', 'XLSX', 'MAIL'][i]}</span>{t}</div>""" for i, (t, c, x, y) in enumerate(ins))
    out["scene-1"] = (page(f"""<div style="position:absolute;inset:0">{chips}</div>
      <div class="card a" style="width:860px;padding:44px 50px;animation-delay:.25s;border-left:10px solid var(--ds-teal-bright)">
        <div class=eyebrow>Family council · invite</div>
        <div class=serif style="font-size:64px;font-weight:600;margin-top:20px">Monday 9:00</div>
        <div style="font-size:46px;margin-top:16px;line-height:1.25">{words('How did we do in September?', say(1, 'How did we do'))}</div></div>""",
                          d, 1.025), d)

    # 2 · late, and not tied: the calendar flips, the total moves, Why?
    d = card_length(2, nr)
    t3, t7, tm, tw, tp = (say(2, "So the report"), say(2, "Then a fund"), say(2, "the total moves"), say(2, "nobody can say"),
                          say(2, "The people are good"))
    cal = lambda day, what, t, col: (f"""<div class=card style="width:250px;text-align:center;overflow:hidden;opacity:0;animation:flip .6s cubic-bezier(.2,.7,.2,1) {t:.2f}s both">
        <div style="background:{col};color:#0F1B2D;font-family:'IBM Plex Mono';font-weight:600;font-size:26px;padding:10px">OCT</div>
        <div class=serif style="font-size:110px;font-weight:600;line-height:1.1">{day}</div>
        <div style="font-size:28px;color:var(--ds-ink-soft);padding:0 10px 20px">{what}</div></div>""")
    out["scene-2"] = (page(f"""<div class=row2 style="display:flex;gap:90px;align-items:center">
        <div style="display:flex;gap:30px">{cal(3, 'Report issued', t3, 'var(--ds-teal-bright)')}{cal(7, 'A fund is revised', t7, 'var(--ds-amber)')}</div>
        <div><div class="serif big strike" style="--S:{tm + .3:.2f}s;font-size:120px;font-weight:600;opacity:0;animation:fade .4s {t3 + .4:.2f}s both,grey .5s {tm + .3:.2f}s both">USD 57.6m</div>
          <div class="serif amber a" style="font-size:84px;font-weight:600;margin-top:16px;animation-delay:{tm + .6:.2f}s">+180,000</div>
          <div class="serif" style="font-size:120px;font-weight:700;margin-top:10px"><span {at(tw)}>Why?</span></div></div></div>
      <div style="margin-top:70px;font-size:44px;font-weight:500">{words('The people are good.', tp)} <span class=amber>{words('The trail is missing.', tp + 1.2)}</span></div>""",
                          d), d)

    # 3 · the promise: the mark, the line, five steps and their agents
    d = card_length(3, nr)
    t0 = say(3, "turns that question", .1)
    steps = "".join(f"""<div class="step a" style="animation-delay:{t0 + .5 + i * .32:.2f}s"><div class=k>{i + 1}</div><div class=t>{s}</div>
        <div class=g>{AGENT_OF[i + 1]}</div></div>""" for i, s in enumerate(STEPS))
    out["scene-3"] = (page(f"""<div class=row2 style="display:flex;align-items:center;gap:36px">
        <img class=mark src="{mark}" style="opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) .1s both">
        <div><h1 style="font-size:96px" {at(.3)}>Signal Harbor</h1><div class="sub" style="margin-top:6px" {at(.6)}>Every figure, explained.</div></div></div>
      <div class=steps>{steps}</div>
      <div style="margin-top:60px;font-size:40px;font-weight:600">{words('Four agents draft.', say(3, 'Four agents'))} <span class=teal>{words('A named person signs every step.', say(3, 'A named person'))}</span></div>""",
                          d, 1.025), d)

    # number cards: "2 · Design", with the agent
    for k, s in enumerate(STEPS, 1):
        out[f"num-{k}"] = (page(f"""<div style="display:flex;align-items:baseline;gap:40px">
          <div class="serif teal a" style="font-size:220px;font-weight:600;animation-delay:.05s">{k}</div>
          <div><h1 style="font-size:130px" {at(.15)}>{s}</h1><div class="eyebrow f" style="margin-top:18px;animation-delay:.4s">{AGENT_OF[k]}</div></div></div>
          <div class=rule style="margin-top:44px;animation-delay:.35s"></div>""", NUM, 1.02), NUM)

    # 7 · the build in one picture
    d = card_length(7, nr)
    nodes = [("Intent", "1 signature"), ("Design pack", "1 approval"), ("Pipeline proven against last month", "0 lines unexplained"), ("Live", "monthly at 06:00, by the 5th business day")]
    strip = "".join(f"""<div class="a" style="flex:1;animation-delay:{.3 + i * .45:.2f}s"><div style="display:flex;align-items:center;gap:14px">
        <div style="width:26px;height:26px;border-radius:50%;background:var(--ds-teal-bright);box-shadow:0 0 22px var(--ds-teal-bright)"></div>
        <div style="flex:1;height:3px;background:{'var(--ds-line,#2A3A50)' if i < 3 else 'transparent'}"></div></div>
        <div class=serif style="font-size:46px;font-weight:600;margin-top:24px;line-height:1.12;padding-right:30px">{t}</div>
        <div class="mono teal" style="font-size:28px;margin-top:16px">{s}</div></div>""" for i, (t, s) in enumerate(nodes))
    out["scene-7"] = (page(f"""<div class=eyebrow {at(.1, 'f')}>The build, in one picture</div><div class=row2 style="display:flex;margin-top:60px">{strip}</div>
      <div style="margin-top:80px;font-size:42px;font-weight:500" class=sub>{words('The proof stays attached to every number.', say(7, 'And the proof'))}</div>""", d), d)

    # 10 · trust
    d = card_length(10, nr)
    icons = ['<rect x="8" y="14" width="32" height="26" rx="5"/><path d="M15 14v-5a9 9 0 0 1 18 0v5"/>',
             '<circle cx="12" cy="12" r="5"/><circle cx="36" cy="36" r="5"/><path d="M16 16l16 16"/>',
             '<path d="M10 26l9 9 19-21"/>']
    lines = [("Client data stays inside the office's space.", say(10, "The office's data")), ("Every figure traces to a file and a person.", say(10, "Every figure")),
             ("Agents draft. People sign.", say(10, "Agents draft"))]
    rows = "".join(f"""<div class=a style="display:flex;align-items:center;gap:36px;margin-top:44px;animation-delay:{t:.2f}s">
        <svg width="72" height="72" viewBox="0 0 48 48" fill="none" stroke="var(--ds-teal-bright)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{ic}</svg>
        <div class=serif style="font-size:60px;font-weight:600">{t_}</div></div>""" for ic, (t_, t) in zip(icons, lines))
    out["scene-10"] = (page(f"""<div class=eyebrow {at(.1, 'f')}>Trust</div>{rows}""", d, 1.02), d)

    # 11 · close: the five steps collapse into the mark
    d = card_length(11, nr)
    row = "".join(f"""<div class="step" style="animation:up .5s {.1 + i * .12:.2f}s both,out .45s {1.5 + i * .06:.2f}s both;opacity:0">
        <div class=k>{i + 1}</div><div class=t>{s}</div></div>""" for i, s in enumerate(STEPS))
    out["scene-11"] = (page(f"""<div class=steps style="position:absolute;left:0;right:0;top:300px;margin:0">{row}</div>
      <div style="text-align:center;display:flex;flex-direction:column;align-items:center">
        <img class=mark src="{mark}" style="width:170px;height:170px;opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) 1.9s both">
        <h1 style="margin-top:36px" {at(say(11, 'Signal Harbor', .3))}>Signal Harbor</h1>
        <div class=sub style="margin-top:24px;font-size:56px;color:var(--ds-ink)">{words('Every figure, explained.', say(11, 'Every figure'))}</div></div>
      <div style="position:absolute;inset:-400px;background:var(--ds-ground);opacity:0;animation:fade .8s {d - .9:.2f}s both;z-index:5"></div>""", d, 1.02), d)

    for n in (2, 3, 11):              # the vertical cuts' cards, laid out for 1080x1920
        html, d = out[f"scene-{n}"]
        extra = ".steps{display:none!important}" if n == 11 else ""     # the close: the mark and the line only, in vertical
        out[f"scene-v-{n}"] = (html.replace("</style>", VCSS + extra + "</style>", 1), d)

    # lower thirds and the progress bar (transparent PNGs)
    for s in scenes():
        if s["lower"]:
            c, t = [x.strip() for x in s["lower"].split("·", 1)]
            out[f"lower-{s['n']}"] = (f"""<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{tokens()}
              *{{margin:0;box-sizing:border-box}}html,body{{width:1920px;height:1080px;background:transparent;font-family:'IBM Plex Sans'}}
              .lower{{position:absolute;left:70px;bottom:190px;display:flex;align-items:center;gap:22px;background:color-mix(in srgb,var(--ds-ground) 92%,transparent);
                border:2px solid color-mix(in srgb,var(--ds-teal-bright) 45%,transparent);border-left:10px solid var(--ds-teal-bright);border-radius:14px;
                padding:14px 32px 14px 20px;box-shadow:0 14px 44px #000a}}
              img{{width:44px;height:44px}}.c{{font-family:'IBM Plex Mono';font-size:22px;letter-spacing:.16em;text-transform:uppercase;color:var(--ds-teal-bright);font-weight:600}}
              .t{{font-size:34px;font-weight:600;color:var(--ds-ink);margin-top:2px}}</style>
              <div class=lower><img src='{mark}'><div><div class=c>{c}</div><div class=t>{t}</div></div></div>""", 0)
    for k in range(1, 6):
        segs = "".join(f"""<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;gap:5px">
            <div style="font-size:15px;font-weight:{600 if i + 1 == k else 500};letter-spacing:.04em;color:{'var(--ds-ink)' if i + 1 == k else 'var(--ds-ink-soft)' if i + 1 < k else 'var(--ds-ink-muted)'}">
              <span class=mono style="color:{'var(--ds-teal-bright)' if i + 1 <= k else 'var(--ds-ink-muted)'}">{i + 1}</span>&nbsp; {s}</div>
            <div style="height:{4 if i + 1 == k else 3}px;border-radius:2px;background:{'var(--ds-teal-bright)' if i + 1 == k else 'color-mix(in srgb,var(--ds-teal-bright) 45%,transparent)' if i + 1 < k else 'var(--ds-line,#2A3A50)'};
              {'box-shadow:0 0 12px var(--ds-teal-bright)' if i + 1 == k else ''}"></div></div>""" for i, s in enumerate(STEPS))
        out[f"bar-{k}"] = (f"""<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{tokens()}{CSS}
          html,body{{background:transparent}}</style><div style="position:absolute;left:0;top:0;width:1920px;height:43px;background:var(--ds-ground);
          display:flex;gap:14px;padding:0 38px 6px">{segs}</div>""", 0)
    return out


# ---- the server -----------------------------------------------------------------------------------------------------------------

def up() -> bool:
    try:
        return urllib.request.urlopen(BASE + "/", timeout=3).status == 200
    except OSError:
        return False


def stop_server() -> None:
    """Stop whatever listens on port 8697 (this film's own server), and nothing else."""
    ps = (f"Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(2)


def prep(*stages: str) -> str:
    out = ""
    for st in stages:
        out = subprocess.run([sys.executable, str(ROOT / "tools/video/vid6_prep.py"), st], check=True, cwd=ROOT, capture_output=True, text=True,
                             env={**os.environ, "SH_FILM_ENV": "vid7"}).stdout.split()[-1]
    return out


def fresh_server() -> str:
    """A fresh copy of the seeded company (a snapshot, made once from a fresh seed plus the prepared project), served from the
    current UI build on port 8697. Returns the prepared project's id."""
    stop_server()
    if not SNAP.exists():
        subprocess.run([sys.executable, str(ROOT / "tools/make_test_env.py"), "vid7", "--seed"], check=True, cwd=ROOT)
        new = prep("start")
        prep("report", "indexes", "livefx")
        (DATA / "new_project.txt").write_text(new, encoding="utf-8")
        shutil.copytree(DATA, SNAP)
    shutil.rmtree(DATA, ignore_errors=True)
    shutil.copytree(SNAP, DATA)
    shutil.copyfile(DATA / "new_project.txt", WORK / "new_project.txt")
    subprocess.Popen([sys.executable, str(Path(__file__).with_name("film7_serve.py"))], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        if up():
            return (DATA / "new_project.txt").read_text(encoding="utf-8").strip()
        time.sleep(1)
    raise SystemExit("the recording server did not start")


# ---- recording ------------------------------------------------------------------------------------------------------------------

class Shot(record.Scene):
    """A scene on this film's clock. at_text waits for the phrase; when an action runs late, the sentence is moved to it
    (cues: sentence -> the take's time at which that sentence should start)."""

    def __init__(self, n: int, page, rec, opener, nr: dict):
        super().__init__(n, page, rec, nr[str(n)]["seconds"], opener)
        self.nr, self.cues = nr, {}

    def at_text(self, phrase: str, early: float = 0.4) -> None:
        i, off, t = phrase_at(self.nr, self.n, phrase)
        left = LEAD + t - early - self.now()
        if left > 0:
            self.hold(left)
        start = self.now() + early - off - LEAD
        if start > self.nr[str(self.n)]["spans"][i][0] + 0.05 and str(i) not in self.cues:
            self.cues[str(i)] = round(start, 3)


def card_of(loc):
    return loc.locator("xpath=ancestor::div[contains(@class,'b9v-card')][1]")


def s4_ask(s: Shot, new: str) -> None:
    """North (Real use): Mei says what she needs; North writes the intent beside the chat; the sponsor's signature."""
    p = s.page
    s.hold(0.4)
    s.at_text("Mei just talks", 0.3)
    s.type(p.locator("textarea").first, "Monthly performance against the benchmark for the family council, by the 5th working day. "
                                        "Raj builds it by hand today.")
    s.click(p.get_by_role("button", name="Start", exact=True))
    s.ready(p.get_by_role("button", name="Not this").or_(p.get_by_role("button", name="Send")).first, 240)
    s.mark("chime")
    s.at_text("North writes it down", 0.4)
    reply = p.locator("div").filter(has_text=re.compile(r"^North\s")).last
    s.soft("ring reply", s.ring, reply, 2.2)
    s.at_text("the figures", 0.3)
    doc = p.get_by_text("Intent of work", exact=True).first.locator("xpath=../..")
    s.soft("ring doc", s.ring, doc, 3.0)
    s.soft("zoom doc", s.zoom, doc, 1.22, 3.2)
    s.at_text("where each number comes from", 0.6)
    acc = p.get_by_role("button", name="Accept", exact=True)
    if acc.count():
        s.click(acc.first)
        s.hold(0.6)
    s.soft("ring new", s.ring, p.get_by_text(re.compile("^New:")).first.locator("xpath=.."), 1.6)
    s.at_text("Daniel, the sponsor, signs", 0.8)
    s.switch("daniel.foo", f"/centre/build/p/{DEMO}/intent", "Intent of work")    # the signed intent of the live project
    q = s.page
    sig = q.get_by_text(re.compile("Daniel Foo signed")).first
    s.soft("scroll signed", s.scroll_to, sig, 260, 800)
    s.soft("ring signed", s.ring, sig.locator("xpath=.."), 2.6)
    s.at_text("never asked for again", 0.6)
    s.soft("zoom signed", s.zoom, sig.locator("xpath=.."), 1.3, 2.2)


def offstage(s: Shot, stage: str, tab: str | None = None, reload: bool = True) -> None:
    s.rec.pause()
    prep(stage)
    if reload:
        s.page.reload()
        if tab:
            s.page.get_by_role("button", name=tab).click()
    s.rec.resume()


def s5_design(s: Shot, new: str) -> None:
    """Span, the architect (Real use): what I already know, the few questions, the design pack, the head of data approves."""
    p = s.page
    s.hold(0.3)
    s.at_text("Span reads before it asks", 0.4)
    s.soft("ring architect", s.ring, p.get_by_text("I read the signed intent and the process map").locator("xpath=.."), 2.4)
    s.at_text("Everything from the intent", 0.4)
    known = p.get_by_text(re.compile("from the intent", re.I))
    s.soft("ring known 1", s.ring, known.first.locator("xpath=.."), 1.4)
    s.soft("zoom known", s.zoom, known.first.locator("xpath=../.."), 1.25, 1.6)
    s.at_text("It asks only what is missing", 0.4)
    s.click(p.get_by_role("button", name="The few questions"))
    s.soft("ring questions", s.ring, p.get_by_text("Span has a proposed answer for each question.").first, 1.8)
    s.at_text("with a proposed answer", 0.2)
    s.click(p.get_by_role("button", name=re.compile("Accept all")))
    s.ready(p.get_by_text("Everything is answered."), 60)
    s.at_text("The result is one design pack", 0.6)
    s.click(p.get_by_role("button", name="The design pack"))
    s.click(p.get_by_role("button", name="Draft the design pack"))
    s.ready(p.get_by_text("Gold tables").first, 180)
    s.mark("chime")
    offstage(s, "slip", "The design pack")
    s.at_text("tables, definitions", 0.3)
    s.soft("ring gold", s.ring, p.get_by_text("Gold tables").first.locator("xpath=.."), 1.6)
    s.soft("scroll def", s.scroll_to, p.get_by_text("Definitions").first, 120, 900)
    s.at_text("the benchmark to prove against", 0.4)
    s.soft("ring bench", s.ring, p.get_by_text("Benchmark check").first.locator("xpath=.."), 2.0)
    send = p.get_by_role("button", name=re.compile("Send to the head of data"))
    s.soft("scroll send", s.scroll_to, send, 380, 700)
    s.click(send)
    s.at_text("Anita, head of data", 0.6)
    s.switch("anita.rao", f"/centre/build/p/{new}/architecture", "What I already know")
    q = s.page
    q.get_by_role("button", name="The design pack").click()
    btn = q.get_by_role("button", name="Approve version 1")
    btn.wait_for(state="visible", timeout=30000)
    s.soft("scroll approve", s.scroll_to, btn, 380, 700)
    s.click(btn)
    s.mark("seal")
    s.ready(q.get_by_text("Approved by Anita Rao").first, 30)
    s.soft("ring approved", s.ring, q.get_by_text("Approved by Anita Rao").first, 2.0)
    offstage(s, "plan1", reload=False)


def s6_build(s: Shot, new: str) -> None:
    """Span, the builder (Testing): run on a copy, last month's report, two lines differ, back to the architect, version 2, every line ties, live."""
    p = s.page
    s.hold(0.3)
    s.soft("ring builder", s.ring, p.get_by_text("I took design pack version 1 as it was approved.").locator("xpath=.."), 2.0)
    s.at_text("runs everything on a copy", 0.4)
    run = p.get_by_role("heading", name="Run on a copy")
    s.soft("scroll run", s.scroll_to, run, 110, 900)
    s.soft("ring run", s.ring, card_of(run), 2.4)
    s.at_text("Nothing real is touched", 0.3)
    s.soft("zoom run", s.zoom, card_of(run), 1.2, 1.6)
    s.at_text("Then it asks", 0.4)
    ask = p.get_by_text("Do you have last month's report to check against?")
    s.soft("scroll ask", s.scroll_to, ask, 150, 800)
    s.soft("ring ask", s.ring, card_of(ask), 2.2)
    s.soft("zoom ask", s.zoom, card_of(ask), 1.3, 1.6)
    s.at_text("say?", 0.0)
    s.soft("point upload", s.point, p.get_by_text("Upload last month's report").first)
    s.mark("tick")
    p.locator("input[type=file]").set_input_files(str(DATA.parent / "September report as issued.csv"))
    s.ready(p.get_by_text("Unexplained", exact=True).first, 90)
    s.at_text("Two lines do not match", 0.5)
    bad = p.get_by_text("Unexplained", exact=True)
    s.soft("scroll bad", s.scroll_to, bad.first.locator("xpath=ancestor::table[1]"), 160, 900)
    s.soft("zoom table", s.zoom, bad.first.locator("xpath=ancestor::table[1]"), 1.3, 3.4)
    s.soft("ring bad 1", s.ring, bad.first.locator("xpath=ancestor::tr[1]"), 1.5)
    s.hold(1.4)
    s.soft("ring bad 2", s.ring, bad.last.locator("xpath=ancestor::tr[1]"), 1.5)
    s.at_text("hands them back", 0.4)
    back = p.get_by_role("button", name="Send back to the architect")
    s.soft("scroll back", s.scroll_to, back, 380, 700)
    s.soft("zoom back", s.zoom, back, 1.35, 1.8)
    s.click(back)
    s.ready(p.get_by_text("With the architect.").first, 30)
    s.soft("ring with", s.ring, p.get_by_text("With the architect.").first.locator("xpath=.."), 1.4)
    s.at_text("Version two of the pack", 0.3)
    offstage(s, "v2")
    s.ready(p.get_by_text("Variance cleared").first, 120)
    s.soft("ring v2", s.ring, p.get_by_text("Pack version 2").first, 1.8)
    s.at_text("Every line ties", 0.6)
    clear = p.get_by_text("Variance cleared").first
    s.soft("scroll clear", s.scroll_to, clear, 200, 800)
    fig = p.get_by_text("4.17%").first
    s.soft("zoom clear", s.zoom, fig.locator("xpath=ancestor::table[1]") if p.get_by_text("4.17%").count() else card_of(clear), 1.3, 4.0)
    s.soft("ring figure", s.ring, fig.locator("xpath=ancestor::tr[1]"), 2.4)
    s.at_text("Only then does Leo go live", 0.3)
    go = p.get_by_role("button", name="Go live", exact=True)
    s.soft("scroll live", s.scroll_to, go, 380, 700)
    s.soft("zoom go", s.zoom, go, 1.3, 1.6)
    s.click(go)
    s.mark("seal")
    s.ready(p.get_by_text("Lumen proposes a starter dashboard").first, 60)
    sched = p.get_by_text(re.compile("06:00")).first
    s.soft("scroll sched", s.scroll_to, sched, 300, 700)
    s.soft("ring sched", s.ring, sched.locator("xpath=.."), 2.4)


def s8_read(s: Shot, new: str) -> None:
    """Lumen (Testing): the starter dashboard, accepted and approved; Consume Today; Consume Markets with its source tags."""
    p = s.page
    s.hold(0.3)
    s.at_text("Lumen has a dashboard ready", 0.6)
    s.click(p.get_by_role("link", name="Lumen proposes a starter dashboard").first)
    s.ready(p.get_by_text("Lumen's starter dashboard").first, 120)
    s.click(p.get_by_role("button", name="Open", exact=True).or_(p.get_by_role("link", name="Open", exact=True)).first)
    s.ready(p.get_by_role("button", name="Accept as it is"), 240)
    s.mark("chime")
    s.soft("scroll starter", s.scroll_to, p.get_by_role("heading", name="Lumen's starter dashboard").last, 200, 900)
    s.soft("ring starter", s.ring, p.get_by_label("Lumen's starter dashboard"), 2.4)
    s.soft("zoom starter", s.zoom, p.get_by_label("Lumen's starter dashboard"), 1.15, 2.2)
    s.at_text("built from what Mei asked for", 0.2)
    s.click(p.get_by_role("button", name="Accept as it is"))
    s.ready(p.get_by_text("You accepted the starter."), 30)
    send = p.get_by_role("button", name="Send for approval")
    s.soft("scroll send", s.scroll_to, send, 200, 600)
    s.click(send)
    s.ready(p.get_by_text("waiting for the head of data").first, 30)
    s.switch("daniel.foo", s.page.url.replace(BASE, ""), "Waiting for your approval")
    q = s.page
    btn = q.get_by_role("button", name="Approve", exact=True)
    s.soft("scroll approve", s.scroll_to, btn, 380, 600)
    s.click(btn)
    s.mark("seal")
    s.ready(q.get_by_text("Approved by").first, 30)
    s.soft("ring approved", s.ring, q.get_by_text("Approved by").first, 1.4)
    s.at_text("Each morning the council reads one note", 0.8)
    s.switch("daniel.foo", "/centre/consume", "What moved")
    q = s.page
    head = q.locator("h1").first
    s.soft("ring note", s.ring, head, 2.2)
    s.soft("zoom note", s.zoom, head, 1.3, 1.8)
    keys = q.locator("section[aria-label='Key figures']")
    s.hold(1.4)
    s.soft("ring keys", s.ring, keys, 1.8)
    moved = q.locator("section[aria-label='What moved']")
    s.soft("scroll moved", s.scroll_to, moved, 90, 900)
    s.soft("ring moved", s.ring, moved, 1.6)
    s.at_text("And market signals", 0.6)
    s.click(q.locator("nav[aria-label='Consume tabs']").get_by_role("link", name="Markets", exact=True))
    s.ready(q.get_by_role("heading", name="The market", exact=True).first, 60)
    s.rec.pause()                                  # the tab keeps Today's scroll: back to the top, off camera
    q.evaluate("window.scrollTo(0, 0)")
    q.locator("h1").first.evaluate("e => e.scrollIntoView({block: 'start'})")
    q.wait_for_timeout(500)
    s.rec.resume()
    mk = q.locator("section[aria-label='The market']")
    s.soft("scroll market", s.scroll_to, mk, 90, 700)
    s.soft("ring market", s.ring, mk, 1.8)
    s.at_text("how the indexes moved", 0.3)
    live = mk.locator("tr").filter(has_text="LIVE API").first
    s.soft("zoom live", s.zoom, live, 1.35, 2.2)
    s.soft("ring live", s.ring, live, 2.2)
    s.at_text("how each portfolio", 0.4)
    pf = q.locator("section[aria-label='Our portfolios against their benchmarks']")
    s.soft("scroll pf", s.scroll_to, pf, 90, 900)
    s.soft("ring liquid", s.ring, pf.locator("tr").filter(has_text="Office blend").first, 1.8)
    s.at_text("and fund did against them", 0.3)
    w = q.locator("section[aria-label='To watch']")
    s.soft("scroll watch", s.scroll_to, w, 90, 900)
    s.soft("ring watch", s.ring, w, 2.4)


def s9_act(s: Shot, new: str) -> None:
    """Tally (Testing): the one-page Action screen; a follow-up drafted; the 12,400 cash break closed as timing; Done today grows."""
    p = s.page
    s.hold(0.4)
    greet = p.get_by_text(re.compile(r"^Good morning, Mei\.")).first
    s.soft("ring greet", s.ring, greet, 2.4)
    s.soft("zoom greet", s.zoom, greet, 1.3, 2.2)
    s.at_text("Tally puts everything", 0.4)
    chips = p.locator("a.ds-chip").first.locator("xpath=..")
    s.soft("ring chips", s.ring, chips, 1.6)
    for name, cue in (("Reconciliations to clear", "breaks to clear"), ("Figures to confirm", "figures to confirm"),
                      ("Statements to chase", "statements to chase"), ("Waiting for my approval", "approvals waiting")):
        s.at_text(cue, 0.2)
        s.soft(f"ring {name}", s.ring, p.locator("a.ds-chip").filter(has_text=name).first, 0.9)
    s.at_text("Each line says what happened", 0.5)
    late = p.get_by_text(re.compile("63 BUSINESS DAYS LATE", re.I)).first
    s.soft("scroll late", s.scroll_to, late, 160, 900)
    row = late.locator("xpath=ancestor::*[.//button[contains(.,'Draft a follow-up')]][1]")
    s.soft("ring late", s.ring, row, 1.6)
    s.click(p.get_by_role("button", name="Draft a follow-up").first)
    s.hold(1.0)
    s.soft("ring draft", s.ring, row, 1.4)
    s.at_text("A twelve thousand", 0.9)
    cash = p.get_by_text(re.compile("^Entity B cash, administrator")).first
    crow = cash.locator("xpath=ancestor::*[.//button[contains(.,'Close as timing')]][1]")
    s.soft("scroll cash", s.scroll_to, cash, 220, 800)
    s.soft("ring cash", s.ring, crow, 1.6)
    s.at_text("explained as a wire in transit", 0.4)
    why = crow.get_by_text(re.compile("timing difference")).first
    s.soft("zoom why", s.zoom, why, 1.3, 2.4)
    s.soft("ring why", s.ring, why, 2.4)
    btn = crow.get_by_role("button", name="Close as timing")
    s.soft("point close", s.point, btn)
    s.at_text("Closed.", 0.3)
    s.click(btn.first)
    s.mark("seal")
    s.hold(1.0)
    done = p.locator("summary").filter(has_text="Done today").first
    s.soft("scroll done", s.scroll_to, done, 300, 900)
    s.click(done)
    s.hold(0.4)
    s.soft("ring done", s.ring, done.locator("xpath=.."), 2.6)
    s.hold(1.4)


# scene: (who, start page, the text that shows it has loaded, what to do)
def plan(new: str) -> dict:
    b = f"/centre/build/p/{new}"
    return {4: ("mei.chen", "/centre/build/new", "What do you need?", s4_ask),
            5: ("leo.park", f"{b}/architecture", "What I already know", s5_design),
            6: ("leo.park", f"{b}/pipelines", "Run on a copy", s6_build),
            8: ("leo.park", f"{b}/pipelines", "Lumen proposes a starter dashboard", s8_read),
            9: ("mei.chen", "/centre/action", "Good morning, Mei", s9_act)}


DEMO = ""      # the seeded live project (its intent is signed by the sponsor)


def film(only: list[int], rehearse: bool, via: list[int] | None = None) -> dict:
    """via: scenes played (Testing, nothing kept) only to bring the data to the state the filmed scenes start from."""
    via = via or []
    global DEMO
    from playwright.sync_api import sync_playwright
    nr = narr()
    new = fresh_server()
    DEMO = next(p.name for p in (DATA / "evergreen" / "consume").glob("prj-*") if p.name != new)
    recf = WORK / "recordings.json"
    out = json.loads(recf.read_text(encoding="utf-8")) if recf.exists() else {}
    todo = {n: v for n, v in plan(new).items() if not only or n in only or n in via}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--hide-scrollbars"])
            states: dict[str, dict] = {}

            # the browser's clock reads about 9 in the morning (Action greets "Good morning"; the film is a Monday morning)
            off = (9 - time.gmtime().tm_hour + 12) % 24 - 12
            tz = "Etc/GMT" + (f"-{off}" if off > 0 else f"+{-off}" if off < 0 else "")

            def opener(who: str, path: str):
                states.setdefault(who, sign_in_state(pw, who))
                ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, storage_state=states[who],
                                          color_scheme="dark", reduced_motion="no-preference", timezone_id=tz)
                ctx.add_init_script(record.INIT)
                pg = ctx.new_page()
                pg.goto(BASE + path)
                return pg

            mode = None
            try:
                for n, (who, start, ready, fn) in todo.items():
                    real = n in REAL and not rehearse and n not in via
                    if real and out.get(str(n), {}).get("mode") == "real" and (WORK / out[str(n)]["clip"]).exists():
                        raise SystemExit(f"scene {n} already has its Real-use take; it is never filmed twice in Real use")
                    want = "real" if real else "testing"
                    if want != mode:
                        record.set_mode(pw, want, states)
                        mode = want
                    usage0 = record.openrouter_usage() if real else 0.0
                    page = opener(who, start)
                    for tries in range(3):
                        try:
                            page.get_by_text(ready).first.wait_for(state="visible", timeout=60000)
                            break
                        except Exception:  # noqa: BLE001
                            if tries == 2:
                                raise
                            page.reload()
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:  # noqa: BLE001 - a page that polls never goes idle
                        pass
                    page.evaluate("window.__sh.move(1100, 600, 10)")
                    page.wait_for_timeout(700)
                    rec = record.Recorder(WORK / f"frames{n}")
                    rec.attach(page)
                    rec.start()
                    s = Shot(n, page, rec, opener, nr)
                    ok = True
                    try:
                        fn(s, new)
                    except Exception as e:  # noqa: BLE001 - a failed scene is reported; what was filmed is kept
                        ok = False
                        rec.resume()
                        print(f"scene {n}: FAILED ({type(e).__name__}: {str(e)[:500]})", flush=True)
                        s.page.screenshot(path=str(WORK / f"scene{n}-failed.png"))
                    s.hold(1.0)
                    secs = s.now() + 0.2
                    rec.pause()
                    clip = WORK / (f"via{n}.mp4" if n in via else f"rehearse{n}.mp4" if rehearse else f"rec{n}.mp4")
                    rec.write(secs, clip)
                    for c in {s.page.context, page.context}:
                        c.close()
                    if n in via:
                        print(f"scene {n}: played to reach the next scene's state ({'ok' if ok else 'FAILED'})", flush=True)
                        continue
                    out[str(n)] = {"clip": clip.name, "seconds": round(secs, 2), "zooms": s.zooms, "marks": s.marks, "cues": s.cues, "ok": ok,
                                   "missed": s.missed, "mode": want}
                    recf.write_text(json.dumps(out, indent=1), encoding="utf-8")
                    if real:
                        time.sleep(10)
                        cost = record.openrouter_usage() - usage0
                        narrate.log_cost(f"film v4 agent take, scene {n} ({fn.__doc__.split(':')[0].strip()}), Real use",
                                         "OpenRouter, the product's Real-use agent models", round(cost, 4))
                    print(f"scene {n}: {'ok' if ok else 'FAILED'}, {secs:.1f} s (voice {nr[str(n)]['seconds']:.1f}), missed {s.missed}, cues {s.cues}", flush=True)
            finally:
                if mode == "real":
                    record.set_mode(pw, "testing", states)
                browser.close()
    finally:
        stop_server()
    return out


# ---- the cut --------------------------------------------------------------------------------------------------------------------

def timeline(nr: dict, recs: dict) -> list[dict]:
    items, t = [], 0.0
    for s in scenes():
        n = s["n"]
        step = STEP_OF.get(n)
        if s["chapter"]:
            items.append({"kind": "num", "n": n, "d": NUM, "start": t, "step": step})
            t += NUM
        v = nr[str(n)]
        spans = [list(x) for x in v["spans"]]
        d = card_length(n, nr)
        rec, speed = None, 1.0
        if s["kind"] in ("screen", "agent"):
            rec = recs.get(str(n))
            if rec:
                cue_at = []
                for i, sp in enumerate(spans):        # a sentence starts on its moment in the take, never on top of the one before
                    c = float((rec.get("cues") or {}).get(str(i), sp[0]))
                    want = max(sp[0], c)
                    if i:
                        want = max(want, spans[i - 1][1] + narrate.GAP)
                    cue_at.append(c)
                    spans[i] = [round(want, 3), round(want + sp[1] - sp[0], 3)]
                # where the voice had to wait for the sentence before, the picture holds for the same time just before that moment
                steps, held = [], 0.0
                for c, sp in zip(cue_at, spans):
                    if sp[0] - c > held + 0.05:
                        held = sp[0] - c
                        steps.append((round(LEAD + c - 0.15, 3), round(held, 3)))
                rec = retime(n, rec, steps)
                d = max(LEAD + spans[-1][1] + TAIL, float(rec["seconds"]))
            else:
                d = max(d, 8.0)
        items.append({"kind": s["kind"] if rec or s["kind"] == "card" else "missing", "n": n, "d": round(d, 3), "start": t, "step": step,
                      "spans": spans, "wavs": v["wavs"], "cap": v["cap"], "rec": rec, "speed": speed, "lower": s["lower"]})
        t += round(d, 3)
    return items


def retime(n: int, rec: dict, steps: list[tuple[float, float]]) -> dict:
    """The take with holds: from each step's second on, the picture runs `held` seconds later (the frame before is held).
    Zooms and sound marks move with it."""
    if not steps:
        return rec

    def shift(x: float) -> float:
        return x + max([h for at_, h in steps if x >= at_] or [0.0])
    expr = "0"
    for at_, h in steps:
        expr = f"if(gte(T,{at_}),{h},{expr})"
    dest = WORK / f"retimed{n}.mp4"
    build.ff("-i", str(WORK / rec["clip"]), "-vf", f"setpts='PTS+({expr})/TB',fps={FPS}", *build.V, "-an", str(dest))
    return {**rec, "clip": dest.name, "seconds": round(float(rec["seconds"]) + steps[-1][1], 3),
            "zooms": [{**z, "t": round(shift(z["t"]), 3)} for z in rec.get("zooms", [])],
            "marks": [[k, round(shift(a), 3)] for k, a in rec.get("marks", [])], "holds": steps}


def placeholder(n: int, d: float) -> Path:
    """A clearly marked card for a scene not filmed yet."""
    name = f"missing-{n}"
    html = page(f"""<div class=eyebrow>Scene {n} · to be filmed</div><h2 style="margin-top:20px">Placeholder</h2>
      <div class=sub style="margin-top:20px">This scene is recorded when its screen lands.</div>""", d)
    return cards.render(None, {name: (html, d)}, CARDS)[name]


def segment(it: dict, i: int, clean: bool = False) -> Path:
    dest = WORK / f"seg-{i:02d}{'-clean' if clean else ''}.mp4"
    lower = CARDS / f"lower-{it['n']}.png"
    lower = lower if lower.exists() and it["kind"] in ("screen", "agent") and not clean else None
    raw = WORK / f"seg-{i:02d}-raw.mp4"
    if it["kind"] == "num":
        build.card_segment(CARDS / f"num-{it['step']}.mp4", it["d"], None, True, True, raw)
    elif it["kind"] in ("screen", "agent"):
        clip = WORK / it["rec"]["clip"]
        short = it["d"] + 0.5 - build.length(clip)
        if short > 1.5:            # the take ends before its words do: its last frame is held (screen_segment holds only 2 s)
            padded = WORK / f"padded{it['n']}.mp4"
            build.ff("-i", str(clip), "-vf", f"tpad=stop_mode=clone:stop_duration={short:.3f}", *build.V, "-an", str(padded))
            clip = padded
        rec = {**it["rec"], "clip": str(clip)}
        build.screen_segment(rec, it["d"], lower, True, True, raw, it["speed"])
    elif it["kind"] == "missing":
        build.card_segment(placeholder(it["n"], it["d"]), it["d"], None, True, True, raw)
    else:
        build.card_segment(CARDS / f"scene-{it['n']}.mp4", it["d"], None, True, True, raw)
    if not it["step"]:
        raw.replace(dest)
        return dest
    w, h, x, y = FRAME
    bar = CARDS / f"bar-{it['step']}.png"
    pre = f"[0:v]scale={w}:{h}:flags=lanczos,pad=1920:1080:{x}:{y}:color={NAVY}[f];[f]" if it["kind"] in ("screen", "agent") else "[0:v]"
    build.ff("-i", str(raw), "-loop", "1", "-i", str(bar), "-filter_complex", f"{pre}[1:v]overlay=0:0:shortest=1,setsar=1[v]", "-map", "[v]",
             *build.V, "-t", f"{it['d']:.3f}", "-an", str(dest))
    raw.unlink()
    return dest


def concat(segs: list[Path], dest: Path) -> Path:
    lst = dest.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    build.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dest))
    return dest


HIDE = {10, 11}       # cards that already show their words: the burned caption is left out (the .srt keeps it)
HIDE_LINES = {(2, 2), (2, 3), (3, 1), (3, 2), (7, 1)}     # single lines a card already shows


def mix(items: list[dict], total: float, dest: Path) -> Path:
    n = int(total * sound.SR) + sound.SR
    vox, fx = np.zeros(n), np.zeros(n)
    for it in items:
        if it["kind"] == "num":
            continue
        for wav, (a, _) in zip(it["wavs"], it["spans"]):
            sound.place(vox, sound.read_wav(Path(wav)), it["start"] + LEAD + a)
        for kind, at_ in (it["rec"] or {}).get("marks", []):
            sound.place(fx, sound.cue(kind) * 0.8, it["start"] + at_ / it["speed"])
    st = {it["n"]: it["start"] for it in items if it["kind"] != "num"}
    nr = narr()
    sound.place(fx, sound.cue("strike"), st[2] + LEAD + phrase_at(nr, 2, "the total moves")[2] + 0.3)
    sound.place(fx, sound.cue("swell"), st[3] - 1.6)
    sound.place(fx, sound.cue("swell") * 0.6, st[11] - 1.4)
    end9 = next(i["start"] + i["d"] for i in items if i["n"] == 9 and i["kind"] != "num")
    sec = {"cold": st[2], "reveal": st[3], "pulse": (st[4] - 1.4, end9), "padonly": (st[10] - 1.0, st[11]), "close": st[11]}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), vox)
    raw = dest.with_name(dest.stem + "-raw.wav")
    sound.write_wav(raw, vox + music * 0.9 + fx)
    build.loudnorm(raw, dest)
    return dest


def make_hero(nr: dict, recs: dict) -> tuple[list[dict], float]:
    cards.render(None, card_items(nr), CARDS)
    items = timeline(nr, recs)
    segs = []
    for i, it in enumerate(items):
        segs.append(segment(it, i))
        print(f"  {it['kind']:7} {it['n']:>2}: {it['d']:.2f} s at {it['start']:.2f}", flush=True)
    picture = concat(segs, WORK / "hero-picture.mp4")
    total = build.length(picture)
    caps = []
    for it in items:
        if it["kind"] == "num":
            continue
        for k, (cap, (a, b)) in enumerate(zip(it["cap"], it["spans"])):
            hide = it["n"] in HIDE or (it["n"], k) in HIDE_LINES
            caps += [(*c, "hide" if hide else "") for c in build.sentence_cues(cap, it["start"] + LEAD + a, it["start"] + LEAD + b)]
    build.write_captions(caps, OUT / f"{NAME}.srt", WORK / "hero.ass")
    audio = mix(items, total, WORK / "hero-audio.wav")
    build.finish(picture, audio, WORK / "hero.ass", HERO)
    (WORK / "timeline.json").write_text(json.dumps([{k: v for k, v in it.items() if k not in ("rec", "wavs")} for it in items], indent=1), encoding="utf-8")
    return items, build.length(HERO)


# Cuts: (scene, first sentence, last sentence) taken from the hero, picture and voice together.
# The 60 s cut: scenes 2, 3, 6, 9 and 11 (script). To fit 60 s it keeps whole sentences only: scene 3's first, scene 6 from
# "Two lines do not match" to the end, scene 9's break and "Closed." The teaser: scene 2's first two sentences, then the close.
CUTS = {"60s": [(2, 0, 3), (3, 0, 0), (6, 3, 9), (9, 4, 5), (11, 0, 1)],
        "15s": [(2, 0, 1), (11, 0, 1)]}
# vertical crops of product shots: (crop width, centre x, centre y) in the hero frame
VCROP = {6: (857, 760, 560), 9: (857, 700, 520)}
VCARD = {2, 3, 11}


def make_cut(label: str, items: list[dict]) -> Path:
    by = {it["n"]: it for it in items if it["kind"] != "num"}
    hero = WORK / "hero-picture.mp4"
    segs, vsegs, caps, capsv, place = [], [], [], [], []
    t = 0.0
    for k, (n, a, b) in enumerate(CUTS[label]):
        it = by[n]
        whole = it["kind"] == "card"
        s0 = 0.0 if whole and a == 0 else LEAD + it["spans"][a][0] - 0.35
        s1 = it["d"] if whole and b == len(it["spans"]) - 1 else LEAD + it["spans"][b][1] + (0.9 if k == len(CUTS[label]) - 1 else 0.45)
        s1 = min(s1, it["d"])
        d = round(s1 - s0, 3)
        vf = f"fade=t=in:st=0:d=0.2:color={NAVY},fade=t=out:st={d - 0.2:.3f}:d=0.2:color={NAVY}"
        dest = WORK / f"cut{label}-{k}.mp4"
        build.ff("-ss", f"{it['start'] + s0:.3f}", "-i", str(hero), "-t", f"{d:.3f}", "-vf", vf, *build.V, "-an", str(dest))
        segs.append(dest)
        vdest = WORK / f"cut{label}-v{k}.mp4"
        if n in VCARD:
            build.ff("-ss", f"{s0:.3f}", "-i", str(CARDS / f"scene-v-{n}.mp4"), "-t", f"{d:.3f}",
                     "-vf", f"tpad=stop_mode=clone:stop_duration=3,{vf}", *build.V, "-an", str(vdest))
        else:
            cw, cx, cy = VCROP[n]
            ch = round(cw * build.VFG_H / 1080)
            crop = (f"crop={cw}:{ch}:{max(0, min(1920 - cw, cx - cw // 2))}:{max(0, min(1080 - ch, cy - ch // 2))},scale=1080:{build.VFG_H}:flags=lanczos,"
                    f"pad=1080:1920:0:{build.VBAND}:color={NAVY}")
            build.ff("-ss", f"{it['start'] + s0:.3f}", "-i", str(hero), "-t", f"{d:.3f}", "-vf", f"{crop},{vf}", *build.V, "-an", str(vdest))
        vsegs.append(vdest)
        for i in range(a, b + 1):
            st = t + LEAD + it["spans"][i][0] - s0
            en = t + LEAD + it["spans"][i][1] - s0
            place.append((Path(it["wavs"][i]), st))
            hide = "hide" if n in HIDE or (n, i) in HIDE_LINES else ""
            caps += [(*c, hide) for c in build.sentence_cues(it["cap"][i], st, en)]
            capsv += [(*c, hide) for c in build.sentence_cues(it["cap"][i], st, en, 52)]
        t += d
    pic, vpic = concat(segs, WORK / f"cut{label}-picture.mp4"), concat(vsegs, WORK / f"cut{label}-vpicture.mp4")
    total = build.length(pic)
    n = int(total * sound.SR) + sound.SR
    vox = np.zeros(n)
    for wav, at_ in place:
        sound.place(vox, sound.read_wav(wav), at_)
    sec = {"cold": 0.3, "reveal": 0.6, "pulse": (3.0, total - 6), "padonly": (total - 6, total - 4), "close": total - 4}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), vox)
    raw = WORK / f"cut{label}-raw.wav"
    sound.write_wav(raw, vox + music * 0.9)
    audio = build.loudnorm(raw, WORK / f"cut{label}-audio.wav") or WORK / f"cut{label}-audio.wav"
    dest = OUT / f"{NAME}-{label}.mp4"
    build.write_captions(caps, OUT / f"{NAME}-{label}.srt", WORK / f"cut{label}.ass")
    build.finish(pic, audio, WORK / f"cut{label}.ass", dest)
    build.write_captions(capsv, WORK / f"cut{label}-v.srt", WORK / f"cut{label}-v.ass", vertical=True, top=["SIGNAL HARBOR", "Every figure, explained."])
    build.finish(vpic, audio, WORK / f"cut{label}-v.ass", OUT / f"{NAME}-{label}-vertical.mp4")
    return dest


def share_copy(total: float) -> Path:
    dest = OUT / f"{NAME}-share.mp4"
    kbps = int(27.5 * 8 * 1024 / total) - 96
    log = WORK / "share2pass"
    c = ["-i", str(HERO), "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", str(log)]
    build.ff(*c, "-pass", "1", "-an", "-f", "mp4", "NUL")
    build.ff(*c, "-pass", "2", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dest))
    return dest


def finish_outputs(items: list[dict], total: float) -> None:
    close = next(i for i in items if i["n"] == 11 and i["kind"] != "num")
    build.ff("-ss", f"{close['start'] + close['d'] - 1.3:.2f}", "-i", str(WORK / "hero-picture.mp4"), "-frames:v", "1", str(OUT / f"{NAME}-poster.png"))
    for label in CUTS:
        print(f"{label}: {build.length(make_cut(label, items)):.1f} s", flush=True)
    print(f"share copy: {share_copy(total).stat().st_size / 1e6:.1f} MB", flush=True)
    st = WORK / "stills"
    shutil.rmtree(st, ignore_errors=True)
    st.mkdir(parents=True)
    build.ff("-i", str(HERO), "-vf", "fps=1/3,scale=1280:-2", str(st / "hero-%03d.png"))
    for label in CUTS:
        build.ff("-i", str(OUT / f"{NAME}-{label}-vertical.mp4"), "-vf", "fps=1/2,scale=540:-2", str(st / f"v{label}-%03d.png"))


def backup() -> None:
    """Anything this film overwrites in out/ is copied to out/backup/vid7/ first."""
    dest = OUT / "backup" / "vid7"
    for p in OUT.glob(f"{NAME}*"):
        dest.mkdir(parents=True, exist_ok=True)
        if not (dest / p.name).exists():
            shutil.copy2(p, dest / p.name)


def main() -> None:
    args = sys.argv[1:]
    only = [int(a) for a in args if a.isdigit()]
    nr = voice()
    if "--rehearse" in args or "--record" in args:
        via = [int(a) for a in args[args.index("--via") + 1:] if a.isdigit()] if "--via" in args else []
        film([n for n in only if n not in via], "--rehearse" in args, via)
        if "--rehearse" in args:
            return
    recs = json.loads((WORK / "recordings.json").read_text(encoding="utf-8"))
    recs = {k: v for k, v in recs.items() if v["clip"].startswith("rec")}
    backup()
    items, total = make_hero(nr, recs)
    print(f"hero: {total:.1f} s", flush=True)
    if "--hero-only" in args:          # the hero, its poster and the share copy; the cuts are left as they are
        close = next(i for i in items if i["n"] == 11 and i["kind"] != "num")
        build.ff("-ss", f"{close['start'] + close['d'] - 1.3:.2f}", "-i", str(WORK / "hero-picture.mp4"), "-frames:v", "1", str(OUT / f"{NAME}-poster.png"))
        print(f"share copy: {share_copy(total).stat().st_size / 1e6:.1f} MB", flush=True)
        return
    finish_outputs(items, total)


if __name__ == "__main__":
    main()
