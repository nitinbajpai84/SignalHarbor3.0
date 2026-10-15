import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DownloadButton from "../../components/DownloadButton";
import { Chip, PageFrame, day, time } from "../../design";
import { getShared, type SharedList } from "../cxui/api";
import AskLumen from "./AskLumen";
import { PublishedDashboards, SharedWithYou } from "./SharedAndDashboards";
import { getLibrary, type Library, type ReportRow } from "./api";
import { Loading, Status, plain } from "./format";

// E5: the reports library. Each report keeps every version; a signed version never changes, and a new figure makes a new version someone signs again.
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function Versions({ r, pptx }: { r: ReportRow; pptx: boolean }) {
  return (
    <ul aria-label={`${r.name}: versions`} style={{ listStyle: "none", padding: 0, margin: "8px 0" }}>
      {[...r.versions].reverse().map((v) => (
        <li key={v.id}>
          <Link className="ds-link" to={v.link}>Version {v.number}</Link> <Status s={v.state} />{" "}
          <span className="ds-muted">{v.signed_by ? `${v.signed_by}, ` : ""}{day(v.issued_at)}</span>{" "}
          {v.pdf ? <DownloadButton path={v.pdf} fallbackName={`${slug(r.name)}-v${v.number}.pdf`} label={`PDF, version ${v.number}`} /> : null}
          {v.pptx && pptx ? <DownloadButton path={v.pptx} fallbackName={`${slug(r.name)}-v${v.number}.pptx`} label={`PowerPoint, version ${v.number}`} /> : null}
        </li>
      ))}
    </ul>
  );
}

function Card({ r, pdf, pptx }: { r: ReportRow; pdf: boolean; pptx: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="ds-card" aria-label={r.name} style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>{r.link ? <Link className="ds-link" to={r.link}>{r.name}</Link> : r.name}</h3>
        <Status s={r.state} />
      </div>
      <p>{r.summary}</p>
      {r.version ? <p className="ds-muted">Version {r.version}{r.signed_by ? ` · ${r.signed_by}` : ""}{r.signed_at ? ` · ${day(r.signed_at)}` : ""}{time(r.signed_at) ? `, ${time(r.signed_at)}` : ""}</p> : null}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        {r.pdf && pdf ? <DownloadButton path={r.pdf} fallbackName={`${slug(r.name)}.pdf`} label="PDF" /> : null}
        {r.pptx && pptx ? <DownloadButton path={r.pptx} fallbackName={`${slug(r.name)}.pptx`} label="PowerPoint" /> : null}
        {r.pdf && !pdf ? <span className="ds-muted">A PDF cannot be made on this server.</span> : null}
        {r.versions.length ? <button type="button" className="ds-link" aria-expanded={open} onClick={() => setOpen(!open)}>Versions</button> : null}
      </div>
      {open ? <Versions r={r} pptx={pptx} /> : null}
    </article>
  );
}

export default function ReportsLibrary() {
  const [lib, setLib] = useState<Library | null>(null);
  const [only, setOnly] = useState<"all" | "waiting">("all");
  const [error, setError] = useState("");
  const [shared, setShared] = useState<SharedList | null>(null);
  useEffect(() => { getLibrary().then(setLib, (e) => setError(plain(e))); }, []);
  useEffect(() => { getShared().then(setShared, () => setShared({ dashboards: [], brief: null })); }, []);
  const title = "Reports";
  if (error) return <PageFrame title={title}><p role="alert">{error}</p></PageFrame>;
  if (!lib) return <PageFrame title={title}><Loading what="the reports library" /></PageFrame>;
  const shown = lib.reports.filter((r) => only === "all" || r.state === "Awaiting signature");
  return (
    <PageFrame crumbs={<>{lib.reports.length} REPORTS · EVERY SIGNED ONE NAMES ITS SIGNER</>} title={title}
      subline="Each report keeps every version. A signed version never changes; a new figure makes a new version that someone signs again.">
      <div role="group" aria-label="Find a report" style={{ display: "flex", gap: 8, margin: "8px 0" }}>
        <Chip tone={only === "all" ? "active" : "default"} onClick={() => setOnly("all")}>All · {lib.reports.length}</Chip>
        <Chip tone={only === "waiting" ? "active" : "default"} onClick={() => setOnly("waiting")}>Awaiting signature · {lib.waiting}</Chip>
      </div>
      {shown.length === 0 ? <p className="ds-muted">Nothing is waiting for a signature.</p> : <div style={{ display: "grid", gap: 12 }}>{shown.map((r) => <Card key={r.id} r={r} pdf={lib.pdf_available} pptx={!!lib.pptx_available} />)}</div>}
      <SharedWithYou shared={shared} />
      <PublishedDashboards shared={shared} />
      <section aria-label="Company reports">
        <h3>Company reports</h3>
        <nav aria-label="Company reports" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Link className="ds-link" to="/centre/consume/office">Office view</Link>
          <Link className="ds-link" to="/centre/consume/managers">Managers</Link>
          <Link className="ds-link" to="/centre/consume/benchmark">Benchmark</Link>
          <Link className="ds-link" to="/centre/consume/figures">Signed KPIs and offers</Link>
          <Link className="ds-link" to="/centre/action/evidence">Statements and evidence</Link>
          <Link className="ds-link" to="/centre/library">Library</Link>
        </nav>
      </section>
      <section aria-label="Delivered each morning">
        <h3>Delivered each morning</h3>
        {lib.delivery.map((d) => <p key={d.href}>{d.text} <Link className="ds-link" to={d.href}>{d.action}</Link></p>)}
        <p>How the Morning Note looks in Slack. <Link className="ds-link" to="/centre/operations#deliveries">See Slack</Link></p>
      </section>
      <AskLumen />
    </PageFrame>
  );
}
