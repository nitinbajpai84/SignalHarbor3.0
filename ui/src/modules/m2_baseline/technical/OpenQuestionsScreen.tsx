import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState, { type ScreenStateName } from "../../../components/ScreenState";
import { useLoad } from "../../../components/useLoad";
import { useSession } from "../../../useSession";
import { CHANGED } from "../api";
import BaselineSteps from "../BaselineSteps";
import { m2Tech as t } from "./copy";
import QuestionItem from "./QuestionItem";
import { AMB_KINDS, getTechnical, type AmbKind, type AmbStatus, type TechnicalScreen } from "./technicalApi";

type StatusFilter = "all" | AmbStatus;
const STATUSES: StatusFilter[] = ["all", "open", "settled", "accepted"];

/** M2-E1: every open question across the baseline's measures, with filters (open, settled, accepted; by kind; by owner) and the three ways
 * to deal with each. The server leaves out anything that names a measure, source or field this person may not see. */
export default function OpenQuestionsScreen() {
  const { baselineId = "" } = useParams();
  const { user } = useSession();
  const loaded = useLoad(() => getTechnical(baselineId), `m2-questions-${baselineId}`, (s) => s.ambiguities.length === 0);
  const [fresh, setFresh] = useState<TechnicalScreen | null>(null);
  const [status, setStatus] = useState<StatusFilter>("open");
  const [kind, setKind] = useState<AmbKind | "all">("all");
  const [owner, setOwner] = useState("all");
  useEffect(() => {
    const again = () => getTechnical(baselineId).then(setFresh).catch(() => undefined);
    window.addEventListener(CHANGED, again);
    return () => window.removeEventListener(CHANGED, again);
  }, [baselineId]);
  const data = fresh ?? loaded.data;
  const state: ScreenStateName = fresh ? (fresh.ambiguities.length ? "populated" : "empty") : loaded.state;
  const locked = data?.signed === true;
  const governor = !!user?.roles?.some((r) => r === "company_admin" || r === "sponsor");
  const owners = [...new Set((data?.ambiguities ?? []).map((a) => a.owner).filter(Boolean))].sort();
  const shown = (data?.ambiguities ?? []).filter((a) => (status === "all" || a.status === status) && (kind === "all" || a.kind === kind) && (owner === "all" || a.owner === owner));
  return (
    <>
      <PageHead eyebrow={t.tab.eyebrow} title={t.tab.title} sub={t.tab.sub} />
      <BaselineSteps baselineId={baselineId} signed={locked} />
      <ScreenState state={state} message={state === "empty" ? t.tab.empty : state === "refused" ? t.refused : loaded.message} onRetry={loaded.retry}>
        {data ? (
          <Panel title={t.tab.counts(data.counts.open, data.counts.settled, data.counts.accepted)}>
            <div className="n-flex wrap" role="group" aria-label={t.tab.statusFilter}>
              {STATUSES.map((s) => (
                <button key={s} type="button" className={`n-btn sm${status === s ? " primary" : ""}`} aria-pressed={status === s} onClick={() => setStatus(s)}>
                  {s === "all" ? t.tab.all : t.status[s]} ({s === "all" ? data.counts.all : data.counts[s]})
                </button>
              ))}
              <label className="n-muted">
                {t.tab.kindFilter}{" "}
                <select className="n-select" aria-label={t.tab.kindFilter} value={kind} onChange={(e) => setKind(e.target.value as AmbKind | "all")}>
                  <option value="all">{t.tab.allKinds}</option>
                  {AMB_KINDS.map((k) => <option key={k} value={k}>{t.kind[k]}</option>)}
                </select>
              </label>
              <label className="n-muted">
                {t.tab.ownerFilter}{" "}
                <select className="n-select" aria-label={t.tab.ownerFilter} value={owner} onChange={(e) => setOwner(e.target.value)}>
                  <option value="all">{t.tab.allOwners}</option>
                  {owners.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </label>
            </div>
            {shown.length === 0 ? (
              <p className="n-muted">{t.tab.none}</p>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
                {shown.map((a) => (
                  <QuestionItem key={`${a.kpi_id}-${a.id}-${a.status}-${a.asked?.at ?? ""}`} baselineId={baselineId} item={a} kpi={data.kpis.find((k) => k.kpi_id === a.kpi_id)} locked={locked} governor={governor} onScreen={setFresh} withMeasure />
                ))}
              </ul>
            )}
          </Panel>
        ) : null}
      </ScreenState>
    </>
  );
}
