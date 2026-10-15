import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { barFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import { InStep } from "../b9/StepPages";
import ArchitectureStep from "./ArchitectureStep";

// V6: the Architecture step (design pack). Same gate as the other Build rooms: whoever sees Build in the bar opens it; what each may do is the
// server's permission lines. Mounted at .../architecture/pack; integration points the step's own tab (.../architecture) at ArchitectureStep.
function Gate({ children }: { children: ReactNode }) {
  const { user } = useSession();
  if (!user) return <p className="ds-muted" role="status">Loading.</p>;
  const roles = user.roles ?? [];
  return barFor(roles).includes("build") ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [
  { path: "build/p/:projectId/architecture/pack", element: <Gate><InStep current="architecture"><ArchitectureStep /></InStep></Gate> },
];
