import { NavLink } from "react-router-dom";

import StatusPill, { type PillTone } from "../../components/StatusPill";
import type { Step, StepState } from "./api";
import { m3Steps } from "./copy";

const HOME = "/modules/m3_connect";
/** Six steps, four screens: the data request and the scan share one, the trial and the findings share one. */
const AREA: Record<Step["id"], string> = { map: "map", request: "intake", scan: "intake", trial: "trial", findings: "trial", plan: "plan" };
const TONE: Record<StepState, PillTone> = { not_started: "muted", in_progress: "info", done: "success" };

/** The six steps of one assessment as tabs (module 2's step bar pattern), each with where it stands. */
export default function ConnectSteps({ assessmentId, steps }: { assessmentId: string; steps: Step[] }) {
  return (
    <nav className="n-tabs" aria-label={m3Steps.label}>
      {steps.map((s) => (
        <NavLink key={s.id} to={`${HOME}/${AREA[s.id]}/${assessmentId}`} end className={({ isActive }) => `n-tab${isActive ? " active" : ""}`}>
          {m3Steps[s.id]} <StatusPill tone={TONE[s.state]}>{m3Steps.state[s.state]}</StatusPill>
        </NavLink>
      ))}
    </nav>
  );
}
