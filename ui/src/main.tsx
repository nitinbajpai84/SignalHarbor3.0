import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./styles/legacy/sh.css"; // first, so every other stylesheet in the bundle comes after it
// The screens files module 1 uses, in the earlier index.html's own order (docs/design/legacy-css.md step 2):
import "./styles/legacy/screens-e3.css"; // n-input, n-select, agent chip, roster card
import "./styles/legacy/screens-e1.css"; // interview transcript, charter document, signature block
import "./styles/legacy/screens-peek.css"; // Intent Centre header, intent switcher list
import "./styles/legacy/screens-flow.css"; // Nira's companion line, room layout (participants, progress, closing card)
import "./styles/legacy/screens-team-rooms.css"; // thread, compose row, member chips
import "./styles/legacy/screens-v3-rail.css"; // rail stage badges
import "./styles/legacy/screens-v3-intent.css"; // sticky notes
import "./styles/legacy/screens-v3-baseline.css"; // "you decide" suggestion block, step card
import "./styles/legacy/screens-e2.css"; // M2-P03: the as-is swimlane (Process & Lever Map), step cards, legend
import "./styles/shell.css";
import App from "./App";
import ApproverPage from "./pages/ApproverPage"; // M1-P09
import { ThemeProvider } from "./theme";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}
createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* M1-P09: the approver's link needs no sign-in and no session calls, so it sits outside App's session provider */}
        <Route path="/approve/:token" element={<ThemeProvider><ApproverPage /></ThemeProvider>} />
        <Route path="*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
