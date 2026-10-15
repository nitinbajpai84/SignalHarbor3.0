import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { centresFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import BuildPage from "./BuildPage";
import ProjectsPage from "./ProjectsPage";

// The same role gate P3 used for Build: people who do not see the Build centre go back to their own start page.
function Gate({ children, also }: { children: ReactNode; also?: "intent" }) {
  const roles = useSession().user?.roles ?? [];
  const mine = centresFor(roles);
  return mine.has("build") || (also && mine.has(also)) ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [
  { path: "build", element: <Gate also="intent"><ProjectsPage /></Gate> },
  { path: "build/p/:projectId", element: <Gate><BuildPage /></Gate> },
];
