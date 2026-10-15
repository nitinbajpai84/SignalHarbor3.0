import { useState } from "react";
import { useParams } from "react-router-dom";

import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../m1_intent/useLoad";
import { getAssessment, getSourceMap, rescoreSources, type MapSource, type SourceMapData, type ZoneId } from "../api";
import ConnectSteps from "../ConnectSteps";
import { m3 } from "../copy";
import NiraNext from "../NiraNext";
import { mapCopy as t } from "./copy";
import SourceMapChart, { KIND_FILL, markLines } from "./SourceMapChart";
import SourcePanel from "./SourcePanel";

const ORDER: ZoneId[] = ["p1", "p2", "unknown", "identify"];

export default function MapScreen() {
  const { assessmentId = "" } = useParams();
  const [version, setVersion] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [fresh, setFresh] = useState<SourceMapData | null>(null);
  const [scoring, setScoring] = useState(false);
  const [rescoreFailed, setRescoreFailed] = useState(false);
  const a = useLoad(() => getAssessment(assessmentId), `m3-assessment-${assessmentId}-${version}`);
  const m = useLoad(() => getSourceMap(assessmentId), `m3-map-${assessmentId}-${version}`, (d) => d.sources.length === 0);
  const data = fresh ?? m.data;
  const reload = () => { setFresh(null); setVersion((v) => v + 1); };
  const rescore = async () => {
    setScoring(true);
    setRescoreFailed(false);
    try {
      setFresh(await rescoreSources(assessmentId));
    } catch {
      setRescoreFailed(true);
    } finally {
      setScoring(false);
    }
  };
  return (
    <>
      <PageHead title={t.title} sub={t.intro} eyebrow={m3.eyebrow}
        crumbs={[{ label: m3.crumbModules, to: "/" }, { label: m3.crumbAssess, to: "/modules/m3_connect" }, { label: t.title }]} />
      {a.data ? <ConnectSteps assessmentId={assessmentId} steps={a.data.steps} /> : null}
      <ScreenState state={m.state} message={m.state === "empty" ? t.empty : m.message} onRetry={m.retry}>
        {data ? (
          <>
            <p><button type="button" className="n-btn" onClick={rescore} disabled={scoring}>{scoring ? t.rescoring : t.rescore}</button></p>
            {rescoreFailed ? <p role="alert" className="state state-error">That could not be scored again. Please try again.</p> : null}
            <Panel title={t.title}>
              <SourceMapChart sources={data.sources} selected={selected} onSelect={setSelected} />
              <Legend />
              <h3>{t.zonesTitle}</h3>
              {ORDER.map((z) => {
                const here = data.sources.filter((s) => s.zone === z);
                return (
                  <section key={z} aria-label={t.zones[z]}>
                    <h4>{t.zones[z]}</h4>
                    {here.length ? (
                      <ul>
                        {here.map((s) => (
                          <li key={s.id}>
                            <button type="button" className="n-btn" onClick={() => setSelected(s.id)}>{s.name}</button>{" "}
                            <span className="n-muted">
                              {[t.kinds[s.kind], s.restricted ? "" : t.measures(s.measures_fed), s.override ? t.moved(s.override.by) : ""].filter(Boolean).join(" · ")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="n-muted">{t.noneInZone}</p>}
                  </section>
                );
              })}
            </Panel>
            {selected ? <SourcePanel assessmentId={assessmentId} sourceId={selected} version={version} onClose={() => setSelected(null)} onMoved={reload} /> : null}
          </>
        ) : null}
      </ScreenState>
      {a.data ? <NiraNext steps={a.data.steps} /> : null}
    </>
  );
}

function Legend() {
  return (
    <div role="group" aria-label={t.legendTitle}>
      <h3>{t.legendTitle}</h3>
      <ul style={{ display: "flex", flexWrap: "wrap", gap: "4px 16px", listStyle: "none", padding: 0 }}>
        {(Object.keys(KIND_FILL) as (keyof typeof KIND_FILL)[]).map((k) => (
          <li key={k}>
            <svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="6" style={{ fill: KIND_FILL[k] }} /></svg> {t.kinds[k]}
          </li>
        ))}
        <li>{t.legendSize}</li>
        <li>{t.legendLock}</li>
        <li>{t.legendMoved}</li>
      </ul>
    </div>
  );
}
