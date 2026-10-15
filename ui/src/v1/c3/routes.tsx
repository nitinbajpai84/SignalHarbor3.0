import type { V1Route } from "..";
import AskPage from "./AskPage";
import DesignPage from "./DesignPage";

export const routes: V1Route[] = [
  { path: "consume/design", element: <DesignPage /> },
  { path: "consume/design/:iid", element: <DesignPage /> },
  { path: "consume/design/:iid/ask", element: <AskPage /> },
];
