import type { V1Route } from "..";
import ConversationPage from "./ConversationPage";

export const routes: V1Route[] = [
  { path: "intent/:iid", element: <ConversationPage /> },
];
