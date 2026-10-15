import { Navigate, useLocation } from "react-router-dom";

import type { V1Route } from "..";
import AttributionTab from "./AttributionTab";

// K11: Consume > What if (it was "Attribution"). Open /centre/consume/what-if?portfolio=<code>&code=<benchmark>&month=YYYY-MM.
/** The old address (and the links other pages made to it) keeps working, query and all. */
function OldAddress() {
  return <Navigate to={`/centre/consume/what-if${useLocation().search}`} replace />;
}
export const routes: V1Route[] = [
  { path: "consume/what-if", element: <AttributionTab /> },
  { path: "consume/analytics", element: <OldAddress /> },
];
