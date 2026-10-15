import { useState } from "react";

import Panel from "../../../components/Panel";
import { useSession } from "../../../useSession";
import TechnicalSection from "../technical/TechnicalSection";
import { answerQuestion, removeKpi, type KpiFull, type Question, type WorkList } from "../api";
import { m2Work } from "../copy";
import GovernancePanel from "./GovernancePanel";
import OwnersPanel from "./OwnersPanel";
import ProvCell from "./ProvCell";
import TriageForm from "./TriageForm";
import { S } from "./layout";

interface Props {
  id: string;
  kpi: KpiFull;
  me: string;
  locked: boolean;
  act: (p: Promise<WorkList>) => void;
  onClose: () => void;
}

function QuestionRow({ id, kpi, q, locked, act }: { id: string; kpi: KpiFull; q: Question; locked: boolean; act: Props["act"] }) {
  const [text, setText] = useState("");
  return (
    <li className="n-suggest-block">
      <div className="n-suggest-label">{m2Work.suggestedHere}</div>
      <p>{q.question}</p>
      {q.answer.mark === "unknown" ? (
        <div className="n-flex wrap">
          <input className="n-input" aria-label={`${m2Work.answer}: ${q.question}`} placeholder={m2Work.answer} value={text} disabled={locked} onChange={(e) => setText(e.target.value)} />
          <button type="button" className="n-btn sm primary" disabled={locked || !text.trim()} onClick={() => act(answerQuestion(id, kpi.id, q.id, text))}>
            {m2Work.answerSave}
          </button>
        </div>
      ) : (
        <ProvCell p={q.answer} />
      )}
    </li>
  );
}

/** One measure opened: say what you know, answer Lens's questions, nominate the owners, set governance. */
export default function KpiDetail({ id, kpi, me, locked, act, onClose }: Props) {
  const { user } = useSession();
  const governor = !!user?.roles?.some((r) => r === "company_admin" || r === "sponsor");
  return (
    <Panel
      eyebrow={m2Work.detailEyebrow}
      title={kpi.name}
      actions={
        <>
          {!locked ? (
            <button type="button" className="n-btn sm ghost" onClick={() => act(removeKpi(id, kpi.id))}>
              {m2Work.remove}
            </button>
          ) : null}
          <button type="button" className="n-btn sm" onClick={onClose}>
            {m2Work.close}
          </button>
        </>
      }
    >
      <div style={S.detail}>
        <TriageForm id={id} kpi={kpi} locked={locked} act={act} />
        <TechnicalSection baselineId={id} kpiId={kpi.id} locked={locked} governor={governor} />
        {kpi.questions.length > 0 ? (
          <div>
            <h3 style={S.h3}>{m2Work.questionsTitle}</h3>
            <ul style={S.list}>
              {kpi.questions.map((q) => (
                <QuestionRow key={`${q.id}-${q.answer.at}`} id={id} kpi={kpi} q={q} locked={locked} act={act} />
              ))}
            </ul>
          </div>
        ) : null}
        <OwnersPanel id={id} kpi={kpi} me={me} locked={locked} act={act} />
        <GovernancePanel key={`${kpi.id}-${kpi.governance.may_see.join("|")}`} id={id} kpi={kpi} locked={locked} act={act} />
      </div>
    </Panel>
  );
}
