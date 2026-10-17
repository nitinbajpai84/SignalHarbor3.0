"""UC01 film, "A fund asks for money": one capital call at Evergreen Office, notice to paid (docs/video/UC01-SCRIPT.md).

    python tools/video/uc01.py          # voice (cached, cost in docs/video/COST.md), cards, cut, sound, subtitles, poster

Cards only, no app recording: the film9 approach (narrate.say for the voice, cards.render for the animated cards,
sound.bed and sound.duck for the music, build.write_captions for the subtitles) in the 3.0 palette of docs/v3/COLOURS.md.
The recurring visual is the signal table: what arrives, the signal Harbor catches, who acts and how little.
Outputs in docs/video/out/: uc01-capital-call.mp4, uc01-capital-call.srt, uc01-capital-call-poster.png.
This film may add at most COST_CAP USD to docs/video/COST.md.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import cards  # noqa: E402
import common  # noqa: E402
import narrate  # noqa: E402
import sound  # noqa: E402
from common import LEAD, OUT, ROOT  # noqa: E402

SCRIPT = ROOT / "docs/video/UC01-SCRIPT.md"
WORK = OUT / "uc01"
CARDS = WORK / "cards"
NAME = "uc01-capital-call"
HERO = OUT / f"{NAME}.mp4"
POSTER = OUT / f"{NAME}-poster.png"
SRT = OUT / f"{NAME}.srt"
TAIL = 0.7
COST_CAP = 0.20          # USD this film may add to COST.md
RED = "#B23B32"
NR: dict = {}            # narration per scene: wavs, spans (seconds from the scene's voice start), cap, seconds
BASE_SPEND = 0.0         # what COST.md already held before this film

FONTS = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&"
         "family=Instrument+Sans:wght@400;500;600;700&display=swap")
ROWS = [
    dict(arr="Capital call notice No. 7 from Cedarpoint Ventures III", sig="USD 1,250,000 due 23 Oct",
         who="Sam Lee", wait="Log it?", done="Logged"),
    dict(arr="Commitment of 10,000,000 in Cedarpoint Ventures III", sig="Unfunded after this call: 2,750,000",
         who="Helen Foo", wait="Record it?", done="Recorded"),
    dict(arr="Cash by entity, verified, less the 250,000 buffer", sig="Short USD 270,000 in Holdings",
         who="Daniel Foo", wait="Decide", done="Decided"),
    dict(arr="Plan: convert SGD 361,800 to USD on Thursday", sig="Convert SGD 361,800, pay on 23 Oct",
         who="Daniel Foo", wait="Approve?", done="Approved"),
    dict(arr="Wire details: account ending 4471, on file 2209", sig="Bank account changed",
         who="Grace Ong", wait="Call back first", done="Confirmed", red=True),
]
CSS = """:root{--navy:#1B3A5C;--amber:#B7791F;--green:#1E7B4F;--red:#B23B32;--brass:#B08D57;--slate:#5A6878;
--ground:#F4F6F9;--card:#FFFFFF;--line:#D3DAE3}
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:var(--ground);color:var(--navy);font-family:'Instrument Sans',sans-serif}
.stage{width:1920px;height:1080px;padding:0 150px;display:flex;flex-direction:column;justify-content:center}
.eyebrow{font-size:28px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--slate);margin-bottom:34px}
h1{font-family:Fraunces,serif;font-weight:600;font-size:150px;line-height:1.04;letter-spacing:-.01em}
.sub{font-size:44px;color:var(--slate);margin-top:36px;line-height:1.35}
.a{opacity:0;animation:up .6s cubic-bezier(.2,.7,.2,1) both}
.f{opacity:0;animation:fade .6s ease-out both}
@keyframes up{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes show{from{opacity:0}to{opacity:1}}
@keyframes hide{to{opacity:0}}
@keyframes lit{from{opacity:.36;border-left-color:var(--line)}to{opacity:1;border-left-color:var(--lc)}}
@keyframes okb{to{border-left-color:var(--green)}}
@keyframes wipe{to{transform:scaleX(1)}}
.hd,.row{display:grid;grid-template-columns:560px 560px 1fr;gap:28px;align-items:center}
.hd{font-size:22px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--slate);padding:0 34px 6px}
.row{background:var(--card);border-radius:14px;border-left:10px solid var(--line);padding:20px 34px;margin-top:14px;
  box-shadow:0 2px 0 rgba(27,58,92,.06);opacity:.36}
.arr{font-size:32px;line-height:1.25;color:var(--slate)}
.sig{font-family:Fraunces,serif;font-weight:600;font-size:38px;line-height:1.15}
.who{display:flex;align-items:center;gap:22px;font-size:30px;font-weight:600}
.pb{display:grid}
.pill{grid-area:1/1;justify-self:start;border:2px solid;border-radius:999px;padding:8px 20px;font-size:26px;font-weight:700;white-space:nowrap;opacity:0}
.pw{color:var(--pc);border-color:var(--pc)}
.pd{color:#fff;background:var(--green);border-color:var(--green)}
.steps{display:flex;gap:40px;margin-top:50px}
.step{flex:1;border-top:5px solid var(--green);padding-top:18px;font-size:30px;line-height:1.3;opacity:0}
.step b{display:block;font-family:Fraunces,serif;font-size:42px;font-weight:600;margin-bottom:6px}
.pair{display:flex;gap:60px;margin-top:10px}
.panel{flex:1;background:var(--card);border-radius:18px;padding:52px 60px;border-top:6px solid var(--navy);opacity:0}
.who2{font-size:28px;font-weight:600;color:var(--slate);letter-spacing:.02em}
.q{font-family:Fraunces,serif;font-size:52px;font-weight:600;line-height:1.2;margin-top:30px}
.ans{margin-top:44px;font-size:36px;color:var(--navy);line-height:1.35;opacity:0}
.big2{display:block;font-family:Fraunces,serif;font-size:120px;font-weight:600;color:var(--brass);line-height:1}
.note{font-size:40px;line-height:1.4;margin-top:30px}
.tiles{display:flex;gap:24px}
.tile{flex:1;background:var(--card);border-radius:16px;padding:26px 28px;border-left:8px solid var(--green);font-size:30px;font-weight:600;opacity:0}
.close{font-family:Fraunces,serif;font-size:96px;font-weight:600;line-height:1.1;margin-top:12px;opacity:0}
.brand{font-size:40px;font-weight:600;margin-top:70px;color:var(--brass);opacity:0}
.k{font-size:30px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;opacity:.85}
.hold{font-family:Fraunces,serif;font-weight:600;line-height:1.1;opacity:0}
.hold2{font-size:50px;font-weight:600;margin-top:26px;opacity:0}
.num{font-family:Fraunces,serif;font-weight:600;font-size:170px;line-height:1.02;opacity:0}
.strike{position:relative;display:inline-block}
.strike::after{content:'';position:absolute;left:-16px;right:-16px;top:52%;height:14px;background:#fff;transform-origin:left;transform:scaleX(0);
  animation:wipe .45s var(--s,0s) both}
"""


def page(body: str, d: float, bg: str = "") -> str:
    """One card: an HTML page of the given length; bg paints the whole frame (the red beat)."""
    html_style = f" style='background:{bg};color:#fff'" if bg else ""
    body_style = f"--D:{d:.2f}s" + (f";background:{bg};color:#fff" if bg else "")
    return (f"<!doctype html><html{html_style}><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{CSS}</style>"
            f"<body style='{body_style}'><div class=stage>{body}</div></body></html>")


def at(t: float, kind: str = "a", base: str = "", style: str = "") -> str:
    """The attributes of an element that animates in at t seconds: one class attribute, one style attribute."""
    cls = f"{base} {kind}".strip()
    return f'class="{cls}" style="animation-delay:{max(t, 0):.2f}s;{style}"'


# ---- the voice and the clock -----------------------------------------------------------------------------------------------------

def scenes() -> list[dict]:
    common.SCRIPT = SCRIPT
    return common.scenes()


def voice() -> None:
    index = {}
    for s in scenes():
        wavs = [narrate.say(x, f"UC01 scene {s['n']}") for x in s["say_sent"]]
        spans, t = [], 0.0
        for w in wavs:
            d = narrate.seconds(w)
            spans.append([round(t, 3), round(t + d, 3)])
            t += d + narrate.GAP
        index[str(s["n"])] = {"wavs": [str(w) for w in wavs], "spans": spans, "cap": s["cap_sent"],
                              "seconds": spans[-1][1], "words": len(s["spoken"].split())}
    (WORK / "narration.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    NR.update(index)
    words = sum(v["words"] for v in index.values())
    secs = sum(v["seconds"] for v in index.values())
    print(f"voice: {words} words, {secs:.1f} s of speech, {words / secs * 60:.0f} words a minute; "
          f"this film's voice spend so far {narrate.spent() - BASE_SPEND:.4f} USD", flush=True)


def T(n: int, k: int, off: float = 0.0) -> float:
    """Seconds into scene n at which its sentence k starts, plus off (the scene's clock, lead-in included)."""
    return LEAD + NR[str(n)]["spans"][k][0] + off


def dur(n: int) -> float:
    return round(LEAD + NR[str(n)]["seconds"] + TAIL, 3)


def starts() -> dict[int, float]:
    st, t = {}, 0.0
    for s in scenes():
        st[s["n"]] = round(t, 3)
        t += dur(s["n"])
    return st


# ---- the cards -----------------------------------------------------------------------------------------------------------------

def table(states: dict, labels: dict | None = None) -> str:
    """The signal table. states: row -> (caught, done), seconds into the scene; a row not in states is not reached yet."""
    labels = labels or {}
    out = ['<div><div class=hd><div>What arrives</div><div>The signal Harbor catches</div><div>Who acts, and how little</div></div>']
    for i, r in enumerate(ROWS):
        c, dn = states.get(i, (None, None))
        if c is None:
            out.append(f'<div class=row><div class=arr>{r["arr"]}</div><div class=sig>{r["sig"]}</div>'
                       f'<div class=who><span>{r["who"]}</span></div></div>')
            continue
        lc = "var(--red)" if r.get("red") else "var(--brass)"
        pc = "var(--red)" if r.get("red") else "var(--amber)"
        anim = f"lit .5s {c:.2f}s both" + (f", okb .5s {dn:.2f}s both" if dn is not None else "")
        wait_anim = f"show .35s {c + .35:.2f}s both" + (f", hide .3s {dn:.2f}s forwards" if dn is not None else "")
        pills = f'<span class="pill pw" style="--pc:{pc};animation:{wait_anim}">{r["wait"]}</span>'
        if dn is not None:
            pills += (f'<span class="pill pd" style="animation:show .35s {dn + .1:.2f}s both">'
                      f'{labels.get(i, r["done"])}</span>')
        out.append(f'<div class=row style="--lc:{lc};animation:{anim}"><div class=arr>{r["arr"]}</div>'
                   f'<div class=sig>{r["sig"]}</div><div class=who><span>{r["who"]}</span><span class=pb>{pills}</span></div></div>')
    out.append("</div>")
    return "".join(out)


def eyebrow(text: str) -> str:
    return f"<div {at(0.05, 'f', 'eyebrow')}>{text}</div>"


def cards_items() -> dict[str, tuple[str, float]]:
    out: dict[str, tuple[str, float]] = {}

    d = dur(1)
    out["scene-1"] = (page(f"""{eyebrow("Evergreen Office · Capital call 7")}
      <h1 {at(T(1, 0))}>A fund asks for money.</h1>
      <div {at(T(1, 1), 'a', 'sub')}>Evergreen Holdings, Cedarpoint Ventures III, USD 1,250,000 due 23 October.</div>""", d), d)

    d = dur(2)
    out["scene-2"] = (page(f"""{eyebrow("Tuesday 13 October, 09:12 · the operations inbox")}
      <div {at(0.2)}>{table({0: (T(2, 2), T(2, 3) + 0.6)})}</div>""", d), d)

    d = dur(3)
    out["scene-3"] = (page(f"""{eyebrow("It fits the commitment")}
      <div {at(0.2)}>{table({0: (0, 0), 1: (T(3, 0), T(3, 2) + 0.8)})}</div>""", d), d)

    d = dur(4)
    out["scene-4"] = (page(f"""{eyebrow("Can we pay it?")}
      <div {at(0.2)}>{table({0: (0, 0), 1: (0, 0), 2: (T(4, 1), None), 3: (T(4, 3), None)})}</div>""", d), d)

    d = dur(5)
    dec = T(5, 1, 0.3)
    out["scene-5"] = (page(f"""{eyebrow("Daniel decides")}
      <div {at(0.2)}>{table({0: (0, 0), 1: (0, 0), 2: (0, dec), 3: (0, dec)})}</div>""", d), d)

    d = dur(6)
    hit = T(6, 1, 0.2)
    out["scene-6"] = (page(f"""<div {at(T(6, 0), 'f', 'k')}>Before the payment</div>
      <div class=hold style="font-size:76px;margin-top:30px;animation:up .6s {T(6, 1):.2f}s both">The bank account changed.</div>
      <div style="display:flex;align-items:baseline;gap:56px;margin-top:40px">
        <span class="num strike" style="--s:{hit:.2f}s;animation:fade .3s {T(6, 1):.2f}s both">2209</span>
        <span class=num style="animation:up .6s {hit + .6:.2f}s both">4471</span>
      </div>
      <div class=hold2 {at(T(6, 2))}>Payment on hold. Harbor does not suggest the new account.</div>
      <div class=hold2 {at(T(6, 3))}>Office rule: call back on a known number before paying.</div>
      <div class=hold2 {at(T(6, 4), 'a', '', 'font-weight:700;margin-top:40px')}>Confirmed by call-back, 13 Oct, 15:40. They moved banks.</div>""",
                          d, bg=RED), d)

    d = dur(7)
    out["scene-7"] = (page(f"""{eyebrow("Thursday to Monday")}
      <div {at(0.2)}>{table({i: (0, 0) for i in range(5)}, {3: "Matched"})}</div>
      <div class=steps>
        <div class=step style="animation:up .5s {T(7, 0):.2f}s both"><b>Thu 22 Oct</b>Trade matched at 1.3405</div>
        <div class=step style="animation:up .5s {T(7, 1):.2f}s both"><b>Fri 23 Oct</b>Payment released by Daniel</div>
        <div class=step style="animation:up .5s {T(7, 2):.2f}s both"><b>Mon 26 Oct</b>Statement: USD 1,250,000 out</div>
      </div>""", d), d)

    d = dur(8)
    out["scene-8"] = (page(f"""{eyebrow("Everyone sees the new picture")}
      <div class=pair>
        <div {at(T(8, 0), 'a', 'panel')}>
          <div class=who2>Raj Patel · Chief Investment Officer</div>
          <div class=q>What is our unfunded commitment across all funds?</div>
          <div class=ans style="animation:up .6s {T(8, 0) + 1.4:.2f}s both"><span class=big2>USD 14.6m</span>
            across all funds, with Cedarpoint Ventures III at 2,750,000.</div>
        </div>
        <div {at(T(8, 1), 'a', 'panel', 'border-top-color:var(--brass)')}>
          <div class=who2>Mei Chen · Principal · Morning note, Monday</div>
          <div class=note>Cedarpoint Ventures III call 7 paid (USD 1,250,000). Holdings cash after calls: USD 1.17m.</div>
        </div>
      </div>""", d), d)

    d = dur(9)
    tiles = "".join(f'<div class=tile style="animation:up .5s {T(9, 0) + i * 0.25:.2f}s both">{x}</div>'
                    for i, x in enumerate(["Notice", "Commitment", "Cash", "Plan", "Bank account"]))
    out["scene-9"] = (page(f"""<div class=tiles>{tiles}</div>
      <div {at(T(9, 0), 'a', 'close')}>Five signals caught.</div>
      <div {at(T(9, 1), 'a', 'close')}>Six people.</div>
      <div {at(T(9, 2), 'a', 'close')}>Four clicks, one decision, one phone call.</div>
      <div {at(T(9, 2) + 1.0, 'a', 'brand')}>Signal Harbor 3.0</div>""", d), d)
    return out


def captions() -> list[tuple]:
    caps, st = [], starts()
    for s in scenes():
        n = s["n"]
        for cap, (a, b) in zip(NR[str(n)]["cap"], NR[str(n)]["spans"]):
            caps += build.sentence_cues(cap, st[n] + LEAD + a, st[n] + LEAD + b)
    return caps


# ---- the mix and the cut ------------------------------------------------------------------------------------------------------

def mix(total: float) -> Path:
    st = starts()
    n = int(total * sound.SR) + sound.SR
    vox, fx = np.zeros(n), np.zeros(n)
    for s in scenes():
        k = str(s["n"])
        for wav, (a, _) in zip(NR[k]["wavs"], NR[k]["spans"]):
            sound.place(vox, sound.read_wav(Path(wav)), st[s["n"]] + LEAD + a)
    for when, kind, gain in [
        (st[2] + T(2, 2), "tick", 0.5), (st[3] + T(3, 0), "tick", 0.5), (st[4] + T(4, 1), "tick", 0.5),
        (st[4] + T(4, 3), "tick", 0.5), (st[5] + T(5, 1, 0.3), "seal", 0.5), (st[6] + T(6, 1, 0.2), "strike", 0.6),
        (st[7] + T(7, 0), "chime", 0.5), (st[9] + T(9, 0), "chime", 0.5),
    ]:
        sound.place(fx, sound.cue(kind), when, gain)
    sec = {"cold": 0.4, "reveal": st[2], "pulse": (st[2], st[6]), "padonly": (st[6], st[7]), "close": st[9]}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), vox)
    raw = WORK / "mix-raw.wav"
    sound.write_wav(raw, vox + music * 0.7 + fx)
    dest = WORK / "mix.wav"
    build.loudnorm(raw, dest)
    return dest


def cut() -> None:
    st = starts()
    segs = [CARDS / f"scene-{s['n']}.mp4" for s in scenes()]
    lst = WORK / "cut.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    picture = WORK / "picture.mp4"
    build.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(picture))
    total = build.length(picture)
    audio = mix(total)
    build.ff("-i", str(picture), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", str(HERO))
    build.write_captions(captions(), SRT, WORK / "captions.ass")
    build.ff("-ss", f"{st[9] + T(9, 2) + 1.6:.2f}", "-i", str(HERO), "-frames:v", "1", str(POSTER))
    print(f"cut: {build.length(HERO):.1f} s, {HERO.stat().st_size / 1e6:.1f} MB", flush=True)


def main() -> None:
    global BASE_SPEND
    BASE_SPEND = narrate.spent()
    narrate.BUDGET = BASE_SPEND + COST_CAP   # narrate refuses another paid call once this film has used the cap
    narrate.TEMPO = 1.1                       # about 145 words a minute
    WORK.mkdir(parents=True, exist_ok=True)
    voice()
    cards.render(None, cards_items(), CARDS)
    cut()


if __name__ == "__main__":
    main()
