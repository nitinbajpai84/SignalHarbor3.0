import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../../components/useLoad";
import { getAnswers, getOutstanding, saveMeetingAnswers, uploadMeetingSample, type AnswerRecord } from "../api";
import { m2, m2Form as T, m2Req } from "../copy";
import QuestionnaireForm from "./QuestionnaireForm";

/** Answer in a meeting (deck slide 6): the organiser fills the same form for someone, marked "in a meeting" with their name. */
export default function MeetingScreen() {
  const { baselineId = "" } = useParams();
  const [params] = useSearchParams();
  const load = useLoad(
    async () => ({ answers: await getAnswers(baselineId), asked: (await getOutstanding(baselineId)).requests.map((r) => r.owner_name) }),
    `meeting-${baselineId}`,
    (d) => d.answers.kpis.length === 0,
  );
  const [owner, setOwner] = useState(params.get("owner") ?? "");
  const [kpiId, setKpiId] = useState("");
  const [records, setRecords] = useState<AnswerRecord[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  const d = load.data;
  const kpi = d?.answers.kpis.find((k) => k.id === (kpiId || d.answers.kpis[0]?.id));
  const name = owner.trim();
  const initial = kpi ? ([...records, ...(d?.answers.answers ?? [])].find((a) => a.owner_name === name && a.kpi_id === kpi.id) ?? null) : null;

  return (
    <>
      <PageHead
        title={T.inMeetingTitle}
        eyebrow={m2Req.eyebrow}
        crumbs={[{ label: m2.title, to: "/modules/m2_baseline" }, { label: m2Req.title, to: `/modules/m2_baseline/requests/${encodeURIComponent(baselineId)}` }, { label: T.inMeetingTitle }]}
        sub={T.inMeetingIntro}
      />
      <ScreenState state={load.state} message={load.state === "empty" ? T.noMeasures : load.message} onRetry={load.retry}>
        {d && kpi ? (
          <Panel>
            <label>
              {T.who}
              <input type="text" list="m2-asked" value={owner} placeholder={T.whoPlaceholder} onChange={(e) => { setOwner(e.target.value); setSaved(null); }} />
            </label>
            <datalist id="m2-asked">
              {d.asked.map((n) => (
                <option key={n} value={n} />
              ))}
            </datalist>
            <label>
              {T.pickMeasure}
              <select value={kpi.id} onChange={(e) => { setKpiId(e.target.value); setSaved(null); }}>
                {d.answers.kpis.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name}
                  </option>
                ))}
              </select>
            </label>
            {name === "" ? (
              <p className="n-muted">{T.needName}</p>
            ) : (
              <>
                <QuestionnaireForm
                  key={`${name}|${kpi.id}`}
                  spec={d.answers.questionnaire}
                  measure={kpi.name}
                  initial={initial}
                  onSave={async (a) => (await saveMeetingAnswers(baselineId, name, kpi.id, a)).saved}
                  onSample={async (f) => (await uploadMeetingSample(baselineId, name, kpi.id, f)).saved}
                  onSaved={(rec) => { setRecords((r) => [rec, ...r]); setSaved(T.meetingSaved(name)); }}
                />
                {saved ? (
                  <p role="status" className="state n-muted">
                    {saved}
                  </p>
                ) : null}
              </>
            )}
          </Panel>
        ) : null}
      </ScreenState>
      <p>
        <Link to={`/modules/m2_baseline/requests/${encodeURIComponent(baselineId)}`}>{T.back}</Link>
      </p>
    </>
  );
}
