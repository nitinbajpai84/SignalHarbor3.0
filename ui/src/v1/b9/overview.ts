import type { Plan, NoPlan, Run } from "../b6/api";
import type { Project } from "../p1/api";
import type { StudioRow } from "../b7/api";
import { nice, type Assignment } from "./api";
import { STEPS, stepName, type StepId } from "./steps";
import type { Mark } from "./progress";

// V5W-2: the project overview's facts, read only from records (the project, its plan, runs, dashboards, assignments). Pure.
export interface Facts { project: Project; plan: Plan | NoPlan | null; runs: Run[]; boards: StudioRow[]; assigns: Assignment[] }
export interface Person { label: string; name: string; sub?: string }
export interface StepView { id: StepId; mark: Mark; status: string; people: Person[]; line: string }
export interface Event { at: string; who: string; text: string; note?: string }

const planOf = (p: Facts["plan"]): Plan | null => (p && "tables" in p ? p : null);
const LINE: Record<StepId, string> = {
  intent: "", architecture: "Span drafts where the figures come from; the head of data approves.",
  pipelines: "Trial run on a copy, checked before it is scheduled.", dashboards: "Lumen drafts the views; someone else approves, then they are sent.",
};

export function stepViews(f: Facts): StepView[] {
  const { project: pr } = f;
  const plan = planOf(f.plan);
  const signed = pr.stage !== "talking";
  const by = (s: StepId) => f.assigns.find((a) => a.step === s);
  const builder = (s: StepId): Person => {
    const a = by(s);
    const name = nice(a?.assignee_name ?? a?.assignee) || nice(pr.people.builder);
    return name ? { label: "BUILDER", name, sub: a?.due ? `due ${a.due}` : undefined } : { label: "BUILDER", name: "Not assigned yet" };
  };
  const owner: Person[] = pr.people.raiser ? [{ label: "OWNER", name: nice(pr.people.raiser) }] : [];
  const approves: Person[] = pr.people.head_of_data ? [{ label: "APPROVES", name: nice(pr.people.head_of_data), sub: "Head of data" }] : [];
  const archDone = !!plan && ["approved", "built", "live"].includes(plan.state);
  const live = plan?.state === "live";
  const boards = (s: string) => f.boards.filter((b) => b.status === s).length;

  let arch: [Mark, string] = !plan ? (by("architecture") ? ["here", `Assigned to ${nice(by("architecture")?.assignee_name ?? by("architecture")?.assignee)}`] : signed ? ["waiting", "Needs a builder"] : ["todo", "Not started"])
    : plan.state === "proposed" ? ["waiting", "Waiting for the head of data"] : plan.state === "rejected" ? ["here", "Sent back"] : archDone ? ["done", "Approved"] : ["here", "Draft"];
  let pipe: [Mark, string] = !archDone ? (by("pipelines") ? ["todo", "Assigned · starts after step 2"] : ["todo", "Not started"])
    : live ? ["done", "Live"] : f.runs.length ? ["here", "Trial run done"] : ["here", "Ready for a trial run"];
  const dash: [Mark, string] = boards("published") ? ["done", `${boards("published")} published`] : boards("submitted") ? ["waiting", "Waiting for approval"] : f.boards.length ? ["here", "In progress"] : ["todo", "Not started"];
  if (!signed) arch = ["todo", "Opens when the intent is signed"];

  return [
    { id: "intent", mark: signed ? "done" : "here", status: signed ? "Signed" : "Being defined with North", line: signed ? "The signed intent is the brief for every later step." : "North asks one thing at a time and drafts the intent beside you.",
      people: [...owner, ...(signed && pr.people.sponsor ? [{ label: "SIGNED", name: nice(pr.people.sponsor), sub: "Sponsor" }] : [])] },
    { id: "architecture", mark: arch[0], status: arch[1], line: LINE.architecture, people: [...owner, builder("architecture"), ...approves] },
    { id: "pipelines", mark: pipe[0], status: pipe[1], line: LINE.pipelines, people: [...owner, builder("pipelines"), ...approves] },
    { id: "dashboards", mark: dash[0], status: dash[1], line: LINE.dashboards, people: [...owner, ...(by("dashboards") ? [builder("dashboards")] : [])] },
  ];
}

const short = (iso: string | null | undefined): string => { const d = new Date(iso ?? ""); return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }); };

/** V6 (design D3, D4): one status line per step for the strip, from records only: who signed or approved, since when, who is waited for. */
export function stepStatuses(f: Facts): string[] {
  const v = stepViews(f);
  const pr = f.project, plan = planOf(f.plan);
  const art = pr.artefacts?.find((a) => a.kind === "intent");
  const intent = art?.state === "signed" && art.signed_by ? `Signed by ${nice(art.signed_by)}` : v[0]!.status;
  const arch = plan && ["approved", "built", "live"].includes(plan.state) && plan.approved_by ? `Approved by ${nice(plan.approved_by)}` : plan?.state === "proposed" ? `Waiting for ${nice(pr.people.head_of_data) || "the head of data"}` : v[1]!.status;
  const liveRun = f.runs.find((r) => r.mode === "live" && r.status === "ok");
  const pipe = plan?.state === "live" ? `Live${liveRun?.finished ? ` since ${short(liveRun.finished)}` : ""}` : v[2]!.status;
  const pub = f.boards.find((b) => b.status === "published");
  const dash = pub?.approved_by ? `Approved by ${nice(pub.approved_by)}` : f.boards.some((b) => b.status === "submitted") ? `Waiting for ${nice(pr.people.sponsor) || "the sponsor"}'s approval` : v[3]!.status;
  return [intent, arch, pipe, dash];
}

/** Which step the page is on: the first that is not done. */
export const currentStep = (v: StepView[]): StepView => v.find((s) => s.mark !== "done") ?? (v[v.length - 1] as StepView);

/** "STEP 2 OF 4 · NEEDS A BUILDER". */
export const headline = (v: StepView[]): string => { const c = currentStep(v); return `STEP ${STEPS.findIndex((s) => s.id === c.id) + 1} OF 4 · ${c.status.toUpperCase()}`; };

export function events(f: Facts): Event[] {
  const out: Event[] = [];
  const { project: pr } = f;
  if (pr.started_at) out.push({ at: pr.started_at, who: nice(pr.started_by), text: "started the project with North" });
  for (const a of pr.artefacts ?? []) if (a.signed_at) out.push({ at: a.signed_at, who: nice(a.signed_by), text: `signed the ${a.kind === "intent" ? "intent" : a.kind.replace(/_/g, " ")}` });
  for (const a of f.assigns) if (a.at) out.push({ at: a.at, who: nice(a.by_name ?? a.by), text: `assigned ${stepName(a.step)} to ${nice(a.assignee_name ?? a.assignee)}${a.due ? `, due ${a.due}` : ""}`, note: a.note ?? undefined });
  const plan = planOf(f.plan);
  if (plan?.approved_at) out.push({ at: plan.approved_at, who: nice(plan.approved_by), text: "approved the architecture" });
  for (const r of f.runs.slice(0, 3)) out.push({ at: r.finished ?? r.started, who: "", text: `A ${r.mode === "live" ? "live" : "trial"} run ${r.status === "ok" ? "finished: all steps ok" : r.status}` });
  return out.filter((e) => !Number.isNaN(new Date(e.at).getTime())).sort((a, b) => +new Date(b.at) - +new Date(a.at));
}
