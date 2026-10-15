import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiGet } from "../api/client";
import { Button, Chip, Pill } from "../design";
import { BASIS, CONFIDENCE, LENSES, LENS_NAME, R, STATES, T } from "./radarCopy";

// Spec 57 Screen A: the radar on the Intent home (`/centre/intent?view=radar&tab=mine|areas|lenses&focus=`). Read only here;
// a card opens the 56 drawer (Screen C). The Consume room (Screen B) reuses RadarColumns.
interface Value { value: number | string | Record<string, number>; unit: string; periods?: string[]; per?: string; by?: string; basis?: string }
export interface RadarOpp {
  id: string; title: string; state: string; belief: string; lens: string; href: string;
  measure?: { id: string; name: string | null } | null;
  baseline?: Value | null; target?: Value | null; expected_uplift?: Value | null;
  baseline_missing?: string | null; target_missing?: string | null; uplift_missing?: string | null;
  confidence: string | null; evidence_mix?: { data: number; document: number; voice: number }; theme: { voices: number } | null;
}
export interface Rejected { id: string; title: string; why: string; broke_by: { kind: string; ref: string }[]; at: string; href: string }
interface Radar {
  opportunities: RadarOpp[]; rejected: Rejected[]; areas?: { id: string; name: string }[];
  scan: { last_at: string | null; read: Record<string, number> | null; schedule: string | null; thresholds: { total: number; missing: string[] } } | null;
  can_set_thresholds?: boolean; notice?: string | null; hidden_below_confidence?: number;
}

const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 700px)").matches;
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const when = (iso: string) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : DATE.format(d); };
const shown = (x: Value["value"]): string => typeof x === "object" && x !== null ? `${Object.keys(x).length} separate values` : typeof x === "number" ? x.toLocaleString("en-GB") : String(x); // a breakdown (one value per holding) is counted, never summed across currencies
const num = (v: Value, bits = ""): string => `${shown(v.value)} ${v.unit}${v.periods?.length ? ` (${v.periods.join(", ")})` : ""}${bits}`;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export const mixLine = (m: NonNullable<RadarOpp["evidence_mix"]>) => [`${m.data} data`, plural(m.document, "document", "documents"), plural(m.voice, "voice", "voices")].join(", ");

// A reader at card tier (no belief sent) may not open the 56 drawer, so the card is not a link for them.
function Wrap({ o, children, ...rest }: { o: RadarOpp; children: React.ReactNode; className: string; "aria-label": string; style: React.CSSProperties }) {
  return o.belief === undefined ? <div {...rest}>{children}</div> : <Link to={o.href} {...rest}>{children}</Link>;
}

export function RadarCard({ o }: { o: RadarOpp }) {
  const proposed = o.state === "proposed";
  const line = (label: string, v: Value | null | undefined, missing?: string | null, extra = "") => <span><span className="ds-soft">{label}: </span>{v ? num(v, extra) : R.notAvailable(missing)}</span>;
  return (
    <Wrap o={o} className="rd-card" aria-label={`${o.title}. ${proposed ? R.proposed : STATES[o.state] ?? o.state}`}
      style={{ border: `1px ${proposed ? "dashed" : "solid"} var(--ds-line-2, var(--ds-line))`, borderRadius: "var(--ds-radius)", padding: 14, display: "flex", flexDirection: "column", gap: 6, color: "var(--ds-ink)", textDecoration: "none", minHeight: 44 }}>
      <strong>{o.title}</strong>
      {o.belief && <span>{o.belief}</span>}
      {o.theme && <span><Chip>{R.theme(o.theme.voices)}</Chip></span>}
      {o.belief !== undefined && (
        <>
      {o.measure && <span className="ds-soft">{o.measure.name ?? "A restricted measure"}</span>}
      {line("Baseline", o.baseline, o.baseline_missing)}
      {line("Target", o.target, o.target_missing, o.target?.by ? ` by ${when(o.target.by)}` : "")}
      <span><span className="ds-soft">Expected uplift: </span>{o.expected_uplift ? `${o.expected_uplift.value} ${o.expected_uplift.unit} per ${o.expected_uplift.per ?? "month"}${o.expected_uplift.basis ? `, ${BASIS[o.expected_uplift.basis] ?? o.expected_uplift.basis}` : ""}` : R.notAvailable(o.uplift_missing)}</span>
        </>
      )}
      <span className="ds-soft">{o.confidence ? CONFIDENCE[o.confidence] ?? o.confidence : R.notAvailable()}{o.evidence_mix ? ` · ${mixLine(o.evidence_mix)}` : ""}</span>
      <span><Pill tone={proposed ? "ok" : "open"}>{STATES[o.state] ?? o.state}</Pill></span>
    </Wrap>
  );
}

/** Four lens columns (collapsible sections at 390). `focus` shows one lens only. */
export function RadarColumns({ list, focus, onFocus }: { list: RadarOpp[]; focus?: string | null; onFocus?: (lens: string | null) => void }) {
  const shown = LENSES.filter(([k]) => !focus || k === focus);
  const open = wide();
  return (
    <div style={{ display: "grid", gap: 12, gridTemplateColumns: open ? `repeat(${shown.length}, minmax(0, 1fr))` : "1fr", alignItems: "start" }}>
      {shown.map(([k, label]) => {
        const mine = list.filter((o) => o.lens === k);
        const head = `${label} (${mine.length})`;
        const body = mine.length ? <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{mine.map((o) => <RadarCard key={o.id} o={o} />)}</div> : <p className="ds-soft">{R.emptyColumn}</p>;
        return open
          ? <section key={k} aria-label={label}><h3>{onFocus ? <button type="button" className="ds-btn" onClick={() => onFocus(focus ? null : k)}>{head}</button> : head}</h3>{body}</section>
          : <details key={k} open={mine.length > 0} aria-label={label}><summary><strong>{head}</strong></summary>{body}</details>;
      })}
    </div>
  );
}

// What the scan read (feeds, documents, voices), then what is on the radar now: the scan's own count of new opportunities is not shown beside cards that earlier scans made.
const readLine = (read: Record<string, number> | null, onRadar: number) => {
  const bits = Object.entries(read ?? {}).filter(([k]) => k !== "opportunities").map(([k, v]) => `${v} ${k}`);
  return `${bits.length ? `${bits.join(", ")} read. ` : ""}${plural(onRadar, "opportunity", "opportunities")} on the radar now.`;
};

export function RadarView() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "areas" ? "areas" : params.get("tab") === "lenses" ? "lenses" : "mine";
  const focus = params.get("focus");
  const [data, setData] = useState<Radar | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const areaId = tab === "areas" ? focus ?? data?.areas?.[0]?.id ?? "" : "";
  const url = tab === "mine" ? "/api/intents/radar?scope=mine" : tab === "areas" ? `/api/intents/radar?scope=area${focus ? `&area=${encodeURIComponent(focus)}` : ""}` : "/api/intents/radar?scope=lens";
  useEffect(() => {
    let live = true;
    apiGet<Radar>(url).then((d) => { if (live) { setData(d); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [url, attempt]);
  const go = (next: Record<string, string | null>) => { const p = new URLSearchParams(params); p.set("view", "radar"); for (const [k, v] of Object.entries(next)) { if (v) p.set(k, v); else p.delete(k); } setParams(p); };
  const lensFocus = tab === "lenses" && LENS_NAME[focus ?? ""] ? focus : null;
  const keyName: Record<string, string> = { ...Object.fromEntries(T.keys), scan: "Scan timing", min_confidence_to_show: "Confidence shown" };
  const missing = data?.scan?.thresholds.missing ?? [];
  const missingNames = missing.map((k) => keyName[k] ?? k).join(", ");
  const live = useMemo(() => (data?.opportunities ?? []).filter((o) => o.state !== "rejected"), [data]);

  return (
    <section aria-label={R.title} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header><h2 style={{ margin: 0 }}>{R.title}</h2><p className="ds-soft">{R.sub}</p></header>
      {wide()
        ? <div role="tablist">{(["mine", "areas", "lenses"] as const).map((k) => <Chip key={k} tone={tab === k ? "active" : "default"} onClick={() => go({ tab: k, focus: null })}>{R.tabs[k]}</Chip>)}</div>
        : <select aria-label="View" value={tab} onChange={(e) => go({ tab: e.target.value, focus: null })} style={{ minHeight: 44 }}>{(["mine", "areas", "lenses"] as const).map((k) => <option key={k} value={k}>{R.tabs[k]}</option>)}</select>}
      {tab === "areas" && (data?.areas?.length
        ? <label>{R.pickArea} <select value={areaId} onChange={(e) => go({ focus: e.target.value })} style={{ minHeight: 44 }}>{data.areas.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        : data && <p>{R.noArea}</p>)}
      {failed && <p role="alert">{R.couldNot} <Button onClick={() => setAttempt((n) => n + 1)}>{R.retry}</Button></p>}
      {!data && !failed && <p aria-busy="true">{R.loading}</p>}
      {data && (
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: wide() ? "minmax(0, 3fr) minmax(0, 1fr)" : "1fr" }}>
          <div>
            {data.can_set_thresholds && (data.notice ?? missing.length > 0) && (
              <p role="status"><strong>North.</strong> {data.notice ?? R.thresholdsNotice(missing.length, data.scan?.thresholds.total ?? missing.length)} <Link to="/centre/intent/admin?tab=defaults">{R.thresholdsLink}</Link></p>
            )}
            {(data.hidden_below_confidence ?? 0) > 0 && <p className="ds-soft">{R.hidden(data.hidden_below_confidence ?? 0)}</p>}
            {tab === "mine" && live.length === 0 ? <p>{R.emptyMine}</p> : <RadarColumns list={live} focus={lensFocus} onFocus={tab === "lenses" ? (l) => go({ focus: l }) : undefined} />}
          </div>
          <aside style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <details open={wide()}><summary><strong>{R.rejectedTitle}</strong></summary>
              {data.rejected.length ? <ul style={{ margin: 0, padding: 0 }}>{data.rejected.map((r) => (
                <li key={r.id} style={{ listStyle: "none", padding: "6px 0", borderTop: "1px solid var(--ds-line)" }}>
                  <Link to={r.href}><strong>{r.title}</strong></Link><br />{r.why}{r.broke_by.length ? <span className="ds-soft"> · {r.broke_by.length === 1 ? "1 record broke it" : `${r.broke_by.length} records broke it`}</span> : null}<span className="ds-soft"> · {when(r.at)}</span>
                </li>))}</ul> : <p className="ds-soft">{R.rejectedNone}</p>}
            </details>
            <details open={wide()}><summary><strong>{R.howTitle}</strong></summary>
              {data.scan?.last_at
                ? <p className="ds-soft">Last scan {when(data.scan.last_at)}{data.scan.schedule ? `, ${data.scan.schedule}` : ""}. {readLine(data.scan.read, live.length)}{missing.length ? ` Not set: ${missingNames}.` : ""}</p>
                : <p className="ds-soft">{R.notRun}{missing.length ? ` ${missingNames}.` : ""}</p>}
              {data.can_set_thresholds && <Link to="/centre/intent/admin?tab=defaults">{R.thresholdsLink}</Link>}
            </details>
          </aside>
        </div>
      )}
    </section>
  );
}
