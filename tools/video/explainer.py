"""The 90-second Build explainer: how a project works, in the five chapters the Build landing lists (ui/src/v1/b9/ExplainerVideo.tsx).

    python tools/video/build.py --explainer                   # voice, record on a fresh seed (port 8696), cut
    python tools/video/build.py --explainer --assemble-only   # only the cut, from docs/video/out/explainer
    python tools/video/explainer.py [--assemble-only] [--keep-server]

Reuses the launch film's tools: narrate.say (ash, cached by text hash, cost in COST.md), record.Recorder and Scene (the
pointer, rings, paused loading), build's camera, captions and loudness, sound's bed and ducking, the close card of scene 20.
Testing mode only, no agent calls: every screen is the seeded demo project. Each chapter starts exactly on the landing's chapter
time (a take that runs long is played a little faster). Server: .sh-tmp/testenv/explainer on port 8696, stopped at the end.
Outputs: docs/video/out/signal-harbor-build-explainer.mp4 and .srt, stills in out/explainer/stills, and the copy the app serves
at /static/explainer.mp4 (ui/public/static, plus ui/dist/static when the UI is built).
"""
import os
import sys

os.environ["SH_FILM_ENV"] = "vid6"      # before common is imported: the explainer's own data and port
os.environ["SH_FILM_PORT"] = "8696"

import argparse  # noqa: E402
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
import narrate  # noqa: E402
import record  # noqa: E402
import sound  # noqa: E402
from common import BASE, DATA, DSF, FPS, LEAD, OUT, ROOT, VH, VW, sign_in_state  # noqa: E402

PORT = 8696
WORK = OUT / "explainer"
NAME = "signal-harbor-build-explainer"
DEST = OUT / f"{NAME}.mp4"
END = 89.8              # the film ends here (the landing promises 90 seconds)
CLOSE = 2.4             # the closing card, inside the last chapter
CARD = ROOT / "docs/video/out/film/cards/scene-20.mp4"     # the launch film's close: mark, Signal Harbor, Every figure, explained.

# (start second, title, narration). {caption|spoken} lets the voice say a figure in words.
CHAPTERS = [
    (0, "Say what you need", "You open Build and press New project. Then you say what you need, in your own words. No forms to fill in. "
     "North, our industry expert, asks the questions a good analyst would ask, and writes the brief beside you. The sponsor signs it."),
    (20, "The data team builds", "Span the architect reads the signed brief first. It asks only what is missing, each question with an answer ready to accept. "
     "Then it drafts the design pack: the tables, the mapping and the checks. The head of data approves it, and it is locked for the builder."),
    (45, "Check the numbers", "Span the builder runs it on a copy, by itself. Then it checks the numbers against last month's report, line by line. "
     "Two lines differ, so it hands the evidence back to the architect. Version 2 is approved, and every figure matches."),
    (65, "Design what people see", "Once it is live, Lumen proposes a starter dashboard from the brief, so nothing starts from a blank page. "
     "Accept it, or ask for something specific. Someone else approves it."),
    (80, "Deliver", "Last, choose where it goes: Reports in Consume, the Morning Note, email or Teams. Each channel is approved too."),
]
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z{])")


def parts(text: str) -> tuple[list[str], list[str]]:
    raw = [s for s in SENT.split(text) if s]
    return ([re.sub(r"\{([^|}]*)\|([^}]*)\}", r"\1", x) for x in raw], [re.sub(r"\{([^|}]*)\|([^}]*)\}", r"\2", x) for x in raw])


def length(i: int) -> float:
    """The chapter's screen time: up to the next chapter, or to the close card."""
    return (CHAPTERS[i + 1][0] if i + 1 < len(CHAPTERS) else END - CLOSE) - CHAPTERS[i][0]


def voice() -> dict:
    """Each sentence voiced (cached by its words), its start and end inside the chapter. Writes WORK/narration.json."""
    WORK.mkdir(parents=True, exist_ok=True)
    index = {}
    for i, (_, title, text) in enumerate(CHAPTERS):
        cap, say = parts(text)
        wavs = [narrate.say(x, f"explainer chapter {i + 1}") for x in say]
        spans, t = [], 0.0
        for w in wavs:
            d = narrate.seconds(w)
            spans.append([round(t, 3), round(t + d, 3)])
            t += d + narrate.GAP
        index[str(i)] = {"wavs": [str(w) for w in wavs], "spans": spans, "cap": cap, "words": len(" ".join(say).split()),
                         "seconds": spans[-1][1]}
        print(f"chapter {i + 1}: {spans[-1][1]:.1f} s of voice for {length(i):.1f} s of picture", flush=True)
    (WORK / "narration.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


# ---- recording ----------------------------------------------------------------------------------------------------------------

class Chapter(record.Scene):
    """A chapter: the launch film's scene clock, timed against this film's narration."""

    def __init__(self, i: int, page, rec, opener, narr: dict):
        super().__init__(i, page, rec, length(i) - LEAD - record.TAIL, opener)
        self.narr = narr[str(i)]

    def at_text(self, phrase: str, early: float = 0.4) -> None:
        for cap, (a, b) in zip(self.narr["cap"], self.narr["spans"]):
            at = cap.find(phrase)
            if at >= 0:
                left = LEAD + a + (b - a) * at / max(len(cap), 1) - early - self.now()
                if left > 0:
                    self.hold(left)
                elif left < -0.6:
                    print(f"  chapter {self.n + 1}: {-left:.1f} s late for '{phrase}'", flush=True)
                return
        raise KeyError(phrase)


def c1_intent(s: Chapter, pid: str) -> None:
    p = s.page
    s.hold(0.4)
    s.soft("ring film", s.ring, p.locator("section[aria-label='How a project works']"), 1.4)
    s.at_text("press New project", 0.5)
    s.click(p.get_by_role("button", name="New project").or_(p.get_by_role("link", name="New project")).first)
    s.ready(p.get_by_text("What do you need?").first)
    s.at_text("Then you say", 0.2)
    s.type(p.locator("textarea").first, "A monthly report of holdings and cash in USD and SGD, for Raj and me.")
    s.at_text("North, our industry expert", 0.6)
    s.switch("daniel.foo", f"/centre/build/p/{pid}/intent", "Intent of work")
    q = s.page
    ask = q.get_by_text("Why does this matter now, who will read the result").first
    s.soft("scroll ask", s.scroll_to, ask, 160, 700)
    s.soft("ring ask", s.ring, ask.locator("xpath=.."), 2.2)
    s.at_text("writes the brief", 0.4)
    doc = q.get_by_text("Who reads the result and what they decide from it").first
    s.soft("ring doc", s.ring, doc.locator("xpath=.."), 2.0)
    s.soft("zoom doc", s.zoom, doc.locator("xpath=.."), 1.25, 1.8)
    s.at_text("The sponsor signs it", 0.5)
    s.soft("ring signed", s.ring, q.get_by_text("Daniel Foo signed it and sent it to Build").first, 2.0)


def offstage(s: Chapter, stage: str, reload_tab: str | None = None) -> None:
    """A step done between shots, never filmed: the film is paused while it runs (then the page is opened again on `reload_tab`)."""
    s.rec.pause()
    r = subprocess.run([sys.executable, str(ROOT / "tools/video/vid6_prep.py"), stage], capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, "SH_FILM_ENV": "vid6"})
    if r.returncode:
        raise RuntimeError(f"{stage}: {r.stderr[-300:]}")
    if stage != "plan1":
        s.page.reload()
        if reload_tab:
            s.page.get_by_role("button", name=reload_tab).click()
    s.rec.resume()


def card(loc):
    return loc.locator("xpath=ancestor::div[contains(@class,'b9v-card')][1]")


def c2_build(s: Chapter, pid: str) -> None:
    p = s.page
    s.hold(0.3)
    s.at_text("reads the signed brief", 0.5)
    s.soft("ring architect", s.ring, p.get_by_text("I read the signed intent and the process map").locator("xpath=.."), 2.4)
    s.at_text("asks only what is missing", 0.5)
    s.click(p.get_by_role("button", name="The few questions"))
    s.soft("ring questions", s.ring, p.get_by_text("Span has a proposed answer for each question.").first, 1.8)
    s.at_text("ready to accept", 0.9)
    s.click(p.get_by_role("button", name=re.compile("Accept all")))
    s.ready(p.get_by_text("Everything is answered."), 30)
    s.at_text("drafts the design pack", 0.5)
    s.click(p.get_by_role("button", name="The design pack"))
    s.click(p.get_by_role("button", name="Draft the design pack"))
    s.ready(p.get_by_text("Gold tables").first, 90)
    s.soft("ring gold", s.ring, p.get_by_text("Gold tables").first.locator("xpath=.."), 2.2)
    offstage(s, "slip", "The design pack")
    s.at_text("the tables", 0.2)
    s.soft("scroll def", s.scroll_to, p.get_by_text("Definitions").first, 120, 1100)
    s.soft("ring bench", s.ring, p.get_by_text("Benchmark check").first.locator("xpath=.."), 2.0)
    send = p.get_by_role("button", name=re.compile("Send to the head of data"))
    s.soft("scroll send", s.scroll_to, send, 380, 900)
    s.click(send)
    s.at_text("The head of data approves", 0.4)
    s.switch("anita.rao", f"/centre/build/p/{pid}/architecture", "What I already know")
    q = s.page
    q.get_by_role("button", name="The design pack").click()
    btn = q.get_by_role("button", name="Approve version 1")
    btn.wait_for(state="visible", timeout=30000)
    s.soft("scroll approve", s.scroll_to, btn, 380, 900)
    s.click(btn)
    s.mark("seal")
    s.ready(q.get_by_text("Approved by Anita Rao").first, 30)
    s.soft("ring approved", s.ring, q.get_by_text("Approved by Anita Rao").first, 2.0)
    offstage(s, "plan1")     # the plan is drawn from the pack and approved before the builder's page opens


def c3_check(s: Chapter, pid: str) -> None:
    p = s.page
    s.hold(0.3)
    run = p.get_by_role("heading", name="Run on a copy")
    s.soft("ring builder", s.ring, p.get_by_text("I took design pack version 1 as it was approved.").locator("xpath=.."), 1.8)
    s.at_text("runs it on a copy", 0.2)
    s.soft("scroll run", s.scroll_to, run, 110, 900)
    s.soft("ring run", s.ring, card(run), 2.0)
    s.at_text("checks the numbers", 0.6)
    ask = p.get_by_text("Do you have last month's report to check against?")
    s.soft("scroll ask", s.scroll_to, ask, 150, 900)
    s.soft("ring ask", s.ring, card(ask), 1.6)
    s.soft("point upload", s.point, p.get_by_text("Upload last month's report").first)
    s.mark("tick")
    p.locator("input[type=file]").set_input_files(str(DATA.parent / "September report as issued.csv"))
    s.ready(p.get_by_text("Unexplained", exact=True).first, 60)
    s.at_text("Two lines differ", 0.4)
    bad = p.get_by_text("Unexplained", exact=True).first
    s.soft("scroll bad", s.scroll_to, bad, 300, 900)
    s.soft("ring bad", s.ring, bad.locator("xpath=ancestor::tr[1]"), 2.0)
    s.soft("ring leg", s.ring, p.get_by_text("Unexplained", exact=True).last.locator("xpath=ancestor::tr[1]"), 1.6)
    s.at_text("hands the evidence back", 0.4)
    back = p.get_by_role("button", name="Send back to the architect")
    s.soft("scroll back", s.scroll_to, back, 380, 700)
    s.click(back)
    s.ready(p.get_by_text("With the architect.").first, 30)
    s.at_text("Version 2 is approved", 0.2)
    offstage(s, "v2")
    s.ready(p.get_by_text("Variance cleared").first, 90)
    s.soft("ring v2", s.ring, p.get_by_text("Pack version 2").first, 1.6)
    s.at_text("every figure matches", 0.5)
    s.soft("scroll clear", s.scroll_to, p.get_by_text("Variance cleared").first, 300, 900)
    s.soft("ring clear", s.ring, card(p.get_by_text("Variance cleared").first), 2.4)


def c4_design(s: Chapter, pid: str) -> None:
    p = s.page
    s.hold(0.3)
    go = p.get_by_role("button", name="Go live", exact=True)
    s.soft("scroll live", s.scroll_to, go, 380, 700)
    s.click(go)
    s.ready(p.get_by_text("Lumen proposes a starter dashboard").first, 60)
    s.at_text("Lumen proposes", 0.3)
    s.click(p.get_by_role("link", name="Lumen proposes a starter dashboard").first)
    s.ready(p.get_by_text("Lumen's starter dashboard").first, 60)
    s.click(p.get_by_role("button", name="Open", exact=True).or_(p.get_by_role("link", name="Open", exact=True)).first)
    s.ready(p.get_by_role("button", name="Accept as it is"), 60)
    s.soft("scroll starter", s.scroll_to, p.get_by_role("heading", name="Lumen's starter dashboard").last, 200, 900)
    s.soft("ring starter", s.ring, p.get_by_label("Lumen's starter dashboard"), 2.4)
    s.at_text("Accept it", 0.3)
    s.click(p.get_by_role("button", name="Accept as it is"))
    s.ready(p.get_by_text("You accepted the starter."), 30)
    s.at_text("Someone else approves", 0.6)
    send = p.get_by_role("button", name="Send for approval")
    s.soft("scroll send", s.scroll_to, send, 200, 700)
    s.click(send)
    s.ready(p.get_by_text("waiting for the head of data").first, 30)
    s.switch("daniel.foo", s.page.url.replace(BASE, ""), "Waiting for your approval")
    q = s.page
    btn = q.get_by_role("button", name="Approve", exact=True)
    s.soft("scroll approve", s.scroll_to, btn, 380, 700)
    s.click(btn)
    s.mark("seal")
    s.ready(q.get_by_text("Approved by").first, 30)
    s.soft("ring approved", s.ring, q.get_by_text("Approved by").first, 1.6)


def c5_deliver(s: Chapter, pid: str) -> None:
    p = s.page
    s.hold(0.2)
    for name, cue in (("Consume", "Consume"), ("Morning Note section", "the Morning Note"), ("Email digest", "email"),
                      ("Microsoft Teams channel", "Teams")):
        s.at_text(cue, 0.3)
        s.soft(f"ring {name}", s.ring, p.get_by_role("button", name=name, exact=True), 0.9)
    s.click(p.get_by_role("button", name="Morning Note section", exact=True))
    s.soft("ring approval line", s.ring, p.get_by_text("A draft is sent for approval to someone other than you.").first, 1.6)


# chapter: (who, start page, the text that shows it has loaded, what to do)
def plan(pid: str, new: str) -> list[tuple]:
    b = f"/centre/build/p/{new}"
    return [("daniel.foo", "/centre/build", "Running projects", c1_intent, pid),
            ("leo.park", f"{b}/architecture", "What I already know", c2_build, new),
            ("leo.park", f"{b}/pipelines", "Run on a copy", c3_check, new),
            ("leo.park", f"{b}/pipelines", "Go live", c4_design, new),
            ("leo.park", f"/centre/build/p/{pid}/delivery", "Add a channel", c5_deliver, pid)]


def up() -> bool:
    try:
        return urllib.request.urlopen(BASE + "/", timeout=3).status == 200
    except OSError:
        return False


def stop_server() -> None:
    """Stop whatever listens on port 8696, and nothing else."""
    ps = (f"Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(1.5)


def fresh_server() -> None:
    stop_server()
    subprocess.run([sys.executable, str(ROOT / "tools/make_test_env.py"), "vid6", "--seed"], check=True, cwd=ROOT)
    env = {**os.environ, "SH_FILM_ENV": "vid6"}
    prep = str(ROOT / "tools/video/vid6_prep.py")     # before the server holds the warehouse
    new = subprocess.run([sys.executable, prep, "start"], check=True, cwd=ROOT, env=env, capture_output=True, text=True).stdout.split()[-1]
    subprocess.run([sys.executable, prep, "report"], check=True, cwd=ROOT, env=env, capture_output=True)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "new_project.txt").write_text(new, encoding="utf-8")
    # the UI built from the current source (D:/Temp/vid7/dist, see film7_serve.py), not the older ui/dist
    subprocess.Popen([sys.executable, str(ROOT / "tools/video/film7_serve.py")], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env={**os.environ, "SH_SERVE_PORT": str(PORT), "SH_SERVE_DATA": str(DATA)})
    for _ in range(90):
        if up():
            return
        time.sleep(1)
    raise SystemExit("the recording server did not start")


def film(narr: dict) -> dict:
    from playwright.sync_api import sync_playwright
    new = (WORK / "new_project.txt").read_text(encoding="utf-8").strip()
    pid = next(p.name for p in (DATA / "evergreen" / "consume").glob("prj-*") if p.name != new)    # the seeded demo project
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--hide-scrollbars"])
        states: dict[str, dict] = {}

        def opener(who: str, path: str):
            states.setdefault(who, sign_in_state(pw, who))
            ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, storage_state=states[who],
                                      color_scheme="dark", reduced_motion="no-preference")
            ctx.add_init_script(record.INIT)
            pg = ctx.new_page()
            pg.goto(BASE + path)
            return pg

        for i, (who, start, ready, fn, arg) in enumerate(plan(pid, new)):
            page = opener(who, start)
            for tries in range(3):          # a page that has not drawn its first screen is opened again, off camera
                try:
                    page.get_by_text(ready).first.wait_for(state="visible", timeout=45000)
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
            rec = record.Recorder(WORK / f"frames{i}")
            rec.attach(page)
            rec.start()
            s = Chapter(i, page, rec, opener, narr)
            ok = True
            try:
                fn(s, arg)
            except Exception as e:  # noqa: BLE001 - a failed chapter is reported; what was filmed is kept
                ok = False
                rec.resume()
                print(f"chapter {i + 1}: FAILED ({type(e).__name__}: {str(e)[:400]})", flush=True)
                s.page.screenshot(path=str(WORK / f"chapter{i + 1}-failed.png"))
            left = s.end() - s.now()
            if left > 0:
                s.hold(left)
            secs = max(s.end(), s.now() + 0.4)
            rec.pause()
            clip = WORK / f"rec{i}.mp4"
            rec.write(secs, clip)
            for c in {s.page.context, page.context}:
                c.close()
            out[str(i)] = {"clip": str(clip), "seconds": round(secs, 2), "zooms": s.zooms, "marks": s.marks, "ok": ok, "missed": s.missed}
            print(f"chapter {i + 1}: {'ok' if ok else 'FAILED'}, {secs:.1f} s for {length(i):.1f}, missed {s.missed}", flush=True)
        browser.close()
    (WORK / "recordings.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


# ---- the cut ------------------------------------------------------------------------------------------------------------------

def cut(narr: dict, recs: dict) -> Path:
    segs, caps, labels = [], [], []
    n = int((END + 1) * sound.SR)
    vox, fx = np.zeros(n), np.zeros(n)
    for i, (t0, title, _) in enumerate(CHAPTERS):
        rec, d = recs[str(i)], length(i)
        speed = max(1.0, float(rec["seconds"]) / d)    # a long take plays a little faster so the next chapter starts on time
        if speed > 1.35:
            print(f"  chapter {i + 1} runs {speed:.2f}x; trim its actions", flush=True)
        dest = WORK / f"seg{i}.mp4"
        build.screen_segment(rec, d, None, True, i + 1 < len(CHAPTERS), dest, round(speed, 3))
        segs.append(dest)
        nr = narr[str(i)]
        for wav, cap, (a, b) in zip(nr["wavs"], nr["cap"], nr["spans"]):
            sound.place(vox, sound.read_wav(Path(wav)), t0 + LEAD + a)
            caps += [(*c, "") for c in build.sentence_cues(cap, t0 + LEAD + a, t0 + LEAD + b)]
        for kind, at in rec.get("marks", []):
            sound.place(fx, sound.cue(kind) * 0.7, t0 + at / speed)
        labels.append((t0, f"{i + 1} · {title}"))
    close = WORK / "seg-close.mp4"
    build.ff("-ss", f"{5.6 - CLOSE:.2f}", "-i", str(CARD), "-t", f"{CLOSE:.3f}",
             "-vf", f"fps={FPS},setsar=1,fade=t=in:st=0:d=0.3:color={build.NAVY}", *build.V, "-an", str(close))
    segs.append(close)
    lst = WORK / "segments.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    plain = WORK / "picture-plain.mp4"
    build.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(plain))
    # a poster frame first: the first frame is the mark and the line (a player's thumbnail), gone one frame later
    poster = OUT / f"{NAME}-poster.png"
    build.ff("-ss", "4.2", "-i", str(CARD), "-frames:v", "1", "-vf", "setsar=1", str(poster))
    picture = WORK / "picture.mp4"
    build.ff("-i", str(plain), "-i", str(poster), "-filter_complex", "[0][1]overlay=enable='lt(t,0.034)',format=yuv420p", *build.V, "-an", str(picture))
    total = build.length(picture)
    ass = WORK / "explainer.ass"
    build.write_captions(caps, OUT / f"{NAME}.srt", ass)
    # the chapter's name, top left under the product's bar, for its first three seconds
    ev = [f"Dialogue: 1,{build.stamp(a + 0.3, True)},{build.stamp(a + 3.3, True)},Cap,,0,0,0,,"
          f"{{\\an7\\pos(40,112)\\fs34\\fad(250,250)}}{t}" for a, t in labels]
    ass.write_text(ass.read_text(encoding="utf-8") + "\n".join(ev) + "\n", encoding="utf-8")
    sec = {"cold": 0.2, "reveal": 0.4, "pulse": (3.0, END - 4.0), "padonly": (END - CLOSE - 0.5, END + 1), "close": END - CLOSE}
    music = sound.duck(np.resize(sound.bed(n / sound.SR, sec), n), vox)
    raw = WORK / "mix.wav"
    sound.write_wav(raw, vox + music * 0.8 + fx)
    mix = WORK / "audio.wav"
    build.loudnorm(raw, mix)
    tmp = WORK / "explainer-full.mp4"
    build.finish(picture, mix, ass, tmp)
    if tmp.stat().st_size > 19.5e6:         # under 20 MB for the landing: two passes at the bitrate that fits
        kbps = int(18.5 * 8 * 1000 / total) - 160
        log = WORK / "2pass"
        common = ["-i", str(tmp), "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", str(log)]
        build.ff(*common, "-pass", "1", "-an", "-f", "mp4", "NUL")
        build.ff(*common, "-pass", "2", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(DEST))
    else:
        shutil.copyfile(tmp, DEST)
    return DEST


def stills() -> None:
    """A frame every 5 s, and one either side of each chapter start, for the review."""
    folder = WORK / "stills"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    build.ff("-i", str(DEST), "-vf", "fps=1/5,scale=1280:-2", str(folder / "every5-%02d.png"))
    for t0, _, _ in CHAPTERS[1:]:
        for at in (t0 - 0.4, t0 + 0.6):
            build.ff("-ss", f"{at:.2f}", "-i", str(DEST), "-frames:v", "1", "-vf", "scale=1280:-2", str(folder / f"edge-{at:05.1f}.png"))


def serve() -> list[Path]:
    """Where the app serves /static/explainer.mp4: Vite copies ui/public into ui/dist, which the server mounts at /."""
    out = []
    for d in (ROOT / "ui/public/static", ROOT / "ui/dist/static"):
        if d.parent.is_dir():
            d.mkdir(exist_ok=True)
            shutil.copyfile(DEST, d / "explainer.mp4")
            out.append(d / "explainer.mp4")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--keep-server", action="store_true")
    a = ap.parse_args(argv)
    narr = voice()
    if a.assemble_only:
        recs = json.loads((WORK / "recordings.json").read_text(encoding="utf-8"))
    else:
        try:
            fresh_server()
            recs = film(narr)
        finally:
            if not a.keep_server:
                stop_server()
    dest = cut(narr, recs)
    stills()
    print(f"{dest}: {build.length(dest):.2f} s, {dest.stat().st_size / 1e6:.1f} MB; served from {[str(p) for p in serve()]}", flush=True)


if __name__ == "__main__":
    main()
