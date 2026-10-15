import type { V1Route } from "..";
import BriefPage from "../e5/BriefPage";
import OfficePage from "./OfficePage";

// K2: the Office view, and the CIO Brief under Consume so it is reachable from the new shell (the old /centre/brief path still works).
export const routes: V1Route[] = [
  { path: "consume/office", element: <OfficePage /> },
  { path: "consume/brief/:reportVersionId", element: <BriefPage /> },
];
