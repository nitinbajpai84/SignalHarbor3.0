import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { barFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import { InStep } from "../b9/StepPages";
import ArchitectureStep from "../b10/ArchitectureStep";
import ArchitectureRoom from "./ArchitectureRoom";
import DashboardsRoom from "./DashboardsRoom";
import PipelinesRoom from "./PipelinesRoom";

// BC1: the three Build rooms take Build's gate in the bar. W3 walk: the sponsor approves the dashboard here (D3), so a role that sees Build in the
// bar opens the rooms; what each may do is the server's permission lines. Never refuse before the roles are known.
function Gate({ children }: { children: ReactNode }) {
  const { user } = useSession();
  if (!user) return <p className="ds-muted" role="status">Loading.</p>;
  const roles = user.roles ?? [];
  return barFor(roles).includes("build") ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [
  { path: "build/p/:projectId/pipelines", element: <Gate><InStep current="pipelines"><PipelinesRoom /></InStep></Gate> },
  { path: "build/p/:projectId/dashboards", element: <Gate><InStep current="dashboards"><DashboardsRoom /></InStep></Gate> },
  { path: "build/p/:projectId/architecture", element: <Gate><InStep current="architecture"><ArchitectureStep /></InStep></Gate> },
  { path: "build/p/:projectId/architecture/model", element: <Gate><InStep current="architecture"><ArchitectureRoom /></InStep></Gate> }, // V6: the old model view stays
];
