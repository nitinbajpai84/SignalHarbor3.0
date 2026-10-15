import type { V1Route } from "..";
import PainPointDemo from "./PainPointDemo";

// W2: the pain-point demo page. Optional ?name=<file> reads local/painpoints/<file>.yaml on the server.
export const routes: V1Route[] = [{ path: "demo/painpoints", element: <PainPointDemo /> }];
