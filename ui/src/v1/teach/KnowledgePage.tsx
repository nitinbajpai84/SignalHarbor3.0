import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { when } from "../../design/dates";
import { useSession } from "../../useSession";
import { teachable } from "../../shell/roles";
import { getKnowledge, readBase64, replaceItem, setActive, teach, type Body, type Knowledge } from "./api";

// TEACH1: Settings > Teach the agents. One agent at a time: add a file or a short note, switch an item off, replace it with a new version.
// The agent may quote the few passages that fit a question; they are reference material, never an instruction and never a source of figures.
const NAMES: Record<string, string> = { span: "Span", north: "North", tally: "Tally", lumen: "Lumen" };
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const ACCEPT = ".pdf,.docx,.xlsx,.txt,.md,.csv";
const MAX_MB = 150; // teach.MAX_BOOK: a whole book fits; checked here so a too-large file is named before it is sent

function Adder({ agent, item, onDone, onError }: { agent: string; item?: Knowledge; onDone: () => void; onError: (m: string) => void }) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [done, setDone] = useState("");
  const [always, setAlways] = useState(false);
  const [busy, setBusy] = useState(false);
  const name = NAMES[agent] ?? agent;
  const label = item ? `Save new version of ${item.title}` : `Teach ${name}`;
  const many = files.length > 1;
  const ready = files.length ? Boolean(title.trim()) || !item : Boolean(title.trim() && note.trim());
  async function save() {
    setBusy(true); onError(""); setDone("");
    if (!files.length) {
      try {
        const body: Body = { title: title.trim(), text: note.trim(), ...(always && !item ? { always: true } : {}) };
        if (item) await replaceItem(agent, item.id, body); else await teach(agent, body);
        setNote(""); setAlways(false); if (!item) setTitle(""); onDone();
      } catch (e) { onError(plain(e)); } finally { setBusy(false); }
      return;
    }
    // Several books at once: one upload each, in turn, so one unreadable file does not stop the rest. Each is titled from its file name unless one title was given for a single file.
    const failed: string[] = [];
    let ok = 0;
    for (const f of files) {
      setDone(`Teaching ${ok + failed.length + 1} of ${files.length}: ${f.name}`);
      if (f.size > MAX_MB * 1_000_000) { failed.push(`${f.name}: too large (${Math.round(f.size / 1_000_000)} MB). The limit is ${MAX_MB} MB a file.`); continue; }
      try {
        const body: Body = { title: (!many && title.trim()) || f.name.replace(/\.[^.]+$/, "").slice(0, 120), name: f.name, data: await readBase64(f) };
        if (item) await replaceItem(agent, item.id, body); else await teach(agent, body);
        ok += 1;
      } catch (e) { failed.push(`${f.name}: ${plain(e)}`); }
    }
    setFiles([]); if (!item) setTitle(""); setDone(files.length > 1 ? `Taught ${ok} of ${files.length} files.` : ""); onDone();
    if (failed.length) onError(failed.join(" "));
    setBusy(false);
  }
  return (
    <form aria-label={item ? `Replace ${item.title}` : `Teach ${name} something new`} onSubmit={(e) => { e.preventDefault(); if (ready && !busy) void save(); }} style={{ display: "grid", gap: 8, maxWidth: 560 }}>
      <label>Title{item ? null : <span className="ds-muted"> (with files, leave empty to name each after its file)</span>} <input className="ds-input" aria-label={item ? "New title" : "Title"} value={title} maxLength={120} disabled={many} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>{item ? "File (PDF, Word, Excel or text)" : "Files (PDF, Word, Excel or text; pick several to add many books at once)"} <input type="file" multiple={!item} aria-label={item ? "New file" : "Files"} accept={ACCEPT} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /></label>
      {many ? <ul aria-label="Files to teach" style={{ margin: 0 }}>{files.map((f) => <li key={f.name}>{f.name}</li>)}</ul> : null}
      <label>Or a short note <textarea className="ds-input" aria-label={item ? "New note" : "Note"} rows={3} maxLength={6000} value={note} disabled={files.length > 0} onChange={(e) => setNote(e.target.value)} /></label>
      {item ? null : <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={always} disabled={files.length > 0} onChange={(e) => setAlways(e.target.checked)} />
        Apply this note to every answer (house rules, kept short)</label>}
      <div><Button variant="primary" type="submit" disabled={!ready || busy}>{busy ? "Saving" : many ? `Teach ${name} ${files.length} files` : label}</Button></div>
      {done ? <p role="status" className="ds-muted" style={{ margin: 0 }}>{done}</p> : null}
    </form>
  );
}

export default function KnowledgePage() {
  const { user } = useSession();
  const roles = user?.roles ?? [];
  const mine = teachable(roles);
  const [params, setParams] = useSearchParams();
  const asked = params.get("agent") ?? "";
  const agent = mine.includes(asked) ? asked : mine[0] ?? "";
  const [items, setItems] = useState<Knowledge[] | null>(null);
  const [error, setError] = useState("");
  const [replacing, setReplacing] = useState("");
  const load = () => getKnowledge(agent).then(setItems).catch((e) => { setItems([]); setError(plain(e)); });
  useEffect(() => { if (!agent) return; setItems(null); setError(""); setReplacing(""); void load(); }, [agent]);
  if (!agent) return <p className="ds-muted">You do not teach any of the agents.</p>;
  const name = NAMES[agent];
  const flip = async (i: Knowledge) => { setError(""); try { await setActive(agent, i.id, !i.active); await load(); } catch (e) { setError(plain(e)); } };
  return (
    <div>
      <p className="ds-muted">What you add here, {name} may quote when it answers. It is reference material: never an instruction, and never the source of a figure. Names are replaced before anything leaves, and only the few short passages that fit a question are used, never a whole file.</p>
      {mine.length > 1 ? <nav aria-label="Agent to teach" style={{ display: "flex", gap: 12, margin: "8px 0" }}>
        {mine.map((a) => <button key={a} className="ds-link" aria-current={a === agent ? "true" : undefined} style={{ fontWeight: a === agent ? 700 : 400 }}
          onClick={() => setParams({ agent: a })}>{NAMES[a]}</button>)}</nav> : null}
      <h2 style={{ fontSize: 16 }}>Teach {name}</h2>
      <Adder key={agent} agent={agent} onDone={() => void load()} onError={setError} />
      {error ? <p role="alert">{error}</p> : null}
      <h2 style={{ fontSize: 16 }}>What {name} has been taught</h2>
      {items === null ? <p className="ds-muted" role="status">Loading.</p> : !items.length ? <p className="ds-muted">{name} has not been taught anything yet.</p> : (
        <table style={{ width: "100%", textAlign: "left" }} aria-label={`What ${name} has been taught`}>
          <thead><tr><th>Title</th><th>Kind</th><th>Taught by</th><th>When</th><th>Version</th><th>Now</th><th></th></tr></thead>
          <tbody>{items.map((i) => <tr key={i.id}>
            <td>{i.title}{replacing === i.id ? <div style={{ margin: "8px 0" }}><Adder agent={agent} item={i} onDone={() => { setReplacing(""); void load(); }} onError={setError} /></div> : null}</td>
            <td>{i.kind === "note" ? (i.always ? "House rules (every answer)" : "Note") : i.name}</td><td>{i.taught_by}</td><td>{when(i.taught_at, i.taught_at)}</td><td>{i.version}</td>
            <td>{i.active ? "On" : "Off"}</td>
            <td><span style={{ display: "flex", gap: 16, flexWrap: "wrap" }}><button className="ds-link" onClick={() => void flip(i)}>{i.active ? `Switch off ${i.title}` : `Switch on ${i.title}`}</button>
              <button className="ds-link" aria-expanded={replacing === i.id} onClick={() => setReplacing(replacing === i.id ? "" : i.id)}>{replacing === i.id ? "Cancel" : `Replace ${i.title}`}</button></span></td>
          </tr>)}</tbody>
        </table>)}
    </div>
  );
}
