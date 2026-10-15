import { InStepper } from "../b9/context";
import { Link, useParams } from "react-router-dom";
import { useContext, useState } from "react";

import { ApiError } from "../../api/client";
import { PageFrame, Pill } from "../../design";
import * as b6 from "../b6/api";
import { Pipeline } from "../b6/Steps";
import { useProjectTitle } from "../s1/useProjectTitle";
import { STATE_TONE, STATE_WORD, type Stage } from "./stages";
import BuilderPanel from "../b11/BuilderPanel";
import VerifyPanel from "../b9verify/VerifyPanel";
import RoomSwitcher from "./RoomSwitcher";
import { planOf, stagesOf, useFacts } from "./useFacts";

// BC1: Pipelines room. Sources to gold as four cards that carry their state, the controls under them, the run log below.
const when = (at: string | null) => { const d = at ? new Date(at) : null; return d && !Number.isNaN(d.getTime()) ? d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : null; };
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");

export function StageCard({ s, schedule }: { s: Stage; schedule: string }) {
  const shown = s.items.slice(0, 4);
  return (
    <li className="b8-stage" data-state={s.state} aria-label={`${s.name}: ${STATE_WORD[s.state]}`}>
      <h3>{s.name}</h3>
      <p className="ds-muted" style={{ margin: 0 }}>{s.line}</p>
      <p style={{ margin: "8px 0" }}><Pill tone={STATE_TONE[s.state]}>{STATE_WORD[s.state]}</Pill></p>
      {shown.length ? <ul>{shown.map((n) => <li key={n}>{n}</li>)}{s.items.length > shown.length ? <li>and {s.items.length - shown.length} more</li> : null}</ul> : <p className="ds-muted">Nothing here yet.</p>}
      {s.id !== "sources" ? <p style={{ margin: 0, fontSize: 13 }}>Last run: {when(s.last) ?? "Not run yet"}<br />Next run: {when(s.next) ?? schedule}</p> : null}
    </li>
  );
}

export default function PipelinesRoom() {
  const { projectId = "" } = useParams();
  const inStepper = useContext(InStepper); // the step rail already carries these links
  const title = useProjectTitle(projectId);
  const facts = useFacts(projectId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const plan = planOf(facts.plan);
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setError(""); try { await fn(); await facts.reload(); } catch (e) { setError(plain(e)); } finally { setBusy(false); } };
  const idle = plan && plan.schedule.freq === "on_arrival" ? "When a new file arrives" : plan?.state === "live" ? `${plan.schedule.freq} at ${plan.schedule.at}` : "Not scheduled until the plan is live";
  return (
    <PageFrame title={`${title}: Pipelines`} subline="Files flow from the sources through bronze and silver to gold, the tables dashboards read."
      crumbs={inStepper ? undefined : <><Link className="ds-link" to="/centre/build">All projects</Link> · <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}`}>Plan and Span</Link></>}>
      <RoomSwitcher pid={projectId} current="pipelines" facts={facts} />
      <BuilderPanel pid={projectId} />
      {!facts.ready ? <p className="ds-muted" role="status">Opening the pipeline.</p> : !plan ? (
        <p>Span has not proposed a plan for this project yet. <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}`}>Ask Span for one</Link>.</p>
      ) : (
        <details className="b8-eng" style={{ marginTop: 16 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>For engineers: the stages, the run controls and the control totals of this project</summary>
          <ol className="b8-flow" aria-label="Stages from sources to gold" style={{ listStyle: "none", padding: 0 }}>
            {stagesOf(facts).map((s) => <StageCard key={s.id} s={s} schedule={idle} />)}
          </ol>
          {error ? <p role="alert">{error}</p> : null}
          <section aria-label="Controls and run log" className="b8-tools">
            <h2 style={{ fontSize: 18 }}>Run it, schedule it, check the log</h2>
            <Pipeline plan={plan} runs={facts.runs} busy={busy} pid={projectId}
              onRun={(m) => void act(() => b6.startRun(projectId, m))} onSchedule={(s) => void act(() => b6.setSchedule(projectId, s))} />
          </section>
          <VerifyPanel pid={projectId} />
        </details>)}
    </PageFrame>
  );
}
