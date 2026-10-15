import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";

import { PageFrame } from "../../design";
import ConversationPage from "../i6/ConversationPage";
import IntentWelcome from "../p3/IntentWelcome";
import { getProject, projectOf } from "../p1/api";
import StepperShell from "./StepperShell";
import type { StepId } from "./steps";

// V5: the pages that sit in the stepper. Rooms 2 to 4 are the b8 rooms, wrapped by b8/routes.tsx.
/** Wraps a room that reads :projectId from the route. */
export function InStep({ current, children }: { current: StepId; children: ReactNode }) {
  const { projectId = "" } = useParams();
  return <StepperShell pid={projectId} current={current}>{children}</StepperShell>;
}

/** /centre/build/new: the start box (what North will ask, templates, a first line). Moved from /centre/intent. */
export function NewProject() {
  return <StepperShell pid="" current="intent"><IntentWelcome /></StepperShell>;
}

/** /centre/build/intent/:iid: step 1, the conversation with North and the intent of work beside it (the old Intent centre page, unchanged). */
export function IntentStep() {
  const { iid = "" } = useParams();
  const [pid, setPid] = useState("");
  useEffect(() => {
    let live = true;
    projectOf(iid).then((p) => live && setPid(p.id)).catch(() => live && setPid("")); // a talking intent may have no project yet: the rail then shows without links
    return () => { live = false; };
  }, [iid]);
  return <StepperShell pid={pid} current="intent"><ConversationPage /></StepperShell>;
}

/** /centre/build/p/:projectId/intent: finds the project's intent and opens step 1 on it. */
export function IntentByProject() {
  const { projectId = "" } = useParams();
  const [state, setState] = useState<{ iid: string } | "none" | null>(null);
  useEffect(() => {
    let live = true;
    getProject(projectId).then((p) => live && setState(p.intent_id ? { iid: p.intent_id } : "none")).catch(() => live && setState("none"));
    return () => { live = false; };
  }, [projectId]);
  if (state === null) return <PageFrame title="Intent"><p className="ds-muted" role="status">Opening the intent.</p></PageFrame>;
  if (state === "none") return <PageFrame title="Intent"><p role="alert">This project has no intent to show yet.</p></PageFrame>;
  return <Navigate to={`/centre/build/intent/${encodeURIComponent(state.iid)}`} replace />;
}
