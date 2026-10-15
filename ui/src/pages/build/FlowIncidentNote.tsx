import { useCallback, useEffect, useState } from "react";

import { apiGet, apiSend, Refused } from "../../api/client";
import { Button, EmptyState, Pill, SideCard } from "../../design";
import "./chain.css";
import { flowCopy } from "./flowCopy";

// Room 3: Span's notes on the open data alerts (GET /api/company/build/flow/incidents). The person acknowledges with the note, or with their own words.
interface Item {
  alert_id: string; fallback?: boolean; sentence?: string | null;
  note: { id: string; title: string; what: string; why?: string; next_step?: string; to?: string | null; can_decide?: boolean };
}
type Load = "loading" | "error" | "refused" | "ready";
const t = flowCopy.incident;

function One({ item, onDone }: { item: Item; onDone: () => void }) {
  const n = item.note;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(n.what);
  const [failed, setFailed] = useState(false);
  const done = (p: Promise<unknown>) => { setFailed(false); p.then(onDone).catch(() => setFailed(true)); };
  return (
    <SideCard title={n.title}>
      <p><Pill tone="draft">{flowCopy.flowTag}</Pill></p>
      {item.fallback && item.sentence ? <p role="status" className="ds-warn">{item.sentence}</p> : null}
      {editing
        ? <textarea className="ds-chip" aria-label="Your note" style={{ width: "100%", minHeight: 88 }} value={text} onChange={(e) => setText(e.target.value)} />
        : <p>{n.what}</p>}
      {n.why && n.why !== n.what ? <p className="bc-note">{n.why}</p> : null}
      {n.next_step ? <p><strong>{t.next}:</strong> {n.next_step}</p> : null}
      {n.can_decide ? (
        <div className="bc-actions">
          {editing ? (
            <>
              <Button variant="primary" disabled={!text.trim()} onClick={() => done(apiSend("POST", `/api/company/build/alerts/${encodeURIComponent(item.alert_id)}/ack`, { note: text.trim() }))}>{t.save}</Button>
              <Button onClick={() => { setEditing(false); setText(n.what); }}>{t.cancel}</Button>
            </>
          ) : (
            <>
              <Button variant="primary" onClick={() => done(apiSend("POST", `/api/company/build/proposals/${encodeURIComponent(n.id)}/accept`))}>{t.ack}</Button>
              <Button onClick={() => setEditing(true)}>{t.edit}</Button>
            </>
          )}
        </div>
      ) : <p className="bc-note">{t.waits(n.to ?? null)}</p>}
      {failed ? <p role="alert" className="ds-warn">{t.failed}</p> : null}
    </SideCard>
  );
}

export default function FlowIncidentNotes({ onDone }: { onDone: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [load, setLoad] = useState<Load>("loading");
  const read = useCallback(async () => {
    try { const r = await apiGet<{ incidents?: Item[] }>("/api/company/build/flow/incidents"); setItems(r.incidents ?? []); setLoad("ready"); }
    catch (e) { setLoad(e instanceof Refused ? "refused" : "error"); }
  }, []);
  useEffect(() => { void read(); }, [read]);
  if (load === "loading") return <p role="status" className="ds-soft">{t.loading}</p>;
  if (load === "refused") return <p role="alert" className="ds-soft">{t.refused}</p>;
  if (load === "error") return <div><p role="alert" className="ds-warn">{t.error}</p><Button onClick={() => { setLoad("loading"); void read(); }}>Try again</Button></div>;
  if (!items.length) return <EmptyState title={t.head} lines={[t.empty]} />;
  return <>{items.map((i) => <One key={i.note.id} item={i} onDone={() => { void read(); onDone(); }} />)}</>;
}
