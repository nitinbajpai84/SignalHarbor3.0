import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { centresFor, landingFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import CompletePage from "./CompletePage";
import DeliveryPage from "./DeliveryPage";
import SettingsPage from "./SettingsPage";

// V5 D1: delivery is in Build. Roles that only have Intent (sponsor, approver) may open it too, because they approve channels; the server decides who may do what.
function Gate({ children }: { children: ReactNode }) {
  const roles = useSession().user?.roles ?? [];
  const mine = centresFor(roles);
  return mine.has("build") || mine.has("intent") ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

export const routes: V1Route[] = [
  { path: "build/p/:projectId/delivery", element: <Gate><DeliveryPage /></Gate> },
  { path: "build/p/:projectId/complete", element: <Gate><CompletePage /></Gate> },
  { path: "build/delivery-settings", element: <Gate><SettingsPage /></Gate> },
];
