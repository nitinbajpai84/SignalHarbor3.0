import type { V1Route } from "../index";
import DesignPage from "./DesignPage";

export const routes: V1Route[] = [{ path: "build/:iid/design", element: <DesignPage /> }];
