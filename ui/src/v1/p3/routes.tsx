import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { centresFor, landingFor, type Centre } from "../../shell/roles";
import { useSession } from "../../useSession";
import type { V1Route } from "..";
import ConsumeEntry from "./ConsumeEntry";
import IntentWelcome from "./IntentWelcome";

// v1 routes mount outside App.tsx's role gates. Build keeps App.tsx's gate (its RoleGate, as an element); intent and consume stay
// open as i6's and c1's routes were (the server decides; participants read the figures as the Consumer seat).
export function Gate({ centre, children }: { centre: Centre; children: ReactNode }) {
  const roles = useSession().user?.roles ?? [];
  return centresFor(roles).has(centre) ? <>{children}</> : <Navigate to={landingFor(roles)} replace state={{ refused: true }} />;
}

// The orchestrator removes the same paths from i6 ("intent"), c1 ("consume") and App.tsx's build redirect.
export const routes: V1Route[] = [
  { path: "intent", element: <IntentWelcome /> },
  { path: "consume/figures", element: <ConsumeEntry /> },
];
