import type { V1Route } from "..";
import MappingPage from "./MappingPage";

export const routes: V1Route[] = [{ path: "build/:iid/mapping", element: <MappingPage /> }];
