import type { V1Route } from "../index";
import RunsPage from "./RunsPage";

export const routes: V1Route[] = [{ path: "build/:iid/runs", element: <RunsPage /> }];
