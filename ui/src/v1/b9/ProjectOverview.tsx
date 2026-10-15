import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill, when } from "../../design";
import { useSession } from "../../useSession";
import { useFacts } from "../b8/useFacts";
import { getProject, type Project } from "../p1/api";
import { listAssignments, initials, type Assignment } from "./api";
import AssignDialog from "./AssignDialog";
import { currentStep, events, headline, stepViews, type Person } from "./overview";
import StepIcon from "./StepIcons";
import { STEPS, stepPath, type StepId } from "./steps";
import "./b9.css";

// V5 A4/A6: /centre/build/p/:projectId/overview. The four steps with their status and people, what has happened, and the next thing to do.
const TONE = { done: "ok", here: "draft", waiting: "late", todo: "open" } as const;

function PersonView({ p }: { p: Person }) {
  return <span className="b9-person"><b aria-hidden="true">{p.name === "Not assigned yet" ? "?" : initials(p.name)}</b><span><small>{p.label}</small>{p.name}{p.sub ? <small>{p.sub}</small> : null}</span></span>;
}

export default function ProjectOverview() {
  const { projectId = "" } = useParams();
  const roles = useSession().user?.roles ?? [];
  const canAssign = roles.some((r) => r === "analyst" || r === "company_admin");
  const facts = useFacts(projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [assigns, setAssigns] = useState<Assignment[]>([]);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<null | { preset: StepId[]; handover: boolean }>(null);

  const load = useCallback(() => {
    getProject(projectId).then(setProject).catch((e) => setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."));
    listAssignments(projectId).then((r) => setAssigns(r.assignments ?? [])).catch(() => setAssigns([])); // no assignments yet, or not available: the page still reads
  }, [projectId]);
  useEffect(() => { load(); }, [load]);

  if (error) return <PageFrame title="Project overview"><p role="alert">{error}</p></PageFrame>;
  if (!project || !facts.ready) return <PageFrame title="Project overview"><p className="ds-muted" role="status">Opening the project.</p></PageFrame>;

  const views = stepViews({ project, plan: facts.plan, runs: facts.runs, boards: facts.boards, assigns });
  const now = currentStep(views);
  const p = encodeURIComponent(projectId);
  const unbuilt = views[1]?.status === "Needs a builder";
  const events_ = events({ project, plan: facts.plan, runs: facts.runs, boards: facts.boards, assigns });
  const builder = assigns.find((a) => a.step === "architecture");
  const next = unbuilt
    ? { title: "Choose who builds Architecture and Pipelines", body: "Span drafts both steps. A person needs to check the draft and send it to the head of data for approval. That can be you or a data engineer.", action: canAssign ? "Assign step" : "" }
    : builder && now.id === "architecture"
    ? { title: `Nothing for you until ${builder.assignee_name ?? "the builder"} sends the architecture`, body: "Span drafts the tables with them. When they send them, the head of data approves, and you get a note here and in Action.", action: "" }
    : { title: `Next: ${now.id === "intent" ? "finish the intent with North" : `open ${STEPS.find((s) => s.id === now.id)?.name}`}`, body: now.status, action: "" };

  return (
    <PageFrame title={project.title} crumbs={<><Link className="ds-link" to="/centre/build">Running projects</Link> · <Link className="ds-link" to={`/centre/project/${p}`}>Project page: documents, run book, deviations</Link></>}
      subline={<><span className="b9-eyebrow">{headline(views)}</span><br />{project.people.raiser ? `Owner ${project.people.raiser}` : ""}{project.people.sponsor ? ` · Sponsor ${project.people.sponsor}` : ""}</>}
      actions={canAssign ? <><Link className="ds-btn" to={`/centre/build/p/${p}/handover`}>Hand over</Link> <Button variant="primary" onClick={() => setDialog({ preset: ["architecture"], handover: false })}>Assign step</Button></> : undefined}>
      <p className="ds-muted" style={{ margin: 0 }}><Link className="ds-link" to={`/centre/project/${p}?artefact=intent`}>Read the signed intent</Link></p>
      <div className="b9-steps" style={{ marginTop: "var(--ds-s3)" }}>
        {views.map((v) => {
          const info = STEPS.find((s) => s.id === v.id)!;
          return (
            <section key={v.id} className="b9-step" data-mark={v.mark} aria-label={`Step ${info.n}: ${info.name}`}>
              <span className="b9-eyebrow">STEP {info.n} · {info.agent.toUpperCase()}</span>
              <h2 style={{ margin: 0, fontSize: 18, display: "flex", alignItems: "center", gap: 8 }}><StepIcon step={v.id} size={20} />{info.name}</h2>
              <span><Pill tone={TONE[v.mark]}>{v.status}</Pill></span>
              <div className="b9-people">{v.people.map((x) => <PersonView key={x.label} p={x} />)}</div>
              <p style={{ margin: 0 }}>{v.line}</p>
              <Link className="ds-link" to={stepPath(projectId, v.id)}>Open {info.name.toLowerCase()}</Link>
            </section>
          );
        })}
      </div>
      <div className="b9-split">
        <section className="b9-box" aria-label="What has happened">
          <h2 style={{ margin: "0 0 var(--ds-s3)", fontSize: 18 }}>What has happened</h2>
          {events_.length === 0 ? <p className="ds-muted">Nothing yet.</p> : (
            <ul className="b9-time-list">{events_.map((e, i) => (
              <li key={i}><strong>{e.who ? `${e.who} ` : ""}{e.text}</strong> <span className="ds-muted">{when(e.at)}</span>{e.note ? <div className="ds-muted">"{e.note}"</div> : null}</li>
            ))}</ul>
          )}
        </section>
        <section className="b9-box" aria-label="Next">
          <span className="b9-eyebrow">NEXT</span>
          <h2 style={{ margin: "4px 0 8px", fontSize: 18 }}>{next.title}</h2>
          <p>{next.body}</p>
          {next.action ? <Button variant="primary" onClick={() => setDialog({ preset: ["architecture", "pipelines"], handover: false })}>{next.action}</Button> : null}
        </section>
      </div>
      {dialog ? <AssignDialog pid={projectId} title={project.title} preset={dialog.preset} handover={dialog.handover} people={project.people}
        onClose={() => setDialog(null)} onDone={() => { setDialog(null); load(); void facts.reload(); }} /> : null}
    </PageFrame>
  );
}
