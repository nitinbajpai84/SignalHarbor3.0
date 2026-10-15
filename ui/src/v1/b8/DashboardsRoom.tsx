import { useContext } from "react";
import { InStepper } from "../b9/context";
import { Link, useParams } from "react-router-dom";

import { PageFrame, Pill } from "../../design";
import { STATUS_WORDS, type Status } from "../b7/api";
import { useProjectTitle } from "../s1/useProjectTitle";
import RoomSwitcher from "./RoomSwitcher";
import { useFacts } from "./useFacts";

// BC1: Dashboards room. The project's dashboards with their state and who approved; the studio itself stays at .../studio.
const TONE: Record<Status, "draft" | "late" | "ok"> = { draft: "draft", submitted: "late", published: "ok" };

export default function DashboardsRoom() {
  const { projectId = "" } = useParams();
  const inStepper = useContext(InStepper); // the step rail already carries these links
  const title = useProjectTitle(projectId);
  const facts = useFacts(projectId);
  const studio = `/centre/build/p/${encodeURIComponent(projectId)}/studio`;
  return (
    <PageFrame title={`${title}: Dashboard studio`} subline="Dashboards are drafted here, sent for approval, and appear in Consume once published."
      crumbs={inStepper ? undefined : <><Link className="ds-link" to="/centre/build">All projects</Link> · <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}`}>Plan and Span</Link></>}>
      <RoomSwitcher pid={projectId} current="dashboards" facts={facts} />
      <p><Link className="ds-btn" to={studio}>Open the studio</Link> <Link className="ds-btn" to={`/centre/build/p/${encodeURIComponent(projectId)}/delivery`}>Delivery</Link></p>
      {!facts.ready ? <p className="ds-muted" role="status">Opening the dashboards.</p> : facts.boards.length === 0 ? <p>There is no dashboard for this project yet. Open the studio to start one.</p> : (
        <ul aria-label="Dashboards in this project" style={{ listStyle: "none", padding: 0 }}>
          {facts.boards.map((d) => (
            <li key={d.id} className="b8-board">
              <span>
                <Link className="ds-link" to={`${studio}?d=${encodeURIComponent(d.id)}`}><strong>{d.title}</strong></Link>{" "}
                <Pill tone={TONE[d.status]}>{STATUS_WORDS[d.status]}</Pill>{d.waiting_for_you ? <> <Pill tone="open">Needs you</Pill></> : null}
                <br /><span className="ds-muted">Version {d.version} · {d.tiles} widgets · made by {d.made_by || "someone no longer in the company"}{d.status === "published" ? (d.approved_by ? ` · approved by ${d.approved_by}` : " · published before approvals were needed") : d.status === "submitted" ? " · waiting for approval" : ""}</span>
              </span>
              <Link className="ds-btn" to={`${studio}?d=${encodeURIComponent(d.id)}`}>Open</Link>
            </li>))}
        </ul>)}
    </PageFrame>
  );
}
