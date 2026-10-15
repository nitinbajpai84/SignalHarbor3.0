import { Navigate, useParams } from "react-router-dom";

import type { V1Route } from "..";
import NewIntent from "./NewIntent";

// The thread page is now I6b's one screen; the old link redirects there.
function ToConversation() {
  const { iid = "" } = useParams();
  return <Navigate to={`/centre/intent/${encodeURIComponent(iid)}`} replace />;
}

export const routes: V1Route[] = [
  { path: "intent/new", element: <NewIntent /> },
  { path: "intent/:iid/thread", element: <ToConversation /> },
];
