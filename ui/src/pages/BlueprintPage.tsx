import HandOverStrip from "./build/HandOverStrip";
import DesignDocPanel from "./build/DesignDocPanel";
import SpanModelPanel from "./build/SpanModelPanel";
import SuggestionsPanel from "./build/SuggestionsPanel";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { getBlueprint, putBlueprint, shown, signBlueprint, type Blueprint, type Hidden, type NoBlueprint } from "../api/build";
import { Refused } from "../api/client";
import { Button, Chip, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, Signature, Strip, type PillTone } from "../design";
import { useSession } from "../useSession";
import { BuildState, day, type LoadState } from "./BuildCentre";

// The blueprint screen (SHAPES 2, sh_platform/build/blueprint.py). Every line shows its mark and source; a company admin may edit a text field until
// it is signed. Provenance is keyed by dotted path ("lineage.0.transform"); a line without its own entry falls back to its row ("lineage.0").

type Ctx = { bp: Blueprint; canEdit: boolean; save: (path: string, value: string) => Promise<void> };
const MARK = { stated: "Stated", guessed: "Guessed" } as const;
const SEVERITY: Record<string, PillTone> = { block: "failed", warn: "late", inform: "draft" };

function markOf(bp: Blueprint, path: string): string {
  const row = path.split(".").slice(0, path.startsWith("model.") ? 3 : 2).join(".");
  const p = bp.provenance[path] ?? bp.provenance[row] ?? Object.entries(bp.provenance).find(([k]) => k.startsWith(`${row}.`))?.[1];
  if (!p) return "Unknown · Nothing says";
  // signing states every line the Architect guessed: the signature is the person's confirmation; the source stays named
  return bp.state === "signed" && p.mark === "guessed" ? `Stated at signing · drafted from ${p.from}` : `${MARK[p.mark]} · ${p.from}`;
}

function Mark({ bp, path }: { bp: Blueprint; path: string }) {
  return <span className="ds-muted">{markOf(bp, path)}</span>;
}

function Field({ ctx, path, value, label }: { ctx: Ctx; path: string; value: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(value);
  const [err, setErr] = useState("");
  if (open) {
    return (
      <span className="ds-comment__decide">
        <input aria-label={label} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
        <Button variant="primary" disabled={!text.trim()} onClick={() => {
          ctx.save(path, text.trim()).then(() => { setOpen(false); setErr(""); }).catch(() => setErr("That change could not be saved."));
        }}>Save</Button>
        <Button onClick={() => setOpen(false)}>Cancel</Button>
        {err ? <span role="alert" className="ds-warn">{err}</span> : null}
      </span>
    );
  }
  return (
    <span>
      {value}{" "}
      {ctx.canEdit ? <button type="button" className="ds-chip" aria-label={`Edit ${label}`} onClick={() => { setText(value); setOpen(true); }}>Edit</button> : null}
    </span>
  );
}

const ROW = 56;
/** A long mart name may break after each underscore, so the lineage table fits its card. */
const breakable = (id: string) => id.split("_").flatMap((part, i) => (i ? [<wbr key={i} />, `_${part}`] : [part]));
/** One arrow per pair: two lineage lines into the same mart draw one arrow. */
const once = <T,>(xs: T[], key: (x: T) => string) => [...new Map(xs.map((x) => [key(x), x])).values()];

// The model drawn without a library: sources on the left, marts, facts as boxes, their dimensions on the right.
function Diagram({ bp }: { bp: Blueprint }) {
  const lineage = bp.lineage.filter(shown);
  const sources = [...new Set(lineage.map((l) => l.source))];
  const marts = [...new Set(lineage.map((l) => l.mart))];
  const facts = bp.model.facts, dims = bp.model.dimensions;
  const h = Math.max(sources.length, marts.length, facts.length, dims.length, 1) * ROW + 10;
  const y = (i: number) => 10 + i * ROW;
  const box = (x: number, i: number, label: string, kind: string) => (
    <g key={`${kind}-${label}`} data-box={kind}>
      <rect x={x} y={y(i)} width={170} height={40} rx={4} fill="none" stroke="currentColor" />
      <text x={x + 8} y={y(i) + 24} fontSize={12} fill="currentColor">{label.length > 24 ? `${label.slice(0, 23)}…` : label}</text>
    </g>
  );
  const arrow = (x1: number, i1: number, x2: number, i2: number, key: string) => (
    <line key={key} x1={x1} y1={y(i1) + 20} x2={x2} y2={y(i2) + 20} stroke="currentColor" markerEnd="url(#arrowhead)" />
  );
  return (
    <svg role="img" aria-label="Diagram of the model: sources, marts, facts and dimensions" viewBox={`0 0 840 ${h}`} width="100%">
      <defs><marker id="arrowhead" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="currentColor" /></marker></defs>
      {once(lineage, (l) => `${l.source}|${l.mart}`).map((l) => arrow(180, sources.indexOf(l.source), 220, marts.indexOf(l.mart), `s-${l.source}-${l.mart}`))}
      {facts.flatMap((f, fi) => once(lineage.filter((l) => f.measures.includes(l.measure)), (l) => l.mart).map((l) => arrow(390, marts.indexOf(l.mart), 430, fi, `m-${f.name}-${l.mart}`)))}
      {facts.flatMap((f, fi) => dims.map((d, di) => (d.keys.some((k) => f.keys.includes(k)) ? arrow(600, fi, 640, di, `d-${f.name}-${d.name}`) : null)))}
      {sources.map((s, i) => box(10, i, s, "source"))}
      {marts.map((m, i) => box(220, i, m, "mart"))}
      {facts.map((f, i) => box(430, i, f.name, "fact"))}
      {dims.map((d, i) => box(640, i, d.name, "dimension"))}
    </svg>
  );
}

/** Rows of a table; a row the person may not see reads Restricted in its first column, so the numbering stays the same for everyone. */
function rows<T extends object>(list: (T | Hidden)[], first: string, row: (r: T, i: number) => Record<string, ReactNode>): Record<string, ReactNode>[] {
  return list.map((r, i) => (shown(r) ? row(r, i) : { [first]: <Pill tone="restricted">Restricted</Pill> }));
}

export default function BlueprintPage() {
  const { user } = useSession();
  const [state, setState] = useState<LoadState>("loading");
  const [got, setGot] = useState<Blueprint | NoBlueprint | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [signErr, setSignErr] = useState("");
  useEffect(() => {
    let live = true;
    getBlueprint()
      .then((r) => { if (live) { setGot(r); setState("populated"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);
  const retry = () => { setState("loading"); setAttempt((n) => n + 1); };

  const bp = got && got.state !== "none" ? got : null;
  const admin = !!user?.roles.includes("company_admin");
  const signed = bp?.state === "signed";
  const ctx: Ctx | null = bp && { bp, canEdit: admin && !signed, save: async (path, value) => setGot(await putBlueprint(path, value)) };
  const sign = () => {
    signBlueprint().then((b) => { setGot(b); setSignErr(""); })
      .catch(() => setSignErr("The blueprint could not be signed. If it is drafted from a draft baseline, sign the baseline first."));
  };
  const sources = (measures: string[]) => [...new Set(bp?.lineage.filter(shown).filter((l) => measures.includes(l.measure)).map((l) => l.source))].join(" · ");

  return (
    <PageFrame
      crumbs={<Link className="ds-link" to="/centre/build">Build centre · Architect your design</Link>}
      title="Blueprint"
      subline={bp ? `Version ${bp.version} · planned for ${bp.band} · drafted by Span, the architect, from the signed catalogue` : "The design the pipelines are built from."}
      actions={<>{bp ? <Pill tone={signed ? "signed" : "draft"}>{signed ? "Signed" : "Draft"}</Pill> : null}<Chip href="/centre/build/architecture">Draw the diagram</Chip></>}
      aside={bp ? (
        <>
          <SideCard title="Approval" action={signed ? { label: "Go to Build the data", href: "/centre/build" } : undefined}>
            <Signature
              state={signed ? "signed" : "waiting"}
              by={signed ? bp.signed_by.map((s) => `${s.name} (${s.role})`).join(", ") : "the head of data"}
              at={signed && bp.signed_by[0] ? day(bp.signed_by[0].at) : undefined}
              onSign={admin && !signed ? sign : undefined} />
            {signErr ? <p role="alert" className="ds-warn">{signErr}</p> : null}
            <p>{signed ? "Signed means read-only. Room 2 is open: the pipelines are built from this design." : "Signing makes the design read-only and opens room 2. A change after that starts the next version beside it."}</p>
          </SideCard>
          <SideCard title="Marks">
            <p>Guessed: drafted by Span from the named source. Stated: confirmed or edited by a person; signing the design states every line.</p>
          </SideCard>
          <Footnote>Every line is drawn from the company's signed records; nothing is written by hand.</Footnote>
        </>
      ) : undefined}
    >
      <HandOverStrip />
      <BuildState state={state} onRetry={retry}>
        {got?.state === "none" ? <EmptyState title="No blueprint yet" lines={[got.message]} links={[{ label: "Back to the Build centre", href: "/centre/build" }]} /> : null}
        {bp && ctx ? (
          <>
            {bp.basis === "draft baseline" ? <p role="status" className="ds-warn">Drafted from a draft baseline: sign the baseline first.</p> : null}
            <Strip label="Draft model · facts and their sources">
              {bp.model.facts.map((f, i) => (
                <SideCard key={f.name} title={`Fact: ${f.name}`}>
                  <p>Grain: <Field ctx={ctx} path={`model.facts.${i}.grain`} value={f.grain} label={`grain of ${f.name}`} /></p>
                  <p>Keys: {f.keys.join(", ")} · Measures: {f.measures.join(", ") || "none you may see"}</p>
                  <p>Sources: {sources(f.measures) || "Not available yet"}</p>
                  <p><Mark bp={bp} path={`model.facts.${i}.grain`} /></p>
                </SideCard>
              ))}
              {bp.model.dimensions.map((d, i) => (
                <SideCard key={d.name} title={`Dimension: ${d.name}`}>
                  <p>Keys: {d.keys.join(", ")} · Attributes: {d.attributes.join(", ") || "none named yet"} · History: type {d.scd}</p>
                  <p><Mark bp={bp} path={`model.dimensions.${i}.keys`} /></p>
                </SideCard>
              ))}
            </Strip>
            <Strip label="Diagram">
              <div className="ds-card ds-side ds-soft"><Diagram bp={bp} /></div>
            </Strip>
            <Strip label="Lineage · each measure traced">
              <DataTable
                columns={[{ key: "measure", label: "Measure and mart" }, { key: "source", label: "Source and fields" }, { key: "transform", label: "Transform" }, { key: "mark", label: "Mark and source" }]}
                rows={rows(bp.lineage, "measure", (l, i) => ({
                  measure: <>{l.measure}<br /><span className="ds-muted">{breakable(l.mart)}</span></>,
                  source: <>{l.source}<br /><span className="ds-muted">{l.fields.join(", ")}</span></>,
                  transform: <Field ctx={ctx} path={`lineage.${i}.transform`} value={l.transform} label={`transform of ${l.measure}`} />,
                  mark: <Mark bp={bp} path={`lineage.${i}.transform`} />,
                }))} />
            </Strip>
            <Strip label="Rules carried from the scan" tone="amber">
              <DataTable
                columns={[{ key: "measure", label: "Measure" }, { key: "rule", label: "Rule" }, { key: "severity", label: "Severity" }, { key: "mark", label: "Mark and source" }]}
                rows={rows(bp.rules, "measure", (r, i) => ({
                  measure: r.measure,
                  rule: <Field ctx={ctx} path={`rules.${i}.rule`} value={r.rule} label={`rule ${r.measure} ${i + 1}`} />,
                  severity: <Pill tone={SEVERITY[r.severity] ?? "draft"}>{r.severity}</Pill>,
                  mark: <><Mark bp={bp} path={`rules.${i}.rule`} /> · from the {r.from}</>,
                }))} />
            </Strip>
            <Strip label="Access rules from the seals" tone="amber">
              <DataTable
                columns={[{ key: "mart", label: "Mart" }, { key: "may", label: "Who may see it" }, { key: "mark", label: "Mark and source" }]}
                rows={rows(bp.access, "mart", (a, i) => ({
                  mart: a.mart, may: a.may_see ? a.may_see.join(", ") : "Not restricted: as the catalogue says",
                  mark: <Mark bp={bp} path={`access.${i}.may_see`} />,
                }))} />
            </Strip>
            <Strip label="Schedule">
              <DataTable
                columns={[{ key: "source", label: "Source" }, { key: "expected", label: "Expected" }, { key: "sla", label: "Ready by" }, { key: "after", label: "After" }, { key: "mark", label: "Mark and source" }]}
                rows={bp.schedule.map((s, i) => ({
                  source: s.source,
                  expected: <Field ctx={ctx} path={`schedule.${i}.expected`} value={s.expected} label={`expected time of ${s.source}`} />,
                  sla: <Field ctx={ctx} path={`schedule.${i}.sla`} value={s.sla} label={`ready-by of ${s.source}`} />,
                  after: s.depends_on.join(", ") || "Nothing",
                  mark: <Mark bp={bp} path={`schedule.${i}.expected`} />,
                }))} />
            </Strip>
            <Strip label="Infrastructure">
              <SideCard title="Where it runs">
                <p>Warehouse: <Field ctx={ctx} path="infra.warehouse" value={bp.infra.warehouse} label="warehouse" /> <Mark bp={bp} path="infra.warehouse" /></p>
                <p>Runner: <Field ctx={ctx} path="infra.runner" value={bp.infra.runner} label="runner" /> <Mark bp={bp} path="infra.runner" /></p>
              </SideCard>
            </Strip>
          </>
        ) : null}
      </BuildState>
      <SpanModelPanel />
      <SuggestionsPanel />
      <DesignDocPanel />
    </PageFrame>
  );
}
