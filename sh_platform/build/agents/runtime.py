"""Span and Flow: who they are, and the runtime every Build agent call uses (plan S1, S8).

Names and subtitles copied from the earlier product's agent personas (agents/gates.py). The model client set-up and name registration are
copied from module 3's Lens (`modules/m3_connect/agent/compile.py` get_model, register_names; not imported: kernel code never imports a
module), and the Runtime shape from `sh_platform/intents/lens.py`. Every model call is `run_agent(rt.model, registry, ...)`, which reaches
the model only through the egress gateway.
"""
import logging
import threading
from dataclasses import dataclass, field

from fastapi import Request

from sh_platform.agents.runs import RunRegistry
from sh_platform.egress.names import names_in_text, protected_names
from sh_platform.egress.providers import ProviderError, build_model_client
from sh_platform.egress.vault import NameVault, VaultUnavailable
from sh_platform.profile import view
from sh_platform.settings import load_model_env

log = logging.getLogger(__name__)
SPAN, FLOW = "Span", "Flow"
SUBTITLE = {SPAN: "Solution architect", FLOW: "Data engineer"}
MODULE_ID = "m4_build"  # the entitlement gate and the run log (S8)


class OpenGate:
    """Entitlement is already checked by the route that led here; the agent loop still asks the gate once per step."""

    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return True


class BuildCentreGate:
    """The same switch the Build routes use: the company exists and its Build centre is not switched off (absent means on).
    Not the m4_build entitlement, which is false for every company that uses Build today."""

    def __init__(self, entitlements):
        self.ent = entitlements

    def is_enabled(self, company_id: str, module_id: str) -> bool:
        return self.ent.company(company_id) is not None and self.ent.switches(company_id)["centres"].get("build", True) is True


@dataclass
class Runtime:
    model: object | None
    gate: object = field(default_factory=OpenGate)
    company_id: str = ""
    company_name: str = ""
    industry: str = ""
    viewer: view.Viewer = field(default_factory=lambda: view.Viewer("", frozenset()))  # nobody: every restricted item stays hidden
    recorder: object | None = None
    gateway: object | None = None  # the internet gateway for search_reference; built from the plane when None

    def routed(self, agent: str, task: str, intent_id: str = "", plane=None, **signals) -> "Runtime":
        """R1: this runtime with the model the router picks for one call (tier by rules, model by the company's mode)."""
        from dataclasses import replace
        from sh_platform.v1.router import route
        return replace(self, model=route(self.model, agent, task, intent_id, plane, **signals))


def get_model(state, plane):
    """The model client for this company, or None (no key set up, or a setting is wrong). Tests plug a stub in as `build_model_factory`."""
    factory = getattr(state, "build_model_factory", None)
    override = getattr(state, "model_env", None)  # tests set {}: the real .env holds keys and a test must never reach a live model
    try:
        from sh_platform.v1.router import route  # R1: every call follows the company's Testing / Real use mode (a stub stays a stub)
        return route(factory(plane) if factory else build_model_client(plane, dict(override) if override is not None else load_model_env()), "", "")
    except ProviderError:
        log.warning("the model settings are not valid")
        return None


def register_names(plane, company: str, people: list[str], organisations=()) -> None:
    """People are people (each part of the name is masked); entities, portfolios, funds, managers, reports and anything else are
    `organisations` (the full name, and a distinctive first word). A case word passed as a person never puts an everyday word in the vault
    (names.protected_names turns a non-person into an organisation and never registers a single everyday word)."""
    vault = NameVault(plane)
    for kind, name in protected_names(company, list(people), list(organisations)):
        try:
            if name:
                vault.register(kind, name)
        except (ValueError, VaultUnavailable):
            log.warning("a name could not be registered with the egress vault")  # the gateway then refuses to send


def register_organisations(plane, names) -> None:
    """Organisations by their full name (and a distinctive first word, "Northgate"), never their other words alone: master data and names
    found in documents are not people, so "Kestrel Ridge Advisors" never puts "Ridge" in the vault."""
    vault = NameVault(plane)
    for name in names:
        for kind, n in protected_names(str(name), []):  # the company branch: full name + distinctive first word only
            try:
                vault.register(kind, n)
            except (ValueError, VaultUnavailable):
                log.warning("a name could not be registered with the egress vault")


def register_document_names(plane, text: str) -> list[str]:
    """NAV-3: the names a document, note or newsletter mentions, registered as full names before its text reaches a model. Returns them."""
    found = names_in_text(text)
    if found:
        register_organisations(plane, found)
    return found


_MASTER_SQL = (("select name from organizations", "company"), ("select entity_name from legal_entities", "org"),
               ("select portfolio_name from portfolios", "org"), ("select display_name from users", "person"),
               ("select canonical_name from instruments where instrument_type in ('private_fund', 'hedge_fund', 'liquid_fund')", "org"),
               ("select distinct manager_name from instruments where manager_name is not null", "org"),
               ("select report_name from reports", "org"))
_master_seen: dict[str, float] = {}
_master_lock = threading.Lock()


# RC2-1: who a payment went to lives only in the landed files (the warehouse keeps amount, reference and dates); these columns name them
COUNTERPARTY_COLUMNS = frozenset({"counterparty", "counterparty_name", "payee", "payee_name", "beneficiary", "beneficiary_name", "paid_to"})


def landed_counterparties(plane) -> list[str]:
    """RC2-1: the distinct payees and counterparties of the landed CSV files the warehouse's source records point at. Read on the machine,
    only to register them in the vault, so a wire's payee is masked before a prompt leaves. Never raises."""
    import csv
    from sh_platform.v1 import wh
    out: set[str] = set()
    try:
        with wh.connect(plane, read_only=True) as con:
            uris = [r[0] for r in con.execute("select distinct raw_payload_uri from source_records where lower(raw_payload_uri) like '%.csv'").fetchall()]
    except Exception:  # noqa: BLE001 - no source records yet
        return []
    for uri in uris:
        try:
            with open(plane.path(*str(uri).split("/")), encoding="utf-8-sig", newline="") as f:
                rows = csv.DictReader(f)
                cols = [c for c in (rows.fieldnames or []) if str(c).strip().lower() in COUNTERPARTY_COLUMNS]
                if cols:
                    out.update(str(r.get(c) or "").strip() for r in rows for c in cols)
        except (OSError, ValueError, csv.Error):
            continue
    return sorted(n for n in out if len(n) >= 3)


def register_company_names(plane) -> bool:
    """ER-02: the company's master data in the vault before any model call: the company, its legal entities, portfolios, funds, managers,
    report names and the people with an account, plus the people and firms named in the manager notes and (RC2-1) the payees and
    counterparties of the landed files. Read from the warehouse; run again
    only when the warehouse file changed (once per change per process). Returns True when it registered. Never raises."""
    try:
        from sh_platform.v1 import wh
        db = wh.path(plane)
        stamp = db.stat().st_mtime if db.is_file() else 0.0
    except Exception:  # noqa: BLE001
        return False
    key = str(plane.root)
    with _master_lock:
        if _master_seen.get(key) == stamp:
            return False
        _master_seen[key] = stamp
    company, people, orgs = "", [], []
    try:
        if stamp:
            with wh.connect(plane, read_only=True) as con:
                have = {r[0] for r in con.execute("select table_name from information_schema.tables where table_schema = 'main'").fetchall()}
                for sql, kind in _MASTER_SQL:
                    if sql.split(" from ")[1].split()[0] not in have:
                        continue
                    for (v,) in con.execute(sql).fetchall():
                        if not v:
                            continue
                        if kind == "company":
                            company = company or str(v)
                        (people if kind == "person" else orgs).append(str(v))
        notes = plane.path("managers")
        for f in (notes.glob("*/notes.json") if notes.is_dir() else []):
            orgs += names_in_text(f.read_text(encoding="utf-8", errors="replace"))
        if stamp:
            orgs += landed_counterparties(plane)
    except Exception:  # noqa: BLE001 - a missing table or a busy file: what was read is still registered
        log.warning("the company's master data could not all be read for the name vault", exc_info=True)
    register_names(plane, company, people)
    register_organisations(plane, orgs)
    return True


def runtime_for_request(request: Request, plane, viewer: view.Viewer) -> Runtime:
    st = request.app.state
    company = st.entitlements.company(request.state.company_id) or {}
    return Runtime(get_model(st, plane), BuildCentreGate(st.entitlements), request.state.company_id, str(company.get("name") or ""),
                   str(company.get("industry") or ""), viewer, RunRegistry(plane), getattr(st, "build_gateway", None))


def runtime_for_plane(plane, viewer: view.Viewer | None = None) -> Runtime:
    """For a background draft started by a route that already checked entitlement (Lens's _OpenGate pattern)."""
    try:
        from sh_platform.v1.router import route  # R1: every call follows the company's Testing / Real use mode
        model = route(build_model_client(plane, load_model_env()), "", "")
    except ProviderError:
        log.warning("the model settings are not valid")
        model = None
    name, industry = "", ""
    try:  # the company record sits on the control plane beside the company folders (Nira's guide needs a name and an industry)
        from sh_platform.entitlements import EntitlementStore
        company = EntitlementStore(plane.root.parent).company(plane.company_id) or {}
        name, industry = str(company.get("name") or ""), str(company.get("industry") or "")
    except Exception:  # noqa: BLE001 - a draft without the company's name still runs
        log.warning("the company record could not be read for the runtime")
    return Runtime(model, company_id=plane.company_id, company_name=name, industry=industry,
                   viewer=viewer or view.Viewer("", frozenset()), recorder=RunRegistry(plane))
