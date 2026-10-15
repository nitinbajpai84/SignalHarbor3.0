import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../../components/useLoad";
import { drawProcessMap, getProcessMap, type KpiMap, type Prov, type ProcessMap } from "../api";
import BaselineSteps from "../BaselineSteps";
import { mapCopy as t } from "../copy";
import KpiMapPanel from "./KpiMapPanel";

const markLabel = (p: Prov) => (p.mark === "stated" ? t.confirmed : p.mark === "guessed" ? t.suggestion : t.unknown);

/** M2-21: the as-is process map per measure, drawn from the owners' answers (old look: Process & Lever Map). */
export default function ProcessMapScreen() {
  const { baselineId = "" } = useParams();
  const s = useLoad(() => getProcessMap(baselineId), `m2-process-map-${baselineId}`, (d) => d.kpis.length === 0);
  const [latest, setLatest] = useState<ProcessMap | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const map = latest ?? s.data;

  const draw = async () => {
    setBusy(true);
    setProblem(null);
    try {
      setLatest(await drawProcessMap(baselineId));
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : t.notStated);
    } finally {
      setBusy(false);
    }
  };
  const swap = (k: KpiMap) => map && setLatest({ ...map, kpis: map.kpis.map((x) => (x.id === k.id ? k : x)) });
  const drawn = map?.kpis.some((k) => k.drawn) ?? false;

  return (
    <>
      <PageHead
        eyebrow={t.eyebrow}
        title={t.title}
        sub={t.sub}
        crumbs={[{ label: t.crumbHome, to: "/modules/m2_baseline" }, { label: t.title }]}
      />
      <BaselineSteps baselineId={baselineId} signed={map?.signed === true} />
      <ScreenState state={s.state} message={s.state === "empty" ? t.empty : s.message} onRetry={s.retry}>
        {map ? (
          <>
            {map.signed ? null : (
              <p className="n-flex wrap">
                <button type="button" className="n-btn primary" onClick={() => void draw()} disabled={busy}>
                  {busy ? t.drawing : drawn ? t.redraw : t.draw}
                </button>
                <span className="n-muted">{t.drawHint}</span>
              </p>
            )}
            {problem ? (
              <p role="alert" className="state state-error">
                {problem}
              </p>
            ) : null}
            {map.kpis.map((k) => (
              <section key={k.id} aria-label={k.name ?? ""}>
                <KpiMapPanel baselineId={baselineId} kpi={k} statuses={map.statuses} signed={map.signed} onChange={swap} />
              </section>
            ))}
            <Panel title={t.defsTitle} eyebrow={t.defsEyebrow}>
              <div className="n-table-wrap">
                <table className="n-table">
                  <thead>
                    <tr>
                      <th>{t.term}</th>
                      <th>{t.definition}</th>
                      <th>{t.state}</th>
                      <th>{t.source}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {map.kpis.map((k) => (
                      <tr key={k.id}>
                        <td>{k.name}</td>
                        <td>{k.definition.value ?? t.notStated}</td>
                        <td>
                          <StatusPill tone={k.definition.mark === "stated" ? "success" : k.definition.mark === "guessed" ? "warning" : "muted"}>
                            {markLabel(k.definition)}
                          </StatusPill>
                        </td>
                        <td>{k.definition.value ? t.by(k.definition.by) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
