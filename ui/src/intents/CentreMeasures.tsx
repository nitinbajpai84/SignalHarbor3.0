import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiGet } from "../api/client";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { Chip, Footnote } from "../design";

// "How the centre is doing" (spec 19, Screen 2). Company admin only; the numbers come from GET /api/intents/measures.

type Month = { month: string } & Record<string, number | string>;
export interface Measure {
  id: string; name: string; value: number | null; numerator: number | null; denominator: number | null;
  by_type: Record<string, unknown>; by_month: Month[]; ids: string[]; missing: string | null; small_group: boolean;
  extensions?: number; actions?: number; free_text?: number; handed?: number; waiting?: number; ratings?: number; note?: string;
  fates?: { problem: number; backlog: number; handled: number; nothing: number };
  answers?: { yes: number; partly: number; no: number; not_answered: number };
}
export interface MeasuresDoc { company: string; window: string; months: string[]; scope: "all" | "visible" | "counts"; measures: Measure[] }

export const measuresCopy = {
  title: "How the centre is doing",
  showAll: "Show all measures",
  hide: "Show fewer",
  window: "Window",
  windows: { "6m": "Last 6 months", "12m": "Last 12 months", quarter: "This quarter" } as Record<string, string>,
  csv: "Download as CSV",
  csvNone: "Nothing to download yet",
  more: "More",
  showIntents: (n: number) => `Show the intents (${n})`,
  definition: "What this counts",
  fields: "Fields read",
  computedFrom: (n: number) => `Computed from ${n} ${n === 1 ? "intent" : "intents"}.`,
  close: "Close",
  fewerFive: "Fewer than five",
  fewerThree: "Fewer than three ratings",
  footnote: "Numbers come from the intent records of this company. Ratings are counted including anonymous ones; notes are never shown here.",
  empty: "Nothing to measure yet. Measures appear after the first intent is opened.",
  sections: [
    { title: "Starting and finishing", ids: ["M01", "M02", "M03", "M04"] },
    { title: "Effort", ids: ["M05", "M06"] },
    { title: "Quality of definitions and outcomes", ids: ["M07", "M08", "M13", "M15"] },
    { title: "What came out", ids: ["M09", "M10", "M11", "M12", "M14"] },
  ],
};

/** The exact definitions of file 19 and the fields each reads. */
export const DEFS: Record<string, [string, string]> = {
  M01: ["Count of intents with state not draft and the first stage opened in the month, grouped by type.", "type, state, stages[0].opened_at"],
  M02: ["Of closed intents, the number closed on or before the final end of the time box (the end after every extension), shown n of m per type.", "closure.closed_at, time_box.ends, time_box.extended_by"],
  M03: ["Median working days (Monday to Friday, no holidays) from the first stage opening to the close, per type, with the count of intents. The mean is not shown.", "stages[0].opened_at, closure.closed_at"],
  M04: ["Per type: the number of closed intents with at least one extension, and the total extensions.", "time_box.extended_by, state"],
  M05: ["For an Initiative with a wall: the span in minutes from the private rooms opening to the signed outcome, with the counts of actions and free-text entries. Elapsed minutes of the work, not a timesheet; no person is named.", "wall inputs.actions, inputs.free_text, started.private_rooms, signed_at"],
  M06: ["Initiatives with a wall only. Cards written by named authors within five minutes of the private rooms opening, divided by the number of distinct named authors, to one decimal.", "wall cards lane.at, author, anonymous"],
  M07: ["Of the technical parts a data owner confirmed in the newest baseline, the number left exactly as Lens drafted them. Sealed measures are never counted.", "baseline technical_confirmed, technical.<part>.from"],
  M08: ["Initiatives whose build-ready stage closed with build ready set to yes, in the period. Beside it, how many were handed to Build and how many are waiting.", "stages[build_ready].closed_at, outcome.build_ready, links.build"],
  M09: ["Of closed Brainstorms, the number with a next step of kind initiative that resolves to an Initiative coming from this Brainstorm.", "closure.next[], links.to, the target's type and links.from"],
  M10: ["Over closed weeks: items that became a Problem, went to the backlog, were already handled, or came to nothing, out of all items. A problem fate with no Problem behind it counts as nothing.", "week items[].fate, fate_ref, closed_at"],
  M11: ["Of closed Problems, the number with a named root cause and a named person for the fix.", "outcome.root_cause, outcome.fix.by, state"],
  M12: ["Closed Decisions with what was chosen, who decided and why all recorded. A Decision closed with a reason for no decision counts in the total only.", "outcome.chosen, decided_by, why, no_decision_reason"],
  M13: ["Per type: the mean rating over intents closed in the period, to one decimal, with the count of ratings. Anonymous ratings included; notes never.", "ratings[]"],
  M14: ["Count of closed intents with at least one next step of kind initiative or problem that resolves to an intent, by type.", "closure.next[], links.to"],
  M15: ["Of closed intents whose organiser was asked one month on, the number answering used, partly and not used, and the number not answered.", "outcome_used.answer, asked_at, answered_at, closure.closed_at"],
};

const narrow = () => typeof window !== "undefined" && window.matchMedia?.("(max-width: 700px)").matches === true;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const of = (m: Measure) => `${m.numerator ?? 0} of ${m.denominator ?? 0}`;

/** The value in words and digits. Null when the row has no value (Not available yet or a small group). */
export function valueText(m: Measure): string | null {
  if (m.value === null) return null;
  switch (m.id) {
    case "M01": return `${m.value} opened`;
    case "M03": return `${m.value} working days, median of ${m.denominator}`;
    case "M04": return `${of(m)} extended, ${plural(m.extensions ?? 0, "extension", "extensions")}`;
    case "M05": return `${m.value} minutes, ${m.actions ?? 0} actions, ${m.free_text ?? 0} free-text entries`;
    case "M06": return `${m.value} cards per person`;
    case "M08": return `${m.value} build-ready, ${m.handed ?? 0} handed to Build, ${m.waiting ?? 0} waiting`;
    case "M10": { const f = m.fates!; return `${plural(f.problem, "problem", "problems")}, ${f.backlog} backlog, ${f.handled} handled, ${f.nothing} nothing, of ${plural(m.denominator ?? 0, "item", "items")}`; }
    case "M13": return `${m.value} from ${m.ratings} ratings`;
    case "M15": { const a = m.answers!; return `${a.yes} used, ${a.partly} partly, ${a.no} not used, ${a.not_answered} not answered, of ${m.denominator}`; }
    default: return of(m);
  }
}

const monthName = (m: string) => new Date(`${m}-01T00:00:00Z`).toLocaleString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const monthCount = (r: Month) => Number(r.count ?? r.items ?? r.ratings ?? r.denominator ?? 0);

/** One row per measure per month: measure id, group, month, numerator, denominator, value. No titles, names or notes. */
export function toCsv(doc: MeasuresDoc): string {
  const group = (id: string) => measuresCopy.sections.find((s) => s.ids.includes(id))?.title ?? "";
  const cell = (v: unknown) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const rows = [["measure", "group", "month", "numerator", "denominator", "value"]];
  for (const m of doc.measures) {
    if (!m.by_month.length) rows.push([m.id, group(m.id), "current", String(m.numerator ?? ""), String(m.denominator ?? ""), String(m.value ?? "")]);
    for (const r of m.by_month) {
      const num = r.numerator ?? r.count ?? (m.id === "M10" ? Number(r.problem) + Number(r.backlog) : r.ratings);
      const den = r.denominator ?? r.items ?? "";
      rows.push([m.id, group(m.id), r.month, String(num ?? ""), String(den), String(num ?? "")]);
    }
  }
  return rows.map((r) => r.map(cell).join(",")).join("\n") + "\n";
}

function download(doc: MeasuresDoc) {
  const url = URL.createObjectURL(new Blob([toCsv(doc)], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `centre-measures-${doc.window}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

function Row({ m, phone, onDefine, onShow }: { m: Measure; phone: boolean; onDefine: () => void; onShow: (ids: string[]) => void }) {
  const text = valueText(m);
  const strip = phone ? m.by_month.slice(-2) : m.by_month;
  return (
    <li className="cm-row" style={{ padding: "10px 0", borderTop: "1px solid var(--line, #e3e6e8)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
        <strong>{m.name}</strong>
        <button type="button" className="n-btn" aria-label={`${measuresCopy.definition}: ${m.name}`} onClick={onDefine}>?</button>
      </div>
      {m.missing && m.value === null && !m.small_group ? (
        <p className="n-muted" style={{ margin: "4px 0" }}>{m.missing}</p>
      ) : m.small_group ? (
        <p style={{ margin: "4px 0" }}><Chip>{m.id === "M13" ? measuresCopy.fewerThree : measuresCopy.fewerFive}</Chip></p>
      ) : (
        <p style={{ margin: "4px 0", fontSize: "1.1rem" }}>{text}</p>
      )}
      {m.missing && m.value !== null ? <p className="n-muted" style={{ margin: "2px 0", fontSize: ".85rem" }}>{m.missing}</p> : null}
      {m.note ? <p className="n-muted" style={{ margin: "2px 0", fontSize: ".85rem" }}>{m.note}</p> : null}
      {strip.length ? (
        <ol aria-label={`${m.name} by month`} style={{ display: "flex", gap: 10, listStyle: "none", padding: 0, margin: "4px 0", fontSize: ".85rem", flexWrap: "wrap" }}>
          {strip.map((r) => <li key={r.month}><span className="n-muted">{monthName(r.month)}</span> {monthCount(r)}</li>)}
        </ol>
      ) : null}
      {m.ids.length ? <button type="button" className="n-btn" onClick={() => onShow(m.ids)}>{measuresCopy.showIntents(m.ids.length)}</button> : null}
    </li>
  );
}

/** The panel. `onShowIntents` lets the home set its filters to exactly those ids; otherwise it opens the home with `?ids=`. */
export function CentreMeasures({ onShowIntents, initiallyOpen = false }: { onShowIntents?: (ids: string[]) => void; initiallyOpen?: boolean }) {
  const [win, setWin] = useState("6m");
  const [open, setOpen] = useState(initiallyOpen);
  const [define, setDefine] = useState<Measure | null>(null);
  const navigate = useNavigate();
  const phone = narrow();
  const load = useLoad(() => apiGet<MeasuresDoc>(`/api/intents/measures?window=${win}`), win);
  const doc = load.data;
  if (doc && doc.scope !== "all") return null;
  const show = onShowIntents ?? ((ids: string[]) => navigate(`/centre/intent?ids=${ids.join(",")}`));
  const anyValue = !!doc?.measures.some((m) => m.value !== null);
  const empty = !!doc && doc.measures.find((m) => m.id === "M01")?.value === null;
  const byId = new Map((doc?.measures ?? []).map((m) => [m.id, m]));
  const csvButton = (
    <button type="button" className="n-btn" disabled={!anyValue} title={anyValue ? undefined : measuresCopy.csvNone} onClick={() => doc && download(doc)}>
      {anyValue ? measuresCopy.csv : measuresCopy.csvNone}
    </button>
  );
  const select = (
    <label style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <span className={phone ? undefined : "n-muted"}>{measuresCopy.window}</span>
      <select value={win} onChange={(e) => setWin(e.target.value)}>
        {Object.entries(measuresCopy.windows).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
    </label>
  );
  const actions = phone ? select : <>{select}{csvButton}</>;
  return (
    <Panel title={measuresCopy.title} actions={actions}>
      <ScreenState state={load.state} message={load.message} onRetry={load.retry}>
        {empty ? <p className="n-muted">{measuresCopy.empty}</p> : (
          <>
            {phone ? <details><summary>{measuresCopy.more}</summary>{csvButton}</details> : null}
            {(
              <div style={{ display: "grid", gridTemplateColumns: phone ? "1fr" : "1fr 1fr", gap: "8px 24px", marginTop: 12 }}>
                {measuresCopy.sections.slice(0, open ? 4 : 1).map((s, i) => (
                  <details key={s.title} open={!phone || i === 0}>
                    <summary><h3 style={{ display: "inline", fontSize: "1rem" }}>{s.title}</h3></summary>
                    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                      {s.ids.map((id) => byId.get(id)).filter((m): m is Measure => !!m).map((m) => (
                        <Row key={m.id} m={m} phone={phone} onDefine={() => setDefine(m)} onShow={show} />
                      ))}
                    </ul>
                  </details>
                ))}
              </div>
            )}
            <button type="button" className="n-btn" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? measuresCopy.hide : measuresCopy.showAll}</button>
            <Footnote>{measuresCopy.footnote}</Footnote>
          </>
        )}
      </ScreenState>
      {define ? (
        <aside role="dialog" aria-label={`${measuresCopy.definition}: ${define.name}`}
          style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: "min(420px, 100vw)", background: "var(--surface, #fff)", padding: 20, boxShadow: "0 0 24px rgba(0,0,0,.2)", overflow: "auto", zIndex: 50 }}>
          <h3>{define.name}</h3>
          <p><strong>{measuresCopy.definition}.</strong> {(DEFS[define.id] ?? ["", ""])[0]}</p>
          <p><strong>{measuresCopy.fields}:</strong> {(DEFS[define.id] ?? ["", ""])[1]}</p>
          <p>{measuresCopy.computedFrom(define.ids.length || define.denominator || 0)}</p>
          <button type="button" className="n-btn" onClick={() => setDefine(null)}>{measuresCopy.close}</button>
        </aside>
      ) : null}
    </Panel>
  );
}

export default CentreMeasures;
