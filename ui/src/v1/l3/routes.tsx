import type { V1Route } from "..";
import LibraryPage from "./LibraryPage";
import LibraryViewPage from "./LibraryViewPage";

export const routes: V1Route[] = [
  { path: "library", element: <LibraryPage /> },
  { path: "library/view", element: <LibraryViewPage /> },
];
