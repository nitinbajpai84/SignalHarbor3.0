import type { V1Route } from "..";
import AdminAgents from "./AdminAgents";

export const routes: V1Route[] = [{ path: "admin/agents", element: <AdminAgents /> }];
