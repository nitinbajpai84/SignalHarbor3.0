import { useParams } from "react-router-dom";

import NiraPanel from "../../components/NiraPanel";
import { useLoad } from "../m1_intent/useLoad";
import type { Step } from "./api";
import { m3Nira, m3Steps } from "./copy";
import { getNext } from "./plan/planApi";

/** Nira's small side panel: one plain sentence from the server, the first thing waiting and on whom ("3 risks need a decision from the sponsor.").
 * Until that sentence arrives, or when it cannot be had, it says the same from the first step that is not done. `refresh` re-asks after a change. */
export default function NiraNext({ steps, refresh = 0 }: { steps: Step[]; refresh?: number }) {
  const { assessmentId = "" } = useParams();
  const said = useLoad(() => getNext(assessmentId), `m3-next-${assessmentId}-${refresh}`);
  const next = steps.find((s) => s.state !== "done");
  return (
    <NiraPanel label={m3Nira.name} name="Nira" footer={null}>
      <h2 className="n-panel-title">{m3Nira.next}</h2>
      {said.state === "populated" && said.data ? (
        <p>{said.data.sentence}</p>
      ) : next ? (
        <p>
          <strong>{m3Steps[next.id]}.</strong> {next.waiting_on}
        </p>
      ) : (
        <p>{m3Nira.allDone}</p>
      )}
    </NiraPanel>
  );
}
