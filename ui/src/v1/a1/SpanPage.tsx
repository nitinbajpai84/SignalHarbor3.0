import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import Panel from "../../components/Panel";
import { Button, DataTable, PageFrame, Pill } from "../../design";
import { Composer, SpeakButton, useReadAloud } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import ProjectTag, { useProjectId } from "../p1/ProjectTag";
import { getSheet, type SheetView } from "../g3/api";
import { useProposals } from "../workbench/proposals";
import { approve, getBlueprint, kindOf, readBase64, sendSpan, type Blueprint, type Layers, type ModelTable } from "./api";
import ModeLine from "../router/ModeLine";
import UsedLine from "../teach/UsedLine";

// A1: /centre/build/:iid. L1: the conversation with Span is docked on the right of the workbench; on the left a strip of three documents:
// System design (the layers diagram, with what Span read), Data model, and Benchmarks and governance (questions, scan, approval).
// The design document draws the design record's data layers the way the Archify specs in docs/architecture do: one band per layer,
// boxes, links left to right.

const STATUS = { available: ["ok", "Available"], partly: ["late", "Partly"], not: ["failed", "Not yet"] } as const;

const when = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

const BOX_W = 170, BOX_H = 46, GAP_X = 56, GAP_Y = 14, HEAD = 34;

/** The design record's layers as Archify draws an architecture: a band per layer, a box per component, links left to right. */
function LayerDiagram({ layers }: { layers: Layers }) {
  const cols = layers.columns;
  const rows = Math.max(1, ...cols.map((c) => c.items.length));
  const W = cols.length * (BOX_W + GAP_X) - GAP_X + 24, H = HEAD + rows * (BOX_H + GAP_Y) + 16;
  const at = new Map<string, { x: number; y: number }>();
  cols.forEach((c, i) => c.items.forEach((it, j) => at.set(it.id, { x: 12 + i * (BOX_W + GAP_X), y: HEAD + j * (BOX_H + GAP_Y) })));
  return (
    <div className="wb-svg">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} role="group" aria-label="Design layers">
        {cols.map((c, i) => (
          <g key={c.kind}>
            <rect x={4 + i * (BOX_W + GAP_X)} y={4} width={BOX_W + 16} height={H - 8} rx={10} fill="var(--ds-surface)" stroke="var(--ds-line-2)" strokeDasharray="4 4" />
            <text x={12 + i * (BOX_W + GAP_X) + BOX_W / 2} y={24} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--ds-ink)">{c.title}</text>
          </g>
        ))}
        {layers.links.map((l, k) => {
          const a = at.get(l.from), b = at.get(l.to);
          if (!a || !b) return null;
          const x1 = a.x + BOX_W, y1 = a.y + BOX_H / 2, x2 = b.x, y2 = b.y + BOX_H / 2, m = (x1 + x2) / 2;
          return <path key={k} d={`M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`} fill="none" stroke="var(--ds-teal-bright)" strokeWidth={1.5} opacity={0.7} />;
        })}
        {cols.flatMap((c) => c.items.map((it) => {
          const p = at.get(it.id)!;
          return (
            <g key={it.id}>
              <title>{it.about || it.label}</title>
              <rect x={p.x} y={p.y} width={BOX_W} height={BOX_H} rx={8} fill="var(--ds-surface)" stroke={c.kind === "gold" ? "var(--ds-teal-bright)" : "var(--ds-line-2)"} strokeWidth={1.5} />
              <text x={p.x + BOX_W / 2} y={p.y + BOX_H / 2 + 4} textAnchor="middle" fontSize={12} fill="var(--ds-ink)">
                {it.label.length > 24 ? `${it.label.slice(0, 23)}…` : it.label}
              </text>
            </g>
          );
        }))}
      </svg>
    </div>
  );
}

function DesignDoc({ bp, iid }: { bp: Blueprint; iid: string }) {
  if (!bp.design || !bp.layers) return <p className="ds-muted">Span draws the three layers here once it has drafted the design.</p>;
  return (
    <>
      {bp.design.fallback && bp.design.message ? <p className="ds-muted">{bp.design.message}</p> : null}
      <LayerDiagram layers={bp.layers} />
      <ul style={{ paddingLeft: 18 }}>{bp.design.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
      <Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/design`}>Open the full design</Link>
    </>
  );
}

function ModelDiagram({ tables }: { tables: ModelTable[] }) {
  const facts = tables.filter((t) => t.kind === "fact"), dims = tables.filter((t) => t.kind === "dimension");
  if (!facts.length || !dims.length) return null;
  const n = Math.max(facts.length, dims.length), W = 2 * BOX_W + 120, H = n * (BOX_H + GAP_Y) + 8;
  const y = (i: number) => 4 + i * (BOX_H + GAP_Y);
  const box = (t: ModelTable, x: number, yy: number) => (
    <g key={t.table}><rect x={x} y={yy} width={BOX_W} height={BOX_H} rx={8} fill="var(--ds-surface)" stroke="var(--ds-line-2)" strokeWidth={1.5} />
      <text x={x + BOX_W / 2} y={yy + BOX_H / 2 + 4} textAnchor="middle" fontSize={12} fill="var(--ds-ink)">{t.table}</text></g>
  );
  return (
    <div className="wb-svg">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} role="group" aria-label="Data model diagram">
        {facts.flatMap((f, i) => dims.map((d, j) => (f.relationships.some((r) => r.includes(d.table)) || d.keys.some((k) => f.keys.includes(k))
          ? <line key={`${f.table}-${d.table}`} x1={4 + BOX_W} y1={y(i) + BOX_H / 2} x2={W - 4 - BOX_W} y2={y(j) + BOX_H / 2} stroke="var(--ds-teal-bright)" strokeWidth={1.5} opacity={0.7} />
          : null)))}
        {facts.map((f, i) => box(f, 4, y(i)))}
        {dims.map((d, j) => box(d, W - 4 - BOX_W, y(j)))}
      </svg>
    </div>
  );
}

function ModelDoc({ tables }: { tables: ModelTable[] }) {
  if (!tables.length) return <p className="ds-muted">Span writes the data model here: the report tables, their grain, keys and relationships.</p>;
  return (
    <>
      <ModelDiagram tables={tables} />
      <DataTable columns={[{ key: "t", label: "Table" }, { key: "g", label: "Grain" }, { key: "k", label: "Keys" }, { key: "r", label: "Relationships" }, { key: "h", label: "History" }, { key: "m", label: "Measures" }]}
        rows={tables.map((t) => ({ t: <>{t.table} <span className="ds-muted">({t.kind})</span></>, g: t.grain || "Not stated", k: t.keys.join(", "),
          r: t.relationships.join("; "), h: t.history, m: t.measures.join(", ") }))} />
    </>
  );
}

function QuestionsTab({ bp, onAnswer }: { bp: Blueprint; onAnswer: (q: string) => void }) {
  if (!bp.questions.length) return <p className="ds-muted">Decisions Span cannot take alone appear here, each with Span's proposed default.</p>;
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
      {bp.questions.map((q) => (
        <li key={q.id}>
          <strong>{q.question}</strong>{" "}
          {q.settled ? <Pill tone="signed">{q.defaulted ? "Default accepted" : "Settled"}</Pill> : <Pill tone="open">Open</Pill>}
          <div>{q.settled ? `Answer: ${q.answer}` : `Span suggests: ${q.default || "no default yet"}`}</div>
          {q.why ? <div className="ds-muted">{q.why}</div> : null}
          {!q.settled && bp.can_talk ? <button type="button" className="ds-link" onClick={() => onAnswer(q.question)}>Answer in the conversation</button> : null}
        </li>
      ))}
    </ul>
  );
}

function ScanTab({ bp, iid }: { bp: Blueprint; iid: string }) {
  if (!bp.scan) return <p className="ds-muted">Span scans the landing files per measure once the design is drafted.</p>;
  const can = bp.scan.kpis.filter((k) => k.status !== "not").length;
  return (
    <>
      <p style={{ marginTop: 0 }}>These {can} of {bp.scan.kpis.length} can be built now.{bp.scan.agreed ? ` Scope agreed by ${bp.scan.agreed.by}.` : ""}</p>
      <ul style={{ paddingLeft: 18 }}>
        {bp.scan.kpis.map((k) => (
          <li key={k.code}>{k.name} <Pill tone={STATUS[k.status][0]}>{STATUS[k.status][1]}</Pill>
            {k.missing.length ? <div className="ds-muted">Missing: {k.missing.map((m) => m.what).join("; ")}</div> : null}</li>
        ))}
      </ul>
      <Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/scan`}>Open the scan</Link>
    </>
  );
}

function ReadSummary({ bp, iid }: { bp: Blueprint; iid: string }) {
  const sig = bp.sow.signature;
  const layer = (l: string) => bp.sow.catalogue.filter((t) => t.layer === l).length;
  const enc = encodeURIComponent(iid);
  return (
    <section>
      <p style={{ margin: "12px 0 0" }}>
        <strong>Intent of work</strong>, version {bp.sow.version}{sig ? `, signed by ${sig.name} on ${when(sig.at)}` : ", not signed yet"}.{" "}
        <Link className="ds-link" to={`/centre/intent/${enc}/sow`}>Read it</Link>
      </p>
      <p style={{ margin: "4px 0" }}>{bp.sow.kpis.length} measures: {bp.sow.kpis.map((k) => k.name).join(", ") || "none"}.</p>
      <p style={{ margin: "4px 0" }}>{bp.sow.sources.length} sources. Catalogue: {layer("landing")} landing, {layer("silver")} cleaned, {layer("gold")} report tables.</p>
      <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>What Span has drafted</h3>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        <li>Design: {bp.design ? <Link className="ds-link" to={`/centre/build/${enc}/design`}>drafted</Link> : "not yet"}</li>
        <li>Scan: {bp.scan ? <Link className="ds-link" to={`/centre/build/${enc}/scan`}>read</Link> : "not yet"}</li>
        <li>Mapping sheet: {bp.mapping ? <Link className="ds-link" to={`/centre/build/${enc}/mapping`}>{`version ${bp.mapping.version}, ${bp.mapping.rows} rows, ${bp.mapping.unclear} unclear`}</Link> : "not yet"}</li>
      </ul>
      <p className="ds-muted" style={{ margin: "8px 0 0" }}>Skill: {bp.skill}</p>
    </section>
  );
}

function Approval({ bp, busy, onApprove }: { bp: Blueprint; busy: boolean; onApprove: () => void }) {
  if (bp.state === "approved") {
    return <Panel tight title="Approved"><p style={{ margin: 0 }}>Approved by {bp.approved_by}{bp.approved_at ? ` on ${when(bp.approved_at)}` : ""}. Span handed the design and the mapping sheet to the build.</p></Panel>;
  }
  if (!bp.design || !bp.scan || !bp.mapping) return null;
  return (
    <Panel tight title="For the head of data">
      <ul style={{ margin: "0 0 8px", paddingLeft: 18 }}>{bp.summary.map((l, i) => <li key={i}>{l}</li>)}</ul>
      {bp.can_approve ? <Button variant="primary" disabled={busy} onClick={onApprove}>Approve design and mapping for the engineer</Button>
        : <p className="ds-muted" style={{ margin: 0 }}>The head of data approves this.</p>}
    </Panel>
  );
}

/** The benchmark sheet as Span reads it: each measure, the figure the person reports today and what to expect after the load. */
function BenchSheet({ iid }: { iid: string }) {
  const [view, setView] = useState<SheetView | null | "none">(null);
  const pid = useProjectId(iid);
  useEffect(() => {
    let live = true;
    getSheet(iid).then((v) => { if (live) setView(v); }, () => { if (live) setView("none"); });
    return () => { live = false; };
  }, [iid]);
  if (view === null) return <p className="ds-muted">Opening the benchmark sheet…</p>;
  const rows = view === "none" ? [] : view.sheet.rows.filter((r) => !r.dropped);
  if (!rows.length) return <p className="ds-muted">There is no benchmark sheet yet. North drafts it with the intent of work.</p>;
  return (
    <>
      <p className="ds-muted" style={{ marginTop: 0 }}>Each measure carries the figure the person reports today and what to expect after the load.</p>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {rows.map((r) => (
          <li key={r.id}>{r.kpi ?? r.code}{Object.values(r.dims ?? {}).length ? ` (${Object.values(r.dims).join(", ")})` : ""}:{" "}
            reported {r.reported ?? "not given yet"}, expect {r.expected ?? "not set"}{r.tolerance !== null ? `, within ${r.tolerance}` : ""}.</li>
        ))}
      </ul>
      {pid ? <p style={{ margin: "4px 0 0" }}><Link className="ds-link" to={`/centre/project/${encodeURIComponent(pid)}?artefact=benchmarks`}>Open the benchmark sheet</Link></p> : null}
    </>
  );
}

function BenchDoc({ bp, iid, onAnswer, busy, onApprove }: { bp: Blueprint; iid: string; onAnswer: (q: string) => void; busy: boolean; onApprove: () => void }) {
  return (
    <>
      <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>Benchmarks</h3>
      <BenchSheet iid={iid} />
      <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>Questions for the head of data</h3>
      <QuestionsTab bp={bp} onAnswer={onAnswer} />
      <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>Scan</h3>
      <ScanTab bp={bp} iid={iid} />
      <Approval bp={bp} busy={busy} onApprove={onApprove} />
    </>
  );
}

/** The Build Centre: one conversation with Span, the blueprint drafted beside it. */
export default function SpanPage() {
  const { iid = "" } = useParams();
  const [bp, setBp] = useState<Blueprint | null>(null);
  const [failed, setFailed] = useState("");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try { setBp(await getBlueprint(iid)); setFailed(""); } catch (err) { setFailed(plain(err)); }
  }, [iid]);
  useEffect(() => { void load(); }, [load]);
  const pr = useProposals(iid, bp?.proposals, load);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [bp, busy]);

  async function act(fn: () => Promise<Blueprint>, after?: () => void) {
    setBusy(true);
    setError("");
    try { setBp(await fn()); after?.(); } catch (err) { setError(plain(err)); } finally { setBusy(false); }
  }

  function send(said: string, up: File[]) {
    void act(async () => sendSpan(iid, said, await Promise.all(up.map(async (f) => ({ name: f.name, data: await readBase64(f), kind: kindOf(f.name) })))),
      () => { setText(""); setFiles([]); });
  }
  const lastSpan = bp?.turns.filter((t) => t.by === "span").at(-1);
  useReadAloud(lastSpan ? { id: lastSpan.id, text: lastSpan.text } : null);

  if (failed) return <PageFrame title="Build Centre"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  if (!bp) return <PageFrame title="Build Centre"><p className="ds-muted">Opening the conversation…</p></PageFrame>;

  const signed = bp.sow.state === "signed";
  const closed = !signed || !bp.can_talk;
  const docs: Doc[] = [
    { id: "design", title: "System design", render: () => <><DesignDoc bp={bp} iid={iid} /><ReadSummary bp={bp} iid={iid} /></> },
    { id: "model", title: "Data model", proposes: ["design"], render: () => <ModelDoc tables={bp.data_model} /> },
    { id: "bench", title: "Benchmarks and governance", render: () => (
      <BenchDoc bp={bp} iid={iid} busy={busy} onApprove={() => void act(() => approve(iid))}
        onAnswer={(q) => { setText(`On "${q}": `); box.current?.focus(); }} />) },
  ];
  return (
    <PageFrame title={`Blueprint: ${bp.title}`} subline="Talk to Span, the build agent. Span drafts the design, the data model, the scan and the mapping sheet as you go.">
      <ProjectTag iid={iid} />
      <Workbench layoutKey="span" documents={docs} agent="Span" iid={iid} proposals={pr.proposals} onAccept={pr.onAccept} onReject={pr.onReject} changeError={pr.error} changeBusy={pr.busy} canAdd={bp.can_talk}
        chatHead={<>
          <p style={{ margin: 0 }}><strong>Span</strong> <span className="ds-muted">the architect · {busy ? "working" : bp.state === "approved" ? "handed to the build" : bp.state === "ready" ? "ready for approval" : "waiting for you"}</span></p>
          <ModeLine />
        </>}
        chatLog={<>
          {!signed ? <p className="ds-muted">The intent of work is not signed yet. Span builds from the signed version only.</p> : null}
          {bp.greeting && signed ? <MessageBubble from="agent" who="Span" text={bp.greeting} /> : null}
          {bp.turns.map((t) => (
            <MessageBubble key={t.id} from={t.by === "span" ? "agent" : "human"} who={t.name} when={when(t.at)} text={t.text} tags={t.did ?? []}>
              {t.by === "span" ? <SpeakButton text={t.text} /> : null}
              {t.id === lastSpan?.id ? <UsedLine used={bp.used} /> : null}
            </MessageBubble>
          ))}
          {busy ? <p className="ds-muted" role="status">Span is working…</p> : null}
          <div ref={end} />
        </>}
        composer={<Composer agent="Span" text={text} setText={setText} files={files} setFiles={setFiles} onSend={send} busy={busy} disabled={closed}
          error={error} boxRef={box} placeholder={bp.state === "approved" ? "Approved and handed to the build." : closed ? "Only the architect talks to Span." : undefined} />} />
    </PageFrame>
  );
}
