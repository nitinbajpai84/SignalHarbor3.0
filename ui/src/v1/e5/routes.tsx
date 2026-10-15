import type { V1Route } from "..";
import BriefPage from "./BriefPage";
import TodayPage from "./TodayPage";

export const routes: V1Route[] = [
  { path: "today", element: <TodayPage /> },
  { path: "brief/:reportVersionId", element: <BriefPage /> },
];
