import type { V1Route } from "..";
import EvidenceList from "./EvidenceList";
import EvidencePage from "./EvidencePage";

export const routes: V1Route[] = [
  { path: "evidence", element: <EvidenceList /> },
  { path: "evidence/:documentId", element: <EvidencePage /> },
];
