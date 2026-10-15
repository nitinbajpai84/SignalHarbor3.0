import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api/client";
import Panel from "../../components/Panel";
import ConsumePage from "../c1/ConsumePage";

// P3: /centre/consume. First what has been built (each signed intent of work and how many of its figures are loaded), then C1's
// figures, which end with "Shape what you see" (C3) and the offers (C2).

interface Built { intent_id: string; title?: string | null; kpis: { latest: unknown }[] }

export default function ConsumeEntry() {
  const [built, setBuilt] = useState<Built[] | null>(null);

  useEffect(() => {
    let live = true;
    apiGet<{ intents: Built[] }>("/api/v1/consume").then((d) => { if (live) setBuilt(d.intents); }, () => undefined); // C1 below says why
    return () => { live = false; };
  }, []);

  return (
    <>
      {built?.length ? (
        <div className="ds-screen">
          <Panel title="What has been built for you">
            <ul style={{ margin: 0 }}>
              {built.map((b) => {
                const n = b.kpis.filter((k) => k.latest).length;
                return <li key={b.intent_id}><strong>{b.title || "Untitled work"}</strong>: {n} of {b.kpis.length} {b.kpis.length === 1 ? "figure" : "figures"} loaded</li>;
              })}
            </ul>
          </Panel>
        </div>
      ) : null}
      <div className="ds-screen"><p><Link className="ds-link" to="/centre/consume/office">Open the Office view</Link></p></div>
      <ConsumePage />
    </>
  );
}
