import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet, Refused } from "../api/client";
import Panel from "../components/Panel";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { oc } from "./outcomesCopy";

// The outcomes of the Intent Centre itself (spec section 9). Every number comes from GET /api/company/outcomes; null reads "Not available yet".

interface Match { matches: number; gap: number; cannot: number; not_yet: number; restricted: number }
interface Outcomes {
  headline: {
    days_file_to_match: number | null; days_card_to_report: number | null; stage: string | null;
    definitions_unchanged: { unchanged: number; of: number } | null; match: Match | null; cards_first_five: number | null;
    files_read: number | null; interviews: { done: number; of: number } | null; drafts_accepted: number | null;
  };
  modules: { module: string; actions: number | null; free_text: number | null; minutes: number | null }[];
  funnel: Record<"cards" | "clusters" | "measures" | "owned" | "matching", number>;
}

const STEPS = ["cards", "clusters", "measures", "owned", "matching"] as const;
const num = (n: number | null): string => (n === null ? oc.na : String(n));
const isEmpty = (o: Outcomes): boolean =>
  Object.entries(o.headline).every(([k, v]) => k === "stage" || v === null) && Object.values(o.funnel).every((n) => n === 0)
  && o.modules.every((m) => m.actions === null && m.free_text === null && m.minutes === null);

function Tile({ label, big, line }: { label: string; big: string | null; line?: string | null }) {
  return (
    <li className="n-panel" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="n-muted">{label}</span>
      <strong style={{ fontFamily: "var(--font-heading)", fontSize: 32, color: big === null ? "var(--mute)" : "var(--ink)" }}>{big ?? oc.na}</strong>
      {line ? <span className="n-muted">{line}</span> : null}
    </li>
  );
}

export default function OutcomesPage() {
  const [state, setState] = useState<ScreenStateName>("loading");
  const [data, setData] = useState<Outcomes | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    apiGet<Outcomes>("/api/company/outcomes")
      .then((o) => { if (live) { setData(o); setState(isEmpty(o) ? "empty" : "populated"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);

  const retry = useCallback(() => { setState("loading"); setAttempt((n) => n + 1); }, []);
  const h = data?.headline;
  const top = Math.max(1, ...(data ? STEPS.map((s) => data.funnel[s]) : [1]));
  const total = h?.match ? h.match.matches + h.match.gap + h.match.cannot + h.match.not_yet : 0;

  return (
    <>
      <h1 className="n-page-title">{oc.title}</h1>
      <p>{oc.intro}</p>
      <p className="n-muted"><Link to="/centre/intent">{oc.back}</Link></p>
      <ScreenState state={state} onRetry={retry}
        message={state === "error" ? oc.failed : state === "refused" ? oc.noAccess : state === "empty" ? oc.empty : undefined}>
        {h && data ? (
          <>
            <Panel title={oc.headline}>
              <ul className="tiles" aria-label={oc.headline}>
                <Tile label={oc.tiles.fileToMatch} big={h.days_file_to_match === null ? null : oc.days(h.days_file_to_match)} />
                <Tile label={oc.tiles.cardToReport} big={h.days_card_to_report === null ? null : oc.days(h.days_card_to_report)} line={h.stage ? oc.stage(h.stage) : null} />
                <Tile label={oc.tiles.unchanged} big={h.definitions_unchanged ? oc.ofN(h.definitions_unchanged.unchanged, h.definitions_unchanged.of) : null} />
                <Tile label={oc.tiles.match} big={h.match ? oc.ofN(h.match.matches, total) : null} line={h.match ? oc.matchLine(h.match) : null} />
                <Tile label={oc.tiles.firstFive} big={h.cards_first_five === null ? null : String(h.cards_first_five)} />
                <Tile label={oc.tiles.files} big={h.files_read === null ? null : String(h.files_read)} />
                <Tile label={oc.tiles.interviews} big={h.interviews ? oc.ofN(h.interviews.done, h.interviews.of) : null} />
                <Tile label={oc.tiles.accepted} big={h.drafts_accepted === null ? null : String(h.drafts_accepted)} />
              </ul>
            </Panel>
            <Panel title={oc.perModule}>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
                {data.modules.map((m) => {
                  const t = oc.targets[m.module];
                  return (
                    <li key={m.module}>
                      <strong>{oc.modules[m.module] ?? m.module}</strong>
                      <dl style={{ display: "flex", gap: 24, flexWrap: "wrap", margin: 0 }}>
                        <div><dt className="n-muted">{oc.actions}</dt><dd style={{ margin: 0 }}>{num(m.actions)}</dd></div>
                        <div><dt className="n-muted">{oc.freeText}</dt><dd style={{ margin: 0 }}>{num(m.free_text)}</dd></div>
                        <div><dt className="n-muted">{oc.minutes}</dt><dd style={{ margin: 0 }}>{num(m.minutes)}</dd></div>
                      </dl>
                      {t ? <span className="n-muted">{`${oc.measured}: ${num(m.actions)} actions · ${oc.target}: ${t.target} actions · ${oc.before}: ${t.before} actions`}</span> : null}
                    </li>
                  );
                })}
              </ul>
            </Panel>
            <Panel title={oc.funnel}>
              {STEPS.map((s) => (
                <div key={s} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ width: 90 }}>{oc.steps[s]}</span>
                  <div role="img" aria-label={`${oc.steps[s]} ${data.funnel[s]}`} style={{ flex: 1, height: 12, background: "var(--border-hairline)", borderRadius: 4 }}>
                    <div style={{ width: `${(100 * data.funnel[s]) / top}%`, height: "100%", background: "var(--teal)", borderRadius: 4 }} />
                  </div>
                  <span>{data.funnel[s]}</span>
                </div>
              ))}
            </Panel>
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
