import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import * as b6 from "../b6/api";
import * as b7 from "../b7/api";
import { getProject } from "../p1/api";
import { InStepper } from "./context";
import { listAssignments } from "./api";
import { stepStatuses } from "./overview";
import { Rail } from "./StepStrip";
import { overviewPath, type StepId } from "./steps";
import "./b9.css";

/** V5: one page per step under one rail. The step's own page sits below; nothing it had is taken away. */
export default function StepperShell({ pid, current, children }: { pid: string; current: StepId; children: ReactNode }) {
  const p = encodeURIComponent(pid);
  const [statuses, setStatuses] = useState<string[] | undefined>();
  useEffect(() => {  // V6 (D4): each step says where it stands; a call that fails leaves its part out and the rail reads as it did
    if (!pid) return;
    let live = true;
    Promise.all([getProject(pid), b6.getPlan(pid).catch(() => null), b6.getRuns(pid).then((r) => r.runs).catch(() => []), b7.listStudio(pid).then((r) => r.dashboards).catch(() => []),
      listAssignments(pid).then((r) => r.assignments ?? []).catch(() => [])])  // V6 review: a handed-over step reads "Assigned to", not "Needs a builder"
      .then(([project, plan, runs, boards, assigns]) => { if (live) setStatuses(stepStatuses({ project, plan, runs, boards, assigns })); })
      .catch(() => undefined);
    return () => { live = false; };
  }, [pid, current]);
  return (
    <InStepper.Provider value={true}>
      <div className="b9-shell" data-step={current}>
        <p style={{ margin: 0 }}>
          <Link className="ds-link" to="/centre/build">All projects</Link>
          {pid ? <> · <Link className="ds-link" to={overviewPath(pid)}>Project overview</Link> · <Link className="ds-link" to={`/centre/build/p/${p}`}>Plan and Span</Link> · <Link className="ds-link" to={`/centre/project/${p}`}>Project page: documents, run book, deviations</Link></> : null}
        </p>
        <Rail pid={pid} current={current} statuses={statuses} />
        {children}
      </div>
    </InStepper.Provider>
  );
}
