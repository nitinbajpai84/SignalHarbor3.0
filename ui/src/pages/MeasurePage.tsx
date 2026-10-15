import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, DataTable, EmptyState, Footnote, LineChart, PageFrame, Pill, SideCard, StatCard, StatGrid, type PillTone } from "../design";
import { apiGet, apiSend } from "../api/client";
import { day, type Point } from "./FeedsPage";
import { type LensList } from "./consumeLens";
import { ContextCard, LensChip, type ContextCardData, type MeasureLens } from "./ContextCard";

// One measure's own page (SHAPES section 6, GET /api/company/feeds/{code}).

interface Run { id?: string; status?: string; started?: string; ended?: string; rows?: number; on_time?: boolean }
export interface Measure {
  code: string; name: string; owner: string | null; may_see: boolean; restricted: string | null; links: { map: string; register: string };
  unit?: string | null; trend?: Point[]; latest?: Point | null; baseline_id?: string | null;
  change?: { previous_period: string; absolute: number; percent: number | null } | null;
  range?: { verdict: string; outside: boolean; basis: string };
  definition?: { business: string | null; technical: { label: string; text: string }[] } | null;
  card?: ContextCardData | null; lens?: MeasureLens | null;
  pipeline?: { source: string; expected?: string; sla?: string; owner?: string; last_run: Run | null } | null;
}
const NA = "Not available yet";
const RUN_TONE: Record<string, PillTone> = { ok: "ok", late: "late", failed: "failed" };

function Ask({ id, name }: { id: string; name: string }) {
  const [q, setQ] = useState(""), [busy, setBusy] = useState(false), [reply, setReply] = useState<string | null>(null);
  const send = () => {
    if (!q.trim()) return;
    setBusy(true);
    apiSend<{ text: string }>("POST", `/api/modules/m2_baseline/baselines/${id}/lens/ask`, { question: q.toLowerCase().includes(name.toLowerCase()) ? q : `${q.trim()} (about the measure ${name})` })
      .then((r) => setReply(r.text)).catch(() => setReply("Lens could not answer just now. Please try again.")).finally(() => setBusy(false));
  };
  return (
    <SideCard title="Ask Lens">
      <form className="ds-comment__decide" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input aria-label="Ask Lens about this measure" placeholder="Ask Lens about this measure" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="primary" disabled={busy}>{busy ? "Asking" : "Send"}</Button>
      </form>
      {reply ? <p aria-live="polite">{reply}</p> : null}
    </SideCard>
  );
}

// The chart's last x label clips at the svg edge when it is long, so months show as "Sep 26" (other period shapes pass through).
const short = (p: string) => { const m = /^(\d{4})-(\d{2})$/.exec(p); return m ? `${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][Number(m[2]) - 1] ?? p} ${m[1]!.slice(2)}` : p; };

const words = (s: string) => { const t = s.replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); };
const SYMBOL: Record<string, string> = { SGD: " SGD", hours: " hours" };
const fmt = (v: number, unit?: string | null) => `${v.toLocaleString()}${SYMBOL[unit ?? ""] ?? ""}`;

const changeLine = (c: NonNullable<Measure["change"]>, unit?: string | null) =>
  `${c.absolute >= 0 ? "Up" : "Down"} ${fmt(Math.abs(c.absolute), unit)}${c.percent === null ? "" : ` (${c.percent.toFixed(1)}%)`} on ${day(c.previous_period)}`;

export default function MeasurePage() {
  const { code = "" } = useParams();
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [m, setM] = useState<Measure | null>(null);
  const [n, setN] = useState(0);
  const [card, setCard] = useState<ContextCardData | null | undefined>(undefined);
  const [lens, setLens] = useState<MeasureLens | null | undefined>(undefined);
  const retry = useCallback(() => { setState("loading"); setN((x) => x + 1); }, []);

  useEffect(() => {
    let live = true;
    apiGet<Measure>(`/api/company/feeds/${encodeURIComponent(code)}`)
      .then((d) => { if (live) { setM(d); setCard(d.card); setLens(d.lens); setState("ready"); } })
      .catch(() => { if (live) setState("error"); });
    // The card and the business view have their own routes; the measure route may carry them too (spec 60), which wins.
    apiGet<ContextCardData>(`/api/company/consume/cards/${encodeURIComponent(code)}`).then((c) => { if (live) setCard((x) => x ?? c); }).catch(() => undefined);
    apiGet<LensList>("/api/company/consume/lenses").then((d) => {
      const l = d.lenses.find((x) => x.measures?.includes(code.toUpperCase()));
      if (live && l) setLens((x) => x ?? { key: l.key });
    }).catch(() => undefined);
    return () => { live = false; };
  }, [code, n]);

  const crumbs = <><Link to="/centre/consume">Consume centre</Link> / <Link to="/centre/consume/feeds">Feeds</Link></>;
  if (state !== "ready" || !m) {
    return (
      <div className="ds-screen">
        <PageFrame crumbs={crumbs} title={code}>
          {state === "loading" ? <p role="status" className="ds-muted">Reading this measure.</p>
            : <div role="alert"><EmptyState title="This measure could not be loaded" lines={["Please try again."]} /><Button onClick={retry}>Try again</Button></div>}
        </PageFrame>
      </div>
    );
  }

  const owner = m.owner ? `Owner: ${m.owner}` : `Owner: ${NA}`;
  if (m.restricted || !m.may_see) {
    return (
      <div className="ds-screen">
        <PageFrame crumbs={crumbs} title={m.name} subline={`${m.code} · ${owner}`} actions={<Pill tone="restricted">Restricted</Pill>}>
          <EmptyState title={m.restricted ?? `Restricted: ask ${m.owner ?? "the owner"}`} lines={["The figure reaches only the people on this measure's access list."]}
            links={[{ label: "See it on the map", href: m.links.map }, { label: "Open the register", href: m.links.register }]} />
        </PageFrame>
      </div>
    );
  }

  const trend = m.trend ?? [];
  const last = trend[trend.length - 1], low = trend.reduce((a, t) => (t.value < a.value ? t : a), trend[0]!), high = trend.reduce((a, t) => (t.value > a.value ? t : a), trend[0]!);
  const ch = m.change, run = m.pipeline?.last_run, warn = !!m.range?.outside;
  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={crumbs}
        title={m.name}
        subline={`${m.code} · ${owner}`}
        actions={<>{m.range ? <Pill tone={warn ? "late" : "ok"}>{m.range.verdict}</Pill> : null}<LensChip lens={lens} /></>}
        aside={<>
          <ContextCard card={card} onChanged={setCard} />
          <SideCard title="Definition">
            {m.definition ? <>
              <p>{m.definition.business ?? NA}</p>
              {m.definition.technical.length ? <dl className="ds-soft">{m.definition.technical.map((p) => <div key={p.label}><dt className="ds-muted">{p.label}</dt><dd>{p.text}</dd></div>)}</dl> : null}
            </> : <p>{NA}</p>}
          </SideCard>
          <SideCard title="Pipeline that feeds it">
            {m.pipeline ? <>
              <p>{words(m.pipeline.source)}{m.pipeline.expected ? `, expected ${m.pipeline.expected.toLowerCase().replace(/^d\+/, "D+")}` : ""}{m.pipeline.sla && m.pipeline.sla !== "Not stated" ? `, SLA ${m.pipeline.sla}` : ""}</p>
              {run ? <p><Pill tone={RUN_TONE[run.status ?? ""] ?? "draft"}>{run.status ?? NA}</Pill> Last run{run.ended ? ` ${day(run.ended)}` : ""}</p> : <p>No run recorded yet</p>}
            </> : <p>{NA}</p>}
          </SideCard>
          <SideCard title="Where it sits">
            <Link to={m.links.map}>See it on the map</Link>
            <Link to={m.links.register}>Open the register</Link>
          </SideCard>
          {m.baseline_id ? <Ask id={m.baseline_id} name={m.name} /> : <SideCard title="Ask Lens"><p>Lens answers once this measure has a signed definition. Until then, leave a question on its page.</p><Link to={m.links.map}>Ask on the measure's page</Link></SideCard>}
        </>}
      >
        <StatGrid cols={2}>
          <StatCard label={m.latest ? `Latest · ${day(m.latest.period)}` : "Latest"} value={m.latest ? fmt(m.latest.value, m.unit) : NA}
            valueTone={warn ? "warn" : undefined} note={ch ? changeLine(ch, m.unit) : undefined} />
          <StatCard label="Usual range" value={m.range?.verdict ?? NA} text note={m.range?.basis} tone={warn ? "warn" : "muted"} />
        </StatGrid>
        {trend.length > 1
          ? <>
              <div className="ds-card ds-side">
                <LineChart points={trend.map((t) => ({ ...t, period: short(t.period) }))} label="Trend over all periods" />
                <p className="ds-muted">{m.unit ? `Values are in ${m.unit}. ` : ""}The chart has no axis, so the latest, lowest and highest values are shown below it.</p>
              </div>
              <StatGrid cols={3}>
                <StatCard label="Latest" value={fmt(last!.value, m.unit)} note={day(last!.period)} />
                <StatCard label="Lowest" value={fmt(low!.value, m.unit)} note={day(low!.period)} />
                <StatCard label="Highest" value={fmt(high!.value, m.unit)} note={day(high!.period)} />
              </StatGrid>
            </>
          : <EmptyState title="No trend yet" lines={["The trend appears once the measure has two periods."]} />}
        {trend.length ? <section aria-label="Periods" style={{ minWidth: 0 }}>
          <DataTable columns={[{ key: "period", label: "Period" }, { key: "value", label: "Value" }]}
            rows={[...trend].reverse().map((t) => ({ period: day(t.period), value: fmt(t.value, m.unit) }))} />
        </section> : null}
        <Footnote>Every value is read from the company's own records.</Footnote>
      </PageFrame>
    </div>
  );
}
