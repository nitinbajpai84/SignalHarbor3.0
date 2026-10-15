import { Route, Routes } from "react-router-dom";

import ConnectArea from "./ConnectArea";
import ConnectHome from "./ConnectHome";
import MapScreen from "./map/MapScreen";
import TrialScreen from "./trial/TrialScreen";
import PlanScreen from "./plan/PlanScreen";
import IntakeScreen from "./intake/IntakeScreen"; // M3-P02

/** Module 3 inside the shell. One route per area; each package replaces its placeholder with its own screen under its own folder:
 * map/ (M3-P01), intake/ (M3-P02), trial/ (M3-P03), plan/ (M3-P04). */
export default function ConnectModule() {
  return (
    <Routes>
      <Route index element={<ConnectHome />} />
      {/* M3-P01 */}
      <Route path="map/:assessmentId" element={<MapScreen />} />
      {/* M3-P02 */}
      <Route path="intake/:assessmentId" element={<IntakeScreen />} />
      {/* M3-P03 */}
      <Route path="trial/:assessmentId" element={<TrialScreen />} />
      {/* M3-P04 */}
      <Route path="plan/:assessmentId" element={<PlanScreen />} />
    </Routes>
  );
}
