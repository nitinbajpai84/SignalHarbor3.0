import { InStepper } from "../b9/context";
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import { PageFrame } from "../../design";
import * as b6 from "../b6/api";
import PlanDiagram from "../b6diagram/PlanDiagram";
import { readBase64 } from "../i6/api";
import { useProjectTitle } from "../s1/useProjectTitle";
import { Composer } from "../voice";
import * as api from "./api";
import RoomSwitcher from "./RoomSwitcher";
import { planOf, useFacts } from "./useFacts";

// BC1: Architecture room. The three layers and their tables, each opening its columns, relationships and lineage; the picture; Span beside it.
const LAYERS = [
  { id: "bronze", name: "Bronze", line: "Raw, exactly as it landed." },
  { id: "silver", name: "Silver", line: "The company model every project shares." },
  { id: "gold", name: "Gold", line: "Built for this project's dashboards." },
] as const;
type LayerId = (typeof LAYERS)[number]["id"];
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");

interface Detail { name: string; layer: LayerId; note: string; columns: { name: string; type: string; from?: string }[]; refs: string[]; up: string[]; down: string[] }

function TableDetail({ d }: { d: Detail }) {
  const hasFrom = d.columns.some((c) => c.from);
  const list = (xs: string[], none: string) => (xs.length ? <ul>{xs.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="ds-muted">{none}</p>);
  return (
    <section aria-label={`Table ${d.name}`} className="ds-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>{d.name}</h3>
      {d.note ? <p>{d.note}</p> : null}
      <h4>Columns</h4>
      {d.columns.length ? <table className="ds-table"><thead><tr><th>Column</th><th>Type</th>{hasFrom ? <th>From</th> : null}</tr></thead>
        <tbody>{d.columns.map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.type}</td>{hasFrom ? <td>{c.from ?? ""}</td> : null}</tr>)}</tbody></table> : <p className="ds-muted">The columns are not known yet. They are learned when the first file loads.</p>}
      <h4>Relationships</h4>
      {list(d.refs, "No relationship to another table.")}
      <h4>Lineage</h4>
      <p style={{ margin: 0 }}><strong>Comes from</strong></p>{list(d.up, "Nothing upstream: this is where data lands.")}
      <p style={{ margin: 0 }}><strong>Feeds</strong></p>{list(d.down, "Nothing downstream yet.")}
    </section>
  );
}

function AskSpan({ pid }: { pid: string }) {
  const [turns, setTurns] = useState<b6.Turn[]>([]);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { b6.getChat(pid).then((c) => setTurns(c.turns)).catch(() => undefined); }, [pid]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns, busy]);
  const send = async (said: string, up: File[]) => {
    if (!said && !up.length) return;
    setBusy(true); setError("");
    try {
      for (const f of up) await b6.sendChatFile(pid, f.name, await readBase64(f));
      setTurns((await b6.sendChat(pid, said, up.map((f) => f.name))).turns); setText(""); setFiles([]);
    } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  };
  return (
    <aside aria-label="Ask Span about the model" className="ds-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Ask Span about the model</h3>
      <div style={{ maxHeight: 360, overflow: "auto" }}>
        {turns.length === 0 ? <MessageBubble from="agent" who="Span" text="Hello, I am Span. Ask me why a table is there, where a column comes from, or what a change would touch." /> : null}
        {turns.map((t) => <MessageBubble key={t.id} from={t.by === "span" ? "agent" : "human"} who={t.name} text={t.text} />)}
        {busy ? <p className="ds-muted" role="status">Span is working…</p> : null}
        <div ref={end} />
      </div>
      <Composer agent="Span" text={text} setText={setText} files={files} setFiles={setFiles} onSend={(s, f) => void send(s, f)} busy={busy} error={error} />
    </aside>
  );
}

export default function ArchitectureRoom() {
  const { projectId = "" } = useParams();
  const inStepper = useContext(InStepper); // the step rail already carries these links
  const title = useProjectTitle(projectId);
  const facts = useFacts(projectId);
  const plan = planOf(facts.plan);
  const [layers, setLayers] = useState<api.Layers | null>(null);
  const [open, setOpen] = useState<{ name: string; layer: LayerId } | null>(null);
  const [shown, setShown] = useState<Detail | null>(null);
  const [problem, setProblem] = useState("");
  useEffect(() => { api.getLayers().then(setLayers).catch(() => undefined); }, []);

  const names = useMemo<Record<LayerId, string[]>>(() => {
    const t = facts.tables;
    const own = (l: LayerId) => plan?.tables.filter((x) => x.layer === l).map((x) => x.name) ?? [];
    const merge = (l: LayerId) => [...new Set([...(t?.[l] ?? []), ...own(l)])];
    return { bronze: merge("bronze"), silver: merge("silver"), gold: merge("gold") };
  }, [facts.tables, plan]);

  const edges = plan?.lineage ?? [];
  const pick = useCallback(async (name: string, layer: LayerId) => {
    setOpen({ name, layer }); setProblem("");
    const mine = plan?.tables.find((x) => x.name === name);
    const up = new Set([...(mine?.depends_on ?? []), ...edges.filter((e) => e.to === name).map((e) => e.from)]);
    const down = new Set(edges.filter((e) => e.from === name).map((e) => e.to));
    plan?.tables.forEach((x) => { if (x.depends_on.includes(name)) down.add(x.name); });
    let extra: api.TableDetail | null = null;
    if (!mine) { try { extra = await api.getTable(name); } catch { /* bronze and gold tables outside the plan are not described by the model route */ } }
    const row = [...(layers?.bronze ?? []), ...(layers?.gold ?? [])].find((r) => r.name === name);
    const refs = [...new Set((extra?.refs ?? []).map((r) => `${r.from.table}${r.from.column ? `.${r.from.column}` : ""} points to ${r.to.table}${r.to.column ? `.${r.to.column}` : ""}`))];
    (extra?.refs ?? []).forEach((r) => { const o = r.from.table === name ? r.to.table : r.from.table; if (r.from.table !== name) down.add(o); else up.add(o); });
    setShown({
      name, layer, up: [...up], down: [...down], refs,
      note: mine?.purpose ?? extra?.note ?? (row ? `Lands from ${row.source}.` : ""),
      columns: mine ? mine.columns : (extra?.columns ?? []).map((c) => ({ name: c.name, type: c.type, from: c.note })),
    });
    if (!mine && !extra && !row) setProblem("We could not read that table just now.");
  }, [plan, edges, layers]);

  return (
    <PageFrame title={`${title}: Architecture`} subline="The system and the data model for this project, from raw files to the tables dashboards read."
      crumbs={inStepper ? undefined : <><Link className="ds-link" to="/centre/build">All projects</Link> · <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}`}>Plan and Span</Link></>}>
      <RoomSwitcher pid={projectId} current="architecture" facts={facts} />
      <div className="b8-split">
        <div>
          {!facts.ready ? <p className="ds-muted" role="status">Reading the model.</p> : LAYERS.map((l) => (
            <section key={l.id} className="b8-layer" data-layer={l.id} aria-label={`${l.name} layer`}>
              <h2 style={{ margin: 0, fontSize: 18 }}>{l.name} <span className="ds-muted" style={{ fontWeight: 400, fontSize: 14 }}>{names[l.id].length} tables · {l.line}</span></h2>
              {names[l.id].length ? names[l.id].map((n) => <button key={n} type="button" className="b8-chip" aria-pressed={open?.name === n} onClick={() => void pick(n, l.id)}>{n}</button>)
                : <p className="ds-muted">No tables in this layer for this project yet.</p>}
            </section>))}
          {problem ? <p role="alert">{problem}</p> : null}
          {shown ? <TableDetail d={shown} /> : facts.ready ? <p className="ds-muted">Choose a table to see its columns, relationships and lineage.</p> : null}
          <details style={{ marginTop: 16 }} open><summary>The picture of this build</summary><PlanDiagram projectId={projectId} /></details>
        </div>
        <AskSpan pid={projectId} />
      </div>
    </PageFrame>
  );
}
