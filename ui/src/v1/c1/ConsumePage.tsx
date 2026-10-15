import { useEffect, useState } from "react";

import { apiGet } from "../../api/client";
import { Button, DataTable, EmptyState, Footnote, PageFrame, Pill, Sparkline, StatGrid } from "../../design";
import { day } from "../../pages/FeedsPage";
import OffersSection from "../c2/OffersSection";
import ShapeLink from "../c3/ShapeLink";

// C1 KPI cards: the signed SOW's KPIs, values only for periods marked loaded; a figure opens to its run and rows (copied from FeedCard and
// MeasurePage's pipeline card in 2.0).

interface Point { period: string; value: number }
interface Kpi {
  code: string; name: string; definition?: string | null; unit?: string | null; owner?: string | null; table: string | null;
  latest: Point | null; trend: Point[]; range_break: boolean; reason: string | null;
}
interface Intent { intent_id: string; title?: string | null; signature?: { name: string; at: string } | null; kpis: Kpi[] }
interface Run { id?: string; status?: string; started?: string; ended?: string; rows?: number }
interface Figure {
  code: string; name: string; period: string; value: number; table: string;
  runs: { source_id: string; run: Run | null }[]; columns: string[]; rows: Record<string, string | number | null>[];
}

const NA = "Not available yet";
const words = (id: string) => id.replace(/_/g, " ");
const fmt = (v: number, unit?: string | null) => `${v.toLocaleString()}${unit ? ` ${unit}` : ""}`;

function KpiCard({ iid, k, onOpen }: { iid: string; k: Kpi; onOpen: (iid: string, k: Kpi) => void }) {
  const head = <span className="ds-stat__label">{k.code} · <span>{k.name}</span></span>;
  if (!k.latest) {
    return (
      <div className="ds-card ds-stat">
        {head}
        <span className="ds-stat__value ds-stat__value--text ds-muted">{NA}</span>
        {k.reason ? <span className="ds-stat__note ds-stat__note--muted">{k.reason}</span> : null}
      </div>
    );
  }
  return (
    <button type="button" className="ds-card ds-stat" onClick={() => onOpen(iid, k)} aria-label={`Open ${k.name} for ${day(k.latest.period)}`}>
      {head}
      <strong className={`ds-stat__value${k.range_break ? " ds-stat__value--warn" : ""}`}>{fmt(k.latest.value, k.unit)}</strong>
      <span className="ds-stat__note ds-stat__note--muted">{day(k.latest.period)}</span>
      {k.trend.length > 1 ? <Sparkline points={k.trend.map((t) => t.value)} /> : null}
      {k.range_break ? <span className="ds-stat__note ds-stat__note--warn">Outside its usual range</span> : null}
      {k.owner ? <span className="ds-stat__note">Owner: {k.owner}</span> : null}
    </button>
  );
}

function FigurePanel({ f, onClose }: { f: Figure; onClose: () => void }) {
  return (
    <section aria-label="Where this figure comes from" className="ds-card ds-side">
      <strong>{f.name}, {day(f.period)}: {f.value.toLocaleString()}</strong>
      {f.runs.length ? f.runs.map((r) => (
        <p key={r.source_id}>
          {r.run
            ? <><Pill tone={r.run.status === "ok" ? "ok" : r.run.status === "failed" ? "failed" : "late"}>{r.run.status ?? NA}</Pill> Loaded from {words(r.source_id)}{r.run.ended ? ` on ${day(r.run.ended)}` : ""}{r.run.rows != null ? `, ${r.run.rows} rows` : ""}</>
            : <>No run recorded for {words(r.source_id)}</>}
        </p>
      )) : <p>No source is named for this KPI.</p>}
      {f.rows.length
        ? <DataTable columns={f.columns.map((c) => ({ key: c, label: c }))} rows={f.rows.map((r) => Object.fromEntries(f.columns.map((c) => [c, String(r[c] ?? "")])))} />
        : <p>No rows for this period.</p>}
      <Button onClick={onClose}>Close</Button>
    </section>
  );
}

export default function ConsumePage() {
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [intents, setIntents] = useState<Intent[]>([]);
  const [fig, setFig] = useState<Figure | null>(null);
  const [figErr, setFigErr] = useState(false);

  useEffect(() => {
    let live = true;
    apiGet<{ intents: Intent[] }>("/api/v1/consume")
      .then((d) => { if (live) { setIntents(d.intents); setState("ready"); } })
      .catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, []);

  const open = (iid: string, k: Kpi) => {
    if (!k.latest) return;
    setFigErr(false);
    apiGet<Figure>(`/api/v1/consume/${encodeURIComponent(iid)}/${encodeURIComponent(k.code)}?period=${encodeURIComponent(k.latest.period)}`)
      .then(setFig)
      .catch(() => { setFig(null); setFigErr(true); });
  };

  return (
    <div className="ds-screen">
      <PageFrame title="Consume centre" subline="The KPIs as signed, for the periods the ops manager has marked loaded.">
        {state === "loading" ? <p role="status" className="ds-muted">Reading the KPIs.</p>
          : state === "error" ? <EmptyState title="The KPIs could not be loaded" lines={["Please try again."]} />
          : intents.length === 0 ? <EmptyState title="No intent of work is signed yet" lines={["KPIs appear here once an intent of work is signed and its first period is loaded."]} />
          : intents.map((i) => (
            <section key={i.intent_id} aria-label={i.title ?? i.intent_id}>
              <h2>{i.title ?? i.intent_id}</h2>
              {i.signature ? <p className="ds-muted">Signed by {i.signature.name}, {day(i.signature.at)}</p> : null}
              <StatGrid>{i.kpis.map((k) => <KpiCard key={k.code} iid={i.intent_id} k={k} onOpen={open} />)}</StatGrid>
            </section>
          ))}
        {fig ? <FigurePanel f={fig} onClose={() => setFig(null)} /> : figErr ? <p role="alert">{NA}</p> : null}
        <Footnote>Every value is read from the company's own records and opens to the run that loaded it.</Footnote>
        <ShapeLink />
        <OffersSection />
      </PageFrame>
    </div>
  );
}
