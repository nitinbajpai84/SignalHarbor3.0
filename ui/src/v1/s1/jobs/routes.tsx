import type { V1Route } from "../..";
import JobsPage from "./JobsPage";

export const routes: V1Route[] = [{ path: "settings/jobs", element: <JobsPage /> }];
