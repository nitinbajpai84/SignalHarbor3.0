import type { V1Route } from "..";
import SpanPage from "./SpanPage";

export const routes: V1Route[] = [{ path: "build/:iid", element: <SpanPage /> }];
