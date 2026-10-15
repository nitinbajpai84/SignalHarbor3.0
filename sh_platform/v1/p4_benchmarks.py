"""P4 Benchmarks: what the intent raiser reports today for the last period and what the figure should read after a month's load.

North (i6_chat) stores one per KPI on the SOW as `benchmark: {period, reported, expected, tolerance, source}` or `benchmark: null` when
the person has none. The figures are copied by this program from the person's own words, never from the model's text (the reply guard
rewrites digits): the model only marks which KPI the latest message gave a benchmark for ("given") or said it has none ("none").
Span's design carries one benchmark per KPI (`for_design`): the SOW's, or a proposed one marked `proposed`. After Flow's load (b4) each
gold figure is checked against its benchmark (`verify`, written to `build/verify/<iid>.json`), and every miss becomes a comment on the
build pack addressed to the intent raiser and the sponsor (P1, guarded). `sign_block` says why the build pack cannot be signed yet.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from sh_platform.v1 import wh

from sh_platform.jsonfile import read_json_strict, write_json_atomic

log = logging.getLogger(__name__)
ARTEFACT = "build_pack"
DEFAULT_TOLERANCE_PCT = 1  # a benchmark with no tolerance said: within 1 % of the expected figure
MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                                      "november", "december"), 1)}
NONE = re.compile(r"\b(?:don'?t|do not|haven'?t|have not)\s+(?:have|got)\b|\bno (?:benchmark|figure|number)s?\b|\bnone\b|\bnot reported\b", re.I)
NUM = r"-?\d+(?:,\d{3})*(?:\.\d+)?"
TOL = re.compile(rf"(?:within|plus or minus|give or take|tolerance(?: of)?|±|\+/-)\s*({NUM})", re.I)
ISO = re.compile(r"\b(\d{4})-(\d{2})\b")
MONTH = re.compile(r"\b(" + "|".join(MONTHS) + r")\b(?:\s+(\d{4}))?", re.I)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _period(text: str, today: date) -> tuple[str, str]:
    """(YYYY-MM, the text with the period taken out). No period said: the last full month."""
    m = ISO.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}", text[:m.start()] + text[m.end():]
    m = MONTH.search(text)
    if m:
        mo = MONTHS[m.group(1).lower()]
        yr = int(m.group(2)) if m.group(2) else (today.year if mo < today.month else today.year - 1)
        return f"{yr}-{mo:02d}", text[:m.start()] + text[m.end():]
    y, mo = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y}-{mo:02d}", text


def parse(text: str, by: str, today: date | None = None) -> dict | None:
    """A benchmark from the person's words, or None when no figure is in them."""
    period, rest = _period(str(text or ""), today or wh.today())
    tol = TOL.search(rest)
    if tol:
        rest = rest[:tol.start()] + rest[tol.end():]
    nums = [_num(n) for n in re.findall(NUM, rest)]
    if not nums:
        return None
    reported, expected = nums[0], nums[1] if len(nums) > 1 else nums[0]
    tolerance = _num(tol.group(1)) if tol else round(abs(expected) * DEFAULT_TOLERANCE_PCT / 100, 6)
    return {"period": period, "reported": reported, "expected": expected, "tolerance": tolerance, "source": f"said by {by}"}


def _norm(v) -> str:
    return " ".join(str(v or "").lower().split())


def segment(kpis: list[dict], k: dict, text: str) -> str:
    """The part of the person's words that belongs to KPI `k`: from its name to the next KPI's name (all of it when not named)."""
    low = str(text or "").lower()
    starts = [low.find(_norm(x.get("name"))) for x in kpis if x.get("name") and _norm(x.get("name")) in low]
    at = low.find(_norm(k.get("name")))
    return text if at < 0 else text[at:min([p for p in starts if p > at] or [len(text)])]


def from_talk(sow: dict, patch_kpis, text: str, by: str, asked: bool, today: date | None = None) -> None:
    """Write benchmarks onto the SOW's KPIs. `patch_kpis`: the model's KPI rows, whose `benchmark` is "given" or "none". With no mark
    and `asked` (North (rules only) just asked for benchmarks), the KPIs named in the text take it, else the first KPI still without one
    ("I don't have one" with no name: every KPI still without one)."""
    kpis = [k for k in sow.get("kpis") or [] if isinstance(k, dict)]
    marks = {_norm(i.get("name")): i["benchmark"] for i in patch_kpis or [] if isinstance(i, dict) and i.get("benchmark") in ("given", "none")}
    low = str(text or "").lower()
    named = sorted(((low.find(_norm(k.get("name"))), k) for k in kpis if k.get("name") and _norm(k.get("name")) in low), key=lambda x: x[0])
    if not marks and asked:
        none = bool(NONE.search(low)) and not re.search(r"\d", ISO.sub("", low))
        if named:
            marks = {_norm(k.get("name")): "none" if none else "given" for _, k in named}
        else:
            left = [k for k in kpis if "benchmark" not in k]
            marks = {_norm(k.get("name")): "none" for k in left} if none else {_norm(left[0].get("name")): "given"} if left else {}
    for k in kpis:
        mark = marks.get(_norm(k.get("name")))
        if mark == "none":
            k["benchmark"] = None
        elif mark == "given":
            got = parse(segment(kpis, k, text), by, today)
            if got:
                k["benchmark"] = got


def line(b) -> str:
    """One benchmark in words (the closing summary, the context North reads)."""
    if not b:
        return "no benchmark given; the design will name one"
    if b.get("sheet"):  # G3: a pointer to rows on the benchmark sheet
        n = len(b.get("rows") or [])
        return f"{n} row{'s' if n != 1 else ''} on the benchmark sheet"
    return (f"for {b['period']} reported {b['reported']:g}; after the load it should read {b['expected']:g} within {b['tolerance']:g} "
            f"({b.get('source') or ''})")


def for_design(sow: dict, today: date | None = None, sheet: dict | None = None) -> list[dict]:
    """The benchmark list for Span's design: the benchmark sheet's rows (G3) for a KPI that has some, else the SOW's own single benchmark,
    else a proposed one the raiser confirms against the first load (proposed rows only where the owner gave none)."""
    t = today or wh.today()
    last = f"{t.year}-{t.month - 1:02d}" if t.month > 1 else f"{t.year - 1}-12"
    out = []
    for k in sow.get("kpis") or []:
        if not isinstance(k, dict) or not k.get("code"):
            continue
        rows = [r for r in (sheet or {}).get("rows") or [] if r.get("code") == k["code"] and not r.get("dropped")]
        b = k.get("benchmark")
        if rows:
            for r in rows:
                dims = {d: v for d, v in (r.get("dims") or {}).items() if v}
                out.append({"code": k["code"], "name": k.get("name"), "row_id": r.get("id"), "dims": dims, "period": dims.get("period") or r.get("period"),
                            "reported": r.get("reported"), "expected": r.get("expected"), "tolerance": r.get("tolerance"),
                            "source": r.get("source"), "proposed": bool(r.get("proposed"))})
        elif b and not b.get("sheet"):
            out.append({"code": k["code"], "name": k.get("name"), **b, "proposed": False})
        else:
            out.append({"code": k["code"], "name": k.get("name"), "period": last, "reported": None, "expected": None, "tolerance": None,
                        "source": f"proposed by Span: the raiser confirms the first loaded figure, within {DEFAULT_TOLERANCE_PCT} % of it",
                        "proposed": True})
    return out


# ---- after the load ------------------------------------------------------------------------------------------------------------

def _read(path, kind=dict):
    try:
        return read_json_strict(path, kind) or kind()
    except (OSError, ValueError):
        return kind()


def _got(plane, sow: dict, code: str, period: str) -> float | None:
    from sh_platform.consume.measure import _full_trend
    from sh_platform.v1.c1_cards import table_of
    table = table_of(sow, code)
    hits = [t["value"] for t in (_full_trend(plane, table) if table else []) if str(t["period"])[:7] == period]
    return hits[-1] if hits else None


def _newest(plane, sow: dict, code: str) -> str | None:
    from sh_platform.consume.measure import _full_trend
    from sh_platform.v1.c1_cards import table_of
    table = table_of(sow, code)
    return max((str(t["period"])[:7] for t in (_full_trend(plane, table) if table else [])), default=None)


def _p1():
    try:
        from sh_platform.v1 import p1_project
        return p1_project
    except ImportError:
        return None


def _mine(P, plane, iid: str) -> tuple[dict | None, list[dict]]:
    """(the intent's project, its comments on the build pack); (None, []) without P1 or a project."""
    project = P.project_of(plane, iid) if P else None
    return project, (P.comments(plane, project["id"], ARTEFACT) if project else [])


def _ref(row: dict) -> str:
    extra = row.get("row_id")  # G3: a sheet row with dimensions beyond the period is its own line
    return f"benchmark:{row['code']}:{row['period']}" + (f":{extra}" if extra and row.get("label") else "")


def _text(row: dict, name: str) -> str:
    got = "no figure" if row["got"] is None else f"{row['got']:g}"
    name = f"{name} ({row['label']})" if row.get("label") else name
    if row["expected"] is None:
        return (f"No benchmark was given for {name}. The load reads {got} for {row['period']}. Is that what you expect? "
                "Answer with the figure you reported, or confirm this one.")
    return (f"{name} for {row['period']}: the load reads {got}, the benchmark expects {row['expected']:g} within {row['tolerance']:g}. "
            "Which is right, and why might they differ?")


def _post(plane, iid: str, sow: dict, misses: list[dict]) -> None:
    P = _p1()
    if P is None or not misses:
        return  # P1 not landed: the miss stays in build/verify/<iid>.json only
    try:
        project, mine = _mine(P, plane, iid)
        if not project:
            return
        ppl = project.get("people") or {}
        to = list(dict.fromkeys(n for n in (ppl.get("raiser"), ppl.get("sponsor")) if n))
        names = {k.get("code"): k.get("name") or k.get("code") for k in sow.get("kpis") or [] if isinstance(k, dict)}
        have = {(c.get("line_ref"), c.get("to"), c.get("text")) for c in mine}
        for row in misses:
            text = _text(row, names.get(row["code"], row["code"]))
            for person in to:
                if (_ref(row), person, text) not in have:  # the same miss is raised once, not on every reload
                    P.comment(plane, project["id"], ARTEFACT, _ref(row), "flow", person, text)
    except Exception as e:  # noqa: BLE001 - P1 is another card's; the verify record stands without the comment
        log.warning("benchmark comment skipped (%s)", type(e).__name__)


def verify(plane, iid: str) -> list[dict]:
    """Every KPI's gold figure against its benchmark: [{code, period, expected, got, tolerance, met}] written to build/verify/<iid>.json.
    `met` is None when there is no expected figure to compare (a proposed benchmark): the raiser is asked to confirm the figure."""
    sow = _read(plane.path("intents", iid, "sow.json"))
    sheet = _read(plane.path("intents", iid, "benchmarks.json"))  # G3: the signed sheet, at the owner's own granularity
    rows = []
    for b in for_design(sow, sheet=sheet):
        if b["proposed"]:  # the loaded period, not calendar last month
            b["period"] = _newest(plane, sow, b["code"]) or b["period"]
        dims = {d: v for d, v in (b.get("dims") or {}).items() if d != "period"}
        why = None
        if dims:
            from sh_platform.v1 import g3_sheet
            got, why = g3_sheet.got_by(plane, sow, b["code"], b["period"], dims)
        else:
            got = _got(plane, sow, b["code"], b["period"])
        met = None if b["expected"] is None else got is not None and abs(got - b["expected"]) <= b["tolerance"] + 1e-9
        rows.append({"code": b["code"], "period": b["period"], "expected": b["expected"], "got": got, "tolerance": b["tolerance"], "met": met,
                     **({"row_id": b["row_id"], "label": ", ".join(dims.values())} if b.get("row_id") and dims else {}),
                     **({"why": why} if why else {})})
    path = plane.path("build", "verify", f"{iid}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, rows)
    _post(plane, iid, sow, [r for r in rows if r["met"] is not True])
    try:  # G4: a miss Flow cannot resolve is always raised to the approver
        from sh_platform.v1 import g4_deviations
        g4_deviations.raise_unresolved(plane, iid, sow, [r for r in rows if r["met"] is False and r["got"] is None])
    except Exception as e:  # noqa: BLE001
        log.warning("unresolved-miss comment skipped (%s)", type(e).__name__)
    return rows


def sign_block(plane, iid: str) -> str | None:
    """Why the build pack cannot be signed yet, or None: a benchmark not met (or not confirmed) unless the next load found it met, or its comment was answered by the addressee and resolved
    (an approved deviation alone proves nothing until the load is read again)."""
    rows = _read(plane.path("build", "verify", f"{iid}.json"), list)
    misses = [r for r in rows if isinstance(r, dict) and r.get("met") is not True]
    if not misses:
        return None
    sow, (_, mine) = _read(plane.path("intents", iid, "sow.json")), _mine(_p1(), plane, iid)
    names = {k.get("code"): k.get("name") or k.get("code") for k in sow.get("kpis") or [] if isinstance(k, dict)}
    done = {(c.get("line_ref"), c.get("text")) for c in mine if c.get("state") == "resolved" and c.get("answered_at")}
    left = [r for r in misses if (_ref(r), _text(r, names.get(r["code"], r["code"]))) not in done]
    try:  # G4: a deviation awaiting approval (or approved but not made) blocks
        from sh_platform.v1 import g4_deviations
        pend = g4_deviations.pending_block(plane, iid)
    except Exception:  # noqa: BLE001
        pend = None
    if not left:
        return pend
    return (f"{len(left)} figure{'s' if len(left) > 1 else ''} not yet matched to the benchmark ({', '.join(r['code'] for r in left)}). "
            "The intent raiser or the sponsor must answer the comment on each, and the signer resolve it, before the build pack is signed." + (f" {pend}" if pend else ""))


def sign(plane, iid: str, by: str) -> dict:
    """The build pack signed by the head of data or the builder (P1 marks it; the project becomes built). Refused (ValueError, a plain
    sentence) while a benchmark miss has no answered comment, or while a comment addressed to the signer is open."""
    P = _p1()
    if P is None:
        raise ValueError("Projects are not available yet, so the build pack cannot be signed.")
    if not plane.path("build", "verify", f"{iid}.json").is_file():
        raise ValueError("Flow has not checked the loaded figures against the benchmarks yet. Run a load first.")
    block = sign_block(plane, iid) or P.sign_block(plane, iid, ARTEFACT, by)
    if block:
        raise ValueError(block)
    rec = P.signed(plane, iid, ARTEFACT, by)
    return P.set_stage(plane, rec["id"], "built")
