"""A19: `GET /api/company/market`, the industry pack briefs as outside material, plus public briefs fetched through the egress gateway when
internet is on for the company, plus briefs the company admin added. Each brief lists the company's measures that left their range in its month.
Shape: docs/plan/SHAPES.md section 7. A measure is "touched" when the brief's front matter `measures:` lists it, or the pack's
measure code or name (kpi_tree.yaml) appears in its text as a whole word."""
import logging
import re
import uuid
from datetime import datetime, timezone

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sh_platform.consume import feeds, market_store
from sh_platform.control.api import _settings
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.gateway import EgressGateway
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.vault import NameVault
from sh_platform.profile.api import _name, _plane, _viewer

log = logging.getLogger(__name__)
router = APIRouter()
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _measures(pack) -> list[dict]:
    try:
        rows = (pack.section("kpi_tree") or {}).get("kpis") or []
    except KeyError:
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("id")]


def _plain(text: str) -> str:
    """Brief text as plain sentences: list markers and emphasis marks dropped, a spaced double hyphen read as a colon."""
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M).replace("**", "")
    return " ".join(text.replace(" -- ", ": ").split())


def _brief(path, label: str, kpis: list[dict]) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = _FRONT.match(text)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            log.warning("bad front matter in %s", path.name)
        text = text[m.end():]
    body = _COMMENT.sub("", text).strip()
    title = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ")), path.stem)
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.startswith("#") and not p.startswith("Dated:")]
    listed = {str(x) for x in (meta.get("measures") or [])} if isinstance(meta, dict) else set()
    hit = [k["id"] for k in kpis if k["id"] in listed
           or any(re.search(rf"(?<!\w){re.escape(str(t))}(?!\w)", body, re.I) for t in (k["id"], k.get("name")) if t)]
    return {"id": path.stem, "title": _plain(title), "summary": _plain(paras[0]) if paras else "", "measures": hit, "names": {k["id"]: k.get("name") for k in kpis if k["id"] in hit},
            "source": str(meta.get("source") or label) if isinstance(meta, dict) else label, "outside": True,
            "date": (re.search(r"^Dated:\s*(\d{4}-\d{2}-\d{2})", body, re.M) or [None, None])[1]}


def briefs_for(loader, industry: str | None) -> list[dict]:
    if not industry:
        return []
    pack = loader.load(industry)
    if pack.empty:
        return []
    folder = loader.root / pack.industry / str(pack.version) / "market_briefs"
    kpis = _measures(pack)
    label = f"{pack.label} pack, version {pack.version}"
    return [_brief(p, label, kpis) for p in sorted(folder.glob("*.md"))] if folder.is_dir() else []


def _fetch(plane, loader, industry, gateway, module_id: str, now: datetime) -> dict:
    """Public briefs from the pack's market_sources.yaml `url` entries, through the gateway, cached a day. Query text is public terms only."""
    cached = market_store.cached_fetch(plane, now)
    if cached:
        return cached
    pack = loader.load(industry) if industry else None
    try:
        sources = ((pack.section("market_sources") or {}).get("sources") or []) if pack else []
    except KeyError:
        sources = []
    out = []
    for s in sources:
        if not (isinstance(s, dict) and s.get("url") and s.get("name")):
            continue
        q = f"Latest public market brief on {s.get('covers') or s['name']} from {s['name']}"
        try:
            text = gateway.internet_query(module_id, str(s["url"]), q).text
        except EgressBlocked as e:
            log.info("A market brief was not fetched (%s).", e.reason_code)
            continue
        out.append({"id": "web-" + re.sub(r"\W+", "-", str(s["name"]).lower()), "title": str(s["name"]), "summary": " ".join(text.split())[:600],
                    "measures": [], "source": str(s["name"]), "outside": True, "fetched": True, "date": now.date().isoformat()})
    return market_store.save_fetch(plane, out, now) if out else {"at": now.isoformat(), "briefs": []}


def _moved(feed: list[dict]) -> list[dict]:
    return [{"code": m["code"], "name": m["name"], "month": m["latest"]["period"][:7]}
            for m in feed if m.get("range_break") and m.get("latest")]


def _latest_move(m: dict | None) -> dict | None:
    """The newest step of a measure's trend (shape 6): period, from, to, change in percent (None when the earlier value is zero)."""
    t = (m or {}).get("trend") or []
    if len(t) < 2:
        return None
    a, b = t[-2], t[-1]
    pct = round((b["value"] - a["value"]) / abs(a["value"]) * 100, 1) if a["value"] else None
    return {"period": b["period"], "from": a["value"], "to": b["value"], "change_pct": pct}


def market_doc(plane, viewer, loader, industry, *, internet: bool, gateway=None, module_id: str = "market",
               names=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    briefs = briefs_for(loader, industry)
    doc: dict = {"internet": internet}
    if internet and gateway is not None:
        f = _fetch(plane, loader, industry, gateway, module_id, now)
        briefs += f["briefs"]
        doc["fetched_at"] = f["at"]
    else:
        doc["internet_line"] = "Internet is off for this company, so only the pack's briefs are shown."
    briefs += market_store.read(plane).get("added", [])
    feed = feeds.build(plane, viewer, names)["measures"]
    by_code = {str(m["code"]).upper(): m for m in feed}
    moved = _moved(feed)
    latest = max((m["month"] for m in moved), default="")
    for b in briefs:
        month = str(b.get("date") or "")[:7]
        # a brief newer than the newest figures sits beside the latest month that has a measure out of range
        pick = month if any(m["month"] == month for m in moved) else latest
        b["moved"] = [{"code": m["code"], "name": m["name"]} for m in moved if m["month"] == pick]
        b["moved_month"] = pick or None
        b["measure_moves"] = [{"code": c, "name": (by_code.get(c.upper()) or {}).get("name") or (b.get("names") or {}).get(c) or c, "latest_move": _latest_move(by_code.get(c.upper()))}
                              for c in b.get("measures", [])]
    doc["briefs"] = briefs
    return doc


def _gateway(request: Request, plane):
    g = getattr(request.app.state, "market_gateway", None)  # tests plug a stub in here
    if g is not None:
        return g

    def no_model(url, body):
        raise EgressBlocked("transport_failed")  # this gateway carries internet queries only
    return EgressGateway(plane, NameVault(plane), EgressPolicy(plane, request.app.state.settings.egress_default),
                         model_allowlist=[], transport=no_model)


@router.get("/api/company/market")
def get_api_company_market(request: Request):
    plane = _plane(request)
    st = request.app.state
    rec = st.entitlements.company(request.state.company_id) or {}
    on = bool(_settings(request, plane)["egress"]["internet"])
    mods = st.entitlements.enabled_modules(request.state.company_id)
    return market_doc(plane, _viewer(request), st.packs, rec.get("industry"), internet=on,
                      gateway=_gateway(request, plane) if on else None, module_id=mods[0] if mods else "market",
                      names=feeds._pack_names(request))


@router.post("/api/company/market/briefs")
async def post_api_company_market_briefs(request: Request):
    if "company_admin" not in (request.state.roles or []):
        return JSONResponse({"detail": "Only the company admin can add a brief."}, status_code=403)
    try:
        body = await request.json()
    except ValueError:
        body = None
    body = body if isinstance(body, dict) else {}
    title, text, measures = body.get("title"), body.get("text"), body.get("measures", [])
    if not (isinstance(title, str) and title.strip() and isinstance(text, str) and text.strip()
            and isinstance(measures, list) and all(isinstance(m, str) for m in measures)):
        return JSONResponse({"detail": "Send a title, the text and, optionally, a list of measure codes."}, status_code=422)
    return add_brief(_plane(request), title, text, measures, _name(request))


def add_brief(plane, title: str, text: str, measures: list[str], by: str) -> dict:
    now = datetime.now(timezone.utc)
    return market_store.add(plane, {"id": "added-" + uuid.uuid4().hex[:8], "title": title.strip()[:200], "summary": text.strip()[:4000],
                                    "measures": [m.strip() for m in measures if m.strip()], "source": f"added by {by}", "outside": True,
                                    "added_by": by, "date": now.date().isoformat()})
