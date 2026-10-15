import { useCallback, useEffect, useState } from "react";

import { apiGet, apiSend, Refused } from "../../api/client";
import { Button, Pill, SideCard } from "../../design";
import "./chain.css";
import { flowCopy, setAside, type Quarantined } from "./flowCopy";

// Room 2: Span's note on one run (GET and POST /api/company/build/flow/runs/{id}[/explain]) and the rows set aside, from the run record.
interface Note { lines?: string[]; text?: string | null; fallback?: boolean; sentence?: string | null; first_missing_link?: string | null }
type Load = "loading" | "error" | "refused" | "ready";
const t = flowCopy.run;

/** "12 rows set aside for <check>", one line per check, straight from the run record. Nothing when nothing was set aside. */
export function SetAside({ held }: { held?: (Quarantined & { masked?: boolean })[] }) {
  if (!held?.length) return null;
  return <ul className="bc-lines" aria-label="Rows set aside">{held.map((q, i) => <li key={`${i}${q.rule}${q.field}`}>{q.masked ? `${flowCopy.rows(q.count)} set aside for a check you cannot see` : setAside(q)}</li>)}</ul>;
}

export default function FlowRunNote({ runId, title, canAsk, onClose }: { runId: string; title: string; canAsk: boolean; onClose: () => void }) {
  const [note, setNote] = useState<Note | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [busy, setBusy] = useState(false);
  const url = `/api/company/build/flow/runs/${encodeURIComponent(runId)}`;
  const run = useCallback(async (again: boolean) => {
    setLoad("loading");
    try { setNote(again ? await apiSend<Note>("POST", `${url}/explain`) : await apiGet<Note>(url)); setLoad("ready"); }
    catch (e) { setLoad(e instanceof Refused ? "refused" : "error"); }
  }, [url]);
  useEffect(() => { void run(false); }, [run]);

  const body = load === "loading" ? <p role="status" className="ds-soft">{t.loading}</p>
    : load === "refused" ? <p role="alert" className="ds-soft">{t.refused}</p>
    : load === "error" || !note ? <p role="alert" className="ds-warn">{t.error}</p>
    : !(note.lines?.length || note.text) ? <p>{t.empty}</p>
    : (
      <>
        <p><Pill tone="draft">{flowCopy.flowTag}</Pill></p>
        {note.fallback && note.sentence ? <p role="status" className="ds-warn">{note.sentence}</p> : null}
        {note.text ? <p>{note.text}</p> : null}
        {note.lines?.length ? <ul className="bc-lines">{note.lines.map((l) => <li key={l}>{l}</li>)}</ul> : null}
      </>
    );
  return (
    <SideCard title={`${flowCopy.flowTag}: ${title}`}>
      {body}
      <div className="bc-actions">
        {canAsk && load !== "loading" ? <Button disabled={busy} onClick={() => { setBusy(true); void run(true).finally(() => setBusy(false)); }}>{t.again}</Button> : null}
        <Button onClick={onClose}>{t.close}</Button>
      </div>
    </SideCard>
  );
}
