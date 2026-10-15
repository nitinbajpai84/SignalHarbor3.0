"""Animated cards of the launch film (kinetic type, chapter cards, b-roll fallbacks, the close) and the lower thirds.

    python tools/video/cards.py              # writes docs/video/out/film/cards/<name>.mp4 (and lower-<n>.png, transparent)
    python tools/video/cards.py scene-1      # only the named cards

Each card is an HTML page with CSS animations, drawn frame by frame: every animation is paused and set to the frame's time
(and `window.tick(t)` runs for count-ups), then the page is captured, so motion is exact at 30 fps on any machine.
Colours and type come from the product's design tokens (ui/src/styles/design.css); the mark is the product's own.
Card scenes are timed to the narration (cards.say -> common.phrase_time): a line lands as it is said.
A card is only drawn again when its HTML or length changed.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from common import FPS, H, LEAD, ROOT, W, WORK, load_json, phrase_time, scenes  # noqa: E402

CARDS = WORK / "cards"
MARK = (ROOT / "ui/public/brand/signal-harbor-mark-512-on-dark.png").as_uri()
FONTS = "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Manrope:wght@500;600;700;800&display=swap"
CHAPTER, TAIL = 1.0, 0.2
VCSS = """html,body{width:1080px!important;height:1920px!important}
.stage{width:1080px!important;height:1920px!important;padding:200px 70px 380px!important}
.eyebrow{font-size:38px!important}
h1{font-size:92px!important}h2{font-size:64px!important}.big{font-size:96px!important}
.vcols{display:grid!important;grid-template-columns:1fr 1fr;gap:50px 40px!important;margin-top:60px!important}
.vstack{flex-direction:column!important;gap:70px!important;align-items:flex-start!important}
.vstack>div:last-child{font-size:42px!important}"""


def tokens() -> str:
    css = (ROOT / "ui/src/styles/design.css").read_text(encoding="utf-8")
    m = re.search(r":root\s*\{(.*?)\n\}", css, re.S)
    return ":root{" + (m[1] if m else "") + "}"


BASE = """
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;background:var(--ds-ground);color:var(--ds-ink);font-family:'DM Sans',var(--ds-font);overflow:hidden}
.stage{position:relative;width:1920px;height:1080px;display:flex;flex-direction:column;justify-content:center;padding:0 160px;overflow:hidden}
.glow{position:absolute;inset:-200px;background:radial-gradient(900px 640px at 74% 24%,color-mix(in srgb,var(--ds-teal) 22%,transparent),transparent 70%),
  radial-gradient(700px 520px at 10% 95%,color-mix(in srgb,var(--ds-teal) 10%,transparent),transparent 70%);animation:drift var(--D) linear both;z-index:0}
.vig{position:absolute;inset:0;background:radial-gradient(1400px 900px at 50% 50%,transparent 55%,#0006 100%);z-index:0}
.stage>*:not(.glow):not(.vig){position:relative;z-index:1}
.push{animation:push var(--D) cubic-bezier(.4,0,.6,1) both;transform-origin:30% 50%}
@keyframes push{from{transform:scale(1)}to{transform:scale(var(--P,1.03))}}
@keyframes drift{from{transform:translate(0,0) scale(1)}to{transform:translate(-60px,30px) scale(1.06)}}
@keyframes up{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes out{from{opacity:1}to{opacity:0}}
@keyframes wipe{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes grey{to{color:var(--ds-ink-muted)}}
@keyframes lit{from{color:var(--ds-ink-muted);border-color:var(--ds-line)}to{color:var(--ds-ink);border-color:var(--ds-teal-bright)}}
@keyframes travel{from{left:0}to{left:calc(100% - 26px)}}
.w{display:inline-block;opacity:0;animation:up .28s cubic-bezier(.2,.7,.2,1) both}
.a{opacity:0;animation:up .6s cubic-bezier(.2,.7,.2,1) both}
.f{opacity:0;animation:fade .7s ease-out both}
.eyebrow{font-size:30px;letter-spacing:.18em;text-transform:uppercase;color:var(--ds-teal-bright);font-weight:600}
.big{font-family:'Manrope',sans-serif;font-weight:800;font-size:150px;letter-spacing:-.03em;line-height:1}
h1{font-family:'Manrope','DM Sans',sans-serif;font-size:120px;line-height:1.02;font-weight:800;letter-spacing:-.03em}
h2{font-family:'Manrope','DM Sans',sans-serif;font-size:84px;line-height:1.08;font-weight:800;letter-spacing:-.02em}
.sub{font-size:44px;color:var(--ds-ink-soft);line-height:1.36}
.mark{width:150px;height:150px}
.rule{width:150px;height:6px;border-radius:3px;background:var(--ds-teal-bright);transform-origin:left;animation:wipe .8s cubic-bezier(.6,0,.2,1) both}
.amber{color:var(--ds-amber)}.teal{color:var(--ds-teal-bright)}.muted{color:var(--ds-ink-muted)}
.strike{position:relative;display:inline-block;align-self:flex-start}
.strike::after{content:'';position:absolute;left:-10px;right:-10px;top:54%;height:8px;border-radius:4px;background:var(--ds-amber);transform-origin:left;
  transform:scaleX(0);animation:wipe .5s cubic-bezier(.6,0,.2,1) var(--S) both}
.lower{position:absolute;left:48px;bottom:210px;display:flex;align-items:center;gap:22px;background:color-mix(in srgb,var(--ds-ground) 90%,transparent);
  border:2px solid color-mix(in srgb,var(--ds-teal-bright) 50%,transparent);border-left:10px solid var(--ds-teal-bright);border-radius:14px;padding:16px 34px 16px 22px;box-shadow:0 14px 44px #000a}
.lower.top{bottom:auto;top:24px}
.lower img{width:48px;height:48px}.lower .c{font-size:24px;letter-spacing:.16em;text-transform:uppercase;color:var(--ds-teal-bright);font-weight:700}
.lower .t{font-size:36px;font-weight:700;margin-top:2px}
"""


def page(body: str, d: float, extra: str = "", push: float = 1.03, script: str = "") -> str:
    return (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{tokens()}{BASE}{extra}</style>"
            f"<body style='--D:{d:.2f}s;--P:{push}'><div class=stage><div class=glow></div><div class=vig></div>"
            f"<div class=push style='display:flex;flex-direction:column;justify-content:center;height:100%'>{body}</div></div>"
            f"<script>{script}</script></body>")


def at(t: float, cls: str = "a") -> str:
    return f'class={cls} style="animation-delay:{max(t, 0):.2f}s"'


def words(text: str, t: float, gap: float = 0.04) -> str:
    """Kinetic type: each word rises in 280 ms, 40 ms after the one before."""
    return " ".join(f'<span class=w style="animation-delay:{t + i * gap:.2f}s">{w}</span>' for i, w in enumerate(text.split()))


def say(n: int, phrase: str, early: float = 0.25) -> float:
    return LEAD + phrase_time(n, phrase) - early


def length(n: int) -> float:
    return round(LEAD + load_json(WORK / "narration.json")[str(n)]["seconds"] + TAIL, 3)


COUNT = """window.tick=t=>{document.querySelectorAll('[data-to]').forEach(e=>{const a=+e.dataset.at,to=+e.dataset.to,from=+(e.dataset.from||0);
 const k=Math.max(0,Math.min(1,(t-a)/0.6)),v=from+(to-from)*(1-Math.pow(1-k,3));e.textContent=(e.dataset.pre||'')+Math.round(v).toLocaleString('en-US');});};"""


def figure(to: int, t: float, pre: str = "USD ", frm: int = 0) -> str:
    return f'<span data-to="{to}" data-from="{frm}" data-at="{t:.2f}" data-pre="{pre}">{pre}{frm:,}</span>'


def build() -> dict[str, tuple[str, float]]:
    """name -> (html, seconds); seconds 0 means a still PNG with a transparent ground."""
    out: dict[str, tuple[str, float]] = {}
    for s in scenes():
        n = s["n"]
        if s["chapter"]:
            out[f"chapter-{n}"] = (page(f"""<div class=eyebrow {at(.05, 'f')}>Chapter</div>
              <h1 style="font-size:150px;margin-top:18px" {at(.15)}>{s['chapter'].upper()}</h1>
              <div class=rule style="margin-top:40px;animation-delay:.4s"></div>""", CHAPTER, push=1.02), CHAPTER)
        if s["lower"]:
            c, t = [x.strip() for x in s["lower"].split("·", 1)]
            for pos, cls in (("", "lower"), ("-top", "lower top")):
                out[f"lower-{n}{pos}"] = (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{tokens()}{BASE}html,body{{background:transparent}}</style>"
                                          f"<div class='{cls}'><img src='{MARK}'><div><div class=c>{c}</div><div class=t>{t[0].upper() + t[1:]}</div></div></div>", 0)

    # 1 · the report changed (S01 to S03)
    d = length(1)
    t1, t2, t3, t4, t5 = say(1, "The September"), say(1, "USD 57.6"), say(1, "Four days later"), say(1, "The number changed"), say(1, "And nobody")
    out["scene-1"] = (page(f"""
      <div class=eyebrow>{words('September report', t1)} <span class=muted style="letter-spacing:.1em">{words('· Issued 3 October', t1 + .3)}</span></div>
      <div class="big strike" style="--S:{t4:.2f}s;margin-top:34px;animation:fade .4s {t2:.2f}s both,grey .5s {t4:.2f}s both;opacity:0">{figure(57600000, t2)}</div>
      <div style="margin-top:46px;font-size:64px;font-weight:700;font-family:Manrope" class=amber>
        <span class=a style="display:inline-block;animation-delay:{t3:.2f}s">+ {figure(180000, t3)}</span>
        <span class=muted style="font-size:40px;font-weight:600;margin-left:26px">{words('one fund revised, 7 October', t3 + .3)}</span></div>
      <div style="margin-top:60px;font-family:Manrope;font-weight:800;font-size:110px"><span {at(t5)}>Why?</span></div>""", d, script=COUNT), d)

    # 2 · BROLL-1 fallback: a figure travels and loses its proof at each step
    d = length(2)
    steps = ["Statement", "Spreadsheet", "Report", "Decision"]
    cues = ["From a statement", "to a spreadsheet", "to a report", "to a decision"]
    row = "".join(f"""<div class=a style="animation-delay:{say(2, c):.2f}s;flex:1;text-align:center">
        <div style="width:22px;height:22px;border-radius:50%;margin:0 auto 26px;background:var(--ds-teal-bright);opacity:{1 - i * .22:.2f}"></div>
        <div style="font-size:46px;font-weight:700;opacity:{1 - i * .2:.2f}">{x}</div></div>""" for i, (x, c) in enumerate(zip(steps, cues)))
    lost = say(2, "the proof gets lost")
    out["scene-2"] = (page(f"""<div class=eyebrow>{words('Every figure travels', say(2, 'Every figure travels'))}</div>
      <div style="position:relative;margin-top:110px;height:4px;background:var(--ds-line);border-radius:2px">
        <div style="position:absolute;top:-11px;width:26px;height:26px;border-radius:50%;background:var(--ds-teal-bright);box-shadow:0 0 30px var(--ds-teal-bright);
          animation:travel {say(2, 'to a decision') - say(2, 'From a statement') + .6:.2f}s cubic-bezier(.5,0,.5,1) {say(2, 'From a statement'):.2f}s both,out .6s {lost:.2f}s both"></div></div>
      <div style="display:flex;margin-top:46px">{row}</div>
      <div style="margin-top:90px;font-family:Manrope;font-size:96px;font-weight:800" class=amber><span {at(lost)}>Proof?</span></div>""", d), d)

    # 3 · the reveal: mark, four centres, four agents, people
    d = length(3)
    centres = [("Intent", "North"), ("Action", "Tally"), ("Build", "Span"), ("Consume", "Lumen")]
    cols = "".join(f"""<div style="flex:1;border-top:4px solid var(--ds-line);padding-top:28px;animation:lit .5s {say(3, c, .1):.2f}s both">
        <div style="font-family:Manrope;font-size:64px;font-weight:800;opacity:0;animation:up .5s {say(3, c, .15):.2f}s both">{c}</div>
        <div class=teal style="font-size:40px;font-weight:700;margin-top:14px;opacity:0;animation:up .5s {say(3, a, .15):.2f}s both">{a}</div></div>"""
                   for c, a in centres)
    out["scene-3"] = (page(f"""<div style="display:flex;align-items:center;gap:40px">
        <img class=mark src="{MARK}" style="opacity:0;animation:up .9s cubic-bezier(.2,.7,.2,1) {say(3, 'This is', .4):.2f}s both">
        <h1 {at(say(3, 'Signal Harbor', .2))}>Signal Harbor</h1></div>
      <div class=vcols style="display:flex;gap:44px;margin-top:90px">{cols}</div>
      <div style="margin-top:80px;font-size:56px;font-weight:700">{words('People stay in charge.', say(3, 'People stay'))}</div>""", d, push=1.04), d)

    # 10 · BROLL-2 fallback: behind every figure, three layers
    d = length(10)
    layers = [("Files as they landed", .55), ("The company model", .8), ("Built for each report", 1.0)]
    strata = "".join(f"""<div style="display:flex;align-items:center;gap:36px;margin-top:30px">
        <div style="height:16px;width:900px;border-radius:8px;background:var(--ds-teal-bright);opacity:{o};transform-origin:left;animation:wipe .9s cubic-bezier(.6,0,.2,1) {.5 + i * .35:.2f}s both"></div>
        <div style="font-size:36px;font-weight:600;opacity:0;animation:fade .6s {.9 + i * .35:.2f}s both">{x}</div></div>""" for i, (x, o) in enumerate(layers))
    out["scene-10"] = (page(f"""<h2>{words('Behind every figure', .15)}</h2><div style="margin-top:50px">{strata}</div>""", d), d)

    # 17 · trust: the machine, the one gate, people approve, every figure traced
    d = length(17)
    g = say(17, "One gated way out")
    out["scene-17"] = (page(f"""<h2 style="font-size:72px">{words('None of this asks for blind trust.', say(17, 'None of this'))}</h2>
      <div class=vstack style="display:flex;gap:240px;align-items:center;margin-top:70px">
        <div style="position:relative;width:640px;height:330px;border:3px solid var(--ds-teal-bright);border-radius:28px;opacity:0;animation:fade .6s {say(17, 'Your data stays'):.2f}s both">
          <div style="position:absolute;left:34px;top:24px;font-size:28px;letter-spacing:.14em;text-transform:uppercase" class=teal>Your machine</div>
          {''.join(f'<div style="position:absolute;left:{60 + i * 130}px;top:120px;width:90px;height:120px;border-radius:14px;background:var(--ds-surface);border:2px solid var(--ds-line)"></div>' for i in range(4))}
          <div style="position:absolute;right:-14px;top:130px;width:24px;height:70px;border-radius:8px;background:var(--ds-amber);opacity:0;animation:fade .4s {g:.2f}s both"></div>
          <div style="position:absolute;right:-160px;top:146px;font-size:26px;font-weight:700;padding:6px 16px;border-radius:999px;border:2px solid var(--ds-amber);opacity:0;animation:fade .3s {g + .5:.2f}s both,travel2 1.8s ease-in-out {g + .5:.2f}s both" class=amber>[Name]</div>
        </div>
        <div style="display:grid;gap:30px;font-size:48px;font-weight:700">
          <div>{words('Your data stays on your machine.', say(17, 'Your data stays'))}</div>
          <div class=muted style="font-size:38px">{words('One gated way out, with names replaced.', g)}</div>
          <div style="margin-top:20px">{words('Agents propose. People approve.', say(17, 'Agents propose'))}</div>
          <div class=teal>{words('Every figure is traced.', say(17, 'Every figure is traced'))}</div></div></div>""", d,
                          "@keyframes travel2{from{transform:translateX(-60px)}to{transform:translateX(60px)}}", push=1.02), d)

    # 19 · BROLL-3 fallback: the answer
    d = length(19)
    a = say(19, "the answer takes seconds")
    out["scene-19"] = (page(f"""<div class=eyebrow>{words('Why did the number move?', say(19, 'Now when someone', .1))}</div>
      <div style="position:relative;height:170px;margin-top:40px">
        <div class="big strike muted" style="position:absolute;--S:.2s;animation:out .6s {a:.2f}s both">USD 57,600,000</div>
        <div class="big teal" style="position:absolute;opacity:0;animation:up .7s {a + .2:.2f}s both">USD 57,780,000</div></div>
      <div style="margin-top:50px;font-size:44px;font-weight:600">{words('Revised fund · confirmed 7 Oct · source attached', a + .6)}</div>
      <div class=teal style="margin-top:30px;font-size:44px;font-weight:700">{words('In seconds. With proof.', say(19, 'With proof'))}</div>""", d), d)

    # 20 · close
    d = length(20)
    out["scene-20"] = (page(f"""<div style="text-align:center;display:flex;flex-direction:column;align-items:center">
        <img class=mark src="{MARK}" style="opacity:0;animation:up .9s cubic-bezier(.2,.7,.2,1) .1s both">
        <h1 style="margin-top:40px" {at(say(20, 'Signal Harbor', .3))}>Signal Harbor</h1>
        <div class=sub style="margin-top:30px;font-size:58px;color:var(--ds-ink)">{words('Every figure, explained.', say(20, 'Every figure'))}</div>
        <div class=teal style="margin-top:80px;font-size:40px;font-weight:600">{words('See it on your own data.', say(20, 'See it on'))}</div></div>
      <div style="position:absolute;inset:-400px;background:var(--ds-ground);opacity:0;animation:fade .8s {d - .9:.2f}s both;z-index:5"></div>""",
                          d, ".stage{padding:0}", push=1.02), d)
    for n in (1, 3, 17, 20):     # the cards the vertical cuts use, laid out for 1080x1920 (the caption band is the bottom 360 px)
        html, d = out[f"scene-{n}"]
        out[f"v-scene-{n}"] = (html.replace("</style>", VCSS + "</style>", 1), d)
    return out


def render(names: list[str] | None = None, items: dict | None = None, folder: Path | None = None) -> dict[str, Path]:
    """items/folder: another film's cards (film7.py), drawn the same way; default this film's."""
    folder = folder or CARDS
    folder.mkdir(parents=True, exist_ok=True)
    made: dict[str, Path] = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for name, (html, d) in (items if items is not None else build()).items():
            if names and name not in names:
                continue
            key = hashlib.sha256(f"{html}|{d}".encode()).hexdigest()[:12]
            dest = folder / (f"{name}.png" if d == 0 else f"{name}.mp4")
            stamp = folder / f"{name}.key"
            made[name] = dest
            if dest.exists() and stamp.exists() and stamp.read_text() == key:
                continue
            f = folder / f"{name}.html"
            f.write_text(html, encoding="utf-8")
            pg.set_viewport_size({"width": 1080, "height": 1920} if name.startswith("v-") or "-v-" in name else {"width": W, "height": H})
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(600)
            if d == 0:
                pg.screenshot(path=str(dest), omit_background=True)
            else:
                ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                                       "-i", "-", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(dest)],
                                      stdin=subprocess.PIPE)
                pg.evaluate("document.getAnimations().forEach(a => a.pause())")
                for i in range(int(round(d * FPS))):
                    t = i / FPS
                    pg.evaluate("t => { document.getAnimations().forEach(a => { a.currentTime = t * 1000 }); window.tick && window.tick(t); }", t)
                    ff.stdin.write(pg.screenshot(type="jpeg", quality=94))
                ff.stdin.close()
                ff.wait()
            stamp.write_text(key)
            print("card", name, f"{d:.1f} s", flush=True)
        b.close()
    return made


if __name__ == "__main__":
    render(sys.argv[1:] or None)
