"""Shared by the smoke tests (a module with a unique name: several conftest.py files exist)."""
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAKE_SECRET = "FAKE-smoke-secret-0123456789-abcdefghijklmnop"  # fake, clearly marked
WATCHED = ("sh_platform", "tools", "packs", "ui/src", "data")  # data/ is git-ignored but must not change


def _load_seed():
    spec = importlib.util.spec_from_file_location("smoke_tool_seed", ROOT / "tools" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


seed = _load_seed()
PEOPLE = seed.people()
# the four companies, same assertions for each: label, id, modules the package must give
CASES = {
    "A": dict(label="A", id="harbor-mutual", modules=["m1_intent", "m2_baseline", "m3_connect"]),
    "B": dict(label="B", id="tidewater-capital",
              modules=["m1_intent", "m2_baseline", "m3_connect", "m4_build", "m5_foresight"]),
    "family": dict(label="family", id="lakeside-family-office", modules=["m1_intent", "m2_baseline", "m3_connect"]),
    "empty": dict(label="empty", id="solo-studio", modules=[]),
}
INDUSTRY = {c["id"]: c["industry"] for c in seed.COMPANIES}
assert [c["id"] for c in CASES.values()] == [c["id"] for c in seed.COMPANIES]  # the table follows the seed


def user_of(company_id: str) -> dict:
    return next(p for p in PEOPLE if p["company"] == company_id)


def snapshot(root: Path) -> dict:
    """Top-level names plus the file lists of the watched trees (hidden names and caches ignored)."""
    snap = {"top": sorted(p.name for p in root.iterdir() if not p.name.startswith("."))}
    for d in WATCHED:
        base = root / d
        snap[d] = sorted(str(f.relative_to(base)) for f in base.rglob("*")
                         if f.is_file() and "__pycache__" not in f.parts) if base.is_dir() else None
    return snap


def post(client, url: str, **kw):
    """A state-changing request as the browser makes it: with the CSRF header."""
    headers = {"x-csrf-token": client.cookies.get("sh_csrf"), **kw.pop("headers", {})}
    return client.post(url, headers=headers, **kw)


def disable_account(store, email: str) -> None:
    """Switch an account off. The ONLY place the smoke tests touch AccountStore privates (it has no public
    disable call yet; replace the body when it does)."""
    rows = store._read()
    for row in rows:
        if row["email"] == email:
            row["disabled"] = True
    store._write(rows)


# ------------------------------------------------------------------ the per-company / per-group summary
GROUPS = {
    "1 sign-in and menu": ["test_signin_me_and_menu_per_company", "test_wrong_password_is_refused"],
    "2 industry isolation": ["test_suggestions_differ_by_industry_and_empty_gets_empty_state",
                             "test_no_word_of_one_industry_leaks_into_the_other",
                             "test_pack_never_falls_back_to_another_industry"],
    "3 solo user": ["test_solo_user_home_and_sign_out", "test_solo_user_cannot_reach_any_module_route"],
    "4 module off, three ways": ["test_module_off_is_refused_by_menu_route_and_tool_and_follows_the_switch",
                                 "test_not_owned_module_looks_the_same_as_an_unknown_module",
                                 "test_agent_tool_refused_for_other_company_even_if_one_company_owns_it"],
    "5 cross-company": ["test_a_user_cannot_steer_the_server_to_another_companys_plane",
                        "test_a_company_user_cannot_use_the_admin_switch_on_another_company",
                        "test_require_same_company_and_plane_paths_fail_closed",
                        "test_no_route_takes_a_company_id_except_the_super_admin_switch"],
    "6 expired session": ["test_idle_session_gets_401_with_the_briefed_shape",
                          "test_activity_keeps_a_session_alive_until_it_goes_idle",
                          "test_browser_request_without_a_session_is_sent_to_login",
                          "test_logout_ends_the_old_cookie", "test_a_disabled_account_loses_its_open_session"],
    "7 default deny": ["test_every_route_of_the_real_app_is_declared",
                       "test_ui_mount_serves_only_the_built_ui_and_never_the_api_or_outside_files",
                       "test_an_undeclared_route_is_refused",
                       "test_an_undeclared_post_is_refused_even_with_a_valid_csrf",
                       "test_websocket_without_a_session_is_closed"],
}
GROUP_OF_FILE = {"test_smoke_egress": "8 egress", "test_smoke_industry_tree": "9 no hardcoded industry",
                 "test_smoke_summary": "10 summary", "test_smoke_process": "11 process record"}
NOT_TIED = "(not tied to one company)"
_OUTCOMES = ("passed", "failed", "skipped")


def _name_and_params(nodeid: str) -> tuple[str, str, str]:
    path, _, rest = nodeid.replace("\\", "/").partition("::")
    name, _, params = rest.partition("[")
    return path.rsplit("/", 1)[-1].removesuffix(".py"), name, params.rstrip("]")


def group_of(nodeid: str) -> str:
    file, name, _ = _name_and_params(nodeid)
    for group, names in GROUPS.items():
        if name in names:
            return group
    return GROUP_OF_FILE.get(file, "other")


def company_of(nodeid: str) -> str:
    """The first seeded company id found in the test's parameter text, else NOT_TIED."""
    params = _name_and_params(nodeid)[2]
    hits = sorted((params.find(c["id"]), c["id"]) for c in seed.COMPANIES if c["id"] in params)
    return hits[0][1] if hits else NOT_TIED


def tally(results) -> tuple[dict, dict]:
    """results: (nodeid, outcome) pairs, outcome one of passed / failed / error / skipped (error counts as failed).
    Returns (by_company, by_group): each maps a name to {"passed": n, "failed": n, "skipped": n}."""
    by_company, by_group = {}, {}
    for nodeid, outcome in results:
        outcome = "failed" if outcome == "error" else outcome
        for table, key in ((by_company, company_of(nodeid)), (by_group, group_of(nodeid))):
            table.setdefault(key, dict.fromkeys(_OUTCOMES, 0))[outcome] += 1
    return by_company, by_group


def render(table: dict, order: list[str]) -> str:
    keys = [k for k in order if k in table] + sorted(k for k in table if k not in order)
    return "; ".join(f"{k} {table[k]['passed']} passed, {table[k]['failed']} failed"
                     + (f", {table[k]['skipped']} skipped" if table[k]["skipped"] else "") for k in keys)
