import { useEffect, useState } from "react";

import { apiGet } from "../../api/client";
import Panel from "../../components/Panel";

// R1: what this intent of work has cost in model use, and how much ran on the fast tier. No model or vendor names on screen.
interface Costs { calls: number; tokens: number; fast_share: number; estimated: boolean; cost_usd?: number | null; priced_all?: boolean; avg_latency_ms?: number | null }

export default function CostPanel({ iid }: { iid: string }) {
  const [c, setC] = useState<Costs | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<Costs>(`/api/v1/router/costs?iid=${encodeURIComponent(iid)}`).then((x) => live && setC(x)).catch(() => undefined);
    return () => { live = false; };
  }, [iid]);
  if (!c) return null;
  return (
    <Panel tight title="Model use">
      <p style={{ margin: 0 }}>
        {c.calls ? `This intent of work used ${c.tokens.toLocaleString("en-GB")} tokens over ${c.calls} calls, ${c.fast_share}% on the fast tier.`
          : "No model calls for this intent of work yet."}
        {c.calls && c.cost_usd != null ? ` About USD ${c.cost_usd < 0.01 && c.cost_usd > 0 ? "0.00 (under a cent)" : c.cost_usd.toFixed(2)} at list prices${c.priced_all ? "" : " (some calls have no price)"}.` : null}
        {c.calls && c.avg_latency_ms != null ? ` A call took ${c.avg_latency_ms.toLocaleString("en-GB")} ms on average.` : null}
        {c.estimated ? <span className="ds-muted"> Some counts are estimated.</span> : null}
      </p>
    </Panel>
  );
}
