import type { V1Route } from "..";
import { Navigate, useLocation } from "react-router-dom";
import MapPage from "./MapPage";
import OperationsPage from "./OperationsPage";
import ReviewQueue from "./ReviewQueue";

// /centre/map is the Map: ?tab=processes|definitions picks a view, ?lens=&project=&focus= shape the ontology (the Trail panel's "Open in the map" lands with ?focus=).
// /centre/map/review is the head of data's queue (Action lists it). /centre/operations is the old Health tab, now under Build.
/** The old whole-company address keeps working. */
function CompanyRedirect() {
  return <Navigate to={`/centre/map${useLocation().search}`} replace />;
}

export const routes: V1Route[] = [
  { path: "map", element: <MapPage /> },
  { path: "map/company", element: <CompanyRedirect /> },
  { path: "map/review", element: <ReviewQueue /> },
  { path: "operations", element: <OperationsPage /> },
];
