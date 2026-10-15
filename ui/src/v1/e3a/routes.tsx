import type { V1Route } from "..";
import AdminRules from "./AdminRules";

export const routes: V1Route[] = [{ path: "admin/rules", element: <AdminRules /> }];
