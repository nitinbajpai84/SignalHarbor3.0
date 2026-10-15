"""Builds the product testing deck: index.html, the editable .pptx and img/.
Run from the repo root: python docs/demo/testing-deck/build_deck.py
One slide list feeds both outputs, so they always say the same thing."""
import html, re
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
IMG = OUT / "img"
IMG.mkdir(exist_ok=True)
L = ROOT / "docs/test/uc-live"
V = ROOT / "docs/plan/v6-landings"
SRC = {
    "uc5-limits-run": Path("D:/Temp/uc5/shots/uc5-10-jul-limits-run.png"),
    "uc5-case": Path("D:/Temp/uc5/shots/uc5-15-sep-harborview-case.png"),
    "uc6-north": L / "uc6-run3-shots/jul-01-mei-intent-drafted.png",
    "uc6-pack": L / "uc6-run3-shots/jul-06-leo-design-pack-drafted.png",
    "uc6-action": L / "uc6-run3-shots/aug-09-raj-action.png",
    "studio": (V / "studio2-6-checks.png", (0, 600, 1100, 1500)),
    "uc6-runs": L / "uc6-run3-shots/aug-07-leo-operations-runs.png",
    "uc8-signed": L / "uc8-run2-shots/jul-02-daniel-intent-signed.png",
    "uc8-check": L / "uc8-run2-shots/jul-10-grace-trade-check-empty.png",
    "data-model": ROOT / "docs/demo/showcase/img/map-data-model.png",
    "sketch-drawn": V / "studio2-1-sketch-drawn.png",
    "sketch-read": V / "studio2-2-sketch-read.png",
    "sketch-built": V / "studio2-3-sketch-built.png",
    "options": (V / "studio2-4-options.png", (1060, 1480, 1420, 2120)),
    "new-charts": V / "studio2-5-new-charts.png",
    "checks": (V / "studio2-6-checks.png", (390, 640, 1410, 1320)),
}


def prep(key):
    """Crop to the top of the screen (screens are tall), save as PNG in img/."""
    src, box = SRC[key] if isinstance(SRC[key], tuple) else (SRC[key], None)
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    w, h = im.size
    maxh = h if box else int(w * (1.4 if w < 900 else 0.68))
    im = im.crop((0, 0, w, min(h, maxh)))
    if im.width > 1600:
        im = im.resize((1600, int(im.height * 1600 / im.width)))
    p = IMG / f"{key}.png"
    im.save(p, optimize=True)
    return p


# ---------- the slides ----------
FOOT = "Evergreen Office is a synthetic family office. All names, files and figures are invented."
S = []
def add(**k): S.append(k)

add(t="title", h="Testing Signal Harbor <em>the way you will use it</em>",
    sub="Product testing for Evergreen Office. Real use cases, synthetic data, month by month.",
    note="13 October 2026")
add(t="bul", k="Method", h="How we test the product", b=[
    "We take a real family-office question and run it end to end.",
    "All data is synthetic. Evergreen Office, its entities and funds are invented.",
    "We run month by month: a build month, then the months after it.",
    "Each step is done as the person who would do it: owner, sponsor, data engineer, head of data, approver.",
    "Every figure is checked against an answer key written before the run.",
    "Every run has a run ID, so any figure can be traced back to its files.",
    "What breaks is written down, fixed, and run again."])
add(t="table", k="Scope", h="The ten family-office use cases", cols=["", "Use case", "The question it answers"], rows=[
    ["UC1", "P&amp;L and NAV explanation", "Why did NAV move this month?"],
    ["UC2", "Reconciliation and break desk", "Where do two records of the same money disagree?"],
    ["UC3", "Manager information inbox", "What did our managers send, and what is late?"],
    ["UC4", "Certified reporting and benchmark", "Is the signed monthly report right against the benchmark?"],
    ["UC5", "Allocation and limit monitoring", "Are we inside our limits?"],
    ["UC6", "Private-asset liquidity and commitments", "Can we meet the capital calls?"],
    ["UC7", "Manager diligence research", "What do we know about this manager, in one place?"],
    ["UC8", "Trade and valuation control", "Do our trades agree with the administrator?"],
    ["UC9", "Process map and SOP builder", "How is the monthly work done, step by step?"],
    ["UC10", "Data pipeline and insight builder", "How does a question become a live dashboard?"]])
add(t="flow", k="Why these three", h="Why we ran UC5, UC6 and UC8 first",
    f=[("Files", "Bank, administrator, notices, trades"), ("Bronze", "Kept exactly as received"),
       ("Silver", "Clean, shared tables"), ("Gold", "One table per question"),
       ("Dashboards and cases", "What people read and act on")],
    b=["They load new files every month, so the whole data path is tested, not a demo screen.",
       "They end in something a person uses: a Lumen dashboard and Tally cases in Action.",
       "Together they cover limits, liquidity and trades, the three monthly worries of a family office.",
       "They use all four centres and all three agents."])
add(t="flow", k="The journey", h="Every use case takes the same path",
    f=[("Intent", "North drafts with the owner. The sponsor signs."),
       ("Build", "Span designs. Files land in bronze. Silver is reused. Gold is built."),
       ("Prove", "The first run is on a copy, checked against the answer key. Then it goes live."),
       ("Consume", "Lumen builds the dashboard. Every figure says where it came from."),
       ("Action", "Tally opens a case for each break. A person decides.")],
    b=["Humans act at four points: sign the intent, approve the design, go live, close a case.",
       "Agents draft and check. People decide."])

# UC5
add(t="img", k="UC5 · Limits", h="Are we inside our limits?", img="uc5-limits-run", b=[
    "Each month the office checks every portfolio against its signed limits.",
    "Limits cover share in an asset class, a manager and a single holding.",
    "The risk owner runs the check. The CIO signs any change to a limit.",
    "A breach becomes a case with a maker and a checker.",
    "Run: July 2026 as the build month, then August, September and October."],
    cap="Reconciliations: the monthly check, with the date the files were received.")
add(t="img", k="UC5 · Result", h="September matched the answer key", img="uc5-case", b=[
    "Hedge funds 54.95% and listed equity 80.61%, as in the key.",
    "Two breaches, each split into real or stale.",
    "Harborview: 5.75% against a 5% limit. Real. Over by USD 308,000.",
    "Cedarpoint: 56.50%, over by USD 343,750, because one input was stale.",
    "Tally wrote the case from the records. The person decides what to do.",
    "Run ID run-20261012-235352-2869."],
    cap="The Harborview case: what Tally found and what to do next.")
add(t="table", k="UC5 · Found and fixed", h="What the test found, and what we changed", cols=["Found in the test", "Fixed"], rows=[
    ["A file loaded late never counted for the day it arrived", "The check now reads by the date a file was received"],
    ["A breach that stayed open opened a new case every month", "One case per standing breach; later months are added to it"],
    ["The administrator's totals block under the data was ignored", "Read as control totals and checked against the rows"],
    ["Limit changes had to be typed in by hand", "Import the signed limits workbook; the CIO signs the changes"],
    ["Still open: a limits dashboard in Consume, and new valuations inside the administrator file", "Two decisions for you; see the last slide"]])

# UC6
add(t="img", k="UC6 · Liquidity", h="Can we meet the capital calls?", img="uc6-north", b=[
    "The CFO wants one page per month: cash per entity, calls due in 30 and in 31 to 60 days, and any shortfall.",
    "It also shows what is still to be called on each private fund.",
    "Mei, the owner, described it to North in plain words. North drafted the intent beside her.",
    "Daniel, the sponsor, read it and signed it."],
    cap="Intent: North drafts the intent as Mei talks.")
add(t="img", k="UC6 · Journey", h="Two months, end to end", img="uc6-pack", b=[
    "Mei handed the project to Leo, the data engineer.",
    "Span drafted the design pack. Anita, head of data, approved it.",
    "July: six files in. Commitments loaded after the five funds were approved.",
    "Run on a copy: 11 of 11 checks passed. Then live.",
    "Lumen's starter dashboard, six tiles, approved by Anita.",
    "August loaded with July's mappings and no edits."],
    cap="Build: Span's design pack, with gold tables and silver reused.")
add(t="table", k="UC6 · Result", h="Cash by entity matched to the cent", cols=["Figure", "Key July", "Run July", "Key August", "Run August"], rows=[
    ["Cash, Holdings", "2,305,906.48", "2,305,906.48", "2,287,630.12", "2,287,630.12"],
    ["Cash, Trust", "1,252,492.34", "1,252,492.34", "1,199,690.58", "1,199,690.58"],
    ["Cash, Entity B", "905,000.00", "905,000.00", "654,014.07", "654,014.07"],
    ["Cash, three entities", "4,463,398.82", "4,463,398.82", "4,141,334.77", "4,141,334.77"],
    ["Calls due, shortfall", "none", "none", "none", "none"]],
    after="Fixed after the test: Span's first gold design did not run; one late notice changed the amount still to be called; North listed some figures as sources. Still open: Action raised a case for a call already paid.")
add(t="img", k="UC6 · Action", h="What a person sees in Action", img="uc6-action", b=[
    "One list of what needs a person today.",
    "Each line says what happened and the one thing to do.",
    "Here: a capital call case from Tally, with a button to take it.",
    "The test showed this call was already paid, so Mei dismissed it as paid. Next: paid calls will not raise a case."],
    cap="Action, as Raj the approver, in the August cycle.")

# UC8
add(t="img", k="UC8 · Trades", h="Do our trades agree with the administrator?", img="uc8-signed", b=[
    "Each month, every trade in our export is matched to the administrator's file.",
    "A break above USD 5,000 needs a person. Raj approves corrections.",
    "Mei wrote the intent with North in about 20 minutes.",
    "Daniel signed it. Span drafted the design. Anita approved it."],
    cap="The signed intent: purpose, readers, figures and sources.")
add(t="img", k="UC8 · Honest result", h="Blocked at the first load, and why", img="uc8-check", b=[
    "Intent, signature and design approval all worked.",
    "July's trades did not reach the silver trades table, so the check compared 0 trades.",
    "The check itself works and holds the signed USD 5,000 allowance.",
    "Months 2 to 4 were not run; they would only repeat the empty check.",
    "Next: a trade loader into silver, then rerun from the load step."],
    cap="The trade check before any trades were loaded.")

# Silver and lineage
add(t="img2", k="Data", h="Silver layer and lineage", imgs=[("data-model", "Map, Data model: bronze, silver and gold, and what a change would touch."),
                                                         ("uc6-runs", "Operations: every source, every run, every run ID.")],
    b=["Source to bronze: kept exactly as received, with arrival time.",
       "Bronze to silver: clean shared tables for entity, fund, cash and trades. Reused, not rebuilt.",
       "Silver to gold: one table per question. Every figure keeps its trail back to file and row."])

# New features
add(t="img", k="New · Studio", h="A dashboard studio shaped by conversation", img="studio", b=[
    "You say what you want in plain words. Lumen places the tile at once.",
    "Select a tile and talk about that tile only.",
    "Every change is a numbered step, so you can go back.",
    "Comments and approval stay on the dashboard."],
    cap="The studio: talk to Lumen on the left, the tiles it placed on the right.")
add(t="img3", k="New · Sketch", h="From a sketch to a dashboard",
    imgs=[("sketch-drawn", "1. The sketch, drawn by hand"), ("sketch-read", "2. What Lumen read"), ("sketch-built", "3. The built dashboard")],
    b=["Draw the page you want. Lumen reads the boxes and labels, says what it understood, and builds it on your data."])
add(t="img", k="New · Options", h="Lumen offers three options", img="options", b=[
    "For any tile, Lumen offers three ways to show it.",
    "Each option says why, in one line, based on industry practice.",
    "One is marked as Lumen's pick. You choose.",
    "If you choose otherwise, Lumen does it your way."],
    cap="Lumen's pick, with the industry practice behind it. The next option follows below.")
add(t="img", k="New · Checks", h="Chart checks before you publish", img="checks", b=[
    "Lumen checks the dashboard before anyone reads it.",
    "Same money counted twice.",
    "A trend flattened by the wrong scale.",
    "Wasted space, house style, too many things on one page.",
    "Each check offers a one-click fix."],
    cap="The checks panel, each finding with its fix.")
add(t="img", k="New · Charts", h="New chart types", img="new-charts", b=[
    "Bullet: a figure against its target or limit.",
    "Waterfall: what moved a total.",
    "Small multiples: one small chart per entity, same scale.",
    "Calendar: what falls due on which day.",
    "Treemap and KPI strip: the whole and the headline figures."],
    cap="New chart types on synthetic data.")
add(t="two", k="New · Teach the agents", h="Books distilled into playbooks for the agents",
    c=[("Lumen: how to build a dashboard", [
        "Ask who reads it and the three to five questions it answers.",
        "Lead with the answer, each figure beside a comparison.",
        "Match the chart to the question: line for trend, sorted bars to compare, waterfall for what moved.",
        "No pies, gauges or 3-D. Check for double counting first."]),
       ("Span: how to design the data", [
        "Name the business question before any column.",
        "Reuse the shared silver tables; a new one needs a reason.",
        "Write the grain of each table in one sentence.",
        "Balances are taken at a date, never added across dates."])],
    after="Drawn from classic books on dashboard design, data modelling and investment basics. Practice is suggested, never forced: the person decides.")
add(t="bul", k="Next", h="What is next", b=[
    "UC8: build the trade loader into silver, then rerun July to October.",
    "UC5: two decisions for you: a limits dashboard in Consume, and new valuations in the administrator file.",
    "UC6: Span's gold design runs first time, with no hand rewrite.",
    "Run UC1 to UC4, UC7, UC9 and UC10 the same way, month by month.",
    "Then a trial month on a copy of your own files."], dark=True)


# ---------- HTML ----------
def esc(s): return s  # strings above are written as safe HTML

def foot(): return f'<div class="foot"><span>{FOOT}</span><span class="sn"></span></div>'

def lis(b): return "<ul>" + "".join(f"<li>{x}</li>" for x in b) + "</ul>"

def html_slide(s):
    t = s["t"]
    k = f'<div class="kicker">{s.get("k","")}</div>' if s.get("k") else ""
    h2 = f'<h2>{s["h"]}</h2>'
    if t == "title":
        return f'<section class="slide dark title"><div class="bar"></div><h1>{s["h"]}</h1><p class="sub">{s["sub"]}</p><p class="sub small" style="margin-top:12px">{s["note"]}</p>{foot()}</section>'
    if t == "bul":
        cls = "slide dark" if s.get("dark") else "slide"
        return f'<section class="{cls}">{k}{h2}{lis(s["b"])}{foot()}</section>'
    if t == "table":
        th = "".join(f"<th>{c}</th>" for c in s["cols"])
        tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in s["rows"])
        aft = f'<p class="flag" style="margin-top:16px">{s["after"]}</p>' if s.get("after") else ""
        return f'<section class="slide tight">{k}{h2}<table class="num"><tr>{th}</tr>{tr}</table>{aft}{foot()}</section>'
    if t == "flow":
        boxes = '<span class="arr">&rarr;</span>'.join(f"<div><b>{a}</b>{b}</div>" for a, b in s["f"])
        return f'<section class="slide">{k}{h2}<div class="flow">{boxes}</div>{lis(s["b"])}{foot()}</section>'
    if t == "img":
        return (f'<section class="slide tight">{k}{h2}<div class="row"><div class="col" style="flex:0 0 470px">{lis(s["b"])}</div>'
                f'<div class="col"><img class="shot" src="img/{s["img"]}.png" alt=""><p class="cap">{s["cap"]}</p></div></div>{foot()}</section>')
    if t in ("img2", "img3"):
        cols = "".join(f'<div class="col"><img class="shot" style="height:{330 if t=="img2" else 380}px" src="img/{i}.png" alt=""><p class="cap">{c}</p></div>' for i, c in s["imgs"])
        return f'<section class="slide tight">{k}{h2}<div class="row">{cols}</div><div style="margin-top:14px">{lis(s["b"])}</div>{foot()}</section>'
    if t == "two":
        cols = "".join(f'<div class="col card"><h3>{a}</h3>{lis(b)}</div>' for a, b in s["c"])
        return f'<section class="slide tight">{k}{h2}<div class="row">{cols}</div><p class="flag" style="margin-top:16px">{s["after"]}</p>{foot()}</section>'
    raise ValueError(t)


def build_html():
    src = (ROOT / "docs/demo/showcase/index.html").read_text(encoding="utf-8")
    head = src[: src.index("<body")]
    head = re.sub(r"<title>.*?</title>", "<title>Signal Harbor product testing</title>", head)
    head = head.replace("</style>", ".shot{object-fit:contain;object-position:top center;background:#0F1B2D}</style>")
    tail = src[src.index('<div class="ui">'):]
    body = '<body>\n<div class="stage" id="stage">\n' + "\n".join(html_slide(s) for s in S) + "\n</div>\n\n"
    (OUT / "index.html").write_text(head + body + tail, encoding="utf-8")


# ---------- PPTX ----------
NAVY, TEAL, AQUA, AMBER, PAPER, INK, MUTED, WHITE = (RGBColor.from_string(x) for x in
    ("0F1B2D", "177878", "5FC2C2", "E0A34A", "F6F4EF", "0F1B2D", "5B6678", "FFFFFF"))
PX = 9525  # EMU per px at 96 dpi; slide is 1280x720 px


def plain(s): return html.unescape(re.sub(r"<[^>]+>", "", s))


def tb(sl, x, y, w, h, text, size=18, color=INK, bold=False, serif=False):
    box = sl.shapes.add_textbox(Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX))
    tf = box.text_frame; tf.word_wrap = True
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run(); r.text = plain(line)
        r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
        r.font.name = "Georgia" if serif else "Calibri"
        p.space_after = Pt(6)
    return box


def pic(sl, key, x, y, w, h):
    p = IMG / f"{key}.png"
    iw, ih = Image.open(p).size
    s = min(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    sl.shapes.add_picture(str(p), Emu(int((x + (w - dw) / 2) * PX)), Emu(int(y * PX)), Emu(int(dw * PX)), Emu(int(dh * PX)))


def build_pptx():
    prs = Presentation(); prs.slide_width = Emu(1280 * PX); prs.slide_height = Emu(720 * PX)
    blank = prs.slide_layouts[6]
    for n, s in enumerate(S, 1):
        sl = prs.slides.add_slide(blank)
        dark = s["t"] == "title" or s.get("dark")
        bg = sl.background.fill; bg.solid(); bg.fore_color.rgb = NAVY if dark else PAPER
        fg = WHITE if dark else INK
        tb(sl, 72, 676, 1000, 24, FOOT, 10, MUTED)
        tb(sl, 1120, 676, 90, 24, f"{n} / {len(S)}", 10, MUTED)
        t = s["t"]
        if t == "title":
            bar = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(72 * PX), Emu(300 * PX), Emu(120 * PX), Emu(6 * PX))
            bar.fill.solid(); bar.fill.fore_color.rgb = AMBER; bar.line.fill.background()
            tb(sl, 72, 330, 1100, 180, s["h"], 54, WHITE, True, True)
            tb(sl, 72, 520, 1000, 80, [s["sub"], s["note"]], 20, RGBColor.from_string("C9D4E2"))
            continue
        tb(sl, 72, 44, 1100, 30, s["k"].upper(), 12, AQUA if dark else TEAL, True)
        tb(sl, 72, 72, 1136, 60, s["h"], 32, fg, True, True)
        if t == "bul":
            tb(sl, 72, 150, 1136, 500, ["•  " + x for x in s["b"]], 20, fg)
        elif t == "table":
            rows, cols = len(s["rows"]) + 1, len(s["cols"])
            tbl = sl.shapes.add_table(rows, cols, Emu(72 * PX), Emu(145 * PX), Emu(1136 * PX), Emu(rows * 40 * PX)).table
            for c, name in enumerate(s["cols"]):
                tbl.cell(0, c).text = plain(name)
            for r, row in enumerate(s["rows"], 1):
                for c, v in enumerate(row):
                    tbl.cell(r, c).text = plain(v)
            for r in range(rows):
                for c in range(cols):
                    for p in tbl.cell(r, c).text_frame.paragraphs:
                        for run in p.runs: run.font.size = Pt(13)
            if s.get("after"):
                tb(sl, 72, 160 + rows * 42, 1136, 80, s["after"], 15, RGBColor.from_string("7A4E0C"))
        elif t == "flow":
            w = (1136 - 12 * (len(s["f"]) - 1)) / len(s["f"])
            for i, (a, b) in enumerate(s["f"]):
                x = 72 + i * (w + 12)
                sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(int(x * PX)), Emu(145 * PX), Emu(int(w * PX)), Emu(130 * PX))
                sh.fill.solid(); sh.fill.fore_color.rgb = WHITE; sh.line.color.rgb = RGBColor.from_string("D9DED8")
                tb(sl, x + 8, 150, w - 16, 120, [a, b], 14, INK).text_frame.paragraphs[0].runs[0].font.color.rgb = TEAL
            tb(sl, 72, 300, 1136, 340, ["•  " + x for x in s["b"]], 19, fg)
        elif t == "img":
            tb(sl, 72, 145, 470, 500, ["•  " + x for x in s["b"]], 16, fg)
            pic(sl, s["img"], 566, 145, 642, 430)
            tb(sl, 566, 590, 642, 40, s["cap"], 12, MUTED)
        elif t in ("img2", "img3"):
            n_ = len(s["imgs"]); w = (1136 - 24 * (n_ - 1)) / n_
            hh = 330 if t == "img2" else 380
            for i, (key, cap) in enumerate(s["imgs"]):
                x = 72 + i * (w + 24)
                pic(sl, key, x, 140, w, hh)
                tb(sl, x, 145 + hh, w, 40, cap, 12, MUTED)
            tb(sl, 72, 190 + hh, 1136, 120, ["•  " + x for x in s["b"]], 15, fg)
        elif t == "two":
            for i, (a, b) in enumerate(s["c"]):
                x = 72 + i * 580
                tb(sl, x, 145, 556, 40, a, 20, TEAL, True, True)
                tb(sl, x, 190, 556, 320, ["•  " + y for y in b], 16, fg)
            tb(sl, 72, 540, 1136, 80, s["after"], 15, RGBColor.from_string("7A4E0C"))
    prs.save(OUT / "Signal-Harbor-product-testing.pptx")


if __name__ == "__main__":
    for k in SRC: prep(k)
    build_html(); build_pptx()
    banned = re.compile(r"wah\s*hin|claude|anthropic|gpt|qwen|openai|llama|gemini", re.I)
    text = (OUT / "index.html").read_text(encoding="utf-8")
    assert not banned.search(text), banned.search(text)
    print(len(S), "slides")
