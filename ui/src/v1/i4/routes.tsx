import type { V1Route } from "..";
import SignPage from "./SignPage";
import SowPage from "./SowPage";

export const routes: V1Route[] = [{ path: "intent/:iid/sow", element: <SowPage /> }, { path: "intent/:iid/sign", element: <SignPage /> }];
