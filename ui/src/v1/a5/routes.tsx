import type { V1Route } from "..";
import EvidenceList from "../e2/EvidenceList";
import AssignPage from "./AssignPage";
import ActionCentre, { ActionEvidence, Stay } from "./ActionCentre";

const ActionEvidenceList = () => <Stay><EvidenceList /></Stay>;

export const routes: V1Route[] = [
  { path: "action", element: <ActionCentre tab="today" /> },
  { path: "action/assign/:pid", element: <AssignPage /> },
  { path: "action/cases", element: <ActionCentre tab="cases" /> },
  { path: "action/cases/:caseId", element: <ActionCentre tab="cases" /> },
  { path: "action/reconciliations", element: <ActionCentre tab="recon" /> },
  // CR1: evidence is linked from Consume > Company reports now; the paths stay so old links open.
  { path: "action/evidence", element: <ActionEvidenceList /> },
  { path: "action/evidence/:documentId", element: <ActionEvidence /> },
];
