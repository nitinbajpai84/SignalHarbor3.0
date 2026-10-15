import type { V1Route } from "..";
import ScanPage from "./ScanPage";

export const routes: V1Route[] = [{ path: "build/:iid/scan", element: <ScanPage /> }];
