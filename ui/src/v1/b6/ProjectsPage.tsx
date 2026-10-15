import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame, Pill } from "../../design";
import { canOps } from "../../shell/roles";
import { useSession } from "../../useSession";
import ExplainerVideo from "../b9/ExplainerVideo";
import StepIcon from "../b9/StepIcons";
import { MiniStrip } from "../b9/StepStrip";
import { filterRows, viewRow, waitingForMe, type Filter, type RowPlus } from "../b9/progress";
import { overviewPath, STEPS, stepPath } from "../b9/steps";
import "../b9/b9.css";
import BuildNav from "./BuildNav";
import { Rooms } from "./Steps";
import TalkBox from "../talk/TalkBox";
import { listProjects, STATE_NAMES } from "./api";
import { initials } from "../b9/api";

// V5 A1/A2: /centre/build. Running projects as cards (stage on the four steps, owner, what is waiting), filters, one New project button.
// Kept from B1: the Span talk box, the links to Ops, intake and Projects today, the finder, and every older room per project.
const CARD_NAME: Record<string, string> = { dashboards: "Dashboards and delivery" };
const todayWords = () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }).toUpperCase();

export default function ProjectsPage() {
  const today = todayWords();
  const user = useSession().user;
  const me = user?.display_name ?? "";
  const canApprove = (user?.roles ?? []).some((r) => r === "head_of_data" || r === "company_admin"); // V6: the head of data approves plans
  const [rows, setRows] = useState<RowPlus[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  useEffect(() => {
    listProjects().then((r) => setRows(r.projects)).catch((e) => { setRows([]); setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."); });
  }, []);
  const all = rows ?? [];
  const n = { all: all.length, waiting: filterRows(all, "waiting", me, canApprove).length, mine: filterRows(all, "mine", me, canApprove).length, live: filterRows(all, "live", me, canApprove).length };
  const shown = filterRows(all, filter, me, canApprove).filter((r) => `${r.id} ${r.title}`.toLowerCase().includes(q.trim().toLowerCase()));
  const chips: [Filter, string][] = [["all", "All"], ["waiting", "Waiting for me"], ["mine", "Mine"], ["live", "Live"]];
  return (
    <PageFrame title="Build something new, one step at a time" crumbs={<span className="ds-eyebrow">BUILD · {today}</span>}
      subline="Every new report, check or data product follows the same four steps. You say what you need; agents draft; a person checks and approves each step."
      actions={<Link className="ds-btn ds-btn--primary" to="/centre/build/new">New project</Link>}>
      <BuildNav current="projects" />
      <ExplainerVideo />
      <ol className="b9-four" aria-label="The four steps">
        {STEPS.map((s, i) => (
          <Fragment key={s.id}>
            <li className="b9-stepcard"><span className="b9-ico"><StepIcon step={s.id} size={22} /></span>
              <span><span className="b9-eyebrow">STEP {s.n}</span><h3>{CARD_NAME[s.id] ?? s.name}</h3></span>
              <p>{s.line}</p><span className="b9-agent">{s.agent}</span></li>
            {i < STEPS.length - 1 ? <li className="b9-arrow" aria-hidden="true">→</li> : null}
          </Fragment>
        ))}
      </ol>
      <div className="b9-running">
        <div>
          <h2 className="ds-serif">Running projects</h2>
          <p className="ds-muted" style={{ margin: 0 }}>
            {rows === null ? "Loading the projects." : n.all === 0 ? "Nothing is running yet." : `${n.all} ${n.all === 1 ? "project is" : "projects are"} moving. ${n.waiting ? `${n.waiting} ${n.waiting === 1 ? "needs" : "need"} you today.` : "Nothing is waiting for you."}`}
          </p>
        </div>
        <div className="b9-filters" role="group" aria-label="Filter the projects">
          {chips.map(([id, label]) => <button key={id} type="button" aria-pressed={filter === id} data-tone={id === "waiting" ? "amber" : undefined} onClick={() => setFilter(id)}>{label} · {n[id]}</button>)}
          <label>Find a project <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Project title" /></label>
        </div>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {rows === null ? <p className="ds-muted" role="status">Loading the projects.</p> : shown.length === 0 && !error ? (
        <p className="ds-muted">{filter === "all" && !q ? <>No projects yet. <Link className="ds-link" to="/centre/build/new">Start a new intent</Link>.</> : "No project matches. Choose All to see every project."}</p>
      ) : null}
      <div className="b9-cards">
        {shown.map((r) => {
          const v = viewRow(r);
          const wait = waitingForMe(r, canApprove);
          return (
            <article key={r.id} className="b9-card" data-waiting={wait}>
              <header>
                <span className="b9-eyebrow" data-tone={wait ? "amber" : undefined}>{wait ? `WAITING FOR YOU · ${STEPS.find((s) => s.id === v.current)?.name.toUpperCase()}` : v.tag}</span>
                <span className="ds-muted">Step {STEPS.findIndex((s) => s.id === v.current) + 1} of 4</span>
              </header>
              <h2><Link className="ds-link" to={overviewPath(r.id)}>{r.title}</Link></h2>
              <MiniStrip marks={v.marks} />
              <p style={{ margin: 0 }}>{v.line}</p>
              <div className="b9-foot">
                <span className="b9-people">
                  <span className="b9-person"><b>{initials(r.owner ?? "?")}</b><span><small>Owner</small>{r.owner ?? "Not set"}</span></span>
                  <span className="b9-person"><b>{r.builder ? initials(r.builder) : "?"}</b><span><small>Building now</small>{r.builder ?? "Not chosen yet"}</span></span>
                </span>
                <span>{r.plan_state ? <Pill tone={r.plan_state === "live" || r.plan_state === "approved" ? "ok" : r.plan_state === "rejected" ? "failed" : "draft"}>{STATE_NAMES[r.plan_state]}</Pill> : <span className="ds-muted">No plan yet</span>}</span>
                <Link className="ds-btn" to={stepPath(r.id, v.current)} aria-label="Go to step">Go to step →</Link>
              </div>
              <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>
                <Link className="ds-link" to={`/centre/project/${encodeURIComponent(r.id)}`}>Project page</Link> · <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(r.id)}`}>Plan and Span</Link> · <Link className="ds-link" to={stepPath(r.id, "pipelines")}>Pipelines</Link> · <Link className="ds-link" to={stepPath(r.id, "dashboards")}>Dashboards</Link> · <Link className="ds-link" to={stepPath(r.id, "architecture")}>Architecture</Link>
                {r.intent_id ? <><br /><Rooms iid={r.intent_id} /></> : null}
              </p>
            </article>
          );
        })}
      </div>
      <TalkBox agent="Span" path="/api/v1/build/chat" hint="For example: what is the data model?" />
      <p style={{ marginTop: "var(--ds-s4)" }}><Link className="ds-link" to="/centre/action">What needs me today</Link>{canOps(user?.roles) ? <> · <Link className="ds-link" to="/centre/build/ops">Ops: loads and alerts</Link> · <Link className="ds-link" to="/centre/data/intake">Data intake</Link></> : null}</p>
    </PageFrame>
  );
}
