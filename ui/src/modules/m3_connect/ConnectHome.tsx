import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import PageHead from "../../components/PageHead";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../m1_intent/useLoad";
import { listAssessments, startAssessment } from "./api";
import { m3 } from "./copy";

const HOME = "/modules/m3_connect";

function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

/** Module 3's entry: the assessments you have started, and a way to start one from the newest signed baseline. */
export default function ConnectHome() {
  const s = useLoad(listAssessments, "m3-assessments", (d) => d.assessments.length === 0 && !d.signed_baseline);
  const go = useNavigate();
  const [error, setError] = useState("");
  const start = () =>
    startAssessment()
      .then((v) => go(`${HOME}/map/${v.assessment.id}`))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : m3.saveFailed));
  const data = s.data;
  return (
    <>
      <PageHead eyebrow={m3.eyebrow} title={m3.title} sub={m3.intro} crumbs={[{ label: m3.crumbModules, to: "/" }, { label: m3.crumbAssess }]} />
      <ScreenState state={s.state} message={s.state === "empty" ? m3.noBaseline : s.message} onRetry={s.retry}>
        {data ? (
          <>
            <Panel eyebrow={m3.crumbAssess} title={m3.yourAssessments}>
              {data.assessments.length === 0 ? (
                <p className="n-muted">{m3.noAssessments}</p>
              ) : (
                <ul className="m1-list">
                  {data.assessments.map((a) => (
                    <li key={a.id} className="n-flex between wrap">
                      <span>{[a.baseline_label, m3.startedOn(when(a.created_at))].filter(Boolean).join(" · ")}</span>
                      <Link className="n-btn sm" to={`${HOME}/map/${a.id}`}>
                        {m3.open}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            {data.assessments.length === 0 || data.can_start ? (
              <Panel title={data.assessments.length === 0 ? m3.startTitle : m3.startNew}>
                <p className="n-muted">{data.assessments.length === 0 ? m3.startHelp : m3.startNewHelp(data.baseline_label ?? "")}</p>
                <button type="button" className="n-btn primary" onClick={start}>
                  {data.assessments.length === 0 ? m3.start : m3.startNew}
                </button>
                {error ? <p role="alert" className="state state-error">{error}</p> : null}
              </Panel>
            ) : null}
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
