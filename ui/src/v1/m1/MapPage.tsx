import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError, Refused, apiGet, apiSend } from "../../api/client";
import { Button, Chip, EmptyState, Footnote, PageFrame, SideCard } from "../../design";
import { ConceptAnswers, ConceptView, Proposals, SuggestChange, useConcept, type Concept } from "../k2/K2Panel";

// M1 The company map (/centre/intent/graph): the ontology built underneath every conversation, read-only for every role.
// Clusters, not a hairball: the intents first, a click opens one intent's things by kind, a click on a thing opens its page (?node=).
// Frame, states and node page copied from ui/src/pages/GraphPage.tsx and NodePage.tsx, reshaped for GET /api/v1/map.

interface Note { id: string; text: string; by: string; at: string; state: string }
export interface MNode {
  id: string; type: string; label: string; restricted?: boolean; what?: string; said_by?: string; from_file?: string; from_record?: string;
  at?: string; intents?: string[]; state?: string; roles?: string[]; definition?: string; stub?: boolean; link?: string; notes?: Note[];
}
interface MEdge { from: string; to: string; type: string }
interface MapDoc { built_at: string | null; nodes: MNode[]; edges: MEdge[] }

const KIND: Record<string, string> = {
  Intent: "Intent", Person: "Person", Team: "Team", Process: "Process", Step: "Step", System: "System", Source: "Source", Document: "Document",
  Table: "Table", Field: "Field", Measure: "KPI", Term: "Term", Rule: "Rule", Decision: "Decision", Signed: "Signed document", View: "View",
  Gap: "Missing piece", Problem: "Problem", Concept: "Concept", Definition: "Definition",
};
const GROUPS: [string, string[]][] = [
  ["People and teams", ["Person", "Team"]], ["How it is done today", ["Process", "Step"]], ["Sources and documents", ["Source", "Document", "System"]],
  ["KPIs and terms", ["Measure", "Term", "Gap", "Concept", "Definition"]], ["Tables and fields", ["Table", "Field"]], ["Rules and decisions", ["Rule", "Decision"]],
  ["Signed documents and views", ["Signed", "View"]],
];
const EDGE: Record<string, string> = {
  variant_of: "is a variant of", asked_for: "asked for", spoke_to: "spoke to", owns: "owns", does: "does", uses: "uses", feeds: "feeds", defined_in: "defined in",
  derived_from: "comes from", signed_by: "signed by", shown_in: "shown in", governed_by: "governed by", supersedes: "replaces",
  step_of: "step of", decided_by: "decided by", solves: "solves", defines: "defines", owned_by: "owned by", member_of: "member of",
};
const STATE: Record<string, string> = { talking: "Talking", signed: "Signed", designed: "Designed", loaded: "Loaded", live: "Live" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso?: string) => { const d = iso ? new Date(iso) : null; return d && !Number.isNaN(d.getTime()) ? `${d.getDate()} ${MONTHS[d.getMonth()]}` : ""; };
const REST = "__rest";
const RECORD: [RegExp, string][] = [
  [/sow\.json$/, "the intent of work"], [/thread\.json$/, "the talk with North"], [/room\.json$/, "the agent room"], [/^build\/scan\//, "the source scan"],
  [/^build\/mapping\//, "the mapping sheet"], [/^build\/blueprint_conversation\//, "the approved design"], [/^build\/engineer\//, "the talk with Span"],
  [/^consume\//, "the consumption brief"], [/^glossary\//, "the company glossary"],
];
/** Where a thing came from, in plain words: a file by its name, a record by what it is (never a path or an id). */
function origin(n: MNode): string {
  const rec = n.from_record ? RECORD.find(([re]) => re.test(n.from_record!))?.[1] ?? "a company record" : "";
  const file = n.from_file ? n.from_file.split("/").pop() : "";
  return file && rec ? `${file}, read into ${rec}` : file || rec || "Not available yet";
}

function NodeChip({ n, on, active }: { n: MNode; on: (id: string) => void; active: boolean }) {
  if (n.restricted) return <span className="ds-chip" title="You may not see this one">{n.label}</span>;
  const notes = n.notes?.length ?? 0;
  return (
    <button type="button" className={`ds-chip${active ? " ds-chip--active" : ""}`} aria-pressed={active} onClick={() => on(n.id)}
      style={n.stub ? { borderStyle: "dashed" } : undefined}>
      {n.label.length > 60 ? `${n.label.slice(0, 59)}…` : n.label}{notes ? ` · ${notes} note${notes > 1 ? "s" : ""}` : ""}
    </button>
  );
}

export default function MapPage() {
  const [params, setParams] = useSearchParams();
  const [doc, setDoc] = useState<MapDoc | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "refused" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<MNode[] | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [writing, setWriting] = useState(false);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const selected = params.get("node");
  const openConcept = useConcept(selected?.startsWith("concept:") ? selected : null);

  useEffect(() => {
    let live = true;
    apiGet<MapDoc>("/api/v1/map")
      .then((d) => { if (live) { setDoc(d); setState("ready"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);

  const byId = useMemo(() => new Map((doc?.nodes ?? []).map((n) => [n.id, n])), [doc]);
  const intents = (doc?.nodes ?? []).filter((n) => n.type === "Intent" && !n.restricted);
  const pick = (id: string) => { setParams(id === selected ? {} : { node: id }, { replace: true }); setWriting(false); setNote(""); };

  async function search(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) { setHits(null); return; }
    try {
      const r = await apiGet<{ nodes: MNode[]; concepts?: Concept[] }>(`/api/v1/map/ask?q=${encodeURIComponent(q)}`);
      setHits(r.nodes); setConcepts(r.concepts ?? []);
    } catch { setHits([]); setConcepts([]); }
  }
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!selected || !text.trim()) return;
    try {
      await apiSend("POST", `/api/v1/map/node/${encodeURIComponent(selected)}/comments`, { text });
      setText(""); setWriting(false); setNote("Thank you. Everyone now sees your note on this.");
      setAttempt((a) => a + 1);
    } catch (err) { setNote(err instanceof ApiError ? err.message : "Your note could not be saved. Please try again."); }
  }

  const title = "The company map";
  const subline = "What the company told its agents, and where each thing came from. Built from every conversation and signed document.";
  if (state !== "ready" || !doc) {
    const s = state === "refused" ? ["The map is not open to you", "Ask your administrator for access."]
      : state === "error" ? ["The map could not be loaded", "Please try again."] : ["Loading the map", "One moment."];
    return (
      <div className="ds-screen"><PageFrame title={title} subline={subline}>
        <EmptyState title={s[0]!} lines={[s[1]!]} />
        {state === "error" && <Button onClick={() => setAttempt((a) => a + 1)}>Try again</Button>}
      </PageFrame></div>
    );
  }
  if (doc.nodes.length === 0) {
    return <div className="ds-screen"><PageFrame title={title} subline={subline}>
      <EmptyState title="Nothing on the map yet" lines={["The map grows as people talk to North and sign the intent of work."]} links={[{ label: "Start an intent", href: "/centre/intent" }]} />
    </PageFrame></div>;
  }

  const members = (cluster: string) => doc.nodes.filter((n) => n.type !== "Intent" && (cluster === REST ? !(n.intents?.length) : n.intents?.includes(cluster)));
  const rest = members(REST);
  const sel = selected ? byId.get(selected) : undefined;
  const out = sel ? doc.edges.filter((e) => e.from === sel.id) : [];
  const into = sel ? doc.edges.filter((e) => e.to === sel.id) : [];
  const ends = (list: MEdge[], other: (e: MEdge) => string, word: (e: MEdge) => string) => (
    <ul>{list.map((e) => { const o = byId.get(other(e)); return o && (
      <li key={`${e.from}>${e.to}>${e.type}`}>{word(e)} {o.restricted ? o.label : <button type="button" className="ds-link" onClick={() => pick(o.id)}>{o.label}</button>} <span className="ds-muted">({KIND[o.type] ?? o.type})</span></li>
    ); })}</ul>
  );

  const cluster = (id: string, label: string, sub: string, nodes: MNode[]) => (
    <div key={id} className="ds-card ds-side">
      <div className="ds-side__head">
        <button type="button" className="ds-side__title ds-link" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
          {open === id ? "▾" : "▸"} {label}
        </button>
        <span className="ds-muted">{sub}</span>
      </div>
      {open === id && GROUPS.map(([g, types]) => {
        const ns = nodes.filter((n) => types.includes(n.type));
        return ns.length > 0 && (
          <div key={g}>
            <p><strong>{g}</strong> <span className="ds-muted">{ns.length}</span></p>
            <div className="ds-frame__actions" style={{ flexWrap: "wrap" }}>{ns.map((n) => <NodeChip key={n.id} n={n} on={pick} active={n.id === selected} />)}</div>
          </div>
        );
      })}
    </div>
  );

  const nodePage = sel && !sel.restricted ? (
    <SideCard title={sel.label} action={sel.link ? { label: "Open the record", href: sel.link } : undefined}>
      <p className="ds-muted">{KIND[sel.type] ?? sel.type}{sel.state ? ` · ${STATE[sel.state] ?? sel.state}` : ""}</p>
      <p>{sel.what || "Not described yet."}</p>
      <p>{sel.said_by ? `Said by ${sel.said_by}${sel.at ? `, ${day(sel.at)}` : ""}.` : sel.at ? `Recorded ${day(sel.at)}.` : "Who said it is not recorded."}</p>
      <p>Came from: {origin(sel)}</p>
      {sel.roles?.length ? <ul>{sel.roles.map((r) => <li key={r}>{r}</li>)}</ul> : null}
      {openConcept && <ConceptView concept={openConcept} />}
      {out.length > 0 && <><p><strong>Connects to</strong></p>{ends(out, (e) => e.to, (e) => EDGE[e.type] ?? e.type)}</>}
      {into.length > 0 && <><p><strong>What depends on it</strong></p>{ends(into, (e) => e.from, (e) => `${EDGE[e.type] ?? e.type} by`)}</>}
      {sel.notes?.length ? <>
        <p><strong>{sel.notes.length} note{sel.notes.length > 1 ? "s" : ""} from {[...new Set(sel.notes.map((n) => n.by))].join(", ")}, {day(sel.notes[sel.notes.length - 1]!.at)}</strong></p>
        <ul>{sel.notes.map((n) => <li key={n.id}>{n.text} <span className="ds-muted">({n.by}, {day(n.at)}{n.state === "seen" ? ", seen" : ""})</span></li>)}</ul>
      </> : null}
      <SuggestChange key={sel.id} node={sel.id} isConcept={sel.type === "Concept"} />
      {writing ? (
        <form onSubmit={send}>
          <textarea aria-label="What looks wrong" placeholder="What looks wrong, in a sentence or two" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />
          <Button type="submit" variant="primary" disabled={!text.trim()}>Send</Button> <Button onClick={() => setWriting(false)}>Cancel</Button>
        </form>
      ) : <Button onClick={() => { setWriting(true); setNote(""); }}>Something looks wrong</Button>}
      {note && <p className="ds-soft" role="status">{note}</p>}
    </SideCard>
  ) : <SideCard title="Pick a thing"><p>Open an intent, then click anything in it to see what it is, who said it and what depends on it.</p></SideCard>;

  return (
    <div className="ds-screen">
      <PageFrame title={title} subline={subline} aside={nodePage}>
        <form onSubmit={search} className="ds-frame__actions">
          <input type="search" aria-label="Search the map" placeholder="Where does net worth come from?" value={q} onChange={(e) => setQ(e.target.value)} />
          <Button type="submit" variant="primary">Search</Button>
        </form>
        <Proposals />
        {hits && concepts.length > 0 && <SideCard title="What it means here"><ConceptAnswers concepts={concepts} onPick={pick} /></SideCard>}
        {hits && (
          <SideCard title={hits.length ? `${hits.length} found` : "Nothing found"}>
            {hits.length ? <ul>{hits.map((h) => <li key={h.id}><button type="button" className="ds-link" onClick={() => pick(h.id)}>{h.label}</button> <span className="ds-muted">({KIND[h.type] ?? h.type})</span>{h.definition ? `: ${h.definition}` : ""}</li>)}</ul>
              : <p>Try other words, for example a KPI, a file or a person.</p>}
            <Chip onClick={() => { setHits(null); setQ(""); }}>Clear</Chip>
          </SideCard>
        )}
        {intents.map((i) => cluster(i.id.slice("intent:".length), i.label, STATE[i.state ?? ""] ?? "", members(i.id.slice("intent:".length))))}
        {rest.length > 0 && cluster(REST, "The rest of the company", `${rest.length} things`, rest)}
        <Footnote>Nobody has to review this map. If something looks wrong, say so on the thing itself and the decision maker sees it.</Footnote>
        {sel && <p><Link className="ds-link" to="/centre/intent/graph">Back to the whole map</Link></p>}
      </PageFrame>
    </div>
  );
}
