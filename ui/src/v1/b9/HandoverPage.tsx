import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, when } from "../../design";
import { useSession } from "../../useSession";
import { useFacts } from "../b8/useFacts";
import { getSow, type SowView } from "../i4/api";
import { getProject, type Project } from "../p1/api";
import { assignSteps, initials, listCandidates, nice, type Candidate } from "./api";
import { stepViews } from "./overview";
import StepIcon from "./StepIcons";
import { ASSIGNABLE, STEPS, stepName, stepPath, overviewPath, type StepId } from "./steps";
import "./b9.css";

// V6 design B4: /centre/build/p/:projectId/handover. Hand the build to the data team on one page: which steps go, who builds them, when and with what note.
// It sends the same call as the Assign dialog (assignSteps with handover), so the server, the assignee's Action card and the history are the ones already there.
const WHO: Record<string, string> = { architecture: "WITH SPAN", pipelines: "WITH SPAN", dashboards: "WITH LUMEN" };
const LINE = (id: StepId, head: string): string =>
  id === "architecture" ? `Span proposes the tables from the signed intent. ${head} approves.`
  : id === "pipelines" ? "Try it on a copy, check the figures against the signed ones, schedule it and go live."
  : "Stays with you unless you hand it over. Lumen drafts the page once the data is live.";

export default function HandoverPage() {
  const { projectId = "" } = useParams();
  const go = useNavigate();
  const me = useSession().user;
  const facts = useFacts(projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [sow, setSow] = useState<SowView | null>(null);
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [steps, setSteps] = useState<StepId[]>(["architecture", "pipelines"]);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getProject(projectId).then((p) => {
      if (!live) return;
      setProject(p);
      getSow(p.intent_id).then((s) => live && setSow(s)).catch(() => undefined); // the signed intent's note and sources are a courtesy; the page stands without them
    }).catch((e) => live && setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."));
    listCandidates(projectId).then((r) => live && setCands(r.people ?? [])).catch(() => live && setCands([]));
    return () => { live = false; };
  }, [projectId]);

  if (error) return <PageFrame title="Hand the build to the data team"><p role="alert">{error}</p></PageFrame>;
  if (!project || !facts.ready) return <PageFrame title="Hand the build to the data team"><p className="ds-muted" role="status">Opening the project.</p></PageFrame>;

  const intent = project.artefacts.find((a) => a.kind === "intent");
  const head = nice(project.people.head_of_data) || "the head of data";
  const own: Candidate[] = [project.people.builder, project.people.head_of_data].filter((x): x is string => !!nice(x)).map((n) => ({ id: n, name: nice(n) }));
  const list: Candidate[] = [...(cands && cands.length ? cands : own), { id: me?.account_id ?? me?.display_name ?? "me", name: "Me", role: `${me?.display_name ?? "You"}: you would check Span's draft yourself` }];
  const chosen = list.find((c) => c.id === to);
  const first = chosen ? chosen.name.split(" ")[0] : "the builder";
  const views = stepViews({ project, plan: facts.plan, runs: facts.runs, boards: facts.boards, assigns: [] });
  const toggle = (s: StepId) => setSteps((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]));
  const note0 = sow?.signature?.note;
  const sources = (sow?.sources ?? []).map((s) => s.name).filter(Boolean);

  async function send() {
    if (!chosen || !steps.length) return;
    setBusy(true); setError("");
    try {
      await assignSteps(projectId, { steps, to: chosen.id, ...(note.trim() ? { note: note.trim() } : {}), ...(due ? { due } : {}), handover: true });
      go(overviewPath(projectId));
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
      setBusy(false);
    }
  }

  return (
    <PageFrame title="Hand the build to the data team" crumbs={<Link className="ds-link" to="/centre/build">All projects</Link>}
      subline={<span className="ds-eyebrow">{intent?.state === "signed" ? "INTENT SIGNED · CHOOSE WHO BUILDS IT" : "THE INTENT IS NOT SIGNED YET"}</span>}>
      <p style={{ margin: 0 }}>
        {intent?.state === "signed" && intent.signed_by ? <>Before this: {intent.signed_by} signed the intent{intent.signed_at ? ` on ${when(intent.signed_at)}` : ""}.</> : "Before this: the sponsor signs the intent."}
        <br />Next: choose the steps and who builds them, then hand over.
      </p>
      <ol className="b9-four" aria-label="The four steps" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        {STEPS.map((s, i) => (
          <li key={s.id} className="b9-stepcard"><span className="b9-ico"><StepIcon step={s.id} size={22} /></span>
            <span><span className="b9-eyebrow">{s.n} · {s.name.toUpperCase()}</span><br />{s.id === "intent" && intent?.signed_by ? `Signed by ${intent.signed_by}` : views[i]?.status}</span>
            <span className="b9-agent">{s.id === "intent" ? "DONE · NORTH" : `${views[i]?.mark === "done" ? "DONE" : views[i]?.mark === "todo" ? "NOT STARTED" : "IN PROGRESS"} · ${s.agent.toUpperCase()}`}</span></li>
        ))}
      </ol>
      <p className="ds-card" style={{ padding: 12, margin: 0 }}>
        Signed.{note0 ? <> {intent?.signed_by?.split(" ")[0] ?? "The sponsor"}'s note: &ldquo;{note0}&rdquo;</> : null}{" "}
        <Link className="ds-link" to={`/centre/project/${encodeURIComponent(projectId)}?artefact=intent`}>Read the signed intent</Link>
      </p>

      <section className="b9-box" aria-labelledby="h-steps">
        <h2 id="h-steps" style={{ marginTop: 0, fontSize: 18 }}>1. Which steps to hand over</h2>
        {ASSIGNABLE.map((s) => (
          <label key={s} style={{ display: "grid", gridTemplateColumns: "24px 1fr auto", gap: 10, alignItems: "start", padding: "8px 0", borderTop: "1px solid var(--ds-line)" }}>
            <input type="checkbox" checked={steps.includes(s)} onChange={() => toggle(s)} aria-label={stepName(s)} />
            <span><strong>{stepName(s) === "Dashboards" ? "Dashboards and delivery" : stepName(s)}</strong><br /><span className="ds-muted">{LINE(s, head)}</span></span>
            <span className="b9-eyebrow">{WHO[s]}</span>
          </label>
        ))}
      </section>

      <section className="b9-box" aria-labelledby="h-who">
        <h2 id="h-who" style={{ marginTop: 0, fontSize: 18 }}>2. Who builds it</h2>
        {cands === null ? <span className="ds-muted" role="status">Loading the people.</span> : null}
        <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
          {list.map((c) => (
            <label key={c.id} className="ds-card" style={{ padding: 12, display: "flex", gap: 10, alignItems: "center", borderColor: to === c.id ? "var(--ds-teal-bright)" : undefined }}>
              <input type="radio" name="b9-who" checked={to === c.id} onChange={() => setTo(c.id)} aria-label={c.name} />
              <span className="b9-person"><b>{initials(c.name)}</b><span>{c.name}{c.role || c.open_steps !== undefined ? <small>{[c.role, c.open_steps !== undefined ? `${c.open_steps} ${c.open_steps === 1 ? "step" : "steps"} open` : ""].filter(Boolean).join(" · ")}</small> : null}</span></span>
            </label>
          ))}
        </div>
      </section>

      <section className="b9-box" aria-labelledby="h-when">
        <h2 id="h-when" style={{ marginTop: 0, fontSize: 18 }}>3. When and how</h2>
        <div className="b9-split" style={{ marginTop: 0 }}>
          <div style={{ display: "grid", gap: 12 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Due<input className="ds-input" type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Note to {first}<textarea className="ds-input" rows={4} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should they check first?" /></label>
          </div>
          <div>
            <strong>{chosen ? `${first} receives` : "The builder receives"}</strong>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
              <li>The signed intent{sow?.process ? `, ${[sow.goal, ...sow.kpis, ...sow.sources].filter(Boolean).length} lines of it` : ""}</li>
              {sources.length ? <li>The sources named in it: {sources.join(", ")}</li> : null}
              <li>You as business owner; {head} approves the design</li>
            </ul>
          </div>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 12 }}>
          <Button variant="primary" disabled={busy || !chosen || !steps.length} onClick={() => void send()}>{chosen ? `Hand over to ${chosen.name}` : "Hand over"}</Button>
          <Link className="ds-btn" to={overviewPath(projectId)}>Save for later</Link>
          <span className="ds-muted">{chosen ? `It lands at the top of ${first}'s Action page. You will see each step finish here.` : "Choose who builds it."}</span>
        </div>
      </section>
      <p className="ds-muted" style={{ margin: 0 }}><Link className="ds-link" to={stepPath(projectId, "architecture")}>Open architecture</Link></p>
    </PageFrame>
  );
}
