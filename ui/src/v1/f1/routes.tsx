import type { V1Route } from "../index";
import EngineerPage from "./EngineerPage";

export const routes: V1Route[] = [{ path: "build/:iid/engineer", element: <EngineerPage /> }];
