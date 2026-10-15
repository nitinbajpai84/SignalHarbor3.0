import type { V1Route } from "..";
import SettingsPage from "./SettingsPage";
import { routes as jobsRoutes } from "./jobs/routes";

export const routes: V1Route[] = [
  { path: "settings", element: <SettingsPage /> },
  { path: "settings/:section", element: <SettingsPage /> },
  ...jobsRoutes,
];
