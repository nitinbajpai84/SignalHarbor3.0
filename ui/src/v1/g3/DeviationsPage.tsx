import { useParams } from "react-router-dom";

import { PageFrame } from "../../design";
import DeviationCards from "./DeviationCards";

// G4: /centre/build/:iid/deviations, where the engineer's "waiting for approval" link lands.
export default function DeviationsPage() {
  const { iid = "" } = useParams<{ iid: string }>();
  return <PageFrame title="Deviations"><DeviationCards iid={iid} /></PageFrame>;
}
