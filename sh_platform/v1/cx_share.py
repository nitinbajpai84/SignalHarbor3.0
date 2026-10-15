"""C3 Dashboards reach people: when a dashboard is shared or refreshed, each audience member who may see the data gets one
card in Action. Cards are rows in `pulse_items` (the E5a Pulse reads that table; E5a has no plug-in point for outside sources,
so this module writes the same row shape, with a "*" role so the card shows whichever role the person is viewing).
Nothing is sent outside the machine. A person without E1d access to any entity gets no card; the same event never makes two cards."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sh_platform.profile.view import Viewer
from sh_platform.v1 import e1_access, wh
from sh_platform.v1.e1_write import org_id

log = logging.getLogger(__name__)
EVENTS = {"shared": "shared with you", "refreshed": "refreshed"}


def _dashboard(plane, project_id: str, dashboard_id: str) -> dict:
    """The dashboard as its audience sees it: the published version (DS1), or {} while nothing is published, so no card is made."""
    from sh_platform.v1.cx_dash import published_view
    path = Path(plane.root) / "consume" / project_id / "dashboards" / f"{dashboard_id}.json"
    return published_view(json.loads(path.read_text(encoding="utf-8"))) or {}


def _people(con, audience: list[str]) -> list[tuple[str, str, str | None]]:
    """Audience entries (user ids or access-group ids) -> distinct active users as (id, display name, account id)."""
    ids: list[str] = []
    for a in audience:
        ids.append(str(a))
        ids += [str(r[0]) for r in con.execute("select user_id from access_group_memberships where access_group_id = ? "
                                               "and (expires_at is null or expires_at > ?)", [a, wh.now()]).fetchall()]
    out = {}
    for u in dict.fromkeys(ids):
        r = con.execute("select id, display_name, external_identity_id from users where id = ? and is_active", [u]).fetchone()
        if r:
            out[str(r[0])] = (str(r[0]), r[1], r[2])
    return list(out.values())


def notify(plane, project_id: str, dashboard_id: str, event: str, token: str | None = None, tiles_changed: int | None = None) -> dict:
    """Make the cards. event: 'shared' or 'refreshed'. token names this one share or refresh (default: the dashboard's updated_at)
    so a repeat call for the same event is a no-op. tiles_changed (refresh) is counted by the caller from the tile data.
    Returns {made: [names], skipped_no_access: [names], already: [names]}."""
    if event not in EVENTS:
        raise ValueError("event must be 'shared' or 'refreshed'")
    dash = _dashboard(plane, project_id, dashboard_id)
    token = token or str(dash.get("updated_at") or "")
    key = f"dash:{dashboard_id}:{event}:{token}"
    title = dash.get("title") or "Dashboard"
    if event == "refreshed" and tiles_changed is not None:
        head = f"{title} refreshed · {tiles_changed} tile{'s' if tiles_changed != 1 else ''} changed"
    else:
        head = f"{title} {EVENTS[event]}"
    now = wh.now()
    res: dict = {"made": [], "skipped_no_access": [], "already": []}
    with wh.connect(plane) as con:
        for uid, name, acc in _people(con, dash.get("audience") or []):
            if not e1_access.visible_entities(plane, Viewer(name, frozenset(), False, acc)):
                res["skipped_no_access"].append(name)
                continue
            if any(json.loads(s).get("key") == key for (s,) in con.execute(
                    "select summary from pulse_items where recipient_user_id = ?", [uid]).fetchall()):
                res["already"].append(name)
                continue
            body = {"role": "*", "key": key, "kind": "dashboard", "headline": head,
                    "text": f"Open the dashboard to see the {len(dash.get('tiles') or [])} tiles.",
                    "status_word": "Refreshed" if event == "refreshed" else "Shared", "urgency": "worth_a_look",
                    "action_type": "open_dashboard", "action": "Open dashboard", "as_of": now.date().isoformat(), "received": None,
                    "effect": None, "owner": dash.get("created_by"), "due": None, "link": f"/centre/consume/d/{dashboard_id}",
                    "exception_id": None, "rank": 4}
            con.execute("insert into pulse_items (id, organization_id, recipient_user_id, headline, summary, generated_at, as_of_at, "
                        "urgency, action_type, delivery_status) values (?,?,?,?,?,?,?,?,?,'pending')",
                        [wh.new_id(), org_id(plane), uid, head[:250], json.dumps(body), now, now, "worth_a_look", "open_dashboard"])
            res["made"].append(name)
    return res
