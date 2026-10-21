from pathlib import Path

from fastapi import FastAPI

from sh_platform.auth import install_auth
from sh_platform.build_env import router as build_env_router
from sh_platform.build.home import router as build_home_router
from sh_platform.context_docs import router as context_docs_router
from sh_platform.control import router as control_router
from sh_platform.profile import router as profile_router
from sh_platform.interview import router as interview_router
from sh_platform.module_loader import install_modules
from sh_platform.modulegate import install_modulegate
from sh_platform.outcomes import router as outcomes_router
from sh_platform.graph.api import router as graph_router
from sh_platform.pulse.__init__ import router as pulse_router
from sh_platform.pulse.messages import router as pulse_messages_router
from sh_platform.build.blueprint import router as blueprint_router
from sh_platform.build.runner import router as runner_router
from sh_platform.build.prove import router as prove_router
from sh_platform.build.uat import router as uat_router
from sh_platform.build.ops import router as ops_router
from sh_platform.build.whatif import router as whatif_router
from sh_platform.consume.feeds import router as feeds_router
from sh_platform.consume.measure import router as measure_router
from sh_platform.consume.market import router as market_router
from sh_platform.memory.api import router as memory_router
from sh_platform.graph.versions import router as graph_node_router
from sh_platform.graph.comments import router as graph_comments_router
from sh_platform.graph.register import router as register_router
from sh_platform.intents import (  # Intent Centre v2 stubs, one per build card
    types as ic_types,
    visibility as ic_visibility,
    access as ic_access,
    wall as ic_wall,
    converge as ic_converge,
    source_map as ic_source_map,
    checkin_review as ic_checkin_review,
    home as ic_home,
    people as ic_people,
    clock as ic_clock,
    north as ic_north,
    closure as ic_closure,
    events as ic_events,
    search as ic_search,
    initiative as ic_initiative,
    define as ic_define,
    processes as ic_processes,
    sources as ic_sources,
    glossary as ic_glossary,
    catalogue as ic_catalogue,
    charter as ic_charter,
    build_ready as ic_build_ready,
    brainstorm as ic_brainstorm,
    checkin as ic_checkin,
    problem as ic_problem,
    decision as ic_decision,
    lens as ic_lens,
    nira as ic_nira,
    share as ic_share,
    past as ic_past,
    links as ic_links,
    backlog as ic_backlog,
    affected as ic_affected,
    admin as ic_admin,
    pack as ic_pack,
    memory as ic_memory,
    measures as ic_measures,
    knowledge_map as ic_knowledge_map,
    opportunities as ic_opportunities,
    records as ic_records)
from sh_platform.packs import PackLoader
from sh_platform.egress.gateway import send_email
from sh_platform.settings import Settings, load_settings
from sh_platform.webui import install_webui

DEFAULT_PACKS = Path(__file__).resolve().parent.parent / "packs"
# Seconds uvicorn keeps an idle connection open. Its default (5 s) equals the 5 s poll of a thread that is working: the server closed the
# kept-alive socket just as the next poll went out on it, and the poller got a connection reset on every poll (r7, uc-002 working stage).
# Longer than any client's poll; every launcher passes it (tools/serve_test.py, tools/serve_v1.py, tools/start.sh).
KEEP_ALIVE_S = 75


def create_app(settings: Settings | None = None, dist_dir: Path | str | None = None,
               modules_root: Path | str | None = None, packs_root: Path | str | None = None) -> FastAPI:
    """modules_root and packs_root are for tests (a temporary folder); the defaults are the repo's own."""
    from sh_platform import mode as run_mode
    run_mode.check()  # W3: only one of DATABASE_URL and REDIS_URL set is a mistake; refuse to start
    app = FastAPI(title="Signal Harbor", docs_url=None, redoc_url=None, openapi_url=None)
    from sh_platform.perf import install_timer; install_timer(app)  # logs any route over 500 ms
    settings = settings or load_settings()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    install_auth(app, settings)  # also sets app.state.settings
    install_modulegate(app, settings)  # after auth: wraps it, so module paths are judged first
    app.state.packs = PackLoader(packs_root or DEFAULT_PACKS)  # industry knowledge, always by parameter
    install_modules(app, modules_root)  # after the gate, before the UI mount
    app.include_router(context_docs_router)  # M1-CTX: company context uploads (D-032)
    app.include_router(profile_router)  # LI-PROFILE: the company profile and Bring what you have
    app.include_router(interview_router)  # LI-INTERVIEW: the one interview, with an invite link per person
    app.include_router(outcomes_router)  # LI-OUTCOMES: the measures of the centre itself
    app.include_router(build_env_router)  # BC-1: the Build centre's environment check
    app.include_router(build_home_router)  # B1: Build centre home
    app.include_router(graph_router)
    app.include_router(pulse_router)
    app.include_router(pulse_messages_router)
    app.state.email_sender = send_email  # the gateway's email exit
    app.include_router(blueprint_router)
    app.include_router(runner_router)
    app.include_router(prove_router)
    app.include_router(uat_router)
    app.include_router(ops_router)
    from sh_platform import v1 as v1_cards
    v1_cards.install(app)  # 1.0: every slim card's router, one file each under sh_platform/v1/ (connectors C5 and the pain-point demo K12 mount here by glob)
    from sh_platform.mcp.routes import router as mcp_router
    app.include_router(mcp_router)  # W2: MCP server, POST /mcp (bearer token) and the Settings token routes
    from sh_platform.build import chain as build_chain
    build_chain.install(app)  # 59: change notes and the architecture record
    from sh_platform.build import proposals as build_proposals, dialect as build_dialect
    app.include_router(build_proposals.router)  # Span and Flow: suggestions to the data team (SF02)
    app.include_router(build_dialect.router)  # Span and Flow: warehouse SQL (SF07)
    from sh_platform.build.agents import routes as span_flow_routes
    app.include_router(span_flow_routes.router)  # Span and Flow: target, model draft, review, design document, run and incident notes (SF13)
    app.include_router(whatif_router)
    app.include_router(feeds_router)
    app.include_router(measure_router)
    app.include_router(market_router)
    app.include_router(memory_router)
    app.include_router(graph_node_router)
    app.include_router(graph_comments_router)
    app.include_router(register_router)  # MVP wave stubs
    app.include_router(control_router)  # IC-5a: super admin control panel and company settings
    app.include_router(ic_types.router)  # IC v2 stub: 02
    app.include_router(ic_visibility.router)  # IC v2 stub: 05
    app.include_router(ic_access.router)  # IC v2 stub: 14
    ic_access.install(app)  # B04: plain refusal bodies for the per-intent check
    from sh_platform.consume import lenses as consume_lenses
    consume_lenses.install(app)  # B60a: business views and context cards
    from sh_platform.intents import radar as ic_radar
    ic_radar.install(app)  # B57a: radar before any /api/intents/{intent_id} router
    app.include_router(ic_home.router)  # IC v2 stub: 04
    app.include_router(ic_people.router)  # IC v2 stub: 06
    app.include_router(ic_clock.router)  # IC v2 stub: 07
    app.include_router(ic_north.router)  # IC v2 stub: 08
    app.include_router(ic_closure.router)  # IC v2 stub: 09, 10
    app.include_router(ic_events.router)  # IC v2 stub: 16
    app.include_router(ic_search.router)  # IC v2 stub: 15
    app.include_router(ic_wall.router)  # B12: the wall inside an intent, before the initiative stubs
    app.include_router(ic_initiative.router)  # IC v2 stub: 22, 23, 24
    app.include_router(ic_define.router)  # IC v2 stub: 26
    app.include_router(ic_processes.router)  # IC v2 stub: 27, 44
    app.include_router(ic_sources.router)  # IC v2 stub: 28
    app.include_router(ic_glossary.router)  # IC v2 stub: 29
    app.include_router(ic_catalogue.router)  # IC v2 stub: 30
    app.include_router(ic_charter.router)  # IC v2 stub: 32
    app.include_router(ic_build_ready.router)  # IC v2 stub: 33
    app.include_router(ic_converge.router)  # B21: converge routes win over the brainstorm stubs
    app.include_router(ic_brainstorm.router)  # IC v2 stub: 35, 36, 37
    app.include_router(ic_checkin_review.router)  # B23: review routes win over the check-in stubs
    app.include_router(ic_checkin.router)  # IC v2 stub: 38, 39, 40
    app.include_router(ic_problem.router)  # IC v2 stub: 41, 42
    app.include_router(ic_decision.router)  # IC v2 stub: 43
    app.include_router(ic_lens.router)  # IC v2 stub: 44
    app.include_router(ic_nira.router)  # IC v2 stub: 45
    app.include_router(ic_share.router)  # IC v2 stub: 11
    app.include_router(ic_past.router)  # IC v2 stub: 12
    app.include_router(ic_links.router)  # IC v2 stub: 20
    app.include_router(ic_backlog.router)  # IC v2 stub: 21
    app.include_router(ic_affected.router)  # IC v2 stub: 47, 42, 43
    app.include_router(ic_admin.router)  # IC v2 stub: 48, 05
    app.include_router(ic_pack.router)  # IC v2 stub: 49
    app.include_router(ic_memory.router)  # IC v2 stub: 46
    app.include_router(ic_measures.router)  # IC v2 stub: 19
    app.include_router(ic_knowledge_map.router)  # IC v2 stub: 55
    app.include_router(ic_opportunities.router)  # IC v2 stub: 56
    app.include_router(ic_source_map.router)  # B37: strategic source map, before the record routes
    from sh_platform.intents import proving as ic_proving
    ic_proving.install(app)  # B58a: Proving and the weekly uplift report
    app.include_router(ic_records.router)  # IC v2 stub: 01  # last: its {intent_id} lines must not catch the literal paths
    install_webui(app, dist_dir)  # last: API routes win over the static mount
    from sh_platform.v1.teach import TeachMiddleware
    app.add_middleware(TeachMiddleware)  # TEACH1: a chat turn of North, Span, Lumen or Tally may quote what the company taught that agent
    from sh_platform.v1.chat_fastpath import ChatStreamMiddleware
    app.add_middleware(ChatStreamMiddleware)  # V5W-7: chat replies as events, outermost
    from sh_platform.v1.read_cache import BumpOnWrite
    app.add_middleware(BumpOnWrite)  # Consume keeps its answers until something is written
    _install_build_scheduler(app)  # V3 B4: pipelines run on their schedule while the server runs
    return app


_SCHEDULER_STARTED = False


def _install_build_scheduler(app: FastAPI) -> None:
    """Start the Build pipeline scheduler once per process when the server starts; stop it on shutdown.
    Tests that build an app without serving it never start it; SH_SCHEDULER=off disables it."""
    import os

    @app.on_event("startup")
    def _start() -> None:
        global _SCHEDULER_STARTED
        if _SCHEDULER_STARTED or os.environ.get("SH_SCHEDULER", "on").lower() == "off":
            return
        from sh_platform.plane import PlaneStore
        from sh_platform.v1 import b6_schedule
        store = PlaneStore(app.state.settings.data_root)
        b6_schedule.start(lambda: [store.plane_for(c) for c in store.list_company_ids()])
        from sh_platform.v1 import d1_delivery  # V5W-4: approved delivery channels go out on their schedule
        d1_delivery.start(lambda: [store.plane_for(c) for c in store.list_company_ids()])
        from sh_platform.v1 import g5_portal  # G5: push for new cards and approvals, and the daily morning email
        g5_portal.start(lambda: [store.plane_for(c) for c in store.list_company_ids()])
        _SCHEDULER_STARTED = True

    @app.on_event("shutdown")
    def _stop() -> None:
        from sh_platform.v1 import b6_schedule
        b6_schedule.stop()
        from sh_platform.v1 import d1_delivery
        d1_delivery.stop()
        from sh_platform.v1 import g5_portal
        g5_portal.stop()
        from sh_platform.state import kv
        kv.unlead()
