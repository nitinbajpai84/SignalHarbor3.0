import { useState } from "react";

import { apiGet, apiSend } from "../../api/client";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, EmptyState, Footnote, Pill, SideCard, Strip } from "../../design";

// C2 Offer card: "with this feed you would also get…", from the industry pack's feed list matched against the intent of work.
// Looks like the market briefs (MarketPage) and the context card: outside suggestion, never the company's own figure.
// The server says who may answer (`can_answer`); this file never works out a role.

export interface Offer {
  id: string; kind: string; title: string;
  unlocks: { code: string; name: string; in_sow: boolean }[];
  must_contain: { name: string; label: string; type: string }[];
}
export interface Offers { intent_id: string | null; offers: Offer[]; line: string | null; can_answer: boolean }

const measurePage = (code: string) => `/centre/intent/map/${encodeURIComponent(code)}`;

export default function OffersSection({ intent }: { intent?: string }) {
  const q = intent ? `?intent=${encodeURIComponent(intent)}` : "";
  const load = useLoad(() => apiGet<Offers>(`/api/v1/consume/offers${q}`), `offers${q}`, (d) => d.offers.length === 0);
  const [done, setDone] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const have = (o: Offer) =>
    apiSend<{ sow: { version: number } }>("POST", `/api/v1/consume/offers/${encodeURIComponent(o.id)}/have`, { intent_id: load.data?.intent_id })
      .then((r) => { setErr(null); setDone((d) => ({ ...d, [o.id]: `Added to the intent of work as a source with one unclear point. It is back to draft at version ${r.sow.version}.` })); })
      .catch(() => setErr("That was not saved. Please try again."));

  return (
    <Strip label="Offers" tone="amber">
      {load.state === "loading" && <div role="status"><EmptyState title="Offers" lines={["Reading them now."]} /></div>}
      {load.state === "empty" && <EmptyState title="Offers" lines={[load.data?.line ?? "No offer for you yet."]} />}
      {(load.state === "error" || load.state === "refused") && (
        <div role="alert">
          <EmptyState title="Offers" lines={[load.message ?? (load.state === "refused" ? "You do not have access to this." : "This could not be read just now. Try again in a moment.")]} />
          {load.state === "error" && <Button onClick={load.retry}>Try again</Button>}
        </div>
      )}
      {load.state === "populated" && load.data?.offers.map((o) => (
        <SideCard key={o.id} title={o.title}>
          <div><Pill tone="open">Suggestion from your industry</Pill></div>
          <p>Measures it would unlock:</p>
          <p>{o.unlocks.map((u) => (
            <span key={u.code}><Chip href={measurePage(u.code)}>{u.name}</Chip>{u.in_sow ? <span className="ds-muted"> (in your intent of work)</span> : null}{" "}</span>
          ))}</p>
          <p className="ds-muted">It must contain: {o.must_contain.map((f) => f.label).join(", ")}.</p>
          {done[o.id]
            ? <p role="status">{done[o.id]}</p>
            : load.data?.can_answer ? <Button variant="primary" onClick={() => have(o)}>We have it</Button> : null}
        </SideCard>
      ))}
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <Footnote>Offers name a kind of feed, never a supplier. Your own figures come only from your measures.</Footnote>
    </Strip>
  );
}
