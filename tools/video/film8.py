"""VID8, files to dashboard: a 90-second caption-only screen film for the client deck (no voice, no model calls).

    python tools/video/film8.py

The copy and the server are the caller's, so that nothing else is touched:
    python tools/seed_demo_boot.py --data-root D:/Temp/vid8-env      (with DATABASE_URL and REDIS_URL unset)
    python tools/serve_test.py --port 8550 --data-root D:/Temp/vid8-env
then, after the film, stop the server on 8550 and delete D:/Temp/vid8-env.

Reuses record.Recorder and record.Scene (pointer, rings, eased scrolling, push-ins), build's camera, navy dips and ffmpeg helpers,
cards.render and cards.tokens. Off camera, once: Leo uploads the administrator's positions file to the copy, reads it, accepts the
proposed mapping (its targets come from the rules) and loads it, so the fund names wait for approval on the intake screen.
Run ids stay on screen (the Runs shot needs them); machine ids are not blanked here.
Outputs in docs/video/out/: signal-harbor-files-to-dashboard.mp4, -share.mp4 (under 20 MB), -poster.png and a .srt.
"""
import html
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import cards  # noqa: E402
import record  # noqa: E402
from common import DSF, FPS, OUT, VH, VW  # noqa: E402

BASE = "http://127.0.0.1:8550"
SEED = Path("D:/Temp/vid8-env")
WORK = OUT / "film8"
CARDS = WORK / "cards"
NAME = "signal-harbor-files-to-dashboard"
HERO = OUT / f"{NAME}.mp4"
SHARE = OUT / f"{NAME}-share.mp4"
POSTER = OUT / f"{NAME}-poster.png"
SRT = OUT / f"{NAME}.srt"
UPLOAD = SEED / "evergreen" / "landing" / "administrator" / "administrator_positions.csv"
INIT = record.INIT.replace("v = v.replace(ID, '');", "")   # keep run ids on screen
assert INIT != record.INIT
FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&"
         "family=IBM+Plex+Mono:wght@500;600&display=swap")
TITLE_D = END_D = 6.0
CAP_IN, CAP_OUT = 0.6, 0.6   # a caption comes in and out this far inside its shot

CSS = """
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;background:var(--ds-ground);color:var(--ds-ink);font-family:'IBM Plex Sans',sans-serif;overflow:hidden}
.stage{position:relative;width:1920px;height:1080px;display:flex;flex-direction:column;justify-content:center;padding:0 170px;overflow:hidden}
.glow{position:absolute;inset:-200px;background:radial-gradient(900px 640px at 74% 24%,color-mix(in srgb,var(--ds-teal) 20%,transparent),transparent 70%);
  animation:drift var(--D) linear both}
@keyframes drift{from{transform:translate(0,0)}to{transform:translate(-60px,30px)}}
@keyframes up{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes wipe{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.a{opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) both}
.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:28px;letter-spacing:.16em;text-transform:uppercase;color:var(--ds-teal-bright);font-weight:600}
h1{position:relative;z-index:1;font-size:118px;line-height:1.06;font-weight:600;letter-spacing:-.02em;max-width:1500px}
.rule{width:150px;height:6px;border-radius:3px;background:var(--ds-teal-bright);transform-origin:left;animation:wipe .8s cubic-bezier(.6,0,.2,1) .4s both}
"""


def page(body: str, d: float) -> str:
    return (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{cards.tokens()}{CSS}</style>"
            f"<body style='--D:{d:.2f}s'><div class=stage><div class=glow></div>{body}</div></body>")


def title_card() -> str:
    return page('<div class="eyebrow a" style="animation-delay:.2s">Signal Harbor</div><div class=rule style="margin:36px 0 40px"></div>'
                '<h1 class=a style="animation-delay:.5s">From files to the figures the council reads</h1>', TITLE_D)


def end_card() -> str:
    return page('<div class="rule" style="margin-bottom:44px"></div>'
                '<h1 class=a style="animation-delay:.3s">Signal Harbor &middot; Every figure, explained.</h1>', END_D)


# ---- the screens: who signs in, where, what the page must show before the take starts --------------------------------------------

def pid_path(shot: dict, pid: str) -> str:
    return shot["path"].replace("{pid}", pid)


# each shot's action: the Scene does the pointer, the rings and the push-ins; a missed highlight is noted, never fatal

def s2_intake(s: record.Scene) -> None:
    p = s.page
    row = p.get_by_text("administrator_positions.csv", exact=True).first
    s.hold(0.5)
    s.soft("ring the file", s.ring, row, 1.6)
    s.hold(0.4)
    s.click(row)
    s.ready(p.get_by_text("Mapping", exact=True).first)
    s.hold(0.4)
    s.soft("zoom the mapping", s.zoom, p.locator("table").first, 1.12, 2.6, 30)
    s.hold(2.2)
    s.soft("ring the date format", s.ring, p.get_by_text("dates read as", exact=False).first, 2.0)
    s.hold(2.2)
    s.soft("scroll to the funds", s.scroll_to, p.get_by_role("button", name="Approve Cash").first, 260, 1300)
    s.hold(0.3)
    s.soft("ring approve", s.ring, p.get_by_role("button", name="Approve Cash").first, 2.4)
    s.hold(2.2)


def s3_architecture(s: record.Scene) -> None:
    p = s.page
    s.hold(0.6)
    s.soft("scroll to silver", s.scroll_to, p.get_by_text("Silver reused", exact=False).first, 140, 1400)
    s.hold(0.4)
    s.soft("ring silver reused", s.ring, p.get_by_text("Silver reused", exact=False).first, 2.4)
    s.hold(2.8)
    s.soft("scroll to gold", s.scroll_to, p.get_by_text("Gold tables", exact=False).first, 120, 1500)
    s.hold(0.4)
    s.soft("zoom gold", s.zoom, p.get_by_text("Gold tables", exact=False).first, 1.1, 2.6, 30)
    s.hold(3.0)


def s4_runs(s: record.Scene) -> None:
    p = s.page
    s.hold(0.5)
    s.soft("scroll to runs", s.scroll_to, p.get_by_text("Runs", exact=True).first, 60, 1300)
    s.hold(0.5)
    test_row = p.locator("tr").filter(has_text="TEST").filter(has_text="Pipeline").first
    prod_row = p.locator("tr").filter(has_text="PRODUCTION").filter(has_text="Pipeline").first
    s.soft("ring a test run", s.ring, test_row, 1.8)
    s.hold(0.4)
    s.click(test_row.locator("button").first)
    s.hold(0.6)
    s.soft("zoom test steps", s.zoom, p.get_by_label(re.compile("^Steps of")).first, 1.12, 2.8, 30)
    s.hold(3.0)
    s.soft("ring a production run", s.ring, prod_row, 1.8)
    s.hold(0.4)
    s.click(prod_row.locator("button").first)
    s.hold(1.6)


def s5_lineage(s: record.Scene) -> None:
    p = s.page
    s.hold(0.5)
    s.click(p.get_by_role("button", name="Lineage").first)
    s.hold(0.6)
    node = p.get_by_role("button", name=re.compile("^position_snapshots")).first
    s.click(node)
    s.hold(0.8)
    s.soft("ring the picked table", s.ring, node, 2.2)
    s.hold(1.0)
    s.soft("zoom the chain", s.zoom, node, 1.16, 3.0, 40)
    s.hold(3.4)


def s6_action(s: record.Scene) -> None:
    """Mei is an owner: she sees the cases, not the reconciliation group that carries 'Close as timing'. So the take shows her
    cash break and the reason Tally gives on its case."""
    p = s.page
    s.hold(0.6)
    s.soft("ring the cash break", s.ring, p.get_by_text("Cash differs", exact=False).first, 2.0)
    s.hold(0.8)
    links = p.locator("a", has_text="Ask Tally")
    idx = next((i for i in range(links.count()) if "0003" in (links.nth(i).get_attribute("href") or "")), 2)
    s.click(links.nth(idx))
    s.ready(p.get_by_text("What Tally found", exact=False).first)
    s.hold(0.5)
    s.soft("ring the timing reason", s.ring, p.get_by_text("a timing difference that clears", exact=False).first, 2.6)
    s.hold(0.8)
    s.soft("zoom the reason", s.zoom, p.get_by_text("a timing difference that clears", exact=False).first, 1.2, 3.0, 40)
    s.hold(3.4)


SHOTS = [
    dict(n=2, who="leo.park", path="/centre/data/intake", ready="Data intake", d=15.5, fn=s2_intake, pos="bottom:64px",
         cap="The data engineer checks how each column lands before loading."),
    dict(n=3, who="anita.rao", path="/centre/build/p/{pid}/architecture", ready="Silver reused", d=15.5, fn=s3_architecture,
         pos="bottom:64px", cap="Span reuses the office's data model first; new tables only with a reason, approved by the head of data."),
    dict(n=4, who="leo.park", path="/centre/operations", ready="Runs", d=16.0, fn=s4_runs, pos="bottom:64px",
         cap="Every run has an ID, test or production, with what each step loaded and checked."),
    dict(n=5, who="anita.rao", path="/centre/map?tab=model", ready="Lineage", d=15.5, fn=s5_lineage, pos="bottom:64px",
         cap="Every figure traces back: file, raw, clean, ready-made, dashboard."),
    dict(n=6, who="mei.chen", path="/centre/action", ready="Cases to handle", d=15.5, fn=s6_action, pos="bottom:64px",
         cap="What needs a person lands in Action, with the reason."),
]


# ---- the copy: sign in off camera, the intake file, the project id ------------------------------------------------------------

def password(email: str) -> str:
    """The seeded password for one account. Held in memory only: never printed, logged or written."""
    for line in (SEED / "_control" / "seed_credentials.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == email and not line.startswith("#"):
            return p[1]
    raise SystemExit(f"no seeded account {email}")


def sign_in(pw, who: str) -> dict:
    """Cookies only, from a throwaway context; the password is typed off camera and not kept."""
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


def prep(browser, state: dict) -> None:
    """Off camera, once: upload the administrator's file, read it, accept the proposed mapping and load it. Idempotent."""
    ctx = browser.new_context(viewport={"width": VW, "height": VH}, storage_state=state)
    pg = ctx.new_page()
    pg.goto(BASE + "/centre/data/intake")
    pg.get_by_text("Data intake", exact=True).first.wait_for(timeout=60000)
    row = pg.get_by_text("administrator_positions.csv", exact=True)
    if row.count() == 0:
        pg.locator("input[type=file]").first.set_input_files(str(UPLOAD))
        row.first.wait_for(timeout=30000)
    row.first.click()
    pg.wait_for_url(re.compile(r"/centre/data/intake/.+"), timeout=30000)
    # the file page does not refresh its detail after a step, so reload before each look at the next button
    for _ in range(14):
        pg.reload()
        pg.wait_for_timeout(1200)
        if pg.get_by_role("button", name="Approve Cash", exact=True).count():
            break
        for name in ("Read this file", "Propose a mapping", "Accept", "Load this file"):
            b = pg.get_by_role("button", name=name, exact=True)
            if b.count():
                b.first.click()
                pg.wait_for_timeout(2500)
                break
    else:
        raise SystemExit("prep: the intake file did not reach 'Approve Cash'")
    print("prep: intake file read, mapping accepted, loaded; fund names wait for approval", flush=True)
    ctx.close()


def uc4_project_id(browser, state: dict) -> str:
    ctx = browser.new_context(viewport={"width": VW, "height": VH}, storage_state=state)
    pg = ctx.new_page()
    pg.goto(BASE + "/centre/build")
    pg.get_by_text("Monthly performance against the office blend", exact=False).first.wait_for(timeout=60000)
    href = pg.evaluate("""() => { const a = [...document.querySelectorAll('a')].find(x => x.getAttribute('href') &&
        x.getAttribute('href').includes('/centre/build/p/') && x.textContent.includes('Monthly performance against the office blend'));
        return a ? a.getAttribute('href') : null }""")
    ctx.close()
    m = re.search(r"/centre/build/p/(prj-[0-9a-f]+)", href or "")
    if not m:
        raise SystemExit("the UC4 benchmark project was not found on the build page")
    return m[1]


# ---- recording -------------------------------------------------------------------------------------------------------------------

def record_shot(browser, states: dict, shot: dict, pid: str) -> dict:
    n, who, clip = shot["n"], shot["who"], WORK / f"rec{shot['n']}.mp4"
    opened = []

    def opener(w: str, path: str):
        ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, storage_state=states[w],
                                  color_scheme="dark", reduced_motion="no-preference")
        ctx.add_init_script(INIT)
        opened.append(ctx)
        pg = ctx.new_page()
        pg.goto(BASE + path)
        return pg

    page = opener(who, pid_path(shot, pid))
    page.get_by_text(shot["ready"], exact=False).first.wait_for(state="visible", timeout=150000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001 - a page that polls never goes idle
        pass
    page.evaluate("window.__sh.move(1100, 600, 10)")
    page.wait_for_timeout(700)
    rec = record.Recorder(WORK / f"frames{n}")
    rec.attach(page)
    rec.start()
    page.evaluate("window.__sh.nudge()")
    s = record.Scene(n, page, rec, shot["d"], opener)
    try:
        shot["fn"](s)
    except Exception as e:  # noqa: BLE001 - what was filmed so far is kept
        rec.resume()
        print(f"shot {n}: FAILED ({type(e).__name__}: {str(e)[:300]})", flush=True)
        page.screenshot(path=str(WORK / f"shot{n}-failed.png"))
    left = shot["d"] - s.now()
    if left > 0:
        s.hold(left)
    elif left < -0.3:
        print(f"shot {n}: {-left:.1f} s over its length", flush=True)
    rec.pause()
    rec.write(shot["d"], clip)
    page.screenshot(path=str(WORK / f"shot{n}-end.png"))
    for c in opened:
        c.close()
    print(f"shot {n}: {shot['d']:.1f} s, {len(rec.frames)} frames, {len(s.zooms)} push-ins, missed {s.missed}", flush=True)
    return {"n": n, "clip": str(clip), "zooms": s.zooms, "d": shot["d"], "missed": s.missed}


# ---- the cut ---------------------------------------------------------------------------------------------------------------------

def shot_segment(clip: Path, zooms: list, d: float, dest: Path) -> None:
    z, x, y = build.camera(zooms, d)
    vf = (f"[0:v]tpad=stop_mode=clone:stop_duration=2,trim=duration={d:.3f},setpts=PTS-STARTPTS,scale=3840:2160:flags=lanczos,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s=1920x1080:fps={FPS},setsar=1")
    vf = build.dips(vf, d, True, True) + "[v0]"
    build.ff("-i", str(clip), "-filter_complex", vf, "-map", "[v0]", *build.V, "-t", f"{d:.3f}", "-an", str(dest))


def caption_png(text: str, pos: str, dest: Path, browser) -> None:
    body = (f"<div class=cap>{html.escape(text)}</div>")
    doc = (f"<!doctype html><meta charset=utf-8><link href='{FONTS}' rel=stylesheet><style>{cards.tokens()}"
           "html,body{margin:0;width:1920px;height:1080px;background:transparent;overflow:hidden}"
           f".cap{{position:absolute;left:50%;transform:translateX(-50%);{pos};max-width:1480px;background:rgba(15,27,45,.9);"
           "border-left:8px solid var(--ds-teal-bright);border-radius:10px;padding:22px 44px 22px 36px;color:#F6F4EE;"
           "font:500 42px/1.3 'IBM Plex Sans',sans-serif;box-shadow:0 10px 34px rgba(0,0,0,.35)}"
           f"</style><body>{body}</body>")
    pg = browser.new_page(viewport={"width": 1920, "height": 1080})
    pg.set_content(doc)
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(400)
    pg.screenshot(path=str(dest), omit_background=True)
    pg.close()


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cut(recs: list[dict], browser) -> None:
    lst_parts = [("title", CARDS / "title.mp4", TITLE_D)]
    for r in recs:
        lst_parts.append((f"shot{r['n']}", WORK / f"seg{r['n']}.mp4", r["d"]))
    lst_parts.append(("end", CARDS / "end.mp4", END_D))
    seg_list = WORK / "cut-segments.txt"
    total = 0.0
    caps = []
    start_of = {}
    for name, path, d in lst_parts:
        start_of[name] = total
        total += d
    for shot in SHOTS:
        a = start_of[f"shot{shot['n']}"]
        caps.append((a + CAP_IN, a + shot["d"] - CAP_OUT, shot["cap"], shot["pos"], shot["n"]))
    seg_list.write_text("".join(f"file '{p.as_posix()}'\n" for _, p, _ in lst_parts), encoding="utf-8")
    cap_pngs = []
    for a, b, text, pos, n in caps:
        png = WORK / f"caption{n}.png"
        caption_png(text, pos, png, browser)
        cap_pngs.append((a, b, png))
    inputs, filt, cur = [], [f"[0:v]fps={FPS},format=yuv420p[v0]"], "v0"
    for i, (a, b, png) in enumerate(cap_pngs, start=1):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", str(png)]
        filt.append(f"[{i}:v]format=rgba,fade=t=in:st={a:.3f}:d=0.4:alpha=1,fade=t=out:st={b - 0.4:.3f}:d=0.4:alpha=1[c{i}]")
        filt.append(f"[{cur}][c{i}]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[o{i}]")
        cur = f"o{i}"
    filt.append(f"[{cur}]format=yuv420p[out]")
    build.ff("-f", "concat", "-safe", "0", "-i", seg_list.name, *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
             "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-an",
             "-movflags", "+faststart", str(HERO), cwd=WORK)
    SRT.write_text("".join(f"{i + 1}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n\n" for i, (a, b, t, _, _) in enumerate(caps)), encoding="utf-8")
    # share copy: two passes to about 17 MB (no audio track), well under 20 MB
    kbps = int(17 * 8 * 1024 / total) - 40
    log = (WORK / "share2pass").as_posix()
    common = ["-i", str(HERO), "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p", "-passlogfile", log]
    build.ff(*common, "-pass", "1", "-an", "-f", "mp4", "NUL")
    build.ff(*common, "-pass", "2", "-an", "-movflags", "+faststart", str(SHARE))
    build.ff("-ss", "4.0", "-i", str(HERO), "-frames:v", "1", str(POSTER))
    print(f"cut: {total:.1f} s, hero {HERO.stat().st_size / 1e6:.1f} MB, share {SHARE.stat().st_size / 1e6:.1f} MB", flush=True)
    (WORK / "film8.json").write_text(json.dumps({"total": total, "shots": recs}, indent=1), encoding="utf-8")


def main() -> None:
    import urllib.request
    try:
        urllib.request.urlopen(BASE + "/login", timeout=5)
    except OSError:
        raise SystemExit("the test server on port 8550 is not running (see the docstring)")
    WORK.mkdir(parents=True, exist_ok=True)
    CARDS.mkdir(parents=True, exist_ok=True)
    cards.render(items={"title": (title_card(), TITLE_D), "end": (end_card(), END_D)}, folder=CARDS)   # its own browser: before ours
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--hide-scrollbars"])
        states = {w: sign_in(pw, w) for w in ("leo.park", "anita.rao", "mei.chen")}
        prep(browser, states["leo.park"])
        pid = uc4_project_id(browser, states["anita.rao"])
        print("UC4 benchmark project found", flush=True)
        recs = []
        for shot in SHOTS:
            r = record_shot(browser, states, shot, pid)
            shot_segment(Path(r["clip"]), r["zooms"], r["d"], WORK / f"seg{r['n']}.mp4")
            recs.append(r)
        cut(recs, browser)
        browser.close()


if __name__ == "__main__":
    main()
