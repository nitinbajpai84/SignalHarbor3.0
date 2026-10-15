import { NavLink } from "react-router-dom";

import StatusPill from "../../components/StatusPill";
import { m2Steps } from "./copy";

const HOME = "/modules/m2_baseline";
const STEPS = [
  ["baselines", m2Steps.workList],
  ["requests", m2Steps.requests],
  ["process-map", m2Steps.processMap],
  ["glossary", m2Steps.glossary],
  ["catalogue", m2Steps.catalogue],
  ["governance", m2Steps.governance],
  ["questions", m2Steps.questions],
  ["signoff", m2Steps.signoff],
] as const;

/** One banner for a signed baseline, the same on every screen (the process map's pill, now shared). */
export function SignedBanner({ help = true }: { help?: boolean }) {
  return (
    <p role="status" className="n-flex wrap">
      <StatusPill tone="info">{m2Steps.signed}</StatusPill> {help ? <span className="n-muted">{m2Steps.signedHelp}</span> : null}
    </p>
  );
}

/** The eight screens of one baseline as the earlier product's tabs, so every screen links to every other. `signed` adds the read-only banner. */
export default function BaselineSteps({ baselineId, signed = false }: { baselineId: string; signed?: boolean }) {
  return (
    <>
      <nav className="n-tabs" aria-label={m2Steps.label}>
        {STEPS.map(([path, label]) => (
          <NavLink key={path} to={`${HOME}/${path}/${baselineId}`} end className={({ isActive }) => `n-tab${isActive ? " active" : ""}`}>
            {label}
          </NavLink>
        ))}
      </nav>
      {signed ? <SignedBanner /> : null}
    </>
  );
}
