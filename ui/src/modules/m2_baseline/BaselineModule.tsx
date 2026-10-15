import { Route, Routes, useLocation } from "react-router-dom";

import BaselineDock from "./agents/BaselineDock"; // M2-AGENTS
import PreReadScreen from "./agents/PreReadScreen"; // M2-AGENTS
import BaselineHome from "./BaselineHome";
import CatalogueScreen from "./catalogue/CatalogueScreen"; // M2-P04
import GovernanceScreen from "./governance/GovernanceScreen"; // M2-E3
import OpenQuestionsScreen from "./technical/OpenQuestionsScreen"; // M2-E1
import ProcessMapScreen from "./process_map/ProcessMapScreen"; // M2-P03
import GlossaryScreen from "./glossary/GlossaryScreen"; // M2-E2
import MeetingScreen from "./requests/MeetingScreen"; // M2-P02
import RequestsScreen from "./requests/RequestsScreen"; // M2-P02
import SignoffScreen from "./signoff/SignoffScreen"; // M2-P05
import type { NiraStep } from "./api";
import WorkListScreen from "./worklist/WorkListScreen"; // M2-P01

const SCREEN = /\/(baselines|preread|requests|process-map|catalogue|glossary|governance|questions|signoff)\/([0-9a-f]{32})/;

/** Lens's block (with Nira's small strip inside it) on every screen of one baseline: the same dock on each, so the person is
 * never without the agents. The screens that are not a baseline's (the module's home) have none. */
function Agents() {
  const m = SCREEN.exec(useLocation().pathname);
  const id = m?.[2] ?? "";
  return m ? <BaselineDock key={id} baselineId={id} step={(m[1] === "preread" ? "baselines" : m[1] === "glossary" || m[1] === "governance" ? "catalogue" : m[1] === "questions" ? "baselines" : m[1]) as NiraStep} /> : null; // pre-read is before the work list (step 1); glossary and governance belong with the catalogue (step 4)
}

/** Module 2 inside the shell. Each package adds its screens here, one route each, under its own folder:
 * worklist/ (M2-P01), requests/ (M2-P02), process_map/ (M2-P03), catalogue/ (M2-P04), signoff/ (M2-P05), agents/ (M2-AGENTS). */
export default function BaselineModule() {
  return (
    <>
      <Routes>
        <Route index element={<BaselineHome />} />
        {/* M2-AGENTS: before the work list, "Give Lens what you already have" */}
        <Route path="preread/:baselineId" element={<PreReadScreen />} />
        {/* M2-P01 */}
        <Route path="baselines/:baselineId" element={<WorkListScreen />} />
        {/* M2-P02 */}
        <Route path="requests/:baselineId" element={<RequestsScreen />} />
        <Route path="requests/:baselineId/meeting" element={<MeetingScreen />} />
        {/* M2-P03 */}
        <Route path="process-map/:baselineId" element={<ProcessMapScreen />} />
        {/* M2-P04 */}
        <Route path="catalogue/:baselineId" element={<CatalogueScreen />} />
        {/* M2-E2 */}
        <Route path="glossary/:baselineId" element={<GlossaryScreen />} />
        {/* M2-E3 */}
        <Route path="governance/:baselineId" element={<GovernanceScreen />} />
        {/* M2-E1 */}
        <Route path="questions/:baselineId" element={<OpenQuestionsScreen />} />
        {/* M2-P05 */}
        <Route path="signoff/:baselineId" element={<SignoffScreen />} />
      </Routes>
      <Agents />
    </>
  );
}
