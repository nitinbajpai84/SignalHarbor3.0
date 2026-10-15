import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { apiSend, downloadFile } from "../../api/client";
import { Button, Chip, DataTable, EmptyState, PageFrame, Pill, SideCard } from "../../design";
import { BuildState, day, useLoad } from "../../pages/BuildCentre";
import "../../pages/build/chain.css";
import { moment as chainMoment } from "../../pages/build/chain";

// B1: copied from 2.0 pages/build/ArchitecturePage.tsx; adds Span's design note from the signed intent of work and the ask button.
const moment = (m: string): string => (m === "sow_signed" ? "Span drafted it from the signed intent of work" : chainMoment(m));
const NO_DESIGN = "No design yet. Span drafts the three layers once the intent of work is signed.";
interface Note { lines: string[]; fallback: boolean; message: string | null; at: string; asked_by: string; blueprint_version: number; record_version: number; counts: Record<string, number> }
interface Design { intent_id: string; sow_state: string; title: string | null; design: Note | null; can_draft: boolean }

type View = "data" | "infrastructure" | "enterprise";
const VIEWS: [View, string][] = [["data", "Data"], ["infrastructure", "Infrastructure"], ["enterprise", "Enterprise solution"]];
interface Comp {
  id: string; label: string; kind: string; view: View; owner: string | null; owner_id?: string | null; version: number; state: string; restricted?: boolean;
  description?: { text: string; mark: string } | null; interfaces?: { to: string; kind: string; contract: string | null }[];
  changed_by?: { id: string; title: string }[];
}
interface Spec { components?: { id: string; label: string; pos?: { x: number; y: number }; size?: { w: number; h: number } }[]; connections?: { id: string; from: string; to: string; label?: string }[] }
interface Arch {
  version: number; regenerated: { moment: string; by: string; at: string } | null;
  counts: Record<View, number>; versions: { v: number; moment: string; at: string }[];
  components: Comp[]; diagram: Spec | null; focus_ids?: string[]; html_url?: string | null;
  this_version?: { added: number; changed: number; retired: number } | null;
  changes?: { id: string; title: string; added: number; changed: number }[];
  owners_missing?: { id: string; label: string }[];
  people?: { id: string; name: string }[];
  can_edit?: boolean; can_download?: boolean;
}

// The diagram is drawn from the stored Archify spec with plain SVG (no renderer library). A restricted component is a box with no name.
function Diagram({ spec, comps, dim, onPick }: { spec: Spec; comps: Comp[]; dim: Set<string> | null; onPick: (id: string) => void }) {
  const list = spec.components ?? [];
  const by = new Map(list.map((c) => [c.id, c]));
  const restricted = new Set(comps.filter((c) => c.restricted).map((c) => c.id));
  const W = Math.max(600, ...list.map((c) => (c.pos?.x ?? 0) + (c.size?.w ?? 160) + 20));
  const H = Math.max(240, ...list.map((c) => (c.pos?.y ?? 0) + (c.size?.h ?? 60) + 20));
  const mid = (id: string) => { const c = by.get(id); return { x: (c?.pos?.x ?? 0) + (c?.size?.w ?? 160) / 2, y: (c?.pos?.y ?? 0) + (c?.size?.h ?? 60) / 2 }; };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Architecture diagram">
      {(spec.connections ?? []).map((l) => { const a = mid(l.from), b = mid(l.to); return <line key={l.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--ds-line-2)" strokeWidth={1.5} />; })}
      {list.map((c) => {
        const x = c.pos?.x ?? 0, y = c.pos?.y ?? 0, w = c.size?.w ?? 160, h = c.size?.h ?? 60, hit = !dim || dim.has(c.id);
        return (
          <g key={c.id} tabIndex={0} role="button" aria-label={restricted.has(c.id) ? "Restricted" : c.label} opacity={hit ? 1 : 0.35} onClick={() => onPick(c.id)} onKeyDown={(e) => { if (e.key === "Enter") onPick(c.id); }}>
            <rect x={x} y={y} width={w} height={h} rx={8} fill="var(--ds-surface)" stroke={hit && dim ? "var(--ds-teal-bright)" : "var(--ds-line-2)"} strokeWidth={hit && dim ? 2.5 : 1.5} />
            <text x={x + w / 2} y={y + h / 2} textAnchor="middle" fontSize={14} fill="var(--ds-ink)">{restricted.has(c.id) ? "Restricted" : c.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Selected({ comp, arch, reload }: { comp: Comp; arch: Arch; reload: () => void }) {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState(comp.description?.text ?? "");
  const [err, setErr] = useState("");
  const save = (body: object) => apiSend("PUT", `/api/company/build/architecture/components/${encodeURIComponent(comp.id)}`, body).then(() => { setErr(""); setEdit(false); reload(); }).catch(() => setErr("That change could not be saved."));
  if (comp.restricted) return <SideCard title="Selected"><p>Restricted</p></SideCard>;
  return (
    <SideCard title="Selected" action={{ label: "Open on the map", href: `/centre/intent/map/component:${encodeURIComponent(comp.id)}` }}>
      <p><strong>{comp.label}</strong></p>
      {edit ? (
        <label className="bc-field">Description<textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} />
          <span className="bc-actions"><Button variant="primary" disabled={!text.trim()} onClick={() => { void save({ description: text.trim() }); }}>Save</Button><Button onClick={() => setEdit(false)}>Cancel</Button></span></label>
      ) : (
        <p>{comp.description?.text ?? "Not available yet: no record describes it."} {arch.can_edit ? <Button onClick={() => { setText(comp.description?.text ?? ""); setEdit(true); }}>Edit description</Button> : null}</p>
      )}
      {arch.can_edit && arch.people ? (
        <label className="bc-field">Owner
          <select value={comp.owner_id ?? ""} onChange={(e) => { void save({ owner: e.target.value || null }); }}>
            <option value="">No owner yet</option>
            {arch.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select></label>
      ) : <p>Owner: {comp.owner ?? "No owner yet"}</p>}
      <p>Version {comp.version}</p>
      {comp.interfaces?.length ? <ul className="bc-lines">{comp.interfaces.map((i, k) => <li key={k}>{i.kind} {i.to}{i.contract ? <> · <Link to="/centre/build/pipelines">contract</Link></> : null}</li>)}</ul> : <p className="bc-note">No interfaces recorded.</p>}
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
    </SideCard>
  );
}

function SpanNote({ note, canDraft, busy, onAsk, err }: { note: Note | null; canDraft: boolean; busy: boolean; onAsk: () => void; err: string }) {
  return (
    <SideCard title="Span's design">
      {note ? (
        <>
          {note.fallback && note.message ? <p className="bc-note">{note.message}</p> : null}
          <ul className="bc-lines">{note.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <p className="bc-note">Drafted by Span from the signed intent of work. Asked by {note.asked_by}. The blueprint is version {note.blueprint_version}, still a draft for a person to sign.</p>
        </>
      ) : <p>{NO_DESIGN}</p>}
      {canDraft ? <Button variant="primary" disabled={busy} onClick={onAsk}>{note ? "Ask Span to draft again" : "Ask Span for the design"}</Button> : null}
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
    </SideCard>
  );
}

/** /centre/build/:iid/design: Span's three layers from the signed SOW, drawn on 2.0's architecture record. */
export default function DesignPage() {
  const { iid = "" } = useParams();
  const d = useLoad<Design>(`/api/v1/build/${encodeURIComponent(iid)}/design`);
  const [busy, setBusy] = useState(false);
  const [askErr, setAskErr] = useState("");
  const ask = () => { setBusy(true); apiSend("POST", `/api/v1/build/${encodeURIComponent(iid)}/design`).then(() => { setAskErr(""); d.retry(); retry(); }).catch(() => setAskErr("Span could not draft the design. Try again.")).finally(() => setBusy(false)); };
  const note = d.data?.design ?? null;
  const [q, setQ] = useSearchParams();
  const view = (VIEWS.find(([k]) => k === q.get("view"))?.[0] ?? "data") as View;
  const v = q.get("v"), focus = q.get("focus");
  const [pick, setPick] = useState<string | null>(null);
  const path = `/api/company/build/architecture?view=${view}${v ? `&v=${encodeURIComponent(v)}` : ""}${focus ? `&focus=${encodeURIComponent(focus)}` : ""}`;
  const { data: a, state, retry } = useLoad<Arch>(path);
  const set = (k: string, val: string | null) => { const n = new URLSearchParams(q); if (val) n.set(k, val); else n.delete(k); setQ(n); };
  const comps = (a?.components ?? []).filter((c) => c.view === view);
  const sel = comps.find((c) => c.id === (pick ?? (focus && focus !== "change" ? focus : null))) ?? null;
  const dim = focus === "change" && a?.focus_ids ? new Set(a.focus_ids) : null;
  const empty = state === "populated" && (!a || (a.version === 0 && !a.components.length));
  return (
    <PageFrame
      crumbs={<Link to="/centre/build">Build centre</Link>}
      title={d.data?.title ? `Design: ${d.data.title}` : "Design"}
      subline={note ? `Drafted by Span from the signed intent of work on ${day(note.at)}. Version ${note.record_version} of the architecture.` : NO_DESIGN}
      aside={a && !empty && note ? (
        <>
          <SpanNote note={note} canDraft={!!d.data?.can_draft} busy={busy} onAsk={ask} err={askErr} />
          {sel ? <Selected comp={sel} arch={a} reload={retry} /> : <SideCard title="Selected"><p>Pick a component to see its interfaces and history.</p></SideCard>}
          <SideCard title="This version">
            {a.this_version ? <p>{a.regenerated ? `Made when ${moment(a.regenerated.moment)}, by ${a.regenerated.by}. ` : ""}Added {a.this_version.added}, changed {a.this_version.changed}, retired {a.this_version.retired}.</p> : <p>First version.</p>}
            {a.versions.length > 1 ? <Chip onClick={() => { const prev = a.versions[a.versions.length - 2]; const n = new URLSearchParams(q); if (prev) n.set("v", String(prev.v)); n.set("focus", "change"); setQ(n); }}>Compare with the previous version</Chip> : null}
          </SideCard>
          <SideCard title="What changed">
            {a.changes?.length ? <ul className="bc-lines">{a.changes.map((c) => <li key={c.id}><Link to={`/centre/build/change/${encodeURIComponent(c.id)}`}>{c.id} added {c.added} component{c.added === 1 ? "" : "s"}, changed {c.changed} ({c.title})</Link></li>)}</ul> : <p>Nothing changed since the previous version.</p>}
          </SideCard>
          {a.owners_missing?.length ? (
            <SideCard title="Owners missing">
              <p>{a.owners_missing.length} component{a.owners_missing.length === 1 ? " has" : "s have"} no owner: {a.owners_missing.map((m) => m.label).join(", ")}</p>
              <ul className="bc-lines">{a.owners_missing.map((m) => <li key={m.id}><button type="button" className="ds-chip" onClick={() => setPick(m.id)}>{m.label}</button></li>)}</ul>
            </SideCard>
          ) : null}
        </>
      ) : undefined}
    >
      <BuildState state={state} onRetry={retry}>
        {empty || !note ? (<><EmptyState title="Not available yet" lines={[d.data?.sow_state && d.data.sow_state !== "signed" ? "The intent of work is not signed yet." : NO_DESIGN]} /><SpanNote note={note} canDraft={!!d.data?.can_draft} busy={busy} onAsk={ask} err={askErr} /></>) : a ? (
          <>
            <div className="bc-actions" role="group" aria-label="Views">
              {VIEWS.map(([k, label]) => (a.counts[k] ? <Chip key={k} tone={k === view ? "active" : "default"} onClick={() => { set("view", k); setPick(null); }}>{label} ({a.counts[k]})</Chip> : <span key={k} className="ds-chip ds-muted">{label}: None yet</span>))}
              {focus === "change" ? <Chip tone="active" onClick={() => set("focus", null)}>This change only</Chip> : null}
              <label className="bc-field">Version
                <select value={v ?? String(a.version)} onChange={(e) => set("v", e.target.value === String(a.version) ? null : e.target.value)}>
                  {[...a.versions].reverse().map((x) => <option key={x.v} value={x.v}>{`Version ${x.v}${x.v === a.version ? " (current)" : ""}, ${moment(x.moment)}, ${day(x.at)}`}</option>)}
                  {!a.versions.length ? <option value={a.version}>Version 1</option> : null}
                </select></label>
              {a.can_download && a.html_url ? <Button onClick={() => { void downloadFile(a.html_url as string, "architecture.html"); }}>Download the diagram</Button> : null}
            </div>
            <div className="bc-only-wide ds-card bc-diagram" style={{ marginTop: "var(--ds-s2)" }}>
              {a.diagram?.components?.length ? <Diagram spec={a.diagram} comps={a.components} dim={dim} onPick={setPick} /> : <p>Nothing drawn yet for this view.</p>}
            </div>
            <p className="bc-only-phone bc-note">Open the diagram on a larger screen.</p>
            {comps.length ? (
              <>
                <div className="bc-only-wide" style={{ marginTop: "var(--ds-s3)" }}>
                  <DataTable columns={[{ key: "n", label: "Name" }, { key: "k", label: "Kind" }, { key: "o", label: "Owner" }, { key: "v", label: "Version" }, { key: "s", label: "State" }, { key: "c", label: "Changed by" }]}
                    rows={comps.map((c) => ({
                      n: c.restricted ? "Restricted" : <button type="button" className="ds-chip" onClick={() => setPick(c.id)}>{c.label}</button>,
                      k: c.kind, o: c.restricted ? "" : c.owner ?? "No owner yet", v: c.version, s: <Pill tone={c.state === "live" ? "signed" : "draft"}>{c.state}</Pill>,
                      c: c.changed_by?.length ? c.changed_by.map((x) => <Link key={x.id} to={`/centre/build/change/${encodeURIComponent(x.id)}`}>{x.title} ({x.id}) </Link>) : "",
                    }))} />
                </div>
                <ul className="bc-only-phone bc-rows" style={{ listStyle: "none", padding: 0 }} aria-label="Components">
                  {comps.map((c) => (
                    <li key={c.id} className="ds-card bc-row">
                      <button type="button" className="ds-chip" onClick={() => setPick(c.id)}>{c.restricted ? "Restricted" : c.label}</button>
                      <span className="bc-note">{c.kind}{c.restricted ? "" : ` · ${c.owner ?? "No owner yet"}`} · {c.state}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : <p className="bc-note" style={{ marginTop: "var(--ds-s3)" }}>No components yet.</p>}
          </>
        ) : null}
      </BuildState>
    </PageFrame>
  );
}
