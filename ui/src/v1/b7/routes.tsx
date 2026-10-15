import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { centresFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import { InStep } from "../b9/StepPages";
import StudioPage from "./StudioPage";

// DS1: the dashboard studio lives in Build. W3 walk: the sponsor approves the dashboard here (D3), so it takes the same gate as the project
// pages (Build or Intent, as b9 and d1); the server's permission lines decide what each may do. Never refuse before the roles are known.
function Gate({ children }: { children: ReactNode }) {
  const { user } = useSession();
  if (!user) return <p className="ds-muted" role="status">Loading.</p>;
  const roles = user.roles ?? [], mine = centresFor(roles);
  return mine.has("build") || mine.has("intent") ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [{ path: "build/p/:projectId/studio", element: <Gate><InStep current="dashboards"><StudioPage /></InStep></Gate> }];
