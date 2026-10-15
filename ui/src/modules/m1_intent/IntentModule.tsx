import { Route, Routes, useParams } from "react-router-dom";

import ModuleHome from "./ModuleHome";
import PrepareScreen from "./PrepareScreen";
import BriefingScreen from "./briefing/BriefingScreen"; // M1-P03
import PrivateRoomScreen from "./private_room/PrivateRoomScreen"; // M1-P04
import SessionPage from "./room/SessionPage"; // M1-P02
import CharterScreen from "./charter/CharterScreen"; // M1-P09
import LaterStages from "./board/LaterStages"; // M1-P07: the board, then back in the room
import StageLinks from "./board/StageLinks"; // M1-P07
import SummaryScreen from "./summary/SummaryScreen";
import DefineScreen from "./define/DefineScreen"; // IC-3s
import WallScreen from "./wall/WallScreen"; // IC-2c

/** M1-P07: the session page, with the way on to the board and the room once the private rooms are open. */
function SessionPageWithLinks() {
  const { sessionId = "" } = useParams();
  return (
    <>
      <SessionPage />
      <StageLinks sessionId={sessionId} />
    </>
  );
}

/** Module 1 inside the shell. Later packages add their screens here, one route each. */
export default function IntentModule() {
  return (
    <Routes>
      <Route index element={<ModuleHome />} />
      <Route path="prepare" element={<PrepareScreen />} />
      {/* M1-P02: was PrepareScreen, which SessionPage still shows */}
      <Route path="sessions/:sessionId" element={<SessionPageWithLinks />} />
      <Route path="sessions/:sessionId/briefing" element={<BriefingScreen />} /> {/* M1-P03 */}
      <Route path="sessions/:sessionId/room" element={<PrivateRoomScreen />} /> {/* M1-P04 */}
      <Route path="sessions/:sessionId/board" element={<LaterStages />} /> {/* M1-P07 */}
      <Route path="sessions/:sessionId/together" element={<LaterStages />} /> {/* M1-P07: follows the session's own stage */}
      <Route path="define/:sessionId" element={<DefineScreen />} /> {/* IC-3s */}
      <Route path="sessions/:sessionId/charter" element={<CharterScreen />} /> {/* M1-P09 */}
      <Route path="wall/:sessionId" element={<WallScreen />} /> {/* IC-2c */}
      <Route path="sessions/:sessionId/summary" element={<SummaryScreen />} /> {/* the summary page */}
    </Routes>
  );
}
