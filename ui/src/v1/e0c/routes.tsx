import type { V1Route } from "..";
import FilePage from "./FilePage";
import IntakePage from "./IntakePage";

export const routes: V1Route[] = [
  { path: "data/intake", element: <IntakePage /> },
  { path: "data/intake/:fileId", element: <FilePage /> },
];
