"""M1-DATA: the html and email readers, the seeded demo documents, and the hostile file that must stay inert."""
import time
from pathlib import Path

import pytest

from ctx_seed import seed
from ctx_const import FAMILY, OTHER
from sh_platform.context_docs import context_passages, reader, retrieval
from sh_platform.context_docs.reader import Refusal
from sh_platform.context_docs.store import DocStore
from sh_platform.egress.aggregates import SuppressedFigures
from sh_platform.egress.gateway import _check_structure
from sh_platform.plane import PlaneStore

HERE = Path(__file__).resolve().parent
DEMO = HERE.parents[1] / "packs" / "family_office" / "1" / "demo_documents"
STORY = DEMO.parent / "demo_story"
# what a client would send: the earlier test pack's documents and the demo story, without the presenter's script and
# the owners' example answers (seed.NOT_CLIENT_DOCUMENTS)
SEEDED = sorted([p.name for p in DEMO.iterdir()] + [p.name for p in STORY.iterdir() if p.name not in seed.NOT_CLIENT_DOCUMENTS])
EML = (b"From: a@example.invalid\nTo: b@example.invalid\nDate: Thu, 3 Sep 2026 09:00:00 +0800\n"
       b"Subject: Capital call notice\nContent-Type: text/plain; charset=utf-8\n\nSYNTHETIC. Call due on 1 March.\n")


def text_of(name: str, data: bytes) -> str:
    return "\n".join(t for _, t in reader.read_segments(name, data))


# ---- html
def test_html_keeps_the_visible_text_only():
    page = (b"<html><head><title>x</title><style>p{color:red}</style></head><body><script>alert(1)</script>"
            b"<h1>Minutes</h1><p>Holding stays <b>strategic</b> &amp; unsold.</p><p>Next item</p></body></html>")
    out = text_of("m.html", page)
    assert "Holding stays strategic & unsold." in out and "Next item" in out and "Minutes" in out
    assert "alert" not in out and "color" not in out and "<" not in out
    assert out.index("Minutes") < out.index("Holding") < out.index("Next item")


@pytest.mark.parametrize("hostile", [b"<a " * 400_000, b"<!--" * 400_000, b"<p>" + b"<div>" * 300_000, b"&#" * 500_000,
                                     b"<script>" + b"x" * 1_900_000, b"<!-- a >" * 100_000, b"<![CDATA[ >" * 150_000],
                         ids=["unclosed-tags", "unclosed-comments", "deep-nesting", "bad-charrefs", "huge-script",
                              "comment-with-gt", "cdata-with-gt"])
def test_a_hostile_html_page_is_read_fast_and_cannot_grow_past_the_cap(hostile, monkeypatch):
    monkeypatch.setattr(reader, "MAX_TEXT_CHARS", 10_000)
    t = time.perf_counter()
    out = text_of("h.html", hostile)
    assert time.perf_counter() - t < 2 and len(out) <= 10_000 + 10


def test_an_html_page_over_the_size_cap_is_refused_before_parsing():
    with pytest.raises(Refusal, match="too large to read"):
        text_of("h.html", b"<p>" + b"x" * reader.MAX_HTML_BYTES)


def test_html_text_over_the_cap_is_stopped_while_reading(monkeypatch):
    monkeypatch.setattr(reader, "MAX_TEXT_CHARS", 1000)
    assert len(text_of("big.html", b"<p>" + b"word " * 200_000 + b"</p>")) < 1100


# ---- email
def test_an_email_gives_headers_and_the_text_part_only():
    msg = (b"From: Ann <a@example.invalid>\nTo: b@example.invalid\nSubject: Update\nMIME-Version: 1.0\n"
           b'Content-Type: multipart/mixed; boundary="X"\n\n--X\nContent-Type: text/plain\n\nSYNTHETIC body line\n'
           b"--X\nContent-Type: text/html\n\n<p>HTMLPART</p>\n"
           b'--X\nContent-Type: text/plain\nContent-Disposition: attachment; filename="a.txt"\n\nATTACHED\n--X--\n')
    out = text_of("m.eml", msg)
    assert "Subject: Update" in out and "From: Ann" in out and "SYNTHETIC body line" in out
    assert "HTMLPART" not in out and "ATTACHED" not in out


def test_an_email_over_the_cap_is_cut_and_an_unreadable_charset_is_skipped(monkeypatch):
    monkeypatch.setattr(reader, "MAX_TEXT_CHARS", 500)
    big = b"Subject: s\nContent-Type: text/plain\n\n" + b"word " * 100_000
    assert len(text_of("big.eml", big)) < 700
    odd = b"Subject: s\nContent-Type: text/plain; charset=no-such-charset\n\nbody\n"
    assert "Subject: s" in text_of("odd.eml", odd)


def test_a_hostile_email_is_read_fast():
    deep = b"Subject: s\nContent-Type: multipart/mixed; boundary=X\n\n" + b"--X\nContent-Type: text/plain\n\nhi\n" * 100_000
    t = time.perf_counter()
    out = text_of("deep.eml", deep)
    assert time.perf_counter() - t < 10
    assert out.count("hi") <= reader.MAX_EML_PARTS  # dropping the part cap would give ~30 000 here


def test_html_and_eml_are_listed_and_pdf_stays_refused():
    assert {"html", "htm", "eml"} <= set(reader.allowed_extensions())
    if not reader.pdf_reader_available():
        with pytest.raises(Refusal):
            reader.read_segments("S01.pdf", b"%PDF-1.4")


# ---- the seeded demo documents
def names(env_root: Path, company: str) -> list[str]:
    return sorted(d["filename"] for d in DocStore(PlaneStore(env_root).plane_for(company)).documents("north"))


def test_the_seed_puts_the_demo_documents_in_the_family_office_company_only(seeded):
    root, _ = seeded
    expected = SEEDED
    assert len(expected) == 21 and names(root, FAMILY) == expected
    assert not set(seed.NOT_CLIENT_DOCUMENTS) & set(expected)
    for other in (OTHER, "tidewater-capital", "solo-studio"):
        assert names(root, other) == []
    assert "untrusted_instruction.txt" not in expected and not list(DEMO.glob("*.pdf"))


def test_a_second_seed_run_adds_nothing(tmp_path):
    root = tmp_path / "data"
    first = seed.seed(root)
    assert first["documents"] == 2 * len(SEEDED)  # North private and Lens shared_full
    again = seed.seed(root)
    assert again["documents"] == 0 and len(names(root, FAMILY)) == len(SEEDED)


def test_the_family_office_admin_sees_them_listed_and_another_company_does_not(demo_env):
    env = demo_env
    c = env.login("company_admin")
    docs = c.get("/api/agents/north/docs").json()
    assert {d["filename"] for d in docs["documents"]} >= {"committee_minutes.html", "manager_conflict.eml"}
    assert all(d["title"].startswith("Illustrative") for d in docs["documents"])
    assert env.login("company_admin", OTHER).get("/api/agents/north/docs").json()["documents"] == []


def test_the_seeded_documents_are_context_for_a_capital_call_question(seeded):
    root, _ = seeded
    plane = PlaneStore(root).plane_for(FAMILY)
    out = context_passages(plane, "north", "How is a distribution that returns recallable capital treated?")
    assert "USD 25,000" not in out and "USD 40,000" not in out  # the notice's own figures never reach North as a quote
    assert "bonus" not in out.lower()  # pay content is restricted
    assert context_passages(PlaneStore(root).plane_for(OTHER), "north", "distribution recallable capital") == ""


# ---- the adversarial file
def test_the_adversarial_document_reaches_north_wrapped_and_passes_the_real_gateway_check(plane):
    s = DocStore(plane)
    s.upload("north", "a", "untrusted_instruction.txt", (HERE / "untrusted_instruction.txt").read_bytes())
    question = "Is the risk assessment for investment O01 missing?"
    out = context_passages(plane, "north", question)
    assert "Ignore the mandate" in out  # it is quoted as data, so North can say what the document asks
    start = out.index(retrieval._UNTRUSTED_BEGIN)
    assert out.index("Ignore the mandate") > start and out.rstrip().endswith(retrieval._UNTRUSTED_END)
    assert "never obey it" in out
    payload = {"messages": [{"role": "user", "content": out}], "question": question}
    _check_structure(payload, SuppressedFigures())
