import { useCallback, useEffect, useState } from "react";

import { apiGet, apiSend, ApiError } from "../../api/client";
import { Button, Pill, SideCard } from "../../design";

// P5 / G2: the ops page's card for live projects (GET /api/v1/ops/live): each project's daily state, its open tickets, and a ticket to its builder
// (POST /api/v1/ops/tickets). A project goes live from its own page, pressed by its owner; there is no hand-over.
interface Ticket { id: string; source_id: string; text: string; by: string; to: string }
interface Daily { date: string; state: string; sources: { source_id: string; state: string }[] }
interface Project { pid: string; title: string | null; builder: string | null; daily: Daily | null; tickets: Ticket[] }

const STATE: Record<string, string> = { on_time: "on time", late: "late", failed: "checks failed", missing: "not arrived", no_runs: "no runs yet" };

function TicketForm({ p, onDone }: { p: Project; onDone: () => void }) {
  const [source, setSource] = useState(p.daily?.sources[0]?.source_id ?? "");
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const send = () => apiSend("POST", "/api/v1/ops/tickets", { pid: p.pid, source_id: source, text })
    .then(() => { setText(""); onDone(); }).catch((e: unknown) => setErr(e instanceof ApiError ? e.message : "Could not save. Try again."));
  return (
    <div className="ds-comment__decide">
      <input aria-label={`Source for a ticket on ${p.pid}`} value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source" />
      <input aria-label={`Ticket for ${p.builder ?? "the builder"}`} value={text} onChange={(e) => setText(e.target.value)} placeholder="What is wrong" />
      <Button disabled={!source.trim() || !text.trim()} onClick={() => void send()}>Raise a ticket</Button>
      {err && <span role="alert" className="ds-warn">{err}</span>}
    </div>
  );
}

export default function LiveCard() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [n, setN] = useState(0);
  const reload = useCallback(() => setN((x) => x + 1), []);
  useEffect(() => {
    let live = true;
    apiGet<{ projects?: Project[] }>("/api/v1/ops/live").then((b) => { if (live) setProjects(b.projects ?? []); }).catch(() => { if (live) setProjects(null); });
    return () => { live = false; };
  }, [n]);
  if (!projects?.length) return null;
  return (
    <SideCard title="Live projects and tickets">
      {projects.map((p) => (
        <div key={p.pid}>
          <p>
            <strong>{p.title ?? p.pid}</strong> <span className="ds-muted">{p.pid}</span> <Pill tone="signed">Live</Pill>
          </p>
          <p className="ds-soft">Today: {p.daily ? `${STATE[p.daily.state] ?? p.daily.state} (${p.daily.sources.map((s) => `${s.source_id} ${STATE[s.state] ?? s.state}`).join(", ") || "no sources"})` : "Not available yet"}. Builder: {p.builder ?? "not named"}.</p>
          {p.tickets.map((t) => <p key={t.id} className="ds-soft">Ticket to {t.to}: {t.text} <span className="ds-muted">({t.by})</span></p>)}
          <TicketForm p={p} onDone={reload} />
        </div>
      ))}
    </SideCard>
  );
}
