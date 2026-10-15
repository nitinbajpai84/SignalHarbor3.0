import type { V1Route } from "..";
import ProjectPage from "./ProjectPage";

export const routes: V1Route[] = [{ path: "project/:pid", element: <ProjectPage /> }];
