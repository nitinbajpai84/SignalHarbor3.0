import type { ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import ScreenState from "./components/ScreenState";
import { v1Routes } from "./v1";
import ContextPage from "./pages/ContextPage"; // M1-CTX
import BringPage from "./pages/BringPage"; // LI-PROFILE
import InterviewPage from "./pages/InterviewPage"; // LI-INTERVIEW
import ControlPage from "./pages/ControlPage"; // IC-5b
import OutcomesPage from "./pages/OutcomesPage";
import BuildEnvironment from "./pages/BuildEnvironment";
import GraphPage from "./pages/GraphPage";
import Gallery from "./design/Gallery";
import PulsePage from "./pages/PulsePage";
import BlueprintPage from "./pages/BlueprintPage";
import PipelinesPage from "./pages/PipelinesPage";
import ProvePage from "./pages/ProvePage";
import OpsPage from "./pages/OpsPage";
import ArchitecturePage from "./pages/build/ArchitecturePage"; // 59
import ChangeNotePage from "./pages/build/ChangeNotePage"; // 59
import ConsumeCentre from "./pages/ConsumeCentre";
import FeedsPage from "./pages/FeedsPage";
import MeasurePage from "./pages/MeasurePage";
import LensPage from "./pages/LensPage";
import MarketPage from "./pages/MarketPage";
import WhatIfPage from "./pages/WhatIfPage";
import NodePage from "./pages/NodePage";
import RegisterPage from "./pages/RegisterPage";
import MemoryPage from "./pages/MemoryPage";
import BaselinePage from "./pages/BaselinePage";
import CharterView from "./pages/CharterView";
import BringCentre from "./pages/BringCentre";
import CentreShell from "./shell/CentreShell";
import { centresFor, landingFor, type Centre } from "./shell/roles";
import WallScreen from "./modules/m1_intent/wall/WallScreen";
import DefineScreen from "./modules/m1_intent/define/DefineScreen";
import TrialScreen from "./modules/m3_connect/trial/TrialScreen";
import TruthScreen from "./modules/m3_connect/truth/TruthScreen";
import RequestScreen from "./modules/m3_connect/request/RequestScreen";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import ModulePage from "./pages/ModulePage";
import NotFoundPage from "./pages/NotFoundPage";
import JoinPage from "./pages/JoinPage"; // M1-P02
import OwnerAnswerPage from "./pages/OwnerAnswerPage"; // M2-P02
import GuestUploadPage from "./modules/m3_connect/intake/GuestUploadPage"; // M3-P02
import IntentNew from "./intents/IntentNew";
import IntentScreen from "./intents/IntentScreen";
import IntentPast from "./intents/IntentPast";
import IntentChain from "./intents/IntentChain";
import IntentBacklog from "./intents/IntentBacklog";
import IntentAdmin from "./intents/IntentAdmin";
import AreasAdmin from "./intents/AreasAdmin";
import VisitorView from "./intents/VisitorView";
import { GapAnalysisRoom } from "./intents/views/BuildReadyView";
import ControlIntents from "./intents/ControlIntents";
import V3Routes from "./v3/routes";
import { ThemeProvider } from "./theme";
import { SessionProvider, useSession } from "./useSession";

/** The usual start page: a sign-in from it, or from "/", needs no ?next (each person then lands per the role table). */
const HOME = "/centre/home";

/** The page to return to after sign-in: an in-app path only, never another site. */
export function safeNext(search: string): string | null {
  const next = new URLSearchParams(search).get("next");
  return next && /^\/(?![/\\])[^\\]*$/.test(next) ? next : null;
}

function Gate({ signedIn, children }: { signedIn: boolean; children: ReactNode }) {
  const { state, retry, user } = useSession();
  const loc = useLocation();
  if (state === "loading") return <ScreenState state="loading" />;
  if (state === "error") return <ScreenState state="error" onRetry={retry} />;
  if ((state === "signed-in") === signedIn) return <>{children}</>;
  if (signedIn) {
    const here = loc.pathname + loc.search;
    return <Navigate to={here === "/" || here === HOME ? "/login" : `/login?next=${encodeURIComponent(here)}`} replace />;
  }
  return <Navigate to={safeNext(loc.search) ?? landingFor(user?.roles)} replace />;
}

/** "/" opens the person's own start page (A-073): the pulse, or Control for the super admin. */
function Landing() {
  const { user } = useSession();
  return <Navigate to={landingFor(user?.roles)} replace />;
}

/** A centre's screens for the roles that see it (A-073). Anyone else goes to their start page, which says why. */
function RoleGate({ centre, also = [] }: { centre: Centre; also?: string[] }) {
  const { user } = useSession();
  const roles = user?.roles ?? [];
  if (centresFor(roles).has(centre) || also.some((r) => roles.includes(r))) return <Outlet />;
  return <Navigate to={landingFor(user?.roles)} replace state={{ refused: true }} />;
}

export default function App() {
  return (
    <ThemeProvider>
      <SessionProvider>
        <Routes>
          <Route path="/login" element={<Gate signedIn={false}><LoginPage /></Gate>} />
          <Route path="/" element={<Gate signedIn><Landing /></Gate>} />
          <Route path="/v3/*" element={<Gate signedIn><V3Routes /></Gate>} />
          <Route path="/pulse" element={<Navigate to="/centre/action" replace />} />
          {/* the old home stays reachable for what is not rebuilt yet; only the avatar menu links here */}
          <Route path="/legacy" element={<Gate signedIn><HomePage /></Gate>} />
          <Route path="/company/context" element={<Gate signedIn><CentreShell /></Gate>}>
            <Route index element={<ContextPage />} />
          </Route>
          <Route path="/company/bring" element={<Gate signedIn><CentreShell /></Gate>}>
            <Route index element={<BringPage />} />
          </Route>
          <Route path="/company/interview" element={<Gate signedIn><CentreShell /></Gate>}>
            <Route index element={<InterviewPage />} />
          </Route>
          <Route path="/centre" element={<Gate signedIn><CentreShell /></Gate>}>
            {/* 1.0: each slim card registers its own screens in ui/src/v1/<card>/routes.tsx; literal paths, so they rank above :intentId */}
            {v1Routes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
            <Route element={<RoleGate centre="control" />}>
              <Route path="control" element={<ControlPage />} />
              <Route path="control/intents" element={<ControlIntents />} />
            </Route>
            <Route element={<RoleGate centre="intent" />}>
              <Route path="intent/bring" element={<BringCentre />} />
              <Route path="intent/outcomes" element={<OutcomesPage />} />
              {/* IC v2 (ruling 1). Literal paths first; the router also ranks a literal segment above :intentId */}
              <Route path="intent/past" element={<IntentPast />} />
              <Route path="intent/past/:intentId/chain" element={<IntentChain />} />
              <Route path="intent/backlog" element={<IntentBacklog />} />
              <Route path="intent/admin" element={<IntentAdmin />} />
              <Route path="intent/admin/areas" element={<AreasAdmin />} />
              <Route path="intent/admin/areas/people" element={<AreasAdmin />} />
              <Route path="shared/:intentId" element={<VisitorView />} />
              <Route path="shared/t/:token" element={<VisitorView />} />
              <Route path="intent/:intentId" element={<IntentScreen />} />
              <Route path="intent/:intentId/:view" element={<IntentScreen />} />
            </Route>
            <Route element={<RoleGate centre="build" also={["owner"]} />}>
            </Route>
            <Route element={<RoleGate centre="build" />}>
              <Route path="build/gap-analysis" element={<GapAnalysisRoom />} />
              <Route path="build/environment" element={<BuildEnvironment />} />
              <Route path="build/blueprint" element={<BlueprintPage />} />
              <Route path="build/pipelines" element={<PipelinesPage />} />
            </Route>
            <Route element={<RoleGate centre="consume" />}>
              <Route path="consume/views" element={<ConsumeCentre />} />
              <Route path="consume/feeds" element={<FeedsPage />} />
              <Route path="consume/feeds/:code" element={<MeasurePage />} />
              <Route path="consume/market" element={<MarketPage />} />
              <Route path="consume/what-if" element={<WhatIfPage />} />
              <Route path="consume/lens/:lens" element={<LensPage />} />
            </Route>
            {/* open to every company role: the pulse, the map, the register and memory (the super admin has none of these) */}
            <Route element={<RoleGate centre="pulse" />}>
              <Route path="pulse" element={<PulsePage />} />
            </Route>
            <Route path="design-gallery" element={<Gallery />} />
            <Route element={<RoleGate centre="map" />}>
              <Route path="intent/graph" element={<GraphPage />} />
              <Route path="intent/map/:nodeId" element={<NodePage />} />
              <Route path="register" element={<RegisterPage />} />
              <Route path="memory" element={<MemoryPage />} />
              {/* the proofs are read by the tester and released by the sponsor, whatever their bar shows; the server decides */}
              <Route path="build/prove" element={<ProvePage />} />
              {/* 59: the chain's named people (head of department, tester, ops) and map readers open these; the server decides */}
              <Route path="build/architecture" element={<ArchitecturePage />} />
              <Route path="build/change/:id" element={<ChangeNotePage />} />
            </Route>
            {/* a seat or a signature to give opens these, whatever the bar shows; the server decides and its refusal is shown */}
            <Route path="intent/baseline/:baselineId" element={<BaselinePage />} />
            <Route path="intent/charter/:sessionId" element={<CharterView />} />
            <Route path="intent/wall/:sessionId" element={<WallScreen />} />
            <Route path="intent/define/:sessionId" element={<DefineScreen />} />
            <Route path="intent/truth/:assessmentId" element={<TruthScreen />} />
            <Route path="intent/truth/:assessmentId/request" element={<RequestScreen />} />
          </Route>
          {/* LI-INTERVIEW: a person's own interview link needs no sign-in */}
          <Route path="/interview/:token" element={<InterviewPage />} />
          <Route path="/modules/:id/*" element={<Gate signedIn><ModulePage /></Gate>} />
          {/* M1-P02: the join link needs no sign-in */}
          <Route path="/join/:code" element={<JoinPage />} />
          {/* M2-P02: the owner's answer link needs no sign-in */}
          <Route path="/answer/:token" element={<OwnerAnswerPage />} />
          {/* M3-P02: the source owner's upload link needs no sign-in */}
          <Route path="/intake/:token" element={<GuestUploadPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </SessionProvider>
    </ThemeProvider>
  );
}
