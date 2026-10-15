import { Link } from "react-router-dom";

import { Strip, when } from "../../design";
import type { Refresh } from "./api";

// DS1: the header line of every dashboard, in the studio and in Consume. The sentence comes from the project's pipeline schedule and runs.
export default function RefreshLine({ refresh }: { refresh: Refresh | null }) {
  if (!refresh) return null;
  const parts = [refresh.words, `last refreshed ${when(refresh.last_refreshed, "not yet")}`, refresh.next ? `next ${when(refresh.next)}` : ""].filter(Boolean);
  return (
    <div aria-label="How fresh these figures are">
      <p className="ds-muted" style={{ margin: "4px 0" }}>{parts.join(" · ")}</p>
      {refresh.warning ? <Strip label="Not up to date" tone="amber">{refresh.warning}. <Link className="ds-link" to={refresh.link ?? "/centre/operations"}>See the source health in Operations</Link></Strip> : null}
    </div>
  );
}
