import type { V1Route } from "../index";
import DeviationsPage from "./DeviationsPage";
import SourceDocPage from "./SourceDocPage";

export const routes: V1Route[] = [{ path: "build/:iid/deviations", element: <DeviationsPage /> }, { path: "build/:iid/source", element: <SourceDocPage /> }];
