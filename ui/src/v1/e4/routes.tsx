import type { V1Route } from "..";
import CasePage from "./CasePage";
import CasesPage from "./CasesPage";

export const routes: V1Route[] = [
  { path: "desk", element: <CasesPage /> },
  { path: "desk/:caseId", element: <CasePage /> },
];
