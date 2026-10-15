import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { centresFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import HandoverPage from "./HandoverPage";
import ProjectOverview from "./ProjectOverview";
import { IntentByProject, IntentStep, NewProject } from "./StepPages";

// V5W-2: the stepper's own pages. People who start work (Intent centre roles) and people who build (Build) both open them.
function Gate({ children }: { children: ReactNode }) {
  const roles = useSession().user?.roles ?? [];
  const mine = centresFor(roles);
  return mine.has("build") || mine.has("intent") ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [
  { path: "build/new", element: <Gate><NewProject /></Gate> },
  { path: "build/intent/:iid", element: <Gate><IntentStep /></Gate> },
  { path: "build/p/:projectId/intent", element: <Gate><IntentByProject /></Gate> },
  { path: "build/p/:projectId/overview", element: <Gate><ProjectOverview /></Gate> },
  { path: "build/p/:projectId/handover", element: <Gate><HandoverPage /></Gate> },
];
