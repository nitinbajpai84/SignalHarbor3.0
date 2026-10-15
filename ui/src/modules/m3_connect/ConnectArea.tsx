import { useParams } from "react-router-dom";

import PageHead from "../../components/PageHead";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../m1_intent/useLoad";
import { getAssessment } from "./api";
import ConnectSteps from "./ConnectSteps";
import { m3, m3Area } from "./copy";
import NiraNext from "./NiraNext";

/** One screen of an assessment: the step strip, Nira's panel and, until its package lands, a placeholder. Each package replaces the
 * placeholder body (the route stays in ConnectModule.tsx). */
export default function ConnectArea({ area }: { area: keyof typeof m3Area }) {
  const { assessmentId = "" } = useParams();
  const s = useLoad(() => getAssessment(assessmentId), `m3-assessment-${assessmentId}`);
  const text = m3Area[area];
  return (
    <>
      <PageHead title={text.title} sub={text.sub} eyebrow={m3.eyebrow}
        crumbs={[{ label: m3.crumbModules, to: "/" }, { label: m3.crumbAssess, to: "/modules/m3_connect" }, { label: text.title }]} />
      <ScreenState state={s.state} message={s.message} onRetry={s.retry}>
        {s.data ? (
          <>
            <ConnectSteps assessmentId={assessmentId} steps={s.data.steps} />
            <p className="n-muted">{m3.comingNext}</p>
            <NiraNext steps={s.data.steps} />
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
