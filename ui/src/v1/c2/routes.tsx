import type { V1Route } from "..";
import { PageFrame } from "../../design";
import OffersSection from "./OffersSection";

// The offers also stand on their own page until the Consume screen (C1) sets OffersSection in place.
export const routes: V1Route[] = [
  { path: "consume/offers", element: <PageFrame title="Offers" subline="What another feed would add to your measures."><OffersSection /></PageFrame> },
];
