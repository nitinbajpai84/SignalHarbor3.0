import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiGet } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Chip } from "../../design";
import "./checkin.css";
import { clockText, dateWords, fateName, kindName, mineCopy as m, recordCopy as r, severityName } from "./checkinCopy";

// Spec 39 Screen C ("Your weeks", ?view=mine) and Screen D (the record, ?view=record). Read only; fates are set in the review.

interface MineItem { id: string; kind: string; text: string; anonymous: boolean; severity: string | null; count: number | null; unit: string | null; fate: string | null; fate_reason: string | null; ref: { label: string } | null }
interface MineWeek { week_key: string; opens: string; counts: Record<string, number>; became_problem: number; answered: boolean; items: MineItem[] }
interface Mine { weeks: MineWeek[]; trend: { answered: number; of: number } | null; minutes: number[] }

export function MineView({ intentId }: { intentId: string }) {
  const load = useLoad(() => apiGet<Mine>(`/api/intents/${intentId}/pulse/mine`), intentId, (d) => d.weeks.length === 0);
  const [open, setOpen] = useState<string | null>(null);
  const d = load.data;
  return (
    <div className="ck">
      <h2 style={{ margin: 0 }}>{m.title}</h2>
      <ScreenState state={load.state} message={load.state === "empty" ? m.none : load.message} onRetry={load.retry}>
        {d && (
          <>
            <p className="ck-muted">{d.trend ? m.trend(d.trend.answered, d.trend.of) : m.trendNa}</p>
            {d.minutes.length > 0 && <p className="ck-muted">{m.minutes(d.minutes.map((x) => clockText(x * 60)).join(", "))}</p>}
            <ul className="ck-list">
              {d.weeks.map((w) => (
                <li key={w.week_key} className="ds-card ck-panel">
                  <button type="button" className="ck-head" style={{ all: "unset", cursor: "pointer", minHeight: 44, display: "block" }} aria-expanded={open === w.week_key} onClick={() => setOpen(open === w.week_key ? null : w.week_key)}>
                    {m.summary(dateWords(w.opens, true), w.counts.ran ?? 0, w.counts.broke ?? 0, w.counts.thought ?? 0)}{w.became_problem ? `. ${m.problem(w.became_problem)}` : ""}
                  </button>
                  {open === w.week_key && (w.items.length === 0 ? <p className="ck-muted">{m.noItems}</p> : w.items.map((i) => (
                    <div key={i.id} className={`ck-card ck-card--${i.kind}`} style={{ cursor: "default" }}>
                      <span>{i.text}</span>
                      <span className="ck-row">
                        <span className="ck-tag">{kindName[i.kind]}</span>
                        {i.severity && <span className="ck-tag">{severityName[i.severity]}</span>}
                        {i.ref && <span className="ck-tag">{i.ref.label}</span>}
                        {i.anonymous && <span className="ck-tag">Anonymous</span>}
                        {i.fate && <span className="ck-tag">{i.fate === "nothing" && i.fate_reason ? m.because(i.fate_reason) : fateName[i.fate]}</span>}
                      </span>
                    </div>
                  )))}
                </li>
              ))}
            </ul>
          </>
        )}
      </ScreenState>
      <div><Link to={`/centre/intent/${intentId}/week`} className="ds-btn">{m.back}</Link></div>
    </div>
  );
}

interface Row { id: string; kind: string; text: string; mark: string; severity: string | null; count: number | null; unit: string | null; amount: { value: number; currency: string } | null; ref: { label: string; kind: string } | null; author: string; provenance: string; sources: string[]; fate: string | null; fate_reason: string | null }
interface Rec { week: { week_key: string; opens: string; answers_close: string; closes: string; state: string }; answered: number; of: number; own_only?: boolean; counts: Record<string, number>; withdrawn: number; guessed: number; median_minutes: number | string | null; items: Row[] }

export function RecordView({ intentId }: { intentId: string }) {
  const [params] = useSearchParams();
  const week = params.get("week");
  const load = useLoad(() => apiGet<Rec>(`/api/intents/${intentId}/pulse/record${week ? `?week=${week}` : ""}`), `${intentId}${week}`, undefined);
  const [kind, setKind] = useState<string | null>(null);
  const [sev, setSev] = useState<string | null>(null);
  const [linked, setLinked] = useState(false);
  const [guessed, setGuessed] = useState(false);
  const d = load.data;
  const rows = (d?.items ?? []).filter((i) => (!kind || i.kind === kind) && (!sev || i.severity === sev) && (!linked || i.ref) && (!guessed || i.mark === "guessed"));
  const total = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : 0;
  return (
    <div className="ck">
      <h2 style={{ margin: 0 }}>{r.title}</h2>
      {/* a refusal with words (the record opens when answers close) is quiet: trying again cannot help */}
      <ScreenState state={load.state === "error" && load.message ? "empty" : load.state} message={load.message} onRetry={load.retry}>
        {d && (
          <>
            <div className="ds-card ck-panel">
              <p>{d.own_only ? r.ownOnly(total) : total === 0 && d.answered === 0 ? r.none(dateWords(d.week.closes)) : r.counts(d.answered, d.of, total, d.counts.ran ?? 0, d.counts.broke ?? 0, d.counts.thought ?? 0)}</p>
              {d.median_minutes !== null && <p className="ck-muted">{r.median(typeof d.median_minutes === "number" ? clockText(d.median_minutes * 60) : d.median_minutes)}</p>}
              {d.withdrawn > 0 && <p className="ck-muted">{r.withdrawn(d.withdrawn)}</p>}
            </div>
            <div className="ck-row" aria-label="Filters">
              {Object.entries(kindName).map(([k, n]) => <Chip key={k} tone={kind === k ? "active" : "default"} onClick={() => setKind(kind === k ? null : k)}>{n}</Chip>)}
              {Object.entries(severityName).map(([k, n]) => <Chip key={k} tone={sev === k ? "active" : "default"} onClick={() => setSev(sev === k ? null : k)}>{n}</Chip>)}
              <Chip tone={linked ? "active" : "default"} onClick={() => setLinked(!linked)}>{r.linkedOnly}</Chip>
              <Chip tone={guessed ? "active" : "default"} onClick={() => setGuessed(!guessed)}>{r.guessedOnly}</Chip>
            </div>
            {rows.length === 0 ? <p className="ck-muted">{r.filterNone}</p> : (
              <ul className="ck-list">
                {rows.map((i) => (
                  <li key={i.id} className={`ck-card ck-card--${i.kind}`} style={{ cursor: "default" }}>
                    <span>{i.text}</span>
                    <span className="ck-row">
                      <span className="ck-tag">{kindName[i.kind]}</span>
                      {i.kind === "broke" && i.severity && <span className="ck-tag">{severityName[i.severity]}</span>}
                      {i.kind === "broke" && <span className="ck-tag">{i.count !== null ? `${i.count} ${i.unit}` : i.amount ? `${i.amount.value} ${i.amount.currency}` : r.notGiven}</span>}
                      {i.ref && <span className="ck-tag">{i.ref.label}</span>}
                      <span className="ck-tag">{i.author}</span>
                      <span className={`ck-tag${i.mark === "guessed" ? " ck-tag--guess" : ""}`}>{i.provenance}</span>
                      {i.fate && <span className="ck-tag">{fateName[i.fate]}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </ScreenState>
      <div><Link to={`/centre/intent/${intentId}/week`} className="ds-btn">{m.back}</Link></div>
    </div>
  );
}
