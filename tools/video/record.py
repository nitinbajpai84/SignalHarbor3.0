"""Record the product scenes of the launch film: Chromium at 1440x810 CSS px drawn at 1920x1080 device px, dark theme.

    python tools/video/record.py                 # every screen scene; agent scenes only with --agents
    python tools/video/record.py 4 7             # only scenes 4 and 7
    python tools/video/record.py --agents        # also the agent scenes (Real use, paid; each take is recorded ONCE)

Needs the recording server on port 8695 on a fresh copy of the demo data (build.py --film starts it) and narration.json
(each action waits for the sentence it belongs to). How it films:
  - frames come from the browser's own screencast at device resolution, saved with their time, laid out at 30 fps;
  - loading is never filmed: the capture pauses while a page or an agent reply loads and resumes on the finished screen;
  - an eased pointer with a soft ring and a click ripple; typing at a human pace; eased scrolling;
  - the teal highlight ring (`ring`) draws round the element the voice names, one at a time;
  - machine ids are blanked, scrollbars hidden, model and vendor names never shown;
  - `zoom()` marks a slow push-in onto the figure being said; build.py renders it; clicks, agent replies, the approval
    and the new tile are marked for the sound design.
Agent scenes run in Real use (switched by the sponsor through POST /api/v1/router/mode) and go back to Testing after;
OpenRouter spend before and after each take is logged in docs/video/COST.md. A take that exists is never recorded again.
Writes docs/video/out/film/recordings.json.
"""
import os
import base64
import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from common import BASE, DATA, DSF, FPS, LEAD, VH, VW, WORK, phrase_time, scenes, sign_in_state  # noqa: E402

REC = WORK / "recordings.json"
TAIL = 0.2

INIT = r"""
try { localStorage.setItem('sh_theme', 'dark'); } catch (e) {}
(() => {
  const css = document.createElement('style');
  css.textContent = `html,body{background:#0F1B2D}
  ::-webkit-scrollbar{width:0!important;height:0!important;display:none} *{scrollbar-width:none!important}
  #__cur{position:fixed;z-index:2147483647;left:0;top:0;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;pointer-events:none;
    background:rgba(95,194,194,.18);border:2px solid rgba(246,244,238,.92);box-shadow:0 0 0 1px rgba(0,0,0,.35),0 6px 18px rgba(0,0,0,.45);
    transform:translate(-200px,-200px);transition:width .12s,height .12s,margin .12s}
  #__cur::after{content:'';position:absolute;left:50%;top:50%;width:5px;height:5px;margin:-2.5px 0 0 -2.5px;border-radius:50%;background:#F6F4EE}
  #__cur.down{width:22px;height:22px;margin:-11px 0 0 -11px}
  .__rip{position:fixed;z-index:2147483646;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;border:3px solid #5FC2C2;pointer-events:none;
    animation:__rip .6s ease-out forwards}
  @keyframes __rip{from{transform:scale(.6);opacity:.95}to{transform:scale(2.6);opacity:0}}
  #__ring{position:fixed;z-index:2147483645;pointer-events:none;border:2px solid #5FC2C2;border-radius:12px;
    box-shadow:0 0 0 4px rgba(95,194,194,.16),0 0 26px 2px rgba(95,194,194,.30);opacity:0;transform:scale(1.06);
    transition:opacity .3s ease-out,transform .3s cubic-bezier(.2,.7,.2,1)}
  #__ring.on{opacity:1;transform:scale(1)}`;
  const onRoot = fn => { if (document.documentElement) fn(); else new MutationObserver((_, o) => { if (document.documentElement) { o.disconnect(); fn(); } }).observe(document, { childList: true }); };
  onRoot(() => document.documentElement.appendChild(css));
  let X = -200, Y = -200, ringEl = null, ringTimer = 0;
  const cur = () => { let c = document.getElementById('__cur'); if (!c && document.body) { c = document.createElement('div'); c.id = '__cur'; document.body.appendChild(c); c.style.transform = `translate(${X}px,${Y}px)`; } return c; };
  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const scroller = el => { for (let p = el && el.parentElement; p && p !== document.body; p = p.parentElement) { const s = getComputedStyle(p); if (/(auto|scroll)/.test(s.overflowY) && p.scrollHeight > p.clientHeight + 4) return p; } return document.scrollingElement; };
  window.__sh = {
    move(x, y, ms) { return new Promise(res => { const c = cur(); const x0 = X, y0 = Y, t0 = performance.now();
      const dx = x - x0, dy = y - y0, bend = Math.min(Math.hypot(dx, dy) * .08, 60);
      const step = now => { const k = Math.min((now - t0) / ms, 1), e = ease(k), arc = Math.sin(Math.PI * e) * bend;
        X = x0 + dx * e - dy / (Math.hypot(dx, dy) || 1) * arc; Y = y0 + dy * e + dx / (Math.hypot(dx, dy) || 1) * arc;
        if (c) c.style.transform = `translate(${X}px,${Y}px)`; if (k < 1) requestAnimationFrame(step); else res(); };
      requestAnimationFrame(step); }); },
    at() { return [X, Y]; },
    press(on) { const c = cur(); if (c) c.classList.toggle('down', on); },
    ripple(x, y) { const r = document.createElement('div'); r.className = '__rip'; r.style.left = x + 'px'; r.style.top = y + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 700); },
    ring(el, ms) {
      if (ringEl) { ringEl.remove(); ringEl = null; }
      clearTimeout(ringTimer);
      const r = document.createElement('div'); r.id = '__ring'; document.body.appendChild(r); ringEl = r;
      const place = () => { if (ringEl !== r) return; const b = el.getBoundingClientRect();
        r.style.left = (b.left - 7) + 'px'; r.style.top = (b.top - 6) + 'px'; r.style.width = (b.width + 14) + 'px'; r.style.height = (b.height + 12) + 'px';
        requestAnimationFrame(place); };
      place(); requestAnimationFrame(() => r.classList.add('on'));
      ringTimer = setTimeout(() => { r.classList.remove('on'); setTimeout(() => { r.remove(); if (ringEl === r) ringEl = null; }, 320); }, ms);
    },
    scroll(el, margin, ms) { return new Promise(res => { const s = scroller(el), doc = s === document.scrollingElement;
      const top = doc ? 0 : s.getBoundingClientRect().top, from = s.scrollTop;
      const to = Math.max(0, Math.min(from + el.getBoundingClientRect().top - top - margin, s.scrollHeight - s.clientHeight)), t0 = performance.now();
      const step = now => { const k = Math.min((now - t0) / ms, 1); s.scrollTop = from + (to - from) * ease(k); if (k < 1) requestAnimationFrame(step); else res(); };
      requestAnimationFrame(step); }); },
    by(dy, ms) { const s = document.scrollingElement; const from = s.scrollTop, t0 = performance.now(); return new Promise(res => {
      const step = now => { const k = Math.min((now - t0) / ms, 1); s.scrollTop = from + dy * ease(k); if (k < 1) requestAnimationFrame(step); else res(); };
      requestAnimationFrame(step); }); },
    nudge() { const c = cur(); if (c) { c.style.opacity = c.style.opacity === '0.999' ? '1' : '0.999'; } },
  };
  const ID = /\b(?:prj|ini|dash|doc|run|rv|sess|tile|ver|ses)-[0-9a-f]{6,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/g;
  const VENDOR = /\b(?:anthropic|openai|google|meta-llama|mistralai|x-ai|qwen|deepseek)\/[\w.:\-]+|\b(?:claude|gpt-[\w.\-]+|gemini[\w.\-]*|openrouter|sonnet|haiku|opus|llama[\w.\-]*|mistral)\b/gi;
  const QUIET = /^(Voice is not available right now; keep typing\.|Testing models \(free tier\)|Real-use models|North is reading only what you add\.|Voice runs on a development service: synthetic data only\.)$/;
  const clean = () => {
    if (!document.body) return;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      let v = n.nodeValue, o = v;
      v = v.replace(ID, ''); ID.lastIndex = 0;
      v = v.replace(VENDOR, 'model'); VENDOR.lastIndex = 0;
      v = v.replace(' (rules only)', '');
      if (v !== o) n.nodeValue = v;
      if (QUIET.test(v.trim()) && n.parentElement) n.parentElement.style.visibility = 'hidden';
    }
    document.querySelectorAll('li').forEach(li => { if (/,\s*error:/i.test(li.textContent.slice(0, 160))) li.style.display = 'none'; });
  };
  setInterval(clean, 100);
  document.addEventListener('DOMContentLoaded', clean);
})();
"""


class Recorder:
    """The browser's screencast, frame by frame, with pauses cut out. Times are 'film time': wall time minus paused time."""

    def __init__(self, folder: Path):
        self.dir = folder
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        self.frames: list[tuple[float, str]] = []
        self.t0 = 0.0
        self.paused_at: float | None = None
        self.paused = 0.0
        self.cdp = None

    def film(self, wall: float) -> float:
        return wall - self.t0 - self.paused

    def attach(self, page: Page) -> None:
        if self.cdp:
            try:
                self.cdp.send("Page.stopScreencast")
                self.cdp.detach()
            except Exception:  # noqa: BLE001 - the old page may be gone already
                pass
        cdp = page.context.new_cdp_session(page)
        self.cdp = cdp

        def frame(ev: dict) -> None:
            try:
                cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:  # noqa: BLE001 - closing
                return
            if self.paused_at is not None or not self.t0:
                return
            t = self.film(time.time())
            f = self.dir / f"{len(self.frames):06d}.jpg"
            f.write_bytes(base64.b64decode(ev["data"]))
            self.frames.append((t, f.name))

        cdp.on("Page.screencastFrame", frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "everyNthFrame": 1})

    def start(self) -> None:
        self.t0 = time.time()

    def pause(self) -> None:
        if self.paused_at is None:
            self.paused_at = time.time()

    def resume(self) -> None:
        if self.paused_at is not None:
            self.paused += time.time() - self.paused_at
            self.paused_at = None

    def now(self) -> float:
        return self.film(self.paused_at or time.time())

    def write(self, end: float, dest: Path) -> float:
        """The frames as a 30 fps clip of exactly `end` seconds (the last frame held)."""
        fr = [(max(t, 0.0), n) for t, n in self.frames if t < end]
        if not fr:
            raise RuntimeError("no frames were captured")
        lines = []
        for i, (t, n) in enumerate(fr):
            nxt = fr[i + 1][0] if i + 1 < len(fr) else end
            lines += [f"file '{n}'", f"duration {max(nxt - t, 0.001):.4f}"]
        lines.append(f"file '{fr[-1][1]}'")
        (self.dir / "frames.txt").write_text("\n".join(lines), encoding="utf-8")
        first = fr[0][0]
        vf = f"scale=1920:1080:flags=lanczos,tpad=start_duration={first:.3f}:start_mode=clone,fps={FPS},format=yuv420p"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "frames.txt", "-vf", vf,
                            "-t", f"{end:.3f}", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(dest)],
                           cwd=self.dir, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("ffmpeg: " + r.stderr[-800:])
        return end


class Scene:
    """One scene: a page, the recorder and a clock that follows the narration."""

    def __init__(self, n: int, page: Page, rec: Recorder, seconds: float, opener):
        self.n, self.page, self.rec, self.T, self.open = n, page, rec, seconds, opener
        self.zooms: list[dict] = []
        self.marks: list[list] = []     # [kind, film time] for the sound design: tick, chime, seal, whoosh
        self.missed: list[str] = []

    # -- the clock
    def now(self) -> float:
        return self.rec.now()

    def hold(self, s: float) -> None:
        if s > 0:
            self.page.wait_for_timeout(int(s * 1000))

    def at_text(self, phrase: str, early: float = 0.4) -> None:
        """Wait until `early` seconds before the narration says `phrase`."""
        left = LEAD + phrase_time(self.n, phrase) - early - self.now()
        if left > 0:
            self.hold(left)
        elif left < -0.6:
            print(f"  scene {self.n}: {-left:.1f} s late for '{phrase}'", flush=True)

    def end(self) -> float:
        return LEAD + self.T + TAIL

    def mark(self, kind: str) -> None:
        self.marks.append([kind, round(self.now(), 3)])

    def soft(self, what: str, fn, *a, **k):
        """Do one camera move or highlight; if the element is not there, note it and carry on (the take is never lost)."""
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001 - a missing highlight must not stop a paid take
            self.missed.append(f"{what}: {type(e).__name__}")
            print(f"  scene {self.n}: skipped {what} ({type(e).__name__}: {str(e)[:120]})", flush=True)
            return None

    # -- loading, never filmed
    def ready(self, loc, timeout: float = 60) -> None:
        """Pause the film until `loc` is on screen and the page has settled, then resume on the finished screen."""
        self.rec.pause()
        loc.first.wait_for(state="visible", timeout=timeout * 1000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:  # noqa: BLE001 - a page that polls never goes idle
            pass
        self.hold(0.6)
        self.rec.resume()
        self.page.evaluate("window.__sh && window.__sh.nudge()")

    def switch(self, who: str, path: str, ready: str) -> None:
        """Cut to another person's screen (signed in off camera)."""
        self.rec.pause()
        self.page = self.open(who, path)
        self.rec.attach(self.page)
        self.ready(self.page.get_by_text(ready))

    # -- the pointer
    def _box(self, loc) -> dict:
        loc.first.scroll_into_view_if_needed(timeout=2500)
        return loc.first.bounding_box()

    def move(self, x: float, y: float, ms: int | None = None) -> None:
        cx, cy = self.page.evaluate("window.__sh.at()")
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        ms = ms or int(min(max(420 + d * 0.6, 500), 1200))
        self.page.evaluate("([x, y, ms]) => window.__sh.move(x, y, ms)", [x, y, ms])
        self.page.mouse.move(x, y)

    def point(self, loc, dx: float | None = None) -> tuple[float, float]:
        b = self._box(loc)
        x = b["x"] + (dx if dx is not None else min(b["width"] / 2, 90))
        y = b["y"] + b["height"] / 2
        self.move(x, y)
        return x, y

    def click(self, loc, pause: float = 0.18) -> None:
        x, y = self.point(loc)
        self.hold(pause)
        self.page.evaluate("([x, y]) => { window.__sh.press(true); window.__sh.ripple(x, y); }", [x, y])
        self.mark("tick")
        self.page.mouse.down()
        self.hold(0.08)
        self.page.mouse.up()
        self.page.evaluate("window.__sh.press(false)")
        self.hold(0.25)

    def type(self, loc, text: str) -> None:
        self.click(loc)
        for ch in text:
            self.page.keyboard.type(ch)
            self.page.wait_for_timeout(int(random.uniform(12, 40) if ch != " " else random.uniform(30, 70)))
        self.hold(0.3)

    def scroll_to(self, loc, margin: float = 120, ms: int = 1200) -> None:
        loc.first.wait_for(state="attached", timeout=2500)
        loc.first.evaluate("(e, [m, ms]) => window.__sh.scroll(e, m, ms)", [margin, ms])
        self.hold(0.12)

    def ring(self, loc, secs: float = 2.4) -> None:
        loc.first.wait_for(state="visible", timeout=2500)
        loc.first.evaluate("(e, ms) => window.__sh.ring(e, ms)", int(secs * 1000))

    # -- the camera
    def zoom(self, loc, z: float = 1.3, hold: float = 2.5, pad: float = 40) -> None:
        """A slow push-in of `z` onto `loc` (rendered by build.py): in over 1.1 s, held, out over 0.9 s. Does not wait.
        An element wider or taller than the zoomed frame is framed from its top-left corner, where its text starts."""
        b = self._box(loc)
        x, y, w, h = b["x"] * DSF, b["y"] * DSF, b["width"] * DSF, b["height"] * DSF
        vw, vh = 1920 / z, 1080 / z
        cx = x + w / 2 if w + 2 * pad <= vw else x - pad + vw / 2
        cy = y + h / 2 if h + 2 * pad <= vh else y - pad + vh / 2
        self.zooms.append({"t": round(self.now(), 3), "cx": round(cx, 1), "cy": round(cy, 1), "z": z, "in": 1.1, "hold": hold, "out": 0.9})


def card_of(p: Page, text: str):
    """The smallest block that holds `text` and its own 'Where is this from?' link."""
    return p.locator("div").filter(has_text=text).filter(has_text="Where is this from?").last


# ---- the scenes (numbers and cue phrases follow docs/video/SCRIPT.md) ----------------------------------------------------------

def s4_today(s: Scene) -> None:
    p = s.page
    s.hold(0.5)
    s.at_text("the revised fund", 0.5)
    s.soft("ring revised", s.ring, p.get_by_text("Investigate the 180,000 USD"), 1.6)
    s.soft("point revised", s.point, p.get_by_text("Investigate the 180,000 USD"))
    s.at_text("a trade the administrator", 0.4)
    s.soft("ring trade", s.ring, p.get_by_text("Trade not matched · Harborview"), 1.8)
    s.soft("point trade", s.point, p.get_by_text("Trade not matched · Harborview"))
    s.at_text("and a cash break", 0.5)
    s.soft("scroll cash", s.scroll_to, p.get_by_text("Cash differs · Entity B"), 330, 900)
    s.soft("ring cash", s.ring, p.get_by_text("Cash differs · Entity B"), 2.4)
    s.soft("zoom cash", s.zoom, p.get_by_text("Cash differs · Entity B").locator("xpath=.."), 1.25, 1.6)
    s.soft("point cash", s.point, p.get_by_text("Cash differs · Entity B"))


def s5_tally(s: Scene) -> None:
    """AGENT (Tally, Real use): the case opens and Tally writes its panel; the wait is cut, the reply is untouched."""
    p = s.page
    s.hold(0.3)
    card = p.locator("xpath=//*[contains(text(),'Cash differs · Entity B')]/ancestor::*[.//a[contains(.,'Open case')] or .//button[contains(.,'Open case')]][1]")
    s.click(card.get_by_text("Open case").first)
    s.ready(p.get_by_text("What Tally found"), 150)
    s.mark("chime")
    s.at_text("disagree by", 0.6)
    s.soft("ring difference", s.ring, p.get_by_role("heading").filter(has_text="12,400"), 2.2)
    s.at_text("Tally has already read", 0.3)
    s.soft("scroll tally", s.scroll_to, p.get_by_role("heading", name="Tally, the data analyst"), 30, 1100)
    s.soft("ring tally", s.ring, p.get_by_role("heading", name="Tally, the data analyst").locator("xpath=.."), 2.0)
    s.at_text("One wire", 0.6)
    wire = p.locator("li, p").filter(has_text="WIRE-20261008-B01")
    s.soft("scroll wire", s.scroll_to, wire, 300, 900)
    s.soft("zoom wire", s.zoom, wire, 1.35, 4.2)
    s.soft("ring wire", s.ring, wire, 3.6)
    s.at_text("A timing difference", 0.4)
    chips = p.locator("li").filter(has_text="WIRE-20261008-B01").locator("button, a")
    s.soft("ring chip 1", s.ring, chips.nth(0), 1.4)
    s.soft("point chip 1", s.point, chips.nth(0))
    s.hold(1.2)
    s.soft("ring chip 2", s.ring, chips.nth(1), 1.6)
    s.soft("point chip 2", s.point, chips.nth(1))


def s6_trail(s: Scene) -> None:
    p = s.page
    s.hold(0.3)
    btn = p.get_by_role("button", name="Where is this from?").last
    s.soft("scroll button", s.scroll_to, btn, 420, 1100)
    s.at_text("Where is this from?", 0.5)
    s.click(btn)
    s.ready(p.get_by_text("1. Source").first, 30)
    s.soft("scroll steps", s.scroll_to, p.get_by_text("1. Source").first, 150, 900)
    for step, cue in (("1. Source", "Source, file"), ("2. File", "file, who"), ("3. Read", "who read it"),
                      ("4. Checked", "who checked it"), ("6. Shown", "where it is used")):
        s.at_text(cue, 0.3)
        s.soft(f"ring {step}", s.ring, p.get_by_text(step, exact=True).locator("xpath=.."), 1.3)


def s7_numbers(s: Scene) -> None:
    p = s.page
    s.hold(0.4)
    s.soft("ring key numbers", s.ring, p.get_by_role("heading").filter(has_text="Key numbers"), 1.8)
    s.at_text("The report issued", 0.5)
    known = card_of(p, "Known now against the issued")
    s.soft("zoom known", s.zoom, p.get_by_text("Known now against the issued").first.locator("xpath=.."), 1.45, 4.6)
    s.hold(0.6)
    s.soft("ring issued", s.ring, p.get_by_text("Issued USD 57,600,000"), 1.5)
    s.at_text("USD 57.78 million", 0.4)
    s.soft("ring known", s.ring, p.get_by_text("USD 57.78M"), 1.5)
    s.at_text("with the revised fund", 0.3)
    s.soft("ring revised", s.ring, known.get_by_text("Revised", exact=True), 1.5)
    s.at_text("The liquid book", 0.5)
    ret = card_of(p, "Return for Sep 2026")
    s.soft("zoom return", s.zoom, p.get_by_text("Return for Sep 2026").first.locator("xpath=.."), 1.5, 3.4)
    s.hold(0.9)
    s.soft("ring benchmark", s.ring, p.get_by_text("Benchmark 2.71%, +1.46 points"), 1.6)
    s.at_text("Certified", 0.3)
    s.soft("ring certified", s.ring, ret.get_by_text("Certified", exact=True), 1.6)


def s8_dashboards(s: Scene) -> None:
    p = s.page
    s.hold(0.3)
    head = p.get_by_role("heading", name="Department and project reports")
    s.soft("scroll reports", s.scroll_to, head, 160, 1300)
    s.soft("ring reports", s.ring, head, 1.6)
    s.at_text("Only what has been approved", 1.9)
    s.click(p.get_by_role("link", name="Monthly investment report in USD and SGD").first)
    s.ready(p.get_by_text("Holdings by status"))
    s.at_text("A question on a figure", 2.2)
    s.soft("scroll comments", s.scroll_to, p.get_by_role("heading", name="Comments on this dashboard"), 300, 1000)
    if not p.get_by_placeholder("Write a comment").count():
        s.click(p.get_by_role("button", name=re.compile(r"^(Comments|\d+ comments?)$")).last)
    box = p.get_by_placeholder("Write a comment")
    box.first.wait_for(state="visible")
    s.type(box.first, "Can we confirm the 8 Oct wire?")
    s.click(p.get_by_role("button", name="Comment", exact=True))
    raise_ = p.get_by_role("button", name="Raise as a case")
    s.ready(raise_)
    s.at_text("becomes a case", 0.6)
    s.click(raise_.first)
    link = p.get_by_role("link").filter(has_text="CASE-").or_(p.get_by_text("Case CASE-"))
    s.ready(link, 30)
    s.soft("ring case link", s.ring, link, 2.4)
    s.soft("point case link", s.point, link)


def s9_shared(s: Scene) -> None:
    p = s.page
    s.hold(0.2)
    head = p.get_by_role("heading", name="Shared with you")
    s.soft("scroll shared", s.scroll_to, head, 250, 1200)
    s.soft("ring shared", s.ring, head.locator("xpath=.."), 2.4)


def s11_span(s: Scene) -> None:
    """AGENT (Span, Real use): ask where cash lives; the reply names the table."""
    p = s.page
    s.hold(0.3)
    s.at_text("Architecture shows", 0.5)
    s.click(p.get_by_role("link", name=re.compile("Model view")).first)
    s.ready(p.get_by_text("Raw, exactly as it landed."))
    for txt, cue in (("Raw, exactly as it landed.", "files as they landed"), ("The company model every project shares.", "the company model"),
                     ("Built for this project's dashboards.", "tables built for")):
        s.at_text(cue, 0.4)
        s.soft(f"ring {cue}", s.ring, p.get_by_text(txt).locator("xpath=.."), 1.5)
    box = p.get_by_placeholder("Write or speak to Span")
    s.type(box, "Which tables hold cash by entity?")
    panel = p.locator("div").filter(has=p.get_by_role("heading", name="Ask Span about the model")).last
    before = p.evaluate("() => (document.body.innerText.match(/cash_movements/g) || []).length")
    s.click(panel.get_by_role("button", name="Send"))
    s.rec.pause()
    try:
        p.wait_for_function("n => (document.body.innerText.match(/cash_movements/g) || []).length > n", arg=before, timeout=150000)
    except Exception:  # noqa: BLE001 - the reply is shown as it came, whatever it names
        s.missed.append("Span reply did not name cash_movements")
    s.hold(1.2)
    s.rec.resume()
    s.mark("chime")
    s.at_text("Span keeps", 0.2)
    s.soft("zoom reply", s.zoom, panel, 1.35, 3.0)
    s.at_text("it names the table", 0.4)
    s.soft("ring reply", s.ring, panel.locator("p, li, div").filter(has_text="cash_movements").last, 2.0)
    s.at_text("with its columns", 0.6)
    s.click(p.get_by_role("button", name="cash_movements", exact=True).first)
    s.ready(p.get_by_text("Lineage").or_(p.get_by_text("lineage")).first)
    s.soft("scroll columns", s.scroll_to, p.get_by_text("Columns").first, 130, 1000)
    s.soft("ring columns", s.ring, p.get_by_text("Columns").first.locator("xpath=.."), 1.4)
    s.at_text("and its lineage", 0.3)
    s.soft("scroll lineage", s.scroll_to, p.get_by_text("Lineage").first, 150, 1000)
    s.soft("ring lineage", s.ring, p.get_by_text("Lineage").first.locator("xpath=.."), 2.4)


def offstage(s: Scene, stage: str) -> None:
    """A step done between shots (vid6_prep.py), never filmed."""
    s.rec.pause()
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("vid6_prep.py")), stage], capture_output=True, text=True,
                       env={**os.environ, "SH_FILM_ENV": os.environ.get("SH_FILM_ENV", "vid6")})
    if r.returncode:
        raise RuntimeError(f"{stage}: {r.stderr[-300:]}")
    s.page.reload()
    s.rec.resume()


def s12_pipelines(s: Scene) -> None:
    """The builder (V6): run on a copy, last month's report, the variance, sent back, version 2, live."""
    p = s.page
    s.hold(0.3)
    run = p.get_by_role("heading", name="Run on a copy")
    s.at_text("runs it on a copy", 0.5)
    s.soft("scroll run", s.scroll_to, run, 110, 900)
    s.soft("ring run", s.ring, run.locator("xpath=ancestor::div[contains(@class,'b9v-card')][1]"), 1.8)
    s.at_text("checks it against", 0.5)
    ask = p.get_by_text("Do you have last month's report to check against?")
    s.soft("scroll ask", s.scroll_to, ask, 150, 800)
    s.soft("point upload", s.point, p.get_by_text("Upload last month's report").first)
    s.mark("tick")
    p.locator("input[type=file]").set_input_files(str(DATA.parent / "September report as issued.csv"))
    s.ready(p.get_by_text("Unexplained", exact=True).first, 60)
    bad = p.get_by_text("Unexplained", exact=True).first
    s.soft("scroll bad", s.scroll_to, bad, 300, 800)
    s.at_text("One line differs", 0.4)
    s.soft("ring bad", s.ring, bad.locator("xpath=ancestor::tr[1]"), 1.8)
    s.at_text("goes back to the architect", 0.5)
    back = p.get_by_role("button", name="Send back to the architect")
    s.soft("scroll back", s.scroll_to, back, 380, 700)
    s.click(back)
    s.ready(p.get_by_text("With the architect.").first, 30)
    s.at_text("Version 2 matches", 0.3)
    offstage(s, "v2")
    s.ready(p.get_by_text("Variance cleared").first, 90)
    s.soft("scroll clear", s.scroll_to, p.get_by_text("Variance cleared").first, 300, 800)
    s.soft("ring clear", s.ring, p.get_by_text("Variance cleared").first.locator("xpath=ancestor::div[contains(@class,'b9v-card')][1]"), 1.8)
    s.at_text("goes live", 0.6)
    go = p.get_by_role("button", name="Go live", exact=True)
    s.soft("scroll live", s.scroll_to, go, 380, 700)
    s.click(go)
    s.ready(p.get_by_text("Lumen proposes a starter dashboard").first, 60)


def s13_lumen(s: Scene) -> None:
    """AGENT (Lumen, Real use): a tile from plain words, then 'make it dots', accept, submit."""
    p = s.page
    s.hold(0.2)
    slot = p.get_by_text("Add a widget here").first
    s.soft("scroll slot", s.scroll_to, slot, 260, 800)
    s.click(slot)
    s.soft("scroll lumen", s.scroll_to, p.get_by_role("heading", name="Talk to Lumen"), 60, 900)
    box = p.get_by_placeholder("Add cash by entity as bars")
    s.type(box, "Show the portfolio against the benchmark by month")
    s.click(p.get_by_role("button", name="Send").last)
    s.ready(p.get_by_text("Proposed by Lumen").first, 150)
    s.mark("chime")
    prop = p.get_by_text("Proposed by Lumen").last.locator("xpath=..")
    s.soft("scroll proposal", s.scroll_to, prop, 90, 800)
    s.at_text("Lumen fills", 0.3)
    s.soft("ring proposal", s.ring, prop, 1.6)
    s.at_text("Make it dots", 1.4)
    s.type(box, "Make it dots")
    before = p.evaluate("() => document.body.innerText.length")
    s.click(p.get_by_role("button", name="Send").last)
    s.rec.pause()
    s.hold(1.5)
    try:
        p.wait_for_function("n => !document.body.innerText.includes('is working') && document.body.innerText.length > n + 60",
                            arg=before, timeout=150000)
    except Exception:  # noqa: BLE001 - the reply is shown as it came
        s.missed.append("dots reply not detected")
    s.hold(1.0)
    s.rec.resume()
    s.mark("chime")
    prop = p.get_by_text("Proposed by Lumen").last.locator("xpath=..")
    s.soft("scroll dots", s.scroll_to, prop, 90, 700)
    s.soft("ring dots", s.ring, prop, 1.4)
    s.at_text("It does", 0.1)
    s.click(p.get_by_role("button", name="Accept").last)
    s.hold(0.4)
    s.soft("scroll grid", s.scroll_to, p.get_by_role("button", name="Add a row"), 620, 900)
    s.at_text("He submits", 0.9)
    sub = p.get_by_role("button", name="Submit for approval")
    s.soft("scroll submit", s.scroll_to, sub, 380, 800)
    s.click(sub)
    s.ready(p.get_by_text("waiting").first, 30)


def s14_approval(s: Scene) -> None:
    p = s.page
    s.hold(0.3)
    s.soft("ring waiting", s.ring, p.get_by_text("Waiting for your approval").first, 2.0)
    s.at_text("The head of data reviews", 0.5)
    btn = p.get_by_role("button", name="Approve", exact=True)
    s.soft("scroll approve", s.scroll_to, btn, 380, 900)
    s.soft("zoom approve", s.zoom, btn, 1.3, 1.6)
    s.at_text("and publishes", 0.5)
    s.click(btn)
    s.mark("seal")
    s.ready(p.get_by_text("Approved by").first, 30)
    s.soft("ring approved", s.ring, p.get_by_text("Approved by").first, 1.6)
    s.at_text("Moments later", 0.9)
    s.switch("daniel.foo", "/centre/consume/shared", "Shared with you")
    q = s.page
    s.soft("ring shared", s.ring, q.get_by_text("Shared with you").first, 1.4)
    s.click(q.get_by_role("link", name="Monthly investment report in USD and SGD").first)
    s.ready(q.get_by_text("Holdings by status"))
    tiles = q.locator("svg").last
    s.soft("scroll tile", s.scroll_to, tiles, 260, 1200)
    s.mark("whoosh")
    s.soft("ring tile", s.ring, tiles.locator("xpath=ancestor::div[1]"), 2.6)


def s15_north(s: Scene) -> None:
    """AGENT (North, Real use): a new intent from plain words."""
    p = s.page
    s.hold(0.3)
    box = p.get_by_placeholder("For example: a monthly report")
    s.soft("ring box", s.ring, box, 1.6)
    s.at_text("as a conversation", 0.6)
    s.type(box, "A quarterly report on how each private fund is pacing against its commitment, for Raj and me.")
    s.click(p.get_by_role("button", name="Start", exact=True))
    s.ready(p.get_by_role("button", name="Not this").or_(p.get_by_role("button", name="Accept")).first, 180)
    s.mark("chime")
    s.at_text("North writes it down", 0.5)
    msg = p.locator("div").filter(has_text="North").filter(has_text="?").last
    s.soft("ring reply", s.ring, msg, 2.4)
    s.soft("zoom reply", s.zoom, msg, 1.3, 2.4)
    s.at_text("and asks the next good question", 0.5)
    doc = p.get_by_role("heading", name="Intent of work").first
    s.soft("point doc", s.point, doc)
    s.soft("ring doc", s.ring, doc.locator("xpath=../.."), 2.6)


def s16_map(s: Scene) -> None:
    p = s.page
    s.hold(0.3)
    s.click(p.get_by_role("button", name="Process maps"))
    s.ready(p.get_by_text("Collect the exports").first)
    s.soft("scroll lanes", s.scroll_to, p.get_by_text("STEP 1", exact=True).or_(p.get_by_text("Step 1", exact=True)).first, 40, 1000)
    s.at_text("who does what", 0.4)
    s.soft("ring lane", s.ring, p.get_by_text("Mei Chen", exact=True).first, 1.0)
    s.at_text("with every manual step flagged", 0.5)
    for i in range(4):
        s.soft(f"ring manual {i + 1}", s.ring, p.get_by_text("Manual", exact=True).nth(i).locator("xpath=.."), 0.75)
        s.hold(0.55)
    s.at_text("In Map", 0.7)
    s.click(p.get_by_role("button", name="Data flow"))
    s.ready(p.get_by_text("Ready for reports").first)
    for txt, cue in (("Ready for reports", "the data flow"), ("Dashboards", "from source"), ("People", "to reader")):
        s.at_text(cue, 0.3)
        s.soft(f"ring {txt}", s.ring, p.get_by_text(txt, exact=True).first.locator("xpath=.."), 1.2)


def s18_settings(s: Scene) -> None:
    p = s.page
    s.hold(0.3)
    s.soft("ring runs", s.ring, p.get_by_role("heading", name="Recent runs"), 1.5)
    s.at_text("What it read", 0.6)
    turn = p.locator("li").filter(has_text="answered")    # a chat turn with its recorded steps (the seeded runs have none)
    show = (turn if turn.count() else p.locator("li")).get_by_role("button", name="Show steps").first
    s.soft("scroll steps", s.scroll_to, show, 300, 800)
    s.click(show)
    s.soft("scroll to steps", s.scroll_to, turn.first if turn.count() else show, 160, 700)
    s.soft("ring steps", s.ring, (turn.first if turn.count() else show).locator("xpath=."), 1.8)
    s.at_text("what it remembers", 0.9)
    s.click(p.get_by_role("link", name="What the agents remember about you").first)
    s.ready(p.get_by_text("The context the agents use").first)
    s.at_text("Yours to correct", 0.5)
    s.soft("ring context", s.ring, p.get_by_text("The context the agents use").first.locator("xpath=.."), 2.0)


def leo_submits_a_widget(page: Page, project: str, dash: str) -> None:
    """Off camera, when the Lumen take already exists: the data engineer adds a library widget to the empty slot and
    submits it, so the approval scene has something waiting."""
    page.goto(f"{BASE}/centre/build/p/{project}/studio?d={dash}")
    page.get_by_text("Add a widget here").or_(page.get_by_text("is waiting for the head of data")).first.wait_for(timeout=30000)
    if page.get_by_text("is waiting for the head of data").count():
        return
    page.get_by_text("Add a widget here").first.click()
    page.get_by_role("button", name="Line chart").click()
    page.locator("select").first.select_option(label="investment report benchmark monthly")
    page.get_by_role("button", name="Add widget to the slot").click()
    page.get_by_role("button", name="Submit for approval").click()
    page.get_by_text("waiting", exact=False).first.wait_for(timeout=30000)


# scene: (who, start page, the text that shows it has loaded, pages to pre-warm, what to do)
def plan(project: str, dash: str, intent: str, new: str = "") -> dict:
    b = f"/centre/build/p/{project}"
    return {
        5: ("mei.chen", "/centre/action", "Cash differs · Entity B", [], s5_tally),
        11: ("anita.rao", f"{b}/architecture", "What I already know", [], s11_span),
        13: ("leo.park", f"{b}/studio?d={dash}", "Widget library", [], s13_lumen),
        15: ("daniel.foo", "/centre/intent", "Your recent intents", [], s15_north),
        4: ("mei.chen", "/centre/action", "Investigate the 180,000 USD", [], s4_today),
        6: ("mei.chen", "/centre/action/cases/CASE-0003", "What Tally found", [], s6_trail),
        7: ("daniel.foo", "/centre/consume", "Key numbers", [], s7_numbers),
        8: ("daniel.foo", "/centre/consume", "Key numbers", [f"/centre/consume/d/{dash}"], s8_dashboards),
        9: ("daniel.foo", "/centre/consume", "Key numbers", [], s9_shared),
        12: ("leo.park", f"/centre/build/p/{new}/pipelines", "Run on a copy", [], s12_pipelines),
        14: ("anita.rao", f"{b}/studio?d={dash}", "Waiting for your approval", ["/centre/consume"], s14_approval),
        16: ("daniel.foo", "/centre/map", "Ready for reports", [f"/centre/intent/{intent}"], s16_map),
        18: ("grace.ong", "/centre/settings/runs", "Recent runs", ["/centre/settings/memory"], s18_settings),
    }


# ---- Real use and its cost ------------------------------------------------------------------------------------------------------

def set_mode(pw, mode: str, states: dict) -> None:
    states.setdefault("daniel.foo", sign_in_state(pw, "daniel.foo"))
    req = pw.request.new_context(base_url=BASE, storage_state=states["daniel.foo"])
    csrf = next((c["value"] for c in states["daniel.foo"]["cookies"] if c["name"] == "sh_csrf"), "")
    r = req.post("/api/v1/router/mode", data={"mode": mode}, headers={"X-CSRF-Token": csrf})
    if not r.ok:
        raise SystemExit(f"could not switch to {mode}: HTTP {r.status}")
    req.dispose()
    print(f"mode: {mode}", flush=True)


def openrouter_usage() -> float:
    from sh_platform.settings import load_model_env
    key = load_model_env().get("OPENROUTER_API_KEY") or ""
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + key})
    return float(json.load(urllib.request.urlopen(req, timeout=20))["data"]["usage"])


def main(only: list[int], agents: bool, rehearse: bool = False) -> dict:
    """rehearse: agent scenes run in Testing (free tier) to check the moves; nothing is kept as a take."""
    import narrate
    new = Path(os.environ["SH_FILM_NEW"]).read_text(encoding="utf-8").strip() if os.environ.get("SH_FILM_NEW") else ""
    project = next(p.name for p in (DATA / "evergreen" / "consume").glob("prj-*") if p.name != new)    # the seeded demo project
    dash = next((DATA / "evergreen" / "consume" / project / "dashboards").glob("dash-*.json")).stem
    intent = next((DATA / "evergreen" / "intents").glob("ini-*")).name
    narration = json.loads((WORK / "narration.json").read_text(encoding="utf-8"))
    kinds = {s["n"]: s["kind"] for s in scenes()}
    out = json.loads(REC.read_text(encoding="utf-8")) if REC.exists() else {}
    have = {int(k) for k, v in out.items() if kinds.get(int(k)) == "agent" and (WORK / v["clip"]).exists()} - {int(x) for x in os.environ.get("SH_RERECORD", "").split()}
    todo = {}
    for n, v in plan(project, dash, intent, new).items():
        if only and n not in only:
            continue
        if kinds[n] == "agent" and not rehearse and (not agents or n in have):
            continue
        todo[n] = v
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--hide-scrollbars"])
        states: dict[str, dict] = {}

        def opener(who: str, path: str) -> Page:
            states.setdefault(who, sign_in_state(pw, who))
            ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, storage_state=states[who],
                                      color_scheme="dark", reduced_motion="no-preference")
            ctx.add_init_script(INIT)
            pg = ctx.new_page()
            pg.goto(BASE + path)
            return pg

        if 14 in todo and 13 not in todo:
            pg = opener("leo.park", "/centre/build")
            leo_submits_a_widget(pg, project, dash)
            pg.context.close()
        mode = None
        try:
            for n, (who, start, ready, warm, fn) in todo.items():
                want = "real" if kinds[n] == "agent" and not rehearse else "testing"
                if want != mode:
                    set_mode(pw, want, states)
                    mode = want
                usage0 = openrouter_usage() if want == "real" else 0.0
                T = float(narration[str(n)]["seconds"])
                page = opener(who, start)
                for w in warm:                                              # pre-warm, off camera
                    page.goto(BASE + w)
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:  # noqa: BLE001
                        pass
                page.goto(BASE + start)
                page.get_by_text(ready).first.wait_for(state="visible", timeout=150000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:  # noqa: BLE001
                    pass
                page.evaluate("window.__sh.move(1100, 600, 10)")
                page.wait_for_timeout(700)
                rec = Recorder(WORK / f"frames{n}")
                rec.attach(page)
                rec.start()
                page.evaluate("window.__sh.nudge()")
                s = Scene(n, page, rec, T, opener)
                ok = True
                try:
                    fn(s)
                except Exception as e:  # noqa: BLE001 - a failed scene is reported; what was filmed so far is kept
                    ok = False
                    rec.resume()
                    print(f"scene {n}: FAILED ({type(e).__name__}: {str(e)[:400]})", flush=True)
                    s.page.screenshot(path=str(WORK / f"scene{n}-failed.png"))
                left = s.end() - s.now()
                if left > 0:
                    s.hold(left)
                length = max(s.end(), s.now() + 0.4)
                rec.pause()
                clip = WORK / (f"rehearse{n}.mp4" if rehearse else f"rec{n}.mp4")
                rec.write(length, clip)
                for c in {s.page.context, page.context}:
                    c.close()
                out[str(n)] = {"clip": clip.name, "seconds": round(length, 2), "zooms": s.zooms, "marks": s.marks, "ok": ok,
                               "frames": len(rec.frames), "missed": s.missed, "mode": want}
                if not rehearse:
                    REC.write_text(json.dumps(out, indent=1), encoding="utf-8")
                if want == "real":
                    time.sleep(8)  # let the provider settle the charge before reading it
                    cost = openrouter_usage() - usage0
                    narrate.log_cost(f"agent take, scene {n} ({fn.__doc__.split(':')[0].strip() if fn.__doc__ else n}), Real use",
                                     "OpenRouter, the product's Real-use agent models", round(cost, 4))
                print(f"scene {n}: {'ok' if ok else 'FAILED'}, {length:.1f} s (voice {T:.1f}), {len(rec.frames)} frames, "
                      f"{len(s.zooms)} zooms, missed {len(s.missed)}", flush=True)
        finally:
            if mode == "real":
                set_mode(pw, "testing", states)
            browser.close()
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main([int(a) for a in args], "--agents" in sys.argv, "--rehearse" in sys.argv)
