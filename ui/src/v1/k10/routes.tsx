import { Navigate } from "react-router-dom";

import type { V1Route } from "..";
import ConsumeRoom from "./ConsumeRoom";

// The Consume reading room: `consume` itself (Today) is mounted by cxui/routes.tsx through ProjectList, which renders the same room; What if is k11/routes.tsx.
// The tabs the redesign folded away keep their old addresses as redirects, so a bookmark or a link from another page still lands somewhere right.
const to = (path: string) => <Navigate to={path} replace />;
export const routes: V1Route[] = [
  { path: "consume/health", element: <ConsumeRoom tab="health" /> },
  { path: "consume/markets", element: <ConsumeRoom tab="markets" /> },
  { path: "consume/reports", element: <ConsumeRoom tab="reports" /> },
  { path: "consume/pnl", element: to("/centre/consume/health") },
  { path: "consume/league", element: to("/centre/consume/health") },
  { path: "consume/signals", element: to("/centre/consume/markets") },
  { path: "consume/shared", element: to("/centre/consume/reports") },
  { path: "consume/dashboards", element: to("/centre/consume/reports") },
  { path: "consume/email", element: to("/centre/operations#deliveries") },
  { path: "consume/slack", element: to("/centre/operations#deliveries") },
];
