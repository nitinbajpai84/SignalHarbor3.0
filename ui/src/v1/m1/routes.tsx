import type { V1Route } from "..";
import MapPage from "./MapPage";

export const routes: V1Route[] = [{ path: "intent/graph", element: <MapPage /> }];
