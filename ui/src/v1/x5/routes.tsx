import type { V1Route } from "..";
import ExtractionPage from "./ExtractionPage";
import ReviewPage from "./ReviewPage";

export const routes: V1Route[] = [
  { path: "extract/review", element: <ReviewPage /> },
  { path: "intent/:iid/extraction", element: <ExtractionPage /> },
];
