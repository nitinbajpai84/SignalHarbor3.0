import { useCallback, useEffect, useState } from "react";

import { apiGet, apiSend, Refused } from "../../api/client";
import { Button, EmptyState, Pill, SideCard } from "../../design";
import { useSession } from "../../useSession";
import "./chain.css";
import { flowCopy } from "./flowCopy";

// Room 0: Span's target architecture (GET and POST /api/company/build/span/target). A suggestion; a person decides at the change note.
interface Target {
  draft: { placements: { id: string; label: string; why?: string }[]; lines: string[]; by?: string; at?: string } | null;
  svg?: string | null; diagram_error?: string | null; empty?: string | null; fallback?: boolean; message?: string | null;
}
type Load = "loading" | "error" | "refused" | "ready";
const t = flowCopy.target;

export default function SpanTargetCard({ intentId }: { intentId: string }) {
  const { user } = useSession();
  const asks = !!user?.roles.some((r) => r === "company_admin" || r === "analyst");
  const [data, setData] = useState<Target | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const read = useCallback(async () => {
    try { setData(await apiGet<Target>("/api/company/build/span/target")); setLoad("ready"); } catch (e) { setLoad(e instanceof Refused ? "refused" : "error"); }
  }, []);
  useEffect(() => { void read(); }, [read]);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => void read(), 3000);  // the draft shows up as soon as it is stored
    return () => clearInterval(timer);
  }, [busy, read]);

  async function ask() {
    setBusy(true); setBanner(null);
    try {
      const r = await apiSend<{ fallback?: boolean; message?: string | null }>("POST", "/api/company/build/span/target", { intent_id: intentId });
      setBanner(r.fallback || r.message ? r.message ?? null : null);
      await read();
    } catch (e) {
      setBanner(e instanceof Error && e.message ? e.message : t.askFailed);
    } finally { setBusy(false); }
  }

  const head = <p><Pill tone="draft">{flowCopy.spanTag}</Pill></p>;
  if (load === "loading") return <SideCard title={t.title}><p role="status" className="ds-soft">{t.loading}</p></SideCard>;
  if (load === "refused") return <SideCard title={t.title}><p role="alert" className="ds-soft">{t.refused}</p></SideCard>;
  if (load === "error" || !data) return <SideCard title={t.title}><p role="alert" className="ds-warn">{t.error}</p><Button onClick={() => void read()}>Try again</Button></SideCard>;
  const d = data.draft;
  const button = asks ? <div className="bc-actions"><Button variant={d ? "secondary" : "primary"} disabled={busy} onClick={() => void ask()}>{busy ? t.asking : d ? t.askAgain : t.ask}</Button></div> : null;
  const note = banner ? <p role="status" className="ds-warn">{banner}</p> : null;
  if (busy && !d) return <SideCard title={t.title}>{head}<p role="status" aria-busy="true" className="bc-note">{t.drafting}</p></SideCard>;
  if (!d) return <SideCard title={t.title}>{head}<EmptyState title="No target yet" lines={[data.empty ?? t.empty]} />{note}{button}</SideCard>;
  return (
    <SideCard title={t.title}>
      {head}
      {note}
      <p className="bc-note">{t.placements(d.placements.length)}</p>
      {data.svg ? <div className="bc-diagram" tabIndex={0} aria-label={t.diagramAlt} style={{ overflowX: "auto", maxWidth: "100%" }}><img alt={t.diagramAlt} src={`data:image/svg+xml;utf8,${encodeURIComponent(data.svg)}`} style={{ width: "100%", minWidth: 640, height: "auto" }} /></div>
        : <p role="alert" className="ds-warn">{data.diagram_error ?? flowCopy.na}</p>}
      <strong>{t.whyHead}</strong>
      {d.lines.length ? <ul className="bc-lines">{d.lines.slice(0, 3).map((l) => <li key={l}>{l}</li>)}</ul> : <p>{flowCopy.na}</p>}
      {button}
    </SideCard>
  );
}
