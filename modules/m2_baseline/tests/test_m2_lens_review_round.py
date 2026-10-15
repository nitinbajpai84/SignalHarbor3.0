"""M2-AGENTS review round: relaxing a measure clears everything Lens drew from a restricted document, and one draft per
measure even when two tabs open at once."""
import json

import pytest
from m2_kit import BASE, login
from test_m2_lens import Stub, with_doc
from test_m2_lens_first_move import FO, _restricted, fo, lens_url, model  # noqa: F401  (fo: fixture)
from test_m2_worklist import confirm, kpi_of, rich_packs, seed_charter, start  # noqa: F401  (rich_packs: autouse fixture)

from sh_platform.context_docs.store import DocStore
from sh_platform.jsonfile import write_json_atomic

PAYDOC = b"Secret pay gap: payroll is run by the payments team. The pay data is extracted by a weekly export from the payroll processor."
PAYREPLY = "DEFINITION: Secret pay gap compares pay across managers. OWNER: The payments team. PRODUCER: The payroll processor. GATHERED: A weekly export."
LEAK = ("Payroll procedure", "payments team", "payroll processor", "weekly export", "compares pay across managers")


@pytest.mark.parametrize("before_relax", ["same", "unrestricted", "renamed"])
def test_relaxing_a_personal_measure_clears_every_field_drawn_from_a_restricted_document(fo, before_relax):
    store = DocStore(fo.plane("co-fo"))
    doc = store.upload("lens", "a", "pay.md", PAYDOC, title="Payroll procedure", restricted=True)
    stub = Stub(PAYREPLY)
    model(fo, stub)
    admin, v, kid = _restricted(fo)
    url = f"{BASE}/baselines/{v['baseline']['id']}"
    admin.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]})
    k = kpi_of(admin.get(url).json(), kid)
    assert k["producer"]["value"] and k["gathered"]["value"] and k["definition"]["from"] == "Payroll procedure"  # filled from the restricted document
    if before_relax == "unrestricted":
        store.set_restricted("lens", doc["doc_id"], False)
    elif before_relax == "renamed":
        write_json_atomic(store._file("lens", doc["doc_id"]), {**store._read("lens", doc["doc_id"]), "title": "Something else"})
    admin.put(f"{url}/kpis/{kid}/governance", json={"personal": "no", "may_see": []})
    stub.sent.clear()
    analyst = login(fo, "co-fo", "Rae Other", ("analyst",))
    seen = [analyst.get(url).text, analyst.get(lens_url(v)).text]
    analyst.post(lens_url(v, "/ask"), json={"question": "What do we know about Secret pay gap?"})
    # lens_facts, as sent to the model (a document that is no longer restricted may be quoted as a passage: that is its own channel)
    seen += [json.loads(stub.sent[0][1]["content"])["context"]["baseline_facts"], analyst.post(f"{url}/nira", json={"kind": "welcome"}).text]
    for text in seen:
        for bit in LEAK:
            assert bit not in text, bit
    k = kpi_of(analyst.get(url).json(), kid)
    assert k["definition"]["mark"] == k["producer"]["mark"] == k["gathered"]["mark"] == "unknown"


def test_a_second_call_skips_what_was_already_drafted_unless_told_to_retry(fo):
    with_doc(fo, "co-fo")
    stub = Stub()
    model(fo, stub)
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    kid = v["kpis"][0]["id"]
    first = c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()
    assert first["outcomes"] == {kid: "documents"} and len(stub.sent) == 1
    second = c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()
    assert second["outcomes"] == {} and len(stub.sent) == 1  # the other tab does not call the model again
    third = c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid], "retry": True}).json()
    assert third["outcomes"] == {kid: "documents"} and len(stub.sent) == 2


# ---- a claim that never finished must not leave a blank card

def _one_measure(fo):
    with_doc(fo, "co-fo")
    model(fo, Stub())
    c = login(fo, "co-fo")
    v = confirm(c, start(c, seed_charter(fo, "co-fo", FO)), name="Calls due, by date", problem_ids=["p1"])
    return c, v, v["kpis"][0]["id"]


def test_an_exception_mid_draft_leaves_no_working_entry(fo, monkeypatch):
    from modules.m2_baseline.agent import lens
    from modules.m2_baseline.store import lens as LS
    c, v, kid = _one_measure(fo)

    def boom(*a, **k):
        raise RuntimeError("crash")
    monkeypatch.setattr(lens, "draft_fields", boom)
    with pytest.raises(RuntimeError):
        c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]})
    assert LS.read(fo.plane("co-fo"), v["baseline"]["id"])["attempts"][kid] == "unreachable"
    assert c.get(lens_url(v)).json()["failed"] == [kid]  # so "Try again" shows


def _claim(fo, v, kid, age):
    import time
    from modules.m2_baseline.store import lens as LS
    plane, bid = fo.plane("co-fo"), v["baseline"]["id"]
    LS.claim(plane, bid, [kid])
    doc = LS.read(plane, bid)
    plane.path("intents", "m2_baseline", bid, "lens.json").write_text(json.dumps({**doc, "claimed": {kid: time.time() - age}}))


def test_a_stale_claim_shows_as_failed_and_can_be_redrafted_without_retry(fo):
    c, v, kid = _one_measure(fo)
    _claim(fo, v, kid, age=600)
    s = c.get(lens_url(v)).json()
    assert s["failed"] == [kid] and s["drafting"] == []
    assert c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()["outcomes"] == {kid: "documents"}


def test_a_fresh_claim_shows_as_drafting_in_a_second_tab(fo):
    c, v, kid = _one_measure(fo)
    _claim(fo, v, kid, age=5)
    s = c.get(lens_url(v)).json()
    assert s["drafting"] == [kid] and s["failed"] == [] and kid not in s["pending"]
    assert c.post(lens_url(v, "/draft"), json={"kpi_ids": [kid]}).json()["outcomes"] == {}  # not taken twice
