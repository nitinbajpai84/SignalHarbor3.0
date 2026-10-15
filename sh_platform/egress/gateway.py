"""Guard 4: the egress gateway, the only exit. Every attempt is logged, never with content.

Order for a model prompt: destination and URL checks, structure checks, tokenise each string,
check the decoded strings AND the serialised body (vault names, raw rows, suppressed figures,
size), write the log line (and fsync), send, map the reply back. Anything refused raises
EgressBlocked before the transport is touched. If the log line cannot be written nothing is sent.
If the transport then fails, a second line with decision "failed" and the same sha256 follows.

Two transports, on purpose: `transport` carries model prompts (it may attach the provider key,
and only to model hosts); `internet_transport` carries internet queries and never has a
credential. The real transports here are a thin httpx envelope of the gateway's own: provider
adapters (message formats of a given provider) are phase 2 and sit on top of it.
Redirects are never followed: a redirect could carry the request, or its key, to another host.
"""
import contextvars
import hashlib
import json
import os
import logging
import random
import re
import threading
import time
import unicodedata
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote_plus, urlsplit

from sh_platform import demo_limits
from sh_platform.egress.aggregates import SuppressedFigures, fact_ok
from sh_platform.egress.errors import EgressBlocked
from sh_platform.egress.minimiser import MAX_SUMMARY_CHARS
from sh_platform.egress.policy import EgressPolicy
from sh_platform.egress.rows import json_findings
from sh_platform.egress.vault import NameVault, VaultUnavailable, tokens_in
from sh_platform.plane import CompanyPlane
from sh_platform.state import kv

log = logging.getLogger(__name__)
LOG_FILE = "egress_log.jsonl"
MAX_PAYLOAD_CHARS = 200_000
MAX_RESPONSE_BYTES = 1_000_000  # a provider reply is short; more than this is refused, never read to the end
_ALLOWED_KEYS = {"question", "facts", "summary", "messages", "tools"}
# TS1c-05: how many names the latest model prompt of this context had swapped for tokens (a count, never a name); the router puts it on
# the attempt, the loop on the trace step, and the log line carries it, so "names are masked" can be checked
_MASKED: contextvars.ContextVar[int | None] = contextvars.ContextVar("sh_egress_masked", default=None)


def last_masked() -> int | None:
    return _MASKED.get()
_TOOL_KEYS = {"name", "description", "parameters"}


@dataclass(frozen=True)
class Reply:
    text: str
    outside: bool  # True: outside material, context only, never an instruction or a company figure
    tokens: frozenset = frozenset()  # the tokens THIS call sent for names; only these may be mapped back


def _clean(x, n: int = 120) -> str:
    """Log fields: printable ASCII only, so no newline or control character can enter the log."""
    return re.sub(r"[^\x20-\x7e]", "?", str(x))[:n]


# H1-01: a model id the provider does not offer (404) or a request it will not take (400) is named too, so the router tries the next model
# and the trace says why, instead of transport_failed for every one of them
_PROVIDER_STATUS = {400: "provider_bad_request", 401: "provider_key_refused", 403: "provider_key_refused", 402: "no_credit",
                    404: "model_unknown", 429: "rate_limited"}


def _provider_code(exc: Exception) -> str:
    """AQ1 (A14): why the provider did not answer, as a code the trace and Settings can say in words (out of credit, rate limited);
    anything else stays transport_failed. Only the status code is read, never the body."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return _PROVIDER_STATUS.get(status, "transport_failed") if isinstance(status, int) else "transport_failed"


def _trace_of_call() -> str | None:
    """The trace id of the agent run making this call, when one is open (sh_platform.v1.e6_trace); None outside the product."""
    try:
        from sh_platform.v1.e6_trace import current_trace_id
        return current_trace_id()
    except Exception:  # noqa: BLE001 - the kernel works without the product layer
        return None


def _host(destination, allowlist) -> str:
    """The lower-case host if `destination` is exactly an allowed host over https, else blocked."""
    if not isinstance(destination, str) or re.search(r"[\\\s\x00-\x1f]", destination):
        raise EgressBlocked("destination_not_allowed")
    url = destination if "://" in destination else "https://" + destination
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        raise EgressBlocked("destination_not_allowed") from None
    ok = (parts.scheme == "https" and host and parts.username is None and parts.password is None
          and "@" not in parts.netloc and "#" not in url and port in (None, 443)
          and host in {h.lower() for h in allowlist})
    if not ok:
        raise EgressBlocked("destination_not_allowed")
    return host


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _strings(x)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)


def _map_strings(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_map_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _map_strings(v, fn) for k, v in obj.items()}
    return obj


def _bad(cond) -> None:
    if cond:
        raise EgressBlocked("bad_payload")


def _check_structure(payload, suppressed: SuppressedFigures) -> None:
    _bad(not isinstance(payload, dict))
    if not set(payload) <= _ALLOWED_KEYS:
        raise EgressBlocked("raw_rows")  # a key the minimiser did not pick: data it did not choose
    for k in ("question", "summary"):
        _bad(k in payload and not isinstance(payload[k], str))
    for k in ("facts", "messages", "tools"):
        _bad(k in payload and not isinstance(payload[k], list))
    for f in payload.get("facts", []):
        if not isinstance(f, dict) or "label" not in f or not set(f) <= {"label", "value", "group_size"}:
            raise EgressBlocked("raw_rows")  # a record, not a fact
        if not fact_ok(f):
            suppressed.add(f)
            raise EgressBlocked("suppressed_figure")  # no/small/odd group size, or odd value
    for m in payload.get("messages", []):
        _bad(not isinstance(m, dict))
        if set(m) != {"role", "content"}:
            raise EgressBlocked("raw_rows")
        _bad(not all(isinstance(v, str) for v in m.values()))
    for t in payload.get("tools", []):
        _bad(not isinstance(t, dict))
        if set(t) != _TOOL_KEYS:
            raise EgressBlocked("raw_rows")
        _bad(not (isinstance(t["name"], str) and isinstance(t["description"], str)
                  and isinstance(t["parameters"], list) and all(isinstance(p, str) for p in t["parameters"])))
    texts = list(_strings(payload))
    if sum(len(t) for t in texts) > MAX_PAYLOAD_CHARS:
        raise EgressBlocked("payload_too_large")
    summary = payload.get("summary")
    if isinstance(summary, str) and len(summary) > MAX_SUMMARY_CHARS:
        raise EgressBlocked("summary_too_long")
    # structural checks on JSON inside the free-text fields (see rows.py); table-shaped text is not detected
    scanned = ([payload.get("question"), summary] + [m["content"] for m in payload.get("messages", [])]
               + [t["description"] for t in payload.get("tools", [])])
    codes = []
    for s in scanned:
        if isinstance(s, str):
            code, bad = json_findings(s)
            for b in bad:
                suppressed.add_figures(b)  # the figure may not come back in later text either
            if code:
                codes.append(code)
    if codes:
        raise EgressBlocked("suppressed_figure" if "suppressed_figure" in codes else codes[0])


# set by the router around its own calls (it logs their cost itself); any other model call is logged by the gateway, so the
# public-demo daily cap sees every call exactly once
ROUTED = contextvars.ContextVar("sh_routed_call", default=False)
COST_LOG = "model_costs.jsonl"


class EgressGateway:
    def __init__(self, plane: CompanyPlane, vault: NameVault, policy: EgressPolicy, *,
                 model_allowlist, transport, internet_transport=None, model_url: str | None = None):
        if vault.plane.root != plane.root or policy.plane.root != plane.root:
            raise ValueError("vault, policy and gateway must belong to the same company plane")
        self._log_path = plane.area("context") / LOG_FILE
        self.vault, self.policy = vault, policy
        self.model_allowlist = list(model_allowlist)
        self.transport = transport
        # never fall back to the model transport: it may carry the provider key
        self.internet_transport = internet_transport or make_httpx_transport(None)
        self._model_url = model_url or (f"https://{self.model_allowlist[0]}" if self.model_allowlist else "")

    # -- log
    def _open_log(self):
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            return open(self._log_path, "a", encoding="utf-8")
        except OSError:
            raise EgressBlocked("log_unavailable") from None

    @staticmethod
    def _write(f, module_id, kind, host, decision, code, body: bytes, attempt: str = "", masked: int | None = None) -> None:
        line = {"attempt": attempt, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "module": _clean(module_id), "kind": kind,
                "host": _clean(host), "decision": decision, "reason_code": _clean(code),
                "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        if isinstance(masked, int):
            line["masked"] = masked  # TS1c-05: names swapped for tokens in this prompt (a count)
        trace = _trace_of_call()
        if trace:
            line["trace_id"] = _clean(trace, 64)  # SS-9: the entry is tied to the agent run that made it (an id, never content)
        try:
            f.write(json.dumps(line) + "\n")
            f.flush()
            os.fsync(f.fileno())
        except OSError:
            raise EgressBlocked("log_unavailable") from None

    def _check_url(self, url: str) -> None:
        """Path and query, decoded repeatedly (so %2520 is seen as a space), must not hold private
        content. Fragments never pass. The log keeps the host only."""
        url = url if "://" in url else "https://" + url
        parts = urlsplit(url)
        if parts.fragment:
            raise EgressBlocked("destination_not_allowed")
        for piece in (parts.path, parts.query):
            s = piece
            for _ in range(8):
                if self.vault.looks_private(s):
                    raise EgressBlocked("vault_name")
                d = unquote_plus(s)
                if d == s:
                    break
                s = d
            else:
                raise EgressBlocked("destination_not_allowed")  # encoded too deep to trust

    def _run(self, module_id, kind, destination, allowlist, transport, pre, prepare) -> str:
        f = self._open_log()
        host, box, logged, aid = "", {"body": b""}, False, uuid.uuid4().hex[:8]
        with f:
            try:
                try:
                    pre()
                    host = _host(destination, allowlist)
                    self._check_url(destination)
                    prepare(box)
                except EgressBlocked:
                    raise
                except VaultUnavailable:
                    raise EgressBlocked("vault_unavailable") from None
                except Exception:
                    raise EgressBlocked("bad_payload") from None
                body = box["body"]
                self._write(f, module_id, kind, host, "sent", "", body, aid, box.get("masked"))  # before the send
                logged = True
                url = destination if "://" in destination else "https://" + destination
                try:
                    return transport(url, body)
                except Exception as e:  # its text is not kept: it could echo the body
                    code = e.reason_code if isinstance(e, EgressBlocked) else _provider_code(e)
                    try:
                        self._write(f, module_id, kind, host, "failed", code, body, aid, box.get("masked"))
                    except EgressBlocked:
                        pass
                    raise EgressBlocked(code) from None
            except EgressBlocked as e:
                if not logged and e.reason_code != "log_unavailable":
                    self._write(f, module_id, kind, host, "blocked", e.reason_code, box["body"], aid, box.get("masked"))
                raise

    # -- model
    def send_model_prompt(self, module_id: str, payload: dict, suppressed: SuppressedFigures | None = None,
                          detokenise: bool = True) -> Reply:
        cost_log = self.vault.plane.area("context") / COST_LOG
        if demo_limits.over_cap(cost_log):  # every model path passes here, routed or not: nothing is sent once the day's cap is used
            raise EgressBlocked("daily_cap")
        if suppressed is None:
            suppressed = SuppressedFigures()
        sent: set = set()
        _MASKED.set(None)

        def prepare(box):
            _check_structure(payload, suppressed)
            safe = _map_strings(payload, self.vault.tokenise)
            # tokens this call put in place of names; a token the person typed is not one of them
            typed = set().union(*(tokens_in(unicodedata.normalize("NFKC", s)) for s in _strings(payload)))
            sent.update(set().union(*(tokens_in(s) for s in _strings(safe))) - typed)
            box["masked"] = len(sent)
            _MASKED.set(len(sent))
            # ensure_ascii off: the check must see real characters, not \uXXXX or \n escapes
            body = json.dumps(safe, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
            box["body"] = body
            if self.vault.contains_name("\n".join(_strings(safe))) or self.vault.contains_name(body.decode("utf-8")):
                raise EgressBlocked("vault_name")
            if suppressed.appears_in(body.decode("utf-8"), self.vault.known_tokens()):
                raise EgressBlocked("suppressed_figure")
        raw = self._run(module_id, "model", self._model_url, self.model_allowlist,
                        self.transport, lambda: None, prepare)
        tokens = frozenset(sent)
        if not ROUTED.get():
            _log_unrouted_cost(self.vault.plane, module_id, raw)
        return Reply(self.detokenise(raw, tokens) if detokenise else raw, outside=False, tokens=tokens)

    def detokenise(self, text: str, only=None) -> str:
        """Map tokens back, inside the plane (only those in `only` when given). Refuses (never returns tokens
        half-mapped) if the vault is unusable."""
        try:
            return self.vault.detokenise(text, only)
        except VaultUnavailable:
            raise EgressBlocked("vault_unavailable") from None

    # -- internet
    def internet_query(self, module_id: str, destination: str, query_text: str,
                       suppressed: SuppressedFigures | None = None) -> Reply:
        def pre():
            if not self.policy.is_internet_allowed(module_id):
                raise EgressBlocked("internet_off")

        def prepare(box):
            _bad(not isinstance(query_text, str))
            box["body"] = json.dumps({"query": query_text}, ensure_ascii=False).encode("utf-8")
            if self.vault.looks_private(query_text):
                raise EgressBlocked("vault_name")  # public terms only: never swapped, always refused
            if suppressed is not None and suppressed.appears_in(query_text + " | " + str(destination),
                                                                self.vault.known_tokens()):
                raise EgressBlocked("suppressed_figure")
        raw = self._run(module_id, "internet", destination, self.policy.internet_hosts(),
                        self.internet_transport, pre, prepare)
        return Reply(raw, outside=True)  # outside material: returned as is, never detokenised


def _log_unrouted_cost(plane, module_id: str, raw: str) -> None:
    """A model call that did not go through the router: its cost row (priced at the specialist tier when the model is unlisted)."""
    from sh_platform.v1.router import log_cost, price_usd  # lazy: the router imports this module
    try:
        d = json.loads(raw)
        used, model = d.get("usage") or {}, d.get("model")
    except (ValueError, AttributeError):
        used, model = {}, None
    tin, tout = used.get("tokens_in"), used.get("tokens_out")
    log_cost(plane, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": module_id, "model": model,
                     "tokens_in": tin, "tokens_out": tout, "routed": False, "cost_usd": price_usd(model, tin, tout, "specialist") or 0.0})


MODEL_TRIES = 3  # three tries in all: waits of about 1 s then 2 s between them (the schedule doubles: 1, 2, 4)
BACKOFF_BASE = 1.0
RETRY_AFTER_CAP = 8.0
TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})  # 501 (not implemented) never recovers
_call_slot = threading.BoundedSemaphore(2)  # process-wide: at most 2 model calls in flight (a room must not burst the quota)
_sleep = time.sleep  # tests replace this


_clock = time.monotonic  # tests replace this
BREAKER_SECONDS = 300.0
_breaker = kv.breaker_map(lambda: _clock())  # provider host -> (refusal code, when it may be tried again); a plain dict in simple mode, Redis in production
_BILLING_WORDS = ("credit", "billing", "insufficient", "quota", "key limit", "spend limit")
_RATE_WORDS = ("per minute", "retry", "rate limit")  # a quota message that names a short window is a passing rate limit


def billing_code(status: int, body: str = "") -> str | None:
    """The refusal code for a provider answer that retrying cannot fix (no credit, quota exhausted, key refused), else None."""
    if status == 402:
        return "no_credit"
    if status in (401, 403):
        return "provider_key_refused"
    b = body.lower()
    if status == 429 and any(w in b for w in _BILLING_WORDS) and not any(w in b for w in _RATE_WORDS):
        return "no_credit"
    return None


def _breaker_check(host: str) -> None:
    """Open breaker: refuse at once with the recorded code. After the window one trial call goes through (the window re-arms)."""
    hit = _breaker.get(host)
    if hit is None:
        return
    code, until = hit
    if _clock() < until:
        raise EgressBlocked(code)
    if hasattr(_breaker, "take_trial"):  # production: one trial across every process; the rest are refused until it re-arms or clears
        if not _breaker.take_trial(host, code, BREAKER_SECONDS):
            raise EgressBlocked(code)
        return
    _breaker[host] = (code, _clock() + BREAKER_SECONDS)  # ponytail: concurrent callers may all trial once; fine at this scale


def provider_down(host: str) -> str | None:
    """NM1: the refusal code (no_credit, provider_key_refused) while this provider's breaker is open, else None. Read-only: it never
    re-arms the window, so a caller can skip the whole prepare step (tokenising, vault reads) for a provider known to refuse."""
    hit = _breaker.get((host or "").lower())
    return hit[0] if hit and _clock() < hit[1] else None


def transient_cause(exc: Exception) -> str | None:
    """A short code for a failure worth retrying (429, 5xx, timeout, connection reset), else None. Never the body.
    A gateway refusal (EgressBlocked) is never transient."""
    import httpx
    if isinstance(exc, EgressBlocked):
        return None
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return f"http_{code}" if code in TRANSIENT_STATUS else None
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError)):
        return "connection"
    return None


def backoff_seconds(attempt: int, headers=None) -> float:
    """1 s, 2 s, 4 s with jitter; a numeric Retry-After wins, capped at RETRY_AFTER_CAP."""
    ra = (headers.get("retry-after") if headers is not None else None) or ""
    if ra.strip().isascii() and ra.strip().isdigit():  # "²" is a digit to isdigit() but not to float()
        return min(float(ra), RETRY_AFTER_CAP)
    return BACKOFF_BASE * 2 ** (attempt - 1) * random.uniform(1.0, 1.25)


def make_httpx_transport(api_key_env: str | None, header: str = "authorization", scheme: str = "Bearer",
                         client=None, timeout: float = 60.0, model_hosts=(), env=None, tries: int = 1):
    """A real transport. The key is read from the environment variable NAMED `api_key_env` at call
    time (from `env`, default the process environment) and attached ONLY when the destination host is in `model_hosts`; with `api_key_env=None`
    (the internet transport) no credential is ever added. The key is never logged, stored or
    returned. Redirects are not followed. A client made here is closed after each call.
    `tries` > 1 (the model transport) retries transient failures and holds the process-wide model call slot."""
    import httpx
    hosts = {h.lower() for h in model_hosts}
    slot = _call_slot if tries > 1 else nullcontext()

    def once(url: str, body: bytes) -> str:
        headers = {"content-type": "application/json"}
        if api_key_env and (urlsplit(url).hostname or "").lower() in hosts:
            key = ((os.environ if env is None else env).get(api_key_env) or "").strip()
            if not key:
                raise EgressBlocked("no_credential")
            headers[header] = f"{scheme} {key}" if scheme else key
        with (nullcontext(client) if client is not None
              else httpx.Client(timeout=timeout, follow_redirects=False)) as c:
            with c.stream("POST", url, content=body, headers=headers, follow_redirects=False) as resp:
                if tries > 1 and resp.status_code >= 400:
                    host = (urlsplit(url).hostname or "").lower()
                    head = b""
                    if resp.status_code == 429:  # bounded: a provider body is never read past 2000 bytes
                        for part in resp.iter_bytes():
                            head += part
                            if len(head) >= 2000:
                                break
                    code = billing_code(resp.status_code, head[:2000].decode("utf-8", errors="replace"))
                    if code:  # only the code is kept, never the body
                        _breaker[host] = (code, _clock() + BREAKER_SECONDS)
                        raise EgressBlocked(code)
                resp.raise_for_status()
                if tries > 1:
                    _breaker.pop((urlsplit(url).hostname or "").lower(), None)
                chunks, size = [], 0
                for part in resp.iter_bytes():
                    size += len(part)
                    if size > MAX_RESPONSE_BYTES:
                        raise EgressBlocked("transport_failed")  # too large: nothing of it is kept
                    chunks.append(part)
                return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")

    def send(url: str, body: bytes) -> str:
        """Up to `tries` tries; only a transient failure is retried (never an EgressBlocked refusal)."""
        if tries > 1:
            _breaker_check((urlsplit(url).hostname or "").lower())
        for attempt in range(1, tries + 1):
            try:
                with slot:  # held for the call only, never while waiting to retry
                    return once(url, body)
            except Exception as e:  # noqa: BLE001
                cause = transient_cause(e)
                if cause is None or attempt == tries:
                    raise
                wait = backoff_seconds(attempt, getattr(getattr(e, "response", None), "headers", None))
                log.warning("model call failed (%s); retry %d of %d in %.1fs", cause, attempt, tries - 1, wait)
                _sleep(wait)
    return send


def send_email(plane: CompanyPlane, addresses: list[str], subject: str, body: str) -> str:
    """The email exit: recipient domains on the company's list, names tokenised, nothing sent if a vault name or a raw
    record is still in it. Logged with the seven fields, never the text. Returns "sent" or "kept in the outbox"."""
    from sh_platform.egress import email as mail
    from sh_platform.egress.policy import EgressPolicy
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[], transport=None)
    f, box, aid, host = gw._open_log(), {"body": b""}, uuid.uuid4().hex[:8], ""
    with f:
        try:
            try:
                _bad(not (isinstance(addresses, list) and addresses and all(isinstance(a, str) for a in addresses)
                          and isinstance(subject, str) and isinstance(body, str)))
                domains = sorted({a.rsplit("@", 1)[-1].lower() for a in addresses})
                host = ",".join(domains)
                if not all("@" in a and not re.search(r"[\s\x00-\x1f,;<>]", a) for a in addresses) \
                        or not set(domains) <= mail.allowed_domains(plane):
                    raise EgressBlocked("destination_not_allowed")
                safe = {"subject": gw.vault.tokenise(subject), "body": gw.vault.tokenise(body)}
                text = "\n".join(safe.values())
                box["body"] = json.dumps(safe, sort_keys=True, ensure_ascii=False).encode("utf-8")
                if gw.vault.contains_name(text):
                    raise EgressBlocked("vault_name")
                code, _ = json_findings(text)
                if code:
                    raise EgressBlocked(code)
            except EgressBlocked:
                raise
            except VaultUnavailable:
                raise EgressBlocked("vault_unavailable") from None
            except Exception:
                raise EgressBlocked("bad_payload") from None
            kept = not mail.smtp_configured()
            gw._write(f, "email", "email", host, mail.OUTBOX_NOTE if kept else "sent", "", box["body"], aid)
            box["logged"] = True
            try:
                return mail.deliver(plane, addresses, safe["subject"], safe["body"])
            except Exception:  # noqa: BLE001 its text could echo the body
                try:
                    gw._write(f, "email", "email", host, "failed", "transport_failed", box["body"], aid)
                except EgressBlocked:
                    pass
                raise EgressBlocked("transport_failed") from None
        except EgressBlocked as e:
            if e.reason_code != "log_unavailable" and not box.get("logged"):
                gw._write(f, "email", "email", host, "blocked", e.reason_code, box["body"], aid)
            raise


def send_webhook(plane: CompanyPlane, url: str, payload: dict, *, transport=None, module_id: str = "delivery") -> str:
    """V5 D1: a delivery message to an incoming webhook (Slack, Teams, or the company's own). The host must be on the company's
    webhook list (EgressPolicy.webhook_hosts), https only; names are tokenised, nothing goes if a vault name or a raw record is
    still in it. Logged with the host only (the URL holds the secret), never the text. `transport(url, body)` is injectable."""
    gw = EgressGateway(plane, NameVault(plane), EgressPolicy(plane), model_allowlist=[], transport=None,
                       internet_transport=transport)

    def prepare(box):
        _bad(not isinstance(payload, dict))
        safe = _map_strings(payload, gw.vault.tokenise)
        body = json.dumps(safe, sort_keys=True, ensure_ascii=False, allow_nan=False)
        box["body"] = body.encode("utf-8")
        if gw.vault.contains_name(body):
            raise EgressBlocked("vault_name")
        code, _ = json_findings(body)
        if code:
            raise EgressBlocked(code)
    return gw._run(module_id, "webhook", url, gw.policy.webhook_hosts(), gw.internet_transport, lambda: None, prepare)
