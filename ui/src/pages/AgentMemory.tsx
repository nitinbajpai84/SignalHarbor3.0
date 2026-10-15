import { useCallback, useEffect, useState } from "react";

import { apiGet, apiSend } from "../api/client";
import { Button, EmptyState } from "../design";

// What the agents have learned from conversations (mem_routes.py): the person's own lines grouped by agent, to correct or forget one by one;
// the company's lines are read by everyone and changed only by those who may.
export interface Learned { id: string; agent: string; agent_name: string; kind: string; text: string; sure: string | null; at: string; source: { said?: string } }
const KIND: Record<string, string> = { preference: "Preference", fact: "Something you said", correction: "A correction you made", term: "An agreed word" };
const SURE: Record<string, string> = { said: "you said it", inferred: "worked out from what you asked", model: "suggested by the model, shown to you first" };
const day = (iso: string) => (iso || "").slice(0, 10);

export default function AgentMemory({ company = false, canEdit = false }: { company?: boolean; canEdit?: boolean }) {
  const base = company ? "/api/v1/memory/company" : "/api/v1/memory/me";
  const [items, setItems] = useState<Learned[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [adding, setAdding] = useState("");
  const load = useCallback(() => {
    setFailed(false);
    apiGet<{ items?: Learned[] }>(base).then((r) => setItems(r.items ?? [])).catch(() => setFailed(true));
  }, [base]);
  useEffect(() => { setItems(null); load(); }, [load]);
  const act = (p: Promise<unknown>) => p.then(load).catch(() => setFailed(true));
  const may = !company || canEdit;

  if (failed) return <div role="alert"><p>What the agents learned did not load. Nothing was changed.</p><Button onClick={load}>Try again</Button></div>;
  if (items === null) return <p className="ds-muted" role="status">Reading what the agents learned.</p>;
  const by = items.reduce<Record<string, Learned[]>>((acc, i) => { (acc[i.agent_name] ??= []).push(i); return acc; }, {});
  return (
    <section aria-label={company ? "What the agents learned about the company" : "What the agents learned from your conversations"}>
      <h2 style={{ fontSize: 16 }}>{company ? "Agreed with the company" : "Learned from your conversations"}</h2>
      {items.length === 0 && <EmptyState title="Nothing yet" lines={[company ? "No agreed words or company notes yet." : "The agents have not learned anything from your conversations yet. Say \"from now on\" or \"always\" and they will tell you what they remember."]} />}
      {Object.entries(by).map(([agent, rows]) => (
        <div key={agent}>
          {!company && <h3 style={{ fontSize: 14 }}>{agent} remembers</h3>}
          {rows.map((i) => (
            <div key={i.id} className="ds-card ds-side">
              <span className="ds-muted">{KIND[i.kind] ?? i.kind}, {day(i.at)}{i.sure ? `, ${SURE[i.sure] ?? i.sure}` : ""}</span>
              {editing?.id === i.id
                ? <textarea className="ds-chip" aria-label="Correct this memory" value={editing.text} onChange={(e) => setEditing({ id: i.id, text: e.target.value })} />
                : <p>{i.text}</p>}
              {i.source?.said && !company && <p className="ds-muted">From: "{i.source.said}"</p>}
              {may && (
                <div className="ds-frame__actions">
                  {editing?.id === i.id
                    ? <Button variant="primary" onClick={() => { void act(apiSend("PATCH", `${base}/${i.id}`, { text: editing.text })); setEditing(null); }}>Save correction</Button>
                    : <Button onClick={() => setEditing({ id: i.id, text: i.text })}>Correct</Button>}
                  <Button onClick={() => void act(apiSend("DELETE", `${base}/${i.id}`))}>Forget this</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
      {company && canEdit && (
        <form onSubmit={(e) => { e.preventDefault(); if (adding.trim()) { void act(apiSend("POST", base, { text: adding.trim() })); setAdding(""); } }}>
          <label>Add a company note <input className="ds-input" value={adding} onChange={(e) => setAdding(e.target.value)} /></label>{" "}
          <Button type="submit">Add</Button>
        </form>
      )}
    </section>
  );
}
