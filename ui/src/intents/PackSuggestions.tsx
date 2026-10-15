import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";

import { apiGet, apiSend } from "../api/client";
import { Button } from "../design";
import { TypeChip } from "./IntentCard";

// The "Suggested first intents" strip (spec 49). GET /api/intents/suggestions already leaves out what this person dismissed or picked up.
// Start this writes a draft with the suggested title, purpose, areas and answers, marks the card picked up, and opens the questions.

interface Item {
  suggestion_id: string; type: string; title: string; purpose: string; why: string; start_answers: Record<string, string>;
  company_areas: string[]; label: string;
}
interface Data { label: string; pack: { label: string; version: number } | null; items: Item[]; dismissed_count: number; dismissed_ids: string[]; may_start: boolean }

const TYPE_NAME: Record<string, string> = { initiative: "Initiative", brainstorm: "Brainstorm", pulse: "Weekly check-in", problem: "Problem", decision: "Decision" };
const COL: CSSProperties = { display: "flex", flexDirection: "column", gap: 8 };
const ROW: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" };
const TAP: CSSProperties = { minHeight: 44 };
const dismissedLine = (n: number) => `Show ${n} dismissed ${n === 1 ? "suggestion" : "suggestions"}`;

export default function PackSuggestions() {
  const nav = useNavigate();
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { apiGet<Data>("/api/intents/suggestions").then(setD, () => setD(null)); }, []);
  useEffect(load, [load]);
  if (!d || !d.may_start || (d.items.length === 0 && d.dismissed_count === 0)) return null;

  const mark = (id: string, what: "dismiss" | "restore") => apiSend("POST", `/api/intents/suggestions/${encodeURIComponent(id)}/${what}`).then(load, () => setErr("We could not save that. Please try again."));
  const startThis = async (i: Item) => {
    setBusy(i.suggestion_id); setErr("");
    const body = { type: i.type, title: i.title, purpose: i.purpose, start_answers: i.start_answers };
    try {
      let made: { id: string };
      try { made = await apiSend<{ id: string }>("POST", "/api/intents", { ...body, areas: i.company_areas }); }
      catch { made = await apiSend<{ id: string }>("POST", "/api/intents", body); }  // an area the company no longer has: start without areas
      await apiSend("POST", `/api/intents/suggestions/${encodeURIComponent(i.suggestion_id)}/picked-up`, { intent_id: made.id }).catch(() => undefined);
      nav(`/centre/intent/new?type=${i.type}&draft=${made.id}`);
    } catch { setErr("We could not start that. Please try again."); }
    setBusy("");
  };

  return (
    <section style={COL} aria-label="Suggested first intents">
      <h2 style={{ fontSize: 17, margin: 0 }}>Suggested first intents</h2>
      <p className="ds-soft">{d.label}{d.pack && <> <span className="ds-chip" style={{ padding: "2px 8px", fontSize: 12 }}>{`Pack: ${d.pack.label}, version ${d.pack.version}`}</span></>}</p>
      {err && <p role="alert" className="state state-error">{err}</p>}
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))" }}>
        {d.items.map((i) => (
          <div key={i.suggestion_id} className="ds-card" style={{ ...COL, padding: 14, borderStyle: "dashed" }}>
            <div style={ROW}><TypeChip type={i.type} name={TYPE_NAME[i.type] ?? i.type} /><span className="ds-chip" style={{ padding: "2px 8px", fontSize: 12 }}>Suggestion</span></div>
            <strong>{i.title}</strong>
            {i.purpose && <span className="ds-soft">{i.purpose}</span>}
            {i.why && <span className="ds-muted" style={{ fontSize: 14 }}>Why others start here: {i.why}</span>}
            <div style={ROW}>
              <Button variant="primary" style={TAP} disabled={busy !== ""} onClick={() => void startThis(i)}>Start this</Button>
              <Button style={TAP} disabled={busy !== ""} onClick={() => void mark(i.suggestion_id, "dismiss")}>Not for us</Button>
            </div>
          </div>
        ))}
      </div>
      {d.dismissed_count > 0 && (
        <div><Button style={TAP} onClick={() => void Promise.all(d.dismissed_ids.map((id) => mark(id, "restore")))}>{dismissedLine(d.dismissed_count)}</Button></div>
      )}
    </section>
  );
}
