import { Navigate, Route, Routes } from "react-router-dom";

import DeskPage from "./desk/DeskPage";
import WelcomePage from "./setup/WelcomePage";
import StartPage from "./setup/StartPage";
import SetupPage from "./setup/SetupPage";
import ThreadPage from "./thread/ThreadPage";
import FilesPage from "./files/FilesPage";
import BoardPage from "./board/BoardPage";
import AnswerPage from "./board/AnswerPage";
import NotePage from "./board/NotePage";
import CasePage from "./case/CasePage";
import OntologyPage from "./trust/OntologyPage";
import ModelPage from "./trust/ModelPage";
import LanguagePage from "./trust/LanguagePage";
import PeoplePage from "./trust/PeoplePage";
import ProofPage from "./trust/ProofPage";
import WorkbenchPage from "./trust/WorkbenchPage";
import ConnectionsPage from "./trust/ConnectionsPage";
import ActionPage from "./action/ActionPage";
import SkillReviewPage from "./action/SkillReviewPage";
import BuildPage from "./build/BuildPage";
import ConsumePage from "./consume/ConsumePage";
import KnowledgePage from "./knowledge/KnowledgePage";
import SkillsPage from "./knowledge/SkillsPage";

/** Mounted by App.tsx at /v3/* inside the signed-in Gate. Paths are relative to /v3. */
export default function V3Routes() {
  return (
    <Routes>
      <Route index element={<Navigate to="desk" replace />} />
      <Route path="desk" element={<DeskPage />} />
      <Route path="welcome" element={<WelcomePage />} />
      <Route path="start" element={<StartPage />} />
      <Route path="setup" element={<SetupPage />} />
      <Route path="thread/:id" element={<ThreadPage />} />
      <Route path="files" element={<FilesPage />} />
      <Route path="board" element={<BoardPage />} />
      <Route path="ask" element={<AnswerPage />} />
      <Route path="note" element={<NotePage />} />
      <Route path="case/:id" element={<CasePage />} />
      <Route path="trust/ontology" element={<OntologyPage />} />
      <Route path="trust/model" element={<ModelPage />} />
      <Route path="trust/language" element={<LanguagePage />} />
      <Route path="trust/people" element={<PeoplePage />} />
      <Route path="trust/proof" element={<ProofPage />} />
      <Route path="trust/workbench" element={<WorkbenchPage />} />
      <Route path="trust/connections" element={<ConnectionsPage />} />
      <Route path="action" element={<ActionPage />} />
      <Route path="skill/:id" element={<SkillReviewPage />} />
      <Route path="build" element={<BuildPage />} />
      <Route path="build/:id" element={<BuildPage />} />
      <Route path="consume" element={<ConsumePage />} />
      <Route path="knowledge" element={<KnowledgePage />} />
      <Route path="knowledge/skills" element={<SkillsPage />} />
      <Route path="*" element={<Navigate to="desk" replace />} />
    </Routes>
  );
}
