import { Link } from "react-router-dom";

import { Pill, EmptyState, Button } from "../../design";
import { useLoad } from "../BuildCentre";
import "./chain.css";
import { backWord, cc, daysWord, isOpen, NOT_NAMED, pillTone, stateWord, stepHref, type ChangeSummary } from "./chain";

/** The five steps of one change: step, person, state. Phone: only the current step is open, the rest show name and state. */
export function StepStrip({ c, current }: { c: ChangeSummary; current?: number }) {
  const now = current ?? c.step;
  return (
    <ol className="bc-steps" aria-label={`Steps for ${c.id}`}>
      {c.steps.map((s) => (
        <li key={s.n} className={`bc-step${s.n === now ? " bc-step--now" : ""}`} aria-current={s.n === now ? "step" : undefined}>
          <Link to={stepHref(c.id, s.n)} className="bc-step__name">{s.n}. {s.name}</Link>
          {s.person ? <span className="bc-step__who">{s.person}</span> : (
            <span className="bc-step__who ds-warn" title={cc.nameThem}>{NOT_NAMED}</span>
          )}
          <Pill tone={s.person ? pillTone(s.state) : "late"}>{stateWord(s)}</Pill>
          {s.n === now ? <span className="bc-note">{daysWord(s)}</span> : null}
        </li>
      ))}
    </ol>
  );
}


/** Screen A: the panel "The chain" on Build home. One row per change note not yet live. */
export default function ChainPanel() {
  const { data, state, retry } = useLoad<{ changes: ChangeSummary[] }>("/api/company/build/changes");
  if (state === "refused") return null;
  const all = data?.changes ?? [];
  const open = all.filter(isOpen);
  const live = all.filter((c) => c.state === "live").length;
  return (
    <section aria-label={cc.chainTitle} className="ds-card bc-row" style={{ marginBottom: "var(--ds-s3)" }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{cc.chainTitle}</h2>
      <p className="bc-note">{cc.chainLine}</p>
      {state === "loading" ? <p role="status" className="bc-note">Reading the build records</p> : null}
      {state === "error" ? <div role="alert"><p className="bc-note">{cc.notAvailable}</p><Button onClick={retry}>{cc.retry}</Button></div> : null}
      {state === "populated" && !open.length ? <EmptyState title={cc.chainEmpty} lines={[]} /> : null}
      <ul className="bc-rows" style={{ listStyle: "none", padding: 0 }}>
        {open.map((c) => (
          <li key={c.id} className="ds-card bc-row">
            <Link to={stepHref(c.id, c.step || 1)}>{c.id} {c.title}</Link>
            <StepStrip c={c} />
            {c.last_return ? (
              <Link className="bc-red" to={stepHref(c.id, c.last_return.to)} aria-label={`Sent back: ${c.last_return.reason}`}>{backWord(c.last_return)}</Link>
            ) : null}
          </li>
        ))}
      </ul>
      {state === "populated" ? (live ? <Link to="/centre/build/architecture?focus=change">Live: {live} change{live === 1 ? "" : "s"}</Link> : <p className="bc-note">{cc.noLive}</p>) : null}
    </section>
  );
}

