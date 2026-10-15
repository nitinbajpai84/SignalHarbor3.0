import type { StepId } from "./steps";

// V5: the four Build step icons, drawn once. Intent speech bubble, Architecture stacked layers, Pipelines connected nodes, Dashboards 2x2 grid.
// V6: a fifth drawing, the paper plane of the Deliver chapter on the Build landing.
// Everyone imports this one component; colour follows the text colour (currentColor).
export default function StepIcon({ step, size = 20, title }: { step: StepId | "deliver"; size?: number; title?: string }) {
  const c = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true} focusable="false" data-step-icon={step}>
      {step === "intent" ? <path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H11l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" {...c} /> : null}
      {step === "architecture" ? <><path d="M12 3l9 4.5-9 4.5-9-4.5z" {...c} /><path d="M3 12l9 4.5 9-4.5" {...c} /><path d="M3 16.5L12 21l9-4.5" {...c} /></> : null}
      {step === "pipelines" ? <><circle cx="5" cy="12" r="2.2" {...c} /><circle cx="19" cy="6" r="2.2" {...c} /><circle cx="19" cy="18" r="2.2" {...c} /><path d="M7 11l10-4M7 13l10 4" {...c} /></> : null}
      {step === "deliver" ? <><path d="M21 3L3 10.5l7 2.5 2.5 7z" {...c} /><path d="M10 13l11-10" {...c} /></> : null}
      {step === "dashboards" ? <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" {...c} /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" {...c} /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" {...c} /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" {...c} /></> : null}
    </svg>
  );
}
