"""G1 fix round: every route that names an intent checks the project's access (B1), Internal is the team's alone and people join the team as
the work moves (B2), and a locked project leaks neither its title nor a ticket count (T2)."""
from tests.v1.test_g1 import WHO, account, client, plane_of, world  # noqa: F401  (world is a fixture)
from sh_platform.auth import all_routes
from sh_platform.v1 import g1_access as G1
from sh_platform.v1 import p1_project as P
from sh_platform.v1 import t2_tickets as T

SELF_GATED = ("/project", "/pickup/")  # the lock row itself; pick-up (p3 refuses a Restricted project in its own line, tested below)


def _restricted(world):
    priya = client(world, "priya.nair")
    iid = priya.post("/api/v1/intents/chat", json={"text": "A private compensation review for the partners"}).json()["id"]
    pid = priya.get(f"/api/v1/intents/{iid}/project").json()["id"]
    assert priya.put(f"/api/v1/projects/{pid}/access", json={"sensitivity": "restricted"}).status_code == 200
    return priya, iid, pid


def test_every_intent_route_refuses_a_person_off_the_team(world):
    _, iid, pid = _restricted(world)
    leela = client(world, "leela.raman")  # an analyst: before B2 the Internal rule let her read
    app = world[0]
    seen = 0
    for route in all_routes(app):  # FastAPI 0.142 wraps included routers: app.routes no longer lists their paths
        path, methods = getattr(route, "path", ""), getattr(route, "methods", None) or set()
        if "{iid}" not in path or not path.startswith("/api/v1/") or any(x in path for x in SELF_GATED):
            continue
        url = path.replace("{iid}", iid).replace("{code}", "k").replace("{tid}", "t").replace("{did}", "d").replace("{rid}", "1").replace("{n}", "1")
        url = url.replace("{doc_id}", "x") + ("?period=2026-09&file=a&line=1&format=md" if "?" not in url else "")
        for m in methods - {"HEAD", "OPTIONS"}:
            r = leela.request(m, url, json={} if m != "GET" else None)
            assert r.status_code == 403, (m, url, r.status_code, r.text[:200])
            seen += "Restricted" in r.text  # the gate's own sentence; a few routes are refused earlier still, by role (company admin only)
    assert seen >= 40  # the review listed some forty handlers
    # the query-keyed ones, the project lock row, pick-up, the waiting list
    for m, tail in (("POST", "/run-book/draft"), ("PUT", "/run-book"), ("POST", "/run-book/sign")):  # G2: keyed by project, not by intent
        assert leela.request(m, f"/api/v1/projects/{pid}{tail}", json={}).status_code == 403, tail
    assert leela.get(f"/api/v1/consume/brief?iid={iid}").status_code == 403
    assert leela.get(f"/api/v1/intents/{iid}/project").json()["locked"]
    assert leela.post(f"/api/v1/build/pickup/{iid}").status_code in (403, 404)
    assert pid not in str(leela.get("/api/v1/build/waiting").json())


def test_internal_is_the_teams_alone_and_people_join_as_work_moves(world):
    plane = plane_of(world)
    priya = client(world, "priya.nair")
    iid = priya.post("/api/v1/intents/chat", json={"text": "A fee review for the investment committee"}).json()["id"]
    pid = priya.get(f"/api/v1/intents/{iid}/project").json()["id"]
    leela, leela_v = client(world, "leela.raman"), account(world, "Leela Raman")
    assert G1.may_see_project(plane, leela_v, pid) == "preview"
    assert leela.get(f"/api/v1/intents/{iid}/thread").status_code == 403 and leela.get(f"/api/v1/intents/{iid}/chat").status_code == 403
    # the engineer opens the engineer screen on a project she holds a ticket on: she joins the team as the data engineer
    assert leela.get(f"/api/v1/build/{iid}/engineer").status_code == 403
    T.raise_ticket(plane, by="Priya Nair", to="Leela Raman", title="Check the fee file", project=pid)
    assert leela.get(f"/api/v1/build/{iid}/engineer").status_code != 403  # past the gate (404: no design yet)
    assert ("Leela Raman", "data engineer") in [(m["name"], m["role"]) for m in G1.team_of(P.read(plane, pid))]
    assert G1.may_see_project(plane, leela_v, pid) == "full"
    # the head of data joins when the design is submitted; ops joins at the first run-book edit
    G1.join(plane, pid, G1.head_of_data(plane), "head of data")
    assert "Arjun Mehta" in [m["name"] for m in G1.team_of(P.read(plane, pid))]
    G1.join(plane, pid, "Arjun Mehta", "head of data")  # idempotent
    assert [m["name"] for m in G1.team_of(P.read(plane, pid))].count("Arjun Mehta") == 1


def test_locked_project_leaks_nothing_through_tickets(world):
    plane = plane_of(world)
    _, iid, pid = _restricted(world)
    dev, dev_v = client(world, "dev.sharma"), account(world, "Dev Sharma")
    t = T.raise_ticket(plane, by="Priya Nair", to="Dev Sharma", title="Look at the pay bands", project=pid)
    mine = dev.get("/api/v1/tickets").json()["tickets"]
    assert [r["id"] for r in mine] == [t["id"]] and mine[0]["project_title"] == "A restricted project"
    assert "compensation" not in str(dev.get(f"/api/v1/tickets/{t['id']}").json()).lower()
    needs, look, lines = [], [], [{**G1.lock_row(P.read(plane, pid), "none"), "pid": pid}]
    T.extend(plane, dev_v, needs, look, lines)
    assert "open_tickets" not in lines[0] and all("compensation" not in str(c).lower() for c in needs)


def test_nobody_joins_the_team_by_themselves(world):
    """Fixes 2: a self-raised ticket, or a run-book edit by the ops seat, never promotes a person to "full"."""
    plane = plane_of(world)
    _, iid, pid = _restricted(world)
    priya = client(world, "priya.nair")
    pid2 = priya.get(f"/api/v1/intents/{priya.post('/api/v1/intents/chat', json={'text': 'An open fee review'}).json()['id']}/project").json()["id"]
    priya.put(f"/api/v1/projects/{pid2}/access", json={"sensitivity": "open"})
    leela, leela_v = client(world, "leela.raman"), account(world, "Leela Raman")
    assert G1.may_see_project(plane, leela_v, pid2) == "read"  # Open: everyone reads
    t = leela.post("/api/v1/tickets", json={"project": pid2, "title": "Mine", "assigned_to": "Leela Raman"})  # raised to herself
    assert t.status_code == 200 and not T.assigned_on(plane, leela_v, pid2)
    assert G1.may_see_project(plane, leela_v, pid2) == "read"
    T.raise_ticket(plane, by="Priya Nair", to="Leela Raman", title="Check it", project=pid2)  # given by someone on the team
    assert T.assigned_on(plane, leela_v, pid2)
    # the run book: not on a project that is not live, nor on a live one without a ticket from the team
    for m, tail in (("POST", "/run-book/draft"), ("PUT", "/run-book"), ("POST", "/run-book/sign")):
        assert leela.request(m, f"/api/v1/projects/{pid2}{tail}", json={}).status_code == 403, tail


def test_routes_keyed_by_query_or_body_refuse_or_filter(world):
    """Fixes 2: intent, pid, doc_id and the newest-intent default are all gated, 403 or a filtered list, never a 404 counted as a pass."""
    _, iid, pid = _restricted(world)
    leela = client(world, "leela.raman")
    plane = plane_of(world)
    from sh_platform.jsonfile import write_json_atomic
    from sh_platform.v1 import i2_north as N, p5_handover as P5, x5_extract as X5
    sow = N.read_sow(plane, iid)
    write_json_atomic(N._path(plane, iid, "sow.json"), {**sow, "state": "signed", "intent_id": iid})  # now /consume would list it
    write_json_atomic(plane.path("extractions", "doc-g1.json"), {"doc_id": "doc-g1", "file": "documents/a.md", "intent_id": iid, "status": "review"})
    assert any(i["intent_id"] == iid for i in __import__("sh_platform.v1.c1_cards", fromlist=["x"]).build(plane)["intents"])
    assert any(i["intent_id"] == iid for i in X5.queue(plane)["items"])
    for m, url, body in (("GET", f"/api/v1/consume/offers?intent={iid}", None), ("POST", "/api/v1/ops/tickets", {"pid": pid, "source_id": "a", "text": "x"}),
                         ("GET", f"/api/v1/ops/live?iid={iid}", None), ("GET", f"/api/v1/consume/brief?iid={iid}", None)):
        assert leela.request(m, url, json=body).status_code == 403, (m, url)
    assert iid not in str(leela.get("/api/v1/consume").json())
    assert iid not in str(leela.get("/api/v1/extract/queue").json())
    assert leela.get("/api/v1/consume/offers").status_code == 403  # no intent named: the newest one (this one) is read, so it is gated
    P5._set(plane, pid, stage="live")  # the ops board lists live projects; the ops seat (an analyst) reads a live one, so ask as the engineer
    dev = client(world, "dev.sharma")
    assert any(r["pid"] == pid for r in P5.board(plane)["projects"]) and G1.may_see_project(plane, account(world, "Dev Sharma"), pid) == "none"
    assert pid not in str(dev.get("/api/v1/ops/live").json())
