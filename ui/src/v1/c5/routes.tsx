import type { V1Route } from "..";
import ConnectApiPage from "./ConnectApiPage";

// C5: Connectors open inside Settings (s1 SettingsPage, section "connectors"). Connect an API is its own page in Build.
export const routes: V1Route[] = [{ path: "build/connect-api", element: <ConnectApiPage /> }];
