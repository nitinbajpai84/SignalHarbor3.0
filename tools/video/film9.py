"""Film 9, "A day at Evergreen Office": about 3.5 minutes, narrated. Ten people, one assistant (docs/video/FILM9-SCRIPT.md).

    python tools/video/film9.py voice                      # narration, one WAV per sentence (narrate.say: cached, cost in docs/video/COST.md)
    python tools/video/film9.py record 2 4 5 6 12          # takes, as each person, from the running app (any take ids, see TAKES)
    python tools/video/film9.py cut                        # cards, lower thirds, the cut, the mix, the outputs

The order the takes are filmed in (drafting takes minutes, see film9_stage.py):
    1. film9_stage.py start ops_clerk; film9_stage.py wait ops_clerk          (background shell)
    2. record 2 4 5 6 12 3                                                     (Sam's drop needs his drafted brief)
    3. record 7a 8 9 10 11a                                                    (each "Start this" starts that person's build, on camera)
    4. film9_stage.py wait cio hr_admin                                        (background shell)
    5. record 7b 11b, then cut
Recorded at http://127.0.0.1:8640 against the film office D:/Temp/sh3-film (synthetic). Reuses record.Recorder and Scene (pointer,
rings, push-ins, loading paused out), build's camera, dips, captions and loudness, cards.render, narrate.say and sound's bed.
The 3.0 look: light pages, navy #1B3A5C, brass #B08D57, light #F4F6F9, Fraunces and Instrument Sans.
Passwords are read from the office's seed_credentials.txt, typed off camera, never printed or written.
Outputs (docs/video/out/): signal-harbor-a-day-at-evergreen.mp4, -share.mp4 (under 20 MB), -poster.png, .srt.
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import cards  # noqa: E402
import common  # noqa: E402
import narrate  # noqa: E402
import record  # noqa: E402
import sound  # noqa: E402
from common import DSF, FPS, LEAD, OUT, ROOT, VH, VW  # noqa: E402

BASE = "http://127.0.0.1:8640"
OFFICE = Path("D:/Temp/sh3-film")
WORK = OUT / "film9"
CARDS = WORK / "cards"
SCRIPT = ROOT / "docs/video/FILM9-SCRIPT.md"
NAME = "signal-harbor-a-day-at-evergreen"
HERO = OUT / f"{NAME}.mp4"
TAIL = 0.7
PHONE = (390, 844)
NAVY, BRASS, LIGHT = "#1B3A5C", "#B08D57", "#F4F6F9"
narrate.TEMPO = 1.1          # about 140 words a minute (the launch film ran at 1.2)
build.NAVY = "0xF4F6F9"      # the dips go to the 3.0 light ground, not to navy
build.LT_IN, build.LT_ON = 0.6, 4.2
FONTS = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&"
         "family=Instrument+Sans:wght@400;500;600;700&display=swap")

# the recorder's overlay in the 3.0 look: light ground, brass ring, navy pointer; the app keeps its own (light) theme
INIT = (record.INIT.replace("try { localStorage.setItem('sh_theme', 'dark'); } catch (e) {}", "")
        .replace("html,body{background:#0F1B2D}", f"html,body{{background:{LIGHT}}}")
        .replace("rgba(95,194,194,.18)", "rgba(176,141,87,.22)").replace("rgba(95,194,194,", "rgba(176,141,87,")
        .replace("#5FC2C2", BRASS).replace("border:2px solid rgba(246,244,238,.92)", f"border:2px solid {NAVY}")
        .replace("background:#F6F4EE}", f"background:{NAVY}}}"))
assert "#5FC2C2" not in INIT and "sh_theme" not in INIT


# ---- the script and the voice ---------------------------------------------------------------------------------------------------

def scenes() -> list[dict]:
    common.SCRIPT = SCRIPT
    out = common.scenes()
    for s in out:
        parts = [x.strip() for x in s["lower"].split("·")] if s["lower"] else []
        s["time"], s["person"], s["title"] = (parts + ["", "", ""])[:3]
    return out


def voice() -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    index = {}
    for s in scenes():
        wavs = [narrate.say(x, f"film 9 scene {s['n']}") for x in s["say_sent"]]
        spans, t = [], 0.0
        for w in wavs:
            d = narrate.seconds(w)
            spans.append([round(t, 3), round(t + d, 3)])
            t += d + narrate.GAP
        index[str(s["n"])] = {"wavs": [str(w) for w in wavs], "spans": spans, "cap": s["cap_sent"], "seconds": spans[-1][1],
                              "words": len(s["spoken"].split())}
    (WORK / "narration.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    words = sum(v["words"] for v in index.values())
    secs = sum(v["seconds"] for v in index.values())
    print(f"voice: {words} words, {secs:.1f} s of speech, {words / secs * 60:.0f} words a minute; spent so far {narrate.spent():.4f} USD")
    return index


def narr() -> dict:
    return json.loads((WORK / "narration.json").read_text(encoding="utf-8"))


def length(n: int) -> float:
    return round(LEAD + narr()[str(n)]["seconds"] + TAIL, 3)


def start_of(n: int, k: int) -> float:
    """Seconds into scene n at which its sentence k starts."""
    return LEAD + narr()[str(n)]["spans"][k][0]


# ---- signing in, off camera -------------------------------------------------------------------------------------------------------

def password(email: str) -> str:
    """The seeded password for one account. Held in memory only: never printed, logged or written."""
    for line in (OFFICE / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == email and not line.startswith("#"):
            return p[1]
    raise SystemExit(f"no seeded account {email}")


def sign_in(pw, who: str) -> dict:
    email = f"{who}.evergreen@example.test"
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": VW, "height": VH})
    pg = ctx.new_page()
    pg.goto(BASE + "/login")
    pg.fill("#email", email)
    pg.fill("#password", password(email))
    pg.click("button[type=submit]")
    pg.wait_for_url(lambda u: "/login" not in u, timeout=30000)
    state = ctx.storage_state()
    b.close()
    return state


def started(state: dict, browser) -> str:
    """The thread of this person's first suggested build, as the Desk finds it."""
    ctx = browser.new_context(storage_state=state)
    r = ctx.request.get(BASE + "/api/v3/me/role").json()
    ctx.close()
    tid = (r.get("builds") or [{}])[0].get("started")
    if not tid:
        raise SystemExit("that build has not been started yet (see the order in the docstring)")
    return tid


# ---- the takes --------------------------------------------------------------------------------------------------------------------

class Shot(record.Scene):
    """record.Scene with cues taken from this film's narration; `off` is where this take starts inside its scene."""

    def __init__(self, n, page, rec, seconds, opener, off: float = 0.0):
        super().__init__(n, page, rec, seconds, opener)
        self.off = off

    def cue(self, k: int, early: float = 0.3) -> None:
        left = start_of(self.n, k) - self.off - early - self.now()
        if left > 0:
            self.hold(left)
        elif left < -0.6:
            print(f"  take {self.n}: {-left:.1f} s late for sentence {k}", flush=True)


def up(loc, n: int = 1):
    x = loc
    for _ in range(n):
        x = x.locator("xpath=..")
    return x


def t2_desk(s: Shot) -> None:
    p = s.page
    s.hold(0.6)
    s.soft("ring greeting", s.ring, p.get_by_role("heading", name=re.compile("Good morning")), 1.8)
    s.cue(1)
    feed = up(p.get_by_text("Overnight", exact=True))
    s.soft("point feed", s.point, feed)
    s.soft("ring feed", s.ring, feed, 3.0)
    s.cue(2, 0.6)
    s.soft("zoom feed", s.zoom, feed, 1.35, 4.2, 30)
    s.cue(3)
    act = p.get_by_text("did not load", exact=False).first
    s.soft("ring act now", s.ring, up(act, 1), 2.6)
    s.soft("point act now", s.point, act)


def t3_drop(s: Shot) -> None:
    p = s.page
    s.hold(0.5)
    band = p.get_by_text("Drop the files for this use case", exact=True)
    s.soft("scroll to band", s.scroll_to, band, 220, 1300)
    s.soft("ring band", s.ring, up(band), 1.6)
    s.cue(1, 0.6)
    pick = p.locator("input[type=file]").first
    s.soft("point choose", s.point, p.get_by_text("Choose files", exact=True))
    s.hold(0.3)
    s.click(p.get_by_text("Choose files", exact=True))
    pick.set_input_files(str(DROP))
    s.ready(p.locator(".b3-recent").get_by_text(DROP.name, exact=True), 60)
    s.mark("chime")
    s.cue(2, 0.2)
    row = p.locator(".b3-recent li").filter(has_text=DROP.name).first
    s.soft("ring row", s.ring, row, 3.0)
    s.soft("zoom row", s.zoom, row, 1.35, 3.6, 40)
    s.hold(2.0)
    s.soft("ring chips", s.ring, p.locator(".b3-chips").first, 2.2)


def t4_phone(s: Shot) -> None:
    p = s.page
    s.hold(0.8)
    s.cue(1, 0.9)
    box = p.locator("#v3c-q")
    s.type(box, "What is our cash by entity today?")
    p.keyboard.press("Enter")
    s.mark("tick")
    s.hold(1.0)
    s.cue(2, 0.6)
    fig = p.locator(".v3c-card").first
    s.soft("ring answer", s.ring, fig, 2.6)
    s.hold(1.8)
    src = p.get_by_text("Source:", exact=False).first
    s.soft("scroll to source", s.scroll_to, src, 330, 1500)
    s.soft("ring source", s.ring, up(src, 1), 2.6)


def t5_daniel(s: Shot) -> None:
    p = s.page
    s.hold(0.6)
    s.soft("ring answer", s.ring, p.locator(".v3c-card").first, 2.2)
    s.cue(1, 0.2)
    chip = p.get_by_role("button", name="Can each entity meet its calls?").first
    s.soft("scroll chip", s.scroll_to, chip, 420, 900)
    s.click(chip)
    s.ready(p.get_by_text("Yes:", exact=False))
    s.mark("chime")
    s.cue(2, 0.3)
    yes = p.get_by_text("Yes:", exact=False).first
    s.soft("ring yes", s.ring, yes, 2.4)
    s.soft("zoom yes", s.zoom, yes, 1.3, 4.0, 40)


def t6_action(s: Shot) -> None:
    p = s.page
    s.hold(0.6)
    s.click(p.locator("button.act-pill").filter(has_text="Exceptions").first)   # other people's drafts wait here too
    item = p.locator("article.act-item").filter(has_text="did not load").first
    s.cue(1, 0.4)
    s.soft("ring exception", s.ring, item, 2.4)
    s.hold(1.4)
    s.click(item.get_by_role("button", name=re.compile("^Open ")))
    s.hold(0.8)
    s.cue(2, 0.2)
    ask = p.get_by_text("What Harbor is asking", exact=False).first
    s.soft("ring asking", s.ring, up(ask, 2), 2.8)
    s.soft("zoom asking", s.zoom, up(ask, 2), 1.25, 3.4, 40)
    s.cue(3, 0.3)
    s.soft("point thread", s.point, p.locator(".act-go, a, button").filter(has_text="Open the thread").first)


def t7a_raj(s: Shot) -> None:
    p = s.page
    card = up(p.get_by_role("heading", name=re.compile("^For you")))
    s.soft("scroll card", s.scroll_to, card, 90, 900)
    s.hold(0.4)
    s.soft("ring card", s.ring, card, 2.6)
    s.cue(1, 0.6)
    li = p.locator(".rs-builds li").filter(has_text="Why did the NAV move").first
    s.soft("ring nav build", s.ring, li, 2.2)
    s.hold(1.6)
    s.click(li.get_by_role("button", name="Start this"))
    s.ready(p.get_by_text("Reading your question", exact=False), 60)
    s.hold(1.4)


def press(name: str):
    """A take: the person's 'For you' card, the suggested build ringed, Start this pressed, the build opening."""
    def take(s: Shot) -> None:
        p = s.page
        card = up(p.get_by_role("heading", name=re.compile("^For you")))
        s.soft("scroll card", s.scroll_to, card, 90, 700)
        s.hold(0.3)
        li = p.locator(".rs-builds li").filter(has_text=name).first
        s.soft("ring build", s.ring, li, 2.0)
        s.hold(1.4)
        s.click(li.get_by_role("button", name="Start this"))
        s.ready(p.get_by_text("Reading your question", exact=False), 60)
        s.hold(1.0)
    return take


def t7b_raj(s: Shot) -> None:
    """Raj's drafted brief: the graph, the question at its centre, then who reads it, a rule and a source."""
    p = s.page
    s.hold(0.5)
    graph = p.locator(".b3-graph").first
    s.soft("ring graph", s.ring, graph, 2.2)
    s.soft("zoom graph", s.zoom, graph, 1.3, 7.5, 20)
    s.hold(2.4)
    for text in ("The question", "Who reads and decides", "Rule", "Amended fund"):
        s.soft(f"ring {text}", s.ring, up(p.locator(".b3-graph").get_by_text(text, exact=False).first), 1.3)
        s.hold(1.4)


def t11b_priya(s: Shot) -> None:
    """Priya's drafted brief: Harbor's message on the process map and its steps, then the graph."""
    p = s.page
    s.hold(0.4)
    msg = p.get_by_text("process steps", exact=False).first
    s.soft("scroll message", s.scroll_to, msg, 260, 1100)
    s.soft("ring message", s.ring, msg, 3.2)
    s.soft("zoom message", s.zoom, msg, 1.3, 3.4, 40)
    s.hold(4.6)
    s.soft("scroll graph", s.scroll_to, p.locator(".b3-graph").first, 140, 1000)
    s.soft("ring graph", s.ring, p.locator(".b3-graph").first, 2.6)


def t12_knowledge(s: Shot) -> None:
    p = s.page
    s.hold(0.6)
    s.cue(1, 0.5)
    box = p.get_by_text("Entity B", exact=True).first
    s.click(box)
    s.hold(0.8)
    side = p.get_by_text("Entity B", exact=True).last
    s.soft("ring side", s.ring, up(side, 2), 2.6)
    s.soft("zoom side", s.zoom, up(side, 2), 1.2, 3.2, 40)
    s.cue(2, 0.6)
    s.click(p.get_by_role("link", name="Skills Harbor uses").first)
    s.ready(p.get_by_text("Skill library", exact=False))
    s.soft("ring intro", s.ring, p.get_by_text("A person admits every new skill", exact=False).first, 3.0)
    s.hold(2.2)
    s.soft("ring table", s.ring, p.locator("table").first, 2.4)


DROP = ROOT / "tests/v1/fixtures/10uc/otc_confirms/FXF-2026-002_confirmation_2026-10-05.pdf"   # recognised by its word "confirmation"
# id -> scene, who, page (or "thread:<who>" for that person's first suggested build), the text it waits for, the action, phone?, part
TAKES = {
    "2": dict(n=2, who="anita.rao", path="/v3/desk", ready="Overnight", fn=t2_desk),
    "3": dict(n=3, who="sam.lee", path="thread:sam.lee", ready="Drop the files for this use case", fn=t3_drop),
    "4": dict(n=4, who="mei.chen", path="/v3/consume", ready="Watchlist", fn=t4_phone, phone=True),
    "5": dict(n=5, who="daniel.foo", path="/v3/consume", ready="Watchlist", fn=t5_daniel),
    "6": dict(n=6, who="grace.ong", path="/v3/action", ready="Needs a person", fn=t6_action),
    "7a": dict(n=7, who="raj.patel", path="/v3/desk", ready="Builds Harbor suggests", fn=t7a_raj, part="a"),
    "7b": dict(n=7, who="raj.patel", path="thread:raj.patel", ready="Click any box", fn=t7b_raj, part="b"),
    "8": dict(n=8, who="sofia.reyes", path="/v3/desk", ready="Builds Harbor suggests", fn=press("Kestrel Ridge")),
    "9": dict(n=9, who="tom.hale", path="/v3/desk", ready="Builds Harbor suggests", fn=press("limit monitoring")),
    "10": dict(n=10, who="helen.foo", path="/v3/desk", ready="Builds Harbor suggests", fn=press("Manager statements")),
    "11a": dict(n=11, who="priya.nair", path="/v3/desk", ready="Builds Harbor suggests", fn=press("Process map and SOP"), part="a"),
    "11b": dict(n=11, who="priya.nair", path="thread:priya.nair", ready="Click any box", fn=t11b_priya, part="b"),
    "12": dict(n=12, who="anita.rao", path="/v3/knowledge", ready="How Evergreen Office works", fn=t12_knowledge),
}
SPLIT = {7: 2, 11: 2}     # scene -> the sentence at which part b (the drafted brief) starts


def take_length(tid: str) -> tuple[float, float]:
    """(offset inside the scene, seconds) of one take."""
    t = TAKES[tid]
    n, L = t["n"], length(t["n"])
    if t.get("part") == "a":
        return 0.0, round(start_of(n, SPLIT[n]) - 0.2, 3)
    if t.get("part") == "b":
        fa = WORK / f"take-{n}a.json"     # part a as it was filmed
        a = json.loads(fa.read_text(encoding="utf-8"))["d"] if fa.exists() else round(start_of(n, SPLIT[n]) - 0.2, 3)
        return a, round(L - a, 3)
    return 0.0, L


class PhoneRecorder(record.Recorder):
    """The phone take, laid out in the middle of the light frame with a navy edge (record.Recorder stretches to 16:9)."""

    def write(self, end: float, dest: Path) -> float:
        fr = [(max(t, 0.0), n) for t, n in self.frames if t < end]
        lines = []
        for i, (t, n) in enumerate(fr):
            nxt = fr[i + 1][0] if i + 1 < len(fr) else end
            lines += [f"file '{n}'", f"duration {max(nxt - t, 0.001):.4f}"]
        lines.append(f"file '{fr[-1][1]}'")
        (self.dir / "frames.txt").write_text("\n".join(lines), encoding="utf-8")
        vf = (f"scale=-2:968:flags=lanczos,pad=iw+20:ih+20:10:10:color=0x1B3A5C,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xF4F6F9,"
              f"tpad=start_duration={fr[0][0]:.3f}:start_mode=clone,fps={FPS},format=yuv420p")
        build.ff("-f", "concat", "-safe", "0", "-i", "frames.txt", "-vf", vf, "-t", f"{end:.3f}", "-c:v", "libx264", "-crf", "14",
                 "-preset", "medium", "-pix_fmt", "yuv420p", str(dest), cwd=self.dir)
        return end


def record_take(browser, states: dict, tid: str) -> dict:
    t = TAKES[tid]
    off, d = take_length(tid)
    phone = t.get("phone", False)
    clip = WORK / f"take-{tid}.mp4"
    opened = []

    def opener(who: str, path: str):
        size = PHONE if phone else (VW, VH)
        ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2.5 if phone else DSF,
                                  storage_state=states[who], color_scheme="light", reduced_motion="no-preference", is_mobile=phone,
                                  has_touch=False)
        ctx.add_init_script(INIT)
        opened.append(ctx)
        pg = ctx.new_page()
        pg.goto(BASE + path)
        return pg

    path = t["path"]
    if path.startswith("thread:"):
        path = "/v3/build/" + started(states[path[7:]], browser)
    page = opener(t["who"], path)
    page.get_by_text(t["ready"], exact=False).first.wait_for(state="visible", timeout=120000)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:  # noqa: BLE001 - a page that polls never goes idle
        pass
    page.wait_for_timeout(800)
    page.evaluate("window.__sh.move(%d, %d, 10)" % ((300, 600) if phone else (1100, 560)))
    page.wait_for_timeout(500)
    rec = (PhoneRecorder if phone else record.Recorder)(WORK / f"frames-{tid}")
    rec.attach(page)
    rec.start()
    page.evaluate("window.__sh.nudge()")
    s = Shot(t["n"], page, rec, d, opener, off)
    try:
        t["fn"](s)
    except Exception as e:  # noqa: BLE001 - what was filmed so far is kept, the failure is reported
        rec.resume()
        print(f"take {tid}: FAILED ({type(e).__name__}: {str(e)[:300]})", flush=True)
        s.page.screenshot(path=str(WORK / f"take-{tid}-failed.png"))
    left = d - s.now()
    if left > 0:
        s.hold(left)
    elif left < -0.3:
        print(f"take {tid}: {-left:.1f} s over its length", flush=True)
    rec.pause()
    rec.write(d, clip)
    s.page.screenshot(path=str(WORK / f"take-{tid}-end.png"))
    for c in opened:
        c.close()
    info = {"tid": tid, "n": t["n"], "clip": str(clip), "zooms": s.zooms, "marks": s.marks, "d": d, "off": off, "missed": s.missed}
    (WORK / f"take-{tid}.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"take {tid}: {d:.1f} s, {len(rec.frames)} frames, {len(s.zooms)} push-ins, missed {s.missed}", flush=True)
    return info


def record_takes(ids: list[str]) -> None:
    urllib.request.urlopen(BASE + "/login", timeout=5)
    WORK.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--hide-scrollbars"])
        who = {TAKES[i]["who"] for i in ids} | {TAKES[i]["path"][7:] for i in ids if TAKES[i]["path"].startswith("thread:")}
        states = {w: sign_in(pw, w) for w in sorted(who)}
        for i in ids:
            record_take(browser, states, i)
        browser.close()


# ---- cards and lower thirds -------------------------------------------------------------------------------------------------------

CSS = f"""
*{{box-sizing:border-box;margin:0}}
:root{{--navy:{NAVY};--brass:{BRASS};--light:{LIGHT};--ink:#0E1A2B;--mute:#5A6878}}
html,body{{width:1920px;height:1080px;background:var(--light);color:var(--ink);font-family:'Instrument Sans',sans-serif;overflow:hidden}}
.stage{{position:relative;width:1920px;height:1080px;display:flex;flex-direction:column;justify-content:center;padding:0 200px;overflow:hidden}}
.glow{{position:absolute;inset:-200px;background:radial-gradient(900px 640px at 78% 22%,rgba(176,141,87,.16),transparent 70%),
  radial-gradient(700px 520px at 8% 96%,rgba(27,58,92,.08),transparent 70%);animation:drift var(--D) linear both}}
@keyframes drift{{from{{transform:translate(0,0)}}to{{transform:translate(-50px,26px)}}}}
@keyframes up{{from{{opacity:0;transform:translateY(24px)}}to{{opacity:1;transform:none}}}}
@keyframes wipe{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
.stage>*:not(.glow){{position:relative;z-index:1}}
.a{{opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) both}}
.brand{{display:flex;align-items:center;gap:22px;font-family:Fraunces,serif;font-size:40px;font-weight:600;color:var(--navy)}}
.sq{{width:52px;height:52px;border-radius:12px;background:var(--navy)}}
.rule{{width:150px;height:6px;border-radius:3px;background:var(--brass);transform-origin:left;animation:wipe .8s cubic-bezier(.6,0,.2,1) both}}
h1{{font-family:Fraunces,serif;font-weight:500;font-size:128px;line-height:1.04;letter-spacing:-.02em;color:var(--navy)}}
.b{{color:var(--brass)}}
.eyebrow{{font-size:28px;letter-spacing:.18em;text-transform:uppercase;color:var(--brass);font-weight:600}}
"""


def card_page(body: str, d: float) -> str:
    return (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{CSS}</style>"
            f"<body style='--D:{d:.2f}s'><div class=stage><div class=glow></div>{body}</div></body>")


def at(t: float) -> str:
    return f'class=a style="animation-delay:{max(t, 0):.2f}s"'


def card_items() -> dict:
    nr = narr()
    d1, d13 = length(1), length(13) + 1.2
    s1 = [LEAD + a for a, _ in nr["1"]["spans"]]
    title = card_page(f"""<div class=brand {at(.1)}><div class=sq></div>Signal Harbor</div>
      <div class=rule style="margin:44px 0 48px;animation-delay:.4s"></div>
      <h1><span {at(s1[0] + .2)}>Evergreen Office.</span><br><span {at(s1[1])}>Ten people.</span>
      <span class=b><span {at(s1[1] + 1.4)}>One assistant.</span></span></h1>""", d1)
    s13 = [LEAD + a for a, _ in nr["13"]["spans"]]
    words = "".join(f'<span {at(s13[i] - .1)} style="display:inline-block;margin-right:34px;animation-delay:{s13[i] - .1:.2f}s">{w}</span>'
                    for i, w in enumerate(["Act.", "Build.", "Consume.", "Know."]))
    close = card_page(f"""<h1 style="font-size:140px">{words}</h1>
      <div class=rule style="margin:56px 0 44px;animation-delay:{s13[4] - .3:.2f}s"></div>
      <div class=brand style="font-size:64px;gap:28px;opacity:0;animation:up .8s {s13[4] - .2:.2f}s both"><div class=sq style="width:72px;height:72px;border-radius:16px"></div>Signal Harbor <span class=b style="font-weight:500">3.0</span></div>""", d13)
    out = {"title": (title, d1), "close": (close, d13)}
    for s in scenes():
        if s["person"]:
            out[f"lower-{s['n']}"] = (f"""<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>
              *{{margin:0;box-sizing:border-box}}html,body{{width:1920px;height:1080px;background:transparent;overflow:hidden;font-family:'Instrument Sans',sans-serif}}
              .lt{{position:absolute;left:56px;bottom:56px;display:flex;align-items:stretch;gap:0;background:rgba(255,255,255,.97);border-radius:16px;
                box-shadow:0 14px 44px rgba(14,26,43,.22),0 0 0 1px rgba(27,58,92,.10);overflow:hidden}}
              .t{{background:{NAVY};color:#fff;font:600 34px 'Instrument Sans';padding:0 30px;display:flex;align-items:center;letter-spacing:.02em}}
              .w{{padding:18px 34px 18px 26px;border-left:8px solid {BRASS}}}
              .n{{font:500 44px Fraunces,serif;color:{NAVY};line-height:1.1}}
              .r{{font:600 22px 'Instrument Sans';letter-spacing:.14em;text-transform:uppercase;color:{BRASS};margin-top:6px}}
              </style><div class=lt><div class=t>{html.escape(s['time'])}</div><div class=w><div class=n>{html.escape(s['person'])}</div>
              <div class=r>{html.escape(s['title'])}</div></div></div>""", 0)
    return out


# ---- the cut ----------------------------------------------------------------------------------------------------------------------

def timeline() -> list[dict]:
    items, t = [], 0.0
    for s in scenes():
        n = s["n"]
        d = length(n) + (1.2 if n == 13 else 0)
        items.append({"n": n, "kind": s["kind"], "d": round(d, 3), "start": round(t, 3)})
        t += round(d, 3)
    return items


def scene_segment(it: dict) -> Path:
    n, dest = it["n"], WORK / f"seg-{it['n']:02d}.mp4"
    if it["kind"] == "card":
        build.card_segment(CARDS / f"{'title' if n == 1 else 'close'}.mp4", it["d"], None, n != 1, True, dest)
        return dest
    ids = [k for k, v in TAKES.items() if v["n"] == n]
    lower = CARDS / f"lower-{n}.png"
    parts = []
    used = 0.0
    for i, k in enumerate(ids):
        info = json.loads((WORK / f"take-{k}.json").read_text(encoding="utf-8"))
        part = WORK / f"seg-{n:02d}-{k}.mp4"
        d = info["d"] if i < len(ids) - 1 else round(it["d"] - used, 3)   # the last part ends with the scene (its last frame held up to 2 s)
        used += d
        build.screen_segment(info, d, lower if i == 0 else None, True, True, part)   # a dip between parts: time passes
        parts.append(part)
    if len(parts) == 1:
        parts[0].replace(dest)
    else:
        lst = WORK / f"seg-{n:02d}.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        build.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dest))
    return dest


def mix(items: list[dict], total: float) -> Path:
    nr = narr()
    n = int(total * sound.SR) + sound.SR
    vox, fx = np.zeros(n), np.zeros(n)
    for it in items:
        for wav, (a, _) in zip(nr[str(it["n"])]["wavs"], nr[str(it["n"])]["spans"]):
            sound.place(vox, sound.read_wav(Path(wav)), it["start"] + LEAD + a)
        for k, v in TAKES.items():
            f = WORK / f"take-{k}.json"
            if v["n"] == it["n"] and f.exists():
                info = json.loads(f.read_text(encoding="utf-8"))
                for kind, at_ in info["marks"]:
                    sound.place(fx, sound.cue(kind) * 0.5, it["start"] + info["off"] + at_)
    st = {it["n"]: it["start"] for it in items}
    sec = {"cold": 0.4, "reveal": st[2] - 0.6, "pulse": (st[2], st[13] - 1.0), "padonly": (st[13] - 1.0, st[13]), "close": st[13]}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), vox)
    raw = WORK / "mix-raw.wav"
    sound.write_wav(raw, vox + music * 0.7 + fx)
    dest = WORK / "mix.wav"
    build.loudnorm(raw, dest)
    return dest


def cut() -> None:
    CARDS.mkdir(parents=True, exist_ok=True)
    cards.render(None, card_items(), CARDS)
    items = timeline()
    segs = [scene_segment(it) for it in items]
    lst = WORK / "cut.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    picture = WORK / "picture.mp4"
    build.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(picture))
    total = build.length(picture)
    audio = mix(items, total)
    build.ff("-i", str(picture), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", str(HERO))
    nr = narr()
    caps = []
    for it in items:
        for cap, (a, b) in zip(nr[str(it["n"])]["cap"], nr[str(it["n"])]["spans"]):
            caps += build.sentence_cues(cap, it["start"] + LEAD + a, it["start"] + LEAD + b)
    build.write_captions(caps, OUT / f"{NAME}.srt", WORK / "captions.ass")
    # share copy: two passes to about 17.5 MB with the voice, under 20 MB
    share = OUT / f"{NAME}-share.mp4"
    kbps = int(17.5 * 8 * 1024 / total) - 96
    c = ["-i", str(HERO), "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", str(WORK / "share2pass")]
    build.ff(*c, "-pass", "1", "-an", "-f", "mp4", "NUL")
    build.ff(*c, "-pass", "2", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(share))
    st7 = next(i for i in items if i["n"] == 7)
    build.ff("-ss", f"{st7['start'] + st7['d'] - 2.0:.2f}", "-i", str(HERO), "-frames:v", "1", str(OUT / f"{NAME}-poster.png"))
    (WORK / "timeline.json").write_text(json.dumps(items, indent=1), encoding="utf-8")
    print(f"cut: {build.length(HERO):.1f} s, hero {HERO.stat().st_size / 1e6:.1f} MB, share {share.stat().st_size / 1e6:.1f} MB", flush=True)
    for it in items:
        print(f"  scene {it['n']:>2} {it['kind']:6} at {it['start']:6.1f} s, {it['d']:.1f} s", flush=True)


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["cut"]
    if cmd == "voice":
        voice()
    elif cmd == "record":
        record_takes(rest)
    elif cmd == "cut":
        cut()
    else:
        raise SystemExit(__doc__)
