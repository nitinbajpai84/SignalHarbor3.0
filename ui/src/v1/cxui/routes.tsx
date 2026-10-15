import type { V1Route } from "..";
import DashboardView from "./DashboardView";
import ProjectList from "./ProjectList";
import ProjectPage from "./ProjectPage";

export const routes: V1Route[] = [
  { path: "consume", element: <ProjectList /> },
  { path: "consume/p/:projectId", element: <ProjectPage /> },
  { path: "consume/d/:dashboardId", element: <DashboardView /> },
];
