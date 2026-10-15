import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../m1_intent/useLoad";
import { getAssessment, type Step } from "../api";
import ConnectSteps from "../ConnectSteps";
import { m3, m3Area } from "../copy";
import NiraNext from "../NiraNext";
import BandsPanel from "./BandsPanel";
import { planCopy as T } from "./copy";
import { acceptAll, decideRisk, draftAgain, editItem, getPlan, getRisks, signPlan, type ItemChange, type PlanView, type RisksView } from "./planApi";
import RisksPanel from "./RisksPanel";
import SignPanel from "./SignPanel";

const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : T.sign.failed);

/** The plan screen (customer actions 3 and 4): the risks to accept, the drafted three-band plan, then the signatures. */
export default function PlanScreen() {
  const { assessmentId = "" } = useParams();
  const s = useLoad(() => Promise.all([getAssessment(assessmentId), getPlan(assessmentId), getRisks(assessmentId)]), `m3-plan-${assessmentId}`,
    ([, p, r]) => !p.drafted && r.risks.length === 0);
  const text = m3Area.plan;
  return (
    <>
      <PageHead title={text.title} sub={text.sub} eyebrow={m3.eyebrow}
        crumbs={[{ label: m3.crumbModules, to: "/" }, { label: m3.crumbAssess, to: "/modules/m3_connect" }, { label: text.title }]} />
      <ScreenState state={s.state} message={s.state === "empty" ? (s.data?.[1].waiting ?? T.waitingTitle) : s.message} onRetry={s.retry}>
        {s.data ? <Body id={assessmentId} steps={s.data[0].steps} first={s.data[1]} firstRisks={s.data[2]} /> : null}
      </ScreenState>
    </>
  );
}

function Body({ id, steps, first, firstRisks }: { id: string; steps: Step[]; first: PlanView; firstRisks: RisksView }) {
  const [plan, setPlan] = useState(first);
  const [risks, setRisks] = useState(firstRisks);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  /** One action at a time; whatever it changes, both views and Nira's sentence are read again. */
  const run = async (work: () => Promise<string | void>): Promise<boolean> => {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      const done = await work();
      const [p, r] = await Promise.all([getPlan(id), getRisks(id)]);
      setPlan(p);
      setRisks({ ...r, accepted: undefined, left_hidden: undefined });
      setVersion((v) => v + 1);
      if (done) setNotice(done);
      return true;
    } catch (e) {
      setProblem(problemText(e));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const locked = !plan.viewer.can_edit || plan.signed_at !== null;
  return (
    <>
      <ConnectSteps assessmentId={id} steps={steps} />
      {plan.waiting ? <p role="status" className="state n-muted">{plan.waiting}</p> : null}
      <RisksPanel view={risks} disabled={busy || locked}
        onDecide={(rid, body) => void run(async () => void (await decideRisk(id, rid, body)))}
        onAcceptAll={() => void run(async () => {
          const got = await acceptAll(id);
          return [T.risks.acceptedN(got.accepted ?? 0), got.left_hidden ? T.risks.leftHidden(got.left_hidden) : ""].filter(Boolean).join(" ");
        })} />
      {plan.drafted ? (
        <BandsPanel plan={plan} disabled={busy || locked}
          onEdit={(change: ItemChange) => run(async () => void (await editItem(id, change)))}
          onRedraft={() => void run(async () => {
            await draftAgain(id);
            return T.plan.redrafted;
          })} />
      ) : null}
      <SignPanel plan={plan} busy={busy} onSign={() => void run(async () => void (await signPlan(id)))} />
      {notice ? <p role="status" className="state n-muted">{notice}</p> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      <NiraNext steps={steps} refresh={version} />
    </>
  );
}
