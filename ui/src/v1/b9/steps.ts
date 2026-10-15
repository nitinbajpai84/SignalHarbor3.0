// V5 (card V5W-2): the four steps of a Build project, in one place. Copy follows docs/plan/v5-designs/A1 and A4.
export type StepId = "intent" | "architecture" | "pipelines" | "dashboards";
export interface StepInfo { id: StepId; n: number; name: string; agent: string; line: string }

export const STEPS: StepInfo[] = [
  { id: "intent", n: 1, name: "Intent", agent: "North", line: "Say what you need in your own words. North drafts it, the sponsor signs it." },
  { id: "architecture", n: 2, name: "Architecture", agent: "Span", line: "Span maps it to the data you have. The data team checks and approves." },
  { id: "pipelines", n: 3, name: "Pipelines", agent: "Span", line: "Try it on a copy, check the numbers, then schedule it and go live." },
  { id: "dashboards", n: 4, name: "Dashboards", agent: "Lumen", line: "Lumen designs what people see. Someone else approves, then it is sent." },
];
/** Steps a person can be given (the intent is signed, not assigned). */
export const ASSIGNABLE: StepId[] = ["architecture", "pipelines", "dashboards"];

export const stepName = (id: StepId): string => STEPS.find((s) => s.id === id)?.name ?? id;
export const stepPath = (pid: string, id: StepId): string => `/centre/build/p/${encodeURIComponent(pid)}/${id}`;
export const overviewPath = (pid: string): string => `/centre/build/p/${encodeURIComponent(pid)}/overview`;
