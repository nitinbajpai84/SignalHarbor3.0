"""M2-E4: the one download, "the signed baseline": a zip with the business glossary (Excel and printable page), the data catalogue (Excel, all its
sheets) and a short "Read me first" page. Everything is built FOR THE VIEWER by the exports that already exist (a measure, row or field they may not
see is not in any file). Before signing the same bundle is a draft and every document says "Draft, not signed". Stdlib only."""
import io
import zipfile
from html import escape
from typing import Callable

from modules.m2_baseline.domain import catalogue as C
from modules.m2_baseline.domain import glossary_export as E
from modules.m2_baseline.store import ambiguities as SA
from modules.m2_baseline.store import catalogue as SC
from modules.m2_baseline.store import glossary as SG
from modules.m2_baseline.store import technical as ST

DRAFT = "Draft, not signed"
FILE = "signed-baseline.zip"
DRAFT_FILE = "draft-baseline.zip"


def stamp_for(view: dict) -> str:
    return f"Signed: version {view['version']}, {str(view['signed_at'])[:10]}" if view["status"] == "signed" else DRAFT


def read_me(company: str, view: dict, gate: dict, risks: list[dict], counts: dict, whole: bool) -> str:
    """The "Read me first" page: what was signed, by whom and when, the fingerprints, the counts, the known risks and what was left out."""
    e, signed = escape, view["status"] == "signed"
    li = lambda xs: ("<ul>" + "".join(f"<li>{e(x)}</li>" for x in xs) + "</ul>") if xs else "<p>None.</p>"  # noqa: E731
    sigs = [f"{s['label']}: {s['name']}, {str(s['at'])[:10]}" + (f" ({s['note']})" if s.get("note") else "") for s in view["signatures"]]
    docs = [f"{d['name']}: fingerprint (sha256) {d['sha256']}, built {str(d['built_at'])[:19].replace('T', ' ')} UTC" for d in view.get("documents") or [] if d.get("sha256")]
    risk_lines = [f"{r['kpi_name']}: {r['text']} Accepted by {r['by']}: {r.get('reason') or r.get('resolution')}" for r in risks]
    out_lines = [f"{r['name']}: {r['reason']} (by {r['by']})" for r in gate["left_out"]]
    if signed:
        top = ("<h2>What was signed</h2><p>Two documents: the <b>Business glossary</b> and the <b>Data catalogue</b> (with its technical definitions, governance and "
               "known risks). A fingerprint is a code worked out from the whole document at signing; if the document changes later, its code changes.</p>" + li(docs)
               + ("" if whole else "<p>The fingerprints cover the whole documents. Your copy shows only what you may see, so it is not identical.</p>")
               + "<h2>Signed by</h2>" + li(sigs))
    else:
        top = ("<h2>This is a draft</h2><p>Nothing here is signed or ready to hand on yet. It shows where the baseline stands today.</p>"
               + li([gate["refusal"] or "Everything needed is in place. The baseline can be signed."]))
    body = (f'<h1>Read me first: {e(E.one_line(company, 120))} baseline <span class="tag">{e(stamp_for(view))}</span></h1>' + top
            + "<h2>In numbers</h2>" + li([f"{n} {w}" for w, n in counts.items()]) + "<h2>Known risks accepted</h2>" + li(risk_lines)
            + "<h2>Left out of this baseline</h2>" + li(out_lines))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Read me first: {e(E.one_line(company, 120))}</title><style>body{{font:15px/1.45 system-ui,sans-serif;margin:2rem;max-width:60rem;color:#111}}"
            ".tag{border:1px solid #b45309;color:#b45309;border-radius:4px;padding:0 .4rem;font-size:.55em;vertical-align:middle}"
            f"@media print{{body{{margin:0}}}}</style></head><body>{body}</body></html>")


def build(plane, baseline_id: str, viewer: C.Viewer, sees: Callable[[dict], bool], company: str, view: dict, gate: dict, whole: bool) -> bytes:
    """The zip, as bytes, for this viewer. `view` is the sign-off view (status, version, signatures, documents); `gate` the gate as this viewer sees it;
    `whole`: this viewer sees every measure (the organiser)."""
    stamp = stamp_for(view)
    rows, unmatched = SG.rows_for_download(plane, baseline_id, sees)
    shown, _ = ST.catalogue_for(plane, baseline_id, viewer)
    left = {r["kpi_id"] for r in gate["left_out"]}
    risks = [a for a in SA.listing(plane, baseline_id, viewer, sees) if a["status"] == "accepted" and a["kpi_id"] not in left]
    counts = {"measures in the baseline": gate["measures"]["total"], "measures ready to build": gate["measures"]["ready"], "glossary entries": len(rows),
              "sources in the catalogue": len(shown["sources"]), "tables": len(shown["tables"]), "fields": len(shown["fields"]), "known risks": len(risks)}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("read-me-first.html", read_me(company, view, gate, risks, counts, whole))
        z.writestr("business-glossary.xlsx", E.build_xlsx(company, rows, unmatched, stamp=stamp))
        z.writestr("business-glossary.html", E.to_html(company, rows, unmatched, stamp=stamp))
        z.writestr("data-catalogue.xlsx", SC.export(plane, baseline_id, viewer, stamp))
    return out.getvalue()
