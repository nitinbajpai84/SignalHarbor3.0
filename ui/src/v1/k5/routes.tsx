import type { V1Route } from "..";
import ActionCentre from "../a5/ActionCentre";
import ManagerPage, { ManagerList } from "./ManagerPage";

// K3: Action > Managers (the tab is added in a5/ActionCentre.tsx), and Consume > Managers (list and one manager).
export const routes: V1Route[] = [
  { path: "action/managers", element: <ActionCentre tab="managers" /> },
  { path: "consume/managers", element: <ManagerList /> },
  { path: "consume/managers/:managerId", element: <ManagerPage /> },
];
