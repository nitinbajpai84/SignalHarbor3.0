"""C5 "Connect an API": scheduled pulls of public outside series (rates, yields, index proxies, news) into market_observations.

Fixed providers only: each has ONE hard-coded host and a catalogue of series ids, so a user can never point a pull at another address
(no SSRF) and only public series ids leave. The generic "any REST API" option is left out on purpose. Every call goes through
ops.Gate (company internet switch, host allowlist, log line before the call). Keys are read by environment variable NAME at the moment
of the call; they never enter a spec, a log, a response or an error text. No model is called here.
Outside material is data: text is stripped of tags and control characters and never read as an instruction.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.policy import EgressPolicy
from sh_platform.jsonfile import write_json_atomic
from sh_platform.v1 import wh
from sh_platform.v1.c5_connect import ops
from sh_platform.v1.c5_connect.kinds import ConnectorError

log = logging.getLogger(__name__)
TIMEOUT = 10.0          # seconds per call
TRIES = 3               # one call plus two retries (a provider that stalls once answers a minute later)
MAX_BYTES = 1_000_000   # a reply larger than this is refused, never read to the end
DAYS = 30
AT = "05:30"            # default pull time, before the 06:00 run
NEWS_KEEP = 50
STATUS = "outside_live_api"  # market_observations.quality_status of every row written here: the outside + live marker

_FX = "fx"


def _s(label, key, kind, **more):
    return {"label": label, "key": key, "kind": kind, **more}


PROVIDERS: dict[str, dict] = {
    "frankfurter": {
        "name": "Frankfurter (ECB reference rates)", "host": "api.frankfurter.dev", "key_env": None, "blurb": "exchange rates, no key needed",
        "series": {
            "USD/SGD": _s("US dollar in Singapore dollars", "FX:USDSGD:ECB", _FX, base="USD", quote="SGD"),
            "EUR/USD": _s("Euro in US dollars", "FX:EURUSD:ECB", _FX, base="EUR", quote="USD"),
            "EUR/SGD": _s("Euro in Singapore dollars", "FX:EURSGD:ECB", _FX, base="EUR", quote="SGD"),
            "GBP/USD": _s("Pound in US dollars", "FX:GBPUSD:ECB", _FX, base="GBP", quote="USD"),
        }},
    "fred": {
        "name": "FRED (St. Louis Fed)", "host": "api.stlouisfed.org", "key_env": "FRED_API_KEY", "blurb": "yields and macro series, free key",
        "series": {
            "DGS10": _s("US 10-year Treasury yield, percent", "YLD:US10Y:FRED", "yield"),
            "DGS2": _s("US 2-year Treasury yield, percent", "YLD:US2Y:FRED", "yield"),
            "DEXSIUS": _s("Singapore dollars per US dollar, daily (Federal Reserve H.10)", "FX:USDSGD:FRED_H10", _FX, base="USD", quote="SGD"),
            "FPCPITOTLZGSGP": _s("Singapore consumer price inflation, percent a year (World Bank)", "MAC:SGCPI:FRED", "macro"),
        }},
    "finnhub": {
        "name": "Finnhub", "host": "finnhub.io", "key_env": "FINNHUB_API_KEY", "blurb": "index proxies and market news, key",
        "series": {
            "ACWI": _s("Global equities proxy (iShares MSCI ACWI ETF)", "IDX:ACWI:FINNHUB", "index_level", base="USD"),
            "AGG": _s("Bonds proxy (iShares Core US Aggregate Bond ETF)", "IDX:AGG:FINNHUB", "index_level", base="USD"),
            "EWS": _s("Singapore equities proxy (iShares MSCI Singapore ETF); the Straits Times Index itself is licensed", "IDX:EWS:FINNHUB",
                      "index_level", base="USD"),
            "news": _s("Market news headlines (never a figure)", "", "news"),
        }},
    "mas": {
        "name": "MAS (Singapore Government Securities)", "host": "eservices.mas.gov.sg", "key_env": None, "blurb": "SGS auction yields, no key needed",
        "series": {f"SGS{t}Y": _s(f"Singapore Government bond {t}-year, auction cut-off yield, percent", f"YLD:SGS{t}Y:MAS_AUCTION", "yield", tenor=t)
                   for t in (2, 5, 10, 15, 20, 30)}},
}
_HHMM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
_TAG = re.compile(r"<[^>]*>")
_CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_KEYQ = re.compile(r"(api_key=)[^&\s\"']+")


class _NoKey(logging.Filter):
    """httpx logs every request address at INFO, and FRED's key rides in the address: mask it before any handler sees the line."""
    def filter(self, r):
        m = r.getMessage()
        if "api_key=" in m:
            r.msg, r.args = _KEYQ.sub(r"\1***", m), None
        return True


logging.getLogger("httpx").addFilter(_NoKey())


def clean_text(x, n: int) -> str:
    """Outside text as plain words: tags and control characters gone, spaces collapsed, cut to n characters."""
    return " ".join(_CTRL.sub(" ", _TAG.sub(" ", html.unescape(str(x or "")))).split())[:n]


def key_status(provider: str) -> dict:
    name = PROVIDERS[provider]["key_env"]
    return {"needs_key": bool(name), "key_env": name, "key_set": bool(name and os.environ.get(name))}


def catalogue() -> list[dict]:
    return [{"id": p, "name": v["name"], "host": v["host"], "blurb": v["blurb"], **key_status(p),
             "series": [{"id": i, "label": s["label"], "kind": s["kind"]} for i, s in v["series"].items()]} for p, v in PROVIDERS.items()]


def clean_spec(raw: dict, cid: str) -> dict:
    """Validate an API spec (called from spec.clean). Series must come from the provider's catalogue; the host is never taken from the caller."""
    from sh_platform.v1 import e0c_landing as L
    prov = raw.get("provider")
    if prov not in PROVIDERS:
        raise L.Refused("Choose one of the listed providers.")
    cat = PROVIDERS[prov]["series"]
    series = raw.get("series")
    if not isinstance(series, list) or not series or len(series) > len(cat) or not all(isinstance(s, str) and s in cat for s in series):
        raise L.Refused("Choose what to pull from the provider's list.")
    sched = raw.get("schedule", "daily")
    at = str(raw.get("at") or AT)
    if sched not in ("daily", "manual") or not _HHMM.fullmatch(at):
        raise L.Refused("The schedule must be daily (with a time such as 05:30) or manual.")
    return {"id": cid, "kind": "api", "provider": prov, "host": PROVIDERS[prov]["host"], "schedule": sched, "at": at,
            "source_code": f"api_{prov}", "credentials": {}, "params": {}, "file_pattern": "", "series": sorted(set(series), key=series.index)}


# ---- the one HTTP function (tests pass F["api_http"])
def _bounded_get(url: str, headers: dict) -> tuple[int, bytes]:
    import httpx
    with httpx.stream("GET", url, headers=headers, timeout=TIMEOUT, follow_redirects=False) as r:
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise ConnectorError("too_large", "The provider's reply was larger than allowed, so it was not read.")
        return r.status_code, bytes(buf)


def allow_host(plane, host: str) -> None:
    """Add one of the fixed provider hosts to the company's allowed list. The internet switch itself is never touched."""
    pol = EgressPolicy(plane)
    if host in {p["host"] for p in PROVIDERS.values()} and host not in pol.internet_hosts():
        pol.set_internet_hosts([*pol.internet_hosts(), host])


class _Client:
    def __init__(self, plane, provider: str, F):
        self.p, self.prov, self.gate = PROVIDERS[provider], provider, ops.Gate(plane)
        self.http = (F or {}).get("api_http") or _bounded_get
        name = self.p["key_env"]
        self.key = (os.environ.get(name) or "").strip().strip("\"'") or None if name else None  # a pasted key often carries a space, a newline or quotes
        if name and not self.key:
            raise ConnectorError("missing_credential", f"{self.p['name'].split(' (')[0]} needs a key, and {name} is not set on the server yet. "
                                 "Ask the administrator to store it under that name.")

    def get(self, path: str, params: dict):
        headers = {"Accept": "application/json", "User-Agent": "SignalHarbor/1.0 (+python-httpx)"}  # FRED stalls on agents naming only SignalHarbor or containing "test"
        q = dict(params)
        if self.key:
            if self.prov == "fred":
                q["api_key"] = self.key
            else:
                headers["X-Finnhub-Token"] = self.key
        url = f"https://{self.p['host']}{path}?{urlencode(q)}"
        for attempt in range(TRIES):
            try:
                st, raw = self.gate.call("api", self.p["host"], lambda: self.http(url, headers))
            except EgressBlocked:
                raise
            except ConnectorError:
                raise
            except Exception as e:  # noqa: BLE001 - a timeout or reset: type only, the text could carry the URL
                log.warning("api call failed: %s", type(e).__name__)
                st, raw = 0, b""
            if st == 200:
                break
            if st in (400, 401, 403) and self.key:
                raise ConnectorError("key_refused", f"{self.p['name'].split(' (')[0]} did not accept the key stored as {self.p['key_env']}. Ask the administrator to check it.")
            if st in (0, 429, 500, 502, 503, 504) and attempt < TRIES - 1:
                time.sleep(0.5 * 2 ** attempt)
                continue
            raise ConnectorError("no_answer", "The provider did not answer. It will be tried again at the next run." if st in (0, 429, 500, 502, 503, 504)
                                 else f"The provider answered with status {st}.")
        try:
            return json.loads(raw)
        except ValueError:
            raise ConnectorError("bad_reply", "The provider's reply was not in the expected shape.") from None


def _dec(x):
    try:
        v = Decimal(str(x))
        return v if v.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _row(s, series_id, d, v):
    return {"series": series_id, "series_key": s["key"], "label": s["label"], "type": s["kind"], "date": d, "value": v,
            "base": s.get("base"), "quote": s.get("quote")}


def _pull_frankfurter(c: _Client, ids, today):
    out = []
    for sid in ids:
        s = c.p["series"][sid]
        j = c.get(f"/v1/{today - timedelta(days=DAYS)}..", {"base": s["base"], "symbols": s["quote"]})
        for d, r in sorted((j.get("rates") or {}).items()):
            v = _dec((r or {}).get(s["quote"]))
            if v is not None:
                out.append(_row(s, sid, date.fromisoformat(d), v))
    return out, []


def _pull_fred(c: _Client, ids, today):
    out = []
    for sid in ids:
        s = c.p["series"][sid]
        start = today - timedelta(days=DAYS if s["kind"] != "macro" else 800)  # annual series: the last two or so years
        j = c.get("/fred/series/observations", {"series_id": sid, "file_type": "json", "observation_start": start.isoformat()})
        for o in j.get("observations") or []:
            v = _dec(o.get("value"))  # "." is FRED's "no value"
            if v is not None:
                out.append(_row(s, sid, date.fromisoformat(o["date"]), v))
    return out, []


def _pull_finnhub(c: _Client, ids, today):
    out, news = [], []
    for sid in ids:
        s = c.p["series"][sid]
        if s["kind"] == "news":
            for n in (c.get("/api/v1/news", {"category": "general"}) or [])[:10]:
                title = clean_text(n.get("headline"), 200)
                if title and isinstance(n.get("datetime"), int):
                    news.append({"id": "news-" + hashlib.sha1(f"finnhub|{n.get('id') or title}".encode()).hexdigest()[:12], "title": title,
                                 "summary": clean_text(n.get("summary"), 600), "measures": [], "kind": "news", "live_api": True, "outside": True,
                                 "source": f"Finnhub · {clean_text(n.get('source'), 40) or 'news'}",
                                 "date": datetime.fromtimestamp(n["datetime"], timezone.utc).date().isoformat()})
            continue
        j = c.get("/api/v1/quote", {"symbol": sid})
        v, t = _dec(j.get("c")), j.get("t")
        if v is not None and v > 0 and isinstance(t, int) and t > 0:  # t=0 / c=0 is Finnhub's answer for an unknown symbol
            out.append(_row(s, sid, datetime.fromtimestamp(t, timezone.utc).date(), v))
    return out, news


def _pull_mas(c: _Client, ids, today):
    out = []
    for sid in ids:
        s = c.p["series"][sid]
        j = c.get("/statistics/api/v1/bondsandbills/m/listbondsandbills", {"sort": "auction_date desc", "filters": f"auction_tenor:{s['tenor']}"})
        for r in (j.get("result") or {}).get("records") or []:
            v = _dec(r.get("cutoff_yield"))
            if v is not None and v > 0 and r.get("bill_bond_ind") == "bond":  # an announced, not yet held auction has yield 0
                out.append(_row(s, sid, date.fromisoformat(r["auction_date"]), v))
    return out, []


_PULL = {"frankfurter": _pull_frankfurter, "fred": _pull_fred, "finnhub": _pull_finnhub, "mas": _pull_mas}


def collect(plane, spec, F=None, today: date | None = None) -> tuple[list[dict], list[dict], float]:
    """Fetch the chosen series. Returns (rows, news, seconds). Nothing is written."""
    t0 = time.monotonic()
    c = _Client(plane, spec["provider"], F)
    rows, news = _PULL[spec["provider"]](c, spec["series"], today or wh.today(plane))
    return rows, news, time.monotonic() - t0


# ---- test (read only, nothing is written)
def test(plane, spec, F=None) -> dict:
    try:
        allow_host(plane, spec["host"])
        rows, news, secs = collect(plane, spec, F)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, **ops._explain(e)}
    latest: dict[str, dict] = {}
    for r in rows:
        if r["series"] not in latest or r["date"] > latest[r["series"]]["date"]:
            latest[r["series"]] = r
    shown = [{"series": k, "date": v["date"].isoformat(), "value": f"{v['value'].normalize():f}"} for k, v in latest.items()]
    n = len(latest)
    msg = f"Connected in {secs:.1f} s. {n} series" + (f", up to {DAYS} days each" if n else "") + (f", {len(news)} headlines" if news else "") + "."
    if not rows and not news:
        return {"ok": False, "code": "empty", "message": "The provider answered but returned no values for those series."}
    return {"ok": True, "message": msg, "seconds": round(secs, 2), "rows": shown, "headlines": [n["title"] for n in news[:3]]}


# ---- write: warehouse rows (outside, live) and news
def _system(con, org: str, provider: str) -> str:
    code = f"api_{provider}"
    r = con.execute("select id from source_systems where organization_id = ? and source_code = ?", [org, code]).fetchone()
    if r:
        return r[0]
    sid = wh.new_id()
    con.execute("insert into source_systems (id, organization_id, source_code, source_name, source_type, connection_method, licence_scope, "
                "permitted_use, expected_cadence, is_active) values (?,?,?,?,?,?,?,?,?,true)",
                [sid, org, code, PROVIDERS[provider]["name"], "api", "live_api", "outside public data", "context only", "daily"])
    return sid


def write_rows(plane, provider: str, rows: list[dict]) -> int:
    """Append new outside observations. A row already known with the same value is skipped; a changed value supersedes it."""
    from sh_platform.v1 import e1_write
    if not rows:
        return 0
    org, now, host = e1_write.org_id(plane), wh.now(plane), PROVIDERS[provider]["host"]
    obs, sups, batch = [], [], None
    with wh.connect(plane) as con:
        sid = _system(con, org, provider)
        for r in rows:
            at = datetime(r["date"].year, r["date"].month, r["date"].day, tzinfo=timezone.utc)
            old = con.execute("select t.id, t.value from market_observations t where t.series_key = ? and t.observed_at = ? and not exists "
                              "(select 1 from market_observations n where n.supersedes_observation_id = t.id)", [r["series_key"], at]).fetchone()
            if old and Decimal(str(old[1])) == r["value"]:
                continue
            if batch is None:
                batch = wh.new_id()
                latest = max(x["date"] for x in rows)
                con.execute("insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, loaded_at, source_period_end, "
                            "storage_uri, validation_status, validation_summary) values (?,?,?,?,?,?,?,?,?,?)",
                            [batch, org, sid, f"{PROVIDERS[provider]['name']} {latest.isoformat()} {uuid.uuid4().hex[:6]}", now, now, latest,
                             f"https://{host}/", "loaded", "Public series from a live API. Outside material."])
            rid = wh.new_id()
            ext = f"{r['series_key']}@{r['date'].isoformat()}"
            con.execute("insert into source_records (id, organization_id, source_batch_id, external_record_id, record_type, effective_at, received_at, "
                        "recorded_at, raw_payload_uri, content_hash, quality_status) values (?,?,?,?,?,?,?,?,?,?,?)",
                        [rid, org, batch, ext, "market_observations", at, now, now, f"https://{host}/#{r['series']}",
                         hashlib.sha256(f"{ext}|{r['value']}".encode()).hexdigest(), "loaded"])
            obs.append({"source_record_id": rid, "series_key": r["series_key"], "observation_type": r["type"], "observed_at": at, "received_at": now,
                        "value": r["value"], "base_currency": r["base"], "quote_currency": r["quote"], "quality_status": STATUS})
            sups.append(old[0] if old else None)
            if old:  # a correction inherits its subject from the row it replaces (series and observed time)
                obs[-1].update(series_key=None, observed_at=None)
    if not obs:
        return 0
    try:
        return len(e1_write.record_many(plane, "market_observations", obs, sups))
    except Exception:
        with wh.connect(plane) as con:
            con.execute("update source_batches set validation_status = 'quarantined' where id = ?", [batch])
        raise


def write_news(plane, news: list[dict]) -> int:
    from sh_platform.consume import market_store
    return market_store.add_news(plane, news, NEWS_KEEP) if news else 0


def markers(plane) -> list[dict]:
    """The newest value of every series written by an API pull, with what Consume must show: provider, observed date, outside, live.
    A series that also came in a file keeps its file rows; these are only the live ones."""
    labels = {s["key"]: s["label"] for p in PROVIDERS.values() for s in p["series"].values() if s["key"]}
    with wh.connect(plane, read_only=True) as con:
        rows = con.execute(
            "select o.series_key, o.observation_type, o.value, o.observed_at, sy.source_name, sy.source_code from market_observations o "
            "join source_records r on r.id = o.source_record_id join source_batches b on b.id = r.source_batch_id "
            "join source_systems sy on sy.id = b.source_system_id where sy.connection_method = 'live_api' and not exists "
            "(select 1 from market_observations n where n.supersedes_observation_id = o.id) "
            "qualify row_number() over (partition by o.series_key order by o.observed_at desc) = 1 order by o.series_key").fetchall()
    return [{"series_key": k, "label": labels.get(k, k), "kind": t, "value": str(v), "observed_date": at.date().isoformat(), "provider": name,
             "source_code": code, "outside": True, "live": True, "marker": f"LIVE API · {name.split(' (')[0]} · {at.date().isoformat()}"}
            for k, t, v, at, name, code in rows]


def pull(plane, spec, F=None) -> dict:
    """The scheduled pull (and Fetch now): fetch, write, record the run in the same run file the file connectors use."""
    with ops._LOCK:
        run, now = ops._run(plane, spec["id"]), wh.now().isoformat()
        wrote = 0
        try:
            allow_host(plane, spec["host"])
            rows, news, _ = collect(plane, spec, F)
            wrote = write_rows(plane, spec["provider"], rows) + write_news(plane, news)
            run.update(status="ok", error=None, last_ok=now, last_files=wrote, last_seen=len(rows) + len(news), last_skipped=0,
                       landed_total=run["landed_total"] + wrote)
        except Exception as e:  # noqa: BLE001
            run.update(status="failed", error=ops._explain(e), last_files=0)
        run["last_run"] = now
        write_json_atomic(ops._runs_path(plane, spec["id"]), run)
        return {"status": run["status"], "error": run["error"], "landed": run["last_files"], "seen": run.get("last_seen", 0), "duplicates": 0, "skipped": 0}


def is_due(spec: dict, last_run: str | None, now: datetime | None = None) -> bool:
    """Daily at spec['at'] (server clock, like the pipeline scheduler): due when that slot has passed and no run has started since."""
    from sh_platform.v1 import b6_schedule
    if spec.get("schedule") != "daily":
        return False
    now = now or datetime.now()
    slot = b6_schedule.last_slot({"freq": "daily", "at": spec.get("at") or AT}, now)
    last = datetime.fromisoformat(last_run).astimezone().replace(tzinfo=None) if last_run else None
    return slot is not None and (last is None or last < slot)
